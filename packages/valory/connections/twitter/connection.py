#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2023 Valory AG
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
"""Scaffold connection and channel."""
import json
from typing import Any, Callable, cast

import tweepy
from aea.configurations.base import PublicId
from aea.connections.base import BaseSyncConnection
from aea.mail.base import Envelope
from aea.protocols.base import Address, Message
from aea.protocols.dialogue.base import Dialogue
from tweepy.errors import HTTPException as TweepyHTTPException

from packages.valory.protocols.twitter.dialogues import TwitterDialogue
from packages.valory.protocols.twitter.dialogues import (
    TwitterDialogues as BaseTwitterDialogues,
)
from packages.valory.protocols.twitter.message import TwitterMessage


PUBLIC_ID = PublicId.from_str("valory/twitter:0.1.0")


class TwitterDialogues(BaseTwitterDialogues):
    """A class to keep track of IPFS dialogues."""

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize dialogues.

        :param kwargs: keyword arguments
        """

        def role_from_first_message(  # pylint: disable=unused-argument
            message: Message, receiver_address: Address
        ) -> Dialogue.Role:
            """Infer the role of the agent from an incoming/outgoing first message

            :param message: an incoming/outgoing first message
            :param receiver_address: the address of the receiving agent
            :return: The role of the agent
            """
            return TwitterDialogue.Role.CONNECTION

        BaseTwitterDialogues.__init__(
            self,
            self_address=str(kwargs.pop("connection_id")),
            role_from_first_message=role_from_first_message,
            **kwargs,
        )


class TwitterConnection(BaseSyncConnection):
    """Proxy to the functionality of the SDK or API."""

    MAX_WORKER_THREADS = 5

    connection_id = PUBLIC_ID

    api: tweepy.API
    auth: tweepy.OAuthHandler

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        """
        Initialize the connection.

        The configuration must be specified if and only if the following
        parameters are None: connection_id, excluded_protocols or restricted_to_protocols.

        Possible arguments:
        - configuration: the connection configuration.
        - data_dir: directory where to put local files.
        - identity: the identity object held by the agent.
        - crypto_store: the crypto store for encrypted communication.
        - restricted_to_protocols: the set of protocols ids of the only supported protocols for this connection.
        - excluded_protocols: the set of protocols ids that we want to exclude for this connection.

        :param args: arguments passed to component base
        :param kwargs: keyword arguments passed to component base
        """
        super().__init__(*args, **kwargs)

        self.consumer_key = self.configuration.config["consumer_key"]
        self.consumer_secret = self.configuration.config["consumer_secret"]
        self.auth_token = self.configuration.config["auth_token"]
        self.access_secret = self.configuration.config["access_secret"]
        self.access_token = self.configuration.config["access_token"]

        self.dialogues = TwitterDialogues(connection_id=PUBLIC_ID)

    def main(self) -> None:
        """
        Run synchronous code in background.

        SyncConnection `main()` usage:
        The idea of the `main` method in the sync connection
        is to provide for a way to actively generate messages by the connection via the `put_envelope` method.

        A simple example is the generation of a message every second:
        ```
        while self.is_connected:
            envelope = make_envelope_for_current_time()
            self.put_enevelope(envelope)
            time.sleep(1)
        ```
        In this case, the connection will generate a message every second
        regardless of envelopes sent to the connection by the agent.
        For instance, this way one can implement periodically polling some internet resources
        and generate envelopes for the agent if some updates are available.
        Another example is the case where there is some framework that runs blocking
        code and provides a callback on some internal event.
        This blocking code can be executed in the main function and new envelops
        can be created in the event callback.
        """

    def on_send(self, envelope: Envelope) -> None:
        """
        Send an envelope.

        :param envelope: the envelope to send.
        """
        twitter_message = cast(TwitterMessage, envelope.message)
        dialogue = self.dialogues.update(twitter_message)

        if twitter_message.performative != TwitterMessage.Performative.CREATE_TWEET:
            self.logger.error(
                f"Performative `{twitter_message.performative.value}` is not supported."
            )
            return

        handler: Callable[[TwitterMessage, TwitterDialogue], TwitterMessage] = getattr(
            self, twitter_message.performative.value
        )
        response = handler(twitter_message, dialogue)
        response_envelope = Envelope(
            to=envelope.sender,
            sender=envelope.to,
            message=response,
            context=envelope.context,
        )
        self.put_envelope(response_envelope)

    def create_tweet(
        self,
        message: TwitterMessage,
        dialogue: TwitterDialogue,
    ) -> TwitterMessage:
        """Create a tweet and return tweet id."""
        # Temp hack: we need to update the connection and protocol
        data = json.loads(message.text)
        text = data["text"]
        credentials = data["credentials"]

        api = (
            self.api
            if not credentials
            else tweepy.Client(
                consumer_key=credentials["consumer_key"],
                consumer_secret=credentials["consumer_secret"],
                access_token=credentials["access_token"],
                access_token_secret=credentials["access_secret"],
            )
        )
        try:
            if isinstance(text, list):
                # Thread
                previous_tweet_id = None
                first_tweet_id = None
                for tweet in text:
                    if not previous_tweet_id:
                        response = api.create_tweet(text=tweet)
                        first_tweet_id = response.data["id"]
                    else:
                        response = api.create_tweet(text=tweet, in_reply_to_tweet_id=previous_tweet_id)
                    previous_tweet_id = response.data["id"]
            else:
                # Single tweet
                response = api.create_tweet(text=text)
                first_tweet_id = response.data["id"]

        except TweepyHTTPException as e:
            error = "; ".join(e.api_messages)
            return cast(
                TwitterMessage,
                dialogue.reply(
                    performative=TwitterMessage.Performative.ERROR,
                    target_message=message,
                    message=error,
                ),
            )

        return cast(
            TwitterMessage,
            dialogue.reply(
                performative=TwitterMessage.Performative.TWEET_CREATED,
                target_message=message,
                tweet_id=first_tweet_id,
            ),
        )

    def on_connect(self) -> None:
        """
        Tear down the connection.

        Connection status set automatically.
        """
        # authenticating to access the twitter API
        self.api = tweepy.Client(
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            access_token=self.access_token,
            access_token_secret=self.access_secret,
        )

    def on_disconnect(self) -> None:
        """
        Tear down the connection.

        Connection status set automatically.
        """
