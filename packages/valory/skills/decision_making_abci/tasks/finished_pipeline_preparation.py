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
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


class FinishedPipelinePreparation(TaskPreparation):
    """FinishedPipelinePreparation"""

    task_name = "finished_pipeline"

    def check_extra_conditions(self):
        """Check extra conditions"""
        yield
        return True

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        updates = {}

        return (
            updates,
            Event.DONE.value,
        )
