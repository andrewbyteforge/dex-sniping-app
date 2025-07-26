#!/usr/bin/env python3
"""
Telegram Notifier for DEX Sniping System - Phase 2 Implementation

File: notifications/telegram_notifier.py
Purpose: Send real-time alerts and notifications via Telegram bot
Phase: 2 - Basic Automation (Telegram/Discord bot for alerts)
"""

import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import os
from urllib.parse import quote

from models.token import TradingOpportunity, TokenInfo, RiskLevel
from utils.logger import logger_manager


class AlertType(Enum):
    """Types of Telegram alerts."""
    OPPORTUNITY = "opportunity"
    TRADE_EXECUTED = "trade_executed"
    POSITION_CLOSED = "position_closed"
    SYSTEM_STATUS = "system_status"
    ERROR_ALERT = "error_alert"
    WHALE_MOVEMENT = "whale_movement"


@dataclass
class TelegramConfig:
    """Configuration for Telegram notifications."""
    bot_token: str
    chat_id: str
    enabled: bool = True
    min_confidence: float = 0.6
    min_liquidity_usd: float = 5000.0
    enabled_chains: List[str] = None
    enabled_alert_types: List[AlertType] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.enabled_chains is None:
            self.enabled_chains = ["ethereum", "base", "solana"]
        if self.enabled_alert_types is None:
            self.enabled_alert_types = [
                AlertType.OPPORTUNITY,
                AlertType.TRADE_EXECUTED,
                AlertType.POSITION_CLOSED,
                AlertType.SYSTEM_STATUS
            ]


