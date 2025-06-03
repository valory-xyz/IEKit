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

"""This module contains the class to connect to a Mech contract."""

import concurrent.futures
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea.crypto.base import LedgerApi
from aea_ledger_ethereum import EthereumApi
from eth_typing import HexStr
from eth_utils import event_abi_to_log_topic
from web3._utils.events import get_event_data
from web3.types import BlockData, BlockIdentifier, EventData, FilterParams, TxReceipt


PUBLIC_ID = PublicId.from_str("valory/mech:0.1.0")
FIVE_MINUTES = 300.0


partial_abis = [
    [
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "requestId",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "bytes",
                    "name": "data",
                    "type": "bytes",
                },
            ],
            "name": "Deliver",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "sender",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "requestId",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "bytes",
                    "name": "data",
                    "type": "bytes",
                },
            ],
            "name": "Request",
            "type": "event",
        },
    ],
    [
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "sender",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "requestId",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "requestIdWithNonce",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "bytes",
                    "name": "data",
                    "type": "bytes",
                },
            ],
            "name": "Request",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {
                    "indexed": True,
                    "internalType": "address",
                    "name": "sender",
                    "type": "address",
                },
                {
                    "indexed": False,
                    "internalType": "uint256",
                    "name": "requestId",
                    "type": "uint256",
                },
                {
                    "indexed": False,
                    "internalType": "bytes",
                    "name": "data",
                    "type": "bytes",
                },
            ],
            "name": "Deliver",
            "type": "event",
        },
    ],
]


