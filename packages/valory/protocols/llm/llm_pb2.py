# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: llm.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database


# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\tllm.proto\x12\x15\x61\x65\x61.valory.llm.v1_0_0"\xa4\x03\n\nLlmMessage\x12I\n\x07request\x18\x05 \x01(\x0b\x32\x36.aea.valory.llm.v1_0_0.LlmMessage.Request_PerformativeH\x00\x12K\n\x08response\x18\x06 \x01(\x0b\x32\x37.aea.valory.llm.v1_0_0.LlmMessage.Response_PerformativeH\x00\x1a\xc5\x01\n\x14Request_Performative\x12\x17\n\x0fprompt_template\x18\x01 \x01(\t\x12_\n\rprompt_values\x18\x02 \x03(\x0b\x32H.aea.valory.llm.v1_0_0.LlmMessage.Request_Performative.PromptValuesEntry\x1a\x33\n\x11PromptValuesEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01\x1a&\n\x15Response_Performative\x12\r\n\x05value\x18\x01 \x01(\tB\x0e\n\x0cperformativeb\x06proto3'
)


_LLMMESSAGE = DESCRIPTOR.message_types_by_name["LlmMessage"]
_LLMMESSAGE_REQUEST_PERFORMATIVE = _LLMMESSAGE.nested_types_by_name[
    "Request_Performative"
]
_LLMMESSAGE_REQUEST_PERFORMATIVE_PROMPTVALUESENTRY = (
    _LLMMESSAGE_REQUEST_PERFORMATIVE.nested_types_by_name["PromptValuesEntry"]
)
_LLMMESSAGE_RESPONSE_PERFORMATIVE = _LLMMESSAGE.nested_types_by_name[
    "Response_Performative"
]
LlmMessage = _reflection.GeneratedProtocolMessageType(
    "LlmMessage",
    (_message.Message,),
    {
        "Request_Performative": _reflection.GeneratedProtocolMessageType(
            "Request_Performative",
            (_message.Message,),
            {
                "PromptValuesEntry": _reflection.GeneratedProtocolMessageType(
                    "PromptValuesEntry",
                    (_message.Message,),
                    {
                        "DESCRIPTOR": _LLMMESSAGE_REQUEST_PERFORMATIVE_PROMPTVALUESENTRY,
                        "__module__": "llm_pb2"
                        # @@protoc_insertion_point(class_scope:aea.valory.llm.v1_0_0.LlmMessage.Request_Performative.PromptValuesEntry)
                    },
                ),
                "DESCRIPTOR": _LLMMESSAGE_REQUEST_PERFORMATIVE,
                "__module__": "llm_pb2"
                # @@protoc_insertion_point(class_scope:aea.valory.llm.v1_0_0.LlmMessage.Request_Performative)
            },
        ),
        "Response_Performative": _reflection.GeneratedProtocolMessageType(
            "Response_Performative",
            (_message.Message,),
            {
                "DESCRIPTOR": _LLMMESSAGE_RESPONSE_PERFORMATIVE,
                "__module__": "llm_pb2"
                # @@protoc_insertion_point(class_scope:aea.valory.llm.v1_0_0.LlmMessage.Response_Performative)
            },
        ),
        "DESCRIPTOR": _LLMMESSAGE,
        "__module__": "llm_pb2"
        # @@protoc_insertion_point(class_scope:aea.valory.llm.v1_0_0.LlmMessage)
    },
)
_sym_db.RegisterMessage(LlmMessage)
_sym_db.RegisterMessage(LlmMessage.Request_Performative)
_sym_db.RegisterMessage(LlmMessage.Request_Performative.PromptValuesEntry)
_sym_db.RegisterMessage(LlmMessage.Response_Performative)

if _descriptor._USE_C_DESCRIPTORS == False:

    DESCRIPTOR._options = None
    _LLMMESSAGE_REQUEST_PERFORMATIVE_PROMPTVALUESENTRY._options = None
    _LLMMESSAGE_REQUEST_PERFORMATIVE_PROMPTVALUESENTRY._serialized_options = b"8\001"
    _LLMMESSAGE._serialized_start = 37
    _LLMMESSAGE._serialized_end = 457
    _LLMMESSAGE_REQUEST_PERFORMATIVE._serialized_start = 204
    _LLMMESSAGE_REQUEST_PERFORMATIVE._serialized_end = 401
    _LLMMESSAGE_REQUEST_PERFORMATIVE_PROMPTVALUESENTRY._serialized_start = 350
    _LLMMESSAGE_REQUEST_PERFORMATIVE_PROMPTVALUESENTRY._serialized_end = 401
    _LLMMESSAGE_RESPONSE_PERFORMATIVE._serialized_start = 403
    _LLMMESSAGE_RESPONSE_PERFORMATIVE._serialized_end = 441
# @@protoc_insertion_point(module_scope)