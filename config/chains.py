# config/chains.py
"""
Multi-chain configuration for DEX sniping across different networks.
Supports Ethereum, Base, and Solana ecosystems.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

class ChainType(Enum):
    """Supported blockchain networks."""
    ETHEREUM = "ethereum"
    BASE = "base"
    SOLANA = "solana"

@dataclass
class ChainConfig:
    """Configuration for a specific blockchain."""
    name: str
    chain_id: int
    rpc_url: str
    block_time: float  # seconds
    gas_token: str
    dex_factory: str
    dex_router: str
    wrapped_native: str
    stable_tokens: List[str]
    min_liquidity_usd: float
    max_gas_price: float

@dataclass
class SolanaConfig:
    """Special configuration for Solana ecosystem."""
    rpc_url: str
    pump_fun_program: str
    pump_fun_api: str
    raydium_program: str
    jupiter_api: str
    wsol_address: str
    usdc_address: str

class MultiChainSettings:
    """Multi-chain configuration manager."""
    
    def __init__(self):
        self.chains = self._initialize_chains()
        self.solana = self._initialize_solana()
        
        # Portfolio settings
        self.max_position_per_chain = {
            ChainType.ETHEREUM: 0.1,  # ETH
            ChainType.BASE: 0.5,      # ETH on Base
            ChainType.SOLANA: 100,    # SOL
        }
        
        # Risk allocation
        self.chain_allocation = {
            ChainType.ETHEREUM: 0.3,  # 30% - Higher quality, higher cost
            ChainType.BASE: 0.4,      # 40% - Good balance
            ChainType.SOLANA: 0.3,    # 30% - High volume, low cost
        }
        
    def _initialize_chains(self) -> Dict[ChainType, ChainConfig]:
        """Initialize EVM-compatible chain configurations."""
        return {
            ChainType.ETHEREUM: ChainConfig(
                name="Ethereum",
                chain_id=1,
                rpc_url="https://ethereum-rpc.publicnode.com",  # Updated RPC with full eth_newFilter support
                block_time=12.0,
                gas_token="ETH",
                dex_factory="0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
                dex_router="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                wrapped_native="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                stable_tokens=[
                    "0xA0b86a33E6441019fad5B4A55745e22A85e5Db69",  # USDC
                    "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
                ],
                min_liquidity_usd=1000,
                max_gas_price=50
            ),
            
            ChainType.BASE: ChainConfig(
                name="Base",
                chain_id=8453,
                rpc_url="https://mainnet.base.org",
                block_time=2.0,
                gas_token="ETH",
                dex_factory="0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6",
                dex_router="0x327Df1E6de05895d2ab08513aaDD9313Fe505d86",
                wrapped_native="0x4200000000000000000000000000000000000006",
                stable_tokens=[
                    "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
                ],
                min_liquidity_usd=500,
                max_gas_price=0.1
            )
        }
    
    def _initialize_solana(self) -> SolanaConfig:
        """Initialize Solana-specific configuration."""
        return SolanaConfig(
            rpc_url="https://api.mainnet-beta.solana.com",
            pump_fun_program="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
            pump_fun_api="https://frontend-api.pump.fun",  # Note: This API has rate limits
            raydium_program="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
            jupiter_api="https://price.jup.ag/v6",  # Updated to v6 API
            wsol_address="So11111111111111111111111111111111111111112",
            usdc_address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        )
    
    def get_chain_config(self, chain: ChainType) -> ChainConfig:
        """Get configuration for a specific chain."""
        return self.chains[chain]
    
    def get_active_chains(self) -> List[ChainType]:
        """Get list of currently active chains."""
        return [ChainType.ETHEREUM, ChainType.BASE, ChainType.SOLANA]
    

# Global multi-chain settings
multichain_settings = MultiChainSettings()