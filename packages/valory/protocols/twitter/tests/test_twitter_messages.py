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

"""Test messages module for twitter protocol."""

# pylint: disable=too-many-statements,too-many-locals,no-member,too-few-public-methods,redefined-builtin
from typing import List

from aea.test_tools.test_protocol import BaseProtocolMessagesTestCase

from packages.valory.protocols.twitter.message import TwitterMessage


class TestMessageTwitter(BaseProtocolMessagesTestCase):
    """Test for the 'twitter' protocol message."""

    MESSAGE_CLASS = TwitterMessage

    def build_messages(self) -> List[TwitterMessage]:  # type: ignore[override]
        """Build the messages to be used for testing."""
        return [
            TwitterMessage(
                performative=TwitterMessage.Performative.CREATE_TWEET,
                text="some str",
            ),
            TwitterMessage(
                performative=TwitterMessage.Performative.TWEET_CREATED,
                tweet_id="some str",
            ),
            TwitterMessage(
                performative=TwitterMessage.Performative.ERROR,
                message="some str",
            ),
        ]

    def build_inconsistent(self) -> List[TwitterMessage]:  # type: ignore[override]
        """Build inconsistent messages to be used for testing."""
        return [
            TwitterMessage(
                performative=TwitterMessage.Performative.CREATE_TWEET,
                # skip content: text
            ),
            TwitterMessage(
                performative=TwitterMessage.Performative.TWEET_CREATED,
                # skip content: tweet_id
            ),
            TwitterMessage(
                performative=TwitterMessage.Performative.ERROR,
                # skip content: message
            ),
        ]
