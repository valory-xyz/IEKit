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
from typing import Any, Dict, Optional, Type, cast

import pytest

from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.abstract_round_abci.behaviour_utils import BaseBehaviour
from packages.valory.skills.abstract_round_abci.behaviours import (
    make_degenerate_behaviour,
)
from packages.valory.skills.abstract_round_abci.test_tools.base import (
    FSMBehaviourBaseCase,
)
from packages.valory.skills.abstract_round_abci.test_tools.common import (
    BaseRandomnessBehaviourTest,
)
from packages.valory.skills.score_write_abci.behaviours import (
    CeramicWriteBehaviour,
    RandomnessBehaviour,
    ScoreAddBehaviour,
    ScoreWriteBaseBehaviour,
    ScoreWriteRoundBehaviour,
    SelectKeeperCeramicBehaviour,
    VerificationBehaviour,
    WalletReadBehaviour,
)
from packages.valory.skills.score_write_abci.rounds import (
    Event,
    FinishedWalletReadRound,
    SynchronizedData,
)


PACKAGE_DIR = Path(__file__).parent.parent

DUMMY_USER_TO_SCORES = {"user_a": 10, "user_b": 10}

DUMMY_WALLET_TO_USERS = {
    "0x0000000000000000000000000000000000000000": "user_a",
    "0x0000000000000000000000000000000000000001": "user_b",
}

CERAMIC_API_STREAM_URL_POINTS_READ = (
    "https://ceramic-clay.3boxlabs.com/api/v0/commits/user_to_points_stream_id"
)
CERAMIC_API_STREAM_URL_POINTS_WRITE = "https://ceramic-clay.3boxlabs.com/api/v0/commits"
CERAMIC_API_STREAM_URL_WALLETS_READ = (
    "https://ceramic-clay.3boxlabs.com/api/v0/commits/wallet_to_users_stream_id"
)

# This response contains the data: {"user_a": 10, "user_b": 10}
DUMMY_API_RESPONSE_READ_POINTS = {
    "streamId": "kjzl6cwe1jw146rixydjkxxy4ne992nmkmyc9puerxkvzq89u4nj8fqla55pvxa",
    "docId": "kjzl6cwe1jw146rixydjkxxy4ne992nmkmyc9puerxkvzq89u4nj8fqla55pvxa",
    "commits": [
        {
            "cid": "bagcqcerahpeugmbk3zkdkv4ycufyrr3tqxti6pa2edongdx3pv6l6xb7u3pa",
            "value": {
                "jws": {
                    "payload": "AXESICI72Ss2P9MwMW8AY7M1a5-snqcAiE5E8DzAQN1-fBu7",
                    "signatures": [
                        {
                            "signature": "LJxjNcVGtTr-zmdRJwi28untH2pEwTNOTDW86gV30XmpXTF6SkezEWYwsixI8DLr6sazJWCDvGPuv5svNaXaAg",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa29uM05lY2Q2TmtreWZvR29IeGlkMnpuR2M1OUxVM0s3bXViYVJjRmJMZkxYI3o2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWCJ9",
                        }
                    ],
                    "link": "bafyreibchpmswnr72mydc3yamoztk247vspkoaeijzcpapgaidox47a3xm",
                },
                "linkedBlock": "omRkYXRhoWZ1c2VyX2EKZmhlYWRlcqJmdW5pcXVlcGw5cTlkNWY1bU5PS1B1UTdrY29udHJvbGxlcnOBeDhkaWQ6a2V5Ono2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWA",
            },
        },
        {
            "cid": "bagcqcera5ap2h62gdoocao5h6l72wmfueu5jx526lkwxy42sekqzyql3w3qq",
            "value": {
                "jws": {
                    "payload": "AXESIOwDeLa7D6V-QcPKI-j0v-XGFeWWLpfYv8ukOEKdJJ1U",
                    "signatures": [
                        {
                            "signature": "V-OCzXf5vWW7GnoGXKIUKm1uWnfA4IGenP2X8lg7WuUYPC6MwMbzUqwMwq9EEl2gVz7BjnAhv3Fbheh4CEcLAQ",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa29uM05lY2Q2TmtreWZvR29IeGlkMnpuR2M1OUxVM0s3bXViYVJjRmJMZkxYI3o2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWCJ9",
                        }
                    ],
                    "link": "bafyreihman4lnoypuv7edq6kepupjp7fyyk6lfros7ml7s5ehbbj2je5kq",
                },
                "linkedBlock": "pGJpZNgqWCYAAYUBEiA7yUMwKt5UNVeYFQuIx3OF5o88GiDc0w77fXy/XD+m3mRkYXRhgaNib3BjYWRkZHBhdGhnL3VzZXJfYmV2YWx1ZQpkcHJldtgqWCYAAYUBEiA7yUMwKt5UNVeYFQuIx3OF5o88GiDc0w77fXy/XD+m3mZoZWFkZXKg",
            },
        },
    ],
}

