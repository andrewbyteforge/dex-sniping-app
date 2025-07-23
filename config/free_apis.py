# config/free_apis.py
"""
Free API configuration for DEX sniping system.
All APIs below have free tiers or are completely free.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from dotenv import load_dotenv

@dataclass
class FreeAPIConfig:
    """Configuration for free external API services."""
    
    # Free RPC endpoints (no API key needed)
    ethereum_rpc_urls: List[str] = None
    base_rpc_urls: List[str] = None
    bsc_rpc_urls: List[str] = None
    polygon_rpc_urls: List[str] = None
    
    # Free blockchain data APIs
    coingecko_free_url: str = "https://api.coingecko.com/api/v3"  # No key needed for basic
    dexscreener_url: str = "https://api.dexscreener.com/latest"  # Free
    the_graph_url: str = "https://api.thegraph.com/subgraphs/name"  # Free
    
    # Free social data
    telegram_bot_token: Optional[str] = None  # Free from @BotFather
    telegram_chat_id: Optional[str] = None
    
    # Free tier APIs (require signup but free)
    alchemy_api_key: Optional[str] = None  # 300M requests/month free
    infura_api_key: Optional[str] = None   # 100k requests/day free
    moralis_api_key: Optional[str] = None  # 40k requests/month free
    etherscan_api_key: Optional[str] = None  # 5 req/sec free
    
    def __post_init__(self):
        if self.ethereum_rpc_urls is None:
            self.ethereum_rpc_urls = [
                "https://ethereum-rpc.publicnode.com",
                "https://rpc.ankr.com/eth",
                "https://eth.public-rpc.com",
                "https://ethereum.blockpi.network/v1/rpc/public",
                "https://rpc.payload.de"
            ]
        
        if self.base_rpc_urls is None:
            self.base_rpc_urls = [
                "https://mainnet.base.org",
                "https://base-rpc.publicnode.com",
                "https://base.blockpi.network/v1/rpc/public"
            ]
        
        if self.bsc_rpc_urls is None:
            self.bsc_rpc_urls = [
                "https://bsc-dataseed.binance.org/",
                "https://bsc-dataseed1.defibit.io/",
                "https://bsc-dataseed1.ninicoin.io/",
                "https://bsc.public-rpc.com"
            ]
        
        if self.polygon_rpc_urls is None:
            self.polygon_rpc_urls = [
                "https://polygon-rpc.com",
                "https://rpc.ankr.com/polygon",
                "https://polygon.blockpi.network/v1/rpc/public"
            ]

class FreeAPIManager:
    """Manager for free API services."""
    
    def __init__(self):
        load_dotenv()
        self.config = FreeAPIConfig()
        self._load_optional_keys()
        
    def _load_optional_keys(self):
        """Load optional API keys from environment."""
        # Only load if they exist - all are optional
        self.config.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.config.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.config.alchemy_api_key = os.getenv('ALCHEMY_API_KEY')
        self.config.infura_api_key = os.getenv('INFURA_API_KEY')
        self.config.moralis_api_key = os.getenv('MORALIS_API_KEY')
        self.config.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY')
    
    def get_rpc_url(self, chain: str) -> str:
        """Get the best available RPC URL for a chain."""
        rpc_lists = {
            'ethereum': self.config.ethereum_rpc_urls,
            'base': self.config.base_rpc_urls,
            'bsc': self.config.bsc_rpc_urls,
            'polygon': self.config.polygon_rpc_urls
        }
        
        urls = rpc_lists.get(chain, [])
        if not urls:
            raise ValueError(f"No RPC URLs configured for chain: {chain}")
        
        # Add API key to premium services if available
        if self.config.alchemy_api_key:
            if chain == 'ethereum':
                urls.insert(0, f"https://eth-mainnet.g.alchemy.com/v2/{self.config.alchemy_api_key}")
            elif chain == 'base':
                urls.insert(0, f"https://base-mainnet.g.alchemy.com/v2/{self.config.alchemy_api_key}")
        
        if self.config.infura_api_key:
            if chain == 'ethereum':
                urls.insert(0, f"https://mainnet.infura.io/v3/{self.config.infura_api_key}")
        
        return urls[0]  # Return primary URL
    
    def get_all_rpc_urls(self, chain: str) -> List[str]:
        """Get all available RPC URLs for failover."""
        return {
            'ethereum': self.config.ethereum_rpc_urls,
            'base': self.config.base_rpc_urls,
            'bsc': self.config.bsc_rpc_urls,
            'polygon': self.config.polygon_rpc_urls
        }.get(chain, [])

# Free API endpoints that don't require keys
FREE_ENDPOINTS = {
    'coingecko': {
        'base_url': 'https://api.coingecko.com/api/v3',
        'rate_limit': '10-50 calls/minute',
        'endpoints': {
            'price': '/simple/price',
            'token_info': '/coins/{id}',
            'market_data': '/coins/markets'
        }
    },
    
    'dexscreener': {
        'base_url': 'https://api.dexscreener.com/latest',
        'rate_limit': 'Generous, no key needed',
        'endpoints': {
            'pairs': '/dex/pairs/{chainId}/{pairAddress}',
            'tokens': '/dex/tokens/{tokenAddress}',
            'search': '/dex/search/?q={query}'
        }
    },
    
    'the_graph': {
        'base_url': 'https://api.thegraph.com/subgraphs/name',
        'rate_limit': '1000 queries/month free',
        'endpoints': {
            'uniswap_v2': '/uniswap/uniswap-v2',
            'uniswap_v3': '/uniswap/uniswap-v3',
            'pancakeswap': '/pancakeswap/pairs'
        }
    }
}

# Usage examples
def get_token_price_free(token_address: str) -> dict:
    """Get token price using free CoinGecko API."""
    import requests
    
    url = f"{FREE_ENDPOINTS['coingecko']['base_url']}/simple/token_price/ethereum"
    params = {
        'contract_addresses': token_address,
        'vs_currencies': 'usd'
    }
    
    response = requests.get(url, params=params)
    return response.json()

def get_dex_data_free(token_address: str) -> dict:
    """Get DEX data using free DexScreener API."""
    import requests
    
    url = f"{FREE_ENDPOINTS['dexscreener']['base_url']}/dex/tokens/{token_address}"
    response = requests.get(url)
    return response.json()

# Create global instance
free_api_manager = FreeAPIManager()