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

"""This package contains the rounds of TwitterScoringAbciApp."""

import json
from enum import Enum
from typing import Dict, FrozenSet, Optional, Set, Tuple, cast
import statistics
from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectNonEmptyUntilThresholdRound,
    CollectSameUntilThresholdRound,
    DegenerateRound,
    EventToTimeout,
    get_name,
)
from packages.valory.skills.twitter_scoring_abci.payloads import (
    DBUpdatePayload,
    TweetEvaluationPayload,
    TwitterCollectionPayload,
)


MAX_API_RETRIES = 3


class Event(Enum):
    """TwitterScoringAbciApp Events"""

    DONE = "done"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"
    API_ERROR = "api_error"
    SKIP = "skip"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def ceramic_db(self) -> dict:
        """Get the data stored in the main stream."""
        return cast(dict, self.db.get_strict("ceramic_db"))

    @property
    def pending_write(self) -> bool:
        """Checks whether there are changes pending to be written to Ceramic."""
        return cast(bool, self.db.get("pending_write", False))

    @property
    def api_retries(self) -> int:
        """Gets the number of API retries."""
        return cast(int, self.db.get("api_retries", 0))

    @property
    def tweets(self) -> dict:
        """Get the tweets."""
        return cast(dict, self.db.get_strict("tweets"))

    @property
    def latest_mention_tweet_id(self) -> dict:
        """Get the latest_mention_tweet_id."""
        return cast(dict, self.db.get_strict("latest_mention_tweet_id"))


class TwitterCollectionRound(CollectSameUntilThresholdRound):
    """TwitterCollectionRound"""

    payload_class = TwitterCollectionPayload
    synchronized_data_class = SynchronizedData

    ERROR_PAYLOAD = {"error": "true"}

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            if self.most_voted_payload == json.dumps(
                self.ERROR_PAYLOAD, sort_keys=True
            ):
                api_retries = (
                    cast(SynchronizedData, self.synchronized_data).api_retries + 1
                )

                if api_retries >= MAX_API_RETRIES:
                    return self.synchronized_data, Event.SKIP

                synchronized_data = self.synchronized_data.update(
                    synchronized_data_class=SynchronizedData,
                    **{
                        get_name(SynchronizedData.api_retries): api_retries,
                    },
                )
                return synchronized_data, Event.API_ERROR

            payload = json.loads(self.most_voted_payload)

            tweets = payload["tweets"]

            if not tweets:
                return self.synchronized_data, Event.SKIP

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.tweets): tweets,
                    get_name(SynchronizedData.latest_mention_tweet_id): payload[
                        "latest_mention_tweet_id"
                    ],
                },
            )
            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class TweetEvaluationRound(CollectNonEmptyUntilThresholdRound):
    """TweetEvaluationRound"""

    payload_class = TweetEvaluationPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""
        if self.collection_threshold_reached:
            self.block_confirmations += 1
        if (
            self.collection_threshold_reached
            and self.block_confirmations > self.required_block_confirmations
        ):
            non_empty_values = self._get_non_empty_values()
            tweets = cast(SynchronizedData, self.synchronized_data).tweets

            # Calculate points average
            for tweet_id in tweets.keys():
                tweet_points = [
                    json.loads(value[0])[tweet_id]
                    for value in non_empty_values.values()
                ]
                median = statistics.median(tweet_points)
                tweets[tweet_id]["points"] = median
                print(f"Tweet {tweet_id} has been awarded {median} points")

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.tweets): tweets,
                },
            )

            if all([len(tu) == 0 for tu in non_empty_values]):
                return self.synchronized_data, self.none_event
            return synchronized_data, Event.DONE
        return None


class DBUpdateRound(CollectSameUntilThresholdRound):
    """DBUpdateRound"""

    payload_class = DBUpdatePayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:

            payload = json.loads(self.most_voted_payload)

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.ceramic_db): payload,
                    get_name(SynchronizedData.pending_write): True,
                },
            )
            return synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedTwitterScoringRound(DegenerateRound):
    """FinishedTwitterScoringRound"""


class TwitterScoringAbciApp(AbciApp[Event]):
    """TwitterScoringAbciApp"""

    initial_round_cls: AppState = TwitterCollectionRound
    initial_states: Set[AppState] = {TwitterCollectionRound}
    transition_function: AbciAppTransitionFunction = {
        TwitterCollectionRound: {
            Event.DONE: TweetEvaluationRound,
            Event.API_ERROR: TwitterCollectionRound,
            Event.SKIP: FinishedTwitterScoringRound,
            Event.NO_MAJORITY: TwitterCollectionRound,
            Event.ROUND_TIMEOUT: TwitterCollectionRound,
        },
        TweetEvaluationRound: {
            Event.DONE: DBUpdateRound,
            Event.ROUND_TIMEOUT: TweetEvaluationRound,
        },
        DBUpdateRound: {
            Event.DONE: FinishedTwitterScoringRound,
            Event.NO_MAJORITY: DBUpdateRound,
            Event.ROUND_TIMEOUT: DBUpdateRound,
        },
        FinishedTwitterScoringRound: {},
    }
    final_states: Set[AppState] = {FinishedTwitterScoringRound}
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset(
        [
            "ceramic_db",
            "pending_write",
        ]
    )
    db_pre_conditions: Dict[AppState, Set[str]] = {
        TwitterCollectionRound: set(),
        TweetEvaluationRound: set(),
        DBUpdateRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedTwitterScoringRound: {
            get_name(SynchronizedData.ceramic_db),
        },
    }
