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

"""Test the handlers.py module of the DynamicNFT skill."""

import datetime
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, cast
from unittest.mock import Mock, patch

import pytest
from aea.protocols.dialogue.base import DialogueMessage
from aea.test_tools.test_skill import BaseSkillTestCase

from packages.fetchai.connections.http_server.connection import (
    PUBLIC_ID as HTTP_SERVER_PUBLIC_ID,
)
from packages.valory.protocols.http.message import HttpMessage
from packages.valory.skills.abstract_round_abci.base import AbciAppDB
from packages.valory.skills.dynamic_nft_abci.dialogues import HttpDialogues
from packages.valory.skills.dynamic_nft_abci.handlers import (
    BAD_REQUEST_CODE,
    HttpHandler,
    NOT_FOUND_CODE,
    OK_CODE,
)


PACKAGE_DIR = Path(__file__).parent.parent

HTTP_SERVER_SENDER = str(HTTP_SERVER_PUBLIC_ID.without_hash())

TOKEN_URI_BASE = "https://pfp.staging.autonolas.tech/"  # nosec


def get_dummy_metadata(token_id, image_hash, points=10):
    """Get the dummy token metadata"""
    return {
        "title": "Autonolas Contribute Badges",
        "name": f"Badge {token_id}",
        "description": "This NFT recognizes the contributions made by the holder to the Autonolas Community.",
        "image": f"ipfs://{image_hash}",
        "attributes": [
            {"trait_type": "Score", "value": points},
            {
                "trait_type": "Level",
                "value": "Idle",
            },
        ],
    }


def get_dummy_health(time_updated: bool = True):
    """Get the dummy health data"""
    return {
        "seconds_since_last_reset": 5.0 if time_updated else None,
        "healthy": True if time_updated else None,
        "seconds_until_next_update": 15.0 if time_updated else None,
        "period": 0,
    }


@dataclass
class HandlerTestCase:
    """HandlerTestCase"""

    name: str
    request_url: str
    request_body: bytes
    token_id_to_points: Dict[str, int]
    response_status_code: int
    response_status_text: str
    response_headers: str
    response_body: bytes
    method: str
    n_outbox_msgs: int
    set_last_update_time: bool = True


