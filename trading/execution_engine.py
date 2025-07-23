#!/usr/bin/env python3
"""
Basic execution engine for automated trading with comprehensive error handling.

Handles order placement, transaction monitoring, and execution confirmation
with support for both paper trading and live execution.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json

from models.token import TradingOpportunity
from trading.risk_manager import PositionSizeResult
from trading.position_manager import Position, PositionStatus
from utils.logger import logger_manager


class OrderType(Enum):
    """Types of trading orders."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Status of trading orders."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TradeOrder:
    """Represents a trading order."""
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
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ExecutionResult:
    """Result of trade execution."""
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
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ExecutionEngine:
    """
    Basic execution engine for automated trading.
    
    Handles:
    - Order creation and submission
    - Transaction monitoring and confirmation
    - Paper trading simulation
    - Gas optimization (basic)
    - Error handling and retry logic
    """

    def __init__(self, risk_manager, position_manager) -> None:
        """
        Initialize the execution engine.
        
        Args:
            risk_manager: Risk management system
            position_manager: Position management system
        """
        self.logger = logger_manager.get_logger("ExecutionEngine")
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        
        # Order tracking
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
        self.paper_trading_mode = True  # Default to paper trading
        
        # Simulated execution parameters
        self.simulation_success_rate = 0.95  # 95% success rate for paper trades
        self.simulation_slippage = 0.005  # 0.5% average slippage

    async def initialize(self) -> None:
        """Initialize the execution engine."""
        try:
            self.logger.info("Initializing execution engine...")
            
            # Start transaction monitoring
            if not self.monitoring_active:
                asyncio.create_task(self._monitoring_loop())
                self.monitoring_active = True
            
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
                
            token_symbol = opportunity.token.symbol or "UNKNOWN"
            self.logger.info(f"🔥 Executing buy order: {token_symbol}")
            
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
                
                if position:
                    # Set up risk management parameters
                    if risk_assessment.recommended_stop_loss:
                        stop_loss_price = execution_result.actual_price * (1 - Decimal(str(risk_assessment.recommended_stop_loss)))
                        position.stop_loss_price = stop_loss_price
                    
                    if risk_assessment.recommended_take_profit:
                        take_profit_price = execution_result.actual_price * (1 + Decimal(str(risk_assessment.recommended_take_profit)))
                        position.take_profit_price = take_profit_price
                    
                    if risk_assessment.max_hold_time_hours:
                        position.max_hold_time = timedelta(hours=risk_assessment.max_hold_time_hours)
                    
                    # Update position in manager
                    await self.position_manager.update_position(position)
                
                self.logger.info(
                    f"✅ Buy order successful: {token_symbol} - "
                    f"TX: {execution_result.tx_hash}, Position: {position.id if position else 'Failed'}"
                )
                
                return position
            else:
                self.logger.error(
                    f"❌ Buy order failed: {token_symbol} - {execution_result.error_message}"
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
            bool: True if successful, False otherwise
        """
        try:
            self.logger.info(f"🚪 Executing sell order: {position.token_symbol}")
            
            # Create sell order
            order = self._create_sell_order(position)
            
            # Create dummy opportunity for sell execution
            from models.token import TokenInfo, LiquidityInfo
            
            token_info = TokenInfo(
                address=position.token_address,
                symbol=position.token_symbol,
                name=position.token_symbol,
                decimals=18,
                price=position.current_price
            )
            
            liquidity_info = LiquidityInfo(
                liquidity_usd=10000,  # Assume sufficient liquidity
                dex_name="DEX",
                pair_address=""
            )
            
            sell_opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                timestamp=datetime.now(),
                chain=position.chain,
                metadata={'sell_order': True}
            )
            
            # Execute the sell order
            execution_result = await self._execute_order(order, sell_opportunity)
            
            if execution_result.success:
                # Update position with exit information
                position.exit_tx_hash = execution_result.tx_hash
                position.status = PositionStatus.CLOSED
                
                self.logger.info(
                    f"✅ Sell order successful: {position.token_symbol} - TX: {execution_result.tx_hash}"
                )
                return True
            else:
                self.logger.error(
                    f"❌ Sell order failed: {position.token_symbol} - {execution_result.error_message}"
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
            risk_assessment: Risk assessment result
            
        Returns:
            TradeOrder: Created buy order
        """
        import uuid
        
        return TradeOrder(
            id=str(uuid.uuid4()),
            order_type=OrderType.BUY,
            token_address=opportunity.token.address,
            token_symbol=opportunity.token.symbol or "UNKNOWN",
            chain=opportunity.chain,
            amount=risk_assessment.approved_amount,
            target_price=opportunity.token.price,
            status=OrderStatus.PENDING,
            created_time=datetime.now(),
            metadata={
                'risk_score': risk_assessment.risk_score,
                'confidence_score': risk_assessment.confidence_score,
                'max_loss_usd': risk_assessment.max_loss_usd,
                'dex_name': opportunity.liquidity.dex_name
            }
        )

    def _create_sell_order(self, position: Position) -> TradeOrder:
        """
        Create a sell order from position.
        
        Args:
            position: Position to close
            
        Returns:
            TradeOrder: Created sell order
        """
        import uuid
        
        return TradeOrder(
            id=str(uuid.uuid4()),
            order_type=OrderType.SELL,
            token_address=position.token_address,
            token_symbol=position.token_symbol,
            chain=position.chain,
            amount=position.entry_amount,
            target_price=position.current_price,
            status=OrderStatus.PENDING,
            created_time=datetime.now(),
            metadata={
                'position_id': position.id,
                'entry_price': str(position.entry_price),
                'current_pnl': str(position.unrealized_pnl)
            }
        )

    async def _execute_order(
        self, 
        order: TradeOrder, 
        opportunity: TradingOpportunity
    ) -> ExecutionResult:
        """
        Execute a trading order.
        
        Args:
            order: Trading order to execute
            opportunity: Associated trading opportunity
            
        Returns:
            ExecutionResult: Result of execution
        """
        try:
            self.total_executions += 1
            execution_start = datetime.now()
            
            # Add to pending orders
            self.pending_orders[order.id] = order
            order.status = OrderStatus.SUBMITTED
            order.submitted_time = execution_start
            
            self.logger.debug(f"Executing {order.order_type.value} order: {order.token_symbol}")
            
            # Execute based on mode
            if self.paper_trading_mode or order.metadata.get('paper_trade', False):
                result = await self._simulate_execution(order, opportunity)
            else:
                result = await self._execute_live_order(order, opportunity)
            
            # Update order status
            if result.success:
                order.status = OrderStatus.CONFIRMED
                order.confirmed_time = datetime.now()
                order.tx_hash = result.tx_hash
                self.successful_executions += 1
            else:
                order.status = OrderStatus.FAILED
            
            # Remove from pending orders
            if order.id in self.pending_orders:
                del self.pending_orders[order.id]
            
            # Add to execution history
            self.execution_history.append(result)
            
            # Update metrics
            execution_time = (datetime.now() - execution_start).total_seconds()
            self.average_execution_time = (
                (self.average_execution_time * (self.total_executions - 1) + execution_time) / 
                self.total_executions
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing order {order.id}: {e}")
            
            # Cleanup on error
            if order.id in self.pending_orders:
                del self.pending_orders[order.id]
            
            return ExecutionResult(
                success=False,
                order_id=order.id,
                tx_hash=None,
                amount_in=Decimal('0'),
                amount_out=Decimal('0'),
                actual_price=Decimal('0'),
                gas_used=None,
                gas_cost=Decimal('0'),
                execution_time=datetime.now(),
                error_message=str(e)
            )

    async def _simulate_execution(
        self, 
        order: TradeOrder, 
        opportunity: TradingOpportunity
    ) -> ExecutionResult:
        """
        Simulate order execution for paper trading.
        
        Args:
            order: Trading order
            opportunity: Trading opportunity
            
        Returns:
            ExecutionResult: Simulated execution result
        """
        try:
            # Simulate execution delay
            await asyncio.sleep(0.1)
            
            # Simulate success/failure based on success rate
            import random
            success = random.random() < self.simulation_success_rate
            
            if not success:
                return ExecutionResult(
                    success=False,
                    order_id=order.id,
                    tx_hash=None,
                    amount_in=Decimal('0'),
                    amount_out=Decimal('0'),
                    actual_price=Decimal('0'),
                    gas_used=None,
                    gas_cost=Decimal('0'),
                    execution_time=datetime.now(),
                    error_message="Simulated execution failure"
                )
            
            # Calculate simulated execution with slippage
            target_price = order.target_price or Decimal('1.0')
            slippage_factor = Decimal(str(1 + random.uniform(-self.simulation_slippage, self.simulation_slippage)))
            actual_price = target_price * slippage_factor
            
            # Calculate amounts
            if order.order_type == OrderType.BUY:
                amount_in = order.amount  # Amount of base currency spent
                amount_out = amount_in / actual_price  # Amount of tokens received
            else:  # SELL
                amount_in = order.amount  # Amount of tokens sold
                amount_out = amount_in * actual_price  # Amount of base currency received
            
            # Simulate gas cost
            simulated_gas_used = random.randint(50000, 200000)
            simulated_gas_cost = Decimal(str(simulated_gas_used * 20e-9))  # Simulate ~20 gwei
            
            # Generate fake transaction hash
            fake_tx_hash = f"0x{''.join(random.choices('0123456789abcdef', k=64))}"
            
            return ExecutionResult(
                success=True,
                order_id=order.id,
                tx_hash=fake_tx_hash,
                amount_in=amount_in,
                amount_out=amount_out,
                actual_price=actual_price,
                gas_used=simulated_gas_used,
                gas_cost=simulated_gas_cost,
                execution_time=datetime.now(),
                metadata={
                    'simulated': True,
                    'slippage': float(slippage_factor - 1),
                    'chain': order.chain
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error in simulated execution: {e}")
            return ExecutionResult(
                success=False,
                order_id=order.id,
                tx_hash=None,
                amount_in=Decimal('0'),
                amount_out=Decimal('0'),
                actual_price=Decimal('0'),
                gas_used=None,
                gas_cost=Decimal('0'),
                execution_time=datetime.now(),
                error_message=f"Simulation error: {str(e)}"
            )

    async def _execute_live_order(
        self, 
        order: TradeOrder, 
        opportunity: TradingOpportunity
    ) -> ExecutionResult:
        """
        Execute live order on blockchain (placeholder implementation).
        
        Args:
            order: Trading order
            opportunity: Trading opportunity
            
        Returns:
            ExecutionResult: Execution result
        """
        try:
            self.logger.warning("Live execution not implemented - using simulation")
            
            # In a real implementation, this would:
            # 1. Connect to appropriate blockchain (Ethereum, Base, Solana)
            # 2. Prepare transaction with optimal gas settings
            # 3. Submit transaction to mempool
            # 4. Monitor for confirmation
            # 5. Handle failed transactions and retries
            
            # For now, fall back to simulation
            return await self._simulate_execution(order, opportunity)
            
        except Exception as e:
            self.logger.error(f"Error in live execution: {e}")
            return ExecutionResult(
                success=False,
                order_id=order.id,
                tx_hash=None,
                amount_in=Decimal('0'),
                amount_out=Decimal('0'),
                actual_price=Decimal('0'),
                gas_used=None,
                gas_cost=Decimal('0'),
                execution_time=datetime.now(),
                error_message=f"Live execution error: {str(e)}"
            )

    async def _monitoring_loop(self) -> None:
        """Monitor pending orders and update their status."""
        self.logger.info("Starting execution monitoring loop")
        
        while self.monitoring_active:
            try:
                # Check for timed out orders
                current_time = datetime.now()
                timeout_threshold = timedelta(seconds=self.transaction_timeout)
                
                timed_out_orders = []
                for order in self.pending_orders.values():
                    if order.submitted_time:
                        time_elapsed = current_time - order.submitted_time
                        if time_elapsed > timeout_threshold:
                            timed_out_orders.append(order)
                
                # Handle timed out orders
                for order in timed_out_orders:
                    self.logger.warning(f"Order timed out: {order.id} ({order.token_symbol})")
                    order.status = OrderStatus.FAILED
                    if order.id in self.pending_orders:
                        del self.pending_orders[order.id]
                
                # Clean up old execution history
                if len(self.execution_history) > 1000:
                    self.execution_history = self.execution_history[-500:]
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                self.logger.info("Execution monitoring loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in execution monitoring loop: {e}")
                await asyncio.sleep(60)

    def get_execution_metrics(self) -> Dict[str, Any]:
        """
        Get execution engine performance metrics.
        
        Returns:
            Dictionary containing execution metrics
        """
        try:
            success_rate = 0.0
            if self.total_executions > 0:
                success_rate = (self.successful_executions / self.total_executions) * 100
            
            # Calculate recent performance
            recent_executions = self.execution_history[-10:] if self.execution_history else []
            recent_success_rate = 0.0
            if recent_executions:
                recent_successes = sum(1 for result in recent_executions if result.success)
                recent_success_rate = (recent_successes / len(recent_executions)) * 100
            
            return {
                'total_executions': self.total_executions,
                'successful_executions': self.successful_executions,
                'success_rate': success_rate,
                'recent_success_rate': recent_success_rate,
                'average_execution_time': self.average_execution_time,
                'pending_orders': len(self.pending_orders),
                'total_gas_used': self.total_gas_used,
                'paper_trading_mode': self.paper_trading_mode,
                'execution_history_size': len(self.execution_history)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting execution metrics: {e}")
            return {}

    def set_paper_trading_mode(self, enabled: bool) -> None:
        """
        Enable or disable paper trading mode.
        
        Args:
            enabled: True to enable paper trading, False for live trading
        """
        old_mode = self.paper_trading_mode
        self.paper_trading_mode = enabled
        
        mode_str = "PAPER TRADING" if enabled else "LIVE TRADING"
        self.logger.info(f"Execution mode changed: {mode_str}")
        
        if not enabled:
            self.logger.warning("⚠️ LIVE TRADING MODE ENABLED - Real funds at risk!")

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: ID of order to cancel
            
        Returns:
            bool: True if order was cancelled successfully
        """
        try:
            if order_id in self.pending_orders:
                order = self.pending_orders[order_id]
                order.status = OrderStatus.CANCELLED
                del self.pending_orders[order_id]
                
                self.logger.info(f"Order cancelled: {order_id} ({order.token_symbol})")
                return True
            else:
                self.logger.warning(f"Cannot cancel non-existent order: {order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    async def cancel_all_orders(self) -> int:
        """
        Cancel all pending orders.
        
        Returns:
            int: Number of orders cancelled
        """
        try:
            cancelled_count = 0
            order_ids = list(self.pending_orders.keys())
            
            for order_id in order_ids:
                if await self.cancel_order(order_id):
                    cancelled_count += 1
            
            self.logger.info(f"Cancelled {cancelled_count} pending orders")
            return cancelled_count
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {e}")
            return 0

    async def cleanup(self) -> None:
        """Cleanup execution engine resources."""
        try:
            self.logger.info("Cleaning up execution engine...")
            
            # Stop monitoring
            self.monitoring_active = False
            
            # Cancel all pending orders
            await self.cancel_all_orders()
            
            self.logger.info("Execution engine cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during execution engine cleanup: {e}")