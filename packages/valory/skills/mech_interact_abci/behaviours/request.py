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

"""This module contains the request state of the mech interaction abci app."""

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import mkdtemp
from typing import Any, Generator, List, Optional, cast

import multibase
import multicodec
from aea.helpers.cid import to_v1
from hexbytes import HexBytes

from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation,
)
from packages.valory.contracts.multisend.contract import MultiSendContract
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import get_name
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
from packages.valory.skills.mech_interact_abci.behaviours.base import (
    DataclassEncoder,
    MechInteractBaseBehaviour,
    WaitableConditionType,
)
from packages.valory.skills.mech_interact_abci.models import MultisendBatch
from packages.valory.skills.mech_interact_abci.payloads import MechRequestPayload
from packages.valory.skills.mech_interact_abci.states.base import (
    MechInteractionResponse,
    MechMetadata,
)
from packages.valory.skills.mech_interact_abci.states.request import MechRequestRound
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
from packages.valory.skills.transaction_settlement_abci.rounds import TX_HASH_LENGTH


METADATA_FILENAME = "metadata.json"
V1_HEX_PREFIX = "f01"
Ox = "0x"

# setting the safe gas to 0 means that all available gas will be used
# which is what we want in most cases
# more info here: https://safe-docs.dev.gnosisdev.com/safe/docs/contracts_tx_execution/
SAFE_GAS = 0
GNOSIS_CHAIN_ID = 100


