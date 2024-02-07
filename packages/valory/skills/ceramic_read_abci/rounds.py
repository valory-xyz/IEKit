# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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
from typing import Dict, FrozenSet, Optional, Set, Tuple, cast

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
    RETRY = "retry"


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

    @property
    def sync_on_ceramic_data(self) -> bool:
        """Get the sync_on_ceramic_data."""
        return cast(bool, self.db.get("sync_on_ceramic_data", True))


class StreamReadRound(CollectSameUntilThresholdRound):
    """StreamReadRound"""

    payload_class = StreamReadPayload
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = "ERROR_PAYLOAD"

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            if self.most_voted_payload == self.ERROR_PAYLOAD:
                return self.synchronized_data, Event.API_ERROR

            # Sync on the data
            if cast(SynchronizedData, self.synchronized_data).sync_on_ceramic_data:
                payload = json.loads(self.most_voted_payload)
                synchronized_data = self.synchronized_data.update(
                    synchronized_data_class=SynchronizedData,
                    **{
                        payload["read_target_property"]: payload["stream_data"],
                    }
                )
                return synchronized_data, Event.DONE

            # Sync on the data hash
            else:
                # For now, we require that ALL the payloads are the same
                # Alternatively, agents that do not agree on the data hash could redownload
                # data from IPFS. All agents should push to IPFS.
                event = (
                    Event.DONE
                    if len(
                        set([cast(StreamReadPayload, p).content for p in self.payloads])
                    )
                    == 1
                    else Event.RETRY
                )
                return self.synchronized_data, event

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
            Event.RETRY: StreamReadRound,
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
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        StreamReadRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedReadingRound: set(),
    }
