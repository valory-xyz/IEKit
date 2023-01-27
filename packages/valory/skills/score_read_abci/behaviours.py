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
from abc import ABC
from collections import OrderedDict
from typing import Dict, Generator, Set, Type, cast

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


class ScoreReadBaseBehaviour(BaseBehaviour, ABC):
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
            api_data = yield from self._get_twitter_api_data()
            self.context.logger.info(f"Retrieved new mentions from Twitter: {api_data}")
            sender = self.context.agent_address
            payload = TwitterObservationPayload(sender=sender, content=api_data)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _get_twitter_api_data(self) -> Generator[None, None, str]:
        """Get Twitter mentions"""

        api_base = self.params.twitter_api_base
        api_endpoint = self.params.twitter_api_endpoint
        api_args = self.params.twitter_api_args
        url = api_base + api_endpoint + api_args
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

        api_data = json.loads(response.body)

        return json.dumps(
            self._count_mentions(api_data),
            sort_keys=True,
        )

    def _count_mentions(self, api_data: Dict) -> Dict:
        """Process Twitter API data"""

        user_to_mentions: Dict[str, int] = {}
        for tweet in api_data["data"]:
            author = tweet["author_id"]
            if author not in user_to_mentions:
                user_to_mentions[author] = 1
            else:
                user_to_mentions[author] = user_to_mentions[author] + 1

        return {
            "user_to_mentions": user_to_mentions,
            "latest_tweet_id": api_data["meta"]["newest_id"],
        }


class ScoringBehaviour(ScoreReadBaseBehaviour):
    """ScoringBehaviour"""

    matching_round: Type[AbstractRound] = ScoringRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            payload_data = json.dumps(
                self._assign_scores(),
                sort_keys=True,
            )

            sender = self.context.agent_address
            payload = ScoringPayload(sender=sender, content=payload_data)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _assign_scores(self) -> Dict:
        """Assign scores to users"""

        user_to_scores = {
            user: score * self.params.twitter_mention_points
            for user, score in self.synchronized_data.most_voted_api_data[
                "user_to_mentions"
            ].items()
        }

        return {
            "user_to_scores": user_to_scores,
            "latest_tweet_id": self.synchronized_data.most_voted_api_data[
                "latest_tweet_id"
            ],
        }


class ScoreReadRoundBehaviour(AbstractRoundBehaviour):
    """ScoreReadRoundBehaviour"""

    initial_behaviour_cls = TwitterObservationBehaviour
    abci_app_cls = ScoreReadAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        ScoringBehaviour,
        TwitterObservationBehaviour,
    ]
