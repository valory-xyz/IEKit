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

"""This module contains the base behaviour for the mech interact abci skill."""

import json
from abc import ABC
from datetime import datetime, timedelta
from typing import Any, Callable, Generator, List, Optional, cast

from aea.configurations.data_types import PublicId

from packages.valory.contracts.agent_registry.contract import AgentRegistryContract
from packages.valory.contracts.mech.contract import Mech
from packages.valory.contracts.mech_marketplace.contract import MechMarketplace
from packages.valory.contracts.mech_marketplace_legacy.contract import (
    MechMarketplaceLegacy,
)
from packages.valory.contracts.mech_mm.contract import MechMM
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import BaseTxPayload
from packages.valory.skills.abstract_round_abci.behaviour_utils import (
    BaseBehaviour,
    TimeoutException,
)
from packages.valory.skills.mech_interact_abci.models import (
    MechMarketplaceConfig,
    MechParams,
    MultisendBatch,
)
from packages.valory.skills.mech_interact_abci.states.base import SynchronizedData


WaitableConditionType = Generator[None, None, bool]


class MechInteractBaseBehaviour(BaseBehaviour, ABC):
    """Represents the base class for the mech interaction FSM behaviour."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the bet placement behaviour."""
        super().__init__(**kwargs)
        self.multisend_batches: List[MultisendBatch] = []
        self.multisend_data = b""
        self._safe_tx_hash = ""
        self._is_marketplace_v2_compatible: Optional[bool] = None
        self._compatibility_check_performed: bool = False

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> MechParams:
        """Return the params."""
        return cast(MechParams, self.context.params)

    @property
    def mech_marketplace_config(self) -> MechMarketplaceConfig:
        """Return the mech marketplace config."""
        return cast(MechMarketplaceConfig, self.context.params.mech_marketplace_config)

    def default_error(
        self, contract_id: str, contract_callable: str, response_msg: ContractApiMessage
    ) -> None:
        """Return a default contract interaction error message."""
        self.context.logger.error(
            f"Could not successfully interact with the {contract_id} contract "
            f"using {contract_callable!r}: {response_msg}"
        )

    def contract_interaction_error(
        self, contract_id: str, contract_callable: str, response_msg: ContractApiMessage
    ) -> None:
        """Return a contract interaction error message."""
        # contracts can only return one message, i.e., multiple levels cannot exist.
        for level in ("info", "warning", "error"):
            msg = response_msg.raw_transaction.body.get(level, None)
            logger = getattr(self.context.logger, level)
            if msg is not None:
                logger(msg)
                return

        self.default_error(contract_id, contract_callable, response_msg)

    def contract_interact(
        self,
        performative: ContractApiMessage.Performative,
        contract_address: str,
        contract_public_id: PublicId,
        contract_callable: str,
        data_key: str,
        placeholder: str,
        **kwargs: Any,
    ) -> WaitableConditionType:
        """Interact with a contract."""
        contract_id = str(contract_public_id)

        self.context.logger.info(
            f"Interacting with contract {contract_id} at address {contract_address}\n"
            f"Calling method {contract_callable} with parameters: {kwargs}"
        )

        response_msg = yield from self.get_contract_api_response(
            performative,
            contract_address,
            contract_id,
            contract_callable,
            **kwargs,
        )

        self.context.logger.info(f"Contract response: {response_msg}")

        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.default_error(contract_id, contract_callable, response_msg)
            return False

        data = response_msg.raw_transaction.body.get(data_key, None)
        if data is None:
            self.contract_interaction_error(
                contract_id, contract_callable, response_msg
            )
            return False

        setattr(self, placeholder, data)
        return True

    def _mech_contract_interact(
        self, contract_callable: str, data_key: str, placeholder: str, **kwargs: Any
    ) -> WaitableConditionType:
        """Interact with the mech contract."""
        status = yield from self.contract_interact(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.mech_contract_address,
            contract_public_id=Mech.contract_id,
            contract_callable=contract_callable,
            data_key=data_key,
            placeholder=placeholder,
            **kwargs,
        )
        return status

    def _mech_mm_contract_interact(
        self, contract_callable: str, data_key: str, placeholder: str, **kwargs: Any
    ) -> WaitableConditionType:
        """Interact with the mech mm contract."""
        status = yield from self.contract_interact(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.mech_marketplace_config.priority_mech_address,
            contract_public_id=MechMM.contract_id,
            contract_callable=contract_callable,
            data_key=data_key,
            placeholder=placeholder,
            **kwargs,
        )
        return status

    def _mech_marketplace_contract_interact(
        self,
        contract_callable: str,
        data_key: str,
        placeholder: str,
        **kwargs: Any,
    ) -> WaitableConditionType:
        """Interact with the mech marketplace contract."""
        status = yield from self.contract_interact(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.mech_marketplace_config.mech_marketplace_address,
            contract_public_id=MechMarketplace.contract_id,
            contract_callable=contract_callable,
            data_key=data_key,
            placeholder=placeholder,
            **kwargs,
        )
        return status

    def _mech_marketplace_legacy_contract_interact(
        self,
        contract_callable: str,
        data_key: str,
        placeholder: str,
        **kwargs: Any,
    ) -> WaitableConditionType:
        """Interact with the mech marketplace contract."""
        status = yield from self.contract_interact(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.mech_marketplace_config.mech_marketplace_address,
            contract_public_id=MechMarketplaceLegacy.contract_id,
            contract_callable=contract_callable,
            data_key=data_key,
            placeholder=placeholder,
            **kwargs,
        )
        return status

    def agent_registry_contract_interact(
        self,
        contract_callable: str,
        data_key: str,
        placeholder: str,
        **kwargs: Any,
    ) -> WaitableConditionType:
        """Interact with the mech marketplace contract."""
        status = yield from self.contract_interact(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.agent_registry_address,
            contract_public_id=AgentRegistryContract.contract_id,
            contract_callable=contract_callable,
            data_key=data_key,
            placeholder=placeholder,
            **kwargs,
        )
        return status

    def wait_for_condition_with_sleep(
        self,
        condition_gen: Callable[[], WaitableConditionType],
        timeout: Optional[float] = None,
    ) -> Generator:
        """Wait for a condition to happen and sleep in-between checks.

        This is a modified version of the base `wait_for_condition` method which:
            1. accepts a generator that creates the condition instead of a callable
            2. sleeps in-between checks

        :param condition_gen: a generator of the condition to wait for
        :param timeout: the maximum amount of time to wait
        :yield: None
        """

        deadline = (
            datetime.now() + timedelta(0, timeout)
            if timeout is not None
            else datetime.max
        )

        while True:
            condition_satisfied = yield from condition_gen()
            if condition_satisfied:
                break
            if timeout is not None and datetime.now() > deadline:
                raise TimeoutException()
            msg = f"Retrying in {self.params.mech_interaction_sleep_time} seconds."
            self.context.logger.info(msg)
            yield from self.sleep(self.params.mech_interaction_sleep_time)

    def finish_behaviour(self, payload: BaseTxPayload) -> Generator:
        """Finish the behaviour."""
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _get_mech_address(self) -> str:
        """Get the current mech address."""
        return self.params.mech_marketplace_config.priority_mech_address.lower()

    def _detect_marketplace_compatibility(self) -> WaitableConditionType:
        """Detect if the marketplace/mech contract supports v2 features."""

        if self._compatibility_check_performed:
            return True  # Use in-memory cached result

        mech_address = self._get_mech_address()
        compatibility_cache = self.synchronized_data.marketplace_compatibility_cache

        # Check if we already know this mech address
        if mech_address in compatibility_cache:
            cached_value = compatibility_cache[mech_address]

            # Handle different cache formats during transition
            if isinstance(cached_value, str):
                # New string format: "v1" or "v2"
                self._is_marketplace_v2_compatible = cached_value == "v2"
                cached_version = cached_value
            elif isinstance(cached_value, bool):
                # Old boolean format: True = v2, False = v1
                self._is_marketplace_v2_compatible = cached_value
                cached_version = "v2" if cached_value else "v1"
            elif isinstance(cached_value, dict):
                # Old dict format: get 'compatible' field
                compatible = cached_value.get("compatible", False)
                self._is_marketplace_v2_compatible = compatible
                cached_version = "v2" if compatible else "v1"
            else:
                # Unknown format, fall through to detection
                self.context.logger.warning(
                    f"Unknown cache format for {mech_address}: {type(cached_value)}"
                )
                cached_version = None

            if cached_version:
                self._compatibility_check_performed = True
                self.context.logger.info(
                    f"Using cached compatibility for {mech_address}: {cached_version}"
                )
                return True

        self.context.logger.info(
            f"Detecting marketplace compatibility for new mech: {mech_address}"
        )

        # Try calling get_payment_type on the mech address
        try:
            status = yield from self._mech_mm_contract_interact(
                contract_callable="get_payment_type",
                data_key="payment_type",
                placeholder="_temp_payment_type_check",
                chain_id=self.params.mech_chain_id,
            )

            if status:
                self.context.logger.info(f"Mech {mech_address} supports v2 features")
                self._is_marketplace_v2_compatible = True
            else:
                self.context.logger.info(f"Mech {mech_address} uses v1 features")
                self._is_marketplace_v2_compatible = False

        except Exception as e:
            self.context.logger.warning(
                f"Feature detection failed for mech {mech_address}: {e}. "
                "Defaulting to v1 (legacy mode)"
            )
            self._is_marketplace_v2_compatible = False

        self._compatibility_check_performed = True
        return True

    def get_updated_compatibility_cache(self) -> str:
        """Get the updated compatibility cache as JSON string for synchronized data."""

        try:
            # Get current cache and convert old formats to new string format
            current_cache = {}
            raw_cache = self.synchronized_data.marketplace_compatibility_cache

            # Convert old cache formats to new string format
            for key, value in raw_cache.items():
                if isinstance(value, bool):
                    # Old boolean format: True = v2, False = v1
                    current_cache[key] = "v2" if value else "v1"
                elif isinstance(value, dict):
                    # Old dict format: get 'compatible' field
                    compatible = value.get("compatible", False)
                    current_cache[key] = "v2" if compatible else "v1"
                elif isinstance(value, str):
                    # New string format: keep as is
                    current_cache[key] = value

            if (
                self._compatibility_check_performed
                and self._is_marketplace_v2_compatible is not None
            ):
                mech_address = self._get_mech_address()
                version = "v2" if self._is_marketplace_v2_compatible else "v1"
                current_cache[mech_address] = version
                self.context.logger.info(f"Updated cache: {mech_address} = {version}")

            return json.dumps(current_cache)
        except Exception as e:
            self.context.logger.warning(f"Failed to serialize compatibility cache: {e}")
            return "{}"

    @property
    def is_marketplace_v2_compatible(self) -> bool:
        """Returns True if the marketplace supports v2 features."""

        if not self._compatibility_check_performed:
            raise ValueError(
                "Compatibility check must be performed before accessing this property"
            )
        return self._is_marketplace_v2_compatible or False

    def should_use_marketplace_v2(self) -> bool:
        """Determine if marketplace v2 flow should be used."""

        if not self.params.use_mech_marketplace:
            return False  # Configuration explicitly disables marketplace

        if not self._compatibility_check_performed:
            raise ValueError("Compatibility check must be performed first")

        return self._is_marketplace_v2_compatible or False
