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
import re
from abc import ABC
from typing import Dict, Generator, Optional, Set, Tuple, Type, cast

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
from packages.valory.skills.abstract_round_abci.models import Requests
from packages.valory.skills.twitter_scoring_abci.ceramic_db import CeramicDB
from packages.valory.skills.twitter_scoring_abci.dialogues import (
    LlmDialogue,
    LlmDialogues,
)
from packages.valory.skills.twitter_scoring_abci.models import Params
from packages.valory.skills.twitter_scoring_abci.payloads import (
    DBUpdatePayload,
    TweetEvaluationPayload,
    TwitterCollectionPayload,
)
from packages.valory.skills.twitter_scoring_abci.prompts import tweet_evaluation_prompt
from packages.valory.skills.twitter_scoring_abci.rounds import (
    DBUpdateRound,
    SynchronizedData,
    TweetEvaluationRound,
    TwitterCollectionRound,
    TwitterScoringAbciApp,
)


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


class TwitterCollectionBehaviour(TwitterScoringBaseBehaviour):
    """TwitterCollectionBehaviour"""

    matching_round: Type[AbstractRound] = TwitterCollectionRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            payload_data = TwitterCollectionRound.ERROR_PAYLOAD

            # Get mentions from Twitter
            tweets, latest_mention_tweet_id = yield from self._get_twitter_mentions()
            self.context.logger.info(f"Retrieved new mentions from Twitter: {tweets}")

            # Get hashtags from Twitter
            # We use latest_mention_tweet_id here to keep search parity between mentions and hashtags
            if (
                tweets != TwitterCollectionRound.ERROR_PAYLOAD
                and latest_mention_tweet_id
            ):
                tweets = yield from self._get_twitter_hashtag_search(
                    tweets, latest_mention_tweet_id
                )

            if (
                tweets != TwitterCollectionRound.ERROR_PAYLOAD
                and latest_mention_tweet_id
            ):
                self.context.logger.info(f"Retrieved new tweets: {list(tweets.keys())}")
                payload_data = {
                    "tweets": tweets,
                    "latest_mention_tweet_id": latest_mention_tweet_id,
                }

            sender = self.context.agent_address
            payload = TwitterCollectionPayload(
                sender=sender, content=json.dumps(payload_data, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _get_twitter_mentions(
        self,
    ) -> Generator[None, None, Tuple[Dict, Optional[int]]]:
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
        next_tweet_id = (
            int(latest_mention_tweet_id) + 1 if int(latest_mention_tweet_id) != 0 else 0
        )
        api_args = self.params.twitter_mentions_args.replace(
            "{since_id}", str(next_tweet_id)
        )
        api_url = api_base + api_endpoint + api_args
        headers = dict(Authorization=f"Bearer {self.params.twitter_api_bearer_token}")

        self.context.logger.info(f"Retrieving mentions from Twitter API [{api_url}]")

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
                    f"Error retrieving mentions from Twitter [{response.status_code}]"
                )
                return TwitterCollectionRound.ERROR_PAYLOAD, None

            api_data = json.loads(response.body)

            # Check the meta field
            if "meta" not in api_data:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'meta' field: {api_data!r}"
                )
                return TwitterCollectionRound.ERROR_PAYLOAD, None

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
                return TwitterCollectionRound.ERROR_PAYLOAD, None

            if "includes" not in api_data or "users" not in api_data["includes"]:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'includes/users' field: {api_data!r}"
                )
                return TwitterCollectionRound.ERROR_PAYLOAD, None

            # Add the retrieved tweets
            for tweet in api_data["data"]:
                tweets[tweet["id"]] = tweet

                # Set the author handle
                for user in api_data["includes"]["users"]:
                    if user["id"] == tweet["author_id"]:
                        tweets[tweet["id"]]["username"] = user["username"]
                        break

            latest_tweet_id = int(api_data["meta"]["newest_id"])

            if "next_token" in api_data["meta"]:
                next_token = api_data["meta"]["next_token"]
                continue

            break

        return tweets, latest_tweet_id

    def _get_twitter_hashtag_search(
        self, tweets: dict, until_id: int
    ) -> Generator[None, None, Dict]:
        """Get registrations from Twitter"""

        api_base = self.params.twitter_api_base
        api_endpoint = self.params.twitter_search_endpoint
        try:
            latest_hashtag_tweet_id = int(
                self.synchronized_data.ceramic_db["module_data"]["twitter"][
                    "latest_mention_tweet_id"
                ]
            )
        except KeyError:
            latest_hashtag_tweet_id = 0
        next_tweet_id = (
            int(latest_hashtag_tweet_id) + 1 if int(latest_hashtag_tweet_id) != 0 else 0
        )
        api_args = self.params.twitter_search_args.replace(
            "{since_id}", str(next_tweet_id)
        )

        api_args += f"&until_id={until_id}"

        api_url = api_base + api_endpoint + api_args

        headers = dict(Authorization=f"Bearer {self.params.twitter_api_bearer_token}")

        self.context.logger.info(f"Retrieving hashes from Twitter API [{api_url}]")

        next_token = None

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
                return TwitterCollectionRound.ERROR_PAYLOAD

            api_data = json.loads(response.body)

            # Check the meta field
            if "meta" not in api_data:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'meta' field: {api_data!r}"
                )
                return TwitterCollectionRound.ERROR_PAYLOAD

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
                return TwitterCollectionRound.ERROR_PAYLOAD

            if "includes" not in api_data or "users" not in api_data["includes"]:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'includes/users' field: {api_data!r}"
                )
                return TwitterCollectionRound.ERROR_PAYLOAD

            # Add the retrieved tweets
            for tweet in api_data["data"]:
                if tweet["id"] not in tweets:  # avoids duplicated tweets
                    tweets[tweet["id"]] = tweet

                    # Set the author handle
                    for user in api_data["includes"]["users"]:
                        if user["id"] == tweet["author_id"]:
                            tweets[tweet["id"]]["username"] = user["username"]
                            break

            if "next_token" in api_data["meta"]:
                next_token = api_data["meta"]["next_token"]
                continue

            break

        return tweets


