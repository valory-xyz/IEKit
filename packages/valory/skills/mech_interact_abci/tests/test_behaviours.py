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

"""This package contains round behaviours of MechInteractAbciApp."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Hashable, Optional, Type, cast
from unittest import mock
from unittest.mock import MagicMock

import pytest

from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.abstract_round_abci.behaviour_utils import (
    make_degenerate_behaviour,
)
from packages.valory.skills.abstract_round_abci.behaviours import BaseBehaviour
from packages.valory.skills.abstract_round_abci.test_tools.base import (
    FSMBehaviourBaseCase,
)
from packages.valory.skills.abstract_round_abci.tests.test_common import dummy_generator
from packages.valory.skills.mech_interact_abci.behaviours.base import (
    MechInteractBaseBehaviour,
)
from packages.valory.skills.mech_interact_abci.behaviours.request import (
    MechRequestBehaviour,
)
from packages.valory.skills.mech_interact_abci.behaviours.response import (
    MechResponseBehaviour,
)
from packages.valory.skills.mech_interact_abci.behaviours.round_behaviour import (
    MechInteractRoundBehaviour,
)
from packages.valory.skills.mech_interact_abci.models import SharedState
from packages.valory.skills.mech_interact_abci.states.base import (
    Event,
    SynchronizedData,
)
from packages.valory.skills.mech_interact_abci.states.final_states import (
    FinishedMechRequestRound,
)


@dataclass
class BehaviourTestCase:
    """BehaviourTestCase"""

    name: str
    initial_data: Dict[str, Hashable]
    event: Event
    return_value: Any
    kwargs: Dict[str, Any] = field(default_factory=dict)


class BaseMechInteractTest(FSMBehaviourBaseCase):
    """Base test case."""

    path_to_skill = Path(__file__).parent.parent

    behaviour: MechInteractRoundBehaviour
    behaviour_class: Type[MechInteractBaseBehaviour]
    next_behaviour_class: Type[MechInteractBaseBehaviour]
    synchronized_data: SynchronizedData
    done_event = Event.DONE

    @property
    def current_behaviour_id(self) -> str:
        """Current RoundBehaviour's behaviour id"""

        return self.behaviour.current_behaviour.behaviour_id

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


class TestMechRequestBehaviour(BaseMechInteractTest):
    """Tests MechRequestBehaviour"""

    behaviour_class: Type[BaseBehaviour] = MechRequestBehaviour
    next_behaviour_class: Type[BaseBehaviour] = make_degenerate_behaviour(
        FinishedMechRequestRound
    )

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path - no mech request",
                    initial_data=dict(mech_requests=[]),
                    event=Event.DONE,
                    return_value={
                        "ledger": None,
                        "contract": None,
                        "metadata_hash": None,
                        "multisend_safe_tx_hash": None,
                    },
                ),
                {},
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        mech_requests='[{"prompt": "dummy_prompt_1", "tool": "dummy_tool_1", "nonce": "dummy_nonce_1"}, {"prompt": "dummy_prompt_2", "tool": "dummy_tool_2", "nonce": "dummy_nonce_2"}]',
                        safe_contract_address="mock_safe_contract_address",
                    ),
                    event=Event.DONE,
                    return_value={
                        "ledger": MagicMock(
                            state=MagicMock(body={"get_balance_result": "10"})
                        ),
                        "contract": MagicMock(
                            performative=ContractApiMessage.Performative.RAW_TRANSACTION,
                            raw_transaction=MagicMock(
                                body={
                                    "token": 10,
                                    "wallet": "mock_safe_contract_address",
                                    "data": "0x0000deadbeef0000",
                                    "request_data": "dummy_request_data",
                                }
                            ),
                        ),
                        "metadata_hash": "QmTzQ1iVRmDDeh8aW5HX99o9dsPwzUo9tb5w1DLT8PaJfM",
                        "multisend_safe_tx_hash": MagicMock(
                            performative=ContractApiMessage.Performative.STATE,
                            state=MagicMock(
                                body={
                                    "tx_hash": "0x0000000000000000000000000000000000000000000000000000000000000000"
                                }
                            ),
                        ),
                    },
                ),
                {},
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs) -> None:
        """Run tests."""
        with mock.patch.object(
            MechRequestBehaviour,
            "get_ledger_api_response",
            dummy_generator(test_case.return_value["ledger"]),
        ), mock.patch.object(
            MechRequestBehaviour,
            "get_contract_api_response",
            dummy_generator(test_case.return_value["contract"]),
        ), mock.patch.object(
            MechRequestBehaviour,
            "send_to_ipfs",
            dummy_generator(test_case.return_value["metadata_hash"]),
        ):
            params = cast(SharedState, self._skill.skill_context.params)
            params.__dict__["_frozen"] = False
            params.mech_request_price = 1
            params.mech_contract_address = "dummy_mech_contract_address"
            self.fast_forward(test_case.initial_data)
            self.behaviour.act_wrapper()
            self.behaviour.act_wrapper()
            self.behaviour.act_wrapper()
            self.behaviour.act_wrapper()
            self.behaviour.act_wrapper()
            self.behaviour.act_wrapper()
            self.behaviour.act_wrapper()

            with mock.patch.object(
                MechRequestBehaviour,
                "get_contract_api_response",
                dummy_generator(test_case.return_value["multisend_safe_tx_hash"]),
            ):
                self.behaviour.act_wrapper()
                self.complete(test_case.event)


class TestMechResponseBehaviour(BaseMechInteractTest):
    """Tests MechResponseBehaviour"""

    # TODO: set next_behaviour_class
    behaviour_class: Type[BaseBehaviour] = MechResponseBehaviour
    next_behaviour_class: Type[BaseBehaviour] = ...

    # TODO: provide test cases
    @pytest.mark.parametrize("test_case", [])
    def test_run(self, test_case: BehaviourTestCase) -> None:
        """Run tests."""

        self.fast_forward(test_case.initial_data)
        # TODO: mock the necessary calls
        # self.mock_ ...
        self.complete(test_case.event)
