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

"""This package contains the rounds of WeekInOlasAbciApp."""

import json
import math
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional, Set, Tuple, cast

from packages.valory.skills.abstract_round_abci.base import (
    ABCIAppInternalError,
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
from packages.valory.skills.olas_week_abci.payloads import (
    OlasWeekDecisionMakingPayload,
    OlasWeekEvaluationPayload,
    OlasWeekRandomnessPayload,
    OlasWeekSelectKeepersPayload,
    OlasWeekTweetCollectionPayload,
    OpenAICallCheckPayload,
)


MAX_API_RETRIES = 2
ERROR_GENERIC = "generic"
ERROR_API_LIMITS = "too many requests"


class Event(Enum):
    """WeekInOlasAbciApp Events"""

    DONE = "done"
    DONE_SKIP = "done_skip"
    DONE_MAX_RETRIES = "done_max_retries"
    DONE_API_LIMITS = "done_api_limits"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"
    OPENAI_CALL_CHECK = "openai_call_check"
    NO_ALLOWANCE = "no_allowance"
    SELECT_KEEPERS = "select_keepers"
    RETRIEVE_TWEETS = "retrieve_tweets"
    TWEET_EVALUATION_ROUND_TIMEOUT = "tweet_evaluation_round_timeout"
    API_ERROR = "api_error"
    EVALUATE = "evaluate"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def api_retries(self) -> int:
        """Gets the number of API retries."""
        return cast(int, self.db.get("api_retries", 0))

    @property
    def sleep_until(self) -> Optional[int]:
        """Gets the timestamp of the next Twitter time window for rate limits."""
        return cast(int, self.db.get("sleep_until", None))

    @property
    def weekly_tweets(self) -> list:
        """Get the weekly_tweets."""
        return cast(list, self.db.get("weekly_tweets", []))

    @property
    def summary_tweets(self) -> list:
        """Get the summary_tweets."""
        return cast(list, self.db.get("summary_tweets", []))

    @property
    def number_of_tweets_pulled_today(self) -> dict:
        """Get the number_of_tweets_pulled_today."""
        return cast(dict, self.db.get("number_of_tweets_pulled_today", None))

    @property
    def last_tweet_pull_window_reset(self) -> dict:
        """Get the last_tweet_pull_window_reset."""
        return cast(dict, self.db.get("last_tweet_pull_window_reset", None))

    @property
    def performed_olas_week_tasks(self) -> dict:
        """Get the twitter_tasks."""
        return cast(dict, self.db.get("performed_olas_week_tasks", {}))

    @property
    def most_voted_keeper_addresses(self) -> list:
        """Get the most_voted_keeper_addresses."""
        return cast(list, self.db.get_strict("most_voted_keeper_addresses"))

    @property
    def most_voted_keeper_address(self) -> list:
        """Get the most_voted_keeper_address."""
        return cast(list, self.db.get_strict("most_voted_keeper_address"))

    @property
    def are_keepers_set(self) -> bool:
        """Check whether keepers are set."""
        return self.db.get("most_voted_keeper_addresses", None) is not None


class OlasWeekDecisionMakingRound(CollectSameUntilThresholdRound):
    """OlasWeekDecisionMakingRound"""

    payload_class = OlasWeekDecisionMakingPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            event = Event(self.most_voted_payload)
            # Reference events to avoid tox -e check-abciapp-specs failures
            # Event.DONE, Event.RETRIEVE_TWEETS, Event.OPENAI_CALL_CHECK, Event.EVALUATE, Event.DONE_SKIP, Event.SELECT_KEEPERS
            return self.synchronized_data, event
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class OlasWeekOpenAICallCheckRound(CollectSameUntilThresholdRound):
    """OlasWeekOpenAICallCheckRound"""

    payload_class = OpenAICallCheckPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    CALLS_REMAINING = "CALLS_REMAINING"

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            performed_olas_week_tasks = cast(
                SynchronizedData, self.synchronized_data
            ).performed_olas_week_tasks

            # Happy path
            if self.most_voted_payload == self.CALLS_REMAINING:
                performed_olas_week_tasks["openai_call_check"] = Event.DONE.value
                synchronized_data = self.synchronized_data.update(
                    synchronized_data_class=SynchronizedData,
                    **{
                        get_name(
                            SynchronizedData.performed_olas_week_tasks
                        ): performed_olas_week_tasks
                    },
                )
                return synchronized_data, Event.DONE

            # No allowance
            performed_olas_week_tasks["openai_call_check"] = Event.NO_ALLOWANCE.value
            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(
                        SynchronizedData.performed_olas_week_tasks
                    ): performed_olas_week_tasks
                },
            )
            return synchronized_data, Event.NO_ALLOWANCE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class OlasWeekTweetCollectionRound(CollectSameUntilThresholdRound):
    """OlasWeekTweetCollectionRound"""

    payload_class = OlasWeekTweetCollectionPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    @property
    def consensus_threshold(self):
        """Consensus threshold"""
        return math.ceil(self.synchronized_data.nb_participants / 2)  # half or 1

    @property
    def threshold_reached(
        self,
    ) -> bool:
        """Check if the threshold has been reached."""
        counts = self.payload_values_count.values()
        return any(count >= self.consensus_threshold for count in counts)

    @property
    def most_voted_payload_values(
        self,
    ) -> Tuple[Any, ...]:
        """Get the most voted payload values."""
        most_voted_payload_values, max_votes = self.payload_values_count.most_common()[
            0
        ]
        if max_votes < self.consensus_threshold:
            raise ABCIAppInternalError("not enough votes")
        return most_voted_payload_values

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            performed_olas_week_tasks = cast(
                SynchronizedData, self.synchronized_data
            ).performed_olas_week_tasks

            payload = json.loads(self.most_voted_payload)

            # API error
            if "error" in payload:
                # API limits
                if payload["error"] == ERROR_API_LIMITS:
                    performed_olas_week_tasks[
                        "retrieve_tweets"
                    ] = Event.DONE_MAX_RETRIES.value

                    synchronized_data = self.synchronized_data.update(
                        synchronized_data_class=SynchronizedData,
                        **{
                            get_name(SynchronizedData.sleep_until): payload[
                                "sleep_until"
                            ],
                            get_name(
                                SynchronizedData.performed_olas_week_tasks
                            ): performed_olas_week_tasks,
                        },
                    )
                    return synchronized_data, Event.DONE_API_LIMITS

                api_retries = (
                    cast(SynchronizedData, self.synchronized_data).api_retries + 1
                )

                # Other API errors
                if api_retries >= MAX_API_RETRIES:
                    performed_olas_week_tasks[
                        "retrieve_tweets"
                    ] = Event.DONE_MAX_RETRIES.value
                    synchronized_data = self.synchronized_data.update(
                        synchronized_data_class=SynchronizedData,
                        **{
                            get_name(SynchronizedData.api_retries): 0,  # reset retries
                            get_name(
                                SynchronizedData.performed_olas_week_tasks
                            ): performed_olas_week_tasks,
                            get_name(SynchronizedData.sleep_until): payload[
                                "sleep_until"
                            ],
                        },
                    )
                    return synchronized_data, Event.DONE_MAX_RETRIES

                synchronized_data = self.synchronized_data.update(
                    synchronized_data_class=SynchronizedData,
                    **{
                        get_name(SynchronizedData.api_retries): api_retries,
                        get_name(SynchronizedData.sleep_until): payload["sleep_until"],
                    },
                )
                return synchronized_data, Event.API_ERROR

            # Happy path
            weekly_tweets = payload["tweets"]
            performed_olas_week_tasks["retrieve_tweets"] = Event.DONE.value

            updates = {
                get_name(SynchronizedData.weekly_tweets): weekly_tweets,
                get_name(SynchronizedData.number_of_tweets_pulled_today): payload[
                    "number_of_tweets_pulled_today"
                ],
                get_name(SynchronizedData.last_tweet_pull_window_reset): payload[
                    "last_tweet_pull_window_reset"
                ],
                get_name(
                    SynchronizedData.performed_olas_week_tasks
                ): performed_olas_week_tasks,
                get_name(SynchronizedData.sleep_until): payload["sleep_until"],
            }

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **updates,
            )
            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class OlasWeekEvaluationRound(OnlyKeeperSendsRound):
    """OlasWeekEvaluationRound"""

    payload_class = OlasWeekEvaluationPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""
        if self.keeper_payload is None:
            return None

        payload = json.loads(
            cast(OlasWeekEvaluationPayload, self.keeper_payload).content
        )

        performed_olas_week_tasks = cast(
            SynchronizedData, self.synchronized_data
        ).performed_olas_week_tasks
        performed_olas_week_tasks["evaluate"] = Event.DONE.value

        synchronized_data = self.synchronized_data.update(
            synchronized_data_class=SynchronizedData,
            **{
                get_name(SynchronizedData.summary_tweets): payload["summary_tweets"],
                get_name(
                    SynchronizedData.performed_olas_week_tasks
                ): performed_olas_week_tasks,
            },
        )

        return synchronized_data, Event.DONE


