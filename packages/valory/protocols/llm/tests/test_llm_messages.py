#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2023 Valory AG
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


# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 valory
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

"""Test messages module for llm protocol."""

# pylint: disable=too-many-statements,too-many-locals,no-member,too-few-public-methods,redefined-builtin
from typing import List

from aea.test_tools.test_protocol import BaseProtocolMessagesTestCase

from packages.valory.protocols.llm.message import LlmMessage


class TestMessageLlm(BaseProtocolMessagesTestCase):
    """Test for the 'llm' protocol message."""

    MESSAGE_CLASS = LlmMessage

    def build_messages(self) -> List[LlmMessage]:  # type: ignore[override]
        """Build the messages to be used for testing."""
        return [
            LlmMessage(
                performative=LlmMessage.Performative.REQUEST,
                prompt_template="some str",
                prompt_values={"some str": "some str"},
            ),
            LlmMessage(
                performative=LlmMessage.Performative.RESPONSE,
                value="some str",
            ),
        ]

    def build_inconsistent(self) -> List[LlmMessage]:  # type: ignore[override]
        """Build inconsistent messages to be used for testing."""
        return [
            LlmMessage(
                performative=LlmMessage.Performative.REQUEST,
                # skip content: prompt_template
                prompt_values={"some str": "some str"},
            ),
            LlmMessage(
                performative=LlmMessage.Performative.RESPONSE,
                # skip content: value
            ),
        ]
