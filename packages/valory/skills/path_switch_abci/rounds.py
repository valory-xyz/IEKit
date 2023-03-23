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

"""This package contains the rounds of PathSwitchAbciApp."""

from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AbstractRound,
    AppState,
    BaseSynchronizedData,
    DegenerateRound,
    EventToTimeout,
)

from packages.valory.skills.path_switch_abci.payloads import (
    PathSwitchPayload,
)


class Event(Enum):
    """PathSwitchAbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"
    DONE = "done"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """


class PathSwitchRound(AbstractRound):
    """PathSwitchRound"""

    payload_class = PathSwitchPayload
    payload_attribute = ""  # TODO: update
    synchronized_data_class = SynchronizedData

    # TODO: replace AbstractRound with one of CollectDifferentUntilAllRound,
    # CollectSameUntilAllRound, CollectSameUntilThresholdRound,
    # CollectDifferentUntilThresholdRound, OnlyKeeperSendsRound, VotingRound,
    # from packages/valory/skills/abstract_round_abci/base.py
    # or implement the methods

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""
        raise NotImplementedError

    def check_payload(self, payload: PathSwitchPayload) -> None:
        """Check payload."""
        raise NotImplementedError

    def process_payload(self, payload: PathSwitchPayload) -> None:
        """Process payload."""
        raise NotImplementedError


class FinishedPathSwitchRound(DegenerateRound):
    """FinishedPathSwitchRound"""


class PathSwitchAbciApp(AbciApp[Event]):
    """PathSwitchAbciApp"""

    initial_round_cls: AppState = PathSwitchRound
    initial_states: Set[AppState] = {PathSwitchRound}
    transition_function: AbciAppTransitionFunction = {
        PathSwitchRound: {
            Event.DONE: FinishedPathSwitchRound,
            Event.NO_MAJORITY: PathSwitchRound,
            Event.ROUND_TIMEOUT: PathSwitchRound
        },
        FinishedPathSwitchRound: {}
    }
    final_states: Set[AppState] = {FinishedPathSwitchRound}
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: Set[str] = []
    db_pre_conditions: Dict[AppState, Set[str]] = {
        PathSwitchRound: [],
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedPathSwitchRound: [],
    }
