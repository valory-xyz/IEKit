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

"""This module contains the shared state for the abci skill of CeramicWriteAbciApp."""

from typing import Any

from packages.valory.skills.abstract_round_abci.models import ApiSpecs, BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.ceramic_read_abci.models import (
    SharedState as CeramicReadSharedState,
)
from packages.valory.skills.ceramic_write_abci.rounds import CeramicWriteAbciApp


class SharedState(CeramicReadSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = CeramicWriteAbciApp


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the parameters object."""

        self.ceramic_api_base = kwargs.get(
            "ceramic_api_base"
        )  # shared param, can't use ensure
        self.ceramic_api_create_endpoint = self._ensure(
            "ceramic_api_create_endpoint", kwargs, str
        )
        self.ceramic_api_commit_endpoint = self._ensure(
            "ceramic_api_commit_endpoint", kwargs, str
        )
        self.ceramic_api_read_endpoint = kwargs.get(
            "ceramic_api_read_endpoint"
        )  # shared param, can't use ensure

        super().__init__(*args, **kwargs)


class RandomnessApi(ApiSpecs):
    """A model that wraps ApiSpecs for randomness api specifications."""


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
