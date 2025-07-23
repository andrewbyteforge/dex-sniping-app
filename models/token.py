# models/token.py
"""
Data models for representing tokens and trading opportunities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

class TokenStatus(Enum):
    """Status of a detected token."""
    DETECTED = "detected"
    ANALYZING = "analyzing"
    APPROVED = "approved"
    REJECTED = "rejected"
    TRADING = "trading"
    COMPLETED = "completed"
    ERROR = "error"

class RiskLevel(Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class TokenInfo:
    """Basic token information."""
    address: str
    symbol: Optional[str] = None
    name: Optional[str] = None
    decimals: Optional[int] = None
    total_supply: Optional[int] = None
    
    def __post_init__(self):
        """Validate token address format."""
        if not self.address or len(self.address) != 42 or not self.address.startswith('0x'):
            raise ValueError(f"Invalid token address: {self.address}")

@dataclass
class LiquidityInfo:
    """Liquidity pool information."""
    pair_address: str
    dex_name: str
    token0: str
    token1: str
    reserve0: float
    reserve1: float
    liquidity_usd: float
    created_at: datetime
    block_number: int
    
@dataclass
class ContractAnalysis:
    """Results of smart contract analysis."""
    is_honeypot: bool = False
    is_mintable: bool = False
    is_pausable: bool = False
    has_blacklist: bool = False
    ownership_renounced: bool = False
    liquidity_locked: bool = False
    lock_duration: Optional[int] = None  # seconds
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.MEDIUM
    analysis_notes: List[str] = field(default_factory=list)

@dataclass
class SocialMetrics:
    """Social media and community metrics."""
    twitter_followers: Optional[int] = None
    telegram_members: Optional[int] = None
    discord_members: Optional[int] = None
    reddit_subscribers: Optional[int] = None
    website_url: Optional[str] = None
    social_score: float = 0.0
    sentiment_score: float = 0.0  # -1 to 1
    
@dataclass
class TradingOpportunity:
    """Represents a potential trading opportunity."""
    token: TokenInfo
    liquidity: LiquidityInfo
    contract_analysis: ContractAnalysis
    social_metrics: SocialMetrics
    
    # Metadata
    detected_at: datetime = field(default_factory=datetime.now)
    status: TokenStatus = TokenStatus.DETECTED
    confidence_score: float = 0.0
    
    # Trading parameters
    recommended_position_size: float = 0.0
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    
    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_confidence_score(self) -> float:
        """Calculate overall confidence score for this opportunity."""
        try:
            score = 0.0
            factors = 0
            
            # Liquidity factor (0-30 points)
            if self.liquidity.liquidity_usd > 10000:
                score += 30
            elif self.liquidity.liquidity_usd > 5000:
                score += 20
            elif self.liquidity.liquidity_usd > 1000:
                score += 10
            factors += 1
            
            # Contract safety factor (0-40 points)
            safety_score = 40
            if self.contract_analysis.is_honeypot:
                safety_score -= 40
            if self.contract_analysis.is_mintable:
                safety_score -= 10
            if self.contract_analysis.has_blacklist:
                safety_score -= 15
            if not self.contract_analysis.ownership_renounced:
                safety_score -= 10
            if not self.contract_analysis.liquidity_locked:
                safety_score -= 15
                
            score += max(0, safety_score)
            factors += 1
            
            # Social factor (0-30 points)
            social_score = self.social_metrics.social_score
            if social_score > 0.8:
                score += 30
            elif social_score > 0.6:
                score += 20
            elif social_score > 0.4:
                score += 10
            factors += 1
            
            # Normalize to 0-1 range
            self.confidence_score = score / 100.0
            return self.confidence_score
            
        except Exception as e:
            # If calculation fails, return low confidence
            self.confidence_score = 0.1
            return self.confidence_score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'token_address': self.token.address,
            'token_symbol': self.token.symbol,
            'token_name': self.token.name,
            'pair_address': self.liquidity.pair_address,
            'dex_name': self.liquidity.dex_name,
            'liquidity_usd': self.liquidity.liquidity_usd,
            'detected_at': self.detected_at.isoformat(),
            'status': self.status.value,
            'confidence_score': self.confidence_score,
            'risk_level': self.contract_analysis.risk_level.value,
            'is_honeypot': self.contract_analysis.is_honeypot,
            'liquidity_locked': self.contract_analysis.liquidity_locked,
            'social_score': self.social_metrics.social_score,
        }
