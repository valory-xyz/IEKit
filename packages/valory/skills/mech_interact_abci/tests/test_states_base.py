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
"""This module contains the tests for the state/base of the mech interact abci app."""

from typing import Mapping
from unittest.mock import MagicMock

from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.mech_interact_abci.payloads import (
    MechRequestPayload,
    MechResponsePayload,
)
from packages.valory.skills.mech_interact_abci.states.base import (
    Event,
    MechInteractionResponse,
    MechInteractionRound,
    MechMetadata,
    MechRequest,
    SynchronizedData,
)


class TestEvent:
    """Test the Event class of MechInteract."""

    def test_import(self) -> None:
        """Test import."""
        assert Event.DONE.value == "done"
        assert Event.NO_MAJORITY.value == "no_majority"
        assert Event.ROUND_TIMEOUT.value == "round_timeout"
        assert Event.SKIP_REQUEST.value == "skip_request"


class TestMechMetaData:
    """Test the MechMetaData of MechInteract."""

    def test_initialization(self) -> None:
        """Test initialization."""
        MechMetadata(prompt="dummy_prompt", tool="dummy_tool", nonce="dummy_nonce")


class TestMechRequest:
    """Test MechRequest of MechInteract."""

    def test_initialization(self) -> None:
        """Test Initialization."""
        MechRequest()


class TestMechInteractionResponse:
    """Test MechInteractionResponse of MechInteract."""

    def test_initialization(self) -> None:
        """Test initialization."""
        MechInteractionResponse()

    def test_retries_exceeded(self) -> None:
        """Test retries exceeded."""
        mech_interact_response = MechInteractionResponse()
        mech_interact_response.retries_exceeded()
        assert (
            mech_interact_response.error
            == "Retries were exceeded while trying to get the mech's response."
        )

    def test_incorrect_format(self) -> None:
        """Test incorrect format."""
        mech_interact_response = MechInteractionResponse()
        mech_interact_response.incorrect_format("dummy_res")
        print(mech_interact_response.error)
        assert (
            mech_interact_response.error
            == "The response's format was unexpected: dummy_res"
        )


class TestSynchronizedData:
    """Test SynchronizedData of Base States of MechInteract."""

    def setup(self) -> None:
        """Set up the tests."""
        self.synchronized_data = SynchronizedData(
            db=AbciAppDB(setup_data=dict(participants=[]))
        )
        self.synchronized_data.update(**dict(mech_price=1))
        self.synchronized_data.update(
            **dict(
                mech_requests='[{"prompt": "dummy_prompt_1", "tool": "dummy_tool_1", "nonce": "dummy_nonce_1"}, {"prompt": "dummy_prompt_2", "tool": "dummy_tool_2", "nonce": "dummy_nonce_2"}]'
            )
        )
        self.synchronized_data.update(
            **dict(
                mech_responses=[{"nonce": "dummy_nonce_1", "result": "dummy_result_1"}]
            )
        )
        self.synchronized_data.update(
            **dict(
                participant_to_requests={
                    "dummy_sender": {
                        "round_count": -1,
                        "id_": "dummy_id",
                        "tx_submitter": "dummy_tx_submitter",
                        "tx_hash": "dummy_tx_hash",
                        "price": 1,
                        "mech_requests": "dummy_mech_requests",
                        "mech_responses": "dummy_mech_responses",
                        "sender": "dummy_sender",
                        "chain_id": 1,
                        "_metaclass_registry_key": "packages.valory.skills.mech_interact_abci.payloads.MechRequestPayload",
                    }
                }
            )
        )
        self.synchronized_data.update(
            **dict(
                participant_to_responses={
                    "dummy_sender": {
                        "round_count": -1,
                        "id_": "dummy_id",
                        "sender": "dummy_sender",
                        "mech_responses": "dummy_mech_responses",
                        "_metaclass_registry_key": "packages.valory.skills.mech_interact_abci.payloads.MechResponsePayload",
                    }
                }
            )
        )
        self.synchronized_data.update(**dict(final_tx_hash="dummy_tx_hash"))
        self.synchronized_data.update(**dict(chain_id="dummy_chain_id"))
        self.synchronized_data.update(**dict(tx_submitter=1))

    def test_initialization(self) -> None:
        """Test initialization."""
        assert isinstance(self.synchronized_data, SynchronizedData)

    def test_mech_price(self) -> None:
        """Test mech price."""
        assert self.synchronized_data.mech_price == 1

    def test_mech_requests(self) -> None:
        """Test mech requests."""
        assert self.synchronized_data.mech_requests == [
            MechMetadata(
                prompt="dummy_prompt_1", tool="dummy_tool_1", nonce="dummy_nonce_1"
            ),
            MechMetadata(
                prompt="dummy_prompt_2", tool="dummy_tool_2", nonce="dummy_nonce_2"
            ),
        ]

    def test_mech_responses(self) -> None:
        """Test mech responses."""
        assert self.synchronized_data.mech_responses == [
            MechInteractionResponse(
                data="",
                requestId=0,
                nonce="dummy_nonce_1",
                result="dummy_result_1",
                error="Unknown",
            )
        ]

    def test_participant_to_requests(self) -> None:
        """Test participant to requests."""
        assert isinstance(self.synchronized_data.participant_to_requests, Mapping)
        for key, value in self.synchronized_data.participant_to_requests.items():
            assert isinstance(key, str)
            assert isinstance(value, MechRequestPayload)

    def test_participant_to_responses(self) -> None:
        """Test participant to responses."""
        assert isinstance(self.synchronized_data.participant_to_responses, Mapping)
        for key, value in self.synchronized_data.participant_to_responses.items():
            assert isinstance(key, str)
            assert isinstance(value, MechResponsePayload)

    def test_final_tx_hash(self) -> None:
        """Test final tx hash."""
        assert self.synchronized_data.final_tx_hash == "dummy_tx_hash"

    def test_chain_id(self) -> None:
        """Test chain id."""
        assert self.synchronized_data.chain_id == "dummy_chain_id"

    def test_tx_submitter(self) -> None:
        """Test tx submitter."""
        assert self.synchronized_data.tx_submitter == "1"


class TestMechInteractionRound:
    """Test MechInteractionRound of MechInteract."""

    def test_initialization(self) -> None:
        """Test initialization."""
        MechInteractionRound(synchronized_data=MagicMock(), context=MagicMock())
