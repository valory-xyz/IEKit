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

# pylint: disable=unused-variable,too-many-arguments,too-many-instance-attributes,wrong-import-position,redefined-outer-name

import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import dotenv
import requests
from eth_account import Account
from eth_account.messages import encode_defunct
from pydantic import BaseModel

from packages.valory.skills.agent_db_abci.agent_db_models import (
    AgentInstance,
    AgentType,
    AttributeDefinition,
    AttributeInstance,
)
from packages.valory.skills.contribute_db_abci.contribute_models import (
    ContributeData,
    ContributeUser,
    ModuleConfigs,
    ModuleData,
    UserTweet,
)


dotenv.load_dotenv(override=True)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
CONTRIBUTE = "contribute"

# https://axatbhardwaj.notion.site/MirrorDB-Agent-and-Attribute-Data-Flow-1eac8d38bc0b80edae04ff1017d80f58
# https://afmdb.autonolas.tech/docs#/default/read_attribute_definitions_by_type_api_agent_types__type_id__attributes__get


def are_models_different(model1: BaseModel, model2: BaseModel) -> bool:
    """Get the different attributes between two Pydantic models."""
    if not isinstance(model2, type(model1)):
        raise ValueError("Models must be of the same type to compare attributes.")

    diffs = []
    dict1 = model1.model_dump(mode="json")
    dict2 = model2.model_dump(mode="json")

    for key in dict1.keys():
        if dict1[key] != dict2[key]:
            diffs.append(key)

    are_different = len(diffs) > 0

    if are_different:
        print(f"Different attributes detected: {diffs}")
    return are_different


class AgentDBClient:
    """AgentDBClient"""

    def __init__(self, base_url, eth_address, private_key):
        """Constructor"""
        self.base_url = base_url.rstrip("/")
        self.eth_address = eth_address
        self.private_key = private_key
        self._attribute_definition_cache: Dict[int, AttributeDefinition] = {}
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

        print(
            f"Made {method} request to {url} with payload: {payload} and params: {params}. Response: {response.status_code}. Response text: {getattr(response, 'text', '')}"
        )

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
        if attr_id in self._attribute_definition_cache:
            return self._attribute_definition_cache[attr_id]
        endpoint = f"/api/attributes/{attr_id}"
        result = self._request("GET", endpoint)
        if result:
            definition = AttributeDefinition.model_validate(result)
            self._attribute_definition_cache[attr_id] = definition
            return definition
        return None

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

    def get_first_attribute_instance_by_attribute_definition(
        self, agent_instance: AgentInstance, attr_def: AttributeDefinition
    ) -> Optional[AttributeInstance]:
        """Get attribute instance by agent ID and attribute definition ID"""
        endpoint = (
            f"/api/agents/{agent_instance.agent_id}/attributes/{attr_def.attr_def_id}/"
        )
        result = self._request("GET", endpoint)
        return AttributeInstance.model_validate(result) if result else None

    def get_attribute_instance_by_attribute_id(
        self, attribute_id: int
    ) -> Optional[AttributeInstance]:
        """Get attribute instance by attribute ID"""
        endpoint = (
            f"/api/agent-attributes/{attribute_id}"
        )
        result = self._request("GET", endpoint)
        return AttributeInstance.model_validate(result) if result else None

    def update_attribute_instance(
        self,
        agent_instance: AgentInstance,
        attribute_def: AttributeDefinition,
        attribute_instance_id: int,
        value: Any,
        value_type="string",
    ) -> Optional[AttributeInstance]:
        """Update attribute instance"""
        endpoint = f"/api/agent-attributes/{attribute_instance_id}"
        payload = {f"{value_type}_value": value}
        payload = {
            "agent_id": agent_instance.agent_id,
            "attr_def_id": attribute_def.attr_def_id,
            f"{value_type}_value": value,
        }
        result = self._request("PUT", endpoint, {"agent_attr": payload}, auth=True)
        return AttributeInstance.model_validate(result) if result else None

    def delete_attribute_instance(
        self, attribute_instance_id: int
    ) -> Optional[AttributeInstance]:
        """Delete attribute instance"""
        endpoint = f"/api/agent-attributes/{attribute_instance_id}"
        result = self._request("DELETE", endpoint, auth=True, nested_auth=False)
        return AttributeInstance.model_validate(result) if result else None

    # Get all attributes of an agent instance

    def get_all_agent_instance_attributes_raw(self, agent_instance: AgentInstance):
        """Get all attributes of an agent by agent ID"""
        endpoint = f"/api/agents/{agent_instance.agent_id}/attributes/"
        payload = {
            "agent_id": agent_instance.agent_id,
        }
        raw_attributes = []
        skip = 0
        while True:
            params = {
                "skip": skip,
                "limit": 100,
            }
            print(f"Reading agent attributes from {skip} to {skip + 100}... ", end="")
            result = self._request(method="GET", endpoint=endpoint, payload={"agent_attr": payload}, params=params, auth=True)

            if result is None:
                print("Error fetching agent attributes")
                continue

            print(f"got {len(result)} attributes")

            raw_attributes += result
            skip = len(raw_attributes)

            if len(result) < 100:
                return raw_attributes

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
            "attr_id": attribute_instance.attribute_id,
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


