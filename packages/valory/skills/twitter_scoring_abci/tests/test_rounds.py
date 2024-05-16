# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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
from unittest import mock

import pytest

from packages.valory.skills.abstract_round_abci.base import (
    AbciAppDB,
    AbstractRound,
    BaseTxPayload,
)
from packages.valory.skills.abstract_round_abci.test_tools.rounds import (
    BaseCollectSameUntilThresholdRoundTest,
    CollectSameUntilThresholdRound,
)
from packages.valory.skills.twitter_scoring_abci.payloads import (
    DBUpdatePayload,
    PreMechRequestPayload,
    TwitterDecisionMakingPayload,
    TwitterHashtagsCollectionPayload,
    TwitterMentionsCollectionPayload,
    TwitterRandomnessPayload,
    TwitterSelectKeepersPayload,
)
from packages.valory.skills.twitter_scoring_abci.rounds import (
    DBUpdateRound,
    Event,
    PreMechRequestRound,
    SynchronizedData,
    TwitterDecisionMakingRound,
    TwitterHashtagsCollectionRound,
    TwitterMentionsCollectionRound,
    TwitterRandomnessRound,
    TwitterSelectKeepersRound,
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
    ceramic_db: Optional[Any] = None


MAX_PARTICIPANTS: int = 4
DUMMY_latest_mention_tweet_id = 0


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


def get_dummy_mentions_collection_payload_serialized(api_error: bool = False) -> str:
    """Dummy twitter observation payload"""
    if api_error:
        return json.dumps({"error": "generic", "sleep_until": None})
    return json.dumps(
        {
            "tweets": {"my_tweet": {}},
            "latest_mention_tweet_id": False,
            "number_of_tweets_pulled_today": 0,
            "last_tweet_pull_window_reset": 0,
            "sleep_until": None,
        },
        sort_keys=True,
    )


def get_dummy_hashtags_collection_payload_serialized(api_error: bool = False) -> str:
    """Dummy twitter observation payload"""
    if api_error:
        return json.dumps({"error": "generic", "sleep_until": None})
    return json.dumps(
        {
            "tweets": {"my_tweet": {}},
            "latest_hashtag_tweet_id": False,
            "number_of_tweets_pulled_today": 0,
            "last_tweet_pull_window_reset": 0,
            "sleep_until": None,
        },
        sort_keys=True,
    )


class BaseTwitterScoringRoundTest(BaseCollectSameUntilThresholdRoundTest):
    """Base test class for ScoreRead rounds."""

    synchronized_data: SynchronizedData
    _synchronized_data_class = SynchronizedData
    _event_class = Event

    def run_test(self, test_case: RoundTestCase) -> None:
        """Run the test"""

        self.synchronized_data.update(**test_case.initial_data)
        context_mock = mock.MagicMock()
        if test_case.ceramic_db:
            context_mock.ceramic_db = test_case.ceramic_db
        test_round = self.round_class(
            synchronized_data=self.synchronized_data, context=context_mock
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


class TestMentionsCollectionRound(BaseTwitterScoringRoundTest):
    """Tests for TwitterMentionsCollectionRound."""

    round_class = TwitterMentionsCollectionRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=TwitterMentionsCollectionPayload,
                    data=get_dummy_mentions_collection_payload_serialized(),
                ),
                final_data={
                    "tweets": json.loads(
                        get_dummy_mentions_collection_payload_serialized()
                    )["tweets"],
                },
                event=Event.DONE,
                most_voted_payload=get_dummy_mentions_collection_payload_serialized(),
                synchronized_data_attr_checks=[],
                ceramic_db={
                    "module_data": {
                        "twitter": {
                            "latest_hashtag_tweet_id": 0,
                            "latest_mention_tweet_id": 0,
                        }
                    }
                },
            ),
            RoundTestCase(
                name="API error",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=TwitterMentionsCollectionPayload,
                    data=get_dummy_mentions_collection_payload_serialized(
                        api_error=True
                    ),
                ),
                final_data={},
                event=Event.DONE_MAX_RETRIES,
                most_voted_payload=get_dummy_mentions_collection_payload_serialized(
                    api_error=True
                ),
                synchronized_data_attr_checks=[],
            ),
            RoundTestCase(
                name="API error: max retries",
                initial_data={
                    "api_retries": 2,
                },
                payloads=get_payloads(
                    payload_cls=TwitterMentionsCollectionPayload,
                    data=get_dummy_mentions_collection_payload_serialized(
                        api_error=True
                    ),
                ),
                final_data={},
                event=Event.DONE_MAX_RETRIES,
                most_voted_payload=get_dummy_mentions_collection_payload_serialized(
                    api_error=True
                ),
                synchronized_data_attr_checks=[],
            ),
            RoundTestCase(
                name="API error: api limits",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=TwitterMentionsCollectionPayload,
                    data=get_dummy_mentions_collection_payload_serialized(
                        api_error=True
                    ).replace('"error": "generic"', '"error": "too many requests"'),
                ),
                final_data={},
                event=Event.DONE_API_LIMITS,
                most_voted_payload=get_dummy_mentions_collection_payload_serialized(
                    api_error=True
                ).replace('"error": "generic"', '"error": "too many requests"'),
                synchronized_data_attr_checks=[],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)


