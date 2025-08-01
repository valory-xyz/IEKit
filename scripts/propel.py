#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2025 Valory AG
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

"""Propel"""

import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import dotenv
import requests
import urllib3
from propel_client.constants import (  # pylint: disable=import-error
    PROPEL_SERVICE_BASE_URL,
)
from propel_client.cred_storage import CredentialStorage  # pylint: disable=import-error
from propel_client.propel import (  # pylint: disable=import-error
    HttpRequestError,
    PropelClient,
)


logger = logging.getLogger("propel")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


dotenv.load_dotenv(override=True)

HTTP_OK = 200
CONTRIBUTE_SERVICE_NAME_TEST = "test_contribute"
CONTRIBUTE_SERVICE_NAME = "contribute"
PROPEL_TEST_KEYS = [359, 360, 361, 362]
PROPEL_PROD_KEYS = [24, 25, 26, 27]

CONTRIBUTE_VARIABLES_TEST = [
    "TEST_CONTRIBUTE_ALL_PARTICIPANTS",
    "CONTRIBUTE_AUTONOMY_AGENT_MEMORY_LIMIT",
    "CONTRIBUTE_AUTONOMY_AGENT_MEMORY_REQUEST",
    "CONTRIBUTE_BASE_LEDGER_RPC",
    "CONTRIBUTE_CENTAUR_ID_TO_SECRETS",
    "CONTRIBUTE_DRAND_ENDPOINT",
    "CONTRIBUTE_ETHEREUM_LEDGER_RPC",
    "CONTRIBUTE_GNOSIS_LEDGER_RPC",
    "CONTRIBUTE_OPENAI_API_KEY_0",
    "CONTRIBUTE_OPENAI_API_KEY_1",
    "CONTRIBUTE_OPENAI_API_KEY_2",
    "CONTRIBUTE_OPENAI_API_KEY_3",
    "CONTRIBUTE_TWITTER_API_BEARER_TOKEN",
    "CONTRIBUTE_DB_PKEY_67f",
    "AGENT_DB_BASE_URL",
    "USE_ACN_FALSE",
    "CONTRIBUTE_TERMINATION_FROM_BLOCK",
]

CONTRIBUTE_VARIABLES_PROD = [
    "CONTRIBUTE_ALL_PARTICIPANTS",
    "CONTRIBUTE_AUTONOMY_AGENT_MEMORY_LIMIT",
    "CONTRIBUTE_AUTONOMY_AGENT_MEMORY_REQUEST",
    "CONTRIBUTE_BASE_LEDGER_RPC",
    "CONTRIBUTE_CENTAUR_ID_TO_SECRETS",
    "CONTRIBUTE_DRAND_ENDPOINT",
    "CONTRIBUTE_ETHEREUM_LEDGER_RPC",
    "CONTRIBUTE_GNOSIS_LEDGER_RPC",
    "CONTRIBUTE_OPENAI_API_KEY_0",
    "CONTRIBUTE_OPENAI_API_KEY_1",
    "CONTRIBUTE_OPENAI_API_KEY_2",
    "CONTRIBUTE_OPENAI_API_KEY_3",
    "CONTRIBUTE_TWITTER_API_BEARER_TOKEN",
    "CONTRIBUTE_CONTRIBUTE_DB_PKEY",
    "AGENT_DB_BASE_URL",
    "CONTRIBUTE_TERMINATION_FROM_BLOCK",
]


class Agent:
    """Agent"""

    def __init__(self, name: str, client: PropelClient):
        """Constructor"""
        self.name = name
        self.client = client

    def get(self):
        """Get the agent"""
        logger.info(f"Getting agent {self.name}")
        return self.client.agents_get(self.name)

    def restart(self):
        """Restart the agent"""
        logger.info(f"Restarting agent {self.name}")
        return self.client.agents_restart(self.name)

    def stop(self):
        """Stop the agent"""
        logger.info(f"Stopping agent {self.name}")
        return self.client.agents_stop(self.name)

    def get_agent_code(self):
        """Get the agent code"""
        logger.info(f"Getting agent code for {self.name}")
        agent_status = self.get()
        tendermint_p2p_url = agent_status.get("tendermint_p2p_url", None)
        if not tendermint_p2p_url:
            return None

        agent_code = tendermint_p2p_url.split(".")[0].split("-")[-1]
        return agent_code

    def get_agent_state(self):
        """Get the agent state"""
        logger.info(f"Getting status for agent {self.name}")
        data = self.get()
        return data.get("agent_state", None)

    def get_agent_health(self) -> Tuple[bool, Dict]:
        """Get the agent status"""
        logger.info(f"Checking status for agent {self.name}")
        agent_code = self.get_agent_code()
        healthcheck_url = (
            f"https://{agent_code}.agent.propel.autonolas.tech/healthcheck"
        )

        try:
            response = requests.get(healthcheck_url, verify=False)  # nosec
            if response.status_code != HTTP_OK:
                return False, {}
            response_json = response.json()
            is_healthy = response_json["is_transitioning_fast"]
            return is_healthy, response_json
        except Exception: # pylint: disable=broad-except
            return False, {}

    def healthcheck(self) -> Tuple[bool, Optional[str]]:
        """Healthcheck the agent"""
        is_healthy, data = self.get_agent_health()
        period = data.get("period", None)
        return is_healthy, period

    def get_current_round(self) -> Optional[str]:
        """Get the current round"""
        _, status = self.get_agent_health()

        if "current_round" in status:
            return status["current_round"]

        if "rounds" not in status:
            return None

        if len(status["rounds"]) == 0:
            return None

        return status["rounds"][-1]


