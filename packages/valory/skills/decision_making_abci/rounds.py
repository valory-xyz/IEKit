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
from packages.valory.skills.decision_making_abci.payloads import (
    DecisionMakingPayload,
    PostTxDecisionPayload,
)


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
    SCORE = "score"
    UPDATE_CENTAURS = "update_centaurs"
    NEXT_CENTAUR = "next_centaur"
    DONE = "done"
    READ_CONTRIBUTE_DB = "read_contribute_db"
    READ_MANUAL_POINTS = "read_manual_points"
    WRITE_CONTRIBUTE_DB = "write_contribute_db"
    WEEK_IN_OLAS_CREATE = "week_in_olas_create"
    TWEET_VALIDATION = "tweet_validation"
    FORCE_DB_UPDATE = "force_db_update"
    CAMPAIGN_VALIDATION = "campaign_validation"
    STAKING_ACTIVITY = "staking_activity"
    STAKING_CHECKPOINT = "staking_checkpoint"
    POST_TX_MECH = "post_tx_mech"
    POST_TX_ACTIVITY_UPDATE = "post_tx_activity_update"
    POST_TX_CHECKPOINT = "post_tx_checkpoint"
    STAKING_DAA_UPDATE = "staking_daa_update"
    POST_TX_DAA = "post_tx_daa"


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
    def summary_tweets(self) -> list:
        """Get the summary_tweets."""
        return cast(list, self.db.get("summary_tweets", []))

    @property
    def tx_submitter(self) -> str:
        """Get the tx_submitter."""
        return cast(str, self.db.get("tx_submitter"))


class DecisionMakingRound(CollectSameUntilThresholdRound):
    """DecisionMakingRound"""

    payload_class = DecisionMakingPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            # We reference all the events here to prevent the check-abciapp-specs tool from complaining
            # since this round receives the event via payload
            # Event.NO_MAJORITY, Event.DONE, Event.UPDATE_CENTAURS, Event.READ_CENTAURS,
            # Event.SCHEDULED_TWEET, Event.LLM, Event.DAILY_ORBIS, Event.DAILY_TWEET, Event.NEXT_CENTAUR
            # Event.SCORE, Event.READ_CONTRIBUTE_DB, Event.READ_MANUAL_POINTS, Event.WRITE_CONTRIBUTE_DB
            # Event.WEEK_IN_OLAS_CREATE, Event.TWEET_VALIDATION, Event.FORCE_DB_UPDATE, Event.CAMPAIGN_VALIDATION
            # Event.STAKING_ACTIVITY, Event.STAKING_CHECKPOINT, Event.STAKING_DAA_UPDATE

            payload = json.loads(self.most_voted_payload)
            event = Event(payload["event"])
            synchronized_data = cast(SynchronizedData, self.synchronized_data)
            if event == Event.DONE:
                synchronized_data = synchronized_data.update(
                    synchronized_data_class=SynchronizedData,
                    **{
                        **payload["updates"],
                        "previous_decision_event": event.value,
                        "score_data": dict(),
                        "centaurs_data": list(),
                    }
                )
            else:
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


class PostTxDecisionMakingRound(CollectSameUntilThresholdRound):
    """PostTxDecisionMakingRound"""

    payload_class = PostTxDecisionPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            # We reference all the events here to prevent the check-abciapp-specs tool from complaining
            # since this round receives the event via payload
            # Event.DONE, Event.NO_MAJORITY
            # Event.POST_TX_MECH, Event.POST_TX_ACTIVITY_UPDATE, Event.POST_TX_CHECKPOINT, Event.POST_TX_DAA

            event = Event(self.most_voted_payload)
            return self.synchronized_data, event

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedDecisionMakingDBLoadRound(DegenerateRound):
    """FinishedDecisionMakingDBLoadRound"""


class FinishedDecisionMakingLLMRound(DegenerateRound):
    """FinishedDecisionMakingLLMRound"""


