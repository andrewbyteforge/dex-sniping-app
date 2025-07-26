#!/usr/bin/env python3
"""
System monitoring and statistics tracking.
Handles all system monitoring, logging, and performance tracking.

File: core/system_monitoring.py
Class: SystemMonitoring
Methods: monitoring_loop, log_statistics, update_metrics
"""

import asyncio
from typing import Dict, Any
from datetime import datetime
from decimal import Decimal

from utils.logger import logger_manager


class SystemMonitoring:
    """
    Handles system monitoring and statistics.
    
    Features:
    - Performance metrics tracking
    - Statistics logging
    - Dashboard metrics updates
    - Health monitoring
    """
    
    def __init__(self, trading_system) -> None:
        """
        Initialize system monitoring.
        
        Args:
            trading_system: Reference to main trading system
        """
        self.trading_system = trading_system
        self.logger = logger_manager.get_logger("SystemMonitoring")

    async def monitoring_loop(self) -> None:
        """Main system monitoring and reporting loop."""
        self.logger.info("🔄 Starting system monitoring loop")
        
        while self.trading_system.is_running:
            try:
                await asyncio.sleep(30)  # Report every 30 seconds
                
                await self.update_performance_metrics()
                await self.log_system_statistics()
                await self.update_dashboard_metrics()
                await self._check_hourly_telegram_update()
                
            except asyncio.CancelledError:
                self.logger.info("System monitoring cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in system monitoring: {e}")
                
                # Send error notification
                await self.trading_system.telegram_manager.handle_monitoring_error(str(e))
                
                await asyncio.sleep(60)

    async def update_performance_metrics(self) -> None:
        """Update system performance metrics."""
        try:
            # Update execution metrics
            if self.trading_system.risk_manager:
                exposure_data = self.trading_system.risk_manager.get_current_exposure()
                self.trading_system.execution_metrics.update({
                    "average_risk_score": exposure_data.get('average_risk_score', 0.0),
                    "position_count": exposure_data.get('total_positions', 0),
                    "daily_pnl": exposure_data.get('daily_pnl', 0.0)
                })
            
            # Calculate success rates
            if self.trading_system.analysis_stats["trades_executed"] > 0:
                success_rate = (self.trading_system.analysis_stats["successful_trades"] / 
                               self.trading_system.analysis_stats["trades_executed"]) * 100
                self.trading_system.execution_metrics["success_rate"] = success_rate
            
        except Exception as e:
            self.logger.error(f"Error updating performance metrics: {e}")

    async def log_system_statistics(self) -> None:
        """Log comprehensive system statistics including Telegram signals."""
        try:
            uptime = datetime.now() - self.trading_system.start_time
            analysis_rate = self.trading_system.analysis_stats["total_analyzed"] / max(uptime.total_seconds() / 60, 1)
            
            self.logger.info("📊 ENHANCED TRADING SYSTEM STATISTICS:")
            self.logger.info(f"   Uptime: {uptime}")
            self.logger.info(f"   Analysis Rate: {analysis_rate:.1f}/min")
            self.logger.info(f"   Total Analyzed: {self.trading_system.analysis_stats['total_analyzed']}")
            self.logger.info(f"   Opportunities Found: {self.trading_system.analysis_stats['opportunities_found']}")
            self.logger.info(f"   High Confidence: {self.trading_system.analysis_stats['high_confidence']}")
            
            # Signal source breakdown
            if self.trading_system.signal_sources:
                self.logger.info("   SIGNAL SOURCES:")
                for source, count in self.trading_system.signal_sources.items():
                    if count > 0:
                        self.logger.info(f"     {source.replace('_', ' ').title()}: {count}")
            
            # Trading execution stats
            self.logger.info("   TRADING EXECUTION:")
            self.logger.info(f"     Mode: {self.trading_system.trading_mode.value}")
            self.logger.info(f"     Assessed: {self.trading_system.execution_metrics['opportunities_assessed']}")
            self.logger.info(f"     Approved: {self.trading_system.execution_metrics['trades_approved']}")
            self.logger.info(f"     Executed: {self.trading_system.analysis_stats['trades_executed']}")
            self.logger.info(f"     Successful: {self.trading_system.analysis_stats['successful_trades']}")
            
            if 'success_rate' in self.trading_system.execution_metrics:
                self.logger.info(f"     Success Rate: {self.trading_system.execution_metrics['success_rate']:.1f}%")
            
            # P&L tracking
            total_pnl = float(self.trading_system.analysis_stats["total_pnl"])
            daily_pnl = self.trading_system.execution_metrics["daily_pnl"]
            self.logger.info(f"     Total P&L: ${total_pnl:.2f}")
            self.logger.info(f"     Daily P&L: ${daily_pnl:.2f}")
            
            # Chain breakdown
            self.logger.info("   CHAIN OPPORTUNITIES:")
            for chain, count in self.trading_system.opportunities_by_chain.items():
                if count > 0:
                    self.logger.info(f"     {chain.capitalize()}: {count}")
            
            # Recommendation breakdown
            self.logger.info("   RECOMMENDATIONS:")
            for action, count in self.trading_system.analysis_stats["recommendations"].items():
                if count > 0:
                    self.logger.info(f"     {action}: {count}")
            
            # Telegram stats
            telegram_stats = self.trading_system.telegram_manager.get_statistics()
            if telegram_stats.get('notifications_enabled'):
                self.logger.info("   TELEGRAM NOTIFICATIONS:")
                self.logger.info(f"     Sent: {telegram_stats.get('notifications_sent', 0)}")
                self.logger.info(f"     Errors: {telegram_stats.get('notification_errors', 0)}")
                
                last_notification = telegram_stats.get('last_notification')
                if last_notification:
                    try:
                        if isinstance(last_notification, str):
                            last_time = datetime.fromisoformat(last_notification.replace('Z', '+00:00'))
                        else:
                            last_time = last_notification
                        time_since = (datetime.now() - last_time).total_seconds() / 60
                        self.logger.info(f"     Last sent: {time_since:.1f} minutes ago")
                    except:
                        pass
            
            # Telegram signal stats
            if telegram_stats.get('signals_enabled'):
                self.logger.info("   TELEGRAM SIGNALS:")
                signal_data = telegram_stats.get('signal_stats', {})
                self.logger.info(f"     Channels Active: {signal_data.get('channels_active', 0)}")
                self.logger.info(f"     Signals Received: {signal_data.get('signals_received', 0)}")
                self.logger.info(f"     Signals Converted: {signal_data.get('signals_converted', 0)}")
                self.logger.info(f"     Buy Signals: {signal_data.get('buy_signals', 0)}")
                self.logger.info(f"     Sell Signals: {signal_data.get('sell_signals', 0)}")
            
            # Portfolio status
            if self.trading_system.position_manager:
                try:
                    portfolio = self.trading_system.trading_executor.get_portfolio_summary()
                    active_positions = portfolio.get('total_positions', 0)
                    total_exposure = portfolio.get('total_exposure_usd', 0)
                    
                    if active_positions > 0:
                        self.logger.info(f"   PORTFOLIO: {active_positions} positions, ${total_exposure:.2f} exposure")
                except Exception:
                    pass  # Ignore portfolio errors in logging
            
            # Dashboard status
            if self.trading_system.dashboard_server and not self.trading_system.disable_dashboard:
                connected_clients = len(getattr(self.trading_system.dashboard_server, 'connected_clients', []))
                self.logger.info(f"   DASHBOARD: {connected_clients} connected clients")
                
        except Exception as e:
            self.logger.error(f"Error logging system statistics: {e}")

    async def update_dashboard_metrics(self) -> None:
        """Update dashboard with latest metrics."""
        try:
            if self.trading_system.dashboard_server and not self.trading_system.disable_dashboard:
                # Update analysis rate
                uptime = datetime.now() - self.trading_system.start_time
                analysis_rate = self.trading_system.analysis_stats["total_analyzed"] / max(uptime.total_seconds() / 60, 1)
                
                await self.trading_system.dashboard_server.update_analysis_rate(int(analysis_rate))
                
                # Update trading metrics
                if hasattr(self.trading_system.dashboard_server, 'update_trading_metrics'):
                    await self.trading_system.dashboard_server.update_trading_metrics(self.trading_system.execution_metrics)
                    
        except Exception as e:
            self.logger.debug(f"Dashboard metrics update failed: {e}")

    async def _check_hourly_telegram_update(self) -> None:
        """Check if it's time to send hourly Telegram status update."""
        try:
            # Delegate to telegram manager
            await self.trading_system.telegram_manager.check_hourly_update()
            
        except Exception as e:
            self.logger.error(f"Error checking hourly Telegram update: {e}")

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        try:
            uptime_seconds = (datetime.now() - self.trading_system.start_time).total_seconds()
            analysis_rate = self.trading_system.analysis_stats["total_analyzed"] / max(uptime_seconds / 60, 1)
            
            return {
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': f"{uptime_seconds//3600:.0f}h {(uptime_seconds%3600)//60:.0f}m",
                'analysis_rate': analysis_rate,
                'total_analyzed': self.trading_system.analysis_stats['total_analyzed'],
                'opportunities_found': self.trading_system.analysis_stats['opportunities_found'],
                'high_confidence': self.trading_system.analysis_stats['high_confidence'],
                'trades_executed': self.trading_system.analysis_stats['trades_executed'],
                'successful_trades': self.trading_system.analysis_stats['successful_trades'],
                'success_rate': self.trading_system.execution_metrics.get('success_rate', 0),
                'daily_pnl': self.trading_system.execution_metrics['daily_pnl'],
                'total_pnl': float(self.trading_system.analysis_stats['total_pnl']),
                'active_positions': self.trading_system.execution_metrics['position_count'],
                'signal_sources': self.trading_system.signal_sources.copy(),
                'opportunities_by_chain': self.trading_system.opportunities_by_chain.copy(),
                'recommendations': self.trading_system.analysis_stats['recommendations'].copy()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")
            return {}
