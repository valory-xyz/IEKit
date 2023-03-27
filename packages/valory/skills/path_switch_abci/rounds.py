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

import json
from enum import Enum
from typing import Dict, FrozenSet, Optional, Set, Tuple, cast

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    DegenerateRound,
    EventToTimeout,
    get_name,
)
from packages.valory.skills.path_switch_abci.payloads import PathSwitchPayload


class Event(Enum):
    """PathSwitchAbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"
    DONE_READ = "done_read"
    DONE_SCORE = "done_score"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def read_stream_id(self) -> Optional[str]:
        """Get the read_stream_id."""
        return cast(str, self.db.get("read_stream_id", None))

    @property
    def read_target_property(self) -> Optional[str]:
        """Get the read_target_property."""
        return cast(str, self.db.get("read_target_property", None))


class PathSwitchRound(CollectSameUntilThresholdRound):
    """PathSwitchRound"""

    payload_class = PathSwitchPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:

            # If read_stream_id has not yet been set -> set it and read it
            if not cast(SynchronizedData, self.synchronized_data).read_stream_id:
                payload = json.loads(self.most_voted_payload)

                synchronized_data = self.synchronized_data.update(
                    synchronized_data_class=SynchronizedData,
                    **{
                        get_name(SynchronizedData.read_stream_id): payload[
                            "read_stream_id"
                        ],
                        get_name(SynchronizedData.read_target_property): payload[
                            "read_target_property"
                        ],
                    }
                )

                return synchronized_data, Event.DONE_READ

            return self.synchronized_data, Event.DONE_SCORE

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedPathSwitchReadRound(DegenerateRound):
    """FinishedPathSwitchReadRound"""


class FinishedPathSwitchScoreRound(DegenerateRound):
    """FinishedPathSwitchScoreRound"""


class PathSwitchAbciApp(AbciApp[Event]):
    """PathSwitchAbciApp"""

    initial_round_cls: AppState = PathSwitchRound
    initial_states: Set[AppState] = {PathSwitchRound}
    transition_function: AbciAppTransitionFunction = {
        PathSwitchRound: {
            Event.DONE_READ: FinishedPathSwitchReadRound,
            Event.DONE_SCORE: FinishedPathSwitchScoreRound,
            Event.NO_MAJORITY: PathSwitchRound,
            Event.ROUND_TIMEOUT: PathSwitchRound,
        },
        FinishedPathSwitchReadRound: {},
        FinishedPathSwitchScoreRound: {},
    }
    final_states: Set[AppState] = {
        FinishedPathSwitchReadRound,
        FinishedPathSwitchScoreRound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset(
        ["read_stream_id", "read_target_property"]
    )
    db_pre_conditions: Dict[AppState, Set[str]] = {
        PathSwitchRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedPathSwitchReadRound: set(),
        FinishedPathSwitchScoreRound: set(),
    }
