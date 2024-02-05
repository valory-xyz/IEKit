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

"""This package contains the rounds of CeramicWriteAbciApp."""

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
    DONE_FINISHED = "done_finished"
    DONE_CONTINUE = "done_continue"
    DID_NOT_SEND = "did_not_send"
    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"
    VERIFICATION_ERROR = "verification_error"
    MAX_RETRIES_ERROR = "max_retries_error"


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
    def write_data(self) -> list:
        """Get the write_stream_id."""
        return cast(list, self.db.get_strict("write_data"))

    @property
    def write_index(self) -> int:
        """Get the write_index."""
        return cast(int, self.db.get("write_index", 0))

    @property
    def stream_id_to_verify(self) -> str:
        """Get the stream_id_to_verify."""
        return cast(str, self.db.get_strict("stream_id_to_verify"))

    @property
    def write_results(self) -> list:
        """Get the write_results."""
        return cast(list, self.db.get("write_results", []))

    @property
    def api_retries(self) -> int:
        """Get the api_retries."""
        return cast(int, self.db.get("api_retries", 0))

    @property
    def is_data_on_sync_db(self) -> bool:
        """Get the is_data_on_sync_db."""
        return cast(bool, self.db.get("is_data_on_sync_db", True))


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

    MAX_RETRIES_PAYLOAD = "MAX_RETRIES_PAYLOAD"

    payload_class = StreamWritePayload
    synchronized_data_class = SynchronizedData

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

        if (
            cast(StreamWritePayload, self.keeper_payload).content
            == StreamWriteRound.MAX_RETRIES_PAYLOAD
        ):
            return self.synchronized_data, Event.MAX_RETRIES_ERROR

        keeper_payload = json.loads(
            cast(StreamWritePayload, self.keeper_payload).content
        )

        if not keeper_payload["success"]:
            api_retries = cast(SynchronizedData, self.synchronized_data).api_retries
            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.api_retries): api_retries + 1,
                }
            )
            return synchronized_data, Event.API_ERROR

        synchronized_data = self.synchronized_data.update(
            synchronized_data_class=SynchronizedData,
            **{
                get_name(SynchronizedData.stream_id_to_verify): keeper_payload[
                    "stream_id_to_verify"
                ],
            }
        )

        return synchronized_data, Event.DONE


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
                return self.synchronized_data, Event.VERIFICATION_ERROR

            synchronized_data = cast(SynchronizedData, self.synchronized_data)
            next_write_index = synchronized_data.write_index + 1

            write_results = synchronized_data.write_results
            write_results.append(
                {"stream_id": synchronized_data.stream_id_to_verify, "verified": True}
            )

            # Check if we need to continue writing
            write_data = (
                synchronized_data.write_data
                if synchronized_data.is_data_on_sync_db
                else self.context.state.ceramic_data
            )

            if next_write_index < len(write_data):
                synchronized_data = synchronized_data.update(
                    synchronized_data_class=SynchronizedData,
                    **{
                        get_name(SynchronizedData.write_index): next_write_index,
                        get_name(SynchronizedData.write_results): write_results,
                    }
                )
                return synchronized_data, Event.DONE_CONTINUE
            else:
                # We have finished writing
                synchronized_data = synchronized_data.update(
                    synchronized_data_class=SynchronizedData,
                    **{
                        get_name(SynchronizedData.write_index): 0,  # reset the index
                        get_name(SynchronizedData.write_results): write_results,
                    }
                )
                return synchronized_data, Event.DONE_FINISHED

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedVerificationRound(DegenerateRound):
    """FinishedVerificationRound"""


class FinishedMaxRetriesRound(DegenerateRound):
    """FinishedMaxRetriesRound"""


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
            Event.MAX_RETRIES_ERROR: FinishedMaxRetriesRound,
        },
        VerificationRound: {
            Event.VERIFICATION_ERROR: RandomnessRound,
            Event.DONE_CONTINUE: StreamWriteRound,
            Event.DONE_FINISHED: FinishedVerificationRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
        },
        FinishedVerificationRound: {},
        FinishedMaxRetriesRound: {},
    }
    final_states: Set[AppState] = {FinishedVerificationRound, FinishedMaxRetriesRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        RandomnessRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedVerificationRound: set(),
        FinishedMaxRetriesRound: set(),
    }
