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

DUMMY_USER_TO_SCORES = {"hello": "world"}

DUMMY_WALLET_TO_USERS = {"wallet_a": "user_a", "wallet_b": "user_b"}

CERAMIC_API_STREAM_URL_POINTS = (
    "https://ceramic-clay.3boxlabs.com/api/v0/commits/user_to_points_stream_id"
)
CERAMIC_API_STREAM_URL_WALLETS = (
    "https://ceramic-clay.3boxlabs.com/api/v0/commits/wallet_to_users_stream_id"
)

DUMMY_API_RESPONSE_READ = {
    "streamId": "kjzl6cwe1jw1484iasm05ja0awfjl0gnnwxw2kyugu5s7xtx3j1ffep8iob3r63",
    "docId": "kjzl6cwe1jw1484iasm05ja0awfjl0gnnwxw2kyugu5s7xtx3j1ffep8iob3r63",
    "commits": [
        {
            "cid": "bagcqceraojqhyoedmb5qnx7jkdm77rxb7h5kukalrav733m5bw6jn3p6c5fq",
            "value": {
                "jws": {
                    "payload": "AXESIBhJmbbXniM1EOHntTa5lBfFeQRJRfC0_kYtaw-pOBOB",
                    "signatures": [
                        {
                            "signature": "hRW6iqTVNNjbwuNBQpYSi_xtjBBdJKNEq6rgFe0uJL6soh7PyMbGfwx8QmUe_S-HvmDLGkzEhXFElE9biNc7Dg",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa29uM05lY2Q2TmtreWZvR29IeGlkMnpuR2M1OUxVM0s3bXViYVJjRmJMZkxYI3o2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWCJ9",
                        }
                    ],
                    "link": "bafyreiayjgm3nv46em2rbyphwu3ltfaxyv4qiskf6c2p4rrnnmh2soatqe",
                },
                "linkedBlock": "omRkYXRhoWVvdGhlcmRkYXRhZmhlYWRlcqJmdW5pcXVlcEh4bEdQemhNZUlZTzl3QzJrY29udHJvbGxlcnOBeDhkaWQ6a2V5Ono2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWA",
            },
        },
        {
            "cid": "bagcqcerask25is7ihbbypevitb24xiq5tt5ywzzt7o2nlngi267i3vcveuwa",
            "value": {
                "jws": {
                    "payload": "AXESIHLsnaWdJAiRKdyyxLXbU_8Slj8Tz_1nsW8yS-gGhIT9",
                    "signatures": [
                        {
                            "signature": "3PY9f9MbvETZk4MncscttLk99cV-zPXKdwvlKIc7XtzeC5QxzAy1Jl4Ya8geJNIgMdC7ctBXBV7i-94IhMHHAA",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa29uM05lY2Q2TmtreWZvR29IeGlkMnpuR2M1OUxVM0s3bXViYVJjRmJMZkxYI3o2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWCJ9",
                        }
                    ],
                    "link": "bafyreids5so2lhjebcistxfsys25wu77ckld6e6p7vt3c3zsjpuanbee7u",
                },
                "linkedBlock": "pGJpZNgqWCYAAYUBEiByYHw4g2B7Bt/pUNn/xuH5+qooC4gr/e2dDbyW7f4XS2RkYXRhgqJib3BmcmVtb3ZlZHBhdGhmL290aGVyo2JvcGNhZGRkcGF0aGQvZm9vZXZhbHVlY2JhemRwcmV22CpYJgABhQESIHJgfDiDYHsG3+lQ2f/G4fn6qigLiCv97Z0NvJbt/hdLZmhlYWRlcqA",
            },
        },
        {
            "cid": "bagcqceraggsggxj3ecdbbw3ltcg4uihayh7s7ax2f6nsxsqzapkrvwhs2p6q",
            "value": {
                "jws": {
                    "payload": "AXESIEgtRA4e3z0hf1VhcjpJvzePVULRCZnvem1pbpj1akLn",
                    "signatures": [
                        {
                            "signature": "FkbSk5zfwoD0AhdXOnej1-vY3qlTiakBmdNYrY-pPXFp49J_PMUGiwfr4LSR9UT4GJ-6OduXXv8WtnTqJVRgBw",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa29uM05lY2Q2TmtreWZvR29IeGlkMnpuR2M1OUxVM0s3bXViYVJjRmJMZkxYI3o2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWCJ9",
                        }
                    ],
                    "link": "bafyreicifvca4hw7huqx6vlboi5etpzxr5kufuijthxxu3ljn2mpk2sc44",
                },
                "linkedBlock": "pGJpZNgqWCYAAYUBEiByYHw4g2B7Bt/pUNn/xuH5+qooC4gr/e2dDbyW7f4XS2RkYXRhgaNib3BncmVwbGFjZWRwYXRoZC9mb29ldmFsdWVkYmF6MmRwcmV22CpYJgABhQESIJK11EvoOEOHkqiYdcuiHZz7i2cz+7TVtMjXvo3UVSUsZmhlYWRlcqA",
            },
        },
        {
            "cid": "bagcqcerailso2sw7yxu5ytb4kmemhj5lyn737r5ztx65vpliowt2d3utnaja",
            "value": {
                "jws": {
                    "payload": "AXESID0CjbtNzDDHpDR_hdE_AT8Jm6nF6Yt5J5n27YNdzlfh",
                    "signatures": [
                        {
                            "signature": "zgVaoiiluocxnJ663PBKMUAEiL-SxHKtxkLLCfy0C7kFrF_zIPIKV_0Fp3BsoOpOD0KfzqHmG617HgJzyy7CBA",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa29uM05lY2Q2TmtreWZvR29IeGlkMnpuR2M1OUxVM0s3bXViYVJjRmJMZkxYI3o2TWtvbjNOZWNkNk5ra3lmb0dvSHhpZDJ6bkdjNTlMVTNLN211YmFSY0ZiTGZMWCJ9",
                        }
                    ],
                    "link": "bafyreib5akg3wtomgdd2ind7qxit6aj7bgn2trpjrn4spgpw5wbv3tsx4e",
                },
                "linkedBlock": "pGJpZNgqWCYAAYUBEiByYHw4g2B7Bt/pUNn/xuH5+qooC4gr/e2dDbyW7f4XS2RkYXRhgqJib3BmcmVtb3ZlZHBhdGhkL2Zvb6Nib3BjYWRkZHBhdGhmL2hlbGxvZXZhbHVlZXdvcmxkZHByZXbYKlgmAAGFARIgMaRjXTsghhDba5iNyiDgwf8vgvovmyvKGQPVGtjy0/1maGVhZGVyoA",
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
                "ceramic_did_str": "did:key:z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
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
                            DUMMY_API_RESPONSE_READ,
                        ),
                        "status": 200,
                    },
                    "write_data": {
                        "body": json.dumps(
                            {},
                        ),
                        "status": 200,
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
                headers="",
                version="",
                url=CERAMIC_API_STREAM_URL_POINTS,
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
                    headers="",
                    version="",
                    url=CERAMIC_API_STREAM_URL_POINTS,
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
                            DUMMY_API_RESPONSE_READ,
                        ),
                        "status": 404,
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
                            DUMMY_API_RESPONSE_READ,
                        ),
                        "status": 200,
                    },
                    "write_data": {
                        "body": json.dumps(
                            {},
                        ),
                        "status": 404,
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
                headers="",
                version="",
                url=CERAMIC_API_STREAM_URL_POINTS,
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
                    headers="",
                    version="",
                    url=CERAMIC_API_STREAM_URL_POINTS,
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
                    initial_data=dict(user_to_scores=DUMMY_USER_TO_SCORES),
                    event=Event.DONE,
                ),
                {
                    "body": json.dumps(
                        DUMMY_API_RESPONSE_READ,
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
                url=CERAMIC_API_STREAM_URL_POINTS,
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
                url=CERAMIC_API_STREAM_URL_POINTS,
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
                    initial_data=dict(user_to_scores=DUMMY_USER_TO_SCORES),
                    event=Event.DONE,
                ),
                {
                    "body": json.dumps(
                        DUMMY_API_RESPONSE_READ,
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
                url=CERAMIC_API_STREAM_URL_WALLETS,
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
            (
                BehaviourTestCase(
                    "Api wrong data",
                    initial_data=dict(),
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
                url=CERAMIC_API_STREAM_URL_WALLETS,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)
