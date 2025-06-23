# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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

"""This package contains the logic for task preparations."""

from datetime import datetime, timezone
from typing import Generator, Optional, cast

from packages.valory.contracts.veolas_delegation.contract import (
    VeOLASDelegationContract,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.contribute_db_abci.contribute_models import TwitterCampaign
from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.signature_validation import (
    SignatureValidationMixin,
)
from packages.valory.skills.decision_making_abci.tasks.task_preparations import (
    TaskPreparation,
)


class CampaignValidationPreparation(TaskPreparation, SignatureValidationMixin):
    """CampaignValidationPreparation"""

    task_name = "campaign_validation"
    task_event = Event.CAMPAIGN_VALIDATION.value

    def check_extra_conditions(self):
        """Validate campaign"""
        yield
        return True

    def _pre_task(self):
        """Preparations before running the task"""
        yield

        for campaign in self.data.twitter_campaigns.campaigns:
            self.logger.info(
                f"Checking campaign proposal {campaign.id} #{campaign.hashtag} [{campaign.status}]"
            )

            # Get campaign start and end times
            start_time = datetime.fromtimestamp(campaign.start_ts, tz=timezone.utc)
            end_time = datetime.fromtimestamp(campaign.end_ts, tz=timezone.utc)

            # Validate pending campaigns
            if campaign.status == "proposed":
                # Verify proposer signature
                message = f"I am signing a message to verify that I propose a campaign starting with {campaign.hashtag[:10]}"
                is_valid = yield from self.validate_signature(
                    message,
                    campaign.proposer.address,
                    campaign.proposer.signature,
                )
                self.logger.info(f"Is the proposer signature valid? {is_valid}")

                campaign.proposer.verified = is_valid

                # Update status
                if is_valid:
                    campaign.status = "voting"
                    self.logger.info("Campaign has been moved into 'voting'")
                else:
                    campaign.status = "void"
                    self.logger.info("Campaign has been moved into 'void'")

            # Check campaings still in voting status
            elif campaign.status == "voting":
                # Campaigns that reached the start time and have not gathered enough votes are void
                if self.now_utc >= start_time:
                    self.logger.info("Campaign has been moved into 'void'")
                    campaign.status = "void"

                # Has the campaign enough votes?
                else:
                    approved = yield from self.check_campaign_consensus(campaign)
                    if approved:
                        self.logger.info("Campaign has been moved into 'scheduled'")
                        campaign.status = "scheduled"

            # Does the campaing need to be started?
            elif campaign.status == "scheduled" and self.now_utc >= start_time:
                self.logger.info("Campaign has been moved into 'live'")
                campaign.status = "live"

            # Does the campaing need to be ended?
            elif campaign.status == "live" and self.now_utc >= end_time:
                self.logger.info("Campaign has been moved into 'ended'")
                campaign.status = "ended"

            # Ignore void and finished states
            else:
                self.logger.info("The campaign does not need to be updated")
                return

            updates = {}
            self.context.contribute_db.update_module_data(self.data)

        return updates, self.task_event

    def _post_task(self):
        """Preparations after running the task"""
        yield
        self.behaviour.context.logger.info("Nothing to do")
        return {}, None

    def check_campaign_consensus(self, campaign: TwitterCampaign):
        """Check whether users agree on approving the campaing"""
        total_voting_power = 0

        for voter in campaign.voters:
            # Verify signature
            hashtag = campaign.hashtag
            message = f"I am signing a message to verify that I approve a campaign starting with {hashtag[:10]}"
            is_valid = yield from self.validate_signature(
                message, voter.address, voter.signature
            )

            self.logger.info(f"Voter: {voter.address}  Signature valid: {is_valid}")
            if not is_valid:
                continue

            # Get voting power
            voting_power = yield from self.get_voting_power(voter["address"])
            self.logger.info(f"Voter: {voter.address}  Voting power: {voting_power}")
            total_voting_power += cast(int, voting_power)

        consensus = total_voting_power >= self.params.tweet_consensus_veolas

        self.behaviour.context.logger.info(
            f"Voting power is {total_voting_power} for campaign {campaign.hashtag}. Approving? {consensus}"
        )

        return consensus

    def get_voting_power(self, address: str):
        """Get the given address's votes."""
        olas_votes = yield from self.get_votes(
            self.params.veolas_delegation_address, address, "ethereum"
        )

        if not olas_votes:
            olas_votes = 0

        self.behaviour.context.logger.info(
            f"Voting power is {olas_votes} for address {address}"
        )
        return olas_votes

    def get_votes(
        self, token_address, voter_address, chain_id
    ) -> Generator[None, None, Optional[float]]:
        """Get the given address's votes."""
        response = yield from self.behaviour.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=token_address,
            contract_id=str(VeOLASDelegationContract.contract_id),
            contract_callable="get_votes",
            voter_address=voter_address,
            chain_id=chain_id,
        )
        if response.performative != ContractApiMessage.Performative.STATE:
            self.behaviour.context.logger.error(
                f"Couldn't get the votes for address {chain_id}::{voter_address}: {response.performative}"
            )
            return None

        if "votes" not in response.state.body:
            self.behaviour.context.logger.error(
                f"State does not contain 'votes': {response.state.body}"
            )
            return None

        votes = int(response.state.body["votes"]) / 1e18  # to olas
        return votes
