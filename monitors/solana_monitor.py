"""
Complete fixed SolanaMonitor with all required methods.

File: monitors/solana_monitor.py (REPLACE ENTIRE FILE)
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import base58
from decimal import Decimal

from models.token import TokenInfo, LiquidityInfo, TradingOpportunity, ContractAnalysis, SocialMetrics, RiskLevel
from monitors.base_monitor import BaseMonitor
from config.chains import multichain_settings
from utils.logger import logger_manager


class SolanaMonitor(BaseMonitor):
    """
    Monitor for detecting new token launches on Solana ecosystem.
    Focuses on Pump.fun for new token detection and Raydium for DEX pairs.
    """
    
    def __init__(
        self, 
        check_interval: float = 1.0
    ) -> None:
        """
        Initialize the Solana monitor.
        
        Args:
            check_interval: Seconds between checks (very fast for Solana)
        """
        super().__init__("Solana", check_interval)
        
        # Configuration
        try:
            self.solana_config = multichain_settings.solana
        except Exception:
            # Fallback configuration if multichain_settings not available
            from types import SimpleNamespace
            self.solana_config = SimpleNamespace(
                pump_fun_api="https://frontend-api.pump.fun",
                raydium_api="https://api.raydium.io/v2",
                enabled=True
            )
        
        # Session and state management
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_tokens: set = set()
        self.last_check_time = datetime.now()
        
        # Additional properties (set after construction)
        self.scorer = None
        self.auto_trading = False
        
        # Statistics tracking
        self.stats = {
            "tokens_processed": 0,
            "opportunities_found": 0,
            "errors_count": 0,
            "last_error": None,
            "uptime_start": datetime.now(),
            "pump_fun_tokens": 0,
            "raydium_pairs": 0
        }
        
        # Known tokens to skip (common Solana tokens)
        self.known_tokens = {
            "So11111111111111111111111111111111111111112",  # SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
            "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",  # WIF
            "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",  # POPCAT
        }

    def set_scorer(self, scorer: Any) -> None:
        """Set the trading scorer after initialization."""
        self.scorer = scorer

    def set_auto_trading(self, enabled: bool) -> None:
        """Set auto trading mode after initialization."""
        self.auto_trading = enabled

    async def initialize(self) -> bool:
        """
        Public initialize method called by production systems.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            self.logger.info("Initializing Solana Monitor...")
            
            # Call the private initialization method
            await self._initialize()
            
            # Test connections
            if self.session:
                connection_tests = await self._test_connections()
                
                if any(connection_tests.values()):
                    self.logger.info("✅ Solana Monitor initialized successfully")
                    self.logger.info(f"   Pump.fun API: {'✅' if connection_tests.get('pump_fun') else '❌'}")
                    self.logger.info(f"   Auto trading: {'✅' if self.auto_trading else '❌'}")
                    
                    return True
                else:
                    self.logger.error("❌ All Solana API connections failed")
                    return False
            else:
                self.logger.error("❌ Failed to create HTTP session")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Solana Monitor: {e}")
            self.stats["errors_count"] += 1
            self.stats["last_error"] = str(e)
            return False

    async def _initialize(self) -> None:
        """
        Initialize Solana connections (required by BaseMonitor abstract class).
        
        This method is required by the abstract BaseMonitor class.
        It's called internally by the BaseMonitor.start() method.
        
        Raises:
            Exception: If unable to initialize required connections
        """
        try:
            # Initialize HTTP session with appropriate timeout for Solana's speed
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            self.logger.info("HTTP session initialized for Solana APIs")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Solana connections: {e}")
            raise

    async def _test_connections(self) -> Dict[str, bool]:
        """
        Test connections to Solana APIs.
        
        Returns:
            Dictionary with connection test results
        """
        connection_results = {}
        
        # Test Pump.fun connection
        try:
            await self._test_pump_fun_connection()
            connection_results['pump_fun'] = True
        except Exception as e:
            self.logger.warning(f"Pump.fun connection test failed: {e}")
            connection_results['pump_fun'] = False
            
        return connection_results
            
    async def _test_pump_fun_connection(self) -> None:
        """
        Test connection to Pump.fun API.
        
        Raises:
            Exception: If connection test fails
        """
        try:
            # Test endpoint - get recent tokens with small limit
            url = f"{self.solana_config.pump_fun_api}/coins"
            params = {'limit': 1, 'sort': 'created_timestamp', 'order': 'DESC'}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    self.logger.info("Pump.fun API connection successful")
                    return
                else:
                    raise Exception(f"Pump.fun API returned status {response.status}")
                    
        except Exception as e:
            raise Exception(f"Pump.fun API test failed: {e}")

    async def _check(self) -> None:
        """
        Check for new tokens on Solana (required by BaseMonitor abstract class).
        
        Raises:
            Exception: Various exceptions from API calls
        """
        try:
            if not self.session:
                await self._initialize()
                return
                
            # Check Pump.fun for new token launches
            await self._check_pump_fun_tokens()
            
        except Exception as e:
            self.logger.error(f"Error during Solana check: {e}")
            self.stats["errors_count"] += 1
            self.stats["last_error"] = str(e)
            raise
            
    async def _check_pump_fun_tokens(self) -> None:
        """
        Check Pump.fun for newly launched tokens.
        
        Raises:
            Exception: If API calls fail
        """
        try:
            # Get recent tokens from Pump.fun
            url = f"{self.solana_config.pump_fun_api}/coins"
            params = {
                'limit': 50,
                'sort': 'created_timestamp',
                'order': 'DESC'
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"Pump.fun API returned status {response.status}")
                    
                data = await response.json()
                
                if not isinstance(data, list):
                    self.logger.warning("Unexpected Pump.fun API response format")
                    return
                
                new_tokens_found = 0
                
                for token_data in data:
                    if await self._process_pump_fun_token(token_data):
                        new_tokens_found += 1
                
                if new_tokens_found > 0:
                    self.logger.info(f"Found {new_tokens_found} new Pump.fun tokens")
                    self.stats["pump_fun_tokens"] += new_tokens_found
                
        except Exception as e:
            self.logger.error(f"Error checking Pump.fun tokens: {e}")
            raise

    async def _process_pump_fun_token(self, token_data: Dict[str, Any]) -> bool:
        """
        Process a token from Pump.fun data.
        
        Args:
            token_data: Token data from Pump.fun API
            
        Returns:
            bool: True if token was processed as new opportunity
        """
        try:
            # Extract token information
            mint_address = token_data.get('mint')
            if not mint_address:
                return False
                
            # Skip if already processed
            if mint_address in self.processed_tokens:
                return False
                
            # Skip known tokens
            if mint_address in self.known_tokens:
                return False
                
            # Check if token is too old (only process recent tokens)
            created_timestamp = token_data.get('created_timestamp')
            if created_timestamp:
                try:
                    created_time = datetime.fromtimestamp(created_timestamp / 1000)
                    if (datetime.now() - created_time).total_seconds() > 3600:  # 1 hour old
                        return False
                except Exception:
                    pass
            
            self.processed_tokens.add(mint_address)
            self.stats["tokens_processed"] += 1
            
            # Create TokenInfo
            token_info = self._create_solana_token_info(token_data)
            if not token_info:
                return False
                
            # Create LiquidityInfo (simplified for Pump.fun)
            liquidity_info = self._create_pump_fun_liquidity_info(token_data)
            if not liquidity_info:
                return False
                
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
            
            self.logger.info(f"New Pump.fun token: {token_info.symbol} ({mint_address[:8]}...)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing Pump.fun token: {e}")
            return False

    def _create_solana_token_info(self, token_data: Dict[str, Any]) -> Optional[TokenInfo]:
        """
        Create TokenInfo from Pump.fun token data.
        
        Args:
            token_data: Token data from API
            
        Returns:
            TokenInfo object or None if creation failed
        """
        try:
            return TokenInfo(
                address=token_data.get('mint', ''),
                name=token_data.get('name', 'Unknown'),
                symbol=token_data.get('symbol', 'UNK'),
                decimals=token_data.get('decimals', 9),  # Common for Solana
                total_supply=token_data.get('total_supply', 0),
                discovered_at=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create Solana token info: {e}")
            return None

    def _create_pump_fun_liquidity_info(self, token_data: Dict[str, Any]) -> Optional[LiquidityInfo]:
        """
        Create LiquidityInfo from Pump.fun token data.
        
        Args:
            token_data: Token data from API
            
        Returns:
            LiquidityInfo object or None if creation failed
        """
        try:
            return LiquidityInfo(
                pair_address=token_data.get('mint', ''),  # Use mint as identifier
                token0_address=token_data.get('mint', ''),
                token1_address="So11111111111111111111111111111111111111112",  # SOL
                token0_reserve=Decimal(str(token_data.get('virtual_token_reserves', 0))),
                token1_reserve=Decimal(str(token_data.get('virtual_sol_reserves', 0))),
                total_supply=Decimal(str(token_data.get('total_supply', 0))),
                block_number=0,  # Not applicable for Solana
                dex="pump_fun"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create Pump.fun liquidity info: {e}")
            return None

    async def _cleanup(self) -> None:
        """
        Cleanup resources when stopping (required by BaseMonitor abstract class).
        Enhanced to properly close all sessions and prevent warnings.
        """
        try:
            # Close HTTP session if it exists
            if hasattr(self, 'session') and self.session:
                if not self.session.closed:
                    await self.session.close()
                    self.logger.info(f"{self.name} monitor session closed")
            
            # Clear the session reference
            self.session = None
            
            # Log cleanup completion
            self.logger.info(f"{self.name} monitor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during {self.name} cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get monitoring statistics.
        
        Returns:
            Dictionary with current statistics
        """
        uptime = datetime.now() - self.stats["uptime_start"]
        
        return {
            "chain": "solana",
            "tokens_processed": self.stats["tokens_processed"],
            "opportunities_found": self.stats["opportunities_found"],
            "errors_count": self.stats["errors_count"],
            "last_error": self.stats["last_error"],
            "uptime_seconds": uptime.total_seconds(),
            "is_running": self.is_running,
            "processed_tokens_count": len(self.processed_tokens),
            "pump_fun_tokens": self.stats["pump_fun_tokens"],
            "raydium_pairs": self.stats["raydium_pairs"],
            "auto_trading": self.auto_trading
        }

    def reset_stats(self) -> None:
        """Reset monitoring statistics."""
        self.stats = {
            "tokens_processed": 0,
            "opportunities_found": 0,
            "errors_count": 0,
            "last_error": None,
            "uptime_start": datetime.now(),
            "pump_fun_tokens": 0,
            "raydium_pairs": 0
        }
        self.processed_tokens.clear()
        self.logger.info("Solana Monitor stats reset")