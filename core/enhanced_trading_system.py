#!/usr/bin/env python3
"""
Enhanced multi-chain DEX sniping system core functionality.
Main system class with initialization and component management.

File: core/enhanced_trading_system.py
Class: EnhancedTradingSystem
Methods: Core system management and initialization
"""

import asyncio
import sys
import os
import signal
import random
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import logger_manager
from models.token import TradingOpportunity, RiskLevel

# Core monitoring and analysis
from monitors.new_token_monitor import NewTokenMonitor
from monitors.base_chain_monitor import BaseChainMonitor  
from monitors.solana_monitor import SolanaMonitor
from monitors.jupiter_solana_monitor import JupiterSolanaMonitor
from monitors.raydium_monitor import RaydiumMonitor
from analyzers.contract_analyzer import ContractAnalyzer
from analyzers.social_analyzer import SocialAnalyzer
from analyzers.trading_scorer import TradingScorer

# Enhanced trading system
from trading.risk_manager import EnhancedRiskManager, PortfolioLimits, MarketCondition
from trading.position_manager import PositionManager, Position, PositionStatus
from trading.execution_engine import ExecutionEngine
from trading.trading_executor import TradingExecutor, TradingMode, ExecutionDecision

# Dashboard integration
from api.dashboard_server import app
from api.dashboard_core import dashboard_server

# Configuration
from config.chains import multichain_settings, ChainType
from config.settings import settings

# Import handlers from other core modules
from core.opportunity_handler import OpportunityHandler
from core.system_monitoring import SystemMonitoring
from core.telegram_manager import TelegramManager

# Telegram integration
try:
    from integrations.telegram_integration import telegram_integration
    from notifications.telegram_notifier import AlertPriority
    TELEGRAM_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Telegram integration not available: {e}")
    TELEGRAM_AVAILABLE = False

# Telegram signal integration
try:
    from integrations.telegram_signal_integration import telegram_signal_integration
    TELEGRAM_SIGNALS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Telegram signal integration not available: {e}")
    TELEGRAM_SIGNALS_AVAILABLE = False


