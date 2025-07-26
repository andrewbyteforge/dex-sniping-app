#!/usr/bin/env python3
"""
Telegram channel monitoring system for trading signals.
Uses .env configuration for all credentials and settings.

File: monitors/telegram_channel_monitor.py
Class: TelegramChannelMonitor
Methods: monitor_channels, parse_signal, extract_tokens
"""

import asyncio
import re
import os
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

try:
    from telethon import TelegramClient, events
    from telethon.tl.types import Channel, Chat
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

from utils.logger import logger_manager
from models.token import TradingOpportunity


class SignalType(Enum):
    """Types of trading signals."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    UNKNOWN = "unknown"


@dataclass
class TelegramSignal:
    """Represents a trading signal from Telegram."""
    channel_name: str
    message_id: int
    timestamp: datetime
    signal_type: SignalType
    token_symbol: str
    token_address: Optional[str]
    target_price: Optional[float]
    confidence: float
    raw_message: str
    channel_followers: int


class TelegramChannelMonitor:
    """
    Monitors Telegram channels for trading signals using .env configuration.
    
    Features:
    - Load all settings from .env file
    - Monitor multiple public channels
    - Extract token mentions and contracts
    - Parse trading signals (BUY/SELL)
    - Filter spam and low-quality signals
    - Rate limiting and error handling
    """
    
    def __init__(self) -> None:
        """Initialize Telegram channel monitor from .env configuration."""
        self.logger = logger_manager.get_logger("TelegramChannelMonitor")
        
        # Check if Telethon is available
        if not TELETHON_AVAILABLE:
            self.logger.error("Telethon not installed. Run: pip install telethon")
            self.enabled = False
            return
        
        # Load configuration from environment
        self._load_configuration()
        
        # Telegram client setup
        self.client: Optional[TelegramClient] = None
        self.enabled = bool(self.api_id and self.api_hash and self.phone_number)
        
        # Monitoring state
        self.signal_callbacks: List[callable] = []
        self.recent_signals: Dict[str, datetime] = {}
        
        # Signal processing configuration
        self._setup_signal_processing()
        
        if self.enabled:
            self.logger.info(f"Telegram channel monitor configured for {len(self.monitored_channels)} channels")
        else:
            self.logger.warning("Telegram channel monitor disabled - missing credentials")

    def _load_configuration(self) -> None:
        """Load configuration from environment variables."""
        try:
            # API credentials
            self.api_id = os.getenv('TELEGRAM_API_ID')
            self.api_hash = os.getenv('TELEGRAM_API_HASH')
            self.phone_number = os.getenv('TELEGRAM_PHONE_NUMBER', '+447764423496')
            
            # Channels to monitor
            channels_str = os.getenv('TELEGRAM_CHANNELS', 'crypto_signals,defi_gems')
            self.monitored_channels = set(
                channel.strip() for channel in channels_str.split(',') if channel.strip()
            )
            
            # Signal filtering
            self.min_confidence = float(os.getenv('TELEGRAM_MIN_CONFIDENCE', '0.6'))
            self.min_followers = int(os.getenv('TELEGRAM_MIN_FOLLOWERS', '1000'))
            
            # Rate limiting
            self.signal_cooldown = int(os.getenv('TELEGRAM_SIGNAL_COOLDOWN', '30'))
            
            # Rate limiting per channel
            self.last_message_time: Dict[str, datetime] = {}
            
            self.logger.info(f"Loaded Telegram config: {len(self.monitored_channels)} channels, "
                           f"min confidence: {self.min_confidence}")
            
        except Exception as e:
            self.logger.error(f"Failed to load Telegram configuration: {e}")
            self.enabled = False

    def _setup_signal_processing(self) -> None:
        """Setup signal processing patterns and filters."""
        # Spam filter keywords
        self.spam_filter_keywords = {
            'scam', 'pump', 'dump', 'rug', 'guaranteed', 'moonshot',
            'easy money', '100x', '1000x', 'get rich', 'lambo',
            'diamond hands', 'hodl', 'to the moon', 'rocket'
        }
        
        # Pattern matching for tokens
        self.token_patterns = [
            r'\$([A-Z]{2,10})',  # $TOKEN format
            r'\b([A-Z]{2,10})(?:\s*(?:token|coin|gem))\b',  # TOKEN token/coin/gem
            r'0x[a-fA-F0-9]{40}',  # Ethereum contract address
            r'[1-9A-HJ-NP-Za-km-z]{32,44}',  # Solana address pattern
        ]
        
        # Signal classification patterns
        self.signal_patterns = {
            SignalType.BUY: [
                r'\b(?:buy|long|bullish|moon|rocket|gem|entry|enter|accumulate)\b',
                r'\b(?:call|signal|alert|buy zone|support)\b',
                r'🚀|📈|💎|🔥|⬆️|📢|🎯|✅|💚|🟢'
            ],
            SignalType.SELL: [
                r'\b(?:sell|short|bearish|dump|exit|close)\b',
                r'\b(?:take profit|tp|stop loss|sl|resistance)\b',
                r'📉|⬇️|❌|🔻|🔴|💀|⛔|🚨'
            ]
        }

    async def initialize(self) -> bool:
        """
        Initialize Telegram client and authenticate.
        
        Returns:
            Success status
        """
        try:
            if not self.enabled:
                self.logger.warning("Telegram channel monitor disabled")
                return False
            
            self.logger.info("Initializing Telegram channel monitor...")
            
            # Create session file path
            session_path = os.path.join(os.getcwd(), 'telegram_trading_session')
            
            # Create Telegram client
            self.client = TelegramClient(
                session_path,
                int(self.api_id),
                self.api_hash
            )
            
            # Connect and authenticate
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                self.logger.warning("Telegram authentication required")
                self.logger.info("Starting authentication process...")
                
                # Request code
                await self.client.send_code_request(self.phone_number)
                
                # In production, you'd handle this more gracefully
                code = input("Enter the verification code from Telegram: ")
                await self.client.sign_in(self.phone_number, code)
            
            # Get user info
            me = await self.client.get_me()
            self.logger.info(f"✅ Authenticated as: {me.first_name} ({me.username})")
            
            # Validate channels
            await self._validate_channels()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram monitor: {e}")
            return False

    async def _validate_channels(self) -> None:
        """Validate access to configured channels."""
        valid_channels = set()
        
        for channel in self.monitored_channels:
            try:
                entity = await self.client.get_entity(channel)
                follower_count = getattr(entity, 'participants_count', 0)
                
                if follower_count >= self.min_followers:
                    valid_channels.add(channel)
                    self.logger.info(f"✅ Channel: {entity.title} (@{channel}) - {follower_count:,} members")
                else:
                    self.logger.warning(f"⚠️ Channel {channel} has only {follower_count} members (min: {self.min_followers})")
                    
            except Exception as e:
                self.logger.error(f"❌ Cannot access channel {channel}: {e}")
        
        self.monitored_channels = valid_channels
        self.logger.info(f"Validated {len(valid_channels)} channels for monitoring")

    def add_signal_callback(self, callback: callable) -> None:
        """Add callback for signal notifications."""
        self.signal_callbacks.append(callback)
        self.logger.info(f"Added signal callback: {callback.__name__}")

    async def start_monitoring(self) -> None:
        """Start monitoring configured channels."""
        try:
            if not self.client or not self.monitored_channels:
                self.logger.error("Cannot start monitoring - client not initialized or no valid channels")
                return
            
            self.logger.info(f"🎯 Starting monitoring of {len(self.monitored_channels)} channels...")
            
            # Set up event handler for new messages
            @self.client.on(events.NewMessage)
            async def handle_new_message(event):
                await self._process_message(event)
            
            # Log channel details
            for channel in self.monitored_channels:
                try:
                    entity = await self.client.get_entity(channel)
                    self.logger.info(f"   📺 {entity.title} (@{channel})")
                except:
                    pass
            
            # Keep running
            self.logger.info("✅ Telegram channel monitoring active")
            await self.client.run_until_disconnected()
            
        except Exception as e:
            self.logger.error(f"Error in channel monitoring: {e}")

    async def _process_message(self, event) -> None:
        """
        Process new message for trading signals.
        
        Args:
            event: Telegram message event
        """
        try:
            # Get channel info
            chat = await event.get_chat()
            if not isinstance(chat, (Channel, Chat)):
                return
            
            channel_name = getattr(chat, 'username', 'unknown')
            if channel_name not in self.monitored_channels:
                return
            
            # Rate limiting per channel
            if self._is_rate_limited(channel_name):
                return
            
            message_text = event.message.message
            if not message_text or len(message_text) < 10:
                return
            
            # Parse signal
            signal = await self._parse_signal(
                channel_name=channel_name,
                message_id=event.message.id,
                message_text=message_text,
                chat=chat
            )
            
            if signal and self._is_valid_signal(signal):
                # Update rate limiting
                self.last_message_time[channel_name] = datetime.now()
                
                # Log signal
                self.logger.info(f"📡 Signal: {signal.signal_type.value.upper()} {signal.token_symbol} "
                               f"from @{channel_name} (confidence: {signal.confidence:.2f})")
                
                # Notify callbacks
                for callback in self.signal_callbacks:
                    try:
                        await callback(signal)
                    except Exception as e:
                        self.logger.error(f"Signal callback failed: {e}")
                        
        except Exception as e:
            self.logger.debug(f"Error processing message: {e}")

    async def _parse_signal(
        self,
        channel_name: str,
        message_id: int,
        message_text: str,
        chat
    ) -> Optional[TelegramSignal]:
        """
        Parse message for trading signals.
        
        Args:
            channel_name: Channel username
            message_id: Message ID
            message_text: Message content
            chat: Chat object
            
        Returns:
            Parsed signal or None
        """
        try:
            # Extract tokens
            tokens = self._extract_tokens(message_text)
            if not tokens:
                return None
            
            # Determine signal type
            signal_type = self._classify_signal(message_text)
            if signal_type == SignalType.UNKNOWN:
                return None
            
            # Extract contract address
            contract_match = re.search(r'0x[a-fA-F0-9]{40}', message_text)
            solana_match = re.search(r'[1-9A-HJ-NP-Za-km-z]{32,44}', message_text)
            
            token_address = None
            if contract_match:
                token_address = contract_match.group(0)
            elif solana_match:
                token_address = solana_match.group(0)
            
            # Extract target price
            price_patterns = [
                r'\$([0-9]+\.?[0-9]*)',
                r'(\d+\.?\d*)\s*(?:usd|dollars?)',
                r'target:?\s*\$?([0-9]+\.?[0-9]*)'
            ]
            
            target_price = None
            for pattern in price_patterns:
                price_match = re.search(pattern, message_text, re.IGNORECASE)
                if price_match:
                    try:
                        target_price = float(price_match.group(1))
                        break
                    except:
                        continue
            
            # Calculate confidence
            confidence = self._calculate_confidence(message_text, chat, channel_name)
            
            # Get channel follower count
            follower_count = getattr(chat, 'participants_count', 0)
            
            return TelegramSignal(
                channel_name=channel_name,
                message_id=message_id,
                timestamp=datetime.now(),
                signal_type=signal_type,
                token_symbol=tokens[0],  # Use first token found
                token_address=token_address,
                target_price=target_price,
                confidence=confidence,
                raw_message=message_text[:200],  # Truncate for storage
                channel_followers=follower_count
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing signal: {e}")
            return None

    def _extract_tokens(self, text: str) -> List[str]:
        """Extract token symbols from text."""
        tokens = []
        text_upper = text.upper()
        
        for pattern in self.token_patterns:
            matches = re.findall(pattern, text_upper)
            for match in matches:
                if isinstance(match, tuple):
                    tokens.extend(match)
                else:
                    tokens.append(match)
        
        # Filter valid tokens
        valid_tokens = []
        for token in tokens:
            # Skip contract addresses
            if token.startswith('0x') or len(token) > 20:
                continue
            # Valid token symbols: 2-10 chars, mostly alphabetic
            if 2 <= len(token) <= 10 and token.replace('$', '').isalpha():
                clean_token = token.replace('$', '')
                if clean_token not in ['USD', 'ETH', 'BTC', 'BNB']:  # Skip common pairs
                    valid_tokens.append(clean_token)
        
        return list(set(valid_tokens))  # Remove duplicates

    def _classify_signal(self, text: str) -> SignalType:
        """Classify message as BUY/SELL signal."""
        text_lower = text.lower()
        
        buy_score = 0
        sell_score = 0
        
        # Check BUY patterns
        for pattern in self.signal_patterns[SignalType.BUY]:
            matches = len(re.findall(pattern, text_lower))
            buy_score += matches
        
        # Check SELL patterns
        for pattern in self.signal_patterns[SignalType.SELL]:
            matches = len(re.findall(pattern, text_lower))
            sell_score += matches
        
        if buy_score > sell_score and buy_score > 0:
            return SignalType.BUY
        elif sell_score > buy_score and sell_score > 0:
            return SignalType.SELL
        else:
            return SignalType.UNKNOWN

    def _calculate_confidence(self, text: str, chat, channel_name: str) -> float:
        """Calculate signal confidence score."""
        confidence = 0.3  # Base confidence
        
        # Channel credibility (follower count)
        follower_count = getattr(chat, 'participants_count', 0)
        if follower_count > 50000:
            confidence += 0.3
        elif follower_count > 10000:
            confidence += 0.2
        elif follower_count > 1000:
            confidence += 0.1
        
        # Message quality indicators
        if re.search(r'0x[a-fA-F0-9]{40}', text):  # Has Ethereum contract
            confidence += 0.2
        elif re.search(r'[1-9A-HJ-NP-Za-km-z]{32,44}', text):  # Has Solana address
            confidence += 0.2
        
        if re.search(r'\$[0-9]+\.?[0-9]*', text):  # Has price target
            confidence += 0.1
        
        if re.search(r'\b(?:dyor|research|analysis)\b', text.lower()):  # Encourages research
            confidence += 0.1
        
        # Channel-specific adjustments
        if 'official' in channel_name.lower():
            confidence += 0.1
        
        # Spam detection (reduces confidence)
        text_lower = text.lower()
        spam_score = sum(1 for keyword in self.spam_filter_keywords if keyword in text_lower)
        confidence -= spam_score * 0.15
        
        # Message length (very short or very long messages are less reliable)
        if len(text) < 50:
            confidence -= 0.1
        elif len(text) > 1000:
            confidence -= 0.1
        
        return max(0.0, min(1.0, confidence))  # Clamp to 0-1

    def _is_valid_signal(self, signal: TelegramSignal) -> bool:
        """Check if signal meets quality thresholds."""
        # Confidence threshold
        if signal.confidence < self.min_confidence:
            return False
        
        # Valid token symbol
        if not signal.token_symbol or len(signal.token_symbol) < 2:
            return False
        
        # Clear signal type
        if signal.signal_type == SignalType.UNKNOWN:
            return False
        
        # Channel size threshold
        if signal.channel_followers < self.min_followers:
            return False
        
        # Check for excessive spam patterns
        spam_count = sum(1 for keyword in self.spam_filter_keywords 
                        if keyword in signal.raw_message.lower())
        if spam_count >= 3:
            return False
        
        return True

    def _is_rate_limited(self, channel_name: str) -> bool:
        """Check if channel is rate limited."""
        if channel_name not in self.last_message_time:
            return False
        
        time_since_last = (datetime.now() - self.last_message_time[channel_name]).total_seconds()
        return time_since_last < self.signal_cooldown

    async def stop(self) -> None:
        """Stop monitoring and cleanup."""
        try:
            if self.client:
                await self.client.disconnect()
            self.logger.info("Telegram channel monitoring stopped")
        except Exception as e:
            self.logger.error(f"Error stopping monitor: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            'enabled': self.enabled,
            'channels_monitored': len(self.monitored_channels),
            'channels': list(self.monitored_channels),
            'min_confidence': self.min_confidence,
            'min_followers': self.min_followers,
            'signal_cooldown': self.signal_cooldown,
            'callbacks_registered': len(self.signal_callbacks)
        }