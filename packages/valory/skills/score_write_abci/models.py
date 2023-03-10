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

"""This module contains the shared state for the abci skill of ScoreWriteAbciApp."""

from typing import Any

from packages.valory.skills.abstract_round_abci.models import ApiSpecs, BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.score_write_abci.rounds import ScoreWriteAbciApp


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = ScoreWriteAbciApp


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the parameters object."""
        self.ceramic_api_base = self._ensure("ceramic_api_base", kwargs, str)
        self.ceramic_api_commit_endpoint = self._ensure(
            "ceramic_api_commit_endpoint", kwargs, str
        )
        self.ceramic_api_read_endpoint = self._ensure(
            "ceramic_api_read_endpoint", kwargs, str
        )
        self.scores_stream_id = self._ensure("scores_stream_id", kwargs, str)
        self.wallets_stream_id = self._ensure("wallets_stream_id", kwargs, str)
        self.ceramic_did_str = "did:key:" + self._ensure("ceramic_did_str", kwargs, str)
        self.ceramic_did_seed = self._ensure("ceramic_did_seed", kwargs, str)
        super().__init__(*args, **kwargs)


class RandomnessApi(ApiSpecs):
    """A model that wraps ApiSpecs for randomness api specifications."""


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