class TestHashtagsCollectionRound(BaseTwitterScoringRoundTest):
    """Tests for TwitterMentionsCollectionRound."""

    round_class = TwitterHashtagsCollectionRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=TwitterHashtagsCollectionPayload,
                    data=get_dummy_hashtags_collection_payload_serialized(),
                ),
                final_data={
                    "tweets": json.loads(
                        get_dummy_hashtags_collection_payload_serialized()
                    )["tweets"],
                },
                event=Event.DONE,
                most_voted_payload=get_dummy_hashtags_collection_payload_serialized(),
                synchronized_data_attr_checks=[],
                ceramic_db={"module_data": {"twitter": {"latest_hashtag_tweet_id": 0}}},
            ),
            RoundTestCase(
                name="API error",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=TwitterHashtagsCollectionPayload,
                    data=get_dummy_hashtags_collection_payload_serialized(
                        api_error=True
                    ),
                ),
                final_data={},
                event=Event.DONE_MAX_RETRIES,
                most_voted_payload=get_dummy_hashtags_collection_payload_serialized(
                    api_error=True
                ),
                synchronized_data_attr_checks=[],
            ),
            RoundTestCase(
                name="API error: max retries",
                initial_data={
                    "api_retries": 2,
                },
                payloads=get_payloads(
                    payload_cls=TwitterHashtagsCollectionPayload,
                    data=get_dummy_hashtags_collection_payload_serialized(
                        api_error=True
                    ),
                ),
                final_data={},
                event=Event.DONE_MAX_RETRIES,
                most_voted_payload=get_dummy_hashtags_collection_payload_serialized(
                    api_error=True
                ),
                synchronized_data_attr_checks=[],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)


class TestDecisionMakingRound(BaseTwitterScoringRoundTest):
    """Tests for TwitterDecisionMakingRound."""

    round_class = TwitterDecisionMakingRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=TwitterDecisionMakingPayload,
                    data=Event.RETRIEVE_HASHTAGS.value,
                ),
                final_data={},
                event=Event.RETRIEVE_HASHTAGS,
                most_voted_payload=Event.RETRIEVE_HASHTAGS.value,
                synchronized_data_attr_checks=[],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)


class TestDBUpdateRound(BaseTwitterScoringRoundTest):
    """Tests for DBUpdateRound."""

    round_class = DBUpdateRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=DBUpdatePayload,
                    data='{"ceramic_diff":{}}',
                ),
                final_data={},
                event=Event.DONE,
                most_voted_payload='{"ceramic_diff":{}}',
                synchronized_data_attr_checks=[],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)


