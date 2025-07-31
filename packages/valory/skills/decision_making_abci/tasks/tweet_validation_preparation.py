# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2025 Valory AG
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

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.signature_validation import (
    SignatureValidationMixin,
)
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


CENTAUR_ID = "2"


class TweetValidationPreparation(TaskPreparation, SignatureValidationMixin):
    """TweetValidationPreparation"""

    task_name = "scheduled_tweet"
    task_event = Event.TWEET_VALIDATION.value

    def check_extra_conditions(self):
        """Validate Twitter credentials"""
        yield
        secrets = self.params.centaur_id_to_secrets[CENTAUR_ID]["twitter"]

        if sorted(secrets.keys()) != sorted(
            ["consumer_key", "consumer_secret", "access_token", "access_secret"]
        ):
            return False

        return True

    def _pre_task(self):
        """Preparations before running the task"""
        updates = {}

        for tweet in self.module_data.scheduled_tweet.tweets:
            tweet_text = tweet.text if isinstance(tweet.text, str) else tweet.text[0]

            self.logger.info(f"Checking tweet proposal: {tweet_text}")

            # Ignore posted tweets
            if tweet.posted:
                self.logger.info("The tweet has been posted already")
                continue

            # Ignore already processed proposals
            if tweet.proposer.verified is not None:
                self.logger.info("The proposal has been already verified")
                continue

            # Verify proposer signature
            message = f"I am signing a message to verify that I propose a tweet starting with {tweet_text[:10]}"
            is_valid = yield from self.validate_signature(
                message,
                tweet.proposer.address,
                tweet.proposer.signature,
            )
            self.logger.info(f"Is the proposer signature valid? {is_valid}")

            tweet.proposer.verified = is_valid

            yield from self.context.contribute_db.update_module_data(
                self.context.contribute_db.data.module_data
            )

        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        yield
        self.behaviour.context.logger.info("Nothing to do")
        return {}, None
