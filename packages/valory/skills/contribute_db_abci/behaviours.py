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

"""This package contains round behaviours of ContributeDBAbciApp."""

from abc import ABC
from typing import Any, Generator, Set, Type, cast

from eth_account import Account

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.contribute_db_abci.models import Params
from packages.valory.skills.contribute_db_abci.rounds import (
    ContributeDBAbciApp,
    DBLoadPayload,
    DBLoadRound,
)


class ContributeDBBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the common apps' skill."""

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        """Initialize the behaviour."""
        super().__init__(**kwargs)

        self.context.agent_db_client.initialize(
            address=Account.from_key(self.params.contribute_db_pkey).address,
            http_request_func=self.get_http_response,
            signing_func_or_pkey=self.params.contribute_db_pkey,
            logger=self.context.logger,
        )

        self.context.contribute_db.initialize(
            client=self.context.agent_db_client,
            agent_address=self.context.agent_address
        )

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


class DBLoadBehaviour(ContributeDBBehaviour):
    """DBLoadBehaviour"""

    matching_round: Type[AbstractRound] = DBLoadRound

    def async_act(self) -> Generator:
        """Get a list of the new tokens."""
        with self.context.benchmark_tool.measure(
            self.behaviour_id,
        ).local():

            # Load AgentDB
            yield from self.context.contribute_db.load_from_remote_db()

        with self.context.benchmark_tool.measure(
            self.behaviour_id,
        ).consensus():
            payload = DBLoadPayload(
                sender=self.context.agent_address,
            )
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class ContributeDBRoundBehaviour(AbstractRoundBehaviour):
    """ContributeDBRoundBehaviour"""

    initial_behaviour_cls = DBLoadBehaviour
    abci_app_cls = ContributeDBAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        DBLoadBehaviour,
    ]
