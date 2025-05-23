
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

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import List, Dict, Optional
from datetime import datetime, date
import re
from uuid import UUID


class EthereumAddress(BaseModel):
    """EthereumAddress"""

    address: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{3,16}$")

    @field_validator("address")
    @classmethod
    def validate_address(cls, address):
        """Validate Ethereum address."""
        if not re.match(r"^(0x)?[0-9a-fA-F]{40}$", address):
            raise ValueError("Ethereum address is not valid")
        return address


class Proposer(BaseModel):
    """Proposer"""

    address: EthereumAddress
    signature: str
    verified: bool = False


class Voter(BaseModel):
    """Voter"""

    address: EthereumAddress
    signature: str
    votingPower: int


class ExecutionAttempt:
    """ExecutionAttempt"""

    id: UUID
    verified: bool
    dateCreated: float


class UserTweet(BaseModel):
    """UserTweet"""

    tweet_id: str
    epoch: int
    points: int
    campaign: str
    timestamp: datetime
    counted_for_activity: bool = False


class ServiceTweet(BaseModel):
    """ServiceTweet"""

    text: List[str]
    posted: bool = False
    voters: List[EthereumAddress] = []
    proposer: Proposer
    action_id: str
    request_id: UUID
    createdDate: float
    executionAttempts: List[ExecutionAttempt] = []


class ContributeUser(BaseModel):
    """ContributeUser"""

    id: int
    points: int = 0
    tweets: List[UserTweet] = []
    token_id: Optional[str] = None
    discord_id: Optional[str] = None
    service_id: Optional[str] = None
    twitter_id: Optional[str] = None
    twitter_handle: Optional[str] = None
    discord_handle: Optional[str] = None
    wallet_address: Optional[EthereumAddress] = None
    service_multisig: Optional[EthereumAddress] = None
    current_period_points: int = 0


class Action(BaseModel):
    """Action"""

    commitId: str
    timestamp: datetime
    description: str
    actorAddress: str


class TwitterCampaign(BaseModel):
    """TwitterCampaign"""

    id: str
    end_ts: str
    status: str
    voters: List[Voter] = []
    hashtag: str
    proposer: Proposer
    start_ts: float


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

    tweets = Dict[str, ServiceTweet]


class TwitterCampaignsConfig(BaseModel):
    """TwitterCampaignsConfig"""

    campaigns: Dict[str, TwitterCampaign]


class PluginConfig(BaseModel):
    """PluginConfig"""

    daily: bool
    enabled: bool
    last_run: datetime
    run_hour_utc: int


class PluginsConfig(BaseModel):
    """PluginsConfig"""

    daily_orbis: PluginConfig
    daily_tweet: PluginConfig
    staking_daa: PluginConfig
    week_in_olas: PluginConfig
    scheduled_tweet: PluginConfig
    staking_activity: PluginConfig
    twitter_campaigns: PluginConfig
    staking_checkpoint: PluginConfig


class PluginsData(BaseModel):
    """PluginsData"""

    daily_orbis: Optional[dict]
    daily_tweet: Optional[dict]
    scheduled_tweet: ScheduledTweetConfig
    twitter_campaigns: TwitterCampaignsConfig
    dynamic_nft: DynamicNFTData
    twitter: TwitterScoringData


class ContributeDatabase(BaseModel):
    """ContributeDatabase"""

    users: Dict[str, ContributeUser]
    plugins_data: PluginsData
    configuration: PluginsConfig

