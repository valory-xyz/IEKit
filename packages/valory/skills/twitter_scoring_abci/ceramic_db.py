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

from typing import Dict, Optional, Tuple


class CeramicDB:
    """A class that represents the user database"""

    USER_FIELDS = {
        "twitter_id",
        "twitter_handle",
        "wallet_address",
        "token_id",
        "points",
    }

    def __init__(self, data: Optional[Dict] = None) -> None:
        """Create a database"""
        self.data = data if data else {"users": [], "module_data": {"twitter": {}}}

    def create_user(self, user_data):
        """Create a new user"""

        fields = self.USER_FIELDS.union(user_data.keys())

        self.data["users"].append(
            {
                field: user_data.get(field, 0 if field == "points" else None)
                for field in fields
            }
        )

    def get_user_by_field(self, field, value) -> Tuple[Optional[Dict], Optional[int]]:
        """Search users"""

        for index, user in enumerate(self.data["users"]):
            if user[field] == value:
                return user, index

        return None, None

    def update_or_create_user(self, field: str, value: str, new_data: Dict):
        """Update an existing user"""
        user, index = self.get_user_by_field(field, value)

        if None in (index, user):
            self.create_user({field: value, **new_data})
            return

        fields = set(user).union(new_data.keys())

        self.data["users"][index] = {
            field: new_data.get(field, user.get(field))
            if field != "points"
            else user["points"] + new_data.get("points", 0)
            for field in fields
        }
