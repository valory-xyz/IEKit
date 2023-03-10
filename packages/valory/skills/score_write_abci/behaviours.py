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

from web3 import Web3

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.abstract_round_abci.common import (
    RandomnessBehaviour,
    SelectKeeperBehaviour,
)
from packages.valory.skills.score_write_abci.ceramic.payloads import (
    build_commit_payload,
    build_data_from_commits,
)
from packages.valory.skills.score_write_abci.models import Params
from packages.valory.skills.score_write_abci.payloads import (
    CeramicWritePayload,
    RandomnessPayload,
    ScoreAddPayload,
    SelectKeeperPayload,
    StartupScoreReadPayload,
    VerificationPayload,
    WalletReadPayload,
)
from packages.valory.skills.score_write_abci.rounds import (
    CeramicWriteRound,
    RandomnessRound,
    ScoreAddRound,
    ScoreWriteAbciApp,
    SelectKeeperRound,
    StartupScoreReadRound,
    SynchronizedData,
    VerificationRound,
    WalletReadRound,
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

    def _get_stream_data(self, stream_id: str) -> Generator[None, None, Optional[dict]]:
        """Get the current data from a Ceramic stream"""

        api_base = self.params.ceramic_api_base
        api_endpoint = self.params.ceramic_api_read_endpoint
        url = api_base + api_endpoint.replace("{stream_id}", stream_id)

        self.context.logger.info(f"Reading data from Ceramic API [{url}]")
        response = yield from self.get_http_response(
            method="GET",
            url=url,
        )

        if response.status_code != 200:
            self.context.logger.error(
                f"API error while reading the stream: {response.status_code}: '{response.body!r}'"
            )
            return None

        try:
            api_data = json.loads(response.body)
        except json.decoder.JSONDecodeError:
            self.context.logger.error(
                f"API error while loading the response json. Response body: '{response.body!r}'"
            )
            return None

        # Extract first and last commit info
        genesis_cid_str = api_data["commits"][0]["cid"]
        previous_cid_str = api_data["commits"][-1]["cid"]

        # Rebuild the current data
        self.context.logger.info(
            f"Bulding stream data from commits:\n'{api_data['commits']!r}'"
        )
        data = build_data_from_commits(api_data["commits"])

        self.context.logger.info(f"Got data from Ceramic API: {data}")

        return {
            "genesis_cid_str": genesis_cid_str,
            "previous_cid_str": previous_cid_str,
            "data": data,
        }


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
                latest_tweet_id = (
                    data["data"]["latest_tweet_id"]
                    if "latest_tweet_id" in data["data"]
                    else 0
                )

                payload_content = json.dumps(
                    {
                        "user_to_total_points": user_to_total_points,
                        "id_to_usernames": id_to_usernames,
                        "latest_tweet_id": latest_tweet_id,
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


class RandomnessBehaviour(RandomnessBehaviour):
    """Retrieve randomness."""

    matching_round = RandomnessRound
    payload_class = RandomnessPayload


class SelectKeeperCeramicBehaviour(SelectKeeperBehaviour, ScoreWriteBaseBehaviour):
    """Select the keeper agent."""

    matching_round = SelectKeeperRound
    payload_class = SelectKeeperPayload


class CeramicWriteBehaviour(ScoreWriteBaseBehaviour):
    """CeramicWriteBehaviour"""

    matching_round: Type[AbstractRound] = CeramicWriteRound

    def _i_am_not_sending(self) -> bool:
        """Indicates if the current agent is the sender or not."""
        return (
            self.context.agent_address
            != self.synchronized_data.most_voted_keeper_address
        )

    def async_act(self) -> Generator[None, None, None]:
        """Do the action"""
        if self._i_am_not_sending():
            yield from self._not_sender_act()
        else:
            yield from self._sender_act()

    def _not_sender_act(self) -> Generator:
        """Do the non-sender action."""
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            self.context.logger.info(
                f"Waiting for the keeper to do its keeping: {self.synchronized_data.most_voted_keeper_address}"
            )
            yield from self.wait_until_round_end()
        self.set_done()

    def _sender_act(self) -> Generator:
        """Do the sender action"""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            success = yield from self._write_ceramic_data()
            if success:
                self.context.logger.info(
                    f"Wrote scores to ceramic stream with id: {self.params.scores_stream_id}"
                )
                payload_content = CeramicWriteRound.SUCCCESS_PAYLOAD
            else:
                self.context.logger.info(
                    f"An error happened while wroting scores to ceramic stream with id: {self.params.scores_stream_id}"
                )
                payload_content = CeramicWriteRound.ERROR_PAYLOAD

            sender = self.context.agent_address
            payload = CeramicWritePayload(sender=sender, content=payload_content)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _write_ceramic_data(self) -> Generator[None, None, bool]:
        """Write the scores to the Ceramic stream"""

        # Get the current stream data
        old_data = yield from self._get_stream_data(self.params.scores_stream_id)

        if not old_data:
            return False

        new_data = {
            "user_to_total_points": self.synchronized_data.user_to_total_points,
            "id_to_usernames": self.synchronized_data.id_to_usernames,
            "latest_tweet_id": self.synchronized_data.latest_tweet_id,
        }

        # Prepare the commit payload
        commit_payload = build_commit_payload(
            self.params.ceramic_did_str,
            self.params.ceramic_did_seed,
            self.params.scores_stream_id,
            old_data,
            new_data,
        )

        # Send the payload
        api_base = self.params.ceramic_api_base
        api_endpoint = self.params.ceramic_api_commit_endpoint
        url = api_base + api_endpoint

        self.context.logger.info(
            f"Writing new scores to Ceramic API [{url}]:\nScores: {self.synchronized_data.user_to_total_points}\nPayload: {commit_payload}"
        )
        response = yield from self.get_http_response(
            method="POST",
            url=url,
            content=json.dumps(commit_payload).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        if response.status_code != 200:
            self.context.logger.error(
                f"API error while updating the stream: {response.status_code}: {response.body}"
            )
            return False

        self.context.logger.info("Updated the stream correctly")
        return True


class VerificationBehaviour(ScoreWriteBaseBehaviour):
    """VerificationBehaviour"""

    matching_round: Type[AbstractRound] = VerificationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            # Get the current data
            data = yield from self._get_stream_data(self.params.scores_stream_id)

            # Verify if the retrieved data matches local user_to_total_points
            expected_data = json.dumps(
                {
                    "user_to_total_points": self.synchronized_data.user_to_total_points,
                    "id_to_usernames": self.synchronized_data.id_to_usernames,
                    "latest_tweet_id": self.synchronized_data.latest_tweet_id,
                },
                sort_keys=True,
            )

            # TODO: during e2e, the mocked Ceramic stream can't be updated, so verification will always fail
            # In this cases, we need to skip verification by detecting if scores_stream_id contains the default value
            skip_verify = self.params.scores_stream_id == "user_to_points_stream_id_e2e"

            if not skip_verify and (
                not data or json.dumps(data["data"], sort_keys=True) != expected_data
            ):
                self.context.logger.info(
                    f"An error happened while verifying data.\nExpected data:\n{expected_data}. Actual data:\n{data}\nSkip verification: {skip_verify}"
                )
                payload_content = CeramicWriteRound.ERROR_PAYLOAD
            else:
                self.context.logger.info("Data verification successful")
                payload_content = CeramicWriteRound.SUCCCESS_PAYLOAD

            sender = self.context.agent_address
            payload = VerificationPayload(sender=sender, content=payload_content)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class WalletReadBehaviour(ScoreWriteBaseBehaviour):
    """WalletReadBehaviour"""

    matching_round: Type[AbstractRound] = WalletReadRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():

            # Get the current data
            data = yield from self._get_stream_data(self.params.wallets_stream_id)

            if not data:
                self.context.logger.info(
                    "An error happened while getting wallet data from the stream"
                )
                payload_content = WalletReadRound.ERROR_PAYLOAD
            else:
                self.context.logger.info(
                    f"Retrieved wallet data from Ceramic: {data['data']}"
                )

                # Checksum addresses
                wallet_to_users = data["data"]
                checksum_wallet_to_users = {
                    Web3.toChecksumAddress(address): user
                    for address, user in wallet_to_users.items()
                }

                payload_content = json.dumps(checksum_wallet_to_users, sort_keys=True)

            sender = self.context.agent_address
            payload = WalletReadPayload(sender=sender, content=payload_content)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class ScoreWriteRoundBehaviour(AbstractRoundBehaviour):
    """ScoreWriteRoundBehaviour"""

    initial_behaviour_cls = ScoreAddBehaviour
    abci_app_cls = ScoreWriteAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        StartupScoreReadBehaviour,
        ScoreAddBehaviour,
        RandomnessBehaviour,
        SelectKeeperCeramicBehaviour,
        CeramicWriteBehaviour,
        VerificationBehaviour,
        WalletReadBehaviour,
    ]
