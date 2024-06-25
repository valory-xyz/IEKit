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

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.tweet_validation_preparation import (
    TweetValidationPreparation,
)


DUMMY_CENTAURS_DATA = [
    {
        "id": "4e77a3b1-5762-4782-830e-0e56c6c05c6f",
        "name": "Dummy Centaur",
        "configuration": {
            "plugins": {
                "daily_tweet": {
                    "daily": True,
                    "enabled": True,
                    "last_run": None,
                    "run_hour_utc": datetime.utcnow().hour,
                },
                "scheduled_tweet": {"daily": False, "enabled": True},
                "daily_orbis": {
                    "daily": True,
                    "enabled": True,
                    "last_run": None,
                    "run_hour_utc": datetime.utcnow().hour,
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


class TestTweetValidationPreparation(unittest.TestCase):
    """Test the WeekInOlasCreatePreparation class."""

    def setUp(self):
        """Set up the tests."""
        self.behaviour = MagicMock()
        self.synchronized_data = MagicMock()
        self.mock_tweet_validation_preparation = TweetValidationPreparation(
            datetime.now(timezone.utc), self.behaviour, self.synchronized_data
        )
        self.mock_tweet_validation_preparation.logger = MagicMock()

    def test_check_extra_conditions(self):
        """Test the check_extra_conditions method."""
        gen = self.mock_tweet_validation_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertTrue(next(gen))

    def test_check_extra_conditions_incorrect_centaur_id(self):
        """Test the check_extra_conditions method with incorrect centaur id."""
        self.mock_tweet_validation_preparation.synchronized_data.current_centaur_index = (
            None
        )
        gen = self.mock_tweet_validation_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertFalse(next(gen))

    def test_check_extra_conditions_not_twitter_on_centaur_id_to_secrets(self):
        """Test the check_extra_conditions method when 'twitter' not in centaur id to secrets."""
        self.mock_tweet_validation_preparation.params.centaur_id_to_secrets = {
            "dummy_data": "dummy_data"
        }
        gen = self.mock_tweet_validation_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertFalse(next(gen))

    def test_check_extra_conditions_secrets_not_match(self):
        """Test the check_extra_conditions method when secrets doesn't match."""
        self.mock_tweet_validation_preparation.params.centaur_id_to_secrets = {
            "dummy_data": "dummy_data"
        }
        gen = self.mock_tweet_validation_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration):
            self.assertFalse(next(gen))

    @patch(
        "packages.valory.skills.decision_making_abci.tasks.tweet_validation_preparation.TweetValidationPreparation.is_contract"
    )
    def test__pre_task(self, mock_is_contract):
        """Test the _pre_task method."""
        mock_is_contract.return_value = {"is_contract": True}
        self.mock_tweet_validation_preparation.synchronized_data.centaurs_data = (
            DUMMY_CENTAURS_DATA
        )
        self.mock_tweet_validation_preparation.synchronized_data.current_centaur_index = (
            0
        )
        gen = self.mock_tweet_validation_preparation._pre_task()
        next(gen)
        calls = [
            call("Checking tweet proposal: My agreed tweet: dummy"),
            call("The tweet has been posted already"),
            call("The proposal has been already verified"),
        ]
        self.mock_tweet_validation_preparation.logger.info.assert_has_calls(
            calls, any_order=True
        )
        with pytest.raises(StopIteration) as excinfo:
            next(gen)
        assert str(
            (
                {
                    "centaurs_data": self.mock_tweet_validation_preparation.synchronized_data.centaurs_data,
                    "has_centaurs_changes": True,
                },
                Event.TWEET_VALIDATION.value,
            )
        ) in str(excinfo.value)

    def test__post_task(self):
        """Test the _post_task method."""
        gen = self.mock_tweet_validation_preparation._post_task()
        next(gen)
        with pytest.raises(
            StopIteration,
        ) as excinfo:
            next(gen)
        assert str(({}, None)) in str(excinfo.value)
