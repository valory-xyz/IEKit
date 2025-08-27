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

"""This module contains the transaction payloads of the TwitterScoringAbciApp."""

from dataclasses import dataclass

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload


@dataclass(frozen=True)
class TwitterMentionsCollectionPayload(BaseTxPayload):
    """Represent a transaction payload for the TwitterMentionsCollectionRound."""

    content: str


@dataclass(frozen=True)
class TwitterCampaignsCollectionPayload(BaseTxPayload):
    """Represent a transaction payload for the TwitterCampaignsCollectionRound."""

    content: str


@dataclass(frozen=True)
class PreMechRequestPayload(BaseTxPayload):
    """Represent a transaction payload for the PreMechRequestRound."""

    content: str


@dataclass(frozen=True)
class PostMechRequestPayload(BaseTxPayload):
    """Represent a transaction payload for the PostMechRequestRound."""

    content: str


@dataclass(frozen=True)
class DBUpdatePayload(BaseTxPayload):
    """Represent a transaction payload for the DBUpdateRound."""

    content: str


@dataclass(frozen=True)
class TwitterDecisionMakingPayload(BaseTxPayload):
    """Represent a transaction payload for the TwitterDecisionMakingRound."""

    event: str


@dataclass(frozen=True)
class TwitterRandomnessPayload(BaseTxPayload):
    """Represent a transaction payload of type 'randomness'."""

    round_id: int
    randomness: str


@dataclass(frozen=True)
class TwitterSelectKeepersPayload(BaseTxPayload):
    """Represent a transaction payload of type 'select_keeper'."""

    keepers: str
