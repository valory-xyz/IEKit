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
"""Test write stream preparation tasks."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.write_stream_preparation import (
    DailyOrbisPreparation,
    OrbisPreparation,
    UpdateCentaursPreparation,
    WriteContributeDBPreparation,
    WriteStreamPreparation,
)
from packages.valory.skills.decision_making_abci.tests import centaur_configs


DUMMY_CENTAURS_DATA = [
    centaur_configs.ENABLED_CENTAUR,
    centaur_configs.DISABLED_CENTAUR,
]


@dataclass
class WriteStreamTestCase:
    """WriteStreamTestCase"""

    name: str
    write_stream_preparation_class: Any
    exception_message: Any
    centaur_configs: Optional[Any] = None


class BaseWriteStreamPreparationTest:
    """Base class for WriteStreamPreparation tests."""

    def create_write_stream_object(self, write_stream_preparation_class):
        """Create the write stream object."""
        synchronized_data = MagicMock()
        synchronized_data.centaurs_data = DUMMY_CENTAURS_DATA
        self.mock_write_stream_preparation = write_stream_preparation_class(
            datetime.now(timezone.utc), MagicMock(), synchronized_data
        )

        self.mock_write_stream_preparation.logger.info = MagicMock()

    def check_extra_conditions_test(self, test_case: WriteStreamTestCase):
        """Test the check_extra_conditions method."""
        gen = self.mock_write_stream_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = test_case.exception_message
        assert str(exception_message) in str(excinfo.value)

    def _post_task_base_test(self, test_case: WriteStreamTestCase):
        """Test the _post_task method."""
        gen = self.mock_write_stream_preparation._post_task()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = test_case.exception_message
        assert str(exception_message) in str(excinfo.value)

    def _pre_task_base_test(self, test_case: WriteStreamTestCase):
        """Test the _pre_task method."""
        gen = self.mock_write_stream_preparation._pre_task()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = test_case.exception_message
        assert str(exception_message) in str(excinfo.value)


class TestWriteStreamPreparation(BaseWriteStreamPreparationTest):
    """Test the WriteStreamPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=WriteStreamPreparation,
                exception_message=True,
            )
        ],
    )
    def test_check_extra_conditions(self, test_case: WriteStreamTestCase):
        """Test the check_extra_conditions method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self.check_extra_conditions_test(test_case)


class TestOrbisPreparation(BaseWriteStreamPreparationTest):
    """Test the OrbisPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=OrbisPreparation,
                exception_message=False,
            )
        ],
    )
    @patch(
        "packages.valory.skills.decision_making_abci.tasks.write_stream_preparation.WriteStreamPreparation.check_extra_conditions"
    )
    def test_check_extra_conditions_not_proceed(
        self, mock_check_extra_conditions, test_case: WriteStreamTestCase
    ):
        """Test the check_extra_conditions method when not proceed."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        mock_check_extra_conditions.return_value = iter(
            [
                None,
            ]
        )
        self.check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Centaur ID to secrets missing id",
                write_stream_preparation_class=OrbisPreparation,
                exception_message=False,
                centaur_configs=centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ID,
            ),
            WriteStreamTestCase(
                name="Centaur ID to secrets missing orbis",
                write_stream_preparation_class=OrbisPreparation,
                exception_message=False,
                centaur_configs=centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ORBIS,
            ),
            WriteStreamTestCase(
                name="Centaur ID to secrets missing orbis key",
                write_stream_preparation_class=OrbisPreparation,
                exception_message=False,
                centaur_configs=centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ORBIS_KEY,
            ),
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=OrbisPreparation,
                exception_message=True,
                centaur_configs=centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
            ),
        ],
    )
    def test_check_extra_conditions(self, test_case: WriteStreamTestCase):
        """Test the check_extra_conditions method when the centaur id is not in centaur id to secrets."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self.mock_write_stream_preparation.params.centaur_id_to_secrets = (
            test_case.centaur_configs
        )
        self.check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=OrbisPreparation,
                exception_message=(
                    {
                        "centaurs_data": DUMMY_CENTAURS_DATA,
                        "has_centaurs_changes": True,
                    },
                    None,
                ),
            )
        ],
    )
    def test__post_task(self, test_case: WriteStreamTestCase):
        """Test the _post_task method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self._post_task_base_test(test_case)


class TestDailyOrbisPreparation(BaseWriteStreamPreparationTest):
    """Test the DailyOrbisPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=DailyOrbisPreparation,
                exception_message=({"centaurs_data": DUMMY_CENTAURS_DATA}, None),
            )
        ],
    )
    def test__post_task(self, test_case: WriteStreamTestCase):
        """Test the _post_task method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self._post_task_base_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=DailyOrbisPreparation,
                exception_message=(
                    {
                        "write_results": [],  # clear previous results
                        "is_data_on_sync_db": False,
                    },
                    Event.DAILY_ORBIS.value,
                ),
            )
        ],
    )
    def test__pre_task(self, test_case: WriteStreamTestCase):
        """Test the _post_task method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self._pre_task_base_test(test_case)