# This response contains the data:
# {  # noqa: E800
#     "0x0000000000000000000000000000000000000000": user_a,  # noqa: E800
#     "0x0000000000000000000000000000000000000001": user_b   # noqa: E800
# }  # noqa: E800
DUMMY_API_RESPONSE_READ_WALLETS = {
    "streamId": "kjzl6cwe1jw14bep29zqigcmhh9jwcbg3j10ffhnida4xsaqkvencc0k9bitlkz",
    "docId": "kjzl6cwe1jw14bep29zqigcmhh9jwcbg3j10ffhnida4xsaqkvencc0k9bitlkz",
    "commits": [
        {
            "cid": "bagcqcera6ympx5s6uci2leszj4cjplw5yu55lqvdj34e5whnipae6bwmacbq",
            "value": {
                "jws": {
                    "payload": "AXESIGuaNXE87FyvF7ydREXtV4-J8YnM5uDKB6dnexWl_pTd",
                    "signatures": [
                        {
                            "signature": "6r-_OxWf5ylmKidxz_A2uDNv3bDN2tul2Ly6a7J2nT4h_O6tAYoLi1I1xpXti1Vp3Y_RG3tnlGQ_IMZy7Sj4AA",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa29uM05lY2Q2TmtreWZvR29IeGlkMnpuR2M1OUxVM0s3bXViYVJjRmJMZkxYI3o2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWCJ9",
                        }
                    ],
                    "link": "bafyreidlti2xcphmlsxrppe5irc62v4prhyytthg4dfapj3hpmk2l7uu3u",
                },
                "linkedBlock": "omRkYXRhoWVoZWxsb2V3b3JsZGZoZWFkZXKiZnVuaXF1ZXBuM1k3WnhqcWttNjVZSGxBa2NvbnRyb2xsZXJzgXg4ZGlkOmtleTp6Nk1rb24zTmVjZDZOa2t5Zm9Hb0h4aWQyem5HYzU5TFUzSzdtdWJhUmNGYkxmTFg",
            },
        },
        {
            "cid": "bagcqcerab526kjv3qyk5tcfjhtxx2dhwf775fis2gg4ylkvboqa5fhsqlnza",
            "value": {
                "jws": {
                    "payload": "AXESIJWL5YG2mWZoxixlOO9PP-S2gbsRT3dHhi-C2p8MkT7Z",
                    "signatures": [
                        {
                            "signature": "MM5IQrutSU_rvl0grfp3P-x9EnCH_q08mhJA1UzgbHAujKxfURgJ62mLMK_F95J8Da6DtKxfZ60wPJG5XkSvDA",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa29uM05lY2Q2TmtreWZvR29IeGlkMnpuR2M1OUxVM0s3bXViYVJjRmJMZkxYI3o2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWCJ9",
                        }
                    ],
                    "link": "bafyreievrpsydnuzmzummldfhdxu6p7ew2a3wekpo5dyml4c3kpqzej63e",
                },
                "linkedBlock": "pGJpZNgqWCYAAYUBEiD2GPv2XqCRpZJZTwSXrt3FO9XCo074TtjtQ8BPBswAg2RkYXRhg6Jib3BmcmVtb3ZlZHBhdGhmL2hlbGxvo2JvcGNhZGRkcGF0aHgrLzB4MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMGV2YWx1ZWZ1c2VyX2GjYm9wY2FkZGRwYXRoeCsvMHgwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAxZXZhbHVlZnVzZXJfYmRwcmV22CpYJgABhQESIPYY+/ZeoJGlkllPBJeu3cU71cKjTvhO2O1DwE8GzACDZmhlYWRlcqA",
            },
        },
    ],
}

