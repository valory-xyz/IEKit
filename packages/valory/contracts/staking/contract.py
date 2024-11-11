# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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

"""This module contains the class to connect to a staking contract."""

from typing import Dict

from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea.crypto.base import LedgerApi
from web3 import Web3


PUBLIC_ID = PublicId.from_str("valory/staking:0.1.0")

CONTRIBUTORS_ABI = [
    {
      "inputs": [
        {
          "internalType": "address[]",
          "name": "multisigs",
          "type": "address[]"
        },
        {
          "internalType": "uint256[]",
          "name": "activityChanges",
          "type": "uint256[]"
        }
      ],
      "name": "increaseActivity",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "address",
          "name": "",
          "type": "address"
        }
      ],
      "name": "mapAccountServiceInfo",
      "outputs": [
        {
          "internalType": "uint256",
          "name": "socialId",
          "type": "uint256"
        },
        {
          "internalType": "uint256",
          "name": "serviceId",
          "type": "uint256"
        },
        {
          "internalType": "address",
          "name": "multisig",
          "type": "address"
        },
        {
          "internalType": "address",
          "name": "stakingInstance",
          "type": "address"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
]


class Staking(Contract):
    """The staking contract."""

    contract_id = PUBLIC_ID

    @classmethod
    def build_checkpoint_tx(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
    ) -> Dict[str, bytes]:
        """Build an ERC20 approval."""
        contract_instance = cls.get_instance(ledger_api, contract_address)
        data = contract_instance.encodeABI("checkpoint", args=())
        return {"data": bytes.fromhex(data[2:])}

    @classmethod
    def build_activity_update_tx(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        updates: Dict[str, int]
    ) -> Dict[str, bytes]:
        """Build an ERC20 approval."""
        # This method is defined on the Contributors contract, not the staking one
        contract_instance = ledger_api.api.eth.contract(
            Web3.to_checksum_address(contract_address), abi=CONTRIBUTORS_ABI
        )
        multisigs = [Web3.to_checksum_address(a) for a in updates.keys()]
        activity_changes = [int(v) for v in updates.values()]
        data = contract_instance.encodeABI("increaseActivity", args=(multisigs,activity_changes))
        return {"data": bytes.fromhex(data[2:])}

    @classmethod
    def get_epoch_end(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
    ) -> Dict:
        """Get the epoch end."""
        contract_instance = cls.get_instance(ledger_api, contract_address)
        liveness = contract_instance.functions.livenessPeriod().call()
        checpoint_ts = contract_instance.functions.tsCheckpoint().call()
        epoch_end = checpoint_ts + liveness
        return dict(epoch_end=epoch_end)

    @classmethod
    def get_epoch(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
    ) -> Dict:
        """Get the epoch."""
        contract_instance = cls.get_instance(ledger_api, contract_address)
        epoch = contract_instance.functions.epochCounter().call()
        return dict(epoch=epoch)

    @classmethod
    def get_service_ids(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
    ) -> Dict:
        """Get the service id list."""
        contract_instance = cls.get_instance(ledger_api, contract_address)
        service_ids = contract_instance.functions.getServiceIds().call()
        return dict(service_ids=service_ids)

    @classmethod
    def get_account_to_service_map(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        wallet_address
    ) -> Dict:
        """Get the account to service map."""
        # This method is defined on the Contributors contract, not the staking one
        contract_instance = ledger_api.api.eth.contract(
            Web3.to_checksum_address(contract_address), abi=CONTRIBUTORS_ABI
        )
        social_id, service_id, multisig_address, staking_contract_address = contract_instance.functions.mapAccountServiceInfo(Web3.to_checksum_address(wallet_address)).call()
        return dict(
            social_id=social_id,
            service_id=service_id,
            multisig_address=multisig_address,
            staking_contract_address=staking_contract_address
        )