class FinishedDecisionMakingWriteTwitterRound(DegenerateRound):
    """FinishedDecisionMakingWriteTwitterRound"""


class FinishedDecisionMakingWriteOrbisRound(DegenerateRound):
    """FinishedDecisionMakingWriteOrbisRound"""


class FinishedDecisionMakingUpdateCentaurRound(DegenerateRound):
    """FinishedDecisionMakingUpdateCentaurRound"""


class FinishedDecisionMakingReadContributeDBRound(DegenerateRound):
    """FinishedDecisionMakingReadContributeDBRound"""


class FinishedDecisionMakingWriteContributeDBRound(DegenerateRound):
    """FinishedDecisionMakingWriteContributeDBRound"""


class FinishedDecisionMakingReadManualPointsRound(DegenerateRound):
    """FinishedDecisionMakingReadManualPointsRound"""


class FinishedDecisionMakingScoreRound(DegenerateRound):
    """FinishedDecisionMakingScoreRound"""


class FinishedDecisionMakingDoneRound(DegenerateRound):
    """FinishedDecisionMakingDoneRound"""


class FinishedDecisionMakingWeekInOlasRound(DegenerateRound):
    """FinishedDecisionMakingWeekInOlasRound"""


class FinishedDecisionMakingActivityRound(DegenerateRound):
    """FinishedDecisionMakingActivityRound"""


class FinishedDecisionMakingCheckpointRound(DegenerateRound):
    """FinishedDecisionMakingCheckpointRound"""


class FinishedDecisionMakingDAARound(DegenerateRound):
    """FinishedDecisionMakingDAARound"""


class FinishedPostMechResponseRound(DegenerateRound):
    """FinishedPostMechResponseRound"""


class FinishedPostActivityUpdateRound(DegenerateRound):
    """FinishedPostActivityUpdateRound"""


class FinishedPostCheckpointRound(DegenerateRound):
    """FinishedPostCheckpointRound"""


class FinishedPostDAARound(DegenerateRound):
    """FinishedPostDAARound"""


