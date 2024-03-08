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

"""This package contains the rounds of FarcasterWriteAbciApp."""

import json
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple, cast

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    DegenerateRound,
    EventToTimeout,
    OnlyKeeperSendsRound,
    get_name,
)
from packages.valory.skills.farcaster_write_abci.payloads import (
    FarcasterWritePayload,
    RandomnessPayload,
    SelectKeeperPayload,
)


class Event(Enum):
    """FarcasterWriteAbciApp Events"""

    DONE = "done"
    CONTINUE = "continue"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"
    API_ERROR = "api_error"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def write_data(self) -> list:
        """Get the write_stream_id."""
        # return cast(list, self.db.get("write_data", []))
        return [{"text": "Agent test: hello world!"}, {"text": "Agent test: and that makes two!"}]

    @property
    def write_index(self) -> int:
        """Get the write_index."""
        return cast(int, self.db.get("write_index", 0))

    @property
    def cast_ids(self) -> List[int]:
        """List of posted cast ids."""
        return cast(list, self.db.get("cast_ids", []))


class RandomnessFarcasterRound(CollectSameUntilThresholdRound):
    """A round for generating randomness"""

    payload_class = RandomnessPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_randomness)
    selection_key = (
        get_name(SynchronizedData.most_voted_randomness),
        get_name(SynchronizedData.most_voted_randomness),
    )


class SelectKeeperFarcasterRound(CollectSameUntilThresholdRound):
    """A round in which a keeper is selected for transaction submission"""

    payload_class = SelectKeeperPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_selection)
    selection_key = get_name(SynchronizedData.most_voted_keeper_address)


class FarcasterWriteRound(OnlyKeeperSendsRound):
    """FarcasterWriteRound"""

    payload_class = FarcasterWritePayload
    synchronized_data_class = SynchronizedData

    def end_block(
        self,
    ) -> Optional[
        Tuple[BaseSynchronizedData, Enum]
    ]:  # pylint: disable=too-many-return-statements
        """Process the end of the block."""
        if self.keeper_payload is None:
            return None
        keeper_payload = json.loads(
            cast(FarcasterWritePayload, self.keeper_payload).content
        )
        if not keeper_payload["success"]:
            return self.synchronized_data, Event.API_ERROR

        synchronized_data = cast(SynchronizedData, self.synchronized_data)

        # No casts to publish
        if not synchronized_data.write_data:
            return synchronized_data, Event.DONE

        write_index = synchronized_data.write_index + 1
        cast_ids = synchronized_data.cast_ids
        cast_ids.append(keeper_payload["cast_id"])

        finished_casting = write_index == len(synchronized_data.write_data)

        return (
            self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.cast_ids): cast_ids,
                    get_name(SynchronizedData.write_index): 0
                    if finished_casting
                    else write_index,
                }
            ),
            Event.DONE if finished_casting else Event.CONTINUE,
        )


class FinishedFarcasterWriteRound(DegenerateRound):
    """FinishedFarcasterWriteRound"""


class FarcasterWriteAbciApp(AbciApp[Event]):
    """FarcasterWriteAbciApp"""

    initial_round_cls: AppState = RandomnessFarcasterRound
    initial_states: Set[AppState] = {RandomnessFarcasterRound}
    transition_function: AbciAppTransitionFunction = {
        RandomnessFarcasterRound: {
            Event.DONE: SelectKeeperFarcasterRound,
            Event.NO_MAJORITY: RandomnessFarcasterRound,
            Event.ROUND_TIMEOUT: RandomnessFarcasterRound,
        },
        SelectKeeperFarcasterRound: {
            Event.DONE: FarcasterWriteRound,
            Event.NO_MAJORITY: RandomnessFarcasterRound,
            Event.ROUND_TIMEOUT: RandomnessFarcasterRound,
        },
        FarcasterWriteRound: {
            Event.DONE: FinishedFarcasterWriteRound,
            Event.CONTINUE: FarcasterWriteRound,
            Event.API_ERROR: RandomnessFarcasterRound,
            Event.ROUND_TIMEOUT: RandomnessFarcasterRound,
        },
        FinishedFarcasterWriteRound: {},
    }
    final_states: Set[AppState] = {FinishedFarcasterWriteRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        RandomnessFarcasterRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedFarcasterWriteRound: set(),
    }
