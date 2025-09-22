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

from packages.valory.skills.contribute_db_abci.contribute_models import TwitterCampaign
from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.campaign_validation_preparation import (
    CampaignValidationPreparation,
)
from packages.valory.skills.decision_making_abci.tests.centaur_configs import (
    DISABLED_CENTAUR,
    ENABLED_CENTAUR,
    ENDED_TO_ENDED_CAMPAIGN,
    LIVE_TO_ENDED_CAMPAIGN,
    PROPOSED_TO_VOID_CAMPAIGN,
    PROPOSED_TO_VOTING_CAMPAIGN,
    SCHEDULED_TO_LIVE_CAMPAIGN,
    VOTING_TO_SCHEDULED_CAMPAIGN,
    VOTING_TO_VOID_CAMPAIGN,
)


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
        self.context = MagicMock()

        self.context.contribute_db.data.module_data.twitter_campaigns.campaigns = [
            TwitterCampaign(**campaign)
        ]

        # Modify the consensus veolas power to force consensus
        self.behaviour.params.tweet_consensus_veolas = 0

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
        gen = self.mock_campaign_validation_preparation._pre_task()

        calls = test_case.logger_message
        self.mock_campaign_validation_preparation.logger.info.assert_has_calls(
            calls, any_order=True
        )

        with pytest.raises(StopIteration) as exception_info:
            while True:
                next(gen)

        updates, event = exception_info.value.value
        return updates, event


class TestCampaignValidationPreparation(BaseCampaignValidationPreparationTest):
    """Test the CampaignValidationPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            CampaignValidationTestCase(
                name="Proposed to voting",
                campaign=PROPOSED_TO_VOTING_CAMPAIGN,
                campaign_validation_preparation_class=CampaignValidationPreparation,
                exception_message=(
                    {},
                    Event.CAMPAIGN_VALIDATION.value,
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
                    {},
                    Event.CAMPAIGN_VALIDATION.value,
                ),
                logger_message=[],
                has_updates=True,
                end_status="void",
                proposer_verified=False,
            ),
            CampaignValidationTestCase(
                name="Voting to void",
                campaign=VOTING_TO_VOID_CAMPAIGN,
                campaign_validation_preparation_class=CampaignValidationPreparation,
                exception_message=(
                    {},
                    Event.CAMPAIGN_VALIDATION.value,
                ),
                logger_message=[],
                has_updates=True,
                end_status="void",
                proposer_verified=True,
            ),
            CampaignValidationTestCase(
                name="Voting to scheduled",
                campaign=VOTING_TO_SCHEDULED_CAMPAIGN,
                campaign_validation_preparation_class=CampaignValidationPreparation,
                exception_message=(
                    {},
                    Event.CAMPAIGN_VALIDATION.value,
                ),
                logger_message=[],
                has_updates=True,
                end_status="scheduled",
                proposer_verified=True,
            ),
            CampaignValidationTestCase(
                name="Scheduled to live",
                campaign=SCHEDULED_TO_LIVE_CAMPAIGN,
                campaign_validation_preparation_class=CampaignValidationPreparation,
                exception_message=(
                    {},
                    Event.CAMPAIGN_VALIDATION.value,
                ),
                logger_message=[],
                has_updates=True,
                end_status="live",
                proposer_verified=True,
            ),
            CampaignValidationTestCase(
                name="Live to ended",
                campaign=LIVE_TO_ENDED_CAMPAIGN,
                campaign_validation_preparation_class=CampaignValidationPreparation,
                exception_message=(
                    {},
                    Event.CAMPAIGN_VALIDATION.value,
                ),
                logger_message=[],
                has_updates=True,
                end_status="ended",
                proposer_verified=True,
            ),
            CampaignValidationTestCase(
                name="Ended to ended",
                campaign=ENDED_TO_ENDED_CAMPAIGN,
                campaign_validation_preparation_class=CampaignValidationPreparation,
                exception_message=(
                    {},
                    Event.CAMPAIGN_VALIDATION.value,
                ),
                logger_message=[],
                has_updates=False,
                end_status="ended",
                proposer_verified=True,
            ),
        ],
        ids=lambda x: x.name,
    )
    @patch(
        "packages.valory.skills.decision_making_abci.tasks.campaign_validation_preparation.CampaignValidationPreparation.is_contract"
    )
    def test__pre_task(
        self,
        mock_is_contract,
        test_case: CampaignValidationTestCase,
    ):
        """Test the _pre_task method."""
        mock_is_contract.return_value = {"is_contract": False}
        self.set_up(test_case.campaign)
        self.create_tweet_validation_object(
            test_case.campaign_validation_preparation_class
        )
        updates, event = self._pre_task_base_test(test_case)

        assert (updates, event) == test_case.exception_message
        campaign = self.mock_campaign_validation_preparation.context.contribute_db.data.module_data.twitter_campaigns.campaigns[
            0
        ]

        assert campaign.proposer.verified is test_case.proposer_verified
        assert campaign.status == test_case.end_status
