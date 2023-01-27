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

"""This package contains payload tests for the ScoreWriteAbciApp."""

from dataclasses import dataclass
from typing import Hashable, Type

import pytest

from packages.valory.skills.score_write_abci.payloads import (
    BaseScoreWritePayload,
    CeramicWritePayload,
    RandomnessPayload,
    SelectKeeperPayload,
    TransactionType,
    VerificationPayload,
)


@dataclass
class PayloadTestCase:
    """PayloadTestCase"""

    payload_cls: Type[BaseScoreWritePayload]
    content: Hashable
    transaction_type: TransactionType


def test_randomness_payload() -> None:
    """Test `RandomnessPayload`."""

    payload = RandomnessPayload(sender="sender", round_id=1, randomness="test")

    assert payload.round_id == 1
    assert payload.randomness == "test"
    assert payload.data == {"round_id": 1, "randomness": "test"}
    assert payload.transaction_type == TransactionType.RANDOMNESS


def test_select_keeper_payload() -> None:
    """Test `SelectKeeperPayload`."""

    payload = SelectKeeperPayload(sender="sender", keeper="test")

    assert payload.keeper == "test"
    assert payload.data == {"keepers": "test"}
    assert payload.transaction_type == TransactionType.SELECT_KEEPER


@pytest.mark.parametrize(
    "test_case",
    [
        PayloadTestCase(
            payload_cls=CeramicWritePayload,
            content="payload_test_content",
            transaction_type=TransactionType.CERAMIC_WRITE,
        ),
        PayloadTestCase(
            payload_cls=VerificationPayload,
            content="payload_test_content",
            transaction_type=TransactionType.VERIFICATION,
        ),
    ],
)
def test_payloads(test_case: PayloadTestCase) -> None:
    """Tests for ScoreWriteAbciApp payloads"""

    payload = test_case.payload_cls(
        sender="sender",
        content=test_case.content,
    )
    assert payload.sender == "sender"
    assert payload.content == test_case.content
    assert payload.transaction_type == test_case.transaction_type
    assert payload.from_json(payload.json) == payload
