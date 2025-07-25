#!/usr/bin/env python3
"""
Enhanced production system with Phase 3 speed optimizations.
Integrates MEV protection, gas optimization, direct nodes, and transaction simulation.

File: main_production_enhanced.py
"""

import asyncio
import sys
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
from decimal import Decimal
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger_manager
from models.token import TradingOpportunity, RiskLevel

# Phase 1 & 2 Components
from monitors.new_token_monitor import NewTokenMonitor
from monitors.base_chain_monitor import BaseChainMonitor
from monitors.solana_monitor import SolanaMonitor
from monitors.jupiter_solana_monitor import JupiterSolanaMonitor
from analyzers.contract_analyzer import ContractAnalyzer
from analyzers.social_analyzer import SocialAnalyzer
from analyzers.trading_scorer import TradingScorer

# Phase 3 Components - Original
from trading.risk_manager import RiskManager, PortfolioLimits, RiskAssessment
from trading.position_manager import PositionManager, Position, PositionStatus
from trading.execution_engine import ExecutionEngine

# Phase 3 Components - Enhanced
from trading.execution_engine_enhanced import EnhancedExecutionEngine
from trading.mev_protection import MEVProtectionManager, MEVProtectionLevel
from trading.gas_optimizer import GasOptimizer, GasStrategy

# Infrastructure components with fallback handling
try:
    from infrastructure.direct_node_manager import DirectNodeManager
    DIRECT_NODE_MANAGER_AVAILABLE = True
except ImportError:
    try:
        from infrastructure.node_manager import DirectNodeManager
        DIRECT_NODE_MANAGER_AVAILABLE = True
    except ImportError:
        DirectNodeManager = None
        DIRECT_NODE_MANAGER_AVAILABLE = False

# Transaction simulator with fallback
try:
    from trading.transaction_simulator import TransactionSimulator
    TRANSACTION_SIMULATOR_AVAILABLE = True
except ImportError:
    TransactionSimulator = None
    TRANSACTION_SIMULATOR_AVAILABLE = False

# Configuration and API
from config.chains import multichain_settings, ChainType
from config.settings import settings


