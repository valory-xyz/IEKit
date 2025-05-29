#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2025 Valory AG
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

"""Test the AgentDBClient class."""

# pylint: disable=unused-variable,too-many-arguments,too-many-instance-attributes

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

import dotenv
import requests
from eth_account import Account
from eth_account.messages import encode_defunct
from pydantic import BaseModel
from rich.align import Align
from rich.console import Console
from rich.table import Table

from packages.valory.skills.agent_db_abci.agent_db_models import (
    AgentInstance,
    AgentType,
    AttributeDefinition,
    AttributeInstance,
)
from packages.valory.skills.decision_making_abci.contribute_models import (
    Action,
    ContributeDatabase,
    ContributeUser,
    DynamicNFTData,
    EthereumAddress,
    ExecutionAttempt,
    ModuleConfig,
    ModuleConfig,
    ModuleData,
    Proposer,
    ScheduledTweetConfig,
    ServiceTweet,
    TwitterCampaign,
    TwitterCampaignsConfig,
    TwitterScoringData,
    UserTweet,
    Voter,
)


dotenv.load_dotenv(override=True)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
CONTRIBUTE = "contribute"

# https://axatbhardwaj.notion.site/MirrorDB-Agent-and-Attribute-Data-Flow-1eac8d38bc0b80edae04ff1017d80f58
# https://afmdb.autonolas.tech/docs#/default/read_attribute_definitions_by_type_api_agent_types__type_id__attributes__get