class OlasWeekRandomnessRound(CollectSameUntilThresholdRound):
    """A round for generating randomness"""

    payload_class = OlasWeekRandomnessPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_randomness)
    selection_key = (
        get_name(SynchronizedData.most_voted_randomness),
        get_name(SynchronizedData.most_voted_randomness),
    )
    extended_requirements = ()


class OlasWeekSelectKeepersRound(CollectSameUntilThresholdRound):
    """A round in which a keeper is selected for transaction submission"""

    payload_class = OlasWeekSelectKeepersPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            performed_olas_week_tasks = cast(
                SynchronizedData, self.synchronized_data
            ).performed_olas_week_tasks
            performed_olas_week_tasks["select_keepers"] = Event.DONE.value

            keepers = json.loads(self.most_voted_payload)

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.most_voted_keeper_addresses): keepers,
                    get_name(SynchronizedData.most_voted_keeper_address): keepers[
                        0
                    ],  # we also set this for reusing the keeper
                    get_name(
                        SynchronizedData.performed_olas_week_tasks
                    ): performed_olas_week_tasks,
                },
            )
            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedWeekInOlasRound(DegenerateRound):
    """FinishedWeekInOlasRound"""


class WeekInOlasAbciApp(AbciApp[Event]):
    """WeekInOlasAbciApp"""

    initial_round_cls: AppState = OlasWeekDecisionMakingRound
    initial_states: Set[AppState] = {OlasWeekDecisionMakingRound}
    transition_function: AbciAppTransitionFunction = {
        OlasWeekDecisionMakingRound: {
            Event.OPENAI_CALL_CHECK: OlasWeekOpenAICallCheckRound,
            Event.DONE_SKIP: FinishedWeekInOlasRound,
            Event.SELECT_KEEPERS: OlasWeekRandomnessRound,
            Event.RETRIEVE_TWEETS: OlasWeekTweetCollectionRound,
            Event.EVALUATE: OlasWeekEvaluationRound,
            Event.DONE: FinishedWeekInOlasRound,
            Event.ROUND_TIMEOUT: OlasWeekDecisionMakingRound,
            Event.NO_MAJORITY: OlasWeekDecisionMakingRound,
        },
        OlasWeekOpenAICallCheckRound: {
            Event.DONE: OlasWeekDecisionMakingRound,
            Event.NO_ALLOWANCE: OlasWeekDecisionMakingRound,
            Event.NO_MAJORITY: OlasWeekOpenAICallCheckRound,
            Event.ROUND_TIMEOUT: OlasWeekOpenAICallCheckRound,
        },
        OlasWeekRandomnessRound: {
            Event.DONE: OlasWeekSelectKeepersRound,
            Event.NO_MAJORITY: OlasWeekRandomnessRound,
            Event.ROUND_TIMEOUT: OlasWeekRandomnessRound,
        },
        OlasWeekSelectKeepersRound: {
            Event.DONE: OlasWeekDecisionMakingRound,
            Event.NO_MAJORITY: OlasWeekRandomnessRound,
            Event.ROUND_TIMEOUT: OlasWeekRandomnessRound,
        },
        OlasWeekTweetCollectionRound: {
            Event.DONE: OlasWeekDecisionMakingRound,
            Event.DONE_MAX_RETRIES: OlasWeekDecisionMakingRound,
            Event.DONE_API_LIMITS: OlasWeekDecisionMakingRound,
            Event.API_ERROR: OlasWeekTweetCollectionRound,
            Event.NO_MAJORITY: OlasWeekRandomnessRound,
            Event.ROUND_TIMEOUT: OlasWeekRandomnessRound,
        },
        OlasWeekEvaluationRound: {
            Event.DONE: OlasWeekDecisionMakingRound,
            Event.TWEET_EVALUATION_ROUND_TIMEOUT: OlasWeekEvaluationRound,
        },
        FinishedWeekInOlasRound: {},
    }
    final_states: Set[AppState] = {
        FinishedWeekInOlasRound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
        Event.TWEET_EVALUATION_ROUND_TIMEOUT: 600.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset(["pending_write"])
    db_pre_conditions: Dict[AppState, Set[str]] = {
        OlasWeekDecisionMakingRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedWeekInOlasRound: set(),
    }
