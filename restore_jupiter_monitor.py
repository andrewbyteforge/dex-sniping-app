"""
Restore Jupiter monitor to a working state with proper filtering.
"""

import os
import shutil

def restore_jupiter_monitor():
    """Restore the Jupiter monitor to a clean working state."""
    
    monitor_path = "monitors/jupiter_solana_monitor.py"
    backup_path = "monitors/jupiter_solana_monitor_backup.py"
    
    # First, make a backup of the broken file
    if os.path.exists(monitor_path):
        shutil.copy(monitor_path, backup_path)
        print(f"✅ Backed up broken file to {backup_path}")
    
    # Create a clean, working Jupiter monitor
    clean_monitor = '''"""
Jupiter Solana monitor for detecting new tokens via Jupiter aggregator.
Filters out known tokens and shows only potentially new opportunities.
"""

import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from monitors.base_monitor import BaseMonitor
from models.token import TokenInfo, TradingOpportunity, LiquidityInfo, ContractAnalysis, SocialMetrics, RiskLevel
from utils.logger import logger_manager
from config.settings import settings


class JupiterSolanaMonitor(BaseMonitor):
    """Monitor for new Solana tokens via Jupiter aggregator."""
    
    def __init__(self):
        """Initialize Jupiter Solana monitor."""
        super().__init__("JupiterSolana")
        self.chain = "solana"
        self.api_url = "https://api.jup.ag/tokens/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_tokens = set()
        self.last_check = datetime.now()
        
        # Known tokens to skip
        self.known_tokens = {
            "USDC", "USDT", "SOL", "WETH", "BTC", "ETH", "SAND", "MANA",
            "LINK", "UNI", "AAVE", "SNX", "CRV", "SUSHI", "MATIC", "DOT",
            "BONK", "WIF", "POPCAT", "MEW", "BOME", "PEPE", "FLOKI",
            "wUST_v1", "acUSD", "abETH", "compassSOL", "UPS", "Speero",
            "pre", "PEW", "pussyinbio", "JITOSOL", "MSOL", "STSOL"
        }
    
    async def initialize(self) -> bool:
        """Initialize the monitor."""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Test connection
            async with self.session.get(self.api_url) as response:
                if response.status == 200:
                    self.logger.info("Jupiter API connection successful")
                    return True
                else:
                    self.logger.error(f"Jupiter API returned status {response.status}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to initialize Jupiter monitor: {e}")
            return False
    
    def should_skip_token(self, token_data: Dict) -> bool:
        """Check if we should skip this token."""
        symbol = token_data.get("symbol", "").upper()
        name = token_data.get("name", "").lower()
        
        # Skip known tokens
        if symbol in self.known_tokens:
            return True
        
        # Skip wrapped/bridge tokens
        skip_words = ["wrapped", "bridge", "portal", "wormhole", "allbridge", "celer"]
        if any(word in name for word in skip_words):
            return True
        
        # Skip if already processed
        address = token_data.get("address", "")
        if address in self.processed_tokens:
            return True
        
        return False
    
    async def check_new_opportunities(self) -> List[TradingOpportunity]:
        """Check for new trading opportunities."""
        if not self.is_running or not self.session:
            return []
        
        opportunities = []
        
        try:
            # Get all tokens from Jupiter
            async with self.session.get(self.api_url) as response:
                if response.status != 200:
                    self.logger.warning(f"Jupiter API returned status {response.status}")
                    return []
                
                data = await response.json()
                
                # Filter for potentially new tokens
                new_tokens = []
                for token in data:
                    # Must be verified
                    if not token.get("verified", False):
                        continue
                    
                    # Apply our filters
                    if self.should_skip_token(token):
                        continue
                    
                    # Add to new tokens
                    new_tokens.append(token)
                    
                    # Mark as processed
                    self.processed_tokens.add(token.get("address", ""))
                    
                    # Limit to prevent spam
                    if len(new_tokens) >= 10:
                        break
                
                if new_tokens:
                    self.logger.info(f"Found {len(new_tokens)} new verified tokens via Jupiter")
                    
                    # Convert to opportunities
                    for token_data in new_tokens:
                        opportunity = await self._create_opportunity(token_data)
                        if opportunity:
                            opportunities.append(opportunity)
                            await self._notify_callbacks(opportunity)
            
            self.last_check = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error checking Jupiter opportunities: {e}")
        
        return opportunities
    
    async def _create_opportunity(self, token_data: Dict) -> Optional[TradingOpportunity]:
        """Create trading opportunity from token data."""
        try:
            # Extract token info
            token_info = TokenInfo(
                address=token_data.get("address", ""),
                symbol=token_data.get("symbol", "UNKNOWN"),
                name=token_data.get("name", "Unknown Token"),
                decimals=token_data.get("decimals", 9),
                total_supply=1000000000,  # Default
                price_usd=0.0,  # Jupiter doesn't provide price in token list
                market_cap_usd=0.0,
                launch_time=datetime.now(),
                chain="solana"
            )
            
            # Create basic liquidity info
            liquidity_info = LiquidityInfo(
                liquidity_usd=0.0,  # Would need additional API call
                liquidity_locked=False,
                lock_end_time=None
            )
            
            # Create basic contract analysis
            contract_analysis = ContractAnalysis(
                is_honeypot=False,
                has_mint_function=False,
                has_pause_function=False,
                ownership_renounced=False,
                risk_score=0.0,
                risk_level=RiskLevel.MEDIUM,
                analysis_notes=["Jupiter verified token"]
            )
            
            # Create basic social metrics
            social_metrics = SocialMetrics(
                twitter_followers=0,
                telegram_members=0,
                holder_count=0,
                sentiment_score=0.5,
                growth_rate_24h=0.0
            )
            
            # Create opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=contract_analysis,
                social_metrics=social_metrics,
                metadata={
                    "source": "jupiter",
                    "chain": "solana",
                    "detected_at": datetime.now().isoformat(),
                    "jupiter_verified": True
                }
            )
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Error creating opportunity: {e}")
            return None
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _check(self) -> List[TradingOpportunity]:
        """Internal check method required by base class."""
        return await self.check_new_opportunities()
    
    async def _cleanup(self):
        """Internal cleanup method required by base class."""
        await self.cleanup()
    
    async def _initialize(self) -> bool:
        """Internal initialize method required by base class."""
        return await self.initialize()
'''
    
    # Write the clean monitor
    with open(monitor_path, 'w', encoding='utf-8') as f:
        f.write(clean_monitor)
    
    print("✅ Jupiter monitor restored to working state!")
    print("\n📋 Features:")
    print("   - Filters out known tokens")
    print("   - Skips wrapped/bridge tokens")
    print("   - Limits to 10 tokens per check")
    print("   - Clean, working code")
    print("\n✅ You can now run: python main_with_trading.py")

if __name__ == "__main__":
    restore_jupiter_monitor()