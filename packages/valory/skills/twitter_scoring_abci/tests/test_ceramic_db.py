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

"""This package contains the tests for Ceramic DB."""
import logging
from copy import copy

from packages.valory.skills.twitter_scoring_abci.ceramic_db import CeramicDB


_dummy_logger = logging.getLogger("dummy")

DEFAULT_DATA = {
    "points": 0,
    "token_id": None,
    "twitter_handle": None,
    "twitter_id": None,
    "wallet_address": None,
    "discord_id": None,
    "discord_handle": None,
    "current_period_points": 0,
}


def test_create_empty():
    """Test CeramicDB"""
    db = CeramicDB()
    assert db.data == {
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


def test_create_non_empty():
    """Test CeramicDB"""
    dummy_data = {"dummy": "data"}
    db = CeramicDB(dummy_data)
    assert db.data == dummy_data


def test_update_or_create():
    """Test CeramicDB"""
    db = CeramicDB()
    default_data = copy(DEFAULT_DATA)

    # Create a new user
    dummy_data = {"dummy": "data"}
    db.update_or_create_user("twitter_id", "dummy_twitter_id", dummy_data)
    default_data.update(dummy_data)
    default_data["twitter_id"] = "dummy_twitter_id"
    assert db.data["users"][0] == default_data

    # Update the same user
    db.update_or_create_user("twitter_id", "dummy_twitter_id", {"points": 1})
    default_data.update({"points": 1})
    assert db.data["users"][0] == default_data


def test_add_user():
    """Test CeramicDB"""
    db = CeramicDB()
    user_data = {"dummy": "data"}
    db.create_user(user_data)

    default_data = copy(DEFAULT_DATA)
    default_data.update(user_data)

    user, _ = db.get_user_by_field("dummy", "data")
    assert user == default_data


def test_merge_by_wallet():
    """Test CeramicDB"""
    db = CeramicDB()
    user_a = {
        "twitter_id": "dummy_twitter_id",
        "wallet_address": "dummy_address",
        "points": 10,
        "current_period_points": 20,
    }
    user_b = {
        "discord_id": "dummy_discord_id",
        "wallet_address": "dummy_address",
        "points": 10,
        "current_period_points": 15,
    }
    db.create_user(user_a)
    db.create_user(user_b)
    db.merge_by_wallet()
    assert len(db.data["users"]) == 1, "User merge was not successful"
    assert db.data["users"][0] == {
        "twitter_id": "dummy_twitter_id",
        "wallet_address": "dummy_address",
        "discord_id": "dummy_discord_id",
        "points": 20,
        "token_id": None,
        "twitter_handle": None,
        "discord_handle": None,
        "current_period_points": 20,
    }


def test_merge_by_wallet_duplicate_field():
    """Test CeramicDB"""
    db = CeramicDB(logger=_dummy_logger)
    user_a = {"twitter_id": "dummy_twitter_id", "wallet_address": "dummy_address"}
    user_b = {"twitter_id": "dummy_twitter_id_2", "wallet_address": "dummy_address"}
    db.create_user(user_a)
    db.create_user(user_b)
    assert db.data["users"][0] == {
        **DEFAULT_DATA,
        "twitter_id": "dummy_twitter_id",
        "wallet_address": "dummy_address",
    }
