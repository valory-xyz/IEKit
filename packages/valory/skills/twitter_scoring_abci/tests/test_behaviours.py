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
from packages.valory.skills.twitter_scoring_abci.behaviours import (
    TAGLINE,
    TwitterCollectionBehaviour,
    TwitterScoringBaseBehaviour,
    TwitterScoringRoundBehaviour,
)
from packages.valory.skills.twitter_scoring_abci.rounds import (
    Event,
    FinishedTwitterScoringRound,
    SynchronizedData,
)


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

TWITTER_MENTIONS_URL = "https://api.twitter.com/2/users/1450081635559428107/mentions?tweet.fields=author_id&user.fields=name&expansions=author_id&max_results=100&since_id=0"
TWITTER_REGISTRATIONS_URL = "https://api.twitter.com/2/tweets/search/recent?query=%23olas&tweet.fields=author_id,created_at&user.fields=name&expansions=author_id&max_results=100&since_id=0"

DUMMY_MENTIONS_RESPONSE = {
    "data": [
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812738", "text": "dummy_text"},
        {"author_id": "1286010187325812737", "text": "dummy_text"},
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
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812738", "text": "dummy_text"},
        {"author_id": "1286010187325812737", "text": "dummy_text"},
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
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812738", "text": "dummy_text"},
        {"author_id": "1286010187325812737", "text": "dummy_text"},
    ],
    "meta": {"result_count": 4, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_MENTIONS_RESPONSE_MISSING_META = {}

DUMMY_MENTIONS_RESPONSE_MULTIPAGE = {
    "data": [
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812738", "text": "dummy_text"},
        {"author_id": "1286010187325812737", "text": "dummy_text"},
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
        },
    ],
    "meta": {"result_count": 0, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_REGISTRATIONS_RESPONSE_MISSING_META = {
    "data": [
        {
            "author_id": "1286010187325812739",
            "text": f"dummy_text #olas {ZERO_ADDRESS}",
        },
    ]
}

DUMMY_REGISTRATIONS_RESPONSE_MISSING_DATA = {
    "meta": {"result_count": 1, "newest_id": "1", "oldest_id": "0"},
}

DUMMY_HASHTAGS_RESPONSE = {
    "data": [
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812739", "text": "dummy_text"},
        {"author_id": "1286010187325812738", "text": "dummy_text"},
        {"author_id": "1286010187325812737", "text": "dummy_text"},
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


class TestTwitterCollectionBehaviour(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterCollectionBehaviour
    next_behaviour_class = make_degenerate_behaviour(FinishedTwitterScoringRound)

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
                        TWITTER_MENTIONS_URL,
                        TWITTER_REGISTRATIONS_URL,
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                        "Authorization: Bearer <default_bearer_token>\r\n",
                        "",
                    ],
                    "response_urls": [
                        "",
                        "",
                        "https://www.autonolas.network/whitepaper",
                    ],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE,
                        ),
                        json.dumps(
                            DUMMY_REGISTRATIONS_RESPONSE,
                        ),
                        json.dumps(
                            {},
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
                        TWITTER_MENTIONS_URL,
                        TWITTER_MENTIONS_URL + "&pagination_token=dummy_next_token",
                        TWITTER_REGISTRATIONS_URL,
                        TWITTER_REGISTRATIONS_URL
                        + "&pagination_token=dummy_next_token",
                    ],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                        "Authorization: Bearer <default_bearer_token>\r\n",
                        "Authorization: Bearer <default_bearer_token>\r\n",
                        "Authorization: Bearer <default_bearer_token>\r\n",
                    ],
                    "response_urls": ["", "", "", ""],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_MULTIPAGE,
                        ),
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE,
                        ),
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
                    "request_urls": [TWITTER_MENTIONS_URL, TWITTER_REGISTRATIONS_URL],
                    "request_headers": [
                        "Authorization: Bearer <default_bearer_token>\r\n",
                        "Authorization: Bearer <default_bearer_token>\r\n",
                    ],
                    "response_urls": ["", ""],
                    "response_bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_COUNT_ZERO,
                        ),
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


class TestTwitterCollectionBehaviourAPIError(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterCollectionBehaviour
    next_behaviour_class = TwitterCollectionBehaviour

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
                    "urls": [TWITTER_MENTIONS_URL, TWITTER_REGISTRATIONS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE,
                        ),
                        json.dumps(DUMMY_HASHTAGS_RESPONSE),
                    ],
                    "status_codes": [404, 200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error registrations: 404",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL, TWITTER_REGISTRATIONS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE,
                        ),
                        json.dumps(DUMMY_HASHTAGS_RESPONSE),
                    ],
                    "status_codes": [200, 404],
                },
            ),
            (
                BehaviourTestCase(
                    "API error mentions: missing data",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL, TWITTER_REGISTRATIONS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_MISSING_DATA,
                        ),
                        json.dumps(DUMMY_HASHTAGS_RESPONSE),
                    ],
                    "status_codes": [200, 200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error registrations: missing data",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL, TWITTER_REGISTRATIONS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE,
                        ),
                        json.dumps(
                            DUMMY_REGISTRATIONS_RESPONSE_MISSING_DATA,
                        ),
                    ],
                    "status_codes": [200, 200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error mentions: missing meta",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL, TWITTER_REGISTRATIONS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_MISSING_META,
                        ),
                        json.dumps(DUMMY_HASHTAGS_RESPONSE),
                    ],
                    "status_codes": [200, 200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error registrations: missing meta",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL, TWITTER_REGISTRATIONS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE,
                        ),
                        json.dumps(DUMMY_REGISTRATIONS_RESPONSE_MISSING_META),
                    ],
                    "status_codes": [200, 200],
                },
            ),
            (
                BehaviourTestCase(
                    "API error mentions: missing includes",
                    initial_data=dict(ceramic_db={}),
                    event=Event.API_ERROR,
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL, TWITTER_REGISTRATIONS_URL],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_MISSING_INCLUDES,
                        ),
                        json.dumps({}),
                    ],
                    "status_codes": [200, 200],
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
