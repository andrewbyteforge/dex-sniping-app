"""
Advanced portfolio tracking and performance analytics.
Provides detailed metrics, reporting, and risk analysis.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import csv
from io import StringIO

from trading.position_manager import Position, PositionExit, PositionStatus
from trading.risk_manager import RiskManager
from utils.logger import logger_manager


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for portfolio tracking."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    average_win: Decimal
    average_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    total_pnl: Decimal
    total_fees: Decimal
    net_pnl: Decimal
    sharpe_ratio: Optional[float]
    max_drawdown: Decimal
    current_drawdown: Decimal
    average_hold_time: timedelta
    profit_factor: float


@dataclass
class ChainMetrics:
    """Performance metrics by blockchain."""
    chain: str
    positions: int
    total_pnl: Decimal
    win_rate: float
    average_position_size: Decimal
    best_performer: Optional[str]
    worst_performer: Optional[str]


class PortfolioTracker:
    """
    Advanced portfolio tracking and performance analytics system.
    Provides comprehensive metrics, reporting, and risk analysis.
    """
    
    def __init__(self, risk_manager: RiskManager) -> None:
        """
        Initialize the portfolio tracker.
        
        Args:
            risk_manager: Risk management system for portfolio limits
        """
        self.logger = logger_manager.get_logger("PortfolioTracker")
        self.risk_manager = risk_manager
        
        # Historical data storage
        self.position_history: List[Position] = []
        self.exit_history: List[PositionExit] = []
        self.daily_snapshots: List[Dict[str, Any]] = []
        
        # Performance tracking
        self.peak_portfolio_value = Decimal('0')
        self.portfolio_start_value = Decimal('0')
        self.daily_returns: List[float] = []
        
        # Analytics cache
        self.last_metrics_calculation: Optional[datetime] = None
        self.cached_metrics: Optional[PerformanceMetrics] = None
        
    def track_position_opened(self, position: Position) -> None:
        """
        Track a newly opened position.
        
        Args:
            position: Position that was opened
        """
        try:
            self.position_history.append(position)
            
            # Update portfolio tracking
            current_value = self._calculate_current_portfolio_value()
            if current_value > self.peak_portfolio_value:
                self.peak_portfolio_value = current_value
            
            self.logger.debug(f"Position tracked: {position.token_symbol}")
            
        except Exception as e:
            self.logger.error(f"Failed to track position opening: {e}")
    
    def track_position_closed(self, position_exit: PositionExit) -> None:
        """
        Track a position closure.
        
        Args:
            position_exit: Position exit details
        """
        try:
            self.exit_history.append(position_exit)
            
            # Update daily returns
            self._update_daily_returns(position_exit)
            
            # Clear cached metrics
            self.cached_metrics = None
            
            self.logger.debug(f"Position exit tracked: {position_exit.position_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to track position closure: {e}")
    
    def get_performance_metrics(self, recalculate: bool = False) -> PerformanceMetrics:
        """
        Get comprehensive performance metrics.
        
        Args:
            recalculate: Force recalculation even if cached
            
        Returns:
            PerformanceMetrics with current portfolio performance
        """
        try:
            # Return cached metrics if recent and not forced
            if (not recalculate and 
                self.cached_metrics and 
                self.last_metrics_calculation and
                (datetime.now() - self.last_metrics_calculation).total_seconds() < 300):  # 5 minutes
                return self.cached_metrics
            
            # Calculate fresh metrics
            metrics = self._calculate_performance_metrics()
            
            # Cache results
            self.cached_metrics = metrics
            self.last_metrics_calculation = datetime.now()
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {e}")
            return self._get_default_metrics()
    
    def _calculate_performance_metrics(self) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        try:
            if not self.exit_history:
                return self._get_default_metrics()
            
            # Basic trade statistics
            total_trades = len(self.exit_history)
            winning_trades = len([exit for exit in self.exit_history if exit.realized_pnl > 0])
            losing_trades = total_trades - winning_trades
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # P&L calculations
            all_pnl = [exit.realized_pnl for exit in self.exit_history]
            winning_pnl = [pnl for pnl in all_pnl if pnl > 0]
            losing_pnl = [pnl for pnl in all_pnl if pnl < 0]
            
            total_pnl = sum(all_pnl)
            total_fees = sum([exit.gas_fees for exit in self.exit_history])
            net_pnl = total_pnl - total_fees
            
            # Win/Loss statistics
            average_win = sum(winning_pnl) / len(winning_pnl) if winning_pnl else Decimal('0')
            average_loss = sum(losing_pnl) / len(losing_pnl) if losing_pnl else Decimal('0')
            largest_win = max(winning_pnl) if winning_pnl else Decimal('0')
            largest_loss = min(losing_pnl) if losing_pnl else Decimal('0')
            
            # Risk metrics
            profit_factor = (
                abs(sum(winning_pnl) / sum(losing_pnl)) 
                if losing_pnl and sum(losing_pnl) != 0 else 0
            )
            
            # Drawdown calculations
            max_drawdown, current_drawdown = self._calculate_drawdown()
            
            # Time metrics
            average_hold_time = self._calculate_average_hold_time()
            
            # Sharpe ratio (simplified)
            sharpe_ratio = self._calculate_sharpe_ratio()
            
            return PerformanceMetrics(
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=win_rate,
                average_win=average_win,
                average_loss=average_loss,
                largest_win=largest_win,
                largest_loss=largest_loss,
                total_pnl=total_pnl,
                total_fees=total_fees,
                net_pnl=net_pnl,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                current_drawdown=current_drawdown,
                average_hold_time=average_hold_time,
                profit_factor=profit_factor
            )
            
        except Exception as e:
            self.logger.error(f"Performance metrics calculation failed: {e}")
            return self._get_default_metrics()
    
    def get_chain_performance(self) -> List[ChainMetrics]:
        """Get performance metrics broken down by blockchain."""
        try:
            chain_data = {}
            
            # Group exits by chain
            for exit in self.exit_history:
                # Get chain from position (simplified lookup)
                chain = self._get_chain_from_position_id(exit.position_id)
                
                if chain not in chain_data:
                    chain_data[chain] = {
                        'exits': [],
                        'positions': 0,
                        'total_pnl': Decimal('0'),
                        'wins': 0
                    }
                
                chain_data[chain]['exits'].append(exit)
                chain_data[chain]['positions'] += 1
                chain_data[chain]['total_pnl'] += exit.realized_pnl
                if exit.realized_pnl > 0:
                    chain_data[chain]['wins'] += 1
            
            # Create metrics for each chain
            chain_metrics = []
            for chain, data in chain_data.items():
                win_rate = (data['wins'] / data['positions'] * 100) if data['positions'] > 0 else 0
                
                # Find best and worst performers
                exits = data['exits']
                best_exit = max(exits, key=lambda x: x.realized_pnl) if exits else None
                worst_exit = min(exits, key=lambda x: x.realized_pnl) if exits else None
                
                avg_position_size = self._calculate_average_position_size_for_chain(chain)
                
                chain_metrics.append(ChainMetrics(
                    chain=chain,
                    positions=data['positions'],
                    total_pnl=data['total_pnl'],
                    win_rate=win_rate,
                    average_position_size=avg_position_size,
                    best_performer=self._get_token_from_position_id(best_exit.position_id) if best_exit else None,
                    worst_performer=self._get_token_from_position_id(worst_exit.position_id) if worst_exit else None
                ))
            
            return sorted(chain_metrics, key=lambda x: x.total_pnl, reverse=True)
            
        except Exception as e:
            self.logger.error(f"Chain performance calculation failed: {e}")
            return []
    
    def generate_performance_report(self, format_type: str = 'text') -> str:
        """
        Generate a comprehensive performance report.
        
        Args:
            format_type: Report format ('text', 'json', 'csv')
            
        Returns:
            Formatted performance report
        """
        try:
            metrics = self.get_performance_metrics()
            chain_performance = self.get_chain_performance()
            
            if format_type == 'json':
                return self._generate_json_report(metrics, chain_performance)
            elif format_type == 'csv':
                return self._generate_csv_report()
            else:
                return self._generate_text_report(metrics, chain_performance)
                
        except Exception as e:
            self.logger.error(f"Performance report generation failed: {e}")
            return f"Error generating report: {str(e)}"
    
    def _generate_text_report(self, metrics: PerformanceMetrics, chain_metrics: List[ChainMetrics]) -> str:
        """Generate human-readable text report."""
        try:
            report = []
            report.append("PORTFOLIO PERFORMANCE REPORT")
            report.append("=" * 50)
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")
            
            # Overall Performance
            report.append("OVERALL PERFORMANCE:")
            report.append(f"Total Trades: {metrics.total_trades}")
            report.append(f"Win Rate: {metrics.win_rate:.1f}%")
            report.append(f"Total P&L: ${metrics.total_pnl:.2f}")
            report.append(f"Net P&L (after fees): ${metrics.net_pnl:.2f}")
            report.append(f"Total Fees: ${metrics.total_fees:.2f}")
            report.append("")
            
            # Risk Metrics
            report.append("RISK METRICS:")
            report.append(f"Profit Factor: {metrics.profit_factor:.2f}")
            report.append(f"Max Drawdown: ${metrics.max_drawdown:.2f}")
            report.append(f"Current Drawdown: ${metrics.current_drawdown:.2f}")
            if metrics.sharpe_ratio:
                report.append(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
            report.append("")
            
            # Trade Analysis
            report.append("TRADE ANALYSIS:")
            report.append(f"Average Win: ${metrics.average_win:.2f}")
            report.append(f"Average Loss: ${metrics.average_loss:.2f}")
            report.append(f"Largest Win: ${metrics.largest_win:.2f}")
            report.append(f"Largest Loss: ${metrics.largest_loss:.2f}")
            report.append(f"Average Hold Time: {str(metrics.average_hold_time).split('.')[0]}")
            report.append("")
            
            # Chain Performance
            if chain_metrics:
                report.append("PERFORMANCE BY CHAIN:")
                for chain in chain_metrics:
                    report.append(f"{chain.chain}:")
                    report.append(f"  Positions: {chain.positions}")
                    report.append(f"  P&L: ${chain.total_pnl:.2f}")
                    report.append(f"  Win Rate: {chain.win_rate:.1f}%")
                    report.append(f"  Avg Position: ${chain.average_position_size:.2f}")
                    if chain.best_performer:
                        report.append(f"  Best: {chain.best_performer}")
                    report.append("")
            
            return "\n".join(report)
            
        except Exception as e:
            self.logger.error(f"Text report generation failed: {e}")
            return "Error generating text report"
    
    def _generate_json_report(self, metrics: PerformanceMetrics, chain_metrics: List[ChainMetrics]) -> str:
        """Generate JSON report."""
        try:
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'overall_performance': {
                    'total_trades': metrics.total_trades,
                    'win_rate': float(metrics.win_rate),
                    'total_pnl': float(metrics.total_pnl),
                    'net_pnl': float(metrics.net_pnl),
                    'total_fees': float(metrics.total_fees),
                    'profit_factor': float(metrics.profit_factor),
                    'max_drawdown': float(metrics.max_drawdown),
                    'sharpe_ratio': metrics.sharpe_ratio
                },
                'chain_performance': [
                    {
                        'chain': chain.chain,
                        'positions': chain.positions,
                        'total_pnl': float(chain.total_pnl),
                        'win_rate': float(chain.win_rate),
                        'average_position_size': float(chain.average_position_size)
                    }
                    for chain in chain_metrics
                ]
            }
            
            return json.dumps(report_data, indent=2)
            
        except Exception as e:
            self.logger.error(f"JSON report generation failed: {e}")
            return json.dumps({'error': str(e)})
    
    def _generate_csv_report(self) -> str:
        """Generate CSV report of all trades."""
        try:
            output = StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'Position ID', 'Token', 'Chain', 'Entry Time', 'Exit Time',
                'Entry Amount', 'Exit Price', 'Realized P&L', 'P&L %',
                'Hold Time (Hours)', 'Exit Reason'
            ])
            
            # Data rows
            for exit in self.exit_history:
                # Get corresponding position data (simplified)
                position = self._get_position_by_id(exit.position_id)
                
                hold_time_hours = (exit.exit_time - (position.entry_time if position else exit.exit_time)).total_seconds() / 3600
                
                writer.writerow([
                    exit.position_id,
                    self._get_token_from_position_id(exit.position_id),
                    self._get_chain_from_position_id(exit.position_id),
                    position.entry_time.isoformat() if position else '',
                    exit.exit_time.isoformat(),
                    str(exit.exit_amount),
                    str(exit.exit_price),
                    str(exit.realized_pnl),
                    f"{exit.realized_pnl_percentage:.2f}%",
                    f"{hold_time_hours:.2f}",
                    exit.exit_reason.value
                ])
            
            return output.getvalue()
            
        except Exception as e:
            self.logger.error(f"CSV report generation failed: {e}")
            return "Error generating CSV report"
    
    # Helper methods for calculations
    
    def _calculate_current_portfolio_value(self) -> Decimal:
        """Calculate current portfolio value."""
        # Simplified implementation
        return Decimal('1000')  # Placeholder
    
    def _calculate_drawdown(self) -> Tuple[Decimal, Decimal]:
        """Calculate maximum and current drawdown."""
        # Simplified implementation
        return Decimal('0'), Decimal('0')
    
    def _calculate_average_hold_time(self) -> timedelta:
        """Calculate average position hold time."""
        if not self.exit_history:
            return timedelta(0)
        
        try:
            total_seconds = 0
            valid_exits = 0
            
            for exit in self.exit_history:
                position = self._get_position_by_id(exit.position_id)
                if position:
                    hold_time = exit.exit_time - position.entry_time
                    total_seconds += hold_time.total_seconds()
                    valid_exits += 1
            
            if valid_exits > 0:
                return timedelta(seconds=total_seconds / valid_exits)
            
        except Exception as e:
            self.logger.error(f"Average hold time calculation failed: {e}")
        
        return timedelta(0)
    
    def _calculate_sharpe_ratio(self) -> Optional[float]:
        """Calculate Sharpe ratio."""
        if len(self.daily_returns) < 30:  # Need at least 30 days
            return None
        
        try:
            import statistics
            
            avg_return = statistics.mean(self.daily_returns)
            std_return = statistics.stdev(self.daily_returns)
            
            if std_return == 0:
                return None
            
            # Assume 5% risk-free rate annually
            risk_free_rate = 0.05 / 365  # Daily risk-free rate
            
            return (avg_return - risk_free_rate) / std_return
            
        except Exception as e:
            self.logger.error(f"Sharpe ratio calculation failed: {e}")
            return None
    
    def _update_daily_returns(self, position_exit: PositionExit) -> None:
        """Update daily returns tracking."""
        try:
            # Simplified daily return calculation
            return_pct = float(position_exit.realized_pnl_percentage) / 100
            self.daily_returns.append(return_pct)
            
            # Keep only last 365 days
            if len(self.daily_returns) > 365:
                self.daily_returns.pop(0)
                
        except Exception as e:
            self.logger.error(f"Daily returns update failed: {e}")
    
    def _get_default_metrics(self) -> PerformanceMetrics:
        """Get default metrics when calculation fails."""
        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            average_win=Decimal('0'),
            average_loss=Decimal('0'),
            largest_win=Decimal('0'),
            largest_loss=Decimal('0'),
            total_pnl=Decimal('0'),
            total_fees=Decimal('0'),
            net_pnl=Decimal('0'),
            sharpe_ratio=None,
            max_drawdown=Decimal('0'),
            current_drawdown=Decimal('0'),
            average_hold_time=timedelta(0),
            profit_factor=0.0
        )
    
    # Simplified helper methods (would be more sophisticated in production)
    
    def _get_chain_from_position_id(self, position_id: str) -> str:
        """Extract chain from position ID."""
        if 'SOL' in position_id:
            return 'SOLANA'
        elif 'BASE' in position_id:
            return 'BASE'
        else:
            return 'ETHEREUM'
    
    def _get_token_from_position_id(self, position_id: str) -> str:
        """Extract token symbol from position ID."""
        return position_id.split('_')[0] if '_' in position_id else 'UNKNOWN'
    
    def _get_position_by_id(self, position_id: str) -> Optional[Position]:
        """Get position by ID from history."""
        for position in self.position_history:
            if position.id == position_id:
                return position
        return None
    
    def _calculate_average_position_size_for_chain(self, chain: str) -> Decimal:
        """Calculate average position size for a specific chain."""
        chain_positions = [pos for pos in self.position_history if self._get_chain_from_position_id(pos.id) == chain]
        
        if not chain_positions:
            return Decimal('0')
        
        total_size = sum(pos.entry_amount for pos in chain_positions)
        return total_size / len(chain_positions)