#!/usr/bin/env python3
"""
Trading execution system for DEX sniping.

Contains the enhanced trading components for automated execution,
risk management, and position tracking.
"""

# Import the new enhanced components
try:
    from .risk_manager import EnhancedRiskManager, PortfolioLimits, MarketCondition, RiskAssessment
    from .position_manager import PositionManager, Position, PositionStatus, ExitReason
    from .execution_engine import ExecutionEngine
    from .trading_executor import TradingExecutor, TradingMode, ExecutionDecision
except ImportError as e:
    # Fallback for backward compatibility
    print(f"Warning: Could not import enhanced trading components: {e}")
    
    # Import legacy components if they exist
    try:
        from .executor import TradingExecutor, TradeConfig, TradeOrder, TradeType, OrderType, TradeStatus
    except ImportError:
        # Create placeholder classes if nothing exists
        class TradingExecutor:
            def __init__(self, *args, **kwargs):
                pass
        
        class TradeConfig:
            def __init__(self, *args, **kwargs):
                pass

# Define what should be available when importing from trading
__all__ = [
    # Enhanced components (preferred)
    'EnhancedRiskManager',
    'PortfolioLimits', 
    'MarketCondition',
    'RiskAssessment',
    'PositionManager',
    'Position',
    'PositionStatus',
    'ExitReason',
    'ExecutionEngine',
    'TradingExecutor',
    'TradingMode',
    'ExecutionDecision',
    
    # Legacy components (backward compatibility)
    'TradeConfig',
    'TradeOrder', 
    'TradeType',
    'OrderType',
    'TradeStatus'
]

# Ensure backward compatibility
try:
    # If legacy imports are available, make them accessible
    from .executor import TradeConfig, TradeOrder, TradeType, OrderType, TradeStatus
except ImportError:
    # Create minimal compatibility layer
    from enum import Enum
    from dataclasses import dataclass
    from typing import Optional
    from decimal import Decimal
    
    class TradeType(Enum):
        BUY = "buy"
        SELL = "sell"
    
    class TradeStatus(Enum):
        PENDING = "pending"
        CONFIRMED = "confirmed"
        FAILED = "failed"
    
    class OrderType(Enum):
        MARKET = "market"
        LIMIT = "limit"
    
    @dataclass
    class TradeConfig:
        max_slippage: float = 0.05
        auto_execute: bool = False
        position_size_eth: float = 0.1
        stop_loss_percentage: float = 0.15
        take_profit_percentage: float = 0.50
    
    @dataclass
    class TradeOrder:
        id: str
        trade_type: TradeType
        token_address: str
        amount: Decimal
        status: TradeStatus = TradeStatus.PENDING