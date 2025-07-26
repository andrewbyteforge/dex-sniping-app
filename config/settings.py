#!/usr/bin/env python3
"""
Configuration settings for the DEX sniping system.
Backward compatible with existing code while adding free API support.

File: config/settings.py
Class: Settings
Methods: Configuration management and attribute access

UPDATE: Added missing trading configuration attributes to fix initialization errors
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class APIConfig:
    """Configuration for external API services."""
    etherscan_api_key: Optional[str] = None
    moralis_api_key: Optional[str] = None
    coingecko_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    # Additional API keys for enhanced features
    twitter_bearer_token: Optional[str] = None
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    honeypot_api_key: Optional[str] = None


@dataclass
class NetworkConfig:
    """Configuration for blockchain networks - BACKWARD COMPATIBLE."""
    
    # KEEP original single URL attributes for compatibility
    ethereum_rpc_url: str = "https://ethereum-rpc.publicnode.com"
    polygon_rpc_url: str = "https://polygon-rpc.com"
    bsc_rpc_url: str = "https://bsc-dataseed.binance.org/"
    arbitrum_rpc_url: str = "https://arb1.arbitrum.io/rpc"
    base_rpc_url: str = "https://mainnet.base.org"
    
    # NEW: Multiple RPC URLs for failover (optional)
    ethereum_rpc_urls: Optional[List[str]] = None
    polygon_rpc_urls: Optional[List[str]] = None
    bsc_rpc_urls: Optional[List[str]] = None
    arbitrum_rpc_urls: Optional[List[str]] = None
    base_rpc_urls: Optional[List[str]] = None
    
    def __post_init__(self) -> None:
        """Initialize backup RPC URLs if not provided."""
        if self.ethereum_rpc_urls is None:
            self.ethereum_rpc_urls = [
                self.ethereum_rpc_url,  # Primary from above
                "https://rpc.ankr.com/eth",
                "https://eth.public-rpc.com",
                "https://ethereum.blockpi.network/v1/rpc/public",
                "https://rpc.payload.de"
            ]
        
        if self.polygon_rpc_urls is None:
            self.polygon_rpc_urls = [
                self.polygon_rpc_url,
                "https://rpc.ankr.com/polygon",
                "https://polygon.blockpi.network/v1/rpc/public"
            ]
        
        if self.bsc_rpc_urls is None:
            self.bsc_rpc_urls = [
                self.bsc_rpc_url,
                "https://bsc.public-rpc.com",
                "https://bsc-dataseed1.defibit.io/"
            ]
        
        if self.arbitrum_rpc_urls is None:
            self.arbitrum_rpc_urls = [
                self.arbitrum_rpc_url,
                "https://rpc.ankr.com/arbitrum"
            ]
        
        if self.base_rpc_urls is None:
            self.base_rpc_urls = [
                self.base_rpc_url,
                "https://base.blockpi.network/v1/rpc/public"
            ]


@dataclass
class ContractAddresses:
    """Smart contract addresses for different networks."""
    
    # Uniswap V2
    uniswap_v2_factory: str = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
    uniswap_v2_router: str = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
    
    # Uniswap V3
    uniswap_v3_factory: str = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
    
    # PancakeSwap
    pancakeswap_factory: str = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
    pancakeswap_router: str = "0x10ED43C718714eb63d5aA57B78B54704E256024E"


class Settings:
    """
    Main settings class for the DEX sniping system.
    
    Provides configuration management with backward compatibility
    and support for dynamic attribute access.
    """
    
    def __init__(self) -> None:
        """Initialize settings with default values."""
        self.api = APIConfig()
        self.networks = NetworkConfig()
        self.contracts = ContractAddresses()
        
        # Load from environment variables
        self._load_from_env()
        
        # Trading settings (with fallback defaults)
        self.max_slippage = 0.05  # 5%
        self.max_gas_price = 50   # gwei
        self.min_liquidity_usd = 1000
        self.max_position_size_eth = 0.1
        
        # Monitoring settings
        self.check_interval = 1.0  # seconds
        self.max_token_age = 300   # seconds (5 minutes)
        
        # Risk management defaults (ADD MISSING ATTRIBUTES)
        self.max_total_exposure_usd = 10000.0
        self.max_single_position_usd = 1000.0
        self.max_positions_per_chain = 5
        self.max_daily_loss_usd = 500.0
        self.max_total_positions = 15
        self.min_liquidity_usd = 50000.0
        self.close_positions_on_shutdown = False
        
        # Blacklisted and whitelisted addresses
        self.blacklisted_tokens: List[str] = []
        self.whitelisted_deployers: List[str] = []
        
        # Free API endpoints
        self.free_endpoints = {
            'coingecko': 'https://api.coingecko.com/api/v3',
            'dexscreener': 'https://api.dexscreener.com/latest', 
            'the_graph': 'https://api.thegraph.com/subgraphs/name'
        }

    def _load_from_env(self) -> None:
        """
        Load configuration from environment variables.
        
        Reads configuration values from .env file and environment.
        """
        # API Keys
        self.api.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY')
        self.api.moralis_api_key = os.getenv('MORALIS_API_KEY')
        self.api.coingecko_api_key = os.getenv('COINGECKO_API_KEY')
        self.api.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.api.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.api.twitter_bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.api.reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        self.api.reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.api.honeypot_api_key = os.getenv('HONEYPOT_API_KEY')
        
        # Network URLs (override defaults if provided)
        if os.getenv('ETHEREUM_RPC_URL'):
            self.networks.ethereum_rpc_url = os.getenv('ETHEREUM_RPC_URL')
        if os.getenv('POLYGON_RPC_URL'):
            self.networks.polygon_rpc_url = os.getenv('POLYGON_RPC_URL')
        if os.getenv('BSC_RPC_URL'):
            self.networks.bsc_rpc_url = os.getenv('BSC_RPC_URL')
        if os.getenv('ARBITRUM_RPC_URL'):
            self.networks.arbitrum_rpc_url = os.getenv('ARBITRUM_RPC_URL')
        if os.getenv('BASE_RPC_URL'):
            self.networks.base_rpc_url = os.getenv('BASE_RPC_URL')
        
        # Trading parameters
        if os.getenv('MAX_SLIPPAGE'):
            self.max_slippage = float(os.getenv('MAX_SLIPPAGE'))
        if os.getenv('MAX_GAS_PRICE'):
            self.max_gas_price = int(os.getenv('MAX_GAS_PRICE'))
        if os.getenv('MIN_LIQUIDITY_USD'):
            self.min_liquidity_usd = float(os.getenv('MIN_LIQUIDITY_USD'))
        if os.getenv('MAX_POSITION_SIZE_ETH'):
            self.max_position_size_eth = float(os.getenv('MAX_POSITION_SIZE_ETH'))
        
        # Risk management parameters
        if os.getenv('MAX_TOTAL_EXPOSURE_USD'):
            self.max_total_exposure_usd = float(os.getenv('MAX_TOTAL_EXPOSURE_USD'))
        if os.getenv('MAX_SINGLE_POSITION_USD'):
            self.max_single_position_usd = float(os.getenv('MAX_SINGLE_POSITION_USD'))
        if os.getenv('MAX_POSITIONS_PER_CHAIN'):
            self.max_positions_per_chain = int(os.getenv('MAX_POSITIONS_PER_CHAIN'))
        if os.getenv('MAX_DAILY_LOSS_USD'):
            self.max_daily_loss_usd = float(os.getenv('MAX_DAILY_LOSS_USD'))
        if os.getenv('MAX_TOTAL_POSITIONS'):
            self.max_total_positions = int(os.getenv('MAX_TOTAL_POSITIONS'))
        
        # System settings
        if os.getenv('CLOSE_POSITIONS_ON_SHUTDOWN'):
            self.close_positions_on_shutdown = os.getenv('CLOSE_POSITIONS_ON_SHUTDOWN').lower() == 'true'

    def get(self, key: str, default=None):
        """
        Get configuration value with fallback.
        
        Args:
            key: Configuration key to retrieve
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return getattr(self, key, default)

    def get_free_endpoint(self, service: str) -> str:
        """
        Get free API endpoint for a service.
        
        Args:
            service: Service name ('coingecko', 'dexscreener', etc.)
            
        Returns:
            API endpoint URL or empty string if not found
        """
        return self.free_endpoints.get(service, '')

    def validate_configuration(self) -> List[str]:
        """
        Validate current configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check critical API keys
        if not self.api.telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN not configured")
        
        # Check RPC URLs
        if not self.networks.ethereum_rpc_url:
            errors.append("Ethereum RPC URL not configured")
        
        # Check trading parameters
        if self.max_slippage <= 0 or self.max_slippage > 1:
            errors.append("Invalid max_slippage (must be between 0 and 1)")
        
        if self.max_gas_price <= 0:
            errors.append("Invalid max_gas_price (must be positive)")
        
        if self.min_liquidity_usd <= 0:
            errors.append("Invalid min_liquidity_usd (must be positive)")
        
        return errors

    def to_dict(self) -> Dict[str, any]:
        """
        Convert settings to dictionary.
        
        Returns:
            Dictionary representation of settings
        """
        return {
            'api': {
                'etherscan_configured': bool(self.api.etherscan_api_key),
                'moralis_configured': bool(self.api.moralis_api_key),
                'coingecko_configured': bool(self.api.coingecko_api_key),
                'telegram_configured': bool(self.api.telegram_bot_token),
            },
            'networks': {
                'ethereum_rpc': self.networks.ethereum_rpc_url,
                'polygon_rpc': self.networks.polygon_rpc_url,
                'bsc_rpc': self.networks.bsc_rpc_url,
                'arbitrum_rpc': self.networks.arbitrum_rpc_url,
                'base_rpc': self.networks.base_rpc_url,
            },
            'trading': {
                'max_slippage': self.max_slippage,
                'max_gas_price': self.max_gas_price,
                'min_liquidity_usd': self.min_liquidity_usd,
                'max_position_size_eth': self.max_position_size_eth,
            },
            'risk_management': {
                'max_total_exposure_usd': self.max_total_exposure_usd,
                'max_single_position_usd': self.max_single_position_usd,
                'max_positions_per_chain': self.max_positions_per_chain,
                'max_daily_loss_usd': self.max_daily_loss_usd,
                'max_total_positions': self.max_total_positions,
            }
        }


# Create global settings instance
settings = Settings()


def debug_settings() -> None:
    """
    Debug function to check current settings.
    
    Prints current configuration for troubleshooting.
    """
    print("🔧 CURRENT SETTINGS DEBUG")
    print("=" * 40)
    
    print(f"Ethereum RPC: {settings.networks.ethereum_rpc_url}")
    print(f"Backup RPCs: {len(settings.networks.ethereum_rpc_urls)} available")
    
    # Test RPC connection
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(settings.networks.ethereum_rpc_url))
        if w3.is_connected():
            block = w3.eth.block_number
            print(f"✅ RPC Working - Block: {block}")
        else:
            print("❌ RPC Not Connected")
    except Exception as e:
        print(f"❌ RPC Error: {e}")
    
    # Check API keys
    apis = {
        'Etherscan': settings.api.etherscan_api_key,
        'Moralis': settings.api.moralis_api_key,
        'CoinGecko': settings.api.coingecko_api_key,
        'Telegram': settings.api.telegram_bot_token
    }
    
    print("\nAPI Keys:")
    for name, key in apis.items():
        status = "✅" if key else "❌"
        print(f"  {name}: {status}")
    
    # Show validation errors
    errors = settings.validate_configuration()
    if errors:
        print(f"\n❌ Configuration Errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print(f"\n✅ Configuration Valid")
    
    print("=" * 40)


if __name__ == "__main__":
    debug_settings()