class DecisionMakingAbciApp(AbciApp[Event]):
    """DecisionMakingAbciApp"""

    initial_round_cls: AppState = DecisionMakingRound
    initial_states: Set[AppState] = {DecisionMakingRound, PostTxDecisionMakingRound}
    transition_function: AbciAppTransitionFunction = {
        DecisionMakingRound: {
            Event.READ_CENTAURS: FinishedDecisionMakingDBLoadRound,
            Event.LLM: FinishedDecisionMakingLLMRound,
            Event.DAILY_TWEET: FinishedDecisionMakingWriteTwitterRound,
            Event.TWEET_VALIDATION: DecisionMakingRound,
            Event.SCHEDULED_TWEET: FinishedDecisionMakingWriteTwitterRound,
            Event.FORCE_DB_UPDATE: DecisionMakingRound,
            Event.WEEK_IN_OLAS_CREATE: FinishedDecisionMakingWeekInOlasRound,
            Event.DAILY_ORBIS: FinishedDecisionMakingWriteOrbisRound,
            Event.UPDATE_CENTAURS: FinishedDecisionMakingUpdateCentaurRound,
            Event.SCORE: FinishedDecisionMakingScoreRound,
            Event.READ_CONTRIBUTE_DB: FinishedDecisionMakingReadContributeDBRound,
            Event.WRITE_CONTRIBUTE_DB: FinishedDecisionMakingWriteContributeDBRound,
            Event.READ_MANUAL_POINTS: FinishedDecisionMakingReadManualPointsRound,
            Event.NEXT_CENTAUR: DecisionMakingRound,
            Event.DONE: FinishedDecisionMakingDoneRound,
            Event.NO_MAJORITY: DecisionMakingRound,
            Event.ROUND_TIMEOUT: DecisionMakingRound,
            Event.CAMPAIGN_VALIDATION: DecisionMakingRound,
            Event.STAKING_ACTIVITY: FinishedDecisionMakingActivityRound,
            Event.STAKING_CHECKPOINT: FinishedDecisionMakingCheckpointRound,
            Event.STAKING_DAA_UPDATE: FinishedDecisionMakingDAARound,
        },
        PostTxDecisionMakingRound: {
            Event.POST_TX_MECH: FinishedPostMechResponseRound,
            Event.POST_TX_ACTIVITY_UPDATE: FinishedPostActivityUpdateRound,
            Event.POST_TX_CHECKPOINT: FinishedPostCheckpointRound,
            Event.POST_TX_DAA: FinishedPostDAARound,
            Event.DONE: PostTxDecisionMakingRound,
            Event.NO_MAJORITY: PostTxDecisionMakingRound,
        },
        FinishedDecisionMakingDBLoadRound: {},
        FinishedDecisionMakingLLMRound: {},
        FinishedDecisionMakingWriteTwitterRound: {},
        FinishedDecisionMakingWriteOrbisRound: {},
        FinishedDecisionMakingScoreRound: {},
        FinishedDecisionMakingUpdateCentaurRound: {},
        FinishedDecisionMakingDoneRound: {},
        FinishedDecisionMakingReadContributeDBRound: {},
        FinishedDecisionMakingWriteContributeDBRound: {},
        FinishedDecisionMakingReadManualPointsRound: {},
        FinishedDecisionMakingWeekInOlasRound: {},
        FinishedDecisionMakingActivityRound: {},
        FinishedDecisionMakingCheckpointRound: {},
        FinishedPostMechResponseRound: {},
        FinishedPostActivityUpdateRound: {},
        FinishedPostCheckpointRound: {},
        FinishedPostDAARound: {},
        FinishedDecisionMakingDAARound: {},
    }
    final_states: Set[AppState] = {
        FinishedDecisionMakingDBLoadRound,
        FinishedDecisionMakingLLMRound,
        FinishedDecisionMakingWriteTwitterRound,
        FinishedDecisionMakingWriteOrbisRound,
        FinishedDecisionMakingScoreRound,
        FinishedDecisionMakingUpdateCentaurRound,
        FinishedDecisionMakingDoneRound,
        FinishedDecisionMakingReadContributeDBRound,
        FinishedDecisionMakingWriteContributeDBRound,
        FinishedDecisionMakingReadManualPointsRound,
        FinishedDecisionMakingWeekInOlasRound,
        FinishedDecisionMakingActivityRound,
        FinishedDecisionMakingCheckpointRound,
        FinishedPostMechResponseRound,
        FinishedPostActivityUpdateRound,
        FinishedPostCheckpointRound,
        FinishedPostDAARound,
        FinishedDecisionMakingDAARound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        DecisionMakingRound: set(),
        PostTxDecisionMakingRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedDecisionMakingDBLoadRound: set(),
        FinishedDecisionMakingLLMRound: {"llm_prompt_templates", "llm_values"},
        FinishedDecisionMakingWriteTwitterRound: {"write_data"},
        FinishedDecisionMakingWriteOrbisRound: {"write_data"},
        FinishedDecisionMakingScoreRound: set(),
        FinishedDecisionMakingUpdateCentaurRound: set(),
        FinishedDecisionMakingDoneRound: set(),
        FinishedDecisionMakingReadContributeDBRound: set(),
        FinishedDecisionMakingWriteContributeDBRound: set(),
        FinishedDecisionMakingReadManualPointsRound: set(),
        FinishedDecisionMakingWeekInOlasRound: set(),
        FinishedDecisionMakingActivityRound: set(),
        FinishedDecisionMakingCheckpointRound: set(),
        FinishedPostMechResponseRound: set(),
        FinishedPostActivityUpdateRound: set(),
        FinishedPostCheckpointRound: set(),
        FinishedPostDAARound: set(),
        FinishedDecisionMakingDAARound: set(),
    }
