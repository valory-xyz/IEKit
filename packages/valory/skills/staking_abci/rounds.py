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

"""This package contains the rounds of StakingAbciApp."""

from enum import Enum
from typing import Dict, FrozenSet, Optional, Set, Tuple

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    DegenerateRound,
    DeserializedCollection,
    EventToTimeout,
    get_name,
)
from packages.valory.skills.staking_abci.payloads import (
    ActivityScorePayload,
    ActiviyUpdatePreparationPayload,
    CheckpointPreparationPayload,
)


class Event(Enum):
    """AbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"
    DONE = "done"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def activity_updates(self) -> Optional[Dict]:
        """Get the activity_updates."""
        return self.db.get("activity_updates")

    @property
    def last_processed_tweet(self) -> Optional[int]:
        """Get the last_processed_tweet."""
        return self.db.get("last_processed_tweet", None)

    @property
    def most_voted_tx_hash(self) -> Optional[float]:
        """Get the token most_voted_tx_hash."""
        return self.db.get("most_voted_tx_hash", None)

    @property
    def tx_submitter(self) -> str:
        """Get the round that submitted a tx to transaction_settlement_abci."""
        return str(self.db.get_strict("tx_submitter"))

    @property
    def participant_to_activity(self) -> DeserializedCollection:
        """Agent to payload mapping for the DataPullRound."""
        return self._get_deserialized("participant_to_activity")

    @property
    def participant_to_update(self) -> DeserializedCollection:
        """Agent to payload mapping for the DataPullRound."""
        return self._get_deserialized("participant_to_update")

    @property
    def participant_to_checkpoint(self) -> DeserializedCollection:
        """Agent to payload mapping for the DataPullRound."""
        return self._get_deserialized("participant_to_checkpoint")



class ActivityScoreRound(CollectSameUntilThresholdRound):
    """ActivityScoreRound"""

    payload_class = ActivityScorePayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_activity)
    selection_key = (
        get_name(SynchronizedData.activity_updates),
        get_name(SynchronizedData.last_processed_tweet),
    )


class ActiviyUpdatePreparationRound(CollectSameUntilThresholdRound):
    """ActiviyUpdatePreparationRound"""

    payload_class = ActiviyUpdatePreparationPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_update)
    selection_key = (
        get_name(SynchronizedData.tx_submitter),
        get_name(SynchronizedData.most_voted_tx_hash),
    )


class CheckpointPreparationRound(CollectSameUntilThresholdRound):
    """CheckpointPreparationRound"""

    payload_class = CheckpointPreparationPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_checkpoint)
    selection_key = (
        get_name(SynchronizedData.tx_submitter),
        get_name(SynchronizedData.most_voted_tx_hash),
    )


class FinishedActiviyUpdatePreparationRound(DegenerateRound):
    """FinishedActiviyUpdatePreparationRound"""


class FinishedCheckpointPreparationRound(DegenerateRound):
    """FinishedCheckpointPreparationRound"""


class StakingAbciApp(AbciApp[Event]):
    """StakingAbciApp"""

    initial_round_cls: AppState = ActivityScoreRound
    initial_states: Set[AppState] = {CheckpointPreparationRound, ActivityScoreRound}
    transition_function: AbciAppTransitionFunction = {
        ActivityScoreRound: {
            Event.DONE: ActiviyUpdatePreparationRound,
            Event.NO_MAJORITY: ActivityScoreRound,
            Event.ROUND_TIMEOUT: ActivityScoreRound
        },
        ActiviyUpdatePreparationRound: {
            Event.DONE: FinishedActiviyUpdatePreparationRound,
            Event.NO_MAJORITY: ActiviyUpdatePreparationRound,
            Event.ROUND_TIMEOUT: ActiviyUpdatePreparationRound
        },
        CheckpointPreparationRound: {
            Event.DONE: FinishedCheckpointPreparationRound,
            Event.NO_MAJORITY: CheckpointPreparationRound,
            Event.ROUND_TIMEOUT: CheckpointPreparationRound
        },
        FinishedActiviyUpdatePreparationRound: {},
        FinishedCheckpointPreparationRound: {}
    }
    final_states: Set[AppState] = {FinishedCheckpointPreparationRound, FinishedActiviyUpdatePreparationRound}
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        CheckpointPreparationRound: set(),
    	ActivityScoreRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedCheckpointPreparationRound: set(),
    	FinishedActiviyUpdatePreparationRound: set(),
    }
