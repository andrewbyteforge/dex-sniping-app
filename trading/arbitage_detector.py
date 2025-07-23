"""
Cross-DEX arbitrage detection and execution.
Finds price discrepancies across DEXs and calculates profitable opportunities.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio

from trading.dex_manager import DEXManager
from utils.logger import logger_manager


class ArbitrageType(Enum):
    """Types of arbitrage opportunities."""
    SIMPLE = "simple"        # Buy on DEX A, sell on DEX B
    TRIANGULAR = "triangular"  # A->B->C->A arbitrage
    FLASH_LOAN = "flash_loan"  # Using flash loans for capital


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity."""
    id: str
    type: ArbitrageType
    token_address: str
    token_symbol: str
    chain: str
    
    # DEX information
    buy_dex: str
    sell_dex: str
    
    # Prices and amounts
    buy_price: Decimal
    sell_price: Decimal
    price_difference_percent: float
    optimal_amount: Decimal
    
    # Profitability
    gross_profit: Decimal
    gas_cost: Decimal
    net_profit: Decimal
    roi_percent: float
    
    # Additional info
    detected_at: datetime
    expires_at: Optional[datetime] = None
    confidence: float = 0.0
    notes: List[str] = None


@dataclass
class TriangularPath:
    """Represents a triangular arbitrage path."""
    token_a: str
    token_b: str
    token_c: str
    dex_ab: str
    dex_bc: str
    dex_ca: str
    expected_profit: Decimal


