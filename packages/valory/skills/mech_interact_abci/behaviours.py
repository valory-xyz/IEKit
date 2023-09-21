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

"""This package contains round behaviours of MechInteractAbciApp."""

from abc import ABC
from typing import Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)

from packages.valory.skills.mech_interact_abci.models import Params
from packages.valory.skills.mech_interact_abci.rounds import (
    SynchronizedData,
    MechInteractAbciApp,
    MechRequestRound,
    MechResponseRound,
)
from packages.valory.skills.mech_interact_abci.rounds import (
    MechRequestPayload,
    MechResponsePayload,
)
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import mkdtemp
from typing import Any, Dict, Generator, Optional, cast
from uuid import uuid4

import multibase
import multicodec
from aea.helpers.cid import to_v1
from packages.valory.contracts.gnosis_safe.contract import GnosisSafeContract
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import get_name
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
from packages.valory.skills.decision_maker_abci.payloads import RequestPayload
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
import dataclasses
from abc import ABC
from datetime import datetime, timedelta
from typing import Any, Callable, Generator, List, Optional, cast

from aea.configurations.data_types import PublicId

from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation,
)
from packages.valory.contracts.mech.contract import Mech
from packages.valory.contracts.multisend.contract import MultiSendContract
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import BaseTxPayload
from packages.valory.skills.abstract_round_abci.behaviour_utils import (
    BaseBehaviour,
    TimeoutException,
)

from packages.valory.skills.twitter_scoring_abci.rounds import SynchronizedData
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
from packages.valory.skills.transaction_settlement_abci.rounds import TX_HASH_LENGTH
from hexbytes import HexBytes
from packages.valory.contracts.multisend.contract import MultiSendOperation
from packages.valory.skills.mech_interact_abci.rounds import SynchronizedData


WaitableConditionType = Generator[None, None, bool]

METADATA_FILENAME = "metadata.json"
V1_HEX_PREFIX = "f01"
Ox = "0x"

# setting the safe gas to 0 means that all available gas will be used
# which is what we want in most cases
# more info here: https://safe-docs.dev.gnosisdev.com/safe/docs/contracts_tx_execution/
SAFE_GAS = 0

@dataclass
class MechMetadata:
    """A Mech's metadata."""

    prompt: str
    tool: str
    nonce: str = field(default_factory=lambda: str(uuid4()))



@dataclass
class MultisendBatch:
    """A structure representing a single transaction of a multisend."""

    to: str
    data: HexBytes
    value: int = 0
    operation: MultiSendOperation = MultiSendOperation.CALL


class MechInteractBaseBehaviour(BaseBehaviour, ABC):
    """Represents the base class for the mech interaction FSM behaviour."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the bet placement behaviour."""
        super().__init__(**kwargs)
        self.multisend_batches: List[MultisendBatch] = []
        self.multisend_data = b""
        self._safe_tx_hash = ""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return SynchronizedData(super().synchronized_data.db)

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
        return [dataclasses.asdict(batch) for batch in self.multisend_batches]

    @property
    def txs_value(self) -> int:
        """Get the total value of the transactions."""
        return sum(batch.value for batch in self.multisend_batches)

    @property
    def tx_hex(self) -> Optional[str]:
        """Serialize the safe tx to a hex string."""
        if self.safe_tx_hash == "":
            self.context.logger.error(
                "Cannot prepare a transaction without a transaction hash."
            )
            return None
        return hash_payload_to_hex(
            self.safe_tx_hash,
            self.txs_value,
            SAFE_GAS,
            self.params.multisend_address,
            self.multisend_data,
            SafeOperation.DELEGATE_CALL.value,
        )

    @staticmethod
    def wei_to_native(wei: int) -> float:
        """Convert WEI to native token."""
        return wei / 10**18

    def default_error(
        self, contract_id: str, contract_callable: str, response_msg: ContractApiMessage
    ) -> None:
        """Return a default contract interaction error message."""
        self.context.logger.error(
            f"Could not successfully interact with the {contract_id} contract "
            f"using {contract_callable!r}: {response_msg}"
        )

    def contract_interaction_error(
        self, contract_id: str, contract_callable: str, response_msg: ContractApiMessage
    ) -> None:
        """Return a contract interaction error message."""
        # contracts can only return one message, i.e., multiple levels cannot exist.
        for level in ("info", "warning", "error"):
            msg = response_msg.raw_transaction.body.get(level, None)
            logger = getattr(self.context.logger, level)
            if msg is not None:
                logger(msg)
                return

        self.default_error(contract_id, contract_callable, response_msg)

    def contract_interact(
        self,
        performative: ContractApiMessage.Performative,
        contract_address: str,
        contract_public_id: PublicId,
        contract_callable: str,
        data_key: str,
        placeholder: str,
        **kwargs: Any,
    ) -> WaitableConditionType:
        """Interact with a contract."""
        contract_id = str(contract_public_id)
        response_msg = yield from self.get_contract_api_response(
            performative,
            contract_address,
            contract_id,
            contract_callable,
            **kwargs,
        )
        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.default_error(contract_id, contract_callable, response_msg)
            return False

        data = response_msg.raw_transaction.body.get(data_key, None)
        if data is None:
            self.contract_interaction_error(
                contract_id, contract_callable, response_msg
            )
            return False

        setattr(self, placeholder, data)
        return True

    def _mech_contract_interact(
        self, contract_callable: str, data_key: str, placeholder: str, **kwargs: Any
    ) -> WaitableConditionType:
        """Interact with the mech contract."""
        status = yield from self.contract_interact(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.mech_agent_address,
            contract_public_id=Mech.contract_id,
            contract_callable=contract_callable,
            data_key=data_key,
            placeholder=placeholder,
            **kwargs,
        )
        return status

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

        # strip "0x" from the response hash
        self.safe_tx_hash = tx_hash
        return True

    def wait_for_condition_with_sleep(
        self,
        condition_gen: Callable[[], WaitableConditionType],
        timeout: Optional[float] = None,
    ) -> Generator[None, None, None]:
        """Wait for a condition to happen and sleep in-between checks.

        This is a modified version of the base `wait_for_condition` method which:
            1. accepts a generator that creates the condition instead of a callable
            2. sleeps in-between checks

        :param condition_gen: a generator of the condition to wait for
        :param timeout: the maximum amount of time to wait
        :yield: None
        """

        deadline = (
            datetime.now() + timedelta(0, timeout)
            if timeout is not None
            else datetime.max
        )

        while True:
            condition_satisfied = yield from condition_gen()
            if condition_satisfied:
                break
            if timeout is not None and datetime.now() > deadline:
                raise TimeoutException()
            self.context.logger.info(f"Retrying in {self.params.sleep_time} seconds.")
            yield from self.sleep(self.params.sleep_time)

    def finish_behaviour(self, payload: BaseTxPayload) -> Generator:
        """Finish the behaviour."""
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()



