# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
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

"""This package contains the logic for task preparations."""
from twitter_text import parse_tweet

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)
from packages.valory.skills.decision_making_abci.tasks.twitter_preparation import (
    DailyTweetPreparation,
)
from packages.valory.skills.decision_making_abci.tasks.write_stream_preparation import (
    DailyOrbisPreparation,
)


MAX_TWEET_LENGTH = 280
TWITTER_URL_LEN = 23  # all urls are changed to be 23 chars
MAX_REPROMPTS = 2


class LLMPreparation(TaskPreparation):
    """LLMPreparation"""

    task_name = "llm"
    task_event = Event.LLM.value

    def check_extra_conditions(self):
        """Check extra conditions"""
        yield

        # This task should only be run if Twitter and Orbis task are going to be run
        run_daily_tweet = yield from DailyTweetPreparation(
            self.synchronized_data,
            self.params,
            self.logger,
            self.now_utc,
            self.behaviour,
        ).check_conditions()

        run_daily_orbis = yield from DailyOrbisPreparation(
            self.synchronized_data,
            self.params,
            self.logger,
            self.now_utc,
            self.behaviour,
        ).check_conditions()

        if not run_daily_tweet and not run_daily_orbis:
            return False

        return True

    def _pre_task(self, reprompt: bool = False):
        """Preparations before running the task"""
        yield
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]

        llm_values = (
            [
                {
                    "text": self.synchronized_data.llm_results[0],
                    "n_chars": str(self.get_max_chars()),
                }
            ]
            if reprompt
            else [
                {
                    "memory": "\n".join(current_centaur["memory"]),
                    "n_chars": str(self.get_max_chars()),
                }
            ]
        )

        task_data = {
            "llm_results": [],  # clear previous results
            "llm_prompt_templates": [self.params.shortener_prompt_template]
            if reprompt
            else [self.params.prompt_template],
            "llm_values": llm_values,
            "re_prompt_attempts": 0
            if not reprompt
            else self.synchronized_data.re_prompt_attempts + 1,
        }
        return task_data, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]

        base_tweet = self.synchronized_data.llm_results[0]
        last_sentence = (
            f" Created by {current_centaur['name']} - see launchcentaurs.com"
        )
        tweet = base_tweet + last_sentence
        tweet_len = parse_tweet(tweet).asdict()["weightedLength"]

        # Re-prompt
        if tweet_len > MAX_TWEET_LENGTH:
            self.logger.info("The tweet is too long")
            if self.synchronized_data.re_prompt_attempts <= MAX_REPROMPTS:
                self.logger.info("Re-prompting")
                updates, event = yield from self._pre_task(reprompt=True)
                return updates, event
            else:  # hard-trim
                self.logger.info("Trimming the tweet")
                tweet = self.trim_tweet(tweet)

        updates = {
            "daily_tweet": tweet,
        }
        return updates, None

    def get_max_chars(self):
        """Get max number of characters in the LLM response"""
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]

        # Tweets include the following last sentence:
        last_sentence = f" Created by {current_centaur['name']} - see "  # we removed the launchcentaurs.com url from here as it always is TWITTER_URL_LEN long
        max_response_chars = MAX_TWEET_LENGTH - (len(last_sentence) + TWITTER_URL_LEN)
        return max_response_chars

    def trim_tweet(self, tweet):
        """Trim tweet"""
        while parse_tweet(tweet).asdict()["weightedLength"] > MAX_TWEET_LENGTH:
            tweet = tweet[:-10]  # trim 10 chars every iteration
        return tweet
