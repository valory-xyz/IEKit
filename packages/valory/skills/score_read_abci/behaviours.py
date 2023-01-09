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

"""This package contains round behaviours of ScoreReadAbciApp."""

import json
from collections import OrderedDict
from typing import Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.score_read_abci.models import Params
from packages.valory.skills.score_read_abci.rounds import (
    ScoreReadAbciApp,
    ScoringPayload,
    ScoringRound,
    SynchronizedData,
    TwitterObservationPayload,
    TwitterObservationRound,
)


class ScoreReadBaseBehaviour(BaseBehaviour):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


class TwitterObservationBehaviour(ScoreReadBaseBehaviour):
    """TwitterObservationBehaviour"""

    matching_round: Type[AbstractRound] = TwitterObservationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            # Get mentions from Twitter
            mentions = yield from self._get_twitter_mentions()
            self.context.logger.info(f"Retrieved new mentions from Twitter: {mentions}")
            sender = self.context.agent_address
            payload = TwitterObservationPayload(sender=sender, content=mentions)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _get_twitter_mentions(self) -> Generator[None, None, str]:
        """Get Twitter mentions"""

        api_base = self.params.twitter_api_base
        api_endpoint = self.params.twitter_api_endpoint
        api_args = self.params.twitter_api_template_args
        url = api_base + "/" + api_endpoint + "?" + api_args
        headers = [
            OrderedDict(Authorization=f"Bearer {self.params.twitter_api_bearer_token}")
        ]

        self.context.logger.info(f"Retrieving mentions from Twitter API [{url}]")
        response = yield from self.get_http_response(
            method="GET", url=url, headers=headers
        )

        if response.status_code != 200:
            self.context.logger.error(
                f"Error retrieving mentions from Twitter [{response.status_code}]"
            )
            return TwitterObservationRound.ERROR_PAYLOAD

        mentions = json.loads(response.body)

        return json.dumps(
            {
                "mentions": mentions,
            },
            sort_keys=True,
        )


class ScoringBehaviour(ScoreReadBaseBehaviour):
    """ScoringBehaviour"""

    matching_round: Type[AbstractRound] = ScoringRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            payload = ScoringPayload(sender=sender, content=...)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class ScoreReadRoundBehaviour(AbstractRoundBehaviour):
    """ScoreReadRoundBehaviour"""

    initial_behaviour_cls = TwitterObservationBehaviour
    abci_app_cls = ScoreReadAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        ScoringBehaviour,
        TwitterObservationBehaviour,
    ]
