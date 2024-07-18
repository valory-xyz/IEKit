# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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

"""This package contains tests for behaviours of OlasWeekAbciApp."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Type, cast
from unittest.mock import patch

import pytest
from aea.exceptions import AEAActException

from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.abstract_round_abci.behaviour_utils import (
    BaseBehaviour,
    make_degenerate_behaviour,
)
from packages.valory.skills.abstract_round_abci.test_tools.base import (
    FSMBehaviourBaseCase,
)
from packages.valory.skills.abstract_round_abci.test_tools.common import (
    BaseRandomnessBehaviourTest,
)
from packages.valory.skills.decision_making_abci.models import CeramicDBBase
from packages.valory.skills.olas_week_abci.behaviours import (
    OlasWeekBaseBehaviour,
    OlasWeekDecisionMakingBehaviour,
    OlasWeekEvaluationBehaviour,
    OlasWeekOpenAICallCheckBehaviour,
    OlasWeekRandomnessBehaviour,
    OlasWeekRoundBehaviour,
    OlasWeekSelectKeepersBehaviour,
    OlasWeekTweetCollectionBehaviour,
)
from packages.valory.skills.olas_week_abci.models import SharedState
from packages.valory.skills.olas_week_abci.rounds import (
    Event,
    FinishedWeekInOlasRound,
    SynchronizedData,
)


PACKAGE_DIR = Path(__file__).parent.parent

TWEETS_URL = "https://api.twitter.com/2/users/1450081635559428107/tweets?tweet.fields=author_id,created_at,conversation_id&user.fields=name&expansions=author_id&max_results=50&start_time={start_time}"


DUMMY_TWEETS_RESPONSE = {
    "data": [
        {
            "author_id": "1286010187325812739",
            "text": "tweet_text_1",
            "id": "1",
            "created_at": "2023-06-01T12:00:00Z",
            "conversation_id": "1001",
        },
        {
            "author_id": "1286010187325812739",
            "text": "tweet_text_2",
            "id": "2",
            "created_at": "2023-06-01T12:05:00Z",
            "conversation_id": "1002",
        },
        {
            "author_id": "1286010187325812738",
            "text": "tweet_text_3",
            "id": "3",
            "created_at": "2023-06-01T12:10:00Z",
            "conversation_id": "1003",
        },
        {
            "author_id": "1286010187325812737",
            "text": "tweet_text_4",
            "id": "4",
            "created_at": "2023-06-01T12:15:00Z",
            "conversation_id": "1004",
        },
    ],
    "includes": {
        "users": [
            {"id": "1286010187325812739", "username": "username_a"},
            {"id": "1286010187325812739", "username": "username_b"},
            {"id": "1286010187325812738", "username": "username_c"},
            {"id": "1286010187325812737", "username": "username_d"},
        ]
    },
    "meta": {"result_count": 4, "newest_id": "4", "oldest_id": "1"},
}

DUMMY_TWEETS_RESPONSE_COUNT_ZERO = {
    "data": [],
    "includes": {
        "users": [
            {"id": "1286010187325812739", "username": "username_a"},
            {"id": "1286010187325812739", "username": "username_b"},
            {"id": "1286010187325812738", "username": "username_c"},
            {"id": "1286010187325812737", "username": "username_d"},
        ]
    },
    "meta": {"result_count": 0},
}

DUMMY_TWEETS_RESPONSE_MISSING_DATA = {
    "meta": {"result_count": 4, "newest_id": "4", "oldest_id": "1"},
}

DUMMY_TWEETS_RESPONSE_MISSING_INCLUDES = {
    "data": [
        {
            "author_id": "1286010187325812739",
            "text": "tweet_text_1",
            "id": "1",
            "created_at": "2023-06-01T12:00:00Z",
            "conversation_id": "1001",
        },
        {
            "author_id": "1286010187325812739",
            "text": "tweet_text_2",
            "id": "2",
            "created_at": "2023-06-01T12:05:00Z",
            "conversation_id": "1002",
        },
        {
            "author_id": "1286010187325812738",
            "text": "tweet_text_3",
            "id": "3",
            "created_at": "2023-06-01T12:10:00Z",
            "conversation_id": "1003",
        },
        {
            "author_id": "1286010187325812737",
            "text": "tweet_text_4",
            "id": "4",
            "created_at": "2023-06-01T12:15:00Z",
            "conversation_id": "1004",
        },
    ],
    "meta": {"result_count": 4, "newest_id": "4", "oldest_id": "1"},
}

DUMMY_TWEETS_RESPONSE_MISSING_META = {}

DUMMY_TWEETS_RESPONSE_MULTIPAGE = {
    "data": [
        {
            "author_id": "1286010187325812739",
            "text": "tweet_text_1",
            "id": "1",
            "created_at": "2023-06-01T12:00:00Z",
            "conversation_id": "1001",
        },
        {
            "author_id": "1286010187325812739",
            "text": "tweet_text_2",
            "id": "2",
            "created_at": "2023-06-01T12:05:00Z",
            "conversation_id": "1002",
        },
        {
            "author_id": "1286010187325812738",
            "text": "tweet_text_3",
            "id": "3",
            "created_at": "2023-06-01T12:10:00Z",
            "conversation_id": "1003",
        },
        {
            "author_id": "1286010187325812737",
            "text": "tweet_text_4",
            "id": "4",
            "created_at": "2023-06-01T12:15:00Z",
            "conversation_id": "1004",
        },
    ],
    "includes": {
        "users": [
            {"id": "1286010187325812739", "username": "username_a"},
            {"id": "1286010187325812739", "username": "username_b"},
            {"id": "1286010187325812738", "username": "username_c"},
            {"id": "1286010187325812737", "username": "username_d"},
        ]
    },
    "meta": {
        "result_count": 4,
        "newest_id": "4",
        "oldest_id": "1",
        "next_token": "dummy_next_token",
    },
}

DUMMY_WEEKLY_TWEETS = [
    {
        "author_id": "1286010187325812739",
        "text": "tweet_text_1",
        "id": "1",
        "created_at": "2023-06-01T12:00:00Z",
        "conversation_id": "1",
    },
    {
        "author_id": "1286010187325812739",
        "text": "tweet_text_2",
        "id": "2",
        "created_at": "2023-06-01T12:05:00Z",
        "conversation_id": "2",
    },
    {
        "author_id": "1286010187325812738",
        "text": "tweet_text_3",
        "id": "3",
        "created_at": "2023-06-01T12:10:00Z",
        "conversation_id": "3",
    },
    {
        "author_id": "1286010187325812737",
        "text": "tweet_text_4",
        "id": "4",
        "created_at": "2023-06-01T12:15:00Z",
        "conversation_id": "4",
    },
]


@dataclass
class BehaviourTestCase:
    """BehaviourTestCase"""

    name: str
    initial_data: Dict[str, Any]
    event: Event
    next_behaviour_class: Optional[Type[OlasWeekBaseBehaviour]] = None
    ceramic_db: Optional[Any] = None


class BaseBehaviourTest(FSMBehaviourBaseCase):
    """Base test case."""

    path_to_skill = Path(__file__).parent.parent

    behaviour: OlasWeekRoundBehaviour
    behaviour_class: Type[OlasWeekBaseBehaviour]
    next_behaviour_class: Type[OlasWeekBaseBehaviour]
    synchronized_data: SynchronizedData
    done_event = Event.DONE

    @classmethod
    def setup_class(cls, **kwargs: Any) -> None:
        """Setup class"""
        super().setup_class(
            param_overrides={
                "twitter_max_pages": 10,
            }
        )
        cls.llm_handler = cls._skill.skill_context.handlers.llm

    def fast_forward(
        self,
        data: Optional[Dict[str, Any]] = None,
        ceramic_db: Optional[Any] = None,
        openai_calls: Optional[Any] = None,
    ) -> None:
        """Fast-forward on initialization"""

        data = data if data is not None else {}
        self.fast_forward_to_behaviour(
            self.behaviour,  # type: ignore
            self.behaviour_class.auto_behaviour_id(),
            SynchronizedData(AbciAppDB(setup_data=AbciAppDB.data_to_lists(data))),
        )
        self.skill.skill_context.state.round_sequence._last_round_transition_timestamp = (
            datetime.now()
        )
        if ceramic_db:
            self.skill.skill_context.ceramic_db = ceramic_db

        assert (
            self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
            == self.behaviour_class.auto_behaviour_id()
        )

    def complete(self, event: Event) -> None:
        """Complete test"""
        print(1)
        self.behaviour.act_wrapper()
        print(2)
        self.mock_a2a_transaction()
        print(3)
        self._test_done_flag_set()
        self.end_round(done_event=event)

        print(
            f"CURRENT BEHAVIOUR: {self.behaviour.current_behaviour.auto_behaviour_id()}"
        )
        print(f"BEHAVIOUR CLASS: {self.behaviour_class.auto_behaviour_id()}")
        assert (
            self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
            == self.next_behaviour_class.auto_behaviour_id()
        )


class TestOlasWeekOpenAICallCheckBehaviour(BaseBehaviourTest):
    """Tests OlasWeekOpenAICallCheckBehaviour"""

    behaviour_class = OlasWeekOpenAICallCheckBehaviour
    next_behaviour_class = OlasWeekDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(),
                    event=Event.DONE,
                ),
                {"max_calls_reached": False},
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(),
                    event=Event.DONE,
                ),
                {"max_calls_reached": True},
            ),
        ],
    )
    def test_run(
        self,
        test_case: BehaviourTestCase,
        kwargs: Any,
    ) -> None:
        """Run tests."""

        with patch(
            "packages.valory.skills.olas_week_abci.models.OpenAICalls"
        ) as MockOpenAICalls:
            openai_calls = MockOpenAICalls()
            openai_calls.max_calls_reached.return_value = kwargs.get(
                "max_calls_reached"
            )
            params = cast(SharedState, self._skill.skill_context.params)
            params.__dict__["_frozen"] = False
            params.openai_calls = openai_calls
            self.fast_forward(test_case.initial_data)
            self.behaviour.act_wrapper()
            self.complete(test_case.event)


class TestTweetCollectionBehaviour(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = OlasWeekTweetCollectionBehaviour
    next_behaviour_class = OlasWeekDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWEETS_URL,
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                    ],
                    "response_urls": [
                        "",
                    ],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_TWEETS_RESPONSE,
                        ),
                    ],
                    "status_code": 200,
                },
            ),
            (
                BehaviourTestCase(
                    "Happy path, multi-page",
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWEETS_URL,
                        TWEETS_URL + "&pagination_token=dummy_next_token",
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                        "Authorization: Bearer <default_bearer_token>\r\n",
                    ],
                    "response_urls": ["", ""],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_TWEETS_RESPONSE_MULTIPAGE,
                        ),
                        json.dumps(
                            DUMMY_TWEETS_RESPONSE,
                        ),
                    ],
                    "status_code": 200,
                },
            ),
            (
                BehaviourTestCase(
                    "Happy path, result_count=0",
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWEETS_URL,
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                    ],
                    "response_urls": [""],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_TWEETS_RESPONSE_COUNT_ZERO,
                        ),
                    ],
                    "status_code": 200,
                },
            ),
        ],
    )
    def test_run(
        self,
        test_case: BehaviourTestCase,
        kwargs: Any,
    ) -> None:
        """Run tests."""

        self.fast_forward(test_case.initial_data)
        now_ts = (
            self.skill.skill_context.state.round_sequence._last_round_transition_timestamp
        )
        start_time = (
            datetime.fromtimestamp(now_ts.timestamp()) - timedelta(days=7)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.behaviour.act_wrapper()
        for i in range(len(kwargs.get("request_urls"))):
            self.mock_http_request(
                request_kwargs=dict(
                    method="GET",
                    headers=kwargs.get("request_headers")[i],
                    version="",
                    url=kwargs.get("request_urls")[i].format(start_time=start_time),
                ),
                response_kwargs=dict(
                    version="",
                    status_code=kwargs.get("status_code"),
                    status_text="",
                    body=kwargs.get("response_bodies")[i].encode(),
                    url=kwargs.get("response_urls")[i],
                ),
            )
        self.complete(test_case.event)


class TestTweetCollectionBehaviourSerial(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = OlasWeekTweetCollectionBehaviour
    next_behaviour_class = OlasWeekDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API daily limit reached",
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
                    event=Event.DONE,
                    ceramic_db={
                        "module_data": {
                            "twitter": {
                                "number_of_tweets_pulled_today": 10000,
                                "last_tweet_pull_window_reset": 1993903085,
                            }
                        }
                    },
                ),
                {
                    "request_urls": [],
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        ceramic_db = None
        if test_case.ceramic_db:
            ceramic_db = CeramicDBBase()
            ceramic_db.load(test_case.ceramic_db)
        self.fast_forward(test_case.initial_data, ceramic_db)
        self.behaviour.act_wrapper()
        for i in range(len(kwargs.get("request_urls"))):
            self.mock_http_request(
                request_kwargs=dict(
                    method="GET",
                    headers=kwargs.get("request_headers")[i],
                    version="",
                    url=kwargs.get("request_urls")[i],
                ),
                response_kwargs=dict(
                    version="",
                    status_code=kwargs.get("status_code"),
                    status_text="",
                    body=kwargs.get("response_bodies")[i].encode(),
                    url=kwargs.get("response_urls")[i],
                ),
            )
        self.complete(test_case.event)


class TestTweetsCollectionBehaviourAPIError(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = OlasWeekTweetCollectionBehaviour
    next_behaviour_class = OlasWeekTweetCollectionBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API error mentions: 404",
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWEETS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_TWEETS_RESPONSE,
                        ),
                        json.dumps(DUMMY_TWEETS_RESPONSE),
                    ],
                    "headers": [""],
                    "status_codes": [404],
                },
            ),
            (
                BehaviourTestCase(
                    "API error mentions: missing data",
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWEETS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_TWEETS_RESPONSE_MISSING_DATA,
                        ),
                        json.dumps(DUMMY_TWEETS_RESPONSE),
                    ],
                    "status_codes": [200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error mentions: missing meta",
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWEETS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_TWEETS_RESPONSE_MISSING_META,
                        ),
                        json.dumps(DUMMY_TWEETS_RESPONSE),
                    ],
                    "status_codes": [200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error mentions: missing includes",
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWEETS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_TWEETS_RESPONSE_MISSING_INCLUDES,
                        ),
                        json.dumps({}),
                    ],
                    "status_codes": [200],
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        now_ts = (
            self.skill.skill_context.state.round_sequence._last_round_transition_timestamp
        )
        start_time = (
            datetime.fromtimestamp(now_ts.timestamp()) - timedelta(days=7)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.behaviour.act_wrapper()
        for i in range(len(kwargs.get("urls"))):
            self.mock_http_request(
                request_kwargs=dict(
                    method="GET",
                    headers="Authorization: Bearer <default_bearer_token>\r\n",
                    version="",
                    url=kwargs.get("urls")[i].format(start_time=start_time),
                ),
                response_kwargs=dict(
                    version="",
                    status_code=kwargs.get("status_codes")[i],
                    status_text="",
                    body=kwargs.get("bodies")[i].encode(),
                    headers=kwargs.get("headers", [""])[i],
                ),
            )
        self.complete(test_case.event)


class TestOlasWeekDecisionMakingBehaviour(BaseBehaviourTest):
    """Tests OlasWeekDecisionMakingBehaviour"""

    behaviour_class = OlasWeekDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case, next_behaviour",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(performed_olas_week_tasks={}),
                    event=Event.OPENAI_CALL_CHECK,
                ),
                OlasWeekOpenAICallCheckBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_olas_week_tasks={"openai_call_check": "no_allowance"}
                    ),
                    event=Event.DONE_SKIP,
                ),
                make_degenerate_behaviour(FinishedWeekInOlasRound),
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_olas_week_tasks={"openai_call_check": None}
                    ),
                    event=Event.SELECT_KEEPERS,
                ),
                OlasWeekRandomnessBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_olas_week_tasks={
                            "openai_call_check": None,
                            "select_keepers": None,
                        }
                    ),
                    event=Event.RETRIEVE_TWEETS,
                ),
                OlasWeekTweetCollectionBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_olas_week_tasks={
                            "openai_call_check": None,
                            "select_keepers": None,
                            "retrieve_tweets": "done_max_retries",
                        }
                    ),
                    event=Event.DONE_SKIP,
                ),
                make_degenerate_behaviour(FinishedWeekInOlasRound),
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_olas_week_tasks={
                            "openai_call_check": None,
                            "select_keepers": None,
                            "retrieve_tweets": None,
                        }
                    ),
                    event=Event.EVALUATE,
                ),
                OlasWeekEvaluationBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_olas_week_tasks={
                            "openai_call_check": None,
                            "select_keepers": None,
                            "retrieve_tweets": None,
                            "evaluate": None,
                        }
                    ),
                    event=Event.DONE,
                ),
                make_degenerate_behaviour(FinishedWeekInOlasRound),
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, next_behaviour) -> None:
        """Run tests."""
        self.next_behaviour_class = next_behaviour
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.complete(test_case.event)


class TestRandomnessBehaviour(BaseRandomnessBehaviourTest):
    """Test randomness in operation."""

    path_to_skill = PACKAGE_DIR

    randomness_behaviour_class = OlasWeekRandomnessBehaviour
    next_behaviour_class = OlasWeekSelectKeepersBehaviour
    done_event = Event.DONE


class TestOlasWeekSelectKeepersBehaviour(BaseBehaviourTest):
    """Test SelectKeepersBehaviour."""

    select_keeper_behaviour_class: Type[BaseBehaviour]
    next_behaviour_class: Type[BaseBehaviour]

    @pytest.mark.parametrize(
        "test_case",
        [
            BehaviourTestCase(
                name="Happy path",
                initial_data={"blacklisted_keepers": []},
                event=Event.DONE,
            ),
            BehaviourTestCase(
                name="Happy path",
                initial_data={"blacklisted_keepers": ["a_1"]},
                event=Event.DONE,
            ),
        ],
    )
    def test_select_keeper(self, test_case) -> None:
        """Test select keeper agent."""
        self.select_keeper_behaviour_class = OlasWeekSelectKeepersBehaviour
        self.next_behaviour_class = OlasWeekDecisionMakingBehaviour
        participants = [self.skill.skill_context.agent_address, "a_1", "a_2"]
        self.fast_forward_to_behaviour(
            behaviour=self.behaviour,
            behaviour_id=self.select_keeper_behaviour_class.auto_behaviour_id(),
            synchronized_data=SynchronizedData(
                AbciAppDB(
                    setup_data=dict(
                        participants=[participants],
                        most_voted_randomness=[
                            "56cbde9e9bbcbdcaf92f183c678eaa5288581f06b1c9c7f884ce911776727688"
                        ],
                        most_voted_keeper_addresses=[["a_1", "a_2"]],
                        blacklisted_keepers=test_case.initial_data[
                            "blacklisted_keepers"
                        ],
                    ),
                )
            ),
        )
        assert (
            cast(
                BaseBehaviour,
                cast(BaseBehaviour, self.behaviour.current_behaviour),
            ).behaviour_id
            == self.select_keeper_behaviour_class.auto_behaviour_id()
        )
        self.behaviour.act_wrapper()
        self.mock_a2a_transaction()
        self._test_done_flag_set()
        self.end_round(done_event=test_case.event)
        behaviour = cast(BaseBehaviour, self.behaviour.current_behaviour)
        assert behaviour.behaviour_id == self.next_behaviour_class.auto_behaviour_id()

    def test_select_keeper_blacklisted(self) -> None:
        """Test select keeper agent when all agents are blacklisted."""
        self.select_keeper_behaviour_class = OlasWeekSelectKeepersBehaviour
        self.next_behaviour_class = OlasWeekDecisionMakingBehaviour
        participants = [
            self.skill.skill_context.agent_address,
            "a_0123456789012345678901234567890123456789",
            "a_1234567890123456789012345678901234567890",
        ]

        self.fast_forward_to_behaviour(
            behaviour=self.behaviour,
            behaviour_id=self.select_keeper_behaviour_class.auto_behaviour_id(),
            synchronized_data=SynchronizedData(
                AbciAppDB(
                    setup_data=dict(
                        participants=[participants],
                        most_voted_randomness=[
                            "56cbde9e9bbcbdcaf92f183c678eaa5288581f06b1c9c7f884ce911776727688"
                        ],
                        most_voted_keeper_addresses=[["a_1", "a_2"]],
                        blacklisted_keepers=[
                            "a_0123456789012345678901234567890123456789a_1234567890123456789012345678901234567890test_agent_address"
                        ],
                    ),
                )
            ),
        )
        assert (
            cast(
                BaseBehaviour,
                cast(BaseBehaviour, self.behaviour.current_behaviour),
            ).behaviour_id
            == self.select_keeper_behaviour_class.auto_behaviour_id()
        )
        with pytest.raises(AEAActException) as excinfo:
            self.behaviour.act_wrapper()

        exception_message = "Cannot continue if all the keepers have been blacklisted!"
        assert exception_message in str(excinfo.value)
