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

"""This package contains round behaviours of StakingMakingAbciApp."""

import json
from abc import ABC
from typing import Dict, Generator, Optional, Set, Tuple, Type, cast

from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation,
)
from packages.valory.contracts.staking.contract import Staking
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.staking_abci.models import Params
from packages.valory.skills.staking_abci.rounds import (
    ActivityScorePayload,
    ActivityScoreRound,
    ActiviyUpdatePreparationPayload,
    ActiviyUpdatePreparationRound,
    CheckpointPreparationPayload,
    CheckpointPreparationRound,
    StakingAbciApp,
    SynchronizedData,
)
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
from packages.valory.skills.transaction_settlement_abci.rounds import TX_HASH_LENGTH


# Define some constants
ZERO_VALUE = 0
EMPTY_CALL_DATA = b"0x"
SAFE_GAS = 0
BASE_CHAIN_ID = "base"


class StakingBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the staking_abci skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


    def _build_safe_tx_hash(
        self,
        to_address: str,
        value: int = ZERO_VALUE,
        data: bytes = EMPTY_CALL_DATA,
        operation: int = SafeOperation.CALL.value,
    ) -> Generator[None, None, Optional[str]]:
        """Prepares and returns the safe tx hash for a multisend tx."""

        self.context.logger.info(
            f"Preparing Safe transaction [{self.synchronized_data.safe_contract_address}]"
        )

        # Prepare the safe transaction
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=to_address,
            value=value,
            data=data,
            safe_tx_gas=SAFE_GAS,
            chain_id=BASE_CHAIN_ID,
            operation=operation,
        )

        # Check for errors
        if response_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                "Couldn't get safe tx hash. Expected response performative "
                f"{ContractApiMessage.Performative.STATE.value!r}, "  # type: ignore
                f"received {response_msg.performative.value!r}: {response_msg}."
            )
            return None

        # Extract the hash and check it has the correct length
        tx_hash: Optional[str] = response_msg.state.body.get("tx_hash", None)

        if tx_hash is None or len(tx_hash) != TX_HASH_LENGTH:
            self.context.logger.error(
                "Something went wrong while trying to get the safe transaction hash. "
                f"Invalid hash {tx_hash!r} was returned."
            )
            return None

        # Transaction to hex
        tx_hash = tx_hash[2:]  # strip the 0x

        safe_tx_hash = hash_payload_to_hex(
            safe_tx_hash=tx_hash,
            ether_value=value,
            safe_tx_gas=SAFE_GAS,
            to_address=to_address,
            data=data,
            operation=operation,
        )

        self.context.logger.info(f"Safe transaction hash is {safe_tx_hash}")

        return safe_tx_hash


