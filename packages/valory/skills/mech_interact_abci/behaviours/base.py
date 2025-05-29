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
from dataclasses import asdict, is_dataclass
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

    @property
    def force_cache_refresh(self) -> bool:
        """Return whether to force cache refresh."""
        return self.params.compatibility_config.force_cache_refresh

    @property
    def max_cache_entries(self) -> int:
        """Return maximum number of cache entries."""
        return self.params.compatibility_config.max_cache_entries

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

    def _get_cache_key(self) -> str:
        """Generate cache key for the current marketplace configuration."""
        priority_mech = self.params.mech_marketplace_config.priority_mech_address
        marketplace = self.params.mech_marketplace_config.mech_marketplace_address
        return f"{priority_mech.lower()}:{marketplace.lower()}"

    def _detect_marketplace_compatibility(self) -> WaitableConditionType:
        """Detect if the marketplace/mech contract supports v2 features."""
        if self._compatibility_check_performed:
            return True  # Use in-memory cached result

        # Check if compatibility detection is enabled
        if not self.params.compatibility_config.enable_compatibility_detection:
            self.context.logger.info(
                "Compatibility detection is disabled in configuration. "
                f"Using fallback mode: {'legacy' if self.params.compatibility_config.fallback_to_legacy else 'v2'}"
            )
            self._is_marketplace_v2_compatible = (
                not self.params.compatibility_config.fallback_to_legacy
            )
            self._compatibility_check_performed = True
            return True

        cache_key = self._get_cache_key()
        compatibility_cache = self.synchronized_data.marketplace_compatibility_cache

        # Check synchronized data cache first (unless forced refresh)
        if cache_key in compatibility_cache and not self.force_cache_refresh:
            # Handle both old format (bool) and new format (dict with metadata)
            cache_value = compatibility_cache[cache_key]
            is_cache_valid = True

            if isinstance(cache_value, bool):
                self._is_marketplace_v2_compatible = cache_value
            elif isinstance(cache_value, dict):
                # Check TTL for new format entries
                import time

                current_time = time.time()
                cache_timestamp = cache_value.get("timestamp", 0)
                cache_age = current_time - cache_timestamp

                if cache_age > self.params.compatibility_config.cache_ttl_seconds:
                    self.context.logger.info(
                        f"Cache entry for {cache_key} has expired (age: {cache_age:.0f}s, TTL: {self.params.compatibility_config.cache_ttl_seconds}s)"
                    )
                    is_cache_valid = False
                else:
                    self._is_marketplace_v2_compatible = cache_value.get(
                        "compatible", False
                    )
            else:
                is_cache_valid = False

            if is_cache_valid:
                self._compatibility_check_performed = True
                # Update access time for LRU
                self._update_cache_access_time(cache_key)
                self.context.logger.info(
                    f"Using cached compatibility result for {cache_key}: "
                    f"v{'2' if self._is_marketplace_v2_compatible else '1'} marketplace "
                    "(from synchronized data)"
                )
                return True

        self.context.logger.info(
            "Detecting marketplace contract compatibility (not in cache)..."
        )

        # Try calling get_payment_type on the priority mech address
        try:
            status = yield from self._mech_mm_contract_interact(
                contract_callable="get_payment_type",
                data_key="payment_type",
                placeholder="_temp_payment_type_check",
                chain_id=self.params.mech_chain_id,
            )

            if status:
                self.context.logger.info(
                    f"Contract at {self.params.mech_marketplace_config.priority_mech_address} "
                    "supports v2 marketplace features (get_payment_type detected)"
                )
                self._is_marketplace_v2_compatible = True
            else:
                self.context.logger.info(
                    f"Contract at {self.params.mech_marketplace_config.priority_mech_address} "
                    "does not support v2 marketplace features (get_payment_type failed)"
                )
                self._is_marketplace_v2_compatible = False

        except Exception as e:
            self.context.logger.warning(
                f"Feature detection failed for contract "
                f"{self.params.mech_marketplace_config.priority_mech_address}: {e}. "
                f"Using fallback mode: {'legacy' if self.params.compatibility_config.fallback_to_legacy else 'v2'}"
            )
            self._is_marketplace_v2_compatible = (
                not self.params.compatibility_config.fallback_to_legacy
            )

        # Update the cache in synchronized data through payload if needed
        self._update_compatibility_cache(cache_key, self._is_marketplace_v2_compatible)

        self._compatibility_check_performed = True
        return True

    def _update_compatibility_cache(self, cache_key: str, compatible: bool) -> None:
        """Update the compatibility cache in synchronized data with size management."""
        try:
            # Get current cache and access times
            current_cache = dict(self.synchronized_data.marketplace_compatibility_cache)
            current_access = dict(
                self.synchronized_data.marketplace_compatibility_cache_access
            )

            # Check if update is needed
            cache_value = current_cache.get(cache_key)
            needs_update = False

            if isinstance(cache_value, bool):
                needs_update = cache_value != compatible
            elif isinstance(cache_value, dict):
                needs_update = cache_value.get("compatible", False) != compatible
            else:
                needs_update = True  # New entry

            if needs_update:
                # Clean cache if it's getting too large
                if (
                    len(current_cache) >= self.max_cache_entries
                    and cache_key not in current_cache
                ):
                    current_cache, current_access = self._evict_lru_entries(
                        current_cache, current_access
                    )

                # Update cache with metadata
                import time

                current_time = time.time()
                existing_entry = current_cache.get(cache_key, {})
                access_count = (
                    existing_entry.get("access_count", 0)
                    if isinstance(existing_entry, dict)
                    else 0
                )
                current_cache[cache_key] = {
                    "compatible": compatible,
                    "timestamp": current_time,
                    "access_count": access_count + 1,
                }
                current_access[cache_key] = current_time

                self.context.logger.info(
                    f"Updated compatibility cache: {cache_key} = v{'2' if compatible else '1'} marketplace "
                    f"(cache size: {len(current_cache)}/{self.max_cache_entries}, TTL: {self.params.compatibility_config.cache_ttl_seconds}s)"
                )
            else:
                self.context.logger.debug(f"Cache value unchanged for {cache_key}")

        except Exception as e:
            self.context.logger.warning(f"Failed to update compatibility cache: {e}")

    def _update_cache_access_time(self, cache_key: str) -> None:
        """Update access time for LRU tracking."""
        # This will be handled in get_updated_compatibility_cache for consensus updates
        pass

    def _evict_lru_entries(self, cache: dict, access_times: dict) -> tuple:
        """Remove least recently used entries and expired entries to make room for new ones."""
        try:
            import time

            current_time = time.time()
            ttl_seconds = self.params.compatibility_config.cache_ttl_seconds

            # First, remove expired entries
            expired_keys = []
            for key, cache_value in cache.items():
                if isinstance(cache_value, dict):
                    cache_timestamp = cache_value.get("timestamp", 0)
                    if current_time - cache_timestamp > ttl_seconds:
                        expired_keys.append(key)

            # Remove expired entries
            for key in expired_keys:
                if key in cache:
                    del cache[key]
                if key in access_times:
                    del access_times[key]

            if expired_keys:
                self.context.logger.info(
                    f"Evicted {len(expired_keys)} expired cache entries. "
                    f"Cache size after cleanup: {len(cache)}/{self.max_cache_entries}"
                )

            # Calculate how many more entries to remove (remove 20% when limit reached)
            target_size = int(self.max_cache_entries * 0.8)
            entries_to_remove = len(cache) - target_size

            if entries_to_remove <= 0:
                return cache, access_times

            # Sort by access time (oldest first)
            sorted_by_access = sorted(access_times.items(), key=lambda x: x[1])

            # Remove oldest entries
            removed_count = 0
            for key, _ in sorted_by_access:
                if removed_count >= entries_to_remove:
                    break
                if key in cache:
                    del cache[key]
                    del access_times[key]
                    removed_count += 1

            self.context.logger.info(
                f"Evicted {removed_count} LRU cache entries. "
                f"Final cache size: {len(cache)}/{self.max_cache_entries}"
            )

            return cache, access_times

        except Exception as e:
            self.context.logger.warning(f"Failed to evict cache entries: {e}")
            return cache, access_times

    def get_updated_compatibility_cache(self) -> str:
        """Get the updated compatibility cache as JSON string for synchronized data."""
        try:
            current_cache = dict(self.synchronized_data.marketplace_compatibility_cache)
            current_access = dict(
                self.synchronized_data.marketplace_compatibility_cache_access
            )
            cache_key = self._get_cache_key()

            if (
                self._compatibility_check_performed
                and self._is_marketplace_v2_compatible is not None
            ):
                # Clean cache if needed before adding new entry
                if (
                    len(current_cache) >= self.max_cache_entries
                    and cache_key not in current_cache
                ):
                    current_cache, current_access = self._evict_lru_entries(
                        current_cache, current_access
                    )

                # Update with metadata
                import time

                current_time = time.time()
                existing_entry = current_cache.get(cache_key, {})
                access_count = (
                    existing_entry.get("access_count", 0)
                    if isinstance(existing_entry, dict)
                    else 0
                )
                current_cache[cache_key] = {
                    "compatible": self._is_marketplace_v2_compatible,
                    "timestamp": current_time,
                    "access_count": access_count + 1,
                }
                current_access[cache_key] = current_time

            return json.dumps(current_cache)
        except Exception as e:
            self.context.logger.warning(f"Failed to serialize compatibility cache: {e}")
            return "{}"

    def get_updated_compatibility_cache_access(self) -> str:
        """Get the updated cache access times as JSON string for synchronized data."""
        try:
            current_access = dict(
                self.synchronized_data.marketplace_compatibility_cache_access
            )
            cache_key = self._get_cache_key()

            if self._compatibility_check_performed:
                import time

                current_access[cache_key] = time.time()

            return json.dumps(current_access)
        except Exception as e:
            self.context.logger.warning(f"Failed to serialize cache access times: {e}")
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

        # Respect the configuration's compatibility detection setting
        if not self.params.compatibility_config.enable_compatibility_detection:
            # Use the configured fallback behavior
            return not self.params.compatibility_config.fallback_to_legacy

        return self._is_marketplace_v2_compatible or False


class DataclassEncoder(json.JSONEncoder):
    """A custom JSON encoder for dataclasses."""

    def default(self, o: Any) -> Any:
        """The default JSON encoder."""
        if is_dataclass(o) and not isinstance(o, type):
            return asdict(o)
        return super().default(o)
