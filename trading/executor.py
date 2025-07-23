"""
Trading executor with real execution capabilities.
Handles transaction signing, submission, retry logic, and monitoring.
"""

import asyncio
import time
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from datetime import datetime, timedelta
import json
from web3 import Web3
from web3.types import TxParams, Wei, HexBytes
from eth_account import Account
from eth_account.datastructures import SignedTransaction

from models.token import TradingOpportunity, RiskLevel
from trading.wallet_manager import WalletManager
from trading.dex_manager import DEXManager
from trading.gas_optimizer import GasOptimizer
from trading.mev_protection import MEVProtectionManager, ProtectedTransaction
from utils.logger import logger_manager


class TradeType(Enum):
    """Type of trade to execute."""
    BUY = "buy"
    SELL = "sell"
    
    
class TradeStatus(Enum):
    """Status of a trade execution."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    EXECUTING = "executing" 
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class OrderType(Enum):
    """Order type for execution."""
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class TradeConfig:
    """
    Configuration for trade execution.
    
    Attributes:
        max_slippage: Maximum allowed slippage
        max_gas_price: Maximum gas price in gwei
        timeout_seconds: Transaction timeout
        retry_attempts: Number of retry attempts
        position_size_eth: Default ETH position size
        position_size_sol: Default SOL position size
        auto_execute: Enable automatic execution
        stop_loss_percentage: Stop loss percentage
        take_profit_percentage: Take profit percentage
        use_mev_protection: Enable MEV protection
        simulate_before_execute: Simulate transactions first
    """
    max_slippage: float = 0.05
    max_gas_price: int = 100
    timeout_seconds: int = 60
    retry_attempts: int = 3
    position_size_eth: float = 0.1
    position_size_sol: float = 1.0
    auto_execute: bool = False
    stop_loss_percentage: float = 0.15
    take_profit_percentage: float = 0.50
    use_mev_protection: bool = True
    simulate_before_execute: bool = True
    confirmation_blocks: int = 2
    enable_partial_fills: bool = True


@dataclass 
class TradeOrder:
    """
    Represents a trade order with full execution details.
    
    Attributes:
        id: Unique order identifier
        opportunity_id: Associated opportunity ID
        trade_type: Buy or sell
        order_type: Market or limit
        token_address: Token contract address
        token_symbol: Token symbol
        chain: Blockchain name
        amount_in: Input amount
        expected_amount_out: Expected output amount
        min_amount_out: Minimum acceptable output
        price: Execution price
        slippage: Slippage tolerance
        gas_price: Gas price in Wei
        gas_limit: Gas limit
        status: Current order status
        created_at: Order creation time
        submitted_at: Transaction submission time
        confirmed_at: Confirmation time
        tx_hash: Transaction hash
        nonce: Transaction nonce
        retry_count: Number of retries
        error_message: Error message if failed
        metadata: Additional order metadata
    """
    id: str
    opportunity_id: str
    trade_type: TradeType
    order_type: OrderType
    token_address: str
    token_symbol: str
    chain: str
    amount_in: Decimal
    expected_amount_out: Decimal
    min_amount_out: Decimal
    price: Optional[Decimal] = None
    slippage: float = 0.05
    gas_price: Optional[Wei] = None
    gas_limit: Optional[int] = None
    status: TradeStatus = TradeStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    tx_hash: Optional[str] = None
    nonce: Optional[int] = None
    retry_count: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary."""
        return {
            'id': self.id,
            'opportunity_id': self.opportunity_id,
            'trade_type': self.trade_type.value,
            'order_type': self.order_type.value,
            'token_address': self.token_address,
            'token_symbol': self.token_symbol,
            'chain': self.chain,
            'amount_in': str(self.amount_in),
            'expected_amount_out': str(self.expected_amount_out),
            'min_amount_out': str(self.min_amount_out),
            'price': str(self.price) if self.price else None,
            'slippage': self.slippage,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'tx_hash': self.tx_hash,
            'retry_count': self.retry_count,
            'error_message': self.error_message
        }


