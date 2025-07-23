"""
Trading configuration for real execution.
Contains DEX addresses, token lists, and trading parameters.
"""

import os
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import timedelta


# DEX Router Addresses
DEX_ROUTERS = {
    "ethereum": {
        "uniswap_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "uniswap_v3_router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "uniswap_v3_quoter": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
        "sushiswap": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
        "1inch": "0x1111111254EEB25477B68fb85Ed929f73A960582"
    },
    "base": {
        "uniswap_v2": "0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24",
        "uniswap_v3": "0x2626664c2603336E57B271c5C0b26F421741e481",
        "baseswap": "0x327Df1E6de05895d2ab08513aaDD9313Fe505d86",
        "aerodrome": "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43"
    },
    "bsc": {
        "pancakeswap_v2": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        "pancakeswap_v3": "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",
        "biswap": "0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8"
    },
    "arbitrum": {
        "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "sushiswap": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "camelot": "0xc873fEcbd354f5A56E00E710B90EF4201db2448d"
    }
}


# DEX Factory Addresses
DEX_FACTORIES = {
    "ethereum": {
        "uniswap_v2": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
        "uniswap_v3": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "sushiswap": "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac"
    },
    "base": {
        "uniswap_v2": "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6",
        "baseswap": "0xFDa619b6d20975be80A10332cD39b9a4b0FAa8BB"
    }
}


# WETH/Native Token Addresses
WRAPPED_NATIVE_TOKENS = {
    "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
    "base": "0x4200000000000000000000000000000000000006",      # WETH
    "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",       # WBNB
    "arbitrum": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",   # WETH
    "optimism": "0x4200000000000000000000000000000000000006",   # WETH
    "polygon": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",    # WMATIC
    "avalanche": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7"   # WAVAX
}


# Stablecoin Addresses
STABLECOINS = {
    "ethereum": {
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "FRAX": "0x853d955aCEf822Db058eb8505911ED77F175b99e"
    },
    "base": {
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",
        "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb"
    }
}


class TradingMode(Enum):
    """Trading system operation modes."""
    SIMULATION = "simulation"
    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"
    BACKTESTING = "backtesting"


class ExecutionSpeed(Enum):
    """Trade execution speed preferences."""
    ULTRA_FAST = "ultra_fast"  # MEV protection, direct nodes
    FAST = "fast"              # Standard with gas optimization
    NORMAL = "normal"          # Standard execution
    SAFE = "safe"              # Extra confirmations


