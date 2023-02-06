# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2022-2023 Valory AG
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
from packages.valory.skills.dynamic_nft_abci.models import (
    Params as DynamicNFTAbciParams,
)
from packages.valory.skills.dynamic_nft_abci.rounds import Event as DynamicNFTEvent
from packages.valory.skills.impact_evaluator_abci.composition import (
    ImpactEvaluatorSkillAbciApp,
)
from packages.valory.skills.reset_pause_abci.rounds import Event as ResetPauseEvent
from packages.valory.skills.score_read_abci.models import Params as ScoreReadAbciParams
from packages.valory.skills.score_read_abci.rounds import Event as ScoreReadEvent
from packages.valory.skills.score_write_abci.models import (
    Params as ScoreWriteAbciParams,
)
from packages.valory.skills.score_write_abci.rounds import Event as ScoreWriteEvent


ScoreReadParams = ScoreReadAbciParams
ScoreWriteParams = ScoreWriteAbciParams
DynamicNFTParams = DynamicNFTAbciParams
Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool

MARGIN = 5


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = ImpactEvaluatorSkillAbciApp

    def setup(self) -> None:
        """Set up."""
        super().setup()
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            ScoreReadEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            ScoreWriteEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            DynamicNFTEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            ResetPauseEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            ResetPauseEvent.RESET_AND_PAUSE_TIMEOUT
        ] = (self.context.params.observation_interval + MARGIN)


class Params(DynamicNFTParams):
    """A model to represent params for multiple abci apps."""