DUMMY_API_RESPONSE_READ_WRONG = {
    "streamId": "kjzl6cwe1jw149mrryi64a6z96jafmfct26pelvznv5fknp11ahytreojv2r6wa",
    "docId": "kjzl6cwe1jw149mrryi64a6z96jafmfct26pelvznv5fknp11ahytreojv2r6wa",
    "commits": [
        {
            "cid": "bagcqcerasckqtaxlcrzx6hvcqyzajhtlblugxqe2cytqf45l4pxflftlfp7a",
            "value": {
                "jws": {
                    "payload": "AXESIOBKJsyU_MDPJJKhKuDQokziMyCFUoqNyyoNNinDDg0F",
                    "signatures": [
                        {
                            "signature": "1RKVcKnR88Ufw75gifwpQYSJLApsldYvLXCehtY58v9BCf1Q8s-hPIPmg3dBjqZjZ1YKnTqlksxNltM-3QamBw",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa29uM05lY2Q2TmtreWZvR29IeGlkMnpuR2M1OUxVM0s3bXViYVJjRmJMZkxYI3o2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWCJ9",
                        }
                    ],
                    "link": "bafyreihajitmzfh4ydhsjevbflqnbism4izsbbksrkg4wkqngyu4gdqnau",
                },
                "linkedBlock": "omRkYXRhoWVvdGhlcmRkYXRhZmhlYWRlcqJmdW5pcXVlcEdxY0VGeC95WmhYVFJQbnNrY29udHJvbGxlcnOBeDhkaWQ6a2V5Ono2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWA",
            },
        }
    ],
}

DUMMY_API_RESPONSE_READ_WRONG_JSON = "-"


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

    @classmethod
    def setup_class(cls, **kwargs: Any) -> None:
        """Set up the test class."""
        super().setup_class(
            param_overrides={
                "ceramic_did_str": "z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
                "ceramic_did_seed": "0101010101010101010101010101010101010101010101010101010101010101",
            }
        )

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

    def complete(self, event: Event, sends: bool = True) -> None:
        """Complete test"""

        self.behaviour.act_wrapper()
        if sends:
            self.mock_a2a_transaction()
        self._test_done_flag_set()
        self.end_round(done_event=event)
        assert (
            self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
            == self.next_behaviour_class.auto_behaviour_id()
        )


