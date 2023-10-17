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

"""This package contains round behaviours of ImpactEvaluatorSkillAbciApp."""

import packages.valory.skills.ceramic_read_abci.rounds as CeramicReadAbci
import packages.valory.skills.ceramic_write_abci.rounds as CeramicWriteAbci
import packages.valory.skills.decision_making_abci.rounds as DecisionMakingAbci
import packages.valory.skills.dynamic_nft_abci.rounds as DynamicNFTAbci
import packages.valory.skills.generic_scoring_abci.rounds as GenericScoringAbci
import packages.valory.skills.llm_abci.rounds as LLMAbciApp
import packages.valory.skills.mech_interact_abci.rounds as MechInteractAbci
import packages.valory.skills.mech_interact_abci.states.final_states
import packages.valory.skills.mech_interact_abci.states.request
import packages.valory.skills.mech_interact_abci.states.response
import packages.valory.skills.olas_week_abci.rounds as WeekInOlasAbciApp
import packages.valory.skills.registration_abci.rounds as RegistrationAbci
import packages.valory.skills.reset_pause_abci.rounds as ResetAndPauseAbci
import packages.valory.skills.transaction_settlement_abci.rounds as TxSettlementAbci
import packages.valory.skills.twitter_scoring_abci.rounds as TwitterScoringAbci
import packages.valory.skills.twitter_write_abci.rounds as TwitterWriteAbciApp
from packages.valory.skills.abstract_round_abci.abci_app_chain import (
    AbciAppTransitionMapping,
    chain,
)
from packages.valory.skills.abstract_round_abci.base import BackgroundAppConfig
from packages.valory.skills.termination_abci.rounds import (
    BackgroundRound,
    Event,
    TerminationAbciApp,
)


# Here we define how the transition between the FSMs should happen
# more information here: https://docs.autonolas.network/fsm_app_introduction/#composition-of-fsm-apps
abci_app_transition_mapping: AbciAppTransitionMapping = {
    RegistrationAbci.FinishedRegistrationRound: DecisionMakingAbci.DecisionMakingRound,
    DecisionMakingAbci.FinishedDecisionMakingReadCentaursRound: CeramicReadAbci.StreamReadRound,
    DecisionMakingAbci.FinishedDecisionMakingLLMRound: LLMAbciApp.LLMRandomnessRound,
    DecisionMakingAbci.FinishedDecisionMakingWriteTwitterRound: TwitterWriteAbciApp.RandomnessTwitterRound,
    DecisionMakingAbci.FinishedDecisionMakingWriteOrbisRound: CeramicWriteAbci.RandomnessRound,
    DecisionMakingAbci.FinishedDecisionMakingUpdateCentaurRound: CeramicWriteAbci.RandomnessRound,
    DecisionMakingAbci.FinishedDecisionMakingReadContributeDBRound: CeramicReadAbci.StreamReadRound,
    DecisionMakingAbci.FinishedDecisionMakingWriteContributeDBRound: CeramicWriteAbci.RandomnessRound,
    DecisionMakingAbci.FinishedDecisionMakingReadManualPointsRound: CeramicReadAbci.StreamReadRound,
    DecisionMakingAbci.FinishedDecisionMakingScoreRound: GenericScoringAbci.GenericScoringRound,
    DecisionMakingAbci.FinishedDecisionMakingDoneRound: ResetAndPauseAbci.ResetAndPauseRound,
    DecisionMakingAbci.FinishedDecisionMakingWeekInOlasRound: WeekInOlasAbciApp.OlasWeekDecisionMakingRound,
    GenericScoringAbci.FinishedGenericScoringRound: TwitterScoringAbci.TwitterDecisionMakingRound,
    TwitterScoringAbci.FinishedTwitterCollectionRound: packages.valory.skills.mech_interact_abci.states.response.MechResponseRound,
    packages.valory.skills.mech_interact_abci.states.final_states.FinishedMechResponseRound: packages.valory.skills.mech_interact_abci.states.request.MechRequestRound,
    packages.valory.skills.mech_interact_abci.states.final_states.FinishedMechRequestRound: TxSettlementAbci.RandomnessTransactionSubmissionRound,
    TxSettlementAbci.FinishedTransactionSubmissionRound: TwitterScoringAbci.TwitterDecisionMakingRound,
    TxSettlementAbci.FailedRound: packages.valory.skills.mech_interact_abci.states.request.MechRequestRound,
    TwitterScoringAbci.FinishedTwitterScoringRound: DynamicNFTAbci.TokenTrackRound,
    WeekInOlasAbciApp.FinishedWeekInOlasRound: DecisionMakingAbci.DecisionMakingRound,
    DynamicNFTAbci.FinishedTokenTrackRound: DecisionMakingAbci.DecisionMakingRound,
    LLMAbciApp.FinishedLLMRound: DecisionMakingAbci.DecisionMakingRound,
    TwitterWriteAbciApp.FinishedTwitterWriteRound: DecisionMakingAbci.DecisionMakingRound,
    CeramicReadAbci.FinishedReadingRound: DecisionMakingAbci.DecisionMakingRound,
    CeramicWriteAbci.FinishedVerificationRound: DecisionMakingAbci.DecisionMakingRound,
    CeramicWriteAbci.FinishedMaxRetriesRound: DecisionMakingAbci.DecisionMakingRound,
    ResetAndPauseAbci.FinishedResetAndPauseRound: DecisionMakingAbci.DecisionMakingRound,
    ResetAndPauseAbci.FinishedResetAndPauseErrorRound: ResetAndPauseAbci.ResetAndPauseRound,
}

termination_config = BackgroundAppConfig(
    round_cls=BackgroundRound,
    start_event=Event.TERMINATE,
    abci_app=TerminationAbciApp,
)


ImpactEvaluatorSkillAbciApp = chain(
    (
        RegistrationAbci.AgentRegistrationAbciApp,
        DecisionMakingAbci.DecisionMakingAbciApp,
        LLMAbciApp.LLMAbciApp,
        TwitterWriteAbciApp.TwitterWriteAbciApp,
        CeramicReadAbci.CeramicReadAbciApp,
        GenericScoringAbci.GenericScoringAbciApp,
        TwitterScoringAbci.TwitterScoringAbciApp,
        DynamicNFTAbci.DynamicNFTAbciApp,
        CeramicWriteAbci.CeramicWriteAbciApp,
        ResetAndPauseAbci.ResetPauseAbciApp,
        WeekInOlasAbciApp.WeekInOlasAbciApp,
        TxSettlementAbci.TransactionSubmissionAbciApp,
        MechInteractAbci.MechInteractAbciApp,
    ),
    abci_app_transition_mapping,
).add_background_app(termination_config)