class ArbitrageDetector:
    """
    Detects and analyzes cross-DEX arbitrage opportunities.
    Monitors price differences and calculates optimal trade sizes.
    """
    
    def __init__(self, dex_manager: DEXManager) -> None:
        """
        Initialize arbitrage detector.
        
        Args:
            dex_manager: DEX manager instance
        """
        self.logger = logger_manager.get_logger("ArbitrageDetector")
        self.dex_manager = dex_manager
        
        # Configuration
        self.min_profit_threshold = Decimal("50")  # $50 minimum profit
        self.max_price_impact = 0.02  # 2% max price impact
        self.gas_buffer = 1.2  # 20% gas buffer
        
        # Tracking
        self.active_opportunities: Dict[str, ArbitrageOpportunity] = {}
        self.price_cache: Dict[str, Dict[str, Decimal]] = {}
        self.last_check: Dict[str, datetime] = {}
        
    async def find_arbitrage_opportunities(
        self,
        token_address: str,
        chain: str,
        amount_eth: Decimal = Decimal("1.0")
    ) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities for a token across DEXs.
        
        Args:
            token_address: Token to check
            chain: Chain to check on
            amount_eth: Test amount in ETH
            
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        try:
            # Get available DEXs for chain
            available_dexs = list(self.dex_manager.ROUTERS.get(chain, {}).keys())
            
            if len(available_dexs) < 2:
                return opportunities  # Need at least 2 DEXs
            
            # Get prices from all DEXs
            prices = await self._get_prices_all_dexs(
                token_address, chain, amount_eth
            )
            
            # Find arbitrage opportunities
            for buy_dex in available_dexs:
                for sell_dex in available_dexs:
                    if buy_dex == sell_dex:
                        continue
                    
                    buy_price = prices.get(buy_dex)
                    sell_price = prices.get(sell_dex)
                    
                    if not buy_price or not sell_price:
                        continue
                    
                    # Check if profitable
                    if sell_price > buy_price:
                        opp = await self._analyze_opportunity(
                            token_address,
                            chain,
                            buy_dex,
                            sell_dex,
                            buy_price,
                            sell_price,
                            amount_eth
                        )
                        
                        if opp and opp.net_profit > self.min_profit_threshold:
                            opportunities.append(opp)
            
            # Sort by profit
            opportunities.sort(key=lambda x: x.net_profit, reverse=True)
            
            # Cache results
            self._cache_opportunities(opportunities)
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Arbitrage detection failed: {e}")
            return opportunities
    
    async def find_triangular_arbitrage(
        self,
        chain: str,
        base_amount: Decimal = Decimal("1.0")
    ) -> List[TriangularPath]:
        """
        Find triangular arbitrage opportunities.
        
        Args:
            chain: Chain to check on
            base_amount: Starting amount in ETH
            
        Returns:
            List of triangular arbitrage paths
        """
        paths = []
        
        try:
            # Common tokens for triangular arbitrage
            weth = self.dex_manager.WETH[chain]
            
            # Get popular tokens (would be from config or API)
            popular_tokens = self._get_popular_tokens(chain)
            
            # Check triangular paths
            for token_b in popular_tokens:
                for token_c in popular_tokens:
                    if token_b == token_c:
                        continue
                    
                    # Check WETH -> B -> C -> WETH
                    profit = await self._check_triangular_path(
                        chain,
                        weth,
                        token_b,
                        token_c,
                        base_amount
                    )
                    
                    if profit > self.min_profit_threshold:
                        paths.append(TriangularPath(
                            token_a=weth,
                            token_b=token_b,
                            token_c=token_c,
                            dex_ab="uniswap_v2",  # Would optimize
                            dex_bc="uniswap_v2",
                            dex_ca="uniswap_v2",
                            expected_profit=profit
                        ))
            
            return paths
            
        except Exception as e:
            self.logger.error(f"Triangular arbitrage detection failed: {e}")
            return paths
    
    async def _get_prices_all_dexs(
        self,
        token_address: str,
        chain: str,
        amount_eth: Decimal
    ) -> Dict[str, Decimal]:
        """Get token prices from all available DEXs."""
        prices = {}
        
        available_dexs = list(self.dex_manager.ROUTERS.get(chain, {}).keys())
        weth = self.dex_manager.WETH[chain]
        path = [weth, token_address]
        
        # Get prices concurrently
        tasks = []
        for dex in available_dexs:
            task = self.dex_manager.get_amounts_out(
                amount_eth, path, chain, dex
            )
            tasks.append((dex, task))
        
        # Gather results
        for dex, task in tasks:
            try:
                amounts = await task
                if amounts and len(amounts) > 1:
                    # Price = ETH in / Tokens out
                    token_amount = amounts[-1]
                    if token_amount > 0:
                        price = amount_eth / token_amount
                        prices[dex] = price
            except Exception as e:
                self.logger.debug(f"Price fetch failed for {dex}: {e}")
        
        return prices
    
    async def _analyze_opportunity(
        self,
        token_address: str,
        chain: str,
        buy_dex: str,
        sell_dex: str,
        buy_price: Decimal,
        sell_price: Decimal,
        test_amount: Decimal
    ) -> Optional[ArbitrageOpportunity]:
        """Analyze a potential arbitrage opportunity."""
        try:
            # Calculate price difference
            price_diff_percent = float(
                (sell_price - buy_price) / buy_price * 100
            )
            
            if price_diff_percent < 1.0:  # Less than 1% difference
                return None
            
            # Estimate optimal amount (would use more sophisticated calculation)
            optimal_amount = await self._calculate_optimal_amount(
                token_address, chain, buy_dex, sell_dex, test_amount
            )
            
            # Calculate expected profit
            tokens_bought = optimal_amount / buy_price
            eth_received = tokens_bought * sell_price
            gross_profit = eth_received - optimal_amount
            
            # Estimate gas costs
            gas_cost = await self._estimate_gas_cost(chain)
            net_profit = gross_profit - gas_cost
            
            if net_profit <= 0:
                return None
            
            # Calculate ROI
            roi_percent = float(net_profit / optimal_amount * 100)
            
            # Create opportunity
            opp_id = f"{token_address[:8]}_{buy_dex}_{sell_dex}_{int(datetime.now().timestamp())}"
            
            return ArbitrageOpportunity(
                id=opp_id,
                type=ArbitrageType.SIMPLE,
                token_address=token_address,
                token_symbol="",  # Would fetch
                chain=chain,
                buy_dex=buy_dex,
                sell_dex=sell_dex,
                buy_price=buy_price,
                sell_price=sell_price,
                price_difference_percent=price_diff_percent,
                optimal_amount=optimal_amount,
                gross_profit=gross_profit,
                gas_cost=gas_cost,
                net_profit=net_profit,
                roi_percent=roi_percent,
                detected_at=datetime.now(),
                confidence=self._calculate_confidence(price_diff_percent),
                notes=[]
            )
            
        except Exception as e:
            self.logger.error(f"Opportunity analysis failed: {e}")
            return None
    
    async def _calculate_optimal_amount(
        self,
        token_address: str,
        chain: str,
        buy_dex: str,
        sell_dex: str,
        test_amount: Decimal
    ) -> Decimal:
        """
        Calculate optimal arbitrage amount considering price impact.
        
        This is simplified - in production would use binary search
        to find the amount that maximizes profit.
        """
        # Start with test amount
        optimal = test_amount
        
        # Test different amounts
        amounts_to_test = [
            test_amount * Decimal("0.5"),
            test_amount,
            test_amount * Decimal("2"),
            test_amount * Decimal("5"),
            test_amount * Decimal("10")
        ]
        
        best_profit = Decimal("0")
        
        for amount in amounts_to_test:
            # Skip if too large
            if amount > Decimal("50"):  # 50 ETH max
                continue
            
            # Would calculate actual profit considering price impact
            # For now, use simple heuristic
            if amount <= Decimal("5"):
                # Low price impact
                profit_multiplier = Decimal("0.95")
            elif amount <= Decimal("10"):
                # Medium price impact
                profit_multiplier = Decimal("0.85")
            else:
                # High price impact
                profit_multiplier = Decimal("0.70")
            
            estimated_profit = amount * profit_multiplier
            
            if estimated_profit > best_profit:
                best_profit = estimated_profit
                optimal = amount
        
        return optimal
    
    async def _estimate_gas_cost(self, chain: str) -> Decimal:
        """Estimate gas cost for arbitrage execution."""
        # Base gas units
        approve_gas = 50000
        swap_gas = 250000
        total_gas = approve_gas + (swap_gas * 2)  # Buy + sell
        
        # Get current gas price (would fetch from chain)
        if chain == "ethereum":
            gas_price_gwei = 30  # Example
        else:
            gas_price_gwei = 1   # Base/L2s are cheaper
        
        # Calculate cost in ETH
        gas_cost_eth = Decimal(total_gas * gas_price_gwei) / Decimal(10**9)
        
        # Apply buffer
        return gas_cost_eth * Decimal(str(self.gas_buffer))
    
    def _calculate_confidence(self, price_diff_percent: float) -> float:
        """Calculate confidence score for arbitrage opportunity."""
        if price_diff_percent > 10:
            return 0.95
        elif price_diff_percent > 5:
            return 0.85
        elif price_diff_percent > 3:
            return 0.70
        elif price_diff_percent > 2:
            return 0.60
        else:
            return 0.50
    
    async def _check_triangular_path(
        self,
        chain: str,
        token_a: str,
        token_b: str,
        token_c: str,
        amount: Decimal
    ) -> Decimal:
        """Check profitability of a triangular arbitrage path."""
        try:
            # Get amounts for each leg
            # A -> B
            amounts_ab = await self.dex_manager.get_amounts_out(
                amount, [token_a, token_b], chain
            )
            if not amounts_ab:
                return Decimal("0")
            
            amount_b = amounts_ab[-1]
            
            # B -> C
            amounts_bc = await self.dex_manager.get_amounts_out(
                amount_b, [token_b, token_c], chain
            )
            if not amounts_bc:
                return Decimal("0")
            
            amount_c = amounts_bc[-1]
            
            # C -> A
            amounts_ca = await self.dex_manager.get_amounts_out(
                amount_c, [token_c, token_a], chain
            )
            if not amounts_ca:
                return Decimal("0")
            
            final_amount = amounts_ca[-1]
            
            # Calculate profit
            profit = final_amount - amount
            
            # Subtract estimated gas
            gas_cost = await self._estimate_gas_cost(chain)
            net_profit = profit - gas_cost
            
            return net_profit if net_profit > 0 else Decimal("0")
            
        except Exception as e:
            self.logger.debug(f"Triangular path check failed: {e}")
            return Decimal("0")
    
    def _get_popular_tokens(self, chain: str) -> List[str]:
        """Get list of popular tokens for triangular arbitrage."""
        if chain == "ethereum":
            return [
                "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
                "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
                "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC
                "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
            ]
        elif chain == "base":
            return [
                "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
                "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",  # DAI
            ]
        else:
            return []
    
    def _cache_opportunities(self, opportunities: List[ArbitrageOpportunity]) -> None:
        """Cache arbitrage opportunities."""
        for opp in opportunities:
            self.active_opportunities[opp.id] = opp
        
        # Clean old opportunities
        cutoff = datetime.now().timestamp() - 300  # 5 minutes
        to_remove = []
        
        for opp_id, opp in self.active_opportunities.items():
            if opp.detected_at.timestamp() < cutoff:
                to_remove.append(opp_id)
        
        for opp_id in to_remove:
            del self.active_opportunities[opp_id]
    
    def get_active_opportunities(self) -> List[ArbitrageOpportunity]:
        """Get all active arbitrage opportunities."""
        return list(self.active_opportunities.values())
    
    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        wallet_name: str,
        slippage: float = 0.02
    ) -> Dict[str, Any]:
        """
        Execute an arbitrage opportunity.
        
        Args:
            opportunity: Arbitrage opportunity to execute
            wallet_name: Wallet to use
            slippage: Maximum slippage tolerance
            
        Returns:
            Execution result
        """
        try:
            self.logger.info(f"Executing arbitrage: {opportunity.id}")
            
            # Calculate minimum amounts with slippage
            min_tokens = opportunity.optimal_amount / opportunity.buy_price
            min_tokens = min_tokens * Decimal(1 - slippage)
            
            min_eth_out = min_tokens * opportunity.sell_price
            min_eth_out = min_eth_out * Decimal(1 - slippage)
            
            # Step 1: Buy tokens on cheaper DEX
            buy_result = await self.dex_manager.swap_eth_for_tokens(
                opportunity.token_address,
                opportunity.optimal_amount,
                min_tokens,
                wallet_name,
                opportunity.chain,
                opportunity.buy_dex
            )
            
            if not buy_result or not buy_result['success']:
                return {
                    'success': False,
                    'error': 'Buy transaction failed',
                    'step': 'buy'
                }
            
            # Step 2: Sell tokens on expensive DEX
            sell_result = await self.dex_manager.swap_tokens_for_eth(
                opportunity.token_address,
                min_tokens,  # Use actual received amount in production
                min_eth_out,
                wallet_name,
                opportunity.chain,
                opportunity.sell_dex
            )
            
            if not sell_result or not sell_result['success']:
                return {
                    'success': False,
                    'error': 'Sell transaction failed',
                    'step': 'sell',
                    'buy_tx': buy_result['tx_hash']
                }
            
            return {
                'success': True,
                'buy_tx': buy_result['tx_hash'],
                'sell_tx': sell_result['tx_hash'],
                'gas_used': buy_result['gas_used'] + sell_result['gas_used']
            }
            
        except Exception as e:
            self.logger.error(f"Arbitrage execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }