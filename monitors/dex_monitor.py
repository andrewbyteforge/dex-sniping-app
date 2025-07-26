#!/usr/bin/env python3
"""
Base DEX Monitor class for Solana DEX integrations.

File: monitors/dex_monitor.py
Purpose: Base class for all DEX monitors (Raydium, Orca, etc.)
"""

import asyncio
import aiohttp
import json
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from decimal import Decimal

from monitors.base_monitor import BaseMonitor
from utils.logger import logger_manager


class PoolEvent:
    """Represents a DEX pool event (creation, liquidity change, etc.)"""
    
    def __init__(
        self,
        event_type: str,
        pool_address: str,
        base_token: str,
        quote_token: str,
        timestamp: datetime,
        data: Dict[str, Any]
    ) -> None:
        """
        Initialize pool event.
        
        Args:
            event_type: Type of event (creation, liquidity_add, liquidity_remove, swap)
            pool_address: Address of the liquidity pool
            base_token: Base token address
            quote_token: Quote token address
            timestamp: When the event occurred
            data: Additional event data
        """
        self.event_type = event_type
        self.pool_address = pool_address
        self.base_token = base_token
        self.quote_token = quote_token
        self.timestamp = timestamp
        self.data = data
        self.processed = False

    def is_whale_event(self, threshold_usd: float = 10000.0) -> bool:
        """Check if this is a whale-sized event."""
        amount_usd = self.data.get('amount_usd', 0)
        return amount_usd >= threshold_usd

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'event_type': self.event_type,
            'pool_address': self.pool_address,
            'base_token': self.base_token,
            'quote_token': self.quote_token,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'processed': self.processed
        }


class WhaleMovement:
    """Represents a significant whale movement."""
    
    def __init__(
        self,
        wallet_address: str,
        movement_type: str,
        token_address: str,
        amount_usd: float,
        timestamp: datetime,
        pool_address: Optional[str] = None
    ) -> None:
        """
        Initialize whale movement.
        
        Args:
            wallet_address: Wallet that made the movement
            movement_type: Type of movement (buy, sell, add_liquidity, remove_liquidity)
            token_address: Token being moved
            amount_usd: USD value of the movement
            timestamp: When the movement occurred
            pool_address: Associated pool if applicable
        """
        self.wallet_address = wallet_address
        self.movement_type = movement_type
        self.token_address = token_address
        self.amount_usd = amount_usd
        self.timestamp = timestamp
        self.pool_address = pool_address

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'wallet_address': self.wallet_address,
            'movement_type': self.movement_type,
            'token_address': self.token_address,
            'amount_usd': self.amount_usd,
            'timestamp': self.timestamp.isoformat(),
            'pool_address': self.pool_address
        }


