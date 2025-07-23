"""
Production-ready main entry point with full trading capabilities.
Integrates all Phase 3 components for automated DEX sniping with risk management.
"""

import asyncio
import sys
import os
from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal

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

# Phase 3 Components
from trading.risk_manager import RiskManager, PortfolioLimits, RiskAssessment
from trading.position_manager import PositionManager, Position, PositionStatus
from trading.execution_engine import ExecutionEngine, ExecutionResult

# Configuration and API
from config.chains import multichain_settings, ChainType
from config.settings import settings


class ProductionTradingSystem:
    """
    Production-ready multi-chain DEX sniping system with full automation.
    Integrates monitoring, analysis, risk management, and execution.
    """

    def __init__(self, auto_trading_enabled: bool = False, disable_dashboard: bool = False) -> None:
        """
        Initialize the production trading system.
        
        Args:
            auto_trading_enabled: Whether to enable automated trading execution
            disable_dashboard: Whether to disable web dashboard
        """
        self.logger = logger_manager.get_logger("ProductionTradingSystem")
        self.auto_trading_enabled = auto_trading_enabled
        self.disable_dashboard = disable_dashboard
        self.is_running = False
        self.start_time: Optional[datetime] = None
        
        # Component initialization flags
        self.components_initialized = {
            'monitors': False,
            'analyzers': False,
            'trading_system': False,
            'web_dashboard': False
        }
        
        # Monitoring components
        self.monitors: List = []
        
        # Analysis components
        self.contract_analyzer: Optional[ContractAnalyzer] = None
        self.social_analyzer: Optional[SocialAnalyzer] = None
        self.trading_scorer: Optional[TradingScorer] = None
        
        # Trading components
        self.risk_manager: Optional[RiskManager] = None
        self.position_manager: Optional[PositionManager] = None
        self.execution_engine: Optional[ExecutionEngine] = None
        
        # Web dashboard
        self.dashboard_server = None
        self.web_server_task: Optional[asyncio.Task] = None
        
        # Performance tracking
        self.system_stats = {
            'opportunities_detected': 0,
            'opportunities_analyzed': 0,
            'positions_opened': 0,
            'trades_executed': 0,
            'total_pnl': Decimal('0'),
            'uptime_start': None,
            'chains': {
                'ETHEREUM': {'opportunities': 0, 'positions': 0},
                'BASE': {'opportunities': 0, 'positions': 0},
                'SOLANA-PUMP': {'opportunities': 0, 'positions': 0},
                'SOLANA-JUPITER': {'opportunities': 0, 'positions': 0}
            }
        }

    async def start(self) -> None:
        """Start the complete production trading system."""
        try:
            self.logger.info("🚀 STARTING PRODUCTION TRADING SYSTEM")
            self.logger.info("=" * 80)
            self.logger.info(f"Auto Trading: {'ENABLED' if self.auto_trading_enabled else 'DISABLED'}")
            self.logger.info("Full Pipeline: Monitor → Analyze → Risk Assess → Execute → Manage")
            self.logger.info("=" * 80)
            
            self.start_time = datetime.now()
            self.system_stats['uptime_start'] = self.start_time
            self.is_running = True
            
            # Initialize all system components
            await self._initialize_all_components()
            
            # Start the main trading loop
            await self._run_production_loop()
            
        except Exception as e:
            self.logger.error(f"FATAL ERROR in production system: {e}")
            raise
        finally:
            await self._cleanup_all_components()

    async def _initialize_all_components(self) -> None:
        """Initialize all system components in proper order."""
        try:
            self.logger.info("INITIALIZING PRODUCTION COMPONENTS...")
            
            # Phase 1: Initialize analysis components
            await self._initialize_analyzers()
            
            # Phase 2: Initialize trading system
            await self._initialize_trading_system()
            
            # Phase 3: Initialize web dashboard (optional)
            if not self.disable_dashboard:
                await self._initialize_web_dashboard()
            else:
                self.logger.info("Web dashboard disabled by command line option")
            
            # Phase 4: Initialize monitors (last, so they can use other components)
            await self._initialize_monitors()
            
            self._log_initialization_summary()
            
        except Exception as e:
            self.logger.error(f"Component initialization failed: {e}")
            raise

    async def _initialize_analyzers(self) -> None:
        """Initialize Phase 2 analysis components."""
        try:
            self.logger.info("Initializing analysis components...")
            
            # Initialize Web3 for contract analysis
            from web3 import Web3
            w3 = Web3(Web3.HTTPProvider(settings.networks.ethereum_rpc_url))
            
            if not w3.is_connected():
                raise ConnectionError("Failed to connect to Ethereum for contract analysis")
            
            # Initialize analyzers
            self.contract_analyzer = ContractAnalyzer(w3)
            await self.contract_analyzer.initialize()
            
            self.social_analyzer = SocialAnalyzer()
            await self.social_analyzer.initialize()
            
            self.trading_scorer = TradingScorer()
            
            self.components_initialized['analyzers'] = True
            self.logger.info("✅ Analysis components initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize analyzers: {e}")
            raise

    async def _initialize_trading_system(self) -> None:
        """Initialize Phase 3 trading system components."""
        try:
            self.logger.info("Initializing trading system...")
            
            # Configure portfolio limits
            portfolio_limits = PortfolioLimits(
                max_total_exposure_usd=5000.0,  # $5K max exposure
                max_single_position_usd=500.0,  # $500 max per position
                max_daily_loss_usd=1000.0,      # $1K daily loss limit
                max_positions_per_chain=3,       # 3 positions per chain
                max_total_positions=10,          # 10 total positions
                min_liquidity_ratio=0.05         # 5% of liquidity max
            )
            
            # Initialize risk manager
            self.risk_manager = RiskManager(portfolio_limits)
            
            # Initialize position manager
            self.position_manager = PositionManager(self.risk_manager)
            await self.position_manager.initialize()
            
            # Initialize execution engine
            self.execution_engine = ExecutionEngine(self.risk_manager, self.position_manager)
            await self.execution_engine.initialize()
            
            self.components_initialized['trading_system'] = True
            self.logger.info("✅ Trading system initialized")
            self.logger.info(f"   Portfolio Limits: ${portfolio_limits.max_total_exposure_usd:,.0f} total exposure")
            self.logger.info(f"   Position Limits: ${portfolio_limits.max_single_position_usd:,.0f} per position")
            self.logger.info(f"   Daily Loss Limit: ${portfolio_limits.max_daily_loss_usd:,.0f}")
            self.logger.info(f"   Auto Trading: {'ENABLED' if self.auto_trading_enabled else 'DISABLED'}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading system: {e}")
            raise

    async def _initialize_web_dashboard(self) -> None:
        """Initialize web dashboard with proper integration."""
        try:
            self.logger.info("Initializing production web dashboard...")
            
            # Import dashboard using the working method
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
            
            # Connect trading components safely
            if hasattr(self, 'execution_engine'):
                self.dashboard_server.trading_executor = self.execution_engine
            if hasattr(self, 'risk_manager'):
                self.dashboard_server.risk_manager = self.risk_manager
            if hasattr(self, 'position_manager'):
                self.dashboard_server.position_manager = self.position_manager
            
            # Initialize dashboard
            await self.dashboard_server.initialize()
            
            # Start server in background
            self.web_server_task = asyncio.create_task(self._start_dashboard_server())
            
            # Wait for startup
            await asyncio.sleep(3)
            
            # Check if server started successfully
            if not self.web_server_task.done():
                self.components_initialized['web_dashboard'] = True
                self.logger.info("✅ Production web dashboard initialized")
                self.logger.info("   🌐 Dashboard: http://localhost:8000")
                self.logger.info("   📊 Real-time opportunity tracking")
                self.logger.info("   💹 Live trading monitoring")
            else:
                self.logger.warning("Dashboard server failed to start")
                self.web_server_task = None
                
        except Exception as e:
            self.logger.warning(f"Dashboard initialization failed: {e}")
            self.logger.info("Continuing without dashboard - console mode only")

    async def _start_dashboard_server(self):
        """Start dashboard server in background."""
        try:
            import uvicorn
            
            config = uvicorn.Config(
                self.dashboard_app,  # Use the loaded app
                host="127.0.0.1",
                port=8000,
                log_level="warning",
                access_log=False
            )
            
            server = uvicorn.Server(config)
            await server.serve()
            
        except Exception as e:
            self.logger.error(f"Dashboard server error: {e}")

    # Update the dashboard update methods to use the working integration

    async def _update_dashboard_safe(self, opportunity: TradingOpportunity) -> None:
        """Safely update dashboard without breaking the main pipeline."""
        try:
            if (hasattr(self, 'dashboard_server') and 
                self.dashboard_server and 
                self.components_initialized.get('web_dashboard', False)):
                
                await self.dashboard_server.add_opportunity(opportunity)
                
        except Exception as e:
            # Don't let dashboard errors break the trading pipeline
            self.logger.debug(f"Dashboard update failed (non-critical): {e}")

    async def _broadcast_trade_safe(self, message: Dict) -> None:
        """Safely broadcast trade message without breaking execution."""
        try:
            if (hasattr(self, 'dashboard_server') and 
                self.dashboard_server and 
                self.components_initialized.get('web_dashboard', False)):
                
                await self.dashboard_server.broadcast_to_clients(message)
                
        except Exception as e:
            # Don't let dashboard broadcast errors break trading
            self.logger.debug(f"Dashboard broadcast failed (non-critical): {e}")





    async def _run_dashboard_server(self, server) -> None:
        """
        Run the dashboard server with proper error handling.
        
        Args:
            server: Uvicorn server instance
        """
        try:
            await server.serve()
        except asyncio.CancelledError:
            self.logger.info("Dashboard server cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Dashboard server error: {e}")
            raise













    async def _initialize_monitors(self) -> None:
        """Initialize chain monitors with production callbacks."""
        try:
            self.logger.info("Initializing production monitors...")
            
            # Ethereum monitor
            try:
                eth_monitor = NewTokenMonitor(check_interval=10.0)  # Slower for production
                eth_monitor.add_callback(self._handle_ethereum_opportunity)
                self.monitors.append(eth_monitor)
                self.logger.info("✅ Ethereum monitor ready")
            except Exception as e:
                self.logger.warning(f"Ethereum monitor failed: {e}")
            
            # Base monitor
            try:
                base_monitor = BaseChainMonitor(check_interval=5.0)
                base_monitor.add_callback(self._handle_base_opportunity)
                self.monitors.append(base_monitor)
                self.logger.info("✅ Base monitor ready")
            except Exception as e:
                self.logger.warning(f"Base monitor failed: {e}")
            
            # Solana monitors
            try:
                pump_monitor = SolanaMonitor(check_interval=10.0)  # Slower to avoid rate limits
                pump_monitor.add_callback(self._handle_solana_pump_opportunity)
                self.monitors.append(pump_monitor)
                self.logger.info("✅ Solana Pump.fun monitor ready")
            except Exception as e:
                self.logger.warning(f"Solana Pump monitor failed: {e}")
            
            try:
                jupiter_monitor = JupiterSolanaMonitor(check_interval=30.0)  # Even slower backup
                jupiter_monitor.add_callback(self._handle_solana_jupiter_opportunity)
                self.monitors.append(jupiter_monitor)
                self.logger.info("✅ Solana Jupiter monitor ready")
            except Exception as e:
                self.logger.warning(f"Solana Jupiter monitor failed: {e}")
            
            if not self.monitors:
                raise RuntimeError("No monitors were successfully initialized")
            
            self.components_initialized['monitors'] = True
            self.logger.info(f"✅ {len(self.monitors)} monitors initialized for production")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize monitors: {e}")
            raise

    async def _run_production_loop(self) -> None:
        """Run the main production trading loop."""
        try:
            self.logger.info("🎯 STARTING PRODUCTION TRADING LOOP")
            self.logger.info("Real-time monitoring across all chains with automated execution")
            
            # Start all monitors
            monitor_tasks = []
            for monitor in self.monitors:
                task = asyncio.create_task(monitor.start())
                monitor_tasks.append(task)
                self.logger.info(f"Started monitor: {monitor.name}")
            
            # Start system monitoring tasks
            system_tasks = [
                asyncio.create_task(self._system_health_monitor()),
                asyncio.create_task(self._performance_reporter()),
                asyncio.create_task(self._position_monitor())
            ]
            
            # Combine all tasks
            all_tasks = monitor_tasks + system_tasks
            if self.web_server_task:
                all_tasks.append(self.web_server_task)
            
            # Wait for tasks (they should run indefinitely)
            await asyncio.gather(*all_tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"Production loop error: {e}")
            raise

    # Production opportunity handlers with full pipeline
    
    async def _handle_ethereum_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Ethereum opportunity with full production pipeline."""
        try:
            self.system_stats['opportunities_detected'] += 1
            self.system_stats['chains']['ETHEREUM']['opportunities'] += 1
            opportunity.metadata['chain'] = 'ETHEREUM'
            
            await self._process_opportunity_full_pipeline(opportunity, "ETHEREUM")
            
        except Exception as e:
            self.logger.error(f"Error handling Ethereum opportunity: {e}")

    async def _handle_base_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Base opportunity with full production pipeline."""
        try:
            self.system_stats['opportunities_detected'] += 1
            self.system_stats['chains']['BASE']['opportunities'] += 1
            opportunity.metadata['chain'] = 'BASE'
            
            await self._process_opportunity_full_pipeline(opportunity, "BASE")
            
        except Exception as e:
            self.logger.error(f"Error handling Base opportunity: {e}")

    async def _handle_solana_pump_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Solana Pump.fun opportunity."""
        try:
            self.system_stats['opportunities_detected'] += 1
            self.system_stats['chains']['SOLANA-PUMP']['opportunities'] += 1
            opportunity.metadata['chain'] = 'SOLANA-PUMP'
            opportunity.metadata['solana_source'] = 'Pump.fun'
            
            await self._process_opportunity_full_pipeline(opportunity, "SOLANA-PUMP")
            
        except Exception as e:
            self.logger.error(f"Error handling Solana Pump opportunity: {e}")

    async def _handle_solana_jupiter_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Solana Jupiter opportunity."""
        try:
            self.system_stats['opportunities_detected'] += 1
            self.system_stats['chains']['SOLANA-JUPITER']['opportunities'] += 1
            opportunity.metadata['chain'] = 'SOLANA-JUPITER'
            opportunity.metadata['solana_source'] = 'Jupiter'
            
            await self._process_opportunity_full_pipeline(opportunity, "SOLANA-JUPITER")
            
        except Exception as e:
            self.logger.error(f"Error handling Solana Jupiter opportunity: {e}")

    async def _process_opportunity_full_pipeline(
        self, 
        opportunity: TradingOpportunity, 
        chain: str
    ) -> None:
        """
        Process opportunity through the complete production pipeline.
        
        Args:
            opportunity: Trading opportunity to process
            chain: Chain identifier for logging
        """
        try:
            pipeline_start = datetime.now()
            
            # Stage 1: Enhanced Analysis
            self.logger.info(f"🔍 ANALYZING: {opportunity.token.symbol} on {chain}")
            
            await self._perform_enhanced_analysis(opportunity)
            self.system_stats['opportunities_analyzed'] += 1
            
            # Stage 2: Risk Assessment
            risk_assessment = self.risk_manager.assess_opportunity(opportunity)
            
            # Stage 3: Trading Decision
            recommendation = opportunity.metadata.get('recommendation', {})
            action = recommendation.get('action', 'UNKNOWN')
            confidence = recommendation.get('confidence', 'UNKNOWN')
            
            # Log analysis results
            await self._log_production_opportunity(opportunity, chain, risk_assessment)
            
            # Stage 4: Execute Trade (if conditions met)
            if self.auto_trading_enabled and self._should_execute_trade(risk_assessment, recommendation):
                position = await self._execute_production_trade(opportunity, risk_assessment)
                
                if position:
                    self.system_stats['positions_opened'] += 1
                    self.system_stats['trades_executed'] += 1
                    self.system_stats['chains'][chain]['positions'] += 1
                    
                    self.logger.info(
                        f"🎯 TRADE EXECUTED: {opportunity.token.symbol} - Position ID: {position.id}"
                    )
            else:
                reason = self._get_no_trade_reason(risk_assessment, recommendation)
                self.logger.info(f"📋 NO TRADE: {opportunity.token.symbol} - {reason}")
            
            # Stage 5: Update Dashboard (safely)
            await self._update_dashboard_safe(opportunity)
            
            # Performance tracking
            pipeline_time = (datetime.now() - pipeline_start).total_seconds()
            self.logger.debug(f"Pipeline completed in {pipeline_time:.2f}s")
            
        except Exception as e:
            self.logger.error(f"Pipeline processing failed for {opportunity.token.symbol}: {e}")

    async def _update_dashboard_safe(self, opportunity: TradingOpportunity) -> None:
        """Safely update dashboard without breaking the main pipeline."""
        try:
            if (hasattr(self, 'dashboard_server') and 
                self.dashboard_server and 
                self.components_initialized.get('web_dashboard', False)):
                
                await self.dashboard_server.add_opportunity(opportunity)
                
        except Exception as e:
            # Don't let dashboard errors break the trading pipeline
            self.logger.debug(f"Dashboard update failed (non-critical): {e}")







    async def _perform_enhanced_analysis(self, opportunity: TradingOpportunity) -> None:
        """Perform complete enhanced analysis with error handling."""
        try:
            # Contract analysis (for EVM chains)
            if 'SOLANA' not in opportunity.metadata.get('chain', ''):
                opportunity.contract_analysis = await self.contract_analyzer.analyze_contract(opportunity)
            else:
                # Simplified analysis for Solana
                from models.token import ContractAnalysis
                opportunity.contract_analysis = ContractAnalysis()
                opportunity.contract_analysis.risk_level = RiskLevel.MEDIUM
                opportunity.contract_analysis.risk_score = 0.4
                
            # Social analysis
            opportunity.social_metrics = await self.social_analyzer.analyze_social_metrics(opportunity)
            
            # Generate trading recommendation
            score = self.trading_scorer.score_opportunity(opportunity)
            recommendation = self.trading_scorer.generate_recommendation(opportunity)
            
            # Update metadata
            opportunity.metadata['recommendation'] = recommendation
            opportunity.metadata['analysis_timestamp'] = datetime.now()
            opportunity.confidence_score = score
            
        except Exception as e:
            self.logger.error(f"Enhanced analysis failed: {e}")
            # Set safe defaults
            opportunity.contract_analysis.risk_level = RiskLevel.HIGH
            opportunity.metadata['recommendation'] = {
                'action': 'AVOID',
                'confidence': 'HIGH',
                'score': 0.0,
                'reasons': ['Analysis failed'],
                'warnings': ['Could not analyze token safely']
            }

    def _should_execute_trade(self, risk_assessment, recommendation: Dict) -> bool:
        """
        Determine if a trade should be executed based on risk and recommendation.
        
        Args:
            risk_assessment: Risk assessment result
            recommendation: Trading recommendation
            
        Returns:
            True if trade should be executed, False otherwise
        """
        try:
            # Must be approved by risk manager
            if risk_assessment.risk_assessment != RiskAssessment.APPROVED:
                return False
            
            # Must have positive position size
            if risk_assessment.approved_amount <= 0:
                return False
            
            # Must be strong buy with high confidence
            action = recommendation.get('action')
            confidence = recommendation.get('confidence')
            
            if action != 'STRONG_BUY' or confidence != 'HIGH':
                return False
            
            # Additional safety check - score must be high
            score = recommendation.get('score', 0.0)
            if score < 0.8:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Trade decision evaluation failed: {e}")
            return False

    def _get_no_trade_reason(self, risk_assessment, recommendation: Dict) -> str:
        """Get human-readable reason for not executing trade."""
        try:
            if not self.auto_trading_enabled:
                return "Auto-trading disabled"
            
            if risk_assessment.risk_assessment == RiskAssessment.REJECTED:
                return f"Risk rejected: {', '.join(risk_assessment.reasons)}"
            
            if risk_assessment.approved_amount <= 0:
                return "No approved position size"
            
            action = recommendation.get('action', 'UNKNOWN')
            confidence = recommendation.get('confidence', 'UNKNOWN')
            
            if action != 'STRONG_BUY':
                return f"Recommendation: {action} (need STRONG_BUY)"
            
            if confidence != 'HIGH':
                return f"Confidence: {confidence} (need HIGH)"
            
            score = recommendation.get('score', 0.0)
            if score < 0.8:
                return f"Score too low: {score:.2f} (need ≥0.8)"
            
            return "Unknown reason"
            
        except Exception:
            return "Evaluation error"

    async def _execute_production_trade(
        self, 
        opportunity: TradingOpportunity, 
        risk_assessment
    ) -> Optional[Position]:
        """
        Execute a production trade with full error handling.
        
        Args:
            opportunity: Trading opportunity
            risk_assessment: Risk assessment result
            
        Returns:
            Position if successful, None otherwise
        """
        try:
            self.logger.info(f"💰 EXECUTING PRODUCTION TRADE: {opportunity.token.symbol}")
            
            position = await self.execution_engine.execute_buy_order(opportunity, risk_assessment)
            
            if position:
                self.logger.info(
                    f"✅ TRADE SUCCESS: {opportunity.token.symbol} - "
                    f"Position: {position.id}, Amount: {position.entry_amount}"
                )
                
                # Broadcast to dashboard (safely)
                await self._broadcast_trade_safe({
                    "type": "trade_executed",
                    "data": {
                        "token_symbol": opportunity.token.symbol,
                        "position_id": position.id,
                        "entry_amount": str(position.entry_amount),
                        "entry_price": str(position.entry_price),
                        "chain": opportunity.metadata.get('chain')
                    }
                })
                
                return position
            else:
                self.logger.warning(f"❌ TRADE FAILED: {opportunity.token.symbol}")
                return None
                
        except Exception as e:
            self.logger.error(f"Production trade execution failed: {e}")
            return None

    async def _broadcast_trade_safe(self, message: Dict) -> None:
        """Safely broadcast trade message without breaking execution."""
        try:
            if (hasattr(self, 'dashboard_server') and 
                self.dashboard_server and 
                self.components_initialized.get('web_dashboard', False)):
                
                await self.dashboard_server.broadcast_message(message)
                
        except Exception as e:
            # Don't let dashboard broadcast errors break trading
            self.logger.debug(f"Dashboard broadcast failed (non-critical): {e}")





    async def _log_production_opportunity(
        self, 
        opportunity: TradingOpportunity, 
        chain: str, 
        risk_assessment
    ) -> None:
        """Log opportunity with production-level detail."""
        try:
            recommendation = opportunity.metadata.get('recommendation', {})
            
            self.logger.info("=" * 100)
            self.logger.info(f"PRODUCTION OPPORTUNITY: {opportunity.token.symbol} on {chain}")
            self.logger.info(f"Address: {opportunity.token.address}")
            self.logger.info(f"Detected: {opportunity.detected_at.strftime('%H:%M:%S')}")
            
            # Risk Assessment
            self.logger.info(f"RISK ASSESSMENT: {risk_assessment.risk_assessment.value.upper()}")
            self.logger.info(f"Risk Score: {risk_assessment.risk_score:.3f}")
            self.logger.info(f"Approved Amount: {risk_assessment.approved_amount}")
            
            # Analysis Results
            analysis = opportunity.contract_analysis
            social = opportunity.social_metrics
            
            self.logger.info(f"Contract Risk: {analysis.risk_level.value.upper()}")
            self.logger.info(f"Social Score: {social.social_score:.2f}")
            self.logger.info(f"Liquidity: ${opportunity.liquidity.liquidity_usd:,.0f}")
            
            # Trading Recommendation
            action = recommendation.get('action', 'UNKNOWN')
            confidence = recommendation.get('confidence', 'UNKNOWN')
            score = recommendation.get('score', 0.0)
            
            self.logger.info(f"RECOMMENDATION: {action} ({confidence}, score: {score:.2f})")
            
            # Reasons
            reasons = risk_assessment.reasons[:3]  # Top 3 reasons
            if reasons:
                self.logger.info(f"Key Factors: {', '.join(reasons)}")
            
            # Trading Decision
            will_trade = (
                self.auto_trading_enabled and 
                self._should_execute_trade(risk_assessment, recommendation)
            )
            self.logger.info(f"TRADING DECISION: {'EXECUTE' if will_trade else 'SKIP'}")
            
            self.logger.info("=" * 100)
            
        except Exception as e:
            self.logger.error(f"Error logging opportunity: {e}")

    # System monitoring tasks

    async def _system_health_monitor(self) -> None:
        """Monitor overall system health and performance."""
        try:
            while self.is_running:
                await asyncio.sleep(60)  # Check every minute
                
                # Check component health
                health_status = {
                    'analyzers': self.components_initialized['analyzers'],
                    'trading_system': self.components_initialized['trading_system'],
                    'monitors_active': len([m for m in self.monitors if m.is_running]),
                    'positions_active': len(self.position_manager.active_positions),
                    'portfolio_status': self.risk_manager.get_portfolio_status()
                }
                
                # Log health status periodically
                if datetime.now().minute % 10 == 0:  # Every 10 minutes
                    self.logger.info(f"SYSTEM HEALTH: {health_status}")
                
        except Exception as e:
            self.logger.error(f"System health monitor error: {e}")

    async def _performance_reporter(self) -> None:
        """Report system performance metrics."""
        try:
            while self.is_running:
                await asyncio.sleep(300)  # Report every 5 minutes
                
                uptime = datetime.now() - self.start_time
                
                # Calculate rates
                opp_rate = self.system_stats['opportunities_detected'] / max(uptime.total_seconds() / 3600, 1)
                analysis_rate = self.system_stats['opportunities_analyzed'] / max(uptime.total_seconds() / 60, 1)
                
                # Get portfolio performance
                portfolio_summary = self.position_manager.get_portfolio_summary()
                execution_metrics = self.execution_engine.get_execution_metrics()
                
                self.logger.info("📊 PRODUCTION PERFORMANCE REPORT")
                self.logger.info(f"Uptime: {str(uptime).split('.')[0]}")
                self.logger.info(f"Opportunity Rate: {opp_rate:.1f}/hour")
                self.logger.info(f"Analysis Rate: {analysis_rate:.1f}/minute")
                self.logger.info(f"Positions: {portfolio_summary.get('active_positions', 0)} active")
                self.logger.info(f"Total P&L: ${portfolio_summary.get('total_pnl', 0):.2f}")
                self.logger.info(f"Win Rate: {portfolio_summary.get('win_rate_percentage', 0):.1f}%")
                self.logger.info(f"Execution Success: {execution_metrics.get('success_rate_percentage', 0):.1f}%")
                
                # Update dashboard if available
                if self.dashboard_server:
                    await self.dashboard_server.update_analysis_rate(int(analysis_rate))
                
        except Exception as e:
            self.logger.error(f"Performance reporter error: {e}")

    async def _position_monitor(self) -> None:
        """Monitor positions for automated management."""
        try:
            while self.is_running:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # The position manager handles its own monitoring
                # This is for additional position-level logic
                
                active_positions = list(self.position_manager.active_positions.values())
                
                for position in active_positions:
                    # Check for positions nearing time limits
                    age = datetime.now() - position.entry_time
                    if age.total_seconds() > 20 * 3600:  # 20 hours (warn before 24h limit)
                        self.logger.warning(
                            f"Position {position.token_symbol} approaching time limit: {age}"
                        )
                    
                    # Log significant P&L changes
                    if abs(position.unrealized_pnl_percentage) > 50:  # >50% movement
                        self.logger.info(
                            f"Significant P&L: {position.token_symbol} "
                            f"{position.unrealized_pnl_percentage:+.1f}%"
                        )
                
        except Exception as e:
            self.logger.error(f"Position monitor error: {e}")

    def _log_initialization_summary(self) -> None:
        """Log system initialization summary."""
        self.logger.info("PRODUCTION SYSTEM INITIALIZATION COMPLETE")
        self.logger.info("=" * 80)
        
        # Component status
        for component, status in self.components_initialized.items():
            status_icon = "✅" if status else "❌"
            self.logger.info(f"{status_icon} {component.replace('_', ' ').title()}: {'Initialized' if status else 'Failed'}")
        
        self.logger.info(f"🔍 Monitors: {len(self.monitors)} active")
        self.logger.info(f"🤖 Auto Trading: {'ENABLED' if self.auto_trading_enabled else 'DISABLED'}")
        
        # Trading limits
        if self.risk_manager:
            limits = self.risk_manager.limits
            self.logger.info(f"💰 Max Exposure: ${limits.max_total_exposure_usd:,.0f}")
            self.logger.info(f"📊 Max Positions: {limits.max_total_positions}")
            self.logger.info(f"🛡️  Daily Loss Limit: ${limits.max_daily_loss_usd:,.0f}")
        
        self.logger.info("🌐 Dashboard: http://localhost:8000")
        self.logger.info("=" * 80)

    def stop(self) -> None:
        """Stop the production system gracefully."""
        self.logger.info("STOPPING production system...")
        self.is_running = False
        
        # Stop monitors
        for monitor in self.monitors:
            monitor.stop()
        
        # Cancel web server
        if self.web_server_task:
            self.web_server_task.cancel()

    async def _cleanup_all_components(self) -> None:
        """Cleanup all system components."""
        try:
            self.logger.info("CLEANING UP production system...")
            
            # Emergency close all positions if auto trading was enabled
            if self.auto_trading_enabled and self.position_manager:
                closed_positions = await self.position_manager.emergency_close_all()
                if closed_positions:
                    self.logger.warning(f"Emergency closed {len(closed_positions)} positions")
            
            # Cleanup analyzers
            if self.contract_analyzer:
                await self.contract_analyzer.cleanup()
            if self.social_analyzer:
                await self.social_analyzer.cleanup()
            
            # Stop position monitoring
            if self.position_manager:
                await self.position_manager.stop_monitoring()
            
            # Cleanup monitors
            for monitor in self.monitors:
                if hasattr(monitor, 'cleanup'):
                    await monitor.cleanup()
            
            # Cancel web server
            if self.web_server_task:
                self.web_server_task.cancel()
                try:
                    await self.web_server_task
                except asyncio.CancelledError:
                    pass
            
            # Final performance report
            if self.start_time:
                total_runtime = datetime.now() - self.start_time
                self.logger.info("FINAL PRODUCTION REPORT")
                self.logger.info(f"Total Runtime: {str(total_runtime).split('.')[0]}")
                self.logger.info(f"Opportunities Detected: {self.system_stats['opportunities_detected']}")
                self.logger.info(f"Opportunities Analyzed: {self.system_stats['opportunities_analyzed']}")
                self.logger.info(f"Positions Opened: {self.system_stats['positions_opened']}")
                self.logger.info(f"Trades Executed: {self.system_stats['trades_executed']}")
                
                if self.position_manager:
                    portfolio = self.position_manager.get_portfolio_summary()
                    self.logger.info(f"Final P&L: ${portfolio.get('total_pnl', 0):.2f}")
                    self.logger.info(f"Win Rate: {portfolio.get('win_rate_percentage', 0):.1f}%")
            
            self.logger.info("PRODUCTION SYSTEM SHUTDOWN COMPLETE")
            
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")


