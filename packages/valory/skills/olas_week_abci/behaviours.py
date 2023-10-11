# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains round behaviours of WeekInOlasAbciApp."""

import json
import math
import random
from abc import ABC
from datetime import datetime, timedelta
from typing import Dict, Generator, List, Optional, Set, Tuple, Type, cast

from packages.valory.connections.openai.connection import (
    PUBLIC_ID as LLM_CONNECTION_PUBLIC_ID,
)
from packages.valory.protocols.llm.message import LlmMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.abstract_round_abci.common import RandomnessBehaviour
from packages.valory.skills.abstract_round_abci.models import Requests
from packages.valory.skills.olas_week_abci.ceramic_db import CeramicDB
from packages.valory.skills.olas_week_abci.dialogues import LlmDialogue, LlmDialogues
from packages.valory.skills.olas_week_abci.models import (
    OpenAICalls,
    Params,
    SharedState,
)
from packages.valory.skills.olas_week_abci.payloads import (
    OlasWeekDecisionMakingPayload,
    OlasWeekEvaluationPayload,
    OlasWeekRandomnessPayload,
    OlasWeekSelectKeepersPayload,
    OlasWeekTweetCollectionPayload,
    OpenAICallCheckPayload,
)
from packages.valory.skills.olas_week_abci.prompts import tweet_summarizer_prompt
from packages.valory.skills.olas_week_abci.rounds import (
    ERROR_API_LIMITS,
    ERROR_GENERIC,
    Event,
    OlasWeekDecisionMakingRound,
    OlasWeekEvaluationRound,
    OlasWeekOpenAICallCheckRound,
    OlasWeekRandomnessRound,
    OlasWeekSelectKeepersRound,
    OlasWeekTweetCollectionRound,
    SynchronizedData,
    WeekInOlasAbciApp,
)


ONE_DAY = 86400.0
ADDRESS_REGEX = r"0x[a-fA-F0-9]{40}"
TAGLINE = "I'm linking my wallet to @Autonolas Contribute:"
DEFAULT_TWEET_POINTS = 100
TWEET_QUALITY_TO_POINTS = {"LOW": 1, "AVERAGE": 2, "HIGH": 3}
TWEET_RELATIONSHIP_TO_POINTS = {"LOW": 100, "AVERAGE": 200, "HIGH": 300}
HTTP_OK = 200
HTTP_TOO_MANY_REQUESTS = 429
MAX_TWEET_CHARS = 250  # do not use 280 as not every char counts the same


def extract_headers(header_str: str) -> dict:
    """Extracts HTTP headers"""
    header_separator = "\r\n" if "\r\n" in header_str else "\n"
    headers = [
        header.split(": ") for header in header_str.split(header_separator) if header
    ]
    return {key: value for key, value in headers}


def parse_summary(summary: str) -> list:
    """Parse the tweet summary"""
    if summary.startswith("Summary: "):
        summary = summary.replace("Summary: ", "")

    tweets = []
    for sentence in summary.split("."):
        sentence = sentence.strip()
        while len(sentence) > MAX_TWEET_CHARS:
            tweets.append(sentence[:MAX_TWEET_CHARS])
            sentence = sentence[MAX_TWEET_CHARS:]
        if not tweets:
            tweets.append(sentence)

    return tweets


class OlasWeekBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @property
    def openai_calls(self) -> OpenAICalls:
        """Return the params."""
        return self.params.openai_calls

    def _check_twitter_limits(self) -> Tuple:
        """Check if the daily limit has exceeded or not"""
        try:
            number_of_tweets_pulled_today = int(
                self.synchronized_data.ceramic_db["module_data"]["twitter"][
                    "number_of_tweets_pulled_today"
                ]
            )
            last_tweet_pull_window_reset = float(
                self.synchronized_data.ceramic_db["module_data"]["twitter"][
                    "last_tweet_pull_window_reset"
                ]
            )
        except KeyError:
            number_of_tweets_pulled_today = 0
            last_tweet_pull_window_reset = cast(
                SharedState, self.context.state
            ).round_sequence.last_round_transition_timestamp.timestamp()

        current_time = cast(
            SharedState, self.context.state
        ).round_sequence.last_round_transition_timestamp.timestamp()

        # 15 min window limit
        if self.synchronized_data.sleep_until:
            time_window_close = self.synchronized_data.sleep_until
            if current_time < time_window_close:
                return True, 0, current_time

        # Window has expired
        if current_time >= last_tweet_pull_window_reset + ONE_DAY:
            return False, 0, current_time

        # Reached max number of tweets
        if number_of_tweets_pulled_today >= self.params.max_tweet_pulls_allowed:
            return True, number_of_tweets_pulled_today, last_tweet_pull_window_reset

        # Window has not expired and we have not reached the max number of tweets
        return False, number_of_tweets_pulled_today, last_tweet_pull_window_reset


class OlasWeekRandomnessBehaviour(RandomnessBehaviour):
    """Retrieve randomness."""

    matching_round = OlasWeekRandomnessRound
    payload_class = OlasWeekRandomnessPayload


