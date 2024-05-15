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

"""This package contains payload tests for the GenericScoringAbciApp."""

from dataclasses import dataclass
from typing import Hashable

import pytest

from packages.valory.skills.generic_scoring_abci.payloads import (
    BaseTxPayload,
    GenericScoringPayload,
)


@dataclass
class PayloadTestCase:
    """PayloadTestCase"""

    name: str
    payload_cls: BaseTxPayload
    content: Hashable


@pytest.mark.parametrize(
    "test_case",
    [
        PayloadTestCase(
            name="Happy path",
            payload_cls=GenericScoringPayload,
            content="payload_test_content",
        ),
        PayloadTestCase(
            name="Payload incorrect data type",
            payload_cls=GenericScoringPayload,
            content=12345,
        ),
    ],
)
def test_payloads(test_case: PayloadTestCase) -> None:
    """Tests for TwitterScoringAbciApp payloads"""

    payload = test_case.payload_cls(
        sender="sender",
        content=test_case.content,
    )

    assert payload.sender == "sender"
    assert payload.content == test_case.content

    if test_case.name == "Payload incorrect data type":
        with pytest.raises(TypeError):
            payload.data()
    else:
        assert payload.from_json(payload.json) == payload
