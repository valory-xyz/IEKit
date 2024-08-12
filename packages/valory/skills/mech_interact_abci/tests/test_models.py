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

"""Test the models.py module of the MechInteract."""
import pytest
from hexbytes import HexBytes

from packages.valory.skills.abstract_round_abci.test_tools.base import DummyContext
from packages.valory.skills.abstract_round_abci.tests.test_models import (
    BASE_DUMMY_PARAMS,
    BASE_DUMMY_SPECS_CONFIG,
)
from packages.valory.skills.mech_interact_abci.models import (
    MechParams,
    MechResponseSpecs,
    MultisendBatch,
    SharedState,
)


class TestMechResponseSpecs:
    """Test MechResponseSpecs of MechInteract models."""

    def test_initialization(self) -> None:
        """Test initialization."""
        MechResponseSpecs(
            **BASE_DUMMY_SPECS_CONFIG,
            response_key="value",
            response_index=0,
            response_type="float",
            error_key="error",
            error_index=None,
            error_type="str",
            error_data="error text",
        )


class TestSharedState:
    """Test SharedState of MechInteract."""

    def test_initialization(self) -> None:
        """Test initialization."""
        SharedState(name="", skill_context=DummyContext())


class TestMechParams:
    """Test MechParams of MechInteract models."""

    def setup(self) -> None:
        """Set up the tests."""
        self.mech_params = MechParams(
            **BASE_DUMMY_PARAMS,
            multisend_address="dummy_multisend_address",
            multisend_batch_size=1,
            mech_contract_address="dummy_mech_contract_address",
            ipfs_address="dummy_ipfs_address",
            mech_interaction_sleep_time=1,
        )

    def test_initialization(self) -> None:
        """Test initialization"""
        assert isinstance(self.mech_params, MechParams)

    @pytest.mark.parametrize(
        "dummy_ipfs_address", ["dummy_ipfs_address", "dummy_ipfs_address/"]
    )
    def test_ipfs_address(self, dummy_ipfs_address) -> None:
        """Test ipfs address."""
        print(self.mech_params.ipfs_address)
        self.mech_params.__dict__["_frozen"] = False
        self.mech_params._ipfs_address = dummy_ipfs_address
        ipfs_address = self.mech_params.ipfs_address
        assert ipfs_address == "dummy_ipfs_address/"


class TestMultisendBatch:
    """Test MultisendBatch of MechInteract models."""

    def test_initialization(self) -> None:
        """Test initialization."""
        MultisendBatch(
            to="",
            data=HexBytes("0xabcdef1234567890"),
        )
