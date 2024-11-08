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

"""This script handles adding and removing vnets on Tenderly"""

# Recreate Tenderly networks.
#
# Requires two files ".env" and "tenderly_vnets.json":
#
# * .env file with:
#   - TENDERLY_ACCESS_KEY
#   - TENDERLY_ACCOUNT_SLUG
#   - TENDERLY_PROJECT_SLUG
#
# * tenderly_vnets.json file populated with:
# {
#     "base": {
#         "network_id": 8453,    # REQUIRED
#         "vnet_id": "value",    # AUTO-UPDATED, DON'T INCLUDE ON FIRST RUN
#         "admin_rpc": "value",  # AUTO-UPDATED, DON'T INCLUDE ON FIRST RUN
#         "public_rpc": "value", # AUTO-UPDATED, DON'T INCLUDE ON FIRST RUN
#         "vnet_slug": "value"   # AUTO-UPDATED, DON'T INCLUDE ON FIRST RUN
#         "wallets": {           # OPTIONAL, JUST FOR PRE-FUNDING WALLETS
#             "addresses": {
#                 "address_1_tag": "address_1_address",
#                 "address_2_tag": "address_2_address",
#             },
#             "funds": {
#                 "native": 100,
#                 "0xcE11e14225575945b8E6Dc0D4F2dD4C570f79d9f": 100
#             }
#         },
#     },
#
#     ... (other networks, as required)
# }
#

import json
import os
import random
import re
import string
from typing import List, Optional, Tuple

import requests
from dotenv import load_dotenv


TENDERLY_VNETS_JSON = "tenderly_vnets.json"

load_dotenv(override=True)


def _delete_vnet(
    tenderly_access_key: str, account_slug: str, project_slug: str, vnet_id: str
) -> None:
    print(f"Deleting {vnet_id}...")
    url = f"https://api.tenderly.co/api/v1/account/{account_slug}/project/{project_slug}/vnets/{vnet_id}"
    response = requests.delete(
        url=url,
        timeout=300,
        headers={"Accept": "application/json", "X-Access-Key": tenderly_access_key},
    )
    print(response)


def _create_vnet(  # pylint: disable=too-many-arguments
    tenderly_access_key: str,
    account_slug: str,
    project_slug: str,
    network_id: int,
    chain_id: int,
    vnet_slug: str,
    vnet_display_name: str,
    block_number: Optional[str] = "latest",
) -> Tuple[str | None, str | None, str | None]:
    print(f"Create fork of {network_id} at block number {block_number}")

    # Define the payload for the fork creation
    payload = {
        "slug": vnet_slug,
        "display_name": vnet_display_name,
        "fork_config": {"network_id": network_id, "block_number": str(block_number)},
        "virtual_network_config": {"chain_config": {"chain_id": chain_id}},
        "sync_state_config": {"enabled": False},
        "explorer_page_config": {
            "enabled": False,
            "verification_visibility": "bytecode",
        },
    }

    url = f"https://api.tenderly.co/api/v1/account/{account_slug}/project/{project_slug}/vnets"
    response = requests.post(
        url=url,
        timeout=300,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Access-Key": tenderly_access_key,
        },
        data=json.dumps(payload),
    )

    print(response.json())
    json_response = response.json()
    vnet_id = json_response.get("id")
    admin_rpc = next(
        (
            rpc["url"]
            for rpc in json_response.get("rpcs", [])
            if rpc["name"] == "Admin RPC"
        ),
        None,
    )
    public_rpc = next(
        (
            rpc["url"]
            for rpc in json_response.get("rpcs", [])
            if rpc["name"] == "Public RPC"
        ),
        None,
    )
    return vnet_id, admin_rpc, public_rpc


def _generate_vnet_slug(preffix: str = "vnet", length: int = 4):
    characters = string.ascii_lowercase
    return (
        preffix
        + "-"
        + "".join(random.choice(characters) for _ in range(length))  # nosec
    )


def _update_bash_variable(file_path: str, variable_name: str, new_value: str):
    pattern = re.compile(rf"^(export\s+)?{variable_name}=(.*)$")

    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    updated_lines = []
    for line in lines:
        match = pattern.match(line)
        if match:
            export_prefix = match.group(1) if match.group(1) else ""
            updated_lines.append(f"{export_prefix}{variable_name}={new_value}\n")
        else:
            updated_lines.append(line)

    with open(file_path, "w", encoding="utf-8") as file:
        file.writelines(updated_lines)


