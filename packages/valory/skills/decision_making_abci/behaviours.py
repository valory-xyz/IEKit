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

"""This package contains round behaviours of DecisionMakingAbciApp."""

import json
from abc import ABC
from datetime import datetime, timezone
from typing import Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.contribute_db_abci.behaviours import ContributeDBBehaviour
from packages.valory.skills.decision_making_abci.models import Params, SharedState
from packages.valory.skills.decision_making_abci.rounds import (
    DecisionMakingAbciApp,
    DecisionMakingPayload,
    DecisionMakingRound,
    Event,
    PostTxDecisionMakingRound,
    PostTxDecisionPayload,
    SynchronizedData,
)
from packages.valory.skills.decision_making_abci.tasks.campaign_validation_preparation import (
    CampaignValidationPreparation,
)
from packages.valory.skills.decision_making_abci.tasks.finished_pipeline_preparation import (
    FinishedPipelinePreparation,
)
from packages.valory.skills.decision_making_abci.tasks.score_preparations import (
    ScorePreparation,
)
from packages.valory.skills.decision_making_abci.tasks.staking import (
    StakingActivityPreparation,
    StakingCheckpointPreparation,
    StakingDAAPreparation,
)
from packages.valory.skills.decision_making_abci.tasks.tweet_validation_preparation import (
    TweetValidationPreparation,
)
from packages.valory.skills.decision_making_abci.tasks.twitter_preparation import (
    ScheduledTweetPreparation,
)
from packages.valory.skills.decision_making_abci.tasks.week_in_olas_preparations import (
    WeekInOlasCreatePreparation,
)


# Task FSM
previous_event_to_task_preparation_cls = {
    None: {
        "prev": None,
        "next": ScorePreparation,
    },
    # Event.WEEK_IN_OLAS_CREATE.value: {
    #     "prev": WeekInOlasCreatePreparation,
    #     "next": TweetValidationPreparation,
    # },
    # Event.TWEET_VALIDATION.value: {
    #     "prev": TweetValidationPreparation,
    #     "next": ScheduledTweetPreparation,
    # },
    # Event.SCHEDULED_TWEET.value: {
    #     "prev": ScheduledTweetPreparation,
    #     "next": CampaignValidationPreparation,
    # },
    # Event.CAMPAIGN_VALIDATION.value: {
    #     "prev": CampaignValidationPreparation,
    #     "next": StakingActivityPreparation,
    # },
    # Event.STAKING_ACTIVITY.value: {
    #     "prev": StakingActivityPreparation,
    #     "next": StakingCheckpointPreparation,
    # },
    # Event.STAKING_CHECKPOINT.value: {
    #     "prev": StakingCheckpointPreparation,
    #     "next": StakingDAAPreparation,
    # },
    # Event.STAKING_DAA_UPDATE.value: {
    #     "prev": StakingDAAPreparation,
    #     "next": ScorePreparation,
    # },
    Event.SCORE.value: {
        "prev": ScorePreparation,
        "next": FinishedPipelinePreparation,
    },
}


