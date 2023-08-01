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

"""This package contains the rounds of DynamicNFTAbciApp."""

import json
from abc import ABC
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
from packages.valory.skills.dynamic_nft_abci.payloads import TokenTrackPayload


class Event(Enum):
    """DynamicNFTAbciApp Events"""

    NO_MAJORITY = "no_majority"
    DONE = "done"
    ROUND_TIMEOUT = "round_timeout"
    CONTRACT_ERROR = "contract_error"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def token_id_to_points(self) -> dict:
        """Get the token id to points mapping."""
        return cast(dict, self.db.get("token_id_to_points", {}))

    @property
    def last_update_time(self) -> float:
        """Get the last update time."""
        return cast(float, self.db.get("last_update_time", None))

    @property
    def ceramic_db(self) -> dict:
        """Get the data stored in the main stream."""
        return cast(dict, self.db.get_strict("ceramic_db"))

    @property
    def pending_write(self) -> bool:
        """Checks whether there are changes pending to be written to Ceramic."""
        return cast(bool, self.db.get("pending_write", False))


class TokenTrackRound(CollectSameUntilThresholdRound):
    """TokenTrackRound"""

    payload_class = TokenTrackPayload
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = {"error": True}

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            payload = json.loads(self.most_voted_payload)

            if payload == TokenTrackRound.ERROR_PAYLOAD:
                return self.synchronized_data, Event.CONTRACT_ERROR

            token_id_to_points = payload["token_id_to_points"]
            last_update_time = payload["last_update_time"]
            ceramic_db = payload["ceramic_db"]
            pending_write = payload["pending_write"]

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.token_id_to_points): token_id_to_points,
                    get_name(SynchronizedData.last_update_time): last_update_time,
                    get_name(SynchronizedData.ceramic_db): ceramic_db,
                    get_name(SynchronizedData.pending_write): pending_write,
                }
            )
            return (synchronized_data, Event.DONE)
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedTokenTrackRound(DegenerateRound, ABC):
    """FinishedTokenTrackRound"""


class DynamicNFTAbciApp(AbciApp[Event]):
    """DynamicNFTAbciApp"""

    initial_round_cls: AppState = TokenTrackRound
    initial_states: Set[AppState] = {TokenTrackRound}
    transition_function: AbciAppTransitionFunction = {
        TokenTrackRound: {
            Event.DONE: FinishedTokenTrackRound,
            Event.CONTRACT_ERROR: TokenTrackRound,
            Event.NO_MAJORITY: TokenTrackRound,
            Event.ROUND_TIMEOUT: TokenTrackRound,
        },
        FinishedTokenTrackRound: {},
    }
    final_states: Set[AppState] = {
        FinishedTokenTrackRound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    db_pre_conditions: Dict[AppState, Set[str]] = {
        TokenTrackRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedTokenTrackRound: set(),
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset(
        ["token_id_to_points", "last_update_time", "ceramic_db", "pending_write"]
    )
