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

"""This package contains the rounds of TwitterScoringAbciApp."""

import json
import math
from dataclasses import asdict, dataclass, is_dataclass
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
    get_name,
)
from packages.valory.skills.mech_interact_abci.states.base import (
    SynchronizedData as MechInteractionSynchronizedData,
)
from packages.valory.skills.twitter_scoring_abci.payloads import (
    DBUpdatePayload,
    PostMechRequestPayload,
    PreMechRequestPayload,
    TwitterDecisionMakingPayload,
    TwitterHashtagsCollectionPayload,
    TwitterMentionsCollectionPayload,
    TwitterRandomnessPayload,
    TwitterSelectKeepersPayload,
)


MAX_API_RETRIES = 2
ERROR_GENERIC = "generic"
ERROR_API_LIMITS = "too many requests"


class DataclassEncoder(json.JSONEncoder):
    """A custom JSON encoder for dataclasses."""

    def default(self, o: Any) -> Any:
        """The default JSON encoder."""
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


@dataclass
class MechMetadata:
    """A Mech's metadata."""

    prompt: str
    tool: str
    nonce: str


@dataclass
class MechRequest:
    """A Mech's request."""

    data: str = ""
    requestId: int = 0


@dataclass
class MechInteractionResponse(MechRequest):
    """A structure for the response of a mech interaction task."""

    nonce: str = ""
    result: Optional[str] = None
    error: str = "Unknown"

    def retries_exceeded(self) -> None:
        """Set an incorrect format response."""
        self.error = "Retries were exceeded while trying to get the mech's response."

    def incorrect_format(self, res: Any) -> None:
        """Set an incorrect format response."""
        self.error = f"The response's format was unexpected: {res}"


class Event(Enum):
    """TwitterScoringAbciApp Events"""

    DONE = "done"
    DONE_MAX_RETRIES = "done_max_retries"
    DONE_API_LIMITS = "done_api_limits"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"
    TWEET_EVALUATION_ROUND_TIMEOUT = "tweet_evaluation_round_timeout"
    API_ERROR = "api_error"
    RETRIEVE_HASHTAGS = "retrieve_hashtags"
    RETRIEVE_MENTIONS = "retrieve_mentions"
    PRE_MECH = "pre_mech"
    POST_MECH = "post_mech"
    DB_UPDATE = "db_update"
    SELECT_KEEPERS = "select_keepers"
    SKIP_EVALUATION = "skip_evaluation"


class SynchronizedData(MechInteractionSynchronizedData):
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
    def tweets(self) -> dict:
        """Get the tweets."""
        return cast(dict, self.db.get("tweets", {}))

    @property
    def latest_mention_tweet_id(self) -> dict:
        """Get the latest_mention_tweet_id."""
        return cast(dict, self.db.get("latest_mention_tweet_id", None))

    @property
    def latest_hashtag_tweet_id(self) -> dict:
        """Get the latest_hashtag_tweet_id."""
        return cast(dict, self.db.get("latest_hashtag_tweet_id", None))

    @property
    def number_of_tweets_pulled_today(self) -> dict:
        """Get the number_of_tweets_pulled_today."""
        return cast(dict, self.db.get("number_of_tweets_pulled_today", None))

    @property
    def last_tweet_pull_window_reset(self) -> dict:
        """Get the last_tweet_pull_window_reset."""
        return cast(dict, self.db.get("last_tweet_pull_window_reset", None))

    @property
    def performed_twitter_tasks(self) -> dict:
        """Get the twitter_tasks."""
        return cast(dict, self.db.get("performed_twitter_tasks", {}))

    @property
    def most_voted_keeper_address(self) -> str:
        """Get the most_voted_keeper_address."""
        return cast(str, self.db.get_strict("most_voted_keeper_address"))

    @property
    def most_voted_keeper_addresses(self) -> list:
        """Get the most_voted_keeper_addresses."""
        return cast(list, self.db.get_strict("most_voted_keeper_addresses"))

    @property
    def are_keepers_set(self) -> bool:
        """Check whether keepers are set."""
        return self.db.get("most_voted_keeper_addresses", None) is not None


