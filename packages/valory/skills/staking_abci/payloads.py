# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
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

"""This module contains the transaction payloads of the StakingAbciApp."""

from dataclasses import dataclass
from typing import Optional

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload


@dataclass(frozen=True)
class ActivityScorePayload(BaseTxPayload):
    """Represent a transaction payload for the ActivityScoreRound."""

    activity_updates: Optional[str]
    latest_activity_tweet_id: Optional[int]
    pending_write: bool


@dataclass(frozen=True)
class ActiviyUpdatePreparationPayload(BaseTxPayload):
    """Represent a transaction payload for the ActiviyUpdatePreparationRound."""

    tx_submitter: Optional[str] = None
    tx_hash: Optional[str] = None
    chain_id: str = "base"


@dataclass(frozen=True)
class CheckpointPreparationPayload(BaseTxPayload):
    """Represent a transaction payload for the CheckpointPreparationRound."""

    tx_submitter: Optional[str] = None
    tx_hash: Optional[str] = None
    chain_id: str = "base"
