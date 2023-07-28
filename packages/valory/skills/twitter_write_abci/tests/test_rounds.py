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
from typing import Any, Callable, Dict, Hashable, List, Mapping, Union, cast
from unittest import mock

import pytest

from packages.valory.skills.abstract_round_abci.base import (
    AbciAppDB,
    AbstractRound,
    BaseTxPayload,
)
from packages.valory.skills.abstract_round_abci.test_tools.rounds import (
    BaseOnlyKeeperSendsRoundTest,
)
from packages.valory.skills.twitter_write_abci.payloads import (
    RandomnessPayload,
    SelectKeeperPayload,
    TwitterWritePayload,
)
from packages.valory.skills.twitter_write_abci.rounds import (
    Event,
    RandomnessTwitterRound,
    SelectKeeperTwitterRound,
    SynchronizedData,
    TwitterWriteRound,
)


MAX_PARTICIPANTS: int = 4


def get_participants() -> List[str]:
    """Participants"""
    return [f"agent_{i}" for i in range(MAX_PARTICIPANTS)]


# -----------------------------------------------------------------------
# Randomness and select keeper tests are ported from Hello World abci app
# -----------------------------------------------------------------------

RANDOMNESS: str = "d1c29dce46f979f9748210d24bce4eae8be91272f5ca1a6aea2832d3dd676f51"


class BaseRoundTestClass:
    """Base test class for Rounds."""

    synchronized_data: SynchronizedData
    participants: List[str]

    @classmethod
    def setup(
        cls,
    ) -> None:
        """Setup the test class."""

        cls.participants = get_participants()
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

        test_round = RandomnessTwitterRound(
            synchronized_data=self.synchronized_data,
        )
        first_payload, *payloads = [
            RandomnessPayload(sender=participant, randomness=RANDOMNESS, round_id=0)
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

        test_round = SelectKeeperTwitterRound(
            synchronized_data=self.synchronized_data,
        )

        first_payload, *payloads = [
            SelectKeeperPayload(sender=participant, keeper="keeper")
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


@dataclass
class RoundTestCase:
    """RoundTestCase"""

    name: str
    initial_data: Dict[str, Hashable]
    payloads: Mapping[str, Union[BaseTxPayload, SelectKeeperPayload]]
    final_data: Dict[str, Any]
    event: Event
    most_voted_payload: Any
    synchronized_data_attr_checks: List[Callable] = field(default_factory=list)


class TestStreamWriteRound(BaseOnlyKeeperSendsRoundTest):
    """Test StreamWriteRound."""

    _synchronized_data_class = SynchronizedData
    _event_class = Event
    _round_class = TwitterWriteRound

    @pytest.mark.parametrize(
        "payload_str, exit_event",
        (
            (
                json.dumps({"success": True, "tweet_id": 123}),
                Event.DONE,
            ),
            (
                json.dumps({"success": False, "tweet_id": None}),
                Event.API_ERROR,
            ),
        ),
    )
    def test_round(
        self,
        payload_str: str,
        exit_event: Event,
    ) -> None:
        """Runs tests."""

        sender = "agent_0-----------------------------------"

        self.participants = frozenset([f"agent_{i}" + "-" * 35 for i in range(4)])
        self.synchronized_data = cast(
            SynchronizedData,
            self.synchronized_data.update(
                participants=[f"agent_{i}" + "-" * 35 for i in range(4)],
                keeper=sender,
                most_voted_keeper_address=sender,
                llm_prompt_templates=["dummy {template}"],
                llm_values=[{"template": "dummy_value"}],
                write_data=[{"text": "dummy_text", "credentials": {}}],
            ),
        )

        test_round = self._round_class(
            synchronized_data=self.synchronized_data,
        )

        self._complete_run(
            self._test_round(
                test_round=test_round,
                keeper_payloads=TwitterWritePayload(
                    sender=sender,
                    content=payload_str,
                ),
                synchronized_data_update_fn=lambda _synchronized_data, _: _synchronized_data.update(
                    keeper=sender,
                ),
                synchronized_data_attr_checks=[],
                exit_event=exit_event,
            )
        )
