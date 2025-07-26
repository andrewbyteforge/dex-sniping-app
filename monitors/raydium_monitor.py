#!/usr/bin/env python3
"""
Raydium DEX Monitor - Real-time monitoring of Raydium pools and whale movements.

File: monitors/raydium_monitor.py
Purpose: Monitor Raydium for new pools, liquidity events, and whale movements

ISSUE FIXED: Abstract method _initialize_dex implementation was incomplete
SOLUTION: Complete implementation of all abstract methods from DEXMonitor
"""

import asyncio
import aiohttp
import json
import websockets
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from decimal import Decimal

from monitors.dex_monitor import DEXMonitor, PoolEvent, WhaleMovement
from config.raydium_config import get_raydium_config, get_api_url
from models.token import TradingOpportunity, LiquidityInfo, ContractAnalysis, SocialMetrics, RiskLevel
from utils.logger import logger_manager


class RaydiumMonitor(DEXMonitor):
    """
    Raydium DEX monitor for real-time pool and whale tracking.
    Implements all abstract methods from DEXMonitor base class.
    """
    
    def __init__(self, check_interval: float = 10.0) -> None:
        """
        Initialize Raydium monitor.
        
        Args:
            check_interval: Seconds between monitoring checks
        """
        config = get_raydium_config()
        super().__init__(
            dex_name="Raydium",
            check_interval=check_interval,
            whale_threshold_usd=config.monitoring.whale_threshold_usd
        )
        
        self.config = config
        self.websocket_connection: Optional[websockets.WebSocketServerProtocol] = None
        self.last_pool_check = datetime.now() - timedelta(hours=1)
        self.known_pools: Set[str] = set()
        
        # Rate limiting
        self.last_request_time = datetime.now()
        self.request_count = 0
        
        # Enhanced tracking
        self.pool_cache: Dict[str, Dict[str, Any]] = {}
        self.whale_wallets: Set[str] = set()

    async def _initialize_dex(self) -> None:
        """
        Initialize Raydium-specific components.
        
        This method implements the abstract method from DEXMonitor.
        It sets up Raydium-specific configuration, API connections, and baseline data.
        
        Raises:
            Exception: If initialization fails for any critical component
        """
        try:
            self.logger.info("🔧 Initializing Raydium DEX components...")
            
            # Validate configuration
            if not self.config:
                raise ValueError("Raydium configuration not loaded")
            
            # Load existing pools to establish baseline
            await self._load_existing_pools()
            
            # Initialize WebSocket connection if enabled
            if self.config.websocket.enabled:
                await self._initialize_websocket()
            
            # Initialize whale wallet tracking if configured
            await self._initialize_whale_tracking()
            
            self.logger.info(f"✅ Raydium initialization complete")
            self.logger.info(f"   📊 Baseline pools loaded: {len(self.known_pools)}")
            self.logger.info(f"   🔌 WebSocket: {'✅ Enabled' if self.config.websocket.enabled else '❌ Disabled'}")
            self.logger.info(f"   🐋 Whale wallets tracked: {len(self.whale_wallets)}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Raydium components: {e}")
            raise

    async def _load_existing_pools(self) -> None:
        """
        Load existing pools to establish a baseline for new pool detection.
        
        This method fetches the current pool list from Raydium API to establish
        what pools already exist, so we can detect truly new pools later.
        
        Raises:
            Exception: If unable to load pool data from API
        """
        try:
            self.logger.info("📊 Loading existing Raydium pools...")
            
            if not self.session:
                raise RuntimeError("HTTP session not initialized")
            
            url = get_api_url(self.config.endpoints.pairs)
            
            await self._rate_limit_check()
            
            async with self.session.get(url) as response:
                self.stats["api_calls_total"] += 1
                
                if response.status == 200:
                    data = await response.json()
                    self.stats["api_calls_successful"] += 1
                    
                    if isinstance(data, list):
                        for pool in data:
                            pool_id = pool.get('id', '')
                            if pool_id:
                                self.known_pools.add(pool_id)
                                self.pool_cache[pool_id] = pool
                    
                    self.logger.info(f"📊 Loaded {len(self.known_pools)} existing pools")
                    
                else:
                    self.stats["api_calls_failed"] += 1
                    error_msg = f"Failed to load existing pools: HTTP {response.status}"
                    self.logger.warning(f"⚠️  {error_msg}")
                    
                    # Don't raise exception for this - we can continue without baseline
                    if response.status >= 500:
                        # Server error - might be temporary
                        self.logger.warning("Server error detected, continuing with empty baseline")
                    elif response.status == 429:
                        # Rate limited - wait and retry once
                        self.logger.info("Rate limited, waiting 60s and retrying...")
                        await asyncio.sleep(60)
                        await self._load_existing_pools()  # Recursive retry
                        return
                    
        except Exception as e:
            self.logger.error(f"💥 Error loading existing pools: {e}")
            self.stats["api_calls_failed"] += 1
            # Don't raise - we can operate without baseline data

    async def _initialize_websocket(self) -> None:
        """
        Initialize WebSocket connection for real-time data.
        
        This method sets up a WebSocket connection to Raydium's real-time API
        for instant notifications of new pools and trading activity.
        
        Note: Currently implements polling fallback as WebSocket details may vary.
        """
        try:
            self.logger.info("🔌 Initializing Raydium WebSocket connection...")
            
            # TODO: Implement actual WebSocket connection
            # Note: This would connect to Raydium's WebSocket API for real-time events
            # Implementation depends on Raydium's specific WebSocket protocol
            
            # For now, we'll rely on polling mode
            self.logger.info("⏭️  WebSocket implementation pending - using polling mode")
            
            # Mark WebSocket as disabled in config to avoid confusion
            self.config.websocket.enabled = False
            
        except Exception as e:
            self.logger.error(f"💥 Error initializing WebSocket: {e}")
            self.config.websocket.enabled = False

    async def _initialize_whale_tracking(self) -> None:
        """
        Initialize whale wallet tracking system.
        
        This method sets up tracking for known whale wallets and large traders
        to monitor their activity across Raydium pools.
        """
        try:
            self.logger.info("🐋 Initializing whale tracking...")
            
            # TODO: Load known whale wallets from configuration or database
            # For now, we'll start with an empty set and build it dynamically
            
            # Example whale wallets (would come from config in production)
            example_whales = {
                # "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",  # Example Solana whale
                # Add more known whale addresses here
            }
            
            self.whale_wallets.update(example_whales)
            self.logger.info(f"🐋 Whale tracking initialized with {len(self.whale_wallets)} wallets")
            
        except Exception as e:
            self.logger.error(f"💥 Error initializing whale tracking: {e}")

    async def _rate_limit_check(self) -> None:
        """
        Ensure we don't exceed Raydium API rate limits.
        
        This method implements intelligent rate limiting to avoid being blocked
        by the Raydium API. It tracks request frequency and adds delays as needed.
        """
        try:
            now = datetime.now()
            time_since_last = (now - self.last_request_time).total_seconds()
            
            # Reset counter if more than a minute has passed
            if time_since_last >= 60:
                self.request_count = 0
                self.last_request_time = now
            
            # Check requests per second limit
            if time_since_last < 1.0 / self.config.rate_limits.requests_per_second:
                wait_time = 1.0 / self.config.rate_limits.requests_per_second - time_since_last
                await asyncio.sleep(wait_time)
            
            # Check requests per minute limit
            if self.request_count >= self.config.rate_limits.requests_per_minute:
                wait_time = 60 - time_since_last
                if wait_time > 0:
                    self.logger.debug(f"⏰ Rate limit reached, waiting {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                    self.request_count = 0
            
            self.request_count += 1
            self.last_request_time = datetime.now()
            
        except Exception as e:
            self.logger.error(f"💥 Error in rate limit check: {e}")

    async def _fetch_new_pools(self) -> List[PoolEvent]:
        """
        Fetch new pool creation events from Raydium.
        
        This method implements the abstract method from DEXMonitor.
        It checks for pools that weren't in our baseline and creates PoolEvent objects.
        
        Returns:
            List[PoolEvent]: List of new pool creation events
            
        Raises:
            Exception: If API request fails catastrophically
        """
        try:
            new_events = []
            
            if not self.session:
                self.logger.warning("Session not available, skipping pool fetch")
                return new_events
            
            # Get current pools from Raydium API
            url = get_api_url(self.config.endpoints.pairs)
            
            await self._rate_limit_check()
            
            async with self.session.get(url) as response:
                self.stats["api_calls_total"] += 1
                
                if response.status == 200:
                    data = await response.json()
                    self.stats["api_calls_successful"] += 1
                    
                    if isinstance(data, list):
                        for pool in data:
                            pool_id = pool.get('id', '')
                            
                            # Check if this is a new pool
                            if pool_id and pool_id not in self.known_pools:
                                
                                # Check if we should monitor this pool based on criteria
                                if self._should_monitor_pool(pool):
                                    event = await self._create_pool_event(pool)
                                    if event:
                                        new_events.append(event)
                                        self.known_pools.add(pool_id)
                                        self.pool_cache[pool_id] = pool
                                        
                                        self.logger.info(f"🆕 New pool discovered: {pool_id}")
                                        self.logger.info(f"   💰 Liquidity: ${pool.get('liquidity', {}).get('usd', 0):,.0f}")
                                        self.logger.info(f"   📊 Volume 24h: ${pool.get('volume24h', 0):,.0f}")
                                else:
                                    # Add to known pools even if not monitoring
                                    self.known_pools.add(pool_id)
                
                elif response.status == 429:
                    # Rate limited
                    self.stats["api_calls_failed"] += 1
                    self.logger.warning("⚠️  Rate limited by Raydium API")
                    await asyncio.sleep(30)  # Wait 30 seconds
                    
                else:
                    self.stats["api_calls_failed"] += 1
                    self.logger.warning(f"⚠️  Failed to fetch pools: HTTP {response.status}")
            
            return new_events
            
        except Exception as e:
            self.logger.error(f"💥 Error fetching new pools: {e}")
            self.stats["api_calls_failed"] += 1
            return []

    def _should_monitor_pool(self, pool_data: Dict[str, Any]) -> bool:
        """
        Determine if a pool meets our monitoring criteria.
        
        Args:
            pool_data: Pool data from Raydium API
            
        Returns:
            bool: True if pool should be monitored
        """
        try:
            # Check liquidity requirements
            liquidity_usd = pool_data.get('liquidity', {}).get('usd', 0)
            if liquidity_usd < self.config.monitoring.min_liquidity_usd:
                return False
            if liquidity_usd > self.config.monitoring.max_liquidity_usd:
                return False
            
            # Check quote token (prefer SOL, USDC, USDT)
            quote_symbol = pool_data.get('quoteSymbol', '').upper()
            if quote_symbol not in self.config.monitoring.supported_quote_tokens:
                return False
            
            # Check that base token is not in excluded list
            base_symbol = pool_data.get('baseSymbol', '').upper()
            if base_symbol in self.config.monitoring.excluded_base_tokens:
                return False
            
            # Check minimum trading activity
            volume_24h = pool_data.get('volume24h', 0)
            if volume_24h < (liquidity_usd * 0.1):  # At least 10% of liquidity in 24h volume
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"💥 Error evaluating pool criteria: {e}")
            return False

    async def _create_pool_event(self, pool_data: Dict[str, Any]) -> Optional[PoolEvent]:
        """
        Create a PoolEvent from Raydium pool data.
        
        Args:
            pool_data: Raw pool data from Raydium API
            
        Returns:
            Optional[PoolEvent]: Created pool event or None if invalid
        """
        try:
            pool_id = pool_data.get('id', '')
            base_mint = pool_data.get('baseMint', '')
            quote_mint = pool_data.get('quoteMint', '')
            
            if not all([pool_id, base_mint, quote_mint]):
                self.logger.warning(f"Incomplete pool data for {pool_id}")
                return None
            
            # Extract event data
            event_data = {
                'pool_id': pool_id,
                'base_token_symbol': pool_data.get('baseSymbol', 'UNKNOWN'),
                'quote_token_symbol': pool_data.get('quoteSymbol', 'UNKNOWN'),
                'initial_liquidity_usd': pool_data.get('liquidity', {}).get('usd', 0),
                'volume_24h': pool_data.get('volume24h', 0),
                'price_usd': pool_data.get('price', 0),
                'market_cap': pool_data.get('marketCap', 0),
                'dex': 'Raydium',
                'pool_data': pool_data,
                'creation_time': datetime.now().isoformat()
            }
            
            event = PoolEvent(
                event_type="pool_creation",
                pool_address=pool_id,
                base_token=base_mint,
                quote_token=quote_mint,
                timestamp=datetime.now(),
                data=event_data
            )
            
            return event
            
        except Exception as e:
            self.logger.error(f"💥 Error creating pool event: {e}")
            return None

    async def _fetch_whale_movements(self) -> List[WhaleMovement]:
        """
        Fetch whale movements from Raydium data.
        
        This method implements the abstract method from DEXMonitor.
        It analyzes large liquidity changes and trading activity to detect whale movements.
        
        Returns:
            List[WhaleMovement]: List of detected whale movements
        """
        try:
            whale_movements = []
            
            # Analyze liquidity changes in monitored pools
            for pool_id in list(self.monitored_pools):
                if pool_id in self.pool_cache:
                    # Check for significant liquidity changes
                    movement = await self._check_pool_liquidity_changes(pool_id)
                    if movement:
                        whale_movements.append(movement)
            
            # TODO: Implement transaction-level whale tracking
            # This would involve:
            # 1. Monitoring large individual transactions
            # 2. Tracking specific whale wallet addresses
            # 3. Analyzing trading patterns for whale behavior
            
            return whale_movements
            
        except Exception as e:
            self.logger.error(f"💥 Error fetching whale movements: {e}")
            return []

    async def _check_pool_liquidity_changes(self, pool_id: str) -> Optional[WhaleMovement]:
        """
        Check for significant liquidity changes in a specific pool.
        
        Args:
            pool_id: The pool ID to check
            
        Returns:
            Optional[WhaleMovement]: Whale movement if detected, None otherwise
        """
        try:
            if not self.session:
                return None
            
            # Get current pool data
            url = get_api_url(f"{self.config.endpoints.info}?ids={pool_id}")
            
            await self._rate_limit_check()
            
            async with self.session.get(url) as response:
                self.stats["api_calls_total"] += 1
                
                if response.status == 200:
                    data = await response.json()
                    self.stats["api_calls_successful"] += 1
                    
                    if isinstance(data, list) and len(data) > 0:
                        current_pool = data[0]
                        cached_pool = self.pool_cache.get(pool_id, {})
                        
                        current_liquidity = current_pool.get('liquidity', {}).get('usd', 0)
                        cached_liquidity = cached_pool.get('liquidity', {}).get('usd', 0)
                        
                        if cached_liquidity > 0:
                            liquidity_change = current_liquidity - cached_liquidity
                            change_percent = abs(liquidity_change) / cached_liquidity
                            
                            # Detect significant changes (>10% and >whale threshold)
                            if (change_percent > 0.1 and 
                                abs(liquidity_change) >= self.whale_threshold_usd):
                                
                                movement_type = "add_liquidity" if liquidity_change > 0 else "remove_liquidity"
                                
                                # Update cache
                                self.pool_cache[pool_id] = current_pool
                                
                                return WhaleMovement(
                                    wallet_address="unknown",  # Would need transaction data for actual wallet
                                    movement_type=movement_type,
                                    token_address=current_pool.get('baseMint', ''),
                                    amount_usd=abs(liquidity_change),
                                    timestamp=datetime.now(),
                                    pool_address=pool_id
                                )
                        
                        # Update cache even if no significant change
                        self.pool_cache[pool_id] = current_pool
                
                else:
                    self.stats["api_calls_failed"] += 1
            
            return None
            
        except Exception as e:
            self.logger.error(f"💥 Error checking liquidity changes for {pool_id}: {e}")
            return None

    async def _fetch_pool_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed data for a specific pool.
        
        This method implements the abstract method from DEXMonitor.
        It retrieves comprehensive pool information including liquidity, volume, and pricing.
        
        Args:
            pool_address: The pool address/ID to fetch data for
            
        Returns:
            Optional[Dict[str, Any]]: Pool data or None if not found/error
        """
        try:
            if not self.session:
                self.logger.warning("Session not available for pool data fetch")
                return None
            
            # Check cache first
            if pool_address in self.pool_cache:
                cached_data = self.pool_cache[pool_address]
                # Return cached data if less than 5 minutes old
                if 'last_updated' in cached_data:
                    last_update = datetime.fromisoformat(cached_data['last_updated'])
                    if (datetime.now() - last_update).total_seconds() < 300:
                        return cached_data
            
            # Fetch fresh data from API
            url = get_api_url(f"{self.config.endpoints.info}?ids={pool_address}")
            
            await self._rate_limit_check()
            
            async with self.session.get(url) as response:
                self.stats["api_calls_total"] += 1
                
                if response.status == 200:
                    data = await response.json()
                    self.stats["api_calls_successful"] += 1
                    
                    if isinstance(data, list) and len(data) > 0:
                        pool_data = data[0]
                        
                        # Add timestamp and cache
                        pool_data['last_updated'] = datetime.now().isoformat()
                        self.pool_cache[pool_address] = pool_data
                        
                        return pool_data
                    else:
                        self.logger.warning(f"No data returned for pool {pool_address}")
                        return None
                        
                elif response.status == 404:
                    self.logger.warning(f"Pool {pool_address} not found")
                    return None
                    
                else:
                    self.stats["api_calls_failed"] += 1
                    self.logger.warning(f"Failed to fetch pool data: HTTP {response.status}")
                    return None
            
        except Exception as e:
            self.logger.error(f"💥 Error fetching pool data for {pool_address}: {e}")
            self.stats["api_calls_failed"] += 1
            return None

    def get_monitored_pools_summary(self) -> Dict[str, Any]:
        """
        Get summary of currently monitored pools.
        
        Returns:
            Dict[str, Any]: Summary statistics of monitored pools
        """
        try:
            total_pools = len(self.monitored_pools)
            total_liquidity = 0
            total_volume_24h = 0
            
            for pool_id in self.monitored_pools:
                if pool_id in self.pool_cache:
                    pool_data = self.pool_cache[pool_id]
                    total_liquidity += pool_data.get('liquidity', {}).get('usd', 0)
                    total_volume_24h += pool_data.get('volume24h', 0)
            
            return {
                'total_pools': total_pools,
                'total_liquidity_usd': total_liquidity,
                'total_volume_24h_usd': total_volume_24h,
                'avg_liquidity_per_pool': total_liquidity / max(total_pools, 1),
                'cached_pools': len(self.pool_cache),
                'known_pools_baseline': len(self.known_pools)
            }
            
        except Exception as e:
            self.logger.error(f"💥 Error generating pool summary: {e}")
            return {
                'total_pools': len(self.monitored_pools),
                'error': str(e)
            }

    async def cleanup(self) -> None:
        """
        Clean up Raydium monitor resources.
        
        This method properly closes connections and saves state before shutdown.
        """
        try:
            self.logger.info("🧹 Cleaning up Raydium Monitor...")
            
            # Close WebSocket connection if open
            if self.websocket_connection:
                await self.websocket_connection.close()
                self.websocket_connection = None
            
            # Parent cleanup handles session closure
            await super()._cleanup()
            
            self.logger.info("✅ Raydium Monitor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"💥 Error during Raydium cleanup: {e}")