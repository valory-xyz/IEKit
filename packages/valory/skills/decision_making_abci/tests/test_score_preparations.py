import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.score_preparations import ScorePreparation

class TestScorePreparation(unittest.TestCase):

    def setUp(self):
        self.behaviour = MagicMock()
        self.synchronized_data = MagicMock()
        self.mock_score_preparation = ScorePreparation(datetime.now(timezone.utc), self.behaviour, self.synchronized_data)

    def test_check_extra_conditions(self):
        gen = self.mock_score_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertEqual(True, next(gen))

    def test__pre_task(self):
        gen = self.mock_score_preparation._pre_task()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertEqual(({}, Event.SCORE.value), next(gen))

    def test__post_task(self):
        gen = self.mock_score_preparation._post_task()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertEqual(({}, None), next(gen))