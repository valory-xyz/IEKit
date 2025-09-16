# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2025 Valory AG
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
from unittest.mock import MagicMock

import pytest
from aea.exceptions import AEAActException
from aea.helpers.transaction.base import State

from packages.valory.contracts.staking.contract import Staking
from packages.valory.protocols.contract_api import ContractApiMessage
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
from packages.valory.skills.contribute_db_abci.contribute_models import ContributeUser
from packages.valory.skills.twitter_scoring_abci.behaviours import (
    DBUpdateBehaviour,
    PostMechRequestBehaviour,
    PreMechRequestBehaviour,
    TAGLINE,
    TwitterCampaignsCollectionBehaviour,
    TwitterDecisionMakingBehaviour,
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

TWITTER_MENTIONS_URL = "https://api.twitter.com/2/tweets/search/recent?query=@autonolas&tweet.fields=author_id,created_at,public_metrics&user.fields=name&expansions=author_id&max_results={max_results}&since_id=2"  # Workaround. Refer to issue #307
TWITTER_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent?query=Olas%20AI%20Agents&tweet.fields=author_id,created_at,conversation_id,public_metrics&user.fields=name&expansions=author_id&max_results={max_results}&since_id=0"


PARAM_OVERRIDES = {
    "twitter_max_pages": 10,
    "staking_contract_addresses": [
        "0xe2E68dDafbdC0Ae48E39cDd1E778298e9d865cF4",
        "0x6Ce93E724606c365Fc882D4D6dfb4A0a35fE2387",
        "0x28877FFc6583170a4C9eD0121fc3195d06fd3A26",
    ],
    "contribute_db_pkey": "0x1111111111111111111111111111111111111111111111111111111111111111",
    "twitter_search_args": "query=Olas%20AI%20Agents&tweet.fields=author_id,created_at,conversation_id,public_metrics&user.fields=name&expansions=author_id&max_results=120&since_id=0",
    "contributors_contract_address": "0x343F2B005cF6D70bA610CD9F1F1927049414B582",
}

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

DUMMY_CAMPAIGNS_RESPONSE = {
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


def get_mocked_contribute_db():
    """Factory to create a fresh mocked contribute DB per test with full control over parameters."""
    users = {
        "1": ContributeUser(
            id=1,
            current_period_points=0,
            twitter_handle="dummy_1",
            service_multisig=None,
            wallet_address=None,
        ),
        "2": ContributeUser(
            id=2,
            current_period_points=0,
            twitter_handle="dummy_2",
            service_multisig=None,
            wallet_address=None,
        ),
        "3": ContributeUser(
            id=3,
            current_period_points=0,
            twitter_handle="dummy_3",
            service_multisig=None,
            wallet_address=None,
        ),
        "4": ContributeUser(
            id=4,
            current_period_points=0,
            twitter_handle="dummy_4",
            service_multisig=None,
            wallet_address=None,
        ),
        "5": ContributeUser(
            id=5,
            current_period_points=0,
            twitter_handle="dummy_5",
            service_multisig=None,
            wallet_address=None,
        ),
    }

    contribute_db = MagicMock()

    def _get_user_by_attribute(attr, value):
        return users.get(value, None)

    contribute_db.get_user_by_attribute.side_effect = _get_user_by_attribute
    return contribute_db


def get_mocked_agent_db(
    number_of_tweets_pulled_today: int = 1,
    last_tweet_pull_window_reset: int = 1993903085,
    latest_hashtag_tweet_id: int = 0,
    campaigns: list = None,
    current_scoring_period=None,
):
    """Factory to create a fresh mocked agent DB per test with full control over parameters."""
    if campaigns is None:
        campaigns = []

    if current_scoring_period is None:
        current_scoring_period = datetime.now().date()
    return MagicMock(
        module_data=MagicMock(
            twitter=MagicMock(
                number_of_tweets_pulled_today=number_of_tweets_pulled_today,
                last_tweet_pull_window_reset=last_tweet_pull_window_reset,
                latest_hashtag_tweet_id=latest_hashtag_tweet_id,
                current_period=current_scoring_period,
            ),
            twitter_campaigns=MagicMock(campaigns=campaigns),
        )
    )


@dataclass
class BehaviourTestCase:
    """BehaviourTestCase"""

    name: str
    initial_data: Dict[str, Any]
    event: Event
    next_behaviour_class: Optional[Type[TwitterScoringBaseBehaviour]] = None
    agent_db: Optional[Any] = None


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
        super().setup_class(param_overrides=PARAM_OVERRIDES)
        # inject before behaviour instantiation
        cls._skill.skill_context.agent_db_client = MagicMock()
        cls._skill.skill_context.contribute_db = get_mocked_contribute_db()
        cls.llm_handler = cls._skill.skill_context.handlers.llm

    def fast_forward(
        self, data: Optional[Dict[str, Any]] = None, agent_db: Optional[Any] = None
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
        if agent_db:
            self.skill.skill_context.contribute_db.data = agent_db

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
    """Tests TestMentionsCollectionBehaviour"""

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
                    agent_db=get_mocked_agent_db(),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWITTER_MENTIONS_URL.format(max_results=100),
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
                    agent_db=get_mocked_agent_db(),
                    event=Event.DONE,
                ),
                {
                    "request_urls": [
                        TWITTER_MENTIONS_URL.format(max_results=100),
                        TWITTER_MENTIONS_URL.format(max_results=100)
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
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "request_urls": [
                        TWITTER_MENTIONS_URL.format(max_results=100),
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
        ids=["Happy path", "Happy path, multi-page", "Happy path, result_count=0"],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data, test_case.agent_db)
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
                    agent_db=get_mocked_agent_db(number_of_tweets_pulled_today=10000),
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
                    agent_db=get_mocked_agent_db(number_of_tweets_pulled_today=10000),
                ),
                {
                    "request_urls": [],
                },
            ),
        ],
        ids=["API daily limit reached", "15 minute window limit"],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""

        self.fast_forward(test_case.initial_data, test_case.agent_db)
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


class TestCampaignsCollectionBehaviour(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterCampaignsCollectionBehaviour
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
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "request_urls": [
                        TWITTER_SEARCH_URL.format(max_results=120),
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
                    ),
                    event=Event.DONE,
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "request_urls": [
                        TWITTER_SEARCH_URL.format(max_results=120),
                        TWITTER_SEARCH_URL.format(max_results=120)
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
                    ),
                    event=Event.DONE,
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "request_urls": [
                        TWITTER_SEARCH_URL.format(max_results=120),
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
        ids=["Happy path", "Happy path, multi-page", "Happy path, result_count=0"],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data, test_case.agent_db)
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


class TestCampaignsCollectionBehaviourSerial(BaseBehaviourTest):
    """TestCampaignsCollectionBehaviourSerial"""

    behaviour_class = TwitterCampaignsCollectionBehaviour
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
                    agent_db=get_mocked_agent_db(number_of_tweets_pulled_today=10000),
                ),
                {
                    "request_urls": [],
                },
            ),
        ],
        ids=["API daily limit reached"],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data, test_case.agent_db)
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
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL.format(max_results=100)],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE,
                        ),
                        json.dumps(DUMMY_CAMPAIGNS_RESPONSE),
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
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL.format(max_results=100)],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_MISSING_DATA,
                        ),
                        json.dumps(DUMMY_CAMPAIGNS_RESPONSE),
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
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL.format(max_results=100)],
                    "bodies": [
                        json.dumps(
                            DUMMY_MENTIONS_RESPONSE_MISSING_META,
                        ),
                        json.dumps(DUMMY_CAMPAIGNS_RESPONSE),
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
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "urls": [TWITTER_MENTIONS_URL.format(max_results=100)],
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
        ids=[
            "API error mentions: 404",
            "API error mentions: missing data",
            "API error mentions: missing meta",
            "API error mentions: missing includes",
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data, agent_db=test_case.agent_db)
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


class TestCampaignsCollectionBehaviourAPIError(BaseBehaviourTest):
    """Tests BinanceObservationBehaviour"""

    behaviour_class = TwitterCampaignsCollectionBehaviour
    next_behaviour_class = TwitterCampaignsCollectionBehaviour

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
                    ),
                    event=Event.API_ERROR,
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "urls": [
                        TWITTER_SEARCH_URL.format(max_results=120),
                    ],
                    "bodies": [
                        json.dumps(DUMMY_CAMPAIGNS_RESPONSE),
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
                    ),
                    event=Event.API_ERROR,
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "urls": [
                        TWITTER_SEARCH_URL.format(max_results=120),
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
                    ),
                    event=Event.API_ERROR,
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "urls": [
                        TWITTER_SEARCH_URL.format(max_results=120),
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
                    ),
                    event=Event.API_ERROR,
                    agent_db=get_mocked_agent_db(),
                ),
                {
                    "urls": [TWITTER_SEARCH_URL.format(max_results=120)],
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
        ids=[
            "API error registrations: 404",
            "API error registrations: missing data",
            "API error registrations: missing meta",
            "API error registrations: missing includes",
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data, test_case.agent_db)
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
                    event=Event.RETRIEVE_CAMPAIGNS,
                ),
                TwitterCampaignsCollectionBehaviour,
            ),
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        performed_twitter_tasks={
                            "select_keepers": None,
                            "retrieve_campaigns": None,
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
                            "retrieve_campaigns": None,
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
                            "retrieve_campaigns": None,
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
                            "retrieve_campaigns": None,
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
                            "retrieve_campaigns": None,
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
                                "username": "dummy_1",
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
                                "username": "dummy_1",
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
                    ),
                    event=Event.DONE,
                    agent_db=get_mocked_agent_db(),
                ),
                {},
            ),
        ],
        ids=["Happy path"],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data, test_case.agent_db)
        self.behaviour.act_wrapper()

        #  3 staking contracts
        for _ in range(3):
            self.mock_contract_api_request(
                request_kwargs=dict(
                    performative=ContractApiMessage.Performative.GET_STATE,
                ),
                contract_id=str(Staking.contract_id),
                response_kwargs=dict(
                    performative=ContractApiMessage.Performative.STATE,
                    callable="get_epoch",
                    state=State(ledger_id="ethereum", body={"epoch": 1}),
                ),
            )

        self.complete(test_case.event)


class TestRandomnessBehaviour(BaseRandomnessBehaviourTest):
    """Test randomness in operation."""

    path_to_skill = PACKAGE_DIR

    randomness_behaviour_class = TwitterRandomnessBehaviour
    next_behaviour_class = TwitterSelectKeepersBehaviour
    done_event = Event.DONE

    @classmethod
    def setup_class(cls, **kwargs: Any) -> None:
        """Setup class"""
        super().setup_class(param_overrides=PARAM_OVERRIDES)
        # inject before behaviour instantiation
        cls._skill.skill_context.agent_db_client = get_mocked_agent_db()
        cls._skill.skill_context.contribute_db = get_mocked_contribute_db()
        cls.llm_handler = cls._skill.skill_context.handlers.llm


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
