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

"""Tests for Persistent Capability Cache and AEA Integration."""

import concurrent.futures
import json
import pytest
import time
from unittest.mock import MagicMock, Mock, patch
from typing import Any, Dict, List

from packages.valory.contracts.mech.contract import (
    MechCapabilityCache, 
    AEAMechResponseIntegration, 
    Mech,
    MechABIDiscoveryEngine
)


class TestMechCapabilityCache:
    """Test suite for MechCapabilityCache."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ledger_api = MagicMock()
        self.mock_ledger_api.api.eth.chain_id = 1
        self.contract_address = "0x1234567890123456789012345678901234567890"
        
        # Mock SynchronizedData
        self.mock_synchronized_data = MagicMock()
        self.mock_db = MagicMock()
        self.mock_synchronized_data.db = self.mock_db
        
        # Sample capabilities
        self.sample_capabilities = {
            "status": "success",
            "abi_version": 0,
            "event_abi": {"name": "Deliver", "inputs": []},
            "has_sender": False,
            "discovery_method": "partial_abi"
        }

    def test_generate_cache_key(self):
        """Test cache key generation."""
        key = MechCapabilityCache._generate_cache_key(self.contract_address, 1)
        expected = f"mech_capabilities_{self.contract_address.lower()}_1"
        assert key == expected

    @patch.object(MechABIDiscoveryEngine, 'discover_contract_capabilities')
    def test_get_capabilities_cache_miss(self, mock_discover):
        """Test capabilities retrieval on cache miss."""
        # Setup cache miss
        self.mock_db.get.return_value = None
        mock_discover.return_value = self.sample_capabilities
        
        result = MechCapabilityCache.get_capabilities(
            self.mock_synchronized_data, self.mock_ledger_api, self.contract_address
        )
        
        assert result == self.sample_capabilities
        mock_discover.assert_called_once()
        # Verify cache store was called
        self.mock_db.update.assert_called_once()

    @patch('time.time')
    @patch.object(MechABIDiscoveryEngine, 'discover_contract_capabilities')
    def test_get_capabilities_cache_hit(self, mock_discover, mock_time):
        """Test capabilities retrieval on cache hit."""
        # Setup valid cache entry
        mock_time.return_value = 1000.0
        cached_data = {
            "capabilities": self.sample_capabilities,
            "timestamp": 900.0,  # 100 seconds ago, within TTL
            "cache_version": "v1.0"
        }
        self.mock_db.get.return_value = json.dumps(cached_data)
        
        result = MechCapabilityCache.get_capabilities(
            self.mock_synchronized_data, self.mock_ledger_api, self.contract_address
        )
        
        assert result == self.sample_capabilities
        mock_discover.assert_not_called()

    @patch('time.time')
    def test_cache_ttl_expiration(self, mock_time):
        """Test cache TTL expiration."""
        mock_time.return_value = 100000.0  # Much later than 24 hours
        expired_data = {
            "capabilities": self.sample_capabilities,
            "timestamp": 100.0,  # Very old timestamp
            "cache_version": "v1.0"
        }
        
        is_valid = MechCapabilityCache._is_cache_valid(expired_data)
        assert is_valid is False

    def test_cache_version_mismatch(self):
        """Test cache invalidation on version mismatch."""
        old_version_data = {
            "capabilities": self.sample_capabilities,
            "timestamp": time.time(),
            "cache_version": "v0.9"  # Old version
        }
        
        is_valid = MechCapabilityCache._is_cache_valid(old_version_data)
        assert is_valid is False

    def test_cache_invalid_structure(self):
        """Test cache invalidation on invalid structure."""
        invalid_data = {
            "capabilities": self.sample_capabilities,
            # Missing timestamp and cache_version
        }
        
        is_valid = MechCapabilityCache._is_cache_valid(invalid_data)
        assert is_valid is False

    @patch.object(MechABIDiscoveryEngine, 'discover_contract_capabilities')
    def test_get_capabilities_without_synchronized_data(self, mock_discover):
        """Test capabilities retrieval without SynchronizedData."""
        mock_discover.return_value = self.sample_capabilities
        
        result = MechCapabilityCache.get_capabilities(
            None, self.mock_ledger_api, self.contract_address
        )
        
        assert result == self.sample_capabilities
        mock_discover.assert_called_once()

    @patch.object(MechABIDiscoveryEngine, 'discover_contract_capabilities')
    def test_force_refresh_bypasses_cache(self, mock_discover):
        """Test force refresh bypasses cache."""
        # Setup valid cache
        cached_data = {
            "capabilities": {"old": "data"},
            "timestamp": time.time(),
            "cache_version": "v1.0"
        }
        self.mock_db.get.return_value = json.dumps(cached_data)
        mock_discover.return_value = self.sample_capabilities
        
        result = MechCapabilityCache.get_capabilities(
            self.mock_synchronized_data, self.mock_ledger_api, 
            self.contract_address, force_refresh=True
        )
        
        assert result == self.sample_capabilities
        mock_discover.assert_called_once()

    def test_cache_storage_error_handling(self):
        """Test graceful handling of cache storage errors."""
        # Mock db.update to raise an exception
        self.mock_db.update.side_effect = TypeError("Storage error")
        
        # Should not raise exception
        MechCapabilityCache._store_in_cache(
            self.mock_synchronized_data, "test_key", self.sample_capabilities
        )

    def test_cache_retrieval_error_handling(self):
        """Test graceful handling of cache retrieval errors."""
        # Mock db.get to raise an exception
        self.mock_db.get.side_effect = TypeError("Retrieval error")
        
        result = MechCapabilityCache._get_from_cache(
            self.mock_synchronized_data, "test_key"
        )
        
        assert result is None


class TestAEAMechResponseIntegration:
    """Test suite for AEAMechResponseIntegration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ledger_api = MagicMock()
        self.mock_ledger_api.api.to_checksum_address.return_value = "0x1234567890123456789012345678901234567890"
        self.mock_ledger_api.api.eth = MagicMock()
        self.contract_address = "0x1234567890123456789012345678901234567890"
        self.request_id = 123

        # Mock SynchronizedData
        self.mock_synchronized_data = MagicMock()

    @patch.object(MechCapabilityCache, 'get_capabilities')
    @patch('packages.valory.contracts.mech.contract.event_abi_to_log_topic')
    @patch('packages.valory.contracts.mech.contract.get_event_data')
    @patch.object(Mech, '_process_delivered_events')
    def test_aea_compatible_success(self, mock_process, mock_get_event_data, 
                                   mock_event_topic, mock_get_capabilities):
        """Test successful AEA-compatible response fetching."""
        # Setup mocks
        capabilities = {
            "status": "success",
            "event_abi": {"name": "Deliver", "inputs": []},
            "abi_version": 0
        }
        mock_get_capabilities.return_value = capabilities
        mock_event_topic.return_value = "0xabcdef"
        
        # Mock log processing
        mock_log = MagicMock()
        self.mock_ledger_api.api.eth.get_logs.return_value = [mock_log]
        mock_event_data = MagicMock()
        mock_event_data.get.return_value = {"requestId": self.request_id}
        mock_get_event_data.return_value = mock_event_data
        mock_process.return_value = {"data": b"response_data"}

        result = AEAMechResponseIntegration.get_response_aea_compatible(
            self.mock_ledger_api, self.contract_address, self.request_id,
            self.mock_synchronized_data
        )

        assert "data" in result
        assert result["data"] == b"response_data"
        mock_get_capabilities.assert_called_once()

    @patch.object(MechCapabilityCache, 'get_capabilities')
    def test_aea_compatible_discovery_failure(self, mock_get_capabilities):
        """Test AEA-compatible handling of discovery failures."""
        mock_get_capabilities.return_value = {
            "status": "error",
            "error": "No compatible ABI found"
        }

        result = AEAMechResponseIntegration.get_response_aea_compatible(
            self.mock_ledger_api, self.contract_address, self.request_id,
            self.mock_synchronized_data
        )

        assert result["status"] == "error"
        assert result["error_type"] == "abi_discovery_failed"
        assert "No compatible ABI found" in result["error"]

    @patch.object(MechCapabilityCache, 'get_capabilities')
    @patch('packages.valory.contracts.mech.contract.event_abi_to_log_topic')
    def test_aea_compatible_log_processing_error(self, mock_event_topic, mock_get_capabilities):
        """Test graceful handling of log processing errors."""
        # Setup valid capabilities
        capabilities = {
            "status": "success",
            "event_abi": {"name": "Deliver", "inputs": []},
            "abi_version": 0
        }
        mock_get_capabilities.return_value = capabilities
        mock_event_topic.return_value = "0xabcdef"
        
        # Mock get_logs to raise exception
        self.mock_ledger_api.api.eth.get_logs.side_effect = Exception("RPC Error")

        result = AEAMechResponseIntegration.get_response_aea_compatible(
            self.mock_ledger_api, self.contract_address, self.request_id,
            self.mock_synchronized_data, timeout=1.0
        )

        assert result["status"] == "error"
        assert result["error_type"] == "timeout"

    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_execute_with_timeout_success(self, mock_executor):
        """Test successful execution with timeout."""
        mock_future = MagicMock()
        mock_future.result.return_value = {"success": True}
        mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future

        def test_func():
            return {"success": True}

        result, error = AEAMechResponseIntegration.execute_with_timeout(test_func, 5.0)

        assert result == {"success": True}
        assert error is None

    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_execute_with_timeout_timeout_error(self, mock_executor):
        """Test timeout error handling."""
        mock_future = MagicMock()
        mock_future.result.side_effect = concurrent.futures.TimeoutError()
        mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future

        def test_func():
            time.sleep(10)  # This won't actually execute due to mock
            return {"success": True}

        result, error = AEAMechResponseIntegration.execute_with_timeout(test_func, 1.0)

        assert result is None
        assert "Operation timed out after 1.0 seconds" in error

    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_execute_with_timeout_general_error(self, mock_executor):
        """Test general error handling."""
        mock_future = MagicMock()
        mock_future.result.side_effect = ValueError("Test error")
        mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future

        def test_func():
            raise ValueError("Test error")

        result, error = AEAMechResponseIntegration.execute_with_timeout(test_func, 5.0)

        assert result is None
        assert "Operation failed: Test error" in error


