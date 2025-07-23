"""
Position management system for tracking active trades and portfolio state.
Handles position lifecycle, P&L calculation, and automated exit strategies.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json

from models.token import TradingOpportunity
from trading.risk_manager import RiskManager, PositionSizeResult
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


@dataclass
class Position:
    """Represents an active trading position."""
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
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_current_price(self, new_price: Decimal) -> None:
        """
        Update current price and recalculate P&L.
        
        Args:
            new_price: New current market price
        """
        try:
            self.current_price = new_price
            self.last_update = datetime.now()
            
            # Update price extremes
            if self.highest_price is None or new_price > self.highest_price:
                self.highest_price = new_price
            if self.lowest_price is None or new_price < self.lowest_price:
                self.lowest_price = new_price
                
            # Calculate unrealized P&L
            if self.entry_price > 0:
                price_change = (new_price - self.entry_price) / self.entry_price
                self.unrealized_pnl_percentage = float(price_change * 100)
                self.unrealized_pnl = self.entry_amount * price_change
                
        except Exception:
            # If calculation fails, keep existing values
            pass
    
    def should_exit(self) -> Tuple[bool, Optional[ExitReason]]:
        """
        Check if position should be exited based on current conditions.
        
        Returns:
            Tuple of (should_exit, exit_reason)
        """
        try:
            # Check stop loss
            if (self.stop_loss_price is not None and 
                self.current_price <= self.stop_loss_price):
                return True, ExitReason.STOP_LOSS
                
            # Check take profit
            if (self.take_profit_price is not None and 
                self.current_price >= self.take_profit_price):
                return True, ExitReason.TAKE_PROFIT
                
            # Check time limit
            if (self.max_hold_time is not None and 
                datetime.now() - self.entry_time > self.max_hold_time):
                return True, ExitReason.TIME_LIMIT
                
            # Check trailing stop
            if (self.trailing_stop_distance is not None and 
                self.highest_price is not None):
                trailing_stop_price = self.highest_price - self.trailing_stop_distance
                if self.current_price <= trailing_stop_price:
                    return True, ExitReason.STOP_LOSS
                    
            return False, None
            
        except Exception:
            return False, None
    
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
            'unrealized_pnl': str(self.unrealized_pnl),
            'unrealized_pnl_percentage': self.unrealized_pnl_percentage,
            'stop_loss_price': str(self.stop_loss_price) if self.stop_loss_price else None,
            'take_profit_price': str(self.take_profit_price) if self.take_profit_price else None,
            'entry_tx_hash': self.entry_tx_hash,
            'gas_fees_paid': str(self.gas_fees_paid)
        }


@dataclass
class PositionExit:
    """Details of a position exit."""
    position_id: str
    exit_price: Decimal
    exit_amount: Decimal
    exit_time: datetime
    exit_reason: ExitReason
    realized_pnl: Decimal
    realized_pnl_percentage: float
    exit_tx_hash: Optional[str] = None
    gas_fees: Decimal = Decimal('0')


class PositionManager:
    """
    Manages active trading positions and their lifecycle.
    Handles position tracking, P&L calculation, and automated exits.
    """
    
    def __init__(self, risk_manager: RiskManager) -> None:
        """
        Initialize the position manager.
        
        Args:
            risk_manager: Risk management system instance
        """
        self.logger = logger_manager.get_logger("PositionManager")
        self.risk_manager = risk_manager
        
        # Position tracking
        self.active_positions: Dict[str, Position] = {}
        self.closed_positions: List[PositionExit] = []
        
        # Performance tracking
        self.total_realized_pnl = Decimal('0')
        self.total_fees_paid = Decimal('0')
        self.position_count = 0
        self.winning_positions = 0
        
        # Monitoring
        self.price_update_task: Optional[asyncio.Task] = None
        self.monitoring_active = False
        
    async def initialize(self) -> None:
        """Initialize the position manager and start monitoring."""
        try:
            self.logger.info("Initializing position manager...")
            
            # Start price monitoring
            await self.start_monitoring()
            
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
            entry_price: Price at which position was entered
            entry_amount: Amount of tokens purchased
            entry_tx_hash: Transaction hash of entry trade
            
        Returns:
            Position object if successful, None otherwise
        """
        try:
            # Generate unique position ID
            position_id = f"{opportunity.token.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Get risk parameters from opportunity metadata
            recommendation = opportunity.metadata.get('recommendation', {})
            stop_loss_pct = recommendation.get('recommended_stop_loss', 0.15)
            take_profit_pct = recommendation.get('recommended_take_profit', 0.30)
            
            # Calculate stop loss and take profit prices
            stop_loss_price = entry_price * (Decimal('1') - Decimal(str(stop_loss_pct)))
            take_profit_price = entry_price * (Decimal('1') + Decimal(str(take_profit_pct)))
            
            # Create position
            position = Position(
                id=position_id,
                token_symbol=opportunity.token.symbol,
                token_address=opportunity.token.address,
                chain=opportunity.metadata.get('chain', 'ETHEREUM'),
                entry_amount=entry_amount,
                entry_price=entry_price,
                current_price=entry_price,
                entry_time=datetime.now(),
                last_update=datetime.now(),
                status=PositionStatus.OPEN,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                max_hold_time=timedelta(hours=24),  # Default 24-hour max hold
                entry_tx_hash=entry_tx_hash,
                metadata={
                    'opportunity_id': opportunity.metadata.get('opportunity_id'),
                    'dex_name': opportunity.liquidity.dex_name,
                    'risk_score': recommendation.get('score', 0.0)
                }
            )
            
            # Add to active positions
            self.active_positions[position_id] = position
            self.position_count += 1
            
            # Update risk manager
            self.risk_manager.add_position(opportunity.token.symbol, entry_amount)
            
            self.logger.info(
                f"Position opened: {position.token_symbol} - "
                f"Amount: {entry_amount}, Price: ${entry_price}, "
                f"Stop Loss: ${stop_loss_price:.6f}, Take Profit: ${take_profit_price:.6f}"
            )
            
            return position
            
        except Exception as e:
            self.logger.error(f"Failed to open position for {opportunity.token.symbol}: {e}")
            return None
    
    async def close_position(
        self, 
        position_id: str, 
        exit_price: Decimal,
        exit_reason: ExitReason,
        exit_tx_hash: Optional[str] = None
    ) -> Optional[PositionExit]:
        """
        Close an active position.
        
        Args:
            position_id: ID of position to close
            exit_price: Price at which position was exited
            exit_reason: Reason for closing position
            exit_tx_hash: Transaction hash of exit trade
            
        Returns:
            PositionExit object if successful, None otherwise
        """
        try:
            if position_id not in self.active_positions:
                self.logger.warning(f"Attempted to close non-existent position: {position_id}")
                return None
                
            position = self.active_positions[position_id]
            
            # Calculate realized P&L
            price_change = (exit_price - position.entry_price) / position.entry_price
            realized_pnl = position.entry_amount * price_change
            realized_pnl_percentage = float(price_change * 100)
            
            # Create exit record
            position_exit = PositionExit(
                position_id=position_id,
                exit_price=exit_price,
                exit_amount=position.entry_amount,
                exit_time=datetime.now(),
                exit_reason=exit_reason,
                realized_pnl=realized_pnl,
                realized_pnl_percentage=realized_pnl_percentage,
                exit_tx_hash=exit_tx_hash
            )
            
            # Update position status
            if exit_reason == ExitReason.STOP_LOSS:
                position.status = PositionStatus.STOP_LOSS_TRIGGERED
            elif exit_reason == ExitReason.TAKE_PROFIT:
                position.status = PositionStatus.TAKE_PROFIT_TRIGGERED
            else:
                position.status = PositionStatus.CLOSED
                
            # Update performance tracking
            self.total_realized_pnl += realized_pnl
            if realized_pnl > 0:
                self.winning_positions += 1
                
            # Update risk manager P&L
            self.risk_manager.update_daily_pnl(float(realized_pnl))
            self.risk_manager.remove_position(position.token_symbol)
            
            # Move to closed positions
            self.closed_positions.append(position_exit)
            del self.active_positions[position_id]
            
            self.logger.info(
                f"Position closed: {position.token_symbol} - "
                f"Exit Price: ${exit_price}, P&L: {realized_pnl:.6f} ({realized_pnl_percentage:.2f}%), "
                f"Reason: {exit_reason.value}"
            )
            
            return position_exit
            
        except Exception as e:
            self.logger.error(f"Failed to close position {position_id}: {e}")
            return None
    
    async def update_position_prices(self) -> None:
        """Update current prices for all active positions."""
        try:
            if not self.active_positions:
                return
                
            for position_id, position in self.active_positions.items():
                try:
                    # Get current price (placeholder - would integrate with price feeds)
                    current_price = await self._get_current_price(position)
                    
                    if current_price:
                        position.update_current_price(current_price)
                        
                        # Check if position should be exited
                        should_exit, exit_reason = position.should_exit()
                        if should_exit:
                            self.logger.info(
                                f"Auto-exit triggered for {position.token_symbol}: {exit_reason.value}"
                            )
                            
                            # Execute exit (placeholder - would integrate with trading engine)
                            await self._execute_position_exit(position, exit_reason)
                            
                except Exception as e:
                    self.logger.error(f"Error updating position {position_id}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Position price update failed: {e}")
    
    async def _get_current_price(self, position: Position) -> Optional[Decimal]:
        """
        Get current market price for a position's token.
        
        Args:
            position: Position to get price for
            
        Returns:
            Current price or None if unavailable
        """
        try:
            # Placeholder implementation
            # In production, this would integrate with:
            # - DEX price feeds
            # - CoinGecko API
            # - Chain-specific price oracles
            
            # Simulate price movement for testing
            import random
            price_change = random.uniform(-0.05, 0.05)  # ±5% random movement
            new_price = position.current_price * (Decimal('1') + Decimal(str(price_change)))
            
            return new_price.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            
        except Exception as e:
            self.logger.error(f"Failed to get current price for {position.token_symbol}: {e}")
            return None
    
    async def _execute_position_exit(self, position: Position, exit_reason: ExitReason) -> None:
        """
        Execute the exit of a position.
        
        Args:
            position: Position to exit
            exit_reason: Reason for exit
        """
        try:
            # Placeholder for actual trade execution
            # In production, this would integrate with the execution engine
            
            exit_price = position.current_price
            await self.close_position(position.id, exit_price, exit_reason)
            
        except Exception as e:
            self.logger.error(f"Failed to execute exit for position {position.id}: {e}")
    
    async def start_monitoring(self) -> None:
        """Start position monitoring task."""
        try:
            if self.monitoring_active:
                return
                
            self.monitoring_active = True
            self.price_update_task = asyncio.create_task(self._monitoring_loop())
            
            self.logger.info("Position monitoring started")
            
        except Exception as e:
            self.logger.error(f"Failed to start position monitoring: {e}")
            raise
    
    async def stop_monitoring(self) -> None:
        """Stop position monitoring task."""
        try:
            self.monitoring_active = False
            
            if self.price_update_task:
                self.price_update_task.cancel()
                try:
                    await self.price_update_task
                except asyncio.CancelledError:
                    pass
                    
            self.logger.info("Position monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping position monitoring: {e}")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for position updates."""
        try:
            while self.monitoring_active:
                await self.update_position_prices()
                await asyncio.sleep(30)  # Update every 30 seconds
                
        except asyncio.CancelledError:
            self.logger.info("Position monitoring loop cancelled")
        except Exception as e:
            self.logger.error(f"Position monitoring loop error: {e}")
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive portfolio summary.
        
        Returns:
            Dictionary containing portfolio performance metrics
        """
        try:
            # Calculate current unrealized P&L
            total_unrealized_pnl = sum(
                pos.unrealized_pnl for pos in self.active_positions.values()
            )
            
            # Calculate win rate
            total_closed = len(self.closed_positions)
            win_rate = (self.winning_positions / total_closed * 100) if total_closed > 0 else 0
            
            # Calculate average hold time
            if self.closed_positions:
                total_hold_time = sum(
                    (exit.exit_time - self.active_positions.get(exit.position_id, Position(
                        id="", token_symbol="", token_address="", chain="",
                        entry_amount=Decimal('0'), entry_price=Decimal('0'),
                        current_price=Decimal('0'), entry_time=exit.exit_time,
                        last_update=exit.exit_time, status=PositionStatus.CLOSED
                    )).entry_time).total_seconds()
                    for exit in self.closed_positions
                )
                avg_hold_time_seconds = total_hold_time / len(self.closed_positions)
                avg_hold_time = str(timedelta(seconds=avg_hold_time_seconds))
            else:
                avg_hold_time = "N/A"
            
            return {
                'active_positions': len(self.active_positions),
                'total_positions_opened': self.position_count,
                'closed_positions': len(self.closed_positions),
                'winning_positions': self.winning_positions,
                'win_rate_percentage': round(win_rate, 2),
                'total_realized_pnl': float(self.total_realized_pnl),
                'total_unrealized_pnl': float(total_unrealized_pnl),
                'total_pnl': float(self.total_realized_pnl + total_unrealized_pnl),
                'total_fees_paid': float(self.total_fees_paid),
                'average_hold_time': avg_hold_time,
                'positions_by_status': self._get_positions_by_status(),
                'top_performers': self._get_top_performers(),
                'worst_performers': self._get_worst_performers()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate portfolio summary: {e}")
            return {}
    
    def _get_positions_by_status(self) -> Dict[str, int]:
        """Get count of positions by status."""
        status_counts = {}
        
        for position in self.active_positions.values():
            status = position.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
        return status_counts
    
    def _get_top_performers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top performing closed positions."""
        try:
            sorted_exits = sorted(
                self.closed_positions,
                key=lambda x: x.realized_pnl_percentage,
                reverse=True
            )
            
            return [
                {
                    'token_symbol': self._get_position_symbol(exit.position_id),
                    'realized_pnl_percentage': exit.realized_pnl_percentage,
                    'realized_pnl': float(exit.realized_pnl),
                    'exit_reason': exit.exit_reason.value
                }
                for exit in sorted_exits[:limit]
            ]
            
        except Exception as e:
            self.logger.error(f"Failed to get top performers: {e}")
            return []
    
    def _get_worst_performers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get worst performing closed positions."""
        try:
            sorted_exits = sorted(
                self.closed_positions,
                key=lambda x: x.realized_pnl_percentage
            )
            
            return [
                {
                    'token_symbol': self._get_position_symbol(exit.position_id),
                    'realized_pnl_percentage': exit.realized_pnl_percentage,
                    'realized_pnl': float(exit.realized_pnl),
                    'exit_reason': exit.exit_reason.value
                }
                for exit in sorted_exits[:limit]
            ]
            
        except Exception as e:
            self.logger.error(f"Failed to get worst performers: {e}")
            return []
    
    def _get_position_symbol(self, position_id: str) -> str:
        """Extract token symbol from position ID."""
        try:
            return position_id.split('_')[0]
        except Exception:
            return "UNKNOWN"
    
    def get_position_details(self, position_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific position.
        
        Args:
            position_id: ID of position to get details for
            
        Returns:
            Position details dictionary or None if not found
        """
        try:
            if position_id in self.active_positions:
                return self.active_positions[position_id].to_dict()
            else:
                # Check closed positions
                for exit in self.closed_positions:
                    if exit.position_id == position_id:
                        return {
                            'position_id': exit.position_id,
                            'status': 'closed',
                            'exit_price': str(exit.exit_price),
                            'exit_time': exit.exit_time.isoformat(),
                            'exit_reason': exit.exit_reason.value,
                            'realized_pnl': str(exit.realized_pnl),
                            'realized_pnl_percentage': exit.realized_pnl_percentage
                        }
                        
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get position details for {position_id}: {e}")
            return None
    
    async def emergency_close_all(self) -> List[str]:
        """
        Emergency close all active positions.
        
        Returns:
            List of position IDs that were closed
        """
        try:
            self.logger.warning("Emergency close all positions triggered")
            
            closed_positions = []
            
            for position_id, position in list(self.active_positions.items()):
                try:
                    exit_result = await self.close_position(
                        position_id,
                        position.current_price,
                        ExitReason.EMERGENCY
                    )
                    
                    if exit_result:
                        closed_positions.append(position_id)
                        
                except Exception as e:
                    self.logger.error(f"Failed to emergency close position {position_id}: {e}")
                    
            self.logger.warning(f"Emergency close completed: {len(closed_positions)} positions closed")
            return closed_positions
            
        except Exception as e:
            self.logger.error(f"Emergency close all failed: {e}")
            return []
