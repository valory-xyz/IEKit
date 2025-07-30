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

"""This package contains round behaviours of AgentDBAbciApp."""

from abc import ABC
from typing import Any, Set, Type

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.agent_db_abci.rounds import AgentDBAbciApp, AgentDBRound


class AgentDBBehaviour(BaseBehaviour, ABC):
    """AgentDBBehaviour"""

    matching_round: Type[AbstractRound] = AgentDBRound

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        """Initialize the behaviour."""
        super().__init__(**kwargs)

        self.context.agent_db_client.initialize(
            address=self.context.agent_address,
            http_request_func=self.get_http_response,
            signing_func=self.get_signature,
            logger=self.context.logger,
            sleep_func=self.sleep,
        )


class AgentDBRoundBehaviour(AbstractRoundBehaviour):
    """AgentDBRoundBehaviour"""

    initial_behaviour_cls = AgentDBBehaviour
    abci_app_cls = AgentDBAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [AgentDBBehaviour]
