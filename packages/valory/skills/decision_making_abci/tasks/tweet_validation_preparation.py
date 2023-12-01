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

from typing import Generator, Optional

from eth_account.messages import encode_defunct

from packages.valory.contracts.wveOLAS.contract import WveOLASContract
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.signature_validation import (
    SignatureValidationMixin,
)
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


PROPOSAL_MINIMUM_WVEOLAS_WEI = 100e3 * 1e18  # 2M wveOLAS to wei
WVEOLAS_ADDRESS_ETHEREUM = "0x4039B809E0C0Ad04F6Fc880193366b251dDf4B40"


class TweetValidationPreparation(TaskPreparation, SignatureValidationMixin):
    """TweetValidationPreparation"""

    task_name = "tweet_validation"
    task_event = Event.TWEET_VALIDATION.value

    def check_extra_conditions(self):
        """Validate Twitter credentials for the current centaur"""
        yield
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
        centaurs_data = self.synchronized_data.centaurs_data
        current_centaur = centaurs_data[self.synchronized_data.current_centaur_index]
        updates = {}

        for tweet in current_centaur["plugins_data"]["scheduled_tweet"]["tweets"]:
            # Ignore posted tweets
            if tweet["posted"]:
                continue

            # Ignore already processed proposals
            if tweet["proposer"]["verified"] is not None:
                continue

            # Verify proposer signature
            message = f"I am signing a message to verify that I propose a tweet starting with {tweet['text'][:10]}"
            message_hash = encode_defunct(text=message)
            is_valid = yield from self.validate_signature(
                message_hash,
                tweet["proposer"]["address"],
                tweet["proposer"]["signature"],
            )
            self.logger.info(f"Is the proposer signature valid? {is_valid}")

            # Check the proposer voting power
            voting_power = yield from self.get_voting_power(
                tweet["proposer"]["address"]
            )
            verified = voting_power >= PROPOSAL_MINIMUM_WVEOLAS_WEI

            tweet["proposer"]["verified"] = verified
            updates = {"centaurs_data": centaurs_data, "has_centaurs_changes": True}

        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        yield
        self.behaviour.context.logger.info("Nothing to do")
        return {}, None

    def get_voting_power(self, address: str):
        """Get the given address's balance."""
        olas_balance = yield from self.get_votes(
            WVEOLAS_ADDRESS_ETHEREUM, address, "ethereum"
        )

        if not olas_balance:
            olas_balance = 0

        self.behaviour.context.logger.info(
            f"Voting power is {olas_balance} for address {address}"
        )
        return olas_balance

    def get_votes(
        self, token_address, owner_address, chain_id
    ) -> Generator[None, None, Optional[float]]:
        """Get the given address's balance."""
        response = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=token_address,
            contract_id=str(WveOLASContract.contract_id),
            contract_callable="get_votes",
            owner_address=owner_address,
            chain_id=chain_id,
        )
        if response.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Couldn't get the balance for address {chain_id}::{owner_address}: {response.performative}"
            )
            return None

        balance = int(response.state.body["balance"]) / 1e18  # to olas
        return balance