class TestPreMechRequestRound(BaseTwitterScoringRoundTest):
    """PreMechRequestRound"""

    round_class = PreMechRequestRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=PreMechRequestPayload,
                    data='{"new_mech_requests":[]}',
                ),
                final_data={},
                event=Event.SKIP_EVALUATION,
                most_voted_payload='{"new_mech_requests":[]}',
                synchronized_data_attr_checks=[],
            ),
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=PreMechRequestPayload,
                    data='{"new_mech_requests":["dummy_request"]}',
                ),
                final_data={},
                event=Event.DONE,
                most_voted_payload='{"new_mech_requests":["dummy_request"]}',
                synchronized_data_attr_checks=[],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)


# -----------------------------------------------------------------------
# Randomness and select keeper tests are ported from Hello World abci app
# -----------------------------------------------------------------------

RANDOMNESS: str = "d1c29dce46f979f9748210d24bce4eae8be91272f5ca1a6aea2832d3dd676f51"


def get_participant_list() -> List[str]:
    """Participants"""
    return [f"agent_{i}" for i in range(MAX_PARTICIPANTS)]


class BaseRoundTestClass:
    """Base test class for Rounds."""

    synchronized_data: SynchronizedData
    participants: List[str]

    @classmethod
    def setup(
        cls,
    ) -> None:
        """Setup the test class."""

        cls.participants = get_participant_list()
        cls.synchronized_data = SynchronizedData(
            AbciAppDB(
                setup_data=dict(
                    participants=[cls.participants],
                    all_participants=[cls.participants],
                    consensus_threshold=[3],
                ),
            )
        )

    def _test_no_majority_event(self, round_obj: AbstractRound) -> None:
        """Test the NO_MAJORITY event."""
        with mock.patch.object(round_obj, "is_majority_possible", return_value=False):
            result = round_obj.end_block()
            assert result is not None
            synchronized_data, event = result
            assert event == Event.NO_MAJORITY


class TestCollectRandomnessRound(BaseRoundTestClass):
    """Tests for CollectRandomnessRound."""

    def test_run(
        self,
    ) -> None:
        """Run tests."""

        test_round = TwitterRandomnessRound(
            synchronized_data=self.synchronized_data, context=mock.MagicMock()
        )
        first_payload, *payloads = [
            TwitterRandomnessPayload(
                sender=participant, randomness=RANDOMNESS, round_id=0
            )
            for participant in self.participants
        ]

        test_round.process_payload(first_payload)
        assert test_round.collection[first_payload.sender] == first_payload
        assert test_round.end_block() is None

        self._test_no_majority_event(test_round)

        for payload in payloads:
            test_round.process_payload(payload)

        actual_next_behaviour = self.synchronized_data.update(
            participant_to_randomness=test_round.serialized_collection,
            most_voted_randomness=test_round.most_voted_payload,
        )

        res = test_round.end_block()
        assert res is not None
        synchronized_data, event = res
        assert all(
            [
                key
                in cast(SynchronizedData, synchronized_data).participant_to_randomness
                for key in cast(
                    SynchronizedData, actual_next_behaviour
                ).participant_to_randomness
            ]
        )
        assert event == Event.DONE


class TestSelectKeeperRound(BaseRoundTestClass):
    """Tests for SelectKeeperRound."""

    def test_run(
        self,
    ) -> None:
        """Run tests."""

        test_round = TwitterSelectKeepersRound(
            synchronized_data=self.synchronized_data, context=mock.MagicMock()
        )

        first_payload, *payloads = [
            TwitterSelectKeepersPayload(
                sender=participant, keepers='["keeper","keeper"]'
            )
            for participant in self.participants
        ]

        test_round.process_payload(first_payload)
        assert test_round.collection[first_payload.sender] == first_payload
        assert test_round.end_block() is None

        self._test_no_majority_event(test_round)

        for payload in payloads:
            test_round.process_payload(payload)

        actual_next_behaviour = self.synchronized_data.update(
            participant_to_selection=test_round.serialized_collection,
            most_voted_keeper_address=test_round.most_voted_payload,
        )

        res = test_round.end_block()
        assert res is not None
        synchronized_data, event = res
        assert all(
            [
                key
                in cast(SynchronizedData, synchronized_data).participant_to_selection
                for key in cast(
                    SynchronizedData, actual_next_behaviour
                ).participant_to_selection
            ]
        )
        assert event == Event.DONE
