#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2024 Valory AG
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
import os
from pathlib import Path
from typing import Any, Callable, List, Optional, cast

import requests
import tweepy
from aea.configurations.base import PublicId
from aea.connections.base import BaseSyncConnection
from aea.mail.base import Envelope
from aea.protocols.base import Address, Message
from aea.protocols.dialogue.base import Dialogue
from aea_cli_ipfs.ipfs_utils import IPFSTool
from tweepy.errors import HTTPException as TweepyHTTPException

from packages.valory.protocols.twitter.dialogues import TwitterDialogue
from packages.valory.protocols.twitter.dialogues import (
    TwitterDialogues as BaseTwitterDialogues,
)
from packages.valory.protocols.twitter.message import TwitterMessage


PUBLIC_ID = PublicId.from_str("valory/twitter:0.1.0")
MEDIA_DIR = "/tmp"   # nosec

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
        self.use_twitter_staging_api = self.configuration.config["use_twitter_staging_api"]
        self.staging_api = self.configuration.config["twitter_staging_api"]
        self.ipfs_tool = IPFSTool()
        self.twitter_cli = None
        self.twitter_api = None

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
        tweet = data["text"]
        thread_media_hashes = data.get("media_hashes", None)
        credentials = data["credentials"]

        # Set up the client and api
        twitter_cli = self.twitter_cli
        twitter_api = self.twitter_api

        if credentials:
            twitter_cli = tweepy.Client(
                consumer_key=credentials["consumer_key"],
                consumer_secret=credentials["consumer_secret"],
                access_token=credentials["access_token"],
                access_token_secret=credentials["access_secret"],
            )

            auth = tweepy.OAuth1UserHandler(
                consumer_key=credentials["consumer_key"],
                consumer_secret=credentials["consumer_secret"],
                access_token=credentials["access_token"],
                access_token_secret=credentials["access_secret"],
            )
            twitter_api = tweepy.API(auth)


        # Process media
        thread_media_ids = self.process_media(thread_media_hashes, twitter_api)
        self.logger.info(f"Processed media ids: {thread_media_ids}")

        # Call the staging API
        if self.use_twitter_staging_api:
            url = f"{self.staging_api}/twitter/create_tweet"

            self.logger.info(
                f"Posting tweet using the staging API {url}"
            )

            try:
                if isinstance(tweet, list):
                    # Thread
                    first_tweet_id = None
                    for text in tweet:
                        response = requests.post(
                            url,
                            json={
                                "user_name": "staging_contribute",
                                "text": text
                            },
                            timeout=10
                        )

                        if not first_tweet_id:
                            first_tweet_id = response.json()["tweet_id"]
                else:
                    # Single tweet
                    response = requests.post(
                        url,
                        json={
                            "user_name": "staging_contribute",
                            "text": tweet
                        },
                        timeout=10
                    )
                    first_tweet_id = response.json()["tweet_id"]

            except requests.exceptions.ConnectionError as error:
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
                    tweet_id=str(first_tweet_id),
                ),
            )

        # Call the Twitter API
        self.logger.info(
            "Posting tweet using tweepy"
        )

        try:
            if isinstance(tweet, list):
                # Thread
                previous_tweet_id = None
                first_tweet_id = None
                for i, text in enumerate(tweet):
                    tweet_kwargs = {}

                    if text:
                        tweet_kwargs["text"] = text

                    if thread_media_ids and thread_media_ids[i]:
                        tweet_kwargs["media_ids"] = thread_media_ids[i]

                    if not previous_tweet_id:
                        self.logger.info(f"Tweepy kwargs: {tweet_kwargs}")
                        response = twitter_cli.create_tweet(**tweet_kwargs)
                        first_tweet_id = response.data["id"]
                    else:
                        tweet_kwargs["in_reply_to_tweet_id"] = previous_tweet_id
                        self.logger.info(f"Tweepy kwargs: {tweet_kwargs}")
                        response = twitter_cli.create_tweet(**tweet_kwargs)
                    previous_tweet_id = response.data["id"]
            else:
                # Single tweet
                tweet_kwargs = {}
                if tweet:
                    tweet_kwargs["text"] = tweet
                if thread_media_ids and thread_media_ids[0]:
                    tweet_kwargs["media_ids"] = thread_media_ids[0]
                self.logger.info(f"Tweepy kwargs: {tweet_kwargs}")
                response = twitter_cli.create_tweet(**tweet_kwargs)
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
        self.twitter_cli = tweepy.Client(
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            access_token=self.access_token,
            access_token_secret=self.access_secret,
        )

        auth = tweepy.OAuth1UserHandler(
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            access_token=self.access_token,
            access_token_secret=self.access_secret,
        )
        self.twitter_api = tweepy.API(auth)

    def on_disconnect(self) -> None:
        """
        Tear down the connection.

        Connection status set automatically.
        """


    def process_media(self, thread_media_hashes: Optional[List], twitter_api) -> Optional[List]:
        """Process tweet media"""
        thread_media_ids = []
        self.logger.info(f"Processing media: {thread_media_hashes}")

        # Media hashes is always a list of lists
        # Each tweet can contain several media items
        # A thread can contain several tweets
        # media_hashes = [[], [hashes_for_tweet_2], [], [hashes_for_tweet_4]]
        if not thread_media_hashes:
            return None

        for tweet_media_hashes in thread_media_hashes:

            tweet_media_ids = []

            if not isinstance(tweet_media_hashes, list):
                self.logger.error(
                    f"Hash list is not a list: {tweet_media_hashes}. Skipping tweet media..."
                )
                thread_media_ids.append(tweet_media_ids)
                continue

            for media_hash in tweet_media_hashes:

                if "." not in media_hash:
                    self.logger.error(
                        f"Hash {media_hash} does not contain an extension. Skipping media..."
                    )
                    continue

                image_hash, image_ext = media_hash.split(".")
                target_file = Path(MEDIA_DIR, image_hash)

                # Remove file if it exists
                if os.path.isfile(target_file):
                    os.remove(target_file)

                # Get media from IPFS
                try:
                    self.ipfs_tool.download(
                        hash_id=image_hash,
                        target_dir=MEDIA_DIR,
                        attempts=1
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to donwload media hash {media_hash}. Skipping media...\n{e}"
                    )
                    continue

                # Rename file to include its corresponding extension
                renamed_file = Path(MEDIA_DIR, f"{image_hash}.{image_ext}")
                os.rename(target_file, renamed_file)
                self.logger.info(f"Got media from IPFS: {media_hash} -> {renamed_file}")

                # Send media to Twitter
                media = twitter_api.media_upload(renamed_file)
                tweet_media_ids.append(media.media_id)
                self.logger.info(f"Uploaded media to Twitter: {media.media_id} ")

            thread_media_ids.append(tweet_media_ids)

        return thread_media_ids