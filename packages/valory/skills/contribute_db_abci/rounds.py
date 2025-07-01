# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2025 Valory AG
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

"""This package contains the rounds of ContributeDBAbciApp."""

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
from packages.valory.skills.contribute_db_abci.payloads import DBLoadPayload


class Event(Enum):
    """ContributeDBAbciApp Events"""

    DONE = "done"
    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def db_keeper(self) -> str:
        """Get the tx_submitter."""
        return cast(str, self.db.get_strict("db_keeper"))


class DBLoadRound(CollectSameUntilThresholdRound):
    """A round for loading the DB"""

    payload_class = DBLoadPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""

        if self.threshold_reached:
            # Get all the agents that have sent, sort them alphabetically and get the first one
            # This will be the db keeper until it is down and therefore does not send any payload
            db_keeper = sorted(list(self.collection.keys()))[0]
            self.context.contribute_db.writer_addresses = [db_keeper]

            return self.synchronized_data, Event.DONE

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedLoadingRound(DegenerateRound):
    """FinishedLoadingRound"""


class ContributeDBAbciApp(AbciApp[Event]):
    """ContributeDBAbciApp"""

    initial_round_cls: AppState = DBLoadRound
    initial_states: Set[AppState] = {DBLoadRound}
    transition_function: AbciAppTransitionFunction = {
        DBLoadRound: {
            Event.DONE: FinishedLoadingRound,
            Event.NO_MAJORITY: DBLoadRound,
            Event.ROUND_TIMEOUT: DBLoadRound,
        },
        FinishedLoadingRound: {},
    }
    final_states: Set[AppState] = {FinishedLoadingRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        DBLoadRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedLoadingRound: set(),
    }
