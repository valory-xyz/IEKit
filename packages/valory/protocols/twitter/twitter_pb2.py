# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: twitter.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder


# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\rtwitter.proto\x12\x19\x61\x65\x61.valory.twitter.v0_1_0"\xad\x03\n\x0eTwitterMessage\x12[\n\x0c\x63reate_tweet\x18\x05 \x01(\x0b\x32\x43.aea.valory.twitter.v0_1_0.TwitterMessage.Create_Tweet_PerformativeH\x00\x12M\n\x05\x65rror\x18\x06 \x01(\x0b\x32<.aea.valory.twitter.v0_1_0.TwitterMessage.Error_PerformativeH\x00\x12]\n\rtweet_created\x18\x07 \x01(\x0b\x32\x44.aea.valory.twitter.v0_1_0.TwitterMessage.Tweet_Created_PerformativeH\x00\x1a)\n\x19\x43reate_Tweet_Performative\x12\x0c\n\x04text\x18\x01 \x01(\t\x1a.\n\x1aTweet_Created_Performative\x12\x10\n\x08tweet_id\x18\x01 \x01(\t\x1a%\n\x12\x45rror_Performative\x12\x0f\n\x07message\x18\x01 \x01(\tB\x0e\n\x0cperformativeb\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "twitter_pb2", _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
    DESCRIPTOR._options = None
    _globals["_TWITTERMESSAGE"]._serialized_start = 45
    _globals["_TWITTERMESSAGE"]._serialized_end = 474
    _globals["_TWITTERMESSAGE_CREATE_TWEET_PERFORMATIVE"]._serialized_start = 330
    _globals["_TWITTERMESSAGE_CREATE_TWEET_PERFORMATIVE"]._serialized_end = 371
    _globals["_TWITTERMESSAGE_TWEET_CREATED_PERFORMATIVE"]._serialized_start = 373
    _globals["_TWITTERMESSAGE_TWEET_CREATED_PERFORMATIVE"]._serialized_end = 419
    _globals["_TWITTERMESSAGE_ERROR_PERFORMATIVE"]._serialized_start = 421
    _globals["_TWITTERMESSAGE_ERROR_PERFORMATIVE"]._serialized_end = 458
# @@protoc_insertion_point(module_scope)
