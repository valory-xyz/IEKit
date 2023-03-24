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

"""This package contains the rounds of CeramicReadAbciApp."""

import json
from enum import Enum
from typing import Dict, Optional, Set, Tuple, cast

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    DegenerateRound,
    EventToTimeout,
)
from packages.valory.skills.ceramic_read_abci.payloads import StreamReadPayload


class Event(Enum):
    """CeramicReadAbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    API_ERROR = "api_error"
    NO_MAJORITY = "no_majority"
    DONE = "done"


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
        """Get the target_property_name."""
        return cast(str, self.db.get("target_property_name", None))


class StreamReadRound(CollectSameUntilThresholdRound):
    """StreamReadRound"""

    payload_class = StreamReadPayload
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = {"error": "true"}

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:

            payload = json.loads(self.most_voted_payload)

            if payload == self.ERROR_PAYLOAD:
                return self.synchronized_data, Event.API_ERROR

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    payload["target_property_name"]: payload["stream_data"],
                }
            )
            return synchronized_data, Event.DONE

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedReadingRound(DegenerateRound):
    """FinishedReadingRound"""


class CeramicReadAbciApp(AbciApp[Event]):
    """CeramicReadAbciApp"""

    initial_round_cls: AppState = StreamReadRound
    initial_states: Set[AppState] = {StreamReadRound}
    transition_function: AbciAppTransitionFunction = {
        StreamReadRound: {
            Event.DONE: FinishedReadingRound,
            Event.API_ERROR: StreamReadRound,
            Event.NO_MAJORITY: StreamReadRound,
            Event.ROUND_TIMEOUT: StreamReadRound,
        },
        FinishedReadingRound: {},
    }
    final_states: Set[AppState] = {FinishedReadingRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: Set[str] = set()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        StreamReadRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedReadingRound: set(),
    }
