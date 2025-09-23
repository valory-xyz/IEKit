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
"""Test tweet validation preparation tasks."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock, call, patch

import pytest

from packages.valory.skills.contribute_db_abci.contribute_models import ServiceTweet
from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.tweet_validation_preparation import (
    TweetValidationPreparation,
)
from packages.valory.skills.decision_making_abci.tests import centaur_configs
from packages.valory.skills.decision_making_abci.tests.centaur_configs import (
    DISABLED_CENTAUR,
    ENABLED_CENTAUR,
)


@dataclass
class TweetValidationTestCase:
    """TweetValidationTestCase"""

    name: str
    tweet_validation_preparation_class: Any
    exception_message: Any
    centaur_configs: Optional[Any] = None
    logger_message: Optional[Any] = None


DUMMY_CENTAURS_DATA = [ENABLED_CENTAUR, DISABLED_CENTAUR]
DUMMY_CENTAURS_DATA_B = [
    {
        "id": "4e77a3b1-5762-4782-830e-0e56c6c05c6f",
        "name": "Dummy Centaur",
        "configuration": {
            "plugins": {
                "daily_tweet": {
                    "daily": True,
                    "enabled": True,
                    "last_run": None,
                    "run_hour_utc": datetime.now(tz=timezone.utc).hour,
                },
                "scheduled_tweet": {"daily": False, "enabled": True},
                "daily_orbis": {
                    "daily": True,
                    "enabled": True,
                    "last_run": None,
                    "run_hour_utc": datetime.now(tz=timezone.utc).hour,
                },
            }
        },
        "plugins_data": {
            "daily_orbis": {},
            "daily_tweet": {},
            "scheduled_tweet": {
                "tweets": [
                    {
                        "request_id": "dummy_id_1",
                        "posted": True,
                        "proposer": {
                            "address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
                            "signature": "0x37904bcb8b6e11ae894856c1d722209397e548219f000fc172f9a58a064718dd634fa00ace138383dfe807f479a0cf22588edb3fd61bfea2f85378a7513c6cc41c",
                            "verified": None,
                        },
                        "text": "My agreed tweet: dummy",
                        "voters": [
                            {"0x6c6766E04eF971367D27E720d1d161a9B495D647": 0},
                            {"0x7885d121ed8Aa3c919AA4d407F197Dc29E33cAf0": 0},
                        ],
                        "executionAttempts": [],
                    },
                    {
                        "request_id": "dummy_id_1",
                        "posted": False,
                        "proposer": {
                            "address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
                            "signature": "0x37904bcb8b6e11ae894856c1d722209397e548219f000fc172f9a58a064718dd634fa00ace138383dfe807f479a0cf22588edb3fd61bfea2f85378a7513c6cc41c",
                            "verified": True,
                        },
                        "text": "My agreed tweet: dummy",
                        "voters": [
                            {"0x6c6766E04eF971367D27E720d1d161a9B495D647": 0},
                            {"0x7885d121ed8Aa3c919AA4d407F197Dc29E33cAf0": 0},
                        ],
                        "executionAttempts": [],
                    },
                    {
                        "request_id": "dummy_id_2",
                        "posted": False,
                        "proposer": {
                            "address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
                            "signature": "0x37904bcb8b6e11ae894856c1d722209397e548219f000fc172f9a58a064718dd634fa00ace138383dfe807f479a0cf22588edb3fd61bfea2f85378a7513c6cc41c",
                            "verified": None,
                        },
                        "text": "My agreed tweet: dummy",
                        "voters": [
                            {"0x6c6766E04eF971367D27E720d1d161a9B495D647": 0},
                            {"0x7885d121ed8Aa3c919AA4d407F197Dc29E33cAf0": 0},
                        ],
                        "executionAttempts": [],
                    },
                ]
            },
        },
        "actions": [
            {
                "timestamp": 1686737751798,
                "description": "added a memory",
                "actorAddress": "0x18C6A47AcA1c6a237e53eD2fc3a8fB392c97169b",
                "commitId": "bagcqcera7ximz76vx25j5qzfrkvedklwcw732xnyuiycd46rgokrbfkzrx4a",
            },
        ],
        "members": [
            {"address": "0x6c6766E04eF971367D27E720d1d161a9B495D647", "ownership": 0},
            {"address": "0x7885d121ed8Aa3c919AA4d407F197Dc29E33cAf0", "ownership": 1},
        ],
        "purpose": "A testing centaur.",
        "memory": [
            "dummy memory 1",
            "dummy memory 2",
        ],
        "messages": [
            {
                "member": "0x18C6A47AcA1c6a237e53eD2fc3a8fB392c97169b",
                "content": "This is an example of dummy content",
                "timestamp": 1686737815115,
            }
        ],
    },
]

SCHEDULED_TWEETS = [
    {
        "posted": True,
        "proposer": {
            "address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
            "signature": "0x37904bcb8b6e11ae894856c1d722209397e548219f000fc172f9a58a064718dd634fa00ace138383dfe807f479a0cf22588edb3fd61bfea2f85378a7513c6cc41c",
            "verified": None,
        },
        "text": ["My agreed tweet: dummy"],
        "media_hashes": [],
        "voters": [],
        "action_id": "",
        "request_id": "00000000-0000-0000-0000-000000000000",
        "executionAttempts": [],
        "createdDate": 1734102210.160343,
    },
    {
        "posted": False,
        "proposer": {
            "address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
            "signature": "0x37904bcb8b6e11ae894856c1d722209397e548219f000fc172f9a58a064718dd634fa00ace138383dfe807f479a0cf22588edb3fd61bfea2f85378a7513c6cc41c",
            "verified": True,
        },
        "text": ["My agreed tweet: dummy"],
        "media_hashes": [],
        "voters": [],
        "action_id": "",
        "executionAttempts": [],
        "createdDate": 1734102210.160343,
        "request_id": "00000000-0000-0000-0000-000000000000",
    },
    {
        "posted": False,
        "proposer": {
            "address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
            "signature": "0x37904bcb8b6e11ae894856c1d722209397e548219f000fc172f9a58a064718dd634fa00ace138383dfe807f479a0cf22588edb3fd61bfea2f85378a7513c6cc41c",
            "verified": None,
        },
        "text": ["My agreed tweet: dummy"],
        "media_hashes": [],
        "voters": [],
        "action_id": "",
        "request_id": "00000000-0000-0000-0000-000000000000",
        "createdDate": 1734102210.160343,
        "executionAttempts": [],
    },
]


class BaseTweetValidationPreparationTest:
    """Base class for TweetValidationPreparation tests."""

    def set_up(self):
        """Set up the class."""
        self.behaviour = MagicMock()
        self.synchronized_data = MagicMock()
        self.context = MagicMock()

    def create_tweet_validation_object(self, tweet_validation_preparation_class):
        """Create the tweet validation object."""
        self.mock_tweet_validation_preparation = tweet_validation_preparation_class(
            datetime.now(timezone.utc),
            self.behaviour,
            self.synchronized_data,
            self.context,
        )

        self.mock_tweet_validation_preparation.behaviour.context.logger.info = (
            MagicMock()
        )
        self.mock_tweet_validation_preparation.logger.info = MagicMock()

    def check_extra_conditions_test(self, test_case: TweetValidationTestCase):
        """Test the check_extra_conditions method."""
        gen = self.mock_tweet_validation_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = test_case.exception_message
        assert str(exception_message) in str(excinfo.value)

    def _post_task_base_test(self, test_case: TweetValidationTestCase):
        """Test the _post_task method."""
        gen = self.mock_tweet_validation_preparation._post_task()

        next(gen)

        with pytest.raises(StopIteration) as excinfo:
            next(gen)
        self.mock_tweet_validation_preparation.behaviour.context.logger.info.assert_called_with(
            test_case.logger_message
        )
        exception_message = test_case.exception_message
        assert str(exception_message) in str(excinfo.value)

    def _pre_task_base_test(self, test_case: TweetValidationTestCase):
        """Test the _pre_task method."""
        self.mock_tweet_validation_preparation.synchronized_data.centaurs_data = (
            DUMMY_CENTAURS_DATA_B
        )
        self.mock_tweet_validation_preparation.synchronized_data.current_centaur_index = (
            0
        )
        gen = self.mock_tweet_validation_preparation._pre_task()
        next(gen)
        calls = test_case.logger_message
        self.mock_tweet_validation_preparation.logger.info.assert_has_calls(
            calls, any_order=True
        )
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = test_case.exception_message
        assert str(exception_message) in str(excinfo.value)


class TestTweetValidationPreparation(BaseTweetValidationPreparationTest):
    """Test the TweetValidationPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            TweetValidationTestCase(
                name="Centaur ID to secrets missing id",
                tweet_validation_preparation_class=TweetValidationPreparation,
                exception_message=False,
                centaur_configs=centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ID,
            ),
            TweetValidationTestCase(
                name="Centaur ID to secrets missing twitter",
                tweet_validation_preparation_class=TweetValidationPreparation,
                exception_message=False,
                centaur_configs=centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_TWITTER,
            ),
            TweetValidationTestCase(
                name="Centaur ID to secrets missing twitter key",
                tweet_validation_preparation_class=TweetValidationPreparation,
                exception_message=False,
                centaur_configs=centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_TWITTER_KEY,
            ),
            TweetValidationTestCase(
                name="Happy Path",
                tweet_validation_preparation_class=TweetValidationPreparation,
                exception_message=True,
                centaur_configs=centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
            ),
        ],
        ids=lambda x: x.name,
    )
    def test_check_extra_conditions(self, test_case: TweetValidationTestCase):
        """Test the check_extra_conditions method when the centaur id is not in centaur id to secrets."""
        self.set_up()
        self.create_tweet_validation_object(
            test_case.tweet_validation_preparation_class
        )
        self.mock_tweet_validation_preparation.params.centaur_id_to_secrets = (
            test_case.centaur_configs
        )
        gen = self.mock_tweet_validation_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = test_case.exception_message
        assert str(exception_message) in str(excinfo.value)

    @pytest.mark.parametrize(
        "test_case",
        [
            TweetValidationTestCase(
                name="Happy Path",
                tweet_validation_preparation_class=TweetValidationPreparation,
                exception_message=({}, None),
                logger_message="Nothing to do",
            )
        ],
    )
    def test__post_task(self, test_case: TweetValidationTestCase):
        """Test the _post_task method."""
        self.set_up()
        self.create_tweet_validation_object(
            test_case.tweet_validation_preparation_class
        )
        self._post_task_base_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TweetValidationTestCase(
                name="Happy Path",
                tweet_validation_preparation_class=TweetValidationPreparation,
                exception_message=(
                    {},
                    Event.TWEET_VALIDATION.value,
                ),
                logger_message=[
                    call("Checking tweet proposal: My agreed tweet: dummy"),
                    call("The tweet has been posted already"),
                    call("The proposal has been already verified"),
                ],
            )
        ],
    )
    @patch(
        "packages.valory.skills.decision_making_abci.tasks.tweet_validation_preparation.TweetValidationPreparation.is_contract"
    )
    def test__pre_task(
        self,
        mock_is_contract,
        test_case: TweetValidationTestCase,
    ):
        """Test the _pre_task method."""
        mock_is_contract.return_value = {"is_contract": True}
        self.set_up()
        self.create_tweet_validation_object(
            test_case.tweet_validation_preparation_class
        )

        self.mock_tweet_validation_preparation.module_data.scheduled_tweet.tweets = [
            ServiceTweet(**tweet) for tweet in SCHEDULED_TWEETS
        ]
        gen = self.mock_tweet_validation_preparation._pre_task()
        next(gen)
        calls = test_case.logger_message
        self.mock_tweet_validation_preparation.logger.info.assert_has_calls(
            calls, any_order=True
        )
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = test_case.exception_message
        assert str(exception_message) in str(excinfo.value)
