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
from packages.valory.agents.impact_evaluator.tests.helpers.fixtures import (  # noqa: F401
    UseHardHatImpactEvaluatorBaseTest,
    UseMockTwitterApiBaseTest,
)
from packages.valory.agents.impact_evaluator.tests.helpers.docker import (
    DEFAULT_JSON_SERVER_ADDR as _DEFAULT_JSON_SERVER_ADDR,
)
from packages.valory.agents.impact_evaluator.tests.helpers.docker import (
    DEFAULT_JSON_SERVER_PORT as _DEFAULT_JSON_SERVER_PORT,
)
from packages.valory.skills.registration_abci.rounds import RegistrationStartupRound
from packages.valory.skills.reset_pause_abci.rounds import ResetAndPauseRound
from packages.valory.skills.dynamic_nft_abci.rounds import (
    NewTokensRound,
)
from packages.valory.skills.score_read_abci.rounds import (
    TwitterObservationRound,
    ScoringRound
)
from packages.valory.skills.score_write_abci.rounds import (
    RandomnessRound,
    SelectKeeperRound,
    CeramicWriteRound,
    VerificationRound,
    ScoreAddRound,
    StartupScoreReadRound,
)


HAPPY_PATH: Tuple[RoundChecks, ...] = (
    RoundChecks(RegistrationStartupRound.auto_round_id()),
    RoundChecks(StartupScoreReadRound.auto_round_id(), n_periods=1),
    RoundChecks(TwitterObservationRound.auto_round_id(), n_periods=2),
    RoundChecks(ScoringRound.auto_round_id(), n_periods=2),
    RoundChecks(ScoreAddRound.auto_round_id(), n_periods=2),
    RoundChecks(RandomnessRound.auto_round_id(), n_periods=2),
    RoundChecks(SelectKeeperRound.auto_round_id(), n_periods=2),
    RoundChecks(CeramicWriteRound.auto_round_id(), n_periods=2),
    RoundChecks(VerificationRound.auto_round_id(), n_periods=2),
    RoundChecks(NewTokensRound.auto_round_id(), n_periods=2),
    RoundChecks(ResetAndPauseRound.auto_round_id(), n_periods=2),
)

# strict check log messages of the happy path
STRICT_CHECK_STRINGS = (
    "Retrieved initial score data from Ceramic:",
    "Retrieving mentions from Twitter API",
    "Calculated score data:",
    "Calculated new total points",
    "Data verification successful",
    "Retrieved wallet data from Ceramic:",
    "Got the new token data:",
    "Period end",
)
PACKAGES_DIR = Path(__file__).parent.parent.parent.parent.parent


MOCK_TWITTER_API_ADDRESS = _DEFAULT_JSON_SERVER_ADDR
MOCK_TWITTER_API_PORT = _DEFAULT_JSON_SERVER_PORT

MOCK_CERAMIC_API_ADDRESS = _DEFAULT_JSON_SERVER_ADDR
MOCK_CERAMIC_API_PORT = _DEFAULT_JSON_SERVER_PORT


@pytest.mark.usefixtures("ipfs_daemon")
class BaseTestEnd2EndImpactEvaluatorNormalExecution(BaseTestEnd2EndExecution):
    """Base class for the impact evaluator service e2e tests."""

    agent_package = "valory/impact_evaluator:0.1.0"
    skill_package = "valory/impact_evaluator_abci:0.1.0"
    wait_to_finish = 180
    strict_check_strings = STRICT_CHECK_STRINGS
    happy_path = HAPPY_PATH
    package_registry_src_rel = PACKAGES_DIR

    __param_args_prefix = f"vendor.valory.skills.{PublicId.from_str(skill_package).name}.models.params.args"

    extra_configs = [
        {
            "dotted_path": f"{__param_args_prefix}.twitter_api_base",
            "value": f"{MOCK_TWITTER_API_ADDRESS}:{MOCK_TWITTER_API_PORT}/",
        },
        {
            "dotted_path": f"{__param_args_prefix}.twitter_api_args",
            "value": "",
        },
        {
            "dotted_path": f"{__param_args_prefix}.ceramic_api_base",
            "value": f"{MOCK_CERAMIC_API_ADDRESS}:{MOCK_CERAMIC_API_PORT}/",
        },
        {
            "dotted_path": f"{__param_args_prefix}.points_to_image_hashes",
            "value": '{"0": "bafybeiabtdl53v2a3irrgrg7eujzffjallpymli763wvhv6gceurfmcemm", "100": "bafybeid46w6yzbehir7ackcnsyuasdkun5aq7jnckt4sknvmiewpph776q", "50000": "bafybeigbxlwzljbxnlwteupmt6c6k7k2m4bbhunvxxa53dc7niuedilnr4", "100000": "bafybeiawxpq4mqckbau3mjwzd3ic2o7ywlhp6zqo7jnaft26zeqm3xsjjy", "150000": "bafybeie6k53dupf7rf6622rzfxu3dmlv36hytqrmzs5yrilxwcrlhrml2m"}',
        },
        {
            "dotted_path": f"{__param_args_prefix}.scores_stream_id",
            "value": "user_to_points_stream_id_e2e",
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
class TestEnd2EndImpactEvaluatorSingleAgent(
    BaseTestEnd2EndImpactEvaluatorNormalExecution,
    UseMockTwitterApiBaseTest,
    UseHardHatImpactEvaluatorBaseTest,
):
    """Test the impact evaluator skill with only one agent."""


@pytest.mark.e2e
@pytest.mark.parametrize("nb_nodes", (2,))
class TestEnd2EndImpactEvaluatorTwoAgents(
    BaseTestEnd2EndImpactEvaluatorNormalExecution,
    UseMockTwitterApiBaseTest,
    UseHardHatImpactEvaluatorBaseTest,
):
    """Test the impact evaluator skill with two agents."""


@pytest.mark.e2e
@pytest.mark.parametrize("nb_nodes", (4,))
class TestEnd2EndImpactEvaluatorFourAgents(
    BaseTestEnd2EndImpactEvaluatorNormalExecution,
    UseMockTwitterApiBaseTest,
    UseHardHatImpactEvaluatorBaseTest,
):
    """Test the impact evaluator skill with four agents."""
