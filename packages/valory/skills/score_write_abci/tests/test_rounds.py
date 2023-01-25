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
    Type,
    cast,
    Deque,
    Union,
)

import pytest

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload
from packages.valory.skills.abstract_round_abci.test_tools.rounds import (
    BaseCollectSameUntilThresholdRoundTest,
    CollectSameUntilThresholdRound,
    BaseOnlyKeeperSendsRoundTest,
)
from packages.valory.skills.score_write_abci.payloads import (
    BaseScoreWritePayload,
    RandomnessPayload,
    SelectKeeperPayload,
    CeramicWritePayload,
    VerificationPayload
)
from packages.valory.skills.score_write_abci.rounds import (
    AbstractRound,
    Event,
    SynchronizedData,
    SelectKeeperRound,
    CeramicWriteRound,
    VerificationRound,
)
from collections import deque


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


MAX_PARTICIPANTS: int = 4


def get_participants() -> FrozenSet[str]:
    """Participants"""
    return frozenset([f"agent_{i}" for i in range(MAX_PARTICIPANTS)])


def get_payloads(
    payload_cls: Union[Type[BaseScoreWritePayload], Type[SelectKeeperPayload]],
    data: Optional[str],
) -> Mapping[str, BaseTxPayload]:
    """Get payloads."""
    return {
        participant: payload_cls(participant, data)
        for participant in get_participants()
    }


def get_dummy_ceramic_write_payload_serialized(api_error: bool = False) -> str:
    """Dummy twitter observation payload"""
    if api_error:
        return "{}"
    return '{"success": true}'


def get_dummy_select_keeper_payload(error: bool = False) -> str:
    """Dummy twitter observation payload"""
    if error:
        return ""
    return int(1).to_bytes(32, "big").hex() + "new_keeper" + "-" * 32


class BaseScoreWriteRoundTest(BaseCollectSameUntilThresholdRoundTest):
    """Base test class for ScoreWrite rounds."""

    round_class: Type[AbstractRound]
    synchronized_data: SynchronizedData
    _synchronized_data_class = SynchronizedData
    _event_class = Event

    def run_test(self, test_case: RoundTestCase) -> None:
        """Run the test"""

        self.synchronized_data.update(**test_case.initial_data)

        test_round = self.round_class(
            synchronized_data=self.synchronized_data,
            consensus_params=self.consensus_params,
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

class TestSelectKeeperRound(BaseScoreWriteRoundTest):
    """Tests for SelectKeeperRound."""

    round_class = SelectKeeperRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=SelectKeeperPayload,
                    data=get_dummy_select_keeper_payload(),
                ),
                final_data={
                    "most_voted_api_data": get_dummy_select_keeper_payload()
                },
                event=Event.DONE,
                most_voted_payload=get_dummy_select_keeper_payload(),
                synchronized_data_attr_checks=[],
            ),
            RoundTestCase(
                name="API error",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=SelectKeeperPayload,
                    data=get_dummy_select_keeper_payload(
                        error=True
                    ),
                ),
                final_data={},
                event=Event.INCORRECT_SERIALIZATION,
                most_voted_payload=get_dummy_select_keeper_payload(
                    error=True
                ),
                synchronized_data_attr_checks=[],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)


class TestVerificationRound(BaseScoreWriteRoundTest):
    """Tests for VerificationRound."""

    round_class = VerificationRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=VerificationPayload,
                    data=get_dummy_ceramic_write_payload_serialized(),
                ),
                final_data={
                    "most_voted_api_data": json.loads(
                        get_dummy_ceramic_write_payload_serialized()
                    ),
                },
                event=Event.DONE,
                most_voted_payload=get_dummy_ceramic_write_payload_serialized(),
                synchronized_data_attr_checks=[],
            ),
            RoundTestCase(
                name="API error",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=VerificationPayload,
                    data=get_dummy_ceramic_write_payload_serialized(
                        api_error=True
                    ),
                ),
                final_data={},
                event=Event.API_ERROR,
                most_voted_payload=get_dummy_ceramic_write_payload_serialized(
                    api_error=True
                ),
                synchronized_data_attr_checks=[],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)


def get_keepers(keepers: Deque[str], retries: int = 1) -> str:
    """Get dummy keepers."""
    return retries.to_bytes(32, "big").hex() + "".join(keepers)


class TestCeramicWriteRound(BaseOnlyKeeperSendsRoundTest):
    """Test CeramicWriteRound."""

    _synchronized_data_class = SynchronizedData
    _event_class = Event
    _round_class = CeramicWriteRound

    @pytest.mark.parametrize(
        "payload_str, exit_event",
        (
            (
                CeramicWriteRound.ERROR_PAYLOAD,
                Event.API_ERROR,
            ),
            (
                CeramicWriteRound.SUCCCESS_PAYLOAD,
                Event.DONE,
            ),
        ),
    )
    def test_round(
        self,
        payload_str: str,
        exit_event: Event,
    ) -> None:
        """Runs tests."""
        keeper_retries = 2
        blacklisted_keepers = ""
        self.participants = frozenset([f"agent_{i}" + "-" * 35 for i in range(4)])
        keepers = deque(("agent_1" + "-" * 35, "agent_3" + "-" * 35))
        self.synchronized_data = cast(
            SynchronizedData,
            self.synchronized_data.update(
                participants=frozenset([f"agent_{i}" + "-" * 35 for i in range(4)]),
                keepers=get_keepers(keepers, keeper_retries),
                blacklisted_keepers=blacklisted_keepers,
            ),
        )

        sender = keepers[0]

        test_round = self._round_class(
            synchronized_data=self.synchronized_data,
            consensus_params=self.consensus_params,
        )

        self._complete_run(
            self._test_round(
                test_round=test_round,
                keeper_payloads=CeramicWritePayload(
                    sender=sender,
                    content=payload_str,
                ),
                synchronized_data_update_fn=lambda _synchronized_data, _: _synchronized_data.update(
                    blacklisted_keepers=blacklisted_keepers,
                    keepers=get_keepers(keepers, keeper_retries),
                    keeper_retries=keeper_retries,
                ),
                synchronized_data_attr_checks=[],
                exit_event=exit_event,
            )
        )