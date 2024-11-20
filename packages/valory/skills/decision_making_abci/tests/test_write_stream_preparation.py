#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2024 Valory AG
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
"""Test write stream preparation tasks."""
from copy import copy, deepcopy
from unittest.mock import patch

import pytest

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.write_stream_preparation import (
    DailyOrbisPreparation,
    OrbisPreparation,
    UpdateCentaursPreparation,
    WriteContributeDBPreparation,
)
from packages.valory.skills.decision_making_abci.test_tools.tasks import (
    BaseTaskTest,
    NOW_UTC,
    TaskTestCase,
)
from packages.valory.skills.decision_making_abci.tests import centaur_configs


DUMMY_CENTAURS_DATA = [deepcopy(centaur_configs.ENABLED_CENTAUR)]

orbis_action = {
    "actorAddress": "did:key:z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
    "outputUrl": "https://app.orbis.club/post/dummy_stream_id",
    "description": "posted to Orbis",
    "timestamp": NOW_UTC.timestamp(),
}

DUMMY_CENTAURS_DATA_ACTIONS = deepcopy(DUMMY_CENTAURS_DATA)
DUMMY_CENTAURS_DATA_ACTIONS[0]["actions"].append(orbis_action)

DUMMY_CENTAURS_DATA_NO_ACTIONS = [deepcopy(centaur_configs.NO_ACTIONS)]
DUMMY_CENTAURS_DATA_NO_ACTIONS[0]["actions"] = orbis_action

DUMMY_CENTAURS_DATA_DAILY_ORBIS = deepcopy(DUMMY_CENTAURS_DATA)
DUMMY_CENTAURS_DATA_DAILY_ORBIS[0]["configuration"]["plugins"]["daily_orbis"][
    "last_run"
] = NOW_UTC.strftime("%Y-%m-%d %H:%M:%S %Z")


class TestOrbisPreparation(BaseTaskTest):
    """Test the OrbisPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=OrbisPreparation,
                exception_message=False,
            )
        ],
    )
    @patch(
        "packages.valory.skills.decision_making_abci.tasks.write_stream_preparation.WriteStreamPreparation.check_extra_conditions"
    )
    def test_check_extra_conditions_not_proceed(
        self, mock_check_extra_conditions, test_case: TaskTestCase
    ):
        """Test the check_extra_conditions method when not proceed."""
        mock_check_extra_conditions.return_value = iter(
            [
                None,
            ]
        )
        super().check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Centaur ID to secrets missing id",
                task_preparation_class=OrbisPreparation,
                exception_message=False,
                initial_data={
                    "centaur_id_to_secrets": deepcopy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ID
                    ),
                    "synchronized_data": {"centaurs_data": copy(DUMMY_CENTAURS_DATA)},
                },
            ),
            TaskTestCase(
                name="Centaur ID to secrets missing orbis",
                task_preparation_class=OrbisPreparation,
                exception_message=False,
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ORBIS,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                },
            ),
            TaskTestCase(
                name="Centaur ID to secrets missing orbis key",
                task_preparation_class=OrbisPreparation,
                exception_message=False,
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ORBIS_KEY,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                },
            ),
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=OrbisPreparation,
                exception_message=True,
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                },
            ),
        ],
    )
    def test_check_extra_conditions(self, test_case: TaskTestCase):
        """Test the check_extra_conditions method when the centaur id is not in centaur id to secrets."""
        super().check_extra_conditions_test(test_case)

    #
    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=OrbisPreparation,
                exception_message=(
                    {
                        "centaurs_data": DUMMY_CENTAURS_DATA_ACTIONS,
                        "has_centaurs_changes": True,
                    },
                    None,
                ),
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                    "write_results": [{"stream_id": "dummy_stream_id"}],
                },
            )
        ],
    )
    def test__post_task(self, test_case: TaskTestCase):
        """Test the _post_task method."""
        super()._post_task_base_test(test_case)


class TestDailyOrbisPreparation(BaseTaskTest):
    """Test the DailyOrbisPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=DailyOrbisPreparation,
                exception_message=(
                    {
                        "centaurs_data": DUMMY_CENTAURS_DATA_DAILY_ORBIS,
                    },
                    None,
                ),
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                    "write_results": [{"stream_id": "dummy_stream_id"}],
                },
            )
        ],
    )
    def test__post_task(self, test_case: TaskTestCase):
        """Test the _post_task method."""
        super()._post_task_base_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=DailyOrbisPreparation,
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {
                        "centaurs_data": DUMMY_CENTAURS_DATA,
                        "daily_tweet": {
                            "text": "dummy text",
                            "media_hashes": "dummy media hashes",
                        },
                    },
                    "write_results": [{"stream_id": "dummy_stream_id"}],
                },
                exception_message=(
                    {
                        "write_results": [],
                        "is_data_on_sync_db": False,
                    },
                    Event.DAILY_ORBIS.value,
                ),
            )
        ],
    )
    def test__pre_task(self, test_case: TaskTestCase):
        """Test the _post_task method."""
        super()._pre_task_base_test(test_case)
        assert self.mock_task_preparation_object.behaviour.context.state.ceramic_data == [
            {
                "op": "create",
                "data": {
                    "body": {
                        "text": "dummy text",
                        "media_hashes": "dummy media hashes",
                    },
                    "context": "z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
                },
                "extra_metadata": {
                    "family": "orbis",
                    "tags": ["orbis", "post"],
                    "schema": "k1dpgaqe3i64kjuyet4w0zyaqwamf9wrp1jim19y27veqkppo34yghivt2pag4wxp0fv2yl04ypy3enwg9eisk6zkcq0a8buskv2tyq5rlldhi2vg3fkmfug4",
                },
                "did_str": "z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
                "did_seed": "0101010101010101010101010101010101010101010101010101010101010101",
            }
        ]


