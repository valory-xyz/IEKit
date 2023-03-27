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

"""This module contains the handlers for the skill of DynamicNFTAbciApp."""

import datetime
import json
import re
from enum import Enum
from typing import Callable, Dict, Optional, Tuple, cast
from urllib.parse import urlparse

from aea.protocols.base import Message

from packages.fetchai.connections.http_server.connection import (
    PUBLIC_ID as HTTP_SERVER_PUBLIC_ID,
)
from packages.valory.protocols.http.message import HttpMessage
from packages.valory.skills.abstract_round_abci.handlers import (
    ABCIRoundHandler as BaseABCIRoundHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    ContractApiHandler as BaseContractApiHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    HttpHandler as BaseHttpHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    IpfsHandler as BaseIpfsHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    LedgerApiHandler as BaseLedgerApiHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    SigningHandler as BaseSigningHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    TendermintHandler as BaseTendermintHandler,
)
from packages.valory.skills.dynamic_nft_abci.dialogues import (
    HttpDialogue,
    HttpDialogues,
)
from packages.valory.skills.dynamic_nft_abci.models import SharedState
from packages.valory.skills.dynamic_nft_abci.rounds import SynchronizedData


ABCIRoundHandler = BaseABCIRoundHandler
SigningHandler = BaseSigningHandler
LedgerApiHandler = BaseLedgerApiHandler
ContractApiHandler = BaseContractApiHandler
TendermintHandler = BaseTendermintHandler
IpfsHandler = BaseIpfsHandler

OK_CODE = 200
NOT_FOUND_CODE = 404
BAD_REQUEST_CODE = 400
AVERAGE_PERIOD_SECONDS = 10
DISCORD_ID_REGEX = r"^\d{16,20}$"

BADGE_LEVELS = {
    "Idle": 100,
    "Basic": 50000,
    "Legendary": 100000,
    "Epic": 150000,
    "Super Epic": None,
}


class HttpMethod(Enum):
    """Http methods"""

    GET = "get"
    HEAD = "head"
    POST = "post"


