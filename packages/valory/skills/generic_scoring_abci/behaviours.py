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

"""This package contains round behaviours of GenericScoringAbciApp."""

import json
from abc import ABC
from typing import Dict, Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.generic_scoring_abci.models import Params
from packages.valory.skills.generic_scoring_abci.rounds import (
    GenericScoringAbciApp,
    GenericScoringPayload,
    GenericScoringRound,
    SynchronizedData,
)
from copy import deepcopy
from packages.valory.skills.decision_making_abci.models import CeramicDB


class GenericScoringBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the generic_scoring_abci skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


class GenericScoringBehaviour(GenericScoringBaseBehaviour):
    """GenericScoringBehaviour"""

    matching_round: Type[AbstractRound] = GenericScoringRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            payload_data = self.update_ceramic_db()
            sender = self.context.agent_address
            payload = GenericScoringPayload(
                sender=sender, content=json.dumps(payload_data, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def update_ceramic_db(self) -> Dict:
        """Calculate the new content of the DB"""

        pending_write = self.synchronized_data.pending_write

        # Instantiate the db
        ceramic_db_copy = deepcopy(self.context.ceramic_db)
        scores_db = CeramicDB()
        scores_db.load(self.synchronized_data.score_data)  # temp db

        # Only update if latest_update_id has increased
        latest_update_id_stream = int(
            scores_db.data["module_data"]["generic"]["latest_update_id"]
        )
        latest_update_id_db = int(
            ceramic_db_copy.data["module_data"]["generic"]["latest_update_id"]
        )

        if latest_update_id_stream <= latest_update_id_db:
            self.context.logger.info(
                f"Not adding scores from the stream because latest_update_id_stream({latest_update_id_stream!r}) <= latest_update_id_db({latest_update_id_db!r})"
            )
            return {"ceramic_diff": self.context.ceramic_db.diff(ceramic_db_copy), "pending_write": pending_write}

        # discord_id, discord_handle, points, wallet_address
        for user in scores_db.data["users"]:
            discord_id = user.pop("discord_id")
            ceramic_db_copy.update_or_create_user(  # overwrites all common fields for the user
                "discord_id", discord_id, user
            )
            pending_write = True

        # latest_update_id
        ceramic_db_copy.data["module_data"]["generic"]["latest_update_id"] = str(
            scores_db.data["module_data"]["generic"]["latest_update_id"]
        )

        # If a user has first contributed to one module (i.e. twitter) without registering a wallet,
        # and later he/she contributes to another module, it could happen that we have two different
        # entries on the database
        ceramic_db_copy.merge_by_wallet()

        return {"ceramic_diff": self.context.ceramic_db.diff(ceramic_db_copy), "pending_write": pending_write}


class GenericScoringRoundBehaviour(AbstractRoundBehaviour):
    """GenericScoringRoundBehaviour"""

    initial_behaviour_cls = GenericScoringBehaviour
    abci_app_cls = GenericScoringAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [GenericScoringBehaviour]
