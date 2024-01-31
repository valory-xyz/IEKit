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

"""This package contains the rounds of GenericScoringAbciApp."""

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
from packages.valory.skills.generic_scoring_abci.payloads import GenericScoringPayload


class Event(Enum):
    """GenericScoringAbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    DONE = "done"
    NO_MAJORITY = "no_majority"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def score_data(self) -> dict:
        """Get the read_stream_id."""
        return cast(dict, self.db.get_strict("score_data"))

    @property
    def pending_write(self) -> bool:
        """Checks whether there are changes pending to be written to Ceramic."""
        return cast(bool, self.db.get("pending_write", False))


class GenericScoringRound(CollectSameUntilThresholdRound):
    """GenericScoringRound"""

    payload_class = GenericScoringPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            payload = json.loads(self.most_voted_payload)
            self.context.ceramic_db.apply_diff(payload["ceramic_diff"])

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.pending_write): payload["pending_write"],
                }
            )

            return synchronized_data, Event.DONE

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedGenericScoringRound(DegenerateRound):
    """FinishedGenericScoringRound"""


class GenericScoringAbciApp(AbciApp[Event]):
    """GenericScoringAbciApp"""

    initial_round_cls: AppState = GenericScoringRound
    initial_states: Set[AppState] = {GenericScoringRound}
    transition_function: AbciAppTransitionFunction = {
        GenericScoringRound: {
            Event.DONE: FinishedGenericScoringRound,
            Event.NO_MAJORITY: GenericScoringRound,
            Event.ROUND_TIMEOUT: GenericScoringRound,
        },
        FinishedGenericScoringRound: {},
    }
    final_states: Set[AppState] = {FinishedGenericScoringRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset(
        [
            "ceramic_db",
            "pending_write",
        ]
    )
    db_pre_conditions: Dict[AppState, Set[str]] = {
        GenericScoringRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedGenericScoringRound: set(),
    }
