import unittest

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from packages.valory.skills.decision_making_abci.tasks.task_preparations import TaskPreparation

class TestTaskPreparation(unittest.TestCase):

    def setUp(self):
        # Create the mock behaviour
        self.behaviour = MagicMock()
        self.behaviour.params = {}
        self.behaviour.context.logger = MagicMock()
        self.behaviour.state = {}
        self.behaviour.context.ceramic_db = MagicMock()
        self.synchronized_data = MagicMock()
        self.synchronized_data.centaurs_data = {}

        # Create an instance of TaskPreparation
        self.mock_task_preparation = TaskPreparation(datetime.now(timezone.utc), self.behaviour, self.synchronized_data)
    def test_set_config_with_no_centaur_data(self):
        self.mock_task_preparation.set_config()
        assert self.mock_task_preparation.enabled == True
        assert self.mock_task_preparation.daily == False
        assert self.mock_task_preparation.weekly == None
        assert self.mock_task_preparation.last_run == None
        assert self.mock_task_preparation.run_hour_utc == None

    def test_set_config_with_centaur_data(self,):
        self.mock_task_preparation.synchronized_data.current_centaur_index = 0
        self.mock_task_preparation.synchronized_data.centaurs_data =[
            {
                "name": "Dummy Centaur",
                "configuration": {
                    "plugins": {
                        self.mock_task_preparation.task_name: {
                            "enabled": True,
                            "daily": True,
                            "weekly": True,
                            "last_run": None,
                            "run_hour_utc": datetime.utcnow().hour
                        }
                    }
                }
            }
        ]


        self.mock_task_preparation.set_config()
        assert self.mock_task_preparation.enabled == True
        assert self.mock_task_preparation.daily == True
        assert self.mock_task_preparation.weekly == True
        assert self.mock_task_preparation.last_run == None
        assert self.mock_task_preparation.run_hour_utc == datetime.utcnow().hour

    def test_log_config(self):
        self.mock_task_preparation.set_config()
        self.mock_task_preparation.log_config()
        self.mock_task_preparation.logger.info.assert_called_with(f"Config: enabled=True  daily=False  weekly=None  last_run=None  run_hour_utc=None")

    def test_check_conditions_task_disabled(self,):
        self.mock_task_preparation.enabled = False
        for value in self.mock_task_preparation.check_conditions():
            assert value == False
            self.mock_task_preparation.logger.info.assert_called_with(f"[{self.__class__.__name__}]: task is disabled")

    def test_check_conditions_daily_task_already_ran_today(self,):
        self.mock_task_preparation.daily = True
        self.mock_task_preparation.last_run = datetime.now(timezone.utc)
        for value in self.mock_task_preparation.check_conditions():
            assert value == False
            self.mock_task_preparation.logger.info.assert_called_with(f"[{self.__class__.__name__}]: task is a daily task and was already ran today")

    def test_check_conditions_weekly_task_wrong_day(self,):
        self.mock_task_preparation.weekly = (datetime.now(timezone.utc).weekday() + 1) % 7  # Tomorrow's weekday
        for value in self.mock_task_preparation.check_conditions():
            assert value == False
            self.mock_task_preparation.logger.info.assert_called_with(f"[{self.__class__.__name__}]: task is a weekly task and today is not the right day")

    def test_check_conditions_weekly_task_already_ran_today(self,):
        self.mock_task_preparation.weekly = datetime.now(timezone.utc).weekday()
        self.mock_task_preparation.last_run = datetime.now(timezone.utc)
        for value in self.mock_task_preparation.check_conditions():
            assert value == False
            self.mock_task_preparation.logger.info.assert_called_with(f"[{self.__class__.__name__}]: task is a weekly task and was already ran today")

    def test_check_conditions_not_time_to_run_yet(self,):
        self.mock_task_preparation.daily = True
        self.mock_task_preparation.run_hour_utc = datetime.now(timezone.utc).hour + 1  # Next hour
        for value in self.mock_task_preparation.check_conditions():
            assert value == False
            self.mock_task_preparation.logger.info.assert_called_with(f"[{self.__class__.__name__}]: task is a daily task but it is not time to run yet")

    def test_check_conditions_extra_conditions_raises_not_implemented(self,):
        with pytest.raises(NotImplementedError):
            for value in self.mock_task_preparation.check_conditions():
                value

    def test__pre_task(self):
        with pytest.raises(NotImplementedError):
            self.mock_task_preparation._pre_task()

    def test_pre_task(self):
        with pytest.raises(NotImplementedError):
            for value in self.mock_task_preparation.pre_task():
                value

    def test__post_task(self):
        with pytest.raises(NotImplementedError):
            self.mock_task_preparation._post_task()

    def test_post_task(self):
        with pytest.raises(NotImplementedError):
            for value in self.mock_task_preparation.post_task():
                value
