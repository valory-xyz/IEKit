# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2022 Valory AG
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

"""Test the dialogues.py module of the DynamicNFT skill."""

from pathlib import Path
from typing import cast

from aea.test_tools.test_skill import BaseSkillTestCase, COUNTERPARTY_AGENT_ADDRESS

from packages.valory.protocols.http.message import HttpMessage
from packages.valory.skills.dynamic_nft_abci.dialogues import (
    HttpDialogue,
    HttpDialogues,
)


PACKAGE_DIR = Path(__file__).parent.parent


class TestDialogues(BaseSkillTestCase):
    """Test dialogue class of http_echo."""

    path_to_skill = PACKAGE_DIR

    @classmethod
    def setup_class(cls):
        """Setup the test class."""
        super().setup_class()
        cls.http_dialogues = cast(
            HttpDialogues, cls._skill.skill_context.http_dialogues
        )

    def test_http_dialogues(self):
        """Test the HttpDialogues class."""
        _, dialogue = self.http_dialogues.create(
            counterparty=COUNTERPARTY_AGENT_ADDRESS,
            performative=HttpMessage.Performative.REQUEST,
            method="some_method",
            url="some_url",
            version="some_version",
            headers="some_headers",
            body=b"some_body",
        )
        assert dialogue.role == HttpDialogue.Role.SERVER
        assert dialogue.self_address == str(self.skill.skill_context.skill_id)
