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
import packages.valory.skills.dynamic_nft_abci.rounds as DynamicNFTAbci
import packages.valory.skills.registration_abci.rounds as RegistrationAbci
import packages.valory.skills.reset_pause_abci.rounds as ResetAndPauseAbci
import packages.valory.skills.score_read_abci.rounds as ScoreReadAbciAbci
import packages.valory.skills.score_write_abci.rounds as ScoreWriteAbciAbci
from packages.valory.skills.abstract_round_abci.abci_app_chain import (
    AbciAppTransitionMapping,
    chain,
)


# Here we define how the transition between the FSMs should happen
# more information here: https://docs.autonolas.network/fsm_app_introduction/#composition-of-fsm-apps
abci_app_transition_mapping: AbciAppTransitionMapping = {
    RegistrationAbci.FinishedRegistrationRound: ScoreReadAbciAbci.TwitterObservationRound,
    ScoreReadAbciAbci.FinishedScoringRound: ScoreWriteAbciAbci.RandomnessRound,
    ScoreWriteAbciAbci.FinishedVerificationRound: DynamicNFTAbci.NewTokensRound,
    DynamicNFTAbci.FinishedNewTokensRound: ResetAndPauseAbci.ResetAndPauseRound,
    ResetAndPauseAbci.FinishedResetAndPauseRound: ScoreReadAbciAbci.TwitterObservationRound,
    ResetAndPauseAbci.FinishedResetAndPauseErrorRound: RegistrationAbci.RegistrationRound,
}

ImpactEvaluatorSkillAbciApp = chain(
    (
        RegistrationAbci.AgentRegistrationAbciApp,
        ScoreReadAbciAbci.ScoreReadAbciApp,
        ScoreWriteAbciAbci.ScoreWriteAbciApp,
        DynamicNFTAbci.DynamicNFTAbciApp,
        ResetAndPauseAbci.ResetPauseAbciApp,
    ),
    abci_app_transition_mapping,
)
