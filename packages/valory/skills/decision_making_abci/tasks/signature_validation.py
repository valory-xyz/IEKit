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

"""This package contains the logic for signature validation."""

import json
from typing import cast

from eth_account.account import Account
from eth_account.messages import (
    _hash_eip191_message,
    encode_defunct,
    encode_structured_data,
)
from eth_utils.curried import keccak
from eth_utils.exceptions import ValidationError

from packages.valory.contracts.compatibility_fallback_handler.contract import (
    CompatibilityFallbackHandlerContract,
)
from packages.valory.protocols.contract_api import ContractApiMessage


HTTP_OK = 200


def fix_message_types(message_object):
    """Fix types so the message is encodable"""
    # timestamp and choice need to be integers
    message_object["message"]["timestamp"] = int(message_object["message"]["timestamp"])
    message_object["message"]["choice"] = int(message_object["message"]["choice"])

    # proposal needs to be bytes
    message_object["message"]["proposal"] = bytes.fromhex(
        message_object["message"]["proposal"][2:]
    )

    return message_object


def build_safe_typed_message(message_object):
    """Build the safe message for a typed message"""
    encoded = encode_structured_data(message_object)
    hashed = _hash_eip191_message(encoded)
    return hashed


def build_safe_text_message(text):
    """Build the safe message for a raw/text message"""
    encoded = encode_defunct(text=text)
    hashed = _hash_eip191_message(encoded)
    return hashed


def validate_eoa_signature(message, expected_address, signature):
    """Validate an EOA signature"""
    try:
        encoded_message = encode_defunct(text=message)
        address = Account.recover_message(encoded_message, signature=signature)
        return address == expected_address
    except ValidationError:
        return False


class SignatureValidationMixin:
    """SignatureValidationMixin"""

    def is_contract(self, address):
        """Check if the account is a smart contract"""

        # Call get_code
        contract_api_msg = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address="0x000000000000000000000000000000000000000",  # this is a ledger api call, not needed
            contract_id=str(CompatibilityFallbackHandlerContract.contract_id),
            contract_callable="is_contract",
            wallet_address=address,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Error getting the code for address {address}: [{contract_api_msg.performative}]"
            )
            return False

        is_contract = contract_api_msg.state.body["is_contract"]

        return is_contract

    def get_message_hash(self, message, safe_address):
        """Get the messageHash from the Safe"""
        encoded_message = encode_defunct(text=message)
        msg_bytes = keccak(
            b"\x19"
            + encoded_message.version
            + encoded_message.header
            + encoded_message.body
        )

        # Call get_code
        contract_api_msg = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=safe_address,
            contract_id=str(CompatibilityFallbackHandlerContract.contract_id),
            contract_callable="get_message_hash",
            message=msg_bytes,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Error getting the message hash for safe {safe_address}. Message: {message}"
            )
            return False

        message_hash = contract_api_msg.state.body["message_hash"]

        return message_hash

    def validate_safe_signature(self, message, address):
        """Validate a safe signature"""
        message_hash = yield from self.get_message_hash(message, address)

        # Get the message from the hash using Safe Transaction Service
        transaction_service_url = self.params.transaction_service_url
        url = transaction_service_url.replace("{message_hash}", message_hash)

        response = yield from self.behaviour.get_http_response(method="GET", url=url)

        # Check response status
        if response.status_code != HTTP_OK:
            return False

        response_json = json.loads(response.body)

        message = response_json["message"]
        safe_address = response_json["safe"]
        signature = response_json["preparedSignature"]

        if address != safe_address:
            return False

        if isinstance(message, str):
            safe_message = build_safe_text_message(message)
        else:
            safe_message = build_safe_typed_message(fix_message_types(message))

        # Call CompatibilityFallbackHandler::isValidSignature
        self.behaviour.context.logger.info(
            f"Verifying message={message} safe_message={safe_message} safe={safe_address} signature={signature}"
        )
        contract_api_msg = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=safe_address,
            contract_id=str(CompatibilityFallbackHandlerContract.contract_id),
            contract_callable="is_valid_signature",
            safe_message=safe_message,
            signature=signature,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Error verifying the signature [{contract_api_msg.performative}]"
            )
            return False

        is_valid = cast(dict, contract_api_msg.state.body["valid"])

        self.behaviour.context.logger.info(f"Signature validity: {is_valid}")

        return is_valid

    def validate_signature(self, message, address, signature):
        """Validate signatures"""
        is_contract = yield from self.is_contract(address)
        if is_contract:
            is_valid = yield from self.validate_safe_signature(message, address)
            return is_valid
        else:
            return validate_eoa_signature(message, address, signature)