class AgentDBClient:
    """AgentDBClient"""

    def __init__(self, base_url, eth_address, private_key):
        """Constructor"""
        self.base_url = base_url.rstrip("/")
        self.eth_address = eth_address
        self.private_key = private_key
        self.agent = self.get_agent_instance_by_address(self.eth_address)
        self.agent_type = (
            self.get_agent_type_by_type_id(self.agent.type_id) if self.agent else None
        )

    def _sign_request(self, endpoint):
        """Generate authentication"""

        if self.agent is None:
            self.agent = self.get_agent_instance_by_address(self.eth_address)

        timestamp = int(datetime.now(timezone.utc).timestamp())
        message_to_sign = f"timestamp:{timestamp},endpoint:{endpoint}"
        signed_message = Account.sign_message(  # pylint: disable=no-value-for-parameter
            encode_defunct(text=message_to_sign), private_key=self.private_key
        )

        auth_data = {
            "agent_id": self.agent.agent_id,
            "signature": signed_message.signature.hex(),
            "message": message_to_sign,
        }
        return auth_data

    def _request(
        self, method, endpoint, payload=None, params=None, auth=False, nested_auth=True
    ):
        """Make the request"""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        if auth:
            payload = payload or {}
            if nested_auth:
                payload["auth"] = self._sign_request(endpoint)
            else:
                payload = payload | self._sign_request(endpoint)
        response = requests.request(
            method, url, headers=headers, json=payload, params=params
        )
        if response.status_code in [200, 201]:
            return response.json()
        if response.status_code == 404:
            return None
        raise Exception(f"Request failed: {response.status_code} - {response.text}")

    # Agent Type Methods

    def create_agent_type(self, type_name, description) -> Optional[AgentType]:
        """Create agent type"""
        endpoint = "/api/agent-types/"
        payload = {"type_name": type_name, "description": description}
        result = self._request("POST", endpoint, payload)
        return AgentType.model_validate(result) if result else None

    def get_agent_type_by_type_id(self, type_id) -> Optional[AgentType]:
        """Get agent by type"""
        endpoint = f"/api/agent-types/{type_id}/"
        result = self._request("GET", endpoint)
        return AgentType.model_validate(result) if result else None

    def get_agent_type_by_type_name(self, type_name) -> Optional[AgentType]:
        """Get agent by type"""
        endpoint = f"/api/agent-types/name/{type_name}/"
        result = self._request("GET", endpoint)
        return AgentType.model_validate(result) if result else None

    def delete_agent_type(self, agent_type: AgentType):
        """Delete agent type"""
        endpoint = f"/api/agent-types/{agent_type.type_id}/"
        result = self._request("DELETE", endpoint, auth=True, nested_auth=True)
        return AgentType.model_validate(result) if result else None

    # Agent Instance Methods

    def create_agent_instance(
        self, agent_name: str, agent_type: AgentType, eth_address: str
    ) -> Optional[AgentInstance]:
        """Create agent instance"""
        endpoint = "/api/agent-registry/"
        payload = {
            "agent_name": agent_name,
            "type_id": agent_type.type_id,
            "eth_address": eth_address,
        }
        result = self._request("POST", endpoint, payload)
        return AgentInstance.model_validate(result) if result else None

    def get_agent_instance_by_address(self, eth_address) -> Optional[AgentInstance]:
        """Get agent by Ethereum address"""
        endpoint = f"/api/agent-registry/address/{eth_address}"
        result = self._request("GET", endpoint)
        return AgentInstance.model_validate(result) if result else None

    def get_agent_instances_by_type_id(self, type_id) -> List[AgentInstance]:
        """Get agent instances by type"""
        endpoint = f"/api/agent-types/{type_id}/agents/"
        params = {
            "skip": 0,
            "limit": 100,
        }
        result = self._request(method="GET", endpoint=endpoint, params=params)
        return (
            [AgentInstance.model_validate(agent) for agent in result] if result else []
        )

    def delete_agent_instance(self, agent_instance: AgentInstance):
        """Delete agent instance"""
        endpoint = f"/api/agent-registry/{agent_instance.agent_id}/"
        result = self._request("DELETE", endpoint, auth=True, nested_auth=False)
        return AgentInstance.model_validate(result) if result else None

    # Attribute Definition Methods

    def create_attribute_definition(
        self,
        agent_type: AgentType,
        attr_name: str,
        data_type: str,
        default_value: str,
        is_required: bool = False,
    ):
        """Create attribute definition"""
        endpoint = f"/api/agent-types/{agent_type.type_id}/attributes/"
        payload = {
            "type_id": agent_type.type_id,
            "attr_name": attr_name,
            "data_type": data_type,
            "default_value": default_value,
            "is_required": is_required,
        }
        result = self._request("POST", endpoint, {"attr_def": payload}, auth=True)
        return AttributeDefinition.model_validate(result) if result else None

    def get_attribute_definition_by_name(
        self, attr_name: str
    ) -> Optional[AttributeDefinition]:
        """Get attribute definition by name"""
        endpoint = f"/api/attributes/name/{attr_name}"
        result = self._request("GET", endpoint)
        return AttributeDefinition.model_validate(result) if result else None

    def get_attribute_definition_by_id(
        self, attr_id: int
    ) -> Optional[AttributeDefinition]:
        """Get attribute definition by id"""
        endpoint = f"/api/attributes/{attr_id}"
        result = self._request("GET", endpoint)
        return AttributeDefinition.model_validate(result) if result else None

    def get_attribute_definitions_by_agent_type(self, agent_type: AgentType):
        """Get attributes by agent type"""
        endpoint = f"/api/agent-types/{agent_type.type_id}/attributes/"
        result = self._request("GET", endpoint)
        return (
            [AttributeDefinition.model_validate(attr) for attr in result]
            if result
            else []
        )

    def delete_attribute_definition(self, attr_def: AttributeDefinition):
        """Delete attribute definition"""
        endpoint = f"/api/attributes/{attr_def.attr_def_id}/"
        result = self._request("DELETE", endpoint, auth=True, nested_auth=True)
        return AttributeDefinition.model_validate(result) if result else None

    # Attribute Instance Methods

    def create_attribute_instance(
        self,
        agent_instance: AgentInstance,
        attribute_def: AttributeDefinition,
        value: Any,
        value_type="string",
    ) -> Optional[AttributeInstance]:
        """Create attribute instance"""
        endpoint = f"/api/agents/{agent_instance.agent_id}/attributes/"
        payload = {
            "agent_id": agent_instance.agent_id,
            "attr_def_id": attribute_def.attr_def_id,
            f"{value_type}_value": value,
        }
        result = self._request("POST", endpoint, {"agent_attr": payload}, auth=True)
        return AttributeInstance.model_validate(result) if result else None

    def get_attribute_instance(
        self, agent_instance: AgentInstance, attr_def: AttributeDefinition
    ) -> Optional[AttributeInstance]:
        """Get attribute instance by agent ID and attribute definition ID"""
        endpoint = (
            f"/api/agents/{agent_instance.agent_id}/attributes/{attr_def.attr_def_id}/"
        )
        result = self._request("GET", endpoint)
        return AttributeInstance.model_validate(result) if result else None

    def update_attribute_instance(
        self,
        agent_instance: AgentInstance,
        attribute_def: AttributeDefinition,
        attribute_instance: AttributeInstance,
        value: Any,
        value_type="string",
    ) -> Optional[AttributeInstance]:
        """Update attribute instance"""
        endpoint = f"/api/agent-attributes/{attribute_instance.attribute_id}"
        payload = {f"{value_type}_value": value}
        payload = {
            "agent_id": agent_instance.agent_id,
            "attr_def_id": attribute_def.attr_def_id,
            f"{value_type}_value": value,
        }
        result = self._request("PUT", endpoint, {"agent_attr": payload}, auth=True)
        return AttributeInstance.model_validate(result) if result else None

    def delete_attribute_instance(
        self, attribute_instance: AttributeInstance
    ) -> Optional[AttributeInstance]:
        """Delete attribute instance"""
        endpoint = f"/api/agent-attributes/{attribute_instance.attribute_id}"
        result = self._request("DELETE", endpoint, auth=True, nested_auth=True)
        return AttributeInstance.model_validate(result) if result else None

    # Get all attributes of an agent instance

    def get_all_agent_instance_attributes_raw(self, agent_instance: AgentInstance):
        """Get all attributes of an agent by agent ID"""
        endpoint = f"/api/agents/{agent_instance.agent_id}/attributes/"
        payload = {
            "agent_id": agent_instance.agent_id,
        }
        return self._request("GET", endpoint, {"agent_attr": payload}, auth=True)

    def parse_attribute_instance(self, attribute_instance: AttributeInstance):
        """Parse attribute instance"""
        attribute_definition = self.get_attribute_definition_by_id(
            attribute_instance.attr_def_id
        )
        data_type = attribute_definition.data_type
        attr_value = getattr(attribute_instance, f"{data_type}_value", None)

        if data_type == "date":
            attr_value = datetime.fromisoformat(attr_value).astimezone(timezone.utc)
        elif data_type == "json":
            pass
        elif data_type == "string":
            attr_value = str(attr_value)
        elif data_type == "integer":
            attr_value = int(attr_value)
        elif data_type == "float":
            attr_value = float(attr_value)
        elif data_type == "boolean":
            attr_value = bool(attr_value)

        parsed_attribute_instance = {
            "attr_name": attribute_definition.attr_name,
            "attr_value": attr_value,
        }
        return parsed_attribute_instance

    def get_all_agent_instance_attributes_parsed(self, agent_instance: AgentInstance):
        """Get all attributes of an agent by agent ID"""
        attribute_instances = self.get_all_agent_instance_attributes_raw(agent_instance)
        parsed_attributes = [
            self.parse_attribute_instance(AttributeInstance(**attr))
            for attr in attribute_instances
        ]
        return parsed_attributes


