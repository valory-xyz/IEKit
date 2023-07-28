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

"""This package contains payload tests for the CeramicReadAbciApp."""

from packages.valory.skills.llm_abci.payloads import (
    LLMPayload,
    RandomnessPayload,
    SelectKeeperPayload,
)


def test_randomness() -> None:
    """Tests for payloads"""

    payload = RandomnessPayload(
        sender="sender",
        round_id=1,
        randomness="randomness",
    )
    assert payload.sender == "sender"
    assert payload.round_id == 1
    assert payload.randomness == "randomness"


def test_select_keeper() -> None:
    """Tests for payloads"""

    payload = SelectKeeperPayload(
        sender="sender",
        keeper="keeper",
    )
    assert payload.sender == "sender"
    assert payload.keeper == "keeper"


def test_llm() -> None:
    """Tests for payloads"""

    payload = LLMPayload(
        sender="sender",
        content="content",
    )
    assert payload.sender == "sender"
    assert payload.content == "content"
