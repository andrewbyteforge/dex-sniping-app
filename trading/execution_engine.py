"""
Trade execution engine for interacting with DEXs and executing trades.
Handles order placement, transaction monitoring, and execution confirmation.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
from web3 import Web3
from web3.contract import Contract

from models.token import TradingOpportunity
from trading.risk_manager import RiskManager, PositionSizeResult
from trading.position_manager import PositionManager, Position
from trading.executor import TradeOrder, TradeType, TradeStatus, OrderType
from utils.logger import logger_manager


class ExecutionResult(Enum):
    """Result of trade execution attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    SLIPPAGE_EXCEEDED = "slippage_exceeded"
    GAS_ESTIMATION_FAILED = "gas_estimation_failed"
    TRANSACTION_FAILED = "transaction_failed"
    TIMEOUT = "timeout"


@dataclass
class ExecutionParams:
    """Parameters for trade execution."""
    token_address: str
    amount_in: Decimal
    min_amount_out: Decimal
    slippage_tolerance: float
    gas_price: Optional[int] = None
    gas_limit: Optional[int] = None
    deadline_minutes: int = 20


@dataclass
class ExecutionResult:
    """Result of a trade execution."""
    success: bool
    tx_hash: Optional[str] = None
    amount_in: Optional[Decimal] = None
    amount_out: Optional[Decimal] = None
    actual_price: Optional[Decimal] = None
    gas_used: Optional[int] = None
    gas_price: Optional[int] = None
    execution_time: Optional[float] = None
    error_message: Optional[str] = None
    slippage_actual: Optional[float] = None