class TweetInterface:
    """TweetInterface"""

    def __init__(self, client: AgentDBClient):
        """Constructor"""
        self.client = client

    def register(self):
        """Create the Tweet attribute definition"""




# class User:
#     """User"""

#     def __init__(self, client: AgentDBClient, user_instance: AgentInstance):
#         """Constructor"""
#         self.client = client
#         self.user_instance = ContributeUser
#         self.loaded = False


#     def load(self):
#         """Load agent data"""


#     def add_interaction(self, interaction: TwitterAction):
#         """Add interaction to agent"""


#     def __str__(self) -> str:
#         if not self.loaded:
#             self.load()

#         title = f"@{self.twitter_username}"
#         table = Table(title=title, show_lines=True)
#         table.add_column("Type", style="cyan", no_wrap=True, justify="center")
#         table.add_column("Timestamp", style="magenta", justify="center")
#         table.add_column("Details", style="yellow", justify="center")

#         interactions = self.likes + self.retweets + self.posts + self.follows
#         interactions.sort(key=lambda x: x.timestamp)

#         for interaction in interactions:
#             table.add_row(
#                 interaction.action,
#                 interaction.timestamp.strftime("%Y-%m-%d %H:%M"),
#                 interaction.model_dump_json(exclude={"action", "timestamp"}),
#             )

