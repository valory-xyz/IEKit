# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
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

"""This module contains the transaction payloads of the ScoreWriteAbciApp."""

from abc import ABC
from enum import Enum
from typing import Any, Dict, Hashable

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload


class TransactionType(Enum):
    """Enumeration of transaction types."""

    RANDOMNESS = "randomness"
    SELECT_KEEPER = "select_keeper"
    CERAMIC_WRITE = "ceramic_write"
    VERIFICATION = "verification"

    def __str__(self) -> str:
        """Get the string value of the transaction type."""
        return self.value


class BaseScoreWritePayload(BaseTxPayload, ABC):
    """Base payload for ScoreWriteAbciApp."""

    def __init__(self, sender: str, content: Hashable, **kwargs: Any) -> None:
        """Initialize a transaction payload."""
        super().__init__(sender, **kwargs)
        self._content = content

    @property
    def content(self) -> Hashable:
        """Get the content."""
        return self._content

    @property
    def data(self) -> Dict[str, Hashable]:
        """Get the data."""
        return dict(content=self.content)


class RandomnessPayload(BaseScoreWritePayload):
    """Represent a transaction payload for the RandomnessRound."""

    transaction_type = TransactionType.RANDOMNESS


class SelectKeeperPayload(BaseScoreWritePayload):
    """Represent a transaction payload for the SelectKeeperRound."""

    transaction_type = TransactionType.SELECT_KEEPER


class CeramicWritePayload(BaseScoreWritePayload):
    """Represent a transaction payload for the CeramicWriteRound."""

    transaction_type = TransactionType.CERAMIC_WRITE


class VerificationPayload(BaseScoreWritePayload):
    """Represent a transaction payload for the VerificationRound."""

    transaction_type = TransactionType.VERIFICATION
