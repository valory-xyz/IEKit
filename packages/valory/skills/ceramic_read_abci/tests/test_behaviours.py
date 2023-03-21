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

"""This package contains round behaviours of CeramicReadAbciApp."""

from pathlib import Path
from typing import Any, Dict, Hashable, Optional, Type
from dataclasses import dataclass, field
import json
import pytest

from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
    make_degenerate_behaviour,
)
from packages.valory.skills.ceramic_read_abci.behaviours import (
    CeramicReadBaseBehaviour,
    CeramicReadRoundBehaviour,
    StreamReadBehaviour,
)
from packages.valory.skills.ceramic_read_abci.rounds import (
    SynchronizedData,
    DegenerateRound,
    Event,
    CeramicReadAbciApp,
    FinishedReadingRound,
    StreamReadRound,
)

from packages.valory.skills.abstract_round_abci.test_tools.base import (
    FSMBehaviourBaseCase,
)

CERAMIC_API_STREAM_URL_READ = (
    "https://ceramic-clay.3boxlabs.com/api/v0/commits/dummy_stream_id"
)

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
    next_behaviour_class: Optional[Type[CeramicReadBaseBehaviour]] = None


class BaseCeramicReadTest(FSMBehaviourBaseCase):
    """Base test case."""

    path_to_skill = Path(__file__).parent.parent

    behaviour: CeramicReadRoundBehaviour
    behaviour_class: Type[CeramicReadBaseBehaviour]
    next_behaviour_class: Type[CeramicReadBaseBehaviour]
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


class TestStreamReadBehaviour(BaseCeramicReadTest):
    """Tests StreamReadBehaviour"""

    behaviour_class = StreamReadBehaviour
    next_behaviour_class = make_degenerate_behaviour(FinishedReadingRound)

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "Happy path",
                    initial_data=dict(
                        stream_id="dummy_stream_id",
                        target_property_name="dummy_property_name",
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
                },
            ),
            (
                BehaviourTestCase(
                    "Json decode error",
                    initial_data=dict(
                        stream_id="dummy_stream_id",
                        target_property_name="dummy_property_name",
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

        self.complete(test_case.event)



class TestStreamReadBehaviourApiError(BaseCeramicReadTest):
    """Tests StreamReadBehaviour"""

    behaviour_class = StreamReadBehaviour
    next_behaviour_class = StreamReadBehaviour

    @pytest.mark.parametrize(
        "test_case, kwargs",
        [
            (
                BehaviourTestCase(
                    "API read error",
                    initial_data=dict(
                        stream_id="dummy_stream_id",
                        target_property_name="dummy_property_name",
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