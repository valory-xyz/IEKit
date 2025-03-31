#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2025 Valory AG
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


import json


with open("contribute_db.json", "r", encoding="utf-8") as db_file:
    data = json.load(db_file)


for user_id, user_data in data["users"].items():
    for tweet_id, tweet in user_data["tweets"].items():
        if tweet["epoch"] and tweet["epoch"] > 38:
            print(f"Tweet {tweet_id} from user {user_data['twitter_handle']}: {tweet['epoch']} -> {38}")
            tweet["epoch"] = 38


with open("contribute_db.json", "w", encoding="utf-8") as db_file:
    json.dump(data, db_file, indent=4)
