"""
Monitor for detecting new token launches on various DEXs.
Focuses on Uniswap V2/V3 initially with plans to expand.

File: monitors/new_token_monitor.py
Class: NewTokenMonitor
Method: Adding public initialize() method
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from web3 import Web3
from web3.contract import Contract
from decimal import Decimal

from models.token import TokenInfo, LiquidityInfo, TradingOpportunity, ContractAnalysis, SocialMetrics
from monitors.base_monitor import BaseMonitor
from config.settings import settings
from utils.logger import logger_manager


class NewTokenMonitor(BaseMonitor):
    """
    Monitor for detecting newly launched tokens on DEXs.
    Currently supports Uniswap V2 with plans for V3 and other DEXs.
    """
    
    def __init__(
        self, 
        check_interval: float = 5.0,
        chain: str = "ethereum",
        rpc_url: Optional[str] = None,
        analyzer: Optional[Any] = None,
        scorer: Optional[Any] = None,
        auto_trading: bool = False
    ) -> None:
        """
        Initialize the new token monitor.
        
        Args:
            check_interval: Seconds between monitoring checks
            chain: Blockchain to monitor ('ethereum', 'base', etc.)
            rpc_url: RPC endpoint URL
            analyzer: Contract analyzer instance
            scorer: Trading scorer instance
            auto_trading: Enable automatic trading
        """
        super().__init__("NewToken", check_interval)
        
        self.chain = chain
        self.rpc_url = rpc_url or settings.networks.ethereum_rpc_url
        self.analyzer = analyzer
        self.scorer = scorer
        self.auto_trading = auto_trading
        
        # Web3 and session management
        self.w3: Optional[Web3] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_block_checked = 0
        self.processed_pairs: set = set()
        
        # Contract instances
        self.uniswap_factory: Optional[Contract] = None
        
        # Statistics tracking
        self.stats = {
            "pairs_processed": 0,
            "opportunities_found": 0,
            "errors_count": 0,
            "last_error": None,
            "uptime_start": datetime.now()
        }
        
        # Uniswap V2 Factory address (Ethereum mainnet)
        self.factory_addresses = {
            "ethereum": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
            "base": "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6"  # BaseSwap factory
        }
        
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
            {
                "constant": True, 
                "inputs": [], 
                "name": "name", 
                "outputs": [{"name": "", "type": "string"}], 
                "type": "function"
            },
            {
                "constant": True, 
                "inputs": [], 
                "name": "symbol", 
                "outputs": [{"name": "", "type": "string"}], 
                "type": "function"
            },
            {
                "constant": True, 
                "inputs": [], 
                "name": "decimals", 
                "outputs": [{"name": "", "type": "uint8"}], 
                "type": "function"
            },
            {
                "constant": True, 
                "inputs": [], 
                "name": "totalSupply", 
                "outputs": [{"name": "", "type": "uint256"}], 
                "type": "function"
            }
        ]

    async def initialize(self) -> bool:
        """
        Public initialize method called by production systems.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            self.logger.info(f"Initializing {self.chain} NewTokenMonitor...")
            
            # Call the private initialization method
            await self._initialize()
            
            # Test the connection
            if self.w3 and self.w3.is_connected():
                latest_block = self.w3.eth.block_number
                self.last_block_checked = latest_block - 5  # Start 5 blocks back
                
                self.logger.info(f"✅ {self.chain} NewTokenMonitor initialized successfully")
                self.logger.info(f"   Latest block: {latest_block}")
                self.logger.info(f"   Starting from block: {self.last_block_checked}")
                self.logger.info(f"   Factory address: {self.factory_addresses.get(self.chain)}")
                
                return True
            else:
                self.logger.error(f"❌ Web3 connection failed for {self.chain}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize {self.chain} NewTokenMonitor: {e}")
            self.stats["errors_count"] += 1
            self.stats["last_error"] = str(e)
            return False
        
    async def _initialize(self) -> None:
        """
        Initialize Web3 connection and contracts.
        
        Raises:
            ConnectionError: If unable to connect to blockchain
            ValueError: If invalid configuration provided
        """
        try:
            # Initialize Web3 connection
            if not self.rpc_url:
                raise ValueError(f"No RPC URL provided for {self.chain}")
                
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            
            if not self.w3.is_connected():
                raise ConnectionError(f"Failed to connect to {self.chain} at {self.rpc_url}")
            
            # Initialize HTTP session for additional API calls
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Initialize factory contract
            factory_address = self.factory_addresses.get(self.chain)
            if not factory_address:
                raise ValueError(f"No factory address configured for chain: {self.chain}")
                
            self.uniswap_factory = self.w3.eth.contract(
                address=factory_address,
                abi=self.factory_abi
            )
            
            self.logger.info(f"Web3 connected to {self.chain}: {self.w3.is_connected()}")
            self.logger.info(f"Factory contract initialized: {factory_address}")
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            raise

    async def _check(self) -> None:
        """
        Perform monitoring check for new token pairs.
        
        Raises:
            Exception: Various exceptions from blockchain or API calls
        """
        try:
            if not self.w3 or not self.w3.is_connected():
                await self._initialize()
                return
                
            current_block = self.w3.eth.block_number
            
            # Only check if there are new blocks
            if current_block <= self.last_block_checked:
                return
                
            # Process blocks in batches to avoid rate limits
            batch_size = min(50, current_block - self.last_block_checked)
            to_block = min(self.last_block_checked + batch_size, current_block)
            
            self.logger.debug(
                f"Scanning {self.chain} blocks {self.last_block_checked + 1} to {to_block}"
            )
            
            # Get PairCreated events
            events = await self._get_pair_created_events(
                self.last_block_checked + 1, 
                to_block
            )
            
            # Process each event
            for event in events:
                await self._process_pair_event(event)
                
            self.last_block_checked = to_block
            
        except Exception as e:
            self.logger.error(f"Error during {self.chain} monitoring check: {e}")
            self.stats["errors_count"] += 1
            self.stats["last_error"] = str(e)
            raise

    async def _get_pair_created_events(
        self, 
        from_block: int, 
        to_block: int
    ) -> List[Dict[str, Any]]:
        """
        Get PairCreated events from the factory contract.
        
        Args:
            from_block: Starting block number
            to_block: Ending block number
            
        Returns:
            List of event dictionaries
            
        Raises:
            Exception: If unable to fetch events
        """
        try:
            event_filter = self.uniswap_factory.events.PairCreated.create_filter(
                fromBlock=from_block,
                toBlock=to_block
            )
            
            events = event_filter.get_all_entries()
            
            if events:
                self.logger.info(
                    f"Found {len(events)} new pairs on {self.chain} "
                    f"(blocks {from_block}-{to_block})"
                )
                
            return events
            
        except Exception as e:
            self.logger.error(f"Failed to get events: {e}")
            return []

    async def _process_pair_event(self, event: Dict[str, Any]) -> None:
        """
        Process a PairCreated event to evaluate trading opportunities.
        
        Args:
            event: Event data from blockchain
        """
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
            self.stats["pairs_processed"] += 1
            
            self.logger.info(f"Processing new {self.chain} pair: {pair_address}")
            self.logger.debug(f"Token0: {token0_address}, Token1: {token1_address}")
            
            # Determine which token is the new one (not WETH/USDC/USDT)
            common_tokens = self._get_common_tokens()
            
            new_token_address = None
            if token0_address.lower() not in common_tokens:
                new_token_address = token0_address
            elif token1_address.lower() not in common_tokens:
                new_token_address = token1_address
            else:
                # Both tokens are common tokens, still process for testing
                new_token_address = token0_address
                
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
            
            self.stats["opportunities_found"] += 1
            
            # Notify callbacks
            await self._notify_callbacks(opportunity)
            
        except Exception as e:
            self.logger.error(f"Error processing {self.chain} pair event: {e}")
            self.stats["errors_count"] += 1

    def _get_common_tokens(self) -> set:
        """
        Get set of common token addresses for the current chain.
        
        Returns:
            Set of lowercase token addresses
        """
        common_tokens = {
            "ethereum": {
                "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH
                "0xa0b86a33e6441019fad5b4a55745e22a85e5db69",  # USDC
                "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT
            },
            "base": {
                "0x4200000000000000000000000000000000000006",  # WETH (Base)
                "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # USDC (Base)
                "0x50c5725949a6f0c72e6c4a641f24049a917db0cb",  # DAI (Base)
            }
        }
        
        return common_tokens.get(self.chain, set())
            
    async def _get_token_info(self, token_address: str) -> Optional[TokenInfo]:
        """
        Get basic information about a token.
        
        Args:
            token_address: Token contract address
            
        Returns:
            TokenInfo object or None if failed
        """
        try:
            # Create token contract
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self.erc20_abi
            )
            
            # Get basic token info with error handling
            try:
                name = token_contract.functions.name().call()
            except Exception:
                name = "Unknown"
                
            try:
                symbol = token_contract.functions.symbol().call()
            except Exception:
                symbol = "UNK"
                
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
                name=name,
                symbol=symbol,
                decimals=decimals,
                total_supply=total_supply,
                chain=self.chain,
                discovered_at=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get token info for {token_address}: {e}")
            return None

    async def _get_liquidity_info(
        self, 
        pair_address: str, 
        token0_address: str, 
        token1_address: str, 
        block_number: int
    ) -> Optional[LiquidityInfo]:
        """
        Get liquidity information for a trading pair.
        
        Args:
            pair_address: Pair contract address
            token0_address: First token address
            token1_address: Second token address
            block_number: Block where pair was created
            
        Returns:
            LiquidityInfo object or None if failed
        """
        try:
            # Simplified liquidity info - in production this would query the pair contract
            return LiquidityInfo(
                pair_address=pair_address,
                token0_address=token0_address,
                token1_address=token1_address,
                token0_reserve=Decimal('0'),  # Would query actual reserves
                token1_reserve=Decimal('0'),  # Would query actual reserves
                total_supply=Decimal('0'),    # Would query LP token supply
                block_number=block_number,
                dex="uniswap_v2" if self.chain == "ethereum" else "baseswap"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get liquidity info for {pair_address}: {e}")
            return None

    async def _cleanup(self) -> None:
        """
        Cleanup resources when stopping.
        """
        try:
            if self.session:
                await self.session.close()
                self.session = None
                
            self.logger.info(f"{self.chain} NewTokenMonitor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get monitoring statistics.
        
        Returns:
            Dictionary with current statistics
        """
        uptime = datetime.now() - self.stats["uptime_start"]
        
        return {
            "chain": self.chain,
            "pairs_processed": self.stats["pairs_processed"],
            "opportunities_found": self.stats["opportunities_found"],
            "errors_count": self.stats["errors_count"],
            "last_error": self.stats["last_error"],
            "uptime_seconds": uptime.total_seconds(),
            "last_block_checked": self.last_block_checked,
            "is_running": self.is_running,
            "processed_pairs_count": len(self.processed_pairs)
        }

    def reset_stats(self) -> None:
        """Reset monitoring statistics."""
        self.stats = {
            "pairs_processed": 0,
            "opportunities_found": 0,
            "errors_count": 0,
            "last_error": None,
            "uptime_start": datetime.now()
        }
        self.processed_pairs.clear()
        self.logger.info(f"{self.chain} NewTokenMonitor stats reset")