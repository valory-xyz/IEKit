import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from packages.valory.skills.decision_making_abci.tasks.week_in_olas_preparations import WeekInOlasCreatePreparation
from packages.valory.skills.decision_making_abci.rounds import Event


class TestScorePreparation(unittest.TestCase):

    def __init__(self, methodName: str = "runTest"):
        super().__init__(methodName)
        self.now_utc = None

    def setUp(self):
        self.behaviour = MagicMock()
        self.synchronized_data = MagicMock()
        self.mock_week_in_olas_create_preparation = WeekInOlasCreatePreparation(datetime.now(timezone.utc), self.behaviour, self.synchronized_data)

    def test_check_extra_conditions(self):
        gen = self.mock_week_in_olas_create_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertEqual(True, next(gen))

    def test__pre_task(self):
        gen = self.mock_week_in_olas_create_preparation._pre_task()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertEqual(({}, Event.WEEK_IN_OLAS_CREATE.value), next(gen))

    def test__post_task(self):
        centaurs_data = {"mock_centaurs_data": "mock_centaurs_data"}
        gen = self.mock_week_in_olas_create_preparation._post_task()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertEqual(({"centaurs_data": centaurs_data, "has_centaurs_changes": True}, None), next(gen))