class MechABIDiscoveryEngine:
    """Intelligent ABI discovery with fallback mechanisms."""
    
    @classmethod
    def discover_contract_capabilities(
        cls, 
        ledger_api: LedgerApi, 
        contract_address: str
    ) -> JSONLike:
        """
        Discover contract capabilities using progressive fallback.
        
        Priority Order:
        1. Partial ABI 0 (Legacy - without sender field)  
        2. Partial ABI 1 (Modern - with sender field)
        3. Full ABI (as last resort)
        """
        
        # Try partial ABIs first (more reliable)
        for abi_version, abi in enumerate(partial_abis):
            try:
                contract_instance = ledger_api.api.eth.contract(contract_address, abi=abi)
                event_abi = contract_instance.events.Deliver().abi
                
                # Analyze event structure
                has_sender = any(
                    inp["name"] == "sender" and inp.get("indexed", False) 
                    for inp in event_abi["inputs"]
                )
                
                return {
                    "status": "success",
                    "abi_version": abi_version,
                    "event_abi": event_abi,
                    "has_sender": has_sender,
                    "discovery_method": "partial_abi",
                    "event_structure": cls._analyze_event_structure(event_abi)
                }
            except AttributeError:
                continue
        
        # Fallback to full ABI
        try:
            contract_instance = Mech.get_instance(ledger_api, contract_address)
            event_abi = contract_instance.events.Deliver().abi
            has_sender = any(inp["name"] == "sender" for inp in event_abi["inputs"])
            
            return {
                "status": "success", 
                "abi_version": "full",
                "event_abi": event_abi,
                "has_sender": has_sender,
                "discovery_method": "full_abi",
                "event_structure": cls._analyze_event_structure(event_abi)
            }
        except AttributeError:
            return {
                "status": "error",
                "error": "No compatible Deliver event found in any ABI version",
                "discovery_method": "exhausted"
            }
    
    @classmethod
    def _analyze_event_structure(cls, event_abi: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the structure of an event ABI."""
        inputs = event_abi.get("inputs", [])
        return {
            "input_count": len(inputs),
            "input_names": [inp["name"] for inp in inputs],
            "indexed_inputs": [inp["name"] for inp in inputs if inp.get("indexed", False)],
            "has_sender": any(inp["name"] == "sender" for inp in inputs),
            "has_request_id": any(inp["name"] == "requestId" for inp in inputs),
            "has_data": any(inp["name"] == "data" for inp in inputs)
        }


class MechCapabilityCache:
    """AEA-native persistent caching via SynchronizedData."""
    
    CACHE_TTL = 24 * 3600  # 24 hours
    CACHE_VERSION = "v1.0"
    
    @classmethod
    def get_capabilities(
        cls,
        synchronized_data: Any,
        ledger_api: LedgerApi,
        contract_address: str,
        force_refresh: bool = False
    ) -> JSONLike:
        """Get capabilities with persistent caching."""
        
        cache_key = cls._generate_cache_key(contract_address, ledger_api.api.eth.chain_id)
        
        # Try cache first (unless forced refresh)
        if not force_refresh and synchronized_data:
            cached_data = cls._get_from_cache(synchronized_data, cache_key)
            if cached_data and cls._is_cache_valid(cached_data):
                return cached_data["capabilities"]
        
        # Discover capabilities
        capabilities = MechABIDiscoveryEngine.discover_contract_capabilities(
            ledger_api, contract_address
        )
        
        # Cache successful discoveries
        if capabilities.get("status") == "success" and synchronized_data:
            cls._store_in_cache(synchronized_data, cache_key, capabilities)
        
        return capabilities
    
    @classmethod
    def _generate_cache_key(cls, contract_address: str, chain_id: int) -> str:
        """Generate deterministic cache key."""
        return f"mech_capabilities_{contract_address.lower()}_{chain_id}"
    
    @classmethod
    def _get_from_cache(cls, synchronized_data: Any, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get data from SynchronizedData cache."""
        try:
            if hasattr(synchronized_data, 'db') and hasattr(synchronized_data.db, 'get'):
                cached_str = synchronized_data.db.get(cache_key)
                if cached_str:
                    import json
                    return json.loads(cached_str)
        except (TypeError, ValueError, AttributeError):
            pass
        return None
    
    @classmethod
    def _store_in_cache(cls, synchronized_data: Any, cache_key: str, capabilities: Dict[str, Any]) -> None:
        """Store data in SynchronizedData cache."""
        try:
            if hasattr(synchronized_data, 'db') and hasattr(synchronized_data.db, 'update'):
                import json
                import time
                cache_data = {
                    "capabilities": capabilities,
                    "timestamp": time.time(),
                    "cache_version": cls.CACHE_VERSION
                }
                synchronized_data.db.update({cache_key: json.dumps(cache_data)})
        except (TypeError, AttributeError):
            pass
    
    @classmethod 
    def _is_cache_valid(cls, cached_data: dict) -> bool:
        """Validate cache entry integrity and TTL."""
        try:
            # Check version compatibility
            if cached_data.get("cache_version") != cls.CACHE_VERSION:
                return False
                
            # Check TTL
            import time
            age = time.time() - cached_data.get("timestamp", 0)
            if age > cls.CACHE_TTL:
                return False
                
            # Validate data structure
            required_keys = ["capabilities", "timestamp", "cache_version"]
            return all(key in cached_data for key in required_keys)
        except (TypeError, KeyError):
            return False


class AEAMechResponseIntegration:
    """AEA-native integration with SynchronizedData and message-based errors."""
    
    @classmethod
    def get_response_aea_compatible(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        request_id: int,
        synchronized_data: Any = None,
        from_block: BlockIdentifier = "earliest",
        to_block: BlockIdentifier = "latest",
        timeout: float = FIVE_MINUTES,
        **kwargs: Any
    ) -> JSONLike:
        """
        AEA-compatible response fetching with persistent caching.
        
        Returns structured messages, never raises exceptions.
        """
        
        def get_responses_with_aea_integration() -> JSONLike:
            # Step 1: Get capabilities (cached if available)
            if synchronized_data:
                capabilities = MechCapabilityCache.get_capabilities(
                    synchronized_data, ledger_api, contract_address
                )
            else:
                # Fallback without cache
                capabilities = MechABIDiscoveryEngine.discover_contract_capabilities(
                    ledger_api, contract_address
                )
            
            # Step 2: Handle discovery errors
            if capabilities.get("status") == "error":
                return {
                    "status": "error",
                    "error": f"ABI discovery failed: {capabilities.get('error', 'Unknown discovery error')}",
                    "error_type": "abi_discovery_failed",
                    "contract_address": contract_address
                }
            
            # Step 3: Use existing enhanced logic for response fetching
            contract_address_checksummed = ledger_api.api.to_checksum_address(contract_address)
            ledger_api_casted = cast(EthereumApi, ledger_api)
            
            # Use discovered event ABI for filtering
            event_abi = capabilities["event_abi"]
            event_topic = event_abi_to_log_topic(event_abi)

            filter_params: FilterParams = {
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": contract_address_checksummed,
                "topics": [event_topic],
            }

            w3 = ledger_api_casted.api.eth
            logs = w3.get_logs(filter_params)
            
            # Process logs with enhanced error handling
            delivered = []
            for log in logs:
                try:
                    decoded_log = get_event_data(w3.codec, event_abi, log)
                    log_request_id = decoded_log.get("args", {}).get("requestId", None)
                    if request_id == log_request_id:
                        delivered.append(decoded_log)
                except Exception:
                    # Log decoding error but continue processing other logs
                    continue
            
            return Mech._process_delivered_events(delivered, request_id, contract_address_checksummed, capabilities)
        
        # Execute with timeout (AEA pattern)
        data, err = cls.execute_with_timeout(get_responses_with_aea_integration, timeout=timeout)
        
        if err is not None:
            # Format timeout error message to match expected format
            if "timed out" in err:
                timeout_msg = f"The RPC didn't respond in {timeout}."
            else:
                timeout_msg = err
            return {
                "status": "error",
                "error": timeout_msg,
                "error_type": "timeout",
                "timeout_seconds": timeout
            }
        
        return data
    
    @classmethod
    def execute_with_timeout(cls, func: Callable, timeout: float) -> Tuple[Any, Optional[str]]:
        """Execute function with timeout - AEA compatible."""
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                data = future.result(timeout=timeout)
                return data, None
            except concurrent.futures.TimeoutError:
                return None, f"Operation timed out after {timeout} seconds"
            except Exception as e:
                return None, f"Operation failed: {str(e)}"


class Mech(Contract):
    """The Mech contract."""

    contract_id = PUBLIC_ID

    @staticmethod
    def execute_with_timeout(func: Callable, timeout: float) -> Any:
        """Execute a function with a timeout."""

        # Create a ProcessPoolExecutor with a maximum of 1 worker (process)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # Submit the function to the executor
            future = executor.submit(
                func,
            )

            try:
                # Wait for the result with a 5-minute timeout
                data = future.result(timeout=timeout)
            except TimeoutError:
                # Handle the case where the execution times out
                err = f"The RPC didn't respond in {timeout}."
                return None, err

            # Check if an error occurred
            if isinstance(data, str):
                # Handle the case where the execution failed
                return None, data

            return data, None

    @classmethod
    def get_price(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
        **kwargs: Any
    ) -> JSONLike:
        """Get the price of a request."""
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        contract_instance = cls.get_instance(ledger_api, contract_address)
        price = ledger_api.contract_method_call(contract_instance, "price")
        return dict(price=price)

    @classmethod
    def get_request_data(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        request_data: bytes,
        **kwargs: Any
    ) -> Dict[str, bytes]:
        """Gets the encoded arguments for a request tx, which should only be called via the multisig.

        :param ledger_api: the ledger API object
        :param contract_address: the contract's address
        :param request_data: the request data
        """
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        contract_instance = cls.get_instance(ledger_api, contract_address)
        encoded_data = contract_instance.encodeABI("request", args=(request_data,))
        return {"data": bytes.fromhex(encoded_data[2:])}

    @classmethod
    def _process_event(
        cls,
        ledger_api: LedgerApi,
        contract: Any,
        tx_hash: HexStr,
        expected_logs: int,
        event_name: str,
        *args: Any,
        **kwargs: Any
    ) -> JSONLike:
        """Process the logs of the given event."""
        ledger_api = cast(EthereumApi, ledger_api)
        receipt: TxReceipt = ledger_api.api.eth.get_transaction_receipt(tx_hash)
        event_method = getattr(contract.events, event_name)
        logs: List[EventData] = list(event_method().process_receipt(receipt))

        n_logs = len(logs)
        if n_logs != expected_logs:
            error = f"{expected_logs} {event_name!r} events were expected. tx {tx_hash} emitted {n_logs} instead."
            return {"error": error}

        results = []
        for log in logs:
            event_args = log.get("args", None)
            if event_args is None or any(
                expected_key not in event_args for expected_key in args
            ):
                return {"error": f"The emitted event's ({event_name}) logs for tx {tx_hash} do not match the expected format: {log}"}
            results.append({arg_name: event_args[arg_name] for arg_name in args})

        return dict(results=results)

    @classmethod
    def process_request_event(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        tx_hash: HexStr,
        expected_logs: int = 1,
        **kwargs: Any
    ) -> JSONLike:
        """
        Process the request receipt to get the requestId and the given data from the `Request` event's logs.

        :param ledger_api: the ledger apis.
        :param contract_address: the contract address.
        :param tx_hash: the hash of a request tx to be processed.
        :param expected_logs: the number of logs expected.
        :return: a dictionary with a key named `results`
        which contains a list of dictionaries (as many as the expected logs) containing the request id and the data.
        """
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        res = {}
        for abi in partial_abis:
            contract_instance = ledger_api.api.eth.contract(contract_address, abi=abi)
            res = cls._process_event(
                ledger_api, contract_instance, tx_hash, expected_logs, "Request", "requestId", "data"
            )
            if "error" not in res:
                return res

        return res

    @classmethod
    def process_deliver_event(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        tx_hash: HexStr,
        expected_logs: int = 1,
        **kwargs: Any
    ) -> JSONLike:
        """
        Process the request receipt to get the requestId and the delivered data if the `Deliver` event has been emitted.

        :param ledger_api: the ledger apis.
        :param contract_address: the contract address.
        :param tx_hash: the hash of a request tx to be processed.
        :param expected_logs: the number of logs expected.
        :return: a dictionary with the request id and the data.
        """
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        res = {}
        for abi in partial_abis:
            contract_instance = ledger_api.api.eth.contract(contract_address, abi=abi)
            res = cls._process_event(
                ledger_api, contract_instance, tx_hash, expected_logs, "Deliver", "requestId", "data"
            )
            if "error" not in res:
                return res

        return res
    @classmethod
    def get_block_number(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
        tx_hash: HexStr,
        **kwargs: Any
    ) -> JSONLike:
        """Get the number of the block in which the tx of the given hash was settled."""
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        receipt: TxReceipt = ledger_api.api.eth.get_transaction_receipt(tx_hash)
        block: BlockData = ledger_api.api.eth.get_block(receipt["blockNumber"])
        return dict(number=block["number"])

    @classmethod
    def get_response(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        request_id: int,
        synchronized_data: Any = None,
        from_block: BlockIdentifier = "earliest",
        to_block: BlockIdentifier = "latest",
        timeout: float = FIVE_MINUTES,
        use_enhanced_discovery: bool = True,
        **kwargs: Any
    ) -> JSONLike:
        """
        Enhanced get_response with intelligent ABI discovery and fallback mechanisms.
        
        Args:
            use_enhanced_discovery: Enable enhanced ABI discovery (default: True)
        """
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        ledger_api = cast(EthereumApi, ledger_api)

        def get_responses_enhanced() -> Any:
            """Get responses using enhanced ABI discovery."""
            
            # Step 1: Get capabilities (cached if available)
            if synchronized_data:
                capabilities = MechCapabilityCache.get_capabilities(
                    synchronized_data, ledger_api, contract_address
                )
            else:
                # Fallback without cache
                capabilities = MechABIDiscoveryEngine.discover_contract_capabilities(
                    ledger_api, contract_address
                )
            
            # Handle discovery errors
            if capabilities.get("status") == "error":
                return {
                    "error": f"ABI discovery failed: {capabilities.get('error', 'Unknown error')}",
                    "contract_address": contract_address,
                    "discovery_method": capabilities.get("discovery_method", "unknown")
                }
            
            # Step 2: Use discovered event ABI for filtering
            event_abi = capabilities["event_abi"]
            event_topic = event_abi_to_log_topic(event_abi)

            filter_params: FilterParams = {
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": contract_address,
                "topics": [event_topic],
            }

            w3 = ledger_api.api.eth
            logs = w3.get_logs(filter_params)
            
            # Step 3: Process logs with enhanced error handling
            delivered = []
            for log in logs:
                try:
                    decoded_log = get_event_data(w3.codec, event_abi, log)
                    log_request_id = decoded_log.get("args", {}).get("requestId", None)
                    if request_id == log_request_id:
                        delivered.append(decoded_log)
                except Exception as decode_error:
                    # Log decoding error but continue processing other logs
                    continue
            
            return cls._process_delivered_events(delivered, request_id, contract_address, capabilities)

        def get_responses_legacy() -> Any:
            """Legacy implementation with partial ABI fallback."""
            # Try partial ABIs first
            for abi_version, abi in enumerate(partial_abis):
                try:
                    contract_instance = ledger_api.api.eth.contract(contract_address, abi=abi)
                    event_abi = contract_instance.events.Deliver().abi
                    event_topic = event_abi_to_log_topic(event_abi)

                    filter_params: FilterParams = {
                        "fromBlock": from_block,
                        "toBlock": to_block,
                        "address": contract_address,
                        "topics": [event_topic],
                    }

                    w3 = ledger_api.api.eth
                    logs = w3.get_logs(filter_params)
                    delivered = [
                        get_event_data(w3.codec, event_abi, log) 
                        for log in logs 
                        if request_id == log.get("args", {}).get("requestId", None)
                    ]
                    
                    return cls._process_delivered_events(delivered, request_id, contract_address)
                    
                except AttributeError:
                    continue
            
            # Fallback to full ABI
            try:
                contract_instance = cls.get_instance(ledger_api, contract_address)
                event_abi = contract_instance.events.Deliver().abi
                event_topic = event_abi_to_log_topic(event_abi)

                fallback_filter_params: FilterParams = {
                    "fromBlock": from_block,
                    "toBlock": to_block,
                    "address": contract_instance.address,
                    "topics": [event_topic],
                }

                w3 = ledger_api.api.eth
                logs = w3.get_logs(fallback_filter_params)
                delivered = [
                    get_event_data(w3.codec, event_abi, log) 
                    for log in logs 
                    if request_id == log.get("args", {}).get("requestId", None)
                ]
                
                return cls._process_delivered_events(delivered, request_id, contract_address)
                
            except AttributeError:
                return {"error": "No compatible Deliver event found in contract ABI"}

        # Choose implementation based on feature flag and SynchronizedData availability
        if use_enhanced_discovery and synchronized_data:
            # Use new optimized path with caching
            return AEAMechResponseIntegration.get_response_aea_compatible(
                ledger_api, contract_address, request_id, synchronized_data,
                from_block, to_block, timeout, **kwargs
            )
        elif use_enhanced_discovery:
            # Use optimization without persistent cache
            return AEAMechResponseIntegration.get_response_aea_compatible(
                ledger_api, contract_address, request_id, None,
                from_block, to_block, timeout, **kwargs
            )
        else:
            # Use legacy implementation
            get_responses_func = get_responses_legacy
            data, err = cls.execute_with_timeout(get_responses_func, timeout=timeout)
            if err is not None:
                return {"error": err}
            return data

    @classmethod
    def _process_delivered_events(
        cls,
        delivered: List[EventData],
        request_id: int,
        contract_address: str,
        capabilities: Optional[Dict[str, Any]] = None
    ) -> JSONLike:
        """Process delivered events with enhanced error handling."""
        n_delivered = len(delivered)

        if n_delivered == 0:
            info = f"The mech ({contract_address}) has not delivered a response yet for request with id {request_id}."
            if capabilities:
                info += f" (Discovered using {capabilities.get('discovery_method', 'unknown')} method)"
            return {"info": info}

        if n_delivered != 1:
            error = (
                f"A single response was expected by the mech ({contract_address}) for request with id {request_id}. "
                f"Received {n_delivered} responses: {delivered}."
            )
            if capabilities:
                error += f" (ABI version: {capabilities.get('abi_version', 'unknown')})"
            return {"error": error}

        delivered_event = delivered.pop()
        deliver_args = delivered_event.get("args", None)
        if deliver_args is None or "data" not in deliver_args:
            error = f"The mech's response does not match the expected format: {delivered_event}"
            if capabilities:
                error += f" (Event structure: {capabilities.get('event_structure', {})})"
            return {"error": error}

        response = {"data": deliver_args["data"]}
        if capabilities:
            response["discovery_info"] = {
                "abi_version": capabilities.get("abi_version"),
                "discovery_method": capabilities.get("discovery_method"),
                "has_sender": capabilities.get("has_sender", False)
            }
        
        return response

    @classmethod
    def get_mech_id(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
        **kwargs: Any
    ) -> JSONLike:
        """Get the price of a request."""
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        contract_instance = cls.get_instance(ledger_api, contract_address)
        mech_id = ledger_api.contract_method_call(contract_instance, "tokenId")
        return dict(id=mech_id)

    @classmethod
    def get_requests_count(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
        address: str,
        **kwargs: Any
    ) -> JSONLike:
        """Get the requests count."""
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        address = ledger_api.api.to_checksum_address(address)
        contract_instance = cls.get_instance(ledger_api, contract_address)
        requests_count = contract_instance.functions.getRequestsCount(address).call()
        return {"requests_count": requests_count}

    @classmethod
    def get_pending_requests(cls, ledger_api: EthereumApi, contract_address: str, sender_address: str, **kwargs: Any) -> JSONLike:
        """Get the pending requests."""
        contract_address = ledger_api.api.to_checksum_address(contract_address)
        sender_address = ledger_api.api.to_checksum_address(sender_address)
        contract_instance = cls.get_instance(ledger_api, contract_address)
        pending_requests = contract_instance.functions.mapUndeliveredRequestsCounts(sender_address).call()
        return {"pending_requests": pending_requests}
