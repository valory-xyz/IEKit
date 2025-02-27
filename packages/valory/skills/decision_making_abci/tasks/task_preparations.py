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
    """Represents the work required before and after running a Centaur task"""

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
        self.ceramic_db = behaviour.context.ceramic_db
        self.now_utc = now_utc
        self.context = context

        self.logger.info(f"Instantiated task {self.__class__.__name__}")
        self.set_config()
        self.log_config()

    def set_config(self):
        """Set the configuration"""
        centaurs_data = self.synchronized_data.centaurs_data

        if not centaurs_data:
            self.set_default_config()
            return

        plugins_config = centaurs_data[self.synchronized_data.current_centaur_index][
            "configuration"
        ]["plugins"]

        if self.task_name in plugins_config:
            plugin_config = plugins_config[self.task_name]
            self.enabled = plugin_config["enabled"]
            self.daily = plugin_config["daily"] if "daily" in plugin_config else False
            self.weekly = (
                int(plugin_config["weekly"]) if "weekly" in plugin_config else None
            )
            self.last_run = (
                datetime.strptime(
                    plugin_config["last_run"], "%Y-%m-%d %H:%M:%S %Z"
                ).replace(tzinfo=timezone.utc)
                if plugin_config.get("last_run", None)
                else None
            )
            self.run_hour_utc = (
                plugin_config["run_hour_utc"]
                if self.daily or (self.weekly is not None)
                else None
            )
            return

        self.set_default_config()

    def set_default_config(self):
        """Set the default configuration"""
        self.logger.info("Setting the default configuration")
        self.enabled = True
        self.daily = False
        self.weekly = None
        self.last_run = None
        self.run_hour_utc = None

    def log_config(self):
        """Log configuration"""
        self.logger.info(
            f"Config: enabled={self.enabled}  daily={self.daily}  weekly={self.weekly}  last_run={self.last_run}  run_hour_utc={self.run_hour_utc}"
        )

    def check_conditions(self):
        """Check wether the task needs to be run"""

        # Is the task enabled?
        if not self.enabled:
            self.logger.info(f"[{self.__class__.__name__}]: task is disabled")
            return False

        # Does the task run every day?
        if self.daily and self.last_run and self.last_run.day == self.now_utc.day:
            self.logger.info(
                f"[{self.__class__.__name__}]: task is a daily task and was already ran today"
            )
            return False

        # Does the task run every week?
        if self.weekly is not None and self.weekly != self.now_utc.weekday():
            self.logger.info(
                f"[{self.__class__.__name__}]: task is a weekly task but today is not the configured run day: {self.now_utc.weekday()} != {self.weekly}"
            )
            return False

        if (
            self.weekly is not None
            and self.last_run
            and (self.now_utc - self.last_run).total_seconds() < SECONDS_IN_DAY
        ):
            self.logger.info(
                f"[{self.__class__.__name__}]: task is a weekly task and was already ran less than a day ago"
            )
            return False

        # Does the task run at a specific time?
        if (
            self.daily or (self.weekly is not None)
        ) and self.now_utc.hour < self.run_hour_utc:
            self.logger.info(
                f"[{self.__class__.__name__}]: not time to run yet [{self.now_utc.hour}!={self.run_hour_utc}]"
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
