# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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

from packages.valory.contracts.erc20.contract import ERC20
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

WXDAI = "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d"


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

    @property
    def collateral_token(self) -> str:
        """Get the contract address of the token that the market maker supports."""
        return WXDAI

    @property
    def is_wxdai(self) -> bool:
        """Get whether the collateral address is wxDAI."""
        return self.collateral_token.lower() == WXDAI.lower()

    @staticmethod
    def wei_to_native(wei: int) -> float:
        """Convert WEI to native token."""
        return wei / 10**18

    def _collateral_amount_info(self, amount: int) -> str:
        """Get a description of the collateral token's amount."""
        return (
            f"{self.wei_to_native(amount)} wxDAI"
            if self.is_wxdai
            else f"{amount} WEI of the collateral token with address {self.collateral_token}"
        )

    @property
    def xdai_deficit(self) -> int:
        """Get the amount of missing xDAI for sending the request."""
        return self.price - self.wallet_balance

    def check_balance(self) -> WaitableConditionType:
        """Check the safe's balance."""
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.collateral_token,
            contract_id=str(ERC20.contract_id),
            contract_callable="check_balance",
            account=self.synchronized_data.safe_contract_address,
        )
        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Could not calculate the balance of the safe: {response_msg}"
            )
            return False

        token = response_msg.raw_transaction.body.get("token", None)
        wallet = response_msg.raw_transaction.body.get("wallet", None)
        if token is None or wallet is None:
            self.context.logger.error(
                f"Something went wrong while trying to get the balance of the safe: {response_msg}"
            )
            return False

        self.token_balance = int(token)
        self.wallet_balance = int(wallet)

        native = self.wei_to_native(self.wallet_balance)
        collateral = self._collateral_amount_info(self.token_balance)
        self.context.logger.info(f"The safe has {native} xDAI and {collateral}.")
        return True

    def _build_unwrap_wxdai_tx(self) -> WaitableConditionType:
        """Exchange wxDAI to xDAI."""
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=WXDAI,
            contract_id=str(ERC20.contract_id),
            contract_callable="build_withdraw_tx",
            amount=self.xdai_deficit,
        )

        if response_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.info(f"Could not build withdraw tx: {response_msg}")
            return False

        withdraw_data = response_msg.state.body.get("data")
        if withdraw_data is None:
            self.context.logger.info(f"Could not build withdraw tx: {response_msg}")
            return False

        batch = MultisendBatch(
            to=self.collateral_token,
            data=HexBytes(withdraw_data),
        )
        self.multisend_batches.append(batch)
        return True

    def _check_unwrap_wxdai(self) -> WaitableConditionType:
        """Check whether the payment for the mech request is possible and unwrap some wxDAI if needed."""
        yield from self.wait_for_condition_with_sleep(self.check_balance)
        missing = self.xdai_deficit
        if missing <= 0:
            return True

        # if the collateral token is wxDAI, subtract the wxDAI balance from the xDAI that is missing for paying the mech
        if self.is_wxdai:
            missing -= self.token_balance

        # if we can cover the required amount by unwrapping some wxDAI, proceed to add this to a multisend tx
        if missing <= 0:
            yield from self.wait_for_condition_with_sleep(self._build_unwrap_wxdai_tx)
            return True

        balance_info = "The balance is not enough to pay for the mech's price"
        refill_info = f". Please refill the safe with at least {self.wei_to_native(missing)} xDAI or wxDAI."
        self.context.logger.warning(balance_info + refill_info)
        self.sleep(self.params.sleep_time)
        return False

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
            chain_id=self.params.mech_chain_id,
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
        self.context.logger.info(
            f"Building multisend safe tx hash: safe={self.synchronized_data.safe_contract_address}"
        )
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
            chain_id=self.params.mech_chain_id,
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
            chain_id=self.params.mech_chain_id,
        )

        if status:
            batch = MultisendBatch(
                to=self.params.mech_contract_address,
                data=HexBytes(self.request_data),
                value=self.price,
            )
            self.multisend_batches.append(batch)

        return status

    def _get_price(self) -> WaitableConditionType:
        """Get the price of the mech request."""
        # If the optional parameter 'request_price' is set, then
        # use that price (wei). Otherwise, determine the request price
        # by calling the contract.
        # This parameter is useful to set 'request_price=0' when the
        # agent is using a Nevermined subscription.
        price = self.params.request_price

        if price:
            self.price = price
            return True

        result = yield from self._mech_contract_interact(
            "get_price",
            "price",
            get_name(MechRequestBehaviour.price),
            chain_id=self.params.mech_chain_id,
        )
        return result

    def _prepare_safe_tx(self) -> Generator:
        """Prepare a multisend safe tx for sending requests to a mech and return the hex for the tx settlement skill."""
        n_iters = min(self.params.multisend_batch_size, len(self._mech_requests))
        steps = (self._get_price,)
        steps += (self._check_unwrap_wxdai,)
        steps += (self._send_metadata_to_ipfs, self._build_request_data) * n_iters
        steps += (self._build_multisend_data, self._build_multisend_safe_tx_hash)

        for step in steps:
            yield from self.wait_for_condition_with_sleep(step)

    def async_act(self) -> Generator:
        """Do the action."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            if not self._mech_requests:
                payload = MechRequestPayload(
                    self.context.agent_address,
                    self.matching_round.auto_round_id(),
                    None,
                    None,
                    self.params.mech_chain_id,
                    None,
                    None,
                )
            else:
                self.context.logger.info(
                    f"Preparing mech requests: {self._mech_requests}"
                )
                yield from self._prepare_safe_tx()
                serialized_data = (
                    json.dumps(data, cls=DataclassEncoder)
                    for data in (self._mech_requests, self._pending_responses)
                )
                self.context.logger.info(
                    f"Preparing mech request:\ntx_hex: {self.tx_hex}\nprice: {self.price}\nserialized_data: {serialized_data}\n"
                )
                payload = MechRequestPayload(
                    self.context.agent_address,
                    self.matching_round.auto_round_id(),
                    self.tx_hex,
                    self.price,
                    self.params.mech_chain_id,
                    *serialized_data,
                )
        yield from self.finish_behaviour(payload)
