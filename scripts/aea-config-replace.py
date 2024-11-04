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
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv


AGENT_NAME = "impact_evaluator"

PATH_TO_VAR = {
    # Agent
    "models/params/args/reset_pause_duration": "RESET_PAUSE_DURATION",
    "models/params/args/reset_tendermint_after": "RESET_TENDERMINT_AFTER",
    "models/params/args/setup/all_participants": "ALL_PARTICIPANTS",
    # "models/params/args/use_acn": "USE_ACN",
    "models/params/args/use_termination": "USE_TERMINATION",

    # Chains
    "config/ledger_apis/ethereum/address": "ETHEREUM_LEDGER_RPC",
    "config/ledger_apis/ethereum/chain_id": "ETHEREUM_LEDGER_CHAIN_ID",
    "config/ledger_apis/gnosis/address": "GNOSIS_LEDGER_RPC",
    "config/ledger_apis/gnosis/chain_id": "GNOSIS_LEDGER_CHAIN_ID",
    "config/ledger_apis/base/address": "BASE_LEDGER_RPC",
    "config/ledger_apis/base/chain_id": "BASE_LEDGER_CHAIN_ID",
    "config/ledger_apis/ethereum/gas_price_strategies/eip1559/default_priority_fee": "DEFAULT_PRIORITY_FEE",
    "models/params/args/setup/safe_contract_address": "SAFE_CONTRACT_ADDRESS",
    "models/params/args/safe_contract_address_base": "SAFE_CONTRACT_ADDRESS_BASE",
    "models/params/args/transaction_service_url": "TRANSACTION_SERVICE_URL",

    # Ceramic
    "models/params/args/ceramic_api_base": "CERAMIC_API_BASE",
    "models/params/args/ceramic_did_str": "CERAMIC_DID_STR",
    "models/params/args/ceramic_did_seed": "CERAMIC_DID_SEED",
    "models/params/args/ceramic_db_stream_id": "CERAMIC_DB_STREAM_ID",
    "models/params/args/centaurs_stream_id": "CENTAURS_STREAM_ID",
    "models/params/args/manual_points_stream_id": "MANUAL_POINTS_STREAM_ID",
    "models/params/args/centaur_id_to_secrets": "CENTAUR_ID_TO_SECRETS",

    # Twitter
    "config/use_twitter_staging_api": "USE_TWITTER_STAGING_API",
    "config/twitter_staging_api": "TWITTER_STAGING_API",

    # OpenAI
    "config/use_openai_staging_api": "USE_OPENAI_STAGING_API",
    "config/openai_staging_api": "OPENAI_STAGING_API",
}

CONFIG_REGEX = r"\${.*?:(.*)}"

def find_and_replace(config, path, new_value):
    """Find and replace a variable"""

    # Find the correct section where this variable fits
    section_index = None
    for i, section in enumerate(config):
        value = section
        try:
            for part in path:
                value = value[part]
            section_index = i
        except KeyError:
            continue

    # To persist the changes in the config variable,
    # access iterating the path parts but the last part
    sub_dic = config[section_index]
    for part in path[:-1]:
        sub_dic = sub_dic[part]

    # Now, get the whole string value
    old_str_value = sub_dic[path[-1]]

    # Extract the old variable value
    match = re.match(CONFIG_REGEX, old_str_value)
    old_var_value = match.groups()[0]

    # Replace the old variable with the secret value in the complete string
    new_str_value = old_str_value.replace(old_var_value, new_value)
    sub_dic[path[-1]] = new_str_value

    return config


def main() -> None:
    """Main"""
    load_dotenv()

    # Load the aea config
    with open(Path(AGENT_NAME, "aea-config.yaml"), "r", encoding="utf-8") as file:
        config = list(yaml.safe_load_all(file))

    # Search and replace all the secrets
    for path, var in PATH_TO_VAR.items():
        try:
            config = find_and_replace(
                config,
                path.split("/"),
                os.getenv(var)
            )
        except Exception as e:
            print(f"Exception while replacing {path}:\n{e}")
            raise ValueError from e

    # Dump the updated config
    with open(Path(AGENT_NAME, "aea-config.yaml"), "w", encoding="utf-8") as file:
        yaml.dump_all(config, file, sort_keys=False)


if __name__ == "__main__":
    main()
