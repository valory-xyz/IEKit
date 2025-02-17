# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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

import itertools
import json
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

import jsonpatch
from aea.skills.base import Model

from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.ceramic_read_abci.models import (
    SharedState as CeramicReadSharedState,
)
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
        self.veolas_delegation_address = self._ensure(
            "veolas_delegation_address", kwargs, str
        )
        self.tweet_consensus_veolas = self._ensure(
            "tweet_consensus_veolas", kwargs, int
        )
        self.checkpoint_threshold_minutes = self._ensure(
            "checkpoint_threshold_minutes", kwargs, int
        )
        self.staking_activity_threshold = self._ensure(
            "staking_activity_threshold", kwargs, int
        )
        self.epoch_end_threshold_minutes = self._ensure(
            "epoch_end_threshold_minutes", kwargs, int
        )
        self.staking_contract_addresses = kwargs.get("staking_contract_addresses", [])
        self.disable_wio_posting = self._ensure(
            "disable_wio_posting", kwargs, bool
        )
        super().__init__(*args, **kwargs)


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool


class CeramicDBBase:
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
        "tweets",
        "service_multisig",
        "service_id",
    }

    def __init__(self) -> None:
        """Create a database"""
        self.data = {}
        self.load()

    def load(self, data: Optional[Dict] = None):
        """Load data into the class"""
        self.data = (
            data
            if data not in (None, {})
            else {
                "users": {},
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

    def get_next_user_id(self):
        """Calculate next user id"""
        if not self.data["users"]:
            return "0"
        user_ids = list(sorted([int(user_id) for user_id in self.data["users"].keys()]))
        return str(int(user_ids[-1]) + 1)

    def create_user(self, user_data):
        """Create a new user"""

        fields = self.USER_FIELDS.union(user_data.keys())

        new_user = {}
        for field in fields:
            if field in ("points", "current_period_points"):
                new_user[field] = user_data.get(field, 0)
            elif field in ("tweets",):
                new_user[field] = user_data.get(field, {})
            else:
                new_user[field] = user_data.get(field, None)

        user_id = self.get_next_user_id()
        self.data["users"][user_id] = new_user

    def get_user_by_field(self, field, value) -> Tuple[Optional[Dict], Optional[str]]:
        """Search users"""

        for user_id, user in self.data["users"].items():
            if user[field] == value:
                return user, user_id  # returns the first user that marches

        return None, None

    def get_user_by_id(self, user_id) -> Optional[Dict]:
        """Search users"""
        return self.data["users"].get(user_id, None)

    def get_user_ids_by_field(self, field, value) -> List[Tuple[Dict, int]]:
        """Search users"""
        user_ids = []
        for user_id, user in self.data["users"].items():
            if user[field] == value:
                user_ids.append(user_id)
        return user_ids

    def update_or_create_user(self, field: str, value: str, new_data: Dict):
        """Update an existing user"""
        user, user_id = self.get_user_by_field(field, value)

        if user is None or user_id is None:
            self.create_user({field: value, **new_data})
            return

        fields = set(user).union(new_data.keys())

        updated_user = {
            field: new_data.get(field, user.get(field))
            if field != "points"
            else user["points"] + new_data.get("points", 0)
            for field in fields
        }

        self.data["users"][user_id] = updated_user

    def merge_by_wallet(self):
        """Merges users that share the wallet"""
        wallet_addresses = set(
            [
                user["wallet_address"]
                for user in self.data["users"].values()
                if user["wallet_address"]
            ]
        )

        for wallet_address in wallet_addresses:
            user_ids = self.get_user_ids_by_field("wallet_address", wallet_address)
            users = [self.get_user_by_id(user_id) for user_id in user_ids]

            if len(users) > 1:
                # Get the set of fields
                fields = set(itertools.chain(*[list(user.keys()) for user in users]))
                fields.remove(
                    "wallet_address"
                )  # we already know this one is duplicated

                # Build the merged user
                merged_user = {}
                for field in fields:
                    # Get all the non None values from all users
                    values = [
                        user[field]
                        for user in users
                        if field in user and user[field] is not None
                    ]

                    # Points must be added
                    if field == "points":
                        values = [sum(values)]

                    # We just keep the max current_period_points
                    if field == "current_period_points":
                        values = [max(values)]

                    # We merge the tweets
                    if field == "tweets":
                        for value in values[1:]:
                            values[0].update(value)  # type: ignore
                        values = [values[0]]

                    # Merge the multisigs
                    # We have no way to tell which one we should keep
                    if field == "service_multisig":
                        values = [values[0] if values else None]

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

                next_user_id = self.get_next_user_id()

                # Remove duplicated users
                for user_id in user_ids:
                    del self.data["users"][user_id]

                # Add merged user
                self.data["users"][next_user_id] = merged_user

    def reset_period_points(self):
        """Resets period points"""
        for user_id in self.data["users"].keys():
            self.data["users"][user_id]["current_period_points"] = 0

    def diff(self, other_db):
        """Create data diff"""
        return str(jsonpatch.make_patch(self.data, other_db.data))

    def apply_diff(self, patch):
        """Apply a diff"""
        self.data = jsonpatch.JsonPatch.from_string(patch).apply(self.data)

    def copy(self):
        """Get a deep copy of the database"""
        copy = CeramicDBBase()
        copy.load(deepcopy(self.data))
        return copy

    def __getitem__(self, key):
        """Dict like access"""
        return self.data[key]


class CeramicDB(Model, CeramicDBBase):
    """CeramicDB Model"""

    def __init__(self, *args, **kwargs):
        """Init"""
        Model.__init__(self, *args, **kwargs)
        CeramicDBBase.__init__(self)
