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

"""This package contains round behaviours of ScoreReadAbciApp."""

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
from packages.valory.skills.score_read_abci.behaviours import (
    ScoreReadBaseBehaviour,
    ScoreReadRoundBehaviour,
    ScoringBehaviour,
    TwitterObservationBehaviour,
)
from packages.valory.skills.score_read_abci.rounds import (
    Event,
    FinishedScoringRound,
    SynchronizedData,
)


TWITTER_API_URL = "https://api.twitter.com/2/users/1450081635559428107/mentions?tweet.fields=author_id&user.fields=name&max_results=100&since_id=0"

DUMMY_API_RESPONSE = {
    "data": [
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812738", "text": "dummy_text"},
        {"author_id": "1286010187325812737", "text": "dummy_text"},
    ],
    "meta": {"result_count": 4, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_MOST_VOTED_API_DATA = {
    "user_to_mentions": {
        "1286010187325812739": 2,
        "1286010187325812738": 1,
        "1286010187325812737": 1,
    },
    "latest_tweet_id": DUMMY_API_RESPONSE["meta"]["newest_id"],
}


@dataclass
class BehaviourTestCase:
    """BehaviourTestCase"""

    name: str
    initial_data: Dict[str, Any]
    event: Event
    next_behaviour_class: Optional[Type[ScoreReadBaseBehaviour]] = None


class BaseSwaapTest(FSMBehaviourBaseCase):
    """Base test case."""

    path_to_skill = Path(__file__).parent.parent

    behaviour: ScoreReadRoundBehaviour
    behaviour_class: Type[ScoreReadBaseBehaviour]
    next_behaviour_class: Type[ScoreReadBaseBehaviour]
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


class TestTwitterObservationBehaviour(BaseSwaapTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterObservationBehaviour
    next_behaviour_class = ScoringBehaviour

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
                        DUMMY_API_RESPONSE,
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
                headers="Authorization: Bearer <default_bearer_token>\r\n",
                version="",
                url=TWITTER_API_URL,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)


class TestTwitterObservationBehaviourAPIError(BaseSwaapTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterObservationBehaviour
    next_behaviour_class = TwitterObservationBehaviour

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
                        DUMMY_API_RESPONSE,
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
        self.mock_http_request(  # we will fail during the first call
            request_kwargs=dict(
                method="GET",
                headers="Authorization: Bearer <default_bearer_token>\r\n",
                version="",
                url=TWITTER_API_URL,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)


class TestScoringBehaviour(BaseSwaapTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = ScoringBehaviour
    next_behaviour_class = make_degenerate_behaviour(  # type: ignore
        FinishedScoringRound
    )

    @pytest.mark.parametrize(
        "test_case",
        [
            BehaviourTestCase(
                "Happy path",
                initial_data={"most_voted_api_data": DUMMY_MOST_VOTED_API_DATA},
                event=Event.DONE,
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.complete(test_case.event)
