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

from datetime import datetime, timezone
from typing import Dict, Generator, List, Optional, Tuple, cast

from packages.valory.contracts.staking.contract import Staking
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)
from packages.valory.skills.staking_abci.behaviours import BASE_CHAIN_ID


POINTS_PER_ACTIVITY_UPDATE = 200


def group_tweets(
    tweet_id_to_points: Dict, pending_points: int
) -> Tuple[int, List[str]]:
    """Group tweets for the next update"""

    # Add the pending points as another tweet
    tweet_id_to_points["dummy_id"] = pending_points

    selected_tweets = []
    update_points = 0

    # Sort the tweet dict, from more points to lest points
    sorted_tweet_id_to_points = dict(
        sorted(tweet_id_to_points.items(), key=lambda item: item[1], reverse=True)
    )

    while True:
        # Stop when adding the remaining points does not produce a new update
        selected_points = sum(
            v for k, v in tweet_id_to_points.items() if k in selected_tweets
        )
        remainder_points = selected_points % POINTS_PER_ACTIVITY_UPDATE
        remaining_points = sum(list(sorted_tweet_id_to_points.values()))
        if remainder_points + remaining_points < POINTS_PER_ACTIVITY_UPDATE:
            break

        # Add the next tweet
        tweet_id = list(sorted_tweet_id_to_points.keys())[0]
        update_points += sorted_tweet_id_to_points[tweet_id]
        if tweet_id != "dummy_id":
            selected_tweets.append(tweet_id)

        # Remove from the dict
        del sorted_tweet_id_to_points[tweet_id]

    # Calculate update
    updates = int(update_points / POINTS_PER_ACTIVITY_UPDATE)

    return updates, selected_tweets


class StakingPreparation(TaskPreparation):
    """StakingPreparation"""

    task_name = None

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

    def get_epoch_end(
        self, staking_contract_address
    ) -> Generator[None, None, Optional[datetime]]:
        """Get the epoch end"""

        self.logger.info(f"Getting epoch end for {staking_contract_address}")

        contract_api_msg = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=staking_contract_address,
            contract_id=str(Staking.contract_id),
            contract_callable="get_epoch_end",
            chain_id=BASE_CHAIN_ID,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Error getting the epoch end: [{contract_api_msg.performative}]"
            )
            return None

        epoch_end_ts = contract_api_msg.state.body["epoch_end"]
        epoch_end = datetime.fromtimestamp(epoch_end_ts, tz=timezone.utc)
        self.logger.info(f"Epoch end is {epoch_end}")
        return epoch_end

    def is_epoch_ending(self, staking_contract_address) -> Generator[None, None, bool]:
        """Check if the epoch is ending"""
        epoch_end = yield from self.get_epoch_end(staking_contract_address)

        if not epoch_end:
            return False

        if self.now_utc > epoch_end:
            return False

        is_epoch_ending = (
            epoch_end - self.now_utc
        ).total_seconds() < self.params.epoch_end_threshold_minutes * 60

        return is_epoch_ending

    def is_checkpoint_callable(
        self, staking_contract_address
    ) -> Generator[None, None, bool]:
        """Check if the epoch has ended"""
        epoch_end = yield from self.get_epoch_end(staking_contract_address)

        if not epoch_end:
            return False

        # If the epoch end is in the past, the epoch has ended and
        # no one has called the checkpoint
        return epoch_end < self.now_utc

    def get_staking_epoch(
        self, staking_contract_address
    ) -> Generator[None, None, Optional[int]]:
        """Get the staking epoch"""

        contract_api_msg = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=staking_contract_address,
            contract_id=str(Staking.contract_id),
            contract_callable="get_epoch",
            chain_id=BASE_CHAIN_ID,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(f"Error getting the epoch: [{contract_api_msg}]")
            return None

        epoch = cast(int, contract_api_msg.state.body["epoch"])
        return epoch

    def get_staking_contract(
        self, wallet_address
    ) -> Generator[None, None, Optional[str]]:
        """Get the staking contract where a user is staked"""

        contract_api_msg = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.params.contributors_contract_address,
            contract_id=str(Staking.contract_id),
            contract_callable="get_account_to_service_map",
            wallet_address=wallet_address,
            chain_id=BASE_CHAIN_ID,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"Error getting the epoch: [{contract_api_msg.performative}]"
            )
            return None

        staking_contract_address = cast(
            str, contract_api_msg.state.body["staking_contract_address"]
        )

        if staking_contract_address == "0x0000000000000000000000000000000000000000":
            return None
        return staking_contract_address


