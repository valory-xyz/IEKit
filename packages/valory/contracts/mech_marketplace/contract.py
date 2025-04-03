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

"""This module contains the class to connect to a Mech Marketplace contract."""

import concurrent.futures
from typing import Any, Callable, Dict, List, cast, Optional

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea.crypto.base import LedgerApi
from aea_ledger_ethereum import EthereumApi
from eth_typing import HexStr
from web3.types import BlockData, BlockIdentifier, EventData, TxReceipt


PUBLIC_ID = PublicId.from_str("valory/mech_marketplace:0.1.0")
FIVE_MINUTES = 300.0


class MechMarketplace(Contract):
    """The Mech Marketplace contract."""

    contract_id = PUBLIC_ID

    @staticmethod
    def execute_with_timeout(func: Callable, timeout: float) -> Any:
        """Execute a function with a timeout."""

        # Create a ProcessPoolExecutor with a maximum of 1 worker (process)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # Submit the function to the executor
            future = executor.submit(
                func,
            )

            try:
                # Wait for the result with a 5-minute timeout
                data = future.result(timeout=timeout)
            except TimeoutError:
                # Handle the case where the execution times out
                err = f"The RPC didn't respond in {timeout}."
                return None, err

            # Check if an error occurred
            if isinstance(data, str):
                # Handle the case where the execution failed
                return None, data

            return data, None



    @classmethod
    def get_request_data(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        request_data: bytes,
        priority_mech: str,
        max_delivery_rate: int,
        payment_type: str,  # Expected to be a '0x...' hex string for bytes32
        payment_data: bytes,
        response_timeout: int,
        **kwargs: Any,
    ) -> Dict[str, bytes]:
        """Gets the encoded arguments for a request tx, which should only be called via the multisig.

        :param ledger_api: the ledger API object
        :param contract_address: the contract's address
        :param request_data: the request data (bytes)
        :param priority_mech: the priority mech address (str)
        :param max_delivery_rate: the maximum delivery rate (uint256)
        :param payment_type: the payment type identifier (bytes32, passed as '0x...' hex str)
        :param payment_data: the payment data (bytes)
        :param response_timeout: the response timeout (uint256)
        """
        checksummed_contract_address = ledger_api.api.to_checksum_address(
            contract_address
        )
        contract_instance = cls.get_instance(ledger_api, checksummed_contract_address)
        # Checksum the priority mech address before passing it to the contract method
        checksummed_priority_mech = ledger_api.api.to_checksum_address(priority_mech)
        encoded_data = contract_instance.encodeABI(
            fn_name="request",
            args=(
                request_data,  
                max_delivery_rate,  
                payment_type,  
                checksummed_priority_mech,  
                response_timeout,  
                payment_data,  
            ),
        )
        return {"data": bytes.fromhex(encoded_data[2:])}

    @classmethod
    def _process_event(
        cls,
        ledger_api: LedgerApi,
        contract: Any,
        tx_hash: HexStr,
        expected_logs: int,
        event_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> JSONLike:
        """Process the logs of the given event."""
        ledger_api = cast(EthereumApi, ledger_api)
        receipt: TxReceipt = ledger_api.api.eth.get_transaction_receipt(tx_hash)
        event_method = getattr(contract.events, event_name)
        logs: List[EventData] = list(event_method().process_receipt(receipt))

        n_logs = len(logs)
        if n_logs != expected_logs:
            error = f"{expected_logs} {event_name!r} events were expected. tx {tx_hash} emitted {n_logs} instead."
            return {"error": error}

        results = []
        for log in logs:
            event_args = log.get("args", None)
            if event_args is None or any(
                expected_key not in event_args for expected_key in args
            ):
                return {
                    "error": f"The emitted event's ({event_name}) logs for tx {tx_hash} do not match the expected format: {log} , event args: {event_args}"
                }

            # Create a result dict with processed values
            result = {}
            for arg_name in args:
                value = event_args[arg_name]

                # If value is a list, process each item
                if isinstance(value, list):
                    processed_list = []
                    for item in value:
                        if isinstance(item, bytes):
                            # Convert bytes to hex string
                            processed_list.append("0x" + item.hex())
                        else:
                            processed_list.append(item)
                    result[arg_name] = processed_list
                # If value is bytes, convert to hex string
                elif isinstance(value, bytes):
                    result[arg_name] = "0x" + value.hex()
                else:
                    result[arg_name] = value

            results.append(result)

        return dict(results=results)

    @classmethod
    def process_request_event(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        tx_hash: HexStr,
        expected_logs: int = 1,
        **kwargs: Any,
    ) -> JSONLike:
        """
        Process the request receipt to get the requestId and the given data from the `Request` event's logs.

        :param ledger_api: the ledger apis.
        :param contract_address: the contract address.
        :param tx_hash: the hash of a request tx to be processed.
        :param expected_logs: the number of logs expected.
        :return: a dictionary with a key named `results`
        which contains a list of dictionaries (as many as the expected logs) containing the request id and the data.
        """
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        contract_instance = cls.get_instance(ledger_api, contract_address)
        res = cls._process_event(
            ledger_api,
            contract_instance,
            tx_hash,
            expected_logs,
            "MarketplaceRequest",
            "requestIds",
            "numRequests",
        )

        print(f"Request event result: {res}")
        return res

    @classmethod
    def process_deliver_event(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        tx_hash: HexStr,
        expected_logs: int = 1,
        **kwargs: Any,
    ) -> JSONLike:
        """
        Process the request receipt to get the requestId and the delivered data if the `MarketplaceDeliver` event has been emitted.

        :param ledger_api: the ledger apis.
        :param contract_address: the contract address.
        :param tx_hash: the hash of a request tx to be processed.
        :param expected_logs: the number of logs expected.
        :return: a dictionary with the request id and the data.
        """
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        contract_instance = cls.get_instance(ledger_api, contract_address)
        res = cls._process_event(
            ledger_api,
            contract_instance,
            tx_hash,
            expected_logs,
            "MarketplaceDelivery",
            "requestId",
            "data",
        )

        return res

    @classmethod
    def get_block_number(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
        tx_hash: HexStr,
        **kwargs: Any,
    ) -> JSONLike:
        """Get the number of the block in which the tx of the given hash was settled."""
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        receipt: TxReceipt = ledger_api.api.eth.get_transaction_receipt(tx_hash)
        block: BlockData = ledger_api.api.eth.get_block(receipt["blockNumber"])
        return dict(number=block["number"])
