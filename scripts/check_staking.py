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

"""This package contains code to read Contribute streams on Ceramic."""
# pylint: disable=import-error

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import dotenv
from ceramic.ceramic import Ceramic
from ceramic.streams import CONTRIBUTE_PROD_DB_STREAM_ID
from rich.console import Console
from rich.table import Table
from web3 import Web3
from web3.contract import Contract


dotenv.load_dotenv(override=True)


EPOCH = "latest"
BASE_LEDGER_RPC = os.getenv("BASE_LEDGER_RPC_ALCHEMY")
GREEN = "bold green"
RED = "bold red"
YELLOW = "bold yellow"
POINTS_PER_UPDATE = 200
web3 = Web3(Web3.HTTPProvider(BASE_LEDGER_RPC))
UNSTAKED = "UNSTAKED"
EVICTED = "EVICTED"


STAKING_CONTRACTS = {
    "Beta 1 (100 OLAS)": {
        "address": "0xe2E68dDafbdC0Ae48E39cDd1E778298e9d865cF4",
        "slots": 100,
        "required_updates": 1
    },
    "Beta 2 (300 OLAS)": {
        "address": "0x6Ce93E724606c365Fc882D4D6dfb4A0a35fE2387",
        "slots": 100,
        "required_updates": 3
    },
    "Beta 3 (500 OLAS)": {
        "address": "0x28877FFc6583170a4C9eD0121fc3195d06fd3A26",
        "slots": 100,
        "required_updates": 5
    },
}
STAKING_ABI_FILE = Path("packages", "valory", "contracts", "staking", "build", "staking.json")
CONTRIBUTORS_ABI_FILE = Path("scripts", "contributors.json")
CONTRIBUTORS_PROXY_CONTRACT_ADDRESS = "0x343F2B005cF6D70bA610CD9F1F1927049414B582"


def read_users_from_ceramic() -> Dict:
    """Read users from Ceramic"""
    ceramic = Ceramic(os.getenv("CERAMIC_API_BASE"))
    user_db, _, _ = ceramic.get_data(CONTRIBUTE_PROD_DB_STREAM_ID)
    return user_db["users"]


def read_users_from_file() -> Dict:
    """Read users from file"""
    with open("contribute_db.json", "r", encoding="utf-8") as file:
        user_db = json.load(file)
        return user_db["users"]


def get_user_by_field(users, field_name, field_value) -> Optional[Dict]:
    """Get user by field"""
    for user_id, user_data in users.items():
        if user_data.get(field_name, None) == field_value:
            return user_id
    return None


def get_contract_by_address(staking_contract_address) -> Optional[Dict]:
    """Get contract by address"""
    for contract_name, contract_data in STAKING_CONTRACTS.items():
        if contract_data["address"] == staking_contract_address:
            return contract_name
    return None


def load_contract(
    contract_address: str, abi_file_path: Path, has_abi_key: bool = True
) -> Contract:
    """Load a smart contract"""
    with open(abi_file_path, "r", encoding="utf-8") as abi_file:
        contract_abi = json.load(abi_file)
        if has_abi_key:
            contract_abi = contract_abi["abi"]

    contract = web3.eth.contract(address=contract_address, abi=contract_abi)
    return contract


def get_slots() -> dict:
    """Get the available slots in all staking contracts"""
    slots = {}

    for contract_name, contract_data in STAKING_CONTRACTS.items():
        staking_token_contract = load_contract(
            web3.to_checksum_address(contract_data["address"]), "staking_token"
        )
        ids = staking_token_contract.functions.getServiceIds().call()
        slots[contract_name] = contract_data["slots"] - len(ids)

    return slots


def get_contract_info() -> Dict:
    """Get staking contract info"""

    contract_info = STAKING_CONTRACTS

    table = Table(title="Contribute staking contracts")
    columns = ["Name", "Adress", "Epoch", "Epoch end", "Used slots"]

    for column in columns:
        table.add_column(column)

    for contract_name, contract_data in STAKING_CONTRACTS.items():
        staking_token_contract = load_contract(
            web3.to_checksum_address(contract_data["address"]), STAKING_ABI_FILE, True
        )

        epoch = staking_token_contract.functions.epochCounter().call()
        ids = staking_token_contract.functions.getServiceIds().call()
        next_epoch_start = datetime.fromtimestamp(staking_token_contract.functions.getNextRewardCheckpointTimestamp().call())

        contract_info[contract_name]["epoch"] = epoch
        contract_info[contract_name]["next_epoch_start"] = next_epoch_start.strftime("%Y-%m-%d %H:%M:%S")
        contract_info[contract_name]["slots"] = contract_data["slots"]
        contract_info[contract_name]["used_slots"] = len(ids)
        contract_info[contract_name]["free_slots"] = contract_data["slots"] - len(ids)

        row = [
            contract_name,
            contract_data["address"],
            str(epoch),
            next_epoch_start.strftime("%Y-%m-%d %H:%M:%S"),
            f"{len(ids):3d} / {contract_data['slots']:3d}"
        ]
        table.add_row(*row, style=GREEN)

    console = Console()
    console.print(table, justify="center")

    return contract_info


