#!/usr/bin/env python3
"""
Telegram integration management for the trading system.
Handles both notifications and signal monitoring.

File: core/telegram_manager.py
Class: TelegramManager
Methods: All Telegram-related functionality

UPDATE: Added missing methods like test_notifications, send_system_startup, send_initialization_error
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
        """
        Initialize all Telegram components.
        
        Raises:
            Exception: If critical initialization fails
        """
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
            # Don't raise - let the system continue without Telegram

    async def _initialize_notifications(self) -> None:
        """
        Initialize Telegram notifications.
        
        Sets up outbound notification system for trading alerts and system status.
        """
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
                if hasattr(self.trading_system, 'trading_mode'):
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
        """
        Initialize Telegram signal monitoring.
        
        Sets up inbound signal monitoring from configured Telegram channels.
        """
        try:
            if not self.trading_system.enable_telegram_signals or not self.signals_available:
                self.logger.info("📱 Telegram signal monitoring disabled or not available")
                return
            
            self.logger.info("📱 Initializing Telegram signal monitoring...")
            
            # Initialize signal integration
            self.signals_enabled = await telegram_signal_integration.initialize()
            
            if self.signals_enabled:
                # Add signal callback to forward signals to opportunity handler
                telegram_signal_integration.add_opportunity_callback(
                    self._handle_telegram_signal
                )
                self.logger.info("✅ Telegram signal monitoring enabled")
            else:
                self.logger.info("📱 Telegram signal monitoring disabled (not configured)")
                
        except Exception as e:
            self.logger.warning(f"Telegram signal monitoring initialization failed: {e}")
            self.signals_enabled = False

    async def _handle_telegram_signal(self, opportunity) -> None:
        """
        Handle incoming Telegram signal by forwarding to opportunity handler.
        
        Args:
            opportunity: TradingOpportunity object converted from signal
        """
        try:
            self.statistics['signals_received'] += 1
            
            # Forward to opportunity handler
            if hasattr(self.trading_system, 'opportunity_handler'):
                await self.trading_system.opportunity_handler.handle_new_opportunity(opportunity)
                self.statistics['signals_processed'] += 1
            
            self.logger.info(f"Processed Telegram signal for {opportunity.token_info.symbol}")
            
        except Exception as e:
            self.logger.error(f"Error handling Telegram signal: {e}")
            self.statistics['signal_errors'] += 1

    # ========================================
    # NOTIFICATION METHODS
    # ========================================

    async def send_opportunity_alert(self, opportunity) -> None:
        """
        Send trading opportunity notification.
        
        Args:
            opportunity: TradingOpportunity object to alert about
        """
        try:
            if not self.notifications_enabled:
                return
            
            await telegram_integration.handle_new_opportunity(opportunity)
            self.statistics['notifications_sent'] += 1
            self.statistics['last_notification'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error sending opportunity alert: {e}")
            self.statistics['notification_errors'] += 1

    async def send_trade_alert(self, alert_data: Dict[str, Any]) -> None:
        """
        Send trading execution alert.
        
        Args:
            alert_data: Dictionary containing trade execution information
        """
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

    async def send_system_status(self, status_type: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Send system status notification.
        
        Args:
            status_type: Type of status update
            message: Status message
            data: Additional status data
        """
        try:
            if not self.notifications_enabled:
                return
            
            await telegram_integration.handle_system_status(status_type, message, data)
            self.statistics['notifications_sent'] += 1
            self.statistics['last_notification'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error sending system status: {e}")
            self.statistics['notification_errors'] += 1

    async def send_system_startup(self) -> None:
        """
        Send system startup notification.
        
        Notifies about successful system initialization and current configuration.
        """
        try:
            if not self.notifications_enabled:
                return
            
            await telegram_integration.handle_system_status(
                status_type="System Started",
                message="Multi-chain trading bot has started successfully and is monitoring for opportunities",
                data={
                    "version": "2.0",
                    "trading_mode": getattr(self.trading_system.trading_mode, 'value', 'unknown'),
                    "auto_trading": self.trading_system.auto_trading_enabled,
                    "enabled_chains": ["ethereum", "base", "solana"],
                    "telegram_enabled": self.notifications_enabled,
                    "signal_monitoring": self.signals_enabled,
                    "dashboard_enabled": not self.trading_system.disable_dashboard,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            self.logger.info("📱 System startup notification sent")
            
        except Exception as e:
            self.logger.error(f"Error sending startup notification: {e}")

    async def send_system_shutdown(self) -> None:
        """
        Send system shutdown notification.
        
        Notifies about graceful system shutdown and provides final summary.
        """
        try:
            if not self.notifications_enabled:
                return
            
            uptime_hours = 0
            if hasattr(self.trading_system, 'start_time') and self.trading_system.start_time:
                uptime_seconds = (datetime.now() - self.trading_system.start_time).total_seconds()
                uptime_hours = round(uptime_seconds / 3600, 2)
            
            await telegram_integration.handle_system_status(
                status_type="System Shutdown",
                message="Trading bot is shutting down gracefully",
                data={
                    "reason": "Manual shutdown",
                    "uptime_hours": uptime_hours,
                    "opportunities_processed": getattr(self.trading_system, 'opportunities_processed', 0),
                    "trades_executed": getattr(self.trading_system, 'trades_executed', 0),
                    "notifications_sent": self.statistics['notifications_sent']
                }
            )
            
            self.logger.info("📱 System shutdown notification sent")
            
        except Exception as e:
            self.logger.error(f"Error sending shutdown notification: {e}")

    async def send_initialization_error(self, error_message: str) -> None:
        """
        Send initialization error notification.
        
        Args:
            error_message: Description of the initialization error
        """
        try:
            if not self.notifications_enabled:
                return
            
            await telegram_integration.handle_error(
                error_type="System Initialization Error",
                error_message=error_message,
                details={
                    "timestamp": datetime.now().isoformat(),
                    "component": "EnhancedTradingSystem",
                    "severity": "critical"
                }
            )
            
            self.logger.info("📱 Initialization error notification sent")
            
        except Exception as e:
            self.logger.error(f"Error sending initialization error notification: {e}")

    async def test_notifications(self) -> None:
        """
        Send test notification to verify Telegram integration.
        
        Sends a test message to confirm the notification system is working correctly.
        """
        try:
            if not self.notifications_enabled:
                self.logger.warning("Telegram not enabled - cannot test")
                return
            
            await telegram_integration.handle_system_status(
                status_type="Test Notification",
                message="This is a test message to verify Telegram integration is working correctly",
                data={
                    "test": True, 
                    "timestamp": datetime.now().isoformat(),
                    "manager_version": "2.0",
                    "features_enabled": {
                        "notifications": self.notifications_enabled,
                        "signal_monitoring": self.signals_enabled
                    }
                }
            )
            
            self.logger.info("📱 Test Telegram notification sent")
            
        except Exception as e:
            self.logger.error(f"Telegram test failed: {e}")
            raise

    # ========================================
    # SIGNAL MONITORING
    # ========================================

    async def start_signal_monitoring(self) -> None:
        """
        Start Telegram signal monitoring.
        
        Begins monitoring configured Telegram channels for trading signals.
        """
        try:
            if not self.signals_enabled:
                self.logger.info("Signal monitoring not enabled")
                return
            
            self.logger.info("🎯 Starting Telegram channel monitoring...")
            await telegram_signal_integration.start_monitoring()
            
        except Exception as e:
            self.logger.error(f"Error starting signal monitoring: {e}")

    async def stop_signal_monitoring(self) -> None:
        """
        Stop Telegram signal monitoring.
        
        Stops monitoring Telegram channels and cleans up resources.
        """
        try:
            if self.signals_enabled and telegram_signal_integration:
                await telegram_signal_integration.stop()
                self.logger.info("✅ Telegram signal monitoring stopped")
                
        except Exception as e:
            self.logger.error(f"Error stopping signal monitoring: {e}")

    # ========================================
    # UTILITIES AND MANAGEMENT
    # ========================================

    async def shutdown(self) -> None:
        """
        Shutdown Telegram manager and cleanup resources.
        
        Gracefully stops all Telegram services and cleans up connections.
        """
        try:
            # Send shutdown notification first
            await self.send_system_shutdown()
            
            # Stop signal monitoring
            await self.stop_signal_monitoring()
            
            # Shutdown notification integration
            if self.notifications_enabled and telegram_integration:
                await telegram_integration.shutdown()
                self.logger.info("✅ Telegram notifications stopped")
            
            self.notifications_enabled = False
            self.signals_enabled = False
            
            self.logger.info("📱 Telegram manager shutdown complete")
                
        except Exception as e:
            self.logger.error(f"Error during Telegram shutdown: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get Telegram manager statistics.
        
        Returns:
            Dictionary containing usage statistics and status information
        """
        return {
            "notifications_available": self.notifications_available,
            "signals_available": self.signals_available,
            "notifications_enabled": self.notifications_enabled,
            "signals_enabled": self.signals_enabled,
            "statistics": self.statistics.copy(),
            "last_hourly_update": self.last_hourly_update.isoformat() if self.last_hourly_update else None
        }

    async def send_daily_summary(self) -> None:
        """
        Send daily trading summary.
        
        Provides a summary of the day's trading activity and system performance.
        """
        try:
            if not self.notifications_enabled:
                return
            
            # Collect summary data
            summary_data = {
                "opportunities_processed": getattr(self.trading_system, 'opportunities_processed', 0),
                "trades_executed": getattr(self.trading_system, 'trades_executed', 0),
                "notifications_sent": self.statistics['notifications_sent'],
                "signals_received": self.statistics['signals_received'],
                "uptime_hours": 0
            }
            
            if hasattr(self.trading_system, 'start_time') and self.trading_system.start_time:
                uptime_seconds = (datetime.now() - self.trading_system.start_time).total_seconds()
                summary_data["uptime_hours"] = round(uptime_seconds / 3600, 2)
            
            await telegram_integration.handle_system_status(
                status_type="Daily Summary",
                message="Daily trading activity summary",
                data=summary_data
            )
            
            self.logger.info("📱 Daily summary sent")
            
        except Exception as e:
            self.logger.error(f"Error sending daily summary: {e}")

    async def handle_new_opportunity(self, opportunity) -> None:
        """
        Handle new trading opportunity notification.
        
        Args:
            opportunity: TradingOpportunity object to process
        """
        try:
            if not self.notifications_enabled:
                return
            
            # Forward to the main opportunity alert handler
            await self.send_opportunity_alert(opportunity)
            
        except Exception as e:
            self.logger.error(f"Error handling new opportunity: {e}")

    async def handle_opportunity_error(self, error_message: str, opportunity=None) -> None:
        """
        Handle opportunity processing errors.
        
        Args:
            error_message: Description of the error
            opportunity: The opportunity that caused the error (optional)
        """
        try:
            self.statistics['notification_errors'] += 1
            
            # Log the error
            self.logger.error(f"Opportunity processing error: {error_message}")
            
            # Send error notification if it's critical
            if self.notifications_enabled and "critical" in error_message.lower():
                await self.send_error_notification(
                    error_type="Opportunity Processing Error",
                    error_message=error_message,
                    details={
                        'opportunity_symbol': getattr(opportunity, 'token_info', {}).get('symbol', 'Unknown') if opportunity else 'Unknown',
                        'timestamp': datetime.now().isoformat()
                    }
                )
            
        except Exception as e:
            self.logger.error(f"Error handling opportunity error: {e}")

    async def send_error_notification(self, error_type: str, error_message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Send error notification.
        
        Args:
            error_type: Type of error that occurred
            error_message: Description of the error
            details: Additional error details
        """
        try:
            if not self.notifications_enabled:
                return
            
            await telegram_integration.handle_error(
                error_type=error_type,
                error_message=error_message,
                details=details or {}
            )
            
            self.statistics['notifications_sent'] += 1
            self.statistics['last_notification'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error sending error notification: {e}")
            self.statistics['notification_errors'] += 1