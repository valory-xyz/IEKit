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

"""This package contains the rounds of MechInteractAbciApp."""

from typing import Dict, Set

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    EventToTimeout,
    get_name,
)
from packages.valory.skills.mech_interact_abci.states.base import (
    Event,
    SynchronizedData,
)
from packages.valory.skills.mech_interact_abci.states.final_states import (
    FinishedMechRequestRound,
    FinishedMechResponseRound,
)
from packages.valory.skills.mech_interact_abci.states.request import MechRequestRound
from packages.valory.skills.mech_interact_abci.states.response import MechResponseRound


class MechInteractAbciApp(AbciApp[Event]):
    """MechInteractAbciApp"""

    initial_round_cls: AppState = MechRequestRound
    initial_states: Set[AppState] = {MechRequestRound, MechResponseRound}
    transition_function: AbciAppTransitionFunction = {
        MechRequestRound: {
            Event.DONE: FinishedMechRequestRound,
            Event.NO_MAJORITY: MechRequestRound,
            Event.ROUND_TIMEOUT: MechRequestRound,
        },
        MechResponseRound: {
            Event.DONE: FinishedMechResponseRound,
            Event.NO_MAJORITY: MechResponseRound,
            Event.ROUND_TIMEOUT: MechResponseRound,
        },
        FinishedMechRequestRound: {},
        FinishedMechResponseRound: {},
    }
    final_states: Set[AppState] = {FinishedMechRequestRound, FinishedMechResponseRound}
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: Set[str] = {get_name(SynchronizedData.mech_responses)}
    db_pre_conditions: Dict[AppState, Set[str]] = {
        MechRequestRound: set(get_name(SynchronizedData.mech_requests)),
        MechResponseRound: set(get_name(SynchronizedData.final_tx_hash)),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedMechRequestRound: {
            get_name(SynchronizedData.final_tx_hash),
            get_name(SynchronizedData.mech_price),
        },
        FinishedMechResponseRound: set(get_name(SynchronizedData.mech_responses)),
    }
