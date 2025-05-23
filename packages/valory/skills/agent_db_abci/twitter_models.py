
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

from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, Literal, Optional
from datetime import datetime, timezone
import json


class TwitterAction(BaseModel):
    """TwitterAction"""

    action: str
    timestamp: datetime

    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON"""
        return {
            "action": self.action,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            "details": self.model_dump_json(exclude={"action", "timestamp"}),
        }


class TwitterPost(TwitterAction):
    """TwitterPost"""

    action: Literal["post"] = "post"
    tweet_id: str
    text: str
    reply_to_tweet_id: Optional[str] = None

    @classmethod
    def from_nested_json(cls, data: Dict[str, Any]) -> "TwitterPost":
        """Convert nested JSON to TwitterPost"""
        if isinstance(data["details"], str):
            data["details"] = json.loads(data["details"])
        return cls(
            action=data["action"],
            timestamp=datetime.fromisoformat(
                data["timestamp"].replace("Z", "+00:00")
            ).astimezone(timezone.utc),
            tweet_id=data["details"]["tweet_id"],
            text=data["details"]["text"],
            reply_to_tweet_id=data["details"].get("reply_to_tweet_id", None),
        )


class TwitterRewtweet(TwitterAction):
    """TwitterRewtweet"""

    action: Literal["retweet"] = "retweet"
    tweet_id: str

    @classmethod
    def from_nested_json(cls, data: Dict[str, Any]) -> "TwitterPost":
        """Convert nested JSON to TwitterPost"""
        if isinstance(data["details"], str):
            data["details"] = json.loads(data["details"])
        return cls(
            action=data["action"],
            timestamp=datetime.fromisoformat(
                data["timestamp"].replace("Z", "+00:00")
            ).astimezone(timezone.utc),
            tweet_id=data["details"]["tweet_id"],
        )


class TwitterFollow(TwitterAction):
    """TwitterFollow"""

    action: Literal["follow"] = "follow"
    username: str

    @classmethod
    def from_nested_json(cls, data: Dict[str, Any]) -> "TwitterPost":
        """Convert nested JSON to TwitterPost"""
        if isinstance(data["details"], str):
            data["details"] = json.loads(data["details"])
        return cls(
            action=data["action"],
            timestamp=datetime.fromisoformat(
                data["timestamp"].replace("Z", "+00:00")
            ).astimezone(timezone.utc),
            username=data["details"]["username"],
        )


class TwitterLike(TwitterAction):
    """TwitterLike"""

    action: Literal["like"] = "like"
    tweet_id: str

    @classmethod
    def from_nested_json(cls, data: Dict[str, Any]) -> "TwitterPost":
        """Convert nested JSON to TwitterPost"""
        if isinstance(data["details"], str):
            data["details"] = json.loads(data["details"])
        return cls(
            action=data["action"],
            timestamp=datetime.fromisoformat(
                data["timestamp"].replace("Z", "+00:00")
            ).astimezone(timezone.utc),
            tweet_id=data["details"]["tweet_id"],
        )
