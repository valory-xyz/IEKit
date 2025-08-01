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

"""This module contains the dynamic_contribution contract definition."""

from typing import Any, cast

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea.crypto.base import LedgerApi
from aea_ledger_ethereum import EthereumApi
from eth_utils import event_abi_to_log_topic
from hexbytes import HexBytes
from web3._utils.events import get_event_data
from web3.types import BlockIdentifier, FilterParams


# Avoid parsing too many blocks at a time. This might take too long and the connection could time out.
# The value covers the free QN version: https://www.quicknode.com/docs/ethereum/eth_getLogs
MAX_BLOCKS = 5
TOPIC_BYTES = 32
TOPIC_CHARS = TOPIC_BYTES * 2
Ox = "0x"
Ox_CHARS = len(Ox)


def pad_address_for_topic(address: str) -> HexBytes:
    """Left-pad an Ethereum address to 32 bytes for use in a topic."""
    return HexBytes(Ox + address[Ox_CHARS:].zfill(TOPIC_CHARS))


class DynamicContributionContract(Contract):
    """The scaffold contract class for a smart contract."""

    contract_id = PublicId.from_str("valory/dynamic_contribution:0.1.0")

    @classmethod
    def get_raw_transaction(
        cls, ledger_api: LedgerApi, contract_address: str, **kwargs: Any
    ) -> JSONLike:
        """
        Handler method for the 'GET_RAW_TRANSACTION' requests.

        Implement this method in the sub class if you want
        to handle the contract requests manually.

        :param ledger_api: the ledger apis.
        :param contract_address: the contract address.
        :param kwargs: the keyword arguments.
        :return: the tx  # noqa: DAR202
        """
        raise NotImplementedError

    @classmethod
    def get_raw_message(
        cls, ledger_api: LedgerApi, contract_address: str, **kwargs: Any
    ) -> bytes:
        """
        Handler method for the 'GET_RAW_MESSAGE' requests.

        Implement this method in the sub class if you want
        to handle the contract requests manually.

        :param ledger_api: the ledger apis.
        :param contract_address: the contract address.
        :param kwargs: the keyword arguments.
        :return: the tx  # noqa: DAR202
        """
        raise NotImplementedError

    @classmethod
    def get_state(
        cls, ledger_api: LedgerApi, contract_address: str, **kwargs: Any
    ) -> JSONLike:
        """
        Handler method for the 'GET_STATE' requests.

        Implement this method in the sub class if you want
        to handle the contract requests manually.

        :param ledger_api: the ledger apis.
        :param contract_address: the contract address.
        :param kwargs: the keyword arguments.
        :return: the tx  # noqa: DAR202
        """
        raise NotImplementedError

    @classmethod
    def get_all_erc721_transfers(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        from_address: str,
        from_block: BlockIdentifier = "earliest",
        to_block: BlockIdentifier = "latest",
    ) -> JSONLike:
        """
        Get all ERC721 transfers from a given address.

        :param ledger_api: LedgerApi object
        :param contract_address: the address of the token to be used
        :param from_address: the address transferring the tokens.
        :param from_block: from which block to search for events
        :param to_block: to which block to search for events
        :return: the ERC20 transfers
        """
        ledger_api = cast(EthereumApi, ledger_api)
        factory_contract = cls.get_instance(ledger_api, contract_address)
        event_abi = factory_contract.events.Transfer().abi
        event_topic = event_abi_to_log_topic(event_abi)

        to_block = (
            ledger_api.api.eth.get_block_number() - 1 if to_block == "latest" else to_block
        )
        ranges = list(range(from_block, to_block, MAX_BLOCKS)) + [to_block]
        from_address = pad_address_for_topic(from_address)

        entries = []
        for i in range(len(ranges) - 1):
            from_block = ranges[i]
            to_block = ranges[i + 1]
            filter_params: FilterParams = {
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": factory_contract.address,
                "topics": [event_topic, from_address],
            }

            w3 = ledger_api.api.eth
            logs = w3.get_logs(filter_params)
            entries = [get_event_data(w3.codec, event_abi, log) for log in logs]

        token_id_to_member = {
            str(entry["args"]["id"]): entry["args"]["to"] for entry in entries
        }

        return dict(
            token_id_to_member=token_id_to_member,
            last_block=int(to_block),
        )
