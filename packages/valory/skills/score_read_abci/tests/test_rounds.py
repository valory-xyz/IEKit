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

"""This package contains the tests for rounds of ScoreRead."""

import json
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Hashable,
    List,
    Mapping,
    Optional,
    cast,
)

import pytest

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload
from packages.valory.skills.abstract_round_abci.test_tools.rounds import (
    BaseCollectSameUntilThresholdRoundTest,
    CollectSameUntilThresholdRound,
)
from packages.valory.skills.score_read_abci.payloads import (
    ScoringPayload,
    TwitterObservationPayload,
)
from packages.valory.skills.score_read_abci.rounds import (
    Event,
    ScoringRound,
    SynchronizedData,
    TwitterObservationRound,
)


@dataclass
class RoundTestCase:
    """RoundTestCase"""

    name: str
    initial_data: Dict[str, Hashable]
    payloads: Mapping[str, BaseTxPayload]
    final_data: Dict[str, Any]
    event: Event
    most_voted_payload: Any
    synchronized_data_attr_checks: List[Callable] = field(default_factory=list)


MAX_PARTICIPANTS: int = 4
DUMMY_LATEST_TWEET_ID = 0


def get_participants() -> FrozenSet[str]:
    """Participants"""
    return frozenset([f"agent_{i}" for i in range(MAX_PARTICIPANTS)])


def get_payloads(
    payload_cls: BaseTxPayload,
    data: Optional[str],
) -> Mapping[str, BaseTxPayload]:
    """Get payloads."""
    return {
        participant: payload_cls(participant, data)
        for participant in get_participants()
    }


def get_dummy_twitter_observation_payload_serialized(api_error: bool = False) -> str:
    """Dummy twitter observation payload"""
    if api_error:
        return json.dumps({})
    return json.dumps(
        {
            "user_to_mentions": {"user_a": 1, "user_b": 2},
            "id_to_usernames": {"user_a": "username_a", "user_b": "username_b"},
            "latest_tweet_id": DUMMY_LATEST_TWEET_ID,
        },
        sort_keys=True,
    )


def get_dummy_scoring_payload_serialized() -> str:
    """Dummy scoring payload"""
    return json.dumps(
        {
            "user_to_new_points": {"1": 200, "2": 300, "3": 500},
            "id_to_usernames": {"1": "username_a", "2": "username_b"},
            "latest_tweet_id": "1",
        },
        sort_keys=True,
    )


class BaseScoreReadRoundTest(BaseCollectSameUntilThresholdRoundTest):
    """Base test class for ScoreRead rounds."""

    synchronized_data: SynchronizedData
    _synchronized_data_class = SynchronizedData
    _event_class = Event

    def run_test(self, test_case: RoundTestCase) -> None:
        """Run the test"""

        self.synchronized_data.update(**test_case.initial_data)

        test_round = self.round_class(
            synchronized_data=self.synchronized_data,
        )

        self._complete_run(
            self._test_round(
                test_round=cast(CollectSameUntilThresholdRound, test_round),
                round_payloads=test_case.payloads,
                synchronized_data_update_fn=lambda sync_data, _: sync_data.update(
                    **test_case.final_data
                ),
                synchronized_data_attr_checks=test_case.synchronized_data_attr_checks,
                most_voted_payload=test_case.most_voted_payload,
                exit_event=test_case.event,
            )
        )


class TestTwitterObservationRound(BaseScoreReadRoundTest):
    """Tests for TwitterObservationRound."""

    round_class = TwitterObservationRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=TwitterObservationPayload,
                    data=get_dummy_twitter_observation_payload_serialized(),
                ),
                final_data={
                    "most_voted_api_data": json.loads(
                        get_dummy_twitter_observation_payload_serialized()
                    ),
                    "latest_tweet_id": DUMMY_LATEST_TWEET_ID,
                },
                event=Event.DONE,
                most_voted_payload=get_dummy_twitter_observation_payload_serialized(),
                synchronized_data_attr_checks=[
                    lambda _synchronized_data: _synchronized_data.most_voted_api_data,
                    lambda _synchronized_data: _synchronized_data.latest_tweet_id,
                ],
            ),
            RoundTestCase(
                name="API error",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=TwitterObservationPayload,
                    data=get_dummy_twitter_observation_payload_serialized(
                        api_error=True
                    ),
                ),
                final_data={},
                event=Event.API_ERROR,
                most_voted_payload=get_dummy_twitter_observation_payload_serialized(
                    api_error=True
                ),
                synchronized_data_attr_checks=[],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)


class TestScoringRound(BaseScoreReadRoundTest):
    """Tests for ScoringRound."""

    round_class = ScoringRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=ScoringPayload,
                    data=get_dummy_scoring_payload_serialized(),
                ),
                final_data={
                    "user_to_new_points": {"1": 200, "2": 300, "3": 500},
                    "id_to_usernames": {},
                    "latest_tweet_id": "1",
                },
                event=Event.DONE,
                most_voted_payload=get_dummy_scoring_payload_serialized(),
                synchronized_data_attr_checks=[
                    lambda _synchronized_data: _synchronized_data.user_to_new_points,
                    lambda _synchronized_data: _synchronized_data.latest_tweet_id,
                ],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)