#         console = Console()
#         with console.capture() as capture:
#             console.print(Align.center(table))

#         return capture.get()


# class ContributeDatabase:
#     """ContributeDatabase"""

#     def __init__(self, client: AgentDBClient):
#         """Constructor"""
#         self.client = client
#         self.agent_type = client.get_agent_type_by_type_name(MEMEOOORR)
#         self.agents = []

#     def load(self):
#         """Load data"""
#         agent_instances = self.client.get_agent_instances_by_type_id(
#             self.agent_type.type_id
#         )
#         for agent_instance in agent_instances:
#             self.agents.append(AgentsFunAgent(self.client, agent_instance))
#             self.agents[-1].load()

#     def get_tweet_likes_number(self, tweet_id) -> int:
#         """Get all tweet likes"""
#         tweet_likes = 0
#         for agent in self.agents:
#             if not agent.loaded:
#                 agent.load()
#             for like in agent.likes:
#                 if like.tweet_id == tweet_id:
#                     tweet_likes += 1
#                     break
#         return tweet_likes

#     def get_tweet_retweets_number(self, tweet_id) -> int:
#         """Get all tweet retweets"""
#         tweet_retweets = 0
#         for agent in self.agents:
#             if not agent.loaded:
#                 agent.load()
#             for retweet in agent.retweets:
#                 if retweet.tweet_id == tweet_id:
#                     tweet_retweets += 1
#                     break
#         return tweet_retweets

#     def get_tweet_replies(self, tweet_id) -> List[TwitterPost]:
#         """Get all tweet replies"""
#         tweet_replies = []
#         for agent in self.agents:
#             if not agent.loaded:
#                 agent.load()
#             for post in agent.posts:
#                 if post.reply_to_tweet_id == tweet_id:
#                     tweet_replies.append(post)
#                     break
#         return tweet_replies

#     def get_tweet_feedback(self, tweet_id) -> Dict[str, Any]:
#         """Get all tweet feedback"""
#         tweet_feedback = {
#             "likes": self.get_tweet_likes_number(tweet_id),
#             "retweets": self.get_tweet_retweets_number(tweet_id),
#             "replies": self.get_tweet_replies(tweet_id),
#         }
#         return tweet_feedback

#     def get_active_agents(self) -> List[AgentsFunAgent]:
#         """Get all active agents"""
#         active_agents = []
#         for agent in self.agents:
#             if not agent.loaded:
#                 agent.load()

#             # An agent is active if it has posted in the last 7 days
#             if not agent.posts:
#                 continue

#             if agent.posts[-1].timestamp < datetime.now(timezone.utc) - timedelta(
#                 days=7
#             ):
#                 continue

#             active_agents.append(agent)
#         return active_agents

#     def __str__(self) -> str:
#         table = Table(title="Agents.fun agent_db", show_lines=True)
#         table.add_column("Agent ID", style="green", justify="center")
#         table.add_column("Twitter name", style="cyan", no_wrap=True, justify="center")
#         table.add_column("Twitter id", style="magenta", justify="center")
#         table.add_column("Agent address", style="yellow", justify="center")

#         for agent in self.agents:
#             if not agent.loaded:
#                 agent.load()
#             table.add_row(
#                 str(agent.agent_instance.agent_id),
#                 agent.twitter_username,
#                 agent.twitter_user_id,
#                 str(agent.agent_instance.eth_address),
#             )

#         console = Console()
#         with console.capture() as capture:
#             console.print(Align.center(table))

#         return capture.get()


# def basic_example(client: AgentDBClient):
#     """Example usage of the AgentDBClient class."""

#     # Read or create agent type
#     memeooorr_type = client.get_agent_type_by_type_name(MEMEOOORR)
#     print(f"memeooorr_type = {memeooorr_type}")

#     if not memeooorr_type:
#         agent_type = client.create_agent_type(
#             type_name=MEMEOOORR, description="Description of memeooorr"
#         )

#     # Read or create agent instance
#     memeooorr_instance = client.get_agent_instance_by_address(client.eth_address)
#     print(f"agent_instance = {memeooorr_instance}")