class TestUpdateCentaursPreparation(BaseTaskTest):
    """Test the UpdateCentaursPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=UpdateCentaursPreparation,
                exception_message=False,
            )
        ],
    )
    @patch(
        "packages.valory.skills.decision_making_abci.tasks.write_stream_preparation.WriteStreamPreparation.check_extra_conditions"
    )
    def test_check_extra_conditions_not_proceed(
        self, mock_check_extra_conditions, test_case: TaskTestCase
    ):
        """Test the check_extra_conditions method when not proceed."""
        mock_check_extra_conditions.return_value = iter(
            [
                None,
            ]
        )
        super().check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=UpdateCentaursPreparation,
                exception_message=False,
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                },
            ),
        ],
    )
    def test_check_extra_conditions(self, test_case: TaskTestCase):
        """Test the check_extra_conditions method when the centaur id is not in centaur id to secrets."""
        super().check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=UpdateCentaursPreparation,
                exception_message=(
                    {
                        "has_centaurs_changes": False,
                    },
                    None,
                ),
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                },
            )
        ],
    )
    def test__post_task(self, test_case: TaskTestCase):
        """Test the _post_task method."""
        super()._post_task_base_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=UpdateCentaursPreparation,
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {
                        "centaurs_data": DUMMY_CENTAURS_DATA,
                    },
                },
                exception_message=(
                    {
                        "write_results": [],
                        "is_data_on_sync_db": False,
                    },
                    Event.UPDATE_CENTAURS.value,
                ),
            ),
        ],
    )
    def test__pre_task(self, test_case: TaskTestCase):
        """Test the _post_task method."""
        super()._pre_task_base_test(test_case)
        assert self.mock_task_preparation_object.behaviour.context.state.ceramic_data == [
            {
                "op": "update",
                "stream_id": "dummy_centaurs_stream_id",
                "data": DUMMY_CENTAURS_DATA,
                "did_str": "did:key:z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
                "did_seed": None,
            }
        ]


class TestWriteContributeDBPreparation(BaseTaskTest):
    """Test the WriteContributeDBPreparation class."""

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=WriteContributeDBPreparation,
                exception_message=False,
            )
        ],
    )
    @patch(
        "packages.valory.skills.decision_making_abci.tasks.write_stream_preparation.WriteStreamPreparation.check_extra_conditions"
    )
    def test_check_extra_conditions_not_proceed(
        self,
        mock_check_extra_conditions,
        test_case: TaskTestCase,
    ):
        """Test the check_extra_conditions method."""
        mock_check_extra_conditions.return_value = iter(
            [
                None,
            ]
        )
        super().check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=WriteContributeDBPreparation,
                exception_message=False,
            )
        ],
    )
    def test_check_extra_conditions(
        self,
        test_case: TaskTestCase,
    ):
        """Test the check_extra_conditions method."""
        super().check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=WriteContributeDBPreparation,
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {
                        "centaurs_data": DUMMY_CENTAURS_DATA,
                    },
                },
                exception_message=(
                    {
                        "is_data_on_sync_db": False,
                    },
                    Event.WRITE_CONTRIBUTE_DB.value,
                ),
            ),
        ],
    )
    def test__pre_task(self, test_case: TaskTestCase):
        """Test the _post_task method."""
        super()._pre_task_base_test(test_case)
        assert self.mock_task_preparation_object.behaviour.context.state.ceramic_data == [
            {
                "op": "update",
                "stream_id": "ceramic_db_stream_id",
                "data": {
                    "module_data": {
                        "dynamic_nft": {},
                        "generic": {"latest_update_id": 0},
                        "twitter": {
                            "current_period": "1970-01-01",
                            "latest_mention_tweet_id": 0,
                        },
                    },
                    "users": {},
                },
                "did_str": "did:key:z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
                "did_seed": None,
            }
        ]

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=WriteContributeDBPreparation,
                exception_message=(
                    {
                        "pending_write": False,
                    },
                    None,
                ),
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                },
            )
        ],
    )
    def test__post_task(self, test_case: TaskTestCase):
        """Test the _post_task method."""
        super()._post_task_base_test(test_case)
