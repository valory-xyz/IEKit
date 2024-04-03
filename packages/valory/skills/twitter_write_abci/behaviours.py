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

"""This package contains round behaviours of TwitterWriteAbciApp."""

import json
from abc import ABC
from typing import Generator, List, Optional, Set, Type, cast

from packages.valory.connections.twitter.connection import (
    PUBLIC_ID as TWITTER_CONNECTION_PUBLIC_ID,
)
from packages.valory.protocols.twitter.message import TwitterMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.abstract_round_abci.common import (
    RandomnessBehaviour,
    SelectKeeperBehaviour,
)
from packages.valory.skills.abstract_round_abci.models import Requests
from packages.valory.skills.twitter_write_abci.dialogues import (
    TwitterDialogue,
    TwitterDialogues,
)
from packages.valory.skills.twitter_write_abci.models import Params
from packages.valory.skills.twitter_write_abci.payloads import TwitterWritePayload
from packages.valory.skills.twitter_write_abci.rounds import (
    RandomnessPayload,
    RandomnessTwitterRound,
    SelectKeeperPayload,
    SelectKeeperTwitterRound,
    SynchronizedData,
    TwitterWriteAbciApp,
    TwitterWriteRound,
)


class BaseTwitterWriteBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


class RandomnessTwitterWriteBehaviour(RandomnessBehaviour, BaseTwitterWriteBehaviour):
    """Retrieve randomness."""

    matching_round = RandomnessTwitterRound
    payload_class = RandomnessPayload


class SelectKeeperTwitterWriteBehaviour(
    SelectKeeperBehaviour, BaseTwitterWriteBehaviour
):
    """Select the keeper agent."""

    matching_round = SelectKeeperTwitterRound
    payload_class = SelectKeeperPayload


class TwitterWriteBehaviour(BaseTwitterWriteBehaviour):
    """TwitterWriteBehaviour"""

    matching_round: Type[AbstractRound] = TwitterWriteRound

    def _i_am_tweeting(self) -> bool:
        """Indicates if the current agent is tweeting or not."""
        return (
            self.context.agent_address
            == self.synchronized_data.most_voted_keeper_address
        )

    def async_act(self) -> Generator[None, None, None]:
        """Do the action"""
        if self._i_am_tweeting():
            yield from self._tweet()
        else:
            yield from self._wait_for_tweet()

    def _wait_for_tweet(self) -> Generator:
        """Do the non-sender action."""
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            self.context.logger.info(
                f"Waiting for the keeper to do its keeping: {self.synchronized_data.most_voted_keeper_address}"
            )
            yield from self.wait_until_round_end()
        self.set_done()

    def _tweet(self) -> Generator:
        """Do the sender action"""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            write_index = self.synchronized_data.write_index
            data = self.synchronized_data.write_data[write_index]
            text = data["text"]
            credentials = data["credentials"]
            media_hashes = data.get("media_hashes", None)
            self.context.logger.info(f"Creating post with text: {text}")
            response = yield from self._create_tweet(
                text=text, credentials=credentials, media_hashes=media_hashes
            )
            if response.performative == TwitterMessage.Performative.ERROR:
                self.context.logger.error(
                    f"Writing post failed with following error message: {response.message}"
                )
                payload_data = {"success": False, "tweet_id": None}
            else:
                self.context.logger.info(f"Posted tweet with ID: {response.tweet_id}")
                payload_data = {"success": True, "tweet_id": response.tweet_id}

            payload = TwitterWritePayload(
                sender=self.context.agent_address,
                content=json.dumps(
                    payload_data,
                    sort_keys=True,
                ),
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _create_tweet(
        self,
        text: str,
        credentials: dict,
        media_hashes: Optional[List] = None,
    ) -> Generator[None, None, TwitterMessage]:
        """Send an http request message from the skill context."""
        twitter_dialogues = cast(TwitterDialogues, self.context.twitter_dialogues)
        twitter_message, twitter_dialogue = twitter_dialogues.create(
            counterparty=str(TWITTER_CONNECTION_PUBLIC_ID),
            performative=TwitterMessage.Performative.CREATE_TWEET,
            text=json.dumps(
                {"text": text, "credentials": credentials, "media_hashes": media_hashes}
            ),  # temp hack: we need to update the connection and protocol
        )
        twitter_message = cast(TwitterMessage, twitter_message)
        twitter_dialogue = cast(TwitterDialogue, twitter_dialogue)
        response = yield from self._do_twitter_request(
            twitter_message, twitter_dialogue
        )
        return response

    def _do_twitter_request(
        self,
        message: TwitterMessage,
        dialogue: TwitterDialogue,
        timeout: Optional[float] = None,
    ) -> Generator[None, None, TwitterMessage]:
        """Do a request and wait the response, asynchronously."""

        self.context.outbox.put_message(message=message)
        request_nonce = self._get_request_nonce_from_dialogue(dialogue)
        cast(Requests, self.context.requests).request_id_to_callback[
            request_nonce
        ] = self.get_callback_request()
        response = yield from self.wait_for_message(timeout=timeout)
        return response


class TwitterWriteRoundBehaviour(AbstractRoundBehaviour):
    """TwitterWriteRoundBehaviour"""

    initial_behaviour_cls = RandomnessTwitterWriteBehaviour
    abci_app_cls = TwitterWriteAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        RandomnessTwitterWriteBehaviour,
        SelectKeeperTwitterWriteBehaviour,
        TwitterWriteBehaviour,
    ]
