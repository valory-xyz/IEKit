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
from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


class WriteStreamPreparation(TaskPreparation):
    """WriteStreamPreparation"""

    def check_extra_conditions(self):
        """Check extra conditions"""
        yield
        return True


class OrbisPreparation(WriteStreamPreparation):
    """OrbisPreparation"""

    def check_extra_conditions(self):
        """Validate Twitter credentials for the current centaur"""

        proceed = yield from super().check_extra_conditions()
        if not proceed:
            return False

        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]
        centaur_id_to_secrets = self.params.centaur_id_to_secrets

        if current_centaur["id"] not in centaur_id_to_secrets:
            return False

        if "orbis" not in centaur_id_to_secrets[current_centaur["id"]]:
            return False

        secrets = centaur_id_to_secrets[current_centaur["id"]]["orbis"]

        if sorted(secrets.keys()) != sorted(["context", "did_seed", "did_str"]):
            return False

        return True

    def _post_task(self):
        """Preparations after running the task"""
        centaurs_data = self.synchronized_data.centaurs_data
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]

        # Update Orbis action
        new_post_streams = self.synchronized_data.write_results
        timestamp = self.now_utc.timestamp()

        orbis_action = {
            "actorAddress": self.params.ceramic_did_str,
            "outputUrl": f"https://app.orbis.club/post/{new_post_streams[0]['stream_id']}",
            "description": "posted to Orbis",
            "timestamp": timestamp,
        }

        if "actions" in current_centaur:
            current_centaur["actions"].append(orbis_action)
        else:
            current_centaur["actions"] = orbis_action

        updates = {"centaurs_data": centaurs_data, "has_centaurs_changes": True}
        yield
        return updates, None


class DailyOrbisPreparation(OrbisPreparation):
    """DailyOrbisPreparation"""

    task_name = "daily_orbis"
    task_event = Event.DAILY_ORBIS.value

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]

        extra_metadata = {
            "family": "orbis",
            "tags": ["orbis", "post"],
            "schema": "k1dpgaqe3i64kjuyet4w0zyaqwamf9wrp1jim19y27veqkppo34yghivt2pag4wxp0fv2yl04ypy3enwg9eisk6zkcq0a8buskv2tyq5rlldhi2vg3fkmfug4",
        }

        write_data = [
            {
                "op": "create",
                "data": {
                    "body": self.synchronized_data.daily_tweet,
                    "context": self.params.centaur_id_to_secrets[current_centaur["id"]][
                        "orbis"
                    ]["did_str"],
                },
                "extra_metadata": extra_metadata,
                "did_str": self.params.centaur_id_to_secrets[current_centaur["id"]][
                    "orbis"
                ]["did_str"],
                "did_seed": self.params.centaur_id_to_secrets[current_centaur["id"]][
                    "orbis"
                ]["did_seed"],
            }
        ]

        # Dump the data into the state
        self.behaviour.context.state.ceramic_data = write_data

        updates = {
            "write_results": [],  # clear previous results
            "is_data_on_sync_db": False,
        }

        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        updates, event = yield from super()._post_task()

        # Update the last run time
        centaurs_data = self.synchronized_data.centaurs_data
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]
        current_centaur["configuration"]["plugins"]["daily_orbis"][
            "last_run"
        ] = self.now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")

        updates = {"centaurs_data": centaurs_data}
        return updates, event


class UpdateCentaursPreparation(WriteStreamPreparation):
    """UpdateCentaursPreparation"""

    task_name = "update_centaurs"
    task_event = Event.UPDATE_CENTAURS.value

    def check_extra_conditions(self):
        """Check extra conditions"""
        proceed = yield from super().check_extra_conditions()
        if not proceed:
            return False

        return self.synchronized_data.has_centaurs_changes

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        write_data = [
            {
                "op": "update",
                "stream_id": self.params.centaurs_stream_id,
                "data": self.synchronized_data.centaurs_data,
                "did_str": self.params.ceramic_did_str,
                "did_seed": self.params.ceramic_did_seed,
            }
        ]

        # Dump the data into the state
        self.behaviour.context.state.ceramic_data = write_data

        updates = {
            "write_results": [],  # clear previous results
            "is_data_on_sync_db": False,
        }
        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""

        updates = {
            "has_centaurs_changes": False,
        }
        yield
        return updates, None


class WriteContributeDBPreparation(WriteStreamPreparation):
    """WriteContributeDBPreparation"""

    task_name = "write_contribute"
    task_event = Event.WRITE_CONTRIBUTE_DB.value

    def check_extra_conditions(self):
        """Check extra conditions"""
        proceed = yield from super().check_extra_conditions()
        if not proceed:
            return False

        return self.synchronized_data.pending_write

    def _pre_task(self):
        """Preparations before running the task"""
        yield
        write_data = [
            {
                "op": "update",
                "stream_id": self.params.ceramic_db_stream_id,
                "data": self.ceramic_db.data,
                "did_str": self.params.ceramic_did_str,
                "did_seed": self.params.ceramic_did_seed,
            }
        ]

        # Dump the data into the state
        self.behaviour.context.state.ceramic_data = write_data

        updates = {
            "is_data_on_sync_db": False,
        }
        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""

        updates = {
            "pending_write": False,
        }
        yield
        return updates, None
