#!/usr/bin/env python3
"""
Raydium DEX Monitor - Real-time monitoring of Raydium pools and whale movements.

File: monitors/raydium_monitor.py
Purpose: Monitor Raydium for new pools, liquidity events, and whale movements
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
    """
    
    def __init__(self, check_interval: float = 10.0) -> None:
        """Initialize Raydium monitor."""
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

    async def initialize(self) -> bool:
        """Initialize the Raydium monitor with full setup."""
        try:
            self.logger.info("🔧 Initializing Raydium DEX Monitor...")
            
            # Initialize HTTP session
            await self._initialize_session()
            
            # Initialize DEX-specific components
            await self._initialize_dex()
            
            self.logger.info("✅ Raydium DEX Monitor initialized successfully")
            self.logger.info(f"   🐋 Whale threshold: ${self.whale_threshold_usd:,.0f}")
            self.logger.info(f"   ⏱️ Check interval: {self.check_interval}s")
            self.logger.info(f"   📊 Known pools baseline: {len(self.known_pools)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Raydium DEX Monitor: {e}")
            self.stats["errors_count"] += 1
            self.stats["last_error"] = str(e)
            return False
        """Initialize Raydium-specific components."""
        try:
            self.logger.info("🔧 Initializing Raydium DEX components...")
            
            # Load existing pools to establish baseline
            await self._load_existing_pools()
            
            # Initialize WebSocket connection if enabled
            if self.config.websocket.enabled:
                await self._initialize_websocket()
            
            self.logger.info(f"✅ Raydium initialization complete")
            self.logger.info(f"   📊 Baseline pools loaded: {len(self.known_pools)}")
            self.logger.info(f"   🔌 WebSocket: {'✅ Enabled' if self.config.websocket.enabled else '❌ Disabled'}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Raydium components: {e}")
            raise

    async def _load_existing_pools(self) -> None:
        """Load existing pools to establish a baseline."""
        try:
            self.logger.info("📊 Loading existing Raydium pools...")
            
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
                    self.logger.warning(f"⚠️  Failed to load existing pools: HTTP {response.status}")
                    
        except Exception as e:
            self.logger.error(f"💥 Error loading existing pools: {e}")
            self.stats["api_calls_failed"] += 1

    async def _initialize_websocket(self) -> None:
        """Initialize WebSocket connection for real-time data."""
        try:
            self.logger.info("🔌 Initializing Raydium WebSocket connection...")
            
            # TODO: Implement WebSocket connection
            # Note: This would connect to Raydium's WebSocket API for real-time events
            # For now, we'll rely on polling
            
            self.logger.info("⏭️  WebSocket implementation pending - using polling mode")
            
        except Exception as e:
            self.logger.error(f"💥 Error initializing WebSocket: {e}")

    async def _rate_limit_check(self) -> None:
        """Ensure we don't exceed rate limits."""
        now = datetime.now()
        time_since_last = (now - self.last_request_time).total_seconds()
        
        # Reset counter if more than a minute has passed
        if time_since_last >= 60:
            self.request_count = 0
        
        # Check if we need to wait
        if self.request_count >= self.config.rate_limits.requests_per_minute:
            wait_time = 60 - time_since_last
            if wait_time > 0:
                self.logger.debug(f"⏰ Rate limit reached, waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
                self.request_count = 0
        
        self.request_count += 1
        self.last_request_time = now

    async def _fetch_new_pools(self) -> List[PoolEvent]:
        """Fetch new pool creation events from Raydium."""
        try:
            new_events = []
            
            # Get current pools
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
                                
                                # Check if we should monitor this pool
                                if self.config.should_monitor_pool(pool):
                                    event = await self._create_pool_event(pool)
                                    if event:
                                        new_events.append(event)
                                        self.known_pools.add(pool_id)
                                        self.pool_cache[pool_id] = pool
                                        
                                        self.logger.info(f"🆕 New pool discovered: {pool_id}")
                                        self.logger.info(f"   💰 Liquidity: ${pool.get('liquidity', {}).get('usd', 0):,.0f}")
                                        self.logger.info(f"   📊 Volume 24h: ${pool.get('volume24h', 0):,.0f}")
                
                else:
                    self.stats["api_calls_failed"] += 1
                    self.logger.warning(f"⚠️  Failed to fetch pools: HTTP {response.status}")
            
            return new_events
            
        except Exception as e:
            self.logger.error(f"💥 Error fetching new pools: {e}")
            self.stats["api_calls_failed"] += 1
            return []

    async def _create_pool_event(self, pool_data: Dict[str, Any]) -> Optional[PoolEvent]:
        """Create a PoolEvent from Raydium pool data."""
        try:
            pool_id = pool_data.get('id', '')
            base_mint = pool_data.get('baseMint', '')
            quote_mint = pool_data.get('quoteMint', '')
            
            if not all([pool_id, base_mint, quote_mint]):
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
                'priority_score': self.config.get_pool_priority_score(pool_data)
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
        """Fetch whale movements from Raydium data."""
        try:
            whale_movements = []
            
            # For now, we'll analyze large liquidity changes in monitored pools
            # In a full implementation, this would track individual transactions
            
            for pool_id in list(self.monitored_pools):
                if pool_id in self.pool_cache:
                    # Check for significant liquidity changes
                    movement = await self._check_pool_liquidity_changes(pool_id)
                    if movement:
                        whale_movements.append(movement)
            
            return whale_movements
            
        except Exception as e:
            self.logger.error(f"💥 Error fetching whale movements: {e}")
            return []

    async def _check_pool_liquidity_changes(self, pool_id: str) -> Optional[WhaleMovement]:
        """Check for significant liquidity changes in a pool."""
        try:
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
                                    wallet_address="unknown",  # Would need transaction data
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
        """Fetch detailed data for a specific pool."""
        try:
            url = get_api_url(f"{self.config.endpoints.info}?ids={pool_address}")
            
            await self._rate_limit_check()
            
            async with self.session.get(url) as response:
                self.stats["api_calls_total"] += 1
                
                if response.status == 200:
                    data = await response.json()
                    self.stats["api_calls_successful"] += 1
                    
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]
                
                else:
                    self.stats["api_calls_failed"] += 1
                    self.logger.warning(f"⚠️  Failed to fetch pool data for {pool_address}: HTTP {response.status}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"💥 Error fetching pool data for {pool_address}: {e}")
            self.stats["api_calls_failed"] += 1
            return None

    async def _create_opportunity_from_event(self, event: PoolEvent) -> None:
        """Create a trading opportunity from a Raydium pool event."""
        try:
            self.logger.info(f"🎯 Creating Raydium opportunity from pool: {event.pool_address}")
            
            pool_data = event.data.get('pool_data', {})
            
            # Create token info
            class RaydiumTokenInfo:
                def __init__(self, pool_data, event_data):
                    self.address = event_data.get('base_token', '')
                    self.symbol = event_data.get('base_token_symbol', 'UNKNOWN')
                    self.name = f"Raydium {self.symbol}"
                    self.decimals = pool_data.get('baseDecimals', 9)
                    self.total_supply = pool_data.get('baseReserve', 0)
            
            token_info = RaydiumTokenInfo(pool_data, event.data)
            
            # Create liquidity info
            liquidity_info = LiquidityInfo(
                pair_address=event.pool_address,
                dex_name="Raydium",
                token0=event.base_token,
                token1=event.quote_token,
                reserve0=float(pool_data.get('baseReserve', 0)),
                reserve1=float(pool_data.get('quoteReserve', 0)),
                liquidity_usd=float(event.data.get('initial_liquidity_usd', 0)),
                created_at=event.timestamp,
                block_number=0  # Would need block data
            )
            
            # Create contract analysis (conservative for new pools)
            contract_analysis = ContractAnalysis(
                is_honeypot=False,  # Unknown for new pools
                is_mintable=True,   # Assume true until verified
                is_pausable=True,   # Assume true until verified
                ownership_renounced=False,  # Unknown for new pools
                risk_score=0.4,  # Higher risk for new pools
                risk_level=RiskLevel.MEDIUM,
                analysis_notes=[
                    f"New Raydium pool detected",
                    f"Liquidity: ${event.data.get('initial_liquidity_usd', 0):,.0f}",
                    f"Volume 24h: ${event.data.get('volume_24h', 0):,.0f}"
                ]
            )
            
            # Create social metrics (basic for new pools)
            social_metrics = SocialMetrics(
                social_score=0.5,  # Neutral for new pools
                sentiment_score=0.0
            )
            
            # Create opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=contract_analysis,
                social_metrics=social_metrics,
                detected_at=event.timestamp,
                confidence_score=min(0.8, event.data.get('priority_score', 0.5) + 0.3),
                metadata={
                    'source': 'raydium_monitor',
                    'chain': 'solana',
                    'dex': 'Raydium',
                    'pool_id': event.pool_address,
                    'detection_method': 'new_pool_creation',
                    'is_new_pool': True,
                    'recommendation': {
                        'action': 'MONITOR_CLOSELY',
                        'confidence': 'HIGH' if event.data.get('priority_score', 0) > 0.7 else 'MEDIUM',
                        'reasoning': f"New Raydium pool with ${event.data.get('initial_liquidity_usd', 0):,.0f} liquidity"
                    },
                    'raydium_data': {
                        'pool_id': event.pool_address,
                        'liquidity_usd': event.data.get('initial_liquidity_usd', 0),
                        'volume_24h': event.data.get('volume_24h', 0),
                        'market_cap': event.data.get('market_cap', 0),
                        'price_usd': event.data.get('price_usd', 0),
                        'priority_score': event.data.get('priority_score', 0),
                        'detection_timestamp': event.timestamp.isoformat()
                    },
                    'trading_score': {
                        'overall_score': min(0.8, event.data.get('priority_score', 0.5) + 0.3),
                        'liquidity_score': min(1.0, event.data.get('initial_liquidity_usd', 0) / 50000),
                        'volume_score': min(1.0, event.data.get('volume_24h', 0) / 100000),
                        'newness_bonus': 0.2,  # Bonus for being a new pool
                        'source_reliability': 0.9  # Raydium is reliable
                    }
                }
            )
            
            # Notify callbacks
            await self._notify_callbacks(opportunity)
            
            self.logger.info(f"✅ Raydium opportunity created for {token_info.symbol}")
            self.logger.info(f"   💰 Liquidity: ${event.data.get('initial_liquidity_usd', 0):,.0f}")
            self.logger.info(f"   📊 Confidence: {opportunity.confidence_score:.3f}")
            self.logger.info(f"   🎯 Priority: {event.data.get('priority_score', 0):.3f}")
            
        except Exception as e:
            self.logger.error(f"💥 Error creating opportunity from Raydium event: {e}")
            import traceback
            self.logger.debug(f"Opportunity creation traceback: {traceback.format_exc()}")

    def get_monitored_pools_summary(self) -> Dict[str, Any]:
        """Get summary of currently monitored pools."""
        return {
            "total_pools": len(self.monitored_pools),
            "known_pools": len(self.known_pools),
            "cached_pools": len(self.pool_cache),
            "recent_events": len([e for e in self.recent_events if e.event_type == "pool_creation"]),
            "whale_movements": len(self.whale_movements),
            "top_pools_by_liquidity": self._get_top_pools_by_liquidity(5)
        }

    def _get_top_pools_by_liquidity(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top pools by liquidity from cache."""
        pools_with_liquidity = [
            {
                "pool_id": pool_id,
                "liquidity_usd": pool_data.get('liquidity', {}).get('usd', 0),
                "symbol": f"{pool_data.get('baseSymbol', 'UNKNOWN')}/{pool_data.get('quoteSymbol', 'UNKNOWN')}",
                "volume_24h": pool_data.get('volume24h', 0)
            }
            for pool_id, pool_data in self.pool_cache.items()
        ]
        
        # Sort by liquidity descending
        pools_with_liquidity.sort(key=lambda x: x['liquidity_usd'], reverse=True)
        
        return pools_with_liquidity[:limit]