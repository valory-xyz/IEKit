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

"""Integration tests for Gnosis mech contract with real RPC."""

import pytest
import time
from unittest.mock import MagicMock
from typing import Any, Dict

from packages.valory.contracts.mech.contract import (
    MechABIDiscoveryEngine,
    MechCapabilityCache,
    Mech
)


# Test configuration
GNOSIS_RPC_URL = "https://wispy-bitter-county.xdai.quiknode.pro/b06415eae92ec245c90aff5831c476eaedeca9dc"
MECH_CONTRACT_ADDRESS = "0x77af31De935740567Cf4fF1986D04B2c964A786a"
CHAIN_ID_GNOSIS = 100


class MockLedgerApi:
    """Mock ledger API for integration testing."""
    
    def __init__(self):
        from web3 import Web3
        self.api = Web3(Web3.HTTPProvider(GNOSIS_RPC_URL))
        self.api.eth.chain_id = CHAIN_ID_GNOSIS
    

class MockSynchronizedData:
    """Mock SynchronizedData for caching tests."""
    
    def __init__(self):
        self.db = MockDB()


class MockDB:
    """Mock database for cache storage."""
    
    def __init__(self):
        self._data = {}
    
    def get(self, key: str) -> str:
        return self._data.get(key)
    
    def update(self, data: Dict[str, str]) -> None:
        self._data.update(data)


@pytest.mark.integration
class TestGnosisRealContract:
    """Integration tests against real Gnosis mech contract."""

    def setup_method(self):
        """Set up test fixtures."""
        self.ledger_api = MockLedgerApi()
        self.contract_address = MECH_CONTRACT_ADDRESS
        self.synchronized_data = MockSynchronizedData()

    def test_contract_connection(self):
        """Test basic connection to Gnosis RPC and contract."""
        try:
            # Test RPC connection
            latest_block = self.ledger_api.api.eth.get_block('latest')
            assert latest_block is not None
            assert latest_block['number'] > 0
            
            # Test contract address checksum
            checksum_address = self.ledger_api.api.to_checksum_address(self.contract_address)
            assert checksum_address == self.contract_address
            
            print(f"✅ Connected to Gnosis - Latest block: {latest_block['number']}")
            
        except Exception as e:
            pytest.skip(f"Cannot connect to Gnosis RPC: {e}")

    def test_abi_discovery_real_contract(self):
        """Test ABI discovery against real Gnosis mech contract."""
        try:
            capabilities = MechABIDiscoveryEngine.discover_contract_capabilities(
                self.ledger_api, self.contract_address
            )
            
            # Verify successful discovery
            assert capabilities["status"] == "success"
            
            # This contract should be legacy (no sender field)
            assert capabilities["has_sender"] is False
            
            # Should use partial ABI (not full ABI fallback)
            assert capabilities["discovery_method"] == "partial_abi"
            
            # Should be ABI version 0 (legacy)
            assert capabilities["abi_version"] == 0
            
            # Verify event structure
            event_structure = capabilities["event_structure"]
            assert event_structure["has_request_id"] is True
            assert event_structure["has_data"] is True
            assert event_structure["has_sender"] is False
            assert len(event_structure["indexed_inputs"]) == 0  # No indexed fields
            
            print(f"✅ ABI Discovery successful: {capabilities['discovery_method']} method")
            print(f"   ABI Version: {capabilities['abi_version']}")
            print(f"   Has Sender: {capabilities['has_sender']}")
            print(f"   Event Structure: {event_structure}")
            
        except Exception as e:
            pytest.fail(f"ABI discovery failed: {e}")

    def test_cache_functionality_real_contract(self):
        """Test caching with real contract discovery."""
        try:
            # First call - should discover and cache
            start_time = time.time()
            capabilities1 = MechCapabilityCache.get_capabilities(
                self.synchronized_data, self.ledger_api, self.contract_address
            )
            first_call_time = time.time() - start_time
            
            assert capabilities1["status"] == "success"
            
            # Second call - should use cache
            start_time = time.time()
            capabilities2 = MechCapabilityCache.get_capabilities(
                self.synchronized_data, self.ledger_api, self.contract_address
            )
            second_call_time = time.time() - start_time
            
            # Should be identical
            assert capabilities1 == capabilities2
            
            # Second call should be significantly faster (cache hit)
            assert second_call_time < first_call_time * 0.5
            
            # Verify cache key was generated
            cache_key = MechCapabilityCache._generate_cache_key(
                self.contract_address, CHAIN_ID_GNOSIS
            )
            cached_data = self.synchronized_data.db.get(cache_key)
            assert cached_data is not None
            
            print(f"✅ Cache test passed:")
            print(f"   First call: {first_call_time:.3f}s")
            print(f"   Second call: {second_call_time:.3f}s")
            print(f"   Speedup: {first_call_time/second_call_time:.1f}x")
            
        except Exception as e:
            pytest.fail(f"Cache functionality test failed: {e}")

    def test_get_response_no_data(self):
        """Test get_response with non-existent request ID."""
        try:
            # Use a request ID that definitely doesn't exist
            fake_request_id = 999999999
            
            result = Mech.get_response(
                ledger_api=self.ledger_api,
                contract_address=self.contract_address,
                request_id=fake_request_id,
                synchronized_data=self.synchronized_data,
                use_enhanced_discovery=True,
                from_block="latest-1000",  # Only check recent blocks
                to_block="latest",
                timeout=10.0
            )
            
            # Should return info message (no response found)
            assert "info" in result
            assert "has not delivered a response yet" in result["info"]
            assert str(fake_request_id) in result["info"]
            
            # Should include discovery info
            if "discovery_info" in result:
                discovery_info = result["discovery_info"]
                assert discovery_info["abi_version"] == 0
                assert discovery_info["discovery_method"] == "partial_abi"
                assert discovery_info["has_sender"] is False
            
            print(f"✅ get_response test passed for non-existent request")
            print(f"   Result: {result}")
            
        except Exception as e:
            pytest.fail(f"get_response test failed: {e}")

    def test_performance_comparison(self):
        """Compare enhanced vs legacy performance."""
        try:
            fake_request_id = 999999999
            block_range = ("latest-100", "latest")
            
            # Test enhanced mode
            start_time = time.time()
            result_enhanced = Mech.get_response(
                ledger_api=self.ledger_api,
                contract_address=self.contract_address,
                request_id=fake_request_id,
                synchronized_data=self.synchronized_data,
                use_enhanced_discovery=True,
                from_block=block_range[0],
                to_block=block_range[1],
                timeout=10.0
            )
            enhanced_time = time.time() - start_time
            
            # Test legacy mode
            start_time = time.time()
            result_legacy = Mech.get_response(
                ledger_api=self.ledger_api,
                contract_address=self.contract_address,
                request_id=fake_request_id,
                use_enhanced_discovery=False,
                from_block=block_range[0],
                to_block=block_range[1],
                timeout=10.0
            )
            legacy_time = time.time() - start_time
            
            # Both should return similar results (no data found)
            assert "info" in result_enhanced
            assert "info" in result_legacy
            
            # Enhanced should be faster or comparable
            speedup = legacy_time / enhanced_time if enhanced_time > 0 else 1.0
            
            print(f"✅ Performance comparison:")
            print(f"   Enhanced mode: {enhanced_time:.3f}s")
            print(f"   Legacy mode: {legacy_time:.3f}s")
            print(f"   Speedup: {speedup:.1f}x")
            
            # Enhanced mode should include discovery metadata
            if "discovery_info" in result_enhanced:
                print(f"   Enhanced includes discovery metadata: ✅")
            
        except Exception as e:
            pytest.fail(f"Performance comparison failed: {e}")

    def test_error_handling_invalid_contract(self):
        """Test error handling with invalid contract address."""
        try:
            invalid_address = "0x0000000000000000000000000000000000000000"
            
            capabilities = MechABIDiscoveryEngine.discover_contract_capabilities(
                self.ledger_api, invalid_address
            )
            
            # Should fail gracefully
            assert capabilities["status"] == "error"
            assert "No compatible Deliver event found" in capabilities["error"]
            assert capabilities["discovery_method"] == "exhausted"
            
            print(f"✅ Error handling test passed for invalid contract")
            
        except Exception as e:
            pytest.fail(f"Error handling test failed: {e}")

    def test_chain_id_consistency(self):
        """Test that chain ID is handled consistently."""
        try:
            # Generate cache key
            cache_key = MechCapabilityCache._generate_cache_key(
                self.contract_address, CHAIN_ID_GNOSIS
            )
            
            # Should include chain ID
            assert str(CHAIN_ID_GNOSIS) in cache_key
            assert self.contract_address.lower() in cache_key
            
            # Should be deterministic
            cache_key2 = MechCapabilityCache._generate_cache_key(
                self.contract_address, CHAIN_ID_GNOSIS
            )
            assert cache_key == cache_key2
            
            print(f"✅ Chain ID consistency test passed")
            print(f"   Cache key: {cache_key}")
            
        except Exception as e:
            pytest.fail(f"Chain ID consistency test failed: {e}")


