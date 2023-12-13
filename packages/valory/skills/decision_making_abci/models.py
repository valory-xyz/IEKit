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

"""This module contains the shared state for the abci skill of DecisionMakingAbciApp."""

import json
from typing import Any

from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.decision_making_abci.rounds import DecisionMakingAbciApp


DEFAULT_PROMPT = """
Using the information in the text below, craft an engaging and relevant post that highlights key insights or facts from the text.
The post should be limited to {n_chars} characters. IMPORTANT: under absolutely no circumstances use links, hashtags # or emojis.
Text: {memory}
"""

SHORTENER_PROMPT = """
Rewrite the tweet to fit {n_chars} characters. If in doubt, make it shorter. IMPORTANT: under absolutely no circumstances use links, hashtags # or emojis.
Text: {text}
"""


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = DecisionMakingAbciApp


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the parameters object."""

        self.prompt_template = DEFAULT_PROMPT
        self.shortener_prompt_template = SHORTENER_PROMPT
        self.centaurs_stream_id = self._ensure("centaurs_stream_id", kwargs, str)
        self.ceramic_did_str = "did:key:" + kwargs.get("ceramic_did_str", "")
        self.ceramic_did_seed = kwargs.get("ceramic_did_seed")
        self.ceramic_db_stream_id = self._ensure("ceramic_db_stream_id", kwargs, str)
        self.manual_points_stream_id = self._ensure(
            "manual_points_stream_id", kwargs, str
        )
        self.centaur_id_to_secrets = json.loads(
            self._ensure("centaur_id_to_secrets", kwargs, str)
        )
        self.transaction_service_url = self._ensure(
            "transaction_service_url", kwargs, str
        )
        self.wveolas_address = self._ensure("wveolas_address", kwargs, str)
        super().__init__(*args, **kwargs)


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
