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

"""This module contains the shared state for the abci skill of ImpactEvaluatorSkillAbciApp."""

from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.ceramic_read_abci.models import (
    Params as CeramicReadAbciParams,
)
from packages.valory.skills.ceramic_read_abci.rounds import Event as CeramicReadEvent
from packages.valory.skills.ceramic_write_abci.models import (
    Params as CeramicWriteAbciParams,
)
from packages.valory.skills.ceramic_write_abci.models import (
    RandomnessApi as CeramicWriteRandomnessApi,
)
from packages.valory.skills.ceramic_write_abci.rounds import Event as CeramicWriteEvent
from packages.valory.skills.dynamic_nft_abci.models import (
    Params as DynamicNFTAbciParams,
)
from packages.valory.skills.dynamic_nft_abci.rounds import Event as DynamicNFTEvent
from packages.valory.skills.impact_evaluator_abci.composition import (
    ImpactEvaluatorSkillAbciApp,
)
from packages.valory.skills.reset_pause_abci.rounds import Event as ResetPauseEvent
from packages.valory.skills.twitter_scoring_abci.models import (
    Params as TwitterScoringAbciParams,
)
from packages.valory.skills.twitter_scoring_abci.rounds import (
    Event as TwitterScoringEvent,
)


CeramicReadParams = CeramicReadAbciParams
CeramicWriteParams = CeramicWriteAbciParams
DynamicNFTParams = DynamicNFTAbciParams
TwitterScoringParams = TwitterScoringAbciParams

Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
RandomnessApi = CeramicWriteRandomnessApi

MARGIN = 5
MULTIPLIER = 2


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = ImpactEvaluatorSkillAbciApp

    def setup(self) -> None:
        """Set up."""
        super().setup()
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            CeramicReadEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            CeramicWriteEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            TwitterScoringEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[DynamicNFTEvent.ROUND_TIMEOUT] = (
            self.context.params.round_timeout_seconds * MULTIPLIER
        )
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            ResetPauseEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            ResetPauseEvent.RESET_AND_PAUSE_TIMEOUT
        ] = (self.context.params.observation_interval + MARGIN)


class Params(
    CeramicReadParams, TwitterScoringParams, CeramicWriteParams, DynamicNFTParams
):
    """A model to represent params for multiple abci apps."""
