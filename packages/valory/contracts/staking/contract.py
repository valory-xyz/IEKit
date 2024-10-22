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


PUBLIC_ID = PublicId.from_str("valory/staking:0.1.0")


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
        contract_instance = cls.get_instance(ledger_api, contract_address)
        data = contract_instance.encodeABI("increaseActivity", args=(updates,))
        return {"data": bytes.fromhex(data[2:])}