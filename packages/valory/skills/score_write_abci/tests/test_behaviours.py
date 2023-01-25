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

"""This package contains round behaviours of ScoreWriteAbciApp."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Type

import pytest

from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.abstract_round_abci.behaviours import (
    make_degenerate_behaviour,
)
from packages.valory.skills.abstract_round_abci.test_tools.base import (
    FSMBehaviourBaseCase,
)
from packages.valory.skills.score_write_abci.behaviours import (
    ScoreWriteBaseBehaviour,
    ScoreWriteRoundBehaviour,
    RandomnessBehaviour,
    SelectKeeperCeramicBehaviour,
    CeramicWriteBehaviour,
    VerificationBehaviour,
)
from packages.valory.skills.score_write_abci.rounds import (
    Event,
    FinishedVerificationRound,
    SynchronizedData,
)
from packages.valory.skills.abstract_round_abci.test_tools.common import (
    BaseRandomnessBehaviourTest,
    BaseSelectKeeperBehaviourTest,
)

PACKAGE_DIR = Path(__file__).parent.parent

DUMMY_USER_TO_SCORES = {"dummy_user": "dummy_score"}

CERAMIC_API_COMMIT_URL = "https://ceramic-clay.3boxlabs.com/api/v0/commits/dummy_stream_id"

class TestRandomnessBehaviour(BaseRandomnessBehaviourTest):
    """Test randomness in operation."""

    path_to_skill = PACKAGE_DIR

    randomness_behaviour_class = RandomnessBehaviour
    next_behaviour_class = SelectKeeperCeramicBehaviour
    done_event = Event.DONE


class TestSelectKeeperBehaviour(BaseSelectKeeperBehaviourTest):
    """Test SelectKeeperBehaviour."""

    path_to_skill = PACKAGE_DIR

    select_keeper_behaviour_class = SelectKeeperCeramicBehaviour
    next_behaviour_class = CeramicWriteBehaviour
    done_event = Event.DONE
    _synchronized_data = SynchronizedData


@dataclass
class BehaviourTestCase:
    """BehaviourTestCase"""

    name: str
    initial_data: Dict[str, Any]
    event: Event
    next_behaviour_class: Optional[Type[ScoreWriteBaseBehaviour]] = None


class BaseScoreWriteTest(FSMBehaviourBaseCase):
    """Base test case."""

    path_to_skill = Path(__file__).parent.parent

    behaviour: ScoreWriteRoundBehaviour
    behaviour_class: Type[ScoreWriteBaseBehaviour]
    next_behaviour_class: Type[ScoreWriteBaseBehaviour]
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


class TestCeramicWriteBehaviour(BaseScoreWriteTest):
    """Tests CeramicWriteBehaviour"""

    behaviour_class = CeramicWriteBehaviour
    next_behaviour_class = VerificationBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(),
                    event=Event.DONE,
                ),
                {
                    "body": json.dumps(
                        {},
                    ),
                    "status_code": 200,
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.mock_http_request(
            request_kwargs=dict(
                method="GET",
                headers="",
                version="",
                url=CERAMIC_API_COMMIT_URL,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)


class TestCeramicWriteBehaviourApiError(BaseScoreWriteTest):
    """Tests CeramicWriteBehaviour"""

    behaviour_class = CeramicWriteBehaviour
    next_behaviour_class = RandomnessBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API error",
                    initial_data=dict(),
                    event=Event.API_ERROR,
                ),
                {
                    "body": json.dumps(
                        {},
                    ),
                    "status_code": 404,
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.mock_http_request(
            request_kwargs=dict(
                method="GET",
                headers="",
                version="",
                url=CERAMIC_API_COMMIT_URL,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)


class TestVerificationBehaviour(BaseScoreWriteTest):
    """Tests CeramicWriteBehaviour"""

    behaviour_class = VerificationBehaviour
    next_behaviour_class = make_degenerate_behaviour(  # type: ignore
        FinishedVerificationRound.auto_round_id()
    )

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(user_to_scores=DUMMY_USER_TO_SCORES),
                    event=Event.DONE,
                ),
                {
                    "body": json.dumps(
                        {"<TODO>": DUMMY_USER_TO_SCORES},
                    ),
                    "status_code": 200,
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.mock_http_request(
            request_kwargs=dict(
                method="GET",
                headers="",
                version="",
                url=CERAMIC_API_COMMIT_URL,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)


class TestVerificationBehaviourApiError(BaseScoreWriteTest):
    """Tests CeramicWriteBehaviour"""

    behaviour_class = VerificationBehaviour
    next_behaviour_class = RandomnessBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Api Error",
                    initial_data=dict(user_to_scores=DUMMY_USER_TO_SCORES),
                    event=Event.API_ERROR,
                ),
                {
                    "body": json.dumps(
                        {},
                    ),
                    "status_code": 404,
                },
            ),
            (
                BehaviourTestCase(
                    "Api wrong data",
                    initial_data=dict(user_to_scores=DUMMY_USER_TO_SCORES),
                    event=Event.API_ERROR,
                ),
                {
                    "body": json.dumps(
                        {"<TODO>": {}},
                    ),
                    "status_code": 200,
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.mock_http_request(
            request_kwargs=dict(
                method="GET",
                headers="",
                version="",
                url=CERAMIC_API_COMMIT_URL,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)