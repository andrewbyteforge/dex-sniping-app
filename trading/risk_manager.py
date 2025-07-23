"""
Risk management system for automated trading execution.
Provides position sizing, risk assessment, and portfolio protection.
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from models.token import TradingOpportunity, RiskLevel
from utils.logger import logger_manager


class RiskAssessment(Enum):
    """Risk assessment levels for trading decisions."""
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"
    MONITOR_ONLY = "monitor_only"


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""
    approved_amount: Decimal
    risk_assessment: RiskAssessment
    risk_score: float
    reasons: List[str]
    max_loss_usd: float
    recommended_stop_loss: float
    recommended_take_profit: float


@dataclass
class PortfolioLimits:
    """Portfolio-wide risk limits."""
    max_total_exposure_usd: float = 1000.0
    max_single_position_usd: float = 100.0
    max_daily_loss_usd: float = 200.0
    max_positions_per_chain: int = 5
    max_total_positions: int = 15
    min_liquidity_ratio: float = 0.1  # 10% of liquidity


class RiskManager:
    """
    Production-ready risk management system for DEX sniping.
    Handles position sizing, portfolio limits, and risk assessment.
    """

    def __init__(self, portfolio_limits: Optional[PortfolioLimits] = None) -> None:
        """
        Initialize the risk management system.
        
        Args:
            portfolio_limits: Optional custom portfolio limits
        """
        self.logger = logger_manager.get_logger("RiskManager")
        self.limits = portfolio_limits or PortfolioLimits()
        
        # Track current positions and daily performance
        self.current_positions: Dict[str, Decimal] = {}
        self.daily_pnl: float = 0.0
        self.position_history: List[Dict] = []
        self.last_reset_date = datetime.now().date()
        
        # Risk assessment weights
        self.risk_weights = {
            'contract_risk': 0.40,
            'liquidity_risk': 0.25,
            'social_risk': 0.15,
            'market_risk': 0.20
        }

    def assess_opportunity(self, opportunity: TradingOpportunity) -> PositionSizeResult:
        """
        Assess trading opportunity and calculate appropriate position size.
        
        Args:
            opportunity: The trading opportunity to assess
            
        Returns:
            PositionSizeResult with sizing and risk assessment
        """
        try:
            self.logger.debug(f"Assessing risk for {opportunity.token.symbol}")
            
            # Reset daily tracking if needed
            self._reset_daily_tracking_if_needed()
            
            # Calculate individual risk components
            contract_risk = self._assess_contract_risk(opportunity)
            liquidity_risk = self._assess_liquidity_risk(opportunity)
            social_risk = self._assess_social_risk(opportunity)
            market_risk = self._assess_market_risk(opportunity)
            
            # Calculate composite risk score
            risk_score = (
                contract_risk * self.risk_weights['contract_risk'] +
                liquidity_risk * self.risk_weights['liquidity_risk'] +
                social_risk * self.risk_weights['social_risk'] +
                market_risk * self.risk_weights['market_risk']
            )
            
            # Determine position size based on risk
            position_result = self._calculate_position_size(
                opportunity, risk_score, contract_risk, liquidity_risk
            )
            
            # Apply portfolio-level constraints
            final_result = self._apply_portfolio_constraints(opportunity, position_result)
            
            self.logger.info(
                f"Risk assessment complete: {opportunity.token.symbol} - "
                f"Score: {risk_score:.2f}, Assessment: {final_result.risk_assessment.value}"
            )
            
            return final_result
            
        except Exception as e:
            self.logger.error(f"Risk assessment failed for {opportunity.token.symbol}: {e}")
            return self._create_rejection_result("Risk assessment failed")

    def _assess_contract_risk(self, opportunity: TradingOpportunity) -> float:
        """
        Assess smart contract security risk.
        
        Args:
            opportunity: Trading opportunity to assess
            
        Returns:
            Risk score from 0.0 (lowest risk) to 1.0 (highest risk)
        """
        try:
            analysis = opportunity.contract_analysis
            risk_score = 0.0
            
            # Critical risk factors
            if analysis.is_honeypot:
                return 1.0  # Maximum risk
                
            # Major risk factors
            if not analysis.ownership_renounced:
                risk_score += 0.3
            if not analysis.liquidity_locked:
                risk_score += 0.4
            if analysis.has_blacklist:
                risk_score += 0.3
                
            # Medium risk factors
            if analysis.is_mintable:
                risk_score += 0.2
            if analysis.is_pausable:
                risk_score += 0.2
                
            # Risk level penalty
            risk_level_penalties = {
                RiskLevel.LOW: 0.0,
                RiskLevel.MEDIUM: 0.1,
                RiskLevel.HIGH: 0.3,
                RiskLevel.CRITICAL: 0.6
            }
            risk_score += risk_level_penalties.get(analysis.risk_level, 0.3)
            
            return min(1.0, risk_score)
            
        except Exception as e:
            self.logger.error(f"Contract risk assessment failed: {e}")
            return 0.8  # High risk on error

    def _assess_liquidity_risk(self, opportunity: TradingOpportunity) -> float:
        """
        Assess liquidity-related risks.
        
        Args:
            opportunity: Trading opportunity to assess
            
        Returns:
            Risk score from 0.0 (lowest risk) to 1.0 (highest risk)
        """
        try:
            liquidity_usd = opportunity.liquidity.liquidity_usd
            risk_score = 0.0
            
            # Liquidity amount risk
            if liquidity_usd < 5000:
                risk_score += 0.6  # Very low liquidity
            elif liquidity_usd < 25000:
                risk_score += 0.4  # Low liquidity
            elif liquidity_usd < 100000:
                risk_score += 0.2  # Medium liquidity
            # Above 100k is considered low risk
            
            # DEX risk assessment
            dex_risk_factors = {
                'Uniswap V2': 0.0,
                'Uniswap V3': 0.0,
                'BaseSwap': 0.1,
                'PancakeSwap': 0.1,
                'Pump.fun': 0.3,  # Bonding curve model is riskier
                'Jupiter': 0.2
            }
            
            dex_name = opportunity.liquidity.dex_name
            risk_score += dex_risk_factors.get(dex_name, 0.2)
            
            return min(1.0, risk_score)
            
        except Exception as e:
            self.logger.error(f"Liquidity risk assessment failed: {e}")
            return 0.7

    def _assess_social_risk(self, opportunity: TradingOpportunity) -> float:
        """
        Assess social and community-related risks.
        
        Args:
            opportunity: Trading opportunity to assess
            
        Returns:
            Risk score from 0.0 (lowest risk) to 1.0 (highest risk)
        """
        try:
            social = opportunity.social_metrics
            risk_score = 0.5  # Start neutral
            
            # Social activity risk
            if social.social_score < 0.2:
                risk_score += 0.3  # Very low social activity
            elif social.social_score < 0.4:
                risk_score += 0.1  # Low social activity
            elif social.social_score > 0.8:
                risk_score -= 0.2  # High social activity reduces risk
                
            # Sentiment risk
            if social.sentiment_score < -0.3:
                risk_score += 0.3  # Very negative sentiment
            elif social.sentiment_score < -0.1:
                risk_score += 0.1  # Negative sentiment
            elif social.sentiment_score > 0.3:
                risk_score -= 0.1  # Positive sentiment reduces risk
                
            return max(0.0, min(1.0, risk_score))
            
        except Exception as e:
            self.logger.error(f"Social risk assessment failed: {e}")
            return 0.6

    def _assess_market_risk(self, opportunity: TradingOpportunity) -> float:
        """
        Assess market timing and chain-specific risks.
        
        Args:
            opportunity: Trading opportunity to assess
            
        Returns:
            Risk score from 0.0 (lowest risk) to 1.0 (highest risk)
        """
        try:
            risk_score = 0.2  # Base market risk
            
            # Age risk (too old or too new can be risky)
            age_minutes = (datetime.now() - opportunity.detected_at).total_seconds() / 60
            if age_minutes > 60:  # Too old
                risk_score += 0.3
            elif age_minutes < 1:  # Too new, might be unstable
                risk_score += 0.1
                
            # Chain-specific risk
            chain = opportunity.metadata.get('chain', '').upper()
            chain_risk_factors = {
                'ETHEREUM': 0.0,      # Most stable
                'BASE': 0.1,          # Relatively new L2
                'SOLANA': 0.2,        # Higher volatility
                'SOLANA-PUMP': 0.3,   # Meme coin factory
                'SOLANA-JUPITER': 0.2
            }
            
            risk_score += chain_risk_factors.get(chain, 0.2)
            
            return min(1.0, risk_score)
            
        except Exception as e:
            self.logger.error(f"Market risk assessment failed: {e}")
            return 0.5

    def _calculate_position_size(
        self, 
        opportunity: TradingOpportunity, 
        risk_score: float,
        contract_risk: float,
        liquidity_risk: float
    ) -> PositionSizeResult:
        """
        Calculate appropriate position size based on risk assessment.
        
        Args:
            opportunity: Trading opportunity
            risk_score: Composite risk score
            contract_risk: Contract-specific risk
            liquidity_risk: Liquidity-specific risk
            
        Returns:
            PositionSizeResult with sizing recommendation
        """
        try:
            reasons = []
            
            # Determine base position size based on chain
            chain = opportunity.metadata.get('chain', 'ETHEREUM')
            base_position_sizes = {
                'ETHEREUM': Decimal('0.05'),      # 0.05 ETH
                'BASE': Decimal('0.1'),           # 0.1 ETH
                'SOLANA': Decimal('50'),          # 50 SOL
                'SOLANA-PUMP': Decimal('25'),     # 25 SOL
                'SOLANA-JUPITER': Decimal('40')   # 40 SOL
            }
            
            base_size = base_position_sizes.get(chain, Decimal('0.05'))
            
            # Apply risk-based scaling
            if risk_score > 0.8:
                assessment = RiskAssessment.REJECTED
                approved_amount = Decimal('0')
                reasons.append("Risk score too high for trading")
            elif risk_score > 0.6:
                assessment = RiskAssessment.CONDITIONAL
                approved_amount = base_size * Decimal('0.3')  # 30% of base
                reasons.append("High risk - reduced position size")
            elif risk_score > 0.4:
                assessment = RiskAssessment.CONDITIONAL
                approved_amount = base_size * Decimal('0.6')  # 60% of base
                reasons.append("Medium risk - moderate position size")
            else:
                assessment = RiskAssessment.APPROVED
                approved_amount = base_size
                reasons.append("Low risk - full position approved")
                
            # Apply liquidity constraints
            liquidity_usd = opportunity.liquidity.liquidity_usd
            if liquidity_usd > 0:
                # Don't take more than 10% of liquidity
                max_size_from_liquidity = Decimal(str(liquidity_usd * 0.1))
                
                # Convert to appropriate units (simplified)
                if 'SOL' in chain:
                    max_size_from_liquidity = max_size_from_liquidity / Decimal('100')  # Assume $100/SOL
                else:
                    max_size_from_liquidity = max_size_from_liquidity / Decimal('3000')  # Assume $3000/ETH
                    
                if approved_amount > max_size_from_liquidity:
                    approved_amount = max_size_from_liquidity
                    reasons.append("Position limited by liquidity constraints")
            
            # Calculate stop loss and take profit
            stop_loss_pct = 0.15 + (risk_score * 0.2)  # 15-35% based on risk
            take_profit_pct = 0.3 + (risk_score * -0.2)  # 30-10% based on risk (lower TP for high risk)
            
            # Estimate max loss in USD
            estimated_token_price_usd = 100.0  # Simplified estimate
            max_loss_usd = float(approved_amount) * estimated_token_price_usd * stop_loss_pct
            
            return PositionSizeResult(
                approved_amount=approved_amount,
                risk_assessment=assessment,
                risk_score=risk_score,
                reasons=reasons,
                max_loss_usd=max_loss_usd,
                recommended_stop_loss=stop_loss_pct,
                recommended_take_profit=take_profit_pct
            )
            
        except Exception as e:
            self.logger.error(f"Position size calculation failed: {e}")
            return self._create_rejection_result("Position sizing calculation failed")

    def _apply_portfolio_constraints(
        self, 
        opportunity: TradingOpportunity, 
        position_result: PositionSizeResult
    ) -> PositionSizeResult:
        """
        Apply portfolio-level constraints to position sizing.
        
        Args:
            opportunity: Trading opportunity
            position_result: Initial position sizing result
            
        Returns:
            Modified PositionSizeResult after applying portfolio constraints
        """
        try:
            if position_result.risk_assessment == RiskAssessment.REJECTED:
                return position_result
                
            reasons = list(position_result.reasons)
            approved_amount = position_result.approved_amount
            
            # Check daily loss limit
            if self.daily_pnl < -self.limits.max_daily_loss_usd:
                return PositionSizeResult(
                    approved_amount=Decimal('0'),
                    risk_assessment=RiskAssessment.REJECTED,
                    risk_score=position_result.risk_score,
                    reasons=["Daily loss limit exceeded"],
                    max_loss_usd=0.0,
                    recommended_stop_loss=position_result.recommended_stop_loss,
                    recommended_take_profit=position_result.recommended_take_profit
                )
            
            # Check position count limits
            chain = opportunity.metadata.get('chain', 'ETHEREUM')
            chain_positions = len([pos for pos in self.current_positions.keys() if chain in pos])
            
            if chain_positions >= self.limits.max_positions_per_chain:
                reasons.append(f"Chain position limit reached ({chain_positions})")
                approved_amount = Decimal('0')
                
            if len(self.current_positions) >= self.limits.max_total_positions:
                reasons.append(f"Total position limit reached ({len(self.current_positions)})")
                approved_amount = Decimal('0')
                
            # Check total exposure (simplified)
            current_exposure_usd = sum([float(pos) * 100 for pos in self.current_positions.values()])
            new_exposure_usd = float(approved_amount) * 100  # Simplified USD conversion
            
            if current_exposure_usd + new_exposure_usd > self.limits.max_total_exposure_usd:
                max_additional = self.limits.max_total_exposure_usd - current_exposure_usd
                if max_additional <= 0:
                    approved_amount = Decimal('0')
                    reasons.append("Total exposure limit reached")
                else:
                    approved_amount = Decimal(str(max_additional / 100))
                    reasons.append("Position size limited by total exposure")
            
            # Update assessment based on constraints
            if approved_amount == Decimal('0') and position_result.risk_assessment != RiskAssessment.REJECTED:
                assessment = RiskAssessment.REJECTED
            else:
                assessment = position_result.risk_assessment
                
            return PositionSizeResult(
                approved_amount=approved_amount,
                risk_assessment=assessment,
                risk_score=position_result.risk_score,
                reasons=reasons,
                max_loss_usd=position_result.max_loss_usd,
                recommended_stop_loss=position_result.recommended_stop_loss,
                recommended_take_profit=position_result.recommended_take_profit
            )
            
        except Exception as e:
            self.logger.error(f"Portfolio constraint application failed: {e}")
            return self._create_rejection_result("Portfolio constraint check failed")

    def _create_rejection_result(self, reason: str) -> PositionSizeResult:
        """
        Create a rejection result with the given reason.
        
        Args:
            reason: Reason for rejection
            
        Returns:
            PositionSizeResult indicating rejection
        """
        return PositionSizeResult(
            approved_amount=Decimal('0'),
            risk_assessment=RiskAssessment.REJECTED,
            risk_score=1.0,
            reasons=[reason],
            max_loss_usd=0.0,
            recommended_stop_loss=0.15,
            recommended_take_profit=0.30
        )

    def _reset_daily_tracking_if_needed(self) -> None:
        """Reset daily tracking if we've moved to a new day."""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_pnl = 0.0
            self.last_reset_date = current_date
            self.logger.info("Daily P&L tracking reset for new day")

    def update_daily_pnl(self, pnl_change: float) -> None:
        """
        Update daily P&L tracking.
        
        Args:
            pnl_change: Change in P&L (positive for profit, negative for loss)
        """
        self.daily_pnl += pnl_change
        self.logger.debug(f"Daily P&L updated: ${self.daily_pnl:.2f}")

    def add_position(self, token_symbol: str, amount: Decimal) -> None:
        """
        Add a new position to tracking.
        
        Args:
            token_symbol: Symbol of the token
            amount: Position size
        """
        self.current_positions[token_symbol] = amount
        self.logger.info(f"Position added: {token_symbol} - {amount}")

    def remove_position(self, token_symbol: str) -> None:
        """
        Remove a position from tracking.
        
        Args:
            token_symbol: Symbol of the token to remove
        """
        if token_symbol in self.current_positions:
            del self.current_positions[token_symbol]
            self.logger.info(f"Position removed: {token_symbol}")

    def get_portfolio_status(self) -> Dict:
        """
        Get current portfolio status and risk metrics.
        
        Returns:
            Dictionary containing portfolio status information
        """
        try:
            current_exposure = sum([float(pos) * 100 for pos in self.current_positions.values()])
            
            return {
                'total_positions': len(self.current_positions),
                'current_exposure_usd': current_exposure,
                'max_exposure_usd': self.limits.max_total_exposure_usd,
                'exposure_utilization': current_exposure / self.limits.max_total_exposure_usd,
                'daily_pnl': self.daily_pnl,
                'daily_loss_limit': self.limits.max_daily_loss_usd,
                'positions_by_chain': self._get_positions_by_chain(),
                'available_capacity': self.limits.max_total_exposure_usd - current_exposure
            }
        except Exception as e:
            self.logger.error(f"Failed to get portfolio status: {e}")
            return {}

    def _get_positions_by_chain(self) -> Dict[str, int]:
        """Get count of positions by chain."""
        chain_counts = {}
        for token_symbol in self.current_positions.keys():
            # Extract chain from token symbol or position metadata
            # This is simplified - in practice you'd have better chain tracking
            if 'SOL' in token_symbol:
                chain = 'SOLANA'
            elif 'BASE' in token_symbol:
                chain = 'BASE'
            else:
                chain = 'ETHEREUM'
                
            chain_counts[chain] = chain_counts.get(chain, 0) + 1
            
        return chain_counts