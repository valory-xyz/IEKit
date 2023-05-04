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

"""This package contains the rounds of TwitterScoringAbciApp."""

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
from packages.valory.skills.twitter_scoring_abci.payloads import TwitterScoringPayload


class Event(Enum):
    """TwitterScoringAbciApp Events"""

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
    def ceramic_db(self) -> dict:
        """Get the data stored in the main stream."""
        return cast(dict, self.db.get_strict("ceramic_db"))

    @property
    def pending_write(self) -> bool:
        """Checks whether there are changes pending to be written to Ceramic."""
        return cast(bool, self.db.get_strict("pending_write"))


class TwitterScoringRound(CollectSameUntilThresholdRound):
    """TwitterScoringRound"""

    payload_class = TwitterScoringPayload
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = {"error": "true"}

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            if self.most_voted_payload == json.dumps(
                self.ERROR_PAYLOAD, sort_keys=True
            ):
                return self.synchronized_data, Event.API_ERROR

            payload = json.loads(self.most_voted_payload)

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.ceramic_db): payload["ceramic_db"],
                    get_name(SynchronizedData.pending_write): payload["pending_write"],
                }
            )
            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedTwitterScoringRound(DegenerateRound):
    """FinishedTwitterScoringRound"""


class TwitterScoringAbciApp(AbciApp[Event]):
    """TwitterScoringAbciApp"""

    initial_round_cls: AppState = TwitterScoringRound
    initial_states: Set[AppState] = {TwitterScoringRound}
    transition_function: AbciAppTransitionFunction = {
        TwitterScoringRound: {
            Event.DONE: FinishedTwitterScoringRound,
            Event.NO_MAJORITY: TwitterScoringRound,
            Event.ROUND_TIMEOUT: TwitterScoringRound,
            Event.API_ERROR: TwitterScoringRound,
        },
        FinishedTwitterScoringRound: {},
    }
    final_states: Set[AppState] = {FinishedTwitterScoringRound}
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
        TwitterScoringRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedTwitterScoringRound: {
            get_name(SynchronizedData.ceramic_db),
        },
    }
