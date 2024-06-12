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

"""Tweepy connection."""

import json
import os
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import jsonschema
import requests
import tweepy
from aea.configurations.base import PublicId
from aea.connections.base import BaseSyncConnection
from aea.mail.base import Envelope
from aea.protocols.base import Address, Message
from aea.protocols.dialogue.base import Dialogue
from aea_cli_ipfs.ipfs_utils import IPFSTool
from tweepy.errors import HTTPException as TweepyHTTPException

from packages.valory.protocols.srr.dialogues import SrrDialogue
from packages.valory.protocols.srr.dialogues import SrrDialogues as BaseSrrDialogues
from packages.valory.protocols.srr.message import SrrMessage


PUBLIC_ID = PublicId.from_str("valory/tweepy:0.1.0")

REQUEST_PAYLOAD_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema",
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "search_recent_tweets",
                "get_users_mentions",
                "get_users_tweets",
                "post_tweet_or_thread",
            ],
        },
        "kwargs": {"type": "object"},
        "additionalProperties": False,
    },
}

CREDENTIALS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema",
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "account_id": {"type": "string"},
            "consumer_key": {"type": "string"},
            "consumer_secret": {"type": "string"},
            "access_secret": {"type": "string"},
            "access_token": {"type": "string"},
            "bearer_token": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

MEDIA_DIR = "/tmp"  # nosec


class SrrDialogues(BaseSrrDialogues):
    """A class to keep track of SRR dialogues."""

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
            return SrrDialogue.Role.CONNECTION

        BaseSrrDialogues.__init__(
            self,
            self_address=str(kwargs.pop("connection_id")),
            role_from_first_message=role_from_first_message,
            **kwargs,
        )


