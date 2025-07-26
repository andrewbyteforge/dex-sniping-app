#!/usr/bin/env python3
"""
Enhanced Solana Monitor with robust error handling and fallback mechanisms.

File: monitors/solana_monitor.py
Functions: Enhanced _check_pump_fun_tokens(), _handle_api_errors(), _circuit_breaker_check()
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


class APICircuitBreaker:
    """Circuit breaker for API failures."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300) -> None:
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    def record_success(self) -> None:
        """Record successful API call."""
        self.failure_count = 0
        self.state = "CLOSED"
        
    def record_failure(self) -> None:
        """Record failed API call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            
    def can_execute(self) -> bool:
        """Check if API call should be attempted."""
        if self.state == "CLOSED":
            return True
            
        if self.state == "OPEN":
            if self.last_failure_time:
                time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
                if time_since_failure >= self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    return True
            return False
            
        # HALF_OPEN state
        return True


class SolanaMonitor(BaseMonitor):
    """
    Enhanced monitor for detecting new token launches on Solana ecosystem.
    Includes robust error handling, circuit breakers, and fallback mechanisms.
    """
    
    def __init__(
        self, 
        check_interval: float = 5.0
    ) -> None:
        """
        Initialize the enhanced Solana monitor.
        
        Args:
            check_interval: Seconds between checks (increased for stability)
        """
        super().__init__("Solana", check_interval)
        
        # Configuration with fallbacks
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
        
        # Enhanced session and state management
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_tokens: set = set()
        self.last_check_time = datetime.now()
        
        # Circuit breakers for different APIs
        self.pump_fun_circuit_breaker = APICircuitBreaker(
            failure_threshold=3,  # More aggressive for 530 errors
            recovery_timeout=120  # 2 minutes recovery time
        )
        
        # Enhanced error tracking
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10
        self.api_healthy = True
        self.last_successful_check: Optional[datetime] = None
        
        # Fallback mode settings
        self.fallback_mode = False
        self.fallback_check_interval = 30.0  # Slower checks in fallback mode
        
        # Additional properties (set after construction)
        self.scorer = None
        self.auto_trading = False
        
        # Enhanced statistics tracking
        self.stats = {
            "tokens_processed": 0,
            "opportunities_found": 0,
            "errors_count": 0,
            "last_error": None,
            "uptime_start": datetime.now(),
            "pump_fun_tokens": 0,
            "raydium_pairs": 0,
            "api_530_errors": 0,
            "circuit_breaker_trips": 0,
            "fallback_mode_activations": 0,
            "last_successful_check": None
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
            self.logger.info("Initializing Enhanced Solana Monitor...")
            
            # Call the private initialization method
            await self._initialize()
            
            # Test connections with circuit breaker consideration
            if self.session:
                connection_tests = await self._test_connections()
                
                # Consider partial success acceptable
                if any(connection_tests.values()) or not all(connection_tests.values()):
                    self.logger.info("✅ Enhanced Solana Monitor initialized")
                    self.logger.info(f"   Pump.fun API: {'✅' if connection_tests.get('pump_fun') else '❌ (will use fallback)'}")
                    self.logger.info(f"   Auto trading: {'✅' if self.auto_trading else '❌'}")
                    self.logger.info(f"   Circuit breaker: ✅ Active")
                    self.logger.info(f"   Fallback mode: {'✅' if self.fallback_mode else '❌'}")
                    
                    # Set fallback mode if API is not healthy
                    if not connection_tests.get('pump_fun', False):
                        self._activate_fallback_mode("Initial connection test failed")
                    
                    return True
                else:
                    self.logger.warning("⚠️  All Solana API connections failed - using fallback mode")
                    self._activate_fallback_mode("All API connections failed")
                    return True  # Still return True to allow system to continue
            else:
                self.logger.error("❌ Failed to create HTTP session")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Enhanced Solana Monitor: {e}")
            self.stats["errors_count"] += 1
            self.stats["last_error"] = str(e)
            return False

    async def _initialize(self) -> None:
        """
        Initialize Solana connections with enhanced error handling.
        
        Raises:
            Exception: If unable to initialize required connections
        """
        try:
            # Initialize HTTP session with enhanced settings for stability
            timeout = aiohttp.ClientTimeout(
                total=15,        # Longer total timeout
                connect=5,       # Quick connect timeout
                sock_read=10     # Socket read timeout
            )
            
            # Enhanced connector settings for stability
            connector = aiohttp.TCPConnector(
                limit=10,        # Connection pool limit
                limit_per_host=5, # Per-host limit
                ttl_dns_cache=300, # DNS cache TTL
                use_dns_cache=True,
                enable_cleanup_closed=True
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': 'DexSniping/1.0',
                    'Accept': 'application/json',
                    'Accept-Encoding': 'gzip, deflate'
                }
            )
            
            self.logger.info("Enhanced HTTP session initialized for Solana APIs")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize enhanced Solana connections: {e}")
            raise

    async def _test_connections(self) -> Dict[str, bool]:
        """
        Test connections to Solana APIs with circuit breaker logic.
        
        Returns:
            Dictionary with connection test results
        """
        connection_results = {}
        
        # Test Pump.fun connection with circuit breaker
        try:
            if self.pump_fun_circuit_breaker.can_execute():
                await self._test_pump_fun_connection()
                connection_results['pump_fun'] = True
                self.pump_fun_circuit_breaker.record_success()
            else:
                self.logger.warning("Pump.fun circuit breaker is OPEN - skipping connection test")
                connection_results['pump_fun'] = False
        except Exception as e:
            self.logger.warning(f"Pump.fun connection test failed: {e}")
            connection_results['pump_fun'] = False
            self.pump_fun_circuit_breaker.record_failure()
            
        return connection_results
            
    async def _test_pump_fun_connection(self) -> None:
        """
        Test connection to Pump.fun API with enhanced error handling.
        
        Raises:
            Exception: If connection test fails
        """
        try:
            # Use a simpler endpoint for testing
            url = f"{self.solana_config.pump_fun_api}/coins"
            params = {
                'limit': 1,
                'sort': 'created_timestamp', 
                'order': 'DESC'
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    self.logger.info("Pump.fun API connection successful")
                    return
                elif response.status == 530:
                    raise Exception(f"Pump.fun API server error (530) - likely temporary maintenance")
                else:
                    raise Exception(f"Pump.fun API returned status {response.status}")
                    
        except asyncio.TimeoutError:
            raise Exception("Pump.fun API connection timeout")
        except aiohttp.ClientError as e:
            raise Exception(f"Pump.fun API connection error: {e}")
        except Exception as e:
            raise Exception(f"Pump.fun API test failed: {e}")

    async def _check(self) -> None:
        """
        Enhanced check for new tokens on Solana with circuit breaker and fallback logic.
        
        Raises:
            Exception: Various exceptions from API calls (handled by base monitor)
        """
        try:
            if not self.session:
                await self._initialize()
                return
            
            # Check if we should skip due to circuit breaker
            if not self.pump_fun_circuit_breaker.can_execute():
                self.logger.debug("Pump.fun circuit breaker is OPEN - skipping check")
                await self._handle_circuit_breaker_skip()
                return
                
            # Check Pump.fun for new token launches
            await self._check_pump_fun_tokens_enhanced()
            
            # Record successful check
            self.consecutive_failures = 0
            self.last_successful_check = datetime.now()
            self.stats["last_successful_check"] = self.last_successful_check
            
            # Deactivate fallback mode if we're successful
            if self.fallback_mode:
                self._deactivate_fallback_mode()
            
        except Exception as e:
            await self._handle_check_error(e)
            raise
            
    async def _check_pump_fun_tokens_enhanced(self) -> None:
        """
        Enhanced check for Pump.fun tokens with better error handling.
        
        Raises:
            Exception: If API calls fail after retries
        """
        try:
            # Get recent tokens from Pump.fun with enhanced parameters
            url = f"{self.solana_config.pump_fun_api}/coins"
            params = {
                'limit': 25,  # Reduced from 50 to decrease load
                'sort': 'created_timestamp',
                'order': 'DESC'
            }
            
            async with self.session.get(url, params=params) as response:
                await self._handle_pump_fun_response(response)
                
        except Exception as e:
            self.logger.error(f"Error checking Pump.fun tokens: {e}")
            raise

    async def _handle_pump_fun_response(self, response: aiohttp.ClientResponse) -> None:
        """
        Handle Pump.fun API response with detailed error handling.
        
        Args:
            response: HTTP response from Pump.fun API
            
        Raises:
            Exception: If response indicates failure
        """
        try:
            if response.status == 200:
                # Success case
                data = await response.json()
                await self._process_pump_fun_data(data)
                self.pump_fun_circuit_breaker.record_success()
                
            elif response.status == 530:
                # Server error - likely maintenance
                self.stats["api_530_errors"] += 1
                self.pump_fun_circuit_breaker.record_failure()
                error_msg = "Pump.fun API server error (530) - likely temporary maintenance"
                self.logger.warning(error_msg)
                raise Exception(error_msg)
                
            elif response.status == 429:
                # Rate limiting
                self.pump_fun_circuit_breaker.record_failure()
                error_msg = "Pump.fun API rate limit exceeded (429)"
                self.logger.warning(error_msg)
                raise Exception(error_msg)
                
            elif response.status >= 500:
                # Server errors
                self.pump_fun_circuit_breaker.record_failure()
                error_msg = f"Pump.fun API server error ({response.status})"
                self.logger.warning(error_msg)
                raise Exception(error_msg)
                
            else:
                # Other errors
                self.pump_fun_circuit_breaker.record_failure()
                error_msg = f"Pump.fun API returned status {response.status}"
                self.logger.warning(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            if "530" in str(e) or "server error" in str(e).lower():
                # Don't log these as errors, they're expected during maintenance
                self.logger.info(f"Pump.fun temporary issue: {e}")
            else:
                self.logger.error(f"Error handling Pump.fun response: {e}")
            raise

    async def _process_pump_fun_data(self, data: Any) -> None:
        """
        Process successful Pump.fun API data.
        
        Args:
            data: Parsed JSON data from API
        """
        try:
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
            self.logger.error(f"Error processing Pump.fun data: {e}")

    async def _process_pump_fun_token(self, token_data: Dict[str, Any]) -> bool:
        """
        Process a token from Pump.fun data with enhanced validation.
        
        Args:
            token_data: Token data dictionary
            
        Returns:
            bool: True if token was processed successfully
        """
        try:
            # Extract and validate token address
            token_address = token_data.get('mint', '')
            if not token_address or token_address in self.known_tokens:
                return False
            
            # Check if already processed
            if token_address in self.processed_tokens:
                return False
            
            # Validate required fields
            required_fields = ['name', 'symbol', 'created_timestamp']
            if not all(field in token_data for field in required_fields):
                self.logger.debug(f"Token {token_address} missing required fields")
                return False
            
            # Create token info
            token_info = self._create_solana_token_info(token_data)
            if not token_info:
                return False
            
            # Create liquidity info
            liquidity_info = self._create_pump_fun_liquidity_info(token_data)
            
            # Create trading opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                confidence_score=0.3,  # Lower initial confidence for new system
                recommendation="MONITOR",  # Conservative recommendation
                risk_level=RiskLevel.HIGH,
                metadata={
                    'source': 'pump_fun',
                    'chain': 'solana',
                    'market_cap_usd': token_data.get('market_cap', 0),
                    'created_timestamp': token_data.get('created_timestamp'),
                    'is_new_launch': True
                }
            )
            
            # Notify callbacks
            await self._notify_callbacks(opportunity)
            
            # Track processing
            self.processed_tokens.add(token_address)
            self.stats["tokens_processed"] += 1
            self.stats["opportunities_found"] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing Pump.fun token: {e}")
            return False

    async def _handle_check_error(self, error: Exception) -> None:
        """
        Handle errors during check operation with enhanced logic.
        
        Args:
            error: Exception that occurred during check
        """
        self.consecutive_failures += 1
        self.stats["errors_count"] += 1
        self.stats["last_error"] = str(error)
        
        error_msg = str(error).lower()
        
        if "530" in error_msg or "server error" in error_msg:
            # Server maintenance - activate fallback mode
            if not self.fallback_mode:
                self._activate_fallback_mode("API server maintenance detected")
                
        elif self.consecutive_failures >= self.max_consecutive_failures:
            # Too many consecutive failures
            self.logger.critical(f"Too many consecutive failures ({self.consecutive_failures})")
            self._activate_fallback_mode("Excessive failures detected")

    async def _handle_circuit_breaker_skip(self) -> None:
        """Handle skipped check due to circuit breaker."""
        if not self.fallback_mode:
            self._activate_fallback_mode("Circuit breaker opened")
        
        # Log minimal message to avoid spam
        self.logger.debug("Skipping check - circuit breaker open")

    def _activate_fallback_mode(self, reason: str) -> None:
        """
        Activate fallback mode with slower checks.
        
        Args:
            reason: Reason for activating fallback mode
        """
        if not self.fallback_mode:
            self.fallback_mode = True
            self.stats["fallback_mode_activations"] += 1
            self.check_interval = self.fallback_check_interval
            self.logger.warning(f"🔄 Activated fallback mode: {reason}")
            self.logger.info(f"   Check interval increased to {self.fallback_check_interval}s")

    def _deactivate_fallback_mode(self) -> None:
        """Deactivate fallback mode and return to normal operation."""
        if self.fallback_mode:
            self.fallback_mode = False
            self.check_interval = 5.0  # Return to normal interval
            self.logger.info("✅ Deactivated fallback mode - API healthy")

    def _create_solana_token_info(self, token_data: Dict[str, Any]) -> Optional[TokenInfo]:
        """
        Create TokenInfo from Solana token data with validation.
        
        Args:
            token_data: Token data from API
            
        Returns:
            TokenInfo object or None if creation failed
        """
        try:
            # For Solana tokens, we need to handle the address validation issue
            # since TokenInfo expects 0x format but Solana uses different format
            
            mint_address = token_data.get('mint', '')
            if not mint_address:
                return None
            
            # Create a custom Solana token info object that doesn't have the 0x validation
            class SolanaTokenInfo:
                def __init__(self, address, symbol, name, decimals, total_supply):
                    self.address = address
                    self.symbol = symbol
                    self.name = name
                    self.decimals = decimals
                    self.total_supply = total_supply
                    
            return SolanaTokenInfo(
                address=mint_address,
                symbol=token_data.get('symbol', 'UNK'),
                name=token_data.get('name', 'Unknown'),
                decimals=token_data.get('decimals', 9),  # Common for Solana
                total_supply=token_data.get('total_supply', 0)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create Solana token info: {e}")
            return None









    def _create_pump_fun_liquidity_info(self, token_data: Dict[str, Any]) -> Optional[LiquidityInfo]:
        """
        Create LiquidityInfo from Pump.fun token data with validation.
        
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
        Enhanced cleanup with proper session handling.
        """
        try:
            # Close HTTP session if it exists
            if hasattr(self, 'session') and self.session:
                if not self.session.closed:
                    await self.session.close()
                    # Small delay to ensure proper cleanup
                    await asyncio.sleep(0.1)
                    self.logger.info(f"{self.name} monitor session closed")
            
            # Clear the session reference
            self.session = None
            
            # Log cleanup completion with stats
            uptime = datetime.now() - self.stats["uptime_start"]
            self.logger.info(f"{self.name} monitor cleanup completed")
            self.logger.info(f"   Total uptime: {uptime}")
            self.logger.info(f"   Tokens processed: {self.stats['tokens_processed']}")
            self.logger.info(f"   API 530 errors: {self.stats['api_530_errors']}")
            self.logger.info(f"   Circuit breaker trips: {self.stats['circuit_breaker_trips']}")
            
        except Exception as e:
            self.logger.error(f"Error during {self.name} cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get enhanced monitoring statistics.
        
        Returns:
            Dictionary with current statistics including circuit breaker info
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
            "auto_trading": self.auto_trading,
            "api_530_errors": self.stats["api_530_errors"],
            "circuit_breaker_trips": self.stats["circuit_breaker_trips"],
            "fallback_mode_activations": self.stats["fallback_mode_activations"],
            "fallback_mode": self.fallback_mode,
            "circuit_breaker_state": self.pump_fun_circuit_breaker.state,
            "consecutive_failures": self.consecutive_failures,
            "last_successful_check": self.stats["last_successful_check"],
            "api_healthy": self.api_healthy
        }

    def reset_stats(self) -> None:
        """Reset enhanced monitoring statistics."""
        self.stats = {
            "tokens_processed": 0,
            "opportunities_found": 0,
            "errors_count": 0,
            "last_error": None,
            "uptime_start": datetime.now(),
            "pump_fun_tokens": 0,
            "raydium_pairs": 0,
            "api_530_errors": 0,
            "circuit_breaker_trips": 0,
            "fallback_mode_activations": 0,
            "last_successful_check": None
        }
        self.processed_tokens.clear()
        self.consecutive_failures = 0
        self.pump_fun_circuit_breaker = APICircuitBreaker()
        self.fallback_mode = False
        self.check_interval = 5.0
        self.logger.info("Enhanced Solana Monitor stats reset")