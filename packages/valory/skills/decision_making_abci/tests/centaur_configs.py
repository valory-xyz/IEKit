#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2023 Valory AG
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

"""This package contains centaur data for tests."""

import datetime
from copy import deepcopy


ENABLED_CENTAUR = {
    "id": "4e77a3b1-5762-4782-830e-0e56c6c05c6f",
    "name": "Dummy Centaur",
    "configuration": {
        "plugins": {
            "daily_tweet": {
                "daily": True,
                "enabled": True,
                "last_run": None,
                "run_hour_utc": datetime.datetime.utcnow().hour,
            },
            "scheduled_tweet": {"daily": False, "enabled": True},
            "daily_orbis": {
                "daily": True,
                "enabled": True,
                "last_run": None,
                "run_hour_utc": datetime.datetime.utcnow().hour,
            },
        }
    },
    "plugins_data": {
        "daily_orbis": {},
        "daily_tweet": {},
        "scheduled_tweet": {
            "tweets": [
                {
                    "request_id": "dummy_id_1",
                    "posted": False,
                    "proposer": {
                        "address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
                        "signature": "0x37904bcb8b6e11ae894856c1d722209397e548219f000fc172f9a58a064718dd634fa00ace138383dfe807f479a0cf22588edb3fd61bfea2f85378a7513c6cc41c",
                        "verified": None,
                    },
                    "text": "My agreed tweet: execute",
                    "voters": [
                        {"0x6c6766E04eF971367D27E720d1d161a9B495D647": 0},
                        {"0x7885d121ed8Aa3c919AA4d407F197Dc29E33cAf0": 0},
                    ],
                    "executionAttempts": [],
                },
                {
                    "request_id": "dummy_id_2",
                    "posted": False,
                    "proposer": {
                        "address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
                        "signature": "0x37904bcb8b6e11ae894856c1d722209397e548219f000fc172f9a58a064718dd634fa00ace138383dfe807f479a0cf22588edb3fd61bfea2f85378a7513c6cc41c",
                        "verified": None,
                    },
                    "text": "My agreed tweet: dont execute",
                    "voters": [
                        {"0x6c6766E04eF971367D27E720d1d161a9B495D647": 0},
                        {"0x7885d121ed8Aa3c919AA4d407F197Dc29E33cAf0": 0},
                    ],
                    "executionAttempts": [],
                },
            ]
        },
    },
    "actions": [
        {
            "timestamp": 1686737751798,
            "description": "added a memory",
            "actorAddress": "0x18C6A47AcA1c6a237e53eD2fc3a8fB392c97169b",
            "commitId": "bagcqcera7ximz76vx25j5qzfrkvedklwcw732xnyuiycd46rgokrbfkzrx4a",
        },
    ],
    "members": [
        {"address": "0x6c6766E04eF971367D27E720d1d161a9B495D647", "ownership": 0},
        {"address": "0x7885d121ed8Aa3c919AA4d407F197Dc29E33cAf0", "ownership": 1},
    ],
    "purpose": "A testing centaur.",
    "memory": [
        "dummy memory 1",
        "dummy memory 2",
    ],
    "messages": [
        {
            "member": "0x18C6A47AcA1c6a237e53eD2fc3a8fB392c97169b",
            "content": "This is an example of dummy content",
            "timestamp": 1686737815115,
        }
    ],
}

DISABLED_CENTAUR = {
    "id": "4e77a3b1-5762-4782-830e-0e56c6c05c6f",
    "name": "Dummy Centaur",
    "configuration": {
        "plugins": {
            "daily_tweet": {
                "daily": True,
                "enabled": False,
                "last_run": None,
                "run_hour_utc": 12,
            },
            "scheduled_tweet": {"daily": False, "enabled": False},
            "daily_orbis": {
                "daily": True,
                "enabled": False,
                "last_run": None,
                "run_hour_utc": 12,
            },
        }
    },
    "plugins_data": {
        "daily_orbis": {},
        "daily_tweet": {},
        "scheduled_tweet": {"tweets": []},
    },
    "actions": [
        {
            "timestamp": 1686737751798,
            "description": "added a memory",
            "actorAddress": "0x18C6A47AcA1c6a237e53eD2fc3a8fB392c97169b",
            "commitId": "bagcqcera7ximz76vx25j5qzfrkvedklwcw732xnyuiycd46rgokrbfkzrx4a",
        },
    ],
    "members": [
        {"address": "0x6c6766E04eF971367D27E720d1d161a9B495D647", "ownership": 0},
        {"address": "0x7885d121ed8Aa3c919AA4d407F197Dc29E33cAf0", "ownership": 1},
    ],
    "purpose": "A testing centaur.",
    "memory": [
        "dummy memory 1",
        "dummy memory 2",
    ],
    "messages": [
        {
            "member": "0x18C6A47AcA1c6a237e53eD2fc3a8fB392c97169b",
            "content": "This is an example of dummy content",
            "timestamp": 1686737815115,
        }
    ],
}


