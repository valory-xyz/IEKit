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

"""This module contains the shared state for the abci skill of GenericScoringAbciApp."""

from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.decision_making_abci.models import (
    CeramicDB as BaseCeramicDB,
)
from packages.valory.skills.decision_making_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.generic_scoring_abci.rounds import GenericScoringAbciApp


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = GenericScoringAbciApp


Params = BaseParams
Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
CeramicDB = BaseCeramicDB