class TestScoreAddBehaviour(BaseScoreWriteTest):
    """Tests ScoreAddBehaviour"""

    behaviour_class = ScoreAddBehaviour
    next_behaviour_class = RandomnessBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        user_to_new_points={"user_a": 10, "user_b": 10, "user_c": 10}
                    ),
                    event=Event.DONE,
                ),
                {
                    "read_data": {
                        "body": json.dumps(
                            DUMMY_API_RESPONSE_READ_POINTS,
                        ),
                        "status": 200,
                        "headers": "",
                    },
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()

        # Read data call
        self.mock_http_request(
            request_kwargs=dict(
                method="GET",
                headers=kwargs.get("read_data")["headers"],
                version="",
                url=CERAMIC_API_STREAM_URL_POINTS_READ,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("read_data")["status"],
                status_text="",
                body=kwargs.get("read_data")["body"].encode(),
            ),
        )

        self.complete(test_case.event)


class TestScoreAddErrorBehaviour(BaseScoreWriteTest):
    """Tests ScoreAddBehaviour"""

    behaviour_class = ScoreAddBehaviour
    next_behaviour_class = RandomnessBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API error",
                    initial_data=dict(user_to_new_points={"user_a": 10}),
                    event=Event.DONE,
                ),
                {
                    "read_data": {
                        "body": json.dumps(
                            DUMMY_API_RESPONSE_READ_POINTS,
                        ),
                        "status": 404,
                        "headers": "",
                    },
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()

        # Read data call
        self.mock_http_request(
            request_kwargs=dict(
                method="GET",
                headers=kwargs.get("read_data")["headers"],
                version="",
                url=CERAMIC_API_STREAM_URL_POINTS_READ,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("read_data")["status"],
                status_text="",
                body=kwargs.get("read_data")["body"].encode(),
            ),
        )

        self.complete(test_case.event)


class TestScoreAddNoChangesBehaviour(BaseScoreWriteTest):
    """Tests ScoreAddBehaviour"""

    behaviour_class = ScoreAddBehaviour
    next_behaviour_class = WalletReadBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "No changes",
                    initial_data=dict(user_to_new_points={}),
                    event=Event.NO_CHANGES,
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


class TestRandomnessBehaviour(BaseRandomnessBehaviourTest):
    """Test randomness in operation."""

    path_to_skill = PACKAGE_DIR

    randomness_behaviour_class = RandomnessBehaviour
    next_behaviour_class = SelectKeeperCeramicBehaviour
    done_event = Event.DONE


class BaseSelectKeeperCeramicBehaviourTest(BaseScoreWriteTest):
    """Test SelectKeeperBehaviour."""

    select_keeper_behaviour_class: Type[BaseBehaviour]
    next_behaviour_class: Type[BaseBehaviour]

    def test_select_keeper(
        self,
    ) -> None:
        """Test select keeper agent."""
        participants = frozenset({self.skill.skill_context.agent_address, "a_1", "a_2"})
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
                        most_voted_keeper_address=["a_1"],
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


class TestSelectKeeperCeramicBehaviour(BaseSelectKeeperCeramicBehaviourTest):
    """Test SelectKeeperBehaviour."""

    select_keeper_behaviour_class = SelectKeeperCeramicBehaviour
    next_behaviour_class = CeramicWriteBehaviour


class TestCeramicWriteBehaviourSender(BaseScoreWriteTest):
    """Tests CeramicWriteBehaviour"""

    behaviour_class = CeramicWriteBehaviour
    next_behaviour_class = VerificationBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(most_voted_keeper_address="test_agent_address"),
                    event=Event.DONE,
                ),
                {
                    "read_data": {
                        "body": json.dumps(
                            DUMMY_API_RESPONSE_READ_POINTS,
                        ),
                        "status": 200,
                        "headers": "",
                    },
                    "write_data": {
                        "body": json.dumps(
                            {},
                        ),
                        "status": 200,
                        "headers": "Content-Type: application/json\r\nAccept: application/json\r\n",
                    },
                },
            ),
            (
                BehaviourTestCase(
                    "Json decode error",
                    initial_data=dict(most_voted_keeper_address="test_agent_address"),
                    event=Event.DONE,
                ),
                {
                    "read_data": {
                        "body": DUMMY_API_RESPONSE_READ_WRONG_JSON,
                        "status": 200,
                        "headers": "",
                    },
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()

        # Read data call
        self.mock_http_request(
            request_kwargs=dict(
                method="GET",
                headers=kwargs.get("read_data")["headers"],
                version="",
                url=CERAMIC_API_STREAM_URL_POINTS_READ,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("read_data")["status"],
                status_text="",
                body=kwargs.get("read_data")["body"].encode(),
            ),
        )

        # Write data call
        if "write_data" in kwargs:
            self.mock_http_request(
                request_kwargs=dict(
                    method="POST",
                    headers=kwargs.get("write_data")["headers"],
                    version="",
                    url=CERAMIC_API_STREAM_URL_POINTS_WRITE,
                ),
                response_kwargs=dict(
                    version="",
                    status_code=kwargs.get("write_data")["status"],
                    status_text="",
                    body=kwargs.get("write_data")["body"].encode(),
                ),
            )

        self.complete(test_case.event)


class TestCeramicWriteBehaviourNonSender(BaseScoreWriteTest):
    """Tests CeramicWriteBehaviour"""

    behaviour_class = CeramicWriteBehaviour
    next_behaviour_class = VerificationBehaviour

    @pytest.mark.parametrize(
        "test_case",
        [
            BehaviourTestCase(
                "Happy path",
                initial_data=dict(most_voted_keeper_address="not_my_address"),
                event=Event.DONE,
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.complete(event=test_case.event, sends=False)


class TestCeramicWriteBehaviourApiError(BaseScoreWriteTest):
    """Tests CeramicWriteBehaviour"""

    behaviour_class = CeramicWriteBehaviour
    next_behaviour_class = RandomnessBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API read error",
                    initial_data=dict(most_voted_keeper_address="test_agent_address"),
                    event=Event.API_ERROR,
                ),
                {
                    "read_data": {
                        "body": json.dumps(
                            DUMMY_API_RESPONSE_READ_POINTS,
                        ),
                        "status": 404,
                        "headers": "",
                    },
                },
            ),
            (
                BehaviourTestCase(
                    "API write error",
                    initial_data=dict(most_voted_keeper_address="test_agent_address"),
                    event=Event.API_ERROR,
                ),
                {
                    "read_data": {
                        "body": json.dumps(
                            DUMMY_API_RESPONSE_READ_POINTS,
                        ),
                        "status": 200,
                        "headers": "",
                    },
                    "write_data": {
                        "body": json.dumps(
                            {},
                        ),
                        "status": 404,
                        "headers": "Content-Type: application/json\r\nAccept: application/json\r\n",
                    },
                },
            ),
        ],
    )
    def test_run(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()

        # Read data call
        self.mock_http_request(
            request_kwargs=dict(
                method="GET",
                headers=kwargs.get("read_data")["headers"],
                version="",
                url=CERAMIC_API_STREAM_URL_POINTS_READ,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("read_data")["status"],
                status_text="",
                body=kwargs.get("read_data")["body"].encode(),
            ),
        )

        # Write data call (only if read was succesful)
        if kwargs.get("read_data")["status"] == 200:
            self.mock_http_request(
                request_kwargs=dict(
                    method="POST",
                    headers=kwargs.get("write_data")["headers"],
                    version="",
                    url=CERAMIC_API_STREAM_URL_POINTS_WRITE,
                ),
                response_kwargs=dict(
                    version="",
                    status_code=kwargs.get("write_data")["status"],
                    status_text="",
                    body=kwargs.get("write_data")["body"].encode(),
                ),
            )

        self.complete(test_case.event)


class TestVerificationBehaviour(BaseScoreWriteTest):
    """Tests CeramicWriteBehaviour"""

    behaviour_class = VerificationBehaviour
    next_behaviour_class = WalletReadBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(user_to_total_points=DUMMY_USER_TO_SCORES),
                    event=Event.DONE,
                ),
                {
                    "body": json.dumps(
                        DUMMY_API_RESPONSE_READ_POINTS,
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
                url=CERAMIC_API_STREAM_URL_POINTS_READ,
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
                    initial_data=dict(user_to_total_points=DUMMY_USER_TO_SCORES),
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
                    initial_data=dict(user_to_total_points=DUMMY_USER_TO_SCORES),
                    event=Event.API_ERROR,
                ),
                {
                    "body": json.dumps(
                        DUMMY_API_RESPONSE_READ_WRONG,
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
                url=CERAMIC_API_STREAM_URL_POINTS_READ,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)


class TestWalletReadBehaviour(BaseScoreWriteTest):
    """Tests WalletReadBehaviour"""

    behaviour_class = WalletReadBehaviour
    next_behaviour_class = make_degenerate_behaviour(  # type: ignore
        FinishedWalletReadRound
    )

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
                        DUMMY_API_RESPONSE_READ_WALLETS,
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
                url=CERAMIC_API_STREAM_URL_WALLETS_READ,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)


class TestWalletReadBehaviourApiError(BaseScoreWriteTest):
    """Tests WalletReadBehaviour"""

    behaviour_class = WalletReadBehaviour
    next_behaviour_class = RandomnessBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Api Error",
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
                url=CERAMIC_API_STREAM_URL_WALLETS_READ,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)
