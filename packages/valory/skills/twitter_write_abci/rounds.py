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

"""This package contains the rounds of TwitterWriteAbciApp."""

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
from packages.valory.skills.twitter_write_abci.payloads import (
    RandomnessPayload,
    SelectKeeperPayload,
    TwitterWritePayload,
)


class Event(Enum):
    """TwitterWriteAbciApp Events"""

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
        return cast(list, self.db.get_strict("write_data"))

    @property
    def write_index(self) -> int:
        """Get the write_index."""
        return cast(int, self.db.get("write_index", 0))

    @property
    def tweet_ids(self) -> List[int]:
        """List of posted tweet ids."""
        return cast(list, self.db.get("tweet_ids", []))


class RandomnessTwitterRound(CollectSameUntilThresholdRound):
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


class SelectKeeperTwitterRound(CollectSameUntilThresholdRound):
    """A round in which a keeper is selected for transaction submission"""

    payload_class = SelectKeeperPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_selection)
    selection_key = get_name(SynchronizedData.most_voted_keeper_address)


class TwitterWriteRound(OnlyKeeperSendsRound):
    """TwitterWriteRound"""

    payload_class = TwitterWritePayload
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
            cast(TwitterWritePayload, self.keeper_payload).content
        )
        if not keeper_payload["success"]:
            return self.synchronized_data, Event.API_ERROR

        synchronized_data = cast(SynchronizedData, self.synchronized_data)
        write_index = synchronized_data.write_index + 1
        tweet_ids = synchronized_data.tweet_ids

        tweet_ids.append(keeper_payload["tweet_id"])

        finished_tweeting = write_index == len(synchronized_data.write_data)

        return (
            self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.tweet_ids): tweet_ids,
                    get_name(SynchronizedData.write_index): 0
                    if finished_tweeting
                    else write_index,
                }
            ),
            Event.DONE if finished_tweeting else Event.CONTINUE,
        )


class FinishedTwitterWriteRound(DegenerateRound):
    """FinishedTwitterWriteRound"""


class TwitterWriteAbciApp(AbciApp[Event]):
    """TwitterWriteAbciApp"""

    initial_round_cls: AppState = RandomnessTwitterRound
    initial_states: Set[AppState] = {RandomnessTwitterRound}
    transition_function: AbciAppTransitionFunction = {
        RandomnessTwitterRound: {
            Event.DONE: SelectKeeperTwitterRound,
            Event.NO_MAJORITY: RandomnessTwitterRound,
            Event.ROUND_TIMEOUT: RandomnessTwitterRound,
        },
        SelectKeeperTwitterRound: {
            Event.DONE: TwitterWriteRound,
            Event.NO_MAJORITY: RandomnessTwitterRound,
            Event.ROUND_TIMEOUT: RandomnessTwitterRound,
        },
        TwitterWriteRound: {
            Event.DONE: FinishedTwitterWriteRound,
            Event.CONTINUE: TwitterWriteRound,
            Event.API_ERROR: RandomnessTwitterRound,
            Event.ROUND_TIMEOUT: RandomnessTwitterRound,
        },
        FinishedTwitterWriteRound: {},
    }
    final_states: Set[AppState] = {FinishedTwitterWriteRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        RandomnessTwitterRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedTwitterWriteRound: set(),
    }
