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
"""Tests for the llm preparation tasks."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from packages.valory.skills.decision_making_abci.models import (
    DEFAULT_PROMPT,
    SHORTENER_PROMPT,
)
from packages.valory.skills.decision_making_abci.tasks.llm_preparation import (
    LLMPreparation,
)
from packages.valory.skills.decision_making_abci.tests import centaur_configs


DUMMY_CENTAURS_DATA = [
    centaur_configs.ENABLED_CENTAUR,
    centaur_configs.DISABLED_CENTAUR,
]

DUMMY_EXCEEDS_MAX_LENGTH_TWEET = "Dummy tweet that exceeds MAX_TWEET_LENGTH counted in blocks of 10 chars:        (00000000)(00000001)(00000002)(00000003)(00000004)(00000005)(00000006)(00000007)(00000008)(00000009)(00000010)(00000011)(00000012)(00000013)(00000014)(00000015)(00000016)(00000017)(00000018)(00000019)(00000020)(00000021)"


@dataclass
class CheckExtraConditionsTestCase:
    """Test case for check_extra_conditions."""

    mock_daily_tweet_preparation: Any
    mock_daily_orbis_preparation: Any


class BaseTestLLMPreparation:
    """Base class for testing LLMPreparation."""

    def set_up(self):
        """Set up the tests."""
        self.behaviour = MagicMock()
        self.behaviour.params = MagicMock()
        self.behaviour.context.logger = MagicMock()
        self.behaviour.state = {}
        self.behaviour.context.ceramic_db = MagicMock()
        self.synchronized_data = MagicMock()
        self.context = MagicMock()
        self.synchronized_data.centaurs_data = DUMMY_CENTAURS_DATA
        self.synchronized_data.current_centaur_index = 0

        # Create an instance of LLMPreparation
        self.mock_llm_preparation = LLMPreparation(
            datetime.now(timezone.utc),
            self.behaviour,
            self.synchronized_data,
            self.context,
        )

        self.mock_llm_preparation.logger.info = MagicMock()


class TestLLMPreparation(BaseTestLLMPreparation):
    """Test the LLMPreparation class."""

    @patch(
        "packages.valory.skills.decision_making_abci.tasks.llm_preparation.DailyTweetPreparation"
    )
    @patch(
        "packages.valory.skills.decision_making_abci.tasks.llm_preparation.DailyOrbisPreparation"
    )
    @pytest.mark.parametrize(
        "test_case",
        (
            CheckExtraConditionsTestCase(
                mock_daily_tweet_preparation=False,
                mock_daily_orbis_preparation=False,
            ),
            CheckExtraConditionsTestCase(
                mock_daily_tweet_preparation=True,
                mock_daily_orbis_preparation=False,
            ),
            CheckExtraConditionsTestCase(
                mock_daily_tweet_preparation=False,
                mock_daily_orbis_preparation=True,
            ),
        ),
    )
    def test_check_extra_conditions(
        self, mock_daily_tweet_preparation, mock_daily_orbis_preparation, test_case
    ) -> None:
        """Test check_extra_conditions with no daily tweet preparation nor daily orbis preparation."""
        self.set_up()
        mock_daily_tweet_preparation.check_conditions.return_value = (
            test_case.mock_daily_tweet_preparation
        )
        mock_daily_orbis_preparation.check_conditions.return_value = (
            test_case.mock_daily_orbis_preparation
        )
        gen = self.mock_llm_preparation.check_extra_conditions()
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)
        assert str(False) in str(excinfo.value)

    def test__pre_task_updates_reprompt_false(self):
        """Test _pre_task with reprompt=False."""
        self.set_up()
        self.mock_llm_preparation.params.prompt_template = DEFAULT_PROMPT
        gen = self.mock_llm_preparation._pre_task()
        mock_current_centaur = (
            self.mock_llm_preparation.synchronized_data.centaurs_data[
                self.mock_llm_preparation.synchronized_data.current_centaur_index
            ]
        )
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = {
            "llm_results": [],
            "llm_prompt_templates": [self.mock_llm_preparation.params.prompt_template],
            "llm_values": [
                {
                    "memory": "\n".join(mock_current_centaur["memory"]),
                    "n_chars": str(self.mock_llm_preparation.get_max_chars()),
                }
            ],
            "re_prompt_attempts": 0,
        }, self.mock_llm_preparation.task_event

        assert str(exception_message) in str(excinfo.value)

    def test__pre_task_updates_reprompt_true(self):
        """Test _pre_task with reprompt=True."""
        self.set_up()
        self.mock_llm_preparation.params.shortener_prompt_template = SHORTENER_PROMPT
        gen = self.mock_llm_preparation._pre_task(reprompt=True)
        next(gen)
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = {
            "llm_results": [],
            "llm_prompt_templates": [
                self.mock_llm_preparation.params.shortener_prompt_template
            ],
            "llm_values": [
                {
                    "text": self.mock_llm_preparation.synchronized_data.llm_results[0],
                    "n_chars": str(self.mock_llm_preparation.get_max_chars()),
                }
            ],
            "re_prompt_attempts": self.mock_llm_preparation.synchronized_data.re_prompt_attempts
            + 1,
        }, self.mock_llm_preparation.task_event

        assert str(exception_message) in str(excinfo.value)

    def test__post_task(self):
        """Test _post_task."""
        self.set_up()
        gen = self.mock_llm_preparation._post_task()
        self.mock_llm_preparation.synchronized_data.llm_results = ["mock llm result"]
        mock_current_centaur = (
            self.mock_llm_preparation.synchronized_data.centaurs_data[
                self.mock_llm_preparation.synchronized_data.current_centaur_index
            ]
        )
        mock_tweet = self.mock_llm_preparation.synchronized_data.llm_results[0] + (
            f" Created by {mock_current_centaur['name']} - see launchcentaurs.com"
        )
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = {
            "daily_tweet": {"text": mock_tweet},
        }, None

        assert str(exception_message) in str(excinfo.value)

    def test__post_task_max_tweet_length_exceeded(self):
        """Test _post_task with a tweet that exceeds the max tweet length."""
        self.set_up()
        gen = self.mock_llm_preparation._post_task()
        self.mock_llm_preparation.params.shortener_prompt_template = SHORTENER_PROMPT
        self.mock_llm_preparation.synchronized_data.re_prompt_attempts = 0
        self.mock_llm_preparation.synchronized_data.llm_results = [
            DUMMY_EXCEEDS_MAX_LENGTH_TWEET
        ]
        self.mock_llm_preparation.logger.info("The tweet is too long")
        next(gen)
        self.mock_llm_preparation.logger.info.assert_called_with("Re-prompting")
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = {
            "llm_results": [],
            "llm_prompt_templates": [
                self.mock_llm_preparation.params.shortener_prompt_template
            ],
            "llm_values": [
                {
                    "text": self.mock_llm_preparation.synchronized_data.llm_results[0],
                    "n_chars": str(self.mock_llm_preparation.get_max_chars()),
                }
            ],
            "re_prompt_attempts": self.mock_llm_preparation.synchronized_data.re_prompt_attempts
            + 1,
        }, self.mock_llm_preparation.task_event

        assert str(exception_message) in str(excinfo.value)

    def test__post_task_max_tweet_length_exceeded_max_retries(self):
        """Test _post_task with a tweet that exceeds the max tweet length."""
        self.set_up()
        gen = self.mock_llm_preparation._post_task()
        self.mock_llm_preparation.synchronized_data.re_prompt_attempts = 10
        self.mock_llm_preparation.synchronized_data.llm_results = [
            DUMMY_EXCEEDS_MAX_LENGTH_TWEET
        ]
        mock_tweet = self.mock_llm_preparation.synchronized_data.llm_results[0]
        mock_tweet_full = (
            mock_tweet + " Created by Dummy Centaur - see launchcentaurs.com"
        )
        self.mock_llm_preparation.logger.info("The tweet is too long")
        self.mock_llm_preparation.logger.info.asset_called_with("Trimming the tweet")
        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        exception_message = {
            "daily_tweet": {
                "text": self.mock_llm_preparation.trim_tweet(mock_tweet_full)
            },
        }, None
        assert str(exception_message) in str(excinfo.value)

    def test_get_max_chars(self):
        """Test get_max_chars."""
        self.set_up()
        assert self.mock_llm_preparation.get_max_chars() == 225

    def test_trim_tweet(self):
        """Test trim_tweet."""
        self.set_up()
        dummy_tweet = DUMMY_EXCEEDS_MAX_LENGTH_TWEET
        dummy_returned_tweet = "Dummy tweet that exceeds MAX_TWEET_LENGTH counted in blocks of 10 chars:        (00000000)(00000001)(00000002)(00000003)(00000004)(00000005)(00000006)(00000007)(00000008)(00000009)(00000010)(00000011)(00000012)(00000013)(00000014)(00000015)(00000016)(00000017)(00000018)(00000019)"
        assert self.mock_llm_preparation.trim_tweet(dummy_tweet) == dummy_returned_tweet
