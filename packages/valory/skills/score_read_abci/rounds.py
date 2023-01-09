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

"""This package contains the rounds of ScoreReadAbciApp."""

import json
from abc import ABC
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, cast

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
from packages.valory.skills.score_read_abci.payloads import (
    ScoringPayload,
    TwitterObservationPayload,
)


class Event(Enum):
    """ScoreReadAbciApp Events"""

    DONE = "done"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"
    API_ERROR = "api_error"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def most_voted_api_data(self) -> Dict:
        """Get the most_voted_api_data."""
        return cast(Dict, self.db.get_strict("most_voted_api_data"))

    @property
    def user_to_scores(self) -> dict:
        """Get the user scores."""
        return cast(dict, self.db.get("user_to_scores", {}))


class ScoreReadAbstractRound(AbstractRound[Event, TransactionType], ABC):
    """Abstract round for the APY estimation skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)


class TwitterObservationRound(ScoreReadAbstractRound, CollectSameUntilThresholdRound):
    """TwitterObservationRound"""

    allowed_tx_type = TwitterObservationPayload.transaction_type
    payload_attribute: str = get_name(TwitterObservationPayload.content)
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = "{}"

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            if self.most_voted_payload == self.ERROR_PAYLOAD:
                return self.synchronized_data, Event.API_ERROR

            payload = json.loads(self.most_voted_payload)

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{get_name(SynchronizedData.most_voted_api_data): payload}
            )
            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class ScoringRound(ScoreReadAbstractRound, CollectSameUntilThresholdRound):
    """ScoringRound"""

    allowed_tx_type = ScoringPayload.transaction_type
    payload_attribute: str = get_name(ScoringPayload.content)
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:

            payload = json.loads(self.most_voted_payload)

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{get_name(SynchronizedData.user_to_scores): payload}
            )
            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedScoringRound(DegenerateRound):
    """FinishedScoringRound"""


class ScoreReadAbciApp(AbciApp[Event]):
    """ScoreReadAbciApp"""

    initial_round_cls: AppState = TwitterObservationRound
    initial_states: Set[AppState] = {TwitterObservationRound}
    transition_function: AbciAppTransitionFunction = {
        TwitterObservationRound: {
            Event.DONE: ScoringRound,
            Event.NO_MAJORITY: TwitterObservationRound,
            Event.ROUND_TIMEOUT: TwitterObservationRound,
        },
        ScoringRound: {
            Event.DONE: FinishedScoringRound,
            Event.NO_MAJORITY: ScoringRound,
            Event.ROUND_TIMEOUT: ScoringRound,
        },
        FinishedScoringRound: {},
    }
    final_states: Set[AppState] = {FinishedScoringRound}
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: List[str] = [
        "user_to_scores",
    ]
    db_pre_conditions: Dict[AppState, List[str]] = {
        TwitterObservationRound: [],
    }
    db_post_conditions: Dict[AppState, List[str]] = {
        FinishedScoringRound: [
            get_name(SynchronizedData.user_to_scores),
        ],
    }