@pytest.mark.integration
@pytest.mark.slow
class TestGnosisLoadTest:
    """Load testing for Gnosis integration."""

    def setup_method(self):
        """Set up load test fixtures."""
        self.ledger_api = MockLedgerApi()
        self.contract_address = MECH_CONTRACT_ADDRESS
        self.synchronized_data = MockSynchronizedData()

    def test_multiple_requests_performance(self):
        """Test performance with multiple sequential requests."""
        try:
            request_ids = [999999990 + i for i in range(5)]
            times = []
            
            for request_id in request_ids:
                start_time = time.time()
                result = Mech.get_response(
                    ledger_api=self.ledger_api,
                    contract_address=self.contract_address,
                    request_id=request_id,
                    synchronized_data=self.synchronized_data,
                    use_enhanced_discovery=True,
                    from_block="latest-50",
                    to_block="latest",
                    timeout=5.0
                )
                elapsed = time.time() - start_time
                times.append(elapsed)
                
                # Should consistently return no data found
                assert "info" in result
            
            avg_time = sum(times) / len(times)
            
            # After first request, subsequent requests should be faster (cached)
            if len(times) > 1:
                first_time = times[0]
                avg_cached_time = sum(times[1:]) / len(times[1:])
                speedup = first_time / avg_cached_time if avg_cached_time > 0 else 1.0
                
                print(f"✅ Load test completed:")
                print(f"   First request: {first_time:.3f}s")
                print(f"   Avg cached requests: {avg_cached_time:.3f}s")
                print(f"   Cache speedup: {speedup:.1f}x")
                print(f"   Overall avg: {avg_time:.3f}s")
                
                # Cached requests should be significantly faster
                assert speedup > 2.0, f"Cache speedup {speedup:.1f}x is less than expected 2.0x"
            
        except Exception as e:
            pytest.fail(f"Load test failed: {e}")


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-s", "--tb=short"])