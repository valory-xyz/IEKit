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

"""This package contains round behaviours of DynamicNFTAbciApp."""

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Type, cast

import pytest

from packages.valory.contracts.dynamic_contribution.contract import (
    DynamicContributionContract,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.protocols.contract_api.custom_types import State
from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.abstract_round_abci.behaviours import (
    make_degenerate_behaviour,
)
from packages.valory.skills.abstract_round_abci.test_tools.base import (
    FSMBehaviourBaseCase,
)
from packages.valory.skills.dynamic_nft_abci.behaviours import (
    DEFAULT_POINTS,
    DynamicNFTBaseBehaviour,
    TokenTrackBehaviour,
)
from packages.valory.skills.dynamic_nft_abci.models import SharedState
from packages.valory.skills.dynamic_nft_abci.rounds import (
    Event,
    FinishedTokenTrackWriteRound,
    SynchronizedData,
    TokenTrackRound,
)


DYNAMIC_CONTRIBUTION_CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"

DUMMY_ADDRESSES = [
    "0x54EfA9b1865FFE8c528fb375A7A606149598932A",
    "0x3c03a080638b3c176aB7D9ed56E25bC416dFf525",
    "0x44704AE66f0B9FF08a7b0584B49FE941AdD1bAE7",
    "0x7B394CD0B75f774c6808cc681b26aC3E5DF96E27",
]

DUMMY_CERAMIC_DB = {
    "users": [
        {
            "wallet_address": address,
            "token_id": None,
            "points": DEFAULT_POINTS,
        }
        for address in DUMMY_ADDRESSES
    ],
    "module_data": {"dynamic_nft": {}},
}

DUMMY_TOKEN_ID_TO_ADDRESS = {i: member for i, member in enumerate(DUMMY_ADDRESSES)}
# Add an extra token for the first address
DUMMY_TOKEN_ID_TO_ADDRESS[100] = "0x54EfA9b1865FFE8c528fb375A7A606149598932A"


@dataclass
class BehaviourTestCase:
    """BehaviourTestCase"""

    name: str
    initial_data: Dict[str, Any]
    event: Event
    next_behaviour_class: Optional[Type[DynamicNFTBaseBehaviour]] = None


class BaseDynamicNFTTest(FSMBehaviourBaseCase):
    """Base test case."""

    path_to_skill = Path(__file__).parent.parent

    behaviour: DynamicNFTBaseBehaviour  # type: ignore
    behaviour_class: Type[DynamicNFTBaseBehaviour]
    next_behaviour_class: Type[DynamicNFTBaseBehaviour]
    synchronized_data: SynchronizedData
    done_event = Event.WRITE

    def fast_forward(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Fast-forward on initialization"""

        data = data if data is not None else {}
        self.fast_forward_to_behaviour(
            self.behaviour,  # type: ignore
            self.behaviour_class.auto_behaviour_id(),
            SynchronizedData(AbciAppDB(setup_data=AbciAppDB.data_to_lists(data))),
        )
        assert (
            self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
            == self.behaviour_class.auto_behaviour_id()
        )

    def complete(self, event: Event) -> None:
        """Complete test"""

        self.behaviour.act_wrapper()
        self.mock_a2a_transaction()
        self._test_done_flag_set()
        self.end_round(done_event=event)
        assert (
            self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
            == self.next_behaviour_class.auto_behaviour_id()
        )


class TestTokenTrackBehaviour(BaseDynamicNFTTest):
    """Tests TokenTrackBehaviour"""

    behaviour_class = TokenTrackBehaviour
    next_behaviour_class = make_degenerate_behaviour(  # type: ignore
        FinishedTokenTrackWriteRound
    )

    def _mock_dynamic_contribution_contract_request(
        self,
        response_body: Dict,
        response_performative: ContractApiMessage.Performative,
    ) -> None:
        """Mock the WeightedPoolContract."""
        self.mock_contract_api_request(
            contract_id=str(DynamicContributionContract.contract_id),
            request_kwargs=dict(
                performative=ContractApiMessage.Performative.GET_STATE,
                contract_address=DYNAMIC_CONTRIBUTION_CONTRACT_ADDRESS,
            ),
            response_kwargs=dict(
                performative=response_performative,
                state=State(
                    ledger_id="ethereum",
                    body=response_body,
                ),
            ),
        )

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(ceramic_db=DUMMY_CERAMIC_DB),
                    event=Event.WRITE,
                ),
                {
                    "mock_response_data": dict(
                        token_id_to_member=DUMMY_TOKEN_ID_TO_ADDRESS,
                        last_block=100,
                    ),
                    "mock_response_performative": ContractApiMessage.Performative.STATE,
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        time_in_future = datetime.datetime.now() + datetime.timedelta(hours=10)
        state = cast(SharedState, self._skill.skill_context.state)
        state.round_sequence._last_round_transition_timestamp = time_in_future
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self._mock_dynamic_contribution_contract_request(
            response_body=kwargs.get("mock_response_data"),
            response_performative=kwargs.get("mock_response_performative"),
        )
        self.complete(test_case.event)


class TestTokenTrackBehaviourContractError(TestTokenTrackBehaviour):
    """Tests TokenTrackBehaviour"""

    behaviour_class = TokenTrackBehaviour
    next_behaviour_class = TokenTrackBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Contract error",
                    initial_data=dict(ceramic_db=DUMMY_CERAMIC_DB),
                    event=Event.CONTRACT_ERROR,
                ),
                {
                    "mock_response_data": dict(
                        member_to_token_id=TokenTrackRound.ERROR_PAYLOAD
                    ),
                    "mock_response_performative": ContractApiMessage.Performative.ERROR,
                },
            )
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self._mock_dynamic_contribution_contract_request(
            response_body=kwargs.get("mock_response_data"),
            response_performative=kwargs.get("mock_response_performative"),
        )
        self.complete(test_case.event)
