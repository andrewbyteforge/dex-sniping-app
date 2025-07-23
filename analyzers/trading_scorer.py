# analyzers/trading_scorer.py
"""
Trading opportunity scoring and recommendation system.
Combines contract analysis, social metrics, and market data to score opportunities.
"""

from typing import Dict, List, Tuple
from datetime import datetime
import math

from models.token import TradingOpportunity, RiskLevel
from utils.logger import logger_manager

class TradingScorer:
    """
    Scores trading opportunities based on multiple factors and generates recommendations.
    """
    
    def __init__(self):
        """Initialize the trading scorer."""
        self.logger = logger_manager.get_logger("TradingScorer")
        
        # Scoring weights for different factors
        self.scoring_weights = {
            'contract_safety': 0.40,    # 40% - Most important
            'social_sentiment': 0.25,   # 25% - Community strength
            'liquidity_quality': 0.20,  # 20% - Market structure
            'timing_factors': 0.15      # 15% - Launch timing, etc.
        }
        
        # Risk tolerance thresholds
        self.risk_thresholds = {
            RiskLevel.LOW: 0.3,
            RiskLevel.MEDIUM: 0.6,
            RiskLevel.HIGH: 0.8,
            RiskLevel.CRITICAL: 1.0
        }
        
    def score_opportunity(self, opportunity: TradingOpportunity) -> float:
        """
        Calculate a comprehensive score for a trading opportunity.
        
        Args:
            opportunity: The opportunity to score
            
        Returns:
            Score from 0.0 (terrible) to 1.0 (excellent)
        """
        try:
            self.logger.info(f"Scoring opportunity: {opportunity.token.symbol}")
            
            # Component scores
            contract_score = self._score_contract_safety(opportunity)
            social_score = self._score_social_metrics(opportunity)
            liquidity_score = self._score_liquidity_quality(opportunity)
            timing_score = self._score_timing_factors(opportunity)
            
            # Weighted combination
            final_score = (
                contract_score * self.scoring_weights['contract_safety'] +
                social_score * self.scoring_weights['social_sentiment'] +
                liquidity_score * self.scoring_weights['liquidity_quality'] +
                timing_score * self.scoring_weights['timing_factors']
            )
            
            # Update opportunity with calculated score
            opportunity.confidence_score = final_score
            
            self.logger.info(
                f"Scoring complete: {opportunity.token.symbol} - "
                f"Final: {final_score:.3f} "
                f"(Contract: {contract_score:.2f}, Social: {social_score:.2f}, "
                f"Liquidity: {liquidity_score:.2f}, Timing: {timing_score:.2f})"
            )
            
            return final_score
            
        except Exception as e:
            self.logger.error(f"Scoring failed for {opportunity.token.symbol}: {e}")
            return 0.1  # Very low score on error
            
    def _score_contract_safety(self, opportunity: TradingOpportunity) -> float:
        """Score contract safety and security factors."""
        try:
            analysis = opportunity.contract_analysis
            score = 1.0  # Start with perfect score
            
            # Major red flags
            if analysis.is_honeypot:
                return 0.0  # Instant fail
                
            # Significant penalties
            if not analysis.ownership_renounced:
                score -= 0.3
                
            if not analysis.liquidity_locked:
                score -= 0.4
                
            if analysis.has_blacklist:
                score -= 0.3
                
            # Medium penalties
            if analysis.is_mintable:
                score -= 0.2
                
            if analysis.is_pausable:
                score -= 0.2
                
            # Apply risk level penalty
            risk_penalty = {
                RiskLevel.LOW: 0.0,
                RiskLevel.MEDIUM: 0.1,
                RiskLevel.HIGH: 0.3,
                RiskLevel.CRITICAL: 0.6
            }.get(analysis.risk_level, 0.3)
            
            score -= risk_penalty
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            self.logger.error(f"Contract scoring failed: {e}")
            return 0.2
            
    def _score_social_metrics(self, opportunity: TradingOpportunity) -> float:
        """Score social media presence and sentiment."""
        try:
            social = opportunity.social_metrics
            
            # Base social activity score
            activity_score = social.social_score if social.social_score else 0.3
            
            # Sentiment modifier
            sentiment = social.sentiment_score if social.sentiment_score else 0.0
            sentiment_multiplier = 1.0 + (sentiment * 0.5)  # -50% to +50% modifier
            
            # Community size bonuses
            size_bonus = 0.0
            if social.twitter_followers and social.twitter_followers > 1000:
                size_bonus += 0.1
            if social.telegram_members and social.telegram_members > 500:
                size_bonus += 0.1
                
            final_score = (activity_score * sentiment_multiplier) + size_bonus
            
            return max(0.0, min(1.0, final_score))
            
        except Exception as e:
            self.logger.error(f"Social scoring failed: {e}")
            return 0.3
            
    def _score_liquidity_quality(self, opportunity: TradingOpportunity) -> float:
        """Score liquidity and market structure quality."""
        try:
            liquidity = opportunity.liquidity
            score = 0.5  # Base score
            
            # Chain-specific bonuses
            chain = opportunity.metadata.get('chain', '').upper()
            if 'ETHEREUM' in chain:
                score += 0.2  # Premium for Ethereum
            elif 'BASE' in chain:
                score += 0.3  # Bonus for Base (lower fees)
            elif 'SOLANA' in chain:
                score += 0.1  # Decent for Solana
                
            # DEX quality bonus
            dex_bonuses = {
                'Uniswap V2': 0.2,
                'BaseSwap': 0.15,
                'Solana-Jupiter': 0.1,
                'Pump.fun': 0.05
            }
            
            dex_name = liquidity.dex_name
            if dex_name in dex_bonuses:
                score += dex_bonuses[dex_name]
                
            # Liquidity amount bonus
            if liquidity.liquidity_usd:
                if liquidity.liquidity_usd > 100000:  # $100k+
                    score += 0.2
                elif liquidity.liquidity_usd > 50000:  # $50k+
                    score += 0.15
                elif liquidity.liquidity_usd > 10000:  # $10k+
                    score += 0.1
                    
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            self.logger.error(f"Liquidity scoring failed: {e}")
            return 0.3
            
    def _score_timing_factors(self, opportunity: TradingOpportunity) -> float:
        """Score timing and launch-related factors."""
        try:
            score = 0.5  # Base timing score
            
            # Age of detection (fresher is better for sniping)
            age_minutes = (datetime.now() - opportunity.detected_at).total_seconds() / 60
            
            if age_minutes < 1:      # Very fresh
                score += 0.3
            elif age_minutes < 5:    # Fresh
                score += 0.2
            elif age_minutes < 15:   # Decent
                score += 0.1
            # No bonus for older opportunities
            
            # Block/timing bonuses for different chains
            chain = opportunity.metadata.get('chain', '').upper()
            block_number = opportunity.liquidity.block_number
            
            if 'BASE' in chain and block_number:
                # Base has 2-second blocks, so being very recent matters more
                score += 0.1
                
            # Source quality for Solana
            if 'SOLANA' in chain:
                source = opportunity.metadata.get('solana_source', '')
                if source == 'Pump.fun':
                    score += 0.2  # Real-time launch detection
                elif source == 'Jupiter':
                    score += 0.1  # Verified but not as fresh
                    
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            self.logger.error(f"Timing scoring failed: {e}")
            return 0.5
            
    def generate_recommendation(self, opportunity: TradingOpportunity) -> Dict[str, any]:
        """
        Generate trading recommendation based on analysis.
        
        Args:
            opportunity: The analyzed opportunity
            
        Returns:
            Dictionary with recommendation details
        """
        try:
            score = opportunity.confidence_score or 0.0
            risk_level = opportunity.contract_analysis.risk_level
            
            # Determine recommendation
            if score >= 0.8 and risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
                action = "STRONG BUY"
                confidence = "HIGH"
                position_size = 0.8  # 80% of max position
            elif score >= 0.65 and risk_level != RiskLevel.CRITICAL:
                action = "BUY"
                confidence = "MEDIUM"
                position_size = 0.5  # 50% of max position
            elif score >= 0.45 and risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
                action = "SMALL BUY"
                confidence = "LOW"
                position_size = 0.2  # 20% of max position
            elif score >= 0.3:
                action = "WATCH"
                confidence = "NEUTRAL"
                position_size = 0.0
            else:
                action = "AVOID"
                confidence = "HIGH"
                position_size = 0.0
                
            # Calculate suggested position sizes for different chains
            max_positions = {
                'ETHEREUM': 0.1,   # ETH
                'BASE': 0.5,       # ETH on Base
                'SOLANA': 100      # SOL
            }
            
            chain = opportunity.metadata.get('chain', 'ETHEREUM').upper()
            max_position = max_positions.get(chain, 0.1)
            suggested_position = max_position * position_size
            
            recommendation = {
                'action': action,
                'confidence': confidence,
                'score': score,
                'risk_level': risk_level.value,
                'suggested_position': suggested_position,
                'chain': chain,
                'reasons': self._get_recommendation_reasons(opportunity),
                'warnings': self._get_risk_warnings(opportunity)
            }
            
            return recommendation
            
        except Exception as e:
            self.logger.error(f"Recommendation generation failed: {e}")
            return {
                'action': 'AVOID',
                'confidence': 'HIGH',
                'score': 0.0,
                'risk_level': 'CRITICAL',
                'suggested_position': 0.0,
                'reasons': ['Analysis failed'],
                'warnings': ['Could not analyze token safety']
            }
            
    def _get_recommendation_reasons(self, opportunity: TradingOpportunity) -> List[str]:
        """Get list of reasons supporting the recommendation - Windows compatible."""
        reasons = []
        
        # Contract safety reasons (Windows-safe symbols)
        if opportunity.contract_analysis.ownership_renounced:
            reasons.append("[OK] Ownership renounced")
        if opportunity.contract_analysis.liquidity_locked:
            reasons.append("[OK] Liquidity locked")
        if not opportunity.contract_analysis.is_honeypot:
            reasons.append("[OK] No honeypot detected")
            
        # Social reasons
        if opportunity.social_metrics.social_score > 0.6:
            reasons.append("[OK] Strong social presence")
        if opportunity.social_metrics.sentiment_score > 0.3:
            reasons.append("[OK] Positive sentiment")
            
        # Timing reasons
        age_minutes = (datetime.now() - opportunity.detected_at).total_seconds() / 60
        if age_minutes < 5:
            reasons.append("[OK] Very early detection")
            
        # Chain reasons
        chain = opportunity.metadata.get('chain', '')
        if 'BASE' in chain:
            reasons.append("[OK] Low-fee Base chain")
        elif 'ETHEREUM' in chain:
            reasons.append("[OK] Premium Ethereum chain")
            
        return reasons









    def _get_risk_warnings(self, opportunity: TradingOpportunity) -> List[str]:
        """Get list of risk warnings - Windows compatible."""
        warnings = []
        
        # Contract warnings (Windows-safe symbols)
        if not opportunity.contract_analysis.ownership_renounced:
            warnings.append("[WARN] Owner can control contract")
        if not opportunity.contract_analysis.liquidity_locked:
            warnings.append("[WARN] Liquidity not locked")
        if opportunity.contract_analysis.is_mintable:
            warnings.append("[WARN] Token supply can be increased")
        if opportunity.contract_analysis.is_pausable:
            warnings.append("[WARN] Trading can be paused")
        if opportunity.contract_analysis.has_blacklist:
            warnings.append("[WARN] Addresses can be blacklisted")
            
        # High-level warnings
        if opportunity.contract_analysis.risk_level == RiskLevel.CRITICAL:
            warnings.append("[CRITICAL] CRITICAL RISK - Consider avoiding")
        elif opportunity.contract_analysis.risk_level == RiskLevel.HIGH:
            warnings.append("[WARN] HIGH RISK - Use small position only")
            
        return warnings
    

    def _score_contract_safety_enhanced(self, opportunity: TradingOpportunity) -> float:
        """Enhanced contract safety scoring with more nuanced assessment."""
        try:
            analysis = opportunity.contract_analysis
            score = 1.0  # Start with perfect score
            
            # Critical failures (automatic very low score)
            if analysis.is_honeypot:
                return 0.0  # Honeypot = instant fail
            
            # Major risk factors (heavy penalties)
            risk_penalties = {
                'ownership_not_renounced': 0.4,      # Owner control is major risk
                'liquidity_not_locked': 0.5,        # Rug pull risk
                'blacklist_function': 0.4,          # Can block addresses
                'pause_function': 0.3,              # Can stop trading
                'high_transfer_fees': 0.3,          # >10% fees
            }
            
            # Apply major penalties
            if not analysis.ownership_renounced:
                score -= risk_penalties['ownership_not_renounced']
                
            if not analysis.liquidity_locked:
                score -= risk_penalties['liquidity_not_locked']
                
            if analysis.has_blacklist:
                score -= risk_penalties['blacklist_function']
                
            if analysis.is_pausable:
                score -= risk_penalties['pause_function']
            
            # Medium risk factors
            if analysis.is_mintable:
                score -= 0.2  # Inflation risk
                
            # Dynamic penalties based on risk level
            risk_level_penalties = {
                RiskLevel.LOW: 0.0,
                RiskLevel.MEDIUM: 0.15,
                RiskLevel.HIGH: 0.35,
                RiskLevel.CRITICAL: 0.6
            }
            
            penalty = risk_level_penalties.get(analysis.risk_level, 0.3)
            score -= penalty
            
            # Bonus for verified contracts
            if 'verified' in ' '.join(analysis.analysis_notes).lower():
                score += 0.1
            
            # Age bonus (older contracts are often safer)
            contract_age_days = opportunity.metadata.get('contract_age_days', 0)
            if contract_age_days > 30:
                score += 0.1
            elif contract_age_days > 7:
                score += 0.05
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            self.logger.error(f"Enhanced contract scoring failed: {e}")
            return 0.2

    def _score_liquidity_quality_enhanced(self, opportunity: TradingOpportunity) -> float:
        """Enhanced liquidity scoring with better metrics."""
        try:
            liquidity = opportunity.liquidity
            score = 0.3  # Base score
            
            # Liquidity amount scoring (logarithmic scale)
            if liquidity.liquidity_usd:
                if liquidity.liquidity_usd >= 1000000:     # $1M+
                    score += 0.4
                elif liquidity.liquidity_usd >= 500000:   # $500k+
                    score += 0.35
                elif liquidity.liquidity_usd >= 100000:   # $100k+
                    score += 0.3
                elif liquidity.liquidity_usd >= 50000:    # $50k+
                    score += 0.2
                elif liquidity.liquidity_usd >= 10000:    # $10k+
                    score += 0.1
                else:  # Less than $10k
                    score -= 0.1  # Penalty for low liquidity
            
            # Chain-specific scoring
            chain = opportunity.metadata.get('chain', '').upper()
            chain_bonuses = {
                'ETHEREUM': 0.2,    # Premium chain
                'BASE': 0.25,      # Good liquidity, low fees
                'ARBITRUM': 0.15,   # L2 with good liquidity
                'POLYGON': 0.1,    # Decent but more risky
                'BSC': 0.05,       # Higher risk
                'SOLANA': 0.1      # Fast but different model
            }
            
            for chain_name, bonus in chain_bonuses.items():
                if chain_name in chain:
                    score += bonus
                    break
            
            # DEX reputation scoring
            dex_scores = {
                'Uniswap V2': 0.15,
                'Uniswap V3': 0.2,      # Better capital efficiency
                'SushiSwap': 0.12,
                'PancakeSwap': 0.08,
                'BaseSwap': 0.1,
                'Raydium': 0.1,
                'Jupiter': 0.08,
                'Pump.fun': 0.05        # Bonding curve model
            }
            
            dex_name = liquidity.dex_name
            if dex_name in dex_scores:
                score += dex_scores[dex_name]
            
            # Volume analysis bonus
            volume_24h = opportunity.metadata.get('volume_24h_usd', 0)
            if volume_24h > 0 and liquidity.liquidity_usd > 0:
                volume_ratio = volume_24h / liquidity.liquidity_usd
                if volume_ratio > 2.0:      # High activity
                    score += 0.15
                elif volume_ratio > 0.5:   # Good activity
                    score += 0.1
                elif volume_ratio > 0.1:   # Some activity
                    score += 0.05
            
            # Penalty for suspicious liquidity patterns
            if liquidity.liquidity_usd and liquidity.liquidity_usd < 5000:
                score -= 0.2  # Very low liquidity penalty
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            self.logger.error(f"Enhanced liquidity scoring failed: {e}")
            return 0.3

    def generate_recommendation_enhanced(self, opportunity: TradingOpportunity) -> Dict[str, any]:
        """Enhanced recommendation generation with better thresholds."""
        try:
            score = opportunity.confidence_score or 0.0
            risk_level = opportunity.contract_analysis.risk_level
            
            # More nuanced recommendation logic
            if score >= 0.85 and risk_level == RiskLevel.LOW:
                action = "STRONG_BUY"
                confidence = "HIGH"
                position_size = 0.8
            elif score >= 0.75 and risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
                action = "BUY"
                confidence = "HIGH"
                position_size = 0.6
            elif score >= 0.65 and risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
                action = "BUY"
                confidence = "MEDIUM"
                position_size = 0.4
            elif score >= 0.55 and risk_level == RiskLevel.LOW:
                action = "SMALL_BUY"
                confidence = "MEDIUM"
                position_size = 0.2
            elif score >= 0.45 and risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
                action = "SMALL_BUY"
                confidence = "LOW"
                position_size = 0.1
            elif score >= 0.35:
                action = "WATCH"
                confidence = "NEUTRAL"
                position_size = 0.0
            else:
                action = "AVOID"
                confidence = "HIGH"
                position_size = 0.0
            
            # Risk level overrides
            if risk_level == RiskLevel.CRITICAL:
                action = "AVOID"
                confidence = "HIGH"
                position_size = 0.0
            elif risk_level == RiskLevel.HIGH and action in ["STRONG_BUY", "BUY"]:
                action = "SMALL_BUY"  # Downgrade
                position_size *= 0.5   # Reduce position
            
            # Calculate position size by chain
            chain_configs = {
                'ETHEREUM': {'max': 0.1, 'unit': 'ETH'},
                'BASE': {'max': 0.5, 'unit': 'ETH'},
                'ARBITRUM': {'max': 0.3, 'unit': 'ETH'},
                'SOLANA': {'max': 100, 'unit': 'SOL'},
                'BSC': {'max': 1.0, 'unit': 'BNB'},
                'POLYGON': {'max': 500, 'unit': 'MATIC'}
            }
            
            chain = opportunity.metadata.get('chain', 'ETHEREUM').upper()
            chain_config = chain_configs.get(chain, chain_configs['ETHEREUM'])
            
            suggested_position = chain_config['max'] * position_size
            
            recommendation = {
                'action': action,
                'confidence': confidence,
                'score': score,
                'risk_level': risk_level.value,
                'suggested_position': suggested_position,
                'position_unit': chain_config['unit'],
                'chain': chain,
                'reasons': self._get_recommendation_reasons_enhanced(opportunity),
                'warnings': self._get_risk_warnings_enhanced(opportunity),
                'analysis_quality': self._assess_analysis_quality(opportunity)
            }
            
            return recommendation
            
        except Exception as e:
            self.logger.error(f"Enhanced recommendation generation failed: {e}")
            return self._get_safe_default_recommendation()

    def _assess_analysis_quality(self, opportunity: TradingOpportunity) -> str:
        """Assess the quality of the analysis performed."""
        quality_score = 0
        
        # Check if contract analysis was thorough
        if opportunity.contract_analysis.analysis_notes:
            quality_score += 1
        
        # Check if social analysis has real data
        if opportunity.social_metrics.twitter_followers > 0:
            quality_score += 1
        if opportunity.social_metrics.telegram_members > 0:
            quality_score += 1
        
        # Check if liquidity analysis is comprehensive
        if opportunity.liquidity.liquidity_usd > 0:
            quality_score += 1
        
        if quality_score >= 3:
            return "HIGH"
        elif quality_score >= 2:
            return "MEDIUM"
        else:
            return "LOW"




# Example usage of the analysis system
if __name__ == "__main__":
    """
    Example of how the Phase 2 analysis system would be integrated.
    """
    print("Phase 2: Contract Analysis + Trading Intelligence")
    print("=" * 50)
    print("Components:")
    print("1. ContractAnalyzer - Security and honeypot detection")
    print("2. SocialAnalyzer - Community sentiment analysis") 
    print("3. TradingScorer - Opportunity scoring and recommendations")
    print()
    print("Integration points:")
    print("- Analyzes each detected opportunity from Phase 1.5")
    print("- Provides risk assessment and trading recommendations")
    print("- Generates actionable intelligence for decision making")