class MechRequestBehaviour(MechInteractBaseBehaviour):
    """A behaviour in which the agents prepare a tx to initiate a request to a mech."""

    matching_round = MechRequestRound

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Behaviour."""
        super().__init__(**kwargs)
        self._v1_hex_truncated: str = ""
        self._request_data: bytes = b""
        self._price: int = 0
        self._mech_requests: List[MechMetadata] = []
        self._pending_responses: List[MechInteractionResponse] = []

    @property
    def metadata_filepath(self) -> str:
        """Get the filepath to the metadata."""
        return str(Path(mkdtemp()) / METADATA_FILENAME)

    @property
    def request_data(self) -> bytes:
        """Get the request data."""
        return self._request_data

    @request_data.setter
    def request_data(self, data: bytes) -> None:
        """Set the request data."""
        self._request_data = data

    @property
    def price(self) -> int:
        """Get the price."""
        return self._price

    @price.setter
    def price(self, price: int) -> None:
        """Set the price."""
        self._price = price

    @property
    def safe_tx_hash(self) -> str:
        """Get the safe_tx_hash."""
        return self._safe_tx_hash

    @safe_tx_hash.setter
    def safe_tx_hash(self, safe_hash: str) -> None:
        """Set the safe_tx_hash."""
        length = len(safe_hash)
        if length != TX_HASH_LENGTH:
            raise ValueError(
                f"Incorrect length {length} != {TX_HASH_LENGTH} detected "
                f"when trying to assign a safe transaction hash: {safe_hash}"
            )
        self._safe_tx_hash = safe_hash[2:]

    @property
    def multi_send_txs(self) -> List[dict]:
        """Get the multisend transactions as a list of dictionaries."""
        return [asdict(batch) for batch in self.multisend_batches]

    @property
    def txs_value(self) -> int:
        """Get the total value of the transactions."""
        return sum(batch.value for batch in self.multisend_batches)

    @property
    def tx_hex(self) -> Optional[str]:
        """Serialize the safe tx to a hex string."""
        if self.safe_tx_hash == "":
            raise ValueError(
                "Cannot prepare a multisend transaction without a safe transaction hash."
            )
        return hash_payload_to_hex(
            self.safe_tx_hash,
            self.txs_value,
            SAFE_GAS,
            self.params.multisend_address,
            self.multisend_data,
            SafeOperation.DELEGATE_CALL.value,
        )

    def _build_multisend_data(
        self,
    ) -> WaitableConditionType:
        """Get the multisend tx."""
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.multisend_address,
            contract_id=str(MultiSendContract.contract_id),
            contract_callable="get_tx_data",
            multi_send_txs=self.multi_send_txs,
            chain_id=GNOSIS_CHAIN_ID,
        )
        expected_performative = ContractApiMessage.Performative.RAW_TRANSACTION
        if response_msg.performative != expected_performative:
            self.context.logger.error(
                f"Couldn't compile the multisend tx. "
                f"Expected response performative {expected_performative.value}, "  # type: ignore
                f"received {response_msg.performative.value}: {response_msg}"
            )
            return False

        multisend_data_str = response_msg.raw_transaction.body.get("data", None)
        if multisend_data_str is None:
            self.context.logger.error(
                f"Something went wrong while trying to prepare the multisend data: {response_msg}"
            )
            return False

        # strip "0x" from the response
        multisend_data_str = str(response_msg.raw_transaction.body["data"])[2:]
        self.multisend_data = bytes.fromhex(multisend_data_str)
        return True

    def _build_multisend_safe_tx_hash(self) -> WaitableConditionType:
        """Prepares and returns the safe tx hash for a multisend tx."""
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=self.params.multisend_address,
            value=self.txs_value,
            data=self.multisend_data,
            safe_tx_gas=SAFE_GAS,
            operation=SafeOperation.DELEGATE_CALL.value,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if response_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                "Couldn't get safe tx hash. Expected response performative "
                f"{ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response_msg.performative.value}: {response_msg}."
            )
            return False

        tx_hash = response_msg.state.body.get("tx_hash", None)
        if tx_hash is None or len(tx_hash) != TX_HASH_LENGTH:
            self.context.logger.error(
                "Something went wrong while trying to get the buy transaction's hash. "
                f"Invalid hash {tx_hash!r} was returned."
            )
            return False

        self.safe_tx_hash = tx_hash
        return True

    def setup(self) -> None:
        """Set up the `MechRequest` behaviour."""
        self._mech_requests = self.synchronized_data.mech_requests
        self.context.logger.info(f"Processing mech requests: {self._mech_requests}")

    def _send_metadata_to_ipfs(
        self,
    ) -> WaitableConditionType:
        """Send Mech metadata to IPFS."""
        metadata = self._mech_requests.pop()
        metadata_hash = yield from self.send_to_ipfs(
            self.metadata_filepath, asdict(metadata), filetype=SupportedFiletype.JSON
        )
        if metadata_hash is None:
            return False

        v1_file_hash = to_v1(metadata_hash)
        cid_bytes = cast(bytes, multibase.decode(v1_file_hash))
        multihash_bytes = multicodec.remove_prefix(cid_bytes)
        v1_file_hash_hex = V1_HEX_PREFIX + multihash_bytes.hex()
        ipfs_link = self.params.ipfs_address + v1_file_hash_hex
        self.context.logger.info(f"Prompt uploaded: {ipfs_link}")
        mech_request_data = v1_file_hash_hex[9:]
        pending_response = MechInteractionResponse(
            nonce=metadata.nonce, data=mech_request_data
        )
        self._v1_hex_truncated = Ox + mech_request_data
        self._pending_responses.append(pending_response)
        return True

    def _build_request_data(self) -> WaitableConditionType:
        """Get the request tx data encoded."""
        status = yield from self._mech_contract_interact(
            "get_request_data",
            "data",
            get_name(MechRequestBehaviour.request_data),
            request_data=self._v1_hex_truncated,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if status:
            batch = MultisendBatch(
                to=self.params.mech_agent_address,
                data=HexBytes(self.request_data),
                value=self.price,
            )
            self.multisend_batches.append(batch)

        return status

    def _get_price(self) -> WaitableConditionType:
        """Get the price of the mech request."""
        result = yield from self._mech_contract_interact(
            "get_price",
            "price",
            get_name(MechRequestBehaviour.price),
            chain_id=GNOSIS_CHAIN_ID,
        )
        return result

    def _prepare_safe_tx(self) -> Generator:
        """Prepare a multisend safe tx for sending requests to a mech and return the hex for the tx settlement skill."""
        n_iters = min(self.params.multisend_batch_size, len(self._mech_requests))
        steps = (self._get_price,)
        steps += (self._send_metadata_to_ipfs, self._build_request_data) * n_iters
        steps += (self._build_multisend_data, self._build_multisend_safe_tx_hash)

        for step in steps:
            yield from self.wait_for_condition_with_sleep(step)

    def async_act(self) -> Generator:
        """Do the action."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            yield from self._prepare_safe_tx()
            serialized_data = (
                json.dumps(data, cls=DataclassEncoder)
                for data in (self._mech_requests, self._pending_responses)
            )
            self.context.logger.info(
                f"Preparing mech request:\ntx_hex: {self.tx_hex}\nprice: {self.price}\nserialized_data: {serialized_data}\n"
            )
            payload = MechRequestPayload(
                self.context.agent_address, self.tx_hex, self.price, *serialized_data
            )
        yield from self.finish_behaviour(payload)
