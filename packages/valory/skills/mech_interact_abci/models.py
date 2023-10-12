# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
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

"""This module contains the models for the abci skill of MechInteractAbciApp."""

from dataclasses import dataclass
from typing import Any, Optional

from aea.exceptions import enforce
from hexbytes import HexBytes

from packages.valory.contracts.multisend.contract import MultiSendOperation
from packages.valory.skills.abstract_round_abci.models import ApiSpecs, BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.mech_interact_abci.rounds import MechInteractAbciApp


Params = BaseParams
Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool


class MechResponseSpecs(ApiSpecs):
    """A model that wraps ApiSpecs for the Mech's response specifications."""


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = MechInteractAbciApp


class MechParams(BaseParams):
    """The mech interact abci skill's parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up the mech-interaction parameters."""
        multisend_address = kwargs.get("multisend_address", None)
        enforce(multisend_address is not None, "Multisend address not specified!")
        self.multisend_address: str = multisend_address
        self.multisend_batch_size: int = self._ensure(
            "multisend_batch_size", kwargs, int
        )
        self.mech_agent_address: str = self._ensure("mech_agent_address", kwargs, str)
        self._ipfs_address: str = self._ensure("ipfs_address", kwargs, str)
        super().__init__(*args, **kwargs)

    @property
    def ipfs_address(self) -> str:
        """Get the IPFS address."""
        if self._ipfs_address.endswith("/"):
            return self._ipfs_address
        return f"{self._ipfs_address}/"


@dataclass
class MechMetadata:
    """A Mech's metadata."""

    prompt: str
    tool: str
    nonce: str


@dataclass
class MultisendBatch:
    """A structure representing a single transaction of a multisend."""

    to: str
    data: HexBytes
    value: int = 0
    operation: MultiSendOperation = MultiSendOperation.CALL


@dataclass
class MechRequest:
    """A Mech's request."""

    data: str = ""
    requestId: int = 0


@dataclass
class MechInteractionResponse(MechRequest):
    """A structure for the response of a mech interaction task."""

    nonce: str = ""
    result: Optional[str] = None
    error: str = "Unknown"

    def retries_exceeded(self) -> None:
        """Set an incorrect format response."""
        self.error = "Retries were exceeded while trying to get the mech's response."

    def incorrect_format(self, res: Any) -> None:
        """Set an incorrect format response."""
        self.error = f"The response's format was unexpected: {res}"
