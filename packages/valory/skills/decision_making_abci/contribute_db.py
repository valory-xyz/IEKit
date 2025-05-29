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

"""This module contains classes to interact with Agents.Fun agent data on AgentDB."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from aea.skills.base import Model

from packages.valory.skills.agent_db_abci.agent_db_client import (
    AgentDBClient,
    AgentInstance,
)
from packages.valory.skills.agent_db_abci.twitter_models import (
    TwitterAction,
    TwitterFollow,
    TwitterLike,
    TwitterPost,
    TwitterRewtweet,
)


MEMEOOORR = "memeooorr"


class AgentsFunAgent:
    """AgentsFunAgent"""

    action_to_class: Dict[str, Any] = {
        "post": TwitterPost,
        "retweet": TwitterRewtweet,
        "follow": TwitterFollow,
        "like": TwitterLike,
    }

    def __init__(self, client: AgentDBClient, agent_instance: AgentInstance):
        """Constructor"""
        self.client = client
        self.agent_instance = agent_instance
        self.twitter_username: str = None
        self.twitter_user_id: str = None
        self.posts: List[TwitterPost] = []
        self.likes: List[TwitterLike] = []
        self.retweets: List[TwitterRewtweet] = []
        self.follows: List[TwitterFollow] = []
        self.loaded = False

    @classmethod
    def register(cls, agent_name: str, client: AgentDBClient):
        """Register agent"""
        agent_type = yield from client.get_agent_type_by_type_name(MEMEOOORR)
        agent_instance = yield from client.create_agent_instance(
            agent_name=agent_name,
            agent_type=agent_type,
            eth_address=client.address,
        )

        return cls(client, agent_instance)

    def delete(self):
        """Delete agent instance"""
        yield from self.client.delete_agent_instance(self.agent_instance)

    def load(self):
        """Load agent data"""
        attributes = yield from self.client.get_all_agent_instance_attributes_parsed(
            self.agent_instance
        )

        interactions = []
        for attr in attributes:
            if attr["attr_name"] == "twitter_username":
                self.twitter_username = attr["attr_value"]
            elif attr["attr_name"] == "twitter_user_id":
                self.twitter_user_id = attr["attr_value"]
            elif attr["attr_name"] == "twitter_interactions":
                action_class = self.action_to_class.get(
                    attr["attr_value"]["action"], None
                )
                if not action_class:
                    raise ValueError(
                        f"Unknown Twitter action: {attr['attr_value']['action']}"
                    )
                interactions.append(
                    action_class.from_nested_json(data=attr["attr_value"])
                )

        # Separate the interactions into different lists and sort by timestamp
        interactions.sort(key=lambda x: x.timestamp)
        self.posts = [
            interaction
            for interaction in interactions
            if isinstance(interaction, TwitterPost)
        ]
        self.retweets = [
            interaction
            for interaction in interactions
            if isinstance(interaction, TwitterRewtweet)
        ]
        self.likes = [
            interaction
            for interaction in interactions
            if isinstance(interaction, TwitterLike)
        ]
        self.follows = [
            interaction
            for interaction in interactions
            if isinstance(interaction, TwitterFollow)
        ]
        self.loaded = True

    def add_interaction(self, interaction: TwitterAction):
        """Add interaction to agent"""

        # Check if the interaction is valid
        action_class = self.action_to_class.get(interaction.action, None)
        if not action_class:
            raise ValueError(f"Unknown Twitter action: {interaction.action}")

        # Create attribute instance
        attr_def = yield from self.client.get_attribute_definition_by_name(
            "twitter_interactions"
        )
        if not attr_def:
            raise ValueError("Attribute definition not found")

        # Create or update attribute instance
        attr_instance = yield from self.client.create_attribute_instance(
            agent_instance=self.agent_instance,
            attribute_def=attr_def,
            value=interaction.to_json(),
            value_type="json",
        )
        return attr_instance

    def __str__(self) -> str:
        """String representation of the agent"""
        return f"Agent id={self.agent_instance.agent_id}  loaded={self.loaded}  username=@{self.twitter_username}"


class AgentsFunDatabase(Model):
    """AgentsFunDatabase"""

    def __init__(self, **kwargs: Any) -> None:
        """Constructor"""
        super().__init__(**kwargs)
        self.client = None
        self.agent_type = None
        self.agents = []

    def initialize(self, client: AgentDBClient):
        """Initialize agent"""
        if self.client is None:
            self.client = client

    def load(self):
        """Load data"""
        if self.agent_type is None:
            self.agent_type = yield from self.client.get_agent_type_by_type_name(
                MEMEOOORR
            )

        agent_instances = yield from self.client.get_agent_instances_by_type_id(
            self.agent_type.type_id
        )
        for agent_instance in agent_instances:
            self.agents.append(AgentsFunAgent(self.client, agent_instance))
            yield from self.agents[-1].load()

    def get_tweet_likes_number(self, tweet_id) -> int:
        """Get all tweet likes"""
        tweet_likes = 0
        for agent in self.agents:
            if not agent.loaded:
                yield from agent.load()
            for like in agent.likes:
                if like.tweet_id == tweet_id:
                    tweet_likes += 1
                    break
        return tweet_likes

    def get_tweet_retweets_number(self, tweet_id) -> int:
        """Get all tweet retweets"""
        tweet_retweets = 0
        for agent in self.agents:
            if not agent.loaded:
                yield from agent.load()
            for retweet in agent.retweets:
                if retweet.tweet_id == tweet_id:
                    tweet_retweets += 1
                    break
        return tweet_retweets

    def get_tweet_replies(self, tweet_id) -> List[TwitterPost]:
        """Get all tweet replies"""
        tweet_replies = []
        for agent in self.agents:
            if not agent.loaded:
                yield from agent.load()
            for post in agent.posts:
                if post.reply_to_tweet_id == tweet_id:
                    tweet_replies.append(post)
                    break
        return tweet_replies

    def get_tweet_feedback(self, tweet_id) -> Dict[str, Any]:
        """Get all tweet feedback"""
        likes = yield from self.get_tweet_likes_number(tweet_id)
        retweets = yield from self.get_tweet_retweets_number(tweet_id)
        replies = yield from self.get_tweet_replies(tweet_id)

        tweet_feedback = {
            "likes": likes,
            "retweets": retweets,
            "replies": replies,
        }
        return tweet_feedback

    def get_active_agents(self) -> List[AgentsFunAgent]:
        """Get all active agents"""
        active_agents = []
        for agent in self.agents:
            if not agent.loaded:
                yield from agent.load()

            # An agent is active if it has posted in the last 7 days
            if not agent.posts:
                continue

            if agent.posts[-1].timestamp < datetime.now(timezone.utc) - timedelta(
                days=7
            ):
                continue

            active_agents.append(agent)
        return active_agents

    def __str__(self) -> str:
        """String representation of the database"""
        return f"AgentsFunDatabase with {len(self.agents)} agents"