#     if not memeooorr_instance:
#         agent_instance = client.create_agent_instance(
#             agent_name="Terminator",
#             agent_type=memeooorr_type,
#             eth_address=client.eth_address,
#         )
#         print(f"memeooorr_instance = {memeooorr_instance}")

#     # Read or create atttribute definition
#     twitter_username_attr_def = client.get_attribute_definition_by_name(
#         "twitter_username"
#     )
#     print(f"twitter_username_attr_def = {twitter_username_attr_def}")

#     if not twitter_username_attr_def:
#         twitter_username_attr_def = client.create_attribute_definition(
#             agent_type=memeooorr_type,
#             attr_name="twitter_username",
#             data_type="string",
#             default_value="",
#             is_required=True,
#         )
#         print(f"twitter_username_attr_def = {twitter_username_attr_def}")

#     # Get agent type attributes
#     memeooorr_attrs = client.get_attribute_definitions_by_agent_type(memeooorr_type)
#     print(f"memeooorr_attrs = {memeooorr_attrs}")

#     # Ensure Attribute Instance exists
#     twitter_username_attr_instance = client.get_attribute_instance(
#         memeooorr_instance, twitter_username_attr_def
#     )
#     print(f"twitter_username_attr_instance = {twitter_username_attr_instance}")

#     # Create or update attribute instance
#     if not twitter_username_attr_instance:
#         twitter_username_instance = client.create_attribute_instance(
#             agent_instance=memeooorr_instance,
#             attribute_def=twitter_username_attr_def,
#             value="user123",
#         )
#         print(f"twitter_username_instance = {twitter_username_instance}")
#     else:
#         client.update_attribute_instance(
#             agent_instance=memeooorr_instance,
#             attribute_def=twitter_username_attr_def,
#             attribute_instance=twitter_username_attr_instance,
#             value="new_terminator",
#         )
#         print(f"Updated twitter_username_instance = {twitter_username_attr_instance}")

#     # Get all attributes of an agent
#     all_attributes = client.get_all_agent_instance_attributes_parsed(memeooorr_instance)
#     print(f"all_attributes = {all_attributes}")


# def init_memeooorr_db(client: AgentDBClient):
#     """Initialize the memeooorr database"""

#     # Read or create agent type
#     memeooorr_type = client.get_agent_type_by_type_name(MEMEOOORR)

#     if not memeooorr_type:
#         print(f"Creating agent type {MEMEOOORR}")
#         memeooorr_type = client.create_agent_type(
#             type_name=MEMEOOORR, description="Description of memeooorr"
#         )
#     print(f"memeooorr_type = {memeooorr_type}")

#     # Read or create agent instance (needed to sign)
#     memeooorr_instance = client.get_agent_instance_by_address(client.eth_address)

#     if not memeooorr_instance:
#         print(f"Creating agent instance {client.eth_address}")
#         memeooorr_instance = client.create_agent_instance(
#             agent_name="Terminator",
#             agent_type=memeooorr_type,
#             eth_address=client.eth_address,
#         )
#     print(f"memeooorr_instance = {memeooorr_instance}")

#     # Read or create attribute definitions
#     memeooorr_attrs = client.get_attribute_definitions_by_agent_type(memeooorr_type)

#     if not memeooorr_attrs:
#         print("Creating agent type attributes")
#         twitter_username_attr_def = client.create_attribute_definition(
#             agent_type=memeooorr_type,
#             attr_name="twitter_username",
#             data_type="string",
#             default_value="",
#             is_required=True,
#         )
#         twitter_user_id_attr_def = client.create_attribute_definition(
#             agent_type=memeooorr_type,
#             attr_name="twitter_user_id",
#             data_type="string",
#             default_value="",
#             is_required=True,
#         )
#         twitter_interactions_attr_def = client.create_attribute_definition(
#             agent_type=memeooorr_type,
#             attr_name="twitter_interactions",
#             data_type="json",
#             default_value="{}",
#             is_required=False,
#         )
#         memeooorr_attrs = client.get_attribute_definitions_by_agent_type(memeooorr_type)
#     else:
#         (
#             twitter_username_attr_def,
#             twitter_user_id_attr_def,
#             twitter_interactions_attr_def,
#         ) = memeooorr_attrs

#     print(f"memeooorr_attrs = {memeooorr_attrs}")

