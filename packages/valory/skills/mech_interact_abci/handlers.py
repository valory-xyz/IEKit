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

"""This module contains the handlers for the skill of MechInteractAbciApp."""

from typing import cast

from aea.protocols.base import Message
from aea.skills.base import Handler

from packages.valory.protocols.acn_data_share.message import AcnDataShareMessage
from packages.valory.skills.abstract_round_abci.handlers import (
    ABCIRoundHandler as BaseABCIRoundHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    ContractApiHandler as BaseContractApiHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    HttpHandler as BaseHttpHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    IpfsHandler as BaseIpfsHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    LedgerApiHandler as BaseLedgerApiHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    SigningHandler as BaseSigningHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    TendermintHandler as BaseTendermintHandler,
)
from packages.valory.skills.mech_interact_abci.states.base import (
    MECH_RESPONSE,
    MechInteractionResponse,
)


ABCIHandler = BaseABCIRoundHandler
HttpHandler = BaseHttpHandler
SigningHandler = BaseSigningHandler
LedgerApiHandler = BaseLedgerApiHandler
ContractApiHandler = BaseContractApiHandler
TendermintHandler = BaseTendermintHandler
IpfsHandler = BaseIpfsHandler


class AcnHandler(Handler):
    """The ACN response handler."""

    SUPPORTED_PROTOCOL = AcnDataShareMessage.protocol_id

    def setup(self) -> None:
        """Set up the handler."""

    def teardown(self) -> None:
        """Tear down the handler."""

    @property
    def current_mech_response(self) -> MechInteractionResponse:
        """Get the current mech response."""
        # accessing the agent shared state, NOT the behaviour's shared state
        return self.context.shared_state.get(MECH_RESPONSE, None)

    def handle(self, message: Message) -> None:
        """Handle incoming Tendermint config-sharing messages"""
        message = cast(AcnDataShareMessage, message)
        handler_name = f"_{message.performative.value}"
        handler = getattr(self, handler_name, None)
        if handler is None:
            self.context.logger.error(f"Unrecognized performative: {message}")
            return

        handler(message)

    def _data(self, message: AcnDataShareMessage) -> None:
        """Handle the data performative."""
        if self.current_mech_response is None:
            self.context.logger.error("No mech response was expected yet.")
            return

        if str(self.current_mech_response.requestId) != str(message.request_id):
            self.context.logger.error(
                f"The request ID does not match the expected one. "
                f"Expected: {self.current_mech_response.requestId}, got: {message.request_id}"
            )
            return

        self.current_mech_response.response_data = cast(bytes, message.content)
        self.current_mech_response.sender_address = message.sender