class EnhancedProductionSystem:
    """
    Production-ready DEX sniping system with Phase 3 speed optimizations.
    Features ultra-fast execution, MEV protection, and intelligent gas management.
    """
    
    def __init__(
        self,
        auto_trading_enabled: bool = False,
        disable_dashboard: bool = False,
        mev_protection_level: MEVProtectionLevel = MEVProtectionLevel.STANDARD
    ) -> None:
        """
        Initialize enhanced production system.
        
        Args:
            auto_trading_enabled: Enable automatic trade execution
            disable_dashboard: Disable web dashboard
            mev_protection_level: Default MEV protection level
        """
        self.logger = logger_manager.get_logger("EnhancedProductionSystem")
        self.auto_trading_enabled = auto_trading_enabled
        self.disable_dashboard = disable_dashboard
        self.mev_protection_level = mev_protection_level
        
        # System components
        self.monitors: List = []
        self.is_running = False
        
        # Phase 2: Analysis components
        self.contract_analyzer: Optional[ContractAnalyzer] = None
        self.social_analyzer: Optional[SocialAnalyzer] = None
        self.trading_scorer: Optional[TradingScorer] = None
        
        # Phase 3: Trading components
        self.risk_manager: Optional[RiskManager] = None
        self.position_manager: Optional[PositionManager] = None
        self.execution_engine: Optional[EnhancedExecutionEngine] = None
        
        # Phase 3 Enhanced: Speed optimization components
        self.node_manager: Optional[DirectNodeManager] = None
        self.mev_protection: Optional[MEVProtectionManager] = None
        self.gas_optimizer: Optional[GasOptimizer] = None
        self.tx_simulator: Optional[TransactionSimulator] = None
        
        # Dashboard
        self.dashboard_server = None
        self.web_server_task = None
        
        # Performance tracking
        self.system_stats = {
            "start_time": None,
            "opportunities_detected": 0,
            "opportunities_analyzed": 0,
            "trades_simulated": 0,
            "trades_executed": 0,
            "positions_opened": 0,
            "mev_attacks_prevented": 0,
            "gas_saved_usd": Decimal("0"),
            "average_detection_time": 0.0,
            "average_execution_time": 0.0,
            "chains": {}
        }
        
        # Component initialization tracking
        self.components_initialized = {
            "monitors": False,
            "analyzers": False,
            "trading_system": False,
            "speed_optimizations": False,
            "web_dashboard": False
        }
        
        # Feature availability warnings
        self._log_feature_availability()

    def _log_feature_availability(self) -> None:
        """Log available features and any missing components."""
        self.logger.info("🔧 Feature Availability Check:")
        
        if DIRECT_NODE_MANAGER_AVAILABLE:
            self.logger.info("✅ Direct Node Manager: Available")
        else:
            self.logger.warning("⚠️ Direct Node Manager: Not available (falling back to standard RPC)")
        
        if TRANSACTION_SIMULATOR_AVAILABLE:
            self.logger.info("✅ Transaction Simulator: Available")
        else:
            self.logger.warning("⚠️ Transaction Simulator: Not available (skipping simulation)")
        
        # Check MEV Protection
        try:
            test_mev = MEVProtectionManager()
            self.logger.info("✅ MEV Protection: Available")
        except Exception as e:
            self.logger.warning(f"⚠️ MEV Protection: Issues detected - {e}")
        
        # Check Gas Optimizer
        try:
            test_gas = GasOptimizer()
            self.logger.info("✅ Gas Optimizer: Available")
        except Exception as e:
            self.logger.warning(f"⚠️ Gas Optimizer: Issues detected - {e}")

    async def start(self) -> None:
        """Start the enhanced production system."""
        try:
            self.logger.info("=" * 70)
            self.logger.info("🚀 STARTING ENHANCED PRODUCTION SYSTEM - PHASE 3 OPTIMIZED")
            self.logger.info("=" * 70)
            self.logger.info(f"Auto Trading: {'ENABLED' if self.auto_trading_enabled else 'DISABLED'}")
            self.logger.info(f"MEV Protection: {self.mev_protection_level.value}")
            self.logger.info(f"Dashboard: {'DISABLED' if self.disable_dashboard else 'ENABLED'}")
            self.logger.info("=" * 70)
            
            self.start_time = datetime.now()
            self.system_stats["start_time"] = self.start_time
            self.is_running = True
            
            # Initialize all components in order
            await self._initialize_infrastructure()
            await self._initialize_analyzers()
            await self._initialize_trading_system()
            await self._initialize_speed_optimizations()
            await self._initialize_monitors()
            
            if not self.disable_dashboard:
                await self._initialize_web_dashboard()
            
            # Log initialization summary
            self._log_initialization_summary()
            
            # Start main monitoring loop
            await self._run_monitoring_loop()
            
        except Exception as e:
            self.logger.error(f"FATAL ERROR in enhanced production system: {e}")
            raise
        finally:
            await self._cleanup()

    async def _initialize_infrastructure(self) -> None:
        """Initialize direct node connections for maximum speed."""
        try:
            self.logger.info("Initializing enhanced infrastructure...")
            
            # Initialize direct node manager if available
            if DIRECT_NODE_MANAGER_AVAILABLE and DirectNodeManager:
                try:
                    self.node_manager = DirectNodeManager()
                    await self.node_manager.initialize()
                    self.logger.info("✅ Direct Node Manager initialized successfully")
                except Exception as e:
                    self.logger.error(f"Direct Node Manager initialization failed: {e}")
                    self.logger.warning("Falling back to standard RPC connections")
                    self.node_manager = None
            else:
                self.logger.warning("⚠️ Direct Node Manager not available, using standard RPC connections")
            
            self.logger.info("✅ Infrastructure initialization completed")
            
        except Exception as e:
            self.logger.error(f"Infrastructure initialization failed: {e}")
            self.logger.warning("Continuing with limited infrastructure capabilities")

    async def _initialize_analyzers(self) -> None:
        """Initialize analysis components."""
        try:
            self.logger.info("Initializing analysis components...")
            
            # Get Web3 connection (prefer direct node)
            w3 = None
            if self.node_manager:
                w3 = await self.node_manager.get_web3_connection("ethereum")
            
            if not w3:
                from web3 import Web3
                try:
                    w3 = Web3(Web3.HTTPProvider(settings.networks.ethereum_rpc_url))
                    if not w3.is_connected():
                        self.logger.warning("Could not connect to Ethereum RPC")
                        w3 = None
                except:
                    self.logger.warning("Web3 connection failed, proceeding with limited functionality")
                    w3 = None
            
            # Initialize analyzers
            if w3:
                self.contract_analyzer = ContractAnalyzer(w3)
                await self.contract_analyzer.initialize()
            else:
                self.logger.warning("Contract analyzer disabled (no Web3 connection)")
                self.contract_analyzer = None
            
            self.social_analyzer = SocialAnalyzer()
            await self.social_analyzer.initialize()
            
            self.trading_scorer = TradingScorer()
            
            self.components_initialized["analyzers"] = True
            self.logger.info("✅ Analysis components initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize analyzers: {e}")
            # Don't raise - continue with limited functionality

    async def _initialize_trading_system(self) -> None:
        """Initialize trading system components."""
        try:
            self.logger.info("Initializing trading system...")
            
            # Initialize risk manager
            portfolio_limits = PortfolioLimits(
                max_total_position_usd=10000.0,
                max_position_size_usd=1000.0,
                max_positions_per_chain=5,
                max_daily_losses_usd=500.0
            )
            
            self.risk_manager = RiskManager(portfolio_limits)
            await self.risk_manager.initialize()
            
            # Initialize position manager
            self.position_manager = PositionManager()
            await self.position_manager.initialize()
            
            # Initialize enhanced execution engine
            self.execution_engine = EnhancedExecutionEngine(
                risk_manager=self.risk_manager,
                position_manager=self.position_manager,
                mev_protection_level=self.mev_protection_level
            )
            
            self.components_initialized["trading_system"] = True
            self.logger.info("✅ Trading system initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading system: {e}")
            raise

    async def _initialize_speed_optimizations(self) -> None:
        """Initialize Phase 3 speed optimization components."""
        try:
            self.logger.info("Initializing speed optimizations...")
            
            # Initialize MEV protection
            try:
                self.mev_protection = MEVProtectionManager(self.mev_protection_level)
                
                # Initialize with Web3 if available
                if self.node_manager:
                    w3 = await self.node_manager.get_web3_connection("ethereum")
                    if w3:
                        await self.mev_protection.initialize(w3)
                
                self.logger.info("✅ MEV Protection initialized")
                
            except Exception as e:
                self.logger.error(f"MEV Protection initialization failed: {e}")
                self.mev_protection = None
            
            # Initialize gas optimizer
            try:
                self.gas_optimizer = GasOptimizer()
                await self.gas_optimizer.initialize()
                self.logger.info("✅ Gas Optimizer initialized")
                
            except Exception as e:
                self.logger.error(f"Gas Optimizer initialization failed: {e}")
                self.gas_optimizer = None
            
            # Initialize transaction simulator
            if TRANSACTION_SIMULATOR_AVAILABLE and TransactionSimulator:
                try:
                    self.tx_simulator = TransactionSimulator()
                    await self.tx_simulator.initialize()
                    self.logger.info("✅ Transaction Simulator initialized")
                    
                except Exception as e:
                    self.logger.error(f"Transaction Simulator initialization failed: {e}")
                    self.tx_simulator = None
            else:
                self.logger.warning("⚠️ Transaction Simulator not available")
                self.tx_simulator = None
            
            self.components_initialized["speed_optimizations"] = True
            self.logger.info("✅ Speed optimizations initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize speed optimizations: {e}")
            # Don't raise - continue with basic functionality

    async def _initialize_monitors(self) -> None:
        """Initialize monitoring components."""
        try:
            self.logger.info("Initializing monitors...")
            
            # Initialize chain monitors based on configuration
            enabled_chains = []
            
            # Ethereum monitor
            if settings.chains.ethereum.enabled:
                eth_monitor = NewTokenMonitor(
                    chain="ethereum",
                    rpc_url=settings.networks.ethereum_rpc_url,
                    analyzer=self.contract_analyzer,
                    scorer=self.trading_scorer,
                    auto_trading=self.auto_trading_enabled
                )
                await eth_monitor.initialize()
                self.monitors.append(eth_monitor)
                enabled_chains.append("ethereum")
            
            # Base monitor
            if settings.chains.base.enabled:
                base_monitor = BaseChainMonitor(
                    chain="base",
                    rpc_url=settings.networks.base_rpc_url,
                    analyzer=self.contract_analyzer,
                    scorer=self.trading_scorer,
                    auto_trading=self.auto_trading_enabled
                )
                await base_monitor.initialize()
                self.monitors.append(base_monitor)
                enabled_chains.append("base")
            
            # Solana monitor (if enabled)
            if hasattr(settings.chains, 'solana') and settings.chains.solana.enabled:
                try:
                    solana_monitor = SolanaMonitor(
                        scorer=self.trading_scorer,
                        auto_trading=self.auto_trading_enabled
                    )
                    await solana_monitor.initialize()
                    self.monitors.append(solana_monitor)
                    enabled_chains.append("solana")
                except Exception as e:
                    self.logger.warning(f"Solana monitor initialization failed: {e}")
            
            # Jupiter Solana monitor (if enabled)
            if hasattr(settings.chains, 'solana') and settings.chains.solana.enabled:
                try:
                    jupiter_monitor = JupiterSolanaMonitor(
                        scorer=self.trading_scorer,
                        auto_trading=self.auto_trading_enabled
                    )
                    await jupiter_monitor.initialize()
                    self.monitors.append(jupiter_monitor)
                    enabled_chains.append("jupiter")
                except Exception as e:
                    self.logger.warning(f"Jupiter monitor initialization failed: {e}")
            
            self.components_initialized["monitors"] = True
            self.logger.info(f"✅ Monitors initialized for chains: {enabled_chains}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize monitors: {e}")
            raise

    async def _initialize_web_dashboard(self) -> None:
        """Initialize web dashboard if enabled."""
        try:
            from api.dashboard import create_dashboard_app
            from api.websocket_handler import WebSocketHandler
            
            self.logger.info("Initializing web dashboard...")
            
            # Create dashboard app
            app = create_dashboard_app(self)
            
            # Start web server
            import uvicorn
            config = uvicorn.Config(
                app=app,
                host="0.0.0.0",
                port=8000,
                log_level="info"
            )
            server = uvicorn.Server(config)
            
            # Start server in background task
            self.web_server_task = asyncio.create_task(server.serve())
            self.dashboard_server = server
            
            self.components_initialized["web_dashboard"] = True
            self.logger.info("✅ Web dashboard initialized at http://localhost:8000")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize web dashboard: {e}")
            self.logger.warning("Continuing without web dashboard")

    async def _run_monitoring_loop(self) -> None:
        """Main monitoring loop."""
        self.logger.info("🔍 Starting main monitoring loop...")
        
        try:
            # Start all monitors
            monitor_tasks = []
            for monitor in self.monitors:
                task = asyncio.create_task(monitor.start_monitoring())
                monitor_tasks.append(task)
            
            # Start performance monitoring
            perf_task = asyncio.create_task(self._performance_monitor_loop())
            
            # Wait for all tasks
            await asyncio.gather(*monitor_tasks, perf_task, return_exceptions=True)
            
        except KeyboardInterrupt:
            self.logger.info("Shutdown requested by user")
        except Exception as e:
            self.logger.error(f"Monitoring loop error: {e}")
        finally:
            self.is_running = False

    async def _performance_monitor_loop(self) -> None:
        """Monitor system performance and log statistics."""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Log stats every minute
                
                # Update system stats
                uptime = datetime.now() - self.start_time
                
                # Log performance summary
                self.logger.info("📊 SYSTEM PERFORMANCE:")
                self.logger.info(f"   Uptime: {uptime}")
                self.logger.info(f"   Opportunities Detected: {self.system_stats['opportunities_detected']}")
                self.logger.info(f"   Opportunities Analyzed: {self.system_stats['opportunities_analyzed']}")
                self.logger.info(f"   Trades Executed: {self.system_stats['trades_executed']}")
                
                if self.mev_protection:
                    mev_stats = self.mev_protection.get_protection_stats()
                    self.logger.info(f"   MEV Attacks Prevented: {mev_stats.get('sandwich_attacks_prevented', 0)}")
                
                if self.node_manager:
                    node_stats = self.node_manager.get_connection_stats()
                    self.logger.info(f"   Node Connections: {node_stats.get('active_connections', 0)}/{node_stats.get('total_connections', 0)}")
                
            except Exception as e:
                self.logger.error(f"Performance monitoring error: {e}")

    def _log_initialization_summary(self) -> None:
        """Log comprehensive initialization summary."""
        self.logger.info("=" * 70)
        self.logger.info("🎯 ENHANCED PRODUCTION SYSTEM INITIALIZATION SUMMARY")
        self.logger.info("=" * 70)
        
        # Component status
        for component, initialized in self.components_initialized.items():
            status = "✅ READY" if initialized else "❌ FAILED"
            self.logger.info(f"   {component.upper()}: {status}")
        
        # Feature availability
        self.logger.info("\n🔧 FEATURE AVAILABILITY:")
        
        features = [
            ("MEV Protection", self.mev_protection is not None),
            ("Gas Optimization", self.gas_optimizer is not None),
            ("Transaction Simulation", self.tx_simulator is not None),
            ("Direct Node Manager", self.node_manager is not None),
            ("Contract Analysis", self.contract_analyzer is not None),
            ("Social Analysis", self.social_analyzer is not None),
            ("Web Dashboard", self.components_initialized["web_dashboard"])
        ]
        
        for feature_name, available in features:
            status = "✅ ENABLED" if available else "⚠️ DISABLED"
            self.logger.info(f"   {feature_name}: {status}")
        
        # Monitor summary
        self.logger.info(f"\n📡 ACTIVE MONITORS: {len(self.monitors)}")
        for monitor in self.monitors:
            self.logger.info(f"   - {monitor.__class__.__name__}")
        
        # Trading mode
        trading_mode = "🔴 LIVE TRADING" if self.auto_trading_enabled else "🟡 SIMULATION MODE"
        self.logger.info(f"\n💼 TRADING MODE: {trading_mode}")
        
        self.logger.info("=" * 70)
        self.logger.info("🚀 SYSTEM READY - MONITORING STARTED")
        self.logger.info("=" * 70)

    async def process_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Process a detected trading opportunity with enhanced features.
        
        Args:
            opportunity: Trading opportunity to process
        """
        try:
            self.system_stats["opportunities_detected"] += 1
            
            # Enhanced risk assessment
            if self.risk_manager:
                risk_assessment = await self.risk_manager.assess_opportunity_risk(opportunity)
                
                if risk_assessment.approved:
                    self.system_stats["opportunities_analyzed"] += 1
                    
                    # Simulate transaction if simulator available
                    if self.tx_simulator:
                        simulation_result = await self.tx_simulator.simulate_trade(opportunity)
                        self.system_stats["trades_simulated"] += 1
                        
                        if not simulation_result.success:
                            self.logger.warning(f"Trade simulation failed: {simulation_result.error_message}")
                            return
                    
                    # Execute trade if auto trading enabled
                    if self.auto_trading_enabled and self.execution_engine:
                        execution_result = await self.execution_engine.execute_trade(
                            opportunity,
                            risk_assessment.position_size_result,
                            execution_mode="live"
                        )
                        
                        if execution_result.success:
                            self.system_stats["trades_executed"] += 1
                            self.logger.info(f"✅ Trade executed: {execution_result.tx_hash}")
                        else:
                            self.logger.error(f"❌ Trade execution failed: {execution_result.error_message}")
                    
                    else:
                        self.logger.info(f"📋 Opportunity logged (auto-trading disabled): {opportunity.token.symbol}")
                
                else:
                    self.logger.debug(f"🚫 Opportunity rejected by risk manager: {risk_assessment.rejection_reason}")
            
        except Exception as e:
            self.logger.error(f"Error processing opportunity: {e}")

    def stop(self) -> None:
        """Stop the enhanced production system."""
        self.logger.info("🛑 Stopping Enhanced Production System...")
        self.is_running = False

    async def _cleanup(self) -> None:
        """Clean up system resources."""
        try:
            self.logger.info("🧹 Cleaning up system resources...")
            
            # Stop monitors
            for monitor in self.monitors:
                if hasattr(monitor, 'stop'):
                    try:
                        await monitor.stop()
                    except Exception as e:
                        self.logger.debug(f"Error stopping monitor: {e}")
            
            # Cleanup node manager
            if self.node_manager:
                try:
                    await self.node_manager.shutdown()
                except Exception as e:
                    self.logger.debug(f"Error shutting down node manager: {e}")
            
            # Stop web server
            if self.web_server_task:
                try:
                    self.web_server_task.cancel()
                    await self.web_server_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.logger.debug(f"Error stopping web server: {e}")
            
            # Final statistics
            uptime = datetime.now() - self.start_time if self.start_time else timedelta(0)
            self.logger.info("=" * 50)
            self.logger.info("📊 FINAL SYSTEM STATISTICS")
            self.logger.info("=" * 50)
            self.logger.info(f"Total Uptime: {uptime}")
            self.logger.info(f"Opportunities Detected: {self.system_stats['opportunities_detected']}")
            self.logger.info(f"Trades Executed: {self.system_stats['trades_executed']}")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            Dictionary containing system status information
        """
        status = {
            "running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            "auto_trading_enabled": self.auto_trading_enabled,
            "mev_protection_level": self.mev_protection_level.value,
            "components": dict(self.components_initialized),
            "statistics": dict(self.system_stats),
            "monitors": len(self.monitors),
            "features": {
                "mev_protection": self.mev_protection is not None,
                "gas_optimization": self.gas_optimizer is not None,
                "transaction_simulation": self.tx_simulator is not None,
                "direct_nodes": self.node_manager is not None,
                "web_dashboard": self.components_initialized.get("web_dashboard", False)
            }
        }
        
        # Add node manager stats if available
        if self.node_manager:
            try:
                status["node_stats"] = self.node_manager.get_connection_stats()
            except Exception:
                pass
        
        # Add MEV protection stats if available
        if self.mev_protection:
            try:
                status["mev_stats"] = self.mev_protection.get_protection_stats()
            except Exception:
                pass
        
        return status


