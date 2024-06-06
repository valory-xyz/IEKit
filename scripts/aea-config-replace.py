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


"""Updates fetched agent with correct config"""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


def main() -> None:
    """Main"""
    load_dotenv()

    with open(Path("impact_evaluator", "aea-config.yaml"), "r", encoding="utf-8") as file:
        config = list(yaml.safe_load_all(file))

        # Ledger
        config[4]["config"]["ledger_apis"]["ethereum"][
            "address"
        ] = f"${{str:{os.getenv('ETHEREUM_LEDGER_RPC')}}}"

        config[4]["config"]["ledger_apis"]["gnosis"][
            "address"
        ] = f"${{str:{os.getenv('GNOSIS_LEDGER_RPC')}}}"


        # Params
        config[6]["models"]["params"]["args"][
            "ceramic_api_base"
        ] = f"${{str:{os.getenv('CERAMIC_API_BASE')}}}"

        config[6]["models"]["params"]["args"][
            "ceramic_db_stream_id"
        ] = f"${{str:{os.getenv('CERAMIC_DB_STREAM_ID')}}}"

        config[6]["models"]["params"]["args"][
            "centaurs_stream_id"
        ] = f"${{str:{os.getenv('CENTAURS_STREAM_ID')}}}"

        config[6]["models"]["params"]["args"][
            "manual_points_stream_id"
        ] = f"${{str:{os.getenv('MANUAL_POINTS_STREAM_ID')}}}"

    with open(Path("impact_evaluator", "aea-config.yaml"), "w", encoding="utf-8") as file:
        yaml.dump_all(config, file, sort_keys=False)


if __name__ == "__main__":
    main()