def update_rpc_variable(new_value: str, chain: str = "BASE"):
    """Updates several files"""
    # .env file
    pattern = rf"{chain.upper()}_LEDGER_RPC=(\S+)"
    env_file = ".env"

    with open(env_file, "r", encoding="utf-8") as file:
        content = file.read()

    if re.search(pattern, content, re.MULTILINE):
        content = re.sub(
            pattern,
            f"{chain.upper()}_LEDGER_RPC={new_value}",
            content,
            flags=re.MULTILINE,
        )
    else:
        content += f"{chain.upper()}_LEDGER_RPC={new_value}\n"

    with open(env_file, "w", encoding="utf-8") as file:
        file.write(content)


def _fund_wallet(  # nosec
    admin_rpc: str,
    wallet_addresses: List[str],
    amount: int,
    native_or_token_address: str = "native",
) -> None:
    print(f"Funding wallets {wallet_addresses} with token {native_or_token_address}...")
    if native_or_token_address == "native":  # nosec
        json_data = {
            "jsonrpc": "2.0",
            "method": "tenderly_setBalance",
            "params": [
                wallet_addresses,
                hex(int(amount * 1e18)),  # to wei
            ],
            "id": "1234",
        }
    else:
        json_data = {
            "jsonrpc": "2.0",
            "method": "tenderly_setErc20Balance",
            "params": [
                native_or_token_address,
                wallet_addresses,
                hex(int(amount * 1e18)),  # to wei
            ],
            "id": "1234",
        }

    response = requests.post(
        url=admin_rpc,
        timeout=300,
        headers={"Content-Type": "application/json"},
        json=json_data,
    )
    if response.status_code != 200:
        print(response.status_code)
        try:
            print(response.json())
        except requests.exceptions.JSONDecodeError:
            pass


def main() -> None:  # pylint: disable=too-many-locals
    """Main"""
    print("Recreating Tenderly Networks")

    account_slug = os.getenv("TENDERLY_ACCOUNT_SLUG")
    project_slug = os.getenv("TENDERLY_PROJECT_SLUG")
    tenderly_access_key = os.getenv("TENDERLY_ACCESS_KEY")

    try:
        with open(TENDERLY_VNETS_JSON, "r", encoding="utf-8") as file:
            vnet_ids = json.load(file)
    except FileNotFoundError:
        vnet_ids = {}

    for key, data in vnet_ids.items():
        if "vnet_id" in data:
            # Delete existing vnets
            _delete_vnet(
                tenderly_access_key=tenderly_access_key,
                account_slug=account_slug,
                project_slug=project_slug,
                vnet_id=data["vnet_id"],
            )

        # Create new network
        network_id = data["network_id"]
        vnet_slug = _generate_vnet_slug(preffix=key)

        vnet_id, admin_rpc, public_rpc = _create_vnet(
            tenderly_access_key=tenderly_access_key,
            account_slug=account_slug,
            project_slug=project_slug,
            network_id=network_id,
            chain_id=network_id,
            vnet_slug=vnet_slug,
            vnet_display_name=vnet_slug,
        )

        if vnet_id is not None:
            data["vnet_id"] = vnet_id
        else:
            data.pop("vnet_id", None)
        data["admin_rpc"] = admin_rpc
        data["public_rpc"] = public_rpc
        data["vnet_slug"] = vnet_slug

        # Save file
        with open(TENDERLY_VNETS_JSON, "w", encoding="utf-8") as file:
            json.dump(vnet_ids, file, ensure_ascii=False, indent=4)

        # Fund wallets
        wallets = vnet_ids[key].get("wallets", {})
        for fund_type, amount in wallets["funds"].items():
            native_or_token_address = "native" if fund_type == "native" else fund_type

            _fund_wallet(
                admin_rpc=vnet_ids[key]["admin_rpc"],
                wallet_addresses=list(wallets["addresses"].values()),
                amount=amount,
                native_or_token_address=native_or_token_address,
            )

    # OPTIONAL - Update variables on bash file
    # bash_file = "run_operate.sh"
    # _update_bash_variable(bash_file, "BASE_RPC", vnet_ids["base"]["admin_rpc"])
    # _update_bash_variable(bash_file, "OPTIMISM_RPC", vnet_ids["optimism"]["admin_rpc"])
    # _update_bash_variable(bash_file, "ETHEREUM_RPC", vnet_ids["ethereum"]["admin_rpc"])

    update_rpc_variable(chain="base", new_value=vnet_ids["base"]["admin_rpc"])
    print("Done!")


if __name__ == "__main__":
    main()
