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
"""Test the task preparation tasks"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


class TestTaskPreparation(unittest.TestCase):
    """Test the TaskPreparation class."""

    def setUp(self):
        """Set up the tests."""

        # Create the mock behaviour
        self.behaviour = MagicMock()
        self.behaviour.params = {}
        self.behaviour.context.logger = MagicMock()
        self.behaviour.state = {}
        self.behaviour.context.ceramic_db = MagicMock()
        self.synchronized_data = MagicMock()
        self.context = MagicMock()
        self.synchronized_data.centaurs_data = {}

        # Create an instance of TaskPreparation
        self.mock_task_preparation = TaskPreparation(
            datetime.now(timezone.utc),
            self.behaviour,
            self.synchronized_data,
            self.context,
        )

    def test_set_config_with_no_centaur_data(self):
        """Test the set_config method with no centaur data."""

        self.mock_task_preparation.set_config()
        assert self.mock_task_preparation.enabled
        assert not self.mock_task_preparation.daily
        assert not self.mock_task_preparation.weekly
        assert not self.mock_task_preparation.last_run
        assert not self.mock_task_preparation.run_hour_utc

    def test_set_config_with_centaur_data(
        self,
    ):
        """Test the set_config method with centaur data."""

        self.mock_task_preparation.synchronized_data.current_centaur_index = 0
        self.mock_task_preparation.synchronized_data.centaurs_data = [
            {
                "name": "Dummy Centaur",
                "configuration": {
                    "plugins": {
                        self.mock_task_preparation.task_name: {
                            "enabled": True,
                            "daily": True,
                            "weekly": True,
                            "last_run": None,
                            "run_hour_utc": datetime.now(tz=timezone.utc).hour,
                        }
                    }
                },
            }
        ]

        self.mock_task_preparation.set_config()
        assert self.mock_task_preparation.enabled
        assert self.mock_task_preparation.daily
        assert self.mock_task_preparation.weekly
        assert not self.mock_task_preparation.last_run
        assert (
            self.mock_task_preparation.run_hour_utc
            == datetime.now(tz=timezone.utc).hour
        )

    def test_log_config(self):
        """Test the log_config method."""

        self.mock_task_preparation.set_config()
        self.mock_task_preparation.log_config()
        self.mock_task_preparation.logger.info.assert_called_with(
            "Config: enabled=True  daily=False  weekly=None  last_run=None  run_hour_utc=None"
        )

    def test_check_conditions_task_disabled(
        self,
    ):
        """Test check_conditions when the task is disabled."""

        self.mock_task_preparation.enabled = False
        gen = self.mock_task_preparation.check_conditions()

        with pytest.raises(StopIteration) as excinfo:
            next(gen)
        exception_message = False
        assert str(exception_message) in str(excinfo.value)
        self.mock_task_preparation.logger.info.assert_called_with(
            "[TaskPreparation]: task is disabled"
        )

    def test_check_conditions_daily_task_already_ran_today(
        self,
    ):
        """Test check_conditions when the task is a daily task and was already ran today."""

        self.mock_task_preparation.daily = True
        self.mock_task_preparation.last_run = datetime.now(timezone.utc)
        gen = self.mock_task_preparation.check_conditions()

        with pytest.raises(StopIteration) as excinfo:
            next(gen)
        exception_message = False
        assert str(exception_message) in str(excinfo.value)
        self.mock_task_preparation.logger.info.assert_called_with(
            "[TaskPreparation]: task is a daily task and was already ran today"
        )

    def test_check_conditions_weekly_task_wrong_day(
        self,
    ):
        """Test check_conditions when the task is a weekly task and today is not the right day."""

        self.mock_task_preparation.weekly = (
            datetime.now(timezone.utc).weekday() + 1
        ) % 7  # Tomorrow's weekday

        gen = self.mock_task_preparation.check_conditions()

        with pytest.raises(StopIteration) as excinfo:
            next(gen)
        exception_message = False
        assert str(exception_message) in str(excinfo.value)
        self.mock_task_preparation.logger.info.assert_called_with(
            f"[TaskPreparation]: task is a weekly task but today is not the configured run day: {self.mock_task_preparation.weekly - 1} != {self.mock_task_preparation.weekly}"
        )

    def test_check_conditions_weekly_task_already_ran_today(
        self,
    ):
        """Test check_conditions when the task is a weekly task and was already ran today."""

        self.mock_task_preparation.weekly = datetime.now(timezone.utc).weekday()
        self.mock_task_preparation.last_run = datetime.now(timezone.utc)
        gen = self.mock_task_preparation.check_conditions()

        with pytest.raises(StopIteration) as excinfo:
            next(gen)
        exception_message = False
        assert str(exception_message) in str(excinfo.value)
        self.mock_task_preparation.logger.info.assert_called_with(
            "[TaskPreparation]: task is a weekly task and was already ran less than a day ago"
        )

    def test_check_conditions_not_time_to_run_yet(
        self,
    ):
        """Test check_conditions when it is not time to run the task yet."""

        self.mock_task_preparation.daily = True
        self.mock_task_preparation.run_hour_utc = (
            datetime.now(timezone.utc).hour + 1
        )  # Next hour
        gen = self.mock_task_preparation.check_conditions()

        with pytest.raises(StopIteration) as excinfo:
            next(gen)
        exception_message = False
        assert str(exception_message) in str(excinfo.value)
        self.mock_task_preparation.logger.info.assert_called_with(
            f"[TaskPreparation]: not time to run yet [{self.mock_task_preparation.now_utc.hour}!={self.mock_task_preparation.run_hour_utc}]"
        )

    def test_check_conditions_extra_conditions_raises_not_implemented(
        self,
    ):
        """Test check_conditions when check_extra_conditions raises a NotImplementedError."""

        gen = self.mock_task_preparation.check_conditions()
        with pytest.raises(NotImplementedError):
            next(gen)

    def test__pre_task(self):
        """Test _pre_task."""

        with pytest.raises(NotImplementedError):
            self.mock_task_preparation._pre_task()

    def test_pre_task(self):
        """Test pre_task."""

        gen = self.mock_task_preparation.pre_task()
        with pytest.raises(NotImplementedError):
            next(gen)

    def test__post_task(self):
        """Test _post_task."""

        with pytest.raises(NotImplementedError):
            self.mock_task_preparation._post_task()

    def test_post_task(self):
        """Test post_task."""

        gen = self.mock_task_preparation.post_task()
        with pytest.raises(NotImplementedError):
            next(gen)