MISSING_DAILY_TWEET_CONFIG_CENTAUR_A = deepcopy(ENABLED_CENTAUR)
del MISSING_DAILY_TWEET_CONFIG_CENTAUR_A["plugins_data"]["scheduled_tweet"]

MISSING_DAILY_TWEET_CONFIG_CENTAUR_B = deepcopy(ENABLED_CENTAUR)
del MISSING_DAILY_TWEET_CONFIG_CENTAUR_B["plugins_data"]["scheduled_tweet"]["tweets"]

MISSING_DAILY_TWEET_CONFIG_CENTAUR_C = deepcopy(ENABLED_CENTAUR)
MISSING_DAILY_TWEET_CONFIG_CENTAUR_C["plugins_data"]["scheduled_tweet"]["tweets"] = None

NO_PENDING_TWEETS = deepcopy(ENABLED_CENTAUR)
NO_PENDING_TWEETS["plugins_data"]["scheduled_tweet"]["tweets"] = []

NO_ACTIONS = deepcopy(ENABLED_CENTAUR)
del NO_ACTIONS["actions"]

NO_TIME_TO_RUN = deepcopy(ENABLED_CENTAUR)
NO_TIME_TO_RUN["configuration"]["plugins"]["daily_tweet"]["run_hour_utc"] = (
    datetime.datetime.utcnow().hour + 12
)

ALREADY_RAN = deepcopy(ENABLED_CENTAUR)
ALREADY_RAN["configuration"]["plugins"]["daily_tweet"]["last_run"] = (
    datetime.datetime.utcnow()
    .replace(tzinfo=datetime.timezone.utc)
    .strftime("%Y-%m-%d %H:%M:%S %Z")
)


DUMMY_CENTAUR_ID_TO_SECRETS_OK = {
    "4e77a3b1-5762-4782-830e-0e56c6c05c6f": {
        "orbis": {
            "context": "kjzl6cwe1jw149t1dw8kb1p2hzo3e0bmyuaihswjb0yl8ze9bho5vf036yy7z1a",
            "did_seed": "0101010101010101010101010101010101010101010101010101010101010101",
            "did_str": "z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
        },
        "twitter": {
            "consumer_key": "dummy_consumer_key",
            "consumer_secret": "dummy_consumer_secret",
            "access_token": "dummy_access_token",
            "access_secret": "dummy_access_secret",
        },
    }
}

DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ID = {}

DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_TWITTER = {
    "4e77a3b1-5762-4782-830e-0e56c6c05c6f": {
        "orbis": {
            "context": "kjzl6cwe1jw149t1dw8kb1p2hzo3e0bmyuaihswjb0yl8ze9bho5vf036yy7z1a",
            "did_seed": "0101010101010101010101010101010101010101010101010101010101010101",
            "did_str": "z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
        },
    }
}

DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_TWITTER_KEY = {
    "4e77a3b1-5762-4782-830e-0e56c6c05c6f": {
        "orbis": {
            "context": "kjzl6cwe1jw149t1dw8kb1p2hzo3e0bmyuaihswjb0yl8ze9bho5vf036yy7z1a",
            "did_seed": "0101010101010101010101010101010101010101010101010101010101010101",
            "did_str": "z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
        },
        "twitter": {
            "consumer_secret": "dummy_consumer_secret",
            "access_token": "dummy_access_token",
            "access_secret": "dummy_access_secret",
        },
    }
}

DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ORBIS = {
    "4e77a3b1-5762-4782-830e-0e56c6c05c6f": {
        "twitter": {
            "consumer_key": "dummy_consumer_key",
            "consumer_secret": "dummy_consumer_secret",
            "access_token": "dummy_access_token",
            "access_secret": "dummy_access_secret",
        }
    }
}

DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ORBIS_KEY = {
    "4e77a3b1-5762-4782-830e-0e56c6c05c6f": {
        "orbis": {
            "did_seed": "0101010101010101010101010101010101010101010101010101010101010101",
            "did_str": "z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
        },
        "twitter": {
            "consumer_key": "dummy_consumer_key",
            "consumer_secret": "dummy_consumer_secret",
            "access_token": "dummy_access_token",
            "access_secret": "dummy_access_secret",
        },
    }
}
