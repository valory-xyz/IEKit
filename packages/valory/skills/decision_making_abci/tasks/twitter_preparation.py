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
from typing import Generator, Optional, cast
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.contracts.uniswap_v2_erc20.contract import UniswapV2ERC20Contract
from packages.valory.protocols.contract_api import ContractApiMessage


TWEET_CONSENSUS_WVEOLAS_WEI = 2e6 * 1e18  # 2M wveOLAS to wei
OLAS_ADDRESS_ETHEREUM = "0x0001a500a6b18995b03f44bb040a5ffc28e45cb0"
OLAS_ADDRESS_GNOSIS = "0xce11e14225575945b8e6dc0d4f2dd4c570f79d9f"


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

        text = yield from self.get_tweet()

        write_data = [
            {
                "text": text,
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
        pending_tweets = yield from self.get_pending_tweets()
        return pending_tweets[0]["text"]

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

        pending_tweets = yield from self.get_pending_tweets()
        if not pending_tweets:
            return False

        return True

    def get_pending_tweets(self):
        """Get not yet posted tweets that need to be posted"""
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]

        pending_tweets = []
        for t in current_centaur["plugins_data"]["scheduled_tweet"]["tweets"]:

            if not t["posted"]:
                continue

            is_tweet_executable = yield from self.is_tweet_executable(t)

            if not is_tweet_executable:
                continue

            pending_tweets.append(t)

        return pending_tweets


    def is_tweet_executable(self, tweet: dict):
        """"Check whether a tweet can be published"""

        # Reject tweets with no execution attempts
        if not tweet["executionAttempts"]:
            return False

        # Reject already processed tweets
        if tweet["executionAttempts"][-1]["verified"] in [True, False]:
            return False

        # At this point, the tweet is awaiting to be published [verified=None]

        # Reject tweet that do not have enough voting power
        consensus = yield from self.check_tweet_consensus(tweet["voters"])
        if not consensus:
            return False

        return True


    def check_tweet_consensus(self, tweet: dict):
        """Check whether users agree on posting"""
        total_voting_power = 0

        for voter in tweet["voters"]:
            voting_power = yield from self.get_voting_power(voter.keys()[0])
            total_voting_power += voting_power

        return total_voting_power >= TWEET_CONSENSUS_WVEOLAS_WEI


    def get_voting_power(self, address: str) -> Generator[None, None, int]:
        """Get the given address's balance."""
        olas_balance_ethereum = yield from self.get_token_balance(OLAS_ADDRESS_ETHEREUM, address, "ethereum") or 0
        olas_balance_gnosis = yield from self.get_token_balance(OLAS_ADDRESS_GNOSIS, address, "gnosis") or 0
        return cast(int, olas_balance_ethereum) + cast(int, olas_balance_gnosis)


    def get_token_balance(self, token_address, owner_address, chain_id) -> Generator[None, None, Optional[int]]:
        """Get the given address's balance."""
        response = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=token_address,
            contract_id=str(UniswapV2ERC20Contract.contract_id),
            contract_callable="balance_of",
            owner_address=owner_address,
            chain_id=chain_id
        )
        if response.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Couldn't get the balance for address {owner_address}: {response.performative}"
            )
            return None

        return response.state.body