class TestHttpHandler(BaseSkillTestCase):
    """Test HttpHandler of http_echo."""

    path_to_skill = PACKAGE_DIR

    @classmethod
    def setup_class(cls):
        """Setup the test class."""
        super().setup_class()
        cls.http_handler = cast(HttpHandler, cls._skill.skill_context.handlers.http)
        cls.logger = cls._skill.skill_context.logger

        cls.http_dialogues = cast(
            HttpDialogues, cls._skill.skill_context.http_dialogues
        )

        cls.get_method = "get"
        cls.post_method = "post"
        cls.url = f"{TOKEN_URI_BASE}0"
        cls.version = "some_version"
        cls.headers = "some_headers"
        cls.body = b"some_body/"
        cls.sender = HTTP_SERVER_SENDER
        cls.skill_id = str(cls._skill.skill_context.skill_id)

        cls.status_code = 100
        cls.status_text = "some_status_text"

        cls.content = b"some_content"
        cls.list_of_messages = (
            DialogueMessage(
                HttpMessage.Performative.REQUEST,
                {
                    "method": cls.get_method,
                    "url": cls.url,
                    "version": cls.version,
                    "headers": cls.headers,
                    "body": cls.body,
                },
            ),
        )

    def setup(self) -> None:
        """Setup"""
        self.http_handler.setup()

    def test_setup(self):
        """Test the setup method of the handler."""
        assert self.http_handler.setup() is None
        self.assert_quantity_in_outbox(0)

    def test_handle_unidentified_dialogue(self):
        """Test the _handle_unidentified_dialogue method of the handler."""
        # setup
        incorrect_dialogue_reference = ("", "")
        incoming_message = self.build_incoming_message(
            message_type=HttpMessage,
            dialogue_reference=incorrect_dialogue_reference,
            performative=HttpMessage.Performative.REQUEST,
            to=self.skill_id,
            method=self.get_method,
            url=self.url,
            version=self.version,
            headers=self.headers,
            body=self.body,
            sender=HTTP_SERVER_SENDER,
        )

        # operation
        with patch.object(self.logger, "log") as mock_logger:
            self.http_handler.handle(incoming_message)

        # after
        mock_logger.assert_any_call(
            logging.INFO,
            f"Received invalid http message={incoming_message}, unidentified dialogue.",
        )

    @pytest.mark.parametrize(
        "test_case",
        [
            HandlerTestCase(
                name="id in token table",
                request_url=f"{TOKEN_URI_BASE}0",
                token_id_to_points={
                    "0": 10,
                },
                request_body=b"some_body/",
                response_status_code=OK_CODE,
                response_status_text="Success",
                response_headers="Content-Type: application/json\nsome_headers",
                response_body=json.dumps(
                    get_dummy_metadata(
                        0, "bafybeiabtdl53v2a3irrgrg7eujzffjallpymli763wvhv6gceurfmcemm"
                    )
                ).encode("utf-8"),
                method="get",
                n_outbox_msgs=1,
            ),
            HandlerTestCase(
                name="id in token table, no threshold match",
                request_url=f"{TOKEN_URI_BASE}0",
                token_id_to_points={"0": -10},
                request_body=b"some_body/",
                response_status_code=OK_CODE,
                response_status_text="Success",
                response_headers="Content-Type: application/json\nsome_headers",
                response_body=json.dumps(
                    get_dummy_metadata(
                        0,
                        "bafybeiabtdl53v2a3irrgrg7eujzffjallpymli763wvhv6gceurfmcemm",
                        -10,
                    )
                ).encode("utf-8"),
                method="get",
                n_outbox_msgs=1,
            ),
            HandlerTestCase(
                name="id not in token table",
                request_url=f"{TOKEN_URI_BASE}1",
                token_id_to_points={},
                request_body=b"some_body/",
                response_status_code=NOT_FOUND_CODE,
                response_status_text="Not found",
                response_headers="some_headers",
                response_body=b"",
                method="get",
                n_outbox_msgs=1,
            ),
            HandlerTestCase(
                name="healthcheck",
                request_url=f"{TOKEN_URI_BASE}healthcheck",
                token_id_to_points={},
                request_body=b"some_body/",
                response_status_code=OK_CODE,
                response_status_text="Success",
                response_headers="Content-Type: application/json\nsome_headers",
                response_body=json.dumps(get_dummy_health()).encode("utf-8"),
                method="get",
                n_outbox_msgs=1,
            ),
            HandlerTestCase(
                name="healthcheck_time_not_updated_yet",
                request_url=f"{TOKEN_URI_BASE}healthcheck",
                token_id_to_points={},
                request_body=b"some_body/",
                response_status_code=OK_CODE,
                response_status_text="Success",
                response_headers="Content-Type: application/json\nsome_headers",
                response_body=json.dumps(get_dummy_health(time_updated=False)).encode(
                    "utf-8"
                ),
                method="get",
                n_outbox_msgs=1,
                set_last_update_time=False,
            ),
            HandlerTestCase(
                name="no-handler",
                request_url="wrong_uri",
                token_id_to_points={},
                request_body=b"some_body/",
                response_status_code=BAD_REQUEST_CODE,
                response_status_text="Bad request",
                response_headers="some_headers",
                response_body=b"",
                method="get",
                n_outbox_msgs=0,
            ),
        ],
    )
    def test_handle_request_get(self, test_case):
        """Test the _handle_request method of the handler where method is get."""
        # setup
        incoming_message = cast(
            HttpMessage,
            self.build_incoming_message(
                message_type=HttpMessage,
                performative=HttpMessage.Performative.REQUEST,
                to=self.skill_id,
                sender=self.sender,
                method=test_case.method,
                url=test_case.request_url,
                version=self.version,
                headers=self.headers,
                body=test_case.request_body,
            ),
        )

        # operation
        with patch.object(self.logger, "log") as mock_logger, patch.object(
            self.http_handler.context.state, "_round_sequence"
        ) as mock_round_sequence:
            mock_now_time = datetime.datetime(2022, 1, 1)
            mock_now_time_timestamp = mock_now_time.timestamp()
            abci_app_db = AbciAppDB(
                {
                    "token_id_to_points": [test_case.token_id_to_points],
                    "last_update_time": [
                        mock_now_time_timestamp - 5.0
                    ]  # 5 seconds before
                    if test_case.set_last_update_time
                    else [None],
                }
            )
            mock_round_sequence.latest_synchronized_data.db = abci_app_db
            mock_round_sequence.block_stall_deadline_expired = False

            datetime_mock = Mock(wraps=datetime.datetime)
            datetime_mock.now.return_value = mock_now_time

            with patch("datetime.datetime", new=datetime_mock):
                self.http_handler.handle(incoming_message)

        # after
        self.assert_quantity_in_outbox(test_case.n_outbox_msgs)

        if test_case.n_outbox_msgs > 0:

            mock_logger.assert_any_call(
                logging.INFO,
                "Received http request with method={}, url={} and body={!r}".format(
                    incoming_message.method, incoming_message.url, incoming_message.body
                ),
            )

            # _handle_get
            message = self.get_message_from_outbox()
            has_attributes, error_str = self.message_has_attributes(
                actual_message=message,
                message_type=HttpMessage,
                performative=HttpMessage.Performative.RESPONSE,
                to=incoming_message.sender,
                sender=incoming_message.to,
                version=incoming_message.version,
                status_code=test_case.response_status_code,
                status_text=test_case.response_status_text,
                headers=test_case.response_headers,
                body=test_case.response_body,
            )
            assert has_attributes, error_str

            mock_logger.assert_any_call(
                logging.INFO,
                f"Responding with: {message}",
            )

    def test_handle_request_post(self):
        """Test the _handle_request method of the handler where method is post."""
        # setup
        incoming_message = cast(
            HttpMessage,
            self.build_incoming_message(
                message_type=HttpMessage,
                performative=HttpMessage.Performative.REQUEST,
                to=self.skill_id,
                sender=self.sender,
                method=self.post_method,
                url=self.url,
                version=self.version,
                headers=self.headers,
                body=self.body,
            ),
        )

        # operation
        with patch.object(self.logger, "log") as mock_logger:
            self.http_handler.handle(incoming_message)

        # after
        self.assert_quantity_in_outbox(1)

        mock_logger.assert_any_call(
            logging.INFO,
            "Received http request with method={}, url={} and body={!r}".format(
                incoming_message.method, incoming_message.url, incoming_message.body
            ),
        )

        # _handle_non_get
        message = self.get_message_from_outbox()
        has_attributes, error_str = self.message_has_attributes(
            actual_message=message,
            message_type=HttpMessage,
            performative=HttpMessage.Performative.RESPONSE,
            to=incoming_message.sender,
            sender=incoming_message.to,
            version=incoming_message.version,
            status_code=BAD_REQUEST_CODE,
            status_text="Bad request",
            headers=incoming_message.headers,
            body=b"",
        )
        assert has_attributes, error_str

        mock_logger.assert_any_call(
            logging.INFO,
            f"Responding with: {message}",
        )

    def test_teardown(self):
        """Test the teardown method of the handler."""
        assert self.http_handler.teardown() is None
        self.assert_quantity_in_outbox(0)

    @pytest.mark.parametrize(
        "url, method, expected_handler_name",
        [
            ("wrong_url", "get", None),
            (
                "http://pfp.staging.autonolas.tech/healthcheck",
                "get",
                "_handle_get_health",
            ),
            (
                "http://pfp.staging.autonolas.tech/healt-hcheck",
                "get",
                "_handle_bad_request",
            ),
            ("http://pfp.staging.autonolas.tech/1", "get", "_handle_get_metadata"),
            ("http://pfp.staging.autonolas.tech/999", "get", "_handle_get_metadata"),
            ("http://pfp.staging.autonolas.tech/-999", "get", "_handle_bad_request"),
            (
                "https://b1f305361a323839.agent.propel.staging.autonolas.tech/1",
                "get",
                "_handle_get_metadata",
            ),
            (
                "http://b1f305361a323839.agent.propel.staging.autonolas.tech/1",
                "get",
                "_handle_get_metadata",
            ),
            (
                "https://b72085557196153b.agent.propel.autonolas.tech/1",
                "get",
                "_handle_get_metadata",
            ),
            (
                "http://b72085557196153b.agent.propel.autonolas.tech/1",
                "get",
                "_handle_get_metadata",
            ),
        ],
    )
    def test_get_handler(self, url, method, expected_handler_name):
        """Test check_url"""
        expected_handler = (
            getattr(self.http_handler, expected_handler_name)
            if expected_handler_name
            else None
        )
        actual_handler, _ = self.http_handler._get_handler(url, method)
        assert (
            actual_handler == expected_handler
        ), f"Wrong value for {url}. Expected {expected_handler}, got {actual_handler}"
