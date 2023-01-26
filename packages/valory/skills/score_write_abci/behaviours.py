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

"""This package contains round behaviours of ScoreWriteAbciApp."""

import json
from typing import Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.score_write_abci.models import Params
from packages.valory.skills.score_write_abci.rounds import (
    ScoreWriteAbciApp,
    SynchronizedData,
    CeramicWriteRound,
    RandomnessRound,
    SelectKeeperRound,
    VerificationRound,
)
from packages.valory.skills.abstract_round_abci.common import (
    RandomnessBehaviour,
    SelectKeeperBehaviour,
)
from packages.valory.skills.score_write_abci.payloads import (
    RandomnessPayload,
    SelectKeeperPayload,
    CeramicWritePayload,
    VerificationPayload,
)
import random


class ScoreWriteBaseBehaviour(BaseBehaviour):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

class RandomnessBehaviour(RandomnessBehaviour):
    """Retrieve randomness."""

    matching_round = RandomnessRound
    payload_class = RandomnessPayload


class SelectKeeperCeramicBehaviour(
    SelectKeeperBehaviour, ScoreWriteBaseBehaviour
):
    """Select the keeper agent."""

    matching_round = SelectKeeperRound
    payload_class = SelectKeeperPayload

    def async_act(self) -> Generator:
        """Do the action."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            participants = sorted(self.synchronized_data.participants)
            random.seed(self.synchronized_data.most_voted_randomness, 2)  # nosec
            index = random.randint(0, len(participants) - 1)  # nosec

            keeper_address = participants[index]

            self.context.logger.info(f"Selected a new keeper: {keeper_address}.")
            payload = SelectKeeperPayload(self.context.agent_address, keeper_address)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class CeramicWriteBehaviour(ScoreWriteBaseBehaviour):
    """CeramicWriteBehaviour"""

    matching_round: Type[AbstractRound] = CeramicWriteRound

    def _i_am_not_sending(self) -> bool:
        """Indicates if the current agent is the sender or not."""
        return (
            self.context.agent_address
            != self.synchronized_data.most_voted_keeper_address
        )

    def async_act(self) -> Generator[None, None, None]:
        """Do the action"""
        if self._i_am_not_sending():
            yield from self._not_sender_act()
        else:
            yield from self._sender_act()

    def _not_sender_act(self) -> Generator:
        """Do the non-sender action."""
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            self.context.logger.info(
                f"Waiting for the keeper to do its keeping: {self.synchronized_data.most_voted_keeper_address}"
            )
            yield from self.wait_until_round_end()
        self.set_done()

    def _sender_act(self) -> Generator:
        """Do the sender action"""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            success = yield from self._write_ceramic_data()
            if success:
                self.context.logger.info(f"Wrote scores to ceramic stream with id: {self.params.ceramic_stream_id}")
                payload_content = CeramicWriteRound.SUCCCESS_PAYLOAD
            else:
                self.context.logger.info(f"An error happened while wroting scores to ceramic stream with id: {self.params.ceramic_stream_id}")
                payload_content = CeramicWriteRound.ERROR_PAYLOAD

            sender = self.context.agent_address
            payload = CeramicWritePayload(sender=sender, content=payload_content)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _write_ceramic_data(self) -> Generator[None, None, bool]:
        """Write the scores to the Ceramic stream"""

        api_base = self.params.ceramic_api_base
        api_endpoint = self.params.ceramic_api_commit_endpoint
        url = api_base + api_endpoint.replace("{stream_id}", self.params.ceramic_stream_id)

        self.context.logger.info(f"Writing scores to Ceramic API [{url}]")
        response = yield from self.get_http_response(
            method="GET",
            url=url,
            content=json.dumps(
                self.synchronized_data.user_to_scores
            ).encode(),
        )

        if response.status_code != 200:
            api_data = json.loads(response.body)
            self.context.logger.info(f"API error {response.status_code}: {api_data}")
            return False

        return True


class VerificationBehaviour(ScoreWriteBaseBehaviour):
    """VerificationBehaviour"""

    matching_round: Type[AbstractRound] = VerificationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            success = yield from self._verify_ceramic_data()
            if success:
                self.context.logger.info("Data verification successful")
                payload_content = CeramicWriteRound.SUCCCESS_PAYLOAD
            else:
                self.context.logger.info("An error happened while verifying data")
                payload_content = CeramicWriteRound.ERROR_PAYLOAD

            sender = self.context.agent_address
            payload = VerificationPayload(sender=sender, content=payload_content)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _verify_ceramic_data(self) -> Generator[None, None, bool]:
        """Write the scores to the Ceramic stream"""

        api_base = self.params.ceramic_api_base
        api_endpoint = self.params.ceramic_api_read_endpoint
        url = api_base + api_endpoint.replace("{stream_id}", self.params.ceramic_stream_id)

        self.context.logger.info(f"Writing scores to Ceramic API [{url}]")
        response = yield from self.get_http_response(
            method="GET",
            url=url,
        )

        api_data = json.loads(response.body)

        if response.status_code != 200:
            self.context.logger.info(f"API error {response.status_code}: {api_data}")
            return False

        if api_data["<TODO>"] != self.synchronized_data.user_to_scores:
            self.context.logger.info(f"Verification failed: data does not match. Expected: {self.synchronized_data.user_to_scores}, Got: {api_data['<TODO>']}")
            return False

        return True


class ScoreWriteRoundBehaviour(AbstractRoundBehaviour):
    """ScoreWriteRoundBehaviour"""

    initial_behaviour_cls = RandomnessBehaviour
    abci_app_cls = ScoreWriteAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        RandomnessBehaviour,
        SelectKeeperCeramicBehaviour,
        CeramicWriteBehaviour,
        VerificationBehaviour,
    ]