class ActivityScoreBehaviour(StakingBaseBehaviour):
    """ActivityScoreBehaviour"""

    matching_round: Type[AbstractRound] = ActivityScoreRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            sender = self.context.agent_address

            pending_write = False
            activity_updates = None
            latest_activity_tweet_id = None

            # Check whether we just came back from settling an update
            if self.synchronized_data.tx_submitter == ActiviyUpdatePreparationBehaviour.auto_behaviour_id():
                # Update the last processed tweet on the model, and mark for Ceramic update
                self.context.ceramic_db.data["module_data"]["staking"][
                    "latest_activity_tweet_id"
                ] = self.synchronized_data.latest_activity_tweet_id
                pending_write = True
                self.context.logger.info(f"Last activity tweet id set to {self.synchronized_data.latest_activity_tweet_id}. Ceramic marked for update.")

            # Process new updates
            else:
                activity_updates, latest_activity_tweet_id = self.get_activity_updates()

            payload = ActivityScorePayload(
                sender=sender,
                activity_updates=json.dumps(activity_updates, sort_keys=True),
                latest_activity_tweet_id=latest_activity_tweet_id,
                pending_write=pending_write
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_activity_updates(self) -> Tuple[Dict, int]:
        """Get the latest activity updates"""

        updates = {}
        ceramic_db_copy = self.context.ceramic_db.copy()

        latest_activity_tweet_id = int(ceramic_db_copy.data["module_data"]["staking_activiy"][
            "latest_activity_tweet_id"
        ])

        latest_processed_tweet = latest_activity_tweet_id

        for user in ceramic_db_copy.data["users"]:

            new_tweets = 0

            for tweet_id in user["tweets"].keys():
                tweet_id = int(tweet_id)

                # Skip old tweets
                if tweet_id <= latest_activity_tweet_id:
                    continue

                # Update the last_processed_tweet
                if tweet_id > latest_processed_tweet:
                    latest_processed_tweet = tweet_id

                # Increase activity count
                new_tweets += 1

            # Add the user activity
            if new_tweets:
                updates[user["service_multisig"]] = new_tweets

        return updates, latest_processed_tweet


class ActiviyUpdatePreparationBehaviour(StakingBaseBehaviour):
    """ActiviyUpdatePreparationBehaviour"""

    matching_round: Type[AbstractRound] = ActiviyUpdatePreparationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            tx_hash = yield from self.get_activity_update_hash()
            payload = ActiviyUpdatePreparationPayload(
                sender=sender,
                tx_submitter=self.auto_behaviour_id(),
                tx_hash=tx_hash
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


    def get_activity_update_hash(self) -> Generator[None, None, Optional[str]]:
        """Prepare the activity update tx"""

        self.context.logger.info(
            "Preparing activity update call"
        )

        # Use the contract api to interact with the activity tracker contract
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.activity_contract_address,
            contract_id=str(Staking.contract_id),
            contract_callable="build_activity_update_tx",
            updates=self.synchronized_data.activity_updates,
            chain_id=BASE_CHAIN_ID,
        )

        # Check that the response is what we expect
        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Error while preparing the activity tracker call: {response_msg}"
            )
            return None

        data_bytes = cast(bytes, response_msg.raw_transaction.body.get("data", None))

        # Ensure that the balance is not None
        if data_bytes is None:
            self.context.logger.error(
                f"Error while preparing the activity tracker call: {response_msg}"
            )
            return None

        # Prepare the safe transaction
        safe_tx_hash = yield from self._build_safe_tx_hash(
            to_address=self.params.activity_contract_address,
            data=data_bytes
        )

        return safe_tx_hash


class CheckpointPreparationBehaviour(StakingBaseBehaviour):
    """CheckpointPreparationBehaviour"""

    matching_round: Type[AbstractRound] = CheckpointPreparationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            tx_hash = yield from self.get_checkpoint_hash()
            payload = CheckpointPreparationPayload(
                sender=sender,
                tx_submitter=self.auto_behaviour_id(),
                tx_hash=tx_hash
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_checkpoint_hash(self) -> Generator[None, None, Optional[str]]:
        """Prepare the checkpoint tx"""
        self.context.logger.info(
            "Preparing checkpoint call"
        )

        # Use the contract api to interact with the staking contract
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.staking_contract_address,
            contract_id=str(Staking.contract_id),
            contract_callable="build_checkpoint_tx",
            chain_id=BASE_CHAIN_ID,
        )

        # Check that the response is what we expect
        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Error while preparing the checkpoint call: {response_msg}"
            )
            return None

        data_bytes = cast(bytes, response_msg.raw_transaction.body.get("data", None))

        # Ensure that the balance is not None
        if data_bytes is None:
            self.context.logger.error(
                f"Error while preparing the checkpoint call: {response_msg}"
            )
            return None

        # Prepare the safe transaction
        safe_tx_hash = yield from self._build_safe_tx_hash(
            to_address=self.params.staking_contract_address,
            data=data_bytes
        )

        return safe_tx_hash


class StakingRoundBehaviour(AbstractRoundBehaviour):
    """StakingRoundBehaviour"""

    initial_behaviour_cls = ActivityScoreBehaviour
    abci_app_cls = StakingAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        ActivityScoreBehaviour,
        ActiviyUpdatePreparationBehaviour,
        CheckpointPreparationBehaviour
    ]