class TestUpdateCentaursPreparation(BaseWriteStreamPreparationTest):
    """Test the UpdateCentaursPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=UpdateCentaursPreparation,
                exception_message=False,
            )
        ],
    )
    @patch(
        "packages.valory.skills.decision_making_abci.tasks.write_stream_preparation.WriteStreamPreparation.check_extra_conditions"
    )
    def test_check_extra_conditions_not_proceed(
        self,
        mock_check_extra_conditions,
        test_case: WriteStreamTestCase,
    ):
        """Test the check_extra_conditions method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        mock_check_extra_conditions.return_value = iter(
            [
                None,
            ]
        )
        self.check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=UpdateCentaursPreparation,
                exception_message=False,
            )
        ],
    )
    def test_check_extra_conditions(
        self,
        test_case: WriteStreamTestCase,
    ):
        """Test the check_extra_conditions method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self.mock_write_stream_preparation.synchronized_data.has_centaurs_changes = (
            False
        )
        self.check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=UpdateCentaursPreparation,
                exception_message=(
                    {
                        "has_centaurs_changes": False,
                    },
                    None,
                ),
            )
        ],
    )
    def test__post_task(self, test_case: WriteStreamTestCase):
        """Test the _post_task method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self._post_task_base_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=UpdateCentaursPreparation,
                exception_message=(
                    {
                        "write_results": [],  # clear previous results
                        "is_data_on_sync_db": False,
                    },
                    Event.UPDATE_CENTAURS.value,
                ),
            )
        ],
    )
    def test__pre_task(self, test_case: WriteStreamTestCase):
        """Test the _post_task method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self._pre_task_base_test(test_case)


class TestWriteContributeDBPreparation(BaseWriteStreamPreparationTest):
    """Test the WriteContributeDBPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=WriteContributeDBPreparation,
                exception_message=False,
            )
        ],
    )
    @patch(
        "packages.valory.skills.decision_making_abci.tasks.write_stream_preparation.WriteStreamPreparation.check_extra_conditions"
    )
    def test_check_extra_conditions_not_proceed(
        self,
        mock_check_extra_conditions,
        test_case: WriteStreamTestCase,
    ):
        """Test the check_extra_conditions method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        mock_check_extra_conditions.return_value = iter(
            [
                None,
            ]
        )
        self.check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=WriteContributeDBPreparation,
                exception_message=True,
            )
        ],
    )
    def test_check_extra_conditions(
        self,
        test_case: WriteStreamTestCase,
    ):
        """Test the check_extra_conditions method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self.mock_write_stream_preparation.synchronized_data.pending_write = True
        self.check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=WriteContributeDBPreparation,
                exception_message=(
                    {
                        "pending_write": False,
                    },
                    None,
                ),
            )
        ],
    )
    def test__post_task(self, test_case: WriteStreamTestCase):
        """Test the _post_task method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self._post_task_base_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            WriteStreamTestCase(
                name="Happy Path",
                write_stream_preparation_class=WriteContributeDBPreparation,
                exception_message=(
                    {
                        "is_data_on_sync_db": False,
                    },
                    Event.WRITE_CONTRIBUTE_DB.value,
                ),
            )
        ],
    )
    def test__pre_task(self, test_case: WriteStreamTestCase):
        """Test the _post_task method."""
        self.create_write_stream_object(test_case.write_stream_preparation_class)
        self._pre_task_base_test(test_case)