class TweepyConnection(BaseSyncConnection):
    """Proxy to the functionality of the Tweepy library."""

    MAX_WORKER_THREADS = 1

    connection_id = PUBLIC_ID

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
        self.twitter_read_credentials = deque(
            self.configuration.config.get("twitter_read_credentials", [])
        )
        self.twitter_write_credentials = deque(
            self.configuration.config.get("twitter_write_credentials", [])
        )
        self.use_staging_api = self.configuration.config.get("use_staging_api", False)
        self.staging_api = self.configuration.config["staging_api"]
        self.ipfs_tool = IPFSTool()

        if not self.twitter_read_credentials:
            self.logger.warning(
                "No Twitter read credentials have been set. The service will not be able to read tweets."
            )

        try:
            jsonschema.validate(
                instance=self.twitter_read_credentials, schema=CREDENTIALS_SCHEMA
            )
        except jsonschema.exceptions.ValidationError as e:
            raise ValueError(
                f"Twitter read credentials do not follow the required schema:\n{e}"
            ) from e

        if not self.twitter_write_credentials:
            self.logger.warning(
                "No Twitter write credentials have been set. The service will not be able to write tweets."
            )

        try:
            jsonschema.validate(
                instance=self.twitter_write_credentials, schema=CREDENTIALS_SCHEMA
            )
        except jsonschema.exceptions.ValidationError as e:
            raise ValueError(
                f"Twitter write credentials do not follow the required schema:\n{e}"
            ) from e

        self.dialogues = SrrDialogues(connection_id=PUBLIC_ID)

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

    def on_connect(self) -> None:
        """
        Tear down the connection.

        Connection status set automatically.
        """

    def on_disconnect(self) -> None:
        """
        Tear down the connection.

        Connection status set automatically.
        """

    def on_send(self, envelope: Envelope) -> None:
        """
        Send an envelope.

        :param envelope: the envelope to send.
        """
        srr_message = cast(SrrMessage, envelope.message)

        dialogue = self.dialogues.update(srr_message)

        if srr_message.performative != SrrMessage.Performative.REQUEST:
            self.logger.error(
                f"Performative `{srr_message.performative.value}` is not supported."
            )
            return

        payload, error = self._get_response(
            payload=json.loads(srr_message.payload),
        )

        response_message = cast(
            SrrMessage,
            dialogue.reply(  # type: ignore
                performative=SrrMessage.Performative.RESPONSE,
                target_message=srr_message,
                payload=json.dumps(payload),
                error=error,
            ),
        )

        response_envelope = Envelope(
            to=envelope.sender,
            sender=envelope.to,
            message=response_message,
            context=envelope.context,
        )

        self.put_envelope(response_envelope)

    def _get_response(self, payload: dict) -> Tuple[Dict, bool]:
        """Get response from Tweepy."""

        # Validate the payload
        try:
            jsonschema.validate(instance=payload, schema=REQUEST_PAYLOAD_SCHEMA)
        except jsonschema.exceptions.ValidationError as e:
            return {"error": f"Tweepy connection request is not valid: {e}"}, True

        # Run the method
        try:
            method = getattr(self, payload["method"])
            result = method(**payload["kwargs"])
            return result, False
        except Exception as e:
            return {"error": f"Exception while calling Tweepy:\n{e}"}, True

    def rotate_read_credentials(self):
        """Rotate read credentials"""
        self.twitter_read_credentials.rotate(-1)

    def get_read_cli(self):
        """Get the Tweepy cli"""
        # Client is Tweepy's interface for Twitter API v2
        cli = tweepy.Client(
            bearer_token=self.twitter_read_credentials[0]["bearer"],
            wait_on_rate_limit=False,
        )
        return cli

    def get_write_cli(self, account_id):
        """Get the Tweepy cli"""
        # Client is Tweepy's interface for Twitter API v2
        for cred in self.twitter_write_credentials:
            if cred["id"] == account_id:
                cli = tweepy.Client(
                    bearer_token=cred["bearer"], wait_on_rate_limit=False
                )
                return cli
        self.logger.error(f"Could not get Tweepy client for acoount_id={account_id}")
        return None

    def get_write_api(self, account_id):
        """Get the Tweepy api"""
        for cred in self.twitter_write_credentials:
            if cred["id"] == account_id:
                auth = tweepy.OAuth1UserHandler(
                    consumer_key=cred["consumer_key"],
                    consumer_secret=cred["consumer_secret"],
                    access_token=cred["access_token"],
                    access_token_secret=cred["access_secret"],
                )
                api = tweepy.API(auth)
                return api

        self.logger.error(f"Could not get Tweepy API for acoount_id={account_id}")
        return None

    def read_with_key_rotation(self, method, **kwargs) -> Tuple[Dict, bool]:
        """Make a call to the tweepy client with automatic key rotation"""
        max_rotations = len(self.twitter_read_credentials)
        rotations = 0

        while rotations < max_rotations:
            try:
                cli = self.get_read_cli()
                method = getattr(cli, method)
                result = method(**kwargs)
                return {"tweets": self.process_tweets(result)}, False
            except Exception as e:
                self.logger.error(
                    f"Error when calling {method} on account {self.twitter_read_credentials[0]['account_id']}. Rotating credentials:\n{e}"
                )
                self.rotate_read_credentials()
                rotations += 1
        return {"error": "Max Twitter read credential rotations reached"}, True

    def process_tweets(self, tweets) -> List:
        """Process tweets"""
        users = {u["id"]: u for u in tweets.includes["users"]}
        return [
            {
                "id": tweet.id,
                "text": tweet.text,
                "author_id": tweet.author_id,
                "username": users[tweet.author_id],
            }
            for tweet in tweets
        ]

    def search_recent_tweets(self, **kwargs) -> Tuple[Dict, bool]:
        """Search recent tweets"""
        return self.read_with_key_rotation(
            method="search_recent_tweets",
            expansions=["author_id"],
            tweet_fields=["author_id", "created_at", "conversation_id"],
            user_fields=["username"],
            **kwargs,
        )

    def get_users_mentions(self, **kwargs) -> Tuple[Dict, bool]:
        """Get users mentions"""
        return self.read_with_key_rotation(
            method="get_users_mentions",
            expansions=["author_id"],
            tweet_fields=["author_id", "created_at", "conversation_id"],
            user_fields=["username"],
            **kwargs,
        )

    def get_users_tweets(self, **kwargs) -> Tuple[Dict, bool]:
        """Get users tweets"""
        return self.read_with_key_rotation(
            method="get_users_tweets",
            expansions=["author_id"],
            tweet_fields=["author_id", "created_at", "conversation_id"],
            user_fields=["username"],
            **kwargs,
        )

    def post_tweet_or_thread(self, **kwargs) -> Tuple[Dict, bool]:
        """Post tweet or thread"""

        if self.use_staging_api:
            return self.post_tweet_or_thread_staging(**kwargs)

        # Process media
        thread_media_ids = self.process_media(**kwargs)
        self.logger.info(f"Processed media ids: {thread_media_ids}")

        # Publish tweets
        cli = self.get_write_cli(kwargs.get("account_id", None))

        if not cli:
            return {"error": "Could not get tweepy cli"}, True

        text = kwargs.get("text")
        tweets = text if isinstance(text, list) else [text]
        thread_media_ids = (
            thread_media_ids if thread_media_ids else [[] for _ in tweets]
        )

        try:
            tweet_id = None
            for text, media_ids in zip(tweets, thread_media_ids):
                tweet_kwargs = {}

                if text:
                    tweet_kwargs["text"] = text

                if media_ids:
                    tweet_kwargs["media_ids"] = media_ids

                if tweet_id:
                    tweet_kwargs["in_reply_to_tweet_id"] = tweet_id

                self.logger.info(f"Tweepy kwargs: {tweet_kwargs}")

                response = cli.create_tweet(**tweet_kwargs)

                if not tweet_id:
                    tweet_id = response.data["id"]

            return {"tweet_id": tweet_id}, False

        except TweepyHTTPException as e:
            return {"error": "; ".join(e.api_messages)}, True

    def post_tweet_or_thread_staging(self, **kwargs) -> Tuple[Dict, bool]:
        """Post tweet or thread to staging"""

        text = kwargs.get("text")
        tweets = text if isinstance(text, list) else [text]

        url = f"{self.staging_api}/twitter/create_tweet"

        self.logger.info(f"Posting tweet using the staging API {url}")

        try:
            tweet_id = None
            for tweet in tweets:
                response = requests.post(
                    url,
                    json={"user_name": "staging_contribute", "text": tweet},
                    timeout=10,
                )

                # Keep the first tweet_id only
                if not tweet_id:
                    tweet_id = response.json()["tweet_id"]

            return {"tweet_id": tweet_id}, False

        except requests.exceptions.ConnectionError as error:
            return {"error": error}, True

    def process_media(self, **kwargs) -> Optional[List]:
        """Process tweet media"""

        # Media hashes is always a list of lists
        # Each tweet can contain several media items
        # A thread can contain several tweets
        # media_hashes = [[], [hashes_for_tweet_2], [], [hashes_for_tweet_4]]  # noqa: E800
        media_hashes = kwargs.get("media_hashes")
        self.logger.info(f"Processing media: {media_hashes}")
        thread_media_ids = []

        if not media_hashes:
            return None

        api = self.get_write_api(kwargs.get("account_id", None))

        if not api:
            return None

        for tweet_media_hashes in media_hashes:
            tweet_media_ids = []

            # tweet_media_hashes is not a list
            if not isinstance(tweet_media_hashes, list):
                self.logger.error(
                    f"Hash list is not a list: {tweet_media_hashes}. Skipping tweet media..."
                )
                thread_media_ids.append(tweet_media_ids)
                continue

            for media_hash in tweet_media_hashes:
                # The hash foes not contain an extension
                if "." not in media_hash:
                    self.logger.error(
                        f"Hash {media_hash} does not contain an extension. Skipping media..."
                    )
                    continue

                # Target file path
                image_hash, image_ext = media_hash.split(".")
                target_file = Path(MEDIA_DIR, image_hash)

                # Remove file if it exists
                if os.path.isfile(target_file):
                    os.remove(target_file)

                # Get media from IPFS
                try:
                    self.ipfs_tool.download(
                        hash_id=image_hash, target_dir=MEDIA_DIR, attempts=1
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
                media = api.media_upload(renamed_file)
                tweet_media_ids.append(media.media_id)
                self.logger.info(f"Uploaded media to Twitter: {media.media_id} ")

            thread_media_ids.append(tweet_media_ids)

        return thread_media_ids