class JsonAttributeInterface:
    """JsonAttributeInterface"""

    attribute_name: str = None

    def __init__(self, client_: AgentDBClient):
        """Constructor"""
        self.client = client_
        self.attr_def = self.client.get_attribute_definition_by_name(self.attribute_name)

    def create_definition(self):
        """Create the attribute definition"""
        if not self.attr_def:
            self.attr_def = self.client.create_attribute_definition(
                agent_type=self.client.agent_type,
                attr_name=self.attribute_name,
                data_type="json",
                default_value="{}",
            )
            print(f"Created attribute definition: {self.attribute_name}")

    def create_instance(
        self, model: BaseModel
    ) -> Optional[AttributeInstance]:
        """Create an attribute instance"""
        attr_def = self.client.get_attribute_definition_by_name(self.attribute_name)
        if not attr_def:
            raise ValueError(f"{self.attribute_name} attribute definition not found")

        # Create or update the tweet attribute instance
        attr_instance = self.client.create_attribute_instance(
            agent_instance=self.client.agent,
            attribute_def=attr_def,
            value=model.model_dump(mode="json"),
            value_type="json",
        )
        return attr_instance

    def update_instance(
        self, model: BaseModel
    ) -> Optional[AttributeInstance]:
        """Update an attribute instance"""
        attr_def = self.client.get_attribute_definition_by_name(self.attribute_name)
        if not attr_def:
            raise ValueError(f"{self.attribute_name} attribute definition not found")

        # Update the attribute instance
        updated_instance = self.client.update_attribute_instance(
            agent_instance=self.client.agent,
            attribute_def=attr_def,
            attribute_instance_id=model.attribute_instance_id,
            value=model.model_dump(mode="json"),
            value_type="json",
        )
        return updated_instance


class TweetAttributeInterface(JsonAttributeInterface):
    """TweetAttribute"""
    attribute_name = "tweet"


class UserAttributeInterface(JsonAttributeInterface):
    """UserAttribute"""
    attribute_name = "user"


class ModuleConfigsAttributeInterface(JsonAttributeInterface):
    """ModuleConfigsAttribute"""
    attribute_name = "module_configs"


class ModuleDataAttributeInterface(JsonAttributeInterface):
    """ModuleDataAttribute"""
    attribute_name = "module_data"


