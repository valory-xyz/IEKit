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

"""This package contains round behaviours of TwitterScoringAbciApp."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Type

import pytest

from packages.valory.connections.openai.connection import (
    PUBLIC_ID as LLM_CONNECTION_PUBLIC_ID,
)
from packages.valory.protocols.llm.message import LlmMessage
from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.abstract_round_abci.behaviour_utils import (
    make_degenerate_behaviour,
)
from packages.valory.skills.abstract_round_abci.test_tools.base import (
    FSMBehaviourBaseCase,
)
from packages.valory.skills.twitter_scoring_abci.behaviours import (
    DBUpdateBehaviour,
    OpenAICallCheckBehaviour,
    TAGLINE,
    TweetEvaluationBehaviour,
    TwitterDecisionMakingBehaviour,
    TwitterHashtagsCollectionBehaviour,
    TwitterMentionsCollectionBehaviour,
    TwitterScoringBaseBehaviour,
    TwitterScoringRoundBehaviour,
)
from packages.valory.skills.twitter_scoring_abci.rounds import (
    Event,
    FinishedTwitterScoringRound,
    SynchronizedData,
)


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

TWITTER_MENTIONS_URL = "https://api.twitter.com/2/users/1450081635559428107/mentions?tweet.fields=author_id&user.fields=name&expansions=author_id&max_results={max_results}&since_id=0"
TWITTER_REGISTRATIONS_URL = "https://api.twitter.com/2/tweets/search/recent?query=%23olas&tweet.fields=author_id,created_at&user.fields=name&expansions=author_id&max_results={max_results}&since_id=0"

DUMMY_MENTIONS_RESPONSE = {
    "data": [
        {"author_id": "1286010187325812739", "text": "dummy_text", "id": "1"},
        {"author_id": "1286010187325812739", "text": "dummy_text", "id": "2"},
        {"author_id": "1286010187325812738", "text": "dummy_text", "id": "3"},
        {"author_id": "1286010187325812737", "text": "dummy_text", "id": "4"},
    ],
    "includes": {
        "users": [
            {"id": "1286010187325812739", "username": "username_a"},
            {"id": "1286010187325812739", "username": "username_b"},
            {"id": "1286010187325812738", "username": "username_c"},
            {"id": "1286010187325812737", "username": "username_d"},
        ]
    },
    "meta": {"result_count": 4, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_MENTIONS_RESPONSE_COUNT_ZERO = {
    "data": [
        {"author_id": "1286010187325812739", "text": "dummy_text", "id": "1"},
        {"author_id": "1286010187325812739", "text": "dummy_text", "id": "2"},
        {"author_id": "1286010187325812738", "text": "dummy_text", "id": "3"},
        {"author_id": "1286010187325812737", "text": "dummy_text", "id": "4"},
    ],
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

DUMMY_MENTIONS_RESPONSE_MISSING_DATA = {
    "meta": {"result_count": 4, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_MENTIONS_RESPONSE_MISSING_INCLUDES = {
    "data": [
        {"author_id": "1286010187325812739", "text": "dummy_text", "id": "1"},
        {"author_id": "1286010187325812739", "text": "dummy_text", "id": "2"},
        {"author_id": "1286010187325812738", "text": "dummy_text", "id": "3"},
        {"author_id": "1286010187325812737", "text": "dummy_text", "id": "4"},
    ],
    "meta": {"result_count": 4, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_MENTIONS_RESPONSE_MISSING_META = {}

DUMMY_MENTIONS_RESPONSE_MULTIPAGE = {
    "data": [
        {"author_id": "1286010187325812739", "text": "dummy_text", "id": "1"},
        {"author_id": "1286010187325812739", "text": "dummy_text", "id": "2"},
        {"author_id": "1286010187325812738", "text": "dummy_text", "id": "3"},
        {"author_id": "1286010187325812737", "text": "dummy_text", "id": "4"},
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
        "newest_id": "1",
        "oldest_id": "0",
        "next_token": "dummy_next_token",
    },
}

DUMMY_MOST_VOTED_MENTIONS_DATA = {
    "user_to_mentions": {
        "1286010187325812739": 2,
        "1286010187325812738": 1,
        "1286010187325812737": 1,
    },
    "id_to_usernames": {
        "1286010187325812739": "username_1",
        "1286010187325812738": "username_2",
        "1286010187325812737": "username_3",
    },
    "latest_mention_tweet_id": DUMMY_MENTIONS_RESPONSE["meta"]["newest_id"],
}

DUMMY_REGISTRATIONS_RESPONSE = {
    "data": [
        {
            "author_id": "1286010187325812739",
            "text": f"{TAGLINE} {ZERO_ADDRESS}",
            "id": "10",
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
    "meta": {"result_count": 1, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_REGISTRATIONS_RESPONSE_MULTIPAGE = {
    "data": [
        {
            "author_id": "1286010187325812739",
            "text": f"dummy_text #olas {ZERO_ADDRESS}",
            "id": "10",
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
        "result_count": 1,
        "newest_id": "1",
        "oldest_id": "0",
        "next_token": "dummy_next_token",
    },
}

DUMMY_REGISTRATIONS_RESPONSE_MULTIPAGE_2 = {
    "data": [
        {
            "author_id": "1286010187325812739",
            "text": f"{TAGLINE} {ZERO_ADDRESS}",
            "id": "10",
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
    "meta": {"result_count": 1, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_REGISTRATIONS_RESPONSE_COUNT_ZERO = {
    "data": [
        {
            "author_id": "1286010187325812739",
            "text": f"dummy_text #olas {ZERO_ADDRESS}",
            "id": "10",
        },
    ],
    "meta": {"result_count": 0, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_REGISTRATIONS_RESPONSE_MISSING_META = {
    "data": [
        {
            "author_id": "1286010187325812739",
            "text": f"dummy_text #olas {ZERO_ADDRESS}",
            "id": "10",
        },
    ]
}

DUMMY_REGISTRATIONS_RESPONSE_MISSING_DATA = {
    "meta": {"result_count": 1, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_REGISTRATIONS_RESPONSE_MISSING_INCLUDES = {
    "data": [
        {
            "author_id": "1286010187325812739",
            "text": f"{TAGLINE} {ZERO_ADDRESS}",
            "id": "10",
        },
    ],
    "meta": {"result_count": 1, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_HASHTAGS_RESPONSE = {
    "data": [
        {"author_id": "1286010187325812739", "text": "dummy_text", "id": "1"},
        {"author_id": "1286010187325812739", "text": "dummy_text", "id": "2"},
        {"author_id": "1286010187325812738", "text": "dummy_text", "id": "3"},
        {"author_id": "1286010187325812737", "text": "dummy_text", "id": "4"},
    ],
    "includes": {
        "users": [
            {"id": "1286010187325812739", "username": "username_a"},
            {"id": "1286010187325812739", "username": "username_b"},
            {"id": "1286010187325812738", "username": "username_c"},
            {"id": "1286010187325812737", "username": "username_d"},
        ]
    },
    "meta": {"result_count": 4, "newest_id": "1", "oldest_id": "0"},
}


@dataclass
class BehaviourTestCase:
    """BehaviourTestCase"""

    name: str
    initial_data: Dict[str, Any]
    event: Event
    next_behaviour_class: Optional[Type[TwitterScoringBaseBehaviour]] = None


class BaseBehaviourTest(FSMBehaviourBaseCase):
    """Base test case."""

    path_to_skill = Path(__file__).parent.parent

    behaviour: TwitterScoringRoundBehaviour
    behaviour_class: Type[TwitterScoringBaseBehaviour]
    next_behaviour_class: Type[TwitterScoringBaseBehaviour]
    synchronized_data: SynchronizedData
    done_event = Event.DONE

    @classmethod
    def setup_class(cls, **kwargs: Any) -> None:
        """Setup class"""
        super().setup_class(param_overrides={"twitter_max_pages": 10})
        cls.llm_handler = cls._skill.skill_context.handlers.llm

    def fast_forward(self, data: Optional[Dict[str, Any]] = None) -> None:
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

    def mock_llm_request(self, request_kwargs: Dict, response_kwargs: Dict) -> None:
        """
        Mock LLM request.

        :param request_kwargs: keyword arguments for request check.
        :param response_kwargs: keyword arguments for mock response.
        """

        self.assert_quantity_in_outbox(1)
        actual_llm_message = self.get_message_from_outbox()
        assert actual_llm_message is not None, "No message in outbox."  # nosec
        has_attributes, error_str = self.message_has_attributes(
            actual_message=actual_llm_message,
            message_type=LlmMessage,
            to=str(LLM_CONNECTION_PUBLIC_ID),
            sender=str(self.skill.skill_context.skill_id),
            **request_kwargs,
        )

        assert has_attributes, error_str  # nosec
        incoming_message = self.build_incoming_message(
            message_type=LlmMessage,
            dialogue_reference=(
                actual_llm_message.dialogue_reference[0],
                "stub",
            ),
            target=actual_llm_message.message_id,
            message_id=-1,
            to=str(self.skill.skill_context.skill_id),
            sender=str(LLM_CONNECTION_PUBLIC_ID),
            **response_kwargs,
        )
        self.llm_handler.handle(incoming_message)
        self.behaviour.act_wrapper()


class TestMentionsCollectionBehaviour(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterMentionsCollectionBehaviour
    next_behaviour_class = TwitterDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(ceramic_db={}),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWITTER_MENTIONS_URL.format(max_results=80),
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                    ],
                    "response_urls": [
                        "",
                    ],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE,
                        ),
                    ],
                    "status_code": 200,
                },
            ),
            (
                BehaviourTestCase(
                    "Happy path, multi-page",
                    initial_data=dict(ceramic_db={}),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWITTER_MENTIONS_URL.format(max_results=80),
                        TWITTER_MENTIONS_URL.format(max_results=80)
                        + "&pagination_token=dummy_next_token",
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                        "Authorization: Bearer <default_bearer_token>\r\n",
                    ],
                    "response_urls": ["", ""],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_MULTIPAGE,
                        ),
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE,
                        ),
                    ],
                    "status_code": 200,
                },
            ),
            (
                BehaviourTestCase(
                    "Happy path, result_count=0",
                    initial_data=dict(ceramic_db={}),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWITTER_MENTIONS_URL.format(max_results=80),
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                    ],
                    "response_urls": [""],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_COUNT_ZERO,
                        ),
                    ],
                    "status_code": 200,
                },
            ),
            (
                BehaviourTestCase(
                    "API daily limit reached",
                    initial_data=dict(
                        ceramic_db={
                            "module_data": {
                                "twitter": {
                                    "number_of_tweets_pulled_today": 10000,
                                    "last_tweet_pull_window_reset": 1993903085,
                                }
                            }
                        }
                    ),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [],
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
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


class TestHashtagsCollectionBehaviour(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterHashtagsCollectionBehaviour
    next_behaviour_class = TwitterDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(ceramic_db={}),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWITTER_REGISTRATIONS_URL.format(max_results=80),
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                        "",
                    ],
                    "response_urls": [
                        "",
                    ],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_REGISTRATIONS_RESPONSE,
                        ),
                    ],
                    "status_code": 200,
                },
            ),
            (
                BehaviourTestCase(
                    "Happy path, multi-page",
                    initial_data=dict(ceramic_db={}),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWITTER_REGISTRATIONS_URL.format(max_results=80),
                        TWITTER_REGISTRATIONS_URL.format(max_results=80)
                        + "&pagination_token=dummy_next_token",
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                        "Authorization: Bearer <default_bearer_token>\r\n",
                    ],
                    "response_urls": ["", ""],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_REGISTRATIONS_RESPONSE_MULTIPAGE,
                        ),
                        json.dumps(
                            DUMMY_REGISTRATIONS_RESPONSE_MULTIPAGE_2,
                        ),
                    ],
                    "status_code": 200,
                },
            ),
            (
                BehaviourTestCase(
                    "Happy path, result_count=0",
                    initial_data=dict(ceramic_db={}),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWITTER_REGISTRATIONS_URL.format(max_results=80),
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                    ],
                    "response_urls": ["", ""],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_REGISTRATIONS_RESPONSE_COUNT_ZERO,
                        ),
                    ],
                    "status_code": 200,
                },
            ),
            (
                BehaviourTestCase(
                    "API daily limit reached",
                    initial_data=dict(
                        ceramic_db={
                            "module_data": {
                                "twitter": {
                                    "number_of_tweets_pulled_today": 10000,
                                    "last_tweet_pull_window_reset": 1993903085,
                                }
                            }
                        }
                    ),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [],
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
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


class TestMentionsCollectionBehaviourAPIError(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterMentionsCollectionBehaviour
    next_behaviour_class = TwitterMentionsCollectionBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API error mentions: 404",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL.format(max_results=80)],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE,
                        ),
                        json.dumps(DUMMY_HASHTAGS_RESPONSE),
                    ],
                    "status_codes": [404],
                },
            ),
            (
                BehaviourTestCase(
                    "API error mentions: missing data",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL.format(max_results=80)],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_MISSING_DATA,
                        ),
                        json.dumps(DUMMY_HASHTAGS_RESPONSE),
                    ],
                    "status_codes": [200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error mentions: missing meta",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL.format(max_results=80)],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_MISSING_META,
                        ),
                        json.dumps(DUMMY_HASHTAGS_RESPONSE),
                    ],
                    "status_codes": [200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error mentions: missing includes",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL.format(max_results=80)],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_MISSING_INCLUDES,
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
        self.behaviour.act_wrapper()
        for i in range(len(kwargs.get("urls"))):
            self.mock_http_request(
                request_kwargs=dict(
                    method="GET",
                    headers="Authorization: Bearer <default_bearer_token>\r\n",
                    version="",
                    url=kwargs.get("urls")[i],
                ),
                response_kwargs=dict(
                    version="",
                    status_code=kwargs.get("status_codes")[i],
                    status_text="",
                    body=kwargs.get("bodies")[i].encode(),
                ),
            )
        self.complete(test_case.event)


class TestHashtagsCollectionBehaviourAPIError(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterHashtagsCollectionBehaviour
    next_behaviour_class = TwitterHashtagsCollectionBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API error registrations: 404",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [
                        TWITTER_REGISTRATIONS_URL.format(max_results=80),
                    ],
                    "bodies": [
                        json.dumps(DUMMY_HASHTAGS_RESPONSE),
                    ],
                    "status_codes": [404],
                },
            ),
            (
                BehaviourTestCase(
                    "API error registrations: missing data",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [
                        TWITTER_REGISTRATIONS_URL.format(max_results=80),
                    ],
                    "bodies": [
                        json.dumps(
                            DUMMY_REGISTRATIONS_RESPONSE_MISSING_DATA,
                        ),
                    ],
                    "status_codes": [200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error registrations: missing meta",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [
                        TWITTER_REGISTRATIONS_URL.format(max_results=80),
                    ],
                    "bodies": [
                        json.dumps(DUMMY_REGISTRATIONS_RESPONSE_MISSING_META),
                    ],
                    "status_codes": [200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error mentions: missing includes",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_REGISTRATIONS_URL.format(max_results=80)],
                    "bodies": [
                        json.dumps(
                            DUMMY_REGISTRATIONS_RESPONSE_MISSING_INCLUDES,
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
        self.behaviour.act_wrapper()
        for i in range(len(kwargs.get("urls"))):
            self.mock_http_request(
                request_kwargs=dict(
                    method="GET",
                    headers="Authorization: Bearer <default_bearer_token>\r\n",
                    version="",
                    url=kwargs.get("urls")[i],
                ),
                response_kwargs=dict(
                    version="",
                    status_code=kwargs.get("status_codes")[i],
                    status_text="",
                    body=kwargs.get("bodies")[i].encode(),
                ),
            )
        self.complete(test_case.event)


class TestTwitterDecisionMakingBehaviour(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case, next_behaviour",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(performed_twitter_tasks={}),
                    event=Event.OPENAI_CALL_CHECK,
                ),
                OpenAICallCheckBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={"openai_call_check": "done"}
                    ),
                    event=Event.RETRIEVE_MENTIONS,
                ),
                TwitterMentionsCollectionBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={"openai_call_check": "no_allowance"}
                    ),
                    event=Event.DONE_SKIP,
                ),
                make_degenerate_behaviour(FinishedTwitterScoringRound),
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={
                            "openai_call_check": "done",
                            "retrieve_hashtags": None,
                        }
                    ),
                    event=Event.RETRIEVE_HASHTAGS,
                ),
                TwitterHashtagsCollectionBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={
                            "openai_call_check": "done",
                            "retrieve_hashtags": None,
                            "retrieve_mentions": None,
                        }
                    ),
                    event=Event.EVALUATE,
                ),
                TweetEvaluationBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={
                            "openai_call_check": "done",
                            "retrieve_hashtags": None,
                            "retrieve_mentions": None,
                            "evaluate": None,
                        }
                    ),
                    event=Event.DB_UPDATE,
                ),
                DBUpdateBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={
                            "openai_call_check": "done",
                            "retrieve_hashtags": None,
                            "retrieve_mentions": None,
                            "evaluate": None,
                            "db_update": None,
                        }
                    ),
                    event=Event.DB_UPDATE,
                ),
                DBUpdateBehaviour,
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, next_behaviour) -> None:
        """Run tests."""
        self.next_behaviour_class = next_behaviour
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.complete(test_case.event)


class TestOpenAICallCheckBehaviour(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = OpenAICallCheckBehaviour
    next_behaviour_class = TwitterDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case",
        (
            BehaviourTestCase(
                "Happy path",
                initial_data=dict(performed_twitter_tasks={}),
                event=Event.DONE,
            ),
        ),
    )
    def test_run(self, test_case: BehaviourTestCase) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.complete(test_case.event)


class TestTweetEvaluationBehaviour(BaseBehaviourTest):
    """Tests TweetEvaluationBehaviour"""

    behaviour_class = TweetEvaluationBehaviour
    next_behaviour_class = TwitterDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(tweets={"1": {"text": "dummy text"}}),
                    event=Event.DONE,
                ),
                {},
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.mock_llm_request(
            request_kwargs=dict(performative=LlmMessage.Performative.REQUEST),
            response_kwargs=dict(
                performative=LlmMessage.Performative.RESPONSE,
                value='{"quality":"HIGH","relationship":"HIGH"}',
            ),
        )
        self.complete(test_case.event)


class TestDBUpdateBehaviour(BaseBehaviourTest):
    """Tests DBUpdateBehaviour"""

    behaviour_class = DBUpdateBehaviour
    next_behaviour_class = TwitterDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        tweets={
                            "1": {
                                "author_id": "1",
                                "points": 900,
                                "username": "dummy",
                                "text": "dummy text",
                            },
                            "2": {
                                "author_id": "2",
                                "points": 900,
                                "username": "dummy_2",
                                "text": "dummy text",
                            },
                            "3": {
                                "author_id": "3",
                                "points": 900,
                                "username": "dummy_3",
                                "text": "I'm linking my wallet to @Autonolas Contribute: 0x0000000000000000000000000000000000000000",
                            },
                            "4": {
                                "author_id": "1",
                                "points": 10000,  # too many points during this period
                                "username": "dummy",
                                "text": "dummy text",
                            },
                        },
                        latest_mention_tweet_id=1,
                        latest_hashtag_tweet_id=1,
                        number_of_tweets_pulled_today=1,
                        last_tweet_pull_window_reset=1993903085,  # in 10 years
                        ceramic_db={
                            "users": [
                                {"twitter_id": "1", "points": 0, "wallet_address": None}
                            ],
                            "module_data": {
                                "twitter": {"current_period": "2023-09-04"}
                            },
                        },
                    ),
                    event=Event.DONE,
                ),
                {},
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.complete(test_case.event)
