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

"""This package contains the tests for rounds of ProposalCollector."""

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
    BaseTxPayload,
    CollectSameUntilThresholdRound,
)
from packages.valory.skills.abstract_round_abci.test_tools.rounds import (
    BaseCollectSameUntilThresholdRoundTest,
)
from packages.valory.skills.decision_making_abci.payloads import DecisionMakingPayload
from packages.valory.skills.decision_making_abci.rounds import (
    DecisionMakingRound,
    Event,
    SynchronizedData,
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


def get_dummy_decision_making_payload_serialized():
    """Dummy payload"""
    return json.dumps(
        {"updates": {"dummy_key": "dummy_value"}, "event": Event.DONE.value},
        sort_keys=True,
    )


class TestSynchronizeDelegationsRoundTest(BaseCollectSameUntilThresholdRoundTest):
    """Base test class for ProposalCollector rounds."""

    synchronized_data: SynchronizedData
    _synchronized_data_class = SynchronizedData
    _event_class = Event
    round_class = DecisionMakingRound

    def run_test(self, test_case: RoundTestCase) -> None:
        """Run the test"""

        self.synchronized_data.update(**test_case.initial_data)

        test_round = self.round_class(
            synchronized_data=self.synchronized_data, context=mock.MagicMock()
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

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path - no new delegations",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=DecisionMakingPayload,
                    data=get_dummy_decision_making_payload_serialized(),
                ),
                final_data={
                    "dummy_key": "dummy_value",
                    "previous_decision_event": "done",
                },
                event=Event.DONE,
                most_voted_payload=get_dummy_decision_making_payload_serialized(),
                synchronized_data_attr_checks=[
                    lambda _synchronized_data: _synchronized_data.previous_decision_event,
                ],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)
