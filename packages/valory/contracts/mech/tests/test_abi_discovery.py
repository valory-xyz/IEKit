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

"""Tests for Enhanced ABI Discovery Engine."""

import pytest
from unittest.mock import MagicMock, Mock, patch
from typing import Any, Dict, List

from packages.valory.contracts.mech.contract import MechABIDiscoveryEngine, Mech, partial_abis


class TestMechABIDiscoveryEngine:
    """Test suite for MechABIDiscoveryEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ledger_api = MagicMock()
        self.mock_ledger_api.api.eth.contract = MagicMock()
        self.contract_address = "0x1234567890123456789012345678901234567890"
        
        # Mock event ABI structures
        self.legacy_event_abi = {
            "name": "Deliver",
            "type": "event",
            "inputs": [
                {"name": "requestId", "type": "uint256", "indexed": False},
                {"name": "data", "type": "bytes", "indexed": False}
            ]
        }
        
        self.modern_event_abi = {
            "name": "Deliver", 
            "type": "event",
            "inputs": [
                {"name": "sender", "type": "address", "indexed": True},
                {"name": "requestId", "type": "uint256", "indexed": False},
                {"name": "data", "type": "bytes", "indexed": False}
            ]
        }

    def test_discover_contract_capabilities_partial_abi_success(self):
        """Test successful discovery using partial ABI."""
        # Mock contract instance
        mock_contract = MagicMock()
        mock_contract.events.Deliver.return_value.abi = self.legacy_event_abi
        self.mock_ledger_api.api.eth.contract.return_value = mock_contract

        result = MechABIDiscoveryEngine.discover_contract_capabilities(
            self.mock_ledger_api, self.contract_address
        )

        assert result["status"] == "success"
        assert result["abi_version"] == 0
        assert result["discovery_method"] == "partial_abi"
        assert result["has_sender"] is False
        assert "event_structure" in result
        
        # Verify contract was called with first partial ABI
        self.mock_ledger_api.api.eth.contract.assert_called_with(
            self.contract_address, abi=partial_abis[0]
        )

    def test_discover_contract_capabilities_modern_abi_success(self):
        """Test discovery with modern ABI (has sender field)."""
        # Mock first ABI to fail, second to succeed
        mock_contract = MagicMock()
        mock_contract.events.Deliver.return_value.abi = self.modern_event_abi
        
        def side_effect(address, abi):
            if abi == partial_abis[0]:
                # First ABI fails
                failing_contract = MagicMock()
                failing_contract.events.Deliver.side_effect = AttributeError("Not found")
                return failing_contract
            else:
                # Second ABI succeeds
                return mock_contract
                
        self.mock_ledger_api.api.eth.contract.side_effect = side_effect

        result = MechABIDiscoveryEngine.discover_contract_capabilities(
            self.mock_ledger_api, self.contract_address
        )

        assert result["status"] == "success"
        assert result["abi_version"] == 1
        assert result["discovery_method"] == "partial_abi"
        assert result["has_sender"] is True

    @patch.object(Mech, 'get_instance')
    def test_discover_contract_capabilities_fallback_to_full_abi(self, mock_get_instance):
        """Test fallback to full ABI when partial ABIs fail."""
        # Mock partial ABIs to fail
        def partial_abi_side_effect(address, abi):
            failing_contract = MagicMock()
            failing_contract.events.Deliver.side_effect = AttributeError("Not found")
            return failing_contract
            
        self.mock_ledger_api.api.eth.contract.side_effect = partial_abi_side_effect

        # Mock full ABI to succeed
        mock_full_contract = MagicMock()
        mock_full_contract.events.Deliver.return_value.abi = self.modern_event_abi
        mock_get_instance.return_value = mock_full_contract

        result = MechABIDiscoveryEngine.discover_contract_capabilities(
            self.mock_ledger_api, self.contract_address
        )

        assert result["status"] == "success"
        assert result["abi_version"] == "full"
        assert result["discovery_method"] == "full_abi"
        assert result["has_sender"] is True

    @patch.object(Mech, 'get_instance')
    def test_discover_contract_capabilities_all_fail(self, mock_get_instance):
        """Test when all ABI discovery methods fail."""
        # Mock all ABIs to fail
        def failing_side_effect(*args, **kwargs):
            failing_contract = MagicMock()
            failing_contract.events.Deliver.side_effect = AttributeError("Not found")
            return failing_contract
            
        self.mock_ledger_api.api.eth.contract.side_effect = failing_side_effect
        mock_get_instance.side_effect = AttributeError("Not found")

        result = MechABIDiscoveryEngine.discover_contract_capabilities(
            self.mock_ledger_api, self.contract_address
        )

        assert result["status"] == "error"
        assert "No compatible Deliver event found" in result["error"]
        assert result["discovery_method"] == "exhausted"

    def test_analyze_event_structure_legacy(self):
        """Test event structure analysis for legacy ABI."""
        result = MechABIDiscoveryEngine._analyze_event_structure(self.legacy_event_abi)
        
        assert result["input_count"] == 2
        assert result["input_names"] == ["requestId", "data"]
        assert result["indexed_inputs"] == []
        assert result["has_sender"] is False
        assert result["has_request_id"] is True
        assert result["has_data"] is True

    def test_analyze_event_structure_modern(self):
        """Test event structure analysis for modern ABI."""
        result = MechABIDiscoveryEngine._analyze_event_structure(self.modern_event_abi)
        
        assert result["input_count"] == 3
        assert result["input_names"] == ["sender", "requestId", "data"]
        assert result["indexed_inputs"] == ["sender"]
        assert result["has_sender"] is True
        assert result["has_request_id"] is True
        assert result["has_data"] is True


class TestEnhancedGetResponse:
    """Test suite for enhanced get_response method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ledger_api = MagicMock()
        self.mock_ledger_api.api.to_checksum_address.return_value = "0x1234567890123456789012345678901234567890"
        self.mock_ledger_api.api.eth = MagicMock()
        self.contract_address = "0x1234567890123456789012345678901234567890"
        self.request_id = 123

        # Mock successful capabilities discovery
        self.mock_capabilities = {
            "status": "success",
            "abi_version": 0,
            "event_abi": {
                "name": "Deliver",
                "inputs": [
                    {"name": "requestId", "type": "uint256"},
                    {"name": "data", "type": "bytes"}
                ]
            },
            "has_sender": False,
            "discovery_method": "partial_abi",
            "event_structure": {
                "input_count": 2,
                "has_sender": False,
                "has_request_id": True,
                "has_data": True
            }
        }

    @patch.object(MechABIDiscoveryEngine, 'discover_contract_capabilities')
    @patch('packages.valory.contracts.mech.contract.event_abi_to_log_topic')
    @patch('packages.valory.contracts.mech.contract.get_event_data')
    def test_get_response_enhanced_success(self, mock_get_event_data, mock_event_abi_to_log_topic, mock_discover):
        """Test successful enhanced get_response."""
        # Setup mocks
        mock_discover.return_value = self.mock_capabilities
        mock_event_abi_to_log_topic.return_value = "0xabcdef"
        
        # Mock log data
        mock_log = MagicMock()
        mock_log.get.return_value = {"requestId": self.request_id}
        self.mock_ledger_api.api.eth.get_logs.return_value = [mock_log]
        
        # Mock decoded event data
        mock_event_data = MagicMock()
        mock_event_data.get.return_value = {"requestId": self.request_id, "data": b"response_data"}
        mock_get_event_data.return_value = mock_event_data

        result = Mech.get_response(
            self.mock_ledger_api,
            self.contract_address,
            self.request_id,
            use_enhanced_discovery=True
        )

        assert "data" in result
        assert result["data"] == b"response_data"
        assert "discovery_info" in result
        assert result["discovery_info"]["abi_version"] == 0
        assert result["discovery_info"]["discovery_method"] == "partial_abi"

    @patch.object(MechABIDiscoveryEngine, 'discover_contract_capabilities')
    def test_get_response_enhanced_discovery_failure(self, mock_discover):
        """Test enhanced get_response when ABI discovery fails."""
        mock_discover.return_value = {
            "status": "error",
            "error": "No compatible Deliver event found",
            "discovery_method": "exhausted"
        }

        result = Mech.get_response(
            self.mock_ledger_api,
            self.contract_address,
            self.request_id,
            use_enhanced_discovery=True
        )

        assert "error" in result
        assert "ABI discovery failed" in result["error"]
        assert result["contract_address"] == self.contract_address

    @patch.object(MechABIDiscoveryEngine, 'discover_contract_capabilities')
    @patch('packages.valory.contracts.mech.contract.event_abi_to_log_topic')
    def test_get_response_enhanced_no_logs_found(self, mock_event_abi_to_log_topic, mock_discover):
        """Test enhanced get_response when no logs are found."""
        mock_discover.return_value = self.mock_capabilities
        mock_event_abi_to_log_topic.return_value = "0xabcdef"
        self.mock_ledger_api.api.eth.get_logs.return_value = []

        result = Mech.get_response(
            self.mock_ledger_api,
            self.contract_address,
            self.request_id,
            use_enhanced_discovery=True
        )

        assert "info" in result
        assert "has not delivered a response yet" in result["info"]
        assert str(self.request_id) in result["info"]

    @patch.object(MechABIDiscoveryEngine, 'discover_contract_capabilities')
    @patch('packages.valory.contracts.mech.contract.event_abi_to_log_topic')
    @patch('packages.valory.contracts.mech.contract.get_event_data')
    def test_get_response_enhanced_multiple_responses(self, mock_get_event_data, mock_event_abi_to_log_topic, mock_discover):
        """Test enhanced get_response when multiple responses found."""
        mock_discover.return_value = self.mock_capabilities
        mock_event_abi_to_log_topic.return_value = "0xabcdef"
        
        # Mock multiple logs
        mock_log1 = MagicMock()
        mock_log2 = MagicMock()
        self.mock_ledger_api.api.eth.get_logs.return_value = [mock_log1, mock_log2]
        
        # Mock multiple decoded events
        mock_event_data = MagicMock()
        mock_event_data.get.return_value = {"requestId": self.request_id}
        mock_get_event_data.return_value = mock_event_data

        result = Mech.get_response(
            self.mock_ledger_api,
            self.contract_address,
            self.request_id,
            use_enhanced_discovery=True
        )

        assert "error" in result
        assert "A single response was expected" in result["error"]
        assert "Received 2 responses" in result["error"]

    def test_get_response_legacy_mode(self):
        """Test get_response with legacy mode (use_enhanced_discovery=False)."""
        # This should use the legacy implementation path
        with patch.object(Mech, 'get_instance') as mock_get_instance:
            mock_contract = MagicMock()
            mock_contract.events.Deliver.return_value.abi = self.mock_capabilities["event_abi"]
            mock_get_instance.return_value = mock_contract
            
            with patch('packages.valory.contracts.mech.contract.event_abi_to_log_topic') as mock_topic:
                mock_topic.return_value = "0xabcdef"
                self.mock_ledger_api.api.eth.get_logs.return_value = []
                
                result = Mech.get_response(
                    self.mock_ledger_api,
                    self.contract_address,
                    self.request_id,
                    use_enhanced_discovery=False
                )

                assert "info" in result
                assert "has not delivered a response yet" in result["info"]


