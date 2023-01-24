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
from collections import OrderedDict
from typing import Dict, Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.score_write_abci.models import Params
from packages.valory.skills.score_write_abci.rounds import (
    ScoreWriteAbciApp,
    SynchronizedData,
    CeramicWritePayload,
    CeramicWriteRound,
    RandomnessPayload,
    RandomnessRound,
    KeeperSelectionPayload,
    KeeperSelectionRound,
    VerificationPayload,
    VerificationRound,
)
from packages.valory.skills.abstract_round_abci.common import (
    RandomnessBehaviour,
    SelectKeeperBehaviour,
)


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

class RandomnessTransactionSubmissionBehaviour(RandomnessBehaviour):
    """Retrieve randomness."""

    matching_round = RandomnessTransactionSubmissionRound
    payload_class = RandomnessPayload



class SelectKeeperTransactionSubmissionBehaviourA(
    SelectKeeperBehaviour, ScoreWriteBaseBehaviour
):
    """Select the keeper agent."""

    matching_round = SelectKeeperTransactionSubmissionRoundA
    payload_class = SelectKeeperPayload

    def async_act(self) -> Generator:
        """Do the action."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            keepers = deque((self._select_keeper(),))
            payload = self.payload_class(
                self.context.agent_address, self.serialized_keepers(keepers, 1)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()



class CeramicWriteBehaviour(ScoreWriteBaseBehaviour):
    """CeramicWriteBehaviour"""

    matching_round: Type[AbstractRound] = CeramicWriteRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            success = yield from self._write_ceramic_data()
            if success:
                self.context.logger.info(f"Wrote scores to ceramic stream with id: {stream_id}")
                payload_content = CeramicWriteRound.SUCCCESS_PAYLOAD
            else:
                self.context.logger.info(f"An error happened while wroting scores to ceramic stream with id: {stream_id}")
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
        api_endpoint = self.params.ceramic_api_write_endpoint
        url = api_base + api_endpoint.replace("{stream_id}", self.params.ceramic_stream_id)

        self.context.logger.info(f"Writing scores to Ceramic API [{url}]")
        response = yield from self.get_http_response(
            method="GET",
            url=url,
            content=json.dumps(
                self.params.user_to_scores
            ).encode(),
        )

        if response.status_code != 200:
            api_data = json.loads(response.body)
            self.context.logger.info(f"API error {response.status_code}: {api_data}")
            return False

        return True


class VerificationBehaviour(ScoreWriteBaseBehaviour):
    """VerificationBehaviour"""

    matching_round: Type[AbstractRound] = CeramicWriteRound

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
            payload = CeramicWritePayload(sender=sender, content=payload_content)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _verify_ceramic_data(self) -> Generator[None, None, bool]:
        """Write the scores to the Ceramic stream"""

        api_base = self.params.ceramic_api_base
        api_endpoint = self.params.ceramic_api_write_endpoint
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

        if api_data["<TODO>"] != self.params.user_to_scores:
            self.context.logger.info(f"Verification failed: data does not match. Expected: {self.params.user_to_scores}, Got: {api_data['<TODO>']}")
            return False

        return True


class ScoreWriteRoundBehaviour(AbstractRoundBehaviour):
    """ScoreWriteRoundBehaviour"""

    initial_behaviour_cls = TwitterObservationBehaviour
    abci_app_cls = ScoreWriteAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        ScoringBehaviour,
        TwitterObservationBehaviour,
    ]
