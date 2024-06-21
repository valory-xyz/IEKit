import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest

from packages.valory.skills.decision_making_abci.models import DEFAULT_PROMPT, SHORTENER_PROMPT
from packages.valory.skills.decision_making_abci.tasks.llm_preparation import LLMPreparation
from packages.valory.skills.decision_making_abci.tests import centaur_configs

DUMMY_CENTAURS_DATA = [
    centaur_configs.ENABLED_CENTAUR,
    centaur_configs.DISABLED_CENTAUR,
]

class TestLLMPreparation(unittest.TestCase):
    def setUp(self):
        self.behaviour = MagicMock()
        self.behaviour.params = MagicMock()
        self.behaviour.context.logger = MagicMock()
        self.behaviour.state = {}
        self.behaviour.context.ceramic_db = MagicMock()
        self.synchronized_data = MagicMock()
        self.synchronized_data.centaurs_data = DUMMY_CENTAURS_DATA
        self.synchronized_data.current_centaur_index = 0

        # Create an instance of LLMPreparation
        self.mock_llm_preparation = LLMPreparation(datetime.now(timezone.utc), self.behaviour, self.synchronized_data)

    @patch('packages.valory.skills.decision_making_abci.tasks.llm_preparation.DailyTweetPreparation')
    @patch('packages.valory.skills.decision_making_abci.tasks.llm_preparation.DailyOrbisPreparation')
    def test_check_extra_conditions_no_daily_tweet_preparation_or_daily_orbis_preparation(self, mock_daily_tweet_preparation, mock_daily_orbis_preparation):
        mock_daily_tweet_preparation.check_conditions.return_value = False
        mock_daily_orbis_preparation.check_conditions.return_value = False
        gen = self.mock_llm_preparation.check_extra_conditions()
        assert next(gen) == None
        with pytest.raises(StopIteration):
             self.assertFalse(next(gen))

    @patch('packages.valory.skills.decision_making_abci.tasks.llm_preparation.DailyTweetPreparation')
    @patch('packages.valory.skills.decision_making_abci.tasks.llm_preparation.DailyOrbisPreparation')
    def test_check_extra_conditions_daily_tweet_preparation(self, mock_daily_tweet_preparation, mock_daily_orbis_preparation):
        mock_daily_tweet_preparation.check_conditions.return_value = True
        mock_daily_orbis_preparation.check_conditions.return_value = False
        gen = self.mock_llm_preparation.check_extra_conditions()
        assert next(gen) == None
        with pytest.raises(StopIteration):
             self.assertTrue(next(gen))

    @patch('packages.valory.skills.decision_making_abci.tasks.llm_preparation.DailyTweetPreparation')
    @patch('packages.valory.skills.decision_making_abci.tasks.llm_preparation.DailyOrbisPreparation')
    def test_check_extra_conditions_daily_tweet_preparation(self, mock_daily_tweet_preparation, mock_daily_orbis_preparation):
        mock_daily_tweet_preparation.check_conditions.return_value = False
        mock_daily_orbis_preparation.check_conditions.return_value = True
        gen = self.mock_llm_preparation.check_extra_conditions()
        assert next(gen) == None
        with pytest.raises(StopIteration):
             self.assertTrue(next(gen))

    def test__pre_task_updates_reprompt_false(self):
        self.mock_llm_preparation.params.prompt_template = DEFAULT_PROMPT
        gen = self.mock_llm_preparation._pre_task()
        mock_current_centaur = self.mock_llm_preparation.synchronized_data.centaurs_data[self.mock_llm_preparation.synchronized_data.current_centaur_index]
        assert next(gen) == None
        with pytest.raises(StopIteration):
            assert next(gen) == {
                "llm_results": [],
                "llm_prompt_templates": [self.mock_llm_preparation.params.prompt_template],
                "llm_values":
                    [
                        {
                            "memory": "\n".join(mock_current_centaur["memory"]),
                            "n_chars": str(self.mock_llm_preparation.get_max_chars()),
                        }
                    ],
                "re_prompt_attempts": 0,
            }, self.mock_llm_preparation.task_event

    def test__pre_task_updates_reprompt_true(self):
        self.mock_llm_preparation.params.shortener_prompt_template = SHORTENER_PROMPT
        gen = self.mock_llm_preparation._pre_task(reprompt=True)
        assert next(gen) == None
        with pytest.raises(StopIteration):
            assert next(gen) == {
                "llm_results": [],
                "llm_prompt_templates": [self.mock_llm_preparation.params.shortener_prompt_template],
                "llm_values":
                    [
                        {
                            "text": self.mock_llm_preparation.synchronized_data.llm_results[0],
                            "n_chars": str(self.mock_llm_preparation.get_max_chars()),
                        }
                    ],
                "re_prompt_attempts": self.mock_llm_preparation.synchronized_data.re_prompt_attempts + 1
            }, self.mock_llm_preparation.task_event

    def test__post_task(self):
        gen = self.mock_llm_preparation._post_task()
        self.mock_llm_preparation.synchronized_data.llm_results = ["mock llm result"]
        mock_current_centaur = self.mock_llm_preparation.synchronized_data.centaurs_data[self.mock_llm_preparation.synchronized_data.current_centaur_index]
        mock_tweet = self.mock_llm_preparation.synchronized_data.llm_results[0] + (
            f" Created by {mock_current_centaur['name']} - see launchcentaurs.com"
        )
        print(mock_tweet)
        with pytest.raises(StopIteration):
            assert next(gen) == {
                "daily_tweet": {"text": mock_tweet},
            }, None

    def test__post_task_max_tweet_length_exceeded(self):
        gen = self.mock_llm_preparation._post_task()
        self.mock_llm_preparation.params.shortener_prompt_template = SHORTENER_PROMPT
        self.mock_llm_preparation.synchronized_data.re_prompt_attempts = 0
        self.mock_llm_preparation.synchronized_data.llm_results = ["Mock tweet that exceeds MAX_TWEET_LENGTH: mockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmock"]
        assert next(gen) == None
        with pytest.raises(StopIteration):
            assert next(gen) == {
                "llm_results": [],
                "llm_prompt_templates": [self.mock_llm_preparation.params.shortener_prompt_template],
                "llm_values":
                    [
                        {
                            "text": self.mock_llm_preparation.synchronized_data.llm_results[0],
                            "n_chars": str(self.mock_llm_preparation.get_max_chars()),
                        }
                    ],
                "re_prompt_attempts": self.mock_llm_preparation.synchronized_data.re_prompt_attempts + 1
            }, self.mock_llm_preparation.task_event
            self.assertCalledWith(self.mock_llm_preparation.logger.info, "Re-promting")

    def test__post_task_max_tweet_length_exceeded(self):
        gen = self.mock_llm_preparation._post_task()
        self.mock_llm_preparation.synchronized_data.re_prompt_attempts = 2
        self.mock_llm_preparation.synchronized_data.llm_results = ["Mock tweet that exceeds MAX_TWEET_LENGTH: mockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmock"]
        mock_tweet = self.mock_llm_preparation.synchronized_data.llm_results[0]
        assert next(gen) == None
        with pytest.raises(StopIteration):
            assert next(gen) == {
            "daily_tweet": {"text": self.mock_llm_preparation.trim_tweet(mock_tweet)},
        },  None

            self.assertCalledWith(self.mock_llm_preparation.logger.info, "Trimming the tweet")

    def test_get_max_chars(self):
        self.assertEqual(self.mock_llm_preparation.get_max_chars(), 225)
    def test_trim_tweet(self):
        mock_tweet = "Mock tweet that exceeds MAX_TWEET_LENGTH: mockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmock"
        mock_returned_tweet = "Mock tweet that exceeds MAX_TWEET_LENGTH: mockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmockmock"
        self.assertEqual(self.mock_llm_preparation.trim_tweet(mock_tweet), mock_returned_tweet)