#     # Create attribute instances
#     twitter_username_attr_instance = client.get_attribute_instance(
#         memeooorr_instance, twitter_username_attr_def
#     )
#     if not twitter_username_attr_instance:
#         print("Creating twitter_username attribute instance")
#         twitter_username_attr_instance = client.create_attribute_instance(
#             agent_instance=memeooorr_instance,
#             attribute_def=twitter_username_attr_def,
#             value="0xTerminator",
#         )
#     print(f"twitter_username_attr_instance = {twitter_username_attr_instance}")

#     twitter_user_id_attr_instance = client.get_attribute_instance(
#         memeooorr_instance, twitter_user_id_attr_def
#     )
#     if not twitter_user_id_attr_instance:
#         print("Creating twitter_user_id attribute instance")
#         twitter_user_id_attr_instance = client.create_attribute_instance(
#             agent_instance=memeooorr_instance,
#             attribute_def=twitter_user_id_attr_def,
#             value="1234567890",
#         )
#     print(f"twitter_user_id_attr_instance = {twitter_user_id_attr_instance}")

#     # Load the database
#     agents_fun_db = AgentsFunDatabase(client=client)
#     agents_fun_db.load()

#     # Add a post
#     post = TwitterPost(
#         timestamp=datetime.now(timezone.utc),
#         tweet_id="1234567890",
#         text="Hello, world!",
#     )
#     agents_fun_db.agents[0].add_interaction(post)

#     # Add a retweet
#     retweet = TwitterRewtweet(
#         timestamp=datetime.now(timezone.utc),
#         tweet_id="0987654321",
#     )
#     agents_fun_db.agents[0].add_interaction(retweet)

#     # Add a like
#     like = TwitterLike(
#         timestamp=datetime.now(timezone.utc),
#         tweet_id="1234567890",
#     )
#     agents_fun_db.agents[0].add_interaction(like)

#     # Add a follow
#     follow = TwitterFollow(
#         timestamp=datetime.now(timezone.utc),
#         username="another_user",
#     )
#     agents_fun_db.agents[0].add_interaction(follow)


# def reset_agents_fun_db(client: AgentDBClient):
#     """Reset the database"""

#     agents_fun_db = AgentsFunDatabase(client=client)
#     agents_fun_db.load()

#     for agent in agents_fun_db.agents:
#         # Delete attributes instances
#         memeooorr_attrs = client.get_all_agent_instance_attributes_parsed(
#             agent.agent_instance
#         )
#         for attr in memeooorr_attrs:
#             print(f"Deleting agent attribute {attr.attr_def_id}")
#             client.delete_attribute_instance(attr)

#         # Delete agent instance
#         print(f"Deleting agent instance {agent.agent_instance.agent_id}")
#         client.delete_agent_instance(agent.agent_instance)

#     # Delete attribute definitions
#     memeooorr_attr_defs = client.get_attribute_definitions_by_agent_type(
#         agents_fun_db.agent_type
#     )
#     for attr_def in memeooorr_attr_defs:
#         print(f"Deleting attribute definition {attr_def.attr_def_id}")
#         client.delete_attribute_definition(attr_def)

#     # Delete agent type
#     print(f"Deleting agent type {agents_fun_db.agent_type.type_id}")
#     client.delete_agent_type(agents_fun_db.agent_type)


# def memeooorr_example(client: AgentDBClient):
#     """Example usage of the AgentDBClient class."""
#     agents_fun_db = AgentsFunDatabase(client=client)
#     agents_fun_db.load()

#     print(agents_fun_db)
#     for agent in agents_fun_db.agents:
#         if agent.likes or agent.retweets or agent.posts or agent.follows:
#             print(agent)


