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

"""This module contains the shared state for the abci skill of FarcasterTestSkillAbciApp."""

from packages.valory.skills.abstract_round_abci.models import ApiSpecs
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.farcaster_test_abci.composition import (
    FarcasterTestSkillAbciApp,
)
from packages.valory.skills.farcaster_write_abci.models import (
    Params as FarcasterWriteParams,
)
from packages.valory.skills.farcaster_write_abci.models import (
    RandomnessApi as FarcasterWriteRandomnessApi,
)
from packages.valory.skills.farcaster_write_abci.rounds import (
    Event as FarcasterWriteEvent,
)
from packages.valory.skills.reset_pause_abci.rounds import Event as ResetPauseEvent


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
RandomnessApi = FarcasterWriteRandomnessApi

MARGIN = 5
MULTIPLIER = 2


class RandomnessApi(ApiSpecs):
    """A model that wraps ApiSpecs for randomness api specifications."""


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = FarcasterTestSkillAbciApp

    def setup(self) -> None:
        """Set up."""
        super().setup()

        FarcasterTestSkillAbciApp.event_to_timeout[
            ResetPauseEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds

        FarcasterTestSkillAbciApp.event_to_timeout[
            ResetPauseEvent.RESET_AND_PAUSE_TIMEOUT
        ] = (self.context.params.reset_pause_duration + MARGIN)

        FarcasterTestSkillAbciApp.event_to_timeout[
            FarcasterWriteEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds


class Params(
    FarcasterWriteParams,

):
    """A model to represent params for multiple abci apps."""
