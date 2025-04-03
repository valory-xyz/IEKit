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

"""This module contains the response state of the mech interaction abci app."""

import json
from typing import Any, Callable, Dict, Generator, List, Optional

from web3.constants import ADDRESS_ZERO

from packages.valory.contracts.mech.contract import Mech
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import get_name
from packages.valory.skills.mech_interact_abci.behaviours.base import (
    DataclassEncoder,
    MechInteractBaseBehaviour,
    WaitableConditionType,
)
from packages.valory.skills.mech_interact_abci.behaviours.request import V1_HEX_PREFIX
from packages.valory.skills.mech_interact_abci.models import MechResponseSpecs
from packages.valory.skills.mech_interact_abci.payloads import MechResponsePayload
from packages.valory.skills.mech_interact_abci.states.base import (
    MECH_RESPONSE,
    MechInteractionResponse,
    MechRequest,
)
from packages.valory.skills.mech_interact_abci.states.response import MechResponseRound


IPFS_HASH_PREFIX = f"{V1_HEX_PREFIX}701220"


class MechResponseBehaviour(MechInteractBaseBehaviour):
    """A behaviour in which the agents receive the Mech's responses."""

    matching_round = MechResponseRound

    ARTIFACTS_KEY = "artifacts"
    BASE64_KEY = "base64"
    MAX_LOG_CHARS = 500

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Behaviour."""
        super().__init__(**kwargs)
        self._from_block: int = 0
        self._requests: List[MechRequest] = []
        self._response_hex: str = ""
        self._mech_responses: List[MechInteractionResponse] = (
            self.synchronized_data.mech_responses
        )
        self.current_mech_response: MechInteractionResponse = MechInteractionResponse(
            error="The mech's response has not been set!"
        )
        self.context.logger.info(f"Current mech response: {self.current_mech_response}")
        self._is_valid_acn_sender: bool = False

    @property
    def current_mech_response(self) -> MechInteractionResponse:
        """Get the current mech response."""
        # accessing the agent shared state, NOT the behaviour's shared state
        return self.context.shared_state[MECH_RESPONSE]

    @current_mech_response.setter
    def current_mech_response(self, response: MechInteractionResponse) -> None:
        """Set the current mech response."""
        self.context.shared_state[MECH_RESPONSE] = response

    @property
    def from_block(self) -> int:
        """Get the block number in which the request to the mech was settled."""
        return self._from_block

    @from_block.setter
    def from_block(self, from_block: int) -> None:
        """Set the block number in which the request to the mech was settled."""
        self._from_block = from_block

    @property
    def requests(self) -> List[MechRequest]:
        """Get the requests."""
        return self._requests

    @requests.setter
    def requests(self, requests: List[Dict[str, str]]) -> None:
        """Set the requests."""
        self._requests = [MechRequest(**request) for request in requests]

    @property
    def response_hex(self) -> str:
        """Get the hash of the response data."""
        return self._response_hex

    @property
    def is_valid_acn_sender(self) -> bool:
        """Is valid ACN sender"""
        return self._is_valid_acn_sender

    @is_valid_acn_sender.setter
    def is_valid_acn_sender(self, is_valid_acn_sender: bool) -> None:
        """Set is valid ACN sender"""
        self._is_valid_acn_sender = is_valid_acn_sender

    @response_hex.setter
    def response_hex(self, response_hash: bytes) -> None:
        """Set the hash of the response data."""
        try:
            self._response_hex = response_hash.hex()
        except AttributeError:
            msg = f"Response hash {response_hash!r} is not valid hex bytes!"
            self.context.logger.error(msg)

    @property
    def mech_response_api(self) -> MechResponseSpecs:
        """Get the mech response api specs."""
        return self.context.mech_response

    @property
    def serialized_responses(self) -> str:
        """Get the Mech's responses serialized."""
        return json.dumps(self._mech_responses, cls=DataclassEncoder)

    def setup(self) -> None:
        """Set up the `MechResponse` behaviour."""
        self._mech_responses = self.synchronized_data.mech_responses

    def set_mech_response_specs(self, request_id: int) -> None:
        """Set the mech's response specs."""
        full_ipfs_hash = IPFS_HASH_PREFIX + self.response_hex
        ipfs_link = self.params.ipfs_address + full_ipfs_hash + f"/{request_id}"
        # The url must be dynamically generated as it depends on the ipfs hash
        self.mech_response_api.__dict__["_frozen"] = False
        self.mech_response_api.url = ipfs_link
        self.mech_response_api.__dict__["_frozen"] = True

    def _get_block_number(self) -> WaitableConditionType:
        """Get the block number in which the request to the mech was settled."""
        result = yield from self.contract_interact(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            # we do not need the address to get the block number, but the base method does
            contract_address=ADDRESS_ZERO,
            contract_public_id=Mech.contract_id,
            contract_callable="get_block_number",
            data_key="number",
            placeholder=get_name(MechResponseBehaviour.from_block),
            tx_hash=self.synchronized_data.final_tx_hash,
            chain_id=self.params.mech_chain_id,
        )

        return result

    @property
    def mech_contract_interact(self) -> Callable[..., WaitableConditionType]:
        """Interact with the mech contract."""
        if self.params.use_mech_marketplace:
            return self._mech_marketplace_contract_interact

        return self._mech_contract_interact

    def _process_request_event(self) -> WaitableConditionType:
        """Process the request event."""
        result = yield from self.mech_contract_interact(
            contract_callable="process_request_event",
            data_key="results",
            placeholder=get_name(MechResponseBehaviour.requests),
            tx_hash=self.synchronized_data.final_tx_hash,
            expected_logs=len(self._mech_responses),
            chain_id=self.params.mech_chain_id,
        )
        self.context.logger.info(f"Request event processed AXAT123: {result}")
        return result

    # Todo : write another version of this fn for MM which uses ids not id

    def _get_response_hash(self) -> WaitableConditionType:
        """Get the hash of the response data."""
        if (
            self.params.use_acn_for_delivers
            and self.current_mech_response.response_data is not None
        ):
            result = yield from self.agent_registry_contract_interact(
                contract_callable="authenticate_sender",
                data_key="is_valid",
                placeholder=get_name(MechResponseBehaviour.is_valid_acn_sender),
                sender_address=self.current_mech_response.sender_address,
                mech_address=self.params.mech_contract_address,
            )
            if result and self.is_valid_acn_sender:
                self.response_hex = self.current_mech_response.response_data
                return True

        # Get the request ID in bytes32 format
        request_id_bytes: Optional[bytes] = None
        request_id_for_specs: Optional[int] = None  # Keep int version for specs

        if self.params.use_mech_marketplace:
            request_ids = self.current_mech_response.requestIds
            self.context.logger.info(
                f"Using Mech Marketplace. Request ids (hex): {request_ids}"
            )
            if request_ids and len(request_ids) > 0:
                hex_request_id = request_ids[0]
                if not isinstance(hex_request_id, str) or not hex_request_id.startswith(
                    "0x"
                ):
                    self.context.logger.error(
                        f"Invalid hex request ID format: {hex_request_id}"
                    )
                    return False
                try:
                    # Convert hex string to bytes32 (remove '0x' prefix first)
                    raw_bytes = bytes.fromhex(hex_request_id[2:])
                    # Ensure it's exactly 32 bytes by padding with zeros if needed
                    request_id_bytes = raw_bytes.rjust(32, b"\x00")
                    # Also keep int version for specs
                    request_id_for_specs = int(hex_request_id, 16)
                    self.context.logger.info(
                        f"Converted marketplace request ID from hex {hex_request_id} to bytes32: 0x{request_id_bytes.hex()}"
                    )
                except (ValueError, TypeError) as e:
                    self.context.logger.error(
                        f"Could not convert request ID {hex_request_id} to bytes32: {e}"
                    )
                    return False
            else:
                self.context.logger.warning(
                    "Mech Marketplace is enabled, but no request IDs found."
                )
                return False
        else:
            # Convert integer requestId to bytes32 for direct mech interaction
            request_id = self.current_mech_response.requestId
            request_id_for_specs = request_id
            try:
                # Convert int to 32-byte hex string (padded with zeros), then to bytes
                hex_str = format(request_id, "064x")  # 32 bytes = 64 hex chars
                request_id_bytes = bytes.fromhex(hex_str)
                self.context.logger.info(
                    f"Converted direct mech request ID from int {request_id} to bytes32: 0x{request_id_bytes.hex()}"
                )
            except (ValueError, TypeError) as e:
                self.context.logger.error(
                    f"Could not convert request ID {request_id} to bytes32: {e}"
                )
                return False

        if request_id_bytes is None or request_id_for_specs is None:
            self.context.logger.error(
                "Could not determine the request ID bytes32 to use for fetching the response."
            )
            return False

        self.context.logger.info(
            f"Filtering the Mech's Deliver events from block {self.from_block} "
            f"for a response to request with id 0x{request_id_bytes.hex()}"
        )

        # Call get_response with bytes32 request ID
        result = yield from self._mech_contract_interact(
            contract_callable="get_response",
            data_key="data",
            placeholder=get_name(MechResponseBehaviour.response_hex),
            request_id=request_id_bytes,
            from_block=self.from_block,
            chain_id=self.params.mech_chain_id,
        )

        if result:
            # Use integer version for specs
            self.set_mech_response_specs(request_id_for_specs)

        return result

    def _handle_response(
        self,
        res: Optional[str],
    ) -> Optional[Any]:
        """Handle the response from the IPFS.

        :param res: the response to handle.
        :return: the response's result, using the given keys. `None` if response is `None` (has failed).
        """
        if res is None:
            msg = f"Could not get the mech's response from {self.mech_response_api.api_id}"
            self.context.logger.error(msg)
            self.mech_response_api.increment_retries()
            return None

        truncated_res = (
            res[: self.MAX_LOG_CHARS] + "..." if len(res) > self.MAX_LOG_CHARS else res
        )
        self.context.logger.info(
            f"Retrieved mech's response (first {self.MAX_LOG_CHARS} characters) : {truncated_res}"
        )
        self.mech_response_api.reset_retries()

        return res

    def _process_response_with_artifacts(self, res: str) -> str:
        """Process response that may contain base64 artifacts.

        :param res: the raw response string
        :return: processed response or original if no special handling needed
        """
        try:
            result_json = json.loads(res)
        except (json.JSONDecodeError, TypeError):
            return res

        if not isinstance(result_json, dict):
            return res

        artifacts = result_json.get(self.ARTIFACTS_KEY, None)
        if not artifacts:
            return res

        # For large responses with artifacts, create a summary to avoid consensus payload size issues
        artifact_count = len(artifacts)
        total_size = sum(
            len(artifact.get(self.BASE64_KEY, "")) for artifact in artifacts
        )

        # Create a summary that doesn't include the full base64 data
        summary = {
            "summary": f"Response contains {artifact_count} image artifacts, total size {total_size} bytes",
            "ipfs_link": self.mech_response_api.url,  # Keep the link for future reference
        }

        # Return summary instead of full response
        return json.dumps(summary)

    def _get_response(self) -> WaitableConditionType:
        """Get the response data from IPFS."""
        specs = self.mech_response_api.get_spec()
        res_raw = yield from self.get_http_response(**specs)
        res = self.mech_response_api.process_response(res_raw)
        res = self._handle_response(res)
        res = self._process_response_with_artifacts(res)

        if self.mech_response_api.is_retries_exceeded():
            self.current_mech_response.retries_exceeded()
            return True

        if res is None:
            return False

        try:
            self.current_mech_response.result = res
        except (ValueError, TypeError):
            self.current_mech_response.incorrect_format(res)

        return True

    def _set_current_response(self, request: MechRequest) -> None:
        """Set the current Mech response."""
        self.context.logger.info(f"response: {request}")
        for pending_response in self._mech_responses:
            self.context.logger.info(f"Pending response: {pending_response}")
            pending_response.requestIds = request.requestIds
            self.current_mech_response = pending_response
            self.context.logger.info(f"Current mech responses: {self._mech_responses}")
            break

    def _process_responses(
        self,
    ) -> Generator:
        """Get the response."""
        for step in (
            self._get_block_number,
            self._process_request_event,
        ):
            yield from self.wait_for_condition_with_sleep(step)

        for request in self.requests:
            self._set_current_response(request)

            # TODO : add a conditional check if this is mm request via use_mech_marketplace param

            for step in (self._get_response_hash, self._get_response):
                yield from self.wait_for_condition_with_sleep(step)

            self.context.logger.info(
                f"Response has been received:\n{self.current_mech_response}"
            )
            if self.current_mech_response.result is None:
                self.context.logger.error(
                    f"There was an error in the mech's response: {self.current_mech_response.error}"
                )

    def async_act(self) -> Generator:
        """Do the action."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            if self.synchronized_data.final_tx_hash:
                yield from self._process_responses()

            self.context.logger.info(
                f"Received mech responses: {self.serialized_responses}"
            )

            payload = MechResponsePayload(
                self.context.agent_address,
                self.serialized_responses,
            )

        yield from self.finish_behaviour(payload)
