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

"""This package contains the tests for Ceramic DB."""

from copy import copy

import pytest

from packages.valory.skills.decision_making_abci.models import CeramicDBBase


DEFAULT_DATA = {
    "points": 0,
    "token_id": None,
    "twitter_handle": None,
    "twitter_id": None,
    "wallet_address": None,
    "discord_id": None,
    "discord_handle": None,
    "current_period_points": 0,
    "tweets": {},
    "service_multisig": None,
    "service_id": None,
}


def test_create_empty():
    """Test CeramicDBBase"""
    db = CeramicDBBase()
    assert db.data == {
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


def test_create_non_empty():
    """Test CeramicDBBase"""
    dummy_data = {"dummy": "data"}
    db = CeramicDBBase()
    db.load(dummy_data)
    assert db.data == dummy_data


def test_update_or_create():
    """Test CeramicDBBase"""
    db = CeramicDBBase()
    default_data = copy(DEFAULT_DATA)

    # Create a new user
    dummy_data = {"dummy": "data"}
    db.update_or_create_user("twitter_id", "dummy_twitter_id", dummy_data)
    default_data.update(dummy_data)
    default_data["twitter_id"] = "dummy_twitter_id"
    assert db.data["users"]["0"] == default_data

    # Update the same user
    db.update_or_create_user("twitter_id", "dummy_twitter_id", {"points": 1})
    default_data.update({"points": 1})
    assert db.data["users"]["0"] == default_data


def test_add_user():
    """Test CeramicDBBase"""
    db = CeramicDBBase()
    user_data = {"dummy": "data"}
    db.create_user(user_data)

    default_data = copy(DEFAULT_DATA)
    default_data.update(user_data)

    user, _ = db.get_user_by_field("dummy", "data")
    assert user == default_data


def test_merge_by_wallet():
    """Test CeramicDBBase"""
    db = CeramicDBBase()
    user_a = {
        "twitter_id": "dummy_twitter_id",
        "wallet_address": "dummy_address",
        "points": 10,
        "current_period_points": 20,
        "tweets": {"1": {"points": 100}, "2": {"points": 200}},
        "service_multisig": "dummy_multisig",
    }
    user_b = {
        "discord_id": "dummy_discord_id",
        "wallet_address": "dummy_address",
        "points": 10,
        "current_period_points": 15,
        "tweets": {"2": {"points": 200}, "3": {"points": 300}},
        "service_multisig": None,
    }
    db.create_user(user_a)
    db.create_user(user_b)
    db.merge_by_wallet()
    assert len(db.data["users"]) == 1, "User merge was not successful"
    assert db.data["users"]["2"] == {
        "twitter_id": "dummy_twitter_id",
        "wallet_address": "dummy_address",
        "discord_id": "dummy_discord_id",
        "points": 20,
        "token_id": None,
        "twitter_handle": None,
        "discord_handle": None,
        "current_period_points": 20,
        "tweets": {"1": {"points": 100}, "2": {"points": 200}, "3": {"points": 300}},
        "service_multisig": "dummy_multisig",
        "service_id": None,
    }


def test_merge_by_wallet_raises():
    """Test CeramicDBBase"""
    db = CeramicDBBase()
    user_a = {
        "twitter_id": "dummy_twitter_id",
        "wallet_address": "dummy_address",
        "service_multisig": None,
    }
    user_b = {
        "twitter_id": "dummy_twitter_id_2",
        "wallet_address": "dummy_address",
        "service_multisig": None,
    }
    db.create_user(user_a)
    db.create_user(user_b)
    with pytest.raises(ValueError):
        db.merge_by_wallet()


def test_reset_period_points():
    """Test CeramicDBBase"""
    db = CeramicDBBase()
    user_a = {
        "twitter_id": "dummy_twitter_id",
        "wallet_address": "dummy_address",
        "points": 10,
        "current_period_points": 20,
        "tweets": {"1": {"points": 100}, "2": {"points": 200}},
    }
    user_b = {
        "discord_id": "dummy_discord_id",
        "wallet_address": "dummy_address",
        "points": 10,
        "current_period_points": 15,
        "tweets": {"2": {"points": 200}, "3": {"points": 300}},
    }
    db.create_user(user_a)
    db.create_user(user_b)
    db.reset_period_points()
    assert all(u["current_period_points"] == 0 for u in db.data["users"].values())


def test_diff():
    """Test CeramicDBBase"""
    db_a = CeramicDBBase()
    db_b = CeramicDBBase()
    user_a = {
        "twitter_id": "dummy_twitter_id",
        "wallet_address": "dummy_address",
        "points": 10,
        "current_period_points": 20,
        "tweets": {"1": {"points": 100}, "2": {"points": 200}},
    }
    user_b = {  # same data as user_a but in different order
        "current_period_points": 20,
        "wallet_address": "dummy_address",
        "points": 10,
        "tweets": {"1": {"points": 100}, "2": {"points": 200}},
        "twitter_id": "dummy_twitter_id",
    }
    db_a.create_user(user_a)
    db_b.create_user(user_b)
    diff = db_b.diff(db_a)
    assert diff == "[]"