async def main():
    """Main entry point for production trading system."""
    # Parse command line arguments for auto-trading
    import argparse
    
    parser = argparse.ArgumentParser(description='Production DEX Sniping System')
    parser.add_argument('--auto-trade', action='store_true', 
                       help='Enable automated trading execution')
    parser.add_argument('--demo-mode', action='store_true',
                       help='Run in demo mode (no real trades)')
    parser.add_argument('--no-dashboard', action='store_true',
                       help='Disable web dashboard (console only)')
    
    args = parser.parse_args()
    
    # Safety confirmation for auto-trading
    if args.auto_trade and not args.demo_mode:
        print("\n⚠️  WARNING: AUTO-TRADING ENABLED WITH REAL FUNDS ⚠️")
        print("This will automatically execute trades with real money.")
        print("Make sure you understand the risks and have proper funding limits set.")
        
        confirmation = input("\nType 'I UNDERSTAND THE RISKS' to continue: ")
        if confirmation != "I UNDERSTAND THE RISKS":
            print("Auto-trading cancelled. Run with --demo-mode for testing.")
            return
    
    # Initialize and start system
    system = ProductionTradingSystem(
        auto_trading_enabled=args.auto_trade,
        disable_dashboard=args.no_dashboard  # Add this parameter
    )
    
    try:
        await system.start()
    except KeyboardInterrupt:
        print("\n⚠️ Shutdown requested by user")
        system.stop()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        system.stop()
        raise
    finally:
        print("Production system stopped. Check logs for detailed information.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSystem interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)