class MechRequestBehaviour(MechInteractBaseBehaviour):
    """A behaviour in which the agents prepare a tx to initiate a request to a mech."""

    matching_round = MechRequestRound

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Behaviour."""
        super().__init__(**kwargs)
        self._metadata: Optional[MechMetadata] = None
        self._v1_hex_truncated: str = ""
        self._request_data: bytes = b""
        self._price: int = 0

    @property
    def metadata_filepath(self) -> str:
        """Get the filepath to the metadata."""
        return str(Path(mkdtemp()) / METADATA_FILENAME)

    @property
    def metadata(self) -> Dict[str, str]:
        """Get the metadata as a dictionary."""
        return asdict(self._metadata)  # type: ignore

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

    def _send_metadata_to_ipfs(
        self,
    ) -> WaitableConditionType:
        """Send Mech metadata to IPFS."""
        metadata_hash = yield from self.send_to_ipfs(
            self.metadata_filepath, self.metadata, filetype=SupportedFiletype.JSON
        )
        if metadata_hash is None:
            return False

        v1_file_hash = to_v1(metadata_hash)
        cid_bytes = cast(bytes, multibase.decode(v1_file_hash))
        multihash_bytes = multicodec.remove_prefix(cid_bytes)
        v1_file_hash_hex = V1_HEX_PREFIX + multihash_bytes.hex()
        ipfs_link = self.params.ipfs_address + v1_file_hash_hex
        self.context.logger.info(f"Prompt uploaded: {ipfs_link}")
        self._v1_hex_truncated = Ox + v1_file_hash_hex[9:]
        return True

    def _build_request_data(self) -> WaitableConditionType:
        """Get the request tx data encoded."""

        for request in self.synchronized_data.mech_requests:
            self._metadata = MechMetadata(prompt=request["prompt"], tool=request["tool"])

            status = yield from self._mech_contract_interact(
                "get_request_data",
                "data",
                get_name(MechRequestBehaviour.request_data),
                request_data=self._v1_hex_truncated,
            )

            batch = MultisendBatch(
                to=self.collateral_token,
                data=HexBytes(self.data),
            )
            self.multisend_batches.append(batch)

        return True

    def _get_price(self) -> WaitableConditionType:
        """Get the price of the mech request."""
        result = yield from self._mech_contract_interact(
            "get_price", "price", get_name(MechRequestBehaviour.price)
        )
        return result

    def _get_safe_tx_hash(self) -> Generator[None, None, bool]:
        """Prepares and returns the safe tx hash."""
        status = yield from self.contract_interact(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_public_id=GnosisSafeContract.contract_id,
            contract_callable="get_raw_safe_transaction_hash",
            to_address=self.params.mech_agent_address,
            value=self.price,
            data=self.request_data,
            data_key="tx_hash",
            placeholder=get_name(MechRequestBehaviour.safe_tx_hash),
        )
        return status

    def _prepare_safe_tx(self) -> Generator[None, None, str]:
        """Prepare the safe transaction for sending a request to mech and return the hex for the tx settlement skill."""
        for step in (
            self._send_metadata_to_ipfs,
            self._build_request_data,
            self._build_multisend_data,
            self._build_multisend_safe_tx_hash,
            self._get_price,
        ):
            yield from self.wait_for_condition_with_sleep(step)

        return hash_payload_to_hex(
            self.safe_tx_hash,
            self.price,
            SAFE_GAS,
            self.params.mech_agent_address,
            self.request_data,
        )

    def async_act(self) -> Generator:
        """Do the action."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            tx_submitter = mech_tx_hex = price = None
            tx_submitter = self.matching_round.auto_round_id()
            mech_tx_hex = yield from self._prepare_safe_tx()
            price = self.price
            agent = self.context.agent_address
            payload = RequestPayload(agent, tx_submitter, mech_tx_hex, price)
        yield from self.finish_behaviour(payload)



class MechResponseBehaviour(MechInteractBaseBehaviour):
    """MechResponseBehaviour"""

    matching_round: Type[AbstractRound] = MechResponseRound

    # TODO: implement logic required to set payload content for synchronization
    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            payload = MechResponsePayload(sender=sender, content=...)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class MechInteractRoundBehaviour(AbstractRoundBehaviour):
    """MechInteractRoundBehaviour"""

    initial_behaviour_cls = MechRequestBehaviour
    abci_app_cls = MechInteractAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        MechRequestBehaviour,
        MechResponseBehaviour
    ]