def load_ceramic_data():
    """Load the contribute database from JSON files."""
    # Load the user and centaurs databases from JSON files
    with open("contribute_db.json", "r", encoding="utf-8") as file:
        user_db = json.load(file)

        for user_id, user in user_db["users"].items():
            user["id"] = user_id
            for tweet_id, tweet in user["tweets"].items():
                tweet["tweet_id"] = tweet_id
                tweet["twitter_user_id"] = user["twitter_id"]

    with open("contribute_centaurs.json", "r", encoding="utf-8") as file:
        centaurs_db = json.load(file)

        for tweet in centaurs_db[0]["plugins_data"]["scheduled_tweet"]["tweets"]:
            if not tweet["proposer"]["address"]:
                tweet["proposer"]["address"] = ZERO_ADDRESS

        for tweet in centaurs_db[0]["plugins_data"]["twitter_campaigns"]["campaigns"]:
            if not tweet["proposer"]["address"]:
                tweet["proposer"]["address"] = ZERO_ADDRESS

    # Combine the data
    combined_db = {
        "users": user_db["users"],
        "module_data": user_db["module_data"] | centaurs_db[0]["plugins_data"],
        "module_configs": centaurs_db[0]["configuration"]["plugins"],
    }
    return combined_db


if __name__ == "__main__":

    contribute_db = ContributeDatabase(**load_ceramic_data())

    # Initialize the client
    db_client = AgentDBClient(
        base_url=os.getenv("AGENT_DB_BASE_URL"),
        eth_address=os.getenv("AGENT_ADDRESS"),
        private_key=os.getenv("AGENT_PRIVATE_KEY"),
    )

    contribute_type = db_client.get_agent_type_by_type_name(CONTRIBUTE)

    # Create Contribute agent
    if not contribute_type:
        contribute_type = db_client.create_agent_type(
            type_name="contribute",
            description="A service that tracks contributions to the Olas ecosystem.",
        )
    print(contribute_type)

    # Create Contribute instance
    contribute_instance = db_client.get_agent_instance_by_address(db_client.eth_address)
    if not contribute_instance:
        contribute_instance = db_client.create_agent_instance(
            agent_name="Contribute",
            agent_type=contribute_type,
            eth_address=db_client.eth_address,
        )
    print(contribute_instance)

    # Create attribute definitions

    # Tweets
    tweet_attr_def = db_client.get_attribute_definition_by_name("tweet")
    if not tweet_attr_def:
        tweet_attr_def = db_client.create_attribute_definition(
            agent_type=contribute_type,
            attr_name="tweet",
            data_type="json",
            default_value="{}",
        )
    print(tweet_attr_def)

    # User
    user_attr_def = db_client.get_attribute_definition_by_name("user")
    if not user_attr_def:
        user_attr_def = db_client.create_attribute_definition(
            agent_type=contribute_type,
            attr_name="user",
            data_type="json",
            default_value="{}",
        )
    print(user_attr_def)

    # ModuleConfig
    module_config_attr_def = db_client.get_attribute_definition_by_name("module_config")
    if not module_config_attr_def:
        module_config_attr_def = db_client.create_attribute_definition(
            agent_type=contribute_type,
            attr_name="module_config",
            data_type="json",
            default_value="{}",
        )
    print(module_config_attr_def)

    # ModuleData
    module_data_attr_def = db_client.get_attribute_definition_by_name("module_data")
    if not module_data_attr_def:
        module_data_attr_def = db_client.create_attribute_definition(
            agent_type=contribute_type,
            attr_name="module_data",
            data_type="json",
            default_value="{}",
        )
    print(module_data_attr_def)

    # Dummy
    dummy_data_attr_def = db_client.get_attribute_definition_by_name("dummy")
    if not dummy_data_attr_def:
        dummy_data_attr_def = db_client.create_attribute_definition(
            agent_type=contribute_type,
            attr_name="dummy",
            data_type="json",
            default_value="{}",
        )
    print(dummy_data_attr_def)

    # Create attribute instances
    # dummy_instance_1 = db_client.create_attribute_instance(
    #     agent_instance=contribute_instance,
    #     attribute_def=dummy_data_attr_def,
    #     value={"a": 1},
    #     value_type="json",
    # )
    # print(dummy_instance_1)

    # dummy_instance_2 = db_client.create_attribute_instance(
    #     agent_instance=contribute_instance,
    #     attribute_def=dummy_data_attr_def,
    #     value={"a": 1},
    #     value_type="json",
    # )
    # print(dummy_instance_2)

    isntance = db_client.get_attribute_instance(
        agent_instance=contribute_instance,
        attr_def=dummy_data_attr_def,
    )
    print(isntance)

    # print(db_client.get_all_agent_instance_attributes_raw(contribute_instance))

    # Tweets
    # for tweet in contribute_db.users

    # Users

    # ModuleConfig

    # ModuleData