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

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


TWEET_CONSENSUS_WVEOLAS_WEI = 2e6 * 1e18  # 2M wveOLAS to wei


class TwitterPreparation(TaskPreparation):
    """TwitterPreparation"""

    def check_extra_conditions(self):
        """Validate Twitter credentials for the current centaur"""
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]
        centaur_id_to_secrets = self.params.centaur_id_to_secrets

        if current_centaur["id"] not in centaur_id_to_secrets:
            return False

        if "twitter" not in centaur_id_to_secrets[current_centaur["id"]]:
            return False

        secrets = centaur_id_to_secrets[current_centaur["id"]]["twitter"]

        if sorted(secrets.keys()) != sorted(
            ["consumer_key", "consumer_secret", "access_token", "access_secret"]
        ):
            return False

        return True

    def _pre_task(self):
        """Preparations before running the task"""
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]

        write_data = [
            {
                "text": self.get_tweet(),
                "credentials": self.params.centaur_id_to_secrets[current_centaur["id"]][
                    "twitter"
                ],
            }
        ]

        updates = {
            "write_data": write_data,
        }

        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        centaurs_data = self.synchronized_data.centaurs_data
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]

        # Update Twitter action
        tweet_ids = self.synchronized_data.tweet_ids
        timestamp = self.now_utc.timestamp()

        twitter_action = {
            "actorAddress": self.params.ceramic_did_str,
            "outputUrl": f"https://twitter.com/launchcentaurs/status/{tweet_ids[0]}",
            "description": "posted to Twitter",
            "timestamp": timestamp,
        }

        if "actions" in current_centaur:
            current_centaur["actions"].append(twitter_action)
        else:
            current_centaur["actions"] = twitter_action

        updates = {"centaurs_data": centaurs_data, "has_centaurs_changes": True}

        return updates, None

    def get_tweet(self):
        """Get the tweet"""
        raise NotImplementedError


class DailyTweetPreparation(TwitterPreparation):
    """DailyTweetPreparation"""

    task_name = "daily_tweet"
    task_event = Event.DAILY_TWEET.value

    def get_tweet(self):
        """Get the tweet"""
        return self.synchronized_data.daily_tweet

    def _post_task(self):
        """Task postprocessing"""
        updates, event = super()._post_task()

        # Update the last run time
        centaurs_data = updates["centaurs_data"]
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]
        current_centaur["configuration"]["plugins"]["daily_tweet"][
            "last_run"
        ] = self.now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")

        updates["centaurs_data"] = centaurs_data

        return updates, event


class ScheduledTweetPreparation(TwitterPreparation):
    """ScheduledTweetPreparation"""

    task_name = "scheduled_tweet"
    task_event = Event.SCHEDULED_TWEET.value

    def _post_task(self):
        """Task postprocessing"""
        updates, event = super()._post_task()

        # Set the scheduled tweet as posted
        centaurs_data = updates["centaurs_data"]
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]
        pending_tweets = self.get_pending_tweets()
        tweet_ids = self.synchronized_data.tweet_ids
        if not pending_tweets:
            return updates, event

        tweet_id = tweet_ids[0]
        for j, tweet in enumerate(
            current_centaur["plugins_data"]["scheduled_tweet"]["tweets"]
        ):
            if pending_tweets[0]["request_id"] == tweet["request_id"]:
                current_centaur["plugins_data"]["scheduled_tweet"]["tweets"][j][
                    "posted"
                ] = True
                current_centaur["plugins_data"]["scheduled_tweet"]["tweets"][j][
                    "action_id"
                ] = f"https://twitter.com/launchcentaurs/status/{tweet_id}"  # even if the tweet does not belong to this account, Twitter resolves it correctly by id
                break

        updates["centaurs_data"] = centaurs_data

        return updates, event

    def get_tweet(self):
        """Get the tweet"""
        return self.get_pending_tweets()[0]["text"]

    def check_extra_conditions(self):
        """Check extra conditions"""
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]

        if not super().check_extra_conditions():
            return False

        if "scheduled_tweet" not in current_centaur["plugins_data"]:
            return False

        if "tweets" not in current_centaur["plugins_data"]["scheduled_tweet"]:
            return False

        if not isinstance(
            current_centaur["plugins_data"]["scheduled_tweet"]["tweets"], list
        ):
            return False

        for tweet in current_centaur["plugins_data"]["scheduled_tweet"]["tweets"]:
            if not all(
                field in tweet
                for field in ["execute", "posted", "request_id", "text", "voters"]
            ):
                return False

        if not self.get_pending_tweets():
            return False

        return True

    def get_pending_tweets(self):
        """Get not yet posted tweets that need to be posted"""
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]
        pending_tweets = [
            t
            for t in current_centaur["plugins_data"]["scheduled_tweet"]["tweets"]
            if not t["posted"] and t["execute"]
        ]
        agreed_pending_tweets = list(
            filter(
                lambda t: self.check_tweet_consensus(t["voters"]),
                pending_tweets,
            )
        )
        return agreed_pending_tweets

    def check_tweet_consensus(self, voters: dict):
        """Check whether users agree on posting"""
        voting_power = sum([int(list(v.values())[0]) for v in voters])
        return voting_power >= TWEET_CONSENSUS_WVEOLAS_WEI
