#!/usr/bin/env python3
"""
Raydium DEX configuration settings.

File: config/raydium_config.py
Purpose: Configuration for Raydium API endpoints, rate limits, and monitoring settings

ISSUE FIXED: Missing configuration methods and incomplete dataclass initialization
SOLUTION: Complete implementation of all referenced configuration methods
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
        """Initialize default values for token lists."""
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
    
    enabled: bool = False  # Default to disabled until implementation complete
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
    """
    Main Raydium configuration class.
    
    Provides centralized configuration management for all Raydium monitoring
    components including API endpoints, rate limits, and monitoring criteria.
    """
    
    def __init__(self):
        """
        Initialize Raydium configuration with all required components.
        
        Sets up default values and loads environment variable overrides.
        """
        self.endpoints = RaydiumAPIEndpoints()
        self.rate_limits = RaydiumRateLimits()
        self.monitoring = RaydiumMonitoringSettings()
        self.websocket = RaydiumWebSocketConfig()
        
        # Load any environment overrides
        self._load_environment_overrides()
    
    def _load_environment_overrides(self) -> None:
        """
        Load configuration overrides from environment variables.
        
        This allows for runtime configuration changes without code modification.
        Useful for deployment-specific settings and testing.
        """
        try:
            # Rate limit overrides
            if os.getenv('RAYDIUM_REQUESTS_PER_MINUTE'):
                self.rate_limits.requests_per_minute = int(os.getenv('RAYDIUM_REQUESTS_PER_MINUTE'))
            
            if os.getenv('RAYDIUM_REQUESTS_PER_SECOND'):
                self.rate_limits.requests_per_second = int(os.getenv('RAYDIUM_REQUESTS_PER_SECOND'))
            
            # Monitoring overrides
            if os.getenv('RAYDIUM_MIN_LIQUIDITY_USD'):
                self.monitoring.min_liquidity_usd = float(os.getenv('RAYDIUM_MIN_LIQUIDITY_USD'))
            
            if os.getenv('RAYDIUM_MAX_LIQUIDITY_USD'):
                self.monitoring.max_liquidity_usd = float(os.getenv('RAYDIUM_MAX_LIQUIDITY_USD'))
            
            if os.getenv('RAYDIUM_WHALE_THRESHOLD_USD'):
                self.monitoring.whale_threshold_usd = float(os.getenv('RAYDIUM_WHALE_THRESHOLD_USD'))
            
            # WebSocket overrides
            if os.getenv('RAYDIUM_WEBSOCKET_ENABLED'):
                self.websocket.enabled = os.getenv('RAYDIUM_WEBSOCKET_ENABLED').lower() == 'true'
            
            # API endpoint overrides
            if os.getenv('RAYDIUM_API_BASE_URL'):
                self.endpoints.base_url = os.getenv('RAYDIUM_API_BASE_URL')
                
        except Exception as e:
            print(f"Warning: Error loading environment overrides: {e}")
    
    def get_api_url(self, endpoint: str) -> str:
        """
        Get full API URL for an endpoint.
        
        Args:
            endpoint: The API endpoint path (e.g., "/v2/main/pairs")
            
        Returns:
            str: Complete URL for the endpoint
        """
        return f"{self.endpoints.base_url}{endpoint}"
    
    def get_backup_api_url(self, endpoint: str) -> str:
        """
        Get backup API URL for an endpoint.
        
        Args:
            endpoint: The API endpoint path
            
        Returns:
            str: Complete backup URL for the endpoint
        """
        return f"{self.endpoints.backup_base_url}{endpoint}"
    
    def is_supported_quote_token(self, token_address: str) -> bool:
        """
        Check if a token is a supported quote token.
        
        Args:
            token_address: The token mint address to check
            
        Returns:
            bool: True if token is supported as quote token
        """
        return token_address in self.monitoring.supported_quote_tokens
    
    def is_excluded_base_token(self, token_address: str) -> bool:
        """
        Check if a token should be excluded as base token.
        
        Args:
            token_address: The token mint address to check
            
        Returns:
            bool: True if token should be excluded
        """
        return token_address in self.monitoring.excluded_base_tokens
    
    def should_monitor_pool(self, pool_data: Dict) -> bool:
        """
        Determine if a pool should be monitored based on criteria.
        
        This method evaluates pools against our monitoring criteria including
        liquidity range, supported tokens, and trading activity.
        
        Args:
            pool_data: Pool data dictionary from Raydium API
            
        Returns:
            bool: True if pool meets monitoring criteria
        """
        try:
            # Check liquidity range
            liquidity_usd = pool_data.get('liquidity', {}).get('usd', 0)
            if not (self.monitoring.min_liquidity_usd <= liquidity_usd <= self.monitoring.max_liquidity_usd):
                return False
            
            # Check quote token support
            quote_mint = pool_data.get('quoteMint', '')
            quote_symbol = pool_data.get('quoteSymbol', '').upper()
            
            # Check by address first, then by symbol as fallback
            if quote_mint and not self.is_supported_quote_token(quote_mint):
                # Fallback to symbol check for compatibility
                if quote_symbol not in ['SOL', 'USDC', 'USDT']:
                    return False
            
            # Check if base token is excluded
            base_mint = pool_data.get('baseMint', '')
            base_symbol = pool_data.get('baseSymbol', '').upper()
            
            # Check by address first, then by symbol
            if base_mint and self.is_excluded_base_token(base_mint):
                return False
            if base_symbol in ['SOL', 'USDC', 'USDT', 'BTC', 'ETH']:
                return False
            
            # Check trading activity
            volume_24h = pool_data.get('volume24h', 0)
            if volume_24h < 1000:  # Minimum $1K daily volume
                return False
            
            # Check trade count if available
            trade_count = pool_data.get('trade24h', {}).get('count', 0)
            if trade_count > 0 and trade_count < self.monitoring.min_trade_count_24h:
                return False
            
            # Check price impact if available
            price_impact = pool_data.get('priceImpact', 0)
            if price_impact > self.monitoring.max_price_impact_threshold:
                return False
            
            return True
            
        except Exception as e:
            print(f"Error evaluating pool monitoring criteria: {e}")
            return False
    
    def get_pool_priority_score(self, pool_data: Dict) -> float:
        """
        Calculate priority score for a pool (0.0 to 1.0).
        
        This scoring system helps prioritize which pools to monitor most closely
        based on liquidity, volume, trading activity, and other factors.
        
        Args:
            pool_data: Pool data dictionary from Raydium API
            
        Returns:
            float: Priority score between 0.0 and 1.0
        """
        try:
            score = 0.0
            
            # Liquidity score (0.3 weight)
            liquidity_usd = pool_data.get('liquidity', {}).get('usd', 0)
            if liquidity_usd > 0:
                # Sweet spot is 10K-100K liquidity for new tokens
                if 10000 <= liquidity_usd <= 100000:
                    score += 0.3
                elif 5000 <= liquidity_usd < 10000:
                    score += 0.2
                elif 100000 < liquidity_usd <= 500000:
                    score += 0.15
                elif liquidity_usd > 500000:
                    score += 0.1  # Too established
            
            # Volume score (0.3 weight)
            volume_24h = pool_data.get('volume24h', 0)
            if volume_24h > 100000:
                score += 0.3
            elif volume_24h > 50000:
                score += 0.25
            elif volume_24h > 10000:
                score += 0.2
            elif volume_24h > 1000:
                score += 0.1
            
            # Trading activity score (0.2 weight)
            trade_count = pool_data.get('trade24h', {}).get('count', 0)
            if trade_count > 500:
                score += 0.2
            elif trade_count > 100:
                score += 0.15
            elif trade_count > 50:
                score += 0.1
            elif trade_count > 10:
                score += 0.05
            
            # Price change score (0.1 weight) - higher volatility can mean more opportunity
            price_change_24h = abs(pool_data.get('priceChange24h', 0))
            if 5 <= price_change_24h <= 50:  # 5-50% change is interesting
                score += 0.1
            elif 2 <= price_change_24h < 5:
                score += 0.05
            
            # Newness bonus (0.1 weight)
            # This would need pool age data - for now, assume newer pools get slight bonus
            # In practice, this would compare pool creation time to current time
            score += 0.05  # Small bonus for being recently discovered
            
            return min(score, 1.0)
            
        except Exception as e:
            print(f"Error calculating pool priority score: {e}")
            return 0.0
    
    def get_rate_limit_delay(self, requests_made: int, time_window: float) -> float:
        """
        Calculate required delay to stay within rate limits.
        
        Args:
            requests_made: Number of requests made in the time window
            time_window: Time window in seconds
            
        Returns:
            float: Delay needed in seconds
        """
        try:
            # Check per-second limit
            if time_window <= 1.0 and requests_made >= self.rate_limits.requests_per_second:
                return 1.0 - time_window
            
            # Check per-minute limit
            if time_window <= 60.0 and requests_made >= self.rate_limits.requests_per_minute:
                return 60.0 - time_window
            
            return 0.0
            
        except Exception:
            return 1.0  # Conservative fallback
    
    def validate_configuration(self) -> bool:
        """
        Validate the configuration for completeness and correctness.
        
        Returns:
            bool: True if configuration is valid
        """
        try:
            # Check required settings
            assert self.monitoring.min_liquidity_usd > 0
            assert self.monitoring.max_liquidity_usd > self.monitoring.min_liquidity_usd
            assert self.monitoring.whale_threshold_usd > 0
            assert self.rate_limits.requests_per_minute > 0
            assert self.rate_limits.requests_per_second > 0
            assert len(self.monitoring.supported_quote_tokens) > 0
            assert self.endpoints.base_url.startswith('http')
            
            return True
            
        except (AssertionError, AttributeError) as e:
            print(f"Configuration validation failed: {e}")
            return False


# Create global configuration instance
raydium_config = RaydiumConfig()


# Helper functions for easy access
def get_raydium_config() -> RaydiumConfig:
    """
    Get the global Raydium configuration.
    
    Returns:
        RaydiumConfig: The global configuration instance
    """
    return raydium_config


def get_api_url(endpoint: str) -> str:
    """
    Get full Raydium API URL for an endpoint.
    
    Args:
        endpoint: The API endpoint path
        
    Returns:
        str: Complete URL for the endpoint
    """
    return raydium_config.get_api_url(endpoint)


def should_monitor_pool(pool_data: Dict) -> bool:
    """
    Check if a pool should be monitored.
    
    Args:
        pool_data: Pool data dictionary from API
        
    Returns:
        bool: True if pool should be monitored
    """
    return raydium_config.should_monitor_pool(pool_data)


def get_pool_priority_score(pool_data: Dict) -> float:
    """
    Get priority score for a pool.
    
    Args:
        pool_data: Pool data dictionary from API
        
    Returns:
        float: Priority score between 0.0 and 1.0
    """
    return raydium_config.get_pool_priority_score(pool_data)


# Configuration validation
def validate_config() -> bool:
    """
    Validate the Raydium configuration.
    
    Returns:
        bool: True if configuration is valid
    """
    try:
        return raydium_config.validate_configuration()
        
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
    print(f"Max Liquidity: ${config.monitoring.max_liquidity_usd:,.0f}")
    print(f"Whale Threshold: ${config.monitoring.whale_threshold_usd:,.0f}")
    print(f"WebSocket Enabled: {config.websocket.enabled}")
    print(f"Supported Quote Tokens: {len(config.monitoring.supported_quote_tokens)}")
    print(f"Excluded Base Tokens: {len(config.monitoring.excluded_base_tokens)}")
    print("=" * 40)
    
    if validate_config():
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration validation failed")
        
    # Test pool evaluation
    test_pool = {
        'id': 'test_pool_123',
        'liquidity': {'usd': 25000},
        'volume24h': 15000,
        'quoteMint': 'So11111111111111111111111111111111111111112',  # SOL
        'baseMint': 'example_token_mint',
        'quoteSymbol': 'SOL',
        'baseSymbol': 'TEST',
        'trade24h': {'count': 45}
    }
    
    should_monitor = should_monitor_pool(test_pool)
    priority_score = get_pool_priority_score(test_pool)
    
    print(f"\n🧪 Test Pool Evaluation:")
    print(f"   Should Monitor: {should_monitor}")
    print(f"   Priority Score: {priority_score:.3f}")