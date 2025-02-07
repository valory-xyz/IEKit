#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2024 Valory AG
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

"""This package contains code to clone streams on Ceramic."""
# pylint: disable=import-error

import os
from copy import deepcopy

import dotenv
from ceramic.ceramic import Ceramic
from ceramic.streams import (
    CONTRIBUTE_CENTAURS_SCHEMA_COMMIT,
    CONTRIBUTE_DB_SCHEMA_COMMIT,
    CONTRIBUTE_PROD_CENTAURS_STREAM_ID,
    CONTRIBUTE_PROD_DB_STREAM_ID,
)


MAX_USERS_PER_COMMIT = 250
MAX_TWEETS_PER_COMMIT = 100

dotenv.load_dotenv(override=True)

ceramic = Ceramic(os.getenv("CERAMIC_API_BASE"))
ceramic_did_str = "did:key:" + str(os.getenv("CERAMIC_DID_STR"))
ceramic_did_seed = os.getenv("CERAMIC_DID_SEED")


def user_db_batch_write(did, did_seed, data, extra_metadata):
    """Batch write the users db to Ceramic when all db does not fit in one commit"""
    print("Batching write...")
    tmp_data = deepcopy(data)
    user_id_list = list(tmp_data["users"].keys())
    tmp_data["users"] = {user_id: tmp_data["users"][user_id] for user_id in user_id_list[:MAX_USERS_PER_COMMIT]}

    stream_id = ceramic.create_stream(
        did,
        did_seed,
        tmp_data,
        extra_metadata
    )

    while len(tmp_data["users"]) < len(data["users"]):
        n_users = len(tmp_data["users"])
        for user_id in user_id_list[n_users : n_users + MAX_USERS_PER_COMMIT]:
            tmp_data["users"][user_id] = data["users"][user_id]

        ceramic.update_stream(
            did,
            did_seed,
            stream_id,
            tmp_data,
        )

    return stream_id


def centaurs_db_batch_write(did, did_seed, data, extra_metadata):
    """Batch write the centaurs db to Ceramic when all db does not fit in one commit"""
    print("Batching write...")
    tweet_list = data[0]["plugins_data"]["scheduled_tweet"]["tweets"]
    tmp_data = deepcopy(data)
    tmp_data[0]["plugins_data"]["scheduled_tweet"]["tweets"] = tweet_list[:MAX_TWEETS_PER_COMMIT]

    stream_id = ceramic.create_stream(
        did,
        did_seed,
        tmp_data,
        extra_metadata
    )

    while len(tmp_data[0]["plugins_data"]["scheduled_tweet"]["tweets"]) < len(data[0]["plugins_data"]["scheduled_tweet"]["tweets"]):
        n_tweets = len(tmp_data[0]["plugins_data"]["scheduled_tweet"]["tweets"])

        tmp_data[0]["plugins_data"]["scheduled_tweet"]["tweets"] += tweet_list[n_tweets : n_tweets + MAX_TWEETS_PER_COMMIT]

        ceramic.update_stream(
            did,
            did_seed,
            stream_id,
            tmp_data,
        )

    return stream_id


def main():
    """Main"""
    extra_metadata_db = {
        "schema": CONTRIBUTE_DB_SCHEMA_COMMIT
    }

    extra_metadata_centaurs = {
        "schema": CONTRIBUTE_CENTAURS_SCHEMA_COMMIT
    }

    # Get the prod data
    user_db, _, _ = ceramic.get_data(CONTRIBUTE_PROD_DB_STREAM_ID)

    # Update multisigs and service_ids
    for user_data in user_db["users"].values():

        if user_data["service_multisig"]:
            user_data["service_multisig_old"] = user_data["service_multisig"]
            user_data["service_multisig"] = None

        if user_data["service_id"]:
            user_data["service_id_old"] = user_data["service_id"]
            user_data["service_id"] = None

    # Clone into a new stream
    stream_id = user_db_batch_write(
        did=ceramic_did_str,
        did_seed=ceramic_did_seed,
        data=user_db,
        extra_metadata=extra_metadata_db,
    )
    print(f"Contribute DB stream id: {stream_id}")


    # Get the prod data
    centaurs_db, _, _ = ceramic.get_data(CONTRIBUTE_PROD_CENTAURS_STREAM_ID)

    # Clone into a new stream
    stream_id = centaurs_db_batch_write(
        did=ceramic_did_str,
        did_seed=ceramic_did_seed,
        data=centaurs_db,
        extra_metadata=extra_metadata_centaurs,
    )
    print(f"Centaurs stream id: {stream_id}")


if __name__ == "__main__":
    main()
