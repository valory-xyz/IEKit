# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2025 Valory AG
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

import packages.valory.skills.contribute_db_abci.rounds as ContributeDBAbci
import packages.valory.skills.decision_making_abci.rounds as DecisionMakingAbci
import packages.valory.skills.dynamic_nft_abci.rounds as DynamicNFTAbci
import packages.valory.skills.mech_interact_abci.rounds as MechInteractAbci
import packages.valory.skills.mech_interact_abci.states.final_states as MechFinalStates
import packages.valory.skills.mech_interact_abci.states.request as MechRequestStates
import packages.valory.skills.mech_interact_abci.states.response as MechResponseStates
import packages.valory.skills.olas_week_abci.rounds as WeekInOlasAbciApp
import packages.valory.skills.registration_abci.rounds as RegistrationAbci
import packages.valory.skills.reset_pause_abci.rounds as ResetAndPauseAbci
import packages.valory.skills.staking_abci.rounds as StakingAbci
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
# more information here: https://open-autonomy.docs.autonolas.tech/open-autonomy/key_concepts/fsm_app_introduction/?h=composition#composition-of-fsm-apps
abci_app_transition_mapping: AbciAppTransitionMapping = {
    RegistrationAbci.FinishedRegistrationRound: DecisionMakingAbci.DecisionMakingRound,
    DecisionMakingAbci.FinishedDecisionMakingDBLoadRound: ContributeDBAbci.DBLoadRound,
    ContributeDBAbci.FinishedLoadingRound: DecisionMakingAbci.DecisionMakingRound,
    DecisionMakingAbci.FinishedDecisionMakingWriteTwitterRound: TwitterWriteAbciApp.RandomnessTwitterRound,
    DecisionMakingAbci.FinishedDecisionMakingDoneRound: ResetAndPauseAbci.ResetAndPauseRound,
    DecisionMakingAbci.FinishedDecisionMakingWeekInOlasRound: WeekInOlasAbciApp.OlasWeekDecisionMakingRound,
    TwitterScoringAbci.FinishedTwitterCollectionRound: MechRequestStates.MechRequestRound,
    MechFinalStates.FinishedMechRequestRound: TxSettlementAbci.RandomnessTransactionSubmissionRound,
    TxSettlementAbci.FinishedTransactionSubmissionRound: DecisionMakingAbci.PostTxDecisionMakingRound,
    TxSettlementAbci.FailedRound: MechRequestStates.MechRequestRound,
    DecisionMakingAbci.FinishedDecisionMakingScoreRound: TwitterScoringAbci.TwitterDecisionMakingRound,
    DecisionMakingAbci.FinishedDecisionMakingActivityRound: StakingAbci.ActivityScoreRound,
    DecisionMakingAbci.FinishedDecisionMakingCheckpointRound: StakingAbci.CheckpointPreparationRound,
    DecisionMakingAbci.FinishedPostMechResponseRound: MechResponseStates.MechResponseRound,
    DecisionMakingAbci.FinishedPostActivityUpdateRound: StakingAbci.ActivityScoreRound,
    DecisionMakingAbci.FinishedDecisionMakingDAARound: StakingAbci.DAAPreparationRound,
    DecisionMakingAbci.FinishedPostCheckpointRound: DecisionMakingAbci.DecisionMakingRound,
    DecisionMakingAbci.FinishedPostDAARound: DecisionMakingAbci.DecisionMakingRound,
    StakingAbci.FinishedActivityRound: DecisionMakingAbci.DecisionMakingRound,
    StakingAbci.FinishedActivityUpdatePreparationRound: TxSettlementAbci.RandomnessTransactionSubmissionRound,
    StakingAbci.FinishedCheckpointPreparationRound: TxSettlementAbci.RandomnessTransactionSubmissionRound,
    StakingAbci.FinishedDAAPreparationRound: TxSettlementAbci.RandomnessTransactionSubmissionRound,
    MechFinalStates.FinishedMechResponseRound: TwitterScoringAbci.TwitterDecisionMakingRound,
    MechFinalStates.FinishedMechRequestSkipRound: TwitterScoringAbci.TwitterDecisionMakingRound,
    MechFinalStates.FinishedMechResponseTimeoutRound: MechResponseStates.MechResponseRound,
    TwitterScoringAbci.FinishedTwitterScoringRound: DynamicNFTAbci.TokenTrackRound,
    WeekInOlasAbciApp.FinishedWeekInOlasRound: DecisionMakingAbci.DecisionMakingRound,
    DynamicNFTAbci.FinishedTokenTrackRound: DecisionMakingAbci.DecisionMakingRound,
    TwitterWriteAbciApp.FinishedTwitterWriteRound: DecisionMakingAbci.DecisionMakingRound,
    ResetAndPauseAbci.FinishedResetAndPauseRound: DecisionMakingAbci.DecisionMakingRound,
    ResetAndPauseAbci.FinishedResetAndPauseErrorRound: RegistrationAbci.RegistrationRound,
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
        TwitterWriteAbciApp.TwitterWriteAbciApp,
        TwitterScoringAbci.TwitterScoringAbciApp,
        DynamicNFTAbci.DynamicNFTAbciApp,
        ContributeDBAbci.ContributeDBAbciApp,
        ResetAndPauseAbci.ResetPauseAbciApp,
        WeekInOlasAbciApp.WeekInOlasAbciApp,
        TxSettlementAbci.TransactionSubmissionAbciApp,
        MechInteractAbci.MechInteractAbciApp,
        StakingAbci.StakingAbciApp,
    ),
    abci_app_transition_mapping,
).add_background_app(termination_config)

# patch to avoid breaking changes introduced on open-autonomy v0.18.3
for state in ImpactEvaluatorSkillAbciApp.get_all_rounds():
    state.extended_requirements = ()
