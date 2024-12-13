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

"""This module contains the shared state for the abci skill of ImpactEvaluatorSkillAbciApp."""

from packages.valory.skills.abstract_round_abci.models import ApiSpecs
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
from packages.valory.skills.decision_making_abci.models import (
    CeramicDB as DecisionMakingCeramicDB,
)
from packages.valory.skills.decision_making_abci.models import (
    Params as DecisionMakingAbciParams,
)
from packages.valory.skills.decision_making_abci.rounds import (
    Event as DecisionMakingEvent,
)
from packages.valory.skills.dynamic_nft_abci.models import (
    Params as DynamicNFTAbciParams,
)
from packages.valory.skills.dynamic_nft_abci.rounds import Event as DynamicNFTEvent
from packages.valory.skills.generic_scoring_abci.rounds import (
    Event as GenericScoringEvent,
)
from packages.valory.skills.impact_evaluator_abci.composition import (
    ImpactEvaluatorSkillAbciApp,
)
from packages.valory.skills.llm_abci.models import Params as LLMAbciParams
from packages.valory.skills.llm_abci.rounds import Event as LLMEvent
from packages.valory.skills.mech_interact_abci.models import (
    MechResponseSpecs as BaseMechResponseSpecs,
)
from packages.valory.skills.mech_interact_abci.models import (
    Params as MechInteractAbciParams,
)
from packages.valory.skills.mech_interact_abci.rounds import Event as MechInteractEvent
from packages.valory.skills.olas_week_abci.models import Params as OlasWeekAbciParams
from packages.valory.skills.olas_week_abci.rounds import Event as OlasWeekEvent
from packages.valory.skills.reset_pause_abci.rounds import Event as ResetPauseEvent
from packages.valory.skills.staking_abci.models import Params as StakingAbciParams
from packages.valory.skills.staking_abci.rounds import Event as StakingEvent
from packages.valory.skills.termination_abci.models import TerminationParams
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
LLMParams = LLMAbciParams
DecisionMakingParams = DecisionMakingAbciParams
OlasWeekParams = OlasWeekAbciParams
MechInteractParams = MechInteractAbciParams

Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
RandomnessApi = CeramicWriteRandomnessApi
MechResponseSpecs = BaseMechResponseSpecs
CeramicDB = DecisionMakingCeramicDB

MARGIN = 5
MULTIPLIER = 5
CERAMIC_TIMEOUT_MULTIPLIER = 10


class RandomnessApi(ApiSpecs):
    """A model that wraps ApiSpecs for randomness api specifications."""


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = ImpactEvaluatorSkillAbciApp

    def setup(self) -> None:
        """Set up."""
        super().setup()
        ImpactEvaluatorSkillAbciApp.event_to_timeout[CeramicReadEvent.ROUND_TIMEOUT] = (
            self.context.params.round_timeout_seconds * CERAMIC_TIMEOUT_MULTIPLIER
        )
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            CeramicWriteEvent.ROUND_TIMEOUT
        ] = (self.context.params.round_timeout_seconds * CERAMIC_TIMEOUT_MULTIPLIER)
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            TwitterScoringEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            TwitterScoringEvent.TWEET_EVALUATION_ROUND_TIMEOUT
        ] = self.context.params.tweet_evaluation_round_timeout
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            GenericScoringEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[DynamicNFTEvent.ROUND_TIMEOUT] = (
            self.context.params.round_timeout_seconds * MULTIPLIER
        )
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            ResetPauseEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            ResetPauseEvent.RESET_AND_PAUSE_TIMEOUT
        ] = (self.context.params.reset_pause_duration + MARGIN)
        ImpactEvaluatorSkillAbciApp.event_to_timeout[LLMEvent.ROUND_TIMEOUT] = (
            self.context.params.round_timeout_seconds * MULTIPLIER
        )
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            DecisionMakingEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            OlasWeekEvent.ROUND_TIMEOUT * MULTIPLIER
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            MechInteractEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        ImpactEvaluatorSkillAbciApp.event_to_timeout[
            StakingEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds


class Params(
    CeramicReadParams,
    TwitterScoringParams,
    CeramicWriteParams,
    DynamicNFTParams,
    DecisionMakingParams,
    OlasWeekParams,
    MechInteractParams,
    StakingAbciParams,
    TerminationParams,
):
    """A model to represent params for multiple abci apps."""
