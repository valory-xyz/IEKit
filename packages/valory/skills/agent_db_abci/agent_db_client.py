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

"""This module contains classes to interact with AgentDB."""

import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union

from aea.skills.base import Model
from eth_account import Account
from eth_account.datastructures import SignedMessage
from eth_account.messages import encode_defunct

from packages.valory.skills.agent_db_abci.agent_db_models import (
    AgentInstance,
    AgentType,
    AttributeDefinition,
    AttributeInstance,
)


# Docs at:
# https://axatbhardwaj.notion.site/MirrorDB-Agent-and-Attribute-Data-Flow-1eac8d38bc0b80edae04ff1017d80f58
# https://afmdb.autonolas.tech/docs#/default/read_attribute_definitions_by_type_api_agent_types__type_id__attributes__get


class AgentDBClient(Model):
    """AgentDBClient"""

    def __init__(self, base_url, **kwargs: Any):
        """Constructor"""
        super().__init__(**kwargs)
        self.base_url: str = base_url.rstrip("/")
        self._attribute_definition_cache: Dict[int, AttributeDefinition] = {}
        self.agent: AgentInstance = None
        self.agent_type = None
        self.address: str = None
        self.signing_func: Callable = None
        self.private_key: Optional[str] = None
        self.http_request_func: Callable = None
        self.logger: Callable = None

    def initialize(
        self,
        address: str,
        http_request_func: Callable,
        signing_func_or_pkey: Union[Callable, str],
        logger: Callable,
    ):
        """Inject external functions"""
        self.address = address
        self.http_request_func = http_request_func
        self.signing_func = (
            signing_func_or_pkey
            if isinstance(signing_func_or_pkey, Callable)
            else self.sign_using_pkey
        )
        self.private_key = (
            signing_func_or_pkey if isinstance(signing_func_or_pkey, str) else None
        )
        self.logger = logger

    def sign_using_pkey(self, message_to_sign: str):
        """Sign using pkey"""
        yield
        if isinstance(message_to_sign, bytes):
            message_to_sign = message_to_sign.decode("utf-8")

        signed_message = Account.sign_message(  # pylint: disable=no-value-for-parameter
            encode_defunct(text=message_to_sign), private_key=self.private_key
        )
        return signed_message

    def ensure_agent_is_loaded(self):
        """Ensure agent is loaded"""
        if self.agent is None:
            self.agent = yield from self.get_agent_instance_by_address(self.address)
            self.agent_type = (
                self.get_agent_type_by_type_id(self.agent.type_id)
                if self.agent
                else None
            )

    def _sign_request(self, endpoint):
        """Generate authentication"""

        if self.signing_func is None:
            raise ValueError(
                "Signing function not set. Use set_external_funcs to set it."
            )

        yield from self.ensure_agent_is_loaded()

        timestamp = int(datetime.now(timezone.utc).timestamp())
        message_to_sign = f"timestamp:{timestamp},endpoint:{endpoint}"

        signature_hex = yield from self.signing_func(message_to_sign.encode("utf-8"))
        if isinstance(signature_hex, SignedMessage):
            signature_hex = signature_hex.signature.hex()

        auth_data = {
            "agent_id": self.agent.agent_id,
            "signature": signature_hex,
            "message": message_to_sign,
        }
        return auth_data

    def _request(
        self, method, endpoint, payload=None, params=None, auth=False, nested_auth=True
    ):
        """Make the request"""

        if self.http_request_func is None:
            raise ValueError(
                "HTTP request function not set. Use set_external_funcs to set it."
            )

        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        if auth:
            payload = payload or {}
            auth = yield from self._sign_request(endpoint)
            if nested_auth:
                payload["auth"] = auth
            else:
                payload = payload | auth

        self.logger.info(
            f"Making {method} request to {url} with payload: {payload} and params: {params}"
        )

        content = json.dumps(payload).encode() if payload else None

        response = yield from self.http_request_func(
            method=method, url=url, content=content, headers=headers, parameters=params
        )

        self.logger.info(f"Response status: {response.status_code}")

        if response.status_code in [200, 201]:
            return json.loads(response.body)

        if response.status_code == 404:
            return None

        raise Exception(
            f"Request failed: {response.status_code} - {getattr(response, 'text', None)}"
        )

    # Agent Type Methods

    def create_agent_type(self, type_name, description) -> Optional[AgentType]:
        """Create agent type"""
        endpoint = "/api/agent-types/"
        payload = {"type_name": type_name, "description": description}
        result = yield from self._request("POST", endpoint, payload)
        return AgentType.model_validate(result) if result else None

    def get_agent_type_by_type_id(self, type_id) -> Optional[AgentType]:
        """Get agent by type"""
        endpoint = f"/api/agent-types/{type_id}/"
        result = yield from self._request("GET", endpoint)
        return AgentType.model_validate(result) if result else None

    def get_agent_type_by_type_name(self, type_name) -> Optional[AgentType]:
        """Get agent by type"""
        endpoint = f"/api/agent-types/name/{type_name}/"
        result = yield from self._request("GET", endpoint)
        return AgentType.model_validate(result) if result else None

    def delete_agent_type(self, agent_type: AgentType):
        """Delete agent type"""
        endpoint = f"/api/agent-types/{agent_type.type_id}/"
        result = yield from self._request(
            "DELETE", endpoint, auth=True, nested_auth=True
        )
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
        result = yield from self._request("POST", endpoint, payload)
        return AgentInstance.model_validate(result) if result else None

    def get_agent_instance_by_address(self, eth_address) -> Optional[AgentInstance]:
        """Get agent by Ethereum address"""
        endpoint = f"/api/agent-registry/address/{eth_address}"
        result = yield from self._request("GET", endpoint)
        return AgentInstance.model_validate(result) if result else None

    def get_agent_instances_by_type_id(self, type_id) -> List[AgentInstance]:
        """Get agent instances by type"""
        endpoint = f"/api/agent-types/{type_id}/agents/"
        params = {
            "skip": 0,
            "limit": 100,
        }
        result = yield from self._request(
            method="GET", endpoint=endpoint, params=params
        )
        return (
            [AgentInstance.model_validate(agent) for agent in result] if result else []
        )

    def delete_agent_instance(self, agent_instance: AgentInstance):
        """Delete agent instance"""
        endpoint = f"/api/agent-registry/{agent_instance.agent_id}/"
        result = yield from self._request(
            "DELETE", endpoint, auth=True, nested_auth=False
        )
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
        result = yield from self._request(
            "POST", endpoint, {"attr_def": payload}, auth=True
        )
        return AttributeDefinition.model_validate(result) if result else None

    def get_attribute_definition_by_name(
        self, attr_name: str
    ) -> Optional[AttributeDefinition]:
        """Get attribute definition by name"""
        endpoint = f"/api/attributes/name/{attr_name}"
        result = yield from self._request("GET", endpoint)
        return AttributeDefinition.model_validate(result) if result else None

    def get_attribute_definition_by_id(
        self, attr_id: int
    ) -> Optional[AttributeDefinition]:
        """Get attribute definition by id"""
        if attr_id in self._attribute_definition_cache:
            return self._attribute_definition_cache[attr_id]

        endpoint = f"/api/attributes/{attr_id}"
        result = yield from self._request("GET", endpoint)
        if result:
            definition = AttributeDefinition.model_validate(result)
            self._attribute_definition_cache[attr_id] = definition
            return definition
        return None

    def get_attribute_definitions_by_agent_type(self, agent_type: AgentType):
        """Get attributes by agent type"""
        endpoint = f"/api/agent-types/{agent_type.type_id}/attributes/"
        result = yield from self._request("GET", endpoint)
        return (
            [AttributeDefinition.model_validate(attr) for attr in result]
            if result
            else []
        )

    def delete_attribute_definition(self, attr_def: AttributeDefinition):
        """Delete attribute definition"""
        endpoint = f"/api/attributes/{attr_def.attr_def_id}/"
        result = yield from self._request(
            "DELETE", endpoint, auth=True, nested_auth=True
        )
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
        result = yield from self._request(
            "POST", endpoint, {"agent_attr": payload}, auth=True
        )
        return AttributeInstance.model_validate(result) if result else None

    def get_first_attribute_instance_by_attribute_definition(
        self, agent_instance: AgentInstance, attr_def: AttributeDefinition
    ) -> Optional[AttributeInstance]:
        """Get attribute instance by agent ID and attribute definition ID"""
        endpoint = (
            f"/api/agents/{agent_instance.agent_id}/attributes/{attr_def.attr_def_id}/"
        )
        result = yield from self._request("GET", endpoint)
        return AttributeInstance.model_validate(result) if result else None

    def get_attribute_instance_by_attribute_id(
        self, attribute_id: int
    ) -> Optional[AttributeInstance]:
        """Get attribute instance by attribute ID"""
        endpoint = f"/api/agent-attributes/{attribute_id}"
        result = yield from self._request("GET", endpoint)
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
        result = yield from self._request(
            "PUT", endpoint, {"agent_attr": payload}, auth=True
        )
        return AttributeInstance.model_validate(result) if result else None

    def delete_attribute_instance(
        self, attribute_instance_id: int
    ) -> Optional[AttributeInstance]:
        """Delete attribute instance"""
        endpoint = f"/api/agent-attributes/{attribute_instance_id}"
        result = yield from self._request(
            "DELETE", endpoint, auth=True, nested_auth=True
        )
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
            self.logger.info(
                f"Reading agent attributes from {skip} to {skip + 100}... "
            )
            result = yield from self._request(
                method="GET",
                endpoint=endpoint,
                payload={"agent_attr": payload},
                params=params,
                auth=True,
            )

            if result is None:
                self.logger.error("Error fetching agent attributes")
                continue

            self.logger.info(f"got {len(result)} attributes")

            raw_attributes += result
            skip = len(raw_attributes)

            if len(result) < 100:
                return raw_attributes

    def parse_attribute_instance(self, attribute_instance: AttributeInstance):
        """Parse attribute instance"""
        attribute_definition = yield from self.get_attribute_definition_by_id(
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
        attribute_instances = yield from self.get_all_agent_instance_attributes_raw(
            agent_instance
        )
        parsed_attributes = []
        for attr in attribute_instances:
            result = yield from self.parse_attribute_instance(AttributeInstance(**attr))
            parsed_attributes.append(result)
        return parsed_attributes
