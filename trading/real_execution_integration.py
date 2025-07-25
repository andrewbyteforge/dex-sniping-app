#!/usr/bin/env python3
"""
Integration file for the Real Execution Engine.
Shows how to integrate the real execution engine into the main system.

File: trading/real_execution_integration.py
"""

import asyncio
from typing import Dict, Optional
from decimal import Decimal
from web3 import Web3
from web3.providers import HTTPProvider

from trading.risk_manager import RiskManager, PortfolioLimits
from trading.position_manager import PositionManager
from trading.wallet_manager import WalletManager
from trading.dex_manager import DEXManager
from trading.execution_engine_real import RealExecutionEngine
from models.token import TradingOpportunity, TokenInfo, LiquidityInfo
from utils.logger import logger_manager
from config.settings import settings


class RealExecutionSystemIntegrator:
    """
    Integrates the real execution engine into the main trading system.
    Handles initialization and configuration for live trading.
    """
    
    def __init__(self) -> None:
        """Initialize the real execution system integrator."""
        self.logger = logger_manager.get_logger("RealExecutionIntegrator")
        
        # Core components
        self.risk_manager: Optional[RiskManager] = None
        self.position_manager: Optional[PositionManager] = None
        self.wallet_manager: Optional[WalletManager] = None
        self.dex_manager: Optional[DEXManager] = None
        self.real_execution_engine: Optional[RealExecutionEngine] = None
        
        # Web3 connections
        self.web3_connections: Dict[str, Web3] = {}
        
        self.logger.warning("🔥 REAL EXECUTION SYSTEM - LIVE TRADING CAPABILITIES")

    async def initialize(self) -> bool:
        """
        Initialize the complete real execution system.
        
        Returns:
            Success status
        """
        try:
            self.logger.info("Initializing real execution system...")
            
            # Step 1: Initialize Web3 connections
            await self._initialize_web3_connections()
            
            # Step 2: Initialize wallet manager
            await self._initialize_wallet_manager()
            
            # Step 3: Initialize risk manager
            await self._initialize_risk_manager()
            
            # Step 4: Initialize position manager
            await self._initialize_position_manager()
            
            # Step 5: Initialize DEX manager
            await self._initialize_dex_manager()
            
            # Step 6: Initialize real execution engine
            await self._initialize_real_execution_engine()
            
            # Step 7: Validate complete setup
            await self._validate_complete_setup()
            
            self.logger.info("✅ Real execution system initialized successfully")
            self._log_system_capabilities()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Real execution system initialization failed: {e}")
            return False

    async def _initialize_web3_connections(self) -> None:
        """Initialize Web3 connections for all supported chains."""
        try:
            self.logger.info("Setting up Web3 connections...")
            
            # Ethereum connection
            if hasattr(settings, 'networks') and hasattr(settings.networks, 'ethereum_rpc_url'):
                ethereum_rpc = settings.networks.ethereum_rpc_url
            else:
                ethereum_rpc = "https://ethereum-rpc.publicnode.com"
            
            self.web3_connections["ethereum"] = Web3(HTTPProvider(ethereum_rpc))
            
            # Base connection
            if hasattr(settings, 'networks') and hasattr(settings.networks, 'base_rpc_url'):
                base_rpc = settings.networks.base_rpc_url
            else:
                base_rpc = "https://mainnet.base.org"
            
            self.web3_connections["base"] = Web3(HTTPProvider(base_rpc))
            
            # Test connections
            for chain, w3 in self.web3_connections.items():
                try:
                    block_number = w3.eth.block_number
                    self.logger.info(f"✅ {chain.upper()}: Connected (Block: {block_number})")
                except Exception as e:
                    self.logger.error(f"❌ {chain.upper()}: Connection failed - {e}")
                    raise
                    
        except Exception as e:
            self.logger.error(f"Web3 connection setup failed: {e}")
            raise

    async def _initialize_wallet_manager(self) -> None:
        """Initialize wallet manager and load wallets."""
        try:
            self.logger.info("Initializing wallet manager...")
            
            self.wallet_manager = WalletManager()
            
            # Load wallets from environment
            self.wallet_manager.load_from_env()
            
            # Add Web3 connections to wallet manager
            for chain, w3 in self.web3_connections.items():
                self.wallet_manager.add_web3_connection(chain, w3)
            
            # Verify main wallet exists
            main_address = self.wallet_manager.get_wallet_address("main")
            if not main_address:
                self.logger.warning("⚠️ Main wallet not found - add TRADING_PRIVATE_KEY to environment")
                # For testing, you could create a new wallet here
                # address, private_key = WalletManager.create_new_wallet()
                # self.logger.info(f"Created test wallet: {address}")
            else:
                self.logger.info(f"✅ Main wallet loaded: {main_address}")
                
            # Check balances
            await self._check_wallet_balances()
            
        except Exception as e:
            self.logger.error(f"Wallet manager initialization failed: {e}")
            raise

    async def _initialize_risk_manager(self) -> None:
        """Initialize risk manager with production limits."""
        try:
            self.logger.info("Initializing risk manager...")
            
            # Conservative production limits
            portfolio_limits = PortfolioLimits(
                max_total_exposure_usd=1000.0,     # $1000 max total exposure
                max_single_position_usd=100.0,    # $100 max per position
                max_daily_loss_usd=200.0,         # $200 max daily loss
                max_positions_per_chain=5,        # 5 positions per chain
                max_total_positions=10,           # 10 total positions
                max_trades_per_hour=3,            # 3 trades per hour
                max_trades_per_day=15             # 15 trades per day
            )
            
            self.risk_manager = RiskManager(portfolio_limits)
            
            self.logger.info("✅ Risk manager initialized with production limits")
            self.logger.info(f"   Max total exposure: ${portfolio_limits.max_total_exposure_usd}")
            self.logger.info(f"   Max position size: ${portfolio_limits.max_single_position_usd}")
            self.logger.info(f"   Max daily loss: ${portfolio_limits.max_daily_loss_usd}")
            
        except Exception as e:
            self.logger.error(f"Risk manager initialization failed: {e}")
            raise

    async def _initialize_position_manager(self) -> None:
        """Initialize position manager."""
        try:
            self.logger.info("Initializing position manager...")
            
            self.position_manager = PositionManager()
            await self.position_manager.initialize()
            
            self.logger.info("✅ Position manager initialized")
            
        except Exception as e:
            self.logger.error(f"Position manager initialization failed: {e}")
            raise

    async def _initialize_dex_manager(self) -> None:
        """Initialize DEX manager."""
        try:
            self.logger.info("Initializing DEX manager...")
            
            self.dex_manager = DEXManager(self.wallet_manager)
            
            # Add Web3 connections
            for chain, w3 in self.web3_connections.items():
                self.dex_manager.add_web3_connection(chain, w3)
            
            self.logger.info("✅ DEX manager initialized")
            self.logger.info("   Supported DEXs: Uniswap V2, SushiSwap")
            self.logger.info("   Supported chains: Ethereum, Base")
            
        except Exception as e:
            self.logger.error(f"DEX manager initialization failed: {e}")
            raise

    async def _initialize_real_execution_engine(self) -> None:
        """Initialize the real execution engine."""
        try:
            self.logger.info("Initializing real execution engine...")
            
            self.real_execution_engine = RealExecutionEngine(
                risk_manager=self.risk_manager,
                position_manager=self.position_manager,
                wallet_manager=self.wallet_manager,
                dex_manager=self.dex_manager
            )
            
            await self.real_execution_engine.initialize(self.web3_connections)
            
            self.logger.info("🔥 Real execution engine initialized - LIVE TRADING READY")
            
        except Exception as e:
            self.logger.error(f"Real execution engine initialization failed: {e}")
            raise

    async def _check_wallet_balances(self) -> None:
        """Check wallet balances across all chains."""
        try:
            main_address = self.wallet_manager.get_wallet_address("main")
            if not main_address:
                return
            
            self.logger.info("Checking wallet balances...")
            
            for chain in self.web3_connections.keys():
                try:
                    balance = await self.wallet_manager.get_balance("main", chain)
                    self.logger.info(f"   {chain.upper()}: {balance:.6f} ETH")
                    
                    if balance < Decimal("0.01"):
                        self.logger.warning(f"⚠️ Low balance on {chain}: {balance:.6f} ETH")
                        
                except Exception as e:
                    self.logger.error(f"Failed to check {chain} balance: {e}")
                    
        except Exception as e:
            self.logger.error(f"Balance check failed: {e}")

    async def _validate_complete_setup(self) -> None:
        """Validate that all components are properly initialized."""
        try:
            self.logger.info("Validating complete setup...")
            
            # Check all components exist
            required_components = [
                ("Risk Manager", self.risk_manager),
                ("Position Manager", self.position_manager),
                ("Wallet Manager", self.wallet_manager),
                ("DEX Manager", self.dex_manager),
                ("Real Execution Engine", self.real_execution_engine)
            ]
            
            for name, component in required_components:
                if component is None:
                    raise Exception(f"{name} not initialized")
                self.logger.debug(f"✅ {name}: OK")
            
            # Check Web3 connections
            if not self.web3_connections:
                raise Exception("No Web3 connections available")
            
            # Check wallet exists
            if not self.wallet_manager.get_wallet_address("main"):
                self.logger.warning("⚠️ No main wallet - live trading disabled")
            
            self.logger.info("✅ Complete setup validation passed")
            
        except Exception as e:
            self.logger.error(f"Setup validation failed: {e}")
            raise

    def _log_system_capabilities(self) -> None:
        """Log system capabilities and warnings."""
        try:
            self.logger.info("\n" + "=" * 70)
            self.logger.info("🔥 REAL EXECUTION SYSTEM CAPABILITIES")
            self.logger.info("=" * 70)
            
            # Trading capabilities
            self.logger.info("📈 TRADING CAPABILITIES:")
            self.logger.info("   • Real DEX contract interactions")
            self.logger.info("   • Automatic transaction signing")
            self.logger.info("   • Transaction confirmation monitoring")
            self.logger.info("   • Gas optimization")
            self.logger.info("   • Slippage protection")
            
            # Supported operations
            self.logger.info("\n🛠️ SUPPORTED OPERATIONS:")
            self.logger.info("   • ETH -> Token swaps (buying)")
            self.logger.info("   • Token -> ETH swaps (selling)")
            self.logger.info("   • Token approvals")
            self.logger.info("   • Position management")
            self.logger.info("   • Emergency stop functionality")
            
            # Risk management
            self.logger.info("\n🛡️ RISK MANAGEMENT:")
            portfolio_limits = self.risk_manager.portfolio_limits
            self.logger.info(f"   • Max total exposure: ${portfolio_limits.max_total_exposure_usd}")
            self.logger.info(f"   • Max position size: ${portfolio_limits.max_single_position_usd}")
            self.logger.info(f"   • Max daily loss: ${portfolio_limits.max_daily_loss_usd}")
            self.logger.info(f"   • Max positions: {portfolio_limits.max_total_positions}")
            
            # Supported chains
            self.logger.info("\n🔗 SUPPORTED CHAINS:")
            for chain in self.web3_connections.keys():
                self.logger.info(f"   • {chain.upper()}")
            
            # Security warnings
            self.logger.info("\n⚠️ SECURITY WARNINGS:")
            self.logger.info("   • This system executes REAL transactions")
            self.logger.info("   • Funds can be PERMANENTLY LOST")
            self.logger.info("   • Always test with small amounts first")
            self.logger.info("   • Keep private keys secure")
            self.logger.info("   • Monitor gas costs and slippage")
            
            self.logger.info("=" * 70 + "\n")
            
        except Exception as e:
            self.logger.error(f"Failed to log system capabilities: {e}")

    async def execute_test_trade(
        self,
        token_address: str,
        amount_eth: Decimal,
        chain: str = "ethereum"
    ) -> bool:
        """
        Execute a test trade to verify system functionality.
        
        Args:
            token_address: Token to buy for testing
            amount_eth: Small ETH amount for testing
            chain: Chain to test on
            
        Returns:
            Success status
        """
        try:
            self.logger.info(f"🧪 EXECUTING TEST TRADE: {amount_eth} ETH -> {token_address}")
            
            # Create test opportunity
            test_token = TokenInfo(
                address=token_address,
                symbol="TEST",
                name="Test Token",
                decimals=18
            )
            
            test_liquidity = LiquidityInfo(
                liquidity_usd=100000.0,
                dex_name="uniswap_v2",
                pair_address=""
            )
            
            test_opportunity = TradingOpportunity(
                token=test_token,
                liquidity=test_liquidity,
                timestamp=datetime.now(),
                chain=chain,
                metadata={"test_trade": True}
            )
            
            # Create test position size result
            from trading.risk_manager import PositionSizeResult, RiskAssessment
            
            position_size_result = PositionSizeResult(
                approved_amount=amount_eth,
                risk_assessment=RiskAssessment.APPROVED,
                risk_score=0.3,
                reasons=["Test trade"],
                max_loss_usd=float(amount_eth) * 0.2,
                recommended_stop_loss=0.2,
                recommended_take_profit=0.5
            )
            
            # Execute test buy order
            position = await self.real_execution_engine.execute_buy_order(
                opportunity=test_opportunity,
                position_size_result=position_size_result,
                slippage_tolerance=Decimal("0.1"),  # 10% slippage for test
                gas_strategy="standard"
            )
            
            if position:
                self.logger.info(f"✅ Test trade successful - Position ID: {position.id}")
                
                # Wait a moment then try to sell (optional)
                self.logger.info("Waiting 30 seconds before test sell...")
                await asyncio.sleep(30)
                
                # Execute test sell order
                sell_result = await self.real_execution_engine.execute_sell_order(
                    position=position,
                    sell_percentage=Decimal("1.0"),  # Sell 100%
                    slippage_tolerance=Decimal("0.1"),
                    gas_strategy="fast"
                )
                
                if sell_result and sell_result.success:
                    self.logger.info("✅ Test sell successful")
                    return True
                else:
                    self.logger.warning("⚠️ Test sell failed")
                    return False
            else:
                self.logger.error("❌ Test trade failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Test trade execution failed: {e}")
            return False

    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            System status dictionary
        """
        try:
            # Get wallet balances
            wallet_status = {}
            main_address = self.wallet_manager.get_wallet_address("main")
            
            if main_address:
                for chain in self.web3_connections.keys():
                    try:
                        balance = await self.wallet_manager.get_balance("main", chain)
                        wallet_status[chain] = {
                            "balance_eth": float(balance),
                            "address": main_address
                        }
                    except Exception as e:
                        wallet_status[chain] = {"error": str(e)}
            
            # Get execution stats
            execution_stats = {}
            if self.real_execution_engine:
                execution_stats = await self.real_execution_engine.get_execution_stats()
            
            # Get position summary
            portfolio_summary = {}
            if self.position_manager:
                portfolio_summary = self.position_manager.get_portfolio_summary()
            
            # Get risk limits
            risk_status = {}
            if self.risk_manager:
                risk_status = {
                    "max_total_exposure": self.risk_manager.portfolio_limits.max_total_exposure_usd,
                    "max_position_size": self.risk_manager.portfolio_limits.max_single_position_usd,
                    "max_daily_loss": self.risk_manager.portfolio_limits.max_daily_loss_usd
                }
            
            return {
                "timestamp": datetime.now().isoformat(),
                "system_ready": all([
                    self.real_execution_engine is not None,
                    self.wallet_manager is not None,
                    self.dex_manager is not None,
                    self.risk_manager is not None,
                    self.position_manager is not None
                ]),
                "wallet_status": wallet_status,
                "execution_stats": execution_stats,
                "portfolio_summary": portfolio_summary,
                "risk_status": risk_status,
                "supported_chains": list(self.web3_connections.keys()),
                "main_wallet_address": main_address
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get system status: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def emergency_shutdown(self) -> Dict[str, Any]:
        """
        Emergency shutdown with position closure.
        
        Returns:
            Shutdown status
        """
        try:
            self.logger.warning("🚨 EMERGENCY SHUTDOWN INITIATED")
            
            shutdown_result = {"timestamp": datetime.now().isoformat()}
            
            # Emergency stop trading
            if self.real_execution_engine:
                emergency_result = await self.real_execution_engine.emergency_stop()
                shutdown_result["emergency_stop"] = emergency_result
            
            # Cleanup components
            cleanup_tasks = []
            
            if self.real_execution_engine:
                cleanup_tasks.append(self.real_execution_engine.cleanup())
            
            if self.position_manager:
                cleanup_tasks.append(self.position_manager.cleanup())
            
            # Execute cleanup
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            shutdown_result["status"] = "completed"
            self.logger.warning("🚨 Emergency shutdown completed")
            
            return shutdown_result
            
        except Exception as e:
            self.logger.error(f"Emergency shutdown failed: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


# Example usage and integration
async def main():
    """Example of how to use the real execution system."""
    
    # Initialize system
    integrator = RealExecutionSystemIntegrator()
    
    try:
        # Initialize all components
        success = await integrator.initialize()
        
        if not success:
            print("❌ System initialization failed")
            return
        
        print("✅ Real execution system ready")
        
        # Get system status
        status = await integrator.get_system_status()
        print(f"System status: {status}")
        
        # Example: Execute test trade (UNCOMMENT TO TEST WITH REAL FUNDS)
        # WARNING: This will spend real ETH!
        """
        test_success = await integrator.execute_test_trade(
            token_address="0xA0b86a33E6441c41076Df8C6568F3fc5E61deAB1",  # Example token
            amount_eth=Decimal("0.001"),  # Very small amount for testing
            chain="ethereum"
        )
        
        if test_success:
            print("✅ Test trade completed successfully")
        else:
            print("❌ Test trade failed")
        """
        
        # Keep system running
        print("System running... Press Ctrl+C to stop")
        try:
            while True:
                await asyncio.sleep(60)
                
                # Periodic status check
                status = await integrator.get_system_status()
                print(f"System status check: {status['system_ready']}")
                
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested...")
            
    except Exception as e:
        print(f"❌ System error: {e}")
        
    finally:
        # Emergency shutdown
        try:
            shutdown_result = await integrator.emergency_shutdown()
            print(f"Shutdown result: {shutdown_result}")
        except Exception as e:
            print(f"Shutdown error: {e}")


if __name__ == "__main__":
    asyncio.run(main())