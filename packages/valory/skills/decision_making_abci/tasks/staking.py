# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


class StakingPreparation(TaskPreparation):
    """StakingPreparation"""

    task_name = "staking_preparation"

    def check_extra_conditions(self):
        """Check whether it is time to call the checkpoint"""

        # This check is common for both the activity tracking and the checkpoint
        # because we want to ensure we always call activity tracking just right before we call the checkpoint
        yield

        # If too much time has passed since last execution, we run the staking skill
        minutes_since_last_run = (self.now_utc - self.last_run).total_seconds() / 60
        if minutes_since_last_run > self.params.checkpoint_threshold_minutes:
            return True

        # If the epoch is about to end, we run the staking skill
        # TODO

        return False

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        updates = {}
        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        centaurs_data = self.synchronized_data.centaurs_data
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]

        # Update the last run time
        current_centaur["configuration"]["plugins"][self.task_name][
            "last_run"
        ] = self.now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")

        updates = {"centaurs_data": centaurs_data, "has_centaurs_changes": True}
        yield
        return updates, None


class StakingActivityPreparation(StakingPreparation):
    """StakingActivityPreparation"""

    task_name = "staking_activiy"
    task_event = Event.STAKING_ACTIVITY.value

    def check_extra_conditions(self):
        """Check user staking threshold"""
        yield

        # If enough users have pending updates, we run the activity update
        pending_updates = self.count_pending_updates()
        if pending_updates > self.params.staking_activity_threshold:
            return True

        # If the checkpoint is about to be called and there's pending updates, we run the activity update
        if super().check_extra_conditions() and pending_updates > 0:
            return True

        return False

    def count_pending_updates(self) -> int:
        """Counts the number of staked users that need to be updated"""

        updates = 0

        # A staked user needs to be updated if they have sent at least a new tweet
        ceramic_db = self.context.ceramic_db
        centaurs_data = self.synchronized_data.centaurs_data
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]

        last_processed_tweet = int(
            current_centaur["configuration"]["plugins"][self.task_name][
                "last_processed_tweet"
            ]
        )

        for user in ceramic_db.users:
            sorted_tweet_ids = list(
                sorted([int(i) for i in user.get("tweets", {}).keys()])
            )

            # No tweets
            if not sorted_tweet_ids:
                continue

            # If the latest tweet id is higher than the last processed tweet, it means this tweet is newer
            if sorted_tweet_ids[-1] > last_processed_tweet:
                updates += 1

        return updates


class StakingCheckpointPreparation(StakingPreparation):
    """StakingCheckpointPreparation"""

    task_name = "staking_checkpoint"
    task_event = Event.STAKING_CHECKPOINT.value
