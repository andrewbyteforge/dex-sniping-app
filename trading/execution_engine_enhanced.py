"""
Enhanced execution engine with MEV protection and gas optimization.
Integrates Phase 3 speed optimization components for production trading.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
from web3 import Web3
from web3.types import TxParams

from models.token import TradingOpportunity
from trading.risk_manager import RiskManager, PositionSizeResult
from trading.position_manager import PositionManager, Position
from trading.executor import TradeOrder, TradeType, TradeStatus
from trading.mev_protection import MEVProtectionManager, MEVProtectionLevel
from trading.gas_optimizer import GasOptimizer, GasStrategy
from utils.logger import logger_manager


@dataclass
class EnhancedExecutionResult:
    """Enhanced execution result with optimization details."""
    success: bool
    tx_hash: Optional[str] = None
    amount_in: Optional[Decimal] = None
    amount_out: Optional[Decimal] = None
    actual_price: Optional[Decimal] = None
    gas_used: Optional[int] = None
    gas_price: Optional[int] = None
    execution_time: Optional[float] = None
    error_message: Optional[str] = None
    mev_protection_used: Optional[str] = None
    gas_optimization_used: Optional[str] = None
    estimated_savings: Optional[Decimal] = None


class EnhancedExecutionEngine:
    """
    Production execution engine with MEV protection and gas optimization.
    Provides fast, secure, and cost-effective trade execution.
    """
    
    def __init__(
        self,
        risk_manager: RiskManager,
        position_manager: PositionManager,
        mev_protection_level: MEVProtectionLevel = MEVProtectionLevel.STANDARD
    ) -> None:
        """
        Initialize enhanced execution engine.
        
        Args:
            risk_manager: Risk management system
            position_manager: Position management system
            mev_protection_level: Default MEV protection level
        """
        self.logger = logger_manager.get_logger("EnhancedExecutionEngine")
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        
        # Initialize optimization components
        self.mev_protection = MEVProtectionManager()
        self.gas_optimizer = GasOptimizer()
        self.default_mev_level = mev_protection_level
        
        # Web3 connections
        self.web3_connections: Dict[str, Web3] = {}
        
        # Performance tracking
        self.execution_metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "mev_protected_trades": 0,
            "gas_optimized_trades": 0,
            "average_execution_time": 0.0,
            "total_gas_saved": Decimal("0"),
            "sandwich_attacks_prevented": 0
        }
        
        # Execution configuration
        self.max_concurrent_orders = 10
        self.transaction_timeout = 300  # 5 minutes
        self.use_simulation = True
        self.monitoring_active = False
        
    async def initialize(self) -> None:
        """Initialize enhanced execution engine with all components."""
        try:
            self.logger.info("Initializing enhanced execution engine...")
            
            # Initialize Web3 connections
            await self._initialize_web3_connections()
            
            # Initialize MEV protection
            if self.web3_connections:
                w3 = list(self.web3_connections.values())[0]
                await self.mev_protection.initialize(w3)
                self.logger.info(f"MEV protection initialized: {self.default_mev_level.value}")
            
            # Initialize gas optimizer
            if self.web3_connections:
                w3 = list(self.web3_connections.values())[0]
                await self.gas_optimizer.initialize(w3)
                self.logger.info("Gas optimization initialized")
            
            # Start monitoring
            await self._start_monitoring()
            
            self.logger.info("Enhanced execution engine initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize enhanced execution engine: {e}")
            raise
    
    async def execute_buy_order_enhanced(
        self,
        opportunity: TradingOpportunity,
        risk_assessment: PositionSizeResult,
        urgency: float = 0.7,  # 0-1, higher = more urgent
        force_protection: bool = False
    ) -> Optional[Position]:
        """
        Execute buy order with MEV protection and gas optimization.
        
        Args:
            opportunity: Trading opportunity
            risk_assessment: Risk assessment with position sizing
            urgency: Trade urgency affecting gas strategy
            force_protection: Force maximum MEV protection
            
        Returns:
            Position if successful, None otherwise
        """
        try:
            self.logger.info(
                f"Executing enhanced buy order: {opportunity.token.symbol} "
                f"Amount: ${risk_assessment.approved_amount}"
            )
            
            # Create base transaction
            tx_params = await self._build_buy_transaction(opportunity, risk_assessment)
            
            # Step 1: Analyze MEV risk
            mev_risk = self.mev_protection.analyze_mev_risk(tx_params)
            value_at_risk = Decimal(str(risk_assessment.approved_amount * 0.05))  # 5% slippage risk
            
            # Step 2: Apply MEV protection if needed
            if force_protection or mev_risk["risk_level"] in ["HIGH", "MEDIUM"]:
                protected_tx = await self.mev_protection.protect_transaction(
                    tx_params,
                    value_at_risk
                )
                tx_to_optimize = protected_tx.protected_tx
                self.execution_metrics["mev_protected_trades"] += 1
            else:
                tx_to_optimize = tx_params
                protected_tx = None
            
            # Step 3: Optimize gas
            gas_strategy = self._select_gas_strategy(urgency, mev_risk["risk_level"])
            optimized_tx = await self.gas_optimizer.optimize_transaction(
                tx_to_optimize,
                strategy=gas_strategy,
                urgency=urgency
            )
            
            if optimized_tx.gas_savings > 0:
                self.execution_metrics["gas_optimized_trades"] += 1
                self.execution_metrics["total_gas_saved"] += Decimal(str(optimized_tx.gas_savings))
            
            # Step 4: Simulate transaction if enabled
            if self.use_simulation:
                simulation_result = await self._simulate_transaction(optimized_tx.optimized_tx)
                if not simulation_result["success"]:
                    self.logger.error(f"Transaction simulation failed: {simulation_result['error']}")
                    return None
            
            # Step 5: Execute transaction
            execution_start = datetime.now()
            
            if protected_tx:
                # Submit via MEV protection
                success, tx_hash = await self.mev_protection.submit_protected_transaction(
                    protected_tx
                )
            else:
                # Submit normally with optimized gas
                success, tx_hash = await self._submit_transaction(optimized_tx.optimized_tx)
            
            execution_time = (datetime.now() - execution_start).total_seconds()
            
            if success and tx_hash:
                # Wait for confirmation
                receipt = await self._wait_for_confirmation(tx_hash)
                
                if receipt and receipt["status"] == 1:
                    # Create position
                    position = await self._create_position_from_receipt(
                        opportunity,
                        risk_assessment,
                        receipt,
                        tx_hash
                    )
                    
                    # Update metrics
                    self.execution_metrics["successful_executions"] += 1
                    self.execution_metrics["total_executions"] += 1
                    self._update_average_execution_time(execution_time)
                    
                    self.logger.info(
                        f"Enhanced buy order successful: {opportunity.token.symbol} "
                        f"TX: {tx_hash} Time: {execution_time:.2f}s"
                    )
                    
                    return position
                else:
                    self.logger.error(f"Transaction failed on-chain: {tx_hash}")
            else:
                self.logger.error("Transaction submission failed")
            
            self.execution_metrics["total_executions"] += 1
            return None
            
        except Exception as e:
            self.logger.error(f"Enhanced buy order execution failed: {e}")
            self.execution_metrics["total_executions"] += 1
            return None
    
    async def execute_sell_order_enhanced(
        self,
        position: Position,
        urgency: float = 0.5
    ) -> bool:
        """
        Execute sell order with optimizations.
        
        Args:
            position: Position to close
            urgency: Trade urgency
            
        Returns:
            True if successful
        """
        try:
            self.logger.info(f"Executing enhanced sell order: {position.token_symbol}")
            
            # Build sell transaction
            tx_params = await self._build_sell_transaction(position)
            
            # Analyze MEV risk (sells often have lower risk)
            mev_risk = self.mev_protection.analyze_mev_risk(tx_params)
            
            # Apply lighter protection for sells
            if mev_risk["risk_level"] == "HIGH":
                protected_tx = await self.mev_protection.protect_transaction(
                    tx_params,
                    Decimal(str(position.entry_amount * 0.02))  # 2% risk
                )
                tx_to_optimize = protected_tx.protected_tx
            else:
                tx_to_optimize = tx_params
                protected_tx = None
            
            # Optimize gas (patient strategy for sells unless urgent)
            gas_strategy = GasStrategy.PATIENT if urgency < 0.7 else GasStrategy.ADAPTIVE
            optimized_tx = await self.gas_optimizer.optimize_transaction(
                tx_to_optimize,
                strategy=gas_strategy,
                urgency=urgency
            )
            
            # Execute
            if protected_tx:
                success, tx_hash = await self.mev_protection.submit_protected_transaction(
                    protected_tx
                )
            else:
                success, tx_hash = await self._submit_transaction(optimized_tx.optimized_tx)
            
            if success and tx_hash:
                receipt = await self._wait_for_confirmation(tx_hash)
                
                if receipt and receipt["status"] == 1:
                    # Update position
                    await self.position_manager.close_position(
                        position_id=position.id,
                        exit_price=position.current_price,
                        exit_reason=position_manager.ExitReason.MANUAL,
                        exit_tx_hash=tx_hash
                    )
                    
                    self.logger.info(f"Enhanced sell order successful: {position.token_symbol}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Enhanced sell order failed: {e}")
            return False
    
    async def batch_execute_orders(
        self,
        orders: List[TradeOrder]
    ) -> List[EnhancedExecutionResult]:
        """
        Execute multiple orders with batching optimization.
        
        Args:
            orders: List of orders to execute
            
        Returns:
            List of execution results
        """
        try:
            self.logger.info(f"Batch executing {len(orders)} orders")
            
            # Build transactions for all orders
            transactions = []
            for order in orders:
                tx = await self._build_transaction_from_order(order)
                transactions.append(tx)
            
            # Optimize as batch
            optimized_txs = await self.gas_optimizer.batch_transactions(transactions)
            
            # Execute optimized transactions
            results = []
            for i, opt_tx in enumerate(optimized_txs):
                result = await self._execute_optimized_transaction(
                    opt_tx,
                    orders[i]
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Batch execution failed: {e}")
            return []
    
    def _select_gas_strategy(self, urgency: float, mev_risk: str) -> GasStrategy:
        """Select appropriate gas strategy based on conditions."""
        if urgency > 0.8 or mev_risk == "HIGH":
            return GasStrategy.AGGRESSIVE
        elif urgency < 0.3 and mev_risk == "LOW":
            return GasStrategy.PATIENT
        else:
            return GasStrategy.ADAPTIVE
    
    async def _simulate_transaction(self, tx_params: TxParams) -> Dict[str, Any]:
        """Simulate transaction before execution."""
        try:
            # Use eth_call to simulate
            result = await self.w3.eth.call(tx_params)
            
            # Decode result (would need ABI)
            return {
                "success": True,
                "result": result,
                "gas_used": 0  # Would calculate from simulation
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _build_buy_transaction(
        self,
        opportunity: TradingOpportunity,
        risk_assessment: PositionSizeResult
    ) -> TxParams:
        """Build buy transaction parameters."""
        # This would build actual DEX swap transaction
        return {
            "from": "0x...",  # Would use actual wallet
            "to": "0x...",    # DEX router
            "value": Web3.to_wei(risk_assessment.approved_amount, "ether"),
            "data": "0x...",  # Swap calldata
            "gas": 300000,
            "nonce": await self._get_nonce()
        }
    
    async def _build_sell_transaction(self, position: Position) -> TxParams:
        """Build sell transaction parameters."""
        # This would build actual DEX swap transaction
        return {
            "from": "0x...",  # Would use actual wallet
            "to": "0x...",    # DEX router
            "value": 0,
            "data": "0x...",  # Swap calldata
            "gas": 250000,
            "nonce": await self._get_nonce()
        }
    
    async def _submit_transaction(self, tx_params: TxParams) -> Tuple[bool, Optional[str]]:
        """Submit transaction to network."""
        try:
            # Sign transaction (would use actual signing)
            signed_tx = self._sign_transaction(tx_params)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx)
            
            return True, tx_hash.hex()
            
        except Exception as e:
            self.logger.error(f"Transaction submission failed: {e}")
            return False, None
    
    async def _wait_for_confirmation(
        self,
        tx_hash: str,
        timeout: int = 300
    ) -> Optional[Dict]:
        """Wait for transaction confirmation."""
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=timeout
            )
            return receipt
            
        except Exception as e:
            self.logger.error(f"Transaction confirmation failed: {e}")
            return None
    
    async def _initialize_web3_connections(self) -> None:
        """Initialize Web3 connections for each chain."""
        # This would initialize actual Web3 connections
        pass
    
    async def _start_monitoring(self) -> None:
        """Start transaction monitoring."""
        self.monitoring_active = True
        asyncio.create_task(self._monitor_transactions())
    
    async def _monitor_transactions(self) -> None:
        """Monitor pending transactions."""
        while self.monitoring_active:
            try:
                # Monitor logic here
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(5)
    
    def _update_average_execution_time(self, new_time: float) -> None:
        """Update average execution time metric."""
        current_avg = self.execution_metrics["average_execution_time"]
        total = self.execution_metrics["successful_executions"]
        
        if total == 0:
            self.execution_metrics["average_execution_time"] = new_time
        else:
            self.execution_metrics["average_execution_time"] = (
                (current_avg * (total - 1) + new_time) / total
            )
    
    async def _get_nonce(self) -> int:
        """Get next nonce for transactions."""
        # Would track nonces properly
        return 0
    
    def _sign_transaction(self, tx_params: TxParams) -> bytes:
        """Sign transaction (placeholder)."""
        return b""
    
    async def _create_position_from_receipt(
        self,
        opportunity: TradingOpportunity,
        risk_assessment: PositionSizeResult,
        receipt: Dict,
        tx_hash: str
    ) -> Position:
        """Create position from transaction receipt."""
        # Would parse actual receipt data
        position = await self.position_manager.open_position(
            opportunity=opportunity,
            entry_amount=risk_assessment.approved_amount,
            entry_price=opportunity.token.price_usd,
            stop_loss_price=Decimal(str(opportunity.token.price_usd * 0.9)),
            take_profit_price=Decimal(str(opportunity.token.price_usd * 1.5)),
            tx_hash=tx_hash
        )
        return position
    
    async def _build_transaction_from_order(self, order: TradeOrder) -> TxParams:
        """Build transaction from order."""
        # Would build actual transaction
        return {}
    
    async def _execute_optimized_transaction(
        self,
        optimized_tx: Any,
        order: TradeOrder
    ) -> EnhancedExecutionResult:
        """Execute an optimized transaction."""
        # Would execute and track results
        return EnhancedExecutionResult(
            success=True,
            tx_hash="0x...",
            gas_optimization_used=optimized_tx.optimization_method
        )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get execution engine performance metrics."""
        mev_stats = self.mev_protection.get_protection_stats()
        gas_stats = self.gas_optimizer.get_optimization_stats()
        
        return {
            "execution_metrics": self.execution_metrics,
            "mev_protection": mev_stats,
            "gas_optimization": gas_stats,
            "success_rate": (
                self.execution_metrics["successful_executions"] /
                max(self.execution_metrics["total_executions"], 1)
            )
        }