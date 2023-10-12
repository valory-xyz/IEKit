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

import json
from enum import Enum
from typing import Dict, List, Mapping, Set, cast

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    CollectSameUntilThresholdRound,
    CollectionRound,
    DegenerateRound,
    EventToTimeout,
    get_name,
)
from packages.valory.skills.mech_interact_abci.models import (
    MechInteractionResponse,
    MechMetadata,
)
from packages.valory.skills.mech_interact_abci.payloads import (
    MechRequestPayload,
    MechResponsePayload,
)
from packages.valory.skills.transaction_settlement_abci.rounds import (
    SynchronizedData as TxSynchronizedData,
)


class Event(Enum):
    """MechInteractAbciApp Events"""

    DONE = "done"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"


class SynchronizedData(TxSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def mech_price(self) -> int:
        """Get the mech's request price."""
        return int(self.db.get_strict("mech_price"))

    @property
    def mech_requests(self) -> List[MechMetadata]:
        """Get the mech requests."""
        serialized = self.db.get("mech_requests", "[]")
        requests = json.loads(serialized)
        return [MechMetadata(**metadata_item) for metadata_item in requests]

    @property
    def mech_responses(self) -> List[MechInteractionResponse]:
        """Get the mech responses."""
        serialized = self.db.get("mech_responses", "[]")
        responses = json.loads(serialized)
        return [MechInteractionResponse(**response_item) for response_item in responses]

    @property
    def participant_to_requests(self) -> Mapping[str, MechRequestPayload]:
        """Get the `participant_to_requests`."""
        serialized = self.db.get_strict("participant_to_requests")
        deserialized = CollectionRound.deserialize_collection(serialized)
        return cast(Mapping[str, MechRequestPayload], deserialized)

    @property
    def participant_to_responses(self) -> Mapping[str, MechResponsePayload]:
        """Get the `participant_to_responses`."""
        serialized = self.db.get_strict("participant_to_responses")
        deserialized = CollectionRound.deserialize_collection(serialized)
        return cast(Mapping[str, MechResponsePayload], deserialized)


class MechRequestRound(CollectSameUntilThresholdRound):
    """A round for performing requests to a Mech."""

    payload_class = MechRequestPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    selection_key = (
        get_name(SynchronizedData.most_voted_tx_hash),
        get_name(SynchronizedData.mech_price),
        get_name(SynchronizedData.mech_requests),
        get_name(SynchronizedData.mech_responses),
    )
    collection_key = get_name(SynchronizedData.participant_to_requests)


class MechResponseRound(CollectSameUntilThresholdRound):
    """A round for collecting the responses from a Mech."""

    payload_class = MechRequestPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    selection_key = get_name(SynchronizedData.mech_responses)
    collection_key = get_name(SynchronizedData.participant_to_responses)


class FinishedMechRequestRound(DegenerateRound):
    """FinishedMechRequestRound"""


class FinishedMechResponseRound(DegenerateRound):
    """FinishedMechResponseRound"""


class MechInteractAbciApp(AbciApp[Event]):
    """MechInteractAbciApp"""

    initial_round_cls: AppState = MechRequestRound
    initial_states: Set[AppState] = {MechRequestRound, MechResponseRound}
    transition_function: AbciAppTransitionFunction = {
        MechRequestRound: {
            Event.DONE: FinishedMechRequestRound,
            Event.NO_MAJORITY: MechRequestRound,
            Event.ROUND_TIMEOUT: MechRequestRound,
        },
        MechResponseRound: {
            Event.DONE: FinishedMechResponseRound,
            Event.NO_MAJORITY: MechResponseRound,
            Event.ROUND_TIMEOUT: MechResponseRound,
        },
        FinishedMechRequestRound: {},
        FinishedMechResponseRound: {},
    }
    final_states: Set[AppState] = {FinishedMechRequestRound, FinishedMechResponseRound}
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: Set[str] = set()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        MechRequestRound: set(get_name(SynchronizedData.mech_requests)),
        MechResponseRound: set(get_name(SynchronizedData.final_tx_hash)),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedMechRequestRound: {
            get_name(SynchronizedData.final_tx_hash),
            get_name(SynchronizedData.mech_price),
        },
        FinishedMechResponseRound: set(get_name(SynchronizedData.mech_responses)),
    }
