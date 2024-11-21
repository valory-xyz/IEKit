import os
from copy import deepcopy

import dotenv
from ceramic import Ceramic
from streams import *


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


extra_metadata_db = {
    "schema": CONTRIBUTE_DB_SCHEMA_COMMIT
}

extra_metadata_centaurs = {
    "schema": CONTRIBUTE_CENTAURS_SCHEMA_COMMIT
}


# Get the prod data
user_db, _, _ = ceramic.get_data(CONTRIBUTE_PROD_DB_STREAM_ID)

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
