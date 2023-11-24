# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2023 Valory AG
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

"""This module contains the class to connect to a ERC20 contract."""
import logging
from typing import Optional

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea_ledger_ethereum import EthereumApi


PUBLIC_ID = PublicId.from_str("valory/compatibility_fallback_handler:0.1.0")

_logger = logging.getLogger(
    f"aea.packages.{PUBLIC_ID.author}.contracts.{PUBLIC_ID.name}.contract"
)

MAGIC_VALUE = "20c13b0b"


# pylint: disable=too-many-arguments,invalid-name
class CompatibilityFallbackHandlerContract(Contract):
    """The Safe CompatibilityFallbackHandler contract."""

    contract_id = PUBLIC_ID

    @classmethod
    def is_valid_signature(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
        safe_message: bytes,
        signature: bytes,
    ) -> Optional[JSONLike]:
        """Validates a signature against a safe."""
        contract_instance = cls.get_instance(ledger_api, contract_address)

        result = ledger_api.contract_method_call(
            contract_instance=contract_instance,
            method_name="isValidSignature",
            _data=safe_message,
            _signature=signature,
        )

        return {"valid": result.hex() == MAGIC_VALUE}

    @classmethod
    def get_code(
        cls,
        ledger_api: EthereumApi,
        address: str,
    ) -> Optional[JSONLike]:
        """Gets the contract code."""

        return ledger_api.api.get_code(address)