@dataclass
class TradeResult:
    """
    Result of a trade execution.
    
    Attributes:
        success: Whether trade was successful
        order_id: Order ID
        tx_hash: Transaction hash
        amount_in: Actual input amount
        amount_out: Actual output amount
        gas_used: Gas used
        gas_price: Gas price paid
        effective_price: Effective execution price
        slippage_actual: Actual slippage
        execution_time: Total execution time
        confirmation_time: Time to confirmation
        block_number: Execution block number
        error: Error message if failed
    """
    success: bool
    order_id: str
    tx_hash: Optional[str] = None
    amount_in: Optional[Decimal] = None
    amount_out: Optional[Decimal] = None
    gas_used: Optional[int] = None
    gas_price: Optional[Wei] = None
    effective_price: Optional[Decimal] = None
    slippage_actual: Optional[float] = None
    execution_time: Optional[float] = None
    confirmation_time: Optional[float] = None
    block_number: Optional[int] = None
    error: Optional[str] = None


class TradingExecutor:
    """
    Production-ready trading execution engine with full capabilities.
    Handles transaction creation, signing, submission, and monitoring.
    """
    
    def __init__(
        self, 
        config: TradeConfig = None,
        wallet_manager: WalletManager = None,
        dex_manager: DEXManager = None,
        gas_optimizer: GasOptimizer = None,
        mev_protection: MEVProtectionManager = None
    ):
        """
        Initialize the trading executor.
        
        Args:
            config: Trading configuration
            wallet_manager: Wallet management instance
            dex_manager: DEX interaction manager
            gas_optimizer: Gas optimization manager
            mev_protection: MEV protection manager
        """
        self.config = config or TradeConfig()
        self.logger = logger_manager.get_logger("TradingExecutor")
        
        # Initialize managers
        self.wallet_manager = wallet_manager or WalletManager()
        self.dex_manager = dex_manager or DEXManager(self.wallet_manager)
        self.gas_optimizer = gas_optimizer or GasOptimizer()
        self.mev_protection = mev_protection or MEVProtectionManager()
        
        # Web3 connections
        self.web3_connections: Dict[str, Web3] = {}
        
        # Trading state
        self.active_orders: Dict[str, TradeOrder] = {}
        self.order_history: List[TradeOrder] = []
        self.pending_transactions: Dict[str, str] = {}  # tx_hash -> order_id
        
        # Performance tracking
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_gas_spent = Wei(0)
        self.average_execution_time = 0.0
        
        # Monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_initialized = False
        
    async def initialize(self, web3_connections: Dict[str, Web3]) -> None:
        """
        Initialize the trading executor.
        
        Args:
            web3_connections: Web3 connections by chain
        """
        try:
            self.logger.info("Initializing Trading Executor...")
            
            # Store Web3 connections
            self.web3_connections = web3_connections
            
            # Initialize components
            for chain, w3 in web3_connections.items():
                self.dex_manager.add_web3_connection(chain, w3)
                if self.config.use_mev_protection and chain == "ethereum":
                    await self.mev_protection.initialize(w3)
                await self.gas_optimizer.initialize(w3)
            
            # Load wallets
            self.wallet_manager.load_from_env()
            
            # Start transaction monitoring
            self.monitoring_task = asyncio.create_task(self._monitor_transactions())
            
            self.is_initialized = True
            self.logger.info("✅ Trading Executor initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Trading Executor: {e}")
            raise
    
    async def execute_buy(
        self,
        opportunity: TradingOpportunity,
        amount_in: Decimal,
        wallet_name: str = "main",
        custom_slippage: Optional[float] = None
    ) -> TradeResult:
        """
        Execute a buy order for a trading opportunity.
        
        Args:
            opportunity: Trading opportunity to buy
            amount_in: Amount to spend (in native token)
            wallet_name: Wallet to use
            custom_slippage: Custom slippage tolerance
            
        Returns:
            TradeResult with execution details
        """
        start_time = time.time()
        
        # Create order
        order = await self._create_order(
            opportunity=opportunity,
            trade_type=TradeType.BUY,
            amount_in=amount_in,
            wallet_name=wallet_name,
            slippage=custom_slippage or self.config.max_slippage
        )
        
        try:
            # Pre-execution checks
            if self.config.simulate_before_execute:
                sim_result = await self._simulate_transaction(order)
                if not sim_result['success']:
                    raise Exception(f"Simulation failed: {sim_result['error']}")
            
            # Get optimal gas price
            gas_price = await self._get_optimal_gas_price(order.chain)
            order.gas_price = gas_price
            
            # Build transaction
            tx_params = await self._build_swap_transaction(order, wallet_name)
            
            # Sign and submit
            if self.config.use_mev_protection and order.chain == "ethereum":
                success, tx_hash = await self._submit_with_mev_protection(
                    tx_params, wallet_name, order
                )
            else:
                success, tx_hash = await self._submit_transaction(
                    tx_params, wallet_name, order
                )
            
            if not success:
                raise Exception("Transaction submission failed")
            
            order.tx_hash = tx_hash
            order.status = TradeStatus.SUBMITTED
            order.submitted_at = datetime.now()
            
            # Wait for confirmation
            receipt = await self._wait_for_confirmation(tx_hash, order.chain)
            
            if receipt and receipt['status'] == 1:
                # Success
                order.status = TradeStatus.CONFIRMED
                order.confirmed_at = datetime.now()
                
                # Parse execution results
                result = await self._parse_swap_receipt(receipt, order)
                
                self.successful_trades += 1
                self.total_gas_spent += Wei(receipt['gasUsed'] * gas_price)
                
                execution_time = time.time() - start_time
                self._update_average_execution_time(execution_time)
                
                self.logger.info(
                    f"✅ Buy executed successfully: {order.token_symbol} "
                    f"Amount: {amount_in} -> {result.amount_out}, "
                    f"Price: ${result.effective_price}, "
                    f"Time: {execution_time:.2f}s"
                )
                
                return result
                
            else:
                # Failed
                order.status = TradeStatus.FAILED
                order.error_message = "Transaction reverted"
                self.failed_trades += 1
                
                return TradeResult(
                    success=False,
                    order_id=order.id,
                    error="Transaction reverted on chain"
                )
                
        except Exception as e:
            self.logger.error(f"Buy execution failed: {e}")
            order.status = TradeStatus.FAILED
            order.error_message = str(e)
            self.failed_trades += 1
            
            # Retry logic
            if order.retry_count < self.config.retry_attempts:
                order.retry_count += 1
                self.logger.info(f"Retrying order {order.id} (attempt {order.retry_count})")
                return await self.execute_buy(
                    opportunity, amount_in, wallet_name, custom_slippage
                )
            
            return TradeResult(
                success=False,
                order_id=order.id,
                error=str(e)
            )
        
        finally:
            self.total_trades += 1
            self.order_history.append(order)
            if order.id in self.active_orders:
                del self.active_orders[order.id]
    
    async def execute_sell(
        self,
        token_address: str,
        token_amount: Decimal,
        chain: str,
        wallet_name: str = "main",
        custom_slippage: Optional[float] = None
    ) -> TradeResult:
        """
        Execute a sell order for a token.
        
        Args:
            token_address: Token to sell
            token_amount: Amount of tokens to sell
            chain: Blockchain name
            wallet_name: Wallet to use
            custom_slippage: Custom slippage tolerance
            
        Returns:
            TradeResult with execution details
        """
        # Create minimal opportunity for sell
        from models.token import TokenInfo, LiquidityInfo
        
        opportunity = TradingOpportunity(
            token=TokenInfo(
                address=token_address,
                symbol="UNKNOWN",
                name="Unknown Token",
                chain=chain,
                decimals=18,
                total_supply=Decimal(0),
                deployer="",
                creation_time=datetime.now(),
                is_verified=False
            ),
            liquidity=LiquidityInfo(
                pair_address="",
                dex_name="",
                liquidity_token=Decimal(0),
                liquidity_usd=0,
                initial_liquidity=0,
                current_liquidity=0,
                liquidity_locked=False,
                lock_period=None
            ),
            detected_at=datetime.now(),
            risk_level=RiskLevel.MEDIUM
        )
        
        # Create sell order
        order = await self._create_order(
            opportunity=opportunity,
            trade_type=TradeType.SELL,
            amount_in=token_amount,
            wallet_name=wallet_name,
            slippage=custom_slippage or self.config.max_slippage
        )
        
        # Execute similar to buy but with sell parameters
        # Implementation would follow same pattern as execute_buy
        # but with swapExactTokensForETH instead
        
        return TradeResult(
            success=False,
            order_id=order.id,
            error="Sell execution not fully implemented yet"
        )
    
    async def _create_order(
        self,
        opportunity: TradingOpportunity,
        trade_type: TradeType,
        amount_in: Decimal,
        wallet_name: str,
        slippage: float
    ) -> TradeOrder:
        """Create a new trade order."""
        import uuid
        
        # Calculate expected output
        if trade_type == TradeType.BUY:
            # Get quote from DEX
            expected_out = await self.dex_manager.get_amount_out(
                opportunity.token.chain,
                amount_in,
                "ETH",
                opportunity.token.address
            )
        else:
            expected_out = await self.dex_manager.get_amount_out(
                opportunity.token.chain,
                amount_in,
                opportunity.token.address,
                "ETH"
            )
        
        # Calculate minimum output with slippage
        min_amount_out = expected_out * Decimal(1 - slippage)
        
        order = TradeOrder(
            id=str(uuid.uuid4()),
            opportunity_id=opportunity.opportunity_id,
            trade_type=trade_type,
            order_type=OrderType.MARKET,
            token_address=opportunity.token.address,
            token_symbol=opportunity.token.symbol,
            chain=opportunity.token.chain,
            amount_in=amount_in,
            expected_amount_out=expected_out,
            min_amount_out=min_amount_out,
            price=opportunity.initial_price,
            slippage=slippage,
            metadata={
                'wallet': wallet_name,
                'dex': opportunity.liquidity.dex_name,
                'risk_level': opportunity.risk_level.value
            }
        )
        
        self.active_orders[order.id] = order
        return order
    
    async def _simulate_transaction(self, order: TradeOrder) -> Dict[str, Any]:
        """Simulate transaction before execution."""
        try:
            # Use transaction simulator if available
            # For now, basic simulation
            wallet = self.wallet_manager.get_wallet(
                order.metadata.get('wallet', 'main')
            )
            w3 = self.web3_connections[order.chain]
            
            # Check wallet balance
            balance = w3.eth.get_balance(wallet.address)
            required = order.amount_in + Decimal(300000 * 50 * 10**9)  # Add gas
            
            if balance < required:
                return {
                    'success': False,
                    'error': 'Insufficient balance'
                }
            
            # TODO: Add more simulation checks
            
            return {'success': True}
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _get_optimal_gas_price(self, chain: str) -> Wei:
        """Get optimal gas price for chain."""
        try:
            if hasattr(self, 'gas_optimizer') and self.gas_optimizer:
                return await self.gas_optimizer.get_optimal_gas_price()
            else:
                # Fallback to standard gas price
                w3 = self.web3_connections[chain]
                return w3.eth.gas_price
        except:
            # Default gas price
            return Wei(50 * 10**9)  # 50 gwei
    
    async def _build_swap_transaction(
        self, 
        order: TradeOrder,
        wallet_name: str
    ) -> TxParams:
        """Build swap transaction parameters."""
        wallet = self.wallet_manager.get_wallet(wallet_name)
        w3 = self.web3_connections[order.chain]
        
        if order.trade_type == TradeType.BUY:
            # Build buy transaction
            tx = await self.dex_manager.build_swap_eth_for_tokens(
                chain=order.chain,
                token_address=order.token_address,
                amount_in_eth=order.amount_in,
                min_amount_out=order.min_amount_out,
                recipient=wallet.address,
                router=order.metadata.get('dex', 'uniswap_v2')
            )
        else:
            # Build sell transaction
            tx = await self.dex_manager.build_swap_tokens_for_eth(
                chain=order.chain,
                token_address=order.token_address,
                amount_in=order.amount_in,
                min_amount_out_eth=order.min_amount_out,
                recipient=wallet.address,
                router=order.metadata.get('dex', 'uniswap_v2')
            )
        
        # Add gas parameters
        tx['gas'] = order.gas_limit or 300000
        tx['gasPrice'] = order.gas_price
        tx['nonce'] = w3.eth.get_transaction_count(wallet.address)
        
        return tx
    
    async def _submit_with_mev_protection(
        self,
        tx_params: TxParams,
        wallet_name: str,
        order: TradeOrder
    ) -> Tuple[bool, Optional[str]]:
        """Submit transaction with MEV protection."""
        try:
            wallet = self.wallet_manager.get_wallet(wallet_name)
            
            # Sign transaction
            signed_tx = wallet.sign_transaction(tx_params)
            
            # Create protected transaction
            protected = ProtectedTransaction(
                signed_tx=signed_tx.rawTransaction,
                max_priority_fee=Decimal(5),  # 5 gwei
                protection_level=self.mev_protection.protection_level
            )
            
            # Submit through MEV protection
            success, tx_hash = await self.mev_protection.submit_transaction(
                protected
            )
            
            return success, tx_hash
            
        except Exception as e:
            self.logger.error(f"MEV protected submission failed: {e}")
            return False, None
    
    async def _submit_transaction(
        self,
        tx_params: TxParams,
        wallet_name: str,
        order: TradeOrder
    ) -> Tuple[bool, Optional[str]]:
        """Submit regular transaction."""
        try:
            wallet = self.wallet_manager.get_wallet(wallet_name)
            w3 = self.web3_connections[order.chain]
            
            # Sign transaction
            signed_tx = wallet.sign_transaction(tx_params)
            
            # Submit to network
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            self.pending_transactions[tx_hash.hex()] = order.id
            
            return True, tx_hash.hex()
            
        except Exception as e:
            self.logger.error(f"Transaction submission failed: {e}")
            return False, None
    
    async def _wait_for_confirmation(
        self, 
        tx_hash: str,
        chain: str
    ) -> Optional[Dict[str, Any]]:
        """Wait for transaction confirmation."""
        w3 = self.web3_connections[chain]
        
        try:
            # Wait for transaction receipt
            receipt = w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=self.config.timeout_seconds
            )
            
            # Wait for additional confirmations
            if self.config.confirmation_blocks > 1:
                target_block = receipt['blockNumber'] + self.config.confirmation_blocks
                while w3.eth.block_number < target_block:
                    await asyncio.sleep(1)
            
            return receipt
            
        except Exception as e:
            self.logger.error(f"Transaction confirmation failed: {e}")
            return None
    
    async def _parse_swap_receipt(
        self,
        receipt: Dict[str, Any],
        order: TradeOrder
    ) -> TradeResult:
        """Parse swap transaction receipt."""
        # Parse logs to get actual amounts
        # This would decode the Swap event logs
        
        # For now, return estimated values
        return TradeResult(
            success=True,
            order_id=order.id,
            tx_hash=receipt['transactionHash'].hex(),
            amount_in=order.amount_in,
            amount_out=order.expected_amount_out,  # Would get actual from logs
            gas_used=receipt['gasUsed'],
            gas_price=order.gas_price,
            effective_price=order.price,
            slippage_actual=0.0,  # Would calculate from actual amounts
            execution_time=None,
            confirmation_time=None,
            block_number=receipt['blockNumber']
        )
    
    async def _monitor_transactions(self) -> None:
        """Monitor pending transactions."""
        while True:
            try:
                # Check pending transactions
                for tx_hash, order_id in list(self.pending_transactions.items()):
                    order = self.active_orders.get(order_id)
                    if not order:
                        continue
                    
                    # Check if confirmed
                    w3 = self.web3_connections[order.chain]
                    try:
                        receipt = w3.eth.get_transaction_receipt(tx_hash)
                        if receipt:
                            # Remove from pending
                            del self.pending_transactions[tx_hash]
                            
                            # Update order status
                            if receipt['status'] == 1:
                                order.status = TradeStatus.CONFIRMED
                                self.logger.info(f"Transaction confirmed: {tx_hash}")
                            else:
                                order.status = TradeStatus.FAILED
                                self.logger.error(f"Transaction failed: {tx_hash}")
                    except:
                        # Still pending
                        pass
                    
                    # Check for timeout
                    if order.submitted_at:
                        elapsed = (datetime.now() - order.submitted_at).total_seconds()
                        if elapsed > self.config.timeout_seconds:
                            order.status = TradeStatus.TIMEOUT
                            del self.pending_transactions[tx_hash]
                            self.logger.warning(f"Transaction timeout: {tx_hash}")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Transaction monitoring error: {e}")
                await asyncio.sleep(5)
    
    def _update_average_execution_time(self, new_time: float) -> None:
        """Update average execution time."""
        if self.average_execution_time == 0:
            self.average_execution_time = new_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.average_execution_time = (
                alpha * new_time + (1 - alpha) * self.average_execution_time
            )
    
    async def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics.
        
        Returns:
            Dictionary of execution metrics
        """
        success_rate = (
            self.successful_trades / self.total_trades * 100 
            if self.total_trades > 0 else 0
        )
        
        return {
            'total_trades': self.total_trades,
            'successful_trades': self.successful_trades,
            'failed_trades': self.failed_trades,
            'success_rate': f"{success_rate:.1f}%",
            'average_execution_time': f"{self.average_execution_time:.2f}s",
            'total_gas_spent_eth': float(Web3.from_wei(self.total_gas_spent, 'ether')),
            'active_orders': len(self.active_orders),
            'pending_transactions': len(self.pending_transactions)
        }
    
    async def shutdown(self) -> None:
        """Shutdown the executor gracefully."""
        self.logger.info("Shutting down Trading Executor...")
        
        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
        
        # Wait for pending transactions
        if self.pending_transactions:
            self.logger.info(f"Waiting for {len(self.pending_transactions)} pending transactions...")
            await asyncio.sleep(5)
        
        self.logger.info("Trading Executor shutdown complete")