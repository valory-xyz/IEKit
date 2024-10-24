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

"""This package contains code to create streams on Ceramic."""

from ceramic import Ceramic
from pathlib import Path
import json
import jsonschema
from dataclasses import dataclass
from typing import Optional

# Do not use the following keys for production
# Create your own DID using tools from Ceramic, like the glaze suite:
# glaze did:create  ->  Created DID did:key:<key> with seed <seed>
DUMMY_DID = {
    "did": "did:key:z6MkszfuezSP8ftgHRhMr8AX8uyTjtKpcia4bP19TBgmhEPs",
    "seed": "9a683e9b21777b5b159974c35c4766bc0c4522855aefc8de30876dbaa252f179"
}

@dataclass
class Stream:
    """Stream class"""
    name: str
    data_path: Path
    schema_path: Path
    stream_id: Optional[str] = None


def create_streams(streams):
    """Create data streams"""

    # We are using the Clay testnet for this. Use your own node for long term
    # storage, as testnet is periodically reset
    ceramic = Ceramic(Ceramic.DEFAULT_URL_BASE)

    for stream in streams:

        with open(stream.data_path, "r", encoding="utf-8") as data_file:
            stream_data = json.load(data_file)

        with open(stream.schema_path, "r", encoding="utf-8") as data_file:
            stream_schema = json.load(data_file)

        try:
            jsonschema.validate(instance=stream_data, schema=stream_schema)
        except jsonschema.exceptions.ValidationError as e:
            print(f"Skipping file {stream.data_path} as it does not follow the schema defined in {stream.schema_path}:\n{e}")
            continue

        stream_id = ceramic.create_stream(
            DUMMY_DID["did"],
            DUMMY_DID["seed"],
            stream_data,
        )
        stream.stream_id = stream_id
        print(f"Created stream {stream_id} with data:\n{stream_data}\n")


if __name__ == "__main__":

    streams = [
        Stream(
            name="CERAMIC_DB_STREAM_ID",
            data_path=Path("ceramic", "schemas", "default_db_stream.json"),
            schema_path=Path("ceramic", "schemas", "db_stream_schema.json")
        ),
        Stream(
            name="CENTAURS_STREAM_ID",
            data_path=Path("ceramic", "schemas", "default_centaurs_stream.json"),
            schema_path=Path("ceramic", "schemas", "centaurs_stream_schema.json")
        ),
        Stream(
            name="MANUAL_POINTS_STREAM_ID",
            data_path=Path("ceramic", "schemas", "default_generic_points_stream.json"),
            schema_path=Path("ceramic", "schemas", "generic_points_stream_schema.json")
        )
    ]

    create_streams(streams)

    env_vars = "\n".join([f"{stream.name}={stream.stream_id}" for stream in streams])
    print(f"Set your environment variables to\n{env_vars}")