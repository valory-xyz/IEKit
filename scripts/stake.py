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

"""Testing script to stake an account"""

import json
import os
from pathlib import Path

import dotenv
from web3 import Web3


# Get the fork
dotenv.load_dotenv(override=True)
RPC = os.getenv("BASE_LEDGER_RPC")
web3 = Web3(Web3.HTTPProvider(RPC))


def load_contract(contract_name, contract_address):
    """Load a contract"""

    with open(Path("scripts", f"{contract_name}.json"), "r", encoding="utf-8") as abi_file:
        abi = json.load(abi_file)

    return web3.eth.contract(
        address=web3.to_checksum_address(contract_address),
        abi=abi
    )

def main():
    """Main"""

    # Load the wallet
    with open(Path("keys.json"), "r", encoding="utf-8") as keys_file:
        keys = json.load(keys_file)
        wallet_address = keys[0]["address"]
        private_key = keys[0]["private_key"]

        native_balance = web3.eth.get_balance(wallet_address) / 1e18
        print(f"Wallet has {native_balance} ETH")

    # Load the contracts
    olas_contract = load_contract("Olas", "0x54330d28ca3357F294334BDC454a032e7f353416")
    contribute_manager_contract = load_contract("ContributeManager", "0xaea9ef993d8a1A164397642648DF43F053d43D85")
    staking_contract_address = "0xe2e68ddafbdc0ae48e39cdd1e778298e9d865cf4"

    # Approve OLAS
    transaction = olas_contract.functions.approve(
        contribute_manager_contract.address,
        web3.to_wei(10000, "ether")  # approved amount
    ).build_transaction(
        {
            "from": wallet_address,
            "nonce": web3.eth.get_transaction_count(web3.to_checksum_address(wallet_address)),
            "gas": 10000000,
            "gasPrice": web3.to_wei(100, "gwei"),
        }
    )
    signed_tx = web3.eth.account.sign_transaction(transaction, private_key)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    if tx_receipt.status != 1:
        raise ValueError("Approval transaction failed")

    # Stake
    transaction = contribute_manager_contract.functions.createAndStake(
        1761132611533934592,  # tsunami twitter id
        web3.to_checksum_address(staking_contract_address)
    ).build_transaction(
        {
            "from": wallet_address,
            "nonce": web3.eth.get_transaction_count(web3.to_checksum_address(wallet_address)),
            "gas": 10000000,
            "gasPrice": web3.to_wei(100, "gwei"),
            "value": web3.to_wei(2, "wei")  # required for staking
        }
    )
    signed_tx = web3.eth.account.sign_transaction(transaction, private_key)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    if tx_receipt.status != 1:
        raise ValueError("Stake transaction failed")


if __name__ == "__main__":
    main()
