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
    #     },
    #
    #     ... (other networks, as required)
    # }
#

import json
import os
import random
import re
import requests
import string
from typing import Tuple, Optional
from dotenv import load_dotenv


TENDERLY_VNETS_JSON = 'tenderly_vnets.json'

load_dotenv()


def _delete_vnet(
    tenderly_access_key: str,
    account_slug: str,
    project_slug: str,
    vnet_id: str
) -> None:
    print(f"Deleting {vnet_id}...")
    url = f"https://api.tenderly.co/api/v1/account/{account_slug}/project/{project_slug}/vnets/{vnet_id}"
    response = requests.delete(
        url=url,
        timeout=300,
        headers={
            "Accept": "application/json",
            "X-Access-Key": tenderly_access_key
        }
    )
    print(response)


def _create_vnet(
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
        "fork_config": {
            "network_id": network_id,
            "block_number": str(block_number)
        },
        "virtual_network_config": {
            "chain_config": {
                "chain_id": chain_id
            }
        },
        "sync_state_config": {
            "enabled": False
        },
        "explorer_page_config": {
            "enabled": False,
            "verification_visibility": "bytecode"
        }
    }

    url = f"https://api.tenderly.co/api/v1/account/{account_slug}/project/{project_slug}/vnets"
    response = requests.post(
        url=url,
        timeout=300,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Access-Key": tenderly_access_key
        },
        data=json.dumps(payload)
    )

    print(response.json())
    json_response = response.json()
    vnet_id = json_response.get('id')
    admin_rpc = next((rpc['url'] for rpc in json_response.get('rpcs', []) if rpc['name'] == "Admin RPC"), None)
    public_rpc = next((rpc['url'] for rpc in json_response.get('rpcs', []) if rpc['name'] == "Public RPC"), None)
    return vnet_id, admin_rpc, public_rpc


def _generate_vnet_slug(preffix: str="vnet", length: int=4):
    characters = string.ascii_lowercase
    return preffix + '-' + ''.join(random.choice(characters) for _ in range(length))


def _update_bash_variable(file_path: str, variable_name: str, new_value: str):
    pattern = re.compile(rf'^(export\s+)?{variable_name}=(.*)$')

    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    updated_lines = []
    for line in lines:
        match = pattern.match(line)
        if match:
            export_prefix = match.group(1) if match.group(1) else ''
            updated_lines.append(f'{export_prefix}{variable_name}={new_value}\n')
        else:
            updated_lines.append(line)

    with open(file_path, 'w', encoding='utf-8') as file:
        file.writelines(updated_lines)


def main() -> None:
    print("Recreating Tenderly Networks")

    account_slug = os.getenv("TENDERLY_ACCOUNT_SLUG")
    project_slug = os.getenv("TENDERLY_PROJECT_SLUG")
    tenderly_access_key = os.getenv("TENDERLY_ACCESS_KEY")

    try:
        with open(TENDERLY_VNETS_JSON, 'r', encoding='utf-8') as file:
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
                vnet_id=data["vnet_id"]
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
        with open(TENDERLY_VNETS_JSON, 'w', encoding='utf-8') as file:
            json.dump(vnet_ids, file, ensure_ascii=False, indent=4)

    # OPTIONAL - Update variables on bash file
    # bash_file = "run_operate.sh"
    # _update_bash_variable(bash_file, "BASE_RPC", vnet_ids["base"]["admin_rpc"])
    # _update_bash_variable(bash_file, "OPTIMISM_RPC", vnet_ids["optimism"]["admin_rpc"])
    # _update_bash_variable(bash_file, "ETHEREUM_RPC", vnet_ids["ethereum"]["admin_rpc"])
    # print("Done!")


if __name__ == "__main__":
    main()
