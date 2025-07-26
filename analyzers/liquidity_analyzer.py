#!/usr/bin/env python3
"""
Liquidity Analyzer - Analyzes pool health, liquidity stability, and trading metrics.

File: analyzers/liquidity_analyzer.py
Purpose: Comprehensive analysis of DEX pool liquidity and health metrics
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from utils.logger import logger_manager


class PoolHealthStatus(Enum):
    """Pool health status levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class LiquidityStability(Enum):
    """Liquidity stability levels."""
    VERY_STABLE = "very_stable"
    STABLE = "stable"
    MODERATE = "moderate"
    VOLATILE = "volatile"
    HIGHLY_VOLATILE = "highly_volatile"


@dataclass
class LiquidityMetrics:
    """Comprehensive liquidity metrics for a pool."""
    
    # Basic metrics
    total_liquidity_usd: float
    volume_24h_usd: float
    volume_to_liquidity_ratio: float
    
    # Trading metrics
    trade_count_24h: int
    unique_traders_24h: int
    average_trade_size_usd: float
    
    # Price metrics
    price_impact_1k: float  # Price impact for $1K trade
    price_impact_10k: float  # Price impact for $10K trade
    price_volatility_24h: float
    
    # Liquidity health
    liquidity_depth_score: float  # 0-1 score
    bid_ask_spread: float
    slippage_tolerance: float
    
    # Stability metrics
    liquidity_stability: LiquidityStability
    volume_consistency_score: float  # 0-1 score
    trader_retention_rate: float
    
    # Pool age and maturity
    pool_age_hours: float
    maturity_score: float  # 0-1 score based on age and activity
    
    # Risk indicators
    large_holder_concentration: float  # % held by top 10 holders
    recent_large_exits: bool
    suspicious_trading_patterns: bool
    
    # Overall health
    overall_health_status: PoolHealthStatus
    health_score: float  # 0-1 composite score
    
    # Timestamps
    calculated_at: datetime
    data_window_hours: float = 24.0


@dataclass
class WhaleActivity:
    """Whale activity analysis for a pool."""
    
    large_entries_24h: List[Dict[str, Any]]
    large_exits_24h: List[Dict[str, Any]]
    net_whale_flow_usd: float
    whale_concentration_risk: float  # 0-1 score
    
    # Whale behavior patterns
    coordinated_activity: bool
    wash_trading_suspected: bool
    market_maker_presence: bool
    
    # Impact analysis
    whale_impact_on_price: float
    liquidity_at_risk: float  # Amount that could exit quickly