class RiskProfile(Enum):
    """Risk tolerance profiles."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


@dataclass
class GasConfiguration:
    """
    Gas configuration for transaction execution.
    
    Attributes:
        strategy: Gas pricing strategy to use
        max_gas_price_gwei: Maximum gas price in gwei
        priority_fee_gwei: Priority fee for EIP-1559 transactions
        gas_limit_multiplier: Multiplier for estimated gas limit
        rapid_mode_multiplier: Multiplier for rapid execution mode
    """
    strategy: str = "adaptive"  # fixed, adaptive, aggressive
    max_gas_price_gwei: int = 100
    priority_fee_gwei: int = 2
    gas_limit_multiplier: float = 1.2
    rapid_mode_multiplier: float = 1.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'strategy': self.strategy,
            'max_gas_price_gwei': self.max_gas_price_gwei,
            'priority_fee_gwei': self.priority_fee_gwei,
            'gas_limit_multiplier': self.gas_limit_multiplier,
            'rapid_mode_multiplier': self.rapid_mode_multiplier
        }


@dataclass
class SlippageConfiguration:
    """
    Slippage tolerance configuration.
    
    Attributes:
        default_tolerance: Default slippage tolerance percentage
        max_tolerance: Maximum allowed slippage
        auto_adjust: Whether to auto-adjust based on volatility
        chain_overrides: Chain-specific slippage settings
    """
    default_tolerance: float = 0.02  # 2%
    max_tolerance: float = 0.10      # 10%
    auto_adjust: bool = True
    chain_overrides: Dict[str, float] = field(default_factory=lambda: {
        "ethereum": 0.02,
        "base": 0.03,
        "bsc": 0.05,
        "arbitrum": 0.02
    })
    
    def get_tolerance(self, chain: str) -> float:
        """
        Get slippage tolerance for specific chain.
        
        Args:
            chain: Chain name
            
        Returns:
            Slippage tolerance as decimal
        """
        return self.chain_overrides.get(chain, self.default_tolerance)


@dataclass
class MEVProtectionConfig:
    """
    MEV (Maximum Extractable Value) protection configuration.
    
    Attributes:
        enabled: Whether MEV protection is enabled
        flashbots_enabled: Use Flashbots for Ethereum
        private_mempool: Use private mempools when available
        bundle_timeout: Timeout for bundle inclusion
        max_priority_fee: Maximum priority fee for MEV protection
    """
    enabled: bool = True
    flashbots_enabled: bool = True
    private_mempool: bool = True
    bundle_timeout: int = 30  # seconds
    max_priority_fee: Decimal = Decimal('10')  # gwei
    
    def should_use_flashbots(self, chain: str) -> bool:
        """Check if Flashbots should be used for chain."""
        return self.enabled and self.flashbots_enabled and chain == "ethereum"


@dataclass
class PositionLimits:
    """
    Position size and risk limits configuration.
    
    Attributes:
        max_position_size_usd: Maximum single position in USD
        max_total_exposure_usd: Maximum total portfolio exposure
        max_positions_per_chain: Maximum concurrent positions per chain
        max_percentage_of_liquidity: Maximum percentage of pool liquidity
        min_liquidity_usd: Minimum required liquidity in pool
    """
    max_position_size_usd: float = 1000.0
    max_total_exposure_usd: float = 10000.0
    max_positions_per_chain: int = 5
    max_percentage_of_liquidity: float = 0.02  # 2% of pool
    min_liquidity_usd: float = 50000.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'max_position_size_usd': self.max_position_size_usd,
            'max_total_exposure_usd': self.max_total_exposure_usd,
            'max_positions_per_chain': self.max_positions_per_chain,
            'max_percentage_of_liquidity': self.max_percentage_of_liquidity,
            'min_liquidity_usd': self.min_liquidity_usd
        }


@dataclass
class MonitoringConfig:
    """
    Token monitoring configuration.
    
    Attributes:
        check_interval: How often to check for new tokens (seconds)
        max_token_age: Maximum age of token to consider (seconds)
        min_holders: Minimum number of holders required
        blacklisted_tokens: List of token addresses to ignore
        whitelisted_deployers: List of trusted deployer addresses
    """
    check_interval: float = 1.0
    max_token_age: int = 300  # 5 minutes
    min_holders: int = 10
    blacklisted_tokens: List[str] = field(default_factory=list)
    whitelisted_deployers: List[str] = field(default_factory=list)
    
    def is_token_blacklisted(self, token_address: str) -> bool:
        """Check if token is blacklisted."""
        return token_address.lower() in [t.lower() for t in self.blacklisted_tokens]
    
    def is_deployer_whitelisted(self, deployer_address: str) -> bool:
        """Check if deployer is whitelisted."""
        return deployer_address.lower() in [d.lower() for d in self.whitelisted_deployers]


@dataclass
class ExitStrategyConfig:
    """
    Exit strategy configuration for positions.
    
    Attributes:
        stop_loss_percentage: Stop loss as percentage of entry
        take_profit_percentage: Take profit as percentage of entry
        trailing_stop_percentage: Trailing stop distance
        time_based_exit_minutes: Exit after X minutes if no profit
        partial_exit_levels: Levels for partial position exits
    """
    stop_loss_percentage: float = 0.10  # 10%
    take_profit_percentage: float = 0.50  # 50%
    trailing_stop_percentage: float = 0.05  # 5%
    time_based_exit_minutes: int = 30
    partial_exit_levels: List[Dict[str, float]] = field(default_factory=lambda: [
        {"percentage": 0.25, "at_profit": 0.20},  # Exit 25% at 20% profit
        {"percentage": 0.50, "at_profit": 0.35},  # Exit 50% at 35% profit
    ])
    
    def calculate_stop_loss(self, entry_price: Decimal) -> Decimal:
        """Calculate stop loss price."""
        return entry_price * Decimal(1 - self.stop_loss_percentage)
    
    def calculate_take_profit(self, entry_price: Decimal) -> Decimal:
        """Calculate take profit price."""
        return entry_price * Decimal(1 + self.take_profit_percentage)


@dataclass
class TradingConfig:
    """
    Master trading configuration class.
    Consolidates all trading parameters and settings.
    """
    # Trading mode and behavior
    mode: TradingMode = TradingMode.SIMULATION
    execution_speed: ExecutionSpeed = ExecutionSpeed.FAST
    risk_profile: RiskProfile = RiskProfile.MODERATE
    
    # Component configurations
    gas: GasConfiguration = field(default_factory=GasConfiguration)
    slippage: SlippageConfiguration = field(default_factory=SlippageConfiguration)
    mev_protection: MEVProtectionConfig = field(default_factory=MEVProtectionConfig)
    position_limits: PositionLimits = field(default_factory=PositionLimits)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    exit_strategy: ExitStrategyConfig = field(default_factory=ExitStrategyConfig)
    
    # Chain-specific settings
    enabled_chains: List[str] = field(default_factory=lambda: ["ethereum", "base"])
    preferred_dexes: Dict[str, List[str]] = field(default_factory=lambda: {
        "ethereum": ["uniswap_v2", "uniswap_v3"],
        "base": ["uniswap_v2", "baseswap"],
        "bsc": ["pancakeswap_v2"],
        "arbitrum": ["uniswap_v3", "sushiswap"]
    })
    
    # Advanced settings
    use_flashloans: bool = False
    enable_arbitrage: bool = False
    enable_sandwich_protection: bool = True
    
    @classmethod
    def from_env(cls) -> "TradingConfig":
        """
        Create configuration from environment variables.
        
        Returns:
            TradingConfig instance with settings from environment
        """
        config = cls()
        
        # Load mode
        mode_str = os.getenv("TRADING_MODE", "simulation").lower()
        config.mode = TradingMode(mode_str)
        
        # Load limits
        if os.getenv("MAX_POSITION_SIZE_USD"):
            config.position_limits.max_position_size_usd = float(
                os.getenv("MAX_POSITION_SIZE_USD")
            )
        
        # Load gas settings
        if os.getenv("MAX_GAS_PRICE_GWEI"):
            config.gas.max_gas_price_gwei = int(
                os.getenv("MAX_GAS_PRICE_GWEI")
            )
        
        # Load slippage
        if os.getenv("SLIPPAGE_TOLERANCE"):
            config.slippage.default_tolerance = float(
                os.getenv("SLIPPAGE_TOLERANCE")
            )
        
        return config
    
    def validate(self) -> List[str]:
        """
        Validate configuration settings.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate position limits
        if self.position_limits.max_position_size_usd <= 0:
            errors.append("max_position_size_usd must be positive")
        
        if self.position_limits.max_position_size_usd > self.position_limits.max_total_exposure_usd:
            errors.append("max_position_size_usd cannot exceed max_total_exposure_usd")
        
        # Validate slippage
        if not 0 < self.slippage.default_tolerance <= 1:
            errors.append("slippage tolerance must be between 0 and 1")
        
        # Validate gas
        if self.gas.max_gas_price_gwei <= 0:
            errors.append("max_gas_price_gwei must be positive")
        
        # Validate exit strategy
        if self.exit_strategy.stop_loss_percentage >= 1:
            errors.append("stop_loss_percentage must be less than 1")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            'mode': self.mode.value,
            'execution_speed': self.execution_speed.value,
            'risk_profile': self.risk_profile.value,
            'gas': self.gas.to_dict(),
            'slippage': {
                'default_tolerance': self.slippage.default_tolerance,
                'max_tolerance': self.slippage.max_tolerance,
                'auto_adjust': self.slippage.auto_adjust
            },
            'position_limits': self.position_limits.to_dict(),
            'enabled_chains': self.enabled_chains,
            'preferred_dexes': self.preferred_dexes
        }


# Create default configuration instance
default_config = TradingConfig()

# Export utility functions
def get_dex_router(chain: str, dex: str) -> Optional[str]:
    """
    Get DEX router address for chain and DEX.
    
    Args:
        chain: Chain name
        dex: DEX name
        
    Returns:
        Router address or None if not found
    """
    return DEX_ROUTERS.get(chain, {}).get(dex)


def get_wrapped_native_token(chain: str) -> Optional[str]:
    """
    Get wrapped native token address for chain.
    
    Args:
        chain: Chain name
        
    Returns:
        Wrapped native token address or None
    """
    return WRAPPED_NATIVE_TOKENS.get(chain)


def get_stablecoins(chain: str) -> Dict[str, str]:
    """
    Get stablecoin addresses for chain.
    
    Args:
        chain: Chain name
        
    Returns:
        Dictionary of stablecoin symbol to address
    """
    return STABLECOINS.get(chain, {})