def get_user_info(user_data: Dict, contract_info: Dict, contributors_contract: Contract) -> Dict:  # pylint: disable=too-many-locals
    """Get user info"""

    user_wallet = user_data["wallet_address"]
    _, service_id, _, staking_contract_address = contributors_contract.functions.mapAccountServiceInfo(user_wallet).call()

    if service_id == 0:
        return {
            "staked": False,
            "color": RED
        }

    staking_token_contract = load_contract(
        web3.to_checksum_address(staking_contract_address), STAKING_ABI_FILE, True
    )
    staking_contract_name = get_contract_by_address(staking_contract_address)

    is_evicted = staking_token_contract.functions.getStakingState(service_id).call() == 2

    accrued_rewards = staking_token_contract.functions.calculateStakingReward(service_id).call()
    # this_epoch_rewards = staking_token_contract.functions.calculateStakingLastReward(service_id).call()   # needs fixing
    this_epoch = contract_info[staking_contract_name]["epoch"]

    this_epoch_tweets = [t for t in user_data["tweets"].values() if t["epoch"] == this_epoch]
    this_epoch_points = sum(t["points"] for t in this_epoch_tweets)

    required_points = POINTS_PER_UPDATE * contract_info[staking_contract_name]['required_updates']
    color = GREEN if this_epoch_points >= required_points else YELLOW
    if is_evicted:
        color = RED

    user_info = {
        "staked": True,
        "evicted": is_evicted,
        "staking_contract_name": staking_contract_name,
        "epoch": str(this_epoch),
        "this_epoch_tweets": str(len(this_epoch_tweets)),
        "required_points": f"{required_points:4d}",
        "this_epoch_points": f"{this_epoch_points:4d}",
        "next_epoch_start": contract_info[staking_contract_name]["next_epoch_start"],
        # "this_epoch_rewards": f"{this_epoch_rewards / 1e18:6.2f}",
        "accrued_rewards": f"{accrued_rewards / 1e18:6.2f}",
        "color": color
    }

    return user_info


def shorten_address(address: str) -> str:
    """Shorten address"""
    return address[:5] + "..." + address[-4:]


def print_table():
    """Prints the status table"""

    # users = read_users_from_file()
    users = read_users_from_ceramic()
    staked_users = {k: v for k, v in users.items() if v.get("service_multisig")}

    contract_info = get_contract_info()
    contributors_contract = load_contract(
        web3.to_checksum_address(CONTRIBUTORS_PROXY_CONTRACT_ADDRESS), CONTRIBUTORS_ABI_FILE, False
    )

    table = Table(title=f"Contribute staking status [{datetime.now().strftime('%H:%M:%S %Y-%m-%d')}]")
    columns = ["User ID", "X handle", "Service Safe", "Contract", "Epoch", "Tweets (this epoch)", "Points (this epoch)", "Rewards (accrued)"]

    for column in columns:
        table.add_column(column)

    for user_id, user_data in staked_users.items():

        user_info = get_user_info(user_data, contract_info, contributors_contract)
        handle = str(user_data.get("twitter_handle", None))

        # Double check stakiing status using info from the chain
        if user_info["staked"]:
            row = [
                user_id,
                "@" + handle,
                shorten_address(user_data["service_multisig"]),
                user_info["staking_contract_name"],
                user_info["epoch"] + f" [{user_info['next_epoch_start']}]" if not user_info["evicted"] else EVICTED,
                user_info["this_epoch_tweets"],
                user_info["this_epoch_points"] + " / " + user_info["required_points"],
                # user_info["this_epoch_rewards"],
                user_info["accrued_rewards"],
            ]
            style = user_info["color"]

        else:
            row = [
                user_id,
                "@" + handle,
                shorten_address(user_data["service_multisig"]),
                UNSTAKED,
                UNSTAKED,
                UNSTAKED,
                UNSTAKED,
                # UNSTAKED,
                UNSTAKED,
            ]
            style = user_info["color"]

        table.add_row(*row, style=style)

    console = Console()
    console.print(table, justify="center")

if __name__ == "__main__":
    print_table()