class DecisionMakingBaseBehaviour(ContributeDBBehaviour, ABC):
    """Base behaviour for the decision_making_abci skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @property
    def local_state(self) -> SharedState:
        """Return the state."""
        return cast(SharedState, self.context.state)


class DecisionMakingBehaviour(DecisionMakingBaseBehaviour):
    """DecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = DecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            updates, event = yield from self.get_updates_and_event()
            payload_content = json.dumps(
                {"updates": updates, "event": event}, sort_keys=True
            )
            sender = self.context.agent_address
            payload = DecisionMakingPayload(sender=sender, content=payload_content)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_updates_and_event(self):
        """Get the updates and event"""

        now_utc = self._get_utc_time()

        # Get the previous and next task preparations
        previous_decision_event = self.synchronized_data.previous_decision_event

        event_list = list(
            previous_event_to_task_preparation_cls.keys()
        )  # since python 3.7, dict keys preserve order

        previous_task_skipped = False

        # Loop until we reach a non-skipped task
        while True:
            task_preparation_clss = previous_event_to_task_preparation_cls[
                previous_decision_event
            ]
            previous_task_preparation_cls = task_preparation_clss["prev"]
            next_task_preparation_cls = task_preparation_clss["next"]
            self.context.logger.info(
                f"Previous task = {previous_task_preparation_cls.__name__ if previous_task_preparation_cls else None}, Next task = {next_task_preparation_cls.__name__}"
            )

            # Init events and updates
            post_event = None
            post_updates = {}
            pre_event = None
            pre_updates = {}

            # Process post task
            if not previous_task_skipped:
                previous_task_preparation = (
                    previous_task_preparation_cls(
                        now_utc, self, self.synchronized_data, self.context
                    )
                    if previous_task_preparation_cls
                    else None
                )

                if previous_task_preparation:
                    (
                        post_updates,
                        post_event,
                    ) = yield from previous_task_preparation.post_task()

                    self.context.logger.info(f"Post task event = {post_event}")

                # If the post task returns an event, do not proceed with the pre task:
                if post_event:
                    return post_updates, post_event

            # Process pre task
            next_task_preparation = (
                next_task_preparation_cls(
                    now_utc,
                    self,
                    self.synchronized_data.update(  # use an updated version of the data
                        synchronized_data_class=SynchronizedData,
                        **post_updates,
                    ),
                    self.context,
                )
                if next_task_preparation_cls
                else None
            )

            if next_task_preparation:
                pre_updates, pre_event = yield from next_task_preparation.pre_task()
                self.context.logger.info(f"Pre task event = {pre_event}")

            if pre_event:
                if set(post_updates.keys()).intersection(set(pre_updates.keys())):
                    raise ValueError(
                        f"Common keys between post_updates [{post_updates}] and pre_updates [{pre_updates}]"
                    )
                return {**post_updates, **pre_updates}, pre_event

            # If not event has been triggered, we skip the task
            self.context.logger.info(
                f"Skipping the {next_task_preparation_cls.__name__} task"
            )
            # Get the next task
            if previous_decision_event != Event.SCORE.value:
                # Regular case: we just get the next task in the list
                previous_decision_event_index = (
                    event_list.index(previous_decision_event) + 1
                ) % len(event_list)
                previous_decision_event = event_list[previous_decision_event_index]
            else:
                # Special case: after NEXT_CENTAUR, we don't want to jump into the first task (READ_CENTAURS),
                # because the data has been already read at the beginning. Also, if we reached this point
                # it means we are skipping the LLM task (it comes after a NEXT_CENTAUR event). In this case,
                # we can directly skip to SCHEDULED_TWEET because skipping LLM means skipping DailyTwitter and DailyOrbis.
                # Therefore, we act as if the previous task was DailyOrbis.
                previous_decision_event = Event.WEEK_IN_OLAS_CREATE.value

            previous_task_skipped = True

    def _get_utc_time(self):
        """Check if it is process time"""
        now_utc = (
            self.local_state.round_sequence._last_round_transition_timestamp
            or datetime.now(timezone.utc)
        )

        # Tendermint timestamps are expected to be UTC, but for some reason
        # we are getting local time. We replace the hour and timezone.
        # TODO: this hour replacement could be problematic in some time zones
        now_utc = now_utc.replace(
            hour=datetime.now(timezone.utc).hour, tzinfo=timezone.utc
        )
        now_utc_str = now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")
        self.context.logger.info(f"Now [UTC]: {now_utc_str}")

        return now_utc


class PostTxDecisionMakingBehaviour(DecisionMakingBaseBehaviour):
    """PostTxDecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = PostTxDecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            event = self.get_event()
            sender = self.context.agent_address
            payload = PostTxDecisionPayload(sender=sender, event=event)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_event(self) -> str:
        """Get the next event"""

        tx_submitter = self.synchronized_data.tx_submitter

        self.context.logger.info(f"Transcation submitter was {tx_submitter}")

        if tx_submitter == "activity_update_preparation_behaviour":
            return Event.POST_TX_ACTIVITY_UPDATE.value

        if tx_submitter == "checkpoint_preparation_behaviour":
            return Event.POST_TX_CHECKPOINT.value

        if tx_submitter == "d_a_a_preparation_behaviour":
            return Event.POST_TX_DAA.value

        # This is a mech request
        return Event.POST_TX_MECH.value


class DecisionMakingRoundBehaviour(AbstractRoundBehaviour):
    """DecisionMakingRoundBehaviour"""

    initial_behaviour_cls = DecisionMakingBehaviour
    abci_app_cls = DecisionMakingAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        DecisionMakingBehaviour,
        PostTxDecisionMakingBehaviour,
    ]