class OlasWeekSelectKeepersBehaviour(OlasWeekBaseBehaviour):
    """Select the keeper agent."""

    matching_round = OlasWeekSelectKeepersRound
    payload_class = OlasWeekSelectKeepersPayload

    def _select_keepers(self) -> List[str]:
        """
        Select new keepers randomly.

        1. Sort the list of participants who are not blacklisted as keepers.
        2. Randomly shuffle it.
        3. Pick the first keepers in order.
        4. If they have already been selected, pick the next ones.

        :return: the selected keepers' addresses.
        """
        # Get all the participants who have not been blacklisted as keepers
        non_blacklisted = (
            self.synchronized_data.participants
            - self.synchronized_data.blacklisted_keepers
        )
        if not non_blacklisted:
            raise RuntimeError(
                "Cannot continue if all the keepers have been blacklisted!"
            )

        # Sorted list of participants who are not blacklisted as keepers
        relevant_set = sorted(list(non_blacklisted))

        needed_keepers = math.ceil(
            self.synchronized_data.nb_participants / 2
        )  # half or 1

        # Check if we need random selection
        if len(relevant_set) <= needed_keepers:
            keeper_addresses = list(relevant_set)
            self.context.logger.info(f"Selected new keepers: {keeper_addresses}.")
            return keeper_addresses

        # Random seeding and shuffling of the set
        random.seed(self.synchronized_data.keeper_randomness)
        random.shuffle(relevant_set)

        # If the keeper is not set yet, pick the first address
        keeper_addresses = relevant_set[0:2]

        # If the keepers have been already set, select the next ones.
        if (
            self.synchronized_data.are_keepers_set
            and len(self.synchronized_data.participants) > 2
        ):
            old_keeper_index = relevant_set.index(
                self.synchronized_data.most_voted_keeper_addresses[0]
            )
            keeper_addresses = [
                relevant_set[
                    (old_keeper_index + 2) % len(relevant_set)
                ],  # skip the previous 2
                relevant_set[(old_keeper_index + 3) % len(relevant_set)],
            ]

        self.context.logger.info(f"Selected new keepers: {keeper_addresses}.")

        return keeper_addresses

    def async_act(self) -> Generator:
        """
        Do the action.

        Steps:
        - Select a keeper randomly.
        - Send the transaction with the keeper and wait for it to be mined.
        - Wait until ABCI application transitions to the next round.
        - Go to the next behaviour state (set done event).
        """

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            payload = OlasWeekSelectKeepersPayload(  # type: ignore
                self.context.agent_address,
                json.dumps(self._select_keepers(), sort_keys=True),
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class OlasWeekDecisionMakingBehaviour(OlasWeekBaseBehaviour):
    """OlasWeekDecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = OlasWeekDecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            event = self.get_next_event()
            self.context.logger.info(f"Next event: {event}")

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(
                payload=OlasWeekDecisionMakingPayload(
                    sender=self.context.agent_address,
                    event=event,
                )
            )
            yield from self.wait_until_round_end()
        self.set_done()

    def get_next_event(self) -> str:
        """Decide what is the next round"""

        performed_tasks = self.synchronized_data.performed_olas_week_tasks

        self.context.logger.info(f"Performed tasks: {performed_tasks}")

        if Event.OPENAI_CALL_CHECK.value not in performed_tasks:
            return Event.OPENAI_CALL_CHECK.value

        if performed_tasks[Event.OPENAI_CALL_CHECK.value] == Event.NO_ALLOWANCE.value:
            return Event.DONE_SKIP.value

        if Event.SELECT_KEEPERS.value not in performed_tasks:
            return Event.SELECT_KEEPERS.value

        if Event.RETRIEVE_TWEETS.value not in performed_tasks:
            return Event.RETRIEVE_TWEETS.value

        if Event.EVALUATE.value not in performed_tasks:
            return Event.EVALUATE.value

        return Event.DONE.value


class OpenAICallCheckBehaviour(OlasWeekBaseBehaviour):
    """OlasWeekTweetCollectionBehaviour"""

    matching_round: Type[AbstractRound] = OlasWeekOpenAICallCheckRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            current_time = cast(
                SharedState, self.context.state
            ).round_sequence.last_round_transition_timestamp.timestamp()
            # Reset the window if the window expired before checking
            self.openai_calls.reset(current_time=current_time)
            if self.openai_calls.max_calls_reached():
                content = None
            else:
                content = OlasWeekOpenAICallCheckRound.CALLS_REMAINING
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(
                payload=OpenAICallCheckPayload(
                    sender=self.context.agent_address,
                    content=content,
                )
            )
            yield from self.wait_until_round_end()
        self.set_done()


class OlasWeekTweetCollectionBehaviour(OlasWeekBaseBehaviour):
    """OlasWeekTweetCollectionBehaviour"""

    matching_round: Type[AbstractRound] = OlasWeekTweetCollectionRound

    def _i_am_not_sending(self) -> bool:
        """Indicates if the current agent is one of the sender or not."""
        return (
            self.context.agent_address
            not in self.synchronized_data.most_voted_keeper_addresses
        )

    def async_act(self) -> Generator[None, None, None]:
        """
        Do the action.

        Steps:
        - If the agent is the keeper, then prepare the transaction and send it.
        - Otherwise, wait until the next round.
        - If a timeout is hit, set exit A event, otherwise set done event.
        """
        if self._i_am_not_sending():
            yield from self._not_sender_act()
        else:
            yield from self._sender_act()

    def _not_sender_act(self) -> Generator:
        """Do the non-sender action."""
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            self.context.logger.info(
                f"Waiting for the keeper to do its keeping: keepers={self.synchronized_data.most_voted_keeper_addresses}, me={self.context.agent_address}"
            )
            yield from self.wait_until_round_end()
        self.set_done()

    def _sender_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            self.context.logger.info("I am a keeper")

            (
                has_limit_reached,
                number_of_tweets_pulled_today,
                last_tweet_pull_window_reset,
            ) = self._check_twitter_limits()

            if has_limit_reached:
                self.context.logger.info(
                    "Cannot retrieve tweets, max number of tweets reached for today or 15-min request amount reached"
                )
                payload_data = {
                    "tweets": None,
                    "error": ERROR_API_LIMITS,
                    "number_of_tweets_pulled_today": number_of_tweets_pulled_today,
                    "sleep_until": self.synchronized_data.sleep_until,
                }

            else:
                # Get mentions from Twitter
                payload_data = yield from self._get_twitter_mentions(
                    number_of_tweets_pulled_today=number_of_tweets_pulled_today
                )

            payload_data["last_tweet_pull_window_reset"] = last_tweet_pull_window_reset
            sender = self.context.agent_address
            payload = OlasWeekTweetCollectionPayload(
                sender=sender, content=json.dumps(payload_data, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _get_twitter_mentions(
        self,
        number_of_tweets_pulled_today: int,
    ) -> Generator[None, None, Dict]:
        """Get Twitter mentions"""

        api_base = self.params.twitter_api_base
        api_endpoint = self.params.twitter_tweets_args

        number_of_tweets_remaining_today = (
            self.params.max_tweet_pulls_allowed - number_of_tweets_pulled_today
        )
        if number_of_tweets_remaining_today <= 0:
            self.context.logger.info(
                "Cannot retrieve twitter mentions, max number of tweets reached for today"
            )
            return {
                "tweets": None,
                "error": ERROR_API_LIMITS,
                "number_of_tweets_pulled_today": number_of_tweets_pulled_today,
                "sleep_until": self.synchronized_data.sleep_until,
            }

        # Calculate the starting time (7 days ago)
        now_ts = cast(
            SharedState, self.context.state
        ).round_sequence.last_round_transition_timestamp.timestamp()

        start_time = datetime.fromtimestamp(now_ts) - timedelta(days = 7)

        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S:00Z")

        # Build the args
        api_args = self.params.twitter_tweets_args.replace(
            "{start_time}", start_time_str
        )
        api_args = api_args.replace(
            "{max_results}", str(number_of_tweets_remaining_today)
        )
        api_url = api_base + api_endpoint + api_args
        headers = dict(Authorization=f"Bearer {self.params.twitter_api_bearer_token}")

        self.context.logger.info(
            f"Retrieving tweets from Twitter API [{api_url}]\nBearer token {self.params.twitter_api_bearer_token[:5]}*******{self.params.twitter_api_bearer_token[-5:]}"
        )

        tweets = {}
        next_token = None

        # Pagination loop: we read a max of <twitter_max_pages> pages each period
        # Each page contains 100 tweets. The default value for twitter_max_pages is 10
        for _ in range(self.params.twitter_max_pages):
            self.context.logger.info(
                f"Retrieving a new page. max_pages={self.params.twitter_max_pages}"
            )
            url = api_url
            # Add the pagination token if it exists
            if next_token:
                url += f"&pagination_token={next_token}"

            # Make the request
            response = yield from self.get_http_response(
                method="GET", url=url, headers=headers
            )

            # Check response status
            if response.status_code != 200:
                header_dict = extract_headers(response.headers)

                remaining, limit, reset_ts = [
                    header_dict.get(header, "?")
                    for header in [
                        "x-rate-limit-remaining",
                        "x-rate-limit-limit",
                        "x-rate-limit-reset",
                    ]
                ]
                reset = (
                    datetime.fromtimestamp(int(reset_ts)).strftime("%Y-%m-%d %H:%M:%S")
                    if reset_ts != "?"
                    else None
                )

                self.context.logger.error(
                    f"Error retrieving mentions from Twitter [{response.status_code}]: {response.body}"
                    f"API limits: {remaining}/{limit}. Window reset: {reset}"
                )

                return {
                    "tweets": None,
                    "error": ERROR_API_LIMITS
                    if response.status_code == HTTP_TOO_MANY_REQUESTS
                    else ERROR_GENERIC,
                    "number_of_tweets_pulled_today": number_of_tweets_pulled_today,
                    "sleep_until": reset_ts
                    if response.status_code == HTTP_TOO_MANY_REQUESTS
                    else self.synchronized_data.sleep_until,
                }

            api_data = json.loads(response.body)

            # Check the meta field
            if "meta" not in api_data:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'meta' field: {api_data!r}"
                )
                return {
                    "tweets": None,
                    "error": ERROR_GENERIC,
                    "number_of_tweets_pulled_today": number_of_tweets_pulled_today,
                    "sleep_until": None,  # we reset this on a successful request
                }

            # Check if there are no more results
            if (
                "result_count" in api_data["meta"]
                and int(api_data["meta"]["result_count"]) == 0
            ):
                break

            # Check that the data exists
            if "data" not in api_data or "newest_id" not in api_data["meta"]:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'meta' field: {api_data!r}"
                )
                return {
                    "tweets": None,
                    "error": ERROR_GENERIC,
                    "number_of_tweets_pulled_today": number_of_tweets_pulled_today,
                    "sleep_until": None,  # we reset this on a successful request
                }

            if "includes" not in api_data or "users" not in api_data["includes"]:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'includes/users' field: {api_data!r}"
                )
                return {
                    "tweets": None,
                    "error": ERROR_GENERIC,
                    "number_of_tweets_pulled_today": number_of_tweets_pulled_today,
                    "sleep_until": None,  # we reset this on a successful request
                }

            # Add the retrieved tweets
            for tweet in api_data["data"]:
                tweets[tweet["id"]] = tweet

                # Set the author handle
                for user in api_data["includes"]["users"]:
                    if user["id"] == tweet["author_id"]:
                        tweets[tweet["id"]]["username"] = user["username"]
                        break
                number_of_tweets_pulled_today += 1

            if "next_token" in api_data["meta"]:
                next_token = api_data["meta"]["next_token"]
                continue

            break

        self.context.logger.info(
            f"Got {len(tweets)} new tweets"
        )

        return {
            "tweets": tweets,
            "number_of_tweets_pulled_today": number_of_tweets_pulled_today,
            "sleep_until": None,  # we reset this on a successful request
        }


class OlasWeekEvaluationBehaviour(OlasWeekBaseBehaviour):
    """OlasWeekEvaluationBehaviour"""

    matching_round: Type[AbstractRound] = OlasWeekEvaluationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            text = "\n\n".join([f"tweet_{i}: {tweet}" for i, tweet in enumerate(self.synchronized_data.weekly_tweets)])

            summary_tweets = yield from self.evaluate_summary(
                text
            )

            sender = self.context.agent_address
            payload = OlasWeekEvaluationPayload(
                sender=sender, content=json.dumps({"summary_tweets": summary_tweets}, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def evaluate_summary(self, text: str) -> Generator[None, None, list]:
        """Create the tweet summary using a LLM."""

        self.context.logger.info(f"Summarizing text: {text}")

        llm_dialogues = cast(LlmDialogues, self.context.llm_dialogues)

        # llm request message
        request_llm_message, llm_dialogue = llm_dialogues.create(
            counterparty=str(LLM_CONNECTION_PUBLIC_ID),
            performative=LlmMessage.Performative.REQUEST,
            prompt_template=tweet_summarizer_prompt.replace("{user_tweets}", text),
            prompt_values={},
        )
        request_llm_message = cast(LlmMessage, request_llm_message)
        llm_dialogue = cast(LlmDialogue, llm_dialogue)
        llm_response_message = yield from self._do_request(
            request_llm_message, llm_dialogue
        )
        data = llm_response_message.value
        self.openai_calls.increase_call_count()
        self.context.logger.info(f"Got summary: {repr(data)}")
        summary = parse_summary(data)
        return summary

    def _do_request(
        self,
        llm_message: LlmMessage,
        llm_dialogue: LlmDialogue,
        timeout: Optional[float] = None,
    ) -> Generator[None, None, LlmMessage]:
        """
        Do a request and wait the response, asynchronously.

        :param llm_message: The request message
        :param llm_dialogue: the HTTP dialogue associated to the request
        :param timeout: seconds to wait for the reply.
        :yield: LLMMessage object
        :return: the response message
        """
        self.context.outbox.put_message(message=llm_message)
        request_nonce = self._get_request_nonce_from_dialogue(llm_dialogue)
        cast(Requests, self.context.requests).request_id_to_callback[
            request_nonce
        ] = self.get_callback_request()
        # notify caller by propagating potential timeout exception.
        response = yield from self.wait_for_message(timeout=timeout)
        return response


class OlasWeekRoundBehaviour(AbstractRoundBehaviour):
    """OlasWeekRoundBehaviour"""

    initial_behaviour_cls = OlasWeekTweetCollectionBehaviour
    abci_app_cls = WeekInOlasAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        OlasWeekDecisionMakingBehaviour,
        OpenAICallCheckBehaviour,
        OlasWeekTweetCollectionBehaviour,
        OlasWeekEvaluationBehaviour,
        OlasWeekRandomnessBehaviour,
        OlasWeekSelectKeepersBehaviour,
    ]
