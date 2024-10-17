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

"""This package contains round behaviours of TwitterScoringAbciApp."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Type, cast

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
from packages.valory.skills.decision_making_abci.tests.test_behaviours import (
    DUMMY_CENTAURS_DATA,
)
from packages.valory.skills.twitter_scoring_abci.behaviours import (
    DBUpdateBehaviour,
    PostMechRequestBehaviour,
    PreMechRequestBehaviour,
    TAGLINE,
    TwitterDecisionMakingBehaviour,
    TwitterHashtagsCollectionBehaviour,
    TwitterMentionsCollectionBehaviour,
    TwitterRandomnessBehaviour,
    TwitterScoringBaseBehaviour,
    TwitterScoringRoundBehaviour,
    TwitterSelectKeepersBehaviour,
)
from packages.valory.skills.twitter_scoring_abci.rounds import (
    DataclassEncoder,
    Event,
    FinishedTwitterScoringRound,
    MechInteractionResponse,
    SynchronizedData,
    TwitterScoringAbciApp,
)


PACKAGE_DIR = Path(__file__).parent.parent
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

TWITTER_MENTIONS_URL = "https://api.twitter.com/2/users/1450081635559428107/mentions?tweet.fields=author_id&user.fields=name&expansions=author_id&max_results={max_results}&since_id=0"
TWITTER_REGISTRATIONS_URL = "https://api.twitter.com/2/tweets/search/recent?query=#OlasNetwork&tweet.fields=author_id,created_at,conversation_id&user.fields=name&expansions=author_id&max_results={max_results}&since_id=0"

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
    ceramic_db: Optional[Any] = None


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

    def fast_forward(
        self, data: Optional[Dict[str, Any]] = None, ceramic_db: Optional[Any] = None
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

        self.behaviour.act_wrapper()
        self.mock_a2a_transaction()
        self._test_done_flag_set()
        self.end_round(done_event=event)
        assert (
            self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
            == self.next_behaviour_class.auto_behaviour_id()
        )


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


class TestMentionsCollectionBehaviourSerial(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterMentionsCollectionBehaviour
    next_behaviour_class = TwitterDecisionMakingBehaviour

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
            (
                BehaviourTestCase(
                    "15 minute window limit",
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                        sleep_until=datetime.now().timestamp() + 200.00,
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
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                        centaurs_data=DUMMY_CENTAURS_DATA,
                    ),
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
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                        centaurs_data=DUMMY_CENTAURS_DATA,
                    ),
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
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                        centaurs_data=DUMMY_CENTAURS_DATA,
                    ),
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


class TestHashtagsCollectionBehaviourSerial(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterHashtagsCollectionBehaviour
    next_behaviour_class = TwitterDecisionMakingBehaviour

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
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
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
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
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
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                    ),
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
                    headers=kwargs.get("headers", [""])[i],
                ),
            )
        self.complete(test_case.event)

    def test_not_sender(self):
        """Test the not sender act."""

        assert not self.fast_forward(
            {"most_voted_keeper_addresses": ["not_my_address", "not_my_address"]}
        )
        self.behaviour.act_wrapper()
        self._test_done_flag_set()


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
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                        centaurs_data=DUMMY_CENTAURS_DATA,
                    ),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [
                        TWITTER_REGISTRATIONS_URL.format(max_results=80),
                    ],
                    "bodies": [
                        json.dumps(DUMMY_HASHTAGS_RESPONSE),
                    ],
                    "headers": [""],
                    "status_codes": [404],
                },
            ),
            (
                BehaviourTestCase(
                    "API error registrations: missing data",
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                        centaurs_data=DUMMY_CENTAURS_DATA,
                    ),
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
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                        centaurs_data=DUMMY_CENTAURS_DATA,
                    ),
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
                    initial_data=dict(
                        most_voted_keeper_addresses=[
                            "test_agent_address",
                            "test_agent_address",
                        ],
                        centaurs_data=DUMMY_CENTAURS_DATA,
                    ),
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
                    headers=kwargs.get("headers", [""])[i],
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
                    event=Event.SELECT_KEEPERS,
                ),
                TwitterRandomnessBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(performed_twitter_tasks={"select_keepers": None}),
                    event=Event.RETRIEVE_HASHTAGS,
                ),
                TwitterHashtagsCollectionBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={
                            "select_keepers": None,
                            "retrieve_hashtags": None,
                        }
                    ),
                    event=Event.RETRIEVE_MENTIONS,
                ),
                TwitterMentionsCollectionBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={
                            "select_keepers": None,
                            "retrieve_hashtags": None,
                            "retrieve_mentions": None,
                        }
                    ),
                    event=Event.PRE_MECH,
                ),
                PreMechRequestBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={
                            "select_keepers": None,
                            "retrieve_hashtags": None,
                            "retrieve_mentions": None,
                            "pre_mech": None,
                        }
                    ),
                    event=Event.POST_MECH,
                ),
                PostMechRequestBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={
                            "select_keepers": None,
                            "retrieve_hashtags": None,
                            "retrieve_mentions": None,
                            "pre_mech": None,
                            "post_mech": None,
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
                            "select_keepers": None,
                            "retrieve_hashtags": None,
                            "retrieve_mentions": None,
                            "pre_mech": None,
                            "post_mech": None,
                            "db_update": None,
                        }
                    ),
                    event=Event.DONE,
                ),
                make_degenerate_behaviour(FinishedTwitterScoringRound),
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, next_behaviour) -> None:
        """Run tests."""
        self.next_behaviour_class = next_behaviour
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()
        self.complete(test_case.event)


@pytest.fixture(scope="class")
def add_mech_responses_to_cross_period(request):
    """Fixture which adds the mech responses to the `cross_period_persisted_keys` of the abci app."""
    TwitterScoringAbciApp.cross_period_persisted_keys = frozenset({"mech_responses"})


class TestPostMechRequestBehaviour(BaseBehaviourTest):
    """Tests PostMechRequestBehaviour"""

    behaviour_class = PostMechRequestBehaviour
    next_behaviour_class = TwitterDecisionMakingBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        tweets={"1": {"text": "dummy text"}},
                        mech_responses=json.dumps(
                            [
                                MechInteractionResponse(
                                    nonce="1",
                                    result='{"quality":"HIGH","relationship":"HIGH"}',
                                )
                            ],
                            cls=DataclassEncoder,
                        ),
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

    def test_cross_period_defaults(self, add_mech_responses_to_cross_period) -> None:
        """Run a test using the default of the mech responses."""
        # use the latest db data, i.e., the defaults of the `cross_period_persisted_keys`
        db_data = self.behaviour.current_behaviour.synchronized_data.db.get_latest()
        self.fast_forward(db_data)
        self.behaviour.act_wrapper()
        self.complete(Event.DONE)


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
                                "created_at": "2024-05-31T08:26:53.000Z",
                            },
                            "2": {
                                "author_id": "2",
                                "points": 900,
                                "username": "dummy_2",
                                "text": "dummy text",
                                "created_at": "2024-05-31T08:26:53.000Z",
                            },
                            "3": {
                                "author_id": "3",
                                "points": 900,
                                "username": "dummy_3",
                                "text": "I'm linking my wallet to @Autonolas Contribute: 0x0000000000000000000000000000000000000000",
                                "created_at": "2024-05-31T08:26:53.000Z",
                            },
                            "4": {
                                "author_id": "1",
                                "points": 10000,  # too many points during this period
                                "username": "dummy",
                                "text": "dummy text",
                                "created_at": "2024-05-31T08:26:53.000Z",
                            },
                            "5": {
                                "author_id": "4",
                                "points": 900,
                                "username": "dummy_4",
                                "text": "I'm linking my wallet to @Autonolas Contribute:\n0x4F4715CA99C973A55303bc4a5f3e3acBb9fF75DB\n\nStart contributing to #OlasNetwork: https://t.co/4ocCNGEtyG",
                                "created_at": "2024-05-31T08:26:53.000Z",
                            },
                        },
                        latest_mention_tweet_id=1,
                        latest_hashtag_tweet_id=1,
                        number_of_tweets_pulled_today=1,
                        last_tweet_pull_window_reset=1993903085,  # in 10 years
                        centaurs_data=DUMMY_CENTAURS_DATA,
                    ),
                    event=Event.DONE,
                    ceramic_db={
                        "users": {
                            "0": {
                                "twitter_id": "1",
                                "points": 0,
                                "wallet_address": None,
                                "token_id": None,
                                "discord_id": None,
                            }
                        },
                        "module_data": {"twitter": {"current_period": "2023-09-04"}},
                    },
                ),
                {},
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
        self.complete(test_case.event)


class TestRandomnessBehaviour(BaseRandomnessBehaviourTest):
    """Test randomness in operation."""

    path_to_skill = PACKAGE_DIR

    randomness_behaviour_class = TwitterRandomnessBehaviour
    next_behaviour_class = TwitterSelectKeepersBehaviour
    done_event = Event.DONE


class BaseSelectKeepersBehaviourTest(BaseBehaviourTest):
    """Test SelectKeepersBehaviour."""

    select_keeper_behaviour_class: Type[BaseBehaviour]
    next_behaviour_class: Type[BaseBehaviour]

    def select_keeper_test(self, test_case) -> None:
        """Test select keeper agent."""
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
        self.end_round(done_event=Event.DONE)
        behaviour = cast(BaseBehaviour, self.behaviour.current_behaviour)
        assert behaviour.behaviour_id == self.next_behaviour_class.auto_behaviour_id()


class TestTwitterSelectKeepersCeramicBehaviour(BaseSelectKeepersBehaviourTest):
    """Test SelectKeeperBehaviour."""

    select_keeper_behaviour_class = TwitterSelectKeepersBehaviour
    next_behaviour_class = TwitterDecisionMakingBehaviour

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
        """Test select keeper."""
        super().select_keeper_test(test_case)

    def test_select_keeper_blacklisted(self) -> None:
        """Test select keeper agent when all agents are blacklisted."""
        self.select_keeper_behaviour_class = TwitterSelectKeepersBehaviour
        self.next_behaviour_class = TwitterDecisionMakingBehaviour
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