class ExecutionEngine:
    """
    Production trade execution engine for DEX interactions.
    Handles order placement, transaction monitoring, and execution confirmation.
    """
    
    def __init__(self, risk_manager: RiskManager, position_manager: PositionManager) -> None:
        """
        Initialize the execution engine.
        
        Args:
            risk_manager: Risk management system
            position_manager: Position management system
        """
        self.logger = logger_manager.get_logger("ExecutionEngine")
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        
        # Web3 connections by chain
        self.web3_connections: Dict[str, Web3] = {}
        self.dex_contracts: Dict[str, Dict[str, Contract]] = {}
        
        # Execution tracking
        self.pending_orders: Dict[str, TradeOrder] = {}
        self.execution_history: List[ExecutionResult] = []
        
        # Performance metrics
        self.total_executions = 0
        self.successful_executions = 0
        self.total_gas_used = 0
        self.average_execution_time = 0.0
        
        # Configuration
        self.max_concurrent_orders = 10
        self.transaction_timeout = 300  # 5 minutes
        self.monitoring_active = False
        
    async def initialize(self) -> None:
        """Initialize the execution engine and Web3 connections."""
        try:
            self.logger.info("Initializing execution engine...")
            
            # Initialize Web3 connections
            await self._initialize_web3_connections()
            
            # Initialize DEX contracts
            await self._initialize_dex_contracts()
            
            # Start transaction monitoring
            await self._start_monitoring()
            
            self.logger.info("Execution engine initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize execution engine: {e}")
            raise
    
    async def execute_buy_order(
        self, 
        opportunity: TradingOpportunity,
        risk_assessment: PositionSizeResult
    ) -> Optional[Position]:
        """
        Execute a buy order for a trading opportunity.
        
        Args:
            opportunity: Trading opportunity to execute
            risk_assessment: Risk assessment result with position sizing
            
        Returns:
            Position object if successful, None otherwise
        """
        try:
            if risk_assessment.approved_amount <= 0:
                self.logger.warning(f"Buy order rejected: {opportunity.token.symbol} - No approved amount")
                return None
                
            self.logger.info(f"Executing buy order: {opportunity.token.symbol}")
            
            # Create trade order
            order = self._create_buy_order(opportunity, risk_assessment)
            
            # Execute the trade
            execution_result = await self._execute_order(order, opportunity)
            
            if execution_result.success:
                # Create position
                position = await self.position_manager.open_position(
                    opportunity=opportunity,
                    entry_price=execution_result.actual_price,
                    entry_amount=execution_result.amount_out,
                    entry_tx_hash=execution_result.tx_hash
                )
                
                self.logger.info(
                    f"Buy order successful: {opportunity.token.symbol} - "
                    f"TX: {execution_result.tx_hash}, Position: {position.id if position else 'Failed'}"
                )
                
                return position
            else:
                self.logger.error(
                    f"Buy order failed: {opportunity.token.symbol} - {execution_result.error_message}"
                )
                return None
                
        except Exception as e:
            self.logger.error(f"Buy order execution failed for {opportunity.token.symbol}: {e}")
            return None
    
    async def execute_sell_order(self, position: Position) -> bool:
        """
        Execute a sell order to close a position.
        
        Args:
            position: Position to close
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Executing sell order: {position.token_symbol}")
            
            # Create sell order
            order = self._create_sell_order(position)
            
            # Execute the trade
            execution_result = await self._execute_order(order)
            
            if execution_result.success:
                # Close position
                await self.position_manager.close_position(
                    position_id=position.id,
                    exit_price=execution_result.actual_price,
                    exit_reason=position_manager.ExitReason.MANUAL,
                    exit_tx_hash=execution_result.tx_hash
                )
                
                self.logger.info(
                    f"Sell order successful: {position.token_symbol} - TX: {execution_result.tx_hash}"
                )
                return True
            else:
                self.logger.error(
                    f"Sell order failed: {position.token_symbol} - {execution_result.error_message}"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Sell order execution failed for {position.token_symbol}: {e}")
            return False
    
    def _create_buy_order(
        self, 
        opportunity: TradingOpportunity, 
        risk_assessment: PositionSizeResult
    ) -> TradeOrder:
        """
        Create a buy order from opportunity and risk assessment.
        
        Args:
            opportunity: Trading opportunity
            risk_assessment: Risk assessment with position sizing
            
        Returns:
            TradeOrder ready for execution
        """
        try:
            order_id = f"BUY_{opportunity.token.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            return TradeOrder(
                id=order_id,
                opportunity_id=opportunity.metadata.get('opportunity_id', ''),
                trade_type=TradeType.BUY,
                order_type=OrderType.MARKET,
                token_address=opportunity.token.address,
                token_symbol=opportunity.token.symbol,
                chain=opportunity.metadata.get('chain', 'ETHEREUM'),
                amount=risk_assessment.approved_amount,
                slippage=0.05,  # 5% default slippage
                status=TradeStatus.PENDING
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create buy order: {e}")
            raise
    
    def _create_sell_order(self, position: Position) -> TradeOrder:
        """
        Create a sell order from position.
        
        Args:
            position: Position to close
            
        Returns:
            TradeOrder ready for execution
        """
        try:
            order_id = f"SELL_{position.token_symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            return TradeOrder(
                id=order_id,
                opportunity_id=position.id,
                trade_type=TradeType.SELL,
                order_type=OrderType.MARKET,
                token_address=position.token_address,
                token_symbol=position.token_symbol,
                chain=position.chain,
                amount=position.entry_amount,
                slippage=0.05,  # 5% default slippage
                status=TradeStatus.PENDING
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create sell order: {e}")
            raise
    
    async def _execute_order(
        self, 
        order: TradeOrder, 
        opportunity: Optional[TradingOpportunity] = None
    ) -> ExecutionResult:
        """
        Execute a trade order on the appropriate DEX.
        
        Args:
            order: Trade order to execute
            opportunity: Optional trading opportunity for additional context
            
        Returns:
            ExecutionResult with execution details
        """
        try:
            start_time = datetime.now()
            order.status = TradeStatus.EXECUTING
            
            self.logger.debug(f"Executing order: {order.id}")
            
            # Get chain-specific execution
            if order.chain.upper() in ['ETHEREUM', 'BASE']:
                result = await self._execute_evm_order(order, opportunity)
            elif 'SOLANA' in order.chain.upper():
                result = await self._execute_solana_order(order, opportunity)
            else:
                result = ExecutionResult(
                    success=False,
                    error_message=f"Unsupported chain: {order.chain}"
                )
            
            # Update execution metrics
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            
            self.total_executions += 1
            if result.success:
                self.successful_executions += 1
                order.status = TradeStatus.COMPLETED
                order.executed_at = datetime.now()
                order.tx_hash = result.tx_hash
            else:
                order.status = TradeStatus.FAILED
                order.error_message = result.error_message
            
            # Update average execution time
            self.average_execution_time = (
                (self.average_execution_time * (self.total_executions - 1) + execution_time) /
                self.total_executions
            )
            
            # Store execution history
            self.execution_history.append(result)
            if len(self.execution_history) > 1000:  # Keep last 1000 executions
                self.execution_history.pop(0)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Order execution failed: {e}")
            order.status = TradeStatus.FAILED
            order.error_message = str(e)
            
            return ExecutionResult(
                success=False,
                error_message=f"Execution error: {str(e)}"
            )
    
    async def _execute_evm_order(
        self, 
        order: TradeOrder, 
        opportunity: Optional[TradingOpportunity] = None
    ) -> ExecutionResult:
        """
        Execute order on EVM-compatible chain (Ethereum, Base).
        
        Args:
            order: Trade order to execute
            opportunity: Optional trading opportunity
            
        Returns:
            ExecutionResult with execution details
        """
        try:
            # This is a placeholder implementation
            # In production, this would:
            # 1. Get Web3 connection for chain
            # 2. Get appropriate DEX router contract
            # 3. Calculate swap parameters
            # 4. Estimate gas
            # 5. Send transaction
            # 6. Monitor transaction confirmation
            
            self.logger.info(f"Executing EVM order: {order.id} on {order.chain}")
            
            # Simulate successful execution for testing
            await asyncio.sleep(2)  # Simulate network delay
            
            # Simulate execution results
            if order.trade_type == TradeType.BUY:
                amount_out = order.amount * Decimal('1000000')  # Simulate token amount
                actual_price = Decimal('0.000001')  # Simulate price
            else:
                amount_out = order.amount * Decimal('0.000001')  # Simulate ETH amount
                actual_price = Decimal('1000000')  # Simulate price
            
            return ExecutionResult(
                success=True,
                tx_hash=f"0x{''.join(['a'] * 64)}",  # Placeholder tx hash
                amount_in=order.amount,
                amount_out=amount_out,
                actual_price=actual_price,
                gas_used=150000,
                gas_price=20,
                slippage_actual=0.02
            )
            
        except Exception as e:
            self.logger.error(f"EVM order execution failed: {e}")
            return ExecutionResult(
                success=False,
                error_message=f"EVM execution failed: {str(e)}"
            )
    
    async def _execute_solana_order(
        self, 
        order: TradeOrder, 
        opportunity: Optional[TradingOpportunity] = None
    ) -> ExecutionResult:
        """
        Execute order on Solana.
        
        Args:
            order: Trade order to execute
            opportunity: Optional trading opportunity
            
        Returns:
            ExecutionResult with execution details
        """
        try:
            # This is a placeholder implementation
            # In production, this would:
            # 1. Connect to Solana RPC
            # 2. Use appropriate DEX (Jupiter, Raydium, etc.)
            # 3. Create and send transaction
            # 4. Monitor confirmation
            
            self.logger.info(f"Executing Solana order: {order.id}")
            
            # Simulate successful execution
            await asyncio.sleep(1)  # Solana is faster
            
            # Simulate execution results
            if order.trade_type == TradeType.BUY:
                amount_out = order.amount * Decimal('1000000')  # Simulate token amount
                actual_price = Decimal('0.0001')  # Simulate price
            else:
                amount_out = order.amount * Decimal('0.0001')  # Simulate SOL amount
                actual_price = Decimal('10000')  # Simulate price
            
            return ExecutionResult(
                success=True,
                tx_hash="1" * 88,  # Placeholder Solana tx hash
                amount_in=order.amount,
                amount_out=amount_out,
                actual_price=actual_price,
                gas_used=5000,  # Solana uses compute units
                gas_price=1,
                slippage_actual=0.01
            )
            
        except Exception as e:
            self.logger.error(f"Solana order execution failed: {e}")
            return ExecutionResult(
                success=False,
                error_message=f"Solana execution failed: {str(e)}"
            )
    
    async def _initialize_web3_connections(self) -> None:
        """Initialize Web3 connections for supported chains."""
        try:
            # This would initialize actual Web3 connections
            # Placeholder implementation
            self.logger.info("Web3 connections initialized (placeholder)")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Web3 connections: {e}")
            raise
    
    async def _initialize_dex_contracts(self) -> None:
        """Initialize DEX contract instances."""
        try:
            # This would initialize actual DEX contracts
            # Placeholder implementation
            self.logger.info("DEX contracts initialized (placeholder)")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize DEX contracts: {e}")
            raise
    
    async def _start_monitoring(self) -> None:
        """Start transaction monitoring."""
        try:
            self.monitoring_active = True
            # This would start actual transaction monitoring
            self.logger.info("Transaction monitoring started")
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring: {e}")
            raise
    
    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get execution performance metrics."""
        try:
            success_rate = (
                (self.successful_executions / self.total_executions * 100) 
                if self.total_executions > 0 else 0
            )
            
            return {
                'total_executions': self.total_executions,
                'successful_executions': self.successful_executions,
                'success_rate_percentage': round(success_rate, 2),
                'average_execution_time_seconds': round(self.average_execution_time, 2),
                'total_gas_used': self.total_gas_used,
                'pending_orders': len(self.pending_orders),
                'recent_executions': [
                    {
                        'success': result.success,
                        'execution_time': result.execution_time,
                        'gas_used': result.gas_used,
                        'error': result.error_message
                    }
                    for result in self.execution_history[-10:]  # Last 10 executions
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get execution metrics: {e}")
            return {}
        
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get portfolio summary (delegates to position manager if available).
        
        Returns:
            Portfolio summary dictionary
        """
        try:
            if hasattr(self, 'position_manager') and self.position_manager:
                return self.position_manager.get_portfolio_summary()
            
            # Fallback basic summary from execution engine
            success_rate = (
                (self.successful_executions / self.total_executions * 100) 
                if self.total_executions > 0 else 0
            )
            
            return {
                'total_positions': 0,
                'total_trades': self.total_executions,
                'successful_trades': self.successful_executions,
                'success_rate': round(success_rate, 2),
                'total_profit': 0.0,
                'daily_losses': 0.0,
                'active_orders': len(self.pending_orders),
                'average_execution_time': round(self.average_execution_time, 2),
                'total_gas_used': self.total_gas_used
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get portfolio summary: {e}")
            return {
                'total_positions': 0,
                'total_trades': 0,
                'successful_trades': 0,
                'success_rate': 0.0,
                'total_profit': 0.0,
                'daily_losses': 0.0,
                'active_orders': 0
            }