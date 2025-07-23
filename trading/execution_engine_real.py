"""
Real execution engine implementation with actual trading capabilities.
Integrates wallet management, DEX interactions, and arbitrage detection.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime
import asyncio
from web3 import Web3

from models.token import TradingOpportunity
from trading.risk_manager import RiskManager, PositionSizeResult
from trading.position_manager import PositionManager, Position
from trading.wallet_manager import WalletManager
from trading.dex_manager import DEXManager
from trading.arbitrage_detector import ArbitrageDetector
from trading.mev_protection import MEVProtectionManager, MEVProtectionLevel
from trading.gas_optimizer import GasOptimizer, GasStrategy
from trading.transaction_simulator import TransactionSimulator
from utils.logger import logger_manager


class RealExecutionEngine:
    """
    Production execution engine with real trading capabilities.
    """
    
    def __init__(
        self,
        risk_manager: RiskManager,
        position_manager: PositionManager,
        wallet_manager: WalletManager,
        mev_protection_level: MEVProtectionLevel = MEVProtectionLevel.STANDARD
    ) -> None:
        """
        Initialize real execution engine.
        
        Args:
            risk_manager: Risk management system
            position_manager: Position management system
            wallet_manager: Wallet management system
            mev_protection_level: Default MEV protection level
        """
        self.logger = logger_manager.get_logger("RealExecutionEngine")
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        self.wallet_manager = wallet_manager
        
        # Initialize components
        self.dex_manager = DEXManager(wallet_manager)
        self.arbitrage_detector = ArbitrageDetector(self.dex_manager)
        self.mev_protection = MEVProtectionManager()
        self.gas_optimizer = GasOptimizer()
        self.tx_simulator = TransactionSimulator()
        
        # Configuration
        self.default_wallet = "main"
        self.default_slippage = 0.05  # 5%
        self.mev_protection_level = mev_protection_level
        
        # Web3 connections
        self.web3_connections: Dict[str, Web3] = {}
        
    async def initialize(self, web3_connections: Dict[str, Web3]) -> None:
        """
        Initialize the execution engine.
        
        Args:
            web3_connections: Web3 connections by chain
        """
        try:
            self.logger.info("Initializing real execution engine...")
            
            # Store Web3 connections
            self.web3_connections = web3_connections
            
            # Initialize DEX manager with connections
            for chain, w3 in web3_connections.items():
                self.dex_manager.add_web3_connection(chain, w3)
            
            # Initialize other components
            if web3_connections:
                # Use first connection for MEV/gas/simulator
                w3 = list(web3_connections.values())[0]
                await self.mev_protection.initialize(w3)
                await self.gas_optimizer.initialize(w3)
                await self.tx_simulator.initialize(w3)
            
            # Load wallets from environment
            self.wallet_manager.load_from_env()
            
            if not self.wallet_manager.wallets:
                self.logger.warning("No wallets loaded - trading will not be possible")
            else:
                self.logger.info(f"Loaded {len(self.wallet_manager.wallets)} wallets")
            
            self.logger.info("Real execution engine initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize execution engine: {e}")
            raise
    
    async def execute_buy_order(
        self,
        opportunity: TradingOpportunity,
        risk_assessment: PositionSizeResult,
        wallet_name: Optional[str] = None,
        slippage: Optional[float] = None,
        use_arbitrage_check: bool = True
    ) -> Optional[Position]:
        """
        Execute a buy order for a trading opportunity.
        
        Args:
            opportunity: Trading opportunity
            risk_assessment: Risk assessment with position sizing
            wallet_name: Wallet to use (default: main)
            slippage: Slippage tolerance (default: 5%)
            use_arbitrage_check: Check for arbitrage opportunities
            
        Returns:
            Position if successful, None otherwise
        """
        try:
            wallet = wallet_name or self.default_wallet
            slippage = slippage or self.default_slippage
            chain = opportunity.metadata.get('chain', 'ethereum').lower()
            
            self.logger.info(
                f"Executing buy order: {opportunity.token.symbol} "
                f"Amount: {risk_assessment.approved_amount} ETH"
            )
            
            # Check wallet balance
            has_balance, balance = self.wallet_manager.has_sufficient_balance(
                wallet, chain, risk_assessment.approved_amount
            )
            
            if not has_balance:
                self.logger.error(f"Insufficient balance. Have: {balance} ETH")
                return None
            
            # Check for arbitrage if enabled
            if use_arbitrage_check:
                arb_opportunities = await self.arbitrage_detector.find_arbitrage_opportunities(
                    opportunity.token.address,
                    chain,
                    risk_assessment.approved_amount
                )
                
                if arb_opportunities:
                    best_arb = arb_opportunities[0]
                    self.logger.info(
                        f"Arbitrage opportunity found! "
                        f"Buy on {best_arb.buy_dex}, sell on {best_arb.sell_dex} "
                        f"for {best_arb.net_profit} ETH profit"
                    )
                    # Could execute arbitrage instead of regular buy
            
            # Simulate transaction first
            sim_report = await self.tx_simulator.simulate_buy_trade(
                opportunity,
                risk_assessment.approved_amount,
                slippage
            )
            
            if not sim_report.success:
                self.logger.error(f"Simulation failed: {sim_report.error_message}")
                return None
            
            # Get optimal gas strategy
            urgency = self._calculate_urgency(opportunity)
            gas_strategy = GasStrategy.AGGRESSIVE if urgency > 0.8 else GasStrategy.ADAPTIVE
            
            optimized_gas = await self.gas_optimizer.optimize_transaction(
                {
                    'value': Web3.to_wei(risk_assessment.approved_amount, 'ether'),
                    'gas': 300000
                },
                strategy=gas_strategy,
                urgency=urgency
            )
            
            # Execute the swap
            min_tokens = sim_report.amount_out * Decimal(1 - slippage)
            
            result = await self.dex_manager.swap_eth_for_tokens(
                token_address=opportunity.token.address,
                amount_eth=risk_assessment.approved_amount,
                min_tokens=min_tokens,
                wallet_name=wallet,
                chain=chain,
                gas_price=optimized_gas.optimized_tx.get('gasPrice'),
                gas_limit=optimized_gas.optimized_tx.get('gas')
            )
            
            if not result or not result['success']:
                self.logger.error("Swap execution failed")
                return None
            
            # Create position
            position = await self.position_manager.open_position(
                opportunity=opportunity,
                entry_amount=risk_assessment.approved_amount,
                entry_price=opportunity.token.price_usd,
                stop_loss_price=Decimal(str(opportunity.token.price_usd * 0.85)),
                take_profit_price=Decimal(str(opportunity.token.price_usd * 1.5)),
                tx_hash=result['tx_hash']
            )
            
            self.logger.info(
                f"Buy order successful: {opportunity.token.symbol} "
                f"TX: {result['tx_hash']}"
            )
            
            return position
            
        except Exception as e:
            self.logger.error(f"Buy order execution failed: {e}")
            return None
    
    async def execute_sell_order(
        self,
        position: Position,
        wallet_name: Optional[str] = None,
        slippage: Optional[float] = None
    ) -> bool:
        """
        Execute a sell order to close a position.
        
        Args:
            position: Position to close
            wallet_name: Wallet to use
            slippage: Slippage tolerance
            
        Returns:
            True if successful
        """
        try:
            wallet = wallet_name or self.default_wallet
            slippage = slippage or self.default_slippage
            chain = position.chain
            
            self.logger.info(f"Executing sell order: {position.token_symbol}")
            
            # Get token balance
            token_balance = await self.wallet_manager.get_balance(
                wallet, chain, position.token_address
            )
            
            if token_balance <= 0:
                self.logger.error("No tokens to sell")
                return False
            
            # Calculate minimum ETH output
            min_eth = token_balance * position.current_price * Decimal(1 - slippage)
            
            # Execute the swap
            result = await self.dex_manager.swap_tokens_for_eth(
                token_address=position.token_address,
                amount_tokens=token_balance,
                min_eth=min_eth,
                wallet_name=wallet,
                chain=chain
            )
            
            if not result or not result['success']:
                self.logger.error("Sell execution failed")
                return False
            
            # Update position
            await self.position_manager.close_position(
                position_id=position.id,
                exit_price=position.current_price,
                exit_reason="MANUAL",
                exit_tx_hash=result['tx_hash']
            )
            
            self.logger.info(
                f"Sell order successful: {position.token_symbol} "
                f"TX: {result['tx_hash']}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Sell order execution failed: {e}")
            return False
    
    async def execute_arbitrage(
        self,
        opportunity: Any,
        wallet_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute an arbitrage opportunity."""
        wallet = wallet_name or self.default_wallet
        
        return await self.arbitrage_detector.execute_arbitrage(
            opportunity, wallet
        )
    
    def _calculate_urgency(self, opportunity: TradingOpportunity) -> float:
        """Calculate trade urgency for gas optimization."""
        urgency = 0.5
        
        # Increase for strong recommendations
        recommendation = opportunity.metadata.get('recommendation', {})
        if recommendation.get('action') == 'STRONG_BUY':
            urgency += 0.3
        elif recommendation.get('action') == 'BUY':
            urgency += 0.2
        
        # Increase for new tokens
        token_age = (datetime.now() - opportunity.token.launch_time).total_seconds()
        if token_age < 300:  # Less than 5 minutes
            urgency += 0.2
        
        return min(urgency, 1.0)
    
    def get_wallet_info(self) -> Dict[str, Any]:
        """Get wallet information."""
        return {
            'wallets': self.wallet_manager.export_addresses(),
            'default_wallet': self.default_wallet,
            'chains_configured': list(self.web3_connections.keys())
        }
    
    async def check_arbitrage_all_chains(
        self,
        token_address: str,
        amount: Decimal = Decimal("1.0")
    ) -> Dict[str, List[Any]]:
        """Check arbitrage opportunities across all configured chains."""
        results = {}
        
        for chain in self.web3_connections.keys():
            opportunities = await self.arbitrage_detector.find_arbitrage_opportunities(
                token_address, chain, amount
            )
            if opportunities:
                results[chain] = opportunities
        
        return results