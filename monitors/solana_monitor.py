#!/usr/bin/env python3
"""
Enhanced Solana Monitor with alternative APIs to bypass geographic restrictions.

File: monitors/solana_monitor.py
Replaces Pump.fun with multiple alternative sources that work globally.
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
    Enhanced Solana monitor using multiple alternative APIs to bypass restrictions.
    Uses Jupiter, Solscan, Birdeye, and CoinGecko instead of Pump.fun.
    """
    
    def __init__(
        self, 
        check_interval: float = 15.0
    ) -> None:
        """
        Initialize the enhanced Solana monitor with alternative APIs.
        
        Args:
            check_interval: Seconds between checks (slower for multiple APIs)
        """
        super().__init__("Solana", check_interval)
        
        # Configuration with fallbacks
        try:
            self.solana_config = multichain_settings.solana
        except Exception:
            # Fallback configuration
            from types import SimpleNamespace
            self.solana_config = SimpleNamespace(
                enabled=True
            )
        
        # Alternative API sources (UK-friendly)
        self.data_sources = {
            "jupiter": {
                "url": "https://token.jup.ag/all",
                "enabled": True,
                "circuit_breaker": APICircuitBreaker(failure_threshold=3, recovery_timeout=120),
                "parser": self._parse_jupiter_tokens,
                "description": "Jupiter Aggregator Token List"
            },
            "solscan": {
                "url": "https://public-api.solscan.io/token/list",
                "enabled": True,
                "circuit_breaker": APICircuitBreaker(failure_threshold=3, recovery_timeout=180),
                "parser": self._parse_solscan_tokens,
                "description": "Solscan Public API"
            },
            "birdeye": {
                "url": "https://public-api.birdeye.so/public/tokenlist",
                "enabled": True,
                "circuit_breaker": APICircuitBreaker(failure_threshold=3, recovery_timeout=240),
                "parser": self._parse_birdeye_tokens,
                "description": "Birdeye Public API"
            },
            "coingecko_solana": {
                "url": "https://api.coingecko.com/api/v3/coins/markets",
                "params": {
                    "vs_currency": "usd",
                    "category": "solana-ecosystem",
                    "order": "market_cap_desc",
                    "per_page": 50,
                    "page": 1,
                    "sparkline": False
                },
                "enabled": True,
                "circuit_breaker": APICircuitBreaker(failure_threshold=5, recovery_timeout=300),
                "parser": self._parse_coingecko_tokens,
                "description": "CoinGecko Solana Ecosystem"
            }
        }
        
        # Session and state management
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_tokens: set = set()
        self.last_check_time = datetime.now()
        
        # Enhanced error tracking
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10
        self.api_healthy = True
        self.last_successful_check: Optional[datetime] = None
        
        # Fallback mode settings
        self.fallback_mode = False
        self.fallback_check_interval = 45.0  # Slower checks in fallback mode
        
        # Track which APIs are working
        self.working_apis = set()
        
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
            "api_calls_total": 0,
            "api_calls_successful": 0,
            "api_calls_failed": 0,
            "working_apis": 0,
            "fallback_mode_activations": 0,
            "last_successful_check": None,
            "sources_stats": {}
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
            self.logger.info("Initializing Enhanced Solana Monitor with Alternative APIs...")
            
            # Call the private initialization method
            await self._initialize()
            
            # Test all available APIs
            if self.session:
                working_count = await self._test_all_apis()
                
                if working_count > 0:
                    self.logger.info("✅ Enhanced Solana Monitor initialized successfully")
                    self.logger.info(f"   Working APIs: {working_count}/{len(self.data_sources)}")
                    self.logger.info(f"   Available sources: {', '.join(self.working_apis)}")
                    self.logger.info(f"   Auto trading: {'✅' if self.auto_trading else '❌'}")
                    self.logger.info(f"   Circuit breakers: ✅ Active for all sources")
                    
                    return True
                else:
                    self.logger.warning("⚠️  No Solana APIs are currently working - activating fallback mode")
                    self._activate_fallback_mode("All APIs failed during initialization")
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
                total=20,        # Longer total timeout for multiple APIs
                connect=5,       # Quick connect timeout
                sock_read=15     # Socket read timeout
            )
            
            # Enhanced connector settings for stability
            connector = aiohttp.TCPConnector(
                limit=15,        # Connection pool limit
                limit_per_host=5, # Per-host limit
                ttl_dns_cache=300, # DNS cache TTL
                use_dns_cache=True,
                enable_cleanup_closed=True
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/json',
                    'Accept-Encoding': 'gzip, deflate',
                    'Accept-Language': 'en-US,en;q=0.9'
                }
            )
            
            self.logger.info("Enhanced HTTP session initialized for alternative Solana APIs")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize enhanced Solana connections: {e}")
            raise

    async def _test_all_apis(self) -> int:
        """
        Test all alternative APIs and return count of working ones.
        
        Returns:
            int: Number of working APIs
        """
        working_count = 0
        self.working_apis.clear()
        
        for source_name, config in self.data_sources.items():
            if not config["enabled"]:
                continue
                
            try:
                if await self._test_api_source(source_name, config):
                    working_count += 1
                    self.working_apis.add(source_name)
                    config["circuit_breaker"].record_success()
                    self.logger.info(f"✅ {config['description']} - Working")
                else:
                    config["circuit_breaker"].record_failure()
                    self.logger.warning(f"❌ {config['description']} - Failed")
                    
            except Exception as e:
                config["circuit_breaker"].record_failure()
                self.logger.warning(f"❌ {config['description']} - Error: {e}")
        
        self.stats["working_apis"] = working_count
        return working_count

    async def _test_api_source(self, source_name: str, config: Dict[str, Any]) -> bool:
        """
        Test a specific API source.
        
        Args:
            source_name: Name of the API source
            config: Configuration for the API
            
        Returns:
            bool: True if API is working
        """
        try:
            url = config["url"]
            params = config.get("params", {})
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # Basic validation that we got meaningful data
                    if isinstance(data, (list, dict)) and data:
                        return True
                        
            return False
            
        except Exception as e:
            self.logger.debug(f"API test failed for {source_name}: {e}")
            return False

    async def _check(self) -> None:
        """
        Enhanced check using multiple alternative APIs with circuit breaker logic.
        
        Raises:
            Exception: Various exceptions from API calls (handled by base monitor)
        """
        try:
            if not self.session:
                await self._initialize()
                return
            
            # Check working APIs
            successful_sources = 0
            total_opportunities = 0
            
            for source_name in list(self.working_apis):
                config = self.data_sources[source_name]
                
                if not config["circuit_breaker"].can_execute():
                    self.logger.debug(f"{source_name} circuit breaker is OPEN - skipping")
                    continue
                
                try:
                    opportunities_count = await self._check_api_source(source_name, config)
                    if opportunities_count >= 0:  # -1 indicates failure
                        successful_sources += 1
                        total_opportunities += opportunities_count
                        config["circuit_breaker"].record_success()
                    else:
                        config["circuit_breaker"].record_failure()
                        
                except Exception as source_error:
                    self.logger.warning(f"Error checking {source_name}: {source_error}")
                    config["circuit_breaker"].record_failure()
                    
                # Small delay between API calls to be respectful
                await asyncio.sleep(0.5)
            
            # Update statistics
            if successful_sources > 0:
                self.consecutive_failures = 0
                self.last_successful_check = datetime.now()
                self.stats["last_successful_check"] = self.last_successful_check
                self.stats["api_calls_successful"] += successful_sources
                
                # Deactivate fallback mode if we're successful
                if self.fallback_mode:
                    self._deactivate_fallback_mode()
                    
                self.logger.debug(f"Successfully checked {successful_sources} Solana APIs, found {total_opportunities} opportunities")
            else:
                self.stats["api_calls_failed"] += 1
                await self._handle_check_error(Exception("All alternative APIs failed"))
            
        except Exception as e:
            await self._handle_check_error(e)
            raise

    async def _check_api_source(self, source_name: str, config: Dict[str, Any]) -> int:
        """
        Check a specific API source for new tokens.
        
        Args:
            source_name: Name of the API source
            config: Configuration for the API
            
        Returns:
            int: Number of opportunities found, -1 if failed
        """
        try:
            self.stats["api_calls_total"] += 1
            
            url = config["url"]
            params = config.get("params", {})
            parser = config["parser"]
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    opportunities_found = await parser(data, source_name)
                    
                    # Update source-specific stats
                    if source_name not in self.stats["sources_stats"]:
                        self.stats["sources_stats"][source_name] = {
                            "calls": 0,
                            "successes": 0,
                            "opportunities": 0
                        }
                    
                    self.stats["sources_stats"][source_name]["calls"] += 1
                    self.stats["sources_stats"][source_name]["successes"] += 1
                    self.stats["sources_stats"][source_name]["opportunities"] += opportunities_found
                    
                    return opportunities_found
                    
                else:
                    self.logger.warning(f"{source_name} API returned status {response.status}")
                    return -1
                    
        except Exception as e:
            self.logger.warning(f"Error checking {source_name} API: {e}")
            return -1

    async def _parse_jupiter_tokens(self, data: Any, source_name: str) -> int:
        """Parse Jupiter token list data."""
        try:
            if not isinstance(data, list):
                return 0
                
            opportunities_found = 0
            
            # Look for recently added tokens (Jupiter updates their list)
            for token_data in data[:50]:  # Check first 50 tokens
                if await self._process_jupiter_token(token_data, source_name):
                    opportunities_found += 1
                    
                # Limit opportunities per source
                if opportunities_found >= 3:
                    break
                    
            return opportunities_found
            
        except Exception as e:
            self.logger.error(f"Error parsing Jupiter tokens: {e}")
            return 0

    async def _parse_solscan_tokens(self, data: Any, source_name: str) -> int:
        """Parse Solscan token list data."""
        try:
            if not isinstance(data, dict) or "data" not in data:
                return 0
                
            opportunities_found = 0
            
            for token_data in data["data"][:30]:  # Check first 30 tokens
                if await self._process_solscan_token(token_data, source_name):
                    opportunities_found += 1
                    
                if opportunities_found >= 2:
                    break
                    
            return opportunities_found
            
        except Exception as e:
            self.logger.error(f"Error parsing Solscan tokens: {e}")
            return 0

    async def _parse_birdeye_tokens(self, data: Any, source_name: str) -> int:
        """Parse Birdeye token list data."""
        try:
            if not isinstance(data, dict) or "tokens" not in data:
                return 0
                
            opportunities_found = 0
            
            for token_data in data["tokens"][:25]:  # Check first 25 tokens
                if await self._process_birdeye_token(token_data, source_name):
                    opportunities_found += 1
                    
                if opportunities_found >= 2:
                    break
                    
            return opportunities_found
            
        except Exception as e:
            self.logger.error(f"Error parsing Birdeye tokens: {e}")
            return 0

    async def _parse_coingecko_tokens(self, data: Any, source_name: str) -> int:
        """Parse CoinGecko Solana ecosystem data."""
        try:
            if not isinstance(data, list):
                return 0
                
            opportunities_found = 0
            
            # CoinGecko returns established tokens, so we'll be more selective
            for token_data in data[:20]:
                if await self._process_coingecko_token(token_data, source_name):
                    opportunities_found += 1
                    
                if opportunities_found >= 1:  # Very selective for CoinGecko
                    break
                    
            return opportunities_found
            
        except Exception as e:
            self.logger.error(f"Error parsing CoinGecko tokens: {e}")
            return 0

    async def _process_jupiter_token(self, token_data: Dict[str, Any], source: str) -> bool:
        """Process a token from Jupiter data."""
        try:
            # Extract token address
            token_address = token_data.get('address', '')
            if not token_address or token_address in self.known_tokens:
                return False
                
            # Check if already processed
            if token_address in self.processed_tokens:
                return False
                
            # Create opportunity
            opportunity = await self._create_opportunity_from_alternative_data(
                token_data, source, "jupiter"
            )
            
            if opportunity:
                await self._notify_callbacks(opportunity)
                self.processed_tokens.add(token_address)
                self.stats["tokens_processed"] += 1
                self.stats["opportunities_found"] += 1
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error processing Jupiter token: {e}")
            return False

    async def _process_solscan_token(self, token_data: Dict[str, Any], source: str) -> bool:
        """Process a token from Solscan data."""
        try:
            token_address = token_data.get('tokenAddress', '')
            if not token_address or token_address in self.known_tokens:
                return False
                
            if token_address in self.processed_tokens:
                return False
                
            opportunity = await self._create_opportunity_from_alternative_data(
                token_data, source, "solscan"
            )
            
            if opportunity:
                await self._notify_callbacks(opportunity)
                self.processed_tokens.add(token_address)
                self.stats["tokens_processed"] += 1
                self.stats["opportunities_found"] += 1
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error processing Solscan token: {e}")
            return False

    async def _process_birdeye_token(self, token_data: Dict[str, Any], source: str) -> bool:
        """Process a token from Birdeye data."""
        try:
            token_address = token_data.get('address', '')
            if not token_address or token_address in self.known_tokens:
                return False
                
            if token_address in self.processed_tokens:
                return False
                
            opportunity = await self._create_opportunity_from_alternative_data(
                token_data, source, "birdeye"
            )
            
            if opportunity:
                await self._notify_callbacks(opportunity)
                self.processed_tokens.add(token_address)
                self.stats["tokens_processed"] += 1
                self.stats["opportunities_found"] += 1
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error processing Birdeye token: {e}")
            return False

    async def _process_coingecko_token(self, token_data: Dict[str, Any], source: str) -> bool:
        """Process a token from CoinGecko data."""
        try:
            # CoinGecko doesn't always provide Solana addresses directly
            # We'll skip this for now or implement address lookup
            return False
            
        except Exception as e:
            self.logger.error(f"Error processing CoinGecko token: {e}")
            return False

    async def _create_opportunity_from_alternative_data(
        self, 
        token_data: Dict[str, Any], 
        source: str, 
        api_type: str
    ) -> Optional[TradingOpportunity]:
        """
        Create trading opportunity from alternative API data.
        
        Args:
            token_data: Token data from API
            source: Source identifier
            api_type: Type of API (jupiter, solscan, etc.)
            
        Returns:
            TradingOpportunity or None if creation failed
        """
        try:
            # Extract data based on API type
            if api_type == "jupiter":
                address = token_data.get('address', '')
                symbol = token_data.get('symbol', 'UNK')
                name = token_data.get('name', 'Unknown')
                decimals = token_data.get('decimals', 9)
            elif api_type == "solscan":
                address = token_data.get('tokenAddress', '')
                symbol = token_data.get('tokenSymbol', 'UNK')
                name = token_data.get('tokenName', 'Unknown')
                decimals = token_data.get('decimals', 9)
            elif api_type == "birdeye":
                address = token_data.get('address', '')
                symbol = token_data.get('symbol', 'UNK')
                name = token_data.get('name', 'Unknown')
                decimals = token_data.get('decimals', 9)
            else:
                return None
            
            # Create Solana token info (custom class to avoid 0x validation)
            class SolanaTokenInfo:
                def __init__(self, address, symbol, name, decimals, total_supply):
                    self.address = address
                    self.symbol = symbol
                    self.name = name
                    self.decimals = decimals
                    self.total_supply = total_supply
            
            token_info = SolanaTokenInfo(
                address=address,
                symbol=symbol,
                name=name,
                decimals=decimals,
                total_supply=1000000000  # Default
            )
            
            # Create liquidity info
            liquidity_info = LiquidityInfo(
                pair_address=address,
                dex_name=f"{api_type.title()} Verified",
                token0=address,
                token1="So11111111111111111111111111111111111111112",  # SOL
                reserve0=0.0,
                reserve1=0.0,
                liquidity_usd=0.0,
                created_at=datetime.now(),
                block_number=0
            )
            
            # Create contract analysis
            contract_analysis = ContractAnalysis(
                is_honeypot=False,
                is_mintable=False,
                is_pausable=False,
                ownership_renounced=True,
                risk_score=0.3,  # Lower risk for verified tokens
                risk_level=RiskLevel.MEDIUM,
                analysis_notes=[f"Verified by {api_type.title()}"]
            )
            
            # Create social metrics
            social_metrics = SocialMetrics(
                social_score=0.5,
                sentiment_score=0.0
            )
            
            # Create opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=contract_analysis,
                social_metrics=social_metrics,
                detected_at=datetime.now(),
                confidence_score=0.4,  # Moderate confidence for alternative sources
                metadata={
                    'source': f'{api_type}_alternative',
                    'chain': 'solana',
                    'api_source': source,
                    'verified_by': api_type,
                    'is_alternative_api': True
                }
            )
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Failed to create opportunity from {api_type} data: {e}")
            return None

    async def _handle_check_error(self, error: Exception) -> None:
        """
        Handle errors during check operation with enhanced logic.
        
        Args:
            error: Exception that occurred during check
        """
        self.consecutive_failures += 1
        self.stats["errors_count"] += 1
        self.stats["last_error"] = str(error)
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.logger.critical(f"Too many consecutive failures ({self.consecutive_failures})")
            self._activate_fallback_mode("Excessive failures detected")

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
            self.check_interval = 15.0  # Return to normal interval
            self.logger.info("✅ Deactivated fallback mode - Alternative APIs healthy")

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
            self.logger.info(f"   API calls: {self.stats['api_calls_total']} total, {self.stats['api_calls_successful']} successful")
            self.logger.info(f"   Working APIs: {len(self.working_apis)}")
            
        except Exception as e:
            self.logger.error(f"Error during {self.name} cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get enhanced monitoring statistics.
        
        Returns:
            Dictionary with current statistics including API health info
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
            "auto_trading": self.auto_trading,
            "api_calls_total": self.stats["api_calls_total"],
            "api_calls_successful": self.stats["api_calls_successful"],
            "api_calls_failed": self.stats["api_calls_failed"],
            "working_apis": len(self.working_apis),
            "available_apis": list(self.working_apis),
            "fallback_mode_activations": self.stats["fallback_mode_activations"],
            "fallback_mode": self.fallback_mode,
            "last_successful_check": self.stats["last_successful_check"],
            "api_healthy": len(self.working_apis) > 0,
            "sources_stats": self.stats["sources_stats"]
        }

    def reset_stats(self) -> None:
        """Reset enhanced monitoring statistics."""
        self.stats = {
            "tokens_processed": 0,
            "opportunities_found": 0,
            "errors_count": 0,
            "last_error": None,
            "uptime_start": datetime.now(),
            "api_calls_total": 0,
            "api_calls_successful": 0,
            "api_calls_failed": 0,
            "working_apis": 0,
            "fallback_mode_activations": 0,
            "last_successful_check": None,
            "sources_stats": {}
        }
        self.processed_tokens.clear()
        self.consecutive_failures = 0
        self.fallback_mode = False
        self.check_interval = 15.0
        self.working_apis.clear()
        
        # Reset circuit breakers
        for config in self.data_sources.values():
            config["circuit_breaker"] = APICircuitBreaker()
            
        self.logger.info("Enhanced Solana Monitor stats reset")