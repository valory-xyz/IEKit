# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2022 Valory AG
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

"""Integration tests for the valory/oracle_abci skill."""

from pathlib import Path
from typing import Tuple
import pytest
from aea.configurations.data_types import PublicId
from aea_test_autonomy.base_test_classes.agents import (
    BaseTestEnd2EndExecution,
    RoundChecks,
)
from aea_test_autonomy.fixture_helpers import abci_host  # noqa: F401
from aea_test_autonomy.fixture_helpers import abci_port  # noqa: F401
from aea_test_autonomy.fixture_helpers import flask_tendermint  # noqa: F401
from aea_test_autonomy.fixture_helpers import ganache_addr  # noqa: F401
from aea_test_autonomy.fixture_helpers import ganache_configuration  # noqa: F401
from aea_test_autonomy.fixture_helpers import ganache_port  # noqa: F401
from aea_test_autonomy.fixture_helpers import ganache_scope_class  # noqa: F401
from aea_test_autonomy.fixture_helpers import ganache_scope_function  # noqa: F401
from aea_test_autonomy.fixture_helpers import hardhat_addr  # noqa: F401
from aea_test_autonomy.fixture_helpers import hardhat_port  # noqa: F401
from aea_test_autonomy.fixture_helpers import key_pairs  # noqa: F401
from aea_test_autonomy.fixture_helpers import tendermint  # noqa: F401
from aea_test_autonomy.fixture_helpers import tendermint_port  # noqa: F401
from aea_test_autonomy.fixture_helpers import ipfs_daemon  # noqa: F401
from aea_test_autonomy.fixture_helpers import ipfs_domain  # noqa: F401
from packages.valory.agents.contribution.tests.helpers.fixtures import (  # noqa: F401
    UseHardHatContributionBaseTest,
    UseMockGoogleSheetsApiBaseTest,
)
from packages.valory.agents.contribution.tests.helpers.docker import (
    DEFAULT_JSON_SERVER_ADDR as _DEFAULT_JSON_SERVER_ADDR,
)
from packages.valory.agents.contribution.tests.helpers.docker import (
    DEFAULT_JSON_SERVER_PORT as _DEFAULT_JSON_SERVER_PORT,
)
from packages.valory.skills.registration_abci.rounds import RegistrationStartupRound
from packages.valory.skills.reset_pause_abci.rounds import ResetAndPauseRound
from packages.valory.skills.dynamic_nft_abci.rounds import (
    NewTokensRound,
    LeaderboardObservationRound,
    ImageCodeCalculationRound,
    ImageGenerationRound,
    DBUpdateRound,
)


HAPPY_PATH: Tuple[RoundChecks, ...] = (
    RoundChecks(RegistrationStartupRound.auto_round_id()),
    RoundChecks(NewTokensRound.auto_round_id(), n_periods=2),
    RoundChecks(LeaderboardObservationRound.auto_round_id(), n_periods=2),
    RoundChecks(ImageCodeCalculationRound.auto_round_id(), n_periods=2),
    RoundChecks(ImageGenerationRound.auto_round_id(), n_periods=2),
    RoundChecks(DBUpdateRound.auto_round_id(), n_periods=2),
    RoundChecks(ResetAndPauseRound.auto_round_id(), n_periods=2),
)

# strict check log messages of the happy path
STRICT_CHECK_STRINGS = (
    "Got the new token list:",
    "Calculated token updates:",
    "Generated the following new images:",
    "Updating database tables",
    "Period end",
)
PACKAGES_DIR = Path(__file__).parent.parent.parent.parent.parent


MOCK_API_ADDRESS = _DEFAULT_JSON_SERVER_ADDR
MOCK_API_PORT = _DEFAULT_JSON_SERVER_PORT
MOCK_WHITELIST_ADDRESS = _DEFAULT_JSON_SERVER_ADDR
MOCK_IPFS_ADDRESS = _DEFAULT_JSON_SERVER_ADDR


@pytest.mark.usefixtures("ipfs_daemon")
class BaseTestEnd2EndContributionNormalExecution(BaseTestEnd2EndExecution):
    """Base class for the contribution service e2e tests."""

    agent_package = "valory/contribution:0.1.0"
    skill_package = "valory/contribution_abci:0.1.0"
    wait_to_finish = 180
    strict_check_strings = STRICT_CHECK_STRINGS
    happy_path = HAPPY_PATH
    package_registry_src_rel = PACKAGES_DIR

    __param_args_prefix = f"vendor.valory.skills.{PublicId.from_str(skill_package).name}.models.params.args"

    extra_configs = [
        {
            "dotted_path": f"{__param_args_prefix}.leaderboard_base_endpoint",
            "value": f"{MOCK_API_ADDRESS}:{MOCK_API_PORT}",
        },
        {
            "dotted_path": f"{__param_args_prefix}.leaderboard_sheet_id",
            "value": "mock_sheet_id",
        },
        {
            "dotted_path": f"{__param_args_prefix}.ipfs_domain_name",
            "value": "/dns/localhost/tcp/5001/http",
        },
        {
            "dotted_path": f"{__param_args_prefix}.whitelist_endpoint",
            "value": f"{MOCK_WHITELIST_ADDRESS}:{MOCK_API_PORT}/mock_whitelist",
        },
        {
            "dotted_path": f"{__param_args_prefix}.ipfs_gateway_base_url",
            "value": f"{MOCK_IPFS_ADDRESS}:{MOCK_API_PORT}/mock_ipfs/",
        },
    ]

    http_server_port_config = {
        "dotted_path": "vendor.fetchai.connections.http_server.config.port",
        "value": 8000,
    }

    def _BaseTestEnd2End__set_extra_configs(self) -> None:
        """Set the current agent's extra config overrides that are skill specific."""
        for config in self.extra_configs:
            self.set_config(**config)

        self.set_config(**self.http_server_port_config)
        self.http_server_port_config["value"] += 1  # port number increment


@pytest.mark.e2e
@pytest.mark.parametrize("nb_nodes", (1,))
class TestEnd2EndContributionSingleAgent(
    BaseTestEnd2EndContributionNormalExecution,
    UseMockGoogleSheetsApiBaseTest,
    UseHardHatContributionBaseTest,
):
    """Test the contribution skill with only one agent."""


@pytest.mark.e2e
@pytest.mark.parametrize("nb_nodes", (2,))
class TestEnd2EndContributionTwoAgents(
    BaseTestEnd2EndContributionNormalExecution,
    UseMockGoogleSheetsApiBaseTest,
    UseHardHatContributionBaseTest,
):
    """Test the contribution skill with two agents."""


@pytest.mark.e2e
@pytest.mark.parametrize("nb_nodes", (4,))
class TestEnd2EndContributionFourAgents(
    BaseTestEnd2EndContributionNormalExecution,
    UseMockGoogleSheetsApiBaseTest,
    UseHardHatContributionBaseTest,
):
    """Test the contribution skill with four agents."""
