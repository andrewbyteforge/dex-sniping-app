#!/usr/bin/env python3
"""
Enhanced position management system for tracking active trades and portfolio state.

Handles position lifecycle, P&L calculation, automated exit strategies,
and comprehensive portfolio analytics.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import uuid

from models.token import TradingOpportunity
from utils.logger import logger_manager


class PositionStatus(Enum):
    """Status of a trading position."""
    OPENING = "opening"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"


class ExitReason(Enum):
    """Reason for position exit."""
    MANUAL = "manual"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIME_LIMIT = "time_limit"
    EMERGENCY = "emergency"
    RISK_MANAGEMENT = "risk_management"
    TRAILING_STOP = "trailing_stop"
    SYSTEM_SHUTDOWN = "system_shutdown"


@dataclass
class Position:
    """Represents an active trading position with comprehensive tracking."""
    id: str
    token_symbol: str
    token_address: str
    chain: str
    entry_amount: Decimal
    entry_price: Decimal
    current_price: Decimal
    entry_time: datetime
    last_update: datetime
    status: PositionStatus
    
    # Risk management parameters
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    trailing_stop_distance: Optional[Decimal] = None
    max_hold_time: Optional[timedelta] = None
    
    # Performance tracking
    unrealized_pnl: Decimal = Decimal('0')
    unrealized_pnl_percentage: float = 0.0
    highest_price: Optional[Decimal] = None
    lowest_price: Optional[Decimal] = None
    
    # Transaction details
    entry_tx_hash: Optional[str] = None
    exit_tx_hash: Optional[str] = None
    gas_fees_paid: Decimal = Decimal('0')
    
    # Exit information
    exit_time: Optional[datetime] = None
    exit_price: Optional[Decimal] = None
    exit_reason: Optional[ExitReason] = None
    realized_pnl: Optional[Decimal] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_current_price(self, new_price: Decimal) -> None:
        """
        Update current price and recalculate P&L.
        
        Args:
            new_price: New current price
        """
        try:
            self.current_price = new_price
            self.last_update = datetime.now()
            
            # Update highest/lowest prices
            if self.highest_price is None or new_price > self.highest_price:
                self.highest_price = new_price
            if self.lowest_price is None or new_price < self.lowest_price:
                self.lowest_price = new_price
            
            # Calculate unrealized P&L
            if self.entry_price > 0:
                price_change = (new_price - self.entry_price) / self.entry_price
                self.unrealized_pnl = self.entry_amount * price_change
                self.unrealized_pnl_percentage = float(price_change * 100)
            
            # Update trailing stop if applicable
            if self.trailing_stop_distance and self.highest_price:
                new_trailing_stop = self.highest_price - self.trailing_stop_distance
                if self.stop_loss_price is None or new_trailing_stop > self.stop_loss_price:
                    self.stop_loss_price = new_trailing_stop
                    
        except Exception as e:
            logger = logger_manager.get_logger("Position")
            logger.error(f"Error updating price for {self.token_symbol}: {e}")

    def close_position(
        self, 
        exit_price: Decimal, 
        exit_reason: ExitReason, 
        exit_tx_hash: Optional[str] = None
    ) -> None:
        """
        Close the position and calculate final P&L.
        
        Args:
            exit_price: Final exit price
            exit_reason: Reason for position closure
            exit_tx_hash: Transaction hash for exit
        """
        try:
            self.status = PositionStatus.CLOSED
            self.exit_time = datetime.now()
            self.exit_price = exit_price
            self.exit_reason = exit_reason
            self.exit_tx_hash = exit_tx_hash
            
            # Calculate realized P&L
            if self.entry_price > 0:
                price_change = (exit_price - self.entry_price) / self.entry_price
                self.realized_pnl = self.entry_amount * price_change
                
                # Update final unrealized P&L (now realized)
                self.unrealized_pnl = self.realized_pnl
                self.unrealized_pnl_percentage = float(price_change * 100)
                
        except Exception as e:
            logger = logger_manager.get_logger("Position")
            logger.error(f"Error closing position {self.token_symbol}: {e}")

    def get_hold_time(self) -> timedelta:
        """Get current hold time."""
        end_time = self.exit_time if self.exit_time else datetime.now()
        return end_time - self.entry_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary for serialization."""
        return {
            'id': self.id,
            'token_symbol': self.token_symbol,
            'token_address': self.token_address,
            'chain': self.chain,
            'entry_amount': str(self.entry_amount),
            'entry_price': str(self.entry_price),
            'current_price': str(self.current_price),
            'entry_time': self.entry_time.isoformat(),
            'last_update': self.last_update.isoformat(),
            'status': self.status.value,
            'stop_loss_price': str(self.stop_loss_price) if self.stop_loss_price else None,
            'take_profit_price': str(self.take_profit_price) if self.take_profit_price else None,
            'unrealized_pnl': str(self.unrealized_pnl),
            'unrealized_pnl_percentage': self.unrealized_pnl_percentage,
            'highest_price': str(self.highest_price) if self.highest_price else None,
            'lowest_price': str(self.lowest_price) if self.lowest_price else None,
            'entry_tx_hash': self.entry_tx_hash,
            'exit_tx_hash': self.exit_tx_hash,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'exit_price': str(self.exit_price) if self.exit_price else None,
            'exit_reason': self.exit_reason.value if self.exit_reason else None,
            'realized_pnl': str(self.realized_pnl) if self.realized_pnl else None,
            'hold_time_seconds': self.get_hold_time().total_seconds(),
            'metadata': self.metadata
        }