async def main():
    """Main entry point for the enhanced production system."""
    parser = argparse.ArgumentParser(description="Enhanced DEX Sniping System")
    parser.add_argument(
        "--auto-trade",
        action="store_true",
        help="Enable automatic trading (USE WITH CAUTION)"
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Disable web dashboard"
    )
    parser.add_argument(
        "--mev-protection",
        choices=["none", "basic", "standard", "maximum", "stealth"],
        default="standard",
        help="MEV protection level"
    )
    
    args = parser.parse_args()
    
    # Convert MEV protection string to enum
    mev_level_map = {
        "none": MEVProtectionLevel.NONE,
        "basic": MEVProtectionLevel.BASIC,
        "standard": MEVProtectionLevel.STANDARD,
        "maximum": MEVProtectionLevel.MAXIMUM,
        "stealth": MEVProtectionLevel.STEALTH
    }
    mev_level = mev_level_map[args.mev_protection]
    
    # Create and start system
    system = EnhancedProductionSystem(
        auto_trading_enabled=args.auto_trade,
        disable_dashboard=args.no_dashboard,
        mev_protection_level=mev_level
    )
    
    try:
        await system.start()
    except KeyboardInterrupt:
        system.logger.info("\nShutdown requested by user")
        system.stop()
    except Exception as e:
        system.logger.error(f"System error: {e}")
        system.stop()
        raise


if __name__ == "__main__":
    asyncio.run(main())