class TestEnhancedMechIntegration:
    """Integration tests for enhanced Mech contract with caching."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.mock_ledger_api = MagicMock()
        self.mock_ledger_api.api.to_checksum_address.return_value = "0x1234567890123456789012345678901234567890"
        self.mock_ledger_api.api.eth.chain_id = 1
        self.contract_address = "0x1234567890123456789012345678901234567890"
        self.request_id = 123
        self.mock_synchronized_data = MagicMock()

    @patch.object(AEAMechResponseIntegration, 'get_response_aea_compatible')
    def test_enhanced_get_response_with_cache(self, mock_aea_integration):
        """Test enhanced get_response with caching enabled."""
        mock_aea_integration.return_value = {"data": b"cached_response"}

        result = Mech.get_response(
            self.mock_ledger_api,
            self.contract_address,
            self.request_id,
            synchronized_data=self.mock_synchronized_data,
            use_enhanced_discovery=True
        )

        assert result == {"data": b"cached_response"}
        mock_aea_integration.assert_called_once_with(
            self.mock_ledger_api, self.contract_address, self.request_id,
            self.mock_synchronized_data, "earliest", "latest", 300.0
        )

    @patch.object(AEAMechResponseIntegration, 'get_response_aea_compatible')
    def test_enhanced_get_response_without_cache(self, mock_aea_integration):
        """Test enhanced get_response without caching."""
        mock_aea_integration.return_value = {"data": b"uncached_response"}

        result = Mech.get_response(
            self.mock_ledger_api,
            self.contract_address,
            self.request_id,
            synchronized_data=None,
            use_enhanced_discovery=True
        )

        assert result == {"data": b"uncached_response"}
        mock_aea_integration.assert_called_once_with(
            self.mock_ledger_api, self.contract_address, self.request_id,
            None, "earliest", "latest", 300.0
        )

    def test_legacy_mode_compatibility(self):
        """Test legacy mode still works."""
        with patch.object(Mech, 'execute_with_timeout') as mock_timeout:
            mock_timeout.return_value = ({"data": b"legacy_response"}, None)

            result = Mech.get_response(
                self.mock_ledger_api,
                self.contract_address,
                self.request_id,
                use_enhanced_discovery=False
            )

            assert result == {"data": b"legacy_response"}
            mock_timeout.assert_called_once()


class TestCachePerformance:
    """Performance and behavior tests for caching system."""

    def setup_method(self):
        """Set up performance test fixtures."""
        self.mock_synchronized_data = MagicMock()
        self.mock_db = MagicMock()
        self.mock_synchronized_data.db = self.mock_db

    def test_cache_key_deterministic(self):
        """Test cache keys are deterministic for consensus."""
        address1 = "0x1234567890123456789012345678901234567890"
        address2 = "0X1234567890123456789012345678901234567890"  # Different case
        
        key1 = MechCapabilityCache._generate_cache_key(address1, 1)
        key2 = MechCapabilityCache._generate_cache_key(address2, 1)
        
        # Should be identical (case-insensitive)
        assert key1 == key2

    def test_cache_size_efficiency(self):
        """Test cache entries are size-efficient."""
        capabilities = {
            "status": "success",
            "abi_version": 0,
            "event_abi": {"name": "Deliver", "inputs": [{"name": "data", "type": "bytes"}]},
            "has_sender": False,
            "discovery_method": "partial_abi",
            "event_structure": {"input_count": 1, "has_sender": False}
        }
        
        cache_data = {
            "capabilities": capabilities,
            "timestamp": time.time(),
            "cache_version": "v1.0"
        }
        
        serialized = json.dumps(cache_data)
        # Should be less than 1KB as designed
        assert len(serialized.encode('utf-8')) < 1024

    @patch('time.time')
    def test_cache_ttl_boundary(self, mock_time):
        """Test cache TTL boundary conditions."""
        # Test just over TTL boundary
        mock_time.return_value = 86401.0  # Just over 24 hours later
        
        boundary_data = {
            "capabilities": {},
            "timestamp": 0.0,
            "cache_version": "v1.0"
        }
        
        is_valid = MechCapabilityCache._is_cache_valid(boundary_data)
        assert is_valid is False  # Should be invalid when over TTL

    def test_multiple_contract_caching(self):
        """Test caching works correctly for multiple contracts."""
        address1 = "0x1111111111111111111111111111111111111111"
        address2 = "0x2222222222222222222222222222222222222222"
        
        key1 = MechCapabilityCache._generate_cache_key(address1, 1)
        key2 = MechCapabilityCache._generate_cache_key(address2, 1)
        
        assert key1 != key2
        assert address1.lower() in key1
        assert address2.lower() in key2


if __name__ == "__main__":
    pytest.main([__file__])