# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2025 Valory AG
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

from typing import Any, Optional, Tuple

from aea.skills.base import Model
from pydantic import BaseModel
from pydantic_core._pydantic_core import ValidationError

from packages.valory.skills.agent_db_abci.agent_db_client import (
    AgentDBClient,
    AttributeInstance,
)
from packages.valory.skills.contribute_db_abci.contribute_models import (
    ContributeData,
    ContributeUser,
    ModuleConfigs,
    ModuleData,
    UserTweet,
)


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
CONTRIBUTE = "contribute"


class JsonAttributeInterface:
    """JsonAttributeInterface"""

    attribute_name: str = None

    def __init__(self, client: AgentDBClient):
        """Constructor"""
        self.client = client

    def create_definition(self):
        """Create the attribute definition"""
        attr_def = yield from self.client.get_attribute_definition_by_name(
            self.attribute_name
        )
        if not attr_def:
            attr_def = yield from self.client.create_attribute_definition(
                agent_type=self.client.agent_type,
                attr_name=self.attribute_name,
                data_type="json",
                default_value="{}",
            )
            print(f"Created attribute definition: {self.attribute_name}")

    def get_instance(self, attribute_id) -> Optional[AttributeInstance]:
        """Get an attribute instance"""
        attribute_instance = self.client.get_attribute_instance_by_attribute_id(
            attribute_id
        )
        return attribute_instance

    def create_instance(self, model: BaseModel) -> Optional[AttributeInstance]:
        """Create an attribute instance"""
        attr_def = yield from self.client.get_attribute_definition_by_name(
            self.attribute_name
        )
        if not attr_def:
            raise ValueError(f"{self.attribute_name} attribute definition not found")

        # Create or update the tweet attribute instance
        attr_instance = yield from self.client.create_attribute_instance(
            agent_instance=self.client.agent,
            attribute_def=attr_def,
            value=model.model_dump(mode="json"),
            value_type="json",
        )
        return attr_instance

    def update_instance(self, model: BaseModel) -> Optional[AttributeInstance]:
        """Update an attribute instance"""
        attr_def = yield from self.client.get_attribute_definition_by_name(
            self.attribute_name
        )
        if not attr_def:
            raise ValueError(f"{self.attribute_name} attribute definition not found")

        if model.attribute_instance_id is None:
            raise ValueError(
                f"Attribute instance ID is required for updating {self.attribute_name}."
            )

        # Update the attribute instance
        updated_instance = yield from self.client.update_attribute_instance(
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


class ContributeDatabase(Model):
    """ContributeDatabase"""

    def __init__(self, **kwargs: Any):
        """Constructor"""
        super().__init__(**kwargs)
        self.client = None
        self.agent_address = None
        self.logger = None
        self.agent = None
        self.agent_type = None
        self.tweet_interface = None
        self.user_interface = None
        self.module_configs_interface = None
        self.module_data_interface = None
        self.data = ContributeData()
        self.writer_addresses = []  # which addresses should write to the db
        self.loaded = False

    def initialize(self, client: AgentDBClient, agent_address: str):
        """Initialize agent"""
        self.client = client
        self.agent_address = agent_address
        self.logger = self.client.logger
        self.tweet_interface = TweetAttributeInterface(self.client)
        self.user_interface = UserAttributeInterface(self.client)
        self.module_configs_interface = ModuleConfigsAttributeInterface(self.client)
        self.module_data_interface = ModuleDataAttributeInterface(self.client)
        self.agent = self.client.agent
        self.agent_type = self.client.agent_type

    def register(self):
        """Register agent and all definitions"""
        contribute_type = yield from self.client.get_agent_type_by_type_name(CONTRIBUTE)

        # Create Contribute agent
        if not contribute_type:
            contribute_type = yield from self.client.create_agent_type(
                type_name="contribute",
                description="A service that tracks contributions to the Olas ecosystem.",
            )
            self.logger.info(f"Created agent type: {contribute_type.type_name}")

        self.agent_type = contribute_type
        self.client.agent_type = contribute_type

        # Create Contribute instance
        contribute_instance = yield from self.client.get_agent_instance_by_address(
            self.client.eth_address
        )
        if not contribute_instance:
            contribute_instance = yield from self.client.create_agent_instance(
                agent_name="Contribute",
                agent_type=contribute_type,
                eth_address=self.client.eth_address,
            )
            self.logger.info(
                f"Created agent instance: {contribute_instance.agent_name}"
            )

        self.agent = contribute_instance
        self.client.agent = contribute_instance

        # Register attribute definitions
        yield from self.tweet_interface.create_definition()
        yield from self.user_interface.create_definition()
        yield from self.module_configs_interface.create_definition()
        yield from self.module_data_interface.create_definition()

    def get_user_by_attribute(self, key, value) -> Optional[ContributeUser]:
        """Get a user by one of its attributes"""

        if key not in ContributeUser.model_fields:
            raise ValueError(f"Invalid user attribute: {key}")

        for user in self.data.users.values():
            if getattr(user, key, None) == value:
                return user
        self.logger.warning(f"User with {key}={value} not found in the database.")
        return None

    def create_tweet(self, tweet: UserTweet) -> Optional[AttributeInstance]:
        """Create a tweet attribute instance"""

        # Check that the user exists
        user = self.get_user_by_attribute("twitter_id", tweet.twitter_user_id)

        if not user:
            self.logger.info(
                f"User with twitter_id {tweet.twitter_user_id} not found. Creating new user..."
            )
            user = ContributeUser(
                id=self.get_next_user_id(),
                twitter_id=tweet.twitter_user_id,
                twitter_handle=tweet.twitter_handle,
            )
            yield from self.create_user(user)

        self.logger.info(
            f"Creating tweet: {tweet.tweet_id} for user {tweet.twitter_user_id}"
        )

        # Create the new tweet
        tweet_instance = yield from self.tweet_interface.create_instance(tweet)

        tweet.attribute_instance_id = (
            tweet_instance.attribute_id if tweet_instance else None
        )
        self.data.tweets[tweet.tweet_id] = tweet

        # Update the user
        self.logger.info(f"Updating user {tweet.twitter_user_id} with new tweet")

        user.tweets[tweet.tweet_id] = tweet

        yield from self.user_interface.update_instance(user)

        return tweet_instance

    def update_tweet(
        self,
        tweet: UserTweet,
    ) -> Optional[AttributeInstance]:
        """Update a tweet attribute instance"""
        attr_instance = yield from self.tweet_interface.update_instance(tweet)
        return attr_instance

    def create_user(self, user: ContributeUser) -> Optional[AttributeInstance]:
        """Create a user attribute instance"""
        self.logger.info(
            f"Creating user: {user.id} with twitter_handle {user.twitter_handle}"
        )

        # Avoid user duplication
        is_duplicate, existing_user = self.is_duplicate_user(user)
        if is_duplicate:
            raise ValueError(
                f"Trying to create a duplicated user:\n{user}\n\nUser already exists:\n{existing_user}"
            )

        user_instance = yield from self.user_interface.create_instance(user)
        user.attribute_instance_id = (
            user_instance.attribute_id if user_instance else None
        )

        self.data.users[user.id] = user
        self.logger.info(
            f"User {user.id} created [twitter_id={user.twitter_id}, twitter_handle={user.twitter_handle}]"
        )
        return user_instance

    def is_duplicate_user(
        self, user: ContributeUser
    ) -> Tuple[bool, Optional[ContributeUser]]:
        """Does the user already exist"""

        UNIQUE_FIELDS = [
            "token_id",
            "discord_id",
            "discord_handle",
            "service_id",
            "twitter_id",
            "twitter_handle",
            "wallet_address",
            "service_multisig",
        ]

        for field_name in UNIQUE_FIELDS:
            field_value = getattr(user, field_name, None)
            existing_user = self.get_user_by_attribute(field_name, field_value)
            if field_value is not None and existing_user:
                self.logger.warning(
                    f"Found existing user with {field_name}={field_value}"
                )
                return True, existing_user
        return False, None

    def update_user(self, user: ContributeUser) -> Optional[AttributeInstance]:
        """Update a user attribute instance"""
        result = yield from self.user_interface.update_instance(user)
        return result

    def create_or_update_user_by_key(self, key: str, value: Any, user: ContributeUser):
        """Creates or updates a user"""
        user = self.get_user_by_attribute(key, value)
        if not user:
            self.logger.info(f"User with {key}={value} not found. Creating...")
            yield from self.create_user(user)
        else:
            self.logger.info(f"User with {key}={value} found. Updating...")
            yield from self.update_user(user)

    def create_module_configs(
        self, config: ModuleConfigs
    ) -> Optional[AttributeInstance]:
        """Create a plugin config attribute instance"""
        self.logger.info("Creating module configs")
        module_configs_instance = (
            yield from self.module_configs_interface.create_instance(config)
        )
        self.data.module_configs = config
        if module_configs_instance:
            self.data.module_configs.attribute_instance_id = (
                module_configs_instance.attribute_id
            )
        return module_configs_instance

    def update_module_configs(
        self, configs: ModuleConfigs
    ) -> Optional[AttributeInstance]:
        """Update a plugin config attribute instance"""
        attr_instance = yield from self.module_configs_interface.update_instance(
            configs
        )
        return attr_instance

    def create_module_data(self, data: ModuleData) -> Optional[AttributeInstance]:
        """Create a plugin data attribute instance"""
        self.logger.info("Creating module data")
        module_data_instance = yield from self.module_data_interface.create_instance(
            data
        )

        self.data.module_data = data

        if module_data_instance:
            self.data.module_data.attribute_instance_id = (
                module_data_instance.attribute_id
            )
        return module_data_instance

    def update_module_data(self, data: ModuleData) -> Optional[AttributeInstance]:
        """Update a plugin data attribute instance"""
        attr_instance = yield from self.module_data_interface.update_instance(data)
        return attr_instance

    def load_from_remote_db(self):
        """Load data from the remote database."""

        if self.loaded:
            return

        if self.client.agent is None:
            yield from self.client.ensure_agent_is_loaded()

        attributes = yield from self.client.get_all_agent_instance_attributes_parsed(
            self.client.agent
        )

        for attribute in attributes:
            attr_name = attribute["attr_name"]
            attr_data = attribute["attr_value"] | {
                "attribute_instance_id": attribute["attr_id"]
            }
            self.logger.info(
                f"Loading attribute: {attr_name} with id: {attribute['attr_id']}"
            )

            try:
                if attr_name == "tweet":
                    tweet = UserTweet(**attr_data)
                    self.data.tweets[tweet.tweet_id] = tweet
                    continue

                if attr_name == "user":
                    attr_data["tweets"] = {}
                    user = ContributeUser(**attr_data)

                    if user.id in self.data.users:
                        raise ValueError(
                            f"User with id {user.id} already exists.\nExisting: {self.data.users[user.id]}\nNew: {user}"
                        )

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

            except ValidationError as e:
                raise ValueError(
                    f"Failed to load attribute {attr_name} with data {attr_data}. Error: {e}"
                ) from e

            raise ValueError(f"Unknown attribute name: {attr_name}")

        self.data.sort()

        for tweet_id, tweet in self.data.tweets.items():
            user = self.get_user_by_attribute("twitter_id", tweet.twitter_user_id)
            if not user:
                self.logger.error(
                    f"User with twitter_id {tweet.twitter_user_id} not found for tweet {tweet}. Skipping this tweet..."
                )
                continue

            user.tweets[tweet_id] = tweet

        if not self.data.tweets:
            raise ValueError("No tweets found in the database.")

        if not self.data.users:
            raise ValueError("No users found in the database.")

        if not self.data.module_configs:
            raise ValueError("No module configs found in the database.")

        if not self.data.module_data:
            raise ValueError("No module data found in the database.")

        for i in [
            "staking_daa",
            "week_in_olas",
            "scheduled_tweet",
            "staking_activity",
            "twitter_campaigns",
            "staking_checkpoint",
        ]:
            if not hasattr(self.data.module_configs, i):
                raise ValueError(f"Module config {i} not found in the database.")

        for i in ["scheduled_tweet", "twitter_campaigns", "dynamic_nft", "twitter"]:
            if not hasattr(self.data.module_data, i):
                raise ValueError(f"Module data {i} not found in the database.")

        self.loaded = True

    def get_next_user_id(self):
        """Get next user id"""
        next_id = 0 if not self.data.users else sorted(self.data.users.keys())[-1] + 1
        if next_id in self.data.users:
            raise ValueError(f"Next user ID {next_id} already exists in the database.")
        return next_id
