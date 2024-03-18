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

"""This module contains the class to connect to the wveolas_delegation contract."""
import logging
from typing import Optional

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea_ledger_ethereum import EthereumApi


PUBLIC_ID = PublicId.from_str("valory/wveolas_delegation:0.1.0")

_logger = logging.getLogger(
    f"aea.packages.{PUBLIC_ID.author}.contracts.{PUBLIC_ID.name}.contract"
)


# pylint: disable=too-many-arguments,invalid-name
class WveOLASDelegationContract(Contract):
    """The wveolas delegation contract."""

    contract_id = PUBLIC_ID

    @classmethod
    def get_votes(
        cls, ledger_api: EthereumApi, contract_address: str, voter_address: str
    ) -> Optional[JSONLike]:
        """Gets an account's voting power."""
        contract_instance = cls.get_instance(ledger_api, contract_address)

        voting_power = ledger_api.contract_method_call(
            contract_instance=contract_instance,
            method_name="votingPower",
            account=voter_address,
        )

        return {"voting_power": voting_power}