class TestProcessDeliveredEvents:
    """Test suite for _process_delivered_events method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.contract_address = "0x1234567890123456789012345678901234567890"
        self.request_id = 123
        self.mock_capabilities = {
            "abi_version": 0,
            "discovery_method": "partial_abi",
            "has_sender": False,
            "event_structure": {"input_count": 2}
        }

    def test_process_delivered_events_no_events(self):
        """Test processing when no events are found."""
        result = Mech._process_delivered_events(
            [], self.request_id, self.contract_address, self.mock_capabilities
        )
        
        assert "info" in result
        assert "has not delivered a response yet" in result["info"]
        assert "partial_abi" in result["info"]

    def test_process_delivered_events_single_success(self):
        """Test successful processing of single event."""
        mock_event = MagicMock()
        mock_event.get.return_value = {"requestId": self.request_id, "data": b"test_data"}
        
        result = Mech._process_delivered_events(
            [mock_event], self.request_id, self.contract_address, self.mock_capabilities
        )
        
        assert "data" in result
        assert result["data"] == b"test_data"
        assert "discovery_info" in result
        assert result["discovery_info"]["abi_version"] == 0

    def test_process_delivered_events_multiple_events(self):
        """Test processing when multiple events found."""
        mock_events = [MagicMock(), MagicMock()]
        
        result = Mech._process_delivered_events(
            mock_events, self.request_id, self.contract_address, self.mock_capabilities
        )
        
        assert "error" in result
        assert "A single response was expected" in result["error"]
        assert "Received 2 responses" in result["error"]
        assert "ABI version: 0" in result["error"]

    def test_process_delivered_events_invalid_format(self):
        """Test processing when event has invalid format."""
        mock_event = MagicMock()
        mock_event.get.return_value = None  # Invalid args
        
        result = Mech._process_delivered_events(
            [mock_event], self.request_id, self.contract_address, self.mock_capabilities
        )
        
        assert "error" in result
        assert "does not match the expected format" in result["error"]
        assert "Event structure:" in result["error"]

    def test_process_delivered_events_without_capabilities(self):
        """Test processing without capabilities info."""
        mock_event = MagicMock()
        mock_event.get.return_value = {"requestId": self.request_id, "data": b"test_data"}
        
        result = Mech._process_delivered_events(
            [mock_event], self.request_id, self.contract_address, None
        )
        
        assert "data" in result
        assert result["data"] == b"test_data"
        assert "discovery_info" not in result


class TestIntegration:
    """Integration tests for the complete enhanced ABI discovery system."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.mock_ledger_api = MagicMock()
        self.mock_ledger_api.api.to_checksum_address.return_value = "0x1234567890123456789012345678901234567890"
        self.contract_address = "0x1234567890123456789012345678901234567890"
        self.request_id = 123

    @patch('packages.valory.contracts.mech.contract.concurrent.futures.ThreadPoolExecutor')
    def test_complete_flow_with_timeout(self, mock_executor):
        """Test complete flow including timeout handling."""
        # Mock successful execution
        mock_future = MagicMock()
        mock_future.result.return_value = {"data": b"success"}
        mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future

        result = Mech.get_response(
            self.mock_ledger_api,
            self.contract_address,
            self.request_id,
            timeout=300.0
        )

        assert "data" in result
        assert result["data"] == b"success"

    @patch('packages.valory.contracts.mech.contract.concurrent.futures.ThreadPoolExecutor')
    def test_complete_flow_with_timeout_error(self, mock_executor):
        """Test complete flow with timeout error."""
        # Mock timeout
        mock_future = MagicMock()
        mock_future.result.side_effect = TimeoutError("Timeout")
        mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future

        result = Mech.get_response(
            self.mock_ledger_api,
            self.contract_address,
            self.request_id,
            timeout=5.0
        )

        assert "error" in result
        assert "The RPC didn't respond in 5.0" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])