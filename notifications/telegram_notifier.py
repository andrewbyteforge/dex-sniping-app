#!/usr/bin/env python3
"""
Telegram notification system for crypto trading bot.
Sends real-time alerts for trading opportunities and system status.

File: notifications/telegram_notifier.py
Class: TelegramNotifier
Methods: send_opportunity_alert, send_trade_alert, send_system_alert
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import json
import logging
from dataclasses import dataclass

from models.token import TradingOpportunity, TokenInfo
from utils.logger import logger_manager
from config.settings import settings


class AlertType(Enum):
    """Types of alerts that can be sent."""
    OPPORTUNITY = "opportunity"
    TRADE_EXECUTED = "trade_executed"
    POSITION_CLOSED = "position_closed"
    SYSTEM_STATUS = "system_status"
    ERROR = "error"
    RISK_WARNING = "risk_warning"


class AlertPriority(Enum):
    """Priority levels for alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TelegramAlert:
    """Represents a Telegram alert message."""
    alert_type: AlertType
    priority: AlertPriority
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self) -> None:
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class TelegramNotifier:
    """
    Handles sending notifications to Telegram.
    
    Features:
    - Rich formatted messages with emojis
    - Alert prioritization and rate limiting
    - Automatic retry logic for failed sends
    - Message formatting for different alert types
    - Error handling and logging
    """
    
    def __init__(self) -> None:
        """Initialize Telegram notifier."""
        self.logger = logger_manager.get_logger("TelegramNotifier")
        
        # Configuration
        self.bot_token: Optional[str] = None
        self.chat_id: Optional[str] = None
        self.enabled: bool = False
        
        # Session for HTTP requests
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting
        self.last_message_time: Dict[str, datetime] = {}
        self.min_interval_seconds: int = 5  # Minimum 5 seconds between similar messages
        
        # Retry configuration
        self.max_retries: int = 3
        self.retry_delay: float = 2.0
        
        # Message formatting
        self.emoji_map = {
            AlertType.OPPORTUNITY: "🎯",
            AlertType.TRADE_EXECUTED: "✅",
            AlertType.POSITION_CLOSED: "🚪",
            AlertType.SYSTEM_STATUS: "ℹ️",
            AlertType.ERROR: "❌",
            AlertType.RISK_WARNING: "⚠️"
        }
        
        self.priority_emoji = {
            AlertPriority.LOW: "🔵",
            AlertPriority.MEDIUM: "🟡",
            AlertPriority.HIGH: "🟠",
            AlertPriority.CRITICAL: "🔴"
        }
        
        self._initialize_configuration()

    def _initialize_configuration(self) -> None:
        """Initialize Telegram configuration from settings."""
        try:
            # Get credentials from settings
            if hasattr(settings, 'api') and hasattr(settings.api, 'telegram_bot_token'):
                self.bot_token = settings.api.telegram_bot_token
                self.chat_id = getattr(settings.api, 'telegram_chat_id', None)
            else:
                # Fallback to environment variables
                import os
                self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
                self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
            
            # Check if properly configured
            if self.bot_token and self.chat_id:
                self.enabled = True
                self.logger.info("Telegram notifications enabled")
            else:
                self.enabled = False
                self.logger.warning("Telegram not configured - notifications disabled")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram configuration: {e}")
            self.enabled = False

    async def start(self) -> bool:
        """
        Start the Telegram notifier.
        
        Returns:
            Success status
        """
        try:
            if not self.enabled:
                self.logger.info("Telegram notifier disabled - skipping start")
                return True
            
            # Create HTTP session
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
            
            # Test connection
            success = await self._test_connection()
            if success:
                await self.send_system_alert(
                    "Trading Bot Started",
                    "Crypto trading bot is now online and monitoring opportunities",
                    AlertPriority.MEDIUM
                )
                self.logger.info("Telegram notifier started successfully")
                return True
            else:
                self.logger.error("Telegram connection test failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start Telegram notifier: {e}")
            return False

    async def stop(self) -> None:
        """Stop the Telegram notifier and cleanup resources."""
        try:
            if self.enabled:
                await self.send_system_alert(
                    "Trading Bot Stopped",
                    "Crypto trading bot has been stopped",
                    AlertPriority.MEDIUM
                )
            
            if self.session:
                await self.session.close()
                self.session = None
                
            self.logger.info("Telegram notifier stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping Telegram notifier: {e}")

    async def send_opportunity_alert(
        self,
        opportunity: TradingOpportunity,
        priority: AlertPriority = AlertPriority.MEDIUM
    ) -> bool:
        """
        Send a new trading opportunity alert.
        
        Args:
            opportunity: Trading opportunity data
            priority: Alert priority level
            
        Returns:
            Success status
        """
        try:
            if not self.enabled:
                return True
            
            # Format opportunity message
            message = self._format_opportunity_message(opportunity)
            
            alert = TelegramAlert(
                alert_type=AlertType.OPPORTUNITY,
                priority=priority,
                title=f"New Opportunity: {opportunity.token_symbol}",
                message=message,
                data={"token_address": opportunity.token_address}
            )
            
            return await self._send_alert(alert)
            
        except Exception as e:
            self.logger.error(f"Failed to send opportunity alert: {e}")
            return False

    async def send_trade_alert(
        self,
        action: str,
        token_symbol: str,
        amount: Union[Decimal, float],
        price: Union[Decimal, float],
        details: Optional[Dict[str, Any]] = None,
        priority: AlertPriority = AlertPriority.HIGH
    ) -> bool:
        """
        Send a trade execution alert.
        
        Args:
            action: Trade action (BUY/SELL)
            token_symbol: Token symbol
            amount: Trade amount
            price: Execution price
            details: Additional trade details
            priority: Alert priority level
            
        Returns:
            Success status
        """
        try:
            if not self.enabled:
                return True
            
            # Format trade message
            message = self._format_trade_message(action, token_symbol, amount, price, details)
            
            alert_type = AlertType.TRADE_EXECUTED if action.upper() == "BUY" else AlertType.POSITION_CLOSED
            
            alert = TelegramAlert(
                alert_type=alert_type,
                priority=priority,
                title=f"Trade {action.upper()}: {token_symbol}",
                message=message,
                data=details
            )
            
            return await self._send_alert(alert)
            
        except Exception as e:
            self.logger.error(f"Failed to send trade alert: {e}")
            return False

    async def send_risk_warning(
        self,
        warning_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a risk management warning.
        
        Args:
            warning_type: Type of risk warning
            message: Warning message
            details: Additional warning details
            
        Returns:
            Success status
        """
        try:
            if not self.enabled:
                return True
            
            formatted_message = f"⚠️ **RISK WARNING: {warning_type}**\n\n{message}"
            
            if details:
                formatted_message += "\n\n**Details:**"
                for key, value in details.items():
                    formatted_message += f"\n• {key}: {value}"
            
            alert = TelegramAlert(
                alert_type=AlertType.RISK_WARNING,
                priority=AlertPriority.CRITICAL,
                title=f"Risk Warning: {warning_type}",
                message=formatted_message,
                data=details
            )
            
            return await self._send_alert(alert)
            
        except Exception as e:
            self.logger.error(f"Failed to send risk warning: {e}")
            return False

    async def send_system_alert(
        self,
        title: str,
        message: str,
        priority: AlertPriority = AlertPriority.MEDIUM,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a system status alert.
        
        Args:
            title: Alert title
            message: Alert message
            priority: Alert priority level
            data: Additional data
            
        Returns:
            Success status
        """
        try:
            if not self.enabled:
                return True
            
            alert = TelegramAlert(
                alert_type=AlertType.SYSTEM_STATUS,
                priority=priority,
                title=title,
                message=message,
                data=data
            )
            
            return await self._send_alert(alert)
            
        except Exception as e:
            self.logger.error(f"Failed to send system alert: {e}")
            return False

    async def send_error_alert(
        self,
        error_type: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send an error alert.
        
        Args:
            error_type: Type of error
            error_message: Error message
            details: Additional error details
            
        Returns:
            Success status
        """
        try:
            if not self.enabled:
                return True
            
            formatted_message = f"**ERROR: {error_type}**\n\n{error_message}"
            
            if details:
                formatted_message += "\n\n**Details:**"
                for key, value in details.items():
                    formatted_message += f"\n• {key}: {value}"
            
            alert = TelegramAlert(
                alert_type=AlertType.ERROR,
                priority=AlertPriority.HIGH,
                title=f"Error: {error_type}",
                message=formatted_message,
                data=details
            )
            
            return await self._send_alert(alert)
            
        except Exception as e:
            self.logger.error(f"Failed to send error alert: {e}")
            return False

    async def _send_alert(self, alert: TelegramAlert) -> bool:
        """
        Send alert to Telegram with retry logic.
        
        Args:
            alert: Alert to send
            
        Returns:
            Success status
        """
        try:
            # Check rate limiting
            rate_limit_key = f"{alert.alert_type.value}_{alert.title}"
            if self._is_rate_limited(rate_limit_key):
                self.logger.debug(f"Rate limited alert: {alert.title}")
                return True
            
            # Format final message
            formatted_message = self._format_alert_message(alert)
            
            # Send with retry logic
            for attempt in range(self.max_retries):
                try:
                    success = await self._send_telegram_message(formatted_message)
                    if success:
                        self.last_message_time[rate_limit_key] = datetime.now()
                        return True
                    
                except Exception as e:
                    self.logger.warning(f"Telegram send attempt {attempt + 1} failed: {e}")
                    
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    
            self.logger.error(f"Failed to send Telegram alert after {self.max_retries} attempts")
            return False
            
        except Exception as e:
            self.logger.error(f"Error sending Telegram alert: {e}")
            return False

    async def _send_telegram_message(self, message: str) -> bool:
        """
        Send message to Telegram API.
        
        Args:
            message: Message to send
            
        Returns:
            Success status
        """
        try:
            if not self.session:
                return False
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"Telegram API error {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")
            return False

    async def _test_connection(self) -> bool:
        """
        Test Telegram bot connection.
        
        Returns:
            Connection status
        """
        try:
            if not self.session:
                return False
            
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        bot_info = data.get('result', {})
                        self.logger.info(f"Connected to Telegram bot: {bot_info.get('username', 'Unknown')}")
                        return True
                    
                return False
                
        except Exception as e:
            self.logger.error(f"Telegram connection test failed: {e}")
            return False

    def _is_rate_limited(self, key: str) -> bool:
        """Check if message type is rate limited."""
        if key not in self.last_message_time:
            return False
        
        time_since_last = (datetime.now() - self.last_message_time[key]).total_seconds()
        return time_since_last < self.min_interval_seconds

    def _format_alert_message(self, alert: TelegramAlert) -> str:
        """Format alert for Telegram."""
        emoji = self.emoji_map.get(alert.alert_type, "📢")
        priority_emoji = self.priority_emoji.get(alert.priority, "")
        
        timestamp = alert.timestamp.strftime("%H:%M:%S UTC") if alert.timestamp else ""
        
        header = f"{emoji} {priority_emoji} **{alert.title}**"
        if timestamp:
            header += f" `{timestamp}`"
        
        return f"{header}\n\n{alert.message}"

    def _format_opportunity_message(self, opportunity: TradingOpportunity) -> str:
        """Format trading opportunity message."""
        symbol = opportunity.token_symbol or "UNKNOWN"
        score = opportunity.analysis_score or 0
        
        message = f"**Token:** `{symbol}`\n"
        message += f"**Score:** `{score:.2f}/100`\n"
        message += f"**Chain:** `{opportunity.chain.upper()}`\n"
        
        if opportunity.market_cap:
            message += f"**Market Cap:** `${opportunity.market_cap:,.0f}`\n"
        
        if opportunity.liquidity:
            message += f"**Liquidity:** `${opportunity.liquidity:,.0f}`\n"
        
        if opportunity.volume_24h:
            message += f"**24h Volume:** `${opportunity.volume_24h:,.0f}`\n"
        
        # Add contract address
        address = opportunity.token_address
        if address:
            short_address = f"{address[:6]}...{address[-4:]}"
            message += f"**Contract:** `{short_address}`\n"
        
        # Add analysis highlights
        if hasattr(opportunity, 'analysis_details') and opportunity.analysis_details:
            message += "\n**Analysis:**\n"
            for key, value in opportunity.analysis_details.items():
                if isinstance(value, (int, float)) and value > 0:
                    message += f"• {key.replace('_', ' ').title()}: `{value}`\n"
        
        return message

    def _format_trade_message(
        self,
        action: str,
        token_symbol: str,
        amount: Union[Decimal, float],
        price: Union[Decimal, float],
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format trade execution message."""
        message = f"**Action:** `{action.upper()}`\n"
        message += f"**Token:** `{token_symbol}`\n"
        message += f"**Amount:** `{amount}`\n"
        message += f"**Price:** `${price}`\n"
        
        if details:
            if 'gas_used' in details:
                message += f"**Gas Used:** `{details['gas_used']}`\n"
            if 'transaction_hash' in details:
                tx_hash = details['transaction_hash']
                short_hash = f"{tx_hash[:8]}...{tx_hash[-6:]}"
                message += f"**TX Hash:** `{short_hash}`\n"
            if 'pnl' in details:
                pnl = details['pnl']
                pnl_emoji = "📈" if pnl > 0 else "📉"
                message += f"**P&L:** `{pnl_emoji} ${pnl:,.2f}`\n"
        
        return message


# Global notifier instance
telegram_notifier = TelegramNotifier()