class TweetEvaluationBehaviour(TwitterScoringBaseBehaviour):
    """TweetEvaluationBehaviour"""

    matching_round: Type[AbstractRound] = TweetEvaluationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            tweet_id_to_points = {}
            for tweet_id, tweet in self.synchronized_data.tweets.items():
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

        llm_dialogues = cast(LlmDialogues, self.context.llm_dialogues)

        # llm request message
        request_llm_message, llm_dialogue = llm_dialogues.create(
            counterparty=str(LLM_CONNECTION_PUBLIC_ID),
            performative=LlmMessage.Performative.REQUEST,
            prompt_template=tweet_evaluation_prompt,
            prompt_values={"user_text": text},
        )
        request_llm_message = cast(LlmMessage, request_llm_message)
        llm_dialogue = cast(LlmDialogue, llm_dialogue)
        llm_response_message = yield from self._do_request(
            request_llm_message, llm_dialogue
        )
        data = llm_response_message.value

        self.context.logger.info(f"Got tweet evaluation: {data}")

        points = DEFAULT_TWEET_POINTS
        try:
            data = json.loads(data)
            quality = data["quality"]
            relationship = data["relationship"]
            if (
                quality not in TWEET_QUALITY_TO_POINTS
                or relationship not in TWEET_RELATIONSHIP_TO_POINTS
            ):
                self.context.logger.error("Evaluation data is not valid")
            else:
                points = (
                    TWEET_QUALITY_TO_POINTS[quality]
                    * TWEET_RELATIONSHIP_TO_POINTS[relationship]
                )
        except:
            self.context.logger.error("Evaluation data is not valid")

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
        latest_mention_tweet_id = self.synchronized_data.tweets

        # Instantiate the db
        ceramic_db = CeramicDB(self.synchronized_data.ceramic_db, self.context.logger)

        # Evaluate tweets
        for tweet in tweets.values():

            author_id = tweet["author_id"]
            twitter_name = tweet["username"]
            new_points = tweet["points"]
            wallet_address = get_registration(tweet["text"])

            # User data to update
            user_data = {"points": new_points, "twitter_handle": twitter_name}

            # If this is a registration
            if wallet_address:
                user_data["wallet_address"] = wallet_address

            # For existing users, all existing user data is replaced except points, which are added
            ceramic_db.update_or_create_user("twitter_id", author_id, user_data)

        # If a user has first contributed to one module (i.e. twitter) without registering a wallet,
        # and later he/she contributes to another module, it could happen that we have two different
        # entries on the database
        ceramic_db.merge_by_wallet()

        # Update the latest_mention_tweet_id
        ceramic_db.data["module_data"]["twitter"]["latest_mention_tweet_id"] = str(
            latest_mention_tweet_id
        )

        self.context.logger.info(
            f"The ceramic_db will be updated to: {ceramic_db.data!r}"
        )

        return ceramic_db.data


def get_registration(text: str) -> Optional[str]:
    """Check if the tweet is a registration and return the wallet address"""

    wallet_address = None

    address_match = re.search(ADDRESS_REGEX, text)
    tagline_match = re.search(TAGLINE, text, re.IGNORECASE)

    if address_match and tagline_match:
        wallet_address = Web3.toChecksumAddress(address_match.group())

    return wallet_address


class TwitterCollectionRoundBehaviour(AbstractRoundBehaviour):
    """TwitterCollectionRoundBehaviour"""

    initial_behaviour_cls = TwitterCollectionBehaviour
    abci_app_cls = TwitterScoringAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        TwitterCollectionBehaviour,
        TweetEvaluationBehaviour,
        DBUpdateBehaviour,
    ]
