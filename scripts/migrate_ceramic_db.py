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

"""This package contains code to handle migrations on Ceramic."""
# pylint: disable=import-error

import json
import os
from copy import deepcopy
from pathlib import Path

import dotenv
import jsonschema
from ceramic.ceramic import Ceramic
from ceramic.streams import (
    CONTRIBUTE_CENTAURS_SCHEMA_COMMIT,
    CONTRIBUTE_DB_SCHEMA_COMMIT,
    CONTRIBUTE_PROD_CENTAURS_STREAM_ID,
    CONTRIBUTE_PROD_DB_STREAM_ID,
)


dotenv.load_dotenv(override=True)

ceramic = Ceramic(os.getenv("CERAMIC_API_BASE"))
ceramic_did_str = "did:key:" + str(os.getenv("CERAMIC_DID_STR"))
ceramic_did_seed = os.getenv("CERAMIC_DID_SEED")

MAX_USERS_PER_COMMIT = 100
MAX_TWEETS_PER_COMMIT = 100

LOCAL_READ = False  # load from the local machine instead of Ceramic
LOCAL_WRITE = False  # write o the local machine instead of Ceramic


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

    # Load the users db
    print("Reading the users db...")
    if LOCAL_READ:
        with open("contribute_db.json", "r", encoding="utf-8") as data_file:
            user_db = json.load(data_file)
    else:
        user_db, _, _ = ceramic.get_data(CONTRIBUTE_PROD_DB_STREAM_ID)

    print("Updating the users db format...")

    # Remove the module data
    del user_db["module_data"]["staking_activity"]

    for user_data in user_db["users"].values():
        for tweet in user_data["tweets"].values():
            # Initialize the counted_for_activity
            tweet["counted_for_activity"] = False

    # Validate the new data
    print("Validating the updated users db...")
    with open(Path("ceramic", "schemas", "db_stream_schema.json"), "r", encoding="utf-8") as data_file:
        stream_schema = json.load(data_file)
        jsonschema.validate(instance=user_db, schema=stream_schema)

    # Write the new data
    print("Writing the updated users db...")

    if LOCAL_WRITE:
        with open("contribute_db_new.json", "w", encoding="utf-8") as data_file:
            json.dump(user_db, data_file, indent=4)
    else:
        extra_metadata = {
            "schema": CONTRIBUTE_DB_SCHEMA_COMMIT  # this is the schema commit, not stream id
        }

        user_db_batch_write(
            did=ceramic_did_str,
            did_seed=ceramic_did_seed,
            data=user_db,
            extra_metadata=extra_metadata,
        )

    # -------------------------------------------------------------------------------------

    # Load the centaurs db
    print("Reading the centaurs db...")

    if LOCAL_READ:
        with open("contribute_centaurs.json", "r", encoding="utf-8") as data_file:
            centaurs_db = json.load(data_file)
    else:
        centaurs_db, _, _ = ceramic.get_data(CONTRIBUTE_PROD_CENTAURS_STREAM_ID)


    print("Updating the db format...")

    centaurs_db["configuration"]["plugins"]["staking_daa"] = {
        "enabled": True,
        "daily": True,
        "last_run": None,
        "run_hour_utc": 0
    }

    # Validate the new data
    print("Validating the updated centaurs db...")
    with open(Path("ceramic", "schemas", "centaurs_stream_schema.json"), "r", encoding="utf-8") as data_file:
        stream_schema = json.load(data_file)
        jsonschema.validate(instance=centaurs_db, schema=stream_schema)

    # Write the new data
    print("Writing the updated centaurs db...")

    if LOCAL_WRITE:
        with open("contribute_centaurs_new.json", "w", encoding="utf-8") as data_file:
            json.dump(centaurs_db, data_file, indent=4)
    else:
        extra_metadata = {
            "schema": CONTRIBUTE_CENTAURS_SCHEMA_COMMIT  # this is the schema commit, not stream id
        }

        centaurs_db_batch_write(
            did=ceramic_did_str,
            did_seed=ceramic_did_seed,
            data=centaurs_db,
            extra_metadata=extra_metadata,
        )

if __name__ == "__main__":
    main()
