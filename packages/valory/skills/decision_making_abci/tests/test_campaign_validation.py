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

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.campaign_validation_preparation import (
    CampaignValidationPreparation,
)
from packages.valory.skills.decision_making_abci.tests.centaur_configs import *


DUMMY_CENTAURS_DATA = [
    ENABLED_CENTAUR,
    DISABLED_CENTAUR,
]


@dataclass
class CampaignValidationTestCase:
    """CampaignValidationTestCase"""

    name: str
    campaign: Dict
    campaign_validation_preparation_class: Any
    exception_message: Any
    end_status: str
    has_updates: bool
    proposer_verified: bool
    centaur_configs: Optional[Any] = None
    logger_message: Optional[Any] = None


class BaseCampaignValidationPreparationTest:
    """Base class for BaseCampaignValidationPreparationTest tests."""

    def set_up(self, campaign):
        """Set up the class."""
        self.behaviour = MagicMock()
        self.synchronized_data = MagicMock()
        self.synchronized_data.centaurs_data = DUMMY_CENTAURS_DATA
        self.synchronized_data.centaurs_data[0]["plugins_data"]["twitter_campaigns"][
            "campaigns"
        ] = [campaign]
        self.context = MagicMock()

    def create_tweet_validation_object(self, campaign_validation_preparation_class):
        """Create the tweet validation object."""
        self.mock_campaign_validation_preparation = (
            campaign_validation_preparation_class(
                datetime.now(timezone.utc),
                self.behaviour,
                self.synchronized_data,
                self.context,
            )
        )

        self.mock_campaign_validation_preparation.behaviour.context.logger.info = (
            MagicMock()
        )
        self.mock_campaign_validation_preparation.logger.info = MagicMock()

    def _pre_task_base_test(self, test_case: CampaignValidationTestCase):
        """Test the _pre_task method."""
        self.mock_campaign_validation_preparation.synchronized_data.centaurs_data = (
            DUMMY_CENTAURS_DATA
        )
        self.mock_campaign_validation_preparation.synchronized_data.current_centaur_index = (
            0
        )
        gen = self.mock_campaign_validation_preparation._pre_task()
        next(gen)
        calls = test_case.logger_message
        self.mock_campaign_validation_preparation.logger.info.assert_has_calls(
            calls, any_order=True
        )
        with pytest.raises(StopIteration):
            next(gen)

        updates, event = test_case.exception_message
        return updates, event


class TestTweetValidationPreparation(BaseCampaignValidationPreparationTest):
    """Test the TweetValidationPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            CampaignValidationTestCase(
                name="Proposed to voting",
                campaign=PROPOSED_TO_VOTING_CAMPAIGN,
                campaign_validation_preparation_class=CampaignValidationPreparation,
                exception_message=(
                    {
                        "centaurs_data": DUMMY_CENTAURS_DATA,
                        "has_centaurs_changes": True,
                    },
                    Event.TWEET_VALIDATION.value,
                ),
                logger_message=[],
                has_updates=True,
                end_status="voting",
                proposer_verified=True,
            ),
            CampaignValidationTestCase(
                name="Proposed to void",
                campaign=PROPOSED_TO_VOID_CAMPAIGN,
                campaign_validation_preparation_class=CampaignValidationPreparation,
                exception_message=(
                    {
                        "centaurs_data": DUMMY_CENTAURS_DATA,
                        "has_centaurs_changes": True,
                    },
                    Event.TWEET_VALIDATION.value,
                ),
                logger_message=[],
                has_updates=True,
                end_status="void",
                proposer_verified=False,
            ),
        ],
    )
    @patch(
        "packages.valory.skills.decision_making_abci.tasks.campaign_validation_preparation.CampaignValidationPreparation.is_contract"
    )
    def test_pre_task(
        self,
        mock_is_contract,
        test_case: CampaignValidationTestCase,
    ):
        """Test the _post_task method."""
        mock_is_contract.return_value = {"is_contract": False}
        self.set_up(test_case.campaign)
        self.create_tweet_validation_object(
            test_case.campaign_validation_preparation_class
        )
        updates, event = self._pre_task_base_test(test_case)

        assert event == Event.TWEET_VALIDATION.value
        assert updates["has_centaurs_changes"] is test_case.has_updates

        campaigns = updates["centaurs_data"][0]["plugins_data"]["twitter_campaigns"][
            "campaigns"
        ]

        assert campaigns[0]["proposer"]["verified"] is test_case.proposer_verified
        assert campaigns[0]["status"] == test_case.end_status
