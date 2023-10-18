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

from aea.exceptions import AEAActException

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
from packages.valory.skills.ceramic_write_abci.behaviours import (
    CeramicWriteBaseBehaviour,
    CeramicWriteRoundBehaviour,
    RandomnessCeramicBehaviour,
    SelectKeeperCeramicBehaviour,
    StreamWriteBehaviour,
    VerificationBehaviour,
)
from packages.valory.skills.ceramic_write_abci.rounds import (
    Event,
    FinishedMaxRetriesRound,
    FinishedVerificationRound,
    SynchronizedData,
)


PACKAGE_DIR = Path(__file__).parent.parent

DUMMY_DID = "z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX"
DUMMY_DID_SEED = "0101010101010101010101010101010101010101010101010101010101010101"

CERAMIC_API_STREAM_URL_READ = (
    "https://ceramic-clay.3boxlabs.com/api/v0/commits/dummy_stream_id"
)
CERAMIC_API_STREAM_URL_WRITE = "https://ceramic-clay.3boxlabs.com/api/v0/commits"

CERAMIC_API_STREAM_URL_CREATE = "https://ceramic-clay.3boxlabs.com/api/v0/streams"

DUMMY_DATA = {
    "user_to_total_points": {"user_a": 10, "user_b": 10},
    "latest_mention_tweet_id": 15,
    "id_to_usernames": {},
    "wallet_to_users": {},
}