class DEXMonitor(BaseMonitor):
    """
    Base class for DEX monitors - implements BaseMonitor abstract methods.
    Provides common functionality for monitoring DEX events, pools, and whale movements.
    """
    
    def __init__(
        self,
        dex_name: str,
        check_interval: float = 10.0,
        whale_threshold_usd: float = 10000.0
    ) -> None:
        """
        Initialize DEX monitor.
        
        Args:
            dex_name: Name of the DEX (e.g., "Raydium", "Orca")
            check_interval: How often to check for new events
            whale_threshold_usd: Minimum USD value to consider a whale movement
        """
        super().__init__(f"{dex_name}_DEX", check_interval)
        self.dex_name = dex_name
        self.whale_threshold_usd = whale_threshold_usd
        
        # Event tracking
        self.recent_events: List[PoolEvent] = []
        self.whale_movements: List[WhaleMovement] = []
        self.monitored_pools: Set[str] = set()
        self.processed_pools: Set[str] = set()
        
        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Statistics
        self.stats = {
            "pools_discovered": 0,
            "whale_movements_detected": 0,
            "events_processed": 0,
            "api_calls_total": 0,
            "api_calls_successful": 0,
            "api_calls_failed": 0,
            "last_pool_creation": None,
            "last_whale_movement": None,
            "uptime_start": datetime.now(),
            "errors_count": 0,
            "last_error": None
        }

    async def _initialize(self) -> None:
        """Initialize the DEX monitor (implements BaseMonitor abstract method)."""
        try:
            self.logger.info(f"🔧 Initializing {self.dex_name} DEX Monitor...")
            
            # Initialize HTTP session
            await self._initialize_session()
            
            # Initialize DEX-specific components
            await self._initialize_dex()
            
            self.logger.info(f"✅ {self.dex_name} DEX Monitor initialized successfully")
            self.logger.info(f"   🐋 Whale threshold: ${self.whale_threshold_usd:,.0f}")
            self.logger.info(f"   ⏱️  Check interval: {self.check_interval}s")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize {self.dex_name} DEX Monitor: {e}")
            self.stats["errors_count"] += 1
            self.stats["last_error"] = str(e)
            raise

    async def initialize(self) -> bool:
        """Public initialize method for external calling."""
        try:
            await self._initialize()
            return True
        except Exception:
            return False

    async def _initialize_session(self) -> None:
        """Initialize HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'User-Agent': 'DEX-Sniping-Bot/1.0',
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip, deflate'
            }
        )

    @abstractmethod
    async def _initialize_dex(self) -> None:
        """Initialize DEX-specific components. Override in subclasses."""
        pass

    @abstractmethod
    async def _fetch_new_pools(self) -> List[PoolEvent]:
        """Fetch new pool creation events. Override in subclasses."""
        pass

    @abstractmethod
    async def _fetch_whale_movements(self) -> List[WhaleMovement]:
        """Fetch recent whale movements. Override in subclasses."""
        pass

    @abstractmethod
    async def _fetch_pool_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed data for a specific pool. Override in subclasses."""
        pass

    async def _check(self) -> None:
        """Main check method - monitors for new events (implements BaseMonitor abstract method)."""
        try:
            self.logger.debug(f"🔍 Checking {self.dex_name} for new events...")
            
            # Fetch new pool events
            new_pools = await self._fetch_new_pools()
            if new_pools:
                await self._process_pool_events(new_pools)
            
            # Fetch whale movements
            whale_movements = await self._fetch_whale_movements()
            if whale_movements:
                await self._process_whale_movements(whale_movements)
            
            # Clean up old events
            await self._cleanup_old_events()
            
            self.logger.debug(f"✅ {self.dex_name} check completed")
            
        except Exception as e:
            self.logger.error(f"💥 Error during {self.dex_name} check: {e}")
            self.stats["errors_count"] += 1
            self.stats["last_error"] = str(e)
            raise

    async def _process_pool_events(self, events: List[PoolEvent]) -> None:
        """Process new pool events."""
        for event in events:
            try:
                if event.pool_address not in self.processed_pools:
                    self.logger.info(f"🆕 New {event.event_type} event: {event.pool_address}")
                    
                    # Add to monitoring
                    self.monitored_pools.add(event.pool_address)
                    self.recent_events.append(event)
                    self.processed_pools.add(event.pool_address)
                    
                    # Update stats
                    self.stats["pools_discovered"] += 1
                    self.stats["events_processed"] += 1
                    
                    if event.event_type == "pool_creation":
                        self.stats["last_pool_creation"] = datetime.now().isoformat()
                    
                    # Notify callbacks if this looks promising
                    if await self._is_promising_event(event):
                        await self._create_opportunity_from_event(event)
                    
            except Exception as e:
                self.logger.error(f"💥 Error processing pool event {event.pool_address}: {e}")

    async def _process_whale_movements(self, movements: List[WhaleMovement]) -> None:
        """Process whale movements."""
        for movement in movements:
            try:
                self.logger.info(f"🐋 Whale {movement.movement_type}: ${movement.amount_usd:,.0f} in {movement.token_address[:8]}...")
                
                self.whale_movements.append(movement)
                self.stats["whale_movements_detected"] += 1
                self.stats["last_whale_movement"] = datetime.now().isoformat()
                
                # Check if this affects any of our monitored pools
                if movement.pool_address in self.monitored_pools:
                    await self._handle_whale_in_monitored_pool(movement)
                
            except Exception as e:
                self.logger.error(f"💥 Error processing whale movement: {e}")

    async def _is_promising_event(self, event: PoolEvent) -> bool:
        """Determine if an event represents a promising opportunity."""
        try:
            # Check basic criteria
            if event.event_type != "pool_creation":
                return False
                
            # Check liquidity amount
            initial_liquidity = event.data.get('initial_liquidity_usd', 0)
            if initial_liquidity < 5000:  # Minimum $5K liquidity
                return False
                
            # Check quote token (prefer SOL, USDC)
            quote_token_symbol = event.data.get('quote_token_symbol', '').upper()
            if quote_token_symbol not in ['SOL', 'USDC', 'USDT']:
                return False
                
            # Check if base token is not a major token
            base_token_symbol = event.data.get('base_token_symbol', '').upper()
            major_tokens = {'SOL', 'USDC', 'USDT', 'BTC', 'ETH', 'BONK', 'WIF'}
            if base_token_symbol in major_tokens:
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"💥 Error evaluating event promise: {e}")
            return False

    async def _create_opportunity_from_event(self, event: PoolEvent) -> None:
        """Create a trading opportunity from a pool event."""
        try:
            # This will be implemented in subclasses
            self.logger.info(f"🎯 Creating opportunity from {self.dex_name} event: {event.pool_address}")
            
            # Notify callbacks
            await self._notify_callbacks(event)
            
        except Exception as e:
            self.logger.error(f"💥 Error creating opportunity from event: {e}")

    async def _handle_whale_in_monitored_pool(self, movement: WhaleMovement) -> None:
        """Handle whale movement in a pool we're monitoring."""
        self.logger.info(f"🎯 Whale activity in monitored pool: {movement.pool_address}")

    async def _cleanup_old_events(self) -> None:
        """Clean up events older than 1 hour."""
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        # Clean recent events
        self.recent_events = [
            event for event in self.recent_events 
            if event.timestamp > cutoff_time
        ]
        
        # Clean whale movements
        self.whale_movements = [
            movement for movement in self.whale_movements 
            if movement.timestamp > cutoff_time
        ]

    async def _cleanup(self) -> None:
        """Cleanup resources (implements BaseMonitor abstract method)."""
        try:
            self.logger.info(f"🧹 Cleaning up {self.dex_name} DEX Monitor...")
            
            if self.session and not self.session.closed:
                await self.session.close()
                await asyncio.sleep(0.1)
            
            self.logger.info(f"✅ {self.dex_name} DEX Monitor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"💥 Error during {self.dex_name} cleanup: {e}")

    def get_recent_pools(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently discovered pools."""
        recent_creation_events = [
            event for event in self.recent_events 
            if event.event_type == "pool_creation"
        ]
        
        # Sort by timestamp, most recent first
        recent_creation_events.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [event.to_dict() for event in recent_creation_events[:limit]]

    def get_whale_movements(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent whale movements."""
        # Sort by timestamp, most recent first
        recent_movements = sorted(
            self.whale_movements, 
            key=lambda x: x.timestamp, 
            reverse=True
        )
        
        return [movement.to_dict() for movement in recent_movements[:limit]]

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive monitor statistics."""
        uptime = datetime.now() - self.stats["uptime_start"]
        
        return {
            "dex_name": self.dex_name,
            "is_running": self.is_running,
            "uptime_seconds": uptime.total_seconds(),
            "pools_discovered": self.stats["pools_discovered"],
            "whale_movements_detected": self.stats["whale_movements_detected"],
            "events_processed": self.stats["events_processed"],
            "monitored_pools_count": len(self.monitored_pools),
            "api_calls_total": self.stats["api_calls_total"],
            "api_calls_successful": self.stats["api_calls_successful"],
            "api_calls_failed": self.stats["api_calls_failed"],
            "last_pool_creation": self.stats["last_pool_creation"],
            "last_whale_movement": self.stats["last_whale_movement"],
            "errors_count": self.stats["errors_count"],
            "last_error": self.stats["last_error"],
            "whale_threshold_usd": self.whale_threshold_usd,
            "recent_pools_count": len([e for e in self.recent_events if e.event_type == "pool_creation"]),
            "recent_whale_movements_count": len(self.whale_movements)
        }