class StakingActivityPreparation(StakingPreparation):
    """StakingActivityPreparation"""

    task_name = "staking_activity"
    task_event = Event.STAKING_ACTIVITY.value
    multisig_to_updates = None
    user_to_counted_tweets = None

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        updates = {}
        if self.multisig_to_updates:
            updates = {
                "staking_multisig_to_updates": self.multisig_to_updates,
                "staking_user_to_counted_tweets": self.user_to_counted_tweets,
            }
        return updates, self.task_event

    def check_extra_conditions(self):
        """Check user staking threshold"""
        yield

        ceramic_db = self.context.ceramic_db

        # Get the current staking epochs
        staking_contract_to_epoch = {}
        for staking_contract_address in self.params.staking_contract_addresses:
            epoch = yield from self.get_staking_epoch(staking_contract_address)
            staking_contract_to_epoch[staking_contract_address] = epoch

        # Get the updates.
        # Store them as a property since we will use them in _pre_task() to return the updates
        (
            self.multisig_to_updates,
            self.user_to_counted_tweets,
        ) = yield from self.get_activity_updates(
            ceramic_db.data["users"], staking_contract_to_epoch
        )
        pending_updates = len(self.multisig_to_updates)

        # If enough users have pending updates, we run the activity update
        if pending_updates >= self.params.staking_activity_threshold:
            self.context.logger.info(
                f"There are enough pending activity updates [{pending_updates}]. Executing..."
            )
            return True

        # If there's some pending updates and the epoch is ending, we run the activity update
        is_some_epoch_ending = False
        for staking_contract_address in self.params.staking_contract_addresses:
            is_epoch_ending = yield from self.is_epoch_ending(staking_contract_address)
            if is_epoch_ending:
                is_some_epoch_ending = True
                break

        if pending_updates > 0 and is_some_epoch_ending:
            self.context.logger.info("Some epoch is ending. Executing...")
            return True

        self.context.logger.info(
            f"Not enough updates pending ({pending_updates}) to trigger the activity update [threshold={self.params.staking_activity_threshold}]"
        )

        return False

    def get_activity_updates(
        self, users: Dict, staking_contract_to_epoch: Dict
    ) -> Generator[None, None, Tuple[Dict, Dict]]:
        """Get the latest activity updates"""

        multisig_to_updates = {}
        user_to_counted_tweets = {}

        for user_id, user_data in users.items():
            # Skip the user if there is no service multisig or wallet
            # This means the user has not staked
            if not user_data.get("service_multisig", None) or not user_data.get(
                "wallet_address", None
            ):
                continue

            service_multisig = user_data["service_multisig"]

            # Get this user's staking contract epoch
            staking_contract = yield from self.get_staking_contract(
                user_data["wallet_address"]
            )

            if not staking_contract:
                continue

            this_epoch = staking_contract_to_epoch[staking_contract]

            # Get this epoch's tweets and points
            # Also filter out tweets that do not belong to a campaign
            this_epoch_tweets = {
                k: v
                for k, v in user_data.get("tweets", {}).items()
                if v["epoch"] == this_epoch and v["campaign"]
            }
            this_epoch_not_counted_tweets = {
                k: v
                for k, v in this_epoch_tweets.items()
                if not v["counted_for_activity"]
            }

            this_epoch_points = sum(t["points"] for t in this_epoch_tweets.values())
            this_epoch_not_counted_points = sum(
                t["points"] for t in this_epoch_not_counted_tweets.values()
            )

            # Since we count each POINTS_PER_ACTIVITY_UPDATE as one update, it can be the case
            # that some partial points are pending from the previous activity update, i.e
            # an user scored 2 tweets this epoch with [200, 300] points.
            # If POINTS_PER_ACTIVITY_UPDATE=200, the activity update will add 2 updates.
            # The remaining 100 points should be added to the next activity update (if any).
            points_pending_from_previous_run = (
                this_epoch_points % POINTS_PER_ACTIVITY_UPDATE
            )

            # Skip this user if there are not enough points for an update
            if (
                points_pending_from_previous_run + this_epoch_not_counted_points
                < POINTS_PER_ACTIVITY_UPDATE
            ):
                continue

            # Group tweets to build new updates. This is not evident and requires
            # an algorithm that optimizes how to group them in order to maximize the number of updates for the user
            not_counted_tweet_id_to_points = {
                k: v["points"] for k, v in this_epoch_not_counted_tweets.items()
            }

            (updates, selected_tweets) = group_tweets(
                not_counted_tweet_id_to_points, points_pending_from_previous_run
            )

            if updates:
                multisig_to_updates[service_multisig] = updates
                user_to_counted_tweets[user_id] = selected_tweets

        self.context.logger.info(f"Calculated activity updates: {multisig_to_updates}")
        self.context.logger.info(
            f"Tweets included in the potential update: {user_to_counted_tweets}"
        )

        return multisig_to_updates, user_to_counted_tweets


class StakingCheckpointPreparation(StakingPreparation):
    """StakingCheckpointPreparation"""

    task_name = "staking_checkpoint"
    task_event = Event.STAKING_CHECKPOINT.value

    def check_extra_conditions(self):
        """Check whether it is time to call the checkpoint"""

        yield

        for staking_contract_address in self.params.staking_contract_addresses:
            is_checkpoint_callable = yield from self.is_checkpoint_callable(
                staking_contract_address
            )
            if is_checkpoint_callable:
                self.context.logger.info(
                    f"Epoch has ended for contract {staking_contract_address} and no one called the checkpoint yet."
                )
                return True

        self.context.logger.info("Not time to call the checkpoint yet.")
        return False


class StakingDAAPreparation(TaskPreparation):
    """StakingDAAPreparation"""

    task_name = "staking_daa"
    task_event = Event.STAKING_DAA_UPDATE.value

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

    def check_extra_conditions(self):
        """Check user staking threshold"""
        yield
        return True
