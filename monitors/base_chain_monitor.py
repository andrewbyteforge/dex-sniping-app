"""
Base Chain monitor for detecting new token launches.
Similar to Ethereum but optimized for Base chain characteristics.

File: monitors/base_chain_monitor.py
Class: BaseChainMonitor  
Method: Adding public initialize() method
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from web3 import Web3
from web3.contract import Contract
from decimal import Decimal

from models.token import TokenInfo, LiquidityInfo, TradingOpportunity, ContractAnalysis, SocialMetrics
from monitors.base_monitor import BaseMonitor
from config.chains import multichain_settings, ChainType
from utils.logger import logger_manager


class BaseChainMonitor(BaseMonitor):
    """
    Monitor for detecting newly launched tokens on Base chain.
    Uses same logic as Ethereum but with Base-specific configuration.
    """
    
    def __init__(
        self, 
        check_interval: float = 2.0,
        chain: str = "base",
        rpc_url: Optional[str] = None,
        analyzer: Optional[Any] = None,
        scorer: Optional[Any] = None,
        auto_trading: bool = False
    ) -> None:
        """
        Initialize the Base chain monitor.
        
        Args:
            check_interval: Seconds between monitoring checks (faster blocks on Base)
            chain: Blockchain identifier
            rpc_url: RPC endpoint URL
            analyzer: Contract analyzer instance
            scorer: Trading scorer instance  
            auto_trading: Enable automatic trading
        """
        super().__init__("BaseChain", check_interval)
        
        self.chain = chain
        self.rpc_url = rpc_url
        self.analyzer = analyzer
        self.scorer = scorer
        self.auto_trading = auto_trading
        
        # Get chain configuration
        try:
            self.chain_config = multichain_settings.get_chain_config(ChainType.BASE)
        except Exception:
            # Fallback configuration if multichain_settings not available
            from types import SimpleNamespace
            self.chain_config = SimpleNamespace(
                name="Base",
                chain_id=8453,
                rpc_url=rpc_url or "https://mainnet.base.org",
                dex_factory="0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6"  # BaseSwap factory
            )
        
        # Core monitoring state
        self.w3: Optional[Web3] = None
        self.last_block_checked = 0
        self.processed_pairs: set = set()
        self.dex_factory: Optional[Contract] = None
        
        # Statistics tracking
        self.stats = {
            "pairs_processed": 0,
            "opportunities_found": 0,
            "errors_count": 0,
            "last_error": None,
            "uptime_start": datetime.now()
        }
        
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
            self.logger.info("Initializing Base Chain Monitor...")
            
            # Call the private initialization method
            await self._initialize()
            
            # Test the connection and get starting block
            if self.w3 and self.w3.is_connected():
                latest_block = self.w3.eth.block_number
                self.last_block_checked = latest_block - 5  # Start 5 blocks back
                
                self.logger.info("✅ Base Chain Monitor initialized successfully")
                self.logger.info(f"   Latest block: {latest_block}")
                self.logger.info(f"   Starting from block: {self.last_block_checked}")
                self.logger.info(f"   Chain ID: {self.chain_config.chain_id}")
                self.logger.info(f"   Factory: {self.chain_config.dex_factory}")
                
                return True
            else:
                self.logger.error("❌ Web3 connection failed for Base chain")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Base Chain Monitor: {e}")
            self.stats["errors_count"] += 1
            self.stats["last_error"] = str(e)
            return False
        
    async def _initialize(self) -> None:
        """
        Initialize Web3 connection for Base chain.
        
        Raises:
            ConnectionError: If unable to connect to Base chain
            ValueError: If invalid chain configuration
        """
        try:
            # Use provided RPC URL or fall back to chain config
            rpc_url = self.rpc_url or self.chain_config.rpc_url
            
            if not rpc_url:
                raise ValueError("No RPC URL provided for Base chain")
            
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            
            if not self.w3.is_connected():
                raise ConnectionError(f"Failed to connect to Base chain at {rpc_url}")
                
            # Verify we're on the right chain
            chain_id = self.w3.eth.chain_id
            expected_chain_id = getattr(self.chain_config, 'chain_id', 8453)
            
            if chain_id != expected_chain_id:
                raise ValueError(f"Expected chain {expected_chain_id}, got {chain_id}")
                
            self.logger.info(f"Connected to {self.chain_config.name} (Chain ID: {chain_id})")
            
            # Initialize DEX factory contract
            factory_address = getattr(self.chain_config, 'dex_factory', None)
            if not factory_address:
                raise ValueError("No DEX factory address configured for Base chain")
                
            self.dex_factory = self.w3.eth.contract(
                address=factory_address,
                abi=self.factory_abi
            )
            
            self.logger.info(f"DEX factory contract initialized at {factory_address}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Base chain: {e}")
            raise
            
    async def _check(self) -> None:
        """
        Check for new token pairs on Base chain.
        
        Raises:
            Exception: Various exceptions from blockchain calls
        """
        try:
            if not self.w3 or not self.w3.is_connected():
                await self._initialize()
                return
                
            current_block = self.w3.eth.block_number
            
            if current_block <= self.last_block_checked:
                return
                
            # Process blocks in smaller batches for Base (faster blocks)
            batch_size = min(20, current_block - self.last_block_checked)
            to_block = min(self.last_block_checked + batch_size, current_block)
            
            self.logger.debug(f"Checking Base blocks {self.last_block_checked + 1} to {to_block}")
            
            # Get PairCreated events
            events = await self._get_pair_created_events(
                self.last_block_checked + 1, 
                to_block
            )
            
            for event in events:
                await self._process_pair_created_event(event)
                
            self.last_block_checked = to_block
            
        except Exception as e:
            self.logger.error(f"Error during Base chain check: {e}")
            self.stats["errors_count"] += 1
            self.stats["last_error"] = str(e)
            raise
            
    async def _get_pair_created_events(self, from_block: int, to_block: int) -> List[Dict[str, Any]]:
        """
        Get PairCreated events from Base chain with proper hex formatting.
        
        Args:
            from_block: Starting block number
            to_block: Ending block number
            
        Returns:
            List of parsed event dictionaries
        """
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
                
            # Parse logs manually for better error handling
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
                    self.logger.warning(f"Error parsing Base event log: {parse_error}")
                    continue
                    
            return parsed_events
            
        except Exception as e:
            self.logger.error(f"Error getting Base chain events: {e}")
            return []

    async def _process_pair_created_event(self, event: Dict[str, Any]) -> None:
        """
        Process a PairCreated event for potential trading opportunities.
        
        Args:
            event: Parsed event data
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
            
            self.logger.info(f"Processing new Base pair: {pair_address}")
            self.logger.debug(f"Token0: {token0_address}, Token1: {token1_address}")
            
            # Determine which token is new (not WETH/USDC on Base)
            base_common_tokens = {
                "0x4200000000000000000000000000000000000006",  # WETH (Base)
                "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # USDC (Base)
                "0x50c5725949a6f0c72e6c4a641f24049a917db0cb",  # DAI (Base)
            }
            
            new_token_address = None
            if token0_address.lower() not in [addr.lower() for addr in base_common_tokens]:
                new_token_address = token0_address
            elif token1_address.lower() not in [addr.lower() for addr in base_common_tokens]:
                new_token_address = token1_address
            else:
                # Both tokens are common, process anyway for completeness
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
            self.logger.error(f"Error processing Base pair event: {e}")
            self.stats["errors_count"] += 1

    async def _get_token_info(self, token_address: str) -> Optional[TokenInfo]:
        """
        Get basic information about a token on Base chain.
        
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
                chain="base",
                discovered_at=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get Base token info for {token_address}: {e}")
            return None

    async def _get_liquidity_info(
        self, 
        pair_address: str, 
        token0_address: str, 
        token1_address: str, 
        block_number: int
    ) -> Optional[LiquidityInfo]:
        """
        Get liquidity information for a Base chain trading pair.
        
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
                dex="baseswap"  # Base chain DEX
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get Base liquidity info for {pair_address}: {e}")
            return None

    async def _cleanup(self) -> None:
        """
        Cleanup resources when stopping.
        """
        try:
            self.logger.info("Base Chain Monitor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Base cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get monitoring statistics.
        
        Returns:
            Dictionary with current statistics
        """
        uptime = datetime.now() - self.stats["uptime_start"]
        
        return {
            "chain": "base",
            "pairs_processed": self.stats["pairs_processed"],
            "opportunities_found": self.stats["opportunities_found"],
            "errors_count": self.stats["errors_count"],
            "last_error": self.stats["last_error"],
            "uptime_seconds": uptime.total_seconds(),
            "last_block_checked": self.last_block_checked,
            "is_running": self.is_running,
            "processed_pairs_count": len(self.processed_pairs),
            "chain_id": getattr(self.chain_config, 'chain_id', 8453)
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
        self.logger.info("Base Chain Monitor stats reset")