class TelegramNotifier:
    """
    Telegram notification system for DEX sniping alerts.
    
    Integrates with existing alert infrastructure to send real-time
    notifications for trading opportunities, executions, and system status.
    """
    
    def __init__(self, config: Optional[TelegramConfig] = None) -> None:
        """
        Initialize Telegram notifier.
        
        Args:
            config: Telegram configuration. If None, loads from environment.
        """
        self.logger = logger_manager.get_logger("TelegramNotifier")
        
        # Load configuration
        if config is None:
            config = self._load_config_from_env()
        
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Statistics
        self.stats = {
            "messages_sent": 0,
            "messages_failed": 0,
            "last_message_time": None,
            "uptime_start": datetime.now()
        }
        
        # Rate limiting
        self.last_message_time = datetime.min
        self.message_count_minute = 0
        self.max_messages_per_minute = 20  # Telegram rate limit
        
        if self.config.enabled:
            self.logger.info("🤖 Telegram notifier initialized")
            self.logger.info(f"   📱 Chat ID: {self.config.chat_id}")
            self.logger.info(f"   🎯 Min confidence: {self.config.min_confidence}")
            self.logger.info(f"   💰 Min liquidity: ${self.config.min_liquidity_usd:,.0f}")
        else:
            self.logger.info("🤖 Telegram notifier disabled")
    
    def _load_config_from_env(self) -> TelegramConfig:
        """
        Load Telegram configuration from environment variables.
        
        Returns:
            TelegramConfig: Configuration object
            
        Raises:
            ValueError: If required environment variables are missing
        """
        try:
            # Required variables
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            chat_id = os.getenv('TELEGRAM_CHAT_ID')
            
            if not bot_token or not chat_id:
                self.logger.warning("Telegram bot token or chat ID not found in environment")
                return TelegramConfig(
                    bot_token="",
                    chat_id="",
                    enabled=False
                )
            
            # Optional variables with defaults
            enabled = os.getenv('TELEGRAM_ALERTS_ENABLED', 'true').lower() == 'true'
            min_confidence = float(os.getenv('TELEGRAM_MIN_CONFIDENCE', '0.6'))
            min_liquidity = float(os.getenv('TELEGRAM_MIN_LIQUIDITY', '5000'))
            
            # Parse enabled chains
            chains_str = os.getenv('TELEGRAM_CHAINS', 'ethereum,base,solana')
            enabled_chains = [chain.strip() for chain in chains_str.split(',')]
            
            return TelegramConfig(
                bot_token=bot_token,
                chat_id=chat_id,
                enabled=enabled,
                min_confidence=min_confidence,
                min_liquidity_usd=min_liquidity,
                enabled_chains=enabled_chains
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load Telegram config: {e}")
            return TelegramConfig(bot_token="", chat_id="", enabled=False)
    
    async def initialize(self) -> None:
        """Initialize HTTP session and test connection."""
        try:
            if not self.config.enabled:
                return
            
            # Initialize HTTP session
            self.session = aiohttp.ClientSession()
            
            # Test bot connection
            await self._test_bot_connection()
            
            self.logger.info("✅ Telegram notifier initialized and tested")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram notifier: {e}")
            self.config.enabled = False
    
    async def _test_bot_connection(self) -> None:
        """Test Telegram bot connection."""
        try:
            url = f"https://api.telegram.org/bot{self.config.bot_token}/getMe"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        bot_info = data.get('result', {})
                        self.logger.info(f"🤖 Connected to Telegram bot: {bot_info.get('username', 'Unknown')}")
                    else:
                        raise Exception(f"Bot API error: {data.get('description', 'Unknown error')}")
                else:
                    raise Exception(f"HTTP {response.status}")
                    
        except Exception as e:
            self.logger.error(f"Telegram bot connection test failed: {e}")
            raise
    
    async def send_opportunity_alert(self, opportunity: TradingOpportunity) -> bool:
        """
        Send trading opportunity alert to Telegram.
        
        Args:
            opportunity: Trading opportunity to alert about
            
        Returns:
            bool: True if message sent successfully
        """
        try:
            if not self._should_send_opportunity_alert(opportunity):
                return False
            
            # Format opportunity message
            message = self._format_opportunity_message(opportunity)
            
            # Send message
            success = await self._send_message(message, alert_type=AlertType.OPPORTUNITY)
            
            if success:
                self.logger.info(f"📱 Sent opportunity alert: {opportunity.token.symbol}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to send opportunity alert: {e}")
            return False
    
    async def send_trading_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Send trading execution alert to Telegram.
        
        Args:
            alert_data: Trading alert data from the system
            
        Returns:
            bool: True if message sent successfully
        """
        try:
            if not self.config.enabled:
                return False
            
            alert_type_str = alert_data.get('type', 'UNKNOWN')
            
            # Map alert types
            alert_type_mapping = {
                'TRADE_EXECUTED': AlertType.TRADE_EXECUTED,
                'POSITION_CLOSED': AlertType.POSITION_CLOSED,
                'TRADE_FAILED': AlertType.ERROR_ALERT,
                'WHALE_MOVEMENT': AlertType.WHALE_MOVEMENT
            }
            
            alert_type = alert_type_mapping.get(alert_type_str, AlertType.SYSTEM_STATUS)
            
            # Check if this alert type is enabled
            if alert_type not in self.config.enabled_alert_types:
                return False
            
            # Format message based on alert type
            if alert_type == AlertType.TRADE_EXECUTED:
                message = self._format_trade_executed_message(alert_data)
            elif alert_type == AlertType.POSITION_CLOSED:
                message = self._format_position_closed_message(alert_data)
            elif alert_type == AlertType.WHALE_MOVEMENT:
                message = self._format_whale_movement_message(alert_data)
            else:
                message = self._format_generic_alert_message(alert_data)
            
            # Send message
            success = await self._send_message(message, alert_type=alert_type)
            
            if success:
                self.logger.info(f"📱 Sent {alert_type_str} alert")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to send trading alert: {e}")
            return False
    
    async def send_system_status(self, status_data: Dict[str, Any]) -> bool:
        """
        Send system status update to Telegram.
        
        Args:
            status_data: System status information
            
        Returns:
            bool: True if message sent successfully
        """
        try:
            if not self.config.enabled:
                return False
            
            if AlertType.SYSTEM_STATUS not in self.config.enabled_alert_types:
                return False
            
            message = self._format_system_status_message(status_data)
            
            success = await self._send_message(message, alert_type=AlertType.SYSTEM_STATUS)
            
            if success:
                self.logger.info("📱 Sent system status update")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to send system status: {e}")
            return False
    
    def _should_send_opportunity_alert(self, opportunity: TradingOpportunity) -> bool:
        """
        Determine if opportunity alert should be sent.
        
        Args:
            opportunity: Trading opportunity to evaluate
            
        Returns:
            bool: True if alert should be sent
        """
        try:
            if not self.config.enabled:
                return False
            
            if AlertType.OPPORTUNITY not in self.config.enabled_alert_types:
                return False
            
            # Check confidence threshold
            if opportunity.confidence_score < self.config.min_confidence:
                return False
            
            # Check liquidity threshold
            if opportunity.liquidity.liquidity_usd < self.config.min_liquidity_usd:
                return False
            
            # Check chain filter
            chain = opportunity.metadata.get('chain', 'unknown').lower()
            if chain not in self.config.enabled_chains:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error evaluating opportunity alert: {e}")
            return False
    
    def _format_opportunity_message(self, opportunity: TradingOpportunity) -> str:
        """Format trading opportunity as Telegram message."""
        try:
            token = opportunity.token
            liquidity = opportunity.liquidity
            metadata = opportunity.metadata
            
            # Get chain and format
            chain = metadata.get('chain', 'unknown').upper()
            chain_emoji = {
                'ETHEREUM': '🔷',
                'BASE': '🔵', 
                'SOLANA': '🟣'
            }.get(chain, '⚪')
            
            # Get recommendation
            recommendation = metadata.get('recommendation', {})
            action = recommendation.get('action', 'MONITOR')
            confidence = recommendation.get('confidence', 'MEDIUM')
            
            # Risk level emoji
            risk_emoji = {
                'LOW': '🟢',
                'MEDIUM': '🟡',
                'HIGH': '🔴',
                'CRITICAL': '🚨'
            }.get(str(opportunity.contract_analysis.risk_level).upper(), '🟡')
            
            # Format message
            message = f"""🚨 NEW OPPORTUNITY DETECTED
    
💎 Token: {token.symbol or 'UNKNOWN'}
{chain_emoji} Chain: {chain}
💰 Liquidity: ${liquidity.liquidity_usd:,.0f}
📊 Confidence: {opportunity.confidence_score:.1%}
⚡ Action: {action}
🎯 Confidence Level: {confidence}
{risk_emoji} Risk: {opportunity.contract_analysis.risk_level.value.upper()}

📈 DEX: {liquidity.dex_name}
🔗 Contract: `{token.address}`
⏰ Detected: {opportunity.detected_at.strftime('%H:%M:%S')}"""

            # Add trading score if available
            trading_score = metadata.get('trading_score', {})
            if trading_score:
                overall_score = trading_score.get('overall_score', 0)
                message += f"\n📊 Score: {overall_score:.1%}"
            
            # Add volume if available
            volume_24h = metadata.get('raydium_data', {}).get('volume_24h', 0)
            if volume_24h > 0:
                message += f"\n📊 Volume 24h: ${volume_24h:,.0f}"
            
            return message
            
        except Exception as e:
            self.logger.error(f"Error formatting opportunity message: {e}")
            return f"🚨 NEW OPPORTUNITY: {opportunity.token.symbol} (Error formatting details)"
    
    def _format_trade_executed_message(self, alert_data: Dict[str, Any]) -> str:
        """Format trade execution message."""
        try:
            position_data = alert_data.get('position', {})
            token_symbol = position_data.get('token_symbol', 'UNKNOWN')
            amount = position_data.get('amount', 0)
            entry_price = position_data.get('entry_price', 0)
            
            message = f"""✅ TRADE EXECUTED

💎 Token: {token_symbol}
💵 Amount: {amount}
📈 Entry Price: ${entry_price}
⏰ Time: {datetime.now().strftime('%H:%M:%S')}"""

            return message
            
        except Exception as e:
            self.logger.error(f"Error formatting trade executed message: {e}")
            return "✅ TRADE EXECUTED (Error formatting details)"
    
    def _format_position_closed_message(self, alert_data: Dict[str, Any]) -> str:
        """Format position closed message."""
        try:
            position_data = alert_data.get('position', {})
            token_symbol = position_data.get('token_symbol', 'UNKNOWN')
            pnl = position_data.get('unrealized_pnl', 0)
            
            pnl_emoji = "📈" if pnl > 0 else "📉"
            pnl_text = f"+${pnl:.2f}" if pnl > 0 else f"${pnl:.2f}"
            
            message = f"""🚪 POSITION CLOSED

💎 Token: {token_symbol}
{pnl_emoji} P&L: {pnl_text}
⏰ Time: {datetime.now().strftime('%H:%M:%S')}"""

            return message
            
        except Exception as e:
            self.logger.error(f"Error formatting position closed message: {e}")
            return "🚪 POSITION CLOSED (Error formatting details)"
    
    def _format_whale_movement_message(self, alert_data: Dict[str, Any]) -> str:
        """Format whale movement message."""
        try:
            whale_data = alert_data.get('whale_data', {})
            amount_usd = whale_data.get('amount_usd', 0)
            movement_type = whale_data.get('movement_type', 'unknown')
            token_symbol = whale_data.get('token_symbol', 'UNKNOWN')
            
            message = f"""🐋 WHALE MOVEMENT DETECTED

💎 Token: {token_symbol}
💰 Amount: ${amount_usd:,.0f}
📊 Type: {movement_type.upper()}
⏰ Time: {datetime.now().strftime('%H:%M:%S')}"""

            return message
            
        except Exception as e:
            self.logger.error(f"Error formatting whale movement message: {e}")
            return "🐋 WHALE MOVEMENT (Error formatting details)"
    
    def _format_system_status_message(self, status_data: Dict[str, Any]) -> str:
        """Format system status message."""
        try:
            system = status_data.get('system', {})
            monitors = status_data.get('monitors', [])
            opportunities = status_data.get('opportunities', {})
            
            uptime = system.get('uptime_formatted', 'Unknown')
            active_monitors = len([m for m in monitors if m.get('is_running', False)])
            total_opportunities = opportunities.get('total_found', 0)
            
            message = f"""📊 SYSTEM STATUS

🟢 Status: Running
⏰ Uptime: {uptime}
🔍 Active Monitors: {active_monitors}
🎯 Opportunities Today: {total_opportunities}
📈 Analysis Rate: {system.get('analysis_rate', 0)}/min"""

            return message
            
        except Exception as e:
            self.logger.error(f"Error formatting system status message: {e}")
            return "📊 SYSTEM STATUS (Error formatting details)"
    
    def _format_generic_alert_message(self, alert_data: Dict[str, Any]) -> str:
        """Format generic alert message."""
        try:
            alert_type = alert_data.get('type', 'UNKNOWN')
            message_text = alert_data.get('message', 'No details available')
            
            return f"""🔔 SYSTEM ALERT

Type: {alert_type}
Message: {message_text}
Time: {datetime.now().strftime('%H:%M:%S')}"""
            
        except Exception as e:
            self.logger.error(f"Error formatting generic alert: {e}")
            return f"🔔 SYSTEM ALERT: {alert_data.get('type', 'UNKNOWN')}"
    
    async def _send_message(self, message: str, alert_type: AlertType) -> bool:
        """
        Send message to Telegram.
        
        Args:
            message: Message text to send
            alert_type: Type of alert for logging
            
        Returns:
            bool: True if message sent successfully
        """
        try:
            if not self.config.enabled or not self.session:
                return False
            
            # Rate limiting check
            if not self._rate_limit_check():
                self.logger.warning("Rate limit exceeded, skipping message")
                return False
            
            # Prepare API request
            url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
            
            payload = {
                'chat_id': self.config.chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            # Send message
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        self.stats["messages_sent"] += 1
                        self.stats["last_message_time"] = datetime.now()
                        return True
                    else:
                        error_desc = data.get('description', 'Unknown error')
                        self.logger.error(f"Telegram API error: {error_desc}")
                        self.stats["messages_failed"] += 1
                        return False
                else:
                    self.logger.error(f"HTTP error sending message: {response.status}")
                    self.stats["messages_failed"] += 1
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            self.stats["messages_failed"] += 1
            return False
    
    def _rate_limit_check(self) -> bool:
        """
        Check if we can send a message without hitting rate limits.
        
        Returns:
            bool: True if message can be sent
        """
        try:
            now = datetime.now()
            
            # Reset counter if more than a minute has passed
            if (now - self.last_message_time).total_seconds() > 60:
                self.message_count_minute = 0
            
            # Check rate limit
            if self.message_count_minute >= self.max_messages_per_minute:
                return False
            
            self.message_count_minute += 1
            self.last_message_time = now
            
            return True
            
        except Exception as e:
            self.logger.error(f"Rate limit check error: {e}")
            return True  # Allow message on error
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
            
            self.logger.info("🤖 Telegram notifier cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Telegram cleanup: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get notification statistics."""
        uptime = (datetime.now() - self.stats["uptime_start"]).total_seconds()
        
        return {
            "enabled": self.config.enabled,
            "messages_sent": self.stats["messages_sent"],
            "messages_failed": self.stats["messages_failed"],
            "success_rate": (
                self.stats["messages_sent"] / 
                max(self.stats["messages_sent"] + self.stats["messages_failed"], 1)
            ) * 100,
            "last_message": self.stats["last_message_time"].isoformat() if self.stats["last_message_time"] else None,
            "uptime_seconds": uptime,
            "chat_id": self.config.chat_id if self.config.enabled else None
        }


# Helper function for easy integration
async def create_telegram_notifier() -> Optional[TelegramNotifier]:
    """
    Create and initialize Telegram notifier.
    
    Returns:
        TelegramNotifier or None if disabled/failed
    """
    try:
        notifier = TelegramNotifier()
        await notifier.initialize()
        return notifier if notifier.config.enabled else None
        
    except Exception as e:
        logger = logger_manager.get_logger("TelegramNotifier")
        logger.error(f"Failed to create Telegram notifier: {e}")
        return None