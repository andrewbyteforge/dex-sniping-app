"""
Enhanced production system with Phase 3 speed optimizations.
Integrates MEV protection, gas optimization, direct nodes, and transaction simulation.
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
from trading.transaction_simulator import TransactionSimulator
from infrastructure.node_manager import DirectNodeManager

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
            
            # Initialize direct node manager
            self.node_manager = DirectNodeManager()
            await self.node_manager.initialize()
            
            # Add high-performance nodes if available
            # Would add actual node configurations from environment
            
            self.logger.info("✅ Infrastructure initialized with direct node connections")
            
        except Exception as e:
            self.logger.error(f"Infrastructure initialization failed: {e}")
            self.logger.warning("Falling back to standard RPC connections")
    
    async def _initialize_speed_optimizations(self) -> None:
        """Initialize Phase 3 speed optimization components."""
        try:
            self.logger.info("Initializing speed optimizations...")
            
            # Get optimized Web3 connection
            w3 = None
            if self.node_manager:
                w3 = await self.node_manager.get_web3_connection("ethereum")
            
            if not w3:
                # Fallback to standard connection
                from web3 import Web3
                w3 = Web3(Web3.HTTPProvider(settings.networks.ethereum_rpc_url))
            
            # Initialize MEV protection
            self.mev_protection = MEVProtectionManager()
            await self.mev_protection.initialize(w3)
            self.logger.info(f"   ✅ MEV Protection: {self.mev_protection_level.value}")
            
            # Initialize gas optimizer
            self.gas_optimizer = GasOptimizer()
            await self.gas_optimizer.initialize(w3)
            self.logger.info("   ✅ Gas Optimizer: Adaptive strategies enabled")
            
            # Initialize transaction simulator
            self.tx_simulator = TransactionSimulator()
            await self.tx_simulator.initialize(w3)
            self.logger.info("   ✅ Transaction Simulator: Pre-execution validation")
            
            # Create enhanced execution engine
            self.execution_engine = EnhancedExecutionEngine(
                self.risk_manager,
                self.position_manager,
                self.mev_protection_level
            )
            await self.execution_engine.initialize()
            
            self.components_initialized["speed_optimizations"] = True
            self.logger.info("✅ Speed optimizations initialized successfully")
            
            # Log performance targets
            self.logger.info("📊 Performance Targets:")
            self.logger.info("   • Detection to analysis: <5 seconds")
            self.logger.info("   • Analysis to execution: <2 seconds")
            self.logger.info("   • MEV protection: Flashbots + private pools")
            self.logger.info("   • Gas optimization: Dynamic pricing strategies")
            
        except Exception as e:
            self.logger.error(f"Speed optimization initialization failed: {e}")
            # Fall back to standard execution engine
            self.execution_engine = ExecutionEngine(self.risk_manager, self.position_manager)
            await self.execution_engine.initialize()
    
    async def _process_opportunity_enhanced(
        self,
        opportunity: TradingOpportunity,
        chain: str
    ) -> None:
        """
        Process opportunity with Phase 3 enhancements.
        
        Args:
            opportunity: Trading opportunity to process
            chain: Chain identifier
        """
        try:
            pipeline_start = datetime.now()
            
            # Stage 1: Enhanced Analysis (unchanged)
            self.logger.info(f"🔍 ANALYZING: {opportunity.token.symbol} on {chain}")
            await self._perform_enhanced_analysis(opportunity)
            self.system_stats["opportunities_analyzed"] += 1
            
            # Stage 2: Risk Assessment
            risk_assessment = self.risk_manager.assess_opportunity(opportunity)
            
            # Stage 3: Transaction Simulation (NEW)
            if self._should_simulate_trade(risk_assessment, opportunity):
                simulation_report = await self.tx_simulator.simulate_buy_trade(
                    opportunity,
                    risk_assessment.approved_amount,
                    max_slippage=0.05
                )
                
                self.system_stats["trades_simulated"] += 1
                
                if not simulation_report.success:
                    self.logger.warning(
                        f"❌ SIMULATION FAILED: {opportunity.token.symbol} - "
                        f"{simulation_report.result.value}: {simulation_report.error_message}"
                    )
                    return
                
                # Log simulation results
                self.logger.info(
                    f"✅ SIMULATION SUCCESS: {opportunity.token.symbol} - "
                    f"Impact: {simulation_report.price_impact:.2%}, "
                    f"Gas: ${simulation_report.total_gas_cost:.2f}"
                )
            
            # Stage 4: Execute Trade with Enhancements
            if self.auto_trading_enabled and self._should_execute_trade(risk_assessment, opportunity):
                # Determine urgency based on opportunity quality
                urgency = self._calculate_trade_urgency(opportunity)
                
                position = await self.execution_engine.execute_buy_order_enhanced(
                    opportunity,
                    risk_assessment,
                    urgency=urgency,
                    force_protection=urgency > 0.8  # Force MEV protection for urgent trades
                )
                
                if position:
                    self.system_stats["positions_opened"] += 1
                    self.system_stats["trades_executed"] += 1
                    
                    # Track MEV protection usage
                    mev_stats = self.mev_protection.get_protection_stats()
                    self.system_stats["mev_attacks_prevented"] = mev_stats["sandwich_attacks_prevented"]
                    
                    # Track gas savings
                    gas_stats = self.gas_optimizer.get_optimization_stats()
                    self.system_stats["gas_saved_usd"] = Decimal(str(gas_stats["total_gas_saved_gwei"] * 0.000002))
                    
                    self.logger.info(
                        f"🎯 ENHANCED TRADE EXECUTED: {opportunity.token.symbol} - "
                        f"Position ID: {position.id}"
                    )
            
            # Update performance metrics
            pipeline_time = (datetime.now() - pipeline_start).total_seconds()
            self._update_performance_metrics(pipeline_time)
            
            # Update dashboard
            await self._update_dashboard_safe(opportunity)
            
        except Exception as e:
            self.logger.error(f"Enhanced pipeline failed for {opportunity.token.symbol}: {e}")
    
    def _should_simulate_trade(
        self,
        risk_assessment: Any,
        opportunity: TradingOpportunity
    ) -> bool:
        """Determine if trade should be simulated."""
        # Always simulate high-value trades
        if risk_assessment.approved_amount > 500:
            return True
        
        # Simulate high-risk trades
        if opportunity.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return True
        
        # Simulate if recommended action is BUY or higher
        recommendation = opportunity.metadata.get("recommendation", {})
        if recommendation.get("action") in ["BUY", "STRONG_BUY"]:
            return True
        
        return False
    
    def _calculate_trade_urgency(self, opportunity: TradingOpportunity) -> float:
        """Calculate trade urgency (0-1) based on opportunity characteristics."""
        urgency = 0.5  # Base urgency
        
        # Increase urgency for strong recommendations
        recommendation = opportunity.metadata.get("recommendation", {})
        if recommendation.get("action") == "STRONG_BUY":
            urgency += 0.3
        elif recommendation.get("action") == "BUY":
            urgency += 0.2
        
        # Increase urgency for new tokens
        token_age = (datetime.now() - opportunity.token.launch_time).total_seconds()
        if token_age < 300:  # Less than 5 minutes old
            urgency += 0.2
        elif token_age < 900:  # Less than 15 minutes old
            urgency += 0.1
        
        # Increase urgency for high momentum
        if opportunity.social_metrics.growth_rate_24h > 1000:
            urgency += 0.1
        
        return min(urgency, 1.0)
    
    def _update_performance_metrics(self, pipeline_time: float) -> None:
        """Update system performance metrics."""
        # Update average execution time
        total_ops = self.system_stats["opportunities_analyzed"]
        current_avg = self.system_stats["average_execution_time"]
        
        if total_ops == 1:
            self.system_stats["average_execution_time"] = pipeline_time
        else:
            self.system_stats["average_execution_time"] = (
                (current_avg * (total_ops - 1) + pipeline_time) / total_ops
            )
    
    def _log_initialization_summary(self) -> None:
        """Log detailed initialization summary."""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("📊 INITIALIZATION SUMMARY")
        self.logger.info("=" * 70)
        
        # Component status
        for component, initialized in self.components_initialized.items():
            status = "✅" if initialized else "❌"
            self.logger.info(f"{status} {component.title()}: {'Ready' if initialized else 'Failed'}")
        
        # Performance features
        self.logger.info("\n🚀 PERFORMANCE FEATURES:")
        
        if self.node_manager:
            node_count = sum(len(configs) for configs in self.node_manager.node_configs.values())
            self.logger.info(f"   • Direct Nodes: {node_count} configured")
        
        if self.mev_protection:
            self.logger.info(f"   • MEV Protection: {self.mev_protection_level.value}")
            self.logger.info("     - Flashbots bundles")
            self.logger.info("     - Private transaction pools")
        
        if self.gas_optimizer:
            self.logger.info("   • Gas Optimization: Enabled")
            self.logger.info("     - Dynamic pricing strategies")
            self.logger.info("     - Transaction batching")
        
        if self.tx_simulator:
            self.logger.info("   • Pre-execution Simulation: Enabled")
            self.logger.info("     - Slippage prediction")
            self.logger.info("     - Failure prevention")
        
        self.logger.info("=" * 70 + "\n")
    
    async def _run_monitoring_loop(self) -> None:
        """Main monitoring loop with enhanced processing."""
        self.logger.info("Starting enhanced monitoring loop...")
        
        while self.is_running:
            try:
                # Gather opportunities from all monitors
                all_tasks = []
                
                for monitor in self.monitors:
                    if hasattr(monitor, 'check_new_opportunities'):
                        all_tasks.append(monitor.check_new_opportunities())
                
                # Wait for all monitors
                results = await asyncio.gather(*all_tasks, return_exceptions=True)
                
                # Process each opportunity with enhancements
                for result in results:
                    if isinstance(result, list):
                        for opportunity in result:
                            if isinstance(opportunity, TradingOpportunity):
                                chain = opportunity.metadata.get('chain', 'Unknown')
                                
                                # Use enhanced processing
                                await self._process_opportunity_enhanced(opportunity, chain)
                
                # Short delay between checks
                await asyncio.sleep(1)
                
                # Log performance stats every minute
                if int((datetime.now() - self.start_time).total_seconds()) % 60 == 0:
                    self._log_performance_stats()
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(5)
    
    def _log_performance_stats(self) -> None:
        """Log detailed performance statistics."""
        runtime = (datetime.now() - self.start_time).total_seconds() / 60
        
        self.logger.info("\n📊 PERFORMANCE STATS")
        self.logger.info(f"Runtime: {runtime:.1f} minutes")
        self.logger.info(f"Opportunities Detected: {self.system_stats['opportunities_detected']}")
        self.logger.info(f"Opportunities Analyzed: {self.system_stats['opportunities_analyzed']}")
        self.logger.info(f"Trades Simulated: {self.system_stats['trades_simulated']}")
        self.logger.info(f"Trades Executed: {self.system_stats['trades_executed']}")
        self.logger.info(f"Average Pipeline Time: {self.system_stats['average_execution_time']:.2f}s")
        
        if self.mev_protection:
            mev_stats = self.mev_protection.get_protection_stats()
            self.logger.info(f"MEV Attacks Prevented: {mev_stats['sandwich_attacks_prevented']}")
            self.logger.info(f"Flashbots Success Rate: {mev_stats['flashbots_success_rate']:.1%}")
        
        if self.gas_optimizer:
            gas_stats = self.gas_optimizer.get_optimization_stats()
            self.logger.info(f"Gas Saved: ${self.system_stats['gas_saved_usd']:.2f}")
            self.logger.info(f"Current Base Fee: {gas_stats['current_base_fee_gwei']:.1f} gwei")
        
        if self.tx_simulator:
            sim_stats = self.tx_simulator.get_simulation_stats()
            self.logger.info(f"Failure Prevention Rate: {sim_stats['failure_prevention_rate']:.1%}")
    
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
            
            # Configure portfolio limits
            portfolio_limits = PortfolioLimits(
                max_total_exposure_usd=10000.0,  # $10K max exposure
                max_single_position_usd=1000.0,   # $1K max per position
                max_daily_loss_usd=2000.0,        # $2K daily loss limit
                max_positions_per_chain=5,        # 5 positions per chain
                max_total_positions=15,           # 15 total positions
                min_liquidity_ratio=0.05          # 5% of liquidity max
            )
            
            # Initialize risk manager
            self.risk_manager = RiskManager(portfolio_limits)
            
            # Initialize position manager
            self.position_manager = PositionManager(self.risk_manager)
            await self.position_manager.initialize()
            
            self.components_initialized["trading_system"] = True
            self.logger.info("✅ Trading system initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading system: {e}")
            raise
    
    async def _initialize_monitors(self) -> None:
        """Initialize all chain monitors with enhanced connections."""
        try:
            self.logger.info("Initializing enhanced monitors...")
            
            # Ethereum monitor with direct node
            eth_w3 = None
            if self.node_manager:
                eth_w3 = await self.node_manager.get_web3_connection("ethereum")
            
            eth_monitor = NewTokenMonitor()
            # Monitors don't have async initialize, they start automatically
            self.monitors.append(eth_monitor)
            self.logger.info("   ✅ Ethereum monitor added")
            
            # Base monitor
            base_monitor = BaseChainMonitor()
            self.monitors.append(base_monitor)
            self.logger.info("   ✅ Base monitor added")
            
            # Solana monitors
            try:
                solana_monitor = SolanaMonitor()
                self.monitors.append(solana_monitor)
                self.logger.info("   ✅ Solana (Pump.fun) monitor added")
            except Exception as e:
                self.logger.warning(f"   ⚠️ Solana monitor failed: {e}")
            
            try:
                jupiter_monitor = JupiterSolanaMonitor()
                self.monitors.append(jupiter_monitor)
                self.logger.info("   ✅ Jupiter monitor added")
            except Exception as e:
                self.logger.warning(f"   ⚠️ Jupiter monitor failed: {e}")
            
            # Subscribe to fast block updates if available
            if self.node_manager:
                for chain in ["ethereum", "base"]:
                    await self.node_manager.subscribe_to_blocks(
                        chain,
                        self._handle_new_block
                    )
            
            self.components_initialized["monitors"] = True
            self.logger.info(f"✅ Initialized {len(self.monitors)} monitors with enhanced connections")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize monitors: {e}")
            raise
    
    async def _handle_new_block(self, block: Dict) -> None:
        """Handle new block from direct node subscription."""
        # Could trigger immediate opportunity checks
        pass
    
    async def _perform_enhanced_analysis(self, opportunity: TradingOpportunity) -> None:
        """Perform enhanced analysis on opportunity."""
        try:
            # Contract analysis
            if self.contract_analyzer and opportunity.token.chain != "solana":
                opportunity.contract_analysis = await self.contract_analyzer.analyze_contract(
                    opportunity
                )
            
            # Social analysis
            if self.social_analyzer:
                opportunity.social_metrics = await self.social_analyzer.analyze_social_metrics(
                    opportunity
                )
            
            # Trading score and recommendation
            if self.trading_scorer:
                score = self.trading_scorer.score_opportunity(opportunity)
                recommendation = self.trading_scorer.generate_recommendation(
                    opportunity, score
                )
                
                opportunity.metadata["score"] = score
                opportunity.metadata["recommendation"] = recommendation
                opportunity.metadata["analysis_time"] = datetime.now().isoformat()
            
        except Exception as e:
            self.logger.error(f"Enhanced analysis failed: {e}")
    
    def _should_execute_trade(self, risk_assessment: Any, opportunity: TradingOpportunity) -> bool:
        """Determine if trade should be executed."""
        if risk_assessment.risk_assessment != "APPROVED":
            return False
        
        recommendation = opportunity.metadata.get("recommendation", {})
        if recommendation.get("action") not in ["BUY", "STRONG_BUY"]:
            return False
        
        return True
    
    async def _initialize_web_dashboard(self) -> None:
        """Initialize web dashboard."""
        try:
            self.logger.info("Initializing web dashboard...")
            
            # Import dashboard
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "dashboard_server", 
                "api/dashboard_server.py"
            )
            dashboard_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(dashboard_module)
            
            # Get dashboard components
            self.dashboard_server = dashboard_module.dashboard_server
            self.dashboard_app = dashboard_module.app
            
            # Connect components
            if self.execution_engine:
                self.dashboard_server.trading_executor = self.execution_engine
            if self.risk_manager:
                self.dashboard_server.risk_manager = self.risk_manager
            if self.position_manager:
                self.dashboard_server.position_manager = self.position_manager
            
            # Initialize dashboard
            await self.dashboard_server.initialize()
            
            # Start server
            self.web_server_task = asyncio.create_task(self._start_dashboard_server())
            await asyncio.sleep(3)
            
            if not self.web_server_task.done():
                self.components_initialized["web_dashboard"] = True
                self.logger.info("✅ Web dashboard initialized")
                self.logger.info("   🌐 Dashboard: http://localhost:8000")
            
        except Exception as e:
            self.logger.warning(f"Dashboard initialization failed: {e}")
            self.logger.info("Continuing without dashboard")
    
    async def _start_dashboard_server(self) -> None:
        """Start dashboard server."""
        try:
            import uvicorn
            
            config = uvicorn.Config(
                self.dashboard_app,
                host="0.0.0.0",
                port=8000,
                log_level="warning"
            )
            
            server = uvicorn.Server(config)
            await server.serve()
            
        except Exception as e:
            self.logger.error(f"Dashboard server failed: {e}")
    
    async def _update_dashboard_safe(self, opportunity: TradingOpportunity) -> None:
        """Safely update dashboard."""
        try:
            if self.dashboard_server:
                await self.dashboard_server.add_opportunity(opportunity)
        except Exception as e:
            self.logger.debug(f"Dashboard update failed: {e}")
    
    async def _cleanup(self) -> None:
        """Clean up all resources."""
        try:
            self.logger.info("Shutting down enhanced production system...")
            
            # Stop monitors
            for monitor in self.monitors:
                if hasattr(monitor, 'stop'):
                    monitor.stop()
            
            # Clean up analyzers
            if self.social_analyzer:
                await self.social_analyzer.cleanup()
            
            # Clean up node manager
            if self.node_manager:
                await self.node_manager.cleanup()
            
            # Stop dashboard
            if self.web_server_task:
                self.web_server_task.cancel()
            
            self.logger.info("Enhanced production system shut down successfully")
            
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def stop(self) -> None:
        """Stop the system."""
        self.is_running = False


async def main():
    """Main entry point."""
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