class TwitterDecisionMakingRound(CollectSameUntilThresholdRound):
    """TwitterDecisionMakingRound"""

    payload_class = TwitterDecisionMakingPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            event = Event(self.most_voted_payload)
            # Reference events to avoid tox -e check-abciapp-specs failures
            # Event.DONE, Event.DB_UPDATE, Event.RETRIEVE_MENTIONS, Event.RETRIEVE_HASHTAGS, Event.SELECT_KEEPERS
            # Event.POST_MECH, Event.PRE_MECH
            return self.synchronized_data, event
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class TwitterMentionsCollectionRound(CollectSameUntilThresholdRound):
    """TwitterMentionsCollectionRound"""

    payload_class = TwitterMentionsCollectionPayload
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
            performed_twitter_tasks = cast(
                SynchronizedData, self.synchronized_data
            ).performed_twitter_tasks

            payload = json.loads(self.most_voted_payload)

            # API error
            if "error" in payload:
                # API limits
                if payload["error"] == ERROR_API_LIMITS:
                    performed_twitter_tasks[
                        "retrieve_mentions"
                    ] = Event.DONE_MAX_RETRIES.value

                    synchronized_data = self.synchronized_data.update(
                        synchronized_data_class=SynchronizedData,
                        **{
                            get_name(SynchronizedData.sleep_until): payload[
                                "sleep_until"
                            ],
                            get_name(
                                SynchronizedData.performed_twitter_tasks
                            ): performed_twitter_tasks,
                        },
                    )
                    return synchronized_data, Event.DONE_API_LIMITS

                api_retries = (
                    cast(SynchronizedData, self.synchronized_data).api_retries + 1
                )

                # Other API errors
                if api_retries >= MAX_API_RETRIES:
                    performed_twitter_tasks[
                        "retrieve_mentions"
                    ] = Event.DONE_MAX_RETRIES.value
                    synchronized_data = self.synchronized_data.update(
                        synchronized_data_class=SynchronizedData,
                        **{
                            get_name(SynchronizedData.api_retries): 0,  # reset retries
                            get_name(
                                SynchronizedData.performed_twitter_tasks
                            ): performed_twitter_tasks,
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
            previous_tweets = cast(SynchronizedData, self.synchronized_data).tweets
            performed_twitter_tasks["retrieve_mentions"] = Event.DONE.value
            new_tweets = payload["tweets"]

            updates = {
                get_name(SynchronizedData.tweets): {
                    **new_tweets,
                    **previous_tweets,
                },  # order matters here: if there is duplication, keep old tweets
                get_name(SynchronizedData.number_of_tweets_pulled_today): payload[
                    "number_of_tweets_pulled_today"
                ],
                get_name(SynchronizedData.last_tweet_pull_window_reset): payload[
                    "last_tweet_pull_window_reset"
                ],
                get_name(
                    SynchronizedData.performed_twitter_tasks
                ): performed_twitter_tasks,
                get_name(SynchronizedData.sleep_until): payload["sleep_until"],
            }

            if payload["latest_mention_tweet_id"]:
                updates[get_name(SynchronizedData.latest_mention_tweet_id)] = payload[
                    "latest_mention_tweet_id"
                ]
            else:
                updates[
                    get_name(SynchronizedData.latest_mention_tweet_id)
                ] = (
                    self.context.contribute_db.data.module_data.twitter.latest_mention_tweet_id
                )

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


class TwitterHashtagsCollectionRound(CollectSameUntilThresholdRound):
    """TwitterHashtagsCollectionRound"""

    payload_class = TwitterHashtagsCollectionPayload
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
            performed_twitter_tasks = cast(
                SynchronizedData, self.synchronized_data
            ).performed_twitter_tasks

            payload = json.loads(self.most_voted_payload)

            # Api error
            if "error" in payload:
                # API limits
                if payload["error"] == ERROR_API_LIMITS:
                    performed_twitter_tasks[
                        "retrieve_hashtags"
                    ] = Event.DONE_MAX_RETRIES.value

                    synchronized_data = self.synchronized_data.update(
                        synchronized_data_class=SynchronizedData,
                        **{
                            get_name(SynchronizedData.sleep_until): payload[
                                "sleep_until"
                            ],
                            get_name(
                                SynchronizedData.performed_twitter_tasks
                            ): performed_twitter_tasks,
                        },
                    )
                    return synchronized_data, Event.DONE_API_LIMITS

                api_retries = (
                    cast(SynchronizedData, self.synchronized_data).api_retries + 1
                )

                # Other API errors
                if api_retries >= MAX_API_RETRIES:
                    performed_twitter_tasks[
                        "retrieve_hashtags"
                    ] = Event.DONE_MAX_RETRIES.value
                    synchronized_data = self.synchronized_data.update(
                        synchronized_data_class=SynchronizedData,
                        **{
                            get_name(SynchronizedData.api_retries): 0,  # reset retries
                            get_name(
                                SynchronizedData.performed_twitter_tasks
                            ): performed_twitter_tasks,
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
            previous_tweets = cast(SynchronizedData, self.synchronized_data).tweets
            performed_twitter_tasks["retrieve_hashtags"] = Event.DONE.value
            new_tweets = payload["tweets"]

            updates = {
                get_name(SynchronizedData.tweets): {
                    **new_tweets,
                    **previous_tweets,
                },  # order matters here: if there is duplication, keep old tweets
                get_name(SynchronizedData.number_of_tweets_pulled_today): payload[
                    "number_of_tweets_pulled_today"
                ],
                get_name(SynchronizedData.last_tweet_pull_window_reset): payload[
                    "last_tweet_pull_window_reset"
                ],
                get_name(
                    SynchronizedData.performed_twitter_tasks
                ): performed_twitter_tasks,
                get_name(SynchronizedData.sleep_until): payload["sleep_until"],
            }

            if payload["latest_hashtag_tweet_id"]:
                updates[get_name(SynchronizedData.latest_hashtag_tweet_id)] = payload[
                    "latest_hashtag_tweet_id"
                ]
            else:
                updates[
                    get_name(SynchronizedData.latest_hashtag_tweet_id)
                ] = (
                    self.context.contribute_db.data.module_data.twitter.latest_hashtag_tweet_id
                )
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


class PreMechRequestRound(CollectSameUntilThresholdRound):
    """PreMechRequestRound"""

    payload_class = PreMechRequestPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""
        if self.threshold_reached:
            payload = json.loads(self.most_voted_payload)
            new_mech_requests = payload["new_mech_requests"]

            mech_responses = cast(
                SynchronizedData, self.synchronized_data
            ).mech_responses

            # Nothing to evaluate (no new tweets) nor responses to retrieve
            if not new_mech_requests and not mech_responses:
                tweets = cast(SynchronizedData, self.synchronized_data).tweets

                synchronized_data = self.synchronized_data.update(
                    synchronized_data_class=SynchronizedData,
                    **{
                        get_name(SynchronizedData.mech_responses): json.dumps(
                            mech_responses
                        ),
                        get_name(SynchronizedData.tweets): tweets,
                    },
                )
                return synchronized_data, Event.SKIP_EVALUATION

            performed_twitter_tasks = cast(
                SynchronizedData, self.synchronized_data
            ).performed_twitter_tasks
            performed_twitter_tasks["pre_mech"] = Event.DONE.value

            self.context.logger.info(
                f"new_mech_requests PreMechRequestRound: {new_mech_requests}"
            )

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.mech_requests): json.dumps(
                        new_mech_requests
                    ),  # delete previous requests
                    get_name(
                        SynchronizedData.performed_twitter_tasks
                    ): performed_twitter_tasks,
                    # Overwrite safe address with the gnosis one before
                    # a mech request
                    get_name(
                        SynchronizedData.safe_contract_address
                    ): self.context.params.safe_contract_address_gnosis,
                },
            )
            return synchronized_data, Event.DONE

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class PostMechRequestRound(CollectSameUntilThresholdRound):
    """PostMechRequestRound"""

    payload_class = PostMechRequestPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""
        if self.threshold_reached:
            payload = json.loads(self.most_voted_payload)

            performed_twitter_tasks = cast(
                SynchronizedData, self.synchronized_data
            ).performed_twitter_tasks
            performed_twitter_tasks["post_mech"] = Event.DONE.value

            # Remove already used responses
            mech_responses = cast(
                SynchronizedData, self.synchronized_data
            ).mech_responses
            mech_responses = [
                r
                for r in mech_responses
                if r.nonce not in payload["responses_to_remove"]
            ]

            serialized_responses = json.dumps(mech_responses, cls=DataclassEncoder)

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.tweets): payload["tweets"],
                    get_name(
                        SynchronizedData.performed_twitter_tasks
                    ): performed_twitter_tasks,
                    get_name(SynchronizedData.mech_responses): serialized_responses,
                },
            )
            return synchronized_data, Event.DONE

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class DBUpdateRound(CollectSameUntilThresholdRound):
    """DBUpdateRound"""

    payload_class = DBUpdatePayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""

        if self.keeper_payload is None:
            return None

        performed_twitter_tasks = cast(
            SynchronizedData, self.synchronized_data
        ).performed_twitter_tasks
        performed_twitter_tasks["db_update"] = Event.DONE.value

        # Clear processed tweets that are no longer needed. Keep only those with no points yet.
        tweets = cast(SynchronizedData, self.synchronized_data).tweets
        tweets = {k: v for k, v in tweets.items() if "points" not in v}

        synchronized_data = self.synchronized_data.update(
            synchronized_data_class=SynchronizedData,
            **{
                get_name(
                    SynchronizedData.performed_twitter_tasks
                ): performed_twitter_tasks,
                get_name(SynchronizedData.tweets): tweets,
            },
        )
        return synchronized_data, Event.DONE


