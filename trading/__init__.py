#!/usr/bin/env python3
"""
Trading execution system for DEX sniping.

Contains the enhanced trading components for automated execution,
risk management, and position tracking.

File: trading/__init__.py
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
    
    # Import legacy components if they exist - but they don't, so create placeholders
    class TradingExecutor:
        def __init__(self, *args, **kwargs):
            pass
    
    class TradingMode:
        DISABLED = "disabled"
        PAPER_ONLY = "paper_only"
        LIVE_TRADING = "live_trading"
        SEMI_AUTO = "semi_auto"
    
    class ExecutionDecision:
        EXECUTE = "execute"
        SKIP = "skip"
        MONITOR = "monitor"
        REJECT = "reject"

# Import the classes from the correct modules
try:
    # Import from execution_engine.py instead of non-existent executor.py
    from .execution_engine import TradeOrder, OrderType, OrderStatus, ExecutionResult
except ImportError:
    # Create minimal compatibility layer if execution_engine is missing
    from enum import Enum
    from dataclasses import dataclass
    from typing import Optional
    from decimal import Decimal
    from datetime import datetime
    
    class OrderType(Enum):
        BUY = "buy"
        SELL = "sell"
    
    class OrderStatus(Enum):
        PENDING = "pending"
        SUBMITTED = "submitted"
        CONFIRMED = "confirmed"
        FAILED = "failed"
        CANCELLED = "cancelled"
    
    # Legacy aliases for backward compatibility
    TradeType = OrderType
    TradeStatus = OrderStatus
    
    @dataclass
    class TradeConfig:
        """Legacy trade configuration."""
        max_slippage: float = 0.05
        auto_execute: bool = False
        position_size_eth: float = 0.1
        stop_loss_percentage: float = 0.15
        take_profit_percentage: float = 0.50
    
    @dataclass
    class TradeOrder:
        """Trade order representation."""
        id: str
        order_type: OrderType
        token_address: str
        token_symbol: str
        chain: str
        amount: Decimal
        target_price: Optional[Decimal]
        status: OrderStatus
        created_time: datetime
        submitted_time: Optional[datetime] = None
        confirmed_time: Optional[datetime] = None
        tx_hash: Optional[str] = None
        gas_limit: Optional[int] = None
        gas_price: Optional[int] = None
        metadata: Optional[dict] = None

        def __post_init__(self):
            if self.metadata is None:
                self.metadata = {}
    
    @dataclass
    class ExecutionResult:
        """Execution result representation."""
        success: bool
        order_id: str
        tx_hash: Optional[str]
        amount_in: Decimal
        amount_out: Decimal
        actual_price: Decimal
        gas_used: Optional[int]
        gas_cost: Decimal
        execution_time: datetime
        error_message: Optional[str] = None
        metadata: Optional[dict] = None

        def __post_init__(self):
            if self.metadata is None:
                self.metadata = {}

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
    
    # Execution components
    'TradeOrder',
    'OrderType',
    'OrderStatus', 
    'ExecutionResult',
    
    # Legacy components (backward compatibility)
    'TradeConfig',
    'TradeType',  # Alias for OrderType
    'TradeStatus'  # Alias for OrderStatus
]