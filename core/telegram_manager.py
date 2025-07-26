#!/usr/bin/env python3
"""
Telegram integration management for the trading system.
Handles both notifications and signal monitoring.

File: core/telegram_manager.py
Class: TelegramManager
Methods: All Telegram-related functionality
"""

import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime

from utils.logger import logger_manager

# Import Telegram integrations
try:
    from integrations.telegram_integration import telegram_integration
    from notifications.telegram_notifier import AlertPriority
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

try:
    from integrations.telegram_signal_integration import telegram_signal_integration
    TELEGRAM_SIGNALS_AVAILABLE = True
except ImportError:
    TELEGRAM_SIGNALS_AVAILABLE = False


class TelegramManager:
    """
    Manages all Telegram functionality for the trading system.
    
    Features:
    - Outbound notifications (alerts, status, errors)
    - Inbound signal monitoring from channels
    - Combined statistics and management
    - Unified interface for all Telegram operations
    """
    
    def __init__(self, trading_system) -> None:
        """
        Initialize Telegram manager.
        
        Args:
            trading_system: Reference to main trading system
        """
        self.trading_system = trading_system
        self.logger = logger_manager.get_logger("TelegramManager")
        
        # Component availability
        self.notifications_available = TELEGRAM_AVAILABLE
        self.signals_available = TELEGRAM_SIGNALS_AVAILABLE
        
        # Component status
        self.notifications_enabled = False
        self.signals_enabled = False
        
        # Statistics tracking
        self.last_hourly_update = datetime.now()
        self.statistics = {
            'notifications_sent': 0,
            'last_notification': None,
            'notification_errors': 0,
            'signals_received': 0,
            'signals_processed': 0,
            'signal_errors': 0
        }

    async def initialize(self) -> None:
        """Initialize all Telegram components."""
        try:
            # Initialize notifications
            await self._initialize_notifications()
            
            # Initialize signal monitoring
            await self._initialize_signal_monitoring()
            
            # Log overall status
            if self.notifications_enabled or self.signals_enabled:
                self.logger.info("✅ Telegram manager initialized")
                features = []
                if self.notifications_enabled:
                    features.append("notifications")
                if self.signals_enabled:
                    features.append("signal monitoring")
                self.logger.info(f"   📱 Active features: {', '.join(features)}")
            else:
                self.logger.info("📱 Telegram manager disabled - no features available")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram manager: {e}")

    async def _initialize_notifications(self) -> None:
        """Initialize Telegram notifications."""
        try:
            if self.trading_system.disable_telegram or not self.notifications_available:
                self.logger.info("📱 Telegram notifications disabled or not available")
                return
            
            self.logger.info("📱 Initializing Telegram notifications...")
            self.notifications_enabled = await telegram_integration.initialize()
            
            if self.notifications_enabled:
                self.logger.info("✅ Telegram notifications enabled")
                
                # Set notification thresholds based on trading mode
                from trading.trading_executor import TradingMode
                if self.trading_system.trading_mode == TradingMode.LIVE_TRADING:
                    telegram_integration.min_score_threshold = 80.0
                else:
                    telegram_integration.min_score_threshold = 70.0
            else:
                self.logger.info("📱 Telegram notifications disabled (not configured)")
                
        except Exception as e:
            self.logger.warning(f"Telegram notifications initialization failed: {e}")
            self.notifications_enabled = False

    async def _initialize_signal_monitoring(self) -> None:
        """Initialize Telegram signal monitoring."""
        try:
            if not self.trading_system.enable_telegram_signals or not self.signals_available:
                self.logger.info("📡 Telegram signal monitoring disabled")
                return
            
            self.logger.info("📡 Initializing Telegram signal monitoring...")
            self.signals_enabled = await telegram_signal_integration.initialize()
            
            if self.signals_enabled:
                # Add callback to handle signals as opportunities
                telegram_signal_integration.add_opportunity_callback(
                    self.trading_system.opportunity_handler.handle_telegram_signal_opportunity
                )
                
                channels_active = telegram_signal_integration.stats.get('channels_active', 0)
                self.logger.info(f"✅ Telegram signal monitoring enabled ({channels_active} channels)")
                
                # Send notification about signal monitoring
                if self.notifications_enabled:
                    await self.handle_system_status(
                        "Signal Monitoring Started",
                        f"Now monitoring {channels_active} Telegram channels for trading signals",
                        {"channels": channels_active}
                    )
            else:
                self.logger.warning("📡 Telegram signal monitoring failed to initialize")
                
        except Exception as e:
            self.logger.warning(f"Telegram signal monitoring initialization failed: {e}")
            self.signals_enabled = False

    # ========================================
    # OUTBOUND NOTIFICATIONS
    # ========================================

    async def handle_new_opportunity(self, opportunity) -> None:
        """Handle new trading opportunity notification."""
        try:
            if not self.notifications_enabled:
                return
            
            await telegram_integration.handle_new_opportunity(opportunity)
            self.statistics['notifications_sent'] += 1
            self.statistics['last_notification'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error sending opportunity notification: {e}")
            self.statistics['notification_errors'] += 1

    async def handle_trading_alert(self, alert_data: Dict[str, Any]) -> None:
        """Handle trading alerts with Telegram notifications."""
        try:
            if not self.notifications_enabled:
                return
            
            alert_type = alert_data.get('type', 'UNKNOWN')
            
            if alert_type == 'TRADE_EXECUTED':
                await telegram_integration.handle_trade_executed(alert_data)
                
            elif alert_type.startswith('POSITION_CLOSED'):
                await telegram_integration.handle_position_closed(alert_data)
                
            elif alert_type == 'TRADE_FAILED':
                error_msg = alert_data.get('error_message', 'Unknown error')
                await telegram_integration.handle_error(
                    error_type="Trade Execution Failed",
                    error_message=error_msg,
                    details=alert_data
                )
                
            elif alert_type.startswith('RISK_WARNING'):
                warning_type = alert_data.get('warning_type', 'General Risk Warning')
                message = alert_data.get('message', 'Risk threshold exceeded')
                await telegram_integration.handle_risk_warning(
                    warning_type=warning_type,
                    message=message,
                    details=alert_data
                )
            
            self.statistics['notifications_sent'] += 1
            self.statistics['last_notification'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error handling trading alert: {e}")
            self.statistics['notification_errors'] += 1

    async def handle_system_status(self, status_type: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Send system status notification."""
        try:
            if not self.notifications_enabled:
                return
            
            await telegram_integration.handle_system_status(status_type, message, data)
            self.statistics['notifications_sent'] += 1
            self.statistics['last_notification'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error sending system status: {e}")
            self.statistics['notification_errors'] += 1

    async def send_startup_notifications(self) -> None:
        """Send startup notifications."""
        try:
            if not self.notifications_enabled:
                return
            
            await telegram_integration.handle_system_status(
                status_type="System Started",
                message="Multi-chain trading bot has started successfully and is monitoring for opportunities",
                data={
                    "version": "2.0",
                    "trading_mode": self.trading_system.trading_mode.value,
                    "auto_trading": self.trading_system.auto_trading_enabled,
                    "enabled_chains": ["ethereum", "base", "solana"],
                    "monitors_count": len(self.trading_system.monitors),
                    "telegram_enabled": self.notifications_enabled,
                    "signal_monitoring": self.signals_enabled,
                    "dashboard_enabled": not self.trading_system.disable_dashboard,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error sending startup notifications: {e}")

    async def send_shutdown_notification(self) -> None:
        """Send shutdown notification."""
        try:
            if not self.notifications_enabled:
                return
            
            await telegram_integration.handle_system_status(
                status_type="System Shutdown",
                message="Trading bot is shutting down gracefully",
                data={
                    "reason": "Manual shutdown",
                    "uptime_hours": self.trading_system._get_uptime_hours()
                }
            )
            
            # Send final daily summary
            await self.send_daily_summary()
            
            # Shutdown integration
            await telegram_integration.shutdown()
            
        except Exception as e:
            self.logger.error(f"Error sending shutdown notification: {e}")

    async def send_daily_summary(self) -> None:
        """Send daily trading summary."""
        try:
            if not self.notifications_enabled:
                return
            
            # Calculate additional stats
            win_rate = 0.0
            if self.trading_system.analysis_stats["trades_executed"] > 0:
                win_rate = (self.trading_system.analysis_stats["successful_trades"] / 
                           self.trading_system.analysis_stats["trades_executed"]) * 100
            
            stats = {
                'opportunities_found': self.trading_system.analysis_stats["opportunities_found"],
                'trades_executed': self.trading_system.analysis_stats["trades_executed"],
                'daily_pnl': float(self.trading_system.analysis_stats["total_pnl"]),
                'win_rate': win_rate
            }
            
            await telegram_integration.send_daily_summary(stats)
            
        except Exception as e:
            self.logger.error(f"Error sending daily summary: {e}")

    async def check_hourly_update(self) -> None:
        """Check if it's time to send hourly status update."""
        try:
            if not self.notifications_enabled:
                return
            
            current_time = datetime.now()
            time_since_last = (current_time - self.last_hourly_update).total_seconds()
            
            # Send hourly update
            if time_since_last >= 3600:  # 1 hour
                await self._send_hourly_update()
                self.last_hourly_update = current_time
            
        except Exception as e:
            self.logger.error(f"Error checking hourly update: {e}")

    async def _send_hourly_update(self) -> None:
        """Send hourly status update."""
        try:
            stats = {
                'opportunities_found': self.trading_system.analysis_stats.get("opportunities_found", 0),
                'trades_executed': self.trading_system.analysis_stats.get("trades_executed", 0),
                'daily_pnl': self.trading_system.execution_metrics.get("daily_pnl", 0),
                'active_positions': self.trading_system.execution_metrics.get("position_count", 0),
                'system_uptime': self.trading_system._get_uptime_hours(),
                'telegram_notifications': self.statistics.get("notifications_sent", 0)
            }
            
            # Format status message
            message = f"System running smoothly. "
            message += f"Found {stats['opportunities_found']} opportunities, "
            message += f"executed {stats['trades_executed']} trades. "
            
            if stats['daily_pnl'] != 0:
                pnl_emoji = "📈" if stats['daily_pnl'] > 0 else "📉"
                message += f"Daily P&L: {pnl_emoji} ${stats['daily_pnl']:.2f}. "
            
            message += f"Sent {stats['telegram_notifications']} notifications."
            
            await self.handle_system_status("Hourly Status Update", message, stats)
            
        except Exception as e:
            self.logger.error(f"Error sending hourly update: {e}")

    # ========================================
    # ERROR HANDLING
    # ========================================

    async def send_initialization_error(self, error_message: str) -> None:
        """Send initialization error notification."""
        try:
            if self.notifications_enabled:
                await telegram_integration.handle_error(
                    error_type="System Initialization Failed",
                    error_message=error_message,
                    details={"timestamp": datetime.now().isoformat()}
                )
        except Exception as e:
            self.logger.error(f"Error sending initialization error: {e}")

    async def send_critical_error(self, error_message: str) -> None:
        """Send critical error notification."""
        try:
            if self.notifications_enabled:
                await telegram_integration.handle_error(
                    error_type="Critical System Error",
                    error_message=error_message,
                    details={"timestamp": datetime.now().isoformat()}
                )
        except Exception as e:
            self.logger.error(f"Error sending critical error: {e}")

    async def send_live_trading_warning(self, portfolio_limits) -> None:
        """Send live trading warning."""
        try:
            if self.notifications_enabled:
                await telegram_integration.handle_risk_warning(
                    warning_type="Live Trading Mode Active",
                    message="System is running in LIVE TRADING mode with real funds at risk",
                    details={
                        "max_exposure": f"${portfolio_limits.max_total_exposure_usd}",
                        "max_position": f"${portfolio_limits.max_single_position_usd}",
                        "daily_loss_limit": f"${portfolio_limits.max_daily_loss_usd}"
                    }
                )
        except Exception as e:
            self.logger.error(f"Error sending live trading warning: {e}")

    async def handle_opportunity_error(self, token_symbol: str, error_message: str) -> None:
        """Handle opportunity processing error."""
        try:
            if self.notifications_enabled:
                await telegram_integration.handle_error(
                    error_type="Opportunity Processing Error",
                    error_message=error_message,
                    details={"token_symbol": token_symbol}
                )
        except Exception as e:
            self.logger.error(f"Error sending opportunity error: {e}")

    async def handle_trading_error(self, token_symbol: str, error_message: str, token_address: str) -> None:
        """Handle trading error."""
        try:
            if self.notifications_enabled:
                await telegram_integration.handle_error(
                    error_type="Trading Assessment Error",
                    error_message=error_message,
                    details={"token_symbol": token_symbol, "token_address": token_address}
                )
        except Exception as e:
            self.logger.error(f"Error sending trading error: {e}")

    async def handle_raydium_error(self, opportunity, error_message: str) -> None:
        """Handle Raydium processing error."""
        try:
            if self.notifications_enabled:
                await telegram_integration.handle_error(
                    error_type="Raydium Opportunity Processing Error",
                    error_message=error_message,
                    details={
                        "token_symbol": getattr(opportunity.token, 'symbol', 'Unknown'),
                        "pool_id": opportunity.metadata.get('pool_id', 'Unknown')
                    }
                )
        except Exception as e:
            self.logger.error(f"Error sending Raydium error: {e}")

    async def handle_monitoring_error(self, error_message: str) -> None:
        """Handle monitoring error."""
        try:
            if self.notifications_enabled:
                await telegram_integration.handle_error(
                    error_type="System Monitoring Error",
                    error_message=error_message,
                    details={"timestamp": datetime.now().isoformat()}
                )
        except Exception as e:
            self.logger.error(f"Error sending monitoring error: {e}")

    async def handle_telegram_signal_received(self, token_symbol: str, signal_type: str, 
                                            channel: str, confidence: float, chain: str) -> None:
        """Handle Telegram signal received notification."""
        try:
            if self.notifications_enabled:
                await telegram_integration.handle_system_status(
                    status_type="Telegram Signal Received",
                    message=f"Received {signal_type.upper()} signal for {token_symbol} from @{channel}",
                    data={
                        "token": token_symbol,
                        "signal_type": signal_type,
                        "channel": channel,
                        "confidence": confidence,
                        "chain": chain
                    }
                )
        except Exception as e:
            self.logger.error(f"Error sending signal received notification: {e}")

    # ========================================
    # SIGNAL MONITORING
    # ========================================

    async def start_signal_monitoring(self) -> None:
        """Start Telegram signal monitoring."""
        try:
            if not self.signals_enabled:
                return
            
            self.logger.info("🎯 Starting Telegram channel monitoring...")
            await telegram_signal_integration.start_monitoring()
            
        except Exception as e:
            self.logger.error(f"Error starting signal monitoring: {e}")

    # ========================================
    # UTILITIES
    # ========================================

    async def test_notifications(self) -> None:
        """Send test notification."""
        try:
            if not self.notifications_enabled:
                self.logger.warning("Telegram not enabled - cannot test")
                return
            
            await telegram_integration.handle_system_status(
                status_type="Test Notification",
                message="This is a test message to verify Telegram integration is working correctly",
                data={"test": True, "timestamp": datetime.now().isoformat()}
            )
            
            self.logger.info("📱 Test Telegram notification sent")
            
        except Exception as e:
            self.logger.error(f"Telegram test failed: {e}")

    async def cleanup(self) -> None:
        """Cleanup Telegram resources."""
        try:
            if self.signals_enabled and telegram_signal_integration:
                await telegram_signal_integration.stop()
                self.logger.info("✅ Telegram signal monitoring stopped")
                
        except Exception as e:
            self.logger.error(f"Error during Telegram cleanup: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get Telegram manager statistics."""
        base_stats = {
            'notifications_enabled': self.notifications_enabled,
            'signals_enabled': self.signals_enabled,
            'notifications_available': self.notifications_available,
            'signals_available': self.signals_available
        }
        
        # Add notification stats
        base_stats.update(self.statistics)
        
        # Add signal stats if available
        if self.signals_enabled and telegram_signal_integration:
            signal_stats = telegram_signal_integration.get_statistics()
            base_stats['signal_stats'] = signal_stats.get('integration', {})
        
        return base_stats