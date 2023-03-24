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

"""This package implements user db handling."""

import itertools
from typing import Any, Dict, List, Optional, Tuple


class CeramicDB:
    """A class that represents the user database"""

    USER_FIELDS = {
        "twitter_id",
        "twitter_handle",
        "wallet_address",
        "token_id",
        "points",
    }

    def __init__(
        self, data: Optional[Dict] = None, logger: Optional[Any] = None
    ) -> None:
        """Create a database"""
        self.data = (
            data
            if data not in (None, {})
            else {"users": [], "module_data": {"twitter": {}, "dynamic_nft": {}, "generic": {}}}
        )

        self.logger = logger
        if self.logger:
            self.logger.info(f"DB: created new db: {self.data}")

    def create_user(self, user_data):
        """Create a new user"""

        fields = self.USER_FIELDS.union(user_data.keys())

        new_user = {
            field: user_data.get(field, 0 if field == "points" else None)
            for field in fields
        }

        self.data["users"].append(new_user)

        if self.logger:
            self.logger.info(f"DB: created new user: {new_user}")

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
            self.logger.info(f"DB: updated user: from {user} to {updated_user}")

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
                            f"DB: multiple valid values found for '{field}' [{values}] while merging users: {users}"
                        )
                    merged_user[field] = values[0] if values else None
                merged_user["wallet_address"] = wallet_address

                # Remove duplicated users
                for index in sorted([index for _, index in users], reverse=True):
                    self.data["users"].pop(index)

                # Add merged user
                self.data["users"].append(merged_user)
