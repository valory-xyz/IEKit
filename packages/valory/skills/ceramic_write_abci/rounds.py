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

"""This package contains the rounds of CeramicWriteAbciApp."""

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
    OnlyKeeperSendsRound,
    get_name,
)
from packages.valory.skills.ceramic_write_abci.payloads import (
    RandomnessPayload,
    SelectKeeperPayload,
    StreamWritePayload,
    VerificationPayload,
)


class Event(Enum):
    """CeramicWriteAbciApp Events"""

    API_ERROR = "api_error"
    DONE = "done"
    DID_NOT_SEND = "did_not_send"
    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def most_voted_randomness_round(self) -> int:  # pragma: no cover
        """Get the most voted randomness round."""
        round_ = self.db.get_strict("most_voted_randomness_round")
        return cast(int, round_)

    @property
    def write_stream_id(self) -> Optional[str]:
        """Get the write_stream_id."""
        return self.db.get("write_stream_id", None)

    @property
    def write_target_property(self) -> Optional[str]:
        """Get the write_target_property."""
        return self.db.get("write_target_property", None)


class RandomnessRound(CollectSameUntilThresholdRound):
    """A round for generating randomness"""

    payload_class = RandomnessPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_randomness)
    selection_key = (
        get_name(SynchronizedData.most_voted_randomness_round),
        get_name(SynchronizedData.most_voted_randomness),
    )


class SelectKeeperRound(CollectSameUntilThresholdRound):
    """A round in which a keeper is selected for transaction submission"""

    payload_class = SelectKeeperPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_selection)
    selection_key = get_name(SynchronizedData.most_voted_keeper_address)


class StreamWriteRound(OnlyKeeperSendsRound):
    """StreamWriteRound"""

    payload_class = StreamWritePayload
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = "error"
    SUCCCESS_PAYLOAD = "success"

    def end_block(
        self,
    ) -> Optional[
        Tuple[BaseSynchronizedData, Enum]
    ]:  # pylint: disable=too-many-return-statements
        """Process the end of the block."""
        if self.keeper_payload is None:
            return None

        if self.keeper_payload is None:  # pragma: no cover
            return self.synchronized_data, Event.DID_NOT_SEND

        if cast(StreamWritePayload, self.keeper_payload).content == self.ERROR_PAYLOAD:
            return self.synchronized_data, Event.API_ERROR

        return self.synchronized_data, Event.DONE


class VerificationRound(CollectSameUntilThresholdRound):
    """VerificationRound"""

    payload_class = VerificationPayload
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = "error"
    SUCCCESS_PAYLOAD = "success"

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:

            if self.most_voted_payload == self.ERROR_PAYLOAD:
                return self.synchronized_data, Event.API_ERROR

            return self.synchronized_data, Event.DONE

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedVerificationRound(DegenerateRound):
    """FinishedVerificationRound"""


class CeramicWriteAbciApp(AbciApp[Event]):
    """CeramicWriteAbciApp"""

    initial_round_cls: AppState = RandomnessRound
    initial_states: Set[AppState] = {RandomnessRound}
    transition_function: AbciAppTransitionFunction = {
        RandomnessRound: {
            Event.DONE: SelectKeeperRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
        },
        SelectKeeperRound: {
            Event.DONE: StreamWriteRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
        },
        StreamWriteRound: {
            Event.API_ERROR: RandomnessRound,
            Event.DID_NOT_SEND: RandomnessRound,
            Event.DONE: VerificationRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
        },
        VerificationRound: {
            Event.API_ERROR: RandomnessRound,
            Event.DONE: FinishedVerificationRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
        },
        FinishedVerificationRound: {},
    }
    final_states: Set[AppState] = {FinishedVerificationRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        RandomnessRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedVerificationRound: set(),
    }
