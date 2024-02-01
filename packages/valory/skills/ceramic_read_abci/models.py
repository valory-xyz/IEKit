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

"""This module contains the shared state for the abci skill of CeramicReadAbciApp."""

from typing import Any, Dict, Optional

from aea.skills.base import SkillContext

from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.ceramic_read_abci.rounds import CeramicReadAbciApp


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = CeramicReadAbciApp

    def __init__(
        self,
        *args: Any,
        skill_context: SkillContext,
        **kwargs: Any,
    ) -> None:
        """Initialize the state."""
        super().__init__(*args, skill_context=skill_context, **kwargs)
        self.ceramic_data: Optional[Dict] = None


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the parameters object."""

        self.ceramic_api_base = kwargs.get(
            "ceramic_api_base"
        )  # shared param, can't use ensure
        self.ceramic_api_read_endpoint = kwargs.get("ceramic_api_read_endpoint")

        # These parameters are optional, therefore we do not use ensure
        self.default_read_stream_id = kwargs.pop("default_read_stream_id", None)
        self.default_read_target_property = kwargs.pop(
            "default_read_target_property", None
        )
        super().__init__(*args, **kwargs)


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
