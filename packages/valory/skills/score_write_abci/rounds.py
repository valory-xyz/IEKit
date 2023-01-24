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

"""This package contains the rounds of ScoreWriteAbciApp."""

import json
from abc import ABC
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, cast, Deque

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AbstractRound,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    DegenerateRound,
    EventToTimeout,
    TransactionType,
    get_name,
)
from packages.valory.skills.score_write_abci.payloads import (
    RandomnessPayload,
    SelectKeeperPayload,
    CeramicWritePayload,
    VerificationPayload
)


class Event(Enum):
    """ScoreWriteAbciApp Events"""

    DONE = "done"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"
    API_ERROR = "api_error"
    INCORRECT_SERIALIZATION = "incorrect_serialization"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def user_to_scores(self) -> dict:
        """Get the user scores."""
        return cast(dict, self.db.get("user_to_scores", {}))

    @property
    def keepers(self) -> Deque[str]:
        """Get the current cycle's keepers who have tried to submit a transaction."""
        if self.is_keeper_set:
            keepers_unparsed = cast(str, self.db.get_strict("keepers"))
            keepers_parsed = textwrap.wrap(
                keepers_unparsed[RETRIES_LENGTH:], ADDRESS_LENGTH
            )
            return deque(keepers_parsed)
        return deque()

    @property
    def keepers_threshold_exceeded(self) -> bool:
        """Check if the number of selected keepers has exceeded the allowed limit."""
        malicious_threshold = self.nb_participants // 3
        return len(self.keepers) > malicious_threshold

    @property
    def most_voted_keeper_address(self) -> str:
        """Get the first in priority keeper to try to re-submit a transaction."""
        return self.keepers[0]

    @property  # TODO: overrides base property, investigate
    def is_keeper_set(self) -> bool:
        """Check whether keeper is set."""
        return bool(self.db.get("keepers", False))

    @property
    def keeper_retries(self) -> int:
        """Get the number of times the current keeper has retried."""
        if self.is_keeper_set:
            keepers_unparsed = cast(str, self.db.get_strict("keepers"))
            keeper_retries = int.from_bytes(
                bytes.fromhex(keepers_unparsed[:RETRIES_LENGTH]), "big"
            )
            return keeper_retries
        return 0


class ScoreWriteAbstractRound(AbstractRound[Event, TransactionType], ABC):
    """Abstract round for the score_read skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)


class RandomnessRound(ScoreWriteAbstractRound, CollectSameUntilThresholdRound):
    """A round for generating randomness"""

    payload_class = RandomnessPayload
    payload_attribute = "randomness"
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_randomness)
    selection_key = get_name(SynchronizedData.most_voted_randomness)


class SelectKeeperRound(ScoreWriteAbstractRound, CollectSameUntilThresholdRound):
    """A round in which a keeper is selected for transaction submission"""

    payload_class = SelectKeeperPayload
    payload_attribute = "keepers"
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_selection)
    selection_key = get_name(SynchronizedData.keepers)

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""

        if self.threshold_reached and self.most_voted_payload is not None:
            if (
                len(self.most_voted_payload) < RETRIES_LENGTH + ADDRESS_LENGTH
                or (len(self.most_voted_payload) - RETRIES_LENGTH) % ADDRESS_LENGTH != 0
            ):
                # if we cannot parse the keepers' payload, then the developer has serialized it incorrectly.
                return self.synchronized_data, Event.INCORRECT_SERIALIZATION

        return super().end_block()


class CeramicWriteRound(ScoreWriteAbstractRound, CollectSameUntilThresholdRound):
    """CeramicWriteRound"""

    allowed_tx_type = CeramicWritePayload.transaction_type
    payload_attribute: str = get_name(CeramicWritePayload.content)
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = "{}"
    SUCCCESS_PAYLOAD = '{"success": true}'

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            if self.most_voted_payload == self.ERROR_PAYLOAD:
                return self.synchronized_data, Event.API_ERROR
            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class VerificationRound(ScoreWriteAbstractRound, CollectSameUntilThresholdRound):
    """VerificationRound"""

    allowed_tx_type = VerificationPayload.transaction_type
    payload_attribute: str = get_name(VerificationPayload.content)
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = "{}"
    SUCCCESS_PAYLOAD = '{"success": true}'

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            if self.most_voted_payload == self.ERROR_PAYLOAD:
                return self.synchronized_data, Event.API_ERROR
            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedVerificationRound(DegenerateRound):
    """FinishedVerificationRound"""


class ScoreWriteAbciApp(AbciApp[Event]):
    """ScoreWriteAbciApp"""

    initial_round_cls: AppState = RandomnessRound
    initial_states: Set[AppState] = {RandomnessRound}
    transition_function: AbciAppTransitionFunction = {
        RandomnessRound: {
            Event.DONE: SelectKeeperRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
        },
        SelectKeeperRound: {
            Event.DONE: CeramicWriteRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
            Event.INCORRECT_SERIALIZATION: RandomnessRound,
        },
        CeramicWriteRound: {
            Event.DONE: VerificationRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
        },
        VerificationRound: {
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
    cross_period_persisted_keys: List[str] = ["user_to_scores", "latest_tweet_id"]
    db_pre_conditions: Dict[AppState, List[str]] = {
        RandomnessRound: [],
    }
    db_post_conditions: Dict[AppState, List[str]] = {
        FinishedVerificationRound: [],
    }