class PositionManager:
    """
    Enhanced position management system for tracking and managing trading positions.
    
    Features:
    - Comprehensive position lifecycle management
    - Real-time P&L calculation and tracking
    - Automated exit condition monitoring
    - Portfolio-level analytics and metrics
    - Risk management integration
    - Performance reporting and analytics
    """

    def __init__(self) -> None:
        """Initialize the position manager."""
        self.logger = logger_manager.get_logger("PositionManager")
        
        # Position storage
        self.active_positions: Dict[str, Position] = {}
        self.closed_positions: Dict[str, Position] = {}
        self.position_history: List[Position] = []
        
        # Performance tracking
        self.total_trades = 0
        self.successful_trades = 0
        self.total_pnl = Decimal('0')
        self.daily_pnl = Decimal('0')
        self.last_reset_date = datetime.now().date()
        
        # Risk tracking
        self.max_concurrent_positions = 20
        self.position_alerts: List[callable] = []
        
        # Monitoring
        self.monitoring_active = False
        self.price_update_interval = 30  # seconds

    async def initialize(self) -> None:
        """Initialize the position manager."""
        try:
            self.logger.info("Initializing position manager...")
            
            # Load any persisted positions
            await self._load_positions()
            
            # Start monitoring task
            if not self.monitoring_active:
                asyncio.create_task(self._monitoring_loop())
                self.monitoring_active = True
            
            self.logger.info("Position manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize position manager: {e}")
            raise

    async def open_position(
        self,
        opportunity: TradingOpportunity,
        entry_price: Decimal,
        entry_amount: Decimal,
        entry_tx_hash: Optional[str] = None
    ) -> Optional[Position]:
        """
        Open a new trading position.
        
        Args:
            opportunity: Trading opportunity that triggered the position
            entry_price: Entry price for the position
            entry_amount: Amount invested in the position
            entry_tx_hash: Transaction hash for entry
            
        Returns:
            Position: Created position object
        """
        try:
            # Check position limits
            if len(self.active_positions) >= self.max_concurrent_positions:
                self.logger.warning(f"Maximum concurrent positions reached: {len(self.active_positions)}")
                return None
            
            # Create position
            position = Position(
                id=str(uuid.uuid4()),
                token_symbol=opportunity.token.symbol or "UNKNOWN",
                token_address=opportunity.token.address,
                chain=opportunity.chain,
                entry_amount=entry_amount,
                entry_price=entry_price,
                current_price=entry_price,
                entry_time=datetime.now(),
                last_update=datetime.now(),
                status=PositionStatus.OPEN,
                entry_tx_hash=entry_tx_hash,
                metadata={
                    'opportunity_id': getattr(opportunity, 'id', None),
                    'dex_name': opportunity.liquidity.dex_name,
                    'liquidity_usd': opportunity.liquidity.liquidity_usd
                }
            )
            
            # Initialize price tracking
            position.update_current_price(entry_price)
            
            # Store position
            self.active_positions[position.id] = position
            
            # Update statistics
            self.total_trades += 1
            self._check_daily_reset()
            
            # Send alert
            await self._send_position_alert("POSITION_OPENED", position)
            
            self.logger.info(f"Position opened: {position.token_symbol} (ID: {position.id[:8]})")
            
            return position
            
        except Exception as e:
            self.logger.error(f"Error opening position: {e}")
            return None

    async def close_position(
        self,
        position_id: str,
        exit_reason: str,
        exit_price: Optional[Decimal] = None,
        exit_tx_hash: Optional[str] = None
    ) -> bool:
        """
        Close an active position.
        
        Args:
            position_id: ID of position to close
            exit_reason: Reason for closing position
            exit_price: Exit price (uses current price if not provided)
            exit_tx_hash: Transaction hash for exit
            
        Returns:
            bool: True if position was successfully closed
        """
        try:
            if position_id not in self.active_positions:
                self.logger.warning(f"Position not found: {position_id}")
                return False
            
            position = self.active_positions[position_id]
            
            # Use current price if exit price not provided
            if exit_price is None:
                exit_price = position.current_price
            
            # Convert exit reason string to enum
            try:
                exit_reason_enum = ExitReason(exit_reason.lower())
            except ValueError:
                exit_reason_enum = ExitReason.MANUAL
            
            # Close the position
            position.close_position(exit_price, exit_reason_enum, exit_tx_hash)
            
            # Move to closed positions
            self.closed_positions[position_id] = position
            self.position_history.append(position)
            del self.active_positions[position_id]
            
            # Update statistics
            if position.realized_pnl and position.realized_pnl > 0:
                self.successful_trades += 1
            
            if position.realized_pnl:
                self.total_pnl += position.realized_pnl
                self.daily_pnl += position.realized_pnl
            
            # Send alert
            await self._send_position_alert("POSITION_CLOSED", position)
            
            pnl_str = f"${float(position.realized_pnl):.2f}" if position.realized_pnl else "N/A"
            self.logger.info(f"Position closed: {position.token_symbol} - PnL: {pnl_str} ({exit_reason})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing position {position_id}: {e}")
            return False

    async def update_position(self, position: Position) -> bool:
        """
        Update an existing position with new data.
        
        Args:
            position: Updated position object
            
        Returns:
            bool: True if update was successful
        """
        try:
            if position.id in self.active_positions:
                self.active_positions[position.id] = position
                return True
            else:
                self.logger.warning(f"Cannot update non-existent position: {position.id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating position: {e}")
            return False

    def get_active_positions(self) -> List[Position]:
        """
        Get all active positions.
        
        Returns:
            List of active Position objects
        """
        return list(self.active_positions.values())

    def get_position(self, position_id: str) -> Optional[Position]:
        """
        Get a specific position by ID.
        
        Args:
            position_id: ID of position to retrieve
            
        Returns:
            Position object if found, None otherwise
        """
        return self.active_positions.get(position_id) or self.closed_positions.get(position_id)

    def get_total_exposure_usd(self) -> float:
        """
        Calculate total portfolio exposure in USD.
        
        Returns:
            Total exposure value in USD
        """
        try:
            total_exposure = 0.0
            
            for position in self.active_positions.values():
                # Simplified calculation - would use actual token prices in production
                position_value_usd = float(position.entry_amount) * float(position.current_price)
                total_exposure += position_value_usd
            
            return total_exposure
            
        except Exception as e:
            self.logger.error(f"Error calculating total exposure: {e}")
            return 0.0

    def get_daily_pnl(self) -> float:
        """
        Get daily profit/loss.
        
        Returns:
            Daily P&L in USD
        """
        self._check_daily_reset()
        return float(self.daily_pnl)

    async def check_exit_conditions(self) -> List[Position]:
        """
        Check all active positions for exit conditions.
        
        Returns:
            List of positions that should be exited
        """
        positions_to_exit = []
        
        try:
            for position in self.active_positions.values():
                should_exit, reason = self._should_exit_position(position)
                if should_exit:
                    position.metadata['exit_reason'] = reason
                    positions_to_exit.append(position)
            
            return positions_to_exit
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {e}")
            return []

    def _should_exit_position(self, position: Position) -> Tuple[bool, str]:
        """
        Check if a position should be exited based on its parameters.
        
        Args:
            position: Position to check
            
        Returns:
            Tuple of (should_exit, reason)
        """
        try:
            # Check stop loss
            if position.stop_loss_price and position.current_price <= position.stop_loss_price:
                return True, "stop_loss"
            
            # Check take profit
            if position.take_profit_price and position.current_price >= position.take_profit_price:
                return True, "take_profit"
            
            # Check maximum hold time
            if position.max_hold_time:
                hold_time = position.get_hold_time()
                if hold_time >= position.max_hold_time:
                    return True, "time_limit"
            
            # Check for emergency conditions (large unrealized loss)
            if position.unrealized_pnl_percentage < -50:  # 50% loss
                return True, "emergency"
            
            return False, ""
            
        except Exception as e:
            self.logger.error(f"Error checking exit condition for {position.token_symbol}: {e}")
            return False, "error"

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for position management."""
        self.logger.info("Starting position monitoring loop")
        
        while self.monitoring_active:
            try:
                # Check exit conditions
                positions_to_exit = await self.check_exit_conditions()
                
                for position in positions_to_exit:
                    await self._send_position_alert("EXIT_CONDITION_MET", position)
                
                # Update position metrics
                await self._update_position_metrics()
                
                await asyncio.sleep(self.price_update_interval)
                
            except asyncio.CancelledError:
                self.logger.info("Position monitoring loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in position monitoring loop: {e}")
                await asyncio.sleep(60)

    async def _update_position_metrics(self) -> None:
        """Update position-level metrics and performance data."""
        try:
            # This would typically fetch current prices from exchanges
            # For now, simulate small price movements for demo purposes
            for position in self.active_positions.values():
                if position.metadata.get('paper_trade', False):
                    # Simulate random price movement for paper trades
                    import random
                    price_change = random.uniform(-0.02, 0.02)  # ±2% movement
                    new_price = position.current_price * (1 + Decimal(str(price_change)))
                    position.update_current_price(new_price)
                
        except Exception as e:
            self.logger.error(f"Error updating position metrics: {e}")

    async def _send_position_alert(self, alert_type: str, position: Position) -> None:
        """
        Send position alert to registered callbacks.
        
        Args:
            alert_type: Type of alert
            position: Position object
        """
        try:
            alert_data = {
                'type': alert_type,
                'timestamp': datetime.now().isoformat(),
                'position': position.to_dict()
            }
            
            # Send to all registered callbacks
            for callback in self.position_alerts:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert_data)
                    else:
                        callback(alert_data)
                except Exception as e:
                    self.logger.error(f"Error in position alert callback: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error sending position alert: {e}")

    def _check_daily_reset(self) -> None:
        """Check if daily counters need to be reset."""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_pnl = Decimal('0')
            self.last_reset_date = current_date
            self.logger.debug("Daily P&L counter reset")

    async def _load_positions(self) -> None:
        """Load persisted positions from storage."""
        try:
            # In a real implementation, this would load from database or file
            # For now, just log that we're ready to load
            self.logger.debug("Position persistence not implemented - starting with empty portfolio")
            
        except Exception as e:
            self.logger.error(f"Error loading positions: {e}")

    async def cleanup(self) -> None:
        """Cleanup position manager resources."""
        try:
            self.logger.info("Cleaning up position manager...")
            
            # Stop monitoring
            self.monitoring_active = False
            
            self.logger.info("Position manager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during position manager cleanup: {e}")