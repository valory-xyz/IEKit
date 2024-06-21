#!/usr/bin/env python3
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

"""Test read stream preparation tasks."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.read_stream_preparation import (
    ReadCentaursPreparation,
    ReadContributeDBPreparation,
    ReadManualPointsPreparation,
)


@dataclass
class ReadStreamTestCase:
    """ReadStreamTestCase"""

    name: str
    read_stream_class: Any
    task_event: Event
    post_updates: dict


class BaseReadStreamPreparation:
    """Base class for testing read stream preparation tasks."""

    def set_up(self):
        """Set up the class."""

        # Create the mock behaviour
        self.behaviour = MagicMock()
        self.behaviour.params.centaurs_stream_id = 0
        self.behaviour.context.state.ceramic_data = {
            "mock_ceramic_data": "mock_ceramic_data"
        }
        self.synchronized_data = MagicMock()

    def create_read_stream_object(self, read_stream_class):
        """Create an instance of the appropriate read stream class."""
        # Create an instance of ReadStreamPreparation
        self.mock_read_stream_preparation = read_stream_class(
            datetime.now(timezone.utc), self.behaviour, self.synchronized_data
        )

    def base_test_check_extra_conditions(self):
        """Base test for check_extra_conditions."""
        gen = self.mock_read_stream_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration):
            assert next(gen)

    def base_test__pre_task(self, event):
        """Base test for _pre_task."""
        gen = self.mock_read_stream_preparation._pre_task()
        next(gen)
        with pytest.raises(StopIteration):
            assert (
                {
                    "read_stream_id": 0,
                    "sync_on_ceramic_data": False,
                },
                event,
            ) == next(gen)

    def base_test__post_task(self, updates):
        """Base test for _post_task."""
        gen = self.mock_read_stream_preparation._post_task()
        next(gen)
        with pytest.raises(StopIteration):
            assert (updates, None) == next(gen)

    def run_tests(self, test_case: ReadStreamTestCase):
        """Run tests."""
        self.set_up()
        self.create_read_stream_object(test_case.read_stream_class)
        self.base_test_check_extra_conditions()
        self.base_test__pre_task(test_case.task_event)
        self.base_test__post_task(test_case.post_updates)


class TestReadStreamsPreparation(BaseReadStreamPreparation):
    """Test class for read stream preparation tasks."""

    @pytest.mark.parametrize(
        "test_case",
        [
            ReadStreamTestCase(
                name="ReadCentaursPreparation",
                read_stream_class=ReadCentaursPreparation,
                task_event=Event.READ_CENTAURS.value,
                post_updates={
                    "read_stream_id": 0,
                    "sync_on_ceramic_data": False,
                },
            ),
            ReadStreamTestCase(
                name="ReadContributeDBPreparation",
                read_stream_class=ReadContributeDBPreparation,
                task_event=Event.READ_CONTRIBUTE_DB.value,
                post_updates={
                    "read_stream_id": 0,
                    "sync_on_ceramic_data": False,
                },
            ),
            ReadStreamTestCase(
                name="ReadManualPointsPreparation",
                read_stream_class=ReadManualPointsPreparation,
                task_event=Event.READ_MANUAL_POINTS.value,
                post_updates={
                    "read_stream_id": 0,
                    "sync_on_ceramic_data": False,
                },
            ),
        ],
    )
    def test_run(self, test_case: ReadStreamTestCase) -> None:
        """Run tests."""
        self.run_tests(test_case)
