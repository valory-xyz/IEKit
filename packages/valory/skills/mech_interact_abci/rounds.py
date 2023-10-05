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

"""This package contains the rounds of MechInteractAbciApp."""

from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, cast

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    CollectSameUntilThresholdRound,
    AppState,
    BaseSynchronizedData,
    DegenerateRound,
    EventToTimeout,
    OnlyKeeperSendsRound,
    get_name
)

from packages.valory.skills.mech_interact_abci.payloads import (
    MechRequestPayload,
    MechResponsePayload,
    MechRandomnessPayload,
    MechSelectKeeperPayload
)


class Event(Enum):
    """MechInteractAbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    DONE = "done"
    NO_MAJORITY = "no_majority"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def mech_requests(self) -> list:
        """Get the mech requests."""
        return cast(list, self.db.get("mech_requests", []))


    @property
    def final_tx_hash(self) -> str:
        """Get the verified tx hash."""
        return cast(str, self.db.get_strict("final_tx_hash"))


class MechRequestRound(OnlyKeeperSendsRound):
    """MechRequestRound"""

    payload_class = MechRequestPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.keeper_payload is None:
            return None

        mech_requests = cast(
            SynchronizedData, self.synchronized_data
        ).mech_requests

        # Assing the request hash to its corresponding requests
        for r in mech_requests:
            if "tx_hash" not in r:
                r["tx_hash"] = cast(MechRequestPayload, self.keeper_payload).tx_hash  # FIXME: do multi-requests have 1 hash only?

        synchronized_data = self.synchronized_data.update(
            synchronized_data_class=SynchronizedData,
            **{
                get_name(
                    SynchronizedData.mech_requests
                ): mech_requests
            },
        )

        return synchronized_data, Event.DONE



class MechResponseRound(CollectSameUntilThresholdRound):
    """MechResponseRound"""

    payload_class = MechResponsePayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:

            mech_requests = cast(
                SynchronizedData, self.synchronized_data
            ).mech_requests

            # Assign the response to its corresponding requests
            response = self.most_voted_payload.request
            # FIXME
            for request in mech_requests:

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(
                        SynchronizedData.mech_requests
                    ): mech_requests
                },
            )

            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class MechRandomnessRound(CollectSameUntilThresholdRound):
    """A round for generating randomness"""

    payload_class = MechRandomnessPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_randomness)
    selection_key = (
        get_name(SynchronizedData.most_voted_randomness),
        get_name(SynchronizedData.most_voted_randomness),
    )

class MechSelectKeeperRound(CollectSameUntilThresholdRound):
    """A round in which a keeper is selected for transaction submission"""

    payload_class = MechSelectKeeperPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_selection)
    selection_key = get_name(SynchronizedData.most_voted_keeper_address)


class FinishedMechRequestRound(DegenerateRound):
    """FinishedMechRequestRound"""


class FinishedMechResponseRound(DegenerateRound):
    """FinishedMechResponseRound"""


class MechInteractAbciApp(AbciApp[Event]):
    """MechInteractAbciApp"""

    initial_round_cls: AppState = MechRequestRound
    initial_states: Set[AppState] = {MechResponseRound, MechRandomnessRound}
    transition_function: AbciAppTransitionFunction = {
        MechRandomnessRound: {
            Event.DONE: MechSelectKeeperRound,
            Event.NO_MAJORITY: MechSelectKeeperRound,
            Event.ROUND_TIMEOUT: MechSelectKeeperRound
        },
        MechSelectKeeperRound: {
            Event.DONE: MechRequestRound,
            Event.NO_MAJORITY: MechRandomnessRound,
            Event.ROUND_TIMEOUT: MechRandomnessRound
        },
        MechRequestRound: {
            Event.DONE: FinishedMechRequestRound,
            Event.ROUND_TIMEOUT: MechRandomnessRound
        },
        MechResponseRound: {
            Event.DONE: FinishedMechResponseRound,
            Event.NO_MAJORITY: MechResponseRound,
            Event.ROUND_TIMEOUT: MechResponseRound
        },
        FinishedMechRequestRound: {},
        FinishedMechResponseRound: {}
    }
    final_states: Set[AppState] = {FinishedMechRequestRound, FinishedMechResponseRound}
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: Set[str] = set()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        MechResponseRound: set(),
    	MechRequestRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedMechRequestRound: set(),
    	FinishedMechResponseRound: set(),
    }
