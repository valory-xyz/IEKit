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

from packages.valory.skills.mech_interact_abci.payloads import (
    MechRequestPayload,
    MechResponsePayload,
)


class Event(Enum):
    """MechInteractAbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    DONE = "done"
    NO_MAJORITY = "no_majority"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """


class MechRequestRound(AbstractRound):
    """MechRequestRound"""

    payload_class = MechRequestPayload
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

    def check_payload(self, payload: MechRequestPayload) -> None:
        """Check payload."""
        raise NotImplementedError

    def process_payload(self, payload: MechRequestPayload) -> None:
        """Process payload."""
        raise NotImplementedError


class MechResponseRound(AbstractRound):
    """MechResponseRound"""

    payload_class = MechResponsePayload
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

    def check_payload(self, payload: MechResponsePayload) -> None:
        """Check payload."""
        raise NotImplementedError

    def process_payload(self, payload: MechResponsePayload) -> None:
        """Process payload."""
        raise NotImplementedError


class FinishedMechRequestRound(DegenerateRound):
    """FinishedMechRequestRound"""


class FinishedMechResponseRound(DegenerateRound):
    """FinishedMechResponseRound"""


class MechInteractAbciApp(AbciApp[Event]):
    """MechInteractAbciApp"""

    initial_round_cls: AppState = MechRequestRound
    initial_states: Set[AppState] = {MechResponseRound, MechRequestRound}
    transition_function: AbciAppTransitionFunction = {
        MechRequestRound: {
            Event.DONE: FinishedMechRequestRound,
            Event.NO_MAJORITY: MechRequestRound,
            Event.ROUND_TIMEOUT: MechRequestRound
        },
        MechResponseRound: {
            Event.DONE: FinishedMechResponseRound,
            Event.NO_MAJORITY: MechResponseRound,
            Event.ROUND_TIMEOUT: MechResponseRound
        },
        FinishedMechRequestRound: {},
        FinishedMechResponseRound: {}
    }
    final_states: Set[AppState] = {FinishedMechRequestRound, FinishedMechResponseRound}
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: Set[str] = []
    db_pre_conditions: Dict[AppState, Set[str]] = {
        MechResponseRound: [],
    	MechRequestRound: [],
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedMechRequestRound: [],
    	FinishedMechResponseRound: [],
    }
