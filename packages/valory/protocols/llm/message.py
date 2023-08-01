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

"""This module contains llm's message definition."""

# pylint: disable=too-many-statements,too-many-locals,no-member,too-few-public-methods,too-many-branches,not-an-iterable,unidiomatic-typecheck,unsubscriptable-object
import logging
from typing import Any, Dict, Set, Tuple, cast

from aea.configurations.base import PublicId
from aea.exceptions import AEAEnforceError, enforce
from aea.protocols.base import Message


_default_logger = logging.getLogger("aea.packages.valory.protocols.llm.message")

DEFAULT_BODY_SIZE = 4


class LlmMessage(Message):
    """A protocol for LLM requests and responses."""

    protocol_id = PublicId.from_str("valory/llm:1.0.0")
    protocol_specification_id = PublicId.from_str("valory/llm:1.0.0")

    class Performative(Message.Performative):
        """Performatives for the llm protocol."""

        REQUEST = "request"
        RESPONSE = "response"

        def __str__(self) -> str:
            """Get the string representation."""
            return str(self.value)

    _performatives = {"request", "response"}
    __slots__: Tuple[str, ...] = tuple()

    class _SlotsCls:
        __slots__ = (
            "dialogue_reference",
            "message_id",
            "performative",
            "prompt_template",
            "prompt_values",
            "target",
            "value",
        )

    def __init__(
        self,
        performative: Performative,
        dialogue_reference: Tuple[str, str] = ("", ""),
        message_id: int = 1,
        target: int = 0,
        **kwargs: Any,
    ):
        """
        Initialise an instance of LlmMessage.

        :param message_id: the message id.
        :param dialogue_reference: the dialogue reference.
        :param target: the message target.
        :param performative: the message performative.
        :param **kwargs: extra options.
        """
        super().__init__(
            dialogue_reference=dialogue_reference,
            message_id=message_id,
            target=target,
            performative=LlmMessage.Performative(performative),
            **kwargs,
        )

    @property
    def valid_performatives(self) -> Set[str]:
        """Get valid performatives."""
        return self._performatives

    @property
    def dialogue_reference(self) -> Tuple[str, str]:
        """Get the dialogue_reference of the message."""
        enforce(self.is_set("dialogue_reference"), "dialogue_reference is not set.")
        return cast(Tuple[str, str], self.get("dialogue_reference"))

    @property
    def message_id(self) -> int:
        """Get the message_id of the message."""
        enforce(self.is_set("message_id"), "message_id is not set.")
        return cast(int, self.get("message_id"))

    @property
    def performative(self) -> Performative:  # type: ignore # noqa: F821
        """Get the performative of the message."""
        enforce(self.is_set("performative"), "performative is not set.")
        return cast(LlmMessage.Performative, self.get("performative"))

    @property
    def target(self) -> int:
        """Get the target of the message."""
        enforce(self.is_set("target"), "target is not set.")
        return cast(int, self.get("target"))

    @property
    def prompt_template(self) -> str:
        """Get the 'prompt_template' content from the message."""
        enforce(self.is_set("prompt_template"), "'prompt_template' content is not set.")
        return cast(str, self.get("prompt_template"))

    @property
    def prompt_values(self) -> Dict[str, str]:
        """Get the 'prompt_values' content from the message."""
        enforce(self.is_set("prompt_values"), "'prompt_values' content is not set.")
        return cast(Dict[str, str], self.get("prompt_values"))

    @property
    def value(self) -> str:
        """Get the 'value' content from the message."""
        enforce(self.is_set("value"), "'value' content is not set.")
        return cast(str, self.get("value"))

    def _is_consistent(self) -> bool:
        """Check that the message follows the llm protocol."""
        try:
            enforce(
                isinstance(self.dialogue_reference, tuple),
                "Invalid type for 'dialogue_reference'. Expected 'tuple'. Found '{}'.".format(
                    type(self.dialogue_reference)
                ),
            )
            enforce(
                isinstance(self.dialogue_reference[0], str),
                "Invalid type for 'dialogue_reference[0]'. Expected 'str'. Found '{}'.".format(
                    type(self.dialogue_reference[0])
                ),
            )
            enforce(
                isinstance(self.dialogue_reference[1], str),
                "Invalid type for 'dialogue_reference[1]'. Expected 'str'. Found '{}'.".format(
                    type(self.dialogue_reference[1])
                ),
            )
            enforce(
                type(self.message_id) is int,
                "Invalid type for 'message_id'. Expected 'int'. Found '{}'.".format(
                    type(self.message_id)
                ),
            )
            enforce(
                type(self.target) is int,
                "Invalid type for 'target'. Expected 'int'. Found '{}'.".format(
                    type(self.target)
                ),
            )

            # Light Protocol Rule 2
            # Check correct performative
            enforce(
                isinstance(self.performative, LlmMessage.Performative),
                "Invalid 'performative'. Expected either of '{}'. Found '{}'.".format(
                    self.valid_performatives, self.performative
                ),
            )

            # Check correct contents
            actual_nb_of_contents = len(self._body) - DEFAULT_BODY_SIZE
            expected_nb_of_contents = 0
            if self.performative == LlmMessage.Performative.REQUEST:
                expected_nb_of_contents = 2
                enforce(
                    isinstance(self.prompt_template, str),
                    "Invalid type for content 'prompt_template'. Expected 'str'. Found '{}'.".format(
                        type(self.prompt_template)
                    ),
                )
                enforce(
                    isinstance(self.prompt_values, dict),
                    "Invalid type for content 'prompt_values'. Expected 'dict'. Found '{}'.".format(
                        type(self.prompt_values)
                    ),
                )
                for (
                    key_of_prompt_values,
                    value_of_prompt_values,
                ) in self.prompt_values.items():
                    enforce(
                        isinstance(key_of_prompt_values, str),
                        "Invalid type for dictionary keys in content 'prompt_values'. Expected 'str'. Found '{}'.".format(
                            type(key_of_prompt_values)
                        ),
                    )
                    enforce(
                        isinstance(value_of_prompt_values, str),
                        "Invalid type for dictionary values in content 'prompt_values'. Expected 'str'. Found '{}'.".format(
                            type(value_of_prompt_values)
                        ),
                    )
            elif self.performative == LlmMessage.Performative.RESPONSE:
                expected_nb_of_contents = 1
                enforce(
                    isinstance(self.value, str),
                    "Invalid type for content 'value'. Expected 'str'. Found '{}'.".format(
                        type(self.value)
                    ),
                )

            # Check correct content count
            enforce(
                expected_nb_of_contents == actual_nb_of_contents,
                "Incorrect number of contents. Expected {}. Found {}".format(
                    expected_nb_of_contents, actual_nb_of_contents
                ),
            )

            # Light Protocol Rule 3
            if self.message_id == 1:
                enforce(
                    self.target == 0,
                    "Invalid 'target'. Expected 0 (because 'message_id' is 1). Found {}.".format(
                        self.target
                    ),
                )
        except (AEAEnforceError, ValueError, KeyError) as e:
            _default_logger.error(str(e))
            return False

        return True