# This response contains the DUMMY_DATA
DUMMY_API_RESPONSE_OK = {
    "streamId": "kjzl6cwe1jw14bgd22tdiyp3l2te7mdco5bv9eqyj221i7pjfc1ip1n1ltearq5",
    "docId": "kjzl6cwe1jw14bgd22tdiyp3l2te7mdco5bv9eqyj221i7pjfc1ip1n1ltearq5",
    "commits": [
        {
            "cid": "bagcqcera672hmi33bvunpd54gfoac5s62oszsciv7vcf3qpah2tzzlmittoq",
            "value": {
                "jws": {
                    "payload": "AXESICx425k4xUCsg-PpRlRNL1Im9a_qRpst0mGK4awhqTxU",
                    "signatures": [
                        {
                            "signature": "TZjZtY2F43Z5orqrxOnpC7jIXrr4u73JdGNOLMHh1xPDJaTUulsU6svdDnuL8mhrNyEbRs0kTurqOHSzFToUBw",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa3JCM1VuMWhUNWdiY0JtWTVHaU1rZkpNMmdnVFpCRXlaUThVc2l2czUzbnFTI3o2TWtyQjNVbjFoVDVnYmNCbVk1R2lNa2ZKTTJnZ1RaQkV5WlE4VXNpdnM1M25xUyJ9",
                        }
                    ],
                    "link": "bafyreibmpdnzsogficwihy7jizke2l2se32272sgtmw5eymk4gwcdkj4kq",
                },
                "linkedBlock": "oWZoZWFkZXKiZnVuaXF1ZXBhY3hGOElBYVIyNVJFYWZva2NvbnRyb2xsZXJzgXg4ZGlkOmtleTp6Nk1rckIzVW4xaFQ1Z2JjQm1ZNUdpTWtmSk0yZ2dUWkJFeVpROFVzaXZzNTNucVM",
            },
        },
        {
            "cid": "bagcqcera65nduwkmdw4keoclb5ka6jvny5tacubbdjd2iskptcehom53lmga",
            "value": {
                "jws": {
                    "payload": "AXESIBK9z2d0Q57t1E6NxqUOhBkDSW_T0me2g8s1hTN_Tio9",
                    "signatures": [
                        {
                            "signature": "zhjZTgjfaMb6a3mN6yaEC_BXBVTzDHKbBXhJc48nYhAazTixKG9Rl5Ljv5wrEuOK3bJLbfIXlsgqyit56nMjBg",
                            "protected": "eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa3JCM1VuMWhUNWdiY0JtWTVHaU1rZkpNMmdnVFpCRXlaUThVc2l2czUzbnFTI3o2TWtyQjNVbjFoVDVnYmNCbVk1R2lNa2ZKTTJnZ1RaQkV5WlE4VXNpdnM1M25xUyJ9",
                        }
                    ],
                    "link": "bafyreiasxxhwo5cdt3w5ituny2sq5bazanew7u6sm63ihszvquzx6trkhu",
                },
                "linkedBlock": "pGJpZNgqWCYAAYUBEiD39HYjew1o14+8MVwBdl7TpZkJFf1EXcHgPqecrYic3WRkYXRhhKNib3BjYWRkZHBhdGhwL3dhbGxldF90b191c2Vyc2V2YWx1ZaCjYm9wY2FkZGRwYXRodS91c2VyX3RvX3RvdGFsX3BvaW50c2V2YWx1ZaJmdXNlcl9hCmZ1c2VyX2IKo2JvcGNhZGRkcGF0aHAvaWRfdG9fdXNlcm5hbWVzZXZhbHVloKNib3BjYWRkZHBhdGh4GC9sYXRlc3RfbWVudGlvbl90d2VldF9pZGV2YWx1ZQ9kcHJldtgqWCYAAYUBEiD39HYjew1o14+8MVwBdl7TpZkJFf1EXcHgPqecrYic3WZoZWFkZXKg",
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
    next_behaviour_class: Optional[Type[CeramicWriteBaseBehaviour]] = None


class BaseCeramicWriteTest(FSMBehaviourBaseCase):
    """Base test case."""

    path_to_skill = Path(__file__).parent.parent

    behaviour: CeramicWriteRoundBehaviour
    behaviour_class: Type[CeramicWriteBaseBehaviour]
    next_behaviour_class: Type[CeramicWriteBaseBehaviour]
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

    randomness_behaviour_class = RandomnessCeramicBehaviour
    next_behaviour_class = SelectKeeperCeramicBehaviour
    done_event = Event.DONE


class BaseSelectKeeperCeramicBehaviourTest(BaseCeramicWriteTest):
    """Test SelectKeeperBehaviour."""

    select_keeper_behaviour_class: Type[BaseBehaviour]
    next_behaviour_class: Type[BaseBehaviour]

    def test_select_keeper(
        self,
    ) -> None:
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
    next_behaviour_class = StreamWriteBehaviour


class TestStreamWriteBehaviourSender(BaseCeramicWriteTest):
    """Tests StreamWriteBehaviour"""

    behaviour_class = StreamWriteBehaviour
    next_behaviour_class = VerificationBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "stream_id": "dummy_stream_id",
                                "op": "update",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                            },
                        ],
                    ),
                    event=Event.DONE,
                ),
                {
                    "read_data": {
                        "body": json.dumps(
                            DUMMY_API_RESPONSE_OK,
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
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "stream_id": "dummy_stream_id",
                                "op": "update",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                            }
                        ],
                    ),
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
                url=CERAMIC_API_STREAM_URL_READ,
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
                    url=CERAMIC_API_STREAM_URL_WRITE,
                ),
                response_kwargs=dict(
                    version="",
                    status_code=kwargs.get("write_data")["status"],
                    status_text="",
                    body=kwargs.get("write_data")["body"].encode(),
                ),
            )

        self.complete(test_case.event)

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path - Orbis - 200",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "op": "create",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                                "extra_metadata": {"family": "orbis"},
                            },
                        ],
                    ),
                    event=Event.DONE,
                ),
                {
                    "write_data": {
                        "body": json.dumps(
                            {"streamId": "dummy_stream_id"},
                        ),
                        "status": 200,
                        "headers": "Content-Type: application/json\r\nAccept: application/json\r\n",
                    },
                    "orbis_status": 200,
                },
            ),
            (
                BehaviourTestCase(
                    "Happy path - Orbis - 400",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "op": "create",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                                "extra_metadata": {"family": "orbis"},
                            },
                        ],
                    ),
                    event=Event.DONE,
                ),
                {
                    "write_data": {
                        "body": json.dumps(
                            {"streamId": "dummy_stream_id"},
                        ),
                        "status": 200,
                        "headers": "Content-Type: application/json\r\nAccept: application/json\r\n",
                    },
                    "orbis_status": 400,
                },
            ),
            (
                BehaviourTestCase(
                    "Happy path - no extra metadata",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "op": "create",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                            },
                        ],
                    ),
                    event=Event.DONE,
                ),
                {
                    "write_data": {
                        "body": json.dumps(
                            {"streamId": "dummy_stream_id"},
                        ),
                        "status": 200,
                        "headers": "Content-Type: application/json\r\nAccept: application/json\r\n",
                    },
                },
            ),
        ],
    )
    def test_create(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()

        # Write data call
        self.mock_http_request(
            request_kwargs=dict(
                method="POST",
                headers=kwargs.get("write_data")["headers"],
                version="",
                url=CERAMIC_API_STREAM_URL_CREATE,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("write_data")["status"],
                status_text="",
                body=kwargs.get("write_data")["body"].encode(),
            ),
        )

        # Orbis update
        if "extra_metadata" in test_case.initial_data["write_data"][0].keys():
            self.mock_http_request(
                request_kwargs=dict(
                    method="GET",
                    headers="Content-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n",
                    version="",
                    url="https://api.orbis.club/index-stream/mainnet/dummy_stream_id",
                ),
                response_kwargs=dict(
                    version="",
                    status_code=kwargs.get("orbis_status"),
                    status_text="",
                    body=json.dumps({}).encode(),
                ),
            )

        self.complete(test_case.event)

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Incorrect stream op",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "op": "wrong_op",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                                "extra_metadata": {"family": "orbis"},
                            },
                        ],
                    ),
                    event=Event.DONE,
                ),
                {
                    "write_data": {
                        "body": json.dumps(
                            {"streamId": "dummy_stream_id"},
                        ),
                        "status": 200,
                        "headers": "Content-Type: application/json\r\nAccept: application/json\r\n",
                    },
                },
            ),
        ],
    )
    def test_raises_no_op(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        with pytest.raises(
            AEAActException, match="Operation wrong_op is not supported"
        ):
            self.behaviour.act_wrapper()


class TestStreamWriteBehaviourNonSender(BaseCeramicWriteTest):
    """Tests StreamWriteBehaviour"""

    behaviour_class = StreamWriteBehaviour
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


class TestStreamWriteBehaviourApiError(BaseCeramicWriteTest):
    """Tests StreamWriteBehaviour"""

    behaviour_class = StreamWriteBehaviour
    next_behaviour_class = RandomnessCeramicBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API read error",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "stream_id": "dummy_stream_id",
                                "op": "update",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                            }
                        ],
                    ),
                    event=Event.API_ERROR,
                ),
                {
                    "read_data": {
                        "body": json.dumps(
                            DUMMY_API_RESPONSE_OK,
                        ),
                        "status": 404,
                        "headers": "",
                    },
                },
            ),
            (
                BehaviourTestCase(
                    "API write error",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "stream_id": "dummy_stream_id",
                                "op": "update",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                            }
                        ],
                    ),
                    event=Event.API_ERROR,
                ),
                {
                    "read_data": {
                        "body": json.dumps(
                            DUMMY_API_RESPONSE_OK,
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
                url=CERAMIC_API_STREAM_URL_READ,
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
                    url=CERAMIC_API_STREAM_URL_WRITE,
                ),
                response_kwargs=dict(
                    version="",
                    status_code=kwargs.get("write_data")["status"],
                    status_text="",
                    body=kwargs.get("write_data")["body"].encode(),
                ),
            )

        self.complete(test_case.event)

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API read error",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "op": "create",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                            }
                        ],
                    ),
                    event=Event.API_ERROR,
                ),
                {},
            ),
        ],
    )
    def test_create(self, test_case: BehaviourTestCase, kwargs: Any) -> None:
        """Run tests."""
        self.fast_forward(test_case.initial_data)
        self.behaviour.act_wrapper()

        self.mock_http_request(
            request_kwargs=dict(
                method="POST",
                headers="Content-Type: application/json\r\nAccept: application/json\r\n",
                version="",
                url=CERAMIC_API_STREAM_URL_CREATE,
            ),
            response_kwargs=dict(
                version="",
                status_code=400,
                status_text="",
                body="{}".encode(),
            ),
        )

        self.complete(test_case.event)


