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


class RandomnessPayload(BaseTxPayload):
    """Represent a transaction payload of type 'randomness'."""

    transaction_type = TransactionType.RANDOMNESS

    def __init__(
        self, sender: str, round_id: int, randomness: str, **kwargs: Any
    ) -> None:
        """Initialize an 'select_keeper' transaction payload.

        We send the DRAND "round_id" to be able to discriminate between payloads
        from different DRAND rounds more easily.

        :param sender: the sender (Ethereum) address
        :param round_id: the round id
        :param randomness: the randomness
        :param kwargs: the keyword arguments
        """
        super().__init__(sender, **kwargs)
        self._round_id = round_id
        self._randomness = randomness

    @property
    def round_id(self) -> int:
        """Get the round id."""
        return self._round_id  # pragma: nocover

    @property
    def randomness(self) -> str:
        """Get the randomness."""
        return self._randomness  # pragma: nocover

    @property
    def data(self) -> Dict:
        """Get the data."""
        return dict(round_id=self.round_id, randomness=self.randomness)


class SelectKeeperPayload(BaseTxPayload):
    """Represent a transaction payload of type 'select_keeper'."""

    transaction_type = TransactionType.SELECT_KEEPER

    def __init__(self, sender: str, keepers: str, **kwargs: Any) -> None:
        """Initialize a 'select_keeper' transaction payload.

        :param sender: the sender (Ethereum) address
        :param keepers: the updated keepers
        :param kwargs: the keyword arguments
        """
        super().__init__(sender, **kwargs)
        self._keepers = keepers

    @property
    def keepers(self) -> str:
        """Get the keeper."""
        return self._keepers

    @property
    def data(self) -> Dict[str, str]:
        """Get the data."""
        return dict(keepers=self.keepers)


class CeramicWritePayload(BaseScoreWritePayload):
    """Represent a transaction payload for the CeramicWriteRound."""

    transaction_type = TransactionType.CERAMIC_WRITE


class VerificationPayload(BaseScoreWritePayload):
    """Represent a transaction payload for the VerificationRound."""

    transaction_type = TransactionType.VERIFICATION
