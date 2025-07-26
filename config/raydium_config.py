#!/usr/bin/env python3
"""
Raydium DEX configuration settings.

File: config/raydium_config.py
Purpose: Configuration for Raydium API endpoints, rate limits, and monitoring settings
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class RaydiumAPIEndpoints:
    """Raydium API endpoint configurations."""
    
    # Main API endpoints
    base_url: str = "https://api.raydium.io"
    
    # V2 endpoints
    pairs: str = "/v2/main/pairs"
    info: str = "/v2/main/info"
    price: str = "/v2/main/price"
    
    # AMM v3 endpoints
    amm_pools: str = "/v2/ammV3/pools"
    liquidity_pools: str = "/v2/sdk/liquidity/pools"
    
    # WebSocket endpoint for real-time data
    websocket: str = "wss://api.raydium.io/v2/ws"
    
    # Alternative endpoints (fallback)
    backup_base_url: str = "https://api-v3.raydium.io"


@dataclass
class RaydiumRateLimits:
    """Rate limiting configuration for Raydium API."""
    
    # API rate limits
    requests_per_minute: int = 120
    requests_per_second: int = 5
    burst_limit: int = 10
    
    # Backoff settings
    initial_backoff: float = 1.0
    max_backoff: float = 30.0
    backoff_multiplier: float = 2.0
    
    # Timeout settings
    request_timeout: float = 15.0
    connection_timeout: float = 10.0


@dataclass
class RaydiumMonitoringSettings:
    """Monitoring configuration for Raydium."""
    
    # Pool filtering
    min_liquidity_usd: float = 5000.0
    max_liquidity_usd: float = 10000000.0  # 10M max to avoid established tokens
    
    # Whale detection
    whale_threshold_usd: float = 10000.0
    large_whale_threshold_usd: float = 50000.0
    
    # Time windows
    new_pool_window_minutes: int = 60  # Consider pools "new" for 1 hour
    whale_tracking_window_minutes: int = 30  # Track whale movements for 30 min
    
    # Token filtering
    supported_quote_tokens: List[str] = None
    excluded_base_tokens: List[str] = None
    
    # Pool metrics thresholds
    min_trade_count_24h: int = 10
    min_unique_traders_24h: int = 5
    max_price_impact_threshold: float = 0.05  # 5% max price impact
    
    def __post_init__(self):
        """Initialize default values."""
        if self.supported_quote_tokens is None:
            self.supported_quote_tokens = [
                "So11111111111111111111111111111111111111112",  # SOL
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
            ]
        
        if self.excluded_base_tokens is None:
            self.excluded_base_tokens = [
                "So11111111111111111111111111111111111111112",  # SOL
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
                "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
                "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",  # WIF
                "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",  # POPCAT
            ]


@dataclass
class RaydiumWebSocketConfig:
    """WebSocket configuration for real-time Raydium data."""
    
    enabled: bool = True
    auto_reconnect: bool = True
    reconnect_interval: float = 5.0
    max_reconnect_attempts: int = 10
    
    # Subscription channels
    pool_events: bool = True
    liquidity_events: bool = True
    trade_events: bool = True
    price_updates: bool = False  # Can be noisy, enable if needed
    
    # Buffer settings
    event_buffer_size: int = 1000
    max_events_per_second: int = 100


class RaydiumConfig:
    """Main Raydium configuration class."""
    
    def __init__(self):
        """Initialize Raydium configuration."""
        self.endpoints = RaydiumAPIEndpoints()
        self.rate_limits = RaydiumRateLimits()
        self.monitoring = RaydiumMonitoringSettings()
        self.websocket = RaydiumWebSocketConfig()
        
        # Load any environment overrides
        self._load_environment_overrides()
    
    def _load_environment_overrides(self) -> None:
        """Load configuration overrides from environment variables."""
        
        # Rate limit overrides
        if os.getenv('RAYDIUM_REQUESTS_PER_MINUTE'):
            self.rate_limits.requests_per_minute = int(os.getenv('RAYDIUM_REQUESTS_PER_MINUTE'))
        
        # Monitoring overrides
        if os.getenv('RAYDIUM_MIN_LIQUIDITY_USD'):
            self.monitoring.min_liquidity_usd = float(os.getenv('RAYDIUM_MIN_LIQUIDITY_USD'))
        
        if os.getenv('RAYDIUM_WHALE_THRESHOLD_USD'):
            self.monitoring.whale_threshold_usd = float(os.getenv('RAYDIUM_WHALE_THRESHOLD_USD'))
        
        # WebSocket overrides
        if os.getenv('RAYDIUM_WEBSOCKET_ENABLED'):
            self.websocket.enabled = os.getenv('RAYDIUM_WEBSOCKET_ENABLED').lower() == 'true'
    
    def get_api_url(self, endpoint: str) -> str:
        """Get full API URL for an endpoint."""
        return f"{self.endpoints.base_url}{endpoint}"
    
    def get_backup_api_url(self, endpoint: str) -> str:
        """Get backup API URL for an endpoint."""
        return f"{self.endpoints.backup_base_url}{endpoint}"
    
    def is_supported_quote_token(self, token_address: str) -> bool:
        """Check if a token is a supported quote token."""
        return token_address in self.monitoring.supported_quote_tokens
    
    def is_excluded_base_token(self, token_address: str) -> bool:
        """Check if a token should be excluded as base token."""
        return token_address in self.monitoring.excluded_base_tokens
    
    def should_monitor_pool(self, pool_data: Dict) -> bool:
        """Determine if a pool should be monitored based on criteria."""
        try:
            # Check liquidity range
            liquidity_usd = pool_data.get('liquidity', {}).get('usd', 0)
            if not (self.monitoring.min_liquidity_usd <= liquidity_usd <= self.monitoring.max_liquidity_usd):
                return False
            
            # Check quote token
            quote_mint = pool_data.get('quoteMint', '')
            if not self.is_supported_quote_token(quote_mint):
                return False
            
            # Check if base token is excluded
            base_mint = pool_data.get('baseMint', '')
            if self.is_excluded_base_token(base_mint):
                return False
            
            # Check trading activity
            volume_24h = pool_data.get('volume24h', 0)
            if volume_24h < 1000:  # Minimum $1K daily volume
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_pool_priority_score(self, pool_data: Dict) -> float:
        """Calculate priority score for a pool (0.0 to 1.0)."""
        try:
            score = 0.0
            
            # Liquidity score (0.3 weight)
            liquidity_usd = pool_data.get('liquidity', {}).get('usd', 0)
            if liquidity_usd > 0:
                # Sweet spot is 10K-100K liquidity
                if 10000 <= liquidity_usd <= 100000:
                    score += 0.3
                elif 5000 <= liquidity_usd < 10000:
                    score += 0.2
                elif liquidity_usd > 100000:
                    score += 0.1
            
            # Volume score (0.3 weight)
            volume_24h = pool_data.get('volume24h', 0)
            if volume_24h > 50000:
                score += 0.3
            elif volume_24h > 10000:
                score += 0.2
            elif volume_24h > 1000:
                score += 0.1
            
            # Age score (0.2 weight) - newer pools get higher score
            # This would need pool creation timestamp from the data
            
            # Trading activity score (0.2 weight)
            trade_count = pool_data.get('trade24h', {}).get('count', 0)
            if trade_count > 100:
                score += 0.2
            elif trade_count > 50:
                score += 0.15
            elif trade_count > 10:
                score += 0.1
            
            return min(score, 1.0)
            
        except Exception:
            return 0.0


# Create global configuration instance
raydium_config = RaydiumConfig()


# Helper functions for easy access
def get_raydium_config() -> RaydiumConfig:
    """Get the global Raydium configuration."""
    return raydium_config


def get_api_url(endpoint: str) -> str:
    """Get full Raydium API URL for an endpoint."""
    return raydium_config.get_api_url(endpoint)


def should_monitor_pool(pool_data: Dict) -> bool:
    """Check if a pool should be monitored."""
    return raydium_config.should_monitor_pool(pool_data)


def get_pool_priority_score(pool_data: Dict) -> float:
    """Get priority score for a pool."""
    return raydium_config.get_pool_priority_score(pool_data)


# Configuration validation
def validate_config() -> bool:
    """Validate the Raydium configuration."""
    try:
        config = get_raydium_config()
        
        # Check required settings
        assert config.monitoring.min_liquidity_usd > 0
        assert config.monitoring.whale_threshold_usd > 0
        assert config.rate_limits.requests_per_minute > 0
        assert len(config.monitoring.supported_quote_tokens) > 0
        
        return True
        
    except Exception as e:
        print(f"❌ Raydium configuration validation failed: {e}")
        return False


if __name__ == "__main__":
    # Test configuration
    config = get_raydium_config()
    print("🔧 Raydium Configuration Test")
    print("=" * 40)
    print(f"Base URL: {config.endpoints.base_url}")
    print(f"Rate Limit: {config.rate_limits.requests_per_minute}/min")
    print(f"Min Liquidity: ${config.monitoring.min_liquidity_usd:,.0f}")
    print(f"Whale Threshold: ${config.monitoring.whale_threshold_usd:,.0f}")
    print(f"WebSocket Enabled: {config.websocket.enabled}")
    print(f"Supported Quote Tokens: {len(config.monitoring.supported_quote_tokens)}")
    print("=" * 40)
    
    if validate_config():
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration validation failed")