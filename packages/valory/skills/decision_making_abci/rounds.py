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

"""This package contains the rounds of DecisionMakingAbciApp."""

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
    EventToTimeout,
)
from packages.valory.skills.decision_making_abci.payloads import DecisionMakingPayload


TWEET_LENGTH = 280
MAX_REPROMPTS = 2


class Event(Enum):
    """DecisionMakingAbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    NO_MAJORITY = "no_majority"
    READ_CENTAURS = "read_centaurs"
    LLM = "llm"
    DAILY_TWEET = "daily_tweet"
    DAILY_ORBIS = "daily_orbis"
    SCHEDULED_TWEET = "scheduled_tweet"
    UPDATE_CENTAURS = "update_centaurs"
    NEXT_CENTAUR = "next_centaur"
    DONE = "done"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def previous_decision_event(self) -> Optional[str]:
        """Get the previous_decision_event."""
        return cast(str, self.db.get("previous_decision_event", None))

    @property
    def centaurs_data(self) -> list:
        """Get the centaurs_data."""
        return cast(list, self.db.get("centaurs_data", []))

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

    @property
    def write_data(self) -> list:
        """Get the write_stream_id."""
        return cast(list, self.db.get_strict("write_data"))

    @property
    def write_results(self) -> list:
        """Get the write_results."""
        return cast(list, self.db.get_strict("write_results"))

    @property
    def read_stream_id(self) -> Optional[str]:
        """Get the read_stream_id."""
        return cast(str, self.db.get("read_stream_id", None))

    @property
    def read_target_property(self) -> Optional[str]:
        """Get the read_target_property."""
        return cast(str, self.db.get("read_target_property", None))

    @property
    def daily_tweet(self) -> str:
        """Gets the daily_tweet."""
        return cast(str, self.db.get_strict("daily_tweet"))

    @property
    def tweet_ids(self) -> list:
        """Gets the tweet_ids."""
        return cast(list, self.db.get("tweet_ids", []))

    @property
    def re_prompt_attempts(self) -> int:
        """Gets the re_prompt_attempts."""
        return cast(int, self.db.get("re_prompt_attempts", 0))

    @property
    def current_centaur_index(self) -> int:
        """Gets the current_centaur_index."""
        return cast(int, self.db.get("current_centaur_index", 0))

    @property
    def has_centaurs_changes(self) -> bool:
        """Gets the has_centaurs_changes."""
        return cast(bool, self.db.get("has_centaurs_changes", False))


class DecisionMakingRound(CollectSameUntilThresholdRound):
    """DecisionMakingRound"""

    payload_class = DecisionMakingPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:

            # We reference all the events here to prevent the check-abciapp-specs tool from complaining
            # since this round receives the event via payload
            # Event.NO_MAJORITY, Event.DONE, Event.UPDATE_CENTAURS, Event.READ_CENTAURS,
            # Event.SCHEDULED_TWEET, Event.LLM, Event.DAILY_ORBIS, Event.DAILY_TWEET, Event.NEXT_CENTAUR

            payload = json.loads(self.most_voted_payload)
            event = Event(payload["event"])
            synchronized_data = cast(SynchronizedData, self.synchronized_data)

            synchronized_data = synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{**payload["updates"], "previous_decision_event": event.value}
            )
            return synchronized_data, event

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedDecisionMakingReadCentaursRound(DegenerateRound):
    """FinishedDecisionMakingReadCentaursRound"""


class FinishedDecisionMakingLLMRound(DegenerateRound):
    """FinishedDecisionMakingLLMRound"""


class FinishedDecisionMakingWriteTwitterRound(DegenerateRound):
    """FinishedDecisionMakingWriteTwitterRound"""


class FinishedDecisionMakingWriteOrbisRound(DegenerateRound):
    """FinishedDecisionMakingWriteOrbisRound"""


class FinishedDecisionMakingUpdateCentaurRound(DegenerateRound):
    """FinishedDecisionMakingUpdateCentaurRound"""


class FinishedDecisionMakingDoneRound(DegenerateRound):
    """FinishedDecisionMakingDoneRound"""


class DecisionMakingAbciApp(AbciApp[Event]):
    """DecisionMakingAbciApp"""

    initial_round_cls: AppState = DecisionMakingRound
    initial_states: Set[AppState] = {DecisionMakingRound}
    transition_function: AbciAppTransitionFunction = {
        DecisionMakingRound: {
            Event.READ_CENTAURS: FinishedDecisionMakingReadCentaursRound,
            Event.LLM: FinishedDecisionMakingLLMRound,
            Event.DAILY_TWEET: FinishedDecisionMakingWriteTwitterRound,
            Event.SCHEDULED_TWEET: FinishedDecisionMakingWriteTwitterRound,
            Event.DAILY_ORBIS: FinishedDecisionMakingWriteOrbisRound,
            Event.UPDATE_CENTAURS: FinishedDecisionMakingUpdateCentaurRound,
            Event.NEXT_CENTAUR: DecisionMakingRound,
            Event.DONE: FinishedDecisionMakingDoneRound,
            Event.NO_MAJORITY: DecisionMakingRound,
            Event.ROUND_TIMEOUT: DecisionMakingRound,
        },
        FinishedDecisionMakingReadCentaursRound: {},
        FinishedDecisionMakingLLMRound: {},
        FinishedDecisionMakingWriteTwitterRound: {},
        FinishedDecisionMakingWriteOrbisRound: {},
        FinishedDecisionMakingUpdateCentaurRound: {},
        FinishedDecisionMakingDoneRound: {},
    }
    final_states: Set[AppState] = {
        FinishedDecisionMakingReadCentaursRound,
        FinishedDecisionMakingLLMRound,
        FinishedDecisionMakingWriteTwitterRound,
        FinishedDecisionMakingWriteOrbisRound,
        FinishedDecisionMakingUpdateCentaurRound,
        FinishedDecisionMakingDoneRound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        DecisionMakingRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedDecisionMakingReadCentaursRound: set(),
        FinishedDecisionMakingLLMRound: {"llm_prompt_templates", "llm_values"},
        FinishedDecisionMakingWriteTwitterRound: {"write_data"},
        FinishedDecisionMakingWriteOrbisRound: {"write_data"},
        FinishedDecisionMakingUpdateCentaurRound: set(),
        FinishedDecisionMakingDoneRound: set(),
    }
