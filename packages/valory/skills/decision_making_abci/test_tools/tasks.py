# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2024 Valory AG
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

"""Base tests package for decision_making_abci task tests."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Type
from unittest.mock import MagicMock

import pytest

from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.abstract_round_abci.test_tools.base import (
    FSMBehaviourBaseCase,
)
from packages.valory.skills.contribute_db_abci.contribute_models import (
    ContributeUser,
    ModuleData,
)
from packages.valory.skills.decision_making_abci.behaviours import (
    DecisionMakingBehaviour,
)
from packages.valory.skills.decision_making_abci.rounds import SynchronizedData
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


NOW_UTC = datetime.now(tz=timezone.utc)


@dataclass
class TaskTestCase:
    """TwitterPreparationTestCase"""

    name: str
    task_preparation_class: Any
    exception_message: Any
    initial_data: Optional[Any] = None


PARAM_OVERRIDES = {
    "twitter_max_pages": 10,
    "staking_contract_addresses": [
        "0xe2E68dDafbdC0Ae48E39cDd1E778298e9d865cF4",
        "0x6Ce93E724606c365Fc882D4D6dfb4A0a35fE2387",
        "0x28877FFc6583170a4C9eD0121fc3195d06fd3A26",
    ],
    "contribute_db_pkey": "0x1111111111111111111111111111111111111111111111111111111111111111",
    "twitter_search_args": "query=Olas%20AI%20Agents&tweet.fields=author_id,created_at,conversation_id,public_metrics&user.fields=name&expansions=author_id&max_results=120&since_id=0",
    "contributors_contract_address": "0x343F2B005cF6D70bA610CD9F1F1927049414B582",
}


def get_mocked_contribute_db():
    """Factory to create a fresh mocked contribute DB per test with full control over parameters."""
    users = {
        "1": ContributeUser(
            id=1,
            current_period_points=0,
            twitter_handle="dummy_1",
            service_multisig=None,
            wallet_address=None,
        ),
        "2": ContributeUser(
            id=2,
            current_period_points=0,
            twitter_handle="dummy_2",
            service_multisig=None,
            wallet_address=None,
        ),
        "3": ContributeUser(
            id=3,
            current_period_points=0,
            twitter_handle="dummy_3",
            service_multisig=None,
            wallet_address=None,
        ),
        "4": ContributeUser(
            id=4,
            current_period_points=0,
            twitter_handle="dummy_4",
            service_multisig=None,
            wallet_address=None,
        ),
        "5": ContributeUser(
            id=5,
            current_period_points=0,
            twitter_handle="dummy_5",
            service_multisig=None,
            wallet_address=None,
        ),
    }

    contribute_db = MagicMock()

    def _get_user_by_attribute(attr, value):
        return users.get(value, None)

    contribute_db.get_user_by_attribute.side_effect = _get_user_by_attribute
    return contribute_db


def get_mocked_agent_db(
    number_of_tweets_pulled_today: int = 1,
    last_tweet_pull_window_reset: int = 1993903085,
    latest_hashtag_tweet_id: int = 0,
    campaigns: list = None,
    current_scoring_period=None,
):
    """Factory to create a fresh mocked agent DB per test with full control over parameters."""
    if campaigns is None:
        campaigns = []

    if current_scoring_period is None:
        current_scoring_period = datetime.now().date()
    return MagicMock(
        module_data=MagicMock(
            twitter=MagicMock(
                number_of_tweets_pulled_today=number_of_tweets_pulled_today,
                last_tweet_pull_window_reset=last_tweet_pull_window_reset,
                latest_hashtag_tweet_id=latest_hashtag_tweet_id,
                current_period=current_scoring_period,
            ),
            twitter_campaigns=MagicMock(campaigns=campaigns),
        )
    )


class BaseTaskTest(FSMBehaviourBaseCase):
    """Base Task Test."""

    path_to_skill = Path(__file__).parent.parent
    behaviour: DecisionMakingBehaviour

    behaviour_class: Type[DecisionMakingBehaviour]
    synchronized_data: SynchronizedData
    mock_task_preparation_object: TaskPreparation

    def set_up(self):
        """Set up the class."""
        self.behaviour = DecisionMakingBehaviour(
            name="dummy", skill_context=self.skill.skill_context
        )
        self.synchronized_data = SynchronizedData(
            AbciAppDB(setup_data=AbciAppDB.data_to_lists({}))
        )
        self.context = MagicMock()

    @classmethod
    def setup_class(cls, **kwargs: Any) -> None:
        """Setup class"""
        super().setup_class(param_overrides=PARAM_OVERRIDES)
        # inject before behaviour instantiation
        cls._skill.skill_context.agent_db_client = MagicMock()
        cls._skill.skill_context.contribute_db = MagicMock()

    def create_task_preparation_object(self, test_case: TaskTestCase):
        """Create the write stream object."""
        self.mock_task_preparation_object = test_case.task_preparation_class(
            datetime.now(timezone.utc),
            self.behaviour,
            self.synchronized_data,
            self.context,
        )
        if test_case.initial_data:
            self.mock_task_preparation_object.module_data = ModuleData(
                **test_case.initial_data["synchronized_data"]["centaurs_data"][0][
                    "plugins_data"
                ]
            )
        self.mock_task_preparation_object.logger.info = MagicMock()

    def mock_params(self, test_case) -> None:
        """Update skill params."""
        self.skill.skill_context.params.__dict__.update({"_frozen": False})
        self.skill.skill_context.params.centaur_id_to_secrets = test_case.initial_data[
            "centaur_id_to_secrets"
        ]

    def teardown(self):
        """Tear down the class."""
        self.skill.skill_context.params.__dict__.update({"_frozen": False})
        self.skill.skill_context.params.centaur_id_to_secrets = {}
        self.mock_task_preparation_object.synchronized_data.update(**{})

    def check_extra_conditions_test(self, test_case: TaskTestCase):
        """Test the check_extra_conditions method."""
        self.set_up()
        self.create_task_preparation_object(test_case)
        if test_case.initial_data:
            if test_case.initial_data["centaur_id_to_secrets"]:
                self.mock_params(test_case)
        gen = self.mock_task_preparation_object.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = test_case.exception_message
        assert str(exception_message) == str(excinfo.value)
        self.teardown()

    def _post_task_base_test(self, test_case: TaskTestCase):
        """Test the _post_task method."""
        self.set_up()
        self.create_task_preparation_object(test_case)
        self.mock_task_preparation_object.now_utc = NOW_UTC
        self.mock_task_preparation_object.synchronized_data.update(
            **test_case.initial_data
        )
        self.mock_params(test_case)
        gen = self.mock_task_preparation_object._post_task()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = test_case.exception_message
        assert str(exception_message) == str(excinfo.value)

    def _pre_task_base_test_logic(self, test_case: TaskTestCase):
        """Test logic for the pre task base test."""
        gen = self.mock_task_preparation_object._pre_task()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = test_case.exception_message
        assert str(exception_message) == str(excinfo.value)

    def _pre_task_base_test(self, test_case: TaskTestCase):
        """Test the _pre_task method."""
        self.set_up()
        self.create_task_preparation_object(test_case)
        self.mock_params(test_case)

        self._pre_task_base_test_logic(test_case)
