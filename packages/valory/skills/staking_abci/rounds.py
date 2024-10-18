# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
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

"""This package contains the rounds of StakingAbciApp."""

from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AbstractRound,
    AppState,
    BaseSynchronizedData,
    DegenerateRound,
    EventToTimeout,
)
from packages.valory.skills.staking_abci.payloads import (
    ActivityScorePayload,
    ActiviyUpdatePreparationPayload,
    CheckpointPreparationPayload,
)


class Event(Enum):
    """AbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"
    DONE = "done"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """


class ActivityScoreRound(AbstractRound):
    """ActivityScoreRound"""

    payload_class = ActivityScorePayload
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

class ActiviyUpdatePreparationRound(AbstractRound):
    """ActiviyUpdatePreparationRound"""

    payload_class = ActiviyUpdatePreparationPayload
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


class CheckpointPreparationRound(AbstractRound):
    """CheckpointPreparationRound"""

    payload_class = CheckpointPreparationPayload
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


class FinishedActiviyUpdatePreparationRound(DegenerateRound):
    """FinishedActiviyUpdatePreparationRound"""


class FinishedCheckpointPreparationRound(DegenerateRound):
    """FinishedCheckpointPreparationRound"""


class StakingAbciApp(AbciApp[Event]):
    """StakingAbciApp"""

    initial_round_cls: AppState = ActivityScoreRound
    initial_states: Set[AppState] = {CheckpointPreparationRound, ActivityScoreRound}
    transition_function: AbciAppTransitionFunction = {
        ActivityScoreRound: {
            Event.DONE: ActiviyUpdatePreparationRound,
            Event.NO_MAJORITY: ActivityScoreRound,
            Event.ROUND_TIMEOUT: ActivityScoreRound
        },
        ActiviyUpdatePreparationRound: {
            Event.DONE: FinishedActiviyUpdatePreparationRound,
            Event.NO_MAJORITY: ActiviyUpdatePreparationRound,
            Event.ROUND_TIMEOUT: ActiviyUpdatePreparationRound
        },
        CheckpointPreparationRound: {
            Event.DONE: FinishedCheckpointPreparationRound,
            Event.NO_MAJORITY: CheckpointPreparationRound,
            Event.ROUND_TIMEOUT: CheckpointPreparationRound
        },
        FinishedActiviyUpdatePreparationRound: {},
        FinishedCheckpointPreparationRound: {}
    }
    final_states: Set[AppState] = {FinishedCheckpointPreparationRound, FinishedActiviyUpdatePreparationRound}
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        CheckpointPreparationRound: set(),
    	ActivityScoreRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedCheckpointPreparationRound: set(),
    	FinishedActiviyUpdatePreparationRound: set(),
    }
