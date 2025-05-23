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

"""This package contains the rounds of AgentDBAbciApp."""

from enum import Enum
from typing import Dict, FrozenSet, Set

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    DegenerateRound,
    EventToTimeout,
)
from packages.valory.skills.agent_db_abci.payloads import AgentDBPayload


class Event(Enum):
    """AgentDBAbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"
    DONE = "done"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """


class AgentDBRound(CollectSameUntilThresholdRound):
    """AgentDBRound"""

    synchronized_data_class = SynchronizedData
    extended_requirements = ()
    payload_class = AgentDBPayload

    # This needs to be mentioned for static checkers
    # Event.DONE, Event.NO_MAJORITY, Event.ROUND_TIMEOUT


class FinishedReadingRound(DegenerateRound):
    """FinishedReadingRound"""


class AgentDBAbciApp(AbciApp[Event]):
    """AgentDBAbciApp"""

    initial_round_cls: AppState = AgentDBRound
    initial_states: Set[AppState] = {AgentDBRound}
    transition_function: AbciAppTransitionFunction = {
        AgentDBRound: {
            Event.DONE: FinishedReadingRound,
            Event.NO_MAJORITY: AgentDBRound,
            Event.ROUND_TIMEOUT: AgentDBRound,
        },
        FinishedReadingRound: {},
    }
    final_states: Set[AppState] = {FinishedReadingRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        AgentDBRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedReadingRound: set(),
    }
