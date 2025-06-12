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


SECONDS_IN_DAY = 24 * 3600


class TaskPreparation:
    """Represents the work required before and after running a task"""

    task_name = None
    task_event = None

    def __init__(self, now_utc, behaviour, synchronized_data, context) -> None:
        """Init"""
        self.name = ""
        self.behaviour = behaviour
        self.synchronized_data = synchronized_data
        self.params = behaviour.params
        self.logger = behaviour.context.logger
        self.state = behaviour.state
        self.now_utc = now_utc
        self.context = context

        self.logger.info(f"Instantiated task {self.__class__.__name__}")
        self.data = getattr(self.context.contribute_db.data.module_data, self.task_name, None)
        self.config = getattr(self.context.contribute_db.data.module_configs, self.task_name)
        self.log_config()

    def log_config(self):
        """Log configuration"""
        self.logger.info(
            f"Config: enabled={self.config.enabled}  daily={self.config.daily}  weekly={self.config.weekly}  last_run={self.config.last_run}  run_hour_utc={self.config.run_hour_utc}"
        )

    def check_conditions(self):
        """Check wether the task needs to be run"""

        # Is the task enabled?
        if not self.config.enabled:
            self.logger.info(f"[{self.__class__.__name__}]: task is disabled")
            return False

        # Does the task run every day?
        if self.config.daily and self.config.last_run and self.config.last_run.day == self.now_utc.day:
            self.logger.info(
                f"[{self.__class__.__name__}]: task is a daily task and was already ran today"
            )
            return False

        # Does the task run every week?
        if self.config.weekly is not None and self.config.weekly != self.now_utc.weekday():
            self.logger.info(
                f"[{self.__class__.__name__}]: task is a weekly task but today is not the configured run day: {self.now_utc.weekday()} != {self.config.weekly}"
            )
            return False

        if (
            self.config.weekly is not None
            and self.config.last_run
            and (self.now_utc - self.config.last_run).total_seconds() < SECONDS_IN_DAY
        ):
            self.logger.info(
                f"[{self.__class__.__name__}]: task is a weekly task and was already ran less than a day ago"
            )
            return False

        # Does the task run at a specific time?
        if (
            self.config.daily or (self.config.weekly is not None)
        ) and self.now_utc.hour < self.config.run_hour_utc:
            self.logger.info(
                f"[{self.__class__.__name__}]: not time to run yet [{self.now_utc.hour}!={self.config.run_hour_utc}]"
            )
            return False

        # Check extra conditions
        proceed = yield from self.check_extra_conditions()
        if not proceed:
            self.logger.info(
                f"[{self.__class__.__name__}]: extra conditions returned False"
            )
            return False

        # Run
        self.logger.info(f"[{self.__class__.__name__}]: running the task")
        return True

    def check_extra_conditions(self):
        """Check extra conditions"""
        raise NotImplementedError

    def _pre_task(self):
        """Preparations before running the task"""
        raise NotImplementedError

    def pre_task(self):
        """Task preprocessing"""
        proceed = yield from self.check_conditions()
        if proceed:
            self.logger.info(f"Running {self.__class__.__name__}._pre_task()")
            updates, event = yield from self._pre_task()
            return updates, event
        self.logger.info(f"Skipping {self.__class__.__name__}._pre_task()")
        return {}, None

    def post_task(self):
        """Task postprocessing"""
        self.logger.info(f"Running {self.__class__.__name__}._post_task()")
        updates, event = yield from self._post_task()
        return updates, event

    def _post_task(self):
        """Preparations after running the task"""
        raise NotImplementedError
