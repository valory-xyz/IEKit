# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2025 Valory AG
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

import packages.valory.skills.farcaster_write_abci.rounds as FarcasterWriteAbci
import packages.valory.skills.registration_abci.rounds as RegistrationAbci
import packages.valory.skills.reset_pause_abci.rounds as ResetAndPauseAbci
from packages.valory.skills.abstract_round_abci.abci_app_chain import (
    AbciAppTransitionMapping,
    chain,
)


# Here we define how the transition between the FSMs should happen
# more information here: https://open-autonomy.docs.autonolas.tech/fsm_app_introduction/#composition-of-fsm-apps
abci_app_transition_mapping: AbciAppTransitionMapping = {
    RegistrationAbci.FinishedRegistrationRound: FarcasterWriteAbci.RandomnessFarcasterRound,
    FarcasterWriteAbci.FinishedFarcasterWriteRound: ResetAndPauseAbci.ResetAndPauseRound,
    ResetAndPauseAbci.FinishedResetAndPauseRound: FarcasterWriteAbci.RandomnessFarcasterRound,
    ResetAndPauseAbci.FinishedResetAndPauseErrorRound: ResetAndPauseAbci.ResetAndPauseRound,
}

FarcasterTestSkillAbciApp = chain(
    (
        RegistrationAbci.AgentRegistrationAbciApp,
        FarcasterWriteAbci.FarcasterWriteAbciApp,
        ResetAndPauseAbci.ResetPauseAbciApp,
    ),
    abci_app_transition_mapping,
)

# patch to avoid breaking changes introduced on open-autonomy v0.18.3
for state in FarcasterTestSkillAbciApp.get_all_rounds():
    state.extended_requirements = ()
