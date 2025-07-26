#!/usr/bin/env python3
"""
Integration for Telegram channel signals with main trading system.
Converts Telegram signals to TradingOpportunity objects.

File: integrations/telegram_signal_integration.py
Class: TelegramSignalIntegration
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal

from monitors.telegram_channel_monitor import TelegramChannelMonitor, TelegramSignal, SignalType
from models.token import TradingOpportunity, TokenInfo, LiquidityInfo, SocialMetrics
from utils.logger import logger_manager


class TelegramSignalIntegration:
    """
    Integrates Telegram channel signals with the main trading system.
    
    Features:
    - Convert Telegram signals to TradingOpportunity objects
    - Filter and validate signals
    - Merge with existing analysis pipeline
    - Track signal performance
    """
    
    def __init__(self) -> None:
        """Initialize Telegram signal integration."""
        self.logger = logger_manager.get_logger("TelegramSignalIntegration")
        
        # Initialize channel monitor
        self.channel_monitor = TelegramChannelMonitor()
        self.enabled = self.channel_monitor.enabled
        
        # Signal tracking
        self.signal_callbacks: List[callable] = []
        self.processed_signals: Dict[str, TelegramSignal] = {}
        
        # Statistics
        self.stats = {
            'signals_received': 0,
            'signals_processed': 0,
            'signals_converted': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'channels_active': 0
        }
        
        if self.enabled:
            # Add signal callback
            self.channel_monitor.add_signal_callback(self._handle_telegram_signal)
            self.logger.info("Telegram signal integration enabled")
        else:
            self.logger.warning("Telegram signal integration disabled - missing configuration")

    async def initialize(self) -> bool:
        """
        Initialize Telegram signal integration.
        
        Returns:
            Success status
        """
        try:
            if not self.enabled:
                return True  # Don't fail if disabled
            
            self.logger.info("Initializing Telegram signal integration...")
            
            # Initialize channel monitor
            success = await self.channel_monitor.initialize()
            if success:
                self.stats['channels_active'] = len(self.channel_monitor.monitored_channels)
                self.logger.info("✅ Telegram signal integration initialized")
                return True
            else:
                self.logger.error("❌ Failed to initialize Telegram channel monitor")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram signal integration: {e}")
            return False

    def add_opportunity_callback(self, callback: callable) -> None:
        """Add callback for converted trading opportunities."""
        self.signal_callbacks.append(callback)
        self.logger.info(f"Added opportunity callback: {callback.__name__}")

    async def start_monitoring(self) -> None:
        """Start monitoring Telegram channels."""
        try:
            if not self.enabled:
                self.logger.info("Telegram monitoring disabled")
                return
            
            self.logger.info("🎯 Starting Telegram channel monitoring...")
            await self.channel_monitor.start_monitoring()
            
        except Exception as e:
            self.logger.error(f"Error starting Telegram monitoring: {e}")

    async def _handle_telegram_signal(self, signal: TelegramSignal) -> None:
        """
        Handle incoming Telegram signal.
        
        Args:
            signal: Telegram signal to process
        """
        try:
            self.stats['signals_received'] += 1
            
            # Log signal
            self.logger.info(f"📡 Telegram signal: {signal.signal_type.value.upper()} {signal.token_symbol} "
                           f"from @{signal.channel_name} (confidence: {signal.confidence:.2f})")
            
            # Update signal type stats
            if signal.signal_type == SignalType.BUY:
                self.stats['buy_signals'] += 1
            elif signal.signal_type == SignalType.SELL:
                self.stats['sell_signals'] += 1
            
            # Convert to trading opportunity
            opportunity = await self._convert_signal_to_opportunity(signal)
            
            if opportunity:
                self.stats['signals_converted'] += 1
                
                # Store processed signal
                signal_key = f"{signal.channel_name}_{signal.token_symbol}_{signal.message_id}"
                self.processed_signals[signal_key] = signal
                
                # Send to main trading system
                for callback in self.signal_callbacks:
                    try:
                        await callback(opportunity)
                    except Exception as e:
                        self.logger.error(f"Opportunity callback failed: {e}")
            
            self.stats['signals_processed'] += 1
            
        except Exception as e:
            self.logger.error(f"Error handling Telegram signal: {e}")

    async def _convert_signal_to_opportunity(self, signal: TelegramSignal) -> Optional[TradingOpportunity]:
        """
        Convert Telegram signal to TradingOpportunity.
        
        Args:
            signal: Telegram signal to convert
            
        Returns:
            TradingOpportunity or None
        """
        try:
            # Create TokenInfo
            token_info = TokenInfo(
                address=signal.token_address or f"telegram_{signal.token_symbol.lower()}",
                symbol=signal.token_symbol,
                name=f"{signal.token_symbol} Token",
                decimals=18,  # Default
                total_supply=1000000000  # Default
            )
            
            # Create LiquidityInfo (estimated)
            liquidity_info = LiquidityInfo(
                pair_address=signal.token_address or f"pair_{signal.token_symbol.lower()}",
                dex_name=f"Telegram Signal ({signal.channel_name})",
                token0=signal.token_address or "",
                token1="0x0000000000000000000000000000000000000000",  # Unknown pair
                reserve0=50000.0,  # Estimated
                reserve1=50000.0,  # Estimated
                liquidity_usd=100000.0,  # Estimated
                created_at=signal.timestamp,
                block_number=0  # Unknown
            )
            
            # Create SocialMetrics based on channel
            social_metrics = SocialMetrics(
                twitter_followers=0,  # Unknown
                telegram_members=signal.channel_followers,
                social_score=signal.confidence,
                sentiment_score=self._calculate_sentiment_score(signal)
            )
            
            # Calculate confidence score (0-1 range)
            confidence_score = signal.confidence
            
            # Adjust confidence based on signal type and our trading mode
            if signal.signal_type == SignalType.SELL:
                confidence_score *= 0.8  # Reduce confidence for sell signals
            
            # Create metadata
            metadata = {
                'source': 'telegram_signal',
                'channel': signal.channel_name,
                'signal_type': signal.signal_type.value,
                'message_id': signal.message_id,
                'target_price': signal.target_price,
                'raw_message': signal.raw_message,
                'channel_followers': signal.channel_followers,
                'original_confidence': signal.confidence,
                'chain': self._detect_chain(signal),
                'recommendation': {
                    'action': signal.signal_type.value.upper() if signal.signal_type != SignalType.UNKNOWN else 'MONITOR',
                    'confidence': self._get_confidence_level(confidence_score),
                    'reasoning': f"Telegram signal from @{signal.channel_name} with {signal.confidence:.1%} confidence"
                },
                'trading_score': {
                    'overall_score': confidence_score * 100,
                    'social_score': signal.confidence * 100,
                    'telegram_source': True
                }
            }
            
            # Create TradingOpportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=None,  # Not available from Telegram
                social_metrics=social_metrics,
                detected_at=signal.timestamp,
                confidence_score=confidence_score,
                metadata=metadata
            )
            
            # Add chain attribute
            opportunity.chain = metadata['chain']
            
            self.logger.debug(f"Converted Telegram signal to opportunity: {signal.token_symbol}")
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Error converting signal to opportunity: {e}")
            return None

    def _calculate_sentiment_score(self, signal: TelegramSignal) -> float:
        """Calculate sentiment score from signal."""
        if signal.signal_type == SignalType.BUY:
            return 0.7  # Positive sentiment
        elif signal.signal_type == SignalType.SELL:
            return -0.3  # Negative sentiment
        else:
            return 0.0  # Neutral

    def _detect_chain(self, signal: TelegramSignal) -> str:
        """Detect blockchain from signal."""
        if signal.token_address:
            if signal.token_address.startswith('0x') and len(signal.token_address) == 42:
                return 'ethereum'  # Could be Ethereum, Base, BSC, etc.
            elif len(signal.token_address) >= 32:
                return 'solana'
        
        # Check message for chain mentions
        message_lower = signal.raw_message.lower()
        if 'solana' in message_lower or 'sol' in message_lower:
            return 'solana'
        elif 'base' in message_lower:
            return 'base'
        elif 'bsc' in message_lower or 'binance' in message_lower:
            return 'bsc'
        else:
            return 'ethereum'  # Default

    def _get_confidence_level(self, score: float) -> str:
        """Convert numeric confidence to level."""
        if score >= 0.8:
            return 'HIGH'
        elif score >= 0.6:
            return 'MEDIUM'
        else:
            return 'LOW'

    async def stop(self) -> None:
        """Stop Telegram monitoring."""
        try:
            if self.enabled and self.channel_monitor:
                await self.channel_monitor.stop()
            self.logger.info("Telegram signal integration stopped")
        except Exception as e:
            self.logger.error(f"Error stopping Telegram integration: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get integration statistics."""
        monitor_stats = {}
        if self.enabled and self.channel_monitor:
            monitor_stats = self.channel_monitor.get_statistics()
        
        return {
            'integration': self.stats,
            'monitor': monitor_stats,
            'enabled': self.enabled,
            'processed_signals_count': len(self.processed_signals)
        }


# Global integration instance
telegram_signal_integration = TelegramSignalIntegration()