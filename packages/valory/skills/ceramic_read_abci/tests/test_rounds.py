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

"""This package contains the tests for rounds of CeramicRead."""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Hashable, List, Mapping, Optional, cast

import pytest

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload
from packages.valory.skills.abstract_round_abci.test_tools.rounds import (
    BaseCollectSameUntilThresholdRoundTest,
    CollectSameUntilThresholdRound,
)
from packages.valory.skills.ceramic_read_abci.payloads import StreamReadPayload
from packages.valory.skills.ceramic_read_abci.rounds import (
    Event,
    StreamReadRound,
    SynchronizedData,
)


MAX_PARTICIPANTS: int = 4


def get_participants() -> List[str]:
    """Participants"""
    return [f"agent_{i}" for i in range(MAX_PARTICIPANTS)]


def get_payloads(
    payload_cls: BaseTxPayload,
    data: Optional[str],
) -> Mapping[str, BaseTxPayload]:
    """Get payloads."""
    return {
        participant: payload_cls(participant, data)
        for participant in get_participants()
    }


def get_dummy_ceramic_read_payload_serialized(api_error: bool = False) -> str:
    """Dummy ceramic write payload"""
    if api_error:
        payload = {"error": "true"}
    else:
        payload = {
            "stream_data": {"dummy": "data"},
            "read_target_property": "dummy_property_name",
        }
    return json.dumps(payload, sort_keys=True)


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


class BaseCeramicReadRoundTest(BaseCollectSameUntilThresholdRoundTest):
    """Base test class for CeramicRead rounds."""

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


class TestStreamReadRound(BaseCeramicReadRoundTest):
    """Tests for StreamReadRound."""

    round_class = StreamReadRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=StreamReadPayload,
                    data=get_dummy_ceramic_read_payload_serialized(),
                ),
                final_data={
                    "most_voted_api_data": get_dummy_ceramic_read_payload_serialized(),
                },
                event=Event.DONE,
                most_voted_payload=get_dummy_ceramic_read_payload_serialized(),
                synchronized_data_attr_checks=[],
            ),
            RoundTestCase(
                name="API error",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=StreamReadPayload,
                    data=get_dummy_ceramic_read_payload_serialized(api_error=True),
                ),
                final_data={},
                event=Event.API_ERROR,
                most_voted_payload=get_dummy_ceramic_read_payload_serialized(
                    api_error=True
                ),
                synchronized_data_attr_checks=[],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)