class TwitterRandomnessRound(CollectSameUntilThresholdRound):
    """A round for generating randomness"""

    payload_class = TwitterRandomnessPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_randomness)
    selection_key = (
        get_name(SynchronizedData.most_voted_randomness),
        get_name(SynchronizedData.most_voted_randomness),
    )
    extended_requirements = ()


class TwitterSelectKeepersRound(CollectSameUntilThresholdRound):
    """A round in which a keeper is selected for transaction submission"""

    payload_class = TwitterSelectKeepersPayload
    synchronized_data_class = SynchronizedData
    extended_requirements = ()

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            performed_twitter_tasks = cast(
                SynchronizedData, self.synchronized_data
            ).performed_twitter_tasks
            performed_twitter_tasks["select_keepers"] = Event.DONE.value

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.most_voted_keeper_addresses): json.loads(
                        self.most_voted_payload
                    ),
                    get_name(
                        SynchronizedData.performed_twitter_tasks
                    ): performed_twitter_tasks,
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


class FinishedTwitterCollectionRound(DegenerateRound):
    """FinishedTwitterScoringRound"""


class TwitterScoringAbciApp(AbciApp[Event]):
    """TwitterScoringAbciApp"""

    initial_round_cls: AppState = TwitterDecisionMakingRound
    initial_states: Set[AppState] = {TwitterDecisionMakingRound}
    transition_function: AbciAppTransitionFunction = {
        TwitterDecisionMakingRound: {
            Event.SELECT_KEEPERS: TwitterRandomnessRound,
            Event.RETRIEVE_HASHTAGS: TwitterHashtagsCollectionRound,
            Event.RETRIEVE_MENTIONS: TwitterMentionsCollectionRound,
            Event.PRE_MECH: PreMechRequestRound,
            Event.POST_MECH: PostMechRequestRound,
            Event.DB_UPDATE: DBUpdateRound,
            Event.DONE: FinishedTwitterScoringRound,
            Event.ROUND_TIMEOUT: TwitterDecisionMakingRound,
            Event.NO_MAJORITY: TwitterDecisionMakingRound,
        },
        TwitterRandomnessRound: {
            Event.DONE: TwitterSelectKeepersRound,
            Event.NO_MAJORITY: TwitterRandomnessRound,
            Event.ROUND_TIMEOUT: TwitterRandomnessRound,
        },
        TwitterSelectKeepersRound: {
            Event.DONE: TwitterDecisionMakingRound,
            Event.NO_MAJORITY: TwitterRandomnessRound,
            Event.ROUND_TIMEOUT: TwitterRandomnessRound,
        },
        TwitterMentionsCollectionRound: {
            Event.DONE: TwitterDecisionMakingRound,
            Event.DONE_MAX_RETRIES: TwitterDecisionMakingRound,
            Event.DONE_API_LIMITS: TwitterDecisionMakingRound,
            Event.API_ERROR: TwitterMentionsCollectionRound,
            Event.NO_MAJORITY: TwitterRandomnessRound,
            Event.ROUND_TIMEOUT: TwitterRandomnessRound,
        },
        TwitterHashtagsCollectionRound: {
            Event.DONE: TwitterDecisionMakingRound,
            Event.DONE_MAX_RETRIES: TwitterDecisionMakingRound,
            Event.DONE_API_LIMITS: TwitterDecisionMakingRound,
            Event.API_ERROR: TwitterHashtagsCollectionRound,
            Event.NO_MAJORITY: TwitterRandomnessRound,
            Event.ROUND_TIMEOUT: TwitterRandomnessRound,
        },
        PreMechRequestRound: {
            Event.DONE: FinishedTwitterCollectionRound,
            Event.SKIP_EVALUATION: FinishedTwitterScoringRound,
            Event.ROUND_TIMEOUT: PreMechRequestRound,
            Event.NO_MAJORITY: PreMechRequestRound,
        },
        PostMechRequestRound: {
            Event.DONE: TwitterDecisionMakingRound,
            Event.ROUND_TIMEOUT: PreMechRequestRound,
            Event.NO_MAJORITY: PostMechRequestRound,
        },
        DBUpdateRound: {
            Event.DONE: TwitterDecisionMakingRound,
            Event.NO_MAJORITY: DBUpdateRound,
            Event.ROUND_TIMEOUT: DBUpdateRound,
        },
        FinishedTwitterScoringRound: {},
        FinishedTwitterCollectionRound: {},
    }
    final_states: Set[AppState] = {
        FinishedTwitterScoringRound,
        FinishedTwitterCollectionRound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
        Event.TWEET_EVALUATION_ROUND_TIMEOUT: 600.0,
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset(["tweets"])
    db_pre_conditions: Dict[AppState, Set[str]] = {
        TwitterDecisionMakingRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedTwitterScoringRound: set(),
        FinishedTwitterCollectionRound: set(),
    }
