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

"""This package contains round behaviours of FarcasterWriteAbciApp."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Type, cast

import pytest

from packages.valory.connections.farcaster.connection import (
    PUBLIC_ID as FARCASTER_CONNECTION_PUBLIC_ID,
)
from packages.valory.protocols.srr.message import SrrMessage
from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.abstract_round_abci.behaviour_utils import BaseBehaviour
from packages.valory.skills.abstract_round_abci.behaviours import (
    make_degenerate_behaviour,
)
from packages.valory.skills.abstract_round_abci.test_tools.base import (
    FSMBehaviourBaseCase,
)
from packages.valory.skills.abstract_round_abci.test_tools.common import (
    BaseRandomnessBehaviourTest,
)
from packages.valory.skills.farcaster_write_abci.behaviours import (
    BaseFarcasterWriteBehaviour,
    FarcasterWriteBehaviour,
    FarcasterWriteRoundBehaviour,
    RandomnessFarcasterWriteBehaviour,
    SelectKeeperFarcasterWriteBehaviour,
)
from packages.valory.skills.farcaster_write_abci.rounds import (
    Event,
    FinishedFarcasterWriteRound,
    SynchronizedData,
)


PACKAGE_DIR = Path(__file__).parent.parent


@dataclass
class BehaviourTestCase:
    """BehaviourTestCase"""

    name: str
    initial_data: Dict[str, Any]
    event: Event
    next_behaviour_class: Optional[Type[BaseFarcasterWriteBehaviour]] = None


class BaseFarcasterWriteTest(FSMBehaviourBaseCase):
    """Base test case."""

    path_to_skill = Path(__file__).parent.parent

    behaviour: FarcasterWriteRoundBehaviour
    behaviour_class: Type[BaseFarcasterWriteBehaviour]
    next_behaviour_class: Type[BaseFarcasterWriteBehaviour]
    synchronized_data: SynchronizedData
    done_event = Event.DONE

    @classmethod
    def setup_class(cls, **kwargs: Any) -> None:
        """setup_class"""
        super().setup_class(**kwargs)
        cls.farcaster_handler = cls._skill.skill_context.handlers.farcaster

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

    def complete(self, event: Event, sends: bool = True) -> None:
        """Complete test"""

        self.behaviour.act_wrapper()
        if sends:
            self.mock_a2a_transaction()
        self._test_done_flag_set()
        self.end_round(done_event=event)
        assert (
            self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
            == self.next_behaviour_class.auto_behaviour_id()
        )

    def mock_farcaster_request(self, request_kwargs: Dict, response_kwargs: Dict) -> None:
        """
        Mock request.

        :param request_kwargs: keyword arguments for request check.
        :param response_kwargs: keyword arguments for mock response.
        """

        self.assert_quantity_in_outbox(1)
        actual_farcaster_message = self.get_message_from_outbox()
        assert actual_farcaster_message is not None, "No message in outbox."  # nosec
        has_attributes, error_str = self.message_has_attributes(
            actual_message=actual_farcaster_message,
            message_type=SrrMessage,
            to=str(FARCASTER_CONNECTION_PUBLIC_ID),
            sender=str(self.skill.skill_context.skill_id),
            **request_kwargs,
        )

        assert has_attributes, error_str  # nosec
        incoming_message = self.build_incoming_message(
            message_type=SrrMessage,
            dialogue_reference=(
                actual_farcaster_message.dialogue_reference[0],
                "stub",
            ),
            target=actual_farcaster_message.message_id,
            message_id=-1,
            to=str(self.skill.skill_context.skill_id),
            sender=str(FARCASTER_CONNECTION_PUBLIC_ID),
            **response_kwargs,
        )
        self.farcaster_handler.handle(incoming_message)
        self.behaviour.act_wrapper()


class TestRandomnessBehaviour(BaseRandomnessBehaviourTest):
    """Test randomness in operation."""

    path_to_skill = PACKAGE_DIR

    randomness_behaviour_class = RandomnessFarcasterWriteBehaviour
    next_behaviour_class = SelectKeeperFarcasterWriteBehaviour
    done_event = Event.DONE


class BaseSelectKeeperFarcasterBehaviourTest(BaseFarcasterWriteTest):
    """Test SelectKeeperBehaviour."""

    select_keeper_behaviour_class: Type[BaseBehaviour]
    next_behaviour_class: Type[BaseBehaviour]

    def test_select_keeper(
        self,
    ) -> None:
        """Test select keeper agent."""
        participants = [self.skill.skill_context.agent_address, "a_1", "a_2"]
        self.fast_forward_to_behaviour(
            behaviour=self.behaviour,
            behaviour_id=self.select_keeper_behaviour_class.auto_behaviour_id(),
            synchronized_data=SynchronizedData(
                AbciAppDB(
                    setup_data=dict(
                        participants=[participants],
                        most_voted_randomness=[
                            "56cbde9e9bbcbdcaf92f183c678eaa5288581f06b1c9c7f884ce911776727688"
                        ],
                        most_voted_keeper_address=["a_1"],
                    ),
                )
            ),
        )
        assert (
            cast(
                BaseBehaviour,
                cast(BaseBehaviour, self.behaviour.current_behaviour),
            ).behaviour_id
            == self.select_keeper_behaviour_class.auto_behaviour_id()
        )
        self.behaviour.act_wrapper()
        self.mock_a2a_transaction()
        self._test_done_flag_set()
        self.end_round(done_event=Event.DONE)
        behaviour = cast(BaseBehaviour, self.behaviour.current_behaviour)
        assert behaviour.behaviour_id == self.next_behaviour_class.auto_behaviour_id()


class TestSelectKeeperFarcasterBehaviour(BaseSelectKeeperFarcasterBehaviourTest):
    """Test SelectKeeperBehaviour."""

    select_keeper_behaviour_class = SelectKeeperFarcasterWriteBehaviour
    next_behaviour_class = FarcasterWriteBehaviour


class TestFarcasterWriteBehaviour(BaseFarcasterWriteTest):
    """Tests TestFarcasterWriteBehaviour"""

    behaviour_class = FarcasterWriteBehaviour
    next_behaviour_class = make_degenerate_behaviour(FinishedFarcasterWriteRound)

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_index=0,
                        write_data=[{"text": "dummy_tweet", "credentials": {}}],
                    ),
                    event=Event.DONE,
                ),
                {},
            ),
            (
                BehaviourTestCase(
                    "Happy path - not keeper",
                    initial_data=dict(
                        most_voted_keeper_address="not_my_address",
                        write_index=0,
                        write_data=[{"text": "dummy_tweet", "credentials": {}}],
                    ),
                    event=Event.DONE,
                ),
                {},
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()

        if test_case.initial_data["most_voted_keeper_address"] == "test_agent_address":
            self.mock_farcaster_request(
                request_kwargs=dict(
                    performative=SrrMessage.Performative.REQUEST
                ),
                response_kwargs=dict(
                    performative=SrrMessage.Performative.RESPONSE,
                    cast_id="dummy",
                ),
            )

            self.complete(test_case.event)
        else:
            self.complete(test_case.event, sends=False)


class TestFarcasterWriteBehaviourError(BaseFarcasterWriteTest):
    """Tests TestFarcasterWriteBehaviour"""

    behaviour_class = FarcasterWriteBehaviour
    next_behaviour_class = RandomnessFarcasterWriteBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_index=0,
                        write_data=[{"text": "dummy_tweet", "credentials": {}}],
                    ),
                    event=Event.API_ERROR,
                ),
                {},
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()

        self.mock_farcaster_request(
            request_kwargs=dict(performative=SrrMessage.Performative.CREATE_TWEET),
            response_kwargs=dict(
                performative=SrrMessage.Performative.ERROR, message="dummy"
            ),
        )

        self.complete(test_case.event)
