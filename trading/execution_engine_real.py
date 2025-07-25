#!/usr/bin/env python3
"""
Real execution engine implementation with actual trading capabilities.
Integrates wallet management, DEX interactions, and comprehensive error handling.

File: trading/execution_engine_real.py
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid
from web3 import Web3
from web3.types import TxParams, Wei, TxReceipt, BlockData
from web3.exceptions import TransactionNotFound, TimeExhausted
import json

from models.token import TradingOpportunity
from trading.risk_manager import RiskManager, PositionSizeResult
from trading.position_manager import PositionManager, Position, PositionStatus, ExitReason
from trading.wallet_manager import WalletManager
from trading.dex_manager import DEXManager
from trading.execution_engine import TradeOrder, OrderType, OrderStatus, ExecutionResult
from utils.logger import logger_manager


class TransactionStatus(Enum):
    """Transaction execution status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    REVERTED = "reverted"


class RealExecutionEngine:
    """
    Production execution engine with real trading capabilities.
    
    Features:
    - Actual DEX contract interactions
    - Real transaction submission and monitoring
    - Wallet integration with secure signing
    - Comprehensive error handling and recovery
    - Transaction confirmation tracking
    - Gas optimization and retry logic
    """
    
    def __init__(
        self,
        risk_manager: RiskManager,
        position_manager: PositionManager,
        wallet_manager: WalletManager,
        dex_manager: DEXManager
    ) -> None:
        """
        Initialize real execution engine.
        
        Args:
            risk_manager: Risk management system
            position_manager: Position management system
            wallet_manager: Wallet management system
            dex_manager: DEX interaction manager
        """
        self.logger = logger_manager.get_logger("RealExecutionEngine")
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        self.wallet_manager = wallet_manager
        self.dex_manager = dex_manager
        
        # Configuration
        self.default_wallet = "main"
        self.default_slippage = Decimal("0.05")  # 5%
        self.confirmation_blocks = 3
        self.max_confirmation_time = 300  # 5 minutes
        self.max_retries = 3
        self.gas_multiplier = Decimal("1.2")  # 20% gas buffer
        
        # Transaction tracking
        self.pending_transactions: Dict[str, Dict[str, Any]] = {}
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_gas_used": 0,
            "total_gas_cost": Decimal("0"),
            "average_confirmation_time": 0.0
        }
        
        # Web3 connections
        self.web3_connections: Dict[str, Web3] = {}
        
        self.logger.info("🔥 RealExecutionEngine initialized - LIVE TRADING ENABLED")

    async def initialize(self, web3_connections: Dict[str, Web3]) -> None:
        """
        Initialize the execution engine with Web3 connections.
        
        Args:
            web3_connections: Dictionary of chain -> Web3 connections
        """
        try:
            self.logger.info("Initializing real execution engine...")
            
            # Store Web3 connections
            self.web3_connections = web3_connections
            
            # Initialize DEX manager with connections
            for chain, w3 in web3_connections.items():
                self.dex_manager.add_web3_connection(chain, w3)
            
            # Start transaction monitoring
            asyncio.create_task(self._monitor_pending_transactions())
            
            # Load wallets from environment
            self.wallet_manager.load_from_env()
            
            # Validate setup
            await self._validate_setup()
            
            self.logger.info("✅ Real execution engine initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize real execution engine: {e}")
            raise

    async def execute_buy_order(
        self,
        opportunity: TradingOpportunity,
        position_size_result: PositionSizeResult,
        wallet_name: Optional[str] = None,
        slippage_tolerance: Optional[Decimal] = None,
        gas_strategy: str = "standard"
    ) -> Optional[Position]:
        """
        Execute a real buy order on a DEX.
        
        Args:
            opportunity: Trading opportunity to execute
            position_size_result: Position sizing and risk assessment
            wallet_name: Wallet to use (defaults to main wallet)
            slippage_tolerance: Maximum slippage (defaults to 5%)
            gas_strategy: Gas strategy (fast, standard, slow)
            
        Returns:
            Position object if successful, None if failed
        """
        wallet_name = wallet_name or self.default_wallet
        slippage_tolerance = slippage_tolerance or self.default_slippage
        
        try:
            self.logger.info(
                f"🔥 EXECUTING REAL BUY ORDER: {opportunity.token.symbol} "
                f"({opportunity.chain}) - Amount: {position_size_result.approved_amount} ETH"
            )
            
            # Pre-execution validation
            validation_result = await self._validate_trade_execution(
                opportunity, position_size_result, wallet_name
            )
            
            if not validation_result["valid"]:
                self.logger.error(f"Trade validation failed: {validation_result['reason']}")
                return None
            
            # Calculate minimum tokens to receive (slippage protection)
            estimated_tokens = await self._estimate_tokens_out(
                opportunity, position_size_result.approved_amount
            )
            
            min_tokens_out = estimated_tokens * (Decimal("1") - slippage_tolerance)
            
            self.logger.info(
                f"Expected tokens: {estimated_tokens:.6f}, "
                f"Min with slippage: {min_tokens_out:.6f}"
            )
            
            # Get optimal gas settings
            gas_settings = await self._get_gas_settings(opportunity.chain, gas_strategy)
            
            # Execute swap on DEX
            swap_result = await self.dex_manager.swap_eth_for_tokens(
                token_address=opportunity.token.address,
                amount_eth=position_size_result.approved_amount,
                min_tokens=min_tokens_out,
                wallet_name=wallet_name,
                chain=opportunity.chain,
                router="uniswap_v2",  # Default router
                deadline_minutes=20,
                gas_price=gas_settings["gas_price"],
                gas_limit=gas_settings["gas_limit"]
            )
            
            if not swap_result or not swap_result.get("tx_hash"):
                self.logger.error("DEX swap failed - no transaction hash")
                return None
            
            tx_hash = swap_result["tx_hash"]
            self.logger.info(f"🚀 Transaction submitted: {tx_hash}")
            
            # Monitor transaction confirmation
            confirmation_result = await self._monitor_transaction(
                tx_hash, opportunity.chain, timeout=self.max_confirmation_time
            )
            
            if confirmation_result["status"] != TransactionStatus.CONFIRMED:
                self.logger.error(
                    f"Transaction failed: {confirmation_result['status'].value} - "
                    f"{confirmation_result.get('error', 'Unknown error')}"
                )
                return None
            
            # Calculate actual execution results
            receipt = confirmation_result["receipt"]
            actual_results = await self._calculate_execution_results(
                receipt, opportunity, position_size_result.approved_amount
            )
            
            # Create position
            position = await self._create_position_from_execution(
                opportunity, actual_results, tx_hash, wallet_name
            )
            
            # Update statistics
            self._update_execution_stats(confirmation_result, actual_results)
            
            self.logger.info(
                f"✅ BUY ORDER COMPLETED: {opportunity.token.symbol} - "
                f"Tokens received: {actual_results['tokens_received']:.6f}, "
                f"Actual price: ${actual_results['actual_price']:.8f}, "
                f"Gas cost: ${actual_results['gas_cost_usd']:.2f}"
            )
            
            return position
            
        except Exception as e:
            self.logger.error(f"Buy order execution failed: {e}")
            self.execution_stats["failed_executions"] += 1
            return None

    async def execute_sell_order(
        self,
        position: Position,
        sell_percentage: Decimal = Decimal("1.0"),  # 100% by default
        wallet_name: Optional[str] = None,
        slippage_tolerance: Optional[Decimal] = None,
        gas_strategy: str = "fast"  # Faster for exits
    ) -> Optional[ExecutionResult]:
        """
        Execute a real sell order to close a position.
        
        Args:
            position: Position to close
            sell_percentage: Percentage of position to sell (0.0 to 1.0)
            wallet_name: Wallet to use
            slippage_tolerance: Maximum slippage tolerance
            gas_strategy: Gas strategy for execution
            
        Returns:
            ExecutionResult if successful, None if failed
        """
        wallet_name = wallet_name or self.default_wallet
        slippage_tolerance = slippage_tolerance or self.default_slippage
        
        try:
            # Calculate sell amount
            sell_amount = position.entry_amount * sell_percentage
            
            self.logger.info(
                f"🔥 EXECUTING REAL SELL ORDER: {position.token_symbol} - "
                f"Amount: {sell_amount:.6f} tokens ({sell_percentage * 100:.1f}%)"
            )
            
            # Check token balance
            token_balance = await self.wallet_manager.get_balance(
                wallet_name, position.chain, position.token_address
            )
            
            if token_balance < sell_amount:
                self.logger.error(
                    f"Insufficient token balance: {token_balance:.6f} < {sell_amount:.6f}"
                )
                return None
            
            # Check/approve token spending
            router_address = self.dex_manager.ROUTERS[position.chain]["uniswap_v2"]
            await self._ensure_token_approval(
                position.token_address, router_address, sell_amount, 
                wallet_name, position.chain
            )
            
            # Estimate ETH output
            estimated_eth = await self._estimate_eth_out(position, sell_amount)
            min_eth_out = estimated_eth * (Decimal("1") - slippage_tolerance)
            
            self.logger.info(
                f"Expected ETH: {estimated_eth:.6f}, "
                f"Min with slippage: {min_eth_out:.6f}"
            )
            
            # Get gas settings
            gas_settings = await self._get_gas_settings(position.chain, gas_strategy)
            
            # Execute swap
            swap_result = await self.dex_manager.swap_tokens_for_eth(
                token_address=position.token_address,
                amount_tokens=sell_amount,
                min_eth=min_eth_out,
                wallet_name=wallet_name,
                chain=position.chain,
                router="uniswap_v2",
                deadline_minutes=10,  # Shorter deadline for exits
                gas_price=gas_settings["gas_price"],
                gas_limit=gas_settings["gas_limit"]
            )
            
            if not swap_result or not swap_result.get("tx_hash"):
                self.logger.error("Sell swap failed - no transaction hash")
                return None
            
            tx_hash = swap_result["tx_hash"]
            self.logger.info(f"🚀 Sell transaction submitted: {tx_hash}")
            
            # Monitor confirmation
            confirmation_result = await self._monitor_transaction(
                tx_hash, position.chain, timeout=self.max_confirmation_time
            )
            
            if confirmation_result["status"] != TransactionStatus.CONFIRMED:
                self.logger.error(f"Sell transaction failed: {confirmation_result['status'].value}")
                return None
            
            # Calculate results
            receipt = confirmation_result["receipt"]
            actual_results = await self._calculate_sell_results(
                receipt, position, sell_amount
            )
            
            # Update position
            if sell_percentage >= Decimal("0.99"):  # Consider 99%+ as full close
                await self.position_manager.close_position(
                    position.id,
                    exit_reason=ExitReason.MANUAL.value,
                    exit_price=actual_results["actual_price"],
                    exit_tx_hash=tx_hash
                )
            else:
                # Partial close - update position
                new_amount = position.entry_amount * (Decimal("1") - sell_percentage)
                position.entry_amount = new_amount
                await self.position_manager.update_position(position)
            
            self.logger.info(
                f"✅ SELL ORDER COMPLETED: {position.token_symbol} - "
                f"ETH received: {actual_results['eth_received']:.6f}, "
                f"PnL: ${actual_results['realized_pnl']:.2f}"
            )
            
            return ExecutionResult(
                success=True,
                order_id=str(uuid.uuid4()),
                tx_hash=tx_hash,
                amount_in=sell_amount,
                amount_out=actual_results["eth_received"],
                actual_price=actual_results["actual_price"],
                gas_used=receipt["gasUsed"],
                gas_cost=actual_results["gas_cost_usd"],
                execution_time=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Sell order execution failed: {e}")
            return None

    async def _validate_trade_execution(
        self,
        opportunity: TradingOpportunity,
        position_size_result: PositionSizeResult,
        wallet_name: str
    ) -> Dict[str, Any]:
        """
        Validate trade execution prerequisites.
        
        Args:
            opportunity: Trading opportunity
            position_size_result: Position sizing result
            wallet_name: Wallet to validate
            
        Returns:
            Validation result dictionary
        """
        try:
            # Check if chain is supported
            if opportunity.chain not in self.web3_connections:
                return {
                    "valid": False,
                    "reason": f"Chain {opportunity.chain} not supported"
                }
            
            # Check wallet exists
            if not self.wallet_manager.get_wallet_address(wallet_name):
                return {
                    "valid": False,
                    "reason": f"Wallet {wallet_name} not found"
                }
            
            # Check sufficient balance
            has_balance, actual_balance = self.wallet_manager.has_sufficient_balance(
                wallet_name, opportunity.chain, position_size_result.approved_amount
            )
            
            if not has_balance:
                return {
                    "valid": False,
                    "reason": f"Insufficient balance: {actual_balance:.6f} ETH available, "
                            f"{position_size_result.approved_amount:.6f} ETH required"
                }
            
            # Check network connectivity
            w3 = self.web3_connections[opportunity.chain]
            try:
                latest_block = w3.eth.block_number
                if latest_block == 0:
                    raise Exception("Invalid block number")
            except Exception:
                return {
                    "valid": False,
                    "reason": f"Network connection issue for {opportunity.chain}"
                }
            
            # Check token contract exists
            token_code = w3.eth.get_code(Web3.to_checksum_address(opportunity.token.address))
            if len(token_code) == 0:
                return {
                    "valid": False,
                    "reason": f"Token contract not found: {opportunity.token.address}"
                }
            
            return {"valid": True, "reason": "All validations passed"}
            
        except Exception as e:
            return {
                "valid": False,
                "reason": f"Validation error: {str(e)}"
            }

    async def _monitor_transaction(
        self,
        tx_hash: str,
        chain: str,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Monitor transaction confirmation with timeout.
        
        Args:
            tx_hash: Transaction hash to monitor
            chain: Chain identifier
            timeout: Maximum wait time in seconds
            
        Returns:
            Monitoring result dictionary
        """
        start_time = datetime.now()
        w3 = self.web3_connections[chain]
        
        try:
            self.logger.info(f"Monitoring transaction: {tx_hash} on {chain}")
            
            # Add to pending transactions
            self.pending_transactions[tx_hash] = {
                "chain": chain,
                "start_time": start_time,
                "status": TransactionStatus.PENDING
            }
            
            # Wait for confirmation
            while (datetime.now() - start_time).total_seconds() < timeout:
                try:
                    # Check if transaction is mined
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    
                    if receipt:
                        # Check if transaction succeeded
                        if receipt.status == 1:
                            # Wait for additional confirmations
                            current_block = w3.eth.block_number
                            confirmations = current_block - receipt.blockNumber
                            
                            if confirmations >= self.confirmation_blocks:
                                self.pending_transactions[tx_hash]["status"] = TransactionStatus.CONFIRMED
                                
                                confirmation_time = (datetime.now() - start_time).total_seconds()
                                
                                self.logger.info(
                                    f"✅ Transaction confirmed: {tx_hash} "
                                    f"(Block: {receipt.blockNumber}, "
                                    f"Confirmations: {confirmations}, "
                                    f"Time: {confirmation_time:.1f}s)"
                                )
                                
                                return {
                                    "status": TransactionStatus.CONFIRMED,
                                    "receipt": receipt,
                                    "confirmations": confirmations,
                                    "confirmation_time": confirmation_time
                                }
                            else:
                                self.logger.debug(
                                    f"Waiting for confirmations: {confirmations}/{self.confirmation_blocks}"
                                )
                        else:
                            # Transaction reverted
                            self.pending_transactions[tx_hash]["status"] = TransactionStatus.REVERTED
                            
                            self.logger.error(f"❌ Transaction reverted: {tx_hash}")
                            
                            return {
                                "status": TransactionStatus.REVERTED,
                                "receipt": receipt,
                                "error": "Transaction reverted"
                            }
                
                except TransactionNotFound:
                    # Transaction not yet mined
                    pass
                
                # Wait before next check
                await asyncio.sleep(5)
            
            # Timeout reached
            self.pending_transactions[tx_hash]["status"] = TransactionStatus.TIMEOUT
            
            self.logger.warning(f"⏰ Transaction timeout: {tx_hash}")
            
            return {
                "status": TransactionStatus.TIMEOUT,
                "error": f"Transaction confirmation timeout after {timeout}s"
            }
            
        except Exception as e:
            self.pending_transactions[tx_hash]["status"] = TransactionStatus.FAILED
            
            self.logger.error(f"❌ Transaction monitoring failed: {tx_hash} - {e}")
            
            return {
                "status": TransactionStatus.FAILED,
                "error": str(e)
            }
        finally:
            # Cleanup
            if tx_hash in self.pending_transactions:
                del self.pending_transactions[tx_hash]

    async def _estimate_tokens_out(
        self,
        opportunity: TradingOpportunity,
        eth_amount: Decimal
    ) -> Decimal:
        """
        Estimate tokens received for ETH amount.
        
        Args:
            opportunity: Trading opportunity
            eth_amount: ETH amount to spend
            
        Returns:
            Estimated tokens to receive
        """
        try:
            # Use DEX manager to get estimated output
            estimated = await self.dex_manager.get_amounts_out(
                amount_in=eth_amount,
                path=[
                    self.dex_manager.WETH[opportunity.chain],
                    opportunity.token.address
                ],
                chain=opportunity.chain
            )
            
            return estimated[-1] if estimated else Decimal("0")
            
        except Exception as e:
            self.logger.warning(f"Token estimation failed, using price: {e}")
            # Fallback to simple price calculation
            if opportunity.token.price:
                return eth_amount / opportunity.token.price
            return Decimal("0")

    async def _get_gas_settings(
        self,
        chain: str,
        strategy: str
    ) -> Dict[str, Any]:
        """
        Get optimized gas settings for transaction.
        
        Args:
            chain: Chain identifier
            strategy: Gas strategy (slow, standard, fast)
            
        Returns:
            Gas settings dictionary
        """
        try:
            w3 = self.web3_connections[chain]
            base_gas_price = w3.eth.gas_price
            
            # Gas multipliers by strategy
            multipliers = {
                "slow": Decimal("0.8"),
                "standard": Decimal("1.0"),
                "fast": Decimal("1.5"),
                "urgent": Decimal("2.0")
            }
            
            multiplier = multipliers.get(strategy, Decimal("1.0"))
            optimized_gas_price = int(base_gas_price * multiplier)
            
            return {
                "gas_price": optimized_gas_price,
                "gas_limit": 300000,  # Conservative estimate
                "strategy": strategy,
                "base_price": base_gas_price,
                "multiplier": float(multiplier)
            }
            
        except Exception as e:
            self.logger.warning(f"Gas optimization failed: {e}")
            # Fallback settings
            return {
                "gas_price": 20000000000,  # 20 gwei
                "gas_limit": 300000,
                "strategy": "fallback"
            }

    async def _calculate_execution_results(
        self,
        receipt: TxReceipt,
        opportunity: TradingOpportunity,
        eth_amount: Decimal
    ) -> Dict[str, Any]:
        """
        Calculate actual execution results from transaction receipt.
        
        Args:
            receipt: Transaction receipt
            opportunity: Trading opportunity
            eth_amount: ETH amount spent
            
        Returns:
            Execution results dictionary
        """
        try:
            # Parse transaction logs to get actual amounts
            # This is a simplified version - in production, you'd parse Transfer events
            
            # Get ETH price for gas cost calculation
            eth_price_usd = Decimal("2000")  # Simplified - get from price feed
            
            gas_cost_eth = Decimal(receipt["gasUsed"]) * Decimal(receipt["effectiveGasPrice"]) / Decimal("1e18")
            gas_cost_usd = gas_cost_eth * eth_price_usd
            
            # Estimate tokens received (simplified)
            estimated_tokens = await self._estimate_tokens_out(opportunity, eth_amount)
            
            # Calculate actual price
            actual_price = eth_amount / estimated_tokens if estimated_tokens > 0 else Decimal("0")
            
            return {
                "tokens_received": estimated_tokens,
                "actual_price": actual_price,
                "gas_used": receipt["gasUsed"],
                "gas_cost_eth": gas_cost_eth,
                "gas_cost_usd": gas_cost_usd,
                "block_number": receipt["blockNumber"],
                "transaction_index": receipt["transactionIndex"]
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate execution results: {e}")
            return {
                "tokens_received": Decimal("0"),
                "actual_price": Decimal("0"),
                "gas_used": receipt.get("gasUsed", 0),
                "gas_cost_eth": Decimal("0"),
                "gas_cost_usd": Decimal("0")
            }

    async def _create_position_from_execution(
        self,
        opportunity: TradingOpportunity,
        execution_results: Dict[str, Any],
        tx_hash: str,
        wallet_name: str
    ) -> Position:
        """
        Create position from successful execution.
        
        Args:
            opportunity: Original trading opportunity
            execution_results: Execution results
            tx_hash: Transaction hash
            wallet_name: Wallet used
            
        Returns:
            Created position
        """
        try:
            position_id = f"pos_{int(datetime.now().timestamp())}_{opportunity.token.symbol}"
            
            position = Position(
                id=position_id,
                token_symbol=opportunity.token.symbol,
                token_address=opportunity.token.address,
                chain=opportunity.chain,
                entry_amount=execution_results["tokens_received"],
                entry_price=execution_results["actual_price"],
                current_price=execution_results["actual_price"],
                entry_time=datetime.now(),
                last_update=datetime.now(),
                status=PositionStatus.OPEN,
                entry_tx_hash=tx_hash,
                gas_fees_paid=execution_results["gas_cost_usd"],
                metadata={
                    "wallet": wallet_name,
                    "execution_engine": "real",
                    "dex": "uniswap_v2",
                    "opportunity_score": opportunity.metadata.get("score", 0.5),
                    "gas_used": execution_results["gas_used"],
                    "block_number": execution_results["block_number"]
                }
            )
            
            # Add to position manager
            await self.position_manager.open_position(position)
            
            return position
            
        except Exception as e:
            self.logger.error(f"Failed to create position: {e}")
            raise

    async def _ensure_token_approval(
        self,
        token_address: str,
        spender_address: str,
        amount: Decimal,
        wallet_name: str,
        chain: str
    ) -> bool:
        """
        Ensure token approval for spending.
        
        Args:
            token_address: Token to approve
            spender_address: Spender address (router)
            amount: Amount to approve
            wallet_name: Wallet to use
            chain: Chain identifier
            
        Returns:
            Success status
        """
        try:
            # Check current allowance
            current_allowance = await self.dex_manager.get_token_allowance(
                token_address, 
                self.wallet_manager.get_wallet_address(wallet_name),
                spender_address,
                chain
            )
            
            if current_allowance >= amount:
                return True
            
            # Need to approve
            self.logger.info(f"Approving token spending: {amount}")
            
            # Approve large amount to avoid frequent approvals
            approve_amount = amount * Decimal("1000")  # 1000x the required amount
            
            approval_tx = await self.dex_manager.approve_token(
                token_address=token_address,
                spender_address=spender_address,
                amount=approve_amount,
                wallet_name=wallet_name,
                chain=chain
            )
            
            if approval_tx:
                # Wait for approval confirmation
                confirmation = await self._monitor_transaction(approval_tx, chain, timeout=120)
                return confirmation["status"] == TransactionStatus.CONFIRMED
            
            return False
            
        except Exception as e:
            self.logger.error(f"Token approval failed: {e}")
            return False

    async def _monitor_pending_transactions(self) -> None:
        """Background task to monitor pending transactions."""
        try:
            while True:
                # Clean up old pending transactions
                current_time = datetime.now()
                expired_txs = [
                    tx_hash for tx_hash, tx_data in self.pending_transactions.items()
                    if (current_time - tx_data["start_time"]).total_seconds() > 600  # 10 minutes
                ]
                
                for tx_hash in expired_txs:
                    self.logger.warning(f"Cleaning up expired transaction: {tx_hash}")
                    del self.pending_transactions[tx_hash]
                
                await asyncio.sleep(60)  # Check every minute
                
        except Exception as e:
            self.logger.error(f"Transaction monitoring task failed: {e}")

    async def _validate_setup(self) -> None:
        """Validate execution engine setup."""
        try:
            # Check if main wallet exists
            if not self.wallet_manager.get_wallet_address(self.default_wallet):
                self.logger.warning(f"Main wallet '{self.default_wallet}' not found")
            
            # Check Web3 connections
            for chain, w3 in self.web3_connections.items():
                try:
                    block_number = w3.eth.block_number
                    self.logger.info(f"✅ {chain}: Connected (Block: {block_number})")
                except Exception as e:
                    self.logger.error(f"❌ {chain}: Connection failed - {e}")
            
        except Exception as e:
            self.logger.error(f"Setup validation failed: {e}")

    def _update_execution_stats(
        self,
        confirmation_result: Dict[str, Any],
        execution_results: Dict[str, Any]
    ) -> None:
        """Update execution statistics."""
        try:
            self.execution_stats["total_executions"] += 1
            
            if confirmation_result["status"] == TransactionStatus.CONFIRMED:
                self.execution_stats["successful_executions"] += 1
                
                # Update gas tracking
                gas_used = execution_results.get("gas_used", 0)
                gas_cost = execution_results.get("gas_cost_usd", Decimal("0"))
                
                self.execution_stats["total_gas_used"] += gas_used
                self.execution_stats["total_gas_cost"] += gas_cost
                
                # Update confirmation time
                conf_time = confirmation_result.get("confirmation_time", 0)
                current_avg = self.execution_stats["average_confirmation_time"]
                total_successful = self.execution_stats["successful_executions"]
                
                self.execution_stats["average_confirmation_time"] = (
                    (current_avg * (total_successful - 1) + conf_time) / total_successful
                )
            else:
                self.execution_stats["failed_executions"] += 1
                
        except Exception as e:
            self.logger.error(f"Failed to update execution stats: {e}")

    async def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution engine statistics.
        
        Returns:
            Statistics dictionary
        """
        try:
            total = self.execution_stats["total_executions"]
            success_rate = (
                self.execution_stats["successful_executions"] / total * 100
                if total > 0 else 0.0
            )
            
            avg_gas_cost = (
                self.execution_stats["total_gas_cost"] / self.execution_stats["successful_executions"]
                if self.execution_stats["successful_executions"] > 0 else Decimal("0")
            )
            
            return {
                "total_executions": total,
                "successful_executions": self.execution_stats["successful_executions"],
                "failed_executions": self.execution_stats["failed_executions"],
                "success_rate_percentage": round(success_rate, 1),
                "total_gas_used": self.execution_stats["total_gas_used"],
                "total_gas_cost_usd": float(self.execution_stats["total_gas_cost"]),
                "average_gas_cost_usd": float(avg_gas_cost),
                "average_confirmation_time": round(self.execution_stats["average_confirmation_time"], 1),
                "pending_transactions": len(self.pending_transactions),
                "supported_chains": list(self.web3_connections.keys())
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get execution stats: {e}")
            return {}

    async def emergency_stop(self) -> Dict[str, Any]:
        """
        Emergency stop all trading activities.
        
        Returns:
            Emergency stop status
        """
        try:
            self.logger.warning("🚨 EMERGENCY STOP ACTIVATED")
            
            # Get current positions
            active_positions = self.position_manager.get_active_positions()
            
            # Attempt to close all positions
            closed_positions = []
            failed_closures = []
            
            for position in active_positions:
                try:
                    result = await self.execute_sell_order(
                        position=position,
                        sell_percentage=Decimal("1.0"),
                        gas_strategy="urgent"
                    )
                    
                    if result and result.success:
                        closed_positions.append(position.id)
                    else:
                        failed_closures.append(position.id)
                        
                except Exception as e:
                    self.logger.error(f"Failed to close position {position.id}: {e}")
                    failed_closures.append(position.id)
            
            emergency_result = {
                "timestamp": datetime.now().isoformat(),
                "positions_found": len(active_positions),
                "positions_closed": len(closed_positions),
                "positions_failed": len(failed_closures),
                "closed_position_ids": closed_positions,
                "failed_position_ids": failed_closures,
                "pending_transactions": len(self.pending_transactions)
            }
            
            self.logger.warning(f"Emergency stop completed: {emergency_result}")
            return emergency_result
            
        except Exception as e:
            self.logger.error(f"Emergency stop failed: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def cleanup(self) -> None:
        """Cleanup execution engine resources."""
        try:
            self.logger.info("Cleaning up real execution engine...")
            
            # Wait for pending transactions to complete
            if self.pending_transactions:
                self.logger.info(f"Waiting for {len(self.pending_transactions)} pending transactions...")
                
                # Wait up to 5 minutes for pending transactions
                wait_time = 0
                while self.pending_transactions and wait_time < 300:
                    await asyncio.sleep(10)
                    wait_time += 10
                
                if self.pending_transactions:
                    self.logger.warning(f"Abandoning {len(self.pending_transactions)} pending transactions")
            
            # Log final statistics
            stats = await self.get_execution_stats()
            self.logger.info(f"Final execution stats: {stats}")
            
            self.logger.info("✅ Real execution engine cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")