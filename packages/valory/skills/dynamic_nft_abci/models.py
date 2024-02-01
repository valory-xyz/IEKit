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

"""This module contains the shared state for the abci skill of DynamicNFTAbciApp."""

import json
from typing import Any

from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.decision_making_abci.models import (
    CeramicDB as BaseCeramicDB,
)
from packages.valory.skills.decision_making_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.dynamic_nft_abci.rounds import DynamicNFTAbciApp


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = DynamicNFTAbciApp

    def setup(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the state."""
        super().setup(*args, **kwargs)


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the parameters object."""
        self.dynamic_contribution_contract_address = self._ensure(
            "dynamic_contribution_contract_address", kwargs, str
        )
        self.token_uri_base = self._ensure("token_uri_base", kwargs, str)
        self.earliest_block_to_monitor = self._ensure(
            "earliest_block_to_monitor", kwargs, int
        )
        self.points_to_image_hashes = json.loads(
            self._ensure("points_to_image_hashes", kwargs, str)
        )

        super().__init__(*args, **kwargs)


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
CeramicDB = BaseCeramicDB
