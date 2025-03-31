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

"""Hello world"""

import json
import os

from ceramic.ceramic import Ceramic  # pylint: disable=import-error


DUMMY_DID = {
    "did": "did:key:z6MkszfuezSP8ftgHRhMr8AX8uyTjtKpcia4bP19TBgmhEPs",
    "seed": "9a683e9b21777b5b159974c35c4766bc0c4522855aefc8de30876dbaa252f179"
}

ceramic = Ceramic(os.getenv("CERAMIC_API_BASE"))

# CREATE
print("Creating stream...")
stream_data = {"hello": "world"}
stream_id = ceramic.create_stream(
    DUMMY_DID["did"],
    DUMMY_DID["seed"],
    stream_data,
)

# READ
print("Reading stream...")
data, _, _ = ceramic.get_data(stream_id)
print(json.dumps(data, indent=4))

# UPDATE
print("Updating stream...")
new_data = {"foo": "bar"}
ceramic.update_stream(
    DUMMY_DID["did"],
    DUMMY_DID["seed"],
    stream_id,
    new_data,
)

# READ
print("Reading stream...")
data, _, _ = ceramic.get_data(stream_id)
print(json.dumps(data, indent=4))
