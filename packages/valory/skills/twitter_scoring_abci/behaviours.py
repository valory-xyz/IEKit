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

"""This package contains round behaviours of TwitterScoringAbciApp."""

import json
import random
import re
from abc import ABC
from datetime import datetime
from typing import Dict, Generator, List, Optional, Set, Tuple, Type, cast

from web3 import Web3

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
from packages.valory.skills.llm_abci.payloads import SelectKeeperPayload
from packages.valory.skills.twitter_scoring_abci.ceramic_db import CeramicDB
from packages.valory.skills.twitter_scoring_abci.dialogues import (
    LlmDialogue,
    LlmDialogues,
)
from packages.valory.skills.twitter_scoring_abci.models import (
    OpenAICalls,
    Params,
    SharedState,
)
from packages.valory.skills.twitter_scoring_abci.payloads import (
    DBUpdatePayload,
    OpenAICallCheckPayload,
    TweetEvaluationPayload,
    TwitterDecisionMakingPayload,
    TwitterHashtagsCollectionPayload,
    TwitterMentionsCollectionPayload,
    TwitterRandomnessPayload,
    TwitterSelectKeeperPayload,
)
from packages.valory.skills.twitter_scoring_abci.prompts import tweet_evaluation_prompt
from packages.valory.skills.twitter_scoring_abci.rounds import (
    DBUpdateRound,
    Event,
    OpenAICallCheckRound,
    SynchronizedData,
    TweetEvaluationRound,
    TwitterDecisionMakingRound,
    TwitterHashtagsCollectionRound,
    TwitterMentionsCollectionRound,
    TwitterRandomnessRound,
    TwitterScoringAbciApp,
    TwitterSelectKeeperRound,
)


ONE_DAY = 86400.0
ADDRESS_REGEX = r"0x[a-fA-F0-9]{40}"
TAGLINE = "I'm linking my wallet to @Autonolas Contribute:"
DEFAULT_TWEET_POINTS = 100
TWEET_QUALITY_TO_POINTS = {"LOW": 1, "AVERAGE": 2, "HIGH": 3}
TWEET_RELATIONSHIP_TO_POINTS = {"LOW": 100, "AVERAGE": 200, "HIGH": 300}


class TwitterScoringBaseBehaviour(BaseBehaviour, ABC):
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

    def _check_daily_limit(self) -> Tuple:
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

        # Window has expired
        if current_time >= last_tweet_pull_window_reset + ONE_DAY:
            return False, 0, current_time

        # Reached max number of tweets
        if number_of_tweets_pulled_today >= self.params.max_tweet_pulls_allowed:
            return True, number_of_tweets_pulled_today, last_tweet_pull_window_reset

        # Window has not expired and we have not reached the max number of tweets
        return False, number_of_tweets_pulled_today, last_tweet_pull_window_reset


class TwitterRandomnessBehaviour(RandomnessBehaviour):
    """Retrieve randomness."""

    matching_round = TwitterRandomnessRound
    payload_class = TwitterRandomnessPayload