class HttpHandler(BaseHttpHandler):
    """This implements the echo handler."""

    SUPPORTED_PROTOCOL = HttpMessage.protocol_id

    def setup(self) -> None:
        """Implement the setup."""
        uri_base_hostname = urlparse(self.context.params.token_uri_base).hostname

        # Route regexes
        hostname_regex = rf".*({uri_base_hostname}|localhost|127.0.0.1)(:\d+)?"
        self.handler_url_regex = rf"{hostname_regex}\/.*"
        metadata_url_regex = rf"{hostname_regex}\/\d+"
        health_url_regex = rf"{hostname_regex}\/healthcheck"

        # Routes
        self.routes = {
            (HttpMethod.GET.value, HttpMethod.HEAD.value): [
                (metadata_url_regex, self._handle_get_metadata),
                (health_url_regex, self._handle_get_health),
            ],
        }

        self.json_content_header = "Content-Type: application/json\n"

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return SynchronizedData(
            db=self.context.state.round_sequence.latest_synchronized_data.db
        )

    def _get_handler(self, url: str, method: str) -> Tuple[Optional[Callable], Dict]:
        """Check if an url is meant to be handled in this handler

        We expect url to match the pattern {hostname}/.*,
        where hostname is allowed to be localhost, 127.0.0.1 or the token_uri_base's hostname.
        Examples:
            localhost:8000/0
            127.0.0.1:8000/100
            https://pfp.staging.autonolas.tech/45
            http://pfp.staging.autonolas.tech/120

        :param url: the url to check
        :returns: the handling method if the message is intended to be handled by this handler, None otherwise, and the regex captures
        """
        # Check base url
        if not re.match(self.handler_url_regex, url):
            self.context.logger.info(
                f"The url {url} does not match the DynamicNFT HttpHandler's pattern"
            )
            return None, {}

        # Check if there is a route for this request
        for methods, routes in self.routes.items():
            if method not in methods:
                continue

            for route in routes:
                # Routes are tuples like (route_regex, handle_method)
                m = re.match(route[0], url)
                if m:
                    return route[1], m.groupdict()

        # No route found
        self.context.logger.info(
            f"The message [{method}] {url} is intended for the DynamicNFT HttpHandler but did not match any valid pattern"
        )
        return self._handle_bad_request, {}

    def handle(self, message: Message) -> None:
        """
        Implement the reaction to an envelope.

        :param message: the message
        """
        http_msg = cast(HttpMessage, message)

        # Check if this is a request sent from the http_server skill
        if (
            http_msg.performative != HttpMessage.Performative.REQUEST
            or message.sender != str(HTTP_SERVER_PUBLIC_ID.without_hash())
        ):
            super().handle(message)
            return

        # Check if this message is for this skill. If not, send to super()
        handler, kwargs = self._get_handler(http_msg.url, http_msg.method)
        if not handler:
            super().handle(message)
            return

        # Retrieve dialogues
        http_dialogues = cast(HttpDialogues, self.context.http_dialogues)
        http_dialogue = cast(HttpDialogue, http_dialogues.update(http_msg))

        # Invalid message
        if http_dialogue is None:
            self.context.logger.info(
                "Received invalid http message={}, unidentified dialogue.".format(
                    http_msg
                )
            )
            return

        # Handle message
        self.context.logger.info(
            "Received http request with method={}, url={} and body={!r}".format(
                http_msg.method,
                http_msg.url,
                http_msg.body,
            )
        )
        handler(http_msg, http_dialogue, **kwargs)

    def _handle_bad_request(
        self, http_msg: HttpMessage, http_dialogue: HttpDialogue
    ) -> None:
        """
        Handle a Http bad request.

        :param http_msg: the http message
        :param http_dialogue: the http dialogue
        """
        http_response = http_dialogue.reply(
            performative=HttpMessage.Performative.RESPONSE,
            target_message=http_msg,
            version=http_msg.version,
            status_code=BAD_REQUEST_CODE,
            status_text="Bad request",
            headers=http_msg.headers,
            body=b"",
        )

        # Send response
        self.context.logger.info("Responding with: {}".format(http_response))
        self.context.outbox.put_message(message=http_response)

    def get_image_hash(self, points) -> str:
        """Get the image hash given the score"""

        # Get the threshold in decreasing order
        thresholds = sorted(
            [int(i) for i in self.context.params.points_to_image_hashes.keys()],
            reverse=True,
        )
        for t in thresholds:
            if points >= t:
                return self.context.params.points_to_image_hashes[str(t)]

        # If there was not match, return the lowest threshold image
        return self.context.params.points_to_image_hashes[str(thresholds[-1])]

    def _handle_get_metadata(
        self, http_msg: HttpMessage, http_dialogue: HttpDialogue
    ) -> None:
        """
        Handle the metadata Http request.

        :param http_msg: the http message
        :param http_dialogue: the http dialogue
        """
        # Get the requested uri and the token table
        request_uri = http_msg.url
        token_id = str(request_uri.split("/")[-1])
        token_id_to_points = self.synchronized_data.token_id_to_points

        if token_id not in token_id_to_points:
            self.context.logger.info(
                f"Requested URL {request_uri} is not present in token table"
            )
            self._send_not_found_response(http_msg, http_dialogue)
            return

        self.context.logger.info(
            f"Requested URL {request_uri} is present in token table"
        )

        # Attributes
        user_points = token_id_to_points[token_id]
        image_hash = self.get_image_hash(user_points)
        user_level = None
        for level, threshold in BADGE_LEVELS.items():
            if not threshold or user_points < threshold:
                user_level = level
                break

        # Build token metadata
        metadata = {
            "title": "Autonolas Contribute Badges",
            "name": f"Badge {token_id}",
            "description": "This NFT recognizes the contributions made by the holder to the Autonolas Community.",
            "image": f"ipfs://{image_hash}",
            "attributes": [
                {"trait_type": "Score", "value": user_points},
                {
                    "trait_type": "Level",
                    "value": user_level,
                },
            ],
        }

        self.context.logger.info(f"Responding with token metadata={metadata}")
        self._send_ok_response(http_msg, http_dialogue, metadata)

    def _handle_get_health(
        self, http_msg: HttpMessage, http_dialogue: HttpDialogue
    ) -> None:
        """
        Handle a Http request of verb GET.

        :param http_msg: the http message
        :param http_dialogue: the http dialogue
        """
        last_update_time = self.synchronized_data.last_update_time

        if last_update_time:
            is_tm_unhealthy = cast(
                SharedState, self.context.state
            ).round_sequence.block_stall_deadline_expired

            current_time = datetime.datetime.now().timestamp()

            reset_pause_duration = self.context.params.reset_pause_duration

            seconds_since_last_reset = current_time - last_update_time
            seconds_until_next_update = (
                AVERAGE_PERIOD_SECONDS + reset_pause_duration - seconds_since_last_reset
            )  # this can be negative if we have passed the estimated reset time without resetting

            is_healthy = all(
                [
                    seconds_since_last_reset < 2 * reset_pause_duration,
                    not is_tm_unhealthy,
                ]
            )

        else:
            seconds_since_last_reset = None
            is_healthy = None
            seconds_until_next_update = None

        data = {
            "seconds_since_last_reset": seconds_since_last_reset,
            "healthy": is_healthy,
            "seconds_until_next_update": seconds_until_next_update,
        }

        self._send_ok_response(http_msg, http_dialogue, data)

    def _send_ok_response(
        self, http_msg: HttpMessage, http_dialogue: HttpDialogue, data: Dict
    ) -> None:
        """Send an OK response with the provided data"""
        http_response = http_dialogue.reply(
            performative=HttpMessage.Performative.RESPONSE,
            target_message=http_msg,
            version=http_msg.version,
            status_code=OK_CODE,
            status_text="Success",
            headers=f"{self.json_content_header}{http_msg.headers}",
            body=json.dumps(data).encode("utf-8"),
        )

        # Send response
        self.context.logger.info("Responding with: {}".format(http_response))
        self.context.outbox.put_message(message=http_response)

    def _send_not_found_response(
        self, http_msg: HttpMessage, http_dialogue: HttpDialogue
    ) -> None:
        """Send an not found response"""
        http_response = http_dialogue.reply(
            performative=HttpMessage.Performative.RESPONSE,
            target_message=http_msg,
            version=http_msg.version,
            status_code=NOT_FOUND_CODE,
            status_text="Not found",
            headers=http_msg.headers,
            body=b"",
        )
        # Send response
        self.context.logger.info("Responding with: {}".format(http_response))
        self.context.outbox.put_message(message=http_response)