class LiquidityAnalyzer:
    """
    Comprehensive liquidity analysis for DEX pools.
    Analyzes pool health, stability, and trading patterns.
    """
    
    def __init__(self) -> None:
        """Initialize the liquidity analyzer."""
        self.logger = logger_manager.get_logger("LiquidityAnalyzer")
        
        # Analysis thresholds
        self.thresholds = {
            'min_liquidity_healthy': 10000,  # $10K minimum for healthy pool
            'excellent_liquidity': 100000,   # $100K+ for excellent rating
            'min_daily_volume': 1000,        # $1K minimum daily volume
            'healthy_volume_ratio': 0.1,     # 10% volume/liquidity ratio
            'max_price_impact_1k': 0.02,     # 2% max price impact for $1K
            'max_price_impact_10k': 0.05,    # 5% max price impact for $10K
            'min_traders_24h': 5,            # Minimum unique traders
            'whale_threshold_usd': 10000,    # $10K+ is whale trade
            'large_trade_threshold': 0.05,   # 5% of liquidity is large trade
            'max_holder_concentration': 0.3, # 30% max concentration
            'min_pool_age_hours': 1,         # 1 hour minimum age
            'mature_pool_age_hours': 168     # 1 week = mature pool
        }
        
        # Scoring weights
        self.weights = {
            'liquidity_amount': 0.25,
            'trading_activity': 0.20,
            'price_stability': 0.20,
            'trader_diversity': 0.15,
            'pool_maturity': 0.10,
            'whale_risk': 0.10
        }

    async def analyze_pool_liquidity(
        self, 
        pool_data: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> LiquidityMetrics:
        """
        Perform comprehensive liquidity analysis on a pool.
        
        Args:
            pool_data: Current pool data from DEX API
            historical_data: Historical data points for trend analysis
            
        Returns:
            LiquidityMetrics object with comprehensive analysis
        """
        try:
            self.logger.debug(f"Analyzing liquidity for pool {pool_data.get('id', 'unknown')}")
            
            # Extract basic metrics
            liquidity_usd = float(pool_data.get('liquidity', {}).get('usd', 0))
            volume_24h = float(pool_data.get('volume24h', 0))
            
            # Calculate core ratios
            volume_to_liquidity = volume_24h / liquidity_usd if liquidity_usd > 0 else 0
            
            # Analyze trading activity
            trading_metrics = await self._analyze_trading_activity(pool_data)
            
            # Analyze price metrics
            price_metrics = await self._analyze_price_metrics(pool_data, historical_data)
            
            # Analyze liquidity health
            health_metrics = await self._analyze_liquidity_health(pool_data, historical_data)
            
            # Analyze stability
            stability_metrics = await self._analyze_stability(pool_data, historical_data)
            
            # Analyze pool maturity
            maturity_metrics = await self._analyze_pool_maturity(pool_data)
            
            # Analyze risk indicators
            risk_metrics = await self._analyze_risk_indicators(pool_data)
            
            # Calculate overall health score
            health_score = await self._calculate_health_score({
                'liquidity_usd': liquidity_usd,
                'volume_24h': volume_24h,
                'volume_ratio': volume_to_liquidity,
                **trading_metrics,
                **price_metrics,
                **health_metrics,
                **stability_metrics,
                **maturity_metrics,
                **risk_metrics
            })
            
            # Determine health status
            health_status = self._determine_health_status(health_score)
            
            # Create metrics object
            metrics = LiquidityMetrics(
                total_liquidity_usd=liquidity_usd,
                volume_24h_usd=volume_24h,
                volume_to_liquidity_ratio=volume_to_liquidity,
                trade_count_24h=trading_metrics['trade_count'],
                unique_traders_24h=trading_metrics['unique_traders'],
                average_trade_size_usd=trading_metrics['avg_trade_size'],
                price_impact_1k=price_metrics['price_impact_1k'],
                price_impact_10k=price_metrics['price_impact_10k'],
                price_volatility_24h=price_metrics['volatility_24h'],
                liquidity_depth_score=health_metrics['depth_score'],
                bid_ask_spread=health_metrics['bid_ask_spread'],
                slippage_tolerance=health_metrics['slippage_tolerance'],
                liquidity_stability=stability_metrics['stability_level'],
                volume_consistency_score=stability_metrics['volume_consistency'],
                trader_retention_rate=stability_metrics['trader_retention'],
                pool_age_hours=maturity_metrics['age_hours'],
                maturity_score=maturity_metrics['maturity_score'],
                large_holder_concentration=risk_metrics['holder_concentration'],
                recent_large_exits=risk_metrics['recent_large_exits'],
                suspicious_trading_patterns=risk_metrics['suspicious_patterns'],
                overall_health_status=health_status,
                health_score=health_score,
                calculated_at=datetime.now()
            )
            
            self.logger.debug(f"Liquidity analysis complete: {health_status.value} ({health_score:.3f})")
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error analyzing pool liquidity: {e}")
            raise

    async def _analyze_trading_activity(self, pool_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trading activity metrics."""
        try:
            # Extract trading data
            volume_24h = float(pool_data.get('volume24h', 0))
            trade_data = pool_data.get('trade24h', {})
            
            trade_count = trade_data.get('count', 0) if isinstance(trade_data, dict) else 0
            unique_traders = trade_data.get('uniqueTraders', 0) if isinstance(trade_data, dict) else max(1, trade_count // 3)
            
            # Calculate average trade size
            avg_trade_size = volume_24h / trade_count if trade_count > 0 else 0
            
            return {
                'trade_count': trade_count,
                'unique_traders': unique_traders,
                'avg_trade_size': avg_trade_size,
                'trading_activity_score': min(1.0, trade_count / 100)  # Normalize to 0-1
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing trading activity: {e}")
            return {
                'trade_count': 0,
                'unique_traders': 0,
                'avg_trade_size': 0,
                'trading_activity_score': 0
            }

    async def _analyze_price_metrics(
        self, 
        pool_data: Dict[str, Any], 
        historical_data: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Analyze price-related metrics."""
        try:
            # Basic price impact estimation (simplified)
            liquidity_usd = float(pool_data.get('liquidity', {}).get('usd', 0))
            
            # Estimate price impact (rough calculation)
            price_impact_1k = min(0.1, 1000 / liquidity_usd) if liquidity_usd > 0 else 0.1
            price_impact_10k = min(0.2, 10000 / liquidity_usd) if liquidity_usd > 0 else 0.2
            
            # Calculate volatility from historical data if available
            volatility_24h = 0.0
            if historical_data and len(historical_data) > 1:
                prices = [float(point.get('price', 0)) for point in historical_data]
                if len(prices) > 1:
                    price_changes = []
                    for i in range(1, len(prices)):
                        if prices[i-1] > 0:
                            change = abs(prices[i] - prices[i-1]) / prices[i-1]
                            price_changes.append(change)
                    volatility_24h = sum(price_changes) / len(price_changes) if price_changes else 0
            
            return {
                'price_impact_1k': price_impact_1k,
                'price_impact_10k': price_impact_10k,
                'volatility_24h': volatility_24h,
                'price_stability_score': max(0, 1 - volatility_24h * 2)  # Higher volatility = lower score
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing price metrics: {e}")
            return {
                'price_impact_1k': 0.1,
                'price_impact_10k': 0.2,
                'volatility_24h': 0.0,
                'price_stability_score': 0.5
            }

    async def _analyze_liquidity_health(
        self, 
        pool_data: Dict[str, Any], 
        historical_data: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Analyze liquidity health indicators."""
        try:
            liquidity_usd = float(pool_data.get('liquidity', {}).get('usd', 0))
            
            # Calculate depth score based on liquidity amount
            depth_score = min(1.0, liquidity_usd / self.thresholds['excellent_liquidity'])
            
            # Estimate bid-ask spread (simplified)
            bid_ask_spread = max(0.001, 1 / liquidity_usd * 1000) if liquidity_usd > 0 else 0.01
            
            # Estimate slippage tolerance
            slippage_tolerance = min(0.05, 5000 / liquidity_usd) if liquidity_usd > 0 else 0.05
            
            return {
                'depth_score': depth_score,
                'bid_ask_spread': bid_ask_spread,
                'slippage_tolerance': slippage_tolerance,
                'liquidity_health_score': depth_score
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing liquidity health: {e}")
            return {
                'depth_score': 0.1,
                'bid_ask_spread': 0.01,
                'slippage_tolerance': 0.05,
                'liquidity_health_score': 0.1
            }

    async def _analyze_stability(
        self, 
        pool_data: Dict[str, Any], 
        historical_data: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Analyze liquidity stability metrics."""
        try:
            # Determine stability level based on volume consistency
            volume_24h = float(pool_data.get('volume24h', 0))
            
            # Default stability analysis
            stability_level = LiquidityStability.MODERATE
            volume_consistency = 0.5
            trader_retention = 0.5
            
            # If historical data is available, calculate better metrics
            if historical_data and len(historical_data) > 5:
                volumes = [float(point.get('volume24h', 0)) for point in historical_data[-7:]]
                if volumes:
                    avg_volume = sum(volumes) / len(volumes)
                    volume_variance = sum((v - avg_volume) ** 2 for v in volumes) / len(volumes)
                    volume_std = volume_variance ** 0.5
                    
                    # Calculate consistency (lower variance = higher consistency)
                    if avg_volume > 0:
                        coefficient_of_variation = volume_std / avg_volume
                        volume_consistency = max(0, 1 - coefficient_of_variation)
                    
                    # Determine stability level
                    if coefficient_of_variation < 0.2:
                        stability_level = LiquidityStability.VERY_STABLE
                    elif coefficient_of_variation < 0.4:
                        stability_level = LiquidityStability.STABLE
                    elif coefficient_of_variation < 0.8:
                        stability_level = LiquidityStability.MODERATE
                    elif coefficient_of_variation < 1.5:
                        stability_level = LiquidityStability.VOLATILE
                    else:
                        stability_level = LiquidityStability.HIGHLY_VOLATILE
            
            return {
                'stability_level': stability_level,
                'volume_consistency': volume_consistency,
                'trader_retention': trader_retention,
                'stability_score': volume_consistency
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing stability: {e}")
            return {
                'stability_level': LiquidityStability.MODERATE,
                'volume_consistency': 0.5,
                'trader_retention': 0.5,
                'stability_score': 0.5
            }

    async def _analyze_pool_maturity(self, pool_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze pool maturity metrics."""
        try:
            # Try to get pool creation time (this depends on the API structure)
            created_at = pool_data.get('createdAt') or pool_data.get('created_at')
            
            if created_at:
                if isinstance(created_at, str):
                    from datetime import datetime
                    creation_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    creation_time = created_at
                
                age_hours = (datetime.now() - creation_time).total_seconds() / 3600
            else:
                # Estimate age based on liquidity and volume (rough heuristic)
                liquidity_usd = float(pool_data.get('liquidity', {}).get('usd', 0))
                volume_24h = float(pool_data.get('volume24h', 0))
                
                if liquidity_usd > 100000 and volume_24h > 50000:
                    age_hours = 72  # Probably a few days old
                elif liquidity_usd > 10000:
                    age_hours = 24  # Probably at least a day old
                else:
                    age_hours = 6   # Probably new
            
            # Calculate maturity score
            maturity_score = min(1.0, age_hours / self.thresholds['mature_pool_age_hours'])
            
            return {
                'age_hours': age_hours,
                'maturity_score': maturity_score,
                'is_mature': age_hours >= self.thresholds['mature_pool_age_hours']
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing pool maturity: {e}")
            return {
                'age_hours': 12.0,
                'maturity_score': 0.1,
                'is_mature': False
            }

    async def _analyze_risk_indicators(self, pool_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze risk indicators."""
        try:
            # This is simplified - in a full implementation, this would analyze:
            # - Token holder distribution
            # - Recent large transactions
            # - Suspicious trading patterns
            
            # Default conservative estimates
            holder_concentration = 0.2  # Assume 20% concentration
            recent_large_exits = False
            suspicious_patterns = False
            
            # Check for potential red flags in available data
            volume_24h = float(pool_data.get('volume24h', 0))
            liquidity_usd = float(pool_data.get('liquidity', {}).get('usd', 0))
            
            # High volume relative to liquidity might indicate manipulation
            if liquidity_usd > 0:
                volume_ratio = volume_24h / liquidity_usd
                if volume_ratio > 5:  # 500%+ volume/liquidity ratio
                    suspicious_patterns = True
            
            return {
                'holder_concentration': holder_concentration,
                'recent_large_exits': recent_large_exits,
                'suspicious_patterns': suspicious_patterns,
                'risk_score': holder_concentration + (0.3 if suspicious_patterns else 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing risk indicators: {e}")
            return {
                'holder_concentration': 0.3,
                'recent_large_exits': False,
                'suspicious_patterns': False,
                'risk_score': 0.3
            }

    async def _calculate_health_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall health score using weighted metrics."""
        try:
            # Liquidity amount score (0-1)
            liquidity_score = min(1.0, metrics['liquidity_usd'] / self.thresholds['excellent_liquidity'])
            
            # Trading activity score (0-1) 
            activity_score = metrics.get('trading_activity_score', 0)
            
            # Price stability score (0-1)
            stability_score = metrics.get('price_stability_score', 0)
            
            # Trader diversity score (0-1)
            min_traders = self.thresholds['min_traders_24h']
            diversity_score = min(1.0, metrics.get('unique_traders', 0) / (min_traders * 5))
            
            # Pool maturity score (0-1)
            maturity_score = metrics.get('maturity_score', 0)
            
            # Whale risk score (0-1, inverted - lower risk = higher score)
            whale_risk_score = 1 - min(1.0, metrics.get('risk_score', 0))
            
            # Calculate weighted health score
            health_score = (
                liquidity_score * self.weights['liquidity_amount'] +
                activity_score * self.weights['trading_activity'] +
                stability_score * self.weights['price_stability'] +
                diversity_score * self.weights['trader_diversity'] +
                maturity_score * self.weights['pool_maturity'] +
                whale_risk_score * self.weights['whale_risk']
            )
            
            return min(1.0, max(0.0, health_score))
            
        except Exception as e:
            self.logger.error(f"Error calculating health score: {e}")
            return 0.5

    def _determine_health_status(self, health_score: float) -> PoolHealthStatus:
        """Determine health status from score."""
        if health_score >= 0.8:
            return PoolHealthStatus.EXCELLENT
        elif health_score >= 0.6:
            return PoolHealthStatus.GOOD
        elif health_score >= 0.4:
            return PoolHealthStatus.FAIR
        elif health_score >= 0.2:
            return PoolHealthStatus.POOR
        else:
            return PoolHealthStatus.CRITICAL

    async def analyze_whale_activity(
        self, 
        pool_data: Dict[str, Any],
        transaction_data: Optional[List[Dict[str, Any]]] = None
    ) -> WhaleActivity:
        """Analyze whale activity in a pool."""
        try:
            # This would analyze large transactions and whale behavior
            # For now, return basic structure
            
            return WhaleActivity(
                large_entries_24h=[],
                large_exits_24h=[],
                net_whale_flow_usd=0.0,
                whale_concentration_risk=0.3,
                coordinated_activity=False,
                wash_trading_suspected=False,
                market_maker_presence=False,
                whale_impact_on_price=0.0,
                liquidity_at_risk=0.0
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing whale activity: {e}")
            raise

    def get_liquidity_recommendation(self, metrics: LiquidityMetrics) -> Dict[str, Any]:
        """Get trading recommendation based on liquidity analysis."""
        try:
            # Determine recommendation based on health score and specific metrics
            if metrics.health_score >= 0.7 and metrics.liquidity_stability in [
                LiquidityStability.STABLE, LiquidityStability.VERY_STABLE
            ]:
                recommendation = "BUY"
                confidence = "HIGH"
                reasoning = f"Excellent liquidity health ({metrics.health_score:.3f}) with stable trading"
                
            elif metrics.health_score >= 0.5 and not metrics.suspicious_trading_patterns:
                recommendation = "MONITOR"
                confidence = "MEDIUM"
                reasoning = f"Good liquidity health ({metrics.health_score:.3f}) but watch for changes"
                
            elif metrics.health_score >= 0.3:
                recommendation = "CAUTION"
                confidence = "LOW"
                reasoning = f"Fair liquidity ({metrics.health_score:.3f}) with elevated risks"
                
            else:
                recommendation = "AVOID"
                confidence = "HIGH"
                reasoning = f"Poor liquidity health ({metrics.health_score:.3f}) - high risk"
            
            return {
                "action": recommendation,
                "confidence": confidence,
                "reasoning": reasoning,
                "health_score": metrics.health_score,
                "key_metrics": {
                    "liquidity_usd": metrics.total_liquidity_usd,
                    "volume_24h": metrics.volume_24h_usd,
                    "stability": metrics.liquidity_stability.value,
                    "price_impact_10k": metrics.price_impact_10k
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generating liquidity recommendation: {e}")
            return {
                "action": "AVOID",
                "confidence": "HIGH", 
                "reasoning": "Analysis error - avoid until resolved",
                "health_score": 0.0,
                "key_metrics": {}
            }