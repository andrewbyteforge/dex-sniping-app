#!/usr/bin/env python3
"""
Enhanced risk management system for automated trading execution.

Provides sophisticated position sizing, risk assessment, portfolio protection,
and dynamic risk adjustment based on market conditions.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json

from models.token import TradingOpportunity, RiskLevel
from utils.logger import logger_manager


class RiskAssessment(Enum):
    """Risk assessment levels for trading decisions."""
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"
    MONITOR_ONLY = "monitor_only"


class MarketCondition(Enum):
    """Market condition assessment."""
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation with enhanced metrics."""
    approved_amount: Decimal
    risk_assessment: RiskAssessment
    risk_score: float
    confidence_score: float
    reasons: List[str]
    warnings: List[str]
    
    # Financial metrics
    max_loss_usd: float
    expected_return_usd: float
    risk_reward_ratio: float
    
    # Exit strategy parameters
    recommended_stop_loss: float
    recommended_take_profit: float
    trailing_stop_distance: Optional[float] = None
    max_hold_time_hours: Optional[int] = None
    
    # Risk breakdown
    contract_risk: float = 0.0
    liquidity_risk: float = 0.0
    social_risk: float = 0.0
    market_risk: float = 0.0
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioLimits:
    """Enhanced portfolio-wide risk limits with dynamic adjustment."""
    # Base limits
    max_total_exposure_usd: float = 1000.0
    max_single_position_usd: float = 100.0
    max_daily_loss_usd: float = 200.0
    max_positions_per_chain: int = 5
    max_total_positions: int = 15
    
    # Liquidity constraints
    min_liquidity_ratio: float = 0.1  # 10% of liquidity
    min_liquidity_usd: float = 1000.0
    
    # Risk concentration limits
    max_exposure_per_token_type: float = 0.3  # 30% of portfolio
    max_correlation_exposure: float = 0.5  # 50% in correlated assets
    
    # Time-based limits
    max_trades_per_hour: int = 10
    max_trades_per_day: int = 50
    cooling_period_minutes: int = 5  # Between trades of same token
    
    # Market condition adjustments
    bearish_exposure_reduction: float = 0.5  # Reduce exposure by 50% in bear market
    volatile_position_limit_reduction: float = 0.3  # Reduce position limits by 30%
    
    def apply_market_condition(self, condition: MarketCondition) -> 'PortfolioLimits':
        """
        Apply market condition adjustments to limits.
        
        Args:
            condition: Current market condition
            
        Returns:
            PortfolioLimits: Adjusted limits based on market condition
        """
        adjusted = PortfolioLimits(
            max_total_exposure_usd=self.max_total_exposure_usd,
            max_single_position_usd=self.max_single_position_usd,
            max_daily_loss_usd=self.max_daily_loss_usd,
            max_positions_per_chain=self.max_positions_per_chain,
            max_total_positions=self.max_total_positions,
            min_liquidity_ratio=self.min_liquidity_ratio,
            min_liquidity_usd=self.min_liquidity_usd,
            max_exposure_per_token_type=self.max_exposure_per_token_type,
            max_correlation_exposure=self.max_correlation_exposure,
            max_trades_per_hour=self.max_trades_per_hour,
            max_trades_per_day=self.max_trades_per_day,
            cooling_period_minutes=self.cooling_period_minutes
        )
        
        if condition == MarketCondition.BEARISH:
            adjusted.max_total_exposure_usd *= (1 - self.bearish_exposure_reduction)
            adjusted.max_single_position_usd *= (1 - self.bearish_exposure_reduction)
            adjusted.max_positions_per_chain = max(1, int(self.max_positions_per_chain * 0.7))
            
        elif condition == MarketCondition.VOLATILE:
            adjusted.max_single_position_usd *= (1 - self.volatile_position_limit_reduction)
            adjusted.max_positions_per_chain = max(1, int(self.max_positions_per_chain * 0.8))
            adjusted.cooling_period_minutes = int(self.cooling_period_minutes * 1.5)
            
        return adjusted


@dataclass
class RiskMetrics:
    """Track risk metrics over time."""
    timestamp: datetime
    total_exposure: float
    portfolio_risk_score: float
    market_condition: MarketCondition
    daily_pnl: float
    win_rate: float
    avg_hold_time: float
    volatility_index: float


