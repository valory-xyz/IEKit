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

"""This package contains round behaviours of DynamicNFTAbciApp."""

import json
from abc import ABC
from typing import Generator, Set, Type, cast

from packages.valory.contracts.dynamic_contribution.contract import (
    DynamicContributionContract,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.dynamic_nft_abci.models import Params, SharedState
from packages.valory.skills.dynamic_nft_abci.payloads import NewTokensPayload
from packages.valory.skills.dynamic_nft_abci.rounds import (
    DynamicNFTAbciApp,
    NewTokensRound,
    SynchronizedData,
)


NULL_ADDRESS = "0x0000000000000000000000000000000000000000"
DEFAULT_POINTS = 0


class DynamicNFTBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


class NewTokensBehaviour(DynamicNFTBaseBehaviour):
    """NewTokensBehaviour"""

    matching_round: Type[AbstractRound] = NewTokensRound

    def async_act(self) -> Generator:
        """Get a list of the new tokens."""
        with self.context.benchmark_tool.measure(
            self.behaviour_id,
        ).local():

            token_id_to_address = yield from self.get_token_id_to_member()

            if token_id_to_address == NewTokensRound.ERROR_PAYLOAD:
                payload_data = json.dumps(NewTokensRound.ERROR_PAYLOAD, sort_keys=True)
            else:
                old_token_to_data = self.synchronized_data.token_to_data

                # New tokens that have been minted and are currently tracked
                new_token_to_data = {
                    token_id: {
                        "address": address,
                        "points": DEFAULT_POINTS,
                    }
                    for token_id, address in token_id_to_address.items()
                    if token_id not in old_token_to_data
                    and address in self.synchronized_data.wallet_to_users
                }

                token_to_data = {
                    **old_token_to_data,
                    **new_token_to_data,
                }

                address_to_token_ids = {
                    data["address"]: token_id
                    for token_id, data in token_to_data.items()
                }
                users_to_address = {
                    user: address
                    for address, user in self.synchronized_data.wallet_to_users.items()
                }

                # Update points in token_to_data with the updated points
                for user, points in self.synchronized_data.user_to_total_points.items():
                    # No wallet linked to Twitter user
                    if user not in users_to_address:
                        self.context.logger.info(
                            f"Twitter user {user} has not linked a wallet yet. Skipping..."
                        )
                        continue
                    address = users_to_address[user]
                    # Not minted
                    if address not in address_to_token_ids:
                        self.context.logger.info(
                            f"Twitter user {user} has not minted a token yet. Skipping..."
                        )
                        continue
                    token_id = address_to_token_ids[address]
                    token_to_data[token_id]["points"] = points
                    self.context.logger.info(
                        f"Twitter user {user} minted token {token_id} and has {points} points"
                    )

                self.context.logger.info(f"Got the new token data: {token_to_data}")

                last_update_time = cast(
                    SharedState, self.context.state
                ).round_sequence.abci_app.last_timestamp.timestamp()

                payload_data = json.dumps(
                    {
                        "token_to_data": token_to_data,
                        "last_update_time": last_update_time,
                    },
                    sort_keys=True,
                )

                self.context.logger.info(f"Payload data={payload_data}")

        with self.context.benchmark_tool.measure(
            self.behaviour_id,
        ).consensus():
            payload = NewTokensPayload(self.context.agent_address, payload_data)
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_token_id_to_member(self) -> Generator[None, None, dict]:
        """Get token id to member data."""
        self.context.logger.info(
            f"Retrieving Transfer events later than block {self.params.earliest_block_to_monitor}"
            f" for contract at {self.params.dynamic_contribution_contract_address}"
        )
        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.params.dynamic_contribution_contract_address,
            contract_id=str(DynamicContributionContract.contract_id),
            contract_callable="get_all_erc721_transfers",
            from_address=NULL_ADDRESS,
            from_block=self.params.earliest_block_to_monitor,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.info("Error retrieving the token_id to member data")
            return NewTokensRound.ERROR_PAYLOAD
        data = cast(dict, contract_api_msg.state.body["token_id_to_member"])
        self.context.logger.info(f"Got token_id to member data: {data}")
        return data


class DynamicNFTRoundBehaviour(AbstractRoundBehaviour):
    """DynamicNFTRoundBehaviour"""

    initial_behaviour_cls = NewTokensBehaviour
    abci_app_cls = DynamicNFTAbciApp
    behaviours: Set[Type[BaseBehaviour]] = [
        NewTokensBehaviour,
    ]
