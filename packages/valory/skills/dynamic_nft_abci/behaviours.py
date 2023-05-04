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
from typing import Dict, Generator, Optional, Set, Tuple, Type, cast

from packages.valory.contracts.dynamic_contribution.contract import (
    DynamicContributionContract,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.dynamic_nft_abci.ceramic_db import CeramicDB
from packages.valory.skills.dynamic_nft_abci.models import Params, SharedState
from packages.valory.skills.dynamic_nft_abci.payloads import TokenTrackPayload
from packages.valory.skills.dynamic_nft_abci.rounds import (
    DynamicNFTAbciApp,
    SynchronizedData,
    TokenTrackRound,
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


class TokenTrackBehaviour(DynamicNFTBaseBehaviour):
    """TokenTrackBehaviour"""

    matching_round: Type[AbstractRound] = TokenTrackRound

    def async_act(self) -> Generator:
        """Get a list of the new tokens."""
        with self.context.benchmark_tool.measure(
            self.behaviour_id,
        ).local():

            (
                new_token_id_to_address,
                last_parsed_block,
            ) = yield from self.get_token_id_to_address()

            if (
                new_token_id_to_address == TokenTrackRound.ERROR_PAYLOAD
                or not last_parsed_block
            ):
                payload_data = TokenTrackRound.ERROR_PAYLOAD
            else:
                payload_data = self.update_ceramic_db(
                    new_token_id_to_address, last_parsed_block
                )

        with self.context.benchmark_tool.measure(
            self.behaviour_id,
        ).consensus():
            payload = TokenTrackPayload(
                self.context.agent_address, json.dumps(payload_data, sort_keys=True)
            )
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_token_id_to_address(
        self,
    ) -> Generator[None, None, Tuple[dict, Optional[int]]]:
        """Get token id to address data."""
        try:
            from_block = int(
                self.synchronized_data.ceramic_db["module_data"]["dynamic_nft"][
                    "last_parsed_block"
                ]
            )
        except KeyError:
            from_block = self.params.earliest_block_to_monitor

        self.context.logger.info(
            f"Retrieving Transfer events later than block {from_block}"
            f" for contract at {self.params.dynamic_contribution_contract_address}"
        )
        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.params.dynamic_contribution_contract_address,
            contract_id=str(DynamicContributionContract.contract_id),
            contract_callable="get_all_erc721_transfers",
            from_address=NULL_ADDRESS,
            from_block=from_block,
        )
        if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.info("Error retrieving the token_id to address data")
            return TokenTrackRound.ERROR_PAYLOAD, from_block
        data = cast(dict, contract_api_msg.state.body["token_id_to_member"])
        last_block = cast(int, contract_api_msg.state.body["last_block"])
        self.context.logger.info(
            f"Got token_id to address data up to block {last_block}: {data}"
        )
        return data, last_block

    def update_ceramic_db(
        self, new_token_id_to_address: Dict, last_parsed_block: int
    ) -> Dict:
        """Calculate the new content of the DB"""

        pending_write = self.synchronized_data.pending_write

        # We store a token_id to points mapping so it is quick
        # to retrieve the scores for a given token_id, which is done
        # during each request to the handler
        token_id_to_points = self.synchronized_data.token_id_to_points

        # Instantiate the db
        ceramic_db = CeramicDB(self.synchronized_data.ceramic_db, self.context.logger)

        # Update token_ids in the ceramic_db
        for token_id, address in new_token_id_to_address.items():
            user, _ = ceramic_db.get_user_by_field("wallet_address", address)

            # Create a new user if it does not exist
            # Update user in the following cases:
            # - User exists and its current token_id is None
            # - User exists and its current token_id is greater than the one in this iteration (only the first minted token is assigned to the user)
            if (
                not user
                or user["token_id"] is None
                or int(token_id) < int(user["token_id"])
            ):
                ceramic_db.update_or_create_user(
                    "wallet_address", address, {"token_id": token_id}
                )
                pending_write = True  # user is created or updated

        # If a user has first contributed to one module (i.e. twitter) without registering a wallet,
        # and later he/she contributes to another module, it could happen that we have two different
        # entries on the database
        ceramic_db.merge_by_wallet()

        # Rebuild token_to_points
        new_token_id_to_points = {
            user["token_id"]: user["points"]
            for user in ceramic_db.data["users"]
            if user["token_id"]
        }

        # ceramic_db only stores the first minted token for each user
        # We add the extra tokens to new_token_id_to_points and assing a score of 0
        for token_id in new_token_id_to_address.keys():
            user, _ = ceramic_db.get_user_by_field("token_id", token_id)
            if not user:
                new_token_id_to_points[token_id] = DEFAULT_POINTS

        # Update token_id_to_points
        token_id_to_points.update(new_token_id_to_points)

        # Last parsed block
        ceramic_db.data["module_data"]["dynamic_nft"]["last_parsed_block"] = str(
            last_parsed_block
        )

        # Last update time
        last_update_time = cast(
            SharedState, self.context.state
        ).round_sequence.last_round_transition_timestamp.timestamp()

        data = {
            "last_update_time": last_update_time,
            "token_id_to_points": token_id_to_points,
            "ceramic_db": ceramic_db.data,
            "pending_write": pending_write,
        }

        self.context.logger.info(f"Token data updated: {data}")

        return data


class DynamicNFTRoundBehaviour(AbstractRoundBehaviour):
    """DynamicNFTRoundBehaviour"""

    initial_behaviour_cls = TokenTrackBehaviour
    abci_app_cls = DynamicNFTAbciApp
    behaviours: Set[Type[BaseBehaviour]] = [
        TokenTrackBehaviour,
    ]
