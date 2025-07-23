"""
Transaction simulation engine for testing trades before execution.
Simulates DEX interactions, calculates slippage, and predicts outcomes.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio
from web3 import Web3
from web3.types import TxParams
import json

from models.token import TradingOpportunity
from utils.logger import logger_manager


class SimulationResult(Enum):
    """Result of transaction simulation."""
    SUCCESS = "success"
    REVERTED = "reverted"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    EXCESSIVE_SLIPPAGE = "excessive_slippage"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    GAS_ESTIMATION_FAILED = "gas_estimation_failed"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class SimulationReport:
    """Detailed report from transaction simulation."""
    result: SimulationResult
    success: bool
    
    # Trade details
    amount_in: Optional[Decimal] = None
    amount_out: Optional[Decimal] = None
    effective_price: Optional[Decimal] = None
    price_impact: Optional[float] = None
    slippage: Optional[float] = None
    
    # Gas details
    estimated_gas: Optional[int] = None
    gas_price: Optional[int] = None
    total_gas_cost: Optional[Decimal] = None
    
    # Error details
    error_message: Optional[str] = None
    revert_reason: Optional[str] = None
    
    # Additional insights
    liquidity_available: Optional[Decimal] = None
    recommended_amount: Optional[Decimal] = None
    warnings: List[str] = None


class TransactionSimulator:
    """
    Simulates transactions before execution to predict outcomes and detect issues.
    Provides detailed analysis of trades including slippage and gas costs.
    """
    
    def __init__(self) -> None:
        """Initialize the transaction simulator."""
        self.logger = logger_manager.get_logger("TransactionSimulator")
        self.w3: Optional[Web3] = None
        
        # DEX configurations
        self.dex_configs = {
            "uniswap_v2": {
                "router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
                "init_code_hash": "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f"
            },
            "uniswap_v3": {
                "router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
                "quoter": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984"
            },
            "sushiswap": {
                "router": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
                "factory": "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac"
            }
        }
        
        # Simulation cache
        self.simulation_cache: Dict[str, SimulationReport] = {}
        self.cache_ttl = 30  # seconds
        
        # Statistics
        self.stats = {
            "total_simulations": 0,
            "successful_simulations": 0,
            "prevented_failures": 0,
            "gas_saved": Decimal("0"),
            "slippage_warnings": 0
        }
    
    async def initialize(self, w3: Web3) -> None:
        """
        Initialize simulator with Web3 connection.
        
        Args:
            w3: Web3 instance
        """
        try:
            self.logger.info("Initializing transaction simulator...")
            self.w3 = w3
            
            # Load DEX ABIs
            await self._load_dex_abis()
            
            # Test simulation capability
            await self._test_simulation()
            
            self.logger.info("Transaction simulator initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize simulator: {e}")
            raise
    
    async def simulate_buy_trade(
        self,
        opportunity: TradingOpportunity,
        amount_in: Decimal,
        max_slippage: float = 0.05
    ) -> SimulationReport:
        """
        Simulate a buy trade for a token.
        
        Args:
            opportunity: Trading opportunity
            amount_in: Amount to spend
            max_slippage: Maximum acceptable slippage
            
        Returns:
            SimulationReport with detailed results
        """
        try:
            self.logger.info(f"Simulating buy trade: {opportunity.token.symbol} Amount: {amount_in}")
            
            # Check cache first
            cache_key = f"buy_{opportunity.token.address}_{amount_in}_{max_slippage}"
            cached = self._get_cached_simulation(cache_key)
            if cached:
                return cached
            
            # Determine DEX and path
            dex_name, swap_path = await self._determine_swap_route(
                opportunity.token.address,
                is_buy=True
            )
            
            # Build swap transaction
            tx_params = await self._build_swap_transaction(
                dex_name=dex_name,
                path=swap_path,
                amount_in=amount_in,
                min_amount_out=0,  # Will calculate
                recipient="0x0000000000000000000000000000000000000000",  # Simulation address
                deadline=int(datetime.now().timestamp()) + 3600
            )
            
            # Run simulation
            report = await self._run_simulation(tx_params, opportunity, amount_in, is_buy=True)
            
            # Check slippage
            if report.slippage and report.slippage > max_slippage:
                report.result = SimulationResult.EXCESSIVE_SLIPPAGE
                report.success = False
                report.warnings.append(f"Slippage {report.slippage:.2%} exceeds max {max_slippage:.2%}")
            
            # Cache result
            self._cache_simulation(cache_key, report)
            
            # Update stats
            self.stats["total_simulations"] += 1
            if report.success:
                self.stats["successful_simulations"] += 1
            else:
                self.stats["prevented_failures"] += 1
            
            return report
            
        except Exception as e:
            self.logger.error(f"Buy simulation failed: {e}")
            return SimulationReport(
                result=SimulationResult.UNKNOWN_ERROR,
                success=False,
                error_message=str(e),
                warnings=[f"Simulation error: {str(e)}"]
            )
    
    async def simulate_sell_trade(
        self,
        token_address: str,
        amount_in: Decimal,
        chain: str = "ethereum",
        max_slippage: float = 0.05
    ) -> SimulationReport:
        """
        Simulate a sell trade for a token.
        
        Args:
            token_address: Token to sell
            amount_in: Amount of tokens to sell
            chain: Blockchain name
            max_slippage: Maximum acceptable slippage
            
        Returns:
            SimulationReport with detailed results
        """
        try:
            self.logger.info(f"Simulating sell trade: {token_address} Amount: {amount_in}")
            
            # Check cache
            cache_key = f"sell_{token_address}_{amount_in}_{max_slippage}"
            cached = self._get_cached_simulation(cache_key)
            if cached:
                return cached
            
            # Determine DEX and path
            dex_name, swap_path = await self._determine_swap_route(
                token_address,
                is_buy=False
            )
            
            # Build swap transaction
            tx_params = await self._build_swap_transaction(
                dex_name=dex_name,
                path=swap_path,
                amount_in=amount_in,
                min_amount_out=0,
                recipient="0x0000000000000000000000000000000000000000",
                deadline=int(datetime.now().timestamp()) + 3600
            )
            
            # Run simulation
            report = await self._run_simulation(tx_params, None, amount_in, is_buy=False)
            
            # Cache result
            self._cache_simulation(cache_key, report)
            
            return report
            
        except Exception as e:
            self.logger.error(f"Sell simulation failed: {e}")
            return SimulationReport(
                result=SimulationResult.UNKNOWN_ERROR,
                success=False,
                error_message=str(e),
                warnings=[f"Simulation error: {str(e)}"]
            )
    
    async def analyze_liquidity_impact(
        self,
        token_address: str,
        trade_amounts: List[Decimal]
    ) -> Dict[str, Any]:
        """
        Analyze liquidity and price impact for different trade sizes.
        
        Args:
            token_address: Token to analyze
            trade_amounts: List of amounts to test
            
        Returns:
            Analysis results with impact curves
        """
        try:
            self.logger.info(f"Analyzing liquidity impact for {token_address}")
            
            results = {
                "token": token_address,
                "timestamp": datetime.now().isoformat(),
                "impact_curve": [],
                "max_recommended_size": Decimal("0"),
                "total_liquidity": Decimal("0")
            }
            
            # Simulate each amount
            for amount in trade_amounts:
                report = await self.simulate_buy_trade(
                    self._create_dummy_opportunity(token_address),
                    amount
                )
                
                if report.price_impact is not None:
                    results["impact_curve"].append({
                        "amount": float(amount),
                        "price_impact": report.price_impact,
                        "effective_price": float(report.effective_price) if report.effective_price else 0,
                        "success": report.success
                    })
                    
                    # Find max recommended size (< 2% impact)
                    if report.price_impact < 0.02 and amount > results["max_recommended_size"]:
                        results["max_recommended_size"] = amount
            
            # Estimate total liquidity
            if results["impact_curve"]:
                # Extrapolate from impact curve
                results["total_liquidity"] = self._estimate_total_liquidity(results["impact_curve"])
            
            return results
            
        except Exception as e:
            self.logger.error(f"Liquidity analysis failed: {e}")
            return {"error": str(e)}
    
    async def _run_simulation(
        self,
        tx_params: TxParams,
        opportunity: Optional[TradingOpportunity],
        amount_in: Decimal,
        is_buy: bool
    ) -> SimulationReport:
        """Run the actual simulation."""
        try:
            report = SimulationReport(
                result=SimulationResult.UNKNOWN_ERROR,
                success=False,
                amount_in=amount_in,
                warnings=[]
            )
            
            # Estimate gas
            try:
                estimated_gas = await self.w3.eth.estimate_gas(tx_params)
                report.estimated_gas = estimated_gas
                
                # Get current gas price
                gas_price = await self.w3.eth.gas_price
                report.gas_price = gas_price
                report.total_gas_cost = Decimal(str(estimated_gas * gas_price / 10**18))
                
            except Exception as e:
                report.result = SimulationResult.GAS_ESTIMATION_FAILED
                report.error_message = f"Gas estimation failed: {str(e)}"
                return report
            
            # Simulate the transaction
            try:
                # Use eth_call to simulate
                result = await self.w3.eth.call(tx_params)
                
                # Decode result (would need actual ABI)
                amount_out = self._decode_swap_result(result)
                report.amount_out = amount_out
                
                # Calculate metrics
                if is_buy:
                    report.effective_price = amount_in / amount_out if amount_out > 0 else Decimal("0")
                else:
                    report.effective_price = amount_out / amount_in if amount_in > 0 else Decimal("0")
                
                # Calculate price impact
                if opportunity and opportunity.token.price_usd > 0:
                    expected_out = amount_in / Decimal(str(opportunity.token.price_usd))
                    actual_out = amount_out
                    report.price_impact = float((expected_out - actual_out) / expected_out)
                    report.slippage = abs(report.price_impact)
                
                # Check for common issues
                if amount_out == 0:
                    report.result = SimulationResult.INSUFFICIENT_LIQUIDITY
                    report.warnings.append("No output tokens received - insufficient liquidity")
                elif report.slippage and report.slippage > 0.1:  # 10%
                    report.warnings.append(f"High slippage detected: {report.slippage:.2%}")
                
                # Success if we got here
                report.result = SimulationResult.SUCCESS
                report.success = True
                
            except Exception as e:
                # Parse revert reason
                revert_reason = self._parse_revert_reason(str(e))
                report.result = SimulationResult.REVERTED
                report.revert_reason = revert_reason
                report.error_message = f"Transaction would revert: {revert_reason}"
                
                # Check specific revert reasons
                if "INSUFFICIENT_LIQUIDITY" in revert_reason:
                    report.result = SimulationResult.INSUFFICIENT_LIQUIDITY
                elif "INSUFFICIENT_OUTPUT_AMOUNT" in revert_reason:
                    report.result = SimulationResult.EXCESSIVE_SLIPPAGE
            
            return report
            
        except Exception as e:
            self.logger.error(f"Simulation execution failed: {e}")
            return SimulationReport(
                result=SimulationResult.UNKNOWN_ERROR,
                success=False,
                error_message=str(e),
                warnings=[f"Unexpected error: {str(e)}"]
            )
    
    async def _determine_swap_route(
        self,
        token_address: str,
        is_buy: bool
    ) -> Tuple[str, List[str]]:
        """Determine best DEX and swap path."""
        # For now, default to Uniswap V2 with WETH path
        weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
        
        if is_buy:
            path = [weth_address, token_address]
        else:
            path = [token_address, weth_address]
        
        return "uniswap_v2", path
    
    async def _build_swap_transaction(
        self,
        dex_name: str,
        path: List[str],
        amount_in: Decimal,
        min_amount_out: Decimal,
        recipient: str,
        deadline: int
    ) -> TxParams:
        """Build swap transaction for simulation."""
        # Get router address
        router_address = self.dex_configs[dex_name]["router"]
        
        # Build transaction (simplified - would use actual ABI)
        tx_params = {
            "to": router_address,
            "from": recipient,
            "value": Web3.to_wei(amount_in, "ether") if path[0] == "ETH" else 0,
            "data": "0x",  # Would encode actual swap function
            "gas": 300000,
        }
        
        return tx_params
    
    async def _load_dex_abis(self) -> None:
        """Load DEX contract ABIs."""
        # In production, would load actual ABIs
        pass
    
    async def _test_simulation(self) -> None:
        """Test simulation capability."""
        try:
            # Simple test call
            test_tx = {
                "to": "0x0000000000000000000000000000000000000000",
                "data": "0x",
                "value": 0
            }
            
            result = self.w3.eth.call(test_tx)
            self.logger.debug("Simulation test successful")
            
        except Exception as e:
            self.logger.warning(f"Simulation test failed: {e}")
    
    def _decode_swap_result(self, result: bytes) -> Decimal:
        """Decode swap simulation result."""
        # Would decode actual result
        # For now, return dummy value
        return Decimal("100")
    
    def _parse_revert_reason(self, error_str: str) -> str:
        """Parse revert reason from error string."""
        # Common revert reasons
        if "INSUFFICIENT_LIQUIDITY" in error_str:
            return "INSUFFICIENT_LIQUIDITY"
        elif "INSUFFICIENT_OUTPUT_AMOUNT" in error_str:
            return "INSUFFICIENT_OUTPUT_AMOUNT"
        elif "EXPIRED" in error_str:
            return "DEADLINE_EXPIRED"
        else:
            return "UNKNOWN_REVERT"
    
    def _get_cached_simulation(self, cache_key: str) -> Optional[SimulationReport]:
        """Get cached simulation result."""
        # Simple in-memory cache
        # In production, would use Redis or similar
        return self.simulation_cache.get(cache_key)
    
    def _cache_simulation(self, cache_key: str, report: SimulationReport) -> None:
        """Cache simulation result."""
        self.simulation_cache[cache_key] = report
        
        # Clean old entries
        if len(self.simulation_cache) > 1000:
            # Remove oldest half
            keys = list(self.simulation_cache.keys())
            for key in keys[:500]:
                del self.simulation_cache[key]
    
    def _create_dummy_opportunity(self, token_address: str) -> TradingOpportunity:
        """Create dummy opportunity for simulation."""
        from models.token import TokenInfo, LiquidityInfo, ContractAnalysis, SocialMetrics
        
        return TradingOpportunity(
            token=TokenInfo(
                address=token_address,
                symbol="TEST",
                name="Test Token",
                decimals=18,
                total_supply=1000000,
                price_usd=1.0,
                market_cap_usd=1000000.0,
                launch_time=datetime.now(),
                chain="ethereum"
            ),
            liquidity=LiquidityInfo(),
            contract_analysis=ContractAnalysis(),
            social_metrics=SocialMetrics(),
            metadata={}
        )
    
    def _estimate_total_liquidity(self, impact_curve: List[Dict]) -> Decimal:
        """Estimate total liquidity from impact curve."""
        # Simple estimation based on impact curve
        if not impact_curve:
            return Decimal("0")
        
        # Find point where impact reaches 10%
        for point in impact_curve:
            if point["price_impact"] >= 0.1:
                # Extrapolate
                return Decimal(str(point["amount"] * 10))
        
        # If no 10% impact found, use largest amount * 20
        return Decimal(str(impact_curve[-1]["amount"] * 20))
    
    def get_simulation_stats(self) -> Dict[str, Any]:
        """Get simulation statistics."""
        return {
            "total_simulations": self.stats["total_simulations"],
            "successful_simulations": self.stats["successful_simulations"],
            "prevented_failures": self.stats["prevented_failures"],
            "failure_prevention_rate": (
                self.stats["prevented_failures"] / 
                max(self.stats["total_simulations"], 1)
            ),
            "gas_saved_eth": float(self.stats["gas_saved"]),
            "slippage_warnings": self.stats["slippage_warnings"],
            "cache_size": len(self.simulation_cache)
        }