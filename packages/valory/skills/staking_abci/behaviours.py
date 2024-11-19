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
from datetime import datetime, timezone
from typing import Dict, Generator, List, Optional, Set, Tuple, Type, cast

from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation,
)
from packages.valory.contracts.multisend.contract import (
    MultiSendContract,
    MultiSendOperation,
)
from packages.valory.contracts.staking.contract import Staking
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.staking_abci.models import Params, SharedState
from packages.valory.skills.staking_abci.rounds import (
    ActivityScorePayload,
    ActivityScoreRound,
    ActivityUpdatePreparationPayload,
    ActivityUpdatePreparationRound,
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

    @property
    def local_state(self) -> SharedState:
        """Return the state."""
        return cast(SharedState, self.context.state)

    def _build_safe_tx_hash(
        self,
        to_address: str,
        value: int = ZERO_VALUE,
        data: bytes = EMPTY_CALL_DATA,
        operation: int = SafeOperation.CALL.value,
    ) -> Generator[None, None, Optional[str]]:
        """Prepares and returns the safe tx hash for a multisend tx."""

        self.context.logger.info(
            f"Preparing Safe transaction [{self.params.safe_contract_address_base}]"
        )

        # Prepare the safe transaction
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.params.safe_contract_address_base,
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

    def get_staked_services(self, staking_contract_address: str) -> Generator[None, None, Optional[List]]:
        """Get the services staked on a contract"""
        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=staking_contract_address,
            contract_id=str(Staking.contract_id),
            contract_callable="get_service_ids",
            chain_id=BASE_CHAIN_ID,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"Error getting the service ids: [{contract_api_msg.performative}]"
            )
            return None

        service_ids = cast(str, contract_api_msg.state.body["service_ids"])

        self.context.logger.info(f"Got {len(service_ids)} staked services for contract {staking_contract_address}")

        return service_ids

    def _get_utc_time(self):
        """Check if it is process time"""
        now_utc = self.local_state.round_sequence.last_round_transition_timestamp

        # Tendermint timestamps are expected to be UTC, but for some reason
        # we are getting local time. We replace the hour and timezone.
        # TODO: this hour replacement could be problematic in some time zones
        now_utc = now_utc.replace(
            hour=datetime.now(timezone.utc).hour, tzinfo=timezone.utc
        )
        now_utc_str = now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")
        self.context.logger.info(f"Now [UTC]: {now_utc_str}")

        return now_utc

    def get_epoch_end(
        self, staking_contract_address
    ) -> Generator[None, None, Optional[datetime]]:
        """Get the epoch end"""

        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=staking_contract_address,
            contract_id=str(Staking.contract_id),
            contract_callable="get_epoch_end",
            chain_id=BASE_CHAIN_ID,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"Error getting the epoch end: [{contract_api_msg.performative}]"
            )
            return None

        epoch_end_ts = cast(int, contract_api_msg.state.body["epoch_end"])
        epoch_end = datetime.fromtimestamp(epoch_end_ts, tz=timezone.utc)
        return epoch_end

    def is_checkpoint_callable(self, staking_contract_address) -> Generator[None, None, bool]:
        """Check if the epoch has ended"""
        epoch_end = yield from self.get_epoch_end(staking_contract_address)

        if not epoch_end:
            return False

        # If the epoch end is in the past, the epoch has ended and
        # no one has called the checkpoint
        return epoch_end < self._get_utc_time()

    def get_staking_epoch(
        self, staking_contract_address
    ) -> Generator[None, None, Optional[int]]:
        """Get the staking epoch"""

        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=staking_contract_address,
            contract_id=str(Staking.contract_id),
            contract_callable="get_epoch",
            chain_id=BASE_CHAIN_ID,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(f"Error getting the epoch: [{contract_api_msg}]")
            return None

        epoch = cast(int, contract_api_msg.state.body["epoch"])
        return epoch


