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

from datetime import datetime

from packages.valory.contracts.staking.contract import Staking
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)
from packages.valory.skills.staking_abci.behaviours import get_activity_updates


class StakingPreparation(TaskPreparation):
    """StakingPreparation"""

    task_name = None

    def check_extra_conditions(self):
        """Check whether it is time to call the checkpoint"""

        # This check is common for both the activity tracking and the checkpoint
        # because we want to ensure we always call activity tracking just right before we call the checkpoint
        yield

        # If too much time has passed since last execution, we run the staking skill
        minutes_since_last_run = (
            (self.now_utc - self.last_run).total_seconds() / 60
            if self.last_run
            else None
        )
        if (
            minutes_since_last_run is None
            or minutes_since_last_run > self.params.checkpoint_threshold_minutes
        ):
            self.context.logger.info("Too much time has passed since last execution.")
            return True

        # If the epoch is about to end, we run the staking skill
        for staking_contract_address in self.params.staking_contract_addresses:
            is_epoch_ending = yield from self.is_epoch_ending(staking_contract_address)
            if is_epoch_ending:
                self.context.logger.info("Epoch is about to end.")
                return True

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

    def is_epoch_ending(self, staking_contract_address):
        """Check if the epoch is ending"""

        contract_api_msg = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=staking_contract_address,
            contract_id=str(Staking.contract_id),
            contract_callable="get_epoch_end",
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Error getting the epoch end: [{contract_api_msg.performative}]"
            )
            return False

        epoch_end_ts = contract_api_msg.state.body["epoch_end"]
        epoch_end = datetime.fromtimestamp(epoch_end_ts)

        # Should not happen, but if the epoch has ended, we do not care about calling
        if self.now_utc > epoch_end:
            return False

        is_epoch_ending = (
            epoch_end - self.now_utc
        ).total_seconds() < self.params.epoch_end_threshold_minutes * 60

        return is_epoch_ending


class StakingActivityPreparation(StakingPreparation):
    """StakingActivityPreparation"""

    task_name = "staking_activiy"
    task_event = Event.STAKING_ACTIVITY.value

    def check_extra_conditions(self):
        """Check user staking threshold"""
        yield

        ceramic_db = self.context.ceramic_db
        latest_activity_tweet_id = int(
            ceramic_db.data["module_data"]["staking_activiy"][
                "latest_activity_tweet_id"
            ]
        )
        updates, _ = get_activity_updates(
            ceramic_db.data["users"], latest_activity_tweet_id
        )
        pending_updates = len(updates)

        # If enough users have pending updates, we run the activity update
        if pending_updates >= self.params.staking_activity_threshold:
            self.context.logger.info(
                f"There are enough pending activity updates [{pending_updates}]. Executing..."
            )
            return True

        # If the checkpoint is about to be called and there's pending updates, we run the activity update
        is_checkpoint_ready = yield from super().check_extra_conditions()
        if is_checkpoint_ready and pending_updates > 0:
            self.context.logger.info(
                "The checkpoint is about to be called. Executing..."
            )
            return True

        self.context.logger.info(
            f"Not enough updates pending ({pending_updates}) to trigger the activity update [threshold={self.params.staking_activity_threshold}]"
        )

        return False


class StakingCheckpointPreparation(StakingPreparation):
    """StakingCheckpointPreparation"""

    task_name = "staking_checkpoint"
    task_event = Event.STAKING_CHECKPOINT.value
