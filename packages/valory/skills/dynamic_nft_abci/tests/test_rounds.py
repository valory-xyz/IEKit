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

"""This package contains the tests for rounds of DynamicNFTAbciApp."""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, Hashable, List, Mapping, Optional

import pytest

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload
from packages.valory.skills.abstract_round_abci.test_tools.rounds import (
    BaseCollectSameUntilThresholdRoundTest,
)
from packages.valory.skills.dynamic_nft_abci.behaviours import DEFAULT_POINTS
from packages.valory.skills.dynamic_nft_abci.payloads import TokenTrackPayload
from packages.valory.skills.dynamic_nft_abci.rounds import (
    Event,
    SynchronizedData,
    TokenTrackRound,
)


DUMMY_CERAMIC_DB = {
    "users": [
        {
            "wallet_address": "0x54EfA9b1865FFE8c528fb375A7A606149598932A",
            "points": DEFAULT_POINTS,
        },
        {
            "wallet_address": "0x3c03a080638b3c176aB7D9ed56E25bC416dFf525",
            "points": DEFAULT_POINTS,
        },
        {
            "wallet_address": "0x44704AE66f0B9FF08a7b0584B49FE941AdD1bAE7",
            "points": DEFAULT_POINTS,
        },
        {
            "wallet_address": "0x19B043aD06C48aeCb2028B0f10503422BD0E0918",
            "points": DEFAULT_POINTS,
        },
        {
            "wallet_address": "0x8325c5e4a56E352355c590E4A43420840F067F98",
            "points": DEFAULT_POINTS,
        },
    ],
    "modules": {"dynamic_nft": {}},
}

DUMMY_TOKEN_ID_TO_POINTS = {
    "1": 100,
    "2": 200,
    "3": 300,
}


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


def get_dummy_token_track_payload_serialized() -> str:
    """Dummy new tokens payload"""
    return json.dumps(
        {
            "ceramic_db": DUMMY_CERAMIC_DB,
            "token_id_to_points": DUMMY_TOKEN_ID_TO_POINTS,
            "last_update_time": "dymmy_last_update_time",
            "pending_write": True,
        },
        sort_keys=True,
    )


def get_dummy_token_track_payload_error_serialized() -> str:
    """Dummy new tokens payload"""
    return json.dumps({"error": True}, sort_keys=True)


@dataclass
class RoundTestCase:
    """RoundTestCase"""

    name: str
    initial_data: Dict[str, Hashable]
    payloads: Mapping[str, BaseTxPayload]
    final_data: Dict[str, Hashable]
    event: Event
    most_voted_payload: Any
    synchronized_data_attr_checks: List[Callable] = field(default_factory=list)


MAX_PARTICIPANTS: int = 4


class BaseDynamicNFTRoundTestClass(BaseCollectSameUntilThresholdRoundTest):
    """Base test class for DynamicNFT rounds."""

    synchronized_data: SynchronizedData
    _synchronized_data_class = SynchronizedData
    _event_class = Event

    def run_test(self, test_case: RoundTestCase, **kwargs: Any) -> None:
        """Run the test"""

        self.synchronized_data.update(**test_case.initial_data)

        test_round = self.round_class(
            synchronized_data=self.synchronized_data,
        )

        self._complete_run(
            self._test_round(
                test_round=test_round,
                round_payloads=test_case.payloads,
                synchronized_data_update_fn=lambda sync_data, _: sync_data.update(
                    **test_case.final_data
                ),
                synchronized_data_attr_checks=test_case.synchronized_data_attr_checks,
                most_voted_payload=test_case.most_voted_payload,
                exit_event=test_case.event,
            )
        )


class TestTokenTrackRound(BaseDynamicNFTRoundTestClass):
    """Tests for TokenTrackRound."""

    round_class = TokenTrackRound

    @pytest.mark.parametrize(
        "test_case",
        (
            RoundTestCase(
                name="Happy path",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=TokenTrackPayload,
                    data=get_dummy_token_track_payload_serialized(),
                ),
                final_data={
                    "token_id_to_points": json.loads(
                        get_dummy_token_track_payload_serialized()
                    )["token_id_to_points"],
                    "ceramic_db": json.loads(
                        get_dummy_token_track_payload_serialized()
                    )["ceramic_db"],
                    "last_update_time": json.loads(
                        get_dummy_token_track_payload_serialized()
                    )["last_update_time"],
                },
                event=Event.WRITE,
                most_voted_payload=get_dummy_token_track_payload_serialized(),
                synchronized_data_attr_checks=[
                    lambda _synchronized_data: _synchronized_data.token_id_to_points,
                    lambda _synchronized_data: _synchronized_data.ceramic_db,
                    lambda _synchronized_data: _synchronized_data.last_update_time,
                ],
            ),
            RoundTestCase(
                name="Contract error",
                initial_data={},
                payloads=get_payloads(
                    payload_cls=TokenTrackPayload,
                    data=get_dummy_token_track_payload_error_serialized(),
                ),
                final_data={},
                event=Event.CONTRACT_ERROR,
                most_voted_payload=get_dummy_token_track_payload_error_serialized(),
                synchronized_data_attr_checks=[],
            ),
        ),
    )
    def test_run(self, test_case: RoundTestCase) -> None:
        """Run tests."""
        self.run_test(test_case)
