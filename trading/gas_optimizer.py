"""
Gas optimization system for efficient transaction execution.
Provides dynamic gas pricing strategies and fee optimization.
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import aiohttp
from web3 import Web3
from web3.types import TxParams, Wei
import statistics
import json

from utils.logger import logger_manager


class GasStrategy(Enum):
    """Gas pricing strategies."""
    ECONOMY = "economy"  # Cheapest, slower
    STANDARD = "standard"  # Balanced
    FAST = "fast"  # Higher gas for speed
    URGENT = "urgent"  # Maximum speed regardless of cost


@dataclass
class GasEstimate:
    """Gas price estimation with confidence intervals."""
    safe_low: int  # Safe low gas price (gwei)
    standard: int  # Standard gas price (gwei)
    fast: int  # Fast gas price (gwei)
    instant: int  # Instant gas price (gwei)
    base_fee: int  # Current base fee (gwei)
    priority_fee_low: int  # Low priority fee (gwei)
    priority_fee_standard: int  # Standard priority fee (gwei)
    priority_fee_fast: int  # Fast priority fee (gwei)
    confidence: float  # Confidence in estimates (0-1)
    timestamp: datetime


@dataclass
class OptimizedTransaction:
    """Optimized transaction with gas savings."""
    original_tx: TxParams
    optimized_tx: TxParams
    strategy_used: GasStrategy
    estimated_savings_gwei: int
    estimated_savings_usd: Decimal
    gas_savings: int  # Gas units saved
    time_estimate_seconds: int
    confidence: float


class GasOptimizer:
    """
    Advanced gas optimization system for transaction efficiency.
    Provides dynamic pricing, network condition analysis, and cost optimization.
    """
    
    def __init__(self) -> None:
        """Initialize gas optimizer."""
        self.logger = logger_manager.get_logger("GasOptimizer")
        self.web3: Optional[Web3] = None
        self.initialized = False
        
        # Gas price sources
        self.gas_apis = {
            "ethgasstation": "https://ethgasstation.info/api/ethgasAPI.json",
            "gastrack": "https://api.gastrack.io/gas/price",
            "blocknative": "https://api.blocknative.com/gasprices/blockprices"
        }
        
        # Network condition tracking
        self.network_stats = {
            "current_base_fee": 0,
            "pending_transactions": 0,
            "congestion_level": "normal",  # low, normal, high, extreme
            "average_block_time": 12.0,
            "mempool_size": 0,
            "gas_price_trend": "stable"  # rising, falling, stable
        }
        
        # Historical data for trend analysis
        self.gas_price_history: List[Dict[str, Any]] = []
        self.max_history_size = 100
        
        # Optimization statistics
        self.optimization_stats = {
            "total_optimizations": 0,
            "total_savings_gwei": 0,
            "total_savings_usd": Decimal("0"),
            "average_savings_percent": 0.0,
            "strategy_usage": {strategy.value: 0 for strategy in GasStrategy},
            "current_base_fee_gwei": 0,
            "network_congestion": "normal"
        }
        
        # Strategy configurations
        self.strategy_configs = {
            GasStrategy.ECONOMY: {
                "base_multiplier": 1.0,
                "priority_multiplier": 0.5,
                "max_wait_time": 300  # 5 minutes
            },
            GasStrategy.STANDARD: {
                "base_multiplier": 1.1,
                "priority_multiplier": 1.0,
                "max_wait_time": 60  # 1 minute
            },
            GasStrategy.FAST: {
                "base_multiplier": 1.25,
                "priority_multiplier": 1.5,
                "max_wait_time": 30  # 30 seconds
            },
            GasStrategy.URGENT: {
                "base_multiplier": 1.5,
                "priority_multiplier": 2.0,
                "max_wait_time": 15  # 15 seconds
            }
        }
    
    async def initialize(self, web3: Web3) -> None:
        """
        Initialize gas optimizer.
        
        Args:
            web3: Web3 connection
        """
        try:
            self.logger.info("Initializing gas optimizer...")
            self.web3 = web3
            
            # Start network monitoring
            asyncio.create_task(self._start_network_monitoring())
            
            # Initialize gas price tracking
            asyncio.create_task(self._update_gas_estimates())
            
            self.initialized = True
            self.logger.info("✅ Gas optimizer initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize gas optimizer: {e}")
            raise
    
    async def optimize_transaction(
        self,
        tx_params: TxParams,
        strategy: GasStrategy = GasStrategy.STANDARD,
        urgency: float = 0.5,
        max_gas_price_gwei: Optional[int] = None
    ) -> OptimizedTransaction:
        """
        Optimize transaction gas parameters.
        
        Args:
            tx_params: Original transaction parameters
            strategy: Gas optimization strategy
            urgency: Urgency level (0-1, higher = more urgent)
            max_gas_price_gwei: Maximum acceptable gas price
            
        Returns:
            Optimized transaction with gas savings
        """
        try:
            if not self.initialized:
                self.logger.warning("Gas optimizer not initialized")
                return self._create_fallback_optimization(tx_params, strategy)
            
            # Get current gas estimates
            gas_estimate = await self._get_current_gas_estimate()
            
            # Adjust strategy based on urgency
            effective_strategy = self._adjust_strategy_for_urgency(strategy, urgency)
            
            # Create optimized transaction
            optimized_tx = await self._optimize_transaction_params(
                tx_params, gas_estimate, effective_strategy, max_gas_price_gwei
            )
            
            # Calculate savings
            savings = self._calculate_savings(tx_params, optimized_tx.optimized_tx)
            
            # Update statistics
            self._update_optimization_stats(effective_strategy, savings)
            
            self.logger.info(
                f"Gas optimization complete: {effective_strategy.value} strategy, "
                f"savings: {savings['savings_gwei']} gwei (${savings['savings_usd']:.2f})"
            )
            
            return optimized_tx
            
        except Exception as e:
            self.logger.error(f"Gas optimization failed: {e}")
            return self._create_fallback_optimization(tx_params, strategy)
    
    async def _get_current_gas_estimate(self) -> GasEstimate:
        """Get current gas price estimates from multiple sources."""
        try:
            # Get base fee from latest block
            latest_block = self.web3.eth.get_block("latest")
            base_fee_wei = latest_block.get("baseFeePerGas", 20_000_000_000)
            base_fee_gwei = int(base_fee_wei / 1_000_000_000)
            
            # Get estimates from APIs
            api_estimates = await self._fetch_gas_estimates_from_apis()
            
            # Combine estimates
            if api_estimates:
                # Use API data if available
                fast_gwei = api_estimates.get("fast", base_fee_gwei + 2)
                standard_gwei = api_estimates.get("standard", base_fee_gwei + 1)
                safe_low_gwei = api_estimates.get("safe_low", base_fee_gwei)
            else:
                # Fallback to calculated estimates
                fast_gwei = base_fee_gwei + 3
                standard_gwei = base_fee_gwei + 2
                safe_low_gwei = base_fee_gwei + 1
            
            # Calculate priority fees
            priority_fee_fast = max(3, int((fast_gwei - base_fee_gwei) * 1.2))
            priority_fee_standard = max(2, fast_gwei - base_fee_gwei)
            priority_fee_low = max(1, int((fast_gwei - base_fee_gwei) * 0.8))
            
            return GasEstimate(
                safe_low=safe_low_gwei,
                standard=standard_gwei,
                fast=fast_gwei,
                instant=fast_gwei + 5,
                base_fee=base_fee_gwei,
                priority_fee_low=priority_fee_low,
                priority_fee_standard=priority_fee_standard,
                priority_fee_fast=priority_fee_fast,
                confidence=0.8 if api_estimates else 0.6,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Gas estimate failed: {e}")
            return self._create_fallback_gas_estimate()
    
    async def _fetch_gas_estimates_from_apis(self) -> Dict[str, int]:
        """Fetch gas estimates from external APIs."""
        estimates = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                # Try multiple sources and take median
                results = []
                
                for api_name, url in self.gas_apis.items():
                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                            if response.status == 200:
                                data = await response.json()
                                parsed = self._parse_gas_api_response(api_name, data)
                                if parsed:
                                    results.append(parsed)
                    except Exception as e:
                        self.logger.debug(f"Gas API {api_name} failed: {e}")
                
                # Calculate median estimates
                if results:
                    estimates["safe_low"] = int(statistics.median([r["safe_low"] for r in results]))
                    estimates["standard"] = int(statistics.median([r["standard"] for r in results]))
                    estimates["fast"] = int(statistics.median([r["fast"] for r in results]))
                    
        except Exception as e:
            self.logger.debug(f"Gas API fetch failed: {e}")
        
        return estimates
    
    def _parse_gas_api_response(self, api_name: str, data: Dict[str, Any]) -> Optional[Dict[str, int]]:
        """Parse gas API response to standard format."""
        try:
            if api_name == "ethgasstation":
                return {
                    "safe_low": int(data.get("safeLow", 20)),
                    "standard": int(data.get("standard", 25)),
                    "fast": int(data.get("fast", 30))
                }
            elif api_name == "gastrack":
                return {
                    "safe_low": int(data.get("slow", 20)),
                    "standard": int(data.get("normal", 25)),
                    "fast": int(data.get("fast", 30))
                }
            # Add more API parsers as needed
            
        except Exception as e:
            self.logger.debug(f"Failed to parse {api_name} response: {e}")
        
        return None
    
    def _adjust_strategy_for_urgency(self, strategy: GasStrategy, urgency: float) -> GasStrategy:
        """Adjust gas strategy based on urgency level."""
        if urgency >= 0.9:
            return GasStrategy.URGENT
        elif urgency >= 0.7:
            return max(strategy, GasStrategy.FAST)
        elif urgency >= 0.4:
            return max(strategy, GasStrategy.STANDARD) if strategy != GasStrategy.ECONOMY else strategy
        else:
            return strategy
    
    async def _optimize_transaction_params(
        self,
        tx_params: TxParams,
        gas_estimate: GasEstimate,
        strategy: GasStrategy,
        max_gas_price_gwei: Optional[int]
    ) -> OptimizedTransaction:
        """Optimize transaction parameters based on strategy."""
        try:
            config = self.strategy_configs[strategy]
            optimized_tx = tx_params.copy()
            
            # Determine if we should use EIP-1559 or legacy
            use_eip1559 = self._should_use_eip1559(tx_params)
            
            if use_eip1559:
                # EIP-1559 optimization
                base_fee = gas_estimate.base_fee
                
                if strategy == GasStrategy.ECONOMY:
                    max_fee = base_fee + gas_estimate.priority_fee_low
                    priority_fee = gas_estimate.priority_fee_low
                elif strategy == GasStrategy.STANDARD:
                    max_fee = base_fee + gas_estimate.priority_fee_standard
                    priority_fee = gas_estimate.priority_fee_standard
                elif strategy == GasStrategy.FAST:
                    max_fee = base_fee + gas_estimate.priority_fee_fast
                    priority_fee = gas_estimate.priority_fee_fast
                else:  # URGENT
                    max_fee = (base_fee * 2) + gas_estimate.priority_fee_fast
                    priority_fee = gas_estimate.priority_fee_fast * 2
                
                # Apply max gas price limit
                if max_gas_price_gwei and max_fee > max_gas_price_gwei:
                    max_fee = max_gas_price_gwei
                    priority_fee = min(priority_fee, max_gas_price_gwei - base_fee)
                
                optimized_tx["type"] = "0x2"
                optimized_tx["maxFeePerGas"] = max_fee * 1_000_000_000  # Convert to wei
                optimized_tx["maxPriorityFeePerGas"] = priority_fee * 1_000_000_000
                optimized_tx.pop("gasPrice", None)  # Remove legacy gas price
                
            else:
                # Legacy transaction optimization
                if strategy == GasStrategy.ECONOMY:
                    gas_price = gas_estimate.safe_low
                elif strategy == GasStrategy.STANDARD:
                    gas_price = gas_estimate.standard
                elif strategy == GasStrategy.FAST:
                    gas_price = gas_estimate.fast
                else:  # URGENT
                    gas_price = gas_estimate.instant
                
                # Apply max gas price limit
                if max_gas_price_gwei and gas_price > max_gas_price_gwei:
                    gas_price = max_gas_price_gwei
                
                optimized_tx["gasPrice"] = gas_price * 1_000_000_000  # Convert to wei
                optimized_tx.pop("type", None)
                optimized_tx.pop("maxFeePerGas", None)
                optimized_tx.pop("maxPriorityFeePerGas", None)
            
            # Optimize gas limit
            optimized_gas_limit = await self._optimize_gas_limit(optimized_tx)
            if optimized_gas_limit:
                optimized_tx["gas"] = optimized_gas_limit
            
            # Calculate savings and time estimate
            savings = self._calculate_savings(tx_params, optimized_tx)
            time_estimate = self._estimate_confirmation_time(strategy)
            
            return OptimizedTransaction(
                original_tx=tx_params,
                optimized_tx=optimized_tx,
                strategy_used=strategy,
                estimated_savings_gwei=savings["savings_gwei"],
                estimated_savings_usd=savings["savings_usd"],
                gas_savings=savings["gas_units_saved"],
                time_estimate_seconds=time_estimate,
                confidence=gas_estimate.confidence
            )
            
        except Exception as e:
            self.logger.error(f"Transaction optimization failed: {e}")
            raise
    
    def _should_use_eip1559(self, tx_params: TxParams) -> bool:
        """Determine if transaction should use EIP-1559."""
        # Use EIP-1559 if not explicitly set to legacy
        return tx_params.get("type") != "0x0" and "gasPrice" not in tx_params
    
    async def _optimize_gas_limit(self, tx_params: TxParams) -> Optional[int]:
        """Optimize gas limit for transaction."""
        try:
            # Estimate gas usage
            estimated_gas = self.web3.eth.estimate_gas(tx_params)
            
            # Add buffer (10-20% depending on complexity)
            buffer_percent = 0.15  # 15% buffer
            optimized_limit = int(estimated_gas * (1 + buffer_percent))
            
            # Ensure it's not less than original limit
            original_limit = tx_params.get("gas", 0)
            if original_limit > 0:
                optimized_limit = max(optimized_limit, original_limit)
            
            return optimized_limit
            
        except Exception as e:
            self.logger.debug(f"Gas limit optimization failed: {e}")
            return None
    
    def _calculate_savings(self, original_tx: TxParams, optimized_tx: TxParams) -> Dict[str, Any]:
        """Calculate gas savings from optimization."""
        try:
            # Calculate original cost
            original_gas_price = self._get_effective_gas_price(original_tx)
            original_gas_limit = original_tx.get("gas", 300000)
            original_cost_wei = original_gas_price * original_gas_limit
            
            # Calculate optimized cost
            optimized_gas_price = self._get_effective_gas_price(optimized_tx)
            optimized_gas_limit = optimized_tx.get("gas", 300000)
            optimized_cost_wei = optimized_gas_price * optimized_gas_limit
            
            # Calculate savings
            savings_wei = max(0, original_cost_wei - optimized_cost_wei)
            savings_gwei = int(savings_wei / 1_000_000_000)
            
            # Convert to USD (simplified - would use real ETH price)
            eth_price_usd = Decimal("2000")  # Placeholder
            savings_eth = Decimal(str(savings_wei)) / Decimal("1e18")
            savings_usd = savings_eth * eth_price_usd
            
            gas_units_saved = max(0, original_gas_limit - optimized_gas_limit)
            
            return {
                "savings_gwei": savings_gwei,
                "savings_usd": savings_usd,
                "gas_units_saved": gas_units_saved,
                "percent_saved": (savings_wei / original_cost_wei * 100) if original_cost_wei > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Savings calculation failed: {e}")
            return {
                "savings_gwei": 0,
                "savings_usd": Decimal("0"),
                "gas_units_saved": 0,
                "percent_saved": 0
            }
    
    def _get_effective_gas_price(self, tx_params: TxParams) -> int:
        """Get effective gas price from transaction parameters."""
        if "gasPrice" in tx_params:
            return tx_params["gasPrice"]
        elif "maxFeePerGas" in tx_params:
            return tx_params["maxFeePerGas"]
        else:
            return 20_000_000_000  # Default 20 gwei
    
    def _estimate_confirmation_time(self, strategy: GasStrategy) -> int:
        """Estimate confirmation time for strategy."""
        config = self.strategy_configs[strategy]
        
        # Adjust based on network congestion
        base_time = config["max_wait_time"]
        congestion = self.network_stats["congestion_level"]
        
        if congestion == "extreme":
            return base_time * 3
        elif congestion == "high":
            return base_time * 2
        elif congestion == "low":
            return max(15, base_time // 2)
        else:
            return base_time
    
    def _create_fallback_optimization(
        self,
        tx_params: TxParams,
        strategy: GasStrategy
    ) -> OptimizedTransaction:
        """Create fallback optimization when APIs fail."""
        optimized_tx = tx_params.copy()
        
        # Simple fallback gas pricing
        if strategy == GasStrategy.ECONOMY:
            gas_price = 20_000_000_000  # 20 gwei
        elif strategy == GasStrategy.STANDARD:
            gas_price = 25_000_000_000  # 25 gwei
        elif strategy == GasStrategy.FAST:
            gas_price = 35_000_000_000  # 35 gwei
        else:  # URGENT
            gas_price = 50_000_000_000  # 50 gwei
        
        optimized_tx["gasPrice"] = gas_price
        
        return OptimizedTransaction(
            original_tx=tx_params,
            optimized_tx=optimized_tx,
            strategy_used=strategy,
            estimated_savings_gwei=0,
            estimated_savings_usd=Decimal("0"),
            gas_savings=0,
            time_estimate_seconds=60,
            confidence=0.5
        )
    
    def _create_fallback_gas_estimate(self) -> GasEstimate:
        """Create fallback gas estimate when APIs fail."""
        return GasEstimate(
            safe_low=20,
            standard=25,
            fast=35,
            instant=50,
            base_fee=18,
            priority_fee_low=2,
            priority_fee_standard=5,
            priority_fee_fast=10,
            confidence=0.3,
            timestamp=datetime.now()
        )
    
    async def _start_network_monitoring(self) -> None:
        """Start monitoring network conditions."""
        try:
            self.logger.info("Starting network monitoring...")
            
            while self.initialized:
                try:
                    await self._update_network_stats()
                    asyncio.create_task(self._update_gas_estimates())
                    await asyncio.sleep(30)  # Update every 30 seconds
                    
                except Exception as e:
                    self.logger.error(f"Network monitoring error: {e}")
                    await asyncio.sleep(60)
                    
        except Exception as e:
            self.logger.error(f"Network monitoring failed: {e}")
    
    async def _update_network_stats(self) -> None:
        """Update network condition statistics."""
        try:
            # Get latest block info
            latest_block = self.web3.eth.get_block("latest")
            
            # Update base fee
            base_fee_wei = latest_block.get("baseFeePerGas", 0)
            self.network_stats["current_base_fee"] = base_fee_wei // 1_000_000_000
            
            # Get pending transaction count
            pending_count = self.web3.eth.get_block_transaction_count("pending")
            self.network_stats["pending_transactions"] = pending_count
            
            # Estimate congestion level
            self._update_congestion_level()
            
            # Update optimization stats
            self.optimization_stats["current_base_fee_gwei"] = self.network_stats["current_base_fee"]
            self.optimization_stats["network_congestion"] = self.network_stats["congestion_level"]
            
        except Exception as e:
            self.logger.debug(f"Network stats update failed: {e}")
    
    def _update_congestion_level(self) -> None:
        """Update network congestion assessment."""
        try:
            base_fee = self.network_stats["current_base_fee"]
            pending_txs = self.network_stats["pending_transactions"]
            
            # Simple congestion heuristics
            if base_fee > 100 or pending_txs > 200000:
                congestion = "extreme"
            elif base_fee > 50 or pending_txs > 100000:
                congestion = "high"
            elif base_fee < 20 and pending_txs < 50000:
                congestion = "low"
            else:
                congestion = "normal"
            
            self.network_stats["congestion_level"] = congestion
            
        except Exception as e:
            self.logger.debug(f"Congestion level update failed: {e}")
    
    async def _update_gas_estimates(self) -> None:
        """Update gas price estimates and history."""
        try:
            gas_estimate = await self._get_current_gas_estimate()
            
            # Add to history
            self.gas_price_history.append({
                "timestamp": gas_estimate.timestamp,
                "base_fee": gas_estimate.base_fee,
                "standard": gas_estimate.standard,
                "fast": gas_estimate.fast
            })
            
            # Trim history
            if len(self.gas_price_history) > self.max_history_size:
                self.gas_price_history.pop(0)
            
            # Update trend
            self._update_gas_price_trend()
            
        except Exception as e:
            self.logger.debug(f"Gas estimates update failed: {e}")
    
    def _update_gas_price_trend(self) -> None:
        """Analyze gas price trends."""
        try:
            if len(self.gas_price_history) < 10:
                return
            
            recent_prices = [entry["standard"] for entry in self.gas_price_history[-10:]]
            older_prices = [entry["standard"] for entry in self.gas_price_history[-20:-10]]
            
            if not older_prices:
                return
            
            recent_avg = statistics.mean(recent_prices)
            older_avg = statistics.mean(older_prices)
            
            if recent_avg > older_avg * 1.1:
                self.network_stats["gas_price_trend"] = "rising"
            elif recent_avg < older_avg * 0.9:
                self.network_stats["gas_price_trend"] = "falling"
            else:
                self.network_stats["gas_price_trend"] = "stable"
                
        except Exception as e:
            self.logger.debug(f"Trend analysis failed: {e}")
    
    def _update_optimization_stats(self, strategy: GasStrategy, savings: Dict[str, Any]) -> None:
        """Update optimization statistics."""
        try:
            self.optimization_stats["total_optimizations"] += 1
            self.optimization_stats["total_savings_gwei"] += savings["savings_gwei"]
            self.optimization_stats["total_savings_usd"] += savings["savings_usd"]
            self.optimization_stats["strategy_usage"][strategy.value] += 1
            
            # Update average savings
            if self.optimization_stats["total_optimizations"] > 0:
                self.optimization_stats["average_savings_percent"] = (
                    savings["percent_saved"] + 
                    self.optimization_stats["average_savings_percent"] * 
                    (self.optimization_stats["total_optimizations"] - 1)
                ) / self.optimization_stats["total_optimizations"]
                
        except Exception as e:
            self.logger.debug(f"Stats update failed: {e}")
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get gas optimization statistics."""
        return self.optimization_stats.copy()
    
    def get_network_conditions(self) -> Dict[str, Any]:
        """Get current network conditions."""
        return self.network_stats.copy()