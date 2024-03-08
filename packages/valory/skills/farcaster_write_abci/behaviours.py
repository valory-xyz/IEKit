# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
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

"""This package contains round behaviours of FarcasterWriteAbciApp."""

import json
from abc import ABC
from typing import Generator, Optional, Set, Type, cast

from packages.valory.connections.farcaster.connection import (
    PUBLIC_ID as FARCASTER_CONNECTION_PUBLIC_ID,
)
from packages.valory.protocols.srr.dialogues import SrrDialogue, SrrDialogues
from packages.valory.protocols.srr.message import SrrMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.abstract_round_abci.common import (
    RandomnessBehaviour,
    SelectKeeperBehaviour,
)
from packages.valory.skills.abstract_round_abci.models import Requests
from packages.valory.skills.farcaster_write_abci.models import Params
from packages.valory.skills.farcaster_write_abci.payloads import FarcasterWritePayload
from packages.valory.skills.farcaster_write_abci.rounds import (
    FarcasterWriteAbciApp,
    FarcasterWriteRound,
    RandomnessFarcasterRound,
    RandomnessPayload,
    SelectKeeperFarcasterRound,
    SelectKeeperPayload,
    SynchronizedData,
)


class BaseFarcasterWriteBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


class RandomnessFarcasterWriteBehaviour(RandomnessBehaviour, BaseFarcasterWriteBehaviour):
    """Retrieve randomness."""

    matching_round = RandomnessFarcasterRound
    payload_class = RandomnessPayload


class SelectKeeperFarcasterWriteBehaviour(
    SelectKeeperBehaviour, BaseFarcasterWriteBehaviour
):
    """Select the keeper agent."""

    matching_round = SelectKeeperFarcasterRound
    payload_class = SelectKeeperPayload


class FarcasterWriteBehaviour(BaseFarcasterWriteBehaviour):
    """FarcasterWriteBehaviour"""

    matching_round: Type[AbstractRound] = FarcasterWriteRound

    def _i_am_casting(self) -> bool:
        """Indicates if the current agent is casting or not."""
        return (
            self.context.agent_address
            == self.synchronized_data.most_voted_keeper_address
        )

    def async_act(self) -> Generator[None, None, None]:
        """Do the action"""
        if self._i_am_casting():
            yield from self._cast()
        else:
            yield from self._wait_for_cast()

    def _wait_for_cast(self) -> Generator:
        """Do the non-sender action."""
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            self.context.logger.info(
                f"Waiting for the keeper to do its keeping: {self.synchronized_data.most_voted_keeper_address}"
            )
            yield from self.wait_until_round_end()
        self.set_done()

    def _cast(self) -> Generator:
        """Do the sender action"""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            write_index = self.synchronized_data.write_index
            write_data = self.synchronized_data.write_data

            if write_data:
                text = write_data[write_index]["text"]
                self.context.logger.info(f"Creating cast with text: {text}")
                response = yield from self._create_cast(text=text)
                response_data = json.loads(response.payload)

                if response.error:
                    self.context.logger.error(
                        f"Writing cast failed with following error message: {response.payload}"
                    )
                    payload_data = {"success": False, "cast_id": None}
                else:
                    self.context.logger.info(f"Posted cast with ID: {response_data['cast_id']}")
                    payload_data = {"success": True, "cast_id": response_data["cast_id"]}

            # No casts to publish
            else:
                self.context.logger.info(f"No casts")
                payload_data = {"success": True, "cast_id": None}

            payload = FarcasterWritePayload(
                sender=self.context.agent_address,
                content=json.dumps(
                    payload_data,
                    sort_keys=True,
                ),
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _create_cast(
        self,
        text: str,
    ) -> Generator[None, None, SrrMessage]:
        """Send an http request message from the skill context."""
        srr_dialogues = cast(SrrDialogues, self.context.srr_dialogues)
        farcaster_message, srr_dialogue = srr_dialogues.create(
            counterparty=str(FARCASTER_CONNECTION_PUBLIC_ID),
            performative=SrrMessage.Performative.REQUEST,
            payload=json.dumps(
                {"method": "post_cast", "args": {"text": text}}
            ),
        )
        farcaster_message = cast(SrrMessage, farcaster_message)
        srr_dialogue = cast(SrrDialogue, srr_dialogue)
        response = yield from self._do_farcaster_request(
            farcaster_message, srr_dialogue
        )
        return response

    def _do_farcaster_request(
        self,
        message: SrrMessage,
        dialogue: SrrDialogue,
        timeout: Optional[float] = None,
    ) -> Generator[None, None, SrrMessage]:
        """Do a request and wait the response, asynchronously."""

        self.context.outbox.put_message(message=message)
        request_nonce = self._get_request_nonce_from_dialogue(dialogue)
        cast(Requests, self.context.requests).request_id_to_callback[
            request_nonce
        ] = self.get_callback_request()
        response = yield from self.wait_for_message(timeout=timeout)
        return response


class FarcasterWriteRoundBehaviour(AbstractRoundBehaviour):
    """FarcasterWriteRoundBehaviour"""

    initial_behaviour_cls = RandomnessFarcasterWriteBehaviour
    abci_app_cls = FarcasterWriteAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        RandomnessFarcasterWriteBehaviour,
        SelectKeeperFarcasterWriteBehaviour,
        FarcasterWriteBehaviour,
    ]
