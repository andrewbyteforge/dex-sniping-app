#!/usr/bin/env python3
"""
Enhanced multi-chain DEX sniping system core functionality.
Main system class with initialization and component management.

File: core/enhanced_trading_system.py
Class: EnhancedTradingSystem
Methods: Core system management and initialization

UPDATE: Added missing _initialize_telegram_integration method for backward compatibility
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
            auto_trading_enabled: Enable automated trading execution
            trading_mode: Trading mode (paper, live, etc.)
            disable_dashboard: Disable web dashboard
            disable_telegram: Disable Telegram notifications
            enable_telegram_signals: Enable Telegram signal monitoring
        """
        self.logger = logger_manager.get_logger("EnhancedTradingSystem")
        
        # Store configuration
        self.auto_trading_enabled = auto_trading_enabled
        self.trading_mode = trading_mode
        self.disable_dashboard = disable_dashboard
        self.disable_telegram = disable_telegram
        self.enable_telegram_signals = enable_telegram_signals
        
        # Initialize component managers
        self.telegram_manager = TelegramManager(self)
        self.opportunity_handler = OpportunityHandler(self)
        self.system_monitoring = SystemMonitoring(self)
        
        # Trading components (initialized in _initialize_trading_system)
        self.risk_manager: Optional[EnhancedRiskManager] = None
        self.position_manager: Optional[PositionManager] = None
        self.execution_engine: Optional[ExecutionEngine] = None
        self.trading_executor: Optional[TradingExecutor] = None
        
        # Monitoring components (initialized in _initialize_monitors)
        self.new_token_monitor: Optional[NewTokenMonitor] = None
        self.base_chain_monitor: Optional[BaseChainMonitor] = None
        self.solana_monitor: Optional[SolanaMonitor] = None
        self.jupiter_monitor: Optional[JupiterSolanaMonitor] = None
        self.raydium_monitor: Optional[RaydiumMonitor] = None
        
        # Analysis components (initialized in _initialize_analyzers)
        self.contract_analyzer: Optional[ContractAnalyzer] = None
        self.social_analyzer: Optional[SocialAnalyzer] = None
        self.trading_scorer: Optional[TradingScorer] = None
        
        # System state
        self.running = False
        self.shutdown_requested = False
        self.components_initialized = {
            'telegram': False,
            'trading_system': False,
            'analyzers': False,
            'monitors': False,
            'dashboard': False
        }
        
        # Statistics tracking
        self.start_time: Optional[datetime] = None
        self.opportunities_processed = 0
        self.trades_executed = 0
        self.notifications_sent = 0

    async def initialize(self) -> None:
        """
        Initialize all system components.
        
        This is the main initialization method that should be called after instantiation.
        
        Raises:
            Exception: If any critical component fails to initialize
        """
        try:
            self.logger.info("🚀 Initializing Enhanced Trading System")
            
            # Initialize Telegram integration first
            await self.telegram_manager.initialize()
            self.components_initialized['telegram'] = True
            
            # Initialize trading components
            await self._initialize_trading_system()
            self.components_initialized['trading_system'] = True
            
            # Initialize analyzers
            await self._initialize_analyzers()
            self.components_initialized['analyzers'] = True
            
            # Initialize monitors
            await self._initialize_monitors()
            self.components_initialized['monitors'] = True
            
            # Initialize dashboard if enabled
            if not self.disable_dashboard:
                await self._initialize_dashboard()
                self.components_initialized['dashboard'] = True
            
            self.logger.info("✅ Enhanced Trading System initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Enhanced Trading System: {e}")
            
            # Send error notification if telegram is available
            if self.components_initialized.get('telegram', False):
                try:
                    await self.telegram_manager.send_initialization_error(str(e))
                except Exception as telegram_error:
                    self.logger.error(f"Failed to send error notification: {telegram_error}")
            
            raise

    async def _initialize_telegram_integration(self) -> None:
        """
        Initialize Telegram integration (backward compatibility method).
        
        This method provides backward compatibility for code that calls the old method name.
        It delegates to the telegram_manager.initialize() method.
        
        Note: This method is deprecated. Use telegram_manager.initialize() directly.
        """
        self.logger.warning("_initialize_telegram_integration is deprecated. Use telegram_manager.initialize() instead.")
        await self.telegram_manager.initialize()

    async def _initialize_trading_system(self) -> None:
        """
        Initialize the trading execution system.
        
        Sets up risk management, position tracking, and execution components.
        
        Raises:
            Exception: If trading system initialization fails
        """
        try:
            self.logger.info("🔧 Initializing trading system...")
            
            # Initialize risk manager
            portfolio_limits = PortfolioLimits(
                max_total_exposure_usd=getattr(settings, 'max_total_exposure_usd', 10000.0),
                max_single_position_usd=getattr(settings, 'max_single_position_usd', 1000.0),
                max_positions_per_chain=getattr(settings, 'max_positions_per_chain', 5),
                max_daily_loss_usd=getattr(settings, 'max_daily_loss_usd', 500.0),
                max_total_positions=getattr(settings, 'max_total_positions', 15),
                min_liquidity_usd=getattr(settings, 'min_liquidity_usd', 50000.0)
            )
            
            self.risk_manager = EnhancedRiskManager(portfolio_limits)
            
            # Initialize position manager
            self.position_manager = PositionManager()
            await self.position_manager.initialize()
            
            # Initialize execution engine
            self.execution_engine = ExecutionEngine()
            await self.execution_engine.initialize()
            
            # Initialize trading executor
            self.trading_executor = TradingExecutor(
                risk_manager=self.risk_manager,
                position_manager=self.position_manager,
                execution_engine=self.execution_engine,
                mode=self.trading_mode,
                auto_trading_enabled=self.auto_trading_enabled
            )
            
            self.logger.info("✅ Trading system initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading system: {e}")
            raise

    async def _initialize_analyzers(self) -> None:
        """
        Initialize analysis components.
        
        Sets up contract analysis, social sentiment analysis, and trading scoring.
        
        Raises:
            Exception: If analyzer initialization fails
        """
        try:
            self.logger.info("🔧 Initializing analyzers...")
            
            # Initialize contract analyzer
            self.contract_analyzer = ContractAnalyzer()
            await self.contract_analyzer.initialize()
            
            # Initialize social analyzer
            self.social_analyzer = SocialAnalyzer()
            await self.social_analyzer.initialize()
            
            # Initialize trading scorer
            self.trading_scorer = TradingScorer()
            await self.trading_scorer.initialize()
            
            self.logger.info("✅ Analyzers initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize analyzers: {e}")
            raise

    async def _initialize_monitors(self) -> None:
        """
        Initialize monitoring components for all supported chains.
        
        Sets up monitors for Ethereum, Base, and Solana chains.
        
        Raises:
            Exception: If monitor initialization fails
        """
        try:
            self.logger.info("🔧 Initializing monitors...")
            
            # Initialize Ethereum new token monitor
            self.new_token_monitor = NewTokenMonitor()
            await self.new_token_monitor.initialize()
            
            # Initialize Base chain monitor
            self.base_chain_monitor = BaseChainMonitor()
            await self.base_chain_monitor.initialize()
            
            # Initialize Solana monitor
            self.solana_monitor = SolanaMonitor()
            await self.solana_monitor.initialize()
            
            # Initialize Jupiter Solana monitor
            self.jupiter_monitor = JupiterSolanaMonitor()
            await self.jupiter_monitor.initialize()
            
            # Initialize Raydium monitor
            self.raydium_monitor = RaydiumMonitor()
            await self.raydium_monitor.initialize()
            
            # Set up opportunity callbacks
            await self._setup_opportunity_callbacks()
            
            self.logger.info("✅ Monitors initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize monitors: {e}")
            raise

    async def _setup_opportunity_callbacks(self) -> None:
        """Set up callbacks for opportunity detection from all monitors."""
        # Connect monitor callbacks to opportunity handler
        if self.new_token_monitor:
            self.new_token_monitor.add_opportunity_callback(
                self.opportunity_handler.handle_new_opportunity
            )
        
        if self.base_chain_monitor:
            self.base_chain_monitor.add_opportunity_callback(
                self.opportunity_handler.handle_new_opportunity
            )
        
        if self.solana_monitor:
            self.solana_monitor.add_opportunity_callback(
                self.opportunity_handler.handle_new_opportunity
            )
        
        if self.jupiter_monitor:
            self.jupiter_monitor.add_opportunity_callback(
                self.opportunity_handler.handle_new_opportunity
            )
        
        if self.raydium_monitor:
            self.raydium_monitor.add_opportunity_callback(
                self.opportunity_handler.handle_new_opportunity
            )

    async def _initialize_dashboard(self) -> None:
        """
        Initialize the web dashboard.
        
        Sets up the web server and dashboard components for real-time monitoring.
        
        Raises:
            Exception: If dashboard initialization fails
        """
        try:
            self.logger.info("🔧 Initializing dashboard...")
            
            # Initialize dashboard server
            await dashboard_server.initialize(self)
            
            self.logger.info("✅ Dashboard initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize dashboard: {e}")
            raise

    async def start(self) -> None:
        """
        Start the trading system main loop.
        
        Begins monitoring for opportunities and executing trades based on configuration.
        
        Raises:
            Exception: If system fails to start
        """
        try:
            if not all(self.components_initialized.values()):
                raise RuntimeError("System not fully initialized. Call initialize() first.")
            
            self.running = True
            self.start_time = datetime.now()
            
            self.logger.info("🎯 Starting Enhanced Trading System")
            
            # Send startup notification
            if self.telegram_manager.notifications_enabled:
                await self.telegram_manager.send_system_startup()
            
            # Start monitoring tasks
            tasks = []
            
            # Start monitors
            if self.new_token_monitor:
                tasks.append(asyncio.create_task(self.new_token_monitor.start()))
            
            if self.base_chain_monitor:
                tasks.append(asyncio.create_task(self.base_chain_monitor.start()))
            
            if self.solana_monitor:
                tasks.append(asyncio.create_task(self.solana_monitor.start()))
            
            if self.jupiter_monitor:
                tasks.append(asyncio.create_task(self.jupiter_monitor.start()))
            
            if self.raydium_monitor:
                tasks.append(asyncio.create_task(self.raydium_monitor.start()))
            
            # Start system monitoring
            tasks.append(asyncio.create_task(self.system_monitoring.start()))
            
            # Start dashboard if enabled
            if not self.disable_dashboard:
                tasks.append(asyncio.create_task(dashboard_server.start()))
            
            # Start Telegram signal monitoring if enabled
            if self.enable_telegram_signals and self.telegram_manager.signals_enabled:
                tasks.append(asyncio.create_task(self.telegram_manager.start_signal_monitoring()))
            
            # Wait for all tasks
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to start trading system: {e}")
            await self.shutdown()
            raise

    async def shutdown(self) -> None:
        """
        Gracefully shutdown the trading system.
        
        Stops all monitoring, closes positions if configured, and cleans up resources.
        """
        if self.shutdown_requested:
            return
        
        self.shutdown_requested = True
        self.running = False
        
        try:
            self.logger.info("🛑 Shutting down Enhanced Trading System")
            
            # Send shutdown notification
            if self.telegram_manager and self.telegram_manager.notifications_enabled:
                await self.telegram_manager.send_system_shutdown()
            
            # Stop monitors
            monitors = [
                self.new_token_monitor,
                self.base_chain_monitor,
                self.solana_monitor,
                self.jupiter_monitor,
                self.raydium_monitor
            ]
            
            for monitor in monitors:
                if monitor:
                    try:
                        await monitor.stop()
                    except Exception as e:
                        self.logger.error(f"Error stopping monitor {monitor.__class__.__name__}: {e}")
            
            # Stop system monitoring
            if self.system_monitoring:
                try:
                    await self.system_monitoring.stop()
                except Exception as e:
                    self.logger.error(f"Error stopping system monitoring: {e}")
            
            # Stop dashboard
            if not self.disable_dashboard and dashboard_server:
                await dashboard_server.stop()
            
            # Stop telegram components
            if self.telegram_manager:
                await self.telegram_manager.shutdown()
            
            # Close trading positions if configured
            if self.position_manager and settings.get('close_positions_on_shutdown', False):
                await self.position_manager.close_all_positions()
            
            self.logger.info("✅ System shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    async def generate_test_opportunities(self) -> None:
        """
        Generate test opportunities for dashboard and notification testing.
        
        Creates mock trading opportunities to test the system without live market data.
        """
        try:
            self.logger.info("🧪 Generating test opportunities...")
            
            # Generate test opportunities for each chain
            test_opportunities = await self._create_test_opportunities()
            
            # Process each test opportunity
            for opportunity in test_opportunities:
                await self.opportunity_handler.handle_new_opportunity(opportunity)
                await asyncio.sleep(2)  # Stagger for demonstration
            
            self.logger.info(f"✅ Generated {len(test_opportunities)} test opportunities")
            
        except Exception as e:
            self.logger.error(f"Failed to generate test opportunities: {e}")

    async def _create_test_opportunities(self) -> List[TradingOpportunity]:
        """Create a list of test trading opportunities."""
        from models.token import TokenInfo, LiquidityInfo, SocialMetrics, ContractAnalysis
        
        test_opportunities = []
        
        # Test Ethereum opportunity
        eth_opportunity = TradingOpportunity(
            token_info=TokenInfo(
                address="0x1234567890abcdef1234567890abcdef12345678",
                symbol="TESTETH",
                name="Test Ethereum Token",
                decimals=18,
                chain="ethereum"
            ),
            liquidity_info=LiquidityInfo(
                total_liquidity_usd=Decimal("150000"),
                liquidity_locked_percentage=85.5,
                largest_holder_percentage=12.3
            ),
            social_metrics=SocialMetrics(
                twitter_followers=15000,
                telegram_members=8500,
                reddit_members=2300
            ),
            contract_analysis=ContractAnalysis(
                is_verified=True,
                has_mint_function=False,
                has_blacklist=False,
                ownership_renounced=True
            ),
            risk_level=RiskLevel.MEDIUM,
            confidence_score=Decimal("78.5"),
            detected_at=datetime.now(),
            source="test_generator"
        )
        test_opportunities.append(eth_opportunity)
        
        # Test Solana opportunity  
        sol_opportunity = TradingOpportunity(
            token_info=TokenInfo(
                address="So11111111111111111111111111111111111111112",
                symbol="TESTSOL",
                name="Test Solana Token",
                decimals=9,
                chain="solana"
            ),
            liquidity_info=LiquidityInfo(
                total_liquidity_usd=Decimal("75000"),
                liquidity_locked_percentage=92.1,
                largest_holder_percentage=8.7
            ),
            social_metrics=SocialMetrics(
                twitter_followers=25000,
                telegram_members=12000,
                reddit_members=4500
            ),
            contract_analysis=ContractAnalysis(
                is_verified=True,
                has_mint_function=False,
                has_blacklist=False,
                ownership_renounced=True
            ),
            risk_level=RiskLevel.LOW,
            confidence_score=Decimal("85.2"),
            detected_at=datetime.now(),
            source="test_generator"
        )
        test_opportunities.append(sol_opportunity)
        
        return test_opportunities

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get current system status and statistics.
        
        Returns:
            Dictionary containing system status information
        """
        uptime = None
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "running": self.running,
            "uptime_seconds": uptime,
            "components_initialized": self.components_initialized,
            "auto_trading_enabled": self.auto_trading_enabled,
            "trading_mode": self.trading_mode.value if self.trading_mode else None,
            "telegram_notifications": not self.disable_telegram,
            "telegram_signals": self.enable_telegram_signals,
            "dashboard_enabled": not self.disable_dashboard,
            "opportunities_processed": self.opportunities_processed,
            "trades_executed": self.trades_executed,
            "notifications_sent": self.notifications_sent
        }