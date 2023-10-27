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

"""This package contains round behaviours of CeramicReadAbciApp."""

import json
from abc import ABC
from typing import Generator, Optional, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.ceramic_read_abci.ceramic.payloads import (
    build_data_from_commits,
)
from packages.valory.skills.ceramic_read_abci.models import Params
from packages.valory.skills.ceramic_read_abci.rounds import (
    CeramicReadAbciApp,
    StreamReadPayload,
    StreamReadRound,
    SynchronizedData,
)


class CeramicReadBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the ceramic_read_abci skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    def _get_stream_data(self, stream_id: str) -> Generator[None, None, Optional[dict]]:
        """Get the current data from a Ceramic stream"""

        api_base = self.params.ceramic_api_base
        api_endpoint = self.params.ceramic_api_read_endpoint
        url = api_base + api_endpoint.replace("{stream_id}", stream_id)

        self.context.logger.info(f"Reading data from Ceramic API [{url}]")
        response = yield from self.get_http_response(
            method="GET",
            url=url,
        )

        if response.status_code != 200:
            self.context.logger.error(
                f"API error while reading the stream: {response.status_code}: '{response.body!r}'"
            )
            return None

        try:
            api_data = json.loads(response.body)
        except json.decoder.JSONDecodeError:
            self.context.logger.error(
                f"API error while loading the response json. Response body: '{response.body!r}'"
            )
            return None

        # Extract first and last commit info
        genesis_cid_str = api_data["commits"][0]["cid"]
        previous_cid_str = api_data["commits"][-1]["cid"]

        # Rebuild the current data
        data = build_data_from_commits(api_data["commits"])

        return {
            "genesis_cid_str": genesis_cid_str,
            "previous_cid_str": previous_cid_str,
            "data": data,
        }


class StreamReadBehaviour(CeramicReadBaseBehaviour):
    """StreamReadBehaviour"""

    matching_round: Type[AbstractRound] = StreamReadRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            # stream_id and read_target_property can be set either in the synchronized_data or as a param. The former has higher priority.
            stream_id = (
                self.synchronized_data.read_stream_id
                or self.params.default_read_stream_id
            )
            if not stream_id:
                raise ValueError(
                    "read_stream_id has not been set neither in the synchronized_data nor as a default parameter"
                )

            read_target_property = (
                self.synchronized_data.read_target_property
                or self.params.default_read_target_property
            )
            if not read_target_property:
                raise ValueError(
                    "read_target_property has not been set neither in the synchronized_data nor as a default parameter"
                )

            # Get the stream data
            stream_data = yield from self._get_stream_data(stream_id)
            if not stream_data:
                payload_content = StreamReadRound.ERROR_PAYLOAD
            else:
                payload_content = {
                    "stream_data": stream_data["data"],
                    "read_target_property": read_target_property,
                }
                self.context.logger.info(
                    f"Loading data into 'synchronized_data.{read_target_property}'"
                )

            # Send the payload
            sender = self.context.agent_address
            payload = StreamReadPayload(
                sender=sender, content=json.dumps(payload_content, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class CeramicReadRoundBehaviour(AbstractRoundBehaviour):
    """CeramicReadRoundBehaviour"""

    initial_behaviour_cls = StreamReadBehaviour
    abci_app_cls = CeramicReadAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [StreamReadBehaviour]
