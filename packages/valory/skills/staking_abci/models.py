# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
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

"""This module contains the shared state for the abci skill of StakingAbciApp."""

from typing import Any

from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.staking_abci.rounds import StakingAbciApp


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = StakingAbciApp


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the parameters object."""

        self.staking_contract_addresses = kwargs.get(
            "staking_contract_addresses", []
        )
        self.contributors_contract_address_old = kwargs.get(
            "contributors_contract_address_old"
        )
        self.safe_contract_address_base = self._ensure(
            "safe_contract_address_base", kwargs, str
        )
        self.multisend_address = kwargs.get("multisend_address", "")
        self.staking_rewards_required_points = self._ensure(
            "staking_rewards_required_points", kwargs, int
        )
        super().__init__(*args, **kwargs)

Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