class ActivityScoreBehaviour(StakingBaseBehaviour):
    """ActivityScoreBehaviour"""

    matching_round: Type[AbstractRound] = ActivityScoreRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            sender = self.context.agent_address
            pending_write = False

            # Check whether we just came back from settling an update
            if self.synchronized_data.tx_submitter == ActivityUpdatePreparationBehaviour.auto_behaviour_id():
                staking_user_to_counted_tweets = self.synchronized_data.staking_user_to_counted_tweets

                # For each user, update the last processed tweet on the model, and mark for Ceramic update
                for user_id, counter_tweets in staking_user_to_counted_tweets.items():
                    for tweet_id in counter_tweets:
                        self.context.ceramic_db.data["users"][user_id]["tweets"][tweet_id]["counted_for_activity"] = True
                pending_write = True
                self.context.logger.info(f"Tweets counted for activity: {staking_user_to_counted_tweets}. Ceramic marked for update.")

            # Process new updates
            else:
                self.context.logger.info("Processing activity updates")

            payload = ActivityScorePayload(
                sender=sender,
                pending_write=pending_write
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class ActivityUpdatePreparationBehaviour(StakingBaseBehaviour):
    """ActivityUpdatePreparationBehaviour"""

    matching_round: Type[AbstractRound] = ActivityUpdatePreparationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            tx_hash = yield from self.get_activity_update_hash()
            payload = ActivityUpdatePreparationPayload(
                sender=sender,
                tx_submitter=self.auto_behaviour_id(),
                tx_hash=tx_hash,
                safe_contract_address=self.params.safe_contract_address_base
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


    def get_activity_update_hash(self) -> Generator[None, None, Optional[str]]:
        """Prepare the activity update tx"""

        self.context.logger.info(
            f"Preparing activity update call: {self.synchronized_data.staking_multisig_to_updates}"
        )

        # Use the contract api to interact with the activity tracker contract
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.contributors_contract_address,
            contract_id=str(Staking.contract_id),
            contract_callable="build_activity_update_tx",
            updates=self.synchronized_data.staking_multisig_to_updates,
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
            to_address=self.params.contributors_contract_address,
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
                tx_hash=tx_hash,
                safe_contract_address=self.params.safe_contract_address_base
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_checkpoint_hash(self) -> Generator[None, None, Optional[str]]:
        """Prepare the checkpoint tx"""
        self.context.logger.info(
            "Preparing checkpoint calls"
        )

        multi_send_txs = []

        for staking_contract_address in self.params.staking_contract_addresses:

            # Check if there is some service staked on this contract
            services_staked = yield from self.get_staked_services(staking_contract_address)
            if not services_staked:
                continue

            # Check if this checkpoint needs to be called
            is_checkpoint_callable = yield from self.is_checkpoint_callable(staking_contract_address)
            if not is_checkpoint_callable:
                continue

            # Use the contract api to interact with the staking contract
            response_msg = yield from self.get_contract_api_response(
                performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
                contract_address=staking_contract_address,
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

            if data_bytes is None:
                self.context.logger.error(
                    f"Error while preparing the checkpoint call: {response_msg}"
                )
                return None

            multi_send_txs.append(
                {
                    "operation": MultiSendOperation.CALL,
                    "to": staking_contract_address,
                    "value": ZERO_VALUE,
                    "data": data_bytes,
                }
            )

        # Multisend call
        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.multisend_address,
            contract_id=str(MultiSendContract.contract_id),
            contract_callable="get_tx_data",
            multi_send_txs=multi_send_txs,
            chain_id=BASE_CHAIN_ID,
        )

        # Check for errors
        if (
            contract_api_msg.performative
            != ContractApiMessage.Performative.RAW_TRANSACTION
        ):
            self.context.logger.error(
                f"Could not get Multisend tx hash. "
                f"Expected: {ContractApiMessage.Performative.RAW_TRANSACTION.value}, "
                f"Actual: {contract_api_msg.performative.value}"
            )
            return None

        # Extract the multisend data and strip the 0x
        multisend_data = cast(str, contract_api_msg.raw_transaction.body["data"])[2:]
        self.context.logger.info(f"Multisend data is {multisend_data}")

        # Prepare the safe transaction
        safe_tx_hash = yield from self._build_safe_tx_hash(
            to_address=self.params.multisend_address,
            value=ZERO_VALUE,  # the safe is not moving any native value into the multisend
            data=bytes.fromhex(multisend_data),
            operation=SafeOperation.DELEGATE_CALL.value
        )

        return safe_tx_hash


class StakingRoundBehaviour(AbstractRoundBehaviour):
    """StakingRoundBehaviour"""

    initial_behaviour_cls = ActivityScoreBehaviour
    abci_app_cls = StakingAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        ActivityScoreBehaviour,
        ActivityUpdatePreparationBehaviour,
        CheckpointPreparationBehaviour
    ]
