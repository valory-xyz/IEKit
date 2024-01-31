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

"""This module contains the shared state for the abci skill of DecisionMakingAbciApp."""

import json
from typing import Any, Dict, List, Optional, Tuple
import itertools
from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.ceramic_read_abci.models import SharedState as CeramicReadSharedState

from packages.valory.skills.decision_making_abci.rounds import DecisionMakingAbciApp


DEFAULT_PROMPT = """
Using the information in the text below, craft an engaging and relevant post that highlights key insights or facts from the text.
The post should be limited to {n_chars} characters. IMPORTANT: under absolutely no circumstances use links, hashtags # or emojis.
Text: {memory}
"""

SHORTENER_PROMPT = """
Rewrite the tweet to fit {n_chars} characters. If in doubt, make it shorter. IMPORTANT: under absolutely no circumstances use links, hashtags # or emojis.
Text: {text}
"""


class SharedState(CeramicReadSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = DecisionMakingAbciApp


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the parameters object."""

        self.prompt_template = DEFAULT_PROMPT
        self.shortener_prompt_template = SHORTENER_PROMPT
        self.centaurs_stream_id = self._ensure("centaurs_stream_id", kwargs, str)
        self.ceramic_did_str = "did:key:" + kwargs.get("ceramic_did_str", "")
        self.ceramic_did_seed = kwargs.get("ceramic_did_seed")
        self.ceramic_db_stream_id = self._ensure("ceramic_db_stream_id", kwargs, str)
        self.manual_points_stream_id = self._ensure(
            "manual_points_stream_id", kwargs, str
        )
        self.centaur_id_to_secrets = json.loads(
            self._ensure("centaur_id_to_secrets", kwargs, str)
        )
        self.transaction_service_url = self._ensure(
            "transaction_service_url", kwargs, str
        )
        self.wveolas_address = self._ensure("wveolas_address", kwargs, str)
        self.tweet_consensus_wveolas = self._ensure(
            "tweet_consensus_wveolas", kwargs, int
        )
        super().__init__(*args, **kwargs)


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool


class CeramicDB:
    """A class that represents the user database"""

    USER_FIELDS = {
        "twitter_id",
        "twitter_handle",
        "discord_id",
        "discord_handle",
        "wallet_address",
        "token_id",
        "points",
        "current_period_points",
        "tweet_id_to_points",
    }

    def __init__(
        self,
        data: Optional[Dict] = None,
        logger: Optional[Any] = None,
    ) -> None:
        """Create a database"""
        self.load(data)
        self.logger = logger

    def load(self, data: Optional[Dict] = None):
        """Load data into the class"""
        self.data = (
            data
            if data not in (None, {})
            else {
                "users": [],
                "module_data": {
                    "twitter": {
                        "latest_mention_tweet_id": 0,
                        "current_period": "1970-01-01",
                    },
                    "dynamic_nft": {},
                    "generic": {"latest_update_id": 0},
                },
            }
        )

    def create_user(self, user_data):
        """Create a new user"""

        fields = self.USER_FIELDS.union(user_data.keys())

        new_user = {}
        for field in fields:
            if field in ("points", "current_period_points"):
                new_user[field] = user_data.get(field, 0)
            elif field in ("tweet_id_to_points",):
                new_user[field] = user_data.get(field, {})
            else:
                new_user[field] = user_data.get(field, None)

        self.data["users"].append(new_user)

        if self.logger:
            self.logger.info(f"DB: created new user: {new_user}")  # pragma: nocover

    def get_user_by_field(self, field, value) -> Tuple[Optional[Dict], Optional[int]]:
        """Search users"""

        for index, user in enumerate(self.data["users"]):
            if user[field] == value:
                return user, index  # returns the first user that marches

        return None, None

    def get_users_by_field(self, field, value) -> List[Tuple[Dict, int]]:
        """Search users"""
        users = []
        for index, user in enumerate(self.data["users"]):
            if user[field] == value:
                users.append((user, index))
        return users

    def update_or_create_user(self, field: str, value: str, new_data: Dict):
        """Update an existing user"""
        user, index = self.get_user_by_field(field, value)

        if user is None or index is None:
            self.create_user({field: value, **new_data})
            return

        fields = set(user).union(new_data.keys())

        updated_user = {
            field: new_data.get(field, user.get(field))
            if field != "points"
            else user["points"] + new_data.get("points", 0)
            for field in fields
        }

        if self.logger:
            self.logger.info(
                f"DB: updated user: from {json.dumps(user, sort_keys=True)} to {json.dumps(updated_user, sort_keys=True)}"
            )

        self.data["users"][index] = updated_user

    def merge_by_wallet(self):
        """Merges users that share the wallet"""
        wallet_addresses = set(
            [
                user["wallet_address"]
                for user in self.data["users"]
                if user["wallet_address"]
            ]
        )

        for wallet_address in wallet_addresses:
            users = self.get_users_by_field("wallet_address", wallet_address)

            if len(users) > 1:
                # Get the set of fields
                fields = set(itertools.chain(*[list(user.keys()) for user, _ in users]))
                fields.remove(
                    "wallet_address"
                )  # we already know this one is duplicated

                # Build the merged user
                merged_user = {}
                for field in fields:
                    # Get all the non None values from all users
                    values = [
                        user[field]
                        for user, _ in users
                        if field in user and user[field] is not None
                    ]

                    # Points must be added
                    if field == "points":
                        values = [sum(values)]

                    # We just keep the max current_period_points
                    if field == "current_period_points":
                        values = [max(values)]

                    # We merge the tweet_id_to_points
                    if field == "tweet_id_to_points":
                        for value in values[1:]:
                            values[0].update(value)  # type: ignore
                        values = [values[0]]

                    # Check whether all values are the same
                    if len(values) > 1:
                        values = (
                            [values[0]]
                            if all([v == values[0] for v in values])
                            else values
                        )

                    # Raise on multiple different valid values
                    if len(values) > 1:
                        raise ValueError(
                            f"DB: multiple valid values found for {field} [{values}] while merging users: {users}"
                        )
                    merged_user[field] = values[0] if values else None
                merged_user["wallet_address"] = wallet_address

                # Remove duplicated users
                for index in sorted([index for _, index in users], reverse=True):
                    self.data["users"].pop(index)

                # Add merged user
                self.data["users"].append(merged_user)