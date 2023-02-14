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
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, cast

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
from packages.valory.skills.score_write_abci.payloads import (
    CeramicWritePayload,
    RandomnessPayload,
    ScoreAddPayload,
    SelectKeeperPayload,
    VerificationPayload,
    WalletReadPayload,
)


ADDRESS_LENGTH = 42
RETRIES_LENGTH = 64


class Event(Enum):
    """ScoreWriteAbciApp Events"""

    DONE = "done"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"
    API_ERROR = "api_error"
    DID_NOT_SEND = "did_not_send"
    NO_CHANGES = "no_changes"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def user_to_new_points(self) -> dict:
        """Get the new points for each user."""
        return cast(dict, self.db.get("user_to_new_points", {}))  # pragma: no cover

    @property
    def user_to_total_points(self) -> dict:
        """Get the new total scores."""
        return cast(dict, self.db.get("user_to_total_points", {}))

    @property
    def wallet_to_users(self) -> dict:
        """Get the wallet to twitter user mapping."""
        return cast(dict, self.db.get("wallet_to_users", {}))


class ScoreAddRound(CollectSameUntilThresholdRound):
    """ScoreAddRound"""

    payload_class = ScoreAddPayload
    payload_attribute = "content"
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = "error"
    NO_CHANGES_PAYLOAD = "no_changes"

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            if self.most_voted_payload == self.ERROR_PAYLOAD:
                return self.synchronized_data, Event.API_ERROR

            if self.most_voted_payload == self.NO_CHANGES_PAYLOAD:
                return self.synchronized_data, Event.NO_CHANGES

            payload = json.loads(self.most_voted_payload)

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.user_to_total_points): payload,
                }
            )

            return synchronized_data, Event.DONE

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class RandomnessRound(CollectSameUntilThresholdRound):
    """A round for generating randomness"""

    payload_class = RandomnessPayload
    payload_attribute = "randomness"
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_randomness)
    selection_key = get_name(SynchronizedData.most_voted_randomness)


class SelectKeeperRound(CollectSameUntilThresholdRound):
    """A round in which a keeper is selected for transaction submission"""

    payload_class = SelectKeeperPayload
    payload_attribute = "keeper"
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_selection)
    selection_key = get_name(SynchronizedData.most_voted_keeper_address)


class CeramicWriteRound(OnlyKeeperSendsRound):
    """CeramicWriteRound"""

    payload_class = CeramicWritePayload
    payload_attribute = "content"
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = "error"
    SUCCCESS_PAYLOAD = "success"

    def end_block(
        self,
    ) -> Optional[
        Tuple[BaseSynchronizedData, Enum]
    ]:  # pylint: disable=too-many-return-statements
        """Process the end of the block."""
        if not self.has_keeper_sent_payload:
            return None

        if self.keeper_payload is None:  # pragma: no cover
            return self.synchronized_data, Event.DID_NOT_SEND

        if self.keeper_payload == self.ERROR_PAYLOAD:
            return self.synchronized_data, Event.API_ERROR

        return self.synchronized_data, Event.DONE


class VerificationRound(CollectSameUntilThresholdRound):
    """VerificationRound"""

    payload_class = VerificationPayload
    payload_attribute = "content"
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = "error"
    SUCCCESS_PAYLOAD = "success"

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            if self.most_voted_payload == self.ERROR_PAYLOAD:
                return self.synchronized_data, Event.API_ERROR
            return self.synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(
                        SynchronizedData.user_to_new_points
                    ): {},  # Remove points that have been succesfully written to Ceramic
                }
            )

            return synchronized_data, Event.NO_MAJORITY
        return None


class WalletReadRound(CollectSameUntilThresholdRound):
    """WalletReadRound"""

    payload_class = WalletReadPayload
    payload_attribute = "content"
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = "error"
    SUCCCESS_PAYLOAD = "success"

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            if self.most_voted_payload == self.ERROR_PAYLOAD:
                return self.synchronized_data, Event.API_ERROR

            payload = json.loads(self.most_voted_payload)

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.wallet_to_users): payload,
                }
            )

            return synchronized_data, Event.DONE

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedWalletReadRound(DegenerateRound):
    """FinishedWalletReadRound"""


class ScoreWriteAbciApp(AbciApp[Event]):
    """ScoreWriteAbciApp"""

    initial_round_cls: AppState = ScoreAddRound
    initial_states: Set[AppState] = {ScoreAddRound}
    transition_function: AbciAppTransitionFunction = {
        ScoreAddRound: {
            Event.DONE: RandomnessRound,
            Event.NO_CHANGES: WalletReadRound,
            Event.NO_MAJORITY: ScoreAddRound,
            Event.ROUND_TIMEOUT: ScoreAddRound,
            Event.API_ERROR: ScoreAddRound,
        },
        RandomnessRound: {
            Event.DONE: SelectKeeperRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
        },
        SelectKeeperRound: {
            Event.DONE: CeramicWriteRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
        },
        CeramicWriteRound: {
            Event.DONE: VerificationRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
            Event.API_ERROR: RandomnessRound,
            Event.DID_NOT_SEND: RandomnessRound,
        },
        VerificationRound: {
            Event.DONE: WalletReadRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
            Event.API_ERROR: RandomnessRound,
        },
        WalletReadRound: {
            Event.DONE: FinishedWalletReadRound,
            Event.NO_MAJORITY: RandomnessRound,
            Event.ROUND_TIMEOUT: RandomnessRound,
            Event.API_ERROR: RandomnessRound,
        },
        FinishedWalletReadRound: {},
    }
    final_states: Set[AppState] = {FinishedWalletReadRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: List[str] = ["latest_tweet_id"]
    db_pre_conditions: Dict[AppState, List[str]] = {
        ScoreAddRound: [],
    }
    db_post_conditions: Dict[AppState, List[str]] = {
        FinishedWalletReadRound: [],
    }
