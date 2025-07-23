# monitors/solana_monitor.py
"""
Solana monitor for detecting new token launches on Pump.fun and Raydium.
Focuses on the high-volume meme coin ecosystem.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import base58

from models.token import TokenInfo, LiquidityInfo, TradingOpportunity, ContractAnalysis, SocialMetrics
from monitors.base_monitor import BaseMonitor
from config.chains import multichain_settings

class SolanaMonitor(BaseMonitor):
    """
    Monitor for detecting new token launches on Solana ecosystem.
    Focuses on Pump.fun for new token detection and Raydium for DEX pairs.
    """
    
    def __init__(self, check_interval: float = 1.0):  # Very fast for Solana
        """Initialize the Solana monitor."""
        super().__init__("Solana", check_interval)
        
        self.solana_config = multichain_settings.solana
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_tokens: set = set()
        self.last_check_time = datetime.now()
        
    async def _initialize(self) -> None:
        """Initialize Solana connections."""
        try:
            # Initialize HTTP session
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Test connection to Pump.fun API
            await self._test_pump_fun_connection()
            
            self.logger.info("Connected to Solana ecosystem")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Solana: {e}")
            raise
            
    async def _test_pump_fun_connection(self) -> None:
        """Test connection to Pump.fun API."""
        try:
            # Test endpoint - get recent tokens
            url = f"{self.solana_config.pump_fun_api}/coins"
            async with self.session.get(url, params={'limit': 1}) as response:
                if response.status == 200:
                    self.logger.info("Pump.fun API connection successful")
                else:
                    self.logger.warning(f"Pump.fun API returned status {response.status}")
        except Exception as e:
            self.logger.warning(f"Pump.fun API test failed: {e}")
            
    async def _check(self) -> None:
        """Check for new tokens on Solana."""
        try:
            # Check Pump.fun for new token launches
            await self._check_pump_fun_tokens()
            
            # Could also check Raydium, Jupiter, etc.
            # await self._check_raydium_pairs()
            
        except Exception as e:
            self.logger.error(f"Error during Solana check: {e}")
            raise
            
    async def _check_pump_fun_tokens(self) -> None:
        """Check Pump.fun for newly launched tokens with better error handling."""
        try:
            url = f"{self.solana_config.pump_fun_api}/coins"
            params = {
                'limit': 20,
                'sort': 'created_timestamp',
                'order': 'desc'
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 530:
                    # Rate limited - reduce frequency temporarily
                    self.logger.debug("Pump.fun API rate limited (530) - backing off")
                    await asyncio.sleep(5)  # Wait 5 seconds before next attempt
                    return
                elif response.status == 503:
                    # Service unavailable - temporary issue
                    self.logger.debug("Pump.fun API temporarily unavailable (503)")
                    return
                elif response.status != 200:
                    self.logger.warning(f"Pump.fun API returned {response.status}")
                    return
                    
                data = await response.json()
                
                if not data or 'coins' not in data:
                    return
                    
                coins = data['coins']
                new_tokens = []
                
                for coin in coins:
                    token_address = coin.get('mint')
                    created_timestamp = coin.get('created_timestamp', 0)
                    
                    if not token_address or token_address in self.processed_tokens:
                        continue
                        
                    # Only process tokens created in the last few minutes
                    created_time = datetime.fromtimestamp(created_timestamp / 1000)
                    if (datetime.now() - created_time).total_seconds() > 300:  # 5 minutes
                        continue
                        
                    new_tokens.append(coin)
                    self.processed_tokens.add(token_address)
                    
                if new_tokens:
                    self.logger.info(f"Found {len(new_tokens)} new Pump.fun tokens")
                    
                for token_data in new_tokens:
                    await self._process_pump_fun_token(token_data)
                    
        except asyncio.TimeoutError:
            self.logger.debug("Pump.fun API timeout - retrying next cycle")
        except aiohttp.ClientError as e:
            self.logger.debug(f"Pump.fun API connection error: {e}")
        except Exception as e:
            self.logger.error(f"Error checking Pump.fun: {e}")






    async def _process_pump_fun_token(self, token_data: Dict[str, Any]) -> None:
        """Process a new Pump.fun token."""
        try:
            # Extract token information
            token_address = token_data.get('mint')
            name = token_data.get('name', 'Unknown')
            symbol = token_data.get('symbol', 'UNKNOWN')
            description = token_data.get('description', '')
            created_timestamp = token_data.get('created_timestamp', 0)
            
            # Additional Pump.fun specific data
            market_cap = token_data.get('usd_market_cap', 0)
            reply_count = token_data.get('reply_count', 0)
            creator = token_data.get('creator', '')
            
            self.logger.info(f"Processing Pump.fun token: {symbol} ({token_address})")
            
            # Create token info
            token_info = TokenInfo(
                address=token_address,
                symbol=symbol,
                name=name,
                decimals=6,  # Standard for Pump.fun tokens
                total_supply=1000000000  # Standard Pump.fun supply
            )
            
            # Create liquidity info (Pump.fun uses bonding curves)
            liquidity_info = LiquidityInfo(
                pair_address=token_address,  # No traditional pair on Pump.fun
                dex_name="Pump.fun",
                token0=token_address,
                token1=self.solana_config.wsol_address,  # Paired with SOL
                reserve0=0.0,
                reserve1=0.0,
                liquidity_usd=market_cap,
                created_at=datetime.fromtimestamp(created_timestamp / 1000),
                block_number=0  # Solana doesn't use block numbers the same way
            )
            
            # Create social metrics from Pump.fun data
            social_metrics = SocialMetrics(
                social_score=min(reply_count / 10.0, 1.0),  # Normalize replies to 0-1
                sentiment_score=0.5  # Neutral until we analyze
            )
            
            # Create opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=ContractAnalysis(),
                social_metrics=social_metrics
            )
            
            # Add Solana-specific metadata
            opportunity.metadata.update({
                'chain': 'Solana',
                'platform': 'Pump.fun',
                'market_cap_usd': market_cap,
                'reply_count': reply_count,
                'creator': creator,
                'description': description[:100] + '...' if len(description) > 100 else description
            })
            
            await self._notify_callbacks(opportunity)
            
        except Exception as e:
            self.logger.error(f"Error processing Pump.fun token: {e}")
            
    async def _cleanup(self) -> None:
        """Cleanup Solana resources."""
        if self.session:
            await self.session.close()
            self.session = None
            
        self.logger.info("Solana monitor cleanup completed")