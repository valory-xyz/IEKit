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


# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 valory
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

"""Serialization module for twitter protocol."""

# pylint: disable=too-many-statements,too-many-locals,no-member,too-few-public-methods,redefined-builtin
from typing import Any, Dict, cast

from aea.mail.base_pb2 import DialogueMessage  # type: ignore
from aea.mail.base_pb2 import Message as ProtobufMessage  # type: ignore
from aea.protocols.base import Message  # type: ignore
from aea.protocols.base import Serializer  # type: ignore

from packages.valory.protocols.twitter import twitter_pb2  # type: ignore
from packages.valory.protocols.twitter.message import TwitterMessage  # type: ignore


class TwitterSerializer(Serializer):
    """Serialization for the 'twitter' protocol."""

    @staticmethod
    def encode(msg: Message) -> bytes:
        """
        Encode a 'Twitter' message into bytes.

        :param msg: the message object.
        :return: the bytes.
        """
        msg = cast(TwitterMessage, msg)
        message_pb = ProtobufMessage()
        dialogue_message_pb = DialogueMessage()
        twitter_msg = twitter_pb2.TwitterMessage()  # type: ignore

        dialogue_message_pb.message_id = msg.message_id
        dialogue_reference = msg.dialogue_reference
        dialogue_message_pb.dialogue_starter_reference = dialogue_reference[0]
        dialogue_message_pb.dialogue_responder_reference = dialogue_reference[1]
        dialogue_message_pb.target = msg.target

        performative_id = msg.performative
        if performative_id == TwitterMessage.Performative.CREATE_TWEET:
            performative = twitter_pb2.TwitterMessage.Create_Tweet_Performative()  # type: ignore
            data = msg.data
            performative.data = data
            twitter_msg.create_tweet.CopyFrom(performative)
        elif performative_id == TwitterMessage.Performative.TWEET_CREATED:
            performative = twitter_pb2.TwitterMessage.Tweet_Created_Performative()  # type: ignore
            tweet_id = msg.tweet_id
            performative.tweet_id = tweet_id
            twitter_msg.tweet_created.CopyFrom(performative)
        elif performative_id == TwitterMessage.Performative.ERROR:
            performative = twitter_pb2.TwitterMessage.Error_Performative()  # type: ignore
            message = msg.message
            performative.message = message
            twitter_msg.error.CopyFrom(performative)
        else:
            raise ValueError("Performative not valid: {}".format(performative_id))

        dialogue_message_pb.content = twitter_msg.SerializeToString()

        message_pb.dialogue_message.CopyFrom(dialogue_message_pb)
        message_bytes = message_pb.SerializeToString()
        return message_bytes

    @staticmethod
    def decode(obj: bytes) -> Message:
        """
        Decode bytes into a 'Twitter' message.

        :param obj: the bytes object.
        :return: the 'Twitter' message.
        """
        message_pb = ProtobufMessage()
        twitter_pb = twitter_pb2.TwitterMessage()  # type: ignore
        message_pb.ParseFromString(obj)
        message_id = message_pb.dialogue_message.message_id
        dialogue_reference = (
            message_pb.dialogue_message.dialogue_starter_reference,
            message_pb.dialogue_message.dialogue_responder_reference,
        )
        target = message_pb.dialogue_message.target

        twitter_pb.ParseFromString(message_pb.dialogue_message.content)
        performative = twitter_pb.WhichOneof("performative")
        performative_id = TwitterMessage.Performative(str(performative))
        performative_content = dict()  # type: Dict[str, Any]
        if performative_id == TwitterMessage.Performative.CREATE_TWEET:
            data = twitter_pb.create_tweet.data
            performative_content["data"] = data
        elif performative_id == TwitterMessage.Performative.TWEET_CREATED:
            tweet_id = twitter_pb.tweet_created.tweet_id
            performative_content["tweet_id"] = tweet_id
        elif performative_id == TwitterMessage.Performative.ERROR:
            message = twitter_pb.error.message
            performative_content["message"] = message
        else:
            raise ValueError("Performative not valid: {}.".format(performative_id))

        return TwitterMessage(
            message_id=message_id,
            dialogue_reference=dialogue_reference,
            target=target,
            performative=performative,
            **performative_content
        )
