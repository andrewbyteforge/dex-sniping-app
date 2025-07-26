#!/usr/bin/env python3
"""
System monitoring and statistics tracking.
Handles all system monitoring, logging, and performance tracking.

File: core/system_monitoring.py
Class: SystemMonitoring
Methods: monitoring_loop, log_statistics, update_metrics, stop

UPDATE: Added missing stop() method to fix shutdown error
"""

import asyncio
from typing import Dict, Any, Optional
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
    - Graceful shutdown support
    """
    
    def __init__(self, trading_system) -> None:
        """
        Initialize system monitoring.
        
        Args:
            trading_system: Reference to main trading system
        """
        self.trading_system = trading_system
        self.logger = logger_manager.get_logger("SystemMonitoring")
        
        # Monitoring state
        self.is_running = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # Statistics tracking
        self.start_time: Optional[datetime] = None
        self.last_update: Optional[datetime] = None
        self.update_count = 0
        self.error_count = 0
        
        # Performance metrics
        self.metrics = {
            'opportunities_processed': 0,
            'trades_executed': 0,
            'notifications_sent': 0,
            'api_calls_made': 0,
            'errors_encountered': 0,
            'uptime_seconds': 0,
            'memory_usage_mb': 0,
            'cpu_usage_percent': 0
        }

    async def start(self) -> None:
        """
        Start system monitoring.
        
        Begins the monitoring loop that tracks system performance and statistics.
        """
        try:
            if self.is_running:
                self.logger.warning("System monitoring already running")
                return
            
            self.is_running = True
            self.start_time = datetime.now()
            
            self.logger.info("🔄 Starting system monitoring")
            
            # Start monitoring loop as a background task
            self.monitoring_task = asyncio.create_task(self.monitoring_loop())
            
        except Exception as e:
            self.logger.error(f"Failed to start system monitoring: {e}")
            self.is_running = False
            raise

    async def stop(self) -> None:
        """
        Stop system monitoring.
        
        Gracefully stops the monitoring loop and cleans up resources.
        """
        try:
            if not self.is_running:
                self.logger.info("System monitoring already stopped")
                return
            
            self.logger.info("🛑 Stopping system monitoring")
            self.is_running = False
            
            # Cancel monitoring task if running
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # Log final statistics
            await self.log_final_statistics()
            
            self.logger.info("✅ System monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping system monitoring: {e}")

    async def monitoring_loop(self) -> None:
        """
        Main system monitoring and reporting loop.
        
        Continuously tracks system performance and logs statistics.
        """
        self.logger.info("🔄 Starting system monitoring loop")
        
        try:
            while self.is_running:
                try:
                    # Update performance metrics
                    await self.update_performance_metrics()
                    
                    # Log system statistics
                    await self.log_system_statistics()
                    
                    # Update dashboard metrics
                    await self.update_dashboard_metrics()
                    
                    # Check for hourly Telegram updates
                    await self._check_hourly_telegram_update()
                    
                    # Update counters
                    self.update_count += 1
                    self.last_update = datetime.now()
                    
                    # Wait before next update (30 seconds)
                    await asyncio.sleep(30)
                    
                except asyncio.CancelledError:
                    self.logger.info("System monitoring loop cancelled")
                    break
                except Exception as e:
                    self.error_count += 1
                    self.logger.error(f"Error in system monitoring loop: {e}")
                    
                    # Send error notification if available
                    try:
                        if hasattr(self.trading_system, 'telegram_manager'):
                            await self.trading_system.telegram_manager.send_error_notification(
                                error_type="System Monitoring Error",
                                error_message=str(e),
                                details={'error_count': self.error_count}
                            )
                    except Exception as notification_error:
                        self.logger.error(f"Failed to send monitoring error notification: {notification_error}")
                    
                    # Back off on repeated errors
                    await asyncio.sleep(60)
                    
        except Exception as e:
            self.logger.error(f"Fatal error in monitoring loop: {e}")
        finally:
            self.logger.info("System monitoring loop ended")

    async def update_performance_metrics(self) -> None:
        """
        Update system performance metrics.
        
        Collects and updates various performance indicators.
        """
        try:
            # Update uptime
            if self.start_time:
                uptime_seconds = (datetime.now() - self.start_time).total_seconds()
                self.metrics['uptime_seconds'] = int(uptime_seconds)
            
            # Update system metrics from trading system
            if hasattr(self.trading_system, 'opportunities_processed'):
                self.metrics['opportunities_processed'] = self.trading_system.opportunities_processed
            
            if hasattr(self.trading_system, 'trades_executed'):
                self.metrics['trades_executed'] = self.trading_system.trades_executed
            
            if hasattr(self.trading_system, 'notifications_sent'):
                self.metrics['notifications_sent'] = self.trading_system.notifications_sent
            
            # Update Telegram statistics if available
            if hasattr(self.trading_system, 'telegram_manager'):
                telegram_stats = self.trading_system.telegram_manager.get_statistics()
                if 'statistics' in telegram_stats:
                    self.metrics['notifications_sent'] = telegram_stats['statistics'].get('notifications_sent', 0)
            
            # Update error count
            self.metrics['errors_encountered'] = self.error_count
            
            # Try to get system resource usage
            try:
                import psutil
                process = psutil.Process()
                self.metrics['memory_usage_mb'] = round(process.memory_info().rss / 1024 / 1024, 2)
                self.metrics['cpu_usage_percent'] = round(process.cpu_percent(), 2)
            except ImportError:
                # psutil not available, skip resource monitoring
                pass
            except Exception as e:
                self.logger.debug(f"Error getting system resources: {e}")
            
        except Exception as e:
            self.logger.error(f"Error updating performance metrics: {e}")

    async def log_system_statistics(self) -> None:
        """
        Log current system statistics.
        
        Provides regular status updates about system performance.
        """
        try:
            # Only log every 10th update to avoid spam (every 5 minutes)
            if self.update_count % 10 == 0:
                stats_msg = (
                    f"📊 System Statistics - "
                    f"Uptime: {self.metrics['uptime_seconds']}s, "
                    f"Opportunities: {self.metrics['opportunities_processed']}, "
                    f"Trades: {self.metrics['trades_executed']}, "
                    f"Notifications: {self.metrics['notifications_sent']}, "
                    f"Errors: {self.metrics['errors_encountered']}"
                )
                
                if self.metrics['memory_usage_mb'] > 0:
                    stats_msg += f", Memory: {self.metrics['memory_usage_mb']}MB"
                
                if self.metrics['cpu_usage_percent'] > 0:
                    stats_msg += f", CPU: {self.metrics['cpu_usage_percent']}%"
                
                self.logger.info(stats_msg)
            
        except Exception as e:
            self.logger.error(f"Error logging system statistics: {e}")

    async def update_dashboard_metrics(self) -> None:
        """
        Update dashboard with current metrics.
        
        Sends performance data to the web dashboard if available.
        """
        try:
            # Update dashboard if available
            if (hasattr(self.trading_system, 'disable_dashboard') and 
                not self.trading_system.disable_dashboard):
                
                # Try to update dashboard metrics
                try:
                    from api.dashboard_core import dashboard_server
                    if hasattr(dashboard_server, 'update_metrics'):
                        await dashboard_server.update_metrics(self.metrics)
                except ImportError:
                    # Dashboard not available
                    pass
                except Exception as e:
                    self.logger.debug(f"Dashboard update failed: {e}")
            
        except Exception as e:
            self.logger.error(f"Error updating dashboard metrics: {e}")

    async def _check_hourly_telegram_update(self) -> None:
        """
        Check if it's time to send hourly Telegram update.
        
        Sends periodic status updates via Telegram notifications.
        """
        try:
            # Send hourly updates if Telegram is available
            if (hasattr(self.trading_system, 'telegram_manager') and 
                self.trading_system.telegram_manager.notifications_enabled):
                
                # Check if an hour has passed since last hourly update
                telegram_manager = self.trading_system.telegram_manager
                if hasattr(telegram_manager, 'last_hourly_update'):
                    time_since_last = datetime.now() - telegram_manager.last_hourly_update
                    
                    if time_since_last.total_seconds() >= 3600:  # 1 hour
                        await self._send_hourly_update()
                        telegram_manager.last_hourly_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error checking hourly Telegram update: {e}")

    async def _send_hourly_update(self) -> None:
        """
        Send hourly status update via Telegram.
        
        Provides regular system health updates to users.
        """
        try:
            hourly_summary = (
                f"🕐 Hourly System Update\n"
                f"⏱️ Uptime: {self.metrics['uptime_seconds']}s\n"
                f"🎯 Opportunities Processed: {self.metrics['opportunities_processed']}\n"
                f"💰 Trades Executed: {self.metrics['trades_executed']}\n"
                f"📱 Notifications Sent: {self.metrics['notifications_sent']}\n"
                f"❌ Errors: {self.metrics['errors_encountered']}"
            )
            
            if self.metrics['memory_usage_mb'] > 0:
                hourly_summary += f"\n💾 Memory: {self.metrics['memory_usage_mb']}MB"
            
            await self.trading_system.telegram_manager.send_system_status(
                status_type="Hourly Update",
                message=hourly_summary,
                data=self.metrics.copy()
            )
            
        except Exception as e:
            self.logger.error(f"Error sending hourly update: {e}")

    async def log_final_statistics(self) -> None:
        """
        Log final statistics when shutting down.
        
        Provides a summary of system performance during the session.
        """
        try:
            if self.start_time:
                total_uptime = (datetime.now() - self.start_time).total_seconds()
                
                final_summary = (
                    f"📊 Final System Statistics:\n"
                    f"⏱️ Total Uptime: {int(total_uptime)}s ({total_uptime/3600:.2f} hours)\n"
                    f"🎯 Opportunities Processed: {self.metrics['opportunities_processed']}\n"
                    f"💰 Trades Executed: {self.metrics['trades_executed']}\n"
                    f"📱 Notifications Sent: {self.metrics['notifications_sent']}\n"
                    f"🔄 Monitoring Updates: {self.update_count}\n"
                    f"❌ Total Errors: {self.metrics['errors_encountered']}"
                )
                
                self.logger.info(final_summary)
            
        except Exception as e:
            self.logger.error(f"Error logging final statistics: {e}")

    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current system metrics.
        
        Returns:
            Dictionary containing current performance metrics
        """
        return {
            **self.metrics.copy(),
            'is_running': self.is_running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'update_count': self.update_count,
            'monitoring_errors': self.error_count
        }

    async def handle_monitoring_error(self, error_message: str) -> None:
        """
        Handle monitoring-related errors.
        
        Args:
            error_message: Description of the error that occurred
        """
        try:
            self.error_count += 1
            self.logger.error(f"Monitoring error #{self.error_count}: {error_message}")
            
            # Send error notification if Telegram is available
            if (hasattr(self.trading_system, 'telegram_manager') and 
                self.trading_system.telegram_manager.notifications_enabled):
                
                await self.trading_system.telegram_manager.send_error_notification(
                    error_type="System Monitoring Error",
                    error_message=error_message,
                    details={
                        'error_count': self.error_count,
                        'timestamp': datetime.now().isoformat()
                    }
                )
            
        except Exception as e:
            self.logger.error(f"Error handling monitoring error: {e}")