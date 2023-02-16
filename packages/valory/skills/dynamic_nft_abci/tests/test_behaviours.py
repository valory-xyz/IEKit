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
    NewTokensBehaviour,
)
from packages.valory.skills.dynamic_nft_abci.models import SharedState
from packages.valory.skills.dynamic_nft_abci.rounds import (
    Event,
    FinishedNewTokensRound,
    NewTokensRound,
    SynchronizedData,
)


DYNAMIC_CONTRIBUTION_CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"

DUMMY_TOKEN_TO_DATA = {
    "1": {
        "address": "0x54EfA9b1865FFE8c528fb375A7A606149598932A",
        "points": DEFAULT_POINTS,
    },
    "2": {
        "address": "0x3c03a080638b3c176aB7D9ed56E25bC416dFf525",
        "points": DEFAULT_POINTS,
    },
    "3": {
        "address": "0x44704AE66f0B9FF08a7b0584B49FE941AdD1bAE7",
        "points": DEFAULT_POINTS,
    },
    "4": {
        "address": "0x19B043aD06C48aeCb2028B0f10503422BD0E0918",
        "points": DEFAULT_POINTS,
    },
    "5": {
        "address": "0x8325c5e4a56E352355c590E4A43420840F067F98",
        "points": DEFAULT_POINTS,
    },
    "6": {
        "address": "0x54EfA9b1865FFE8c528fb375A7A606149598932A",
        "points": DEFAULT_POINTS,
    },
}


DUMMY_ADDRESSES = [
    "0x54EfA9b1865FFE8c528fb375A7A606149598932A",
    "0x3c03a080638b3c176aB7D9ed56E25bC416dFf525",
    "0x44704AE66f0B9FF08a7b0584B49FE941AdD1bAE7",
    "0x7B394CD0B75f774c6808cc681b26aC3E5DF96E27",
    "0x54EfA9b1865FFE8c528fb375A7A606149598932A",  # addresses are repeated
    "0x3c03a080638b3c176aB7D9ed56E25bC416dFf525",
    "0x44704AE66f0B9FF08a7b0584B49FE941AdD1bAE7",
    "0x7B394CD0B75f774c6808cc681b26aC3E5DF96E27",
]

DUMMY_TOKEN_ID_TO_MEMBER = {i: member for i, member in enumerate(DUMMY_ADDRESSES)}


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
    done_event = Event.DONE

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


class TestNewTokensBehaviour(BaseDynamicNFTTest):
    """Tests NewTokensBehaviour"""

    behaviour_class = NewTokensBehaviour
    next_behaviour_class = make_degenerate_behaviour(  # type: ignore
        FinishedNewTokensRound
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
                    initial_data=dict(
                        token_to_data={
                            "0": {"address": "dummy_address_0", "points": 0},
                            "1": {"address": "dummy_address_1", "points": 0},
                            "2": {"address": "dummy_address_2", "points": 0},
                        },
                        user_to_total_points={
                            "dummy_user_0": 10,
                            "dummy_user_1": 20,
                            "dummy_user_8": 10,
                        },
                        wallet_to_users={
                            "dummy_address": "dummy_user",
                            "dummy_address_0": "dummy_user_0",
                            "dummy_address_8": "dummy_user_8",
                        },
                    ),
                    event=Event.DONE,
                ),
                {
                    "mock_response_data": dict(
                        token_id_to_member=DUMMY_TOKEN_ID_TO_MEMBER,
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


class TestNewTokensBehaviourContractError(TestNewTokensBehaviour):
    """Tests NewTokensBehaviour"""

    behaviour_class = NewTokensBehaviour
    next_behaviour_class = NewTokensBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Contract error",
                    initial_data=dict(),
                    event=Event.CONTRACT_ERROR,
                ),
                {
                    "mock_response_data": dict(
                        member_to_token_id=NewTokensRound.ERROR_PAYLOAD
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
