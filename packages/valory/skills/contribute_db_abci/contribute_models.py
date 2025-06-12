# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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

"""This module contains definitions for Twitter models."""

import json
import re
from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator
from pydantic_core import core_schema

from packages.valory.skills.agent_db_abci.agent_db_models import (
    AgentInstance,
    AgentType,
    AttributeDefinition,
    AttributeInstance,
)


class EthereumAddress(str):
    """EthereumAddress"""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source, _handler):
        """Get the Pydantic core schema for EthereumAddress."""
        return core_schema.with_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
        )

    @classmethod
    def validate(cls, value: str, _info) -> str:
        """Validate that the value is a valid Ethereum address."""
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", value):
            raise ValueError(f"Invalid Ethereum address: {value}")
        return value


class Proposer(BaseModel):
    """Proposer"""

    address: EthereumAddress
    signature: str
    verified: bool = False


class Voter(BaseModel):
    """Voter"""

    address: EthereumAddress
    signature: str
    votingPower: float


class ExecutionAttempt(BaseModel):
    """ExecutionAttempt"""

    id: UUID
    verified: Optional[bool]
    dateCreated: float


class UserTweet(BaseModel):
    """UserTweet"""

    tweet_id: str
    twitter_user_id: str
    epoch: Optional[int] = None
    points: Optional[int] = None
    campaign: Optional[str] = None
    timestamp: Optional[datetime] = None
    counted_for_activity: bool = False
    attribute_instance_id: Optional[int] = None


class ServiceTweet(BaseModel):
    """ServiceTweet"""

    text: List[str]
    posted: bool = False
    voters: List[Voter] = []
    proposer: Proposer
    action_id: str
    request_id: UUID
    createdDate: float
    executionAttempts: List[ExecutionAttempt] = []


class ContributeUser(BaseModel):
    """ContributeUser"""

    id: int
    points: int = 0
    tweets: Dict[str, UserTweet] = {}
    token_id: Optional[str] = None
    discord_id: Optional[str] = None
    service_id: Optional[str] = None
    twitter_id: Optional[str] = None
    twitter_handle: Optional[str] = None
    discord_handle: Optional[str] = None
    wallet_address: Optional[EthereumAddress] = None
    service_multisig: Optional[EthereumAddress] = None
    current_period_points: int = 0
    attribute_instance_id: Optional[int] = None

    def model_dump(self, mode):
        """Dump the user data to a JSON-compatible dictionary."""
        data = super().model_dump(mode=mode)
        data["tweets"] = list(data["tweets"].keys())  # We just store the tweet ids
        return data


class Action(BaseModel):
    """Action"""

    commitId: str
    timestamp: datetime
    description: str
    actorAddress: str


class TwitterCampaign(BaseModel):
    """TwitterCampaign"""

    id: str
    end_ts: int
    status: str
    voters: List[Voter] = []
    hashtag: str
    proposer: Proposer
    start_ts: int


class TwitterScoringData(BaseModel):
    """TwitterScoringData"""

    current_period: date
    latest_hashtag_tweet_id: str
    latest_mention_tweet_id: str
    last_tweet_pull_window_reset: float
    number_of_tweets_pulled_today: int


class DynamicNFTData(BaseModel):
    """DynamicNFTConfig"""

    last_parsed_block: int


class ScheduledTweetConfig(BaseModel):
    """ScheduledTweetConfig"""

    tweets: List[ServiceTweet]


class TwitterCampaignsConfig(BaseModel):
    """TwitterCampaignsConfig"""

    campaigns: List[TwitterCampaign]


class ModuleConfig(BaseModel):
    """ModuleConfig"""

    daily: bool = False
    weekly: Optional[int] = None
    enabled: bool = False
    last_run: Optional[datetime] = None
    run_hour_utc: int = 0

    @field_validator("last_run", mode="before")
    @classmethod
    def parse_utc_datetime(cls, v):
        """Parse the last_run datetime string to a datetime object."""
        if isinstance(v, str) and v.endswith(" UTC"):
            v = v[:-4]  # Remove the trailing ' UTC'
        return v


class ModuleConfigs(BaseModel):
    """ModuleConfigs"""

    staking_daa: ModuleConfig
    week_in_olas: ModuleConfig
    scheduled_tweet: ModuleConfig
    staking_activity: ModuleConfig
    twitter_campaigns: ModuleConfig
    staking_checkpoint: ModuleConfig
    attribute_instance_id: Optional[int] = None


class ModuleData(BaseModel):
    """ModuleData"""

    scheduled_tweet: ScheduledTweetConfig
    twitter_campaigns: TwitterCampaignsConfig
    dynamic_nft: DynamicNFTData
    twitter: TwitterScoringData
    attribute_instance_id: Optional[int] = None


class ContributeData(BaseModel):
    """ContributeData"""

    users: Dict[str, ContributeUser] = {}
    tweets: Dict[str, UserTweet] = {}
    module_data: Optional[ModuleData] = None
    module_configs: Optional[ModuleConfigs] = None

    def sort(self):
        """Sort users and tweets."""
        self.users = dict(
            sorted(self.users.items(), key=lambda item: int(item[0]), reverse=False)
        )
        self.tweets = dict(
            sorted(self.tweets.items(), key=lambda item: int(item[0]), reverse=False)
        )