class ContributeDatabase:
    """ContributeDatabase"""

    def __init__(self, client_: AgentDBClient):
        """Constructor"""
        self.client = client_
        self.agent = self.client.agent
        self.agent_type = self.client.agent_type
        self.tweet_interface = TweetAttributeInterface(self.client)
        self.user_interface = UserAttributeInterface(self.client)
        self.module_configs_interface = ModuleConfigsAttributeInterface(self.client)
        self.module_data_interface = ModuleDataAttributeInterface(self.client)
        self.data = ContributeData()

    def register(self):
        """Register agent and all definitions"""
        contribute_type = self.client.get_agent_type_by_type_name(CONTRIBUTE)

        # Create Contribute agent
        if not contribute_type:
            contribute_type = self.client.create_agent_type(
                type_name="contribute",
                description="A service that tracks contributions to the Olas ecosystem.",
            )
            print(f"Created agent type: {contribute_type.type_name}")

        self.agent_type = contribute_type
        self.client.agent_type = contribute_type

        # Create Contribute instance
        contribute_instance = self.client.get_agent_instance_by_address(self.client.eth_address)
        if not contribute_instance:
            contribute_instance = self.client.create_agent_instance(
                agent_name="Contribute",
                agent_type=contribute_type,
                eth_address=self.client.eth_address,
            )
            print(f"Created agent instance: {contribute_instance.agent_name}")

        self.agent = contribute_instance
        self.client.agent = contribute_instance

        # Register attribute definitions
        self.tweet_interface.create_definition()
        self.user_interface.create_definition()
        self.module_configs_interface.create_definition()
        self.module_data_interface.create_definition()

    def get_user_by_attribute(self, key, value) -> Optional[ContributeUser]:
        """Get a user by one of its attributes"""

        if key not in ContributeUser.model_fields:
            raise ValueError(f"Invalid user attribute: {key}")

        for user_id, user in self.data.users.items():
            if getattr(user, key, None) == value:
                return user
        print(f"User with {key}={value} not found in the database.")
        return None

    def create_tweet(self, tweet: UserTweet) -> Optional[AttributeInstance]:
        """Create a tweet attribute instance"""

        # Check that the user exists
        user = self.get_user_by_attribute("twitter_id", tweet.twitter_user_id)

        if not user:
            print(
                f"User with twitter_id {tweet.twitter_user_id} not found. Creating new user..."
            )
            user = ContributeUser(
                id=self.get_next_user_id(),
                twitter_id=tweet.twitter_user_id,
                twitter_handle=tweet.twitter_handle,
            )
            self.create_user(user)

        print(
            f"Creating tweet: {tweet.tweet_id} for user {tweet.twitter_user_id}"
        )

        # Create the new tweet
        tweet_instance = self.tweet_interface.create_instance(tweet)

        tweet.attribute_instance_id = (
            tweet_instance.attribute_id if tweet_instance else None
        )
        self.data.tweets[tweet.tweet_id] = tweet

        # Update the user
        print(f"Updating user {tweet.twitter_user_id} with new tweet")

        user.tweets[tweet.tweet_id] = tweet

        self.user_interface.update_instance(user)

        return tweet_instance

    def update_tweet(self, tweet: UserTweet) -> Optional[AttributeInstance]:
        """Update a tweet attribute instance"""
        return self.tweet_interface.update_instance(tweet)

    def create_user(self, user: ContributeUser) -> Optional[AttributeInstance]:
        """Create a user attribute instance"""
        print(f"Creating user: {user.id} with twitter_id {user.twitter_id}")
        user_instance = self.user_interface.create_instance(user)
        if user_instance:
            self.data.users[user.id] = user
        return user_instance

    def update_user(self, user: ContributeUser) -> Optional[AttributeInstance]:
        """Update a user attribute instance"""
        result = self.user_interface.update_instance(user)
        return result

    def create_module_configs(self, config: ModuleConfigs) -> Optional[AttributeInstance]:
        """Create a plugin config attribute instance"""
        print("Creating module configs")
        module_configs_instance = self.module_configs_interface.create_instance(config)
        if module_configs_instance:
            self.data.module_configs = config
            self.data.module_configs.attribute_instance_id = module_configs_instance.attribute_id
        return module_configs_instance

    def update_module_configs(self, configs: ModuleConfigs) -> Optional[AttributeInstance]:
        """Update a plugin config attribute instance"""
        return self.module_configs_interface.update_instance(configs)

    def create_module_data(self, data: ModuleData) -> Optional[AttributeInstance]:
        """Create a plugin data attribute instance"""
        print("Creating module data")
        module_data_instance = self.module_data_interface.create_instance(data)
        if module_data_instance:
            self.data.module_data = data
            self.data.module_data.attribute_instance_id = module_data_instance.attribute_id
        return module_data_instance

    def update_module_data(self, data: ModuleData) -> Optional[AttributeInstance]:
        """Update a plugin data attribute instance"""
        return self.module_data_interface.update_instance(data)

    def create_or_update_user_by_key(self, key: str, value: Any, user: ContributeUser):
        """Creates or updates a user"""
        user = self.get_user_by_attribute(key, value)
        if not user:
            self.create_user(user)
        else:
            self.update_user(user)

    def load_from_remote_db(self):
        """Load data from the remote database."""

        attributes = self.client.get_all_agent_instance_attributes_parsed(self.client.agent)

        for attribute in attributes:
            attr_name = attribute["attr_name"]
            attr_data = attribute["attr_value"] | {"attribute_instance_id": attribute["attr_id"]}
            print(f"Loading attribute: {attr_name} with id: {attribute['attr_id']}")

            if attr_name == "tweet":
                tweet = UserTweet(**attr_data)
                self.data.tweets[tweet.tweet_id] = tweet
                continue

            if attr_name == "user":
                attr_data["tweets"] = {}
                user = ContributeUser(**attr_data)

                if user.id in self.data.users:
                    raise ValueError(f"User with id {user.id} already exists.\nExisting: {self.data.users[user.id]}\nNew: {user}")

                self.data.users[user.id] = user
                continue

            if attr_name == "module_configs":
                module_configs = ModuleConfigs(**attr_data)
                self.data.module_configs = module_configs
                continue

            if attr_name == "module_data":
                module_data = ModuleData(**attr_data)
                self.data.module_data = module_data
                continue

            raise ValueError(
                f"Unknown attribute name: {attr_name}"
            )

        self.data.sort()

        for tweet_id, tweet in self.data.tweets.items():
            user = self.get_user_by_attribute("twitter_id", tweet.twitter_user_id)

            if user is None:
                print(f"Tweet with id {tweet_id} has no user associated with it. Skipping...")
                continue

            user.tweets[tweet_id] = tweet

    def get_next_user_id(self):
        """Get next user id"""
        next_id = 0 if not self.data.users else sorted(self.data.users.keys())[-1] + 1
        if next_id in self.data.users:
            raise ValueError(f"Next user ID {next_id} already exists in the database.")
        return next_id


