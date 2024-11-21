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

"""This package contains code to write schemas on Ceramic."""
# pylint: disable=import-error

import json
import os
from pathlib import Path

import dotenv
from ceramic import Ceramic


dotenv.load_dotenv(override=True)

ceramic = Ceramic(os.getenv("CERAMIC_API_BASE"))
ceramic_did_str = "did:key:" + str(os.getenv("CERAMIC_DID_STR"))
ceramic_did_seed = os.getenv("CERAMIC_DID_SEED")


# Step 1: create the schemas
# --------------------------

# Users db
with open(Path("ceramic", "schemas", "db_stream_schema.json"), "r", encoding="utf-8") as inf:
    schema = json.load(inf)
    stream_id = ceramic.create_stream(
        did=ceramic_did_str,
        did_seed=ceramic_did_seed,
        data=schema,
    )
    print(f"db_stream_schema -> {stream_id}")

# Centaurs db
with open(Path("ceramic", "schemas", "centaurs_stream_schema.json"), "r", encoding="utf-8") as inf:
    schema = json.load(inf)
    stream_id = ceramic.create_stream(
        did=ceramic_did_str,
        did_seed=ceramic_did_seed,
        data=schema,
    )
    print(f"centaurs_stream_schema -> {stream_id}")


# Manual points db
with open(Path("ceramic", "schemas", "generic_points_stream_schema.json"), "r", encoding="utf-8") as inf:
    schema = json.load(inf)
    stream_id = ceramic.create_stream(
        did=ceramic_did_str,
        did_seed=ceramic_did_seed,
        data=schema,
    )
    print(f"generic_points_stream_schema -> {stream_id}")

print("Run 'glaze stream:commits <stream_id>' to get the stream commit")

# Step 2: get the schema commit
# -------------------------
# glaze config:set ceramic-url https://ceramic-valory.hirenodes.io
# glaze stream:commits <stream_id>
