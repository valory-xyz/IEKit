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

"""This package contains round behaviours of ContributionSkillAbci."""

from typing import Set, Type

from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.contribute_db_abci.behaviours import (
    ContributeDBRoundBehaviour,
)
from packages.valory.skills.decision_making_abci.behaviours import (
    DecisionMakingRoundBehaviour,
)
from packages.valory.skills.dynamic_nft_abci.behaviours import DynamicNFTRoundBehaviour
from packages.valory.skills.impact_evaluator_abci.composition import (
    ImpactEvaluatorSkillAbciApp,
)
from packages.valory.skills.mech_interact_abci.behaviours.round_behaviour import (
    MechInteractRoundBehaviour,
)
from packages.valory.skills.olas_week_abci.behaviours import OlasWeekRoundBehaviour
from packages.valory.skills.registration_abci.behaviours import (
    AgentRegistrationRoundBehaviour,
    RegistrationStartupBehaviour,
)
from packages.valory.skills.reset_pause_abci.behaviours import (
    ResetPauseABCIConsensusBehaviour,
)
from packages.valory.skills.staking_abci.behaviours import StakingRoundBehaviour
from packages.valory.skills.termination_abci.behaviours import (
    BackgroundBehaviour,
    TerminationAbciBehaviours,
)
from packages.valory.skills.transaction_settlement_abci.behaviours import (
    TransactionSettlementRoundBehaviour,
)
from packages.valory.skills.twitter_scoring_abci.behaviours import (
    TwitterScoringRoundBehaviour,
)
from packages.valory.skills.twitter_write_abci.behaviours import (
    TwitterWriteRoundBehaviour,
)


class ImpactEvaluatorConsensusBehaviour(AbstractRoundBehaviour):
    """Class to define the behaviours this AbciApp has."""

    initial_behaviour_cls = RegistrationStartupBehaviour
    abci_app_cls = ImpactEvaluatorSkillAbciApp
    behaviours: Set[Type[BaseBehaviour]] = {
        *AgentRegistrationRoundBehaviour.behaviours,
        *ContributeDBRoundBehaviour.behaviours,
        *TwitterScoringRoundBehaviour.behaviours,
        *DynamicNFTRoundBehaviour.behaviours,
        *DecisionMakingRoundBehaviour.behaviours,
        *TwitterWriteRoundBehaviour.behaviours,
        *ResetPauseABCIConsensusBehaviour.behaviours,
        *TransactionSettlementRoundBehaviour.behaviours,
        *TerminationAbciBehaviours.behaviours,
        *OlasWeekRoundBehaviour.behaviours,
        *MechInteractRoundBehaviour.behaviours,
        *StakingRoundBehaviour.behaviours,
    }
    background_behaviours_cls = {BackgroundBehaviour}