def load_ceramic_data():
    """Load the contribute database from JSON files."""
    # Load the user and centaurs databases from JSON files
    tweets = {}
    with open("contribute_db.json", "r", encoding="utf-8") as file:
        user_db = json.load(file)

        for user_id, user in user_db["users"].items():
            user["id"] = user_id
            for tweet_id, tweet in user["tweets"].items():
                tweet["tweet_id"] = tweet_id
                tweet["twitter_user_id"] = user["twitter_id"]
                tweets[tweet_id] = tweet

    with open("contribute_centaurs.json", "r", encoding="utf-8") as file:
        centaurs_db = json.load(file)

        for tweet in centaurs_db[0]["plugins_data"]["scheduled_tweet"]["tweets"]:
            if not tweet["proposer"]["address"]:
                tweet["proposer"]["address"] = ZERO_ADDRESS

        for tweet in centaurs_db[0]["plugins_data"]["twitter_campaigns"]["campaigns"]:
            if not tweet["proposer"]["address"]:
                tweet["proposer"]["address"] = ZERO_ADDRESS

    print(f"Loaded {len(user_db['users'])} users and {len(tweets)} tweets from contribute_db.json")

    # Combine the data
    combined_db = {
        "users": user_db["users"],
        "tweets": tweets,
        "module_data": user_db["module_data"] | centaurs_db[0]["plugins_data"],
        "module_configs": centaurs_db[0]["configuration"]["plugins"],
    }
    return combined_db


