import unittest
from dataclasses import dataclass
from typing import Any

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.read_stream_preparation import ReadCentaursPreparation, \
    ReadContributeDBPreparation, ReadManualPointsPreparation

@dataclass
class ReadStreamTestCase():
    name: str
    read_stream_class: Any
    task_event: Event
    post_updates: dict

class BaseReadStreamPreparation():
    def set_up(self):
        # Create the mock behaviour
        self.behaviour = MagicMock()
        # self.behaviour.params = MagicMock()
        self.behaviour.params.centaurs_stream_id = 0
        # self.behaviour.context.logger = MagicMock()
        # self.behaviour.state = {}
        # self.behaviour.context.ceramic_db = MagicMock()
        self.behaviour.context.state.ceramic_data = {"mock_ceramic_data": "mock_ceramic_data"}
        self.synchronized_data = MagicMock()
        # self.synchronized_data.centaurs_data = {}

    def create_read_stream_object(self, read_stream_class):
        # Create an instance of ReadCentaursPreparation
        self.mock_read_stream_preparation = read_stream_class(datetime.now(timezone.utc), self.behaviour, self.synchronized_data)

    def base_test_check_extra_conditions(self):
        gen = self.mock_read_stream_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration):
            assert next(gen) == True

    def base_test__pre_task(self, event):
        gen = self.mock_read_stream_preparation._pre_task()
        next(gen)
        with pytest.raises(StopIteration):
            assert ({"read_stream_id": 0,"sync_on_ceramic_data": False,}, event) == next(gen)

    def base_test__post_task(self, updates):
        gen = self.mock_read_stream_preparation._post_task()
        next(gen)
        with pytest.raises(StopIteration):
            assert (updates, None) == next(gen)

    def run_tests(self, test_case: ReadStreamTestCase):
        self.set_up()
        self.create_read_stream_object(test_case.read_stream_class)
        self.base_test_check_extra_conditions()
        self.base_test__pre_task(test_case.task_event)
        self.base_test__post_task(test_case.post_updates)

class TestReadStreamsPreparation(BaseReadStreamPreparation):
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
                }
            ),
            ReadStreamTestCase(
                name="ReadContributeDBPreparation",
                read_stream_class=ReadContributeDBPreparation,
                task_event=Event.READ_CONTRIBUTE_DB.value,
                post_updates={
                    "read_stream_id": 0,
                    "sync_on_ceramic_data": False,
                }
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