class TestStreamWriteBehaviourRetriesError(BaseCeramicWriteTest):
    """Tests StreamWriteBehaviour"""

    behaviour_class = StreamWriteBehaviour
    next_behaviour_class = make_degenerate_behaviour(FinishedMaxRetriesRound)

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API read error",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "stream_id": "dummy_stream_id",
                                "op": "update",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                            }
                        ],
                        api_retries=2,
                    ),
                    event=Event.MAX_RETRIES_ERROR,
                ),
                {
                    "read_data": {
                        "body": json.dumps(
                            DUMMY_API_RESPONSE_OK,
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
                url=CERAMIC_API_STREAM_URL_READ,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("read_data")["status"],
                status_text="",
                body=kwargs.get("read_data")["body"].encode(),
            ),
        )

        self.complete(test_case.event)


class TestVerificationBehaviour(BaseCeramicWriteTest):
    """Tests StreamWriteBehaviour"""

    behaviour_class = VerificationBehaviour
    next_behaviour_class = make_degenerate_behaviour(FinishedVerificationRound)

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "stream_id": "dummy_stream_id",
                                "op": "update",
                                "data": {
                                    "wallet_to_users": {},
                                    "user_to_total_points": {
                                        "user_a": 10,
                                        "user_b": 10,
                                    },
                                    "id_to_usernames": {},
                                    "latest_mention_tweet_id": 15,
                                },
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                            }
                        ],
                        stream_id_to_verify="dummy_stream_id",
                    ),
                    event=Event.DONE_FINISHED,
                ),
                {
                    "body": json.dumps(
                        DUMMY_API_RESPONSE_OK,
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
                url=CERAMIC_API_STREAM_URL_READ,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)


class TestVerificationBehaviourApiError(BaseCeramicWriteTest):
    """Tests StreamWriteBehaviour"""

    behaviour_class = VerificationBehaviour
    next_behaviour_class = RandomnessCeramicBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Api Error",
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "stream_id": "dummy_stream_id",
                                "op": "update",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                            }
                        ],
                        stream_id_to_verify="dummy_stream_id",
                    ),
                    event=Event.VERIFICATION_ERROR,
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
                    initial_data=dict(
                        most_voted_keeper_address="test_agent_address",
                        write_data=[
                            {
                                "stream_id": "dummy_stream_id",
                                "op": "update",
                                "data": "stream_content",
                                "did_str": DUMMY_DID,
                                "did_seed": DUMMY_DID_SEED,
                            }
                        ],
                        stream_id_to_verify="dummy_stream_id",
                    ),
                    event=Event.VERIFICATION_ERROR,
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
                url=CERAMIC_API_STREAM_URL_READ,
            ),
            response_kwargs=dict(
                version="",
                status_code=kwargs.get("status_code"),
                status_text="",
                body=kwargs.get("body").encode(),
            ),
        )
        self.complete(test_case.event)