class EnhancedRiskManager:
    """
    Production-ready enhanced risk management system for DEX sniping.
    
    Features:
    - Sophisticated multi-factor risk assessment
    - Dynamic position sizing based on market conditions
    - Portfolio-level risk management
    - Real-time risk monitoring and adjustment
    - Advanced exit strategy optimization
    """

    def __init__(self, portfolio_limits: Optional[PortfolioLimits] = None) -> None:
        """
        Initialize the enhanced risk management system.
        
        Args:
            portfolio_limits: Optional custom portfolio limits
        """
        self.logger = logger_manager.get_logger("EnhancedRiskManager")
        self.base_limits = portfolio_limits or PortfolioLimits()
        self.current_limits = self.base_limits
        
        # Market condition tracking
        self.market_condition = MarketCondition.UNKNOWN
        self.market_condition_confidence = 0.0
        self.last_market_update = datetime.now()
        
        # Portfolio state tracking
        self.current_positions: Dict[str, Decimal] = {}
        self.position_correlations: Dict[str, float] = {}
        self.daily_trades_count = 0
        self.hourly_trades_count = 0
        self.last_trade_times: Dict[str, datetime] = {}
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        
        # Risk assessment weights (dynamically adjusted)
        self.base_risk_weights = {
            'contract_risk': 0.35,
            'liquidity_risk': 0.25,
            'social_risk': 0.15,
            'market_risk': 0.25
        }
        self.current_risk_weights = self.base_risk_weights.copy()
        
        # Performance tracking
        self.risk_metrics_history: List[RiskMetrics] = []
        self.total_assessments = 0
        self.approved_trades = 0
        self.rejected_trades = 0
        
        # Advanced features
        self.volatility_window = 24  # Hours to track volatility
        self.correlation_threshold = 0.7  # High correlation threshold
        self.confidence_threshold = 0.8  # Minimum confidence for approval
        
        self.logger.info("Enhanced risk manager initialized")

    async def assess_opportunity(self, opportunity: TradingOpportunity) -> PositionSizeResult:
        """
        Comprehensive opportunity assessment with enhanced risk analysis.
        
        Args:
            opportunity: Trading opportunity to assess
            
        Returns:
            PositionSizeResult: Detailed assessment with position sizing
        """
        try:
            self.total_assessments += 1
            token_symbol = opportunity.token.symbol or "UNKNOWN"
            
            self.logger.debug(f"Assessing opportunity: {token_symbol}")
            
            # Reset daily counters if needed
            self._check_daily_reset()
            
            # Update market conditions
            await self._update_market_conditions(opportunity)
            
            # Apply market condition adjustments to limits
            self.current_limits = self.base_limits.apply_market_condition(self.market_condition)
            
            # Perform comprehensive risk assessment
            risk_scores = await self._calculate_risk_scores(opportunity)
            overall_risk_score = self._calculate_overall_risk(risk_scores)
            confidence_score = self._calculate_confidence_score(opportunity, risk_scores)
            
            # Check portfolio constraints
            portfolio_check = self._check_portfolio_constraints(opportunity)
            if not portfolio_check['approved']:
                return self._create_rejection_result(
                    reason=portfolio_check['reason'],
                    risk_scores=risk_scores,
                    confidence_score=confidence_score
                )
            
            # Calculate position size
            position_result = await self._calculate_position_size(
                opportunity, risk_scores, overall_risk_score, confidence_score
            )
            
            # Apply final validations
            final_result = self._apply_final_validations(position_result, opportunity)
            
            # Track decision
            if final_result.risk_assessment == RiskAssessment.APPROVED:
                self.approved_trades += 1
            elif final_result.risk_assessment == RiskAssessment.REJECTED:
                self.rejected_trades += 1
            
            # Log assessment summary
            self._log_assessment_summary(opportunity, final_result)
            
            return final_result
            
        except Exception as e:
            self.logger.error(f"Risk assessment failed for {token_symbol}: {e}")
            return self._create_error_result(str(e))

    async def _calculate_risk_scores(self, opportunity: TradingOpportunity) -> Dict[str, float]:
        """
        Calculate detailed risk scores for all risk categories.
        
        Args:
            opportunity: Trading opportunity to assess
            
        Returns:
            Dictionary containing risk scores for each category
        """
        try:
            risk_scores = {}
            
            # Contract Risk Assessment
            contract_risk = await self._assess_contract_risk(opportunity)
            risk_scores['contract_risk'] = contract_risk
            
            # Liquidity Risk Assessment
            liquidity_risk = await self._assess_liquidity_risk(opportunity)
            risk_scores['liquidity_risk'] = liquidity_risk
            
            # Social Risk Assessment
            social_risk = await self._assess_social_risk(opportunity)
            risk_scores['social_risk'] = social_risk
            
            # Market Risk Assessment
            market_risk = await self._assess_market_risk(opportunity)
            risk_scores['market_risk'] = market_risk
            
            # Additional risk factors
            timing_risk = self._assess_timing_risk(opportunity)
            risk_scores['timing_risk'] = timing_risk
            
            correlation_risk = self._assess_correlation_risk(opportunity)
            risk_scores['correlation_risk'] = correlation_risk
            
            return risk_scores
            
        except Exception as e:
            self.logger.error(f"Error calculating risk scores: {e}")
            return {
                'contract_risk': 0.8,
                'liquidity_risk': 0.8,
                'social_risk': 0.8,
                'market_risk': 0.8,
                'timing_risk': 0.8,
                'correlation_risk': 0.5
            }

    async def _assess_contract_risk(self, opportunity: TradingOpportunity) -> float:
        """
        Assess smart contract and token-specific risks.
        
        Args:
            opportunity: Trading opportunity
            
        Returns:
            Contract risk score (0.0 = low risk, 1.0 = high risk)
        """
        try:
            risk_score = 0.0
            
            # Check contract analysis if available
            contract_analysis = opportunity.metadata.get('contract_analysis', {})
            
            # Honeypot risk
            if contract_analysis.get('is_honeypot', False):
                risk_score += 0.9  # Very high risk
            
            # Ownership concentration
            ownership_risk = contract_analysis.get('ownership_risk', 0.5)
            risk_score += ownership_risk * 0.3
            
            # Liquidity lock status
            if not contract_analysis.get('liquidity_locked', True):
                risk_score += 0.2
            
            # Contract verification
            if not contract_analysis.get('is_verified', False):
                risk_score += 0.15
            
            # Trading restrictions
            if contract_analysis.get('has_trading_restrictions', False):
                risk_score += 0.2
            
            # Token age (newer = riskier)
            token_age_hours = contract_analysis.get('token_age_hours', 0)
            if token_age_hours < 1:
                risk_score += 0.3
            elif token_age_hours < 24:
                risk_score += 0.1
            
            return min(risk_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error assessing contract risk: {e}")
            return 0.8  # Conservative high risk if error

    async def _assess_liquidity_risk(self, opportunity: TradingOpportunity) -> float:
        """
        Assess liquidity-related risks.
        
        Args:
            opportunity: Trading opportunity
            
        Returns:
            Liquidity risk score (0.0 = low risk, 1.0 = high risk)
        """
        try:
            risk_score = 0.0
            
            liquidity_usd = opportunity.liquidity.liquidity_usd or 0
            
            # Low liquidity risk
            if liquidity_usd < self.current_limits.min_liquidity_usd:
                risk_score += 0.8
            elif liquidity_usd < self.current_limits.min_liquidity_usd * 5:
                risk_score += 0.4
            elif liquidity_usd < self.current_limits.min_liquidity_usd * 10:
                risk_score += 0.2
            
            # Liquidity concentration (if available in metadata)
            liquidity_sources = opportunity.metadata.get('liquidity_sources', 1)
            if liquidity_sources == 1:
                risk_score += 0.2  # Single source risk
            
            # Price impact estimation
            trade_size_usd = 100  # Assume $100 trade for impact calculation
            if liquidity_usd > 0:
                price_impact = trade_size_usd / liquidity_usd
                if price_impact > 0.05:  # > 5% impact
                    risk_score += min(price_impact * 2, 0.5)
            
            return min(risk_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error assessing liquidity risk: {e}")
            return 0.6  # Moderate risk if error

    async def _assess_social_risk(self, opportunity: TradingOpportunity) -> float:
        """
        Assess social sentiment and community risks.
        
        Args:
            opportunity: Trading opportunity
            
        Returns:
            Social risk score (0.0 = low risk, 1.0 = high risk)
        """
        try:
            risk_score = 0.0
            
            social_metrics = opportunity.metadata.get('social_metrics', {})
            
            # Sentiment analysis
            sentiment = social_metrics.get('sentiment', 'neutral')
            if sentiment == 'very_negative':
                risk_score += 0.6
            elif sentiment == 'negative':
                risk_score += 0.3
            elif sentiment == 'neutral':
                risk_score += 0.1
            # Positive sentiment reduces risk (negative risk_score handled below)
            
            # Social volume/activity
            social_volume = social_metrics.get('volume_score', 0.5)
            if social_volume < 0.2:
                risk_score += 0.3  # Low social activity = higher risk
            elif social_volume > 0.8:
                risk_score += 0.2  # Extreme hype = higher risk
            
            # Community quality indicators
            community_score = social_metrics.get('community_quality', 0.5)
            risk_score += (1 - community_score) * 0.3
            
            # Spam/bot detection
            if social_metrics.get('high_bot_activity', False):
                risk_score += 0.4
            
            return max(min(risk_score, 1.0), 0.0)
            
        except Exception as e:
            self.logger.error(f"Error assessing social risk: {e}")
            return 0.5  # Neutral risk if error

    async def _assess_market_risk(self, opportunity: TradingOpportunity) -> float:
        """
        Assess broader market and timing risks.
        
        Args:
            opportunity: Trading opportunity
            
        Returns:
            Market risk score (0.0 = low risk, 1.0 = high risk)
        """
        try:
            risk_score = 0.0
            
            # Market condition impact
            if self.market_condition == MarketCondition.BEARISH:
                risk_score += 0.4
            elif self.market_condition == MarketCondition.VOLATILE:
                risk_score += 0.3
            elif self.market_condition == MarketCondition.UNKNOWN:
                risk_score += 0.2
            
            # Time-based risks (market hours, etc.)
            current_hour = datetime.now().hour
            
            # Higher risk during low activity hours (US timezone assumed)
            if current_hour < 6 or current_hour > 22:
                risk_score += 0.1
            
            # Weekend risk (if applicable)
            if datetime.now().weekday() >= 5:  # Saturday or Sunday
                risk_score += 0.1
            
            # Chain-specific market risks
            chain = opportunity.chain.lower()
            if chain == 'solana':
                risk_score += 0.1  # Higher volatility on Solana
            elif chain == 'base':
                risk_score += 0.05  # Slight additional risk on newer chains
            
            return min(risk_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error assessing market risk: {e}")
            return 0.3  # Moderate risk if error

    def _assess_timing_risk(self, opportunity: TradingOpportunity) -> float:
        """
        Assess timing-related risks.
        
        Args:
            opportunity: Trading opportunity
            
        Returns:
            Timing risk score (0.0 = low risk, 1.0 = high risk)
        """
        try:
            risk_score = 0.0
            
            # Time since token launch
            launch_time = opportunity.metadata.get('launch_time')
            if launch_time:
                time_since_launch = datetime.now() - launch_time
                hours_since_launch = time_since_launch.total_seconds() / 3600
                
                # Very new tokens are riskier
                if hours_since_launch < 0.5:  # Less than 30 minutes
                    risk_score += 0.4
                elif hours_since_launch < 2:  # Less than 2 hours
                    risk_score += 0.2
                elif hours_since_launch < 24:  # Less than 24 hours
                    risk_score += 0.1
            
            # Check if we've traded this token recently
            token_address = opportunity.token.address
            if token_address in self.last_trade_times:
                time_since_last_trade = datetime.now() - self.last_trade_times[token_address]
                cooling_period = timedelta(minutes=self.current_limits.cooling_period_minutes)
                
                if time_since_last_trade < cooling_period:
                    risk_score += 0.5  # High risk for rapid re-entry
            
            return min(risk_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error assessing timing risk: {e}")
            return 0.2

    def _assess_correlation_risk(self, opportunity: TradingOpportunity) -> float:
        """
        Assess portfolio correlation risks.
        
        Args:
            opportunity: Trading opportunity
            
        Returns:
            Correlation risk score (0.0 = low risk, 1.0 = high risk)
        """
        try:
            risk_score = 0.0
            
            # Check exposure to similar tokens/categories
            token_category = opportunity.metadata.get('category', 'unknown')
            chain = opportunity.chain
            
            # Count existing positions in same category
            same_category_count = 0
            same_chain_count = 0
            
            for position_key, amount in self.current_positions.items():
                if token_category in position_key:
                    same_category_count += 1
                if chain in position_key:
                    same_chain_count += 1
            
            # Risk increases with concentration
            if same_category_count >= 3:
                risk_score += 0.3
            elif same_category_count >= 2:
                risk_score += 0.2
            
            if same_chain_count >= self.current_limits.max_positions_per_chain * 0.8:
                risk_score += 0.2
            
            return min(risk_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error assessing correlation risk: {e}")
            return 0.1

    def _calculate_overall_risk(self, risk_scores: Dict[str, float]) -> float:
        """
        Calculate overall weighted risk score.
        
        Args:
            risk_scores: Individual risk scores by category
            
        Returns:
            Overall risk score (0.0 = low risk, 1.0 = high risk)
        """
        try:
            overall_risk = 0.0
            
            # Apply weights to main risk categories
            for category, weight in self.current_risk_weights.items():
                if category in risk_scores:
                    overall_risk += risk_scores[category] * weight
            
            # Add additional risk factors with lower weights
            if 'timing_risk' in risk_scores:
                overall_risk += risk_scores['timing_risk'] * 0.1
            
            if 'correlation_risk' in risk_scores:
                overall_risk += risk_scores['correlation_risk'] * 0.1
            
            return min(overall_risk, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error calculating overall risk: {e}")
            return 0.8

    def _calculate_confidence_score(
        self, 
        opportunity: TradingOpportunity, 
        risk_scores: Dict[str, float]
    ) -> float:
        """
        Calculate confidence score for the opportunity assessment.
        
        Args:
            opportunity: Trading opportunity
            risk_scores: Risk scores by category
            
        Returns:
            Confidence score (0.0 = low confidence, 1.0 = high confidence)
        """
        try:
            confidence = 0.0
            
            # Data completeness factor
            available_data_points = 0
            total_data_points = 6
            
            if opportunity.metadata.get('contract_analysis'):
                available_data_points += 1
            if opportunity.metadata.get('social_metrics'):
                available_data_points += 1
            if opportunity.liquidity.liquidity_usd and opportunity.liquidity.liquidity_usd > 0:
                available_data_points += 1
            if opportunity.token.price:
                available_data_points += 1
            if opportunity.metadata.get('launch_time'):
                available_data_points += 1
            if opportunity.metadata.get('category'):
                available_data_points += 1
            
            data_completeness = available_data_points / total_data_points
            confidence += data_completeness * 0.4
            
            # Risk assessment consistency
            risk_variance = self._calculate_risk_variance(risk_scores)
            consistency_score = 1 - min(risk_variance, 1.0)
            confidence += consistency_score * 0.3
            
            # Market condition confidence
            confidence += self.market_condition_confidence * 0.2
            
            # Historical performance of similar assessments
            historical_accuracy = self._get_historical_accuracy(opportunity)
            confidence += historical_accuracy * 0.1
            
            return min(confidence, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error calculating confidence score: {e}")
            return 0.5

    def _calculate_risk_variance(self, risk_scores: Dict[str, float]) -> float:
        """Calculate variance in risk scores to assess consistency."""
        try:
            main_scores = [
                risk_scores.get('contract_risk', 0.5),
                risk_scores.get('liquidity_risk', 0.5),
                risk_scores.get('social_risk', 0.5),
                risk_scores.get('market_risk', 0.5)
            ]
            
            mean_score = sum(main_scores) / len(main_scores)
            variance = sum((score - mean_score) ** 2 for score in main_scores) / len(main_scores)
            
            return variance
            
        except Exception as e:
            self.logger.error(f"Error calculating risk variance: {e}")
            return 0.5

    def _get_historical_accuracy(self, opportunity: TradingOpportunity) -> float:
        """Get historical accuracy for similar opportunities."""
        try:
            # Simplified implementation - would use ML models in production
            # For now, return based on recent success rate
            if self.total_assessments > 10:
                success_rate = self.approved_trades / max(self.total_assessments, 1)
                return min(success_rate, 1.0)
            else:
                return 0.5  # Neutral confidence for new system
                
        except Exception as e:
            self.logger.error(f"Error getting historical accuracy: {e}")
            return 0.5

    async def _calculate_position_size(
        self,
        opportunity: TradingOpportunity,
        risk_scores: Dict[str, float],
        overall_risk: float,
        confidence_score: float
    ) -> PositionSizeResult:
        """
        Calculate optimal position size based on risk assessment.
        
        Args:
            opportunity: Trading opportunity
            risk_scores: Individual risk scores
            overall_risk: Overall risk score
            confidence_score: Assessment confidence
            
        Returns:
            PositionSizeResult: Detailed position sizing result
        """
        try:
            # Base position size calculation
            base_position_usd = self.current_limits.max_single_position_usd
            
            # Risk-adjusted sizing
            risk_multiplier = 1 - overall_risk
            confidence_multiplier = confidence_score
            
            # Kelly criterion approximation for position sizing
            win_probability = confidence_score * (1 - overall_risk)
            avg_win = 0.3  # Assume 30% average win
            avg_loss = 0.2  # Assume 20% average loss
            
            kelly_fraction = (win_probability * avg_win - (1 - win_probability) * avg_loss) / avg_win
            kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap at 25% of base size
            
            # Final position size
            position_size_usd = base_position_usd * risk_multiplier * confidence_multiplier
            
            # Apply Kelly criterion if it suggests smaller position
            kelly_position = base_position_usd * kelly_fraction
            if kelly_position < position_size_usd:
                position_size_usd = kelly_position
            
            # Convert to token amount (simplified - would use actual price in production)
            token_price_usd = float(opportunity.token.price or 1.0)
            if token_price_usd > 0:
                approved_amount = Decimal(str(position_size_usd / token_price_usd))
            else:
                approved_amount = Decimal('0')
            
            # Determine risk assessment
            risk_assessment = self._determine_risk_assessment(overall_risk, confidence_score)
            
            # Calculate exit strategy parameters
            stop_loss, take_profit = self._calculate_exit_levels(overall_risk, confidence_score)
            
            # Calculate financial metrics
            max_loss_usd = position_size_usd * stop_loss
            expected_return_usd = position_size_usd * take_profit * win_probability
            risk_reward_ratio = take_profit / stop_loss if stop_loss > 0 else 0
            
            # Generate reasons and warnings
            reasons, warnings = self._generate_assessment_reasons(
                risk_scores, overall_risk, confidence_score, risk_assessment
            )
            
            return PositionSizeResult(
                approved_amount=approved_amount,
                risk_assessment=risk_assessment,
                risk_score=overall_risk,
                confidence_score=confidence_score,
                reasons=reasons,
                warnings=warnings,
                max_loss_usd=max_loss_usd,
                expected_return_usd=expected_return_usd,
                risk_reward_ratio=risk_reward_ratio,
                recommended_stop_loss=stop_loss,
                recommended_take_profit=take_profit,
                trailing_stop_distance=stop_loss * 0.5,  # 50% of stop loss distance
                max_hold_time_hours=self._calculate_max_hold_time(overall_risk),
                contract_risk=risk_scores.get('contract_risk', 0),
                liquidity_risk=risk_scores.get('liquidity_risk', 0),
                social_risk=risk_scores.get('social_risk', 0),
                market_risk=risk_scores.get('market_risk', 0),
                metadata={
                    'market_condition': self.market_condition.value,
                    'position_size_usd': position_size_usd,
                    'kelly_fraction': kelly_fraction,
                    'risk_multiplier': risk_multiplier,
                    'confidence_multiplier': confidence_multiplier
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return self._create_error_result(str(e))

    def _determine_risk_assessment(self, overall_risk: float, confidence_score: float) -> RiskAssessment:
        """Determine final risk assessment based on scores."""
        if overall_risk > 0.8 or confidence_score < 0.3:
            return RiskAssessment.REJECTED
        elif overall_risk > 0.6 or confidence_score < 0.5:
            return RiskAssessment.MONITOR_ONLY
        elif overall_risk > 0.4 or confidence_score < 0.7:
            return RiskAssessment.CONDITIONAL
        else:
            return RiskAssessment.APPROVED

    def _calculate_exit_levels(self, overall_risk: float, confidence_score: float) -> Tuple[float, float]:
        """Calculate stop loss and take profit levels."""
        # Base levels
        base_stop_loss = 0.15  # 15%
        base_take_profit = 0.30  # 30%
        
        # Risk adjustments
        stop_loss = base_stop_loss + (overall_risk * 0.2)  # Higher risk = tighter stop
        take_profit = base_take_profit - (overall_risk * 0.15)  # Higher risk = lower target
        
        # Confidence adjustments
        if confidence_score > 0.8:
            take_profit += 0.1  # Higher target for high confidence
        elif confidence_score < 0.5:
            stop_loss -= 0.05  # Tighter stop for low confidence
        
        return min(stop_loss, 0.35), max(take_profit, 0.1)

    def _calculate_max_hold_time(self, overall_risk: float) -> int:
        """Calculate maximum hold time in hours based on risk."""
        base_hours = 24
        risk_adjustment = overall_risk * 12  # 0-12 hour reduction
        return max(int(base_hours - risk_adjustment), 2)

    def _generate_assessment_reasons(
        self,
        risk_scores: Dict[str, float],
        overall_risk: float,
        confidence_score: float,
        risk_assessment: RiskAssessment
    ) -> Tuple[List[str], List[str]]:
        """Generate human-readable reasons and warnings."""
        reasons = []
        warnings = []
        
        # Risk-based reasons
        if overall_risk < 0.3:
            reasons.append("Low overall risk profile")
        elif overall_risk < 0.6:
            reasons.append("Moderate risk within acceptable range")
        else:
            reasons.append("High risk - requires careful monitoring")
        
        # Confidence-based reasons
        if confidence_score > 0.8:
            reasons.append("High confidence in assessment")
        elif confidence_score > 0.6:
            reasons.append("Good confidence in analysis")
        else:
            warnings.append("Low confidence - limited data available")
        
        # Specific risk factors
        if risk_scores.get('contract_risk', 0) > 0.7:
            warnings.append("High contract risk detected")
        if risk_scores.get('liquidity_risk', 0) > 0.7:
            warnings.append("Low liquidity may impact execution")
        if risk_scores.get('social_risk', 0) > 0.7:
            warnings.append("Negative social sentiment")
        
        # Market condition warnings
        if self.market_condition == MarketCondition.BEARISH:
            warnings.append("Bearish market conditions")
        elif self.market_condition == MarketCondition.VOLATILE:
            warnings.append("High market volatility")
        
        return reasons, warnings

    def _check_portfolio_constraints(self, opportunity: TradingOpportunity) -> Dict[str, Any]:
        """Check if opportunity passes portfolio-level constraints."""
        try:
            # Check position count limits
            active_positions = len(self.current_positions)
            if active_positions >= self.current_limits.max_total_positions:
                return {
                    'approved': False,
                    'reason': f"Maximum positions reached ({active_positions}/{self.current_limits.max_total_positions})"
                }
            
            # Check chain-specific limits
            chain_positions = sum(1 for key in self.current_positions.keys() if opportunity.chain in key)
            if chain_positions >= self.current_limits.max_positions_per_chain:
                return {
                    'approved': False,
                    'reason': f"Maximum {opportunity.chain} positions reached ({chain_positions}/{self.current_limits.max_positions_per_chain})"
                }
            
            # Check daily trade limits
            if self.daily_trades_count >= self.current_limits.max_trades_per_day:
                return {
                    'approved': False,
                    'reason': f"Daily trade limit reached ({self.daily_trades_count}/{self.current_limits.max_trades_per_day})"
                }
            
            # Check hourly trade limits
            if self.hourly_trades_count >= self.current_limits.max_trades_per_hour:
                return {
                    'approved': False,
                    'reason': f"Hourly trade limit reached ({self.hourly_trades_count}/{self.current_limits.max_trades_per_hour})"
                }
            
            # Check daily loss limits
            if self.daily_pnl <= -self.current_limits.max_daily_loss_usd:
                return {
                    'approved': False,
                    'reason': f"Daily loss limit reached (${self.daily_pnl:.2f})"
                }
            
            # Check cooling period for same token
            token_address = opportunity.token.address
            if token_address in self.last_trade_times:
                time_since_last = datetime.now() - self.last_trade_times[token_address]
                cooling_period = timedelta(minutes=self.current_limits.cooling_period_minutes)
                
                if time_since_last < cooling_period:
                    remaining_minutes = (cooling_period - time_since_last).total_seconds() / 60
                    return {
                        'approved': False,
                        'reason': f"Cooling period active - {remaining_minutes:.1f} minutes remaining"
                    }
            
            return {'approved': True, 'reason': 'Portfolio constraints passed'}
            
        except Exception as e:
            self.logger.error(f"Error checking portfolio constraints: {e}")
            return {'approved': False, 'reason': 'Portfolio constraint check failed'}

    async def _update_market_conditions(self, opportunity: TradingOpportunity) -> None:
        """
        Update market condition assessment based on recent data.
        
        Args:
            opportunity: Current trading opportunity for context
        """
        try:
            # Simple market condition assessment (would be more sophisticated in production)
            current_time = datetime.now()
            
            # Update market condition every 30 minutes
            if (current_time - self.last_market_update).total_seconds() > 1800:
                
                # Analyze recent opportunities for market sentiment
                recent_opportunities = getattr(self, 'recent_opportunities', [])
                
                if len(recent_opportunities) > 10:
                    # Calculate average risk scores
                    avg_risk = sum(opp.get('risk_score', 0.5) for opp in recent_opportunities[-10:]) / 10
                    
                    # Determine market condition
                    if avg_risk > 0.7:
                        self.market_condition = MarketCondition.BEARISH
                        self.market_condition_confidence = 0.7
                    elif avg_risk > 0.6:
                        self.market_condition = MarketCondition.VOLATILE
                        self.market_condition_confidence = 0.6
                    elif avg_risk < 0.4:
                        self.market_condition = MarketCondition.BULLISH
                        self.market_condition_confidence = 0.8
                    else:
                        self.market_condition = MarketCondition.NEUTRAL
                        self.market_condition_confidence = 0.6
                else:
                    # Default to neutral with low confidence
                    self.market_condition = MarketCondition.NEUTRAL
                    self.market_condition_confidence = 0.4
                
                self.last_market_update = current_time
                self.logger.debug(f"Market condition updated: {self.market_condition.value} (confidence: {self.market_condition_confidence})")
                
        except Exception as e:
            self.logger.error(f"Error updating market conditions: {e}")

    def _apply_final_validations(
        self, 
        position_result: PositionSizeResult, 
        opportunity: TradingOpportunity
    ) -> PositionSizeResult:
        """
        Apply final validations and adjustments to position sizing result.
        
        Args:
            position_result: Initial position sizing result
            opportunity: Trading opportunity
            
        Returns:
            PositionSizeResult: Final validated result
        """
        try:
            # Check minimum position size
            min_position_usd = 10.0  # $10 minimum
            position_usd = float(position_result.approved_amount) * float(opportunity.token.price or 1.0)
            
            if position_usd < min_position_usd:
                position_result.risk_assessment = RiskAssessment.REJECTED
                position_result.approved_amount = Decimal('0')
                position_result.reasons.append(f"Position too small (${position_usd:.2f} < ${min_position_usd})")
                return position_result
            
            # Check liquidity impact
            liquidity_usd = opportunity.liquidity.liquidity_usd or 0
            if liquidity_usd > 0:
                impact_ratio = position_usd / liquidity_usd
                if impact_ratio > self.current_limits.min_liquidity_ratio:
                    # Reduce position size to meet liquidity constraints
                    max_position_usd = liquidity_usd * self.current_limits.min_liquidity_ratio
                    adjusted_amount = Decimal(str(max_position_usd / float(opportunity.token.price or 1.0)))
                    
                    if adjusted_amount < position_result.approved_amount:
                        position_result.approved_amount = adjusted_amount
                        position_result.warnings.append(f"Position reduced due to liquidity constraints (impact: {impact_ratio:.1%})")
            
            # Final confidence check
            if position_result.confidence_score < self.confidence_threshold:
                if position_result.risk_assessment == RiskAssessment.APPROVED:
                    position_result.risk_assessment = RiskAssessment.CONDITIONAL
                    position_result.warnings.append("Downgraded to conditional due to low confidence")
            
            return position_result
            
        except Exception as e:
            self.logger.error(f"Error in final validations: {e}")
            return position_result

    def _create_rejection_result(
        self, 
        reason: str, 
        risk_scores: Optional[Dict[str, float]] = None,
        confidence_score: float = 0.0
    ) -> PositionSizeResult:
        """Create a rejection result with proper formatting."""
        return PositionSizeResult(
            approved_amount=Decimal('0'),
            risk_assessment=RiskAssessment.REJECTED,
            risk_score=1.0,
            confidence_score=confidence_score,
            reasons=[reason],
            warnings=[],
            max_loss_usd=0.0,
            expected_return_usd=0.0,
            risk_reward_ratio=0.0,
            recommended_stop_loss=0.0,
            recommended_take_profit=0.0,
            contract_risk=risk_scores.get('contract_risk', 0.8) if risk_scores else 0.8,
            liquidity_risk=risk_scores.get('liquidity_risk', 0.8) if risk_scores else 0.8,
            social_risk=risk_scores.get('social_risk', 0.8) if risk_scores else 0.8,
            market_risk=risk_scores.get('market_risk', 0.8) if risk_scores else 0.8
        )

    def _create_error_result(self, error_message: str) -> PositionSizeResult:
        """Create an error result."""
        return PositionSizeResult(
            approved_amount=Decimal('0'),
            risk_assessment=RiskAssessment.REJECTED,
            risk_score=1.0,
            confidence_score=0.0,
            reasons=[f"Assessment error: {error_message}"],
            warnings=["Risk assessment failed - defaulting to rejection"],
            max_loss_usd=0.0,
            expected_return_usd=0.0,
            risk_reward_ratio=0.0,
            recommended_stop_loss=0.0,
            recommended_take_profit=0.0,
            contract_risk=1.0,
            liquidity_risk=1.0,
            social_risk=1.0,
            market_risk=1.0
        )

    def _log_assessment_summary(
        self, 
        opportunity: TradingOpportunity, 
        result: PositionSizeResult
    ) -> None:
        """Log comprehensive assessment summary."""
        try:
            token_symbol = opportunity.token.symbol or "UNKNOWN"
            
            self.logger.info(f"🔍 RISK ASSESSMENT: {token_symbol}")
            self.logger.info(f"   Decision: {result.risk_assessment.value.upper()}")
            self.logger.info(f"   Risk Score: {result.risk_score:.3f}")
            self.logger.info(f"   Confidence: {result.confidence_score:.3f}")
            self.logger.info(f"   Position Size: {result.approved_amount}")
            
            if result.risk_assessment != RiskAssessment.REJECTED:
                self.logger.info(f"   Stop Loss: {result.recommended_stop_loss:.1%}")
                self.logger.info(f"   Take Profit: {result.recommended_take_profit:.1%}")
                self.logger.info(f"   Max Loss: ${result.max_loss_usd:.2f}")
                self.logger.info(f"   R/R Ratio: {result.risk_reward_ratio:.2f}")
            
            # Log detailed risk breakdown
            self.logger.debug(f"   Contract Risk: {result.contract_risk:.3f}")
            self.logger.debug(f"   Liquidity Risk: {result.liquidity_risk:.3f}")
            self.logger.debug(f"   Social Risk: {result.social_risk:.3f}")
            self.logger.debug(f"   Market Risk: {result.market_risk:.3f}")
            
            # Log reasons and warnings
            if result.reasons:
                self.logger.debug(f"   Reasons: {' | '.join(result.reasons)}")
            if result.warnings:
                self.logger.warning(f"   Warnings: {' | '.join(result.warnings)}")
                
        except Exception as e:
            self.logger.error(f"Error logging assessment summary: {e}")

    def _check_daily_reset(self) -> None:
        """Check if daily counters need to be reset."""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_trades_count = 0
            self.daily_pnl = 0.0
            self.last_reset_date = current_date
            self.logger.debug("Daily counters reset")

    def update_position_opened(self, opportunity: TradingOpportunity, amount: Decimal) -> None:
        """
        Update risk manager state when a position is opened.
        
        Args:
            opportunity: Trading opportunity that was executed
            amount: Amount of position opened
        """
        try:
            token_address = opportunity.token.address
            
            # Update position tracking
            self.current_positions[token_address] = amount
            
            # Update trade counters
            self.daily_trades_count += 1
            self.hourly_trades_count += 1
            
            # Update last trade time
            self.last_trade_times[token_address] = datetime.now()
            
            self.logger.debug(f"Position opened tracking updated: {opportunity.token.symbol}")
            
        except Exception as e:
            self.logger.error(f"Error updating position opened: {e}")

    def update_position_closed(
        self, 
        token_address: str, 
        pnl: float, 
        trade_successful: bool
    ) -> None:
        """
        Update risk manager state when a position is closed.
        
        Args:
            token_address: Token address of closed position
            pnl: Profit/loss from the trade
            trade_successful: Whether trade was successful
        """
        try:
            # Remove from current positions
            if token_address in self.current_positions:
                del self.current_positions[token_address]
            
            # Update P&L tracking
            self.daily_pnl += pnl
            
            # Update performance metrics
            if trade_successful:
                self.successful_trades += 1
            
            self.logger.debug(f"Position closed tracking updated: PnL ${pnl:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error updating position closed: {e}")

    def get_current_exposure(self) -> Dict[str, Any]:
        """
        Get current portfolio exposure metrics.
        
        Returns:
            Dictionary containing exposure information
        """
        try:
            total_positions = len(self.current_positions)
            
            # Calculate exposure by chain
            chain_exposure = {}
            for position_key in self.current_positions.keys():
                # Extract chain from position key (simplified)
                for chain in ['ethereum', 'base', 'solana']:
                    if chain in position_key.lower():
                        chain_exposure[chain] = chain_exposure.get(chain, 0) + 1
                        break
            
            # Calculate risk metrics
            avg_risk = 0.0
            if hasattr(self, 'recent_risk_scores') and self.recent_risk_scores:
                avg_risk = sum(self.recent_risk_scores[-10:]) / min(len(self.recent_risk_scores), 10)
            
            return {
                'total_positions': total_positions,
                'max_positions': self.current_limits.max_total_positions,
                'chain_exposure': chain_exposure,
                'daily_trades': self.daily_trades_count,
                'daily_pnl': self.daily_pnl,
                'market_condition': self.market_condition.value,
                'average_risk_score': avg_risk,
                'total_assessments': self.total_assessments,
                'approval_rate': self.approved_trades / max(self.total_assessments, 1) * 100
            }
            
        except Exception as e:
            self.logger.error(f"Error getting current exposure: {e}")
            return {}

    def update_risk_weights(self, new_weights: Dict[str, float]) -> None:
        """
        Update risk assessment weights.
        
        Args:
            new_weights: New weights for risk categories
        """
        try:
            # Validate weights sum to 1.0
            total_weight = sum(new_weights.values())
            if abs(total_weight - 1.0) > 0.01:
                self.logger.warning(f"Risk weights don't sum to 1.0: {total_weight}")
                # Normalize weights
                new_weights = {k: v/total_weight for k, v in new_weights.items()}
            
            self.current_risk_weights.update(new_weights)
            self.logger.info(f"Risk weights updated: {self.current_risk_weights}")
            
        except Exception as e:
            self.logger.error(f"Error updating risk weights: {e}")

    async def cleanup(self) -> None:
        """Cleanup risk manager resources."""
        try:
            self.logger.info("Cleaning up risk manager...")
            
            # Save metrics history if needed
            if hasattr(self, 'metrics_file'):
                await self._save_metrics_history()
            
            self.logger.info("Risk manager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during risk manager cleanup: {e}")

    async def _save_metrics_history(self) -> None:
        """Save risk metrics history to file."""
        try:
            # Implementation would save metrics to persistent storage
            # For now, just log summary
            if self.risk_metrics_history:
                self.logger.info(f"Risk metrics history: {len(self.risk_metrics_history)} entries")
                
        except Exception as e:
            self.logger.error(f"Error saving metrics history: {e}")


# Maintain backward compatibility
RiskManager = EnhancedRiskManager