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

from copy import copy

from packages.valory.skills.twitter_scoring_abci.ceramic_db import CeramicDB


DEFAULT_DATA = {
    "points": 0,
    "token_id": None,
    "twitter_handle": None,
    "twitter_id": None,
    "wallet_address": None,
}


def test_create_empty():
    """Test CeramicDB"""
    db = CeramicDB()
    assert db.data == {"users": [], "module_data": {"twitter": {}, "dynamic_nft": {}}}


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