class TwitterSelectKeeperBehaviour(TwitterScoringBaseBehaviour):
    """Select the keeper agent."""

    matching_round = TwitterSelectKeeperRound
    payload_class = TwitterSelectKeeperPayload

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
            payload = TwitterSelectKeeperPayload(  # type: ignore
                self.context.agent_address, self._select_keepers()
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class TwitterDecisionMakingBehaviour(TwitterScoringBaseBehaviour):
    """TwitterDecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = TwitterDecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            event = self.get_next_event()
            self.context.logger.info(f"Next event: {event}")

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(
                payload=TwitterDecisionMakingPayload(
                    sender=self.context.agent_address,
                    event=event,
                )
            )
            yield from self.wait_until_round_end()
        self.set_done()

    def get_next_event(self) -> str:
        """Decide what is the next round"""

        performed_tasks = self.synchronized_data.performed_twitter_tasks

        self.context.logger.info(f"Performed tasks: {performed_tasks}")

        if Event.OPENAI_CALL_CHECK.value not in performed_tasks:
            return Event.OPENAI_CALL_CHECK.value

        if performed_tasks[Event.OPENAI_CALL_CHECK.value] == Event.NO_ALLOWANCE.value:
            return Event.DONE_SKIP.value

        if Event.SELECT_KEEPERS.value not in performed_tasks:
            return Event.SELECT_KEEPERS.value

        if Event.RETRIEVE_HASHTAGS.value not in performed_tasks:
            return Event.RETRIEVE_HASHTAGS.value

        if Event.RETRIEVE_MENTIONS.value not in performed_tasks:
            return Event.RETRIEVE_MENTIONS.value

        if Event.EVALUATE.value not in performed_tasks:
            return Event.EVALUATE.value

        if Event.DB_UPDATE.value not in performed_tasks:
            return Event.DB_UPDATE.value

        return Event.DONE.value


class OpenAICallCheckBehaviour(TwitterScoringBaseBehaviour):
    """TwitterMentionsCollectionBehaviour"""

    matching_round: Type[AbstractRound] = OpenAICallCheckRound

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
                content = OpenAICallCheckRound.CALLS_REMAINING
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(
                payload=OpenAICallCheckPayload(
                    sender=self.context.agent_address,
                    content=content,
                )
            )
            yield from self.wait_until_round_end()
        self.set_done()


class TwitterMentionsCollectionBehaviour(TwitterScoringBaseBehaviour):
    """TwitterMentionsCollectionBehaviour"""

    matching_round: Type[AbstractRound] = TwitterMentionsCollectionRound

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
                f"Waiting for the keeper to do its keeping: {self.synchronized_data.most_voted_keeper_address}"
            )
            yield from self.wait_until_round_end()
        self.set_done()

    def _sender_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            (
                has_limit_reached,
                number_of_tweets_pulled_today,
                last_tweet_pull_window_reset,
            ) = self._check_daily_limit()

            if has_limit_reached:
                self.context.logger.info(
                    "Cannot retrieve tweets, max number of tweets reached for today"
                )
                payload_data = TwitterMentionsCollectionRound.ERROR_PAYLOAD
            else:
                # Get mentions from Twitter
                (
                    tweets,
                    latest_mention_tweet_id,
                    number_of_tweets_pulled_today,
                ) = yield from self._get_twitter_mentions(
                    number_of_tweets_pulled_today=number_of_tweets_pulled_today
                )

                if tweets == TwitterMentionsCollectionRound.ERROR_PAYLOAD:
                    payload_data = TwitterMentionsCollectionRound.ERROR_PAYLOAD
                else:
                    self.context.logger.info(
                        f"Retrieved new mentions [until_id={latest_mention_tweet_id}]: {list(tweets.keys())}"
                    )
                    payload_data = {
                        "tweets": tweets,
                        "latest_mention_tweet_id": latest_mention_tweet_id,
                        "number_of_tweets_pulled_today": number_of_tweets_pulled_today,
                        "last_tweet_pull_window_reset": last_tweet_pull_window_reset,
                    }

            sender = self.context.agent_address
            payload = TwitterMentionsCollectionPayload(
                sender=sender, content=json.dumps(payload_data, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _get_twitter_mentions(
        self,
        number_of_tweets_pulled_today: int,
    ) -> Generator[None, None, Tuple[Dict, Optional[int], int]]:
        """Get Twitter mentions"""

        api_base = self.params.twitter_api_base
        api_endpoint = self.params.twitter_mentions_endpoint
        try:
            latest_mention_tweet_id = int(
                self.synchronized_data.ceramic_db["module_data"]["twitter"][
                    "latest_mention_tweet_id"
                ]
            )
        except KeyError:
            latest_mention_tweet_id = 0

        number_of_tweets_remaining_today = (
            self.params.max_tweet_pulls_allowed - number_of_tweets_pulled_today
        )
        if number_of_tweets_remaining_today <= 0:
            self.context.logger.info(
                "Cannot retrieve twitter mentions, max number of tweets reached for today"
            )
            return (
                TwitterMentionsCollectionRound.ERROR_PAYLOAD,
                None,
                number_of_tweets_pulled_today,
            )

        next_tweet_id = (
            int(latest_mention_tweet_id) + 1 if int(latest_mention_tweet_id) != 0 else 0
        )
        api_args = self.params.twitter_mentions_args.replace(
            "{since_id}", str(next_tweet_id)
        )
        api_args = api_args.replace(
            "{max_results}", str(number_of_tweets_remaining_today)
        )
        api_url = api_base + api_endpoint + api_args
        headers = dict(Authorization=f"Bearer {self.params.twitter_api_bearer_token}")

        self.context.logger.info(
            f"Retrieving mentions from Twitter API [{api_url}]\nBearer token {self.params.twitter_api_bearer_token[:5]}*******{self.params.twitter_api_bearer_token[-5:]}"
        )

        tweets = {}
        next_token = None
        latest_tweet_id = None

        # Pagination loop: we read a max of <twitter_max_pages> pages each period
        # Each page contains 100 tweets. The default value for twitter_max_pages is 10
        for _ in range(self.params.twitter_max_pages):
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
                self.context.logger.error(
                    f"Error retrieving mentions from Twitter [{response.status_code}]: {response.body}"
                )
                return (
                    TwitterMentionsCollectionRound.ERROR_PAYLOAD,
                    None,
                    number_of_tweets_pulled_today,
                )

            api_data = json.loads(response.body)

            # Check the meta field
            if "meta" not in api_data:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'meta' field: {api_data!r}"
                )
                return (
                    TwitterMentionsCollectionRound.ERROR_PAYLOAD,
                    None,
                    number_of_tweets_pulled_today,
                )

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
                return (
                    TwitterMentionsCollectionRound.ERROR_PAYLOAD,
                    None,
                    number_of_tweets_pulled_today,
                )

            if "includes" not in api_data or "users" not in api_data["includes"]:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'includes/users' field: {api_data!r}"
                )
                return (
                    TwitterMentionsCollectionRound.ERROR_PAYLOAD,
                    None,
                    number_of_tweets_pulled_today,
                )

            # Add the retrieved tweets
            for tweet in api_data["data"]:
                tweets[tweet["id"]] = tweet

                # Set the author handle
                for user in api_data["includes"]["users"]:
                    if user["id"] == tweet["author_id"]:
                        tweets[tweet["id"]]["username"] = user["username"]
                        break
                number_of_tweets_pulled_today += 1
            latest_tweet_id = int(api_data["meta"]["newest_id"])

            if "next_token" in api_data["meta"]:
                next_token = api_data["meta"]["next_token"]
                continue

            break

        self.context.logger.info(
            f"Got {len(tweets)} new mentions until tweet_id={latest_tweet_id}"
        )

        return tweets, latest_tweet_id, number_of_tweets_pulled_today


class TwitterHashtagsCollectionBehaviour(TwitterScoringBaseBehaviour):
    """TwitterHashtagsCollectionBehaviour"""

    matching_round: Type[AbstractRound] = TwitterHashtagsCollectionRound

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
                f"Waiting for the keeper to do its keeping: {self.synchronized_data.most_voted_keeper_address}"
            )
            yield from self.wait_until_round_end()
        self.set_done()

    def _sender_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            (
                has_limit_reached,
                number_of_tweets_pulled_today,
                last_tweet_pull_window_reset,
            ) = self._check_daily_limit()

            if has_limit_reached:
                self.context.logger.info(
                    "Cannot retrieve tweets, max number of tweets reached for today"
                )
                payload_data = TwitterMentionsCollectionRound.ERROR_PAYLOAD
            else:
                # Get hashtags from Twitter
                (
                    tweets,
                    latest_hashtag_tweet_id,
                    number_of_tweets_pulled_today,
                ) = yield from self._get_twitter_hashtag_search(
                    number_of_tweets_pulled_today=number_of_tweets_pulled_today
                )

                if tweets == TwitterMentionsCollectionRound.ERROR_PAYLOAD:
                    payload_data = TwitterMentionsCollectionRound.ERROR_PAYLOAD
                else:
                    self.context.logger.info(
                        f"Retrieved new hashtags [until_id={latest_hashtag_tweet_id}]: {list(tweets.keys())}"
                    )
                    payload_data = {
                        "tweets": tweets,
                        "latest_hashtag_tweet_id": latest_hashtag_tweet_id,
                        "number_of_tweets_pulled_today": number_of_tweets_pulled_today,
                        "last_tweet_pull_window_reset": last_tweet_pull_window_reset,
                    }

            sender = self.context.agent_address
            payload = TwitterHashtagsCollectionPayload(
                sender=sender, content=json.dumps(payload_data, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _get_twitter_hashtag_search(
        self,
        number_of_tweets_pulled_today: int,
    ) -> Generator[None, None, Tuple[Dict, Optional[int], int]]:
        """Get registrations from Twitter"""

        api_base = self.params.twitter_api_base
        api_endpoint = self.params.twitter_search_endpoint
        try:
            latest_hashtag_tweet_id = int(
                self.synchronized_data.ceramic_db["module_data"]["twitter"][
                    "latest_hashtag_tweet_id"
                ]
            )
        except KeyError:
            latest_hashtag_tweet_id = 0

        number_of_tweets_remaining_today = (
            self.params.max_tweet_pulls_allowed - number_of_tweets_pulled_today
        )
        if number_of_tweets_remaining_today <= 0:
            self.context.logger.info(
                "Cannot retrieve hashtag mentions, max number of tweets reached for today"
            )
            return (
                TwitterMentionsCollectionRound.ERROR_PAYLOAD,
                None,
                number_of_tweets_pulled_today,
            )

        next_tweet_id = (
            int(latest_hashtag_tweet_id) + 1 if int(latest_hashtag_tweet_id) != 0 else 0
        )
        api_args = self.params.twitter_search_args.replace(
            "{since_id}", str(next_tweet_id)
        )
        api_args = api_args.replace(
            "{max_results}", str(number_of_tweets_remaining_today)
        )
        api_url = api_base + api_endpoint + api_args
        headers = dict(Authorization=f"Bearer {self.params.twitter_api_bearer_token}")

        self.context.logger.info(f"Retrieving hashes from Twitter API [{api_url}]")

        next_token = None
        latest_tweet_id = None
        retrieved_tweets = 0
        tweets = {}
        # Pagination loop: we read a max of <twitter_max_pages> pages each period
        # Each page contains 100 tweets. The default value for twitter_max_pages is 10
        for _ in range(self.params.twitter_max_pages):

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
                self.context.logger.error(
                    f"Error retrieving mentions from Twitter [{response.status_code}]"
                )
                return (
                    TwitterMentionsCollectionRound.ERROR_PAYLOAD,
                    None,
                    number_of_tweets_pulled_today,
                )

            api_data = json.loads(response.body)

            # Check the meta field
            if "meta" not in api_data:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'meta' field: {api_data!r}"
                )
                return (
                    TwitterMentionsCollectionRound.ERROR_PAYLOAD,
                    None,
                    number_of_tweets_pulled_today,
                )

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
                return (
                    TwitterMentionsCollectionRound.ERROR_PAYLOAD,
                    None,
                    number_of_tweets_pulled_today,
                )

            if "includes" not in api_data or "users" not in api_data["includes"]:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'includes/users' field: {api_data!r}"
                )
                return (
                    TwitterMentionsCollectionRound.ERROR_PAYLOAD,
                    None,
                    number_of_tweets_pulled_today,
                )

            # Add the retrieved tweets
            for tweet in api_data["data"]:
                retrieved_tweets += 1
                if tweet["id"] not in tweets:  # avoids duplicated tweets
                    tweets[tweet["id"]] = tweet

                    # Set the author handle
                    for user in api_data["includes"]["users"]:
                        if user["id"] == tweet["author_id"]:
                            tweets[tweet["id"]]["username"] = user["username"]
                            break
                number_of_tweets_pulled_today += 1
            latest_tweet_id = int(api_data["meta"]["newest_id"])

            if "next_token" in api_data["meta"]:
                next_token = api_data["meta"]["next_token"]
                continue

            break

        self.context.logger.info(
            f"Got {retrieved_tweets} new hashtag tweets until tweet_id={latest_tweet_id}"
        )

        return tweets, latest_tweet_id, number_of_tweets_pulled_today


class TweetEvaluationBehaviour(TwitterScoringBaseBehaviour):
    """TweetEvaluationBehaviour"""

    matching_round: Type[AbstractRound] = TweetEvaluationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            tweet_id_to_points = {}
            for tweet_id, tweet in self.synchronized_data.tweets.items():
                if "points" in tweet:
                    # Already scored previously
                    continue
                tweet_id_to_points[tweet_id] = yield from self.evaluate_tweet(
                    tweet["text"]
                )

            sender = self.context.agent_address
            payload = TweetEvaluationPayload(
                sender=sender, content=json.dumps(tweet_id_to_points, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def evaluate_tweet(self, text: str) -> Generator[None, None, int]:
        """Evaluate the tweet through a LLM."""

        self.context.logger.info(f"Evaluating tweet: {text}")

        llm_dialogues = cast(LlmDialogues, self.context.llm_dialogues)

        # llm request message
        request_llm_message, llm_dialogue = llm_dialogues.create(
            counterparty=str(LLM_CONNECTION_PUBLIC_ID),
            performative=LlmMessage.Performative.REQUEST,
            prompt_template=tweet_evaluation_prompt.replace("{user_text}", text),
            prompt_values={},
        )
        request_llm_message = cast(LlmMessage, request_llm_message)
        llm_dialogue = cast(LlmDialogue, llm_dialogue)
        llm_response_message = yield from self._do_request(
            request_llm_message, llm_dialogue
        )
        data = llm_response_message.value
        self.openai_calls.increase_call_count()
        self.context.logger.info(f"Got tweet evaluation: {repr(data)}")

        points = DEFAULT_TWEET_POINTS
        try:
            data = parse_evaluation(data)
            quality = data["quality"]
            relationship = data["relationship"]
            if (
                quality not in TWEET_QUALITY_TO_POINTS
                or relationship not in TWEET_RELATIONSHIP_TO_POINTS
            ):
                self.context.logger.error("Evaluation data is not valid: key not valid")
            else:
                points = (
                    TWEET_QUALITY_TO_POINTS[quality]
                    * TWEET_RELATIONSHIP_TO_POINTS[relationship]
                )
        except Exception as e:
            self.context.logger.error(f"Evaluation data is not valid: exception {e}")

        self.context.logger.info(f"Points: {points}")
        return points

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


def parse_evaluation(data: str) -> Dict:
    """Parse the data from the LLM"""
    start = data.find("{")
    end = data.find("}")
    sub_string = data[start : end + 1]
    return json.loads(sub_string)


class DBUpdateBehaviour(TwitterScoringBaseBehaviour):
    """DBUpdateBehaviour"""

    matching_round: Type[AbstractRound] = DBUpdateRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            ceramic_db = self.update_ceramic_db()

            sender = self.context.agent_address
            payload = DBUpdatePayload(
                sender=sender, content=json.dumps(ceramic_db, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def update_ceramic_db(self) -> Dict:
        """Calculate the new content of the DB"""

        tweets = self.synchronized_data.tweets
        latest_mention_tweet_id = self.synchronized_data.latest_mention_tweet_id
        latest_hashtag_tweet_id = self.synchronized_data.latest_hashtag_tweet_id
        number_of_tweets_pulled_today = (
            self.synchronized_data.number_of_tweets_pulled_today
        )
        last_tweet_pull_window_reset = (
            self.synchronized_data.last_tweet_pull_window_reset
        )

        # Instantiate the db
        ceramic_db = CeramicDB(self.synchronized_data.ceramic_db, self.context.logger)

        # Have we changed scoring period?
        now = cast(
            SharedState, self.context.state
        ).round_sequence.last_round_transition_timestamp.timestamp()

        today = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        current_period = ceramic_db.data["module_data"]["twitter"]["current_period"]
        is_period_changed = today != current_period
        if is_period_changed:
            self.context.logger.info(
                f"Scoring period has changed from {current_period} to {today}"
            )
        period_reset_users = set()

        # Update data
        for tweet in tweets.values():

            self.context.logger.info(f"Updating db with tweet: {tweet}")

            author_id = tweet["author_id"]
            twitter_name = tweet["username"]
            new_points = tweet["points"]
            wallet_address = self.get_registration(tweet["text"])

            # Check this user's point limit per period
            user, _ = ceramic_db.get_user_by_field("twitter_id", tweet["author_id"])

            if not user:
                # New user
                period_reset_users.add(tweet["author_id"])
                current_period_points = 0
            else:
                if is_period_changed and user["twitter_id"] not in period_reset_users:
                    # Existing user, not reset yet
                    period_reset_users.add(user["twitter_id"])
                    current_period_points = 0
                else:
                    # Existing user, already reset
                    current_period_points = user["current_period_points"]

            if current_period_points + new_points > self.params.max_points_per_period:
                self.context.logger.info(
                    f"User {author_id} has surpassed the max points per period: new_points={new_points} current_period_points={current_period_points}, max_points_per_period={self.params.max_points_per_period}"
                )
                new_points = self.params.max_points_per_period - current_period_points
                self.context.logger.info(f"Updated points for this tweet: {new_points}")

            current_period_points += new_points

            # User data to update
            user_data = {
                "points": int(new_points),
                "twitter_handle": twitter_name,
                "current_period_points": int(current_period_points),
            }

            # If this is a registration
            if wallet_address:
                self.context.logger.info(
                    f"Detected a Twitter registration for @{twitter_name}: {wallet_address}. Tweet: {tweet['text']}"
                )
                user_data["wallet_address"] = wallet_address

            # For existing users, all existing user data is replaced except points, which are added
            ceramic_db.update_or_create_user("twitter_id", author_id, user_data)

        # If a user has first contributed to one module (i.e. twitter) without registering a wallet,
        # and later he/she contributes to another module, it could happen that we have two different
        # entries on the database
        ceramic_db.merge_by_wallet()

        # Update the latest_hashtag_tweet_id
        ceramic_db.data["module_data"]["twitter"]["latest_hashtag_tweet_id"] = str(
            latest_hashtag_tweet_id
        )
        # Update the latest_mention_tweet_id
        ceramic_db.data["module_data"]["twitter"]["latest_mention_tweet_id"] = str(
            latest_mention_tweet_id
        )

        # Update the number of tweets made today
        ceramic_db.data["module_data"]["twitter"][
            "number_of_tweets_pulled_today"
        ] = str(number_of_tweets_pulled_today)
        ceramic_db.data["module_data"]["twitter"]["last_tweet_pull_window_reset"] = str(
            last_tweet_pull_window_reset
        )

        # Update the current_period
        ceramic_db.data["module_data"]["twitter"]["current_period"] = today

        self.context.logger.info(
            f"The ceramic_db will be updated to: {ceramic_db.data!r}"
        )

        return ceramic_db.data

    def get_registration(self, text: str) -> Optional[str]:
        """Check if the tweet is a registration and return the wallet address"""

        wallet_address = None

        address_match = re.search(ADDRESS_REGEX, text)
        tagline_match = re.search(TAGLINE, text, re.IGNORECASE)

        if address_match and tagline_match:
            wallet_address = Web3.to_checksum_address(address_match.group())

            address_to_twitter_handles = {
                user["wallet_address"]: user["twitter_handle"]
                for user in self.synchronized_data.ceramic_db["users"]
                if user["wallet_address"]
            }

            # Ignore registration if both address and Twitter handle already exist
            if (
                wallet_address in address_to_twitter_handles
                and address_to_twitter_handles[wallet_address]
            ):
                return None

        return wallet_address


class TwitterScoringRoundBehaviour(AbstractRoundBehaviour):
    """TwitterScoringRoundBehaviour"""

    initial_behaviour_cls = TwitterMentionsCollectionBehaviour
    abci_app_cls = TwitterScoringAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        TwitterDecisionMakingBehaviour,
        OpenAICallCheckBehaviour,
        TwitterMentionsCollectionBehaviour,
        TwitterHashtagsCollectionBehaviour,
        TweetEvaluationBehaviour,
        DBUpdateBehaviour,
        TwitterRandomnessBehaviour,
        TwitterSelectKeeperBehaviour,
    ]
