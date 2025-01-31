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

"""This package contains the rounds of ProposalVoterAbciApp."""

import json
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
    OnlyKeeperSendsRound,
    get_name,
)
from packages.valory.skills.llm_abci.payloads import (
    LLMPayload,
    RandomnessPayload,
    SelectKeeperPayload,
)


class Event(Enum):
    """ProposalVoterAbciApp Events"""

    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"
    DONE = "done"
    DONE_CONTINUE = "done_continue"
    DONE_FINISHED = "done_finished"
    DID_NOT_SEND = "did_not_send"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def llm_prompt_templates(self) -> list:
        """Get the llm_prompt_templates."""
        return cast(list, self.db.get_strict("llm_prompt_templates"))

    @property
    def llm_values(self) -> list:
        """Get the llm_values."""
        return cast(list, self.db.get_strict("llm_values"))

    @property
    def llm_results(self) -> list:
        """Get the llm_results."""
        return cast(list, self.db.get("llm_results", []))


class LLMRandomnessRound(CollectSameUntilThresholdRound):
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
    extended_requirements = ()


class LLMSelectKeeperRound(CollectSameUntilThresholdRound):
    """A round in which a keeper is selected for transaction submission"""

    payload_class = SelectKeeperPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_selection)
    selection_key = get_name(SynchronizedData.most_voted_keeper_address)
    extended_requirements = ()


class LLMRound(OnlyKeeperSendsRound):
    """LLMRound"""

    payload_class = LLMPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(
        self,
    ) -> Optional[
        Tuple[BaseSynchronizedData, Enum]
    ]:  # pylint: disable=too-many-return-statements
        """Process the end of the block."""
        if self.keeper_payload is None:
            return None

        if self.keeper_payload is None:  # pragma: no cover
            return self.synchronized_data, Event.DID_NOT_SEND

        keeper_payload = json.loads(cast(LLMPayload, self.keeper_payload).content)
        synchronized_data = cast(SynchronizedData, self.synchronized_data)

        # Remove prompt and values at index 0
        llm_prompt_templates = synchronized_data.llm_prompt_templates
        llm_prompt_templates.pop(0)
        llm_values = synchronized_data.llm_values
        llm_values.pop(0)

        llm_results = synchronized_data.llm_results
        llm_results.append(keeper_payload["result"])
        synchronized_data = synchronized_data.update(
            synchronized_data_class=SynchronizedData,
            **{
                get_name(SynchronizedData.llm_prompt_templates): llm_prompt_templates,
                get_name(SynchronizedData.llm_values): llm_values,
                get_name(SynchronizedData.llm_results): llm_results,
            }
        )

        return (
            synchronized_data,
            Event.DONE_CONTINUE if llm_prompt_templates else Event.DONE_FINISHED,
        )


class FinishedLLMRound(DegenerateRound):
    """FinisheLLMRound"""


class LLMAbciApp(AbciApp[Event]):
    """LLMAbciApp"""

    initial_round_cls: AppState = LLMRandomnessRound
    initial_states: Set[AppState] = {LLMRandomnessRound}
    transition_function: AbciAppTransitionFunction = {
        LLMRandomnessRound: {
            Event.DONE: LLMSelectKeeperRound,
            Event.NO_MAJORITY: LLMRandomnessRound,
            Event.ROUND_TIMEOUT: LLMRandomnessRound,
        },
        LLMSelectKeeperRound: {
            Event.DONE: LLMRound,
            Event.NO_MAJORITY: LLMRandomnessRound,
            Event.ROUND_TIMEOUT: LLMRandomnessRound,
        },
        LLMRound: {
            Event.DONE_CONTINUE: LLMRound,
            Event.DONE_FINISHED: FinishedLLMRound,
            Event.DID_NOT_SEND: LLMRandomnessRound,
            Event.ROUND_TIMEOUT: LLMRandomnessRound,
        },
        FinishedLLMRound: {},
    }
    final_states: Set[AppState] = {
        FinishedLLMRound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: Set[str] = set()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        LLMRandomnessRound: {"llm_values"},
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedLLMRound: {"llm_results"},
    }