class EnhancedTradingSystem:
    """
    Enhanced multi-chain DEX sniping system with automated trading execution and Telegram notifications.
    
    Features:
    - Multi-chain monitoring (Ethereum, Base, Solana)
    - Comprehensive risk assessment and position sizing
    - Automated trading execution with risk management
    - Real-time dashboard with performance tracking
    - Telegram notifications for all events
    - Advanced analytics and reporting
    """

    def __init__(
        self, 
        auto_trading_enabled: bool = False,
        trading_mode: TradingMode = TradingMode.PAPER_ONLY,
        disable_dashboard: bool = False,
        disable_telegram: bool = False,
        enable_telegram_signals: bool = False
    ) -> None:
        """
        Initialize the enhanced trading system.
        
        Args:
            auto_trading_enabled: Enable automated trade execution
            trading_mode: Trading execution mode
            disable_dashboard: Disable web dashboard
            disable_telegram: Disable Telegram notifications
            enable_telegram_signals: Enable Telegram channel monitoring
        """
        self.logger = logger_manager.get_logger("EnhancedTradingSystem")
        self.auto_trading_enabled = auto_trading_enabled
        self.trading_mode = trading_mode
        self.disable_dashboard = disable_dashboard
        self.disable_telegram = disable_telegram
        self.enable_telegram_signals = enable_telegram_signals
        
        # System state
        self.is_running = False
        self.start_time = datetime.now()
        self._shutdown_event: Optional[asyncio.Event] = None
        
        # Core components
        self.monitors: List[Any] = []
        self.analyzers: Dict[str, Any] = {}
        
        # Enhanced trading components
        self.risk_manager: Optional[EnhancedRiskManager] = None
        self.position_manager: Optional[PositionManager] = None
        self.execution_engine: Optional[ExecutionEngine] = None
        self.trading_executor: Optional[TradingExecutor] = None
        
        # Dashboard
        self.dashboard_server = None
        self.web_server_task = None
        
        # Component handlers
        self.opportunity_handler = OpportunityHandler(self)
        self.system_monitoring = SystemMonitoring(self)
        self.telegram_manager = TelegramManager(self)
        
        # Performance tracking
        self.analysis_stats = {
            "total_analyzed": 0,
            "high_confidence": 0,
            "trades_executed": 0,
            "successful_trades": 0,
            "total_pnl": Decimal('0'),
            "opportunities_found": 0,
            "recommendations": {
                "BUY": 0,
                "HOLD": 0,
                "SELL": 0,
                "AVOID": 0
            }
        }
        
        # Chain-specific tracking
        self.opportunities_by_chain = {
            "ethereum": 0,
            "base": 0,
            "solana": 0
        }
        
        # Trading performance
        self.execution_metrics = {
            "opportunities_assessed": 0,
            "trades_approved": 0,
            "trades_rejected": 0,
            "average_risk_score": 0.0,
            "average_confidence": 0.0,
            "position_count": 0,
            "daily_pnl": 0.0
        }
        
        # Signal source tracking
        self.signal_sources = {}

    def setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for graceful shutdown.
        
        This enables Ctrl+C and other termination signals to properly
        shut down the system instead of hanging.
        """
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            signal_name = signal.Signals(signum).name
            self.logger.info(f"🛑 Received {signal_name} signal, initiating graceful shutdown...")
            
            # Set a flag to stop the main loop
            if hasattr(self, '_shutdown_event') and self._shutdown_event:
                self._shutdown_event.set()
            
            # If we're in an event loop, create a task to shutdown
            try:
                loop = asyncio.get_running_loop()
                if not loop.is_closed():
                    loop.create_task(self._graceful_shutdown())
            except RuntimeError:
                # No event loop running, force exit
                self.logger.warning("No event loop running, forcing exit...")
                sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination request
        
        if sys.platform != "win32":
            # Unix-specific signals
            signal.signal(signal.SIGHUP, signal_handler)   # Hangup
            signal.signal(signal.SIGQUIT, signal_handler)  # Quit
        
        self.logger.info("✅ Signal handlers registered (Ctrl+C will now work)")

    async def _graceful_shutdown(self) -> None:
        """
        Perform graceful shutdown of the system.
        
        This method ensures all components are properly stopped and
        resources are cleaned up before exit.
        """
        try:
            self.logger.info("🔄 Starting graceful shutdown sequence...")
            
            # Send shutdown notification via Telegram manager
            await self.telegram_manager.send_shutdown_notification()
            
            # Stop all monitors first
            self.logger.info("Stopping monitors...")
            for monitor in self.monitors:
                try:
                    if hasattr(monitor, 'stop'):
                        monitor.stop()
                    self.logger.info(f"✅ {monitor.__class__.__name__} stopped")
                except Exception as e:
                    self.logger.warning(f"Error stopping {monitor.__class__.__name__}: {e}")
            
            # Stop trading components
            if hasattr(self, 'trading_executor') and self.trading_executor:
                try:
                    if hasattr(self.trading_executor, 'stop'):
                        self.trading_executor.stop()
                    self.logger.info("✅ Trading executor stopped")
                except Exception as e:
                    self.logger.warning(f"Error stopping trading executor: {e}")
            
            # Cleanup all resources
            await self.cleanup()
            
            self.logger.info("✅ Graceful shutdown completed")
            
            # Force exit after cleanup
            sys.exit(0)
            
        except Exception as e:
            self.logger.error(f"💥 Error during graceful shutdown: {e}")
            # Force exit even if cleanup fails
            sys.exit(1)

    def create_shutdown_event(self) -> None:
        """Create shutdown event for clean termination."""
        self._shutdown_event = asyncio.Event()

    async def run_with_signal_handling(self) -> None:
        """
        Run the trading system with proper signal handling.
        
        This method replaces the regular run() method and includes
        signal handling for graceful shutdown.
        """
        try:
            # Setup signal handlers
            self.setup_signal_handlers()
            
            # Create shutdown event
            self.create_shutdown_event()
            
            # Initialize the system
            await self.initialize()
            
            # Send startup notifications
            await self.telegram_manager.send_startup_notifications()
            
            # Start all monitors
            self.logger.info("🚀 Starting all monitors...")
            monitor_tasks = []
            
            for monitor in self.monitors:
                try:
                    if hasattr(monitor, 'start'):
                        task = asyncio.create_task(monitor.start())
                        monitor_tasks.append(task)
                        self.logger.info(f"✅ {monitor.__class__.__name__} started")
                except Exception as e:
                    self.logger.error(f"Failed to start {monitor.__class__.__name__}: {e}")
            
            # Start Telegram signal monitoring if enabled
            if self.enable_telegram_signals and self.telegram_manager.signals_enabled:
                try:
                    signal_task = asyncio.create_task(self.telegram_manager.start_signal_monitoring())
                    monitor_tasks.append(signal_task)
                    self.logger.info("✅ Telegram signal monitoring started")
                except Exception as e:
                    self.logger.error(f"Failed to start Telegram signal monitoring: {e}")
            
            # Start system monitoring loop
            monitoring_task = asyncio.create_task(self.system_monitoring.monitoring_loop())
            monitor_tasks.append(monitoring_task)
            
            self.logger.info(f"🎯 All {len(monitor_tasks)} tasks started successfully")
            self.logger.info("💡 Press Ctrl+C to stop the system gracefully")
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
            self.logger.info("🛑 Shutdown signal received, stopping...")
            
            # Cancel all monitor tasks
            for task in monitor_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if monitor_tasks:
                await asyncio.gather(*monitor_tasks, return_exceptions=True)
            
            self.logger.info("✅ All monitors stopped")
            
        except KeyboardInterrupt:
            self.logger.info("🛑 KeyboardInterrupt received, shutting down...")
            await self._graceful_shutdown()
        except Exception as e:
            self.logger.error(f"💥 Error in main run loop: {e}")
            await self._graceful_shutdown()

    async def initialize(self) -> None:
        """Initialize all system components."""
        try:
            self.logger.info("🚀 Initializing Enhanced Trading System")
            
            # Initialize Telegram integration first
            await self.telegram_manager.initialize()
            
            # Initialize trading components
            await self._initialize_trading_system()
            
            # Initialize analyzers
            await self._initialize_analyzers()
            
            # Initialize monitors
            await self._initialize_monitors()
            
            # Initialize dashboard if enabled
            if not self.disable_dashboard:
                await self._initialize_dashboard()
            
            self.logger.info("✅ Enhanced Trading System initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Enhanced Trading System: {e}")
            
            # Send error notification
            await self.telegram_manager.send_initialization_error(str(e))
            
            raise

    async def _initialize_trading_system(self) -> None:
        """Initialize the trading execution system."""
        try:
            self.logger.info("Initializing trading execution system...")
            
            # Create portfolio limits based on trading mode
            if self.trading_mode == TradingMode.LIVE_TRADING:
                # Conservative limits for live trading
                portfolio_limits = PortfolioLimits(
                    max_total_exposure_usd=500.0,
                    max_single_position_usd=50.0,
                    max_daily_loss_usd=100.0,
                    max_positions_per_chain=3,
                    max_total_positions=8,
                    max_trades_per_hour=5,
                    max_trades_per_day=20
                )
            else:
                # More aggressive limits for paper trading
                portfolio_limits = PortfolioLimits(
                    max_total_exposure_usd=2000.0,
                    max_single_position_usd=200.0,
                    max_daily_loss_usd=400.0,
                    max_positions_per_chain=5,
                    max_total_positions=15,
                    max_trades_per_hour=10,
                    max_trades_per_day=50
                )
            
            # Initialize risk manager
            self.risk_manager = EnhancedRiskManager(portfolio_limits)
            
            # Initialize position manager
            self.position_manager = PositionManager()
            await self.position_manager.initialize()
            
            # Initialize execution engine
            self.execution_engine = ExecutionEngine(self.risk_manager, self.position_manager)
            await self.execution_engine.initialize()
            
            # Initialize trading executor
            self.trading_executor = TradingExecutor(
                risk_manager=self.risk_manager,
                position_manager=self.position_manager,
                execution_engine=self.execution_engine,
                trading_mode=self.trading_mode
            )
            
            # Add trading alerts callback
            self.trading_executor.add_alert_callback(self._handle_trading_alert)
            
            await self.trading_executor.initialize()
            
            # Log trading configuration
            self.logger.info(f"Trading Mode: {self.trading_mode.value}")
            self.logger.info(f"Auto Trading: {'ENABLED' if self.auto_trading_enabled else 'DISABLED'}")
            self.logger.info(f"Max Exposure: ${portfolio_limits.max_total_exposure_usd}")
            self.logger.info(f"Max Position: ${portfolio_limits.max_single_position_usd}")
            
            if self.trading_mode == TradingMode.LIVE_TRADING:
                self.logger.warning("⚠️ LIVE TRADING MODE - Real funds at risk!")
                
                # Send live trading warning via Telegram
                await self.telegram_manager.send_live_trading_warning(portfolio_limits)
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading system: {e}")
            raise

    async def _initialize_analyzers(self) -> None:
        """Initialize analysis components."""
        try:
            self.logger.info("Initializing analyzers...")
            
            # Initialize Web3 connection for analyzers
            from web3 import Web3
            try:
                # Try to connect to a public RPC (for analysis only)
                w3 = Web3(Web3.HTTPProvider('https://eth.llamarpc.com'))
                if not w3.is_connected():
                    # Fallback to another public RPC
                    w3 = Web3(Web3.HTTPProvider('https://rpc.ankr.com/eth'))
                
                self.logger.info(f"Web3 connected: {w3.is_connected()}")
            except Exception as e:
                self.logger.warning(f"Web3 connection failed: {e}, using mock connection")
                w3 = None
            
            # Contract analyzer for security assessment
            try:
                if w3:
                    self.analyzers['contract'] = ContractAnalyzer(w3)
                    await self.analyzers['contract'].initialize()
                else:
                    self.logger.warning("Skipping ContractAnalyzer - no Web3 connection")
            except Exception as e:
                self.logger.warning(f"ContractAnalyzer initialization failed: {e}")
                self.analyzers['contract'] = None
            
            # Social analyzer for sentiment analysis
            try:
                self.analyzers['social'] = SocialAnalyzer()
                await self.analyzers['social'].initialize()
            except Exception as e:
                self.logger.warning(f"SocialAnalyzer initialization failed: {e}")
                self.analyzers['social'] = None
            
            # Trading scorer for opportunity ranking
            try:
                self.analyzers['trading_scorer'] = TradingScorer()
                self.logger.info("✅ TradingScorer initialized")
            except Exception as e:
                self.logger.warning(f"TradingScorer initialization failed: {e}")
                self.analyzers['trading_scorer'] = None
            
            # Count successful initializations
            active_analyzers = len([a for a in self.analyzers.values() if a is not None])
            self.logger.info(f"✅ {active_analyzers}/{len(self.analyzers)} analyzers initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize analyzers: {e}")
            # Don't raise - continue without analyzers
            self.analyzers = {'contract': None, 'social': None, 'trading_scorer': None}

    async def _initialize_monitors(self) -> None:
        """Initialize all blockchain monitors."""
        try:
            self.logger.info("🔍 Initializing blockchain monitors...")
            
            # Ethereum monitor
            try:
                eth_monitor = NewTokenMonitor(
                    check_interval=5.0,
                    chain="ethereum",
                    analyzer=self.analyzers.get('contract'),
                    scorer=self.analyzers.get('trading_scorer'),
                    auto_trading=self.auto_trading_enabled
                )
                eth_monitor.add_callback(self.opportunity_handler.handle_opportunity)
                
                if await eth_monitor.initialize():
                    self.monitors.append(eth_monitor)
                    self.logger.info("✅ Ethereum monitor initialized")
                else:
                    self.logger.warning("⚠️  Ethereum monitor initialization failed")
                    
            except Exception as e:
                self.logger.warning(f"Ethereum monitor failed: {e}")
            
            # Base chain monitor
            try:
                base_monitor = BaseChainMonitor(
                    check_interval=8.0,
                    analyzer=self.analyzers.get('contract'),
                    scorer=self.analyzers.get('trading_scorer'),
                    auto_trading=self.auto_trading_enabled
                )
                base_monitor.add_callback(self.opportunity_handler.handle_opportunity)
                
                if await base_monitor.initialize():
                    self.monitors.append(base_monitor)
                    self.logger.info("✅ Base monitor initialized")
                else:
                    self.logger.warning("⚠️  Base monitor initialization failed")
                    
            except Exception as e:
                self.logger.warning(f"Base monitor failed: {e}")
            
            # Solana monitor
            try:
                sol_monitor = SolanaMonitor(check_interval=10.0)
                sol_monitor.add_callback(self.opportunity_handler.handle_opportunity)
                
                if await sol_monitor.initialize():
                    self.monitors.append(sol_monitor)
                    self.logger.info("✅ Solana monitor initialized")
                else:
                    self.logger.warning("❌ Solana monitor initialization failed")
                    
            except Exception as e:
                self.logger.warning(f"Solana monitor failed: {e}")
            
            # Raydium DEX monitor
            try:
                raydium_monitor = RaydiumMonitor(check_interval=10.0)
                raydium_monitor.add_callback(self.opportunity_handler.handle_raydium_opportunity)
                
                if await raydium_monitor.initialize():
                    self.monitors.append(raydium_monitor)
                    self.logger.info("✅ Raydium DEX monitor initialized")
                else:
                    self.logger.warning("❌ Raydium monitor initialization failed")
                    
            except Exception as e:
                self.logger.warning(f"Raydium monitor failed: {e}")
            
            # Jupiter monitor
            try:
                jupiter_monitor = JupiterSolanaMonitor()
                jupiter_monitor.add_callback(self.opportunity_handler.handle_opportunity)
                self.monitors.append(jupiter_monitor)
                self.logger.info("✅ Jupiter monitor initialized")
            except Exception as e:
                self.logger.warning(f"Jupiter monitor failed: {e}")
            
            # Monitor initialization summary
            active_monitors = len(self.monitors)
            self.logger.info(f"🎯 Monitor initialization complete: {active_monitors} active monitors")
            
            if active_monitors == 0:
                self.logger.error("❌ No monitors initialized successfully!")
                await self.telegram_manager.send_critical_error("No monitoring capabilities available")
                raise RuntimeError("No monitoring capabilities available")
            
            # Log monitor details
            for i, monitor in enumerate(self.monitors, 1):
                monitor_name = getattr(monitor, 'name', monitor.__class__.__name__)
                self.logger.info(f"   {i}. {monitor_name} - {getattr(monitor, 'chain', 'multi-chain')}")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize monitors: {e}")
            raise

    async def _initialize_dashboard(self) -> None:
        """Initialize web dashboard."""
        try:
            self.logger.info("Initializing dashboard...")
            
            # Set dashboard references to trading components
            dashboard_server.trading_executor = self.trading_executor
            dashboard_server.position_manager = self.position_manager
            dashboard_server.risk_manager = self.risk_manager
            
            # Initialize dashboard
            await dashboard_server.initialize()
            
            # Start web server
            import uvicorn
            
            async def run_server():
                config = uvicorn.Config(
                    app,
                    host="0.0.0.0",
                    port=8000,
                    log_level="info",
                    access_log=False
                )
                server = uvicorn.Server(config)
                await server.serve()
            
            self.web_server_task = asyncio.create_task(run_server())
            self.dashboard_server = dashboard_server
            
            self.logger.info("✅ Dashboard initialized at http://localhost:8000")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize dashboard: {e}")
            raise

    async def _handle_trading_alert(self, alert_data: Dict[str, Any]) -> None:
        """
        Handle trading alerts from the execution system.
        
        Args:
            alert_data: Alert information
        """
        try:
            # Delegate to telegram manager
            await self.telegram_manager.handle_trading_alert(alert_data)
            
            # Update local statistics
            alert_type = alert_data.get('type', 'UNKNOWN')
            
            if alert_type == 'TRADE_EXECUTED':
                self.analysis_stats["trades_executed"] += 1
                self.execution_metrics["position_count"] += 1
                
            elif alert_type.startswith('POSITION_CLOSED'):
                self.execution_metrics["position_count"] = max(0, self.execution_metrics["position_count"] - 1)
                
                position_data = alert_data.get('position')
                if position_data:
                    pnl = position_data.get('unrealized_pnl', 0)
                    if isinstance(pnl, (int, float, Decimal)):
                        self.analysis_stats["total_pnl"] += Decimal(str(pnl))
                        self.execution_metrics["daily_pnl"] += float(pnl)
                        
                        if pnl > 0:
                            self.analysis_stats["successful_trades"] += 1
            
            # Broadcast alert to dashboard
            if self.dashboard_server:
                await self.dashboard_server.broadcast_message({
                    "type": "trading_alert",
                    "data": alert_data
                })
                
        except Exception as e:
            self.logger.error(f"Error handling trading alert: {e}")

    def _get_uptime_hours(self) -> float:
        """Calculate system uptime in hours."""
        try:
            if hasattr(self, 'start_time'):
                uptime_seconds = (datetime.now() - self.start_time).total_seconds()
                return round(uptime_seconds / 3600, 1)
            return 0.0
        except:
            return 0.0

    async def cleanup(self) -> None:
        """Clean up all system resources."""
        try:
            self.logger.info("🧹 Starting Enhanced Trading System cleanup...")
            
            # Stop all monitors
            for monitor in self.monitors:
                try:
                    if hasattr(monitor, 'stop'):
                        monitor.stop()
                    if hasattr(monitor, 'cleanup'):
                        await monitor.cleanup()
                    self.logger.info(f"✅ {monitor.__class__.__name__} cleaned up")
                except Exception as e:
                    self.logger.warning(f"Error cleaning up {monitor.__class__.__name__}: {e}")
            
            # Stop trading components
            if self.trading_executor:
                try:
                    await self.trading_executor.cleanup()
                    self.logger.info("✅ Trading executor cleaned up")
                except Exception as e:
                    self.logger.warning(f"Error cleaning up trading executor: {e}")
            
            # Cleanup component handlers
            await self.telegram_manager.cleanup()
            
            # Clean up analyzers
            for name, analyzer in self.analyzers.items():
                try:
                    if analyzer and hasattr(analyzer, 'cleanup'):
                        await analyzer.cleanup()
                    self.logger.info(f"✅ {name} analyzer cleaned up")
                except Exception as e:
                    self.logger.warning(f"Error cleaning up {name} analyzer: {e}")
            
            self.logger.info("✅ Enhanced Trading System cleanup completed")
            
        except Exception as e:
            self.logger.error(f"💥 Error during system cleanup: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            'system': {
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                'status': 'running',
                'monitors_count': len(self.monitors),
                'analyzers_count': len([a for a in self.analyzers.values() if a is not None])
            },
            'analysis_stats': self.analysis_stats,
            'execution_metrics': self.execution_metrics,
            'opportunities_by_chain': self.opportunities_by_chain,
            'signal_sources': self.signal_sources,
            'telegram': self.telegram_manager.get_statistics()
        }