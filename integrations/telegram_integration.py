#!/usr/bin/env python3
"""
Integration file to add Telegram notifications to the main trading system.
Connects the TelegramNotifier to your existing main_with_trading.py system.

File: integrations/telegram_integration.py
Class: TelegramIntegration
Methods: integrate_with_main_system, handle_opportunity, handle_trade_alert
"""

import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime

from notifications.telegram_notifier import telegram_notifier, AlertPriority
from models.token import TradingOpportunity
from utils.logger import logger_manager


class TelegramIntegration:
    """
    Integrates Telegram notifications with the main trading system.
    
    Features:
    - Automatic opportunity notifications
    - Trade execution alerts
    - System status updates
    - Error notifications
    - Risk warnings
    """
    
    def __init__(self) -> None:
        """Initialize Telegram integration."""
        self.logger = logger_manager.get_logger("TelegramIntegration")
        self.enabled: bool = False
        
        # Statistics for filtering
        self.notifications_sent: int = 0
        self.last_opportunity_time: Optional[datetime] = None
        
        # Filter settings
        self.min_score_threshold: float = 70.0  # Only alert on high-score opportunities
        self.max_notifications_per_hour: int = 20  # Rate limiting

    async def initialize(self) -> bool:
        """
        Initialize Telegram integration.
        
        Returns:
            Success status
        """
        try:
            self.logger.info("Initializing Telegram integration...")
            
            # Start telegram notifier
            success = await telegram_notifier.start()
            if success:
                self.enabled = True
                self.logger.info("✅ Telegram integration enabled")
                return True
            else:
                self.logger.warning("❌ Telegram integration failed to start")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram integration: {e}")
            return False

    async def shutdown(self) -> None:
        """Shutdown Telegram integration."""
        try:
            if self.enabled:
                await telegram_notifier.stop()
                self.enabled = False
                self.logger.info("Telegram integration stopped")
                
        except Exception as e:
            self.logger.error(f"Error shutting down Telegram integration: {e}")

    async def handle_new_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Handle new trading opportunity notification.
        
        Args:
            opportunity: Trading opportunity to notify about
        """
        try:
            if not self.enabled:
                return
            
            # Calculate score from multiple sources
            score = 0
            
            # Try to get score from confidence_score (0-1 range)
            if hasattr(opportunity, 'confidence_score') and opportunity.confidence_score:
                score = opportunity.confidence_score * 100
            
            # Try to get score from analysis_score
            elif hasattr(opportunity, 'analysis_score') and opportunity.analysis_score:
                score = opportunity.analysis_score
            
            # Try to get score from metadata
            elif hasattr(opportunity, 'metadata') and opportunity.metadata:
                trading_score = opportunity.metadata.get('trading_score', {})
                if isinstance(trading_score, dict):
                    score = trading_score.get('overall_score', 0) * 100
                elif isinstance(trading_score, (int, float)):
                    score = trading_score * 100
            
            # Default fallback
            if score == 0:
                score = 50  # Default moderate score
            
            # Filter based on score threshold
            if score < self.min_score_threshold:
                self.logger.debug(f"Opportunity {opportunity.token.symbol} below threshold: {score:.1f}")
                return
            
            # Determine priority based on score
            priority = self._get_opportunity_priority(score)
            
            # Send notification
            success = await telegram_notifier.send_opportunity_alert(
                opportunity=opportunity,
                priority=priority
            )
            
            if success:
                self.notifications_sent += 1
                self.last_opportunity_time = datetime.now()
                self.logger.info(f"📱 Telegram alert sent for {opportunity.token.symbol} (score: {score:.1f})")
            else:
                self.logger.warning(f"Failed to send Telegram alert for {opportunity.token.symbol}")
                
        except Exception as e:
            self.logger.error(f"Error handling opportunity notification: {e}")

    async def handle_trade_executed(self, trade_data: Dict[str, Any]) -> None:
        """
        Handle trade execution notification.
        
        Args:
            trade_data: Trade execution data
        """
        try:
            if not self.enabled:
                return
            
            # Extract trade information
            action = trade_data.get('action', 'BUY')
            
            # Try different ways to get token symbol
            token_symbol = (
                trade_data.get('token_symbol') or
                trade_data.get('symbol') or
                trade_data.get('position', {}).get('token_symbol') or
                'UNKNOWN'
            )
            
            amount = trade_data.get('amount', 0)
            price = trade_data.get('price', 0)
            
            # Prepare details
            details = {
                'transaction_hash': trade_data.get('transaction_hash'),
                'gas_used': trade_data.get('gas_used'),
                'chain': trade_data.get('chain'),
                'dex': trade_data.get('dex')
            }
            
            # Remove None values
            details = {k: v for k, v in details.items() if v is not None}
            
            # Send notification
            success = await telegram_notifier.send_trade_alert(
                action=action,
                token_symbol=token_symbol,
                amount=amount,
                price=price,
                details=details,
                priority=AlertPriority.HIGH
            )
            
            if success:
                self.notifications_sent += 1
                self.logger.info(f"📱 Trade alert sent: {action} {token_symbol}")
            else:
                self.logger.warning(f"Failed to send trade alert: {action} {token_symbol}")
                
        except Exception as e:
            self.logger.error(f"Error handling trade notification: {e}")

    async def handle_position_closed(self, position_data: Dict[str, Any]) -> None:
        """
        Handle position closed notification.
        
        Args:
            position_data: Position closure data
        """
        try:
            if not self.enabled:
                return
            
            # Extract position information
            position_info = position_data.get('position', {})
            token_symbol = (
                position_info.get('token_symbol') or
                position_data.get('token_symbol') or
                'UNKNOWN'
            )
            
            entry_price = position_info.get('entry_price', 0)
            exit_price = position_info.get('exit_price', 0)
            amount = position_info.get('amount', 0)
            pnl = position_info.get('unrealized_pnl', 0)
            reason = position_data.get('exit_reason', 'Manual')
            
            # Calculate performance
            pnl_percentage = 0
            if entry_price and entry_price > 0:
                pnl_percentage = ((exit_price - entry_price) / entry_price) * 100
            
            # Prepare details
            details = {
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_percentage': f"{pnl_percentage:.2f}%",
                'exit_reason': reason,
                'duration': position_data.get('duration'),
                'transaction_hash': position_data.get('transaction_hash')
            }
            
            # Remove None values
            details = {k: v for k, v in details.items() if v is not None}
            
            # Send notification
            success = await telegram_notifier.send_trade_alert(
                action="SELL",
                token_symbol=token_symbol,
                amount=amount,
                price=exit_price,
                details=details,
                priority=AlertPriority.HIGH
            )
            
            if success:
                self.notifications_sent += 1
                self.logger.info(f"📱 Position closed alert sent: {token_symbol}")
            else:
                self.logger.warning(f"Failed to send position closed alert: {token_symbol}")
                
        except Exception as e:
            self.logger.error(f"Error handling position closed notification: {e}")

    async def handle_system_status(self, status_type: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Handle system status notification.
        
        Args:
            status_type: Type of status update
            message: Status message
            data: Additional status data
        """
        try:
            if not self.enabled:
                return
            
            # Determine priority based on status type
            priority = AlertPriority.MEDIUM
            if 'error' in status_type.lower() or 'failed' in status_type.lower():
                priority = AlertPriority.HIGH
            elif 'critical' in status_type.lower() or 'warning' in status_type.lower():
                priority = AlertPriority.CRITICAL
            
            # Send notification
            success = await telegram_notifier.send_system_alert(
                title=status_type,
                message=message,
                priority=priority,
                data=data
            )
            
            if success:
                self.notifications_sent += 1
                self.logger.debug(f"📱 System status alert sent: {status_type}")
                
        except Exception as e:
            self.logger.error(f"Error handling system status notification: {e}")

    async def handle_risk_warning(self, warning_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Handle risk warning notification.
        
        Args:
            warning_type: Type of risk warning
            message: Warning message
            details: Additional warning details
        """
        try:
            if not self.enabled:
                return
            
            # Send risk warning
            success = await telegram_notifier.send_risk_warning(
                warning_type=warning_type,
                message=message,
                details=details
            )
            
            if success:
                self.notifications_sent += 1
                self.logger.info(f"📱 Risk warning sent: {warning_type}")
                
        except Exception as e:
            self.logger.error(f"Error handling risk warning notification: {e}")

    async def handle_error(self, error_type: str, error_message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Handle error notification.
        
        Args:
            error_type: Type of error
            error_message: Error message
            details: Additional error details
        """
        try:
            if not self.enabled:
                return
            
            # Send error alert
            success = await telegram_notifier.send_error_alert(
                error_type=error_type,
                error_message=error_message,
                details=details
            )
            
            if success:
                self.notifications_sent += 1
                self.logger.info(f"📱 Error alert sent: {error_type}")
                
        except Exception as e:
            self.logger.error(f"Error handling error notification: {e}")

    async def send_daily_summary(self, stats: Dict[str, Any]) -> None:
        """
        Send daily trading summary.
        
        Args:
            stats: Daily trading statistics
        """
        try:
            if not self.enabled:
                return
            
            # Format daily summary message
            message = "**📊 Daily Trading Summary**\n\n"
            
            # Add key statistics
            opportunities = stats.get('opportunities_found', 0)
            trades = stats.get('trades_executed', 0)
            pnl = stats.get('daily_pnl', 0)
            
            message += f"**Opportunities Found:** `{opportunities}`\n"
            message += f"**Trades Executed:** `{trades}`\n"
            message += f"**Daily P&L:** `${pnl:,.2f}`\n"
            
            if stats.get('win_rate'):
                message += f"**Win Rate:** `{stats['win_rate']:.1f}%`\n"
            
            if stats.get('best_performer'):
                best = stats['best_performer']
                message += f"**Best Performer:** `{best['symbol']} (+{best['pnl']:.1f}%)`\n"
            
            # Send summary
            success = await telegram_notifier.send_system_alert(
                title="Daily Summary",
                message=message,
                priority=AlertPriority.LOW
            )
            
            if success:
                self.logger.info("📱 Daily summary sent")
                
        except Exception as e:
            self.logger.error(f"Error sending daily summary: {e}")

    def _get_opportunity_priority(self, score: float) -> AlertPriority:
        """
        Determine alert priority based on opportunity score.
        
        Args:
            score: Opportunity analysis score
            
        Returns:
            Alert priority level
        """
        if score >= 90:
            return AlertPriority.CRITICAL
        elif score >= 80:
            return AlertPriority.HIGH
        elif score >= 70:
            return AlertPriority.MEDIUM
        else:
            return AlertPriority.LOW

    def get_statistics(self) -> Dict[str, Any]:
        """Get Telegram integration statistics."""
        return {
            'enabled': self.enabled,
            'notifications_sent': self.notifications_sent,
            'last_opportunity_time': self.last_opportunity_time.isoformat() if self.last_opportunity_time else None,
            'score_threshold': self.min_score_threshold,
            'max_notifications_per_hour': self.max_notifications_per_hour
        }


# Global integration instance
telegram_integration = TelegramIntegration()