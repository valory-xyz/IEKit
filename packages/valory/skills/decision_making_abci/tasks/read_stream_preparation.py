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


class ReadCentaursPreparation(TaskPreparation):
    """ReadCentaursPreparation"""

    task_name = "read_centaurs"
    task_event = Event.READ_CENTAURS.value

    def check_extra_conditions(self):
        """Check extra conditions"""
        yield
        return True

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        updates = {
            "read_stream_id": self.params.centaurs_stream_id,
            "read_target_property": "centaurs_data",
        }
        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        updates = {
            "current_centaur_index": 0,  # reset the centaur index after reading
        }
        yield
        return updates, None


class ReadContributeDBPreparation(TaskPreparation):
    """ReadContributeDBPreparation"""

    task_name = "read_contribute_db"
    task_event = Event.READ_CONTRIBUTE_DB.value

    def check_extra_conditions(self):
        """Check extra conditions"""
        yield
        return True

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        updates = {
            "read_stream_id": self.params.ceramic_db_stream_id,
            "read_target_property": "ceramic_db",
        }
        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        updates = {}
        yield
        return updates, None


class ReadManualPointsPreparation(TaskPreparation):
    """ReadManualPointsPreparation"""

    task_name = "read_manual_points"
    task_event = Event.READ_MANUAL_POINTS.value

    def check_extra_conditions(self):
        """Check extra conditions"""
        yield
        return True

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        updates = {
            "read_stream_id": self.params.manual_points_stream_id,
            "read_target_property": "score_data",
        }
        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        updates = {}
        yield
        return updates, None
