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

"""This package contains code to update streams on Ceramic."""
# pylint: disable=import-error

import json
import os

import dotenv
from ceramic import Ceramic


dotenv.load_dotenv(override=True)

ceramic = Ceramic(os.getenv("CERAMIC_API_BASE"))
ceramic_did_str = "did:key:" + str(os.getenv("CERAMIC_DID_STR"))
ceramic_did_seed = os.getenv("CERAMIC_DID_SEED")

stream_id = os.getenv("CERAMIC_DB_STREAM_ID")

# Load from json
with open("stream.json", "r", encoding="utf-8") as inf:
    new_data = json.load(inf)

# Update stream
ceramic.update_stream(
    ceramic_did_str,
    ceramic_did_seed,
    stream_id,
    new_data,
)

print("Done")
