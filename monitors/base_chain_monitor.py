"""
Base Chain monitor for detecting new token launches.
Similar to Ethereum but optimized for Base chain characteristics.
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from web3 import Web3
from web3.contract import Contract

from models.token import TokenInfo, LiquidityInfo, TradingOpportunity, ContractAnalysis, SocialMetrics
from monitors.base_monitor import BaseMonitor
from config.chains import multichain_settings, ChainType

class BaseChainMonitor(BaseMonitor):
    """
    Monitor for detecting newly launched tokens on Base chain.
    Uses same logic as Ethereum but with Base-specific configuration.
    """
    
    def __init__(self, check_interval: float = 2.0):  # Faster blocks on Base
        """Initialize the Base chain monitor."""
        super().__init__("BaseChain", check_interval)
        
        self.chain_config = multichain_settings.get_chain_config(ChainType.BASE)
        self.w3: Optional[Web3] = None
        self.last_block_checked = 0
        self.processed_pairs: set = set()
        self.dex_factory: Optional[Contract] = None
        
        # Same ABI as Uniswap V2 (most DEXs use this standard)
        self.factory_abi = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "token0", "type": "address"},
                    {"indexed": True, "name": "token1", "type": "address"},
                    {"indexed": False, "name": "pair", "type": "address"},
                    {"indexed": False, "name": "", "type": "uint256"}
                ],
                "name": "PairCreated",
                "type": "event"
            }
        ]
        
        self.erc20_abi = [
            {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
        ]
        
    async def _initialize(self) -> None:
        """Initialize Web3 connection for Base chain."""
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.chain_config.rpc_url))
            
            if not self.w3.is_connected():
                raise ConnectionError("Failed to connect to Base chain")
                
            # Verify we're on the right chain
            chain_id = self.w3.eth.chain_id
            if chain_id != self.chain_config.chain_id:
                raise ValueError(f"Expected chain {self.chain_config.chain_id}, got {chain_id}")
                
            self.logger.info(f"Connected to {self.chain_config.name} (Chain ID: {chain_id})")
            
            # Initialize DEX factory contract
            self.dex_factory = self.w3.eth.contract(
                address=self.chain_config.dex_factory,
                abi=self.factory_abi
            )
            
            # Start from recent block
            self.last_block_checked = self.w3.eth.block_number - 5
            self.logger.info(f"Starting from block {self.last_block_checked}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Base chain: {e}")
            raise
            
    async def _check(self) -> None:
        """Check for new token pairs on Base chain."""
        try:
            current_block = self.w3.eth.block_number
            
            if current_block <= self.last_block_checked:
                return
                
            self.logger.debug(f"Checking Base blocks {self.last_block_checked + 1} to {current_block}")
            
            # Get PairCreated events
            events = await self._get_pair_created_events(
                self.last_block_checked + 1, 
                current_block
            )
            
            for event in events:
                await self._process_pair_created_event(event)
                
            self.last_block_checked = current_block
            
        except Exception as e:
            self.logger.error(f"Error during Base chain check: {e}")
            raise
            
    async def _get_pair_created_events(self, from_block: int, to_block: int) -> List[Any]:
        """Get PairCreated events from Base chain with proper hex formatting."""
        try:
            # Create proper event signature
            event_signature_bytes = self.w3.keccak(text="PairCreated(address,address,address,uint256)")
            event_signature = event_signature_bytes.hex()
            
            # Ensure proper 0x prefix for event signature
            if not event_signature.startswith('0x'):
                event_signature = '0x' + event_signature
            
            # Convert block numbers to proper hex format
            from_block_hex = hex(from_block) if isinstance(from_block, int) else from_block
            to_block_hex = hex(to_block) if isinstance(to_block, int) else to_block
            
            # Ensure proper 0x prefix for block numbers
            if not from_block_hex.startswith('0x'):
                from_block_hex = '0x' + from_block_hex.lstrip('0x')
            if not to_block_hex.startswith('0x'):
                to_block_hex = '0x' + to_block_hex.lstrip('0x')
                
            self.logger.debug(f"Base chain query: blocks {from_block_hex} to {to_block_hex}")
            
            # Try the request with carefully formatted parameters
            filter_params = {
                'fromBlock': from_block_hex,
                'toBlock': to_block_hex,
                'address': self.chain_config.dex_factory,
                'topics': [event_signature]
            }
            
            logs = self.w3.eth.get_logs(filter_params)
            
            if logs:
                self.logger.info(f"Found {len(logs)} new Base pairs in blocks {from_block}-{to_block}")
                
                # Parse logs manually
                parsed_events = []
                for log in logs:
                    try:
                        if len(log['topics']) >= 3:
                            # Extract and convert addresses to checksum format
                            token0_raw = '0x' + log['topics'][1].hex()[-40:]
                            token1_raw = '0x' + log['topics'][2].hex()[-40:]
                            
                            data_hex = log['data'].hex()
                            if not data_hex.startswith('0x'):
                                data_hex = '0x' + data_hex
                            pair_address_raw = '0x' + data_hex[26:66]  # Adjusted offset
                            
                            token0 = self.w3.to_checksum_address(token0_raw)
                            token1 = self.w3.to_checksum_address(token1_raw)
                            pair_address = self.w3.to_checksum_address(pair_address_raw)
                            
                            parsed_event = {
                                'args': {
                                    'token0': token0,
                                    'token1': token1,
                                    'pair': pair_address
                                },
                                'blockNumber': log['blockNumber']
                            }
                            parsed_events.append(parsed_event)
                            
                    except Exception as parse_error:
                        self.logger.warning(f"Error parsing Base log: {parse_error}")
                        continue
                
                self.logger.info(f"Successfully parsed {len(parsed_events)} Base events")
                return parsed_events
                
        except Exception as e:
            self.logger.error(f"Error getting Base events from blocks {from_block}-{to_block}: {e}")
            
            # Fallback: Try with Web3's native integer formatting
            if "hex string without 0x prefix" in str(e):
                try:
                    self.logger.info("Trying Base fallback with native Web3 formatting...")
                    
                    logs = self.w3.eth.get_logs({
                        'fromBlock': from_block,  # Let Web3 handle conversion
                        'toBlock': to_block,      # Let Web3 handle conversion
                        'address': self.chain_config.dex_factory,
                        'topics': [self.w3.keccak(text="PairCreated(address,address,address,uint256)")]
                    })
                    
                    # Parse the same way as above
                    parsed_events = []
                    for log in logs:
                        try:
                            if len(log['topics']) >= 3:
                                token0_raw = '0x' + log['topics'][1].hex()[-40:]
                                token1_raw = '0x' + log['topics'][2].hex()[-40:]
                                data_hex = log['data'].hex()
                                if not data_hex.startswith('0x'):
                                    data_hex = '0x' + data_hex
                                pair_address_raw = '0x' + data_hex[26:66]
                                
                                token0 = self.w3.to_checksum_address(token0_raw)
                                token1 = self.w3.to_checksum_address(token1_raw)
                                pair_address = self.w3.to_checksum_address(pair_address_raw)
                                
                                parsed_event = {
                                    'args': {
                                        'token0': token0,
                                        'token1': token1,
                                        'pair': pair_address
                                    },
                                    'blockNumber': log['blockNumber']
                                }
                                parsed_events.append(parsed_event)
                                
                        except Exception:
                            continue
                    
                    return parsed_events
                    
                except Exception as fallback_error:
                    self.logger.error(f"Base fallback also failed: {fallback_error}")
                    
                    # Final fallback: try alternative Base RPC endpoints
                    return await self._try_alternative_base_rpc(from_block, to_block)
            
        return []











    async def _try_alternative_base_rpc(self, from_block: int, to_block: int) -> List[Any]:
        """Try alternative Base RPC endpoints as fallback."""
        alternative_rpcs = [
            "https://base.blockpi.network/v1/rpc/public",
            "https://base-rpc.publicnode.com",
            "https://base.meowrpc.com",
        ]
        
        for rpc_url in alternative_rpcs:
            try:
                self.logger.debug(f"Trying Base RPC: {rpc_url}")
                
                # Create temporary Web3 instance with alternative RPC
                temp_w3 = Web3(Web3.HTTPProvider(rpc_url))
                
                if not temp_w3.is_connected():
                    continue
                    
                # Simple integer-based query for alternative RPCs
                logs = temp_w3.eth.get_logs({
                    'fromBlock': from_block,
                    'toBlock': to_block,
                    'address': self.chain_config.dex_factory
                })
                
                # Filter for PairCreated events manually
                event_signature = self.w3.keccak(text="PairCreated(address,address,address,uint256)").hex()
                pair_logs = [log for log in logs if log['topics'] and log['topics'][0].hex() == event_signature]
                
                if pair_logs:
                    self.logger.info(f"Found {len(pair_logs)} Base pairs using alternative RPC")
                    
                    # Update main connection to working RPC
                    self.w3 = temp_w3
                    self.chain_config.rpc_url = rpc_url
                    
                    # Parse events (same logic as above)
                    parsed_events = []
                    for log in pair_logs:
                        try:
                            if len(log['topics']) >= 3:
                                token0_raw = '0x' + log['topics'][1].hex()[-40:]
                                token1_raw = '0x' + log['topics'][2].hex()[-40:]
                                data_hex = log['data'].hex()
                                pair_address_raw = '0x' + data_hex[24:64]
                                
                                token0 = self.w3.to_checksum_address(token0_raw)
                                token1 = self.w3.to_checksum_address(token1_raw)
                                pair_address = self.w3.to_checksum_address(pair_address_raw)
                                
                                parsed_event = {
                                    'args': {'token0': token0, 'token1': token1, 'pair': pair_address},
                                    'blockNumber': log['blockNumber']
                                }
                                parsed_events.append(parsed_event)
                        except Exception:
                            continue
                    
                    return parsed_events
                    
            except Exception as rpc_error:
                self.logger.debug(f"Alternative RPC {rpc_url} failed: {rpc_error}")
                continue
                
        return []
        
    async def _process_pair_created_event(self, event: Any) -> None:
        """Process a Base chain pair creation event."""
        try:
            pair_address = event['args']['pair']
            token0_address = event['args']['token0']
            token1_address = event['args']['token1']
            block_number = event['blockNumber']
            
            if pair_address in self.processed_pairs:
                return
                
            self.processed_pairs.add(pair_address)
            
            self.logger.info(f"Processing new Base pair: {pair_address}")
            self.logger.debug(f"Base Token0: {token0_address}, Token1: {token1_address}")
            
            # Identify new token (exclude WETH and stablecoins)
            excluded_tokens = [self.chain_config.wrapped_native] + self.chain_config.stable_tokens
            
            new_token_address = None
            if token0_address not in excluded_tokens:
                new_token_address = token0_address
            elif token1_address not in excluded_tokens:
                new_token_address = token1_address
            else:
                new_token_address = token0_address  # Process anyway for testing
                
            # Get token information
            token_info = await self._get_token_info(new_token_address)
            if not token_info:
                return
                
            # Create liquidity info
            liquidity_info = LiquidityInfo(
                pair_address=pair_address,
                dex_name="BaseSwap",
                token0=token0_address,
                token1=token1_address,
                reserve0=0.0,
                reserve1=0.0,
                liquidity_usd=0.0,
                created_at=datetime.now(),
                block_number=block_number
            )
            
            # Create opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=ContractAnalysis(),
                social_metrics=SocialMetrics()
            )
            
            # Add chain identifier to metadata
            opportunity.metadata['chain'] = self.chain_config.name
            opportunity.metadata['chain_id'] = self.chain_config.chain_id
            
            await self._notify_callbacks(opportunity)
            
        except Exception as e:
            self.logger.error(f"Error processing Base pair event: {e}")
            
    async def _get_token_info(self, token_address: str) -> Optional[TokenInfo]:
        """Get token information from Base chain."""
        try:
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self.erc20_abi
            )
            
            # Get token details with fallbacks
            try:
                name = token_contract.functions.name().call()
            except Exception:
                name = f"BaseToken_{token_address[:8]}"
                
            try:
                symbol = token_contract.functions.symbol().call()
            except Exception:
                symbol = f"BASE_{token_address[:6]}"
                
            try:
                decimals = token_contract.functions.decimals().call()
            except Exception:
                decimals = 18
                
            try:
                total_supply = token_contract.functions.totalSupply().call()
            except Exception:
                total_supply = 0
                
            return TokenInfo(
                address=token_address,
                symbol=symbol,
                name=name,
                decimals=decimals,
                total_supply=total_supply
            )
            
        except Exception as e:
            self.logger.error(f"Error getting Base token info for {token_address}: {e}")
            return None
            
    async def _cleanup(self) -> None:
        """Cleanup Base chain resources."""
        self.logger.info("Base chain monitor cleanup completed")


    # Additional utility function for hex formatting
    def ensure_hex_prefix(value) -> str:
        """Ensure a value has proper 0x hex prefix."""
        if isinstance(value, int):
            hex_val = hex(value)
        else:
            hex_val = str(value)
        
        if not hex_val.startswith('0x'):
            hex_val = '0x' + hex_val.lstrip('0x')
        
        return hex_val


    # Alternative approach using Web3's internal utilities
    def format_block_identifier(block_number):
        """Format block number for RPC calls using Web3's internal methods."""
        from web3._utils.blocks import select_method_for_block_identifier
        from web3.types import BlockIdentifier
        
        if isinstance(block_number, int):
            return hex(block_number)
        return block_number