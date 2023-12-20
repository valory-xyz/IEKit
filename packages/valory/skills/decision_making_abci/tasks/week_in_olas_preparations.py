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
import uuid

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


class WeekInOlasCreatePreparation(TaskPreparation):
    """WeekInOlasCreatePreparation"""

    task_name = "week_in_olas"
    task_event = Event.WEEK_IN_OLAS_CREATE.value

    def check_extra_conditions(self):
        """Check extra conditions"""
        yield
        return True

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        updates = {}
        return updates, self.task_event

    def _post_task(self):
        """Task postprocessing"""
        centaurs_data = self.synchronized_data.centaurs_data
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]

        # Update the last run time
        current_centaur["configuration"]["plugins"]["week_in_olas"][
            "last_run"
        ] = self.now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")

        # Add the new thread to proposed tweets
        thread = {
            "text": self.synchronized_data.summary_tweets,
            "posted": False,
            "voters": [],
            "proposer": {
                "address": "0x12b680F1Ffb678598eFC0C57BB2edCAebB762A9A",  # service safe address (ethereum)
                "verified": True,  # we automatically trust in the backend
                "signature": "",
            },
            "action_id": "",
            "request_id": str(uuid.UUID(int=int(self.now_utc.timestamp()))),
            "createdDate": self.now_utc.timestamp(),
            "executionAttempts": [],
        }

        current_centaur["plugins_data"]["scheduled_tweet"]["tweets"].append(thread)

        updates = {"centaurs_data": centaurs_data, "has_centaurs_changes": True}
        yield
        return updates, None
