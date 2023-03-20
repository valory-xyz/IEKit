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

"""This package contains round behaviours of ScoreWriteAbciApp."""

import json
from abc import ABC
from typing import Dict, Generator, Optional, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.score_write_abci.models import Params
from packages.valory.skills.score_write_abci.payloads import (
    ScoreAddPayload,
    StartupScoreReadPayload,
)
from packages.valory.skills.score_write_abci.rounds import (
    ScoreAddRound,
    ScoreWriteAbciApp,
    StartupScoreReadRound,
    SynchronizedData,
)


class ScoreWriteBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


class StartupScoreReadBehaviour(ScoreWriteBaseBehaviour):
    """StartupScoreReadBehaviour"""

    matching_round: Type[AbstractRound] = StartupScoreReadRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            # Get the current data
            data = yield from self._get_stream_data(self.params.scores_stream_id)

            if not data:
                self.context.logger.info(
                    "An error happened while getting scores data from the stream at startup"
                )
                payload_content = StartupScoreReadRound.ERROR_PAYLOAD
            else:
                self.context.logger.info(
                    f"Retrieved initial score data from Ceramic: {data['data']}"
                )

                user_to_total_points = (
                    data["data"]["user_to_total_points"]
                    if "user_to_total_points" in data["data"]
                    else {}
                )
                id_to_usernames = (
                    data["data"]["id_to_usernames"]
                    if "id_to_usernames" in data["data"]
                    else {}
                )
                latest_mention_tweet_id = (
                    data["data"]["latest_mention_tweet_id"]
                    if "latest_mention_tweet_id" in data["data"]
                    else 0
                )
                wallet_to_users = (
                    data["data"]["wallet_to_users"]
                    if "wallet_to_users" in data["data"]
                    else {}
                )

                payload_content = json.dumps(
                    {
                        "user_to_total_points": user_to_total_points,
                        "id_to_usernames": id_to_usernames,
                        "latest_mention_tweet_id": latest_mention_tweet_id,
                        "wallet_to_users": wallet_to_users,
                    },
                    sort_keys=True,
                )

            sender = self.context.agent_address
            payload = StartupScoreReadPayload(sender=sender, content=payload_content)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class ScoreAddBehaviour(ScoreWriteBaseBehaviour):
    """ScoreAddBehaviour"""

    matching_round: Type[AbstractRound] = ScoreAddRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            user_to_total_points = self._add_points()

            if user_to_total_points == {}:
                payload_content = ScoreAddRound.NO_CHANGES_PAYLOAD
            else:
                payload_content = json.dumps(user_to_total_points, sort_keys=True)

            sender = self.context.agent_address
            payload = ScoreAddPayload(sender=sender, content=payload_content)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _add_points(self) -> Generator[None, None, Optional[Dict]]:
        """Add the old and new points for each user"""

        # Get the new points
        user_to_new_points = self.synchronized_data.user_to_new_points

        if not user_to_new_points:
            self.context.logger.info("There are no new points to add")
            return {}

        # Get the old scores
        user_to_old_points = self.synchronized_data.user_to_total_points

        # Add the points
        user_to_total_points = user_to_old_points
        for user, new_points in user_to_new_points.items():
            if user not in user_to_old_points:
                user_to_total_points[user] = new_points
            else:
                user_to_total_points[user] += new_points

        self.context.logger.info(f"Calculated new total points: {user_to_total_points}")
        return user_to_total_points


class ScoreWriteRoundBehaviour(AbstractRoundBehaviour):
    """ScoreWriteRoundBehaviour"""

    initial_behaviour_cls = ScoreAddBehaviour
    abci_app_cls = ScoreWriteAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        StartupScoreReadBehaviour,
        ScoreAddBehaviour,
    ]
