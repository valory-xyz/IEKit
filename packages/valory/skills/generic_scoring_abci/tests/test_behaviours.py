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

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Type

import pytest

from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.abstract_round_abci.behaviours import (
    BaseBehaviour,
    make_degenerate_behaviour,
)
from packages.valory.skills.abstract_round_abci.test_tools.base import (
    FSMBehaviourBaseCase,
)
from packages.valory.skills.generic_scoring_abci.behaviours import (
    GenericScoringBaseBehaviour,
    GenericScoringBehaviour,
    GenericScoringRoundBehaviour,
)
from packages.valory.skills.generic_scoring_abci.rounds import (
    Event,
    FinishedGenericScoringRound,
    SynchronizedData,
)


DUMMY_CERAMIC_DB = {
    "users": [
        {
            "discord_id": "dummy_discord_id",
            "wallet_address": "dummy_wallet_address",
            "points": 10,
        }
    ],
    "module_data": {
        "twitter": {"latest_mention_tweet_id": 0},
        "dynamic_nft": {},
        "generic": {"latest_update_id": 0},
    },
}

DUMMY_SCORE_DATA = {
    "users": [
        {
            "discord_id": "dummy_discord_id",
            "wallet_address": "dummy_wallet_address",
            "points": 10,
        }
    ],
    "module_data": {
        "twitter": {},
        "dynamic_nft": {},
        "generic": {"latest_update_id": 1},
    },
}


@dataclass
class BehaviourTestCase:
    """BehaviourTestCase"""

    name: str
    initial_data: Dict[str, Any]
    event: Event
    next_behaviour_class: Optional[Type[GenericScoringBaseBehaviour]] = None


class BaseGenericScoringTest(FSMBehaviourBaseCase):
    """Base test case."""

    path_to_skill = Path(__file__).parent.parent

    behaviour: GenericScoringRoundBehaviour
    behaviour_class: Type[GenericScoringBaseBehaviour]
    next_behaviour_class: Type[GenericScoringBaseBehaviour]
    synchronized_data: SynchronizedData
    done_event = Event.DONE

    def fast_forward(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Fast-forward on initialization"""

        data = data if data is not None else {}
        self.fast_forward_to_behaviour(
            self.behaviour,  # type: ignore
            self.behaviour_class.auto_behaviour_id(),
            SynchronizedData(AbciAppDB(setup_data=AbciAppDB.data_to_lists(data))),
        )
        assert (
            self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
            == self.behaviour_class.auto_behaviour_id()
        )

    def complete(self, event: Event) -> None:
        """Complete test"""

        self.behaviour.act_wrapper()
        self.mock_a2a_transaction()
        self._test_done_flag_set()
        self.end_round(done_event=event)
        assert (
            self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
            == self.next_behaviour_class.auto_behaviour_id()
        )


class TestGenericScoringBehaviour(BaseGenericScoringTest):
    """Tests GenericScoringBehaviour"""

    behaviour_class: Type[BaseBehaviour] = GenericScoringBehaviour
    next_behaviour_class: Type[BaseBehaviour] = make_degenerate_behaviour(
        FinishedGenericScoringRound
    )

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        ceramic_db=DUMMY_CERAMIC_DB, score_data=DUMMY_SCORE_DATA
                    ),
                    event=Event.DONE,
                ),
                {},
            )
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.complete(test_case.event)
