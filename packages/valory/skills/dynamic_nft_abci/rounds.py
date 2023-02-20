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
from typing import Dict, Optional, Set, Tuple, cast

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
from packages.valory.skills.dynamic_nft_abci.payloads import NewTokensPayload


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
    def token_to_data(self) -> dict:
        """Get the token table."""
        return cast(dict, self.db.get("token_to_data", {}))

    @property
    def user_to_total_points(self) -> dict:
        """Get the user scores."""
        return cast(dict, self.db.get("user_to_total_points", {}))

    @property
    def last_update_time(self) -> float:
        """Get the last update time."""
        return cast(float, self.db.get("last_update_time", None))

    @property
    def wallet_to_users(self) -> dict:
        """Get the wallet to twitter user mapping."""
        return cast(dict, self.db.get("wallet_to_users", {}))

    @property
    def last_parsed_block(self) -> int:
        """Get the last parsed block."""
        return cast(int, self.db.get("last_parsed_block", None))


class NewTokensRound(CollectSameUntilThresholdRound):
    """NewTokensRound"""

    payload_class = NewTokensPayload
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = {"error": True}

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            payload = json.loads(self.most_voted_payload)

            if payload == NewTokensRound.ERROR_PAYLOAD:
                return self.synchronized_data, Event.CONTRACT_ERROR

            token_to_data = payload["token_to_data"]
            last_update_time = payload["last_update_time"]
            last_parsed_block = payload["last_parsed_block"]

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.token_to_data): token_to_data,
                    get_name(SynchronizedData.last_update_time): last_update_time,
                    get_name(SynchronizedData.last_parsed_block): last_parsed_block,
                }
            )
            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedNewTokensRound(DegenerateRound, ABC):
    """FinishedNewTokensRound"""

    round_id: str = "finished_new_tokens"


class DynamicNFTAbciApp(AbciApp[Event]):
    """DynamicNFTAbciApp"""

    initial_round_cls: AppState = NewTokensRound
    initial_states: Set[AppState] = {NewTokensRound}
    transition_function: AbciAppTransitionFunction = {
        NewTokensRound: {
            Event.DONE: FinishedNewTokensRound,
            Event.CONTRACT_ERROR: NewTokensRound,
            Event.NO_MAJORITY: NewTokensRound,
            Event.ROUND_TIMEOUT: NewTokensRound,
        },
        FinishedNewTokensRound: {},
    }
    final_states: Set[AppState] = {FinishedNewTokensRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    db_pre_conditions: Dict[AppState, Set[str]] = {
        NewTokensRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedNewTokensRound: {
            get_name(SynchronizedData.token_to_data),
            get_name(SynchronizedData.last_update_time),
        }
    }
    cross_period_persisted_keys: Set[str] = {
        "token_to_data",
        "last_update_time",
        "last_parsed_block",
        "user_to_total_points",
    }
