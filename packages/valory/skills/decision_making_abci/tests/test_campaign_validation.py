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

"""Test the campaign validation preparation tasks"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from unittest.mock import patch
import pytest

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.campaign_validation_preparation import (
    CampaignValidationPreparation,
)
from packages.valory.skills.decision_making_abci.tests import centaur_configs
from packages.valory.skills.decision_making_abci.tasks.signature_validation import SignatureValidationMixin

DUMMY_CENTAURS_DATA = [
    centaur_configs.ENABLED_CENTAUR,
    centaur_configs.DISABLED_CENTAUR,
]


class TestCampaignValidationPreparation(unittest.TestCase):
    """Test the FinishedPipeliTestCampaignValidationPreparationnePreparation class."""

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
        self.synchronized_data.centaurs_data = DUMMY_CENTAURS_DATA
        self.synchronized_data.current_centaur_index = 0

        # Create an instance of CampaignValidationPreparation
        self.mock_campaign_validation_preparation = CampaignValidationPreparation(
            datetime.now(timezone.utc),
            self.behaviour,
            self.synchronized_data,
            self.context,
        )

    @patch("packages.valory.skills.decision_making_abci.tasks.signature_validation.SignatureValidationMixin.validate_signature")
    def test_pre_task(self, mock_validate_signature):
        """Test pre_task"""

        # Configurar el generador para que devuelva False indefinidamente
        mock_validate_signature.return_value = MagicMock()
        mock_validate_signature.return_value.__iter__.return_value = iter([False, False, False])

        gen = self.mock_campaign_validation_preparation._pre_task()
        updates = next(gen)



    # def test_check_extra_conditions(self):
    #     """Test check_extra_conditions."""
    #     gen = self.mock_campaign_validation_preparation.check_extra_conditions()
    #     self.assertIsInstance(gen, type((lambda: (yield))()))
    #     next(gen)
    #     with pytest.raises(StopIteration):
    #         assert next(gen)

    # def test__pre_task(self):
    #     """Test _pre_task."""
    #     gen = self.mock_campaign_validation_preparation._pre_task()
    #     self.assertIsInstance(gen, type((lambda: (yield))()))
    #     next(gen)
    #     with pytest.raises(StopIteration) as excinfo:
    #         next(gen)

    #     exception_message = {
    #         "current_centaur_index": self.mock_campaign_validation_preparation.get_next_centaur_index()
    #     }, Event.NEXT_CENTAUR.value
    #     assert str(exception_message) in str(excinfo.value)

    #     self.mock_campaign_validation_preparation.logger.info.assert_called_with(
    #         f"Next centaur index: {self.mock_campaign_validation_preparation.get_next_centaur_index()} [{len(self.mock_campaign_validation_preparation.synchronized_data.centaurs_data)}]"
    #     )
