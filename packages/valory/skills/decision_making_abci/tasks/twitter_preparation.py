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

from typing import Generator, Optional, cast

from packages.valory.contracts.veolas_delegation.contract import (
    VeOLASDelegationContract,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.signature_validation import (
    SignatureValidationMixin,
)
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


class TwitterPreparation(TaskPreparation):
    """TwitterPreparation"""

    def check_extra_conditions(self):
        """Validate Twitter credentials for the current centaur"""
        yield
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
        yield
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]

        tweet = self.get_tweet()

        write_data = [
            {
                "text": tweet["text"],
                "media_hashes": tweet.get("media_hashes", None),
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
        yield
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
        updates, event = yield from super()._post_task()

        # Update the last run time
        centaurs_data = updates["centaurs_data"]
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]
        current_centaur["configuration"]["plugins"]["daily_tweet"][
            "last_run"
        ] = self.now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")

        updates["centaurs_data"] = centaurs_data
        return updates, event


class ScheduledTweetPreparation(TwitterPreparation, SignatureValidationMixin):
    """ScheduledTweetPreparation"""

    task_name = "scheduled_tweet"
    task_event = Event.SCHEDULED_TWEET.value

    def __init__(self, now_utc, behaviour, synchronized_data) -> None:
        """Init"""
        super().__init__(now_utc, behaviour, synchronized_data)
        self.pending_tweets = []
        self.tweets_need_update = False
        self.updated_tweets = None

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        centaurs_data = self.synchronized_data.centaurs_data
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]

        updates = {}
        event = None

        if self.tweets_need_update:
            current_centaur["plugins_data"]["scheduled_tweet"][
                "tweets"
            ] = self.updated_tweets
            updates["centaurs_data"] = centaurs_data
            updates["has_centaurs_changes"] = True
            event = Event.FORCE_DB_UPDATE.value

        if self.pending_tweets:
            tweet = self.get_tweet()

            write_data = [
                {
                    "text": tweet["text"],
                    "media_hashes": tweet.get("media_hashes", None),
                    "credentials": self.params.centaur_id_to_secrets[
                        current_centaur["id"]
                    ]["twitter"],
                }
            ]

            updates["write_data"] = write_data
            event = self.task_event

        return updates, event

    def _post_task(self):
        """Task postprocessing"""
        if (
            self.synchronized_data.previous_decision_event
            == Event.FORCE_DB_UPDATE.value
        ):
            self.logger.info("Not running post_task because this was a force db update")
            return {}, None

        updates, event = yield from super()._post_task()

        # Set the scheduled tweet as posted
        centaurs_data = updates["centaurs_data"]
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]
        pending_tweets = self.get_pending_tweets()
        tweet_ids = self.synchronized_data.tweet_ids
        if not pending_tweets:
            self.logger.info("No tweets are pending to be published")
            return updates, event

        self.logger.info("There are tweets pending to be published")

        posted_tweet_id = pending_tweets[0]["request_id"]

        tweet_id = tweet_ids[0]
        for j, tweet in enumerate(
            current_centaur["plugins_data"]["scheduled_tweet"]["tweets"]
        ):
            if tweet["request_id"] == posted_tweet_id:
                current_centaur["plugins_data"]["scheduled_tweet"]["tweets"][j][
                    "posted"
                ] = True
                current_centaur["plugins_data"]["scheduled_tweet"]["tweets"][j][
                    "action_id"
                ] = f"https://twitter.com/launchcentaurs/status/{tweet_id}"  # even if the tweet does not belong to this account, Twitter resolves it correctly by id
                current_centaur["plugins_data"]["scheduled_tweet"]["tweets"][j][
                    "executionAttempts"
                ][-1]["verified"] = True
                break

        updates["centaurs_data"] = centaurs_data
        updates["has_centaurs_changes"] = True
        return updates, event

    def get_tweet(self):
        """Get the tweet"""
        return self.pending_tweets[0]

    def check_extra_conditions(self):
        """Check extra conditions"""
        if (
            self.synchronized_data.previous_decision_event
            == Event.FORCE_DB_UPDATE.value
        ):
            self.logger.info("Not running again because this was a force db update")
            return False

        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]

        proceed = yield from super().check_extra_conditions()
        if not proceed:
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
                field in tweet for field in ["posted", "request_id", "text", "voters"]
            ):
                return False

        self.pending_tweets = self.get_pending_tweets()
        if not self.pending_tweets and not self.tweets_need_update:
            self.logger.info(
                f"No pending tweets nor tweet votes to update:\npending_tweets={self.pending_tweets}\n\ntweets_need_update={self.tweets_need_update}"
            )
            return False

        return True

    def get_pending_tweets(self):
        """Get not yet posted tweets that need to be posted"""
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]

        pending_tweets = []
        for tweet in current_centaur["plugins_data"]["scheduled_tweet"]["tweets"]:
            self.logger.info(
                f"Checking tweet: {tweet['text']} {tweet.get('media_hashes', None)}"
            )

            # Ignore posted tweets
            if tweet["posted"]:
                self.logger.info("The tweet has been already posted")
                continue

            # Ignore unverified proposals
            if not tweet["proposer"]["verified"]:
                self.logger.info("The tweet proposer signature is not valid")
                continue

            # Ignore tweets not marked for posting
            if not tweet["executionAttempts"]:
                continue

            if tweet["executionAttempts"][-1]["verified"] is not None:
                self.logger.info("The tweet is not marked for execution")
                continue

            # At this point, the tweet is awaiting to be published [verified=None]

            # Ignore tweet with no voters
            if not tweet["voters"]:
                self.logger.info("The tweet has no voters")
                continue

            # Mark execution for success or failure
            is_tweet_executable = yield from self.check_tweet_consensus(tweet)
            self.logger.info("The tweet will be marked for execution")

            # We only update the executionAttempt now if the verification failed
            # If it succeeded, it will be updated after posting
            if not is_tweet_executable:
                tweet["executionAttempts"][-1]["verified"] = False
                self.tweets_need_update = True
                continue

            pending_tweets.append(tweet)

        self.updated_tweets = current_centaur["plugins_data"]["scheduled_tweet"][
            "tweets"
        ]

        return pending_tweets

    def check_tweet_consensus(self, tweet: dict):
        """Check whether users agree on posting"""
        total_voting_power = 0

        for voter in tweet["voters"]:
            # Verify signature
            tweet_text = (
                tweet["text"] if isinstance(tweet["text"], str) else tweet["text"][0]
            )
            message = f"I am signing a message to verify that I approve the tweet starting with {tweet_text[:10]}"
            is_valid = yield from self.validate_signature(
                message, voter["address"], voter["signature"]
            )

            self.logger.info(f"Voter: {voter['address']}  Signature valid: {is_valid}")
            if not is_valid:
                continue

            # Get voting power
            voting_power = yield from self.get_voting_power(voter["address"])
            self.logger.info(f"Voter: {voter['address']}  Voting power: {voting_power}")
            total_voting_power += cast(int, voting_power)

        consensus = total_voting_power >= self.params.tweet_consensus_veolas

        self.behaviour.context.logger.info(
            f"Voting power is {total_voting_power} for tweet {tweet['text']}. Executing? {consensus}"
        )

        return consensus

    def get_voting_power(self, address: str):
        """Get the given address's votes."""
        olas_votes = yield from self.get_votes(
            self.params.veolas_delegation_address, address, "ethereum"
        )

        if not olas_votes:
            olas_votes = 0

        self.behaviour.context.logger.info(
            f"Voting power is {olas_votes} for address {address}"
        )
        return olas_votes

    def get_votes(
        self, token_address, voter_address, chain_id
    ) -> Generator[None, None, Optional[float]]:
        """Get the given address's votes."""
        response = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=token_address,
            contract_id=str(VeOLASDelegationContract.contract_id),
            contract_callable="get_votes",
            voter_address=voter_address,
            chain_id=chain_id,
        )
        if response.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Couldn't get the votes for address {chain_id}::{voter_address}: {response.performative}"
            )
            return None

        if "votes" not in response.state.body:
            self.behaviour.context.logger.error(
                f"State does not contain 'votes': {response.state.body}"
            )
            return None

        votes = int(response.state.body["votes"]) / 1e18  # to olas
        return votes
