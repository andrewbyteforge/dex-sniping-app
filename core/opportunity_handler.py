#!/usr/bin/env python3
"""
Opportunity processing and analysis handler.
Handles all opportunity-related processing and dashboard integration.

File: core/opportunity_handler.py
Class: OpportunityHandler
Methods: handle_opportunity, analyze_opportunity, dashboard_integration
"""

import asyncio
import random
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal

from models.token import TradingOpportunity, TokenInfo, LiquidityInfo, ContractAnalysis, SocialMetrics, RiskLevel
from utils.logger import logger_manager


class OpportunityHandler:
    """
    Handles all opportunity processing and analysis.
    
    Features:
    - Process opportunities from all sources
    - Comprehensive analysis pipeline
    - Dashboard integration
    - Test opportunity generation
    """
    
    def __init__(self, trading_system) -> None:
        """
        Initialize opportunity handler.
        
        Args:
            trading_system: Reference to main trading system
        """
        self.trading_system = trading_system
        self.logger = logger_manager.get_logger("OpportunityHandler")

    async def handle_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Enhanced opportunity handler with robust dashboard integration and Telegram notifications.
        
        Args:
            opportunity: Trading opportunity from monitors
        """
        try:
            # Validate opportunity structure
            if not opportunity or not hasattr(opportunity, 'token'):
                self.logger.warning("Invalid opportunity received - skipping")
                return

            token_symbol = getattr(opportunity.token, 'symbol', 'UNKNOWN')
            token_address = getattr(opportunity.token, 'address', 'UNKNOWN')
            
            self.logger.info(f"🔍 Processing opportunity: {token_symbol} ({token_address[:10]}...)")
            
            # Ensure opportunity has required attributes
            if not hasattr(opportunity, 'metadata') or not opportunity.metadata:
                opportunity.metadata = {}
                
            if not hasattr(opportunity, 'chain') or not opportunity.chain:
                # Try to infer chain from metadata or set default
                opportunity.chain = opportunity.metadata.get('chain', 'ethereum')
            
            # Ensure opportunity has timestamp
            timestamp = self._ensure_timestamp(opportunity)
            
            # Ensure price field exists
            if not hasattr(opportunity.token, 'price'):
                opportunity.token.price = 1.0  # Default price
            
            # Update analysis statistics
            self.trading_system.analysis_stats["total_analyzed"] += 1
            self.trading_system.analysis_stats["opportunities_found"] += 1
            
            # Track by chain
            chain = opportunity.metadata.get('chain', 'unknown').lower()
            if chain in self.trading_system.opportunities_by_chain:
                self.trading_system.opportunities_by_chain[chain] += 1
            
            # Track signal source
            source = opportunity.metadata.get('source', 'blockchain_monitor')
            if source not in self.trading_system.signal_sources:
                self.trading_system.signal_sources[source] = 0
            self.trading_system.signal_sources[source] += 1
            
            # Perform comprehensive analysis
            enhanced_opportunity = await self._analyze_opportunity(opportunity)
            
            # Send Telegram notification for new opportunities
            await self.trading_system.telegram_manager.handle_new_opportunity(enhanced_opportunity)
            
            # Execute trading logic if enabled
            if self.trading_system.auto_trading_enabled and self.trading_system.trading_executor:
                try:
                    decision = await self.trading_system.trading_executor.assess_opportunity(enhanced_opportunity)
                    self.trading_system.execution_metrics["opportunities_assessed"] += 1
                    
                    decision_value = decision.value if hasattr(decision, 'value') else str(decision)
                    
                    if decision_value == "EXECUTE":
                        self.trading_system.execution_metrics["trades_approved"] += 1
                        self.logger.info(f"✅ Trade approved for {token_symbol}")
                    elif decision_value == "REJECT":
                        self.trading_system.execution_metrics["trades_rejected"] += 1
                        self.logger.debug(f"❌ Trade rejected for {token_symbol}")
                    
                except Exception as trading_error:
                    self.logger.error(f"Trading assessment failed for {token_symbol}: {trading_error}")
                    
                    # Send error notification
                    await self.trading_system.telegram_manager.handle_trading_error(
                        token_symbol, str(trading_error), token_address
                    )
            
            # Always add to dashboard, regardless of trading mode
            await self._add_to_dashboard_guaranteed(enhanced_opportunity)
            
            # Log successful processing
            self.logger.debug(f"✅ Successfully processed opportunity: {token_symbol}")
            
        except Exception as e:
            token_symbol = getattr(opportunity.token, 'symbol', 'UNKNOWN') if hasattr(opportunity, 'token') else 'UNKNOWN'
            self.logger.error(f"Error handling opportunity {token_symbol}: {e}")
            
            # Send error notification
            await self.trading_system.telegram_manager.handle_opportunity_error(token_symbol, str(e))
            
            import traceback
            self.logger.debug(f"Full traceback: {traceback.format_exc()}")

    async def handle_raydium_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Handle trading opportunities specifically from Raydium DEX.
        
        Args:
            opportunity: Trading opportunity from Raydium monitor
        """
        try:
            self.logger.info(f"🌊 Raydium opportunity detected: {opportunity.token.symbol}")
            self.logger.info(f"   💰 Liquidity: ${opportunity.liquidity.liquidity_usd:,.0f}")
            self.logger.info(f"   📊 Confidence: {opportunity.confidence_score:.3f}")
            self.logger.info(f"   🏦 Pool: {opportunity.metadata.get('pool_id', 'Unknown')[:8]}...")
            
            # Update statistics
            self.trading_system.analysis_stats["opportunities_found"] += 1
            
            # Enhanced analysis for Raydium-specific factors
            raydium_analysis = await self._analyze_raydium_opportunity(opportunity)
            
            # Merge Raydium-specific analysis
            enhanced_opportunity = self._enhance_opportunity_with_raydium_data(
                opportunity, 
                raydium_analysis
            )
            
            # Use the general opportunity handler with enhanced data
            await self.handle_opportunity(enhanced_opportunity)
            
        except Exception as e:
            self.logger.error(f"💥 Error handling Raydium opportunity: {e}")
            
            # Send error notification
            await self.trading_system.telegram_manager.handle_raydium_error(
                opportunity, str(e)
            )

    async def handle_telegram_signal_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Handle trading opportunities from Telegram signals.
        
        Args:
            opportunity: Trading opportunity converted from Telegram signal
        """
        try:
            token_symbol = opportunity.token.symbol
            channel = opportunity.metadata.get('channel', 'unknown')
            signal_type = opportunity.metadata.get('signal_type', 'unknown')
            confidence = opportunity.metadata.get('original_confidence', 0)
            
            self.logger.info(f"📡 Telegram signal opportunity: {signal_type.upper()} {token_symbol} "
                           f"from @{channel} (confidence: {confidence:.2f})")
            
            # Process through normal opportunity pipeline
            await self.handle_opportunity(opportunity)
            
            # Send notification about signal received
            await self.trading_system.telegram_manager.handle_telegram_signal_received(
                token_symbol, signal_type, channel, confidence, opportunity.metadata.get('chain', 'unknown')
            )
            
        except Exception as e:
            self.logger.error(f"Error handling Telegram signal opportunity: {e}")

    def _ensure_timestamp(self, opportunity: TradingOpportunity) -> datetime:
        """Ensure opportunity has timestamp."""
        timestamp = None
        for attr_name in ['timestamp', 'detected_at', 'created_at']:
            if hasattr(opportunity, attr_name):
                timestamp = getattr(opportunity, attr_name)
                break
        
        if not timestamp:
            timestamp = datetime.now()
            opportunity.timestamp = timestamp
            if hasattr(opportunity, 'detected_at'):
                opportunity.detected_at = timestamp
        
        return timestamp

    async def _analyze_opportunity(self, opportunity: TradingOpportunity) -> TradingOpportunity:
        """
        Perform comprehensive analysis on trading opportunity.
        
        Args:
            opportunity: Base opportunity to analyze
            
        Returns:
            TradingOpportunity: Enhanced opportunity with analysis results
        """
        try:
            enhanced_metadata = opportunity.metadata.copy()
            
            # Ensure opportunity has timestamp
            if not hasattr(opportunity, 'timestamp') or not opportunity.timestamp:
                opportunity.timestamp = datetime.now()
            
            # Contract security analysis
            if self.trading_system.analyzers.get('contract'):
                try:
                    contract_analysis = await self.trading_system.analyzers['contract'].analyze_contract(opportunity)
                    enhanced_metadata['contract_analysis'] = self._serialize_analysis(contract_analysis)
                except Exception as e:
                    self.logger.warning(f"Contract analysis failed: {e}")
                    enhanced_metadata['contract_analysis'] = {'error': str(e)}
            else:
                # Mock contract analysis for testing
                enhanced_metadata['contract_analysis'] = self._mock_contract_analysis()
            
            # Social sentiment analysis
            if self.trading_system.analyzers.get('social'):
                try:
                    social_metrics = await self.trading_system.analyzers['social'].analyze_social_metrics(opportunity)
                    enhanced_metadata['social_metrics'] = self._serialize_analysis(social_metrics)
                except Exception as e:
                    self.logger.warning(f"Social analysis failed: {e}")
                    enhanced_metadata['social_metrics'] = {'error': str(e)}
            else:
                # Mock social analysis for testing
                enhanced_metadata['social_metrics'] = self._mock_social_analysis()
            
            # Trading score and recommendation
            trading_score_data = await self._calculate_trading_score(opportunity)
            enhanced_metadata.update(trading_score_data)
            
            # Create enhanced opportunity
            enhanced_opportunity = TradingOpportunity(
                token=opportunity.token,
                liquidity=opportunity.liquidity,
                contract_analysis=getattr(opportunity, 'contract_analysis', None),
                social_metrics=getattr(opportunity, 'social_metrics', None),
                detected_at=opportunity.timestamp,
                metadata=enhanced_metadata
            )
            
            # Add chain as metadata
            enhanced_opportunity.metadata['chain'] = getattr(opportunity, 'chain', 'ethereum')
            
            return enhanced_opportunity
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive analysis: {e}")
            return opportunity

    async def _calculate_trading_score(self, opportunity: TradingOpportunity) -> Dict[str, Any]:
        """Calculate trading score and recommendation."""
        result = {}
        
        if self.trading_system.analyzers.get('trading_scorer'):
            try:
                trading_score_result = self.trading_system.analyzers['trading_scorer'].score_opportunity(opportunity)
                
                # Handle both sync and async results
                if hasattr(trading_score_result, '__await__'):
                    trading_score = await trading_score_result
                else:
                    trading_score = trading_score_result
                
                # Convert to standard format
                if isinstance(trading_score, (float, int)):
                    result['trading_score'] = {
                        'overall_score': float(trading_score),
                        'risk_score': 1.0 - float(trading_score),
                        'opportunity_score': float(trading_score)
                    }
                    
                    # Create recommendation
                    action, confidence = self._score_to_recommendation(trading_score)
                    result['recommendation'] = {
                        'action': action,
                        'confidence': confidence,
                        'reasoning': f"Score-based analysis suggests {action} with {confidence} confidence (score: {trading_score:.3f})"
                    }
                else:
                    result['trading_score'] = trading_score
                    recommendation = trading_score.get('recommendation', {}) if isinstance(trading_score, dict) else {}
                    if recommendation:
                        result['recommendation'] = recommendation
                
                # Update statistics
                action = result.get('recommendation', {}).get('action', 'HOLD')
                confidence = result.get('recommendation', {}).get('confidence', 'MEDIUM')
                
                if action in self.trading_system.analysis_stats["recommendations"]:
                    self.trading_system.analysis_stats["recommendations"][action] += 1
                
                if confidence == 'HIGH':
                    self.trading_system.analysis_stats["high_confidence"] += 1
                    
            except Exception as e:
                self.logger.warning(f"Trading score analysis failed: {e}")
                result['trading_score'] = {'error': str(e)}
        else:
            # Mock trading score for testing
            result.update(self._mock_trading_score())
        
        return result

    def _score_to_recommendation(self, score: float) -> tuple:
        """Convert score to action and confidence."""
        if score >= 0.7:
            return 'BUY', 'HIGH'
        elif score >= 0.5:
            return 'HOLD', 'MEDIUM'
        elif score >= 0.3:
            return 'HOLD', 'LOW'
        else:
            return 'AVOID', 'HIGH'

    def _serialize_analysis(self, analysis) -> Dict[str, Any]:
        """Serialize analysis object to dict."""
        if hasattr(analysis, '__dict__'):
            return analysis.__dict__
        return analysis

    def _mock_contract_analysis(self) -> Dict[str, Any]:
        """Mock contract analysis for testing."""
        return {
            'is_honeypot': False,
            'ownership_risk': 0.3,
            'liquidity_locked': True,
            'is_verified': True,
            'risk_score': 0.4
        }

    def _mock_social_analysis(self) -> Dict[str, Any]:
        """Mock social analysis for testing."""
        return {
            'sentiment': random.choice(['positive', 'neutral', 'negative']),
            'volume_score': random.uniform(0.2, 0.8),
            'community_quality': random.uniform(0.3, 0.9),
            'high_bot_activity': random.choice([True, False])
        }

    def _mock_trading_score(self) -> Dict[str, Any]:
        """Mock trading score for testing."""
        action = random.choice(['BUY', 'HOLD', 'SELL', 'AVOID'])
        confidence = random.choice(['HIGH', 'MEDIUM', 'LOW'])
        
        result = {
            'trading_score': {
                'overall_score': random.uniform(0.1, 0.9),
                'risk_score': random.uniform(0.2, 0.8),
                'opportunity_score': random.uniform(0.3, 0.9)
            },
            'recommendation': {
                'action': action,
                'confidence': confidence,
                'reasoning': f"Mock analysis suggests {action} with {confidence} confidence"
            }
        }
        
        # Update statistics
        if action in self.trading_system.analysis_stats["recommendations"]:
            self.trading_system.analysis_stats["recommendations"][action] += 1
        
        if confidence == 'HIGH':
            self.trading_system.analysis_stats["high_confidence"] += 1
        
        return result

    async def _analyze_raydium_opportunity(self, opportunity: TradingOpportunity) -> Dict[str, Any]:
        """Perform Raydium-specific analysis."""
        analysis = {
            'raydium_score': 0.0,
            'solana_network_load': 'normal',
            'pool_age_score': 0.0,
            'raydium_liquidity_quality': 'medium',
            'cross_dex_potential': False,
            'recommended_position_size': 0.0
        }
        
        try:
            # Analyze liquidity quality
            liquidity_usd = opportunity.liquidity.liquidity_usd
            if liquidity_usd >= 100000:
                analysis['raydium_liquidity_quality'] = 'high'
                analysis['raydium_score'] += 0.3
            elif liquidity_usd >= 50000:
                analysis['raydium_liquidity_quality'] = 'medium'
                analysis['raydium_score'] += 0.2
            else:
                analysis['raydium_liquidity_quality'] = 'low'
                analysis['raydium_score'] += 0.1
            
            # Check for cross-DEX arbitrage potential
            analysis['cross_dex_potential'] = liquidity_usd > 25000
            if analysis['cross_dex_potential']:
                analysis['raydium_score'] += 0.2
            
            # Calculate recommended position size
            base_position = min(0.02, opportunity.confidence_score * 0.03)
            raydium_multiplier = 1.0 + (analysis['raydium_score'] - 0.5)
            analysis['recommended_position_size'] = base_position * raydium_multiplier
            
        except Exception as e:
            self.logger.error(f"Error in Raydium analysis: {e}")
        
        return analysis

    def _enhance_opportunity_with_raydium_data(
        self, 
        opportunity: TradingOpportunity, 
        raydium_analysis: Dict[str, Any]
    ) -> TradingOpportunity:
        """Enhance opportunity with Raydium-specific data."""
        try:
            # Update confidence score
            raydium_boost = raydium_analysis.get('raydium_score', 0.0) * 0.2
            enhanced_confidence = min(1.0, opportunity.confidence_score + raydium_boost)
            
            # Update metadata
            enhanced_metadata = opportunity.metadata.copy()
            enhanced_metadata.update({
                'raydium_analysis': raydium_analysis,
                'enhanced_by': 'raydium_analyzer',
                'chain_optimized': 'solana',
                'dex_specific_score': raydium_analysis.get('raydium_score', 0.0)
            })
            
            # Create enhanced opportunity
            enhanced_opportunity = TradingOpportunity(
                token=opportunity.token,
                liquidity=opportunity.liquidity,
                contract_analysis=opportunity.contract_analysis,
                social_metrics=opportunity.social_metrics,
                detected_at=opportunity.detected_at,
                confidence_score=enhanced_confidence,
                metadata=enhanced_metadata
            )
            
            return enhanced_opportunity
            
        except Exception as e:
            self.logger.error(f"Error enhancing opportunity with Raydium data: {e}")
            return opportunity

    async def _add_to_dashboard_guaranteed(self, opportunity: TradingOpportunity) -> None:
        """Guaranteed dashboard update with comprehensive error handling."""
        try:
            # Skip if dashboard is disabled
            if self.trading_system.disable_dashboard:
                return
                
            # Try dashboard server add_opportunity method
            if hasattr(self.trading_system, 'dashboard_server') and self.trading_system.dashboard_server:
                try:
                    await self.trading_system.dashboard_server.add_opportunity(opportunity)
                    self.logger.debug(f"✅ Dashboard updated via server: {opportunity.token.symbol}")
                    return
                except Exception as server_error:
                    self.logger.warning(f"Dashboard server update failed: {server_error}")
            
            # Manual dashboard update as fallback
            if hasattr(self.trading_system, 'dashboard_server') and self.trading_system.dashboard_server:
                try:
                    await self._manual_dashboard_update(opportunity)
                    self.logger.debug(f"✅ Dashboard updated manually: {opportunity.token.symbol}")
                    return
                except Exception as manual_error:
                    self.logger.warning(f"Manual dashboard update failed: {manual_error}")
            
            # Log failure but don't break the system
            self.logger.warning(f"All dashboard update methods failed for {opportunity.token.symbol}")
            
        except Exception as e:
            # Final safety net
            self.logger.error(f"Critical dashboard update error: {e}")

    async def _manual_dashboard_update(self, opportunity: TradingOpportunity) -> None:
        """Manual dashboard update as fallback method."""
        try:
            # Extract data safely with defaults
            token_symbol = getattr(opportunity.token, 'symbol', 'UNKNOWN')
            token_address = getattr(opportunity.token, 'address', '')
            chain = opportunity.metadata.get('chain', 'ethereum')
            
            # Extract liquidity info safely
            liquidity_usd = 0.0
            if hasattr(opportunity, 'liquidity') and opportunity.liquidity:
                liquidity_usd = float(getattr(opportunity.liquidity, 'liquidity_usd', 0))
            
            # Create opportunity data structure
            opp_data = {
                "token_symbol": token_symbol,
                "token_address": token_address,
                "chain": chain.lower(),
                "risk_level": opportunity.metadata.get("risk_level", "unknown"),
                "recommendation": opportunity.metadata.get("recommendation", {}).get("action", "MONITOR"),
                "confidence": opportunity.metadata.get("recommendation", {}).get("confidence", "LOW"),
                "score": opportunity.metadata.get("trading_score", {}).get("overall_score", 0.0),
                "liquidity_usd": liquidity_usd,
                "detected_at": datetime.now().isoformat(),
                "age_minutes": 0
            }
            
            # Update dashboard stats manually
            if hasattr(self.trading_system.dashboard_server, 'stats'):
                self.trading_system.dashboard_server.stats["total_opportunities"] += 1
                
                if opp_data["confidence"] == "HIGH":
                    self.trading_system.dashboard_server.stats["high_confidence"] += 1
            
            # Add to opportunities queue manually
            if hasattr(self.trading_system.dashboard_server, 'opportunities_queue'):
                self.trading_system.dashboard_server.opportunities_queue.append(opportunity)
                
                # Keep queue size manageable
                if len(self.trading_system.dashboard_server.opportunities_queue) > 100:
                    self.trading_system.dashboard_server.opportunities_queue.pop(0)
            
            # Broadcast to WebSocket clients
            if hasattr(self.trading_system.dashboard_server, 'broadcast_message'):
                await self.trading_system.dashboard_server.broadcast_message({
                    "type": "new_opportunity",
                    "data": opp_data
                })
            
        except Exception as e:
            self.logger.error(f"Manual dashboard update failed: {e}")
            raise

    async def generate_test_opportunities(self) -> None:
        """Generate test opportunities for dashboard testing."""
        try:
            await asyncio.sleep(15)  # Wait for system to initialize
            
            self.logger.info("🧪 Generating test opportunities for dashboard verification...")
            
            test_tokens = [
                ("TESTMEME", "ethereum", 150000.0),
                ("MOCKCOIN", "solana", 75000.0), 
                ("BASETEST", "base", 200000.0)
            ]
            
            for i, (symbol, chain, liquidity) in enumerate(test_tokens):
                try:
                    await asyncio.sleep(10)  # Stagger opportunities
                    
                    test_opportunity = await self._create_test_opportunity(symbol, chain, liquidity)
                    
                    if test_opportunity:
                        await self.handle_opportunity(test_opportunity)
                        self.logger.info(f"🧪 Test opportunity {i+1}/3 processed: {symbol}")
                    
                except Exception as test_error:
                    self.logger.error(f"Test opportunity {i+1} failed: {test_error}")
            
            self.logger.info("🧪 Test opportunity generation completed")
            
        except Exception as e:
            self.logger.error(f"Test opportunity generation failed: {e}")

    async def _create_test_opportunity(self, symbol: str, chain: str, liquidity: float) -> Optional[TradingOpportunity]:
        """Create a test trading opportunity."""
        try:
            # Generate test address based on chain
            if chain == "solana":
                test_address = f"{symbol}{''.join(random.choices('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz', k=40))}"
            else:
                test_address = f"0x{''.join(random.choices('0123456789abcdef', k=40))}"
            
            # Create test token info
            if chain == "solana":
                class SolanaTokenInfo:
                    def __init__(self, address, symbol, name, decimals=9, total_supply=1000000000):
                        self.address = address
                        self.symbol = symbol
                        self.name = name
                        self.decimals = decimals
                        self.total_supply = total_supply
                        self.price = 1.0
                
                token_info = SolanaTokenInfo(
                    address=test_address,
                    symbol=symbol,
                    name=f"Test {symbol}",
                    decimals=9,
                    total_supply=1000000000
                )
            else:
                token_info = TokenInfo(
                    address=test_address,
                    symbol=symbol,
                    name=f"Test {symbol}",
                    decimals=18,
                    total_supply=1000000000
                )
            
            # Create test liquidity info  
            liquidity_info = LiquidityInfo(
                pair_address=test_address,
                dex_name=f"Test DEX ({chain})",
                token0=test_address,
                token1="0x0000000000000000000000000000000000000000" if chain != "solana" else "So11111111111111111111111111111111111111112",
                reserve0=float(liquidity / 2),
                reserve1=float(liquidity / 2),
                liquidity_usd=liquidity,
                created_at=datetime.now(),
                block_number=0
            )
            
            # Create test opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=None,
                social_metrics=None,
                detected_at=datetime.now(),
                confidence_score=random.uniform(0.3, 0.8),
                metadata={
                    'chain': chain,
                    'source': 'test_generator',
                    'is_test': True,
                    'recommendation': {
                        'action': random.choice(['BUY', 'MONITOR', 'HOLD']),
                        'confidence': random.choice(['LOW', 'MEDIUM', 'HIGH'])
                    },
                    'trading_score': {
                        'overall_score': random.uniform(0.2, 0.9),
                        'risk_score': random.uniform(0.1, 0.7)
                    }
                }
            )
            
            # Add chain information
            opportunity.chain = chain
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Failed to create test opportunity: {e}")
            return None