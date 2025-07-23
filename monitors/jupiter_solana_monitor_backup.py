# monitors/jupiter_solana_monitor.py
"""
Alternative Solana monitor using Jupiter API instead of Pump.fun.
Bypasses overloaded Pump.fun API while still detecting new Solana tokens.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from models.token import LiquidityInfo, TradingOpportunity, ContractAnalysis, SocialMetrics
from monitors.base_monitor import BaseMonitor

class JupiterSolanaMonitor(BaseMonitor):
    """
    Alternative Solana monitor using Jupiter API and direct Solana RPC.
    Works around Pump.fun API overload issues.
    """
    
    def __init__(self, check_interval: float = 3.0):  # Slower to be respectful
        """Initialize the Jupiter-based Solana monitor."""
        super().__init__("JupiterSolana", check_interval)
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_tokens: set = set()
        
        # Jupiter and Solana endpoints
        self.jupiter_api = "https://quote-api.jup.ag/v6"
        self.solana_rpc = "https://api.mainnet-beta.solana.com"
        self.birdeye_api = "https://public-api.birdeye.so/defi"
        
        # Well-known Solana tokens to filter against
        self.known_tokens = {
            "So11111111111111111111111111111111111111112",  # SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
        }
        
    async def _initialize(self) -> None:
        """Initialize Jupiter connections."""
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Test Jupiter connection
            await self._test_jupiter_connection()
            
            self.logger.info("Connected to Jupiter Solana ecosystem")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Jupiter Solana: {e}")
            raise
            
    async def _test_jupiter_connection(self) -> None:
        """Test Jupiter API connection."""
        try:
            # Simple health check with a basic quote
            url = f"{self.jupiter_api}/quote"
            params = {
                "inputMint": "So11111111111111111111111111111111111111112",  # SOL
                "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                "amount": "1000000000"  # 1 SOL
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    self.logger.info("Jupiter API connection successful")
                else:
                    self.logger.warning(f"Jupiter API returned status {response.status}")
                    
        except Exception as e:
            self.logger.warning(f"Jupiter API test failed: {e}")
            
    async def _check(self) -> None:
        """Check for new tokens using Jupiter and alternative sources."""
        try:
            # Method 1: Check new tokens via Birdeye (alternative to Pump.fun)
            await self._check_birdeye_new_tokens()
            
            # Method 2: Monitor Jupiter token list for new additions
            await self._check_jupiter_token_updates()
            
        except Exception as e:
            self.logger.error(f"Error during Jupiter Solana check: {e}")
            raise
            
    async def _check_birdeye_new_tokens(self) -> None:
        """Check Birdeye API for newly listed tokens with improved error handling."""
        try:
            url = f"{self.birdeye_api}/tokenlist"
            params = {
                "sort_by": "v24hUSD",
                "sort_type": "desc", 
                "offset": 0,
                "limit": 50
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 401:
                    # API key required or invalid - disable this source temporarily
                    self.logger.debug("Birdeye API requires authentication (401) - skipping for now")
                    return
                elif response.status == 429:
                    # Rate limited
                    self.logger.debug("Birdeye API rate limited (429) - backing off")
                    await asyncio.sleep(10)
                    return
                elif response.status != 200:
                    self.logger.debug(f"Birdeye API returned {response.status}")
                    return
                    
                data = await response.json()
                tokens = data.get('data', {}).get('tokens', [])
                
                new_tokens = []
                for token in tokens:
                    token_address = token.get('address')
                    
                    if not token_address or token_address in self.processed_tokens:
                        
                    if token_address in self.known_tokens:
                        
                    # Check if token is relatively new (high volume but recent)
                    volume_24h = token.get('v24hUSD', 0)
                    if volume_24h > 10000:  # Active token with volume
                        new_tokens.append(token)
                        self.processed_tokens.add(token_address)
                        
                if new_tokens:
                    self.logger.info(f"Found {len(new_tokens)} active Solana tokens via Birdeye")
                    
                for token_data in new_tokens:
                # Filter out known tokens
                symbol = token_data.get("symbol", "")
                name = token_data.get("name", "")
                if self.should_skip_token(symbol, name):
                    continue
                    # Skip well-known tokens
                    symbol = token_data.get("symbol", "").upper()
                    if symbol in self.known_tokens:
                        continue
                
                # Skip wrapped/bridge tokens
                name = token_data.get("name", "").lower()
                if any(pattern in name for pattern in self.skip_patterns):
                
                # Skip if already in watchlist
                try:
                    from models.watchlist import watchlist_manager
                    if watchlist_manager.is_in_watchlist(symbol):
                        self.logger.debug(f"Skipping {symbol} - already in watchlist")
                except:
                    pass
                await self._process_solana_token(token_data, "Birdeye")
                    
        except asyncio.TimeoutError:
            self.logger.debug("Birdeye API timeout - retrying next cycle")
        except aiohttp.ClientError as e:
            self.logger.debug(f"Birdeye API connection error: {e}")
        except Exception as e:
            self.logger.debug(f"Birdeye check failed: {e}")










    async def _check_jupiter_token_updates(self) -> None:
        """Monitor Jupiter for token list updates."""
        try:
            # Get Jupiter's strict token list (verified tokens)
            url = "https://token.jup.ag/strict"
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    return
                    
                tokens = await response.json()
                
                # Look for tokens not in our processed set
                new_tokens = []
                for token in tokens[-10:]:  # Check last 10 tokens (most recent)
                    token_address = token.get('address')
                    
                    if token_address and token_address not in self.processed_tokens:
                        if token_address not in self.known_tokens:
                            new_tokens.append(token)
                            self.processed_tokens.add(token_address)
                            
                if new_tokens:
                    self.logger.info(f"Found {len(new_tokens)} new verified tokens via Jupiter")
                    
                for token_data in new_tokens:
                # Filter out known tokens
                symbol = token_data.get("symbol", "")
                name = token_data.get("name", "")
                if self.should_skip_token(symbol, name):
                    continue
                    # Skip well-known tokens
                    symbol = token_data.get("symbol", "").upper()
                    if symbol in self.known_tokens:
                        continue
                    
                # Skip wrapped/bridge tokens
                name = token_data.get("name", "").lower()
                if any(pattern in name for pattern in self.skip_patterns):
                
                # Skip if already in watchlist
                try:
                    from models.watchlist import watchlist_manager
                    if watchlist_manager.is_in_watchlist(symbol):
                        self.logger.debug(f"Skipping {symbol} - already in watchlist")
                except:
                    pass
                await self._process_solana_token(token_data, "Jupiter")
                    
        except Exception as e:
            self.logger.debug(f"Jupiter token list check failed: {e}")
            
    async def _process_solana_token(self, token_data: Dict[str, Any], source: str) -> None:
        """Process a detected Solana token."""
        try:
            token_address = token_data.get('address')
            name = token_data.get('name', 'Unknown')
            symbol = token_data.get('symbol', 'UNKNOWN')
            
            # Get additional data based on source
            if source == "Birdeye":
                decimals = token_data.get('decimals', 6)
                market_cap = token_data.get('mc', 0)
                volume_24h = token_data.get('v24hUSD', 0)
                price = token_data.get('price', 0)
            else:  # Jupiter
                decimals = token_data.get('decimals', 6)
                market_cap = 0
                volume_24h = 0
                price = 0
                
            self.logger.info(f"Processing Solana token from {source}: {symbol} ({token_address})")
            
            # Create token info (bypass Ethereum validation for Solana addresses)
            token_info = type('SolanaToken', (), {
                'address': token_address,
                'symbol': symbol,
                'name': name,
                'decimals': decimals,
                'total_supply': 1000000000 * (10 ** decimals)
            })()
            
            # Create liquidity info
            liquidity_info = LiquidityInfo(
                pair_address=token_address,  # Solana uses the token address
                dex_name=f"Solana-{source}",
                token0=token_address,
                token1="So11111111111111111111111111111111111111112",  # SOL
                reserve0=0.0,
                reserve1=0.0,
                liquidity_usd=market_cap,
                created_at=datetime.now(),
                block_number=0
            )
            
            # Create social metrics
            social_metrics = SocialMetrics(
                social_score=min(volume_24h / 100000.0, 1.0) if volume_24h else 0.5,
                sentiment_score=0.5
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
                'platform': source,
                'market_cap_usd': market_cap,
                'volume_24h_usd': volume_24h,
                'price_usd': price,
                'source': f"{source} API"
            })
            
            await self._notify_callbacks(opportunity)
            
        except Exception as e:
            self.logger.error(f"Error processing Solana token from {source}: {e}")
            
    async def _cleanup(self) -> None:
        """Cleanup Jupiter resources."""
        if self.session:
            await self.session.close()
            self.session = None
            
        self.logger.info("Jupiter Solana monitor cleanup completed")