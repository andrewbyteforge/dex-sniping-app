"""
Advanced gas optimization strategies for DEX trading.
Implements dynamic gas pricing, transaction batching, and efficiency improvements.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import statistics
from web3 import Web3
from web3.types import TxParams, Wei

from utils.logger import logger_manager


class GasStrategy(Enum):
    """Gas pricing strategies."""
    AGGRESSIVE = "aggressive"  # Higher gas for faster inclusion
    STANDARD = "standard"      # Market rate
    PATIENT = "patient"        # Lower gas, wait for inclusion
    ADAPTIVE = "adaptive"      # Dynamic based on conditions
    BATCH = "batch"           # Batch multiple transactions


@dataclass
class GasAnalysis:
    """Gas market analysis results."""
    base_fee: Wei
    priority_fee: Wei
    estimated_total: Wei
    inclusion_probability: float
    estimated_wait_blocks: int
    gas_limit: int
    optimization_suggestions: List[str]


@dataclass
class OptimizedTransaction:
    """Transaction with gas optimizations applied."""
    original_tx: TxParams
    optimized_tx: TxParams
    gas_savings: Wei
    optimization_method: str
    estimated_inclusion_time: int  # blocks


class GasOptimizer:
    """
    Advanced gas optimization for DEX trading transactions.
    Reduces costs while maintaining competitive execution speed.
    """
    
    def __init__(self) -> None:
        """Initialize the gas optimization system."""
        self.logger = logger_manager.get_logger("GasOptimizer")
        self.w3: Optional[Web3] = None
        
        # Gas price history tracking
        self.gas_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
        
        # Optimization statistics
        self.stats = {
            "transactions_optimized": 0,
            "total_gas_saved": Wei(0),
            "average_savings_percentage": 0.0,
            "successful_inclusions": 0,
            "failed_inclusions": 0
        }
        
        # Strategy configurations
        self.strategy_configs = {
            GasStrategy.AGGRESSIVE: {
                "priority_multiplier": 1.5,
                "max_wait_blocks": 1,
                "retry_escalation": 1.2
            },
            GasStrategy.STANDARD: {
                "priority_multiplier": 1.0,
                "max_wait_blocks": 3,
                "retry_escalation": 1.1
            },
            GasStrategy.PATIENT: {
                "priority_multiplier": 0.7,
                "max_wait_blocks": 10,
                "retry_escalation": 1.05
            },
            GasStrategy.ADAPTIVE: {
                "priority_multiplier": 1.0,  # Dynamically adjusted
                "max_wait_blocks": 5,
                "retry_escalation": 1.15
            }
        }
        
        # Transaction batching
        self.pending_batch: List[TxParams] = []
        self.batch_timeout = 5  # seconds
        self.max_batch_size = 5
        
    async def initialize(self, w3: Web3) -> None:
        """
        Initialize gas optimizer with Web3 connection.
        
        Args:
            w3: Web3 instance for blockchain interaction
        """
        try:
            self.logger.info("Initializing gas optimization system...")
            self.w3 = w3
            
            # Start gas price monitoring
            asyncio.create_task(self._monitor_gas_prices())
            
            # Load historical gas data if available
            await self._load_gas_history()
            
            self.logger.info("Gas optimizer initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize gas optimizer: {e}")
            raise
    
    async def optimize_transaction(
        self,
        tx_params: TxParams,
        strategy: GasStrategy = GasStrategy.ADAPTIVE,
        urgency: float = 0.5  # 0 = patient, 1 = urgent
    ) -> OptimizedTransaction:
        """
        Optimize gas parameters for a transaction.
        
        Args:
            tx_params: Original transaction parameters
            strategy: Gas optimization strategy to use
            urgency: Transaction urgency (0-1)
            
        Returns:
            OptimizedTransaction with optimizations applied
        """
        try:
            self.logger.debug(f"Optimizing transaction with {strategy.value} strategy")
            
            # Analyze current gas market
            gas_analysis = await self._analyze_gas_market()
            
            # Apply strategy-specific optimizations
            if strategy == GasStrategy.BATCH:
                return await self._optimize_for_batching(tx_params, gas_analysis)
            else:
                optimized_tx = await self._apply_gas_strategy(
                    tx_params, 
                    gas_analysis, 
                    strategy, 
                    urgency
                )
            
            # Calculate savings
            original_cost = self._calculate_gas_cost(tx_params)
            optimized_cost = self._calculate_gas_cost(optimized_tx)
            savings = original_cost - optimized_cost
            
            self.stats["transactions_optimized"] += 1
            self.stats["total_gas_saved"] += savings
            
            return OptimizedTransaction(
                original_tx=tx_params,
                optimized_tx=optimized_tx,
                gas_savings=savings,
                optimization_method=strategy.value,
                estimated_inclusion_time=gas_analysis.estimated_wait_blocks
            )
            
        except Exception as e:
            self.logger.error(f"Failed to optimize transaction: {e}")
            # Return original transaction if optimization fails
            return OptimizedTransaction(
                original_tx=tx_params,
                optimized_tx=tx_params,
                gas_savings=Wei(0),
                optimization_method="none",
                estimated_inclusion_time=1
            )
    
    async def estimate_optimal_gas(
        self,
        tx_params: TxParams,
        target_inclusion_blocks: int = 2
    ) -> GasAnalysis:
        """
        Estimate optimal gas price for target inclusion time.
        
        Args:
            tx_params: Transaction parameters
            target_inclusion_blocks: Desired inclusion within N blocks
            
        Returns:
            GasAnalysis with recommendations
        """
        try:
            # Get current gas market data
            analysis = await self._analyze_gas_market()
            
            # Adjust for target inclusion time
            if target_inclusion_blocks <= 1:
                # Need aggressive pricing
                analysis.priority_fee = Wei(int(analysis.priority_fee * 1.5))
                analysis.optimization_suggestions.append("Use aggressive gas pricing for fast inclusion")
            elif target_inclusion_blocks >= 5:
                # Can use patient pricing
                analysis.priority_fee = Wei(int(analysis.priority_fee * 0.7))
                analysis.optimization_suggestions.append("Use patient gas pricing to save costs")
            
            # Estimate gas limit
            if "data" in tx_params and tx_params["data"]:
                # Complex transaction, estimate higher
                estimated_gas = await self._estimate_gas_usage(tx_params)
                analysis.gas_limit = int(estimated_gas * 1.1)  # 10% buffer
            
            # Calculate total estimated cost
            analysis.estimated_total = Wei(
                (analysis.base_fee + analysis.priority_fee) * analysis.gas_limit
            )
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Failed to estimate optimal gas: {e}")
            return self._get_fallback_gas_analysis()
    
    async def batch_transactions(
        self,
        transactions: List[TxParams]
    ) -> List[OptimizedTransaction]:
        """
        Batch multiple transactions for gas efficiency.
        
        Args:
            transactions: List of transactions to batch
            
        Returns:
            List of optimized transactions
        """
        try:
            self.logger.info(f"Batching {len(transactions)} transactions")
            
            # Group transactions by target
            batches = self._group_transactions_for_batching(transactions)
            optimized_txs = []
            
            for batch in batches:
                if len(batch) > 1:
                    # Create multicall transaction
                    multicall_tx = await self._create_multicall_transaction(batch)
                    
                    # Optimize the multicall
                    optimized = await self.optimize_transaction(
                        multicall_tx,
                        strategy=GasStrategy.STANDARD
                    )
                    optimized_txs.append(optimized)
                else:
                    # Single transaction, optimize normally
                    optimized = await self.optimize_transaction(
                        batch[0],
                        strategy=GasStrategy.ADAPTIVE
                    )
                    optimized_txs.append(optimized)
            
            return optimized_txs
            
        except Exception as e:
            self.logger.error(f"Failed to batch transactions: {e}")
            # Fall back to individual optimization
            return [
                await self.optimize_transaction(tx, GasStrategy.STANDARD)
                for tx in transactions
            ]
    
    async def _analyze_gas_market(self) -> GasAnalysis:
        """Analyze current gas market conditions."""
        try:
            # Get latest block
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block.get('baseFeePerGas', Wei(0))
            
            # Calculate priority fee from recent transactions
            priority_fees = await self._get_recent_priority_fees()
            
            # Use 60th percentile for standard inclusion
            priority_fee = Wei(int(statistics.quantile(priority_fees, 0.6)))
            
            # Estimate inclusion probability
            inclusion_prob = self._estimate_inclusion_probability(
                base_fee + priority_fee
            )
            
            # Estimate wait time
            wait_blocks = self._estimate_wait_blocks(inclusion_prob)
            
            suggestions = []
            
            # Provide optimization suggestions
            if base_fee > Wei(100 * 10**9):  # > 100 gwei
                suggestions.append("High network congestion - consider delaying non-urgent transactions")
            
            if len(self.gas_history) > 100:
                avg_base_fee = statistics.mean([h['base_fee'] for h in self.gas_history[-100:]])
                if base_fee < avg_base_fee * 0.8:
                    suggestions.append("Gas prices below average - good time for transactions")
            
            return GasAnalysis(
                base_fee=base_fee,
                priority_fee=priority_fee,
                estimated_total=base_fee + priority_fee,
                inclusion_probability=inclusion_prob,
                estimated_wait_blocks=wait_blocks,
                gas_limit=21000,  # Default, will be updated
                optimization_suggestions=suggestions
            )
            
        except Exception as e:
            self.logger.error(f"Gas market analysis failed: {e}")
            return self._get_fallback_gas_analysis()
    
    async def _apply_gas_strategy(
        self,
        tx_params: TxParams,
        gas_analysis: GasAnalysis,
        strategy: GasStrategy,
        urgency: float
    ) -> TxParams:
        """Apply specific gas strategy to transaction."""
        try:
            optimized = tx_params.copy()
            config = self.strategy_configs[strategy]
            
            # Calculate gas prices based on strategy
            if strategy == GasStrategy.ADAPTIVE:
                # Dynamically adjust based on urgency and market
                multiplier = 0.7 + (urgency * 0.8)  # 0.7x to 1.5x
                priority_fee = Wei(int(gas_analysis.priority_fee * multiplier))
            else:
                priority_fee = Wei(
                    int(gas_analysis.priority_fee * config["priority_multiplier"])
                )
            
            # Set EIP-1559 gas parameters
            optimized["maxFeePerGas"] = Wei(gas_analysis.base_fee * 2 + priority_fee)
            optimized["maxPriorityFeePerGas"] = priority_fee
            
            # Optimize gas limit
            if "gas" not in optimized:
                estimated_gas = await self._estimate_gas_usage(tx_params)
                # Add buffer based on strategy
                buffer = 1.05 if strategy == GasStrategy.PATIENT else 1.1
                optimized["gas"] = int(estimated_gas * buffer)
            
            # Remove legacy gas price if present
            if "gasPrice" in optimized:
                del optimized["gasPrice"]
            
            return optimized
            
        except Exception as e:
            self.logger.error(f"Failed to apply gas strategy: {e}")
            return tx_params
    
    async def _optimize_for_batching(
        self,
        tx_params: TxParams,
        gas_analysis: GasAnalysis
    ) -> OptimizedTransaction:
        """Optimize transaction for batching."""
        try:
            # Add to pending batch
            self.pending_batch.append(tx_params)
            
            # Check if batch should be sent
            should_send = (
                len(self.pending_batch) >= self.max_batch_size or
                self._is_batch_timeout()
            )
            
            if should_send:
                # Create and optimize batch transaction
                batch_tx = await self._create_multicall_transaction(self.pending_batch)
                self.pending_batch = []
                
                return await self.optimize_transaction(
                    batch_tx,
                    strategy=GasStrategy.STANDARD
                )
            else:
                # Return placeholder for now
                return OptimizedTransaction(
                    original_tx=tx_params,
                    optimized_tx=tx_params,
                    gas_savings=Wei(0),
                    optimization_method="pending_batch",
                    estimated_inclusion_time=0
                )
                
        except Exception as e:
            self.logger.error(f"Batch optimization failed: {e}")
            return await self.optimize_transaction(tx_params, GasStrategy.STANDARD)
    
    async def _monitor_gas_prices(self) -> None:
        """Monitor gas prices continuously."""
        while True:
            try:
                latest_block = self.w3.eth.get_block('latest')
                
                gas_data = {
                    "timestamp": datetime.now(),
                    "block_number": latest_block['number'],
                    "base_fee": latest_block.get('baseFeePerGas', 0),
                    "gas_used": latest_block['gasUsed'],
                    "gas_limit": latest_block['gasLimit']
                }
                
                self.gas_history.append(gas_data)
                
                # Trim history if too large
                if len(self.gas_history) > self.max_history_size:
                    self.gas_history = self.gas_history[-self.max_history_size:]
                
                # Wait for next block
                await asyncio.sleep(12)  # ~1 block time
                
            except Exception as e:
                self.logger.error(f"Gas monitoring error: {e}")
                await asyncio.sleep(30)
    
    async def _get_recent_priority_fees(self) -> List[Wei]:
        """Get priority fees from recent transactions."""
        try:
            latest_block = self.w3.eth.get_block('latest', full_transactions=True)
            priority_fees = []
            
            for tx in latest_block['transactions'][:20]:  # Sample 20 transactions
                if 'maxPriorityFeePerGas' in tx:
                    priority_fees.append(tx['maxPriorityFeePerGas'])
                elif 'gasPrice' in tx and 'baseFeePerGas' in latest_block:
                    # Calculate priority fee from legacy transaction
                    priority = tx['gasPrice'] - latest_block['baseFeePerGas']
                    if priority > 0:
                        priority_fees.append(Wei(priority))
            
            # Ensure we have some data
            if not priority_fees:
                priority_fees = [Wei(2 * 10**9)]  # Default 2 gwei
            
            return priority_fees
            
        except Exception as e:
            self.logger.error(f"Failed to get recent priority fees: {e}")
            return [Wei(2 * 10**9)]  # Default fallback
    
    def _estimate_inclusion_probability(self, total_fee: Wei) -> float:
        """Estimate probability of inclusion based on fee."""
        try:
            if not self.gas_history:
                return 0.5
            
            # Compare to recent included transactions
            recent_fees = [h['base_fee'] for h in self.gas_history[-50:]]
            percentile = statistics.quantiles(recent_fees, n=100)
            
            # Find position in distribution
            position = 0
            for i, fee in enumerate(percentile):
                if total_fee >= fee:
                    position = i + 1
                else:
                    break
            
            return position / 100
            
        except Exception:
            return 0.5
    
    def _estimate_wait_blocks(self, inclusion_probability: float) -> int:
        """Estimate blocks to wait based on inclusion probability."""
        if inclusion_probability >= 0.9:
            return 1
        elif inclusion_probability >= 0.7:
            return 2
        elif inclusion_probability >= 0.5:
            return 3
        elif inclusion_probability >= 0.3:
            return 5
        else:
            return 10
    
    async def _estimate_gas_usage(self, tx_params: TxParams) -> int:
        """Estimate gas usage for transaction."""
        try:
            # Use eth_estimateGas
            estimated = self.w3.eth.estimate_gas(tx_params)
            return estimated
        except Exception:
            # Fallback estimates based on transaction type
            if tx_params.get("data"):
                return 200000  # Contract interaction
            else:
                return 21000   # Simple transfer
    
    def _calculate_gas_cost(self, tx_params: TxParams) -> Wei:
        """Calculate total gas cost for transaction."""
        gas_limit = tx_params.get("gas", 21000)
        
        if "maxFeePerGas" in tx_params:
            return Wei(gas_limit * tx_params["maxFeePerGas"])
        elif "gasPrice" in tx_params:
            return Wei(gas_limit * tx_params["gasPrice"])
        else:
            return Wei(0)
    
    def _group_transactions_for_batching(
        self, 
        transactions: List[TxParams]
    ) -> List[List[TxParams]]:
        """Group transactions that can be batched together."""
        # Group by target contract
        groups: Dict[str, List[TxParams]] = {}
        
        for tx in transactions:
            target = tx.get("to", "unknown")
            if target not in groups:
                groups[target] = []
            groups[target].append(tx)
        
        # Convert to list of batches
        batches = []
        for group in groups.values():
            # Split large groups
            for i in range(0, len(group), self.max_batch_size):
                batches.append(group[i:i + self.max_batch_size])
        
        return batches
    
    async def _create_multicall_transaction(
        self, 
        transactions: List[TxParams]
    ) -> TxParams:
        """Create a multicall transaction from multiple transactions."""
        # This would implement actual multicall encoding
        # For now, return first transaction as placeholder
        return transactions[0] if transactions else {}
    
    def _is_batch_timeout(self) -> bool:
        """Check if batch timeout has been reached."""
        # Implement batch timeout logic
        return False
    
    async def _load_gas_history(self) -> None:
        """Load historical gas data."""
        # This would load from persistent storage
        pass
    
    def _get_fallback_gas_analysis(self) -> GasAnalysis:
        """Get fallback gas analysis when real analysis fails."""
        return GasAnalysis(
            base_fee=Wei(30 * 10**9),  # 30 gwei
            priority_fee=Wei(2 * 10**9),  # 2 gwei
            estimated_total=Wei(32 * 10**9),
            inclusion_probability=0.5,
            estimated_wait_blocks=3,
            gas_limit=200000,
            optimization_suggestions=["Using fallback gas estimates"]
        )
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get gas optimization statistics."""
        total_optimized = self.stats["transactions_optimized"]
        
        return {
            "transactions_optimized": total_optimized,
            "total_gas_saved_gwei": self.w3.from_wei(self.stats["total_gas_saved"], "gwei"),
            "average_savings_percentage": (
                self.stats["average_savings_percentage"] if total_optimized > 0 else 0
            ),
            "success_rate": (
                self.stats["successful_inclusions"] / 
                max(self.stats["successful_inclusions"] + self.stats["failed_inclusions"], 1)
            ),
            "current_base_fee_gwei": (
                self.w3.from_wei(self.gas_history[-1]["base_fee"], "gwei") 
                if self.gas_history else 0
            )
        }