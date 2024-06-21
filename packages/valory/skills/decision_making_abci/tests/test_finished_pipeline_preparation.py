import unittest

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.finished_pipeline_preparation import FinishedPipelinePreparation
from packages.valory.skills.decision_making_abci.tests import centaur_configs

DUMMY_CENTAURS_DATA = [
    centaur_configs.ENABLED_CENTAUR,
    centaur_configs.DISABLED_CENTAUR,
]

class TestFinishedPipelinePreparation(unittest.TestCase):

    def setUp(self):
        # Create the mock behaviour
        self.behaviour = MagicMock()
        self.behaviour.params = {}
        self.behaviour.context.logger = MagicMock()
        self.behaviour.state = {}
        self.behaviour.context.ceramic_db = MagicMock()
        self.synchronized_data = MagicMock()
        self.synchronized_data.centaurs_data = DUMMY_CENTAURS_DATA
        self.synchronized_data.current_centaur_index = 0

        # Create an instance of FinishedPipelinePreparation
        self.mock_finished_pipeline_preparation = FinishedPipelinePreparation(datetime.now(timezone.utc), self.behaviour, self.synchronized_data)
    def test_check_extra_conditions(self):
        gen = self.mock_finished_pipeline_preparation.check_extra_conditions()
        self.assertIsInstance(gen, type((lambda: (yield))()))
        assert next(gen) == None
        with pytest.raises(StopIteration):
            assert next(gen) == True
    def test__pre_task(self):
        gen = self.mock_finished_pipeline_preparation._pre_task()
        self.assertIsInstance(gen, type((lambda: (yield))()))
        assert  next(gen) == None
        with pytest.raises(StopIteration):
            assert next(gen) == {"current_centaur_index": self.mock_finished_pipeline_preparation.get_next_centaur_index()}, Event.NEXT_CENTAUR.value

        for value in gen:
            self.mock_finished_pipeline_preparation.logger.info.assert_called_with(f"Next centaur index: {self.mock_finished_pipeline_preparation.get_next_centaur_index()} [{len(self.mock_finished_pipeline_preparation.synchronized_data.centaurs_data)}]")

    def test_get_next_centaur_index(self):
        assert self.mock_finished_pipeline_preparation.get_next_centaur_index() == 1

    def test_check_conditions_proceeds_extra_conditions(self):
        self.mock_finished_pipeline_preparation.enabled = False
        self.mock_finished_pipeline_preparation.daily = False
        self.mock_finished_pipeline_preparation.weekly = None

        gen = self.mock_finished_pipeline_preparation.check_conditions()
        with pytest.raises(StopIteration):
            assert next(gen) == False