def sync_remote_db(local_data, remote_db):
    """Initialize the contribute database from Ceramic data."""

    remote_db.register()

    # Users
    for user_id, local_user in local_data.users.items():

        # Add new users to the remote db
        if user_id not in remote_db.data.users:
            print(f"Creating user {user_id} with twitter_id {local_user.twitter_id}")
            user_attribute = remote_db.create_user(local_user)
            remote_db.data.users[user_id].attribute_instance_id = user_attribute.attribute_id if user_attribute else None
            continue

        remote_user = remote_db.data.users[user_id]

        # Update existing users
        local_user.attribute_instance_id = remote_user.attribute_instance_id
        if are_models_different(remote_user, local_user):
            print(f"Updating user {user_id} with new data")
            remote_db.update_user(local_user)

    # Tweets
    for i, local_tweet in enumerate(local_data.tweets.values()):

        # Skip existing tweets
        if local_tweet.tweet_id in remote_db.data.tweets:
            continue

        print(f"Creating tweet {i + 1}: {local_tweet.tweet_id} for user {local_tweet.twitter_user_id}")
        tweet_attribute = remote_db.create_tweet(local_tweet)
        remote_db.data.tweets[local_tweet.tweet_id].attribute_instance_id = tweet_attribute.attribute_id if tweet_attribute else None

    # ModuleConfigs
    local_data.module_configs.attribute_instance_id = remote_db.data.module_configs.attribute_instance_id
    remote_db.update_module_configs(local_data.module_configs)

    # ModuleData
    local_data.module_data.attribute_instance_id = remote_db.data.module_data.attribute_instance_id
    remote_db.update_module_data(local_data.module_data)


def clear_remote_db(remote_db):
    """Remove all data from the remote database."""

    print("Clearing remote database...")

    # Clear tweets
    for tweet_id, tweet in remote_db.data.tweets.items():
        if tweet.attribute_instance_id is not None:
            remote_db.client.delete_attribute_instance(tweet.attribute_instance_id)

    # Clear users
    for user_id, user in remote_db.data.users.items():
        if user.attribute_instance_id is not None:
            print(f"Deleting user {user_id} with attribute instance ID {user.attribute_instance_id}")
            remote_db.client.delete_attribute_instance(user.attribute_instance_id)

    # Clear module configs
    if remote_db.data.module_configs and remote_db.data.module_configs.attribute_instance_id:
        remote_db.client.delete_attribute_instance(remote_db.data.module_configs.attribute_instance_id)

    # Clear module data
    if remote_db.data.module_data and remote_db.data.module_data.attribute_instance_id:
        remote_db.client.delete_attribute_instance(remote_db.data.module_data.attribute_instance_id)

    print("Remote database cleared")


def main():
    """Main"""

    # Initialize the client
    client = AgentDBClient(
        base_url=os.getenv("AGENT_DB_BASE_URL"),
        eth_address=os.getenv("CONTRIBUTE_DB_ADDRESS"),
        private_key=os.getenv("CONTRIBUTE_DB_PKEY"),
    )

    # Load the contribute data from JSON files
    # local_data = ContributeData(**load_ceramic_data())
    # local_data.sort()
    # print(f"Local database: loaded {len(local_data.users)} users and {len(local_data.tweets)} tweets.")

    # Load the remote database
    remote_db = ContributeDatabase(client)
    remote_db.load_from_remote_db()
    print(f"Remote database: loaded {len(remote_db.data.users)} users and {len(remote_db.data.tweets)} tweets.")

    # Sync both databases
    # sync_remote_db(local_data, remote_db)

    # Clear the remote database
    # clear_remote_db(remote_db)


if __name__ == "__main__":
    main()