class Service:
    """Service"""

    def __init__(self, name: str, agents: List[str], client: PropelClient):
        """Constructor"""
        self.name = name
        self.client = client
        self.agents = {name: Agent(name, client) for name in agents}
        self.not_healthy_counter = 0
        self.last_notification = None
        self.last_restart = None

    def restart(self):
        """Restart the service"""
        logger.info(f"Restarting service {self.name}")
        for agent in self.agents.values():
            agent.restart()

    def stop(self):
        """Stop the service"""
        logger.info(f"Stopping service {self.name}")
        for agent in self.agents.values():
            agent.stop()

    def healthcheck(self) -> bool:
        """Healthcheck the service"""
        logger.info(f"Checking health for service {self.name}")
        alive_threshold = math.floor(len(self.agents) * 2 / 3) + 1
        alive_agents = 0
        for agent in self.agents.values():
            is_agent_healthy, _ = agent.healthcheck()
            if is_agent_healthy:
                alive_agents += 1
        is_service_healthy = alive_agents >= alive_threshold

        if not is_service_healthy:
            self.not_healthy_counter += 1
        else:
            self.not_healthy_counter = 0

        return is_service_healthy


class Propel:
    """Propel"""

    def __init__(self):
        """Constructor"""
        self.client = PropelClient(
            base_url=PROPEL_SERVICE_BASE_URL, credentials_storage=CredentialStorage()
        )
        self.login()

    def login(self):
        """Login"""
        self.client.login(
            username=os.getenv("PROPEL_USERNAME"),
            password=os.getenv("PROPEL_PASSWORD"),
        )

    def logout(self):
        """Logout"""
        self.client.logout()

    def deploy(self, service_name, variables, service_ipfs_hash, number_of_agents, keys):
        """Deploy a service"""

        agent_names = [
            f"{service_name}_agent_{i}" for i in range(number_of_agents)
        ]

        # Check if Contribute is already deployed and stop it
        existing_agents = []
        for agent_name in agent_names:
            agent = None
            try:
                agent = self.client.agents_get(agent_name)
            except HttpRequestError:
                print(f"Agent {agent_name} does not exist on Propel")

            if agent:
                existing_agents.append(agent_name)

                # Stop the agent if needed
                if agent.get("agent_state", None) in ["STARTED", "ERROR"]:
                    print(f"Stopping agent {agent_name}...")
                    self.client.agents_stop(agent_name)

        # Wait for stop and delete
        for agent_name in existing_agents:

            # Await for the agent to stop
            while True:
                agent = self.client.agents_get(agent_name)

                if agent.get("agent_state", None) == "DEPLOYED":
                    break
                print(f"Waiting for agent {agent_name} to stop...")
                time.sleep(10)

            print(f"Agent {agent_name} is stopped")
            print(f"Deleting agent {agent_name}...")
            self.client.agents_delete(agent_name)

        # Create the agents
        for i, agent_name in enumerate(agent_names):

            print(f"Creating agent {agent_name}...")
            self.client.agents_create(
                key=keys[i],
                name=agent_name,
                service_ipfs_hash=service_ipfs_hash,
                ingress_enabled=True,
                variables=variables,
                tendermint_ingress_enabled=True,
            )

        # Wait for the agents to be deployed and start them
        for agent_name in agent_names:
            while True:
                agent = self.client.agents_get(agent_name)
                if agent.get("agent_state", None) == "DEPLOYED":
                    print(f"Agent {agent_name} is deployed")
                    break
                print(f"Waiting for agent {agent_name} to be deployed...")
                time.sleep(10)

        # Start the agents
        for agent_name in agent_names:
            print(f"Starting agent {agent_name}...")
            self.client.agents_restart(agent_name)

        # Wait for the agents to start
        for agent_name in agent_names:
            while True:
                agent = self.client.agents_get(agent_name)
                state = agent.get("agent_state", None)
                if state == "STARTED":
                    print(f"Agent {agent_name} is running")
                    break
                if state == "ERROR":
                    print(f"Agent {agent_name} has failed to run")
                    break
                print(f"Waiting for agent {agent_name} to start...")
                time.sleep(10)


def deploy_contribute():
    """Deploy Contribute"""

    # Test
    # SERVICE_NAME_TEST = "impact_evaluator_local"

    # Prod
    SERVICE_NAME_PROD = "impact_evaluator"

    # Load the service hash
    with open(Path("packages", "packages.json"), "r", encoding="utf-8") as f:
        packages = json.load(f)
        service_ipfs_hash = packages["dev"][f"service/valory/{SERVICE_NAME_PROD}/0.1.0"]

    propel = Propel()

    # Test
    # propel.deploy(CONTRIBUTE_SERVICE_NAME_TEST, CONTRIBUTE_VARIABLES_TEST, service_ipfs_hash, 1, PROPEL_TEST_KEYS)

    # Prod
    propel.deploy(CONTRIBUTE_SERVICE_NAME, CONTRIBUTE_VARIABLES_PROD, service_ipfs_hash, 4, PROPEL_PROD_KEYS)


if __name__ == "__main__":
    deploy_contribute()
