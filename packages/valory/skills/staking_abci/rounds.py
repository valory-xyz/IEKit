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
    DeserializedCollection,
    EventToTimeout,
    get_name,
)
from packages.valory.skills.staking_abci.payloads import (
    ActivityScorePayload,
    ActivityUpdatePreparationPayload,
    CheckpointPreparationPayload,
    DAAPreparationPayload,
)


class Event(Enum):
    """AbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"
    DONE = "done"
    PROCESS_UPDATES = "process_updates"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def most_voted_tx_hash(self) -> Optional[float]:
        """Get the token most_voted_tx_hash."""
        return self.db.get("most_voted_tx_hash", None)

    @property
    def tx_submitter(self) -> Optional[str]:
        """Get the round that submitted a tx to transaction_settlement_abci."""
        return self.db.get("tx_submitter", None)

    @property
    def participant_to_update(self) -> DeserializedCollection:
        """Agent to payload mapping for the DataPullRound."""
        return self._get_deserialized("participant_to_update")

    @property
    def participant_to_checkpoint(self) -> DeserializedCollection:
        """Agent to payload mapping for the DataPullRound."""
        return self._get_deserialized("participant_to_checkpoint")

    @property
    def pending_write(self) -> bool:
        """Checks whether there are changes pending to be written to Ceramic."""
        return cast(bool, self.db.get("pending_write", False))

    @property
    def chain_id(self) -> Optional[str]:
        """Get the chain name where to send the transactions to."""
        return cast(str, self.db.get("chain_id", None))

    @property
    def staking_multisig_to_updates(self) -> Dict:
        """Get the staking_multisig_to_updates."""
        return self.db.get("staking_multisig_to_updates")

    @property
    def staking_user_to_counted_tweets(self) -> Dict:
        """Get the staking_user_to_counted_tweets."""
        return self.db.get("staking_user_to_counted_tweets")

class ActivityScoreRound(CollectSameUntilThresholdRound):
    """ActivityScoreRound"""

    payload_class = ActivityScorePayload
    synchronized_data_class = SynchronizedData

    selection_key = (
        get_name(SynchronizedData.pending_write),
    )

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:

            # Instantiate the payload using the most voted values
            payload = ActivityScorePayload(*(("dummy_sender",) + self.most_voted_payload_values))

            # We have finished with the activity update
            # Mark Ceramic for a write and clean updates
            if payload.pending_write:
                synchronized_data = self.synchronized_data.update(
                    synchronized_data_class=SynchronizedData,
                    **{
                        get_name(SynchronizedData.pending_write): True,
                        get_name(SynchronizedData.staking_multisig_to_updates): {},
                        get_name(SynchronizedData.staking_user_to_counted_tweets): {},
                    },
                )

                return synchronized_data, Event.DONE

            # Prepare the update transaction
            return self.synchronized_data, Event.PROCESS_UPDATES

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None

        # Event.ROUND_TIMEOUT


class ActivityUpdatePreparationRound(CollectSameUntilThresholdRound):
    """ActivityUpdatePreparationRound"""

    payload_class = ActivityUpdatePreparationPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_update)
    selection_key = (
        get_name(SynchronizedData.tx_submitter),
        get_name(SynchronizedData.most_voted_tx_hash),
        get_name(SynchronizedData.chain_id),
        get_name(SynchronizedData.safe_contract_address),
    )

    # We reference all the events here to prevent the check-abciapp-specs tool from complaining
    # since this round receives the event via payload
    # Event.NO_MAJORITY, Event.ROUND_TIMEOUT, Event.DONE


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
        get_name(SynchronizedData.chain_id),
        get_name(SynchronizedData.safe_contract_address),
    )

    # We reference all the events here to prevent the check-abciapp-specs tool from complaining
    # since this round receives the event via payload
    # Event.DONE, Event.NO_MAJORITY, Event.ROUND_TIMEOUT


class DAAPreparationRound(CollectSameUntilThresholdRound):
    """DAAPreparationRound"""

    payload_class = DAAPreparationPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_checkpoint)
    selection_key = (
        get_name(SynchronizedData.tx_submitter),
        get_name(SynchronizedData.most_voted_tx_hash),
        get_name(SynchronizedData.chain_id),
        get_name(SynchronizedData.safe_contract_address),
    )

    # We reference all the events here to prevent the check-abciapp-specs tool from complaining
    # since this round receives the event via payload
    # Event.DONE, Event.NO_MAJORITY, Event.ROUND_TIMEOUT


class FinishedActivityUpdatePreparationRound(DegenerateRound):
    """FinishedActivityUpdatePreparationRound"""


class FinishedActivityRound(DegenerateRound):
    """FinishedActivityRound"""


class FinishedCheckpointPreparationRound(DegenerateRound):
    """FinishedCheckpointPreparationRound"""


class FinishedDAAPreparationRound(DegenerateRound):
    """FinishedDAAPreparationRound"""


class StakingAbciApp(AbciApp[Event]):
    """StakingAbciApp"""

    initial_round_cls: AppState = ActivityScoreRound
    initial_states: Set[AppState] = {CheckpointPreparationRound, ActivityScoreRound, DAAPreparationRound}
    transition_function: AbciAppTransitionFunction = {
        ActivityScoreRound: {
            Event.DONE: FinishedActivityRound,
            Event.PROCESS_UPDATES: ActivityUpdatePreparationRound,
            Event.NO_MAJORITY: ActivityScoreRound,
            Event.ROUND_TIMEOUT: ActivityScoreRound
        },
        ActivityUpdatePreparationRound: {
            Event.DONE: FinishedActivityUpdatePreparationRound,
            Event.NO_MAJORITY: ActivityUpdatePreparationRound,
            Event.ROUND_TIMEOUT: ActivityUpdatePreparationRound
        },
        CheckpointPreparationRound: {
            Event.DONE: FinishedCheckpointPreparationRound,
            Event.NO_MAJORITY: CheckpointPreparationRound,
            Event.ROUND_TIMEOUT: CheckpointPreparationRound
        },
        DAAPreparationRound: {
            Event.DONE: FinishedDAAPreparationRound,
            Event.NO_MAJORITY: DAAPreparationRound,
            Event.ROUND_TIMEOUT: DAAPreparationRound
        },
        FinishedActivityUpdatePreparationRound: {},
        FinishedActivityRound: {},
        FinishedCheckpointPreparationRound: {}
    }
    final_states: Set[AppState] = {FinishedCheckpointPreparationRound, FinishedActivityUpdatePreparationRound, FinishedActivityRound, FinishedDAAPreparationRound}
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        CheckpointPreparationRound: set(),
    	ActivityScoreRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedCheckpointPreparationRound: {"most_voted_tx_hash"},
    	FinishedActivityUpdatePreparationRound: {"most_voted_tx_hash"},
        FinishedActivityRound: set(),
        FinishedDAAPreparationRound: {"most_voted_tx_hash"},
    }
