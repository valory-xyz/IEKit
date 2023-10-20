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

"""Serialization module for llm protocol."""

# pylint: disable=too-many-statements,too-many-locals,no-member,too-few-public-methods,redefined-builtin
from typing import Any, Dict, cast

from aea.mail.base_pb2 import DialogueMessage  # type: ignore
from aea.mail.base_pb2 import Message as ProtobufMessage  # type: ignore
from aea.protocols.base import Message  # type: ignore
from aea.protocols.base import Serializer  # type: ignore

from packages.valory.protocols.llm import llm_pb2  # type: ignore
from packages.valory.protocols.llm.message import LlmMessage  # type: ignore


class LlmSerializer(Serializer):
    """Serialization for the 'llm' protocol."""

    @staticmethod
    def encode(msg: Message) -> bytes:
        """
        Encode a 'Llm' message into bytes.

        :param msg: the message object.
        :return: the bytes.
        """
        msg = cast(LlmMessage, msg)
        message_pb = ProtobufMessage()
        dialogue_message_pb = DialogueMessage()
        llm_msg = llm_pb2.LlmMessage()  # type: ignore

        dialogue_message_pb.message_id = msg.message_id
        dialogue_reference = msg.dialogue_reference
        dialogue_message_pb.dialogue_starter_reference = dialogue_reference[0]
        dialogue_message_pb.dialogue_responder_reference = dialogue_reference[1]
        dialogue_message_pb.target = msg.target

        performative_id = msg.performative
        if performative_id == LlmMessage.Performative.REQUEST:
            performative = llm_pb2.LlmMessage.Request_Performative()  # type: ignore
            prompt_template = msg.prompt_template
            performative.prompt_template = prompt_template
            prompt_values = msg.prompt_values
            performative.prompt_values.update(prompt_values)
            llm_msg.request.CopyFrom(performative)
        elif performative_id == LlmMessage.Performative.RESPONSE:
            performative = llm_pb2.LlmMessage.Response_Performative()  # type: ignore
            value = msg.value
            performative.value = value
            llm_msg.response.CopyFrom(performative)
        else:
            raise ValueError("Performative not valid: {}".format(performative_id))

        dialogue_message_pb.content = llm_msg.SerializeToString()

        message_pb.dialogue_message.CopyFrom(dialogue_message_pb)
        message_bytes = message_pb.SerializeToString()
        return message_bytes

    @staticmethod
    def decode(obj: bytes) -> Message:
        """
        Decode bytes into a 'Llm' message.

        :param obj: the bytes object.
        :return: the 'Llm' message.
        """
        message_pb = ProtobufMessage()
        llm_pb = llm_pb2.LlmMessage()  # type: ignore
        message_pb.ParseFromString(obj)
        message_id = message_pb.dialogue_message.message_id
        dialogue_reference = (
            message_pb.dialogue_message.dialogue_starter_reference,
            message_pb.dialogue_message.dialogue_responder_reference,
        )
        target = message_pb.dialogue_message.target

        llm_pb.ParseFromString(message_pb.dialogue_message.content)
        performative = llm_pb.WhichOneof("performative")
        performative_id = LlmMessage.Performative(str(performative))
        performative_content = dict()  # type: Dict[str, Any]
        if performative_id == LlmMessage.Performative.REQUEST:
            prompt_template = llm_pb.request.prompt_template
            performative_content["prompt_template"] = prompt_template
            prompt_values = llm_pb.request.prompt_values
            prompt_values_dict = dict(prompt_values)
            performative_content["prompt_values"] = prompt_values_dict
        elif performative_id == LlmMessage.Performative.RESPONSE:
            value = llm_pb.response.value
            performative_content["value"] = value
        else:
            raise ValueError("Performative not valid: {}.".format(performative_id))

        return LlmMessage(
            message_id=message_id,
            dialogue_reference=dialogue_reference,
            target=target,
            performative=performative,
            **performative_content
        )
