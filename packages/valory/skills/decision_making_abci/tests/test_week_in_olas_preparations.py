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
"""Test week in olas preparation tasks."""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.week_in_olas_preparations import (
    WeekInOlasCreatePreparation,
)


class TesWeekInOlasPreparation(unittest.TestCase):
    """Test the WeekInOlasCreatePreparation class."""

    def setUp(self):
        """Set up the tests."""
        self.behaviour = MagicMock()
        self.synchronized_data = MagicMock()
        self.mock_week_in_olas_create_preparation = WeekInOlasCreatePreparation(
            datetime.now(timezone.utc), self.behaviour, self.synchronized_data
        )

    def test_check_extra_conditions(self):
        """Test the check_extra_conditions method."""
        gen = self.mock_week_in_olas_create_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertTrue(next(gen))

    def test__pre_task(self):
        """Test the _pre_task method."""
        gen = self.mock_week_in_olas_create_preparation._pre_task()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = ({}, Event.WEEK_IN_OLAS_CREATE.value)
        assert str(exception_message) in str(excinfo.value)

    def test__post_task(self):
        """Test the _post_task method."""
        gen = self.mock_week_in_olas_create_preparation._post_task()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = (
            {
                "centaurs_data": self.mock_week_in_olas_create_preparation.synchronized_data.centaurs_data,
                "has_centaurs_changes": True,
            },
            None,
        )
        assert str(exception_message) in str(excinfo.value)
