# config/settings.py
"""
Configuration settings for the DEX sniping system.
Backward compatible with existing code while adding free API support.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from dotenv import load_dotenv

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
    
    # NEW: Multiple RPC URLs for failover (optional)
    ethereum_rpc_urls: Optional[List[str]] = None
    polygon_rpc_urls: Optional[List[str]] = None
    bsc_rpc_urls: Optional[List[str]] = None
    arbitrum_rpc_urls: Optional[List[str]] = None
    
    def __post_init__(self):
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
    """Main settings class for the DEX sniping system."""
    
    def __init__(self):
        self.api = APIConfig()
        self.networks = NetworkConfig()
        self.contracts = ContractAddresses()
        
        # Load from environment variables
        self._load_from_env()
        
        # Trading settings
        self.max_slippage = 0.05  # 5%
        self.max_gas_price = 50   # gwei
        self.min_liquidity_usd = 1000
        self.max_position_size_eth = 0.1
        
        # Monitoring settings
        self.check_interval = 1.0  # seconds
        self.max_token_age = 300   # seconds (5 minutes)
        
        # Risk management
        self.blacklisted_tokens: List[str] = []
        self.whitelisted_deployers: List[str] = []
        
        # Free API endpoints (new)
        self.free_endpoints = {
            'coingecko': 'https://api.coingecko.com/api/v3',
            'dexscreener': 'https://api.dexscreener.com/latest', 
            'the_graph': 'https://api.thegraph.com/subgraphs/name'
        }
        
    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Load the .env file first
        load_dotenv()
        
        # BACKWARD COMPATIBLE: Load single RPC URL first
        env_rpc = os.getenv('ETHEREUM_RPC_URL')
        if env_rpc:
            self.networks.ethereum_rpc_url = env_rpc
            # Also update the list to prioritize the env URL
            self.networks.ethereum_rpc_urls = [env_rpc] + [
                url for url in self.networks.ethereum_rpc_urls 
                if url != env_rpc
            ]
        
        # Load other network URLs
        polygon_rpc = os.getenv('POLYGON_RPC_URL')
        if polygon_rpc:
            self.networks.polygon_rpc_url = polygon_rpc
            
        bsc_rpc = os.getenv('BSC_RPC_URL')
        if bsc_rpc:
            self.networks.bsc_rpc_url = bsc_rpc
            
        arbitrum_rpc = os.getenv('ARBITRUM_RPC_URL')
        if arbitrum_rpc:
            self.networks.arbitrum_rpc_url = arbitrum_rpc
        
        # Load API keys (all optional now)
        self.api.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY')
        self.api.moralis_api_key = os.getenv('MORALIS_API_KEY')
        self.api.coingecko_api_key = os.getenv('COINGECKO_API_KEY')
        self.api.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.api.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Additional API keys
        self.api.twitter_bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.api.reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        self.api.reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.api.honeypot_api_key = os.getenv('HONEYPOT_API_KEY')
    
    def get_rpc_url(self, chain: str = 'ethereum') -> str:
        """Get the primary RPC URL for a chain."""
        if chain == 'ethereum':
            return self.networks.ethereum_rpc_url
        elif chain == 'polygon':
            return self.networks.polygon_rpc_url
        elif chain == 'bsc':
            return self.networks.bsc_rpc_url
        elif chain == 'arbitrum':
            return self.networks.arbitrum_rpc_url
        else:
            raise ValueError(f"Unsupported chain: {chain}")
    
    def get_rpc_urls(self, chain: str = 'ethereum') -> List[str]:
        """Get all RPC URLs for a chain (for failover)."""
        if chain == 'ethereum':
            return self.networks.ethereum_rpc_urls or [self.networks.ethereum_rpc_url]
        elif chain == 'polygon':
            return self.networks.polygon_rpc_urls or [self.networks.polygon_rpc_url]
        elif chain == 'bsc':
            return self.networks.bsc_rpc_urls or [self.networks.bsc_rpc_url]
        elif chain == 'arbitrum':
            return self.networks.arbitrum_rpc_urls or [self.networks.arbitrum_rpc_url]
        else:
            raise ValueError(f"Unsupported chain: {chain}")
    
    def get_free_api_url(self, service: str) -> str:
        """Get free API endpoint URL."""
        return self.free_endpoints.get(service, '')

# Create global settings instance
settings = Settings()

# Debug function to check configuration
def debug_settings():
    """Debug function to check current settings."""
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
    
    print("=" * 40)

if __name__ == "__main__":
    debug_settings()