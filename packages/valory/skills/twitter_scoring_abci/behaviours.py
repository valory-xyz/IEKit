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
from typing import Dict, Generator, List, Set, Type, cast

from web3 import Web3

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.twitter_scoring_abci.ceramic_db import CeramicDB
from packages.valory.skills.twitter_scoring_abci.models import Params
from packages.valory.skills.twitter_scoring_abci.payloads import TwitterScoringPayload
from packages.valory.skills.twitter_scoring_abci.rounds import (
    SynchronizedData,
    TwitterScoringAbciApp,
    TwitterScoringRound,
)


ADDRESS_REGEX = r"0x[a-fA-F0-9]{40}"


class ScoreReadBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


class TwitterScoringBehaviour(ScoreReadBaseBehaviour):
    """TwitterScoringBehaviour"""

    matching_round: Type[AbstractRound] = TwitterScoringRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            # Get mentions from Twitter
            mentions = yield from self._get_twitter_mentions()
            self.context.logger.info(f"Retrieved new mentions from Twitter: {mentions}")

            registrations = {}
            if mentions != TwitterScoringRound.ERROR_PAYLOAD:
                # Get registrations from Twitter
                registrations = yield from self._get_twitter_registrations()
                self.context.logger.info(
                    f"Retrieved recent registrations from Twitter: {registrations}"
                )

            # Check for errors and merge data
            if (
                mentions == TwitterScoringRound.ERROR_PAYLOAD
                or registrations == TwitterScoringRound.ERROR_PAYLOAD
            ):
                payload_data = TwitterScoringRound.ERROR_PAYLOAD
            else:
                api_data = mentions
                api_data.update(registrations)
                # Calculate the new Ceramic content
                payload_data = self.update_ceramic_db(api_data)

            sender = self.context.agent_address
            payload = TwitterScoringPayload(
                sender=sender, content=json.dumps(payload_data, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _get_twitter_mentions(self) -> Generator[None, None, Dict]:
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

        mentions = []
        user_data = []
        next_token = None
        latest_mention_tweet_id = None

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
                return TwitterScoringRound.ERROR_PAYLOAD

            api_data = json.loads(response.body)

            # Check the meta field
            if "meta" not in api_data:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'meta' field: {api_data!r}"
                )
                return TwitterScoringRound.ERROR_PAYLOAD

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
                return TwitterScoringRound.ERROR_PAYLOAD

            if "includes" not in api_data or "users" not in api_data["includes"]:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'includes/users' field: {api_data!r}"
                )
                return TwitterScoringRound.ERROR_PAYLOAD

            mentions += api_data["data"]
            user_data += api_data["includes"]["users"]
            latest_mention_tweet_id = api_data["meta"]["newest_id"]

            if "next_token" in api_data["meta"]:
                next_token = api_data["meta"]["next_token"]
                continue

            break

        user_to_mentions = self._count_mentions(mentions)
        id_to_usernames = self._get_id_to_usernames(user_data)

        return {
            "user_to_mentions": user_to_mentions,
            "id_to_usernames": id_to_usernames,
            "latest_mention_tweet_id": latest_mention_tweet_id or next_tweet_id,
        }

    def _count_mentions(self, mentions: Dict) -> Dict:
        """Process Twitter API data"""

        user_to_mentions: Dict[str, int] = {}

        for tweet in mentions:
            author = tweet["author_id"]
            if author not in user_to_mentions:
                user_to_mentions[author] = 1
            else:
                user_to_mentions[author] = user_to_mentions[author] + 1

        return user_to_mentions

    def _get_id_to_usernames(self, user_data: List) -> Dict:
        """Process Twitter user data"""
        return {i["id"]: "@" + i["username"] for i in user_data}

    def _get_wallet_to_ids(self, tweets: List) -> Dict[str, str]:
        """Process Twitter user data"""
        result = {}
        for tweet in tweets:
            match = re.search(ADDRESS_REGEX, tweet["text"])
            if match:
                result[Web3.toChecksumAddress(match.group())] = tweet["author_id"]
        return result

    def _get_twitter_registrations(self) -> Generator[None, None, Dict]:
        """Get registrations from Twitter"""

        api_base = self.params.twitter_api_base
        api_endpoint = self.params.twitter_search_endpoint
        api_args = self.params.twitter_search_args
        api_url = api_base + api_endpoint + api_args

        headers = dict(Authorization=f"Bearer {self.params.twitter_api_bearer_token}")

        self.context.logger.info(f"Retrieving wallets from Twitter API [{api_url}]")

        registrations = []
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
                return TwitterScoringRound.ERROR_PAYLOAD

            api_data = json.loads(response.body)

            # Check the meta field
            if "meta" not in api_data:
                self.context.logger.error(
                    f"Twitter API response does not contain the required 'meta' field: {api_data!r}"
                )
                return TwitterScoringRound.ERROR_PAYLOAD

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
                return TwitterScoringRound.ERROR_PAYLOAD

            registrations += api_data["data"]

            if "next_token" in api_data["meta"]:
                next_token = api_data["meta"]["next_token"]
                continue

            break

        wallet_to_ids = self._get_wallet_to_ids(registrations)

        return {
            "wallet_to_users": wallet_to_ids,
        }

    def update_ceramic_db(self, api_data: Dict) -> Dict:
        """Calculate the new content of the DB"""

        # Instantiate the db
        ceramic_db = CeramicDB(self.synchronized_data.ceramic_db, self.context.logger)

        # Add the new mention points
        for twitter_id, mentions in api_data["user_to_mentions"].items():
            new_points = self.params.twitter_mention_points * mentions
            ceramic_db.update_or_create_user(
                "twitter_id", twitter_id, {"points": new_points}
            )

        # id_to_usernames
        for twitter_id, twitter_name in api_data["id_to_usernames"].items():
            ceramic_db.update_or_create_user(
                "twitter_id", twitter_id, {"twitter_handle": twitter_name}
            )

        # wallet_to_users
        for wallet_address, twitter_id in api_data["wallet_to_users"].items():
            ceramic_db.update_or_create_user(
                "twitter_id", twitter_id, {"wallet_address": wallet_address}
            )

        # If a user has first contributed to one module (i.e. twitter) without registering a wallet,
        # and later he/she contributes to another module, it could happen that we have two different
        # entries on the database
        ceramic_db.merge_by_wallet()

        # latest_mention_tweet_id
        ceramic_db.data["module_data"]["twitter"]["latest_mention_tweet_id"] = str(
            api_data["latest_mention_tweet_id"]
        )

        self.context.logger.info(
            f"The ceramic_db will be updated to: {ceramic_db.data!r}"
        )

        return ceramic_db.data


class TwitterScoringRoundBehaviour(AbstractRoundBehaviour):
    """TwitterScoringRoundBehaviour"""

    initial_behaviour_cls = TwitterScoringBehaviour
    abci_app_cls = TwitterScoringAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        TwitterScoringBehaviour,
    ]
