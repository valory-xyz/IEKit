
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

"""This module contains definitions for AgentDB models."""

from pydantic import BaseModel
from datetime import datetime
from typing import Any, List


class AgentType(BaseModel):
    """AgentType"""

    type_id: int
    type_name: str
    description: str


class AgentInstance(BaseModel):
    """AgentInstance"""

    agent_id: int
    type_id: int
    agent_name: str
    eth_address: str
    created_at: datetime


class AttributeDefinition(BaseModel):
    """AttributeDefinition"""

    attr_def_id: int
    type_id: int
    attr_name: str
    data_type: str
    is_required: bool
    default_value: Any


class AttributeInstance(BaseModel):
    """AttributeInstance"""

    attribute_id: int
    attr_def_id: int
    agent_id: int
    last_updated: datetime
    string_value: str | None
    integer_value: int | None
    float_value: float | None
    boolean_value: bool | None
    date_value: datetime | None
    json_value: Any | None


class AgentsFunAgentType(BaseModel):
    """AgentsFunAgentType"""

    agent_type: AgentType
    attribute_definitions: List[AttributeDefinition]
