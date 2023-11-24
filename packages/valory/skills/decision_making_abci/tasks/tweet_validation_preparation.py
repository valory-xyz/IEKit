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

"""This package contains the logic for task preparations."""

import json
from typing import Generator, Optional, cast

from eth_account.account import Account
from eth_account.messages import (
    _hash_eip191_message,
    encode_defunct,
    encode_structured_data,
)
from eth_utils.exceptions import ValidationError

from packages.valory.contracts.compatibility_fallback_handler import (
    CompatibilityFallbackHandlerContract,
)
from packages.valory.contracts.uniswap_v2_erc20.contract import UniswapV2ERC20Contract
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


TWEET_CONSENSUS_WVEOLAS_WEI = 2e6 * 1e18  # 2M wveOLAS to wei
OLAS_ADDRESS_ETHEREUM = "0x0001a500a6b18995b03f44bb040a5ffc28e45cb0"
OLAS_ADDRESS_GNOSIS = "0xce11e14225575945b8e6dc0d4f2dd4c570f79d9f"
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


def validate_eoa_signature(message_hash, expected_address, signature):
    """Validate an EOA signature"""
    try:
        address = Account.recover_message(message_hash, signature=signature)
        return address == expected_address
    except ValidationError:
        return False


class TweetValidationPreparation(TaskPreparation):
    """TweetValidationPreparation"""

    task_name = "tweet_validation"
    task_event = Event.TWEET_VALIDATION.value

    def check_extra_conditions(self):
        """Validate Twitter credentials for the current centaur"""
        current_centaur = self.synchronized_data.centaurs_data[
            self.synchronized_data.current_centaur_index
        ]
        centaur_id_to_secrets = self.params.centaur_id_to_secrets

        if current_centaur["id"] not in centaur_id_to_secrets:
            return False

        if "twitter" not in centaur_id_to_secrets[current_centaur["id"]]:
            return False

        secrets = centaur_id_to_secrets[current_centaur["id"]]["twitter"]

        if sorted(secrets.keys()) != sorted(
            ["consumer_key", "consumer_secret", "access_token", "access_secret"]
        ):
            return False

        return True

    def _pre_task(self):
        """Preparations before running the task"""
        self.behaviour.context.logger.info("Nothing to do")
        return {}, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        centaurs_data = self.synchronized_data.centaurs_data
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]

        removal_ids = []
        for tweet in current_centaur["plugins_data"]["scheduled_tweet"]["tweets"]:
            # Ignore posted tweets
            if not tweet["posted"]:
                continue

            # Remove invalid votes and mark tweet for removal if needed
            tweet = yield from self.clean_votes(tweet)
            if not tweet["voters"]:
                removal_ids.append(tweet["request_id"])
                continue

            # Ignore tweet if it is not market for execution
            if not tweet["executionAttempts"]:
                continue

            # Mark execution for success or failure
            is_tweet_executable = yield from self.is_tweet_executable(tweet)
            tweet["executionAttempts"][-1]["verified"] = is_tweet_executable

        # Remove invalid tweets
        filtered_tweets = [
            t
            for t in current_centaur["plugins_data"]["scheduled_tweet"]["tweets"]
            if t["request_id"] not in removal_ids
        ]
        current_centaur["plugins_data"]["scheduled_tweet"]["tweets"] = filtered_tweets

        updates = {"centaurs_data": centaurs_data, "has_centaurs_changes": True}

        return updates, None

    def clean_votes(self, tweet):
        """Remove invalid signatures"""
        message_hash = encode_defunct(text=tweet["text"])

        valid_voters = []
        for v in tweet["voters"]:
            is_valid = yield from self.validate_signature(
                message_hash, v.keys()[0], v.values()[0]
            )
            if is_valid:
                valid_voters.append(v)
        tweet["voters"] = valid_voters
        return tweet

    def is_tweet_executable(self, tweet: dict):
        """Check whether a tweet can be published"""

        # Reject tweets with no execution attempts
        if not tweet["executionAttempts"]:
            return False

        # Reject already processed tweets
        if tweet["executionAttempts"][-1]["verified"] in [True, False]:
            return False

        # At this point, the tweet is awaiting to be published [verified=None]

        # Reject tweet that do not have enough voting power
        consensus = yield from self.check_tweet_consensus(tweet["voters"])
        if not consensus:
            return False

        return True

    def check_tweet_consensus(self, tweet: dict):
        """Check whether users agree on posting"""
        total_voting_power = 0

        for voter in tweet["voters"]:
            voting_power = yield from self.get_voting_power(voter.keys()[0])
            total_voting_power += voting_power

        self.behaviour.context.logger.info(
            f"Voting power is {total_voting_power} for tweet {tweet['text']}"
        )
        return total_voting_power >= TWEET_CONSENSUS_WVEOLAS_WEI

    def get_voting_power(self, address: str) -> Generator[None, None, int]:
        """Get the given address's balance."""
        olas_balance_ethereum = (
            yield from self.get_token_balance(
                OLAS_ADDRESS_ETHEREUM, address, "ethereum"
            )
            or 0
        )
        olas_balance_gnosis = (
            yield from self.get_token_balance(OLAS_ADDRESS_GNOSIS, address, "gnosis")
            or 0
        )
        voting_power = cast(int, olas_balance_ethereum) + cast(int, olas_balance_gnosis)
        self.behaviour.context.logger.info(
            f"Voting power is {voting_power} for address {address}"
        )
        return voting_power

    def get_token_balance(
        self, token_address, owner_address, chain_id
    ) -> Generator[None, None, Optional[int]]:
        """Get the given address's balance."""
        response = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=token_address,
            contract_id=str(UniswapV2ERC20Contract.contract_id),
            contract_callable="balance_of",
            owner_address=owner_address,
            chain_id=chain_id,
        )
        if response.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Couldn't get the balance for address {chain_id}::{owner_address}: {response.performative}"
            )
            return None

        return response.state.body

    def is_contract(self, address):
        """Check if the account is a smart contract"""

        # Call get_code
        contract_api_msg = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.params.dynamic_contribution_contract_address,
            contract_id=str(CompatibilityFallbackHandlerContract.contract_id),
            contract_callable="get_code",
            address=address,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Error getting the code for address {address}: [{contract_api_msg.performative}]"
            )
            return False

        is_valid = cast(dict, contract_api_msg.state.body["valid"])

        return is_valid

    def validate_safe_signature(self, message_hash, address):
        """Validate a safe signature"""
        # Get the message from the hash using Safe Transaction Service
        url = f"https://safe-transaction-mainnet.safe.global/api/v1/messages/{message_hash}/"

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
        contract_api_msg = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.params.dynamic_contribution_contract_address,
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

    def validate_signature(self, message_hash, address, signature):
        """Validate signatures"""
        is_contract = yield from self.is_contract(address)
        if is_contract:
            yield from self.validate_safe_signature(message_hash, address)
        else:
            return validate_eoa_signature(message_hash, address, signature)
