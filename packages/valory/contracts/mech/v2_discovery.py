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

"""V2 Mech Discovery Utility for Marketplace Contracts."""

from typing import Any, Dict, List, Optional, cast
from aea.common import JSONLike
from aea.crypto.base import LedgerApi
from aea_ledger_ethereum import EthereumApi
from web3.types import BlockIdentifier


# Known V2 Marketplace Contract Addresses
V2_MARKETPLACE_ADDRESSES = {
    100: "0x...",  # Gnosis Chain - Update with actual address
    1: "0x...",    # Ethereum Mainnet - Update with actual address
}

# V2 Marketplace ABI for mech discovery
V2_MARKETPLACE_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "mech", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "owner", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "price", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "metadataURI", "type": "string"}
        ],
        "name": "MechRegistered",
        "type": "event"
    },
    {
        "inputs": [{"internalType": "address", "name": "mech", "type": "address"}],
        "name": "getMechInfo",
        "outputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "uint256", "name": "price", "type": "uint256"},
            {"internalType": "string", "name": "metadataURI", "type": "string"},
            {"internalType": "bool", "name": "isActive", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getAllMechs",
        "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "offset", "type": "uint256"},
            {"internalType": "uint256", "name": "limit", "type": "uint256"}
        ],
        "name": "getMechsPaginated",
        "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]


class V2MechDiscovery:
    """Utility class for discovering V2 mechs through marketplace contracts."""
    
    @classmethod
    def get_marketplace_address(cls, chain_id: int) -> Optional[str]:
        """Get V2 marketplace address for given chain ID."""
        return V2_MARKETPLACE_ADDRESSES.get(chain_id)
    
    @classmethod
    def discover_v2_mechs(
        cls,
        ledger_api: LedgerApi,
        chain_id: Optional[int] = None,
        marketplace_address: Optional[str] = None,
        from_block: BlockIdentifier = "earliest",
        to_block: BlockIdentifier = "latest"
    ) -> JSONLike:
        """
        Discover all V2 mechs available through marketplace.
        
        Args:
            ledger_api: The ledger API instance
            chain_id: Chain ID to use for marketplace lookup
            marketplace_address: Direct marketplace address (overrides chain_id lookup)
            from_block: Starting block for event scanning
            to_block: Ending block for event scanning
            
        Returns:
            JSONLike: Dictionary containing discovered mechs and their info
        """
        ledger_api = cast(EthereumApi, ledger_api)
        
        # Determine marketplace address
        if marketplace_address:
            marketplace_addr = ledger_api.api.to_checksum_address(marketplace_address)
        else:
            if chain_id is None:
                chain_id = ledger_api.api.eth.chain_id
            marketplace_addr = cls.get_marketplace_address(chain_id)
            if not marketplace_addr:
                return {
                    "status": "error",
                    "error": f"No V2 marketplace address found for chain ID {chain_id}",
                    "chain_id": chain_id
                }
        
        try:
            # Create contract instance
            contract = ledger_api.api.eth.contract(
                address=marketplace_addr,
                abi=V2_MARKETPLACE_ABI
            )
            
            # Method 1: Try to get all mechs directly (if supported)
            mechs_list = cls._get_mechs_direct(contract)
            
            # Method 2: If direct method fails, scan events
            if not mechs_list:
                mechs_list = cls._get_mechs_from_events(
                    ledger_api, contract, from_block, to_block
                )
            
            # Get detailed info for each mech
            mechs_info = []
            for mech_address in mechs_list:
                mech_info = cls._get_mech_detailed_info(contract, mech_address)
                if mech_info:
                    mechs_info.append(mech_info)
            
            return {
                "status": "success",
                "marketplace_address": marketplace_addr,
                "chain_id": chain_id or ledger_api.api.eth.chain_id,
                "total_mechs": len(mechs_info),
                "mechs": mechs_info,
                "discovery_method": "marketplace_contract"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to discover V2 mechs: {str(e)}",
                "marketplace_address": marketplace_addr,
                "chain_id": chain_id
            }
    
    @classmethod
    def _get_mechs_direct(cls, contract: Any) -> List[str]:
        """Try to get mechs using direct contract call."""
        try:
            # Try getAllMechs first
            mechs = contract.functions.getAllMechs().call()
            return [mech for mech in mechs if mech != "0x0000000000000000000000000000000000000000"]
        except Exception:
            # Try paginated approach
            try:
                mechs = []
                offset = 0
                limit = 100
                
                while True:
                    batch = contract.functions.getMechsPaginated(offset, limit).call()
                    if not batch:
                        break
                    mechs.extend([mech for mech in batch if mech != "0x0000000000000000000000000000000000000000"])
                    if len(batch) < limit:
                        break
                    offset += limit
                
                return mechs
            except Exception:
                return []
    
    @classmethod
    def _get_mechs_from_events(
        cls,
        ledger_api: EthereumApi,
        contract: Any,
        from_block: BlockIdentifier,
        to_block: BlockIdentifier
    ) -> List[str]:
        """Get mechs by scanning MechRegistered events."""
        try:
            # Get MechRegistered events
            event_filter = contract.events.MechRegistered.create_filter(
                fromBlock=from_block,
                toBlock=to_block
            )
            
            mechs = set()
            for event in event_filter.get_all_entries():
                mech_address = event['args']['mech']
                mechs.add(mech_address)
            
            return list(mechs)
        except Exception:
            return []
    
    @classmethod
    def _get_mech_detailed_info(cls, contract: Any, mech_address: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific mech."""
        try:
            # Call getMechInfo
            owner, price, metadata_uri, is_active = contract.functions.getMechInfo(mech_address).call()
            
            return {
                "address": mech_address,
                "owner": owner,
                "price": price,
                "metadata_uri": metadata_uri,
                "is_active": is_active,
                "price_eth": price / 10**18 if price > 0 else 0
            }
        except Exception:
            # Return basic info if detailed call fails
            return {
                "address": mech_address,
                "owner": None,
                "price": None,
                "metadata_uri": None,
                "is_active": None,
                "error": "Could not fetch detailed info"
            }
    
    @classmethod
    def get_mech_metadata(
        cls,
        ledger_api: LedgerApi,
        mech_address: str,
        marketplace_address: Optional[str] = None,
        chain_id: Optional[int] = None
    ) -> JSONLike:
        """
        Get metadata for a specific mech address.
        
        Args:
            ledger_api: The ledger API instance
            mech_address: Address of the mech to query
            marketplace_address: Marketplace contract address
            chain_id: Chain ID for marketplace lookup
            
        Returns:
            JSONLike: Mech metadata and information
        """
        ledger_api = cast(EthereumApi, ledger_api)
        mech_address = ledger_api.api.to_checksum_address(mech_address)
        
        # Determine marketplace address
        if marketplace_address:
            marketplace_addr = ledger_api.api.to_checksum_address(marketplace_address)
        else:
            if chain_id is None:
                chain_id = ledger_api.api.eth.chain_id
            marketplace_addr = cls.get_marketplace_address(chain_id)
            if not marketplace_addr:
                return {
                    "status": "error",
                    "error": f"No V2 marketplace address found for chain ID {chain_id}",
                    "mech_address": mech_address
                }
        
        try:
            # Create contract instance
            contract = ledger_api.api.eth.contract(
                address=marketplace_addr,
                abi=V2_MARKETPLACE_ABI
            )
            
            # Get mech info
            mech_info = cls._get_mech_detailed_info(contract, mech_address)
            if not mech_info:
                return {
                    "status": "error",
                    "error": "Could not retrieve mech information",
                    "mech_address": mech_address
                }
            
            return {
                "status": "success",
                "mech_address": mech_address,
                "marketplace_address": marketplace_addr,
                "chain_id": chain_id or ledger_api.api.eth.chain_id,
                "mech_info": mech_info
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to get mech metadata: {str(e)}",
                "mech_address": mech_address,
                "marketplace_address": marketplace_addr
            }
    
    @classmethod
    def filter_active_mechs(cls, mechs_discovery_result: JSONLike) -> JSONLike:
        """Filter discovery result to only include active mechs."""
        if mechs_discovery_result.get("status") != "success":
            return mechs_discovery_result
        
        mechs = mechs_discovery_result.get("mechs", [])
        active_mechs = [mech for mech in mechs if mech.get("is_active", False)]
        
        result = mechs_discovery_result.copy()
        result["mechs"] = active_mechs
        result["total_mechs"] = len(active_mechs)
        result["filtered"] = "active_only"
        
        return result
    
    @classmethod
    def sort_mechs_by_price(cls, mechs_discovery_result: JSONLike, ascending: bool = True) -> JSONLike:
        """Sort discovery result by mech price."""
        if mechs_discovery_result.get("status") != "success":
            return mechs_discovery_result
        
        mechs = mechs_discovery_result.get("mechs", [])
        
        # Sort by price, handling None values
        def price_key(mech):
            price = mech.get("price", 0)
            return price if price is not None else float('inf')
        
        sorted_mechs = sorted(mechs, key=price_key, reverse=not ascending)
        
        result = mechs_discovery_result.copy()
        result["mechs"] = sorted_mechs
        result["sorted_by"] = f"price_{'asc' if ascending else 'desc'}"
        
        return result


# Convenience functions for common use cases
def find_cheapest_v2_mech(
    ledger_api: LedgerApi,
    chain_id: Optional[int] = None,
    marketplace_address: Optional[str] = None
) -> JSONLike:
    """Find the cheapest active V2 mech."""
    discovery_result = V2MechDiscovery.discover_v2_mechs(
        ledger_api, chain_id, marketplace_address
    )
    
    if discovery_result.get("status") != "success":
        return discovery_result
    
    # Filter active and sort by price
    active_mechs = V2MechDiscovery.filter_active_mechs(discovery_result)
    sorted_mechs = V2MechDiscovery.sort_mechs_by_price(active_mechs, ascending=True)
    
    mechs = sorted_mechs.get("mechs", [])
    if not mechs:
        return {
            "status": "error",
            "error": "No active mechs found",
            "total_mechs": 0
        }
    
    cheapest = mechs[0]
    return {
        "status": "success",
        "cheapest_mech": cheapest,
        "total_active_mechs": len(mechs)
    }


def get_v2_mech_for_request(
    ledger_api: LedgerApi,
    max_price_wei: int,
    chain_id: Optional[int] = None,
    marketplace_address: Optional[str] = None
) -> JSONLike:
    """Get a suitable V2 mech for a request within price range."""
    discovery_result = V2MechDiscovery.discover_v2_mechs(
        ledger_api, chain_id, marketplace_address
    )
    
    if discovery_result.get("status") != "success":
        return discovery_result
    
    # Filter active mechs within price range
    active_mechs = V2MechDiscovery.filter_active_mechs(discovery_result)
    suitable_mechs = []
    
    for mech in active_mechs.get("mechs", []):
        mech_price = mech.get("price", 0)
        if mech_price is not None and mech_price <= max_price_wei:
            suitable_mechs.append(mech)
    
    if not suitable_mechs:
        return {
            "status": "error",
            "error": f"No active mechs found within price range {max_price_wei} wei",
            "max_price_wei": max_price_wei
        }
    
    # Sort by price and return cheapest suitable mech
    sorted_suitable = sorted(suitable_mechs, key=lambda m: m.get("price", 0))
    
    return {
        "status": "success",
        "selected_mech": sorted_suitable[0],
        "total_suitable_mechs": len(sorted_suitable),
        "max_price_wei": max_price_wei
    }