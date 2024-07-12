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
from packages.valory.skills.decision_making_abci.behaviours import (
    DecisionMakingBehaviour,
)
from packages.valory.skills.decision_making_abci.rounds import SynchronizedData
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


NOW_UTC = datetime.utcnow()


@dataclass
class TaskTestCase:
    """TwitterPreparationTestCase"""

    name: str
    task_preparation_class: Any
    exception_message: Any
    initial_data: Optional[Any] = None


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

    def create_task_preparation_object(self, test_case: TaskTestCase):
        """Create the write stream object."""
        self.mock_task_preparation_object = test_case.task_preparation_class(
            datetime.now(timezone.utc), self.behaviour, self.synchronized_data
        )
        if test_case.initial_data:
            self.mock_task_preparation_object.synchronized_data.update(
                **test_case.initial_data["synchronized_data"]
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
        self.skill.skill_context.params.centaur_id_to_secrets = []
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

        print(f"Exception value: {excinfo.value}")
        print(f"Exception message: {test_case.exception_message}")
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
        print(" ")
        print(exception_message)
        print(excinfo.value)
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
