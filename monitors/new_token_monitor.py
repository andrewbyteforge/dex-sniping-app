"""
Monitor for detecting new token launches on various DEXs.
Focuses on Uniswap V2/V3 initially with plans to expand.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from web3 import Web3
from web3.contract import Contract

from models.token import TokenInfo, LiquidityInfo, TradingOpportunity, ContractAnalysis, SocialMetrics
from monitors.base_monitor import BaseMonitor
from config.settings import settings

class NewTokenMonitor(BaseMonitor):
    """
    Monitor for detecting newly launched tokens on DEXs.
    Currently supports Uniswap V2 with plans for V3 and other DEXs.
    """
    
    def __init__(self, check_interval: float = 5.0):
        """Initialize the new token monitor."""
        super().__init__("NewToken", check_interval)
        
        self.w3: Optional[Web3] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_block_checked = 0
        self.processed_pairs: set = set()
        
        # Contract instances
        self.uniswap_factory: Optional[Contract] = None
        
        # ABI for Uniswap V2 Factory (simplified)
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
        
        # ABI for ERC20 tokens (basic)
        self.erc20_abi = [
            {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
        ]
        
    async def _initialize(self) -> None:
        """Initialize Web3 connection and contracts."""
        try:
            # Initialize Web3
            self.w3 = Web3(Web3.HTTPProvider(settings.networks.ethereum_rpc_url))
            
            if not self.w3.is_connected():
                raise ConnectionError("Failed to connect to Ethereum node")
                
            self.logger.info("Connected to Ethereum node")
            
            # Initialize Uniswap Factory contract
            self.uniswap_factory = self.w3.eth.contract(
                address=settings.contracts.uniswap_v2_factory,
                abi=self.factory_abi
            )
            
            # Initialize HTTP session
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Get current block number
            self.last_block_checked = self.w3.eth.block_number - 10  # Start 10 blocks back
            self.logger.info(f"Starting from block {self.last_block_checked}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            raise
            
    async def _check(self) -> None:
        """Check for new token pairs created."""
        try:
            current_block = self.w3.eth.block_number
            
            if current_block <= self.last_block_checked:
                return
                
            self.logger.debug(f"Checking blocks {self.last_block_checked + 1} to {current_block}")
            
            # Get PairCreated events from recent blocks
            events = await self._get_pair_created_events(
                self.last_block_checked + 1, 
                current_block
            )
            
            for event in events:
                await self._process_pair_created_event(event)
                
            self.last_block_checked = current_block
            
        except Exception as e:
            self.logger.error(f"Error during check: {e}")
            raise
            
    async def _get_pair_created_events(self, from_block: int, to_block: int) -> List[Any]:
        """Get PairCreated events using the most reliable method with proper hex formatting."""
        try:
            # Convert block numbers to proper hex format
            from_block_hex = hex(from_block)
            to_block_hex = hex(to_block)
            
            # Ensure proper 0x prefix
            if not from_block_hex.startswith('0x'):
                from_block_hex = '0x' + from_block_hex.lstrip('0x')
            if not to_block_hex.startswith('0x'):
                to_block_hex = '0x' + to_block_hex.lstrip('0x')
            
            # Use getLogs directly with proper hex formatting
            event_signature = self.w3.keccak(text="PairCreated(address,address,address,uint256)").hex()
            
            # Ensure event signature has 0x prefix
            if not event_signature.startswith('0x'):
                event_signature = '0x' + event_signature
            
            filter_params = {
                'fromBlock': from_block_hex,
                'toBlock': to_block_hex,
                'address': settings.contracts.uniswap_v2_factory,
                'topics': [event_signature]
            }
            
            self.logger.debug(f"Getting logs with params: fromBlock={from_block_hex}, toBlock={to_block_hex}")
            
            logs = self.w3.eth.get_logs(filter_params)
            
            if logs:
                self.logger.info(f"Found {len(logs)} new pairs in blocks {from_block}-{to_block}")
                
                # Parse logs manually
                parsed_events = []
                for log in logs:
                    try:
                        if len(log['topics']) >= 3:
                            # Extract addresses from topics
                            token0_raw = '0x' + log['topics'][1].hex()[-40:]
                            token1_raw = '0x' + log['topics'][2].hex()[-40:]
                            
                            # Extract pair address from data
                            data_hex = log['data'].hex()
                            if not data_hex.startswith('0x'):
                                data_hex = '0x' + data_hex
                            pair_address_raw = '0x' + data_hex[26:66]  # Adjusted offset
                            
                            # Convert to checksum addresses
                            token0 = self.w3.to_checksum_address(token0_raw)
                            token1 = self.w3.to_checksum_address(token1_raw)
                            pair_address = self.w3.to_checksum_address(pair_address_raw)
                            
                            # Create event structure
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
                        self.logger.warning(f"Error parsing log: {parse_error}")
                        continue
                
                self.logger.info(f"Successfully parsed {len(parsed_events)} events")
                return parsed_events
                
        except Exception as e:
            self.logger.error(f"Error getting events from blocks {from_block}-{to_block}: {e}")
            
            # If hex formatting error, try with Web3's native formatting
            if "hex string without 0x prefix" in str(e):
                try:
                    self.logger.info("Retrying with Web3 native hex formatting...")
                    
                    # Use Web3's built-in hex conversion
                    logs = self.w3.eth.get_logs({
                        'fromBlock': from_block,  # Let Web3 handle conversion
                        'toBlock': to_block,      # Let Web3 handle conversion
                        'address': settings.contracts.uniswap_v2_factory,
                        'topics': [self.w3.keccak(text="PairCreated(address,address,address,uint256)")]
                    })
                    
                    # Parse the logs the same way as above
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
                                
                        except Exception as parse_error:
                            self.logger.warning(f"Error parsing retry log: {parse_error}")
                            continue
                    
                    return parsed_events
                    
                except Exception as retry_error:
                    self.logger.error(f"Retry also failed: {retry_error}")
            
        return []







    async def _process_pair_created_event(self, event: Any) -> None:
        """Process a single PairCreated event."""
        try:
            # Extract event data
            pair_address = event['args']['pair']
            token0_address = event['args']['token0']
            token1_address = event['args']['token1']
            block_number = event['blockNumber']
            
            # Skip if already processed
            if pair_address in self.processed_pairs:
                return
                
            self.processed_pairs.add(pair_address)
            
            self.logger.info(f"Processing new pair: {pair_address}")
            self.logger.debug(f"Token0: {token0_address}, Token1: {token1_address}")
            
            # FOR TESTING: Show ALL pairs, not just WETH pairs
            # Determine which token is the new one (not WETH/USDC/USDT)
            common_tokens = [
                "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
                "0xA0b86a33E6441019fad5B4A55745e22A85e5Db69",  # USDC
                "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
            ]
            
            new_token_address = None
            if token0_address not in common_tokens:
                new_token_address = token0_address
            elif token1_address not in common_tokens:
                new_token_address = token1_address
            else:
                # Both tokens are common tokens, still process for testing
                new_token_address = token0_address  # Just pick one for testing
                
            # Get token information
            token_info = await self._get_token_info(new_token_address)
            if not token_info:
                return
                
            # Get liquidity information
            liquidity_info = await self._get_liquidity_info(
                pair_address, token0_address, token1_address, block_number
            )
            if not liquidity_info:
                return
                
            # Create trading opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=ContractAnalysis(),  # Will be filled by analyzer
                social_metrics=SocialMetrics()  # Will be filled by social analyzer
            )
            
            # Notify callbacks
            await self._notify_callbacks(opportunity)
            
        except Exception as e:
            self.logger.error(f"Error processing pair event: {e}")
            
    async def _get_token_info(self, token_address: str) -> Optional[TokenInfo]:
        """Get basic information about a token."""
        try:
            # Create token contract
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self.erc20_abi
            )
            
            # Get token details with timeouts
            try:
                name = token_contract.functions.name().call()
            except Exception:
                name = f"Token_{token_address[:8]}"
                
            try:
                symbol = token_contract.functions.symbol().call()
            except Exception:
                symbol = f"TKN_{token_address[:6]}"
                
            try:
                decimals = token_contract.functions.decimals().call()
            except Exception:
                decimals = 18
                
            try:
                total_supply = token_contract.functions.totalSupply().call()
            except Exception:
                total_supply = 0
                
            token_info = TokenInfo(
                address=token_address,
                symbol=symbol,
                name=name,
                decimals=decimals,
                total_supply=total_supply
            )
            
            self.logger.debug(f"Token info: {symbol} ({name}) - {token_address}")
            return token_info
            
        except Exception as e:
            self.logger.error(f"Error getting token info for {token_address}: {e}")
            return None
            
    async def _get_liquidity_info(
        self, 
        pair_address: str, 
        token0: str, 
        token1: str, 
        block_number: int
    ) -> Optional[LiquidityInfo]:
        """Get liquidity information for a pair."""
        try:
            # For now, create basic liquidity info
            # In a real implementation, you would call the pair contract
            # to get reserves and calculate USD value
            
            liquidity_info = LiquidityInfo(
                pair_address=pair_address,
                dex_name="Uniswap V2",
                token0=token0,
                token1=token1,
                reserve0=0.0,  # Would get from pair contract
                reserve1=0.0,  # Would get from pair contract
                liquidity_usd=0.0,  # Would calculate from reserves
                created_at=datetime.now(),
                block_number=block_number
            )
            
            return liquidity_info
            
        except Exception as e:
            self.logger.error(f"Error getting liquidity info for {pair_address}: {e}")
            return None
            
    async def _cleanup(self) -> None:
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None
            
        self.logger.info("Cleanup completed")