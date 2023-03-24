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

"""This package contains round behaviours of PathSwitchAbciApp."""

from abc import ABC
from typing import Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)

from packages.valory.skills.path_switch_abci.models import Params
from packages.valory.skills.path_switch_abci.rounds import (
    SynchronizedData,
    PathSwitchAbciApp,
    PathSwitchRound,
)
from packages.valory.skills.path_switch_abci.rounds import (
    PathSwitchPayload,
)
import json


class PathSwitchBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the path_switch_abci skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


class PathSwitchBehaviour(PathSwitchBaseBehaviour):
    """PathSwitchBehaviour"""

    matching_round: Type[AbstractRound] = PathSwitchRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            # Data needed for the decision making
            payload_data = {
                "read_stream_id": self.params.manual_points_stream_id,
                "read_target_property": self.params.manual_points_target_property,
            }

            sender = self.context.agent_address
            payload = PathSwitchPayload(sender=sender, content=json.dumps(payload_data, sort_keys=True))

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class PathSwitchRoundBehaviour(AbstractRoundBehaviour):
    """PathSwitchRoundBehaviour"""

    initial_behaviour_cls = PathSwitchBehaviour
    abci_app_cls = PathSwitchAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        PathSwitchBehaviour
    ]
