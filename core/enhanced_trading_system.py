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
        
        # Analysis statistics
        self.analysis_stats = {
            'total_analyzed': 0,
            'opportunities_found': 0,
            'high_confidence': 0,
            'by_chain': {},
            'by_source': {},
            'last_update': datetime.now()
        }
        
        # Opportunity tracking by chain
        self.opportunities_by_chain = {
            'ethereum': [],
            'base': [],
            'solana': [],
            'total': []
        }
        
        # Signal sources tracking for different opportunity origins
        self.signal_sources = {
            'monitors': ['ethereum_monitor', 'base_monitor', 'solana_monitor', 'jupiter_monitor', 'raydium_monitor'],
            'telegram': ['telegram_signals', 'telegram_channels'],
            'manual': ['dashboard', 'api'],
            'active_sources': set()
        }
        
        # Analyzers dictionary for opportunity analysis
        self.analyzers = {
            'contract': None,
            'social': None, 
            'trading_scorer': None
        }
        
        # Dashboard components
        self.dashboard_uvicorn_server = None
        self.dashboard_task = None

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
            self.execution_engine = ExecutionEngine(
                risk_manager=self.risk_manager,
                position_manager=self.position_manager
            )
            await self.execution_engine.initialize()
            
            # Initialize trading executor
            self.trading_executor = TradingExecutor(
                risk_manager=self.risk_manager,
                position_manager=self.position_manager,
                execution_engine=self.execution_engine,
                trading_mode=self.trading_mode
            )
            
            # Configure auto trading after initialization
            if hasattr(self.trading_executor, 'auto_execution_enabled'):
                self.trading_executor.auto_execution_enabled = self.auto_trading_enabled
            
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
            
            # Initialize Web3 connection for contract analysis
            w3 = None
            try:
                from web3 import Web3
                # Try multiple RPC endpoints for reliability
                rpc_urls = [
                    'https://eth.llamarpc.com',
                    'https://rpc.ankr.com/eth',
                    'https://ethereum-rpc.publicnode.com',
                    getattr(settings.networks, 'ethereum_rpc_url', 'https://eth.public-rpc.com')
                ]
                
                for rpc_url in rpc_urls:
                    try:
                        w3 = Web3(Web3.HTTPProvider(rpc_url))
                        if w3.is_connected():
                            self.logger.info(f"✅ Web3 connected via {rpc_url}")
                            break
                    except Exception as rpc_error:
                        self.logger.debug(f"RPC {rpc_url} failed: {rpc_error}")
                        continue
                
                if not w3 or not w3.is_connected():
                    self.logger.warning("❌ Could not establish Web3 connection")
                    w3 = None
                    
            except Exception as web3_error:
                self.logger.warning(f"Web3 initialization failed: {web3_error}")
                w3 = None
            
            # Initialize contract analyzer (only if Web3 is available)
            try:
                if w3:
                    self.contract_analyzer = ContractAnalyzer(w3)
                    await self.contract_analyzer.initialize()
                    self.analyzers['contract'] = self.contract_analyzer
                    self.logger.info("✅ Contract analyzer initialized")
                else:
                    self.contract_analyzer = None
                    self.analyzers['contract'] = None
                    self.logger.warning("⚠️ Contract analyzer disabled (no Web3 connection)")
            except Exception as e:
                self.logger.warning(f"Contract analyzer initialization failed: {e}")
                self.contract_analyzer = None
                self.analyzers['contract'] = None
            
            # Initialize social analyzer
            try:
                self.social_analyzer = SocialAnalyzer()
                await self.social_analyzer.initialize()
                self.analyzers['social'] = self.social_analyzer
                self.logger.info("✅ Social analyzer initialized")
            except Exception as e:
                self.logger.warning(f"Social analyzer initialization failed: {e}")
                self.social_analyzer = None
                self.analyzers['social'] = None
            
            # Initialize trading scorer
            try:
                self.trading_scorer = TradingScorer()
                self.analyzers['trading_scorer'] = self.trading_scorer
                # TradingScorer doesn't require async initialization
                self.logger.info("✅ Trading scorer initialized")
            except Exception as e:
                self.logger.warning(f"Trading scorer initialization failed: {e}")
                self.trading_scorer = None
                self.analyzers['trading_scorer'] = None
            
            # Count successful initializations
            analyzers = [self.contract_analyzer, self.social_analyzer, self.trading_scorer]
            active_count = len([a for a in analyzers if a is not None])
            total_count = len(analyzers)
            
            self.logger.info(f"✅ Analyzers initialized ({active_count}/{total_count} active)")
            
            if active_count == 0:
                self.logger.warning("⚠️ No analyzers available - running with limited functionality")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize analyzers: {e}")
            # Don't raise - continue without analyzers
            self.contract_analyzer = None
            self.social_analyzer = None
            self.trading_scorer = None
            self.logger.warning("⚠️ Running without analyzers - basic monitoring only")

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
        # Connect monitor callbacks to opportunity handler using the correct method names
        if self.new_token_monitor:
            self.new_token_monitor.add_callback(
                self.opportunity_handler.handle_opportunity
            )
        
        if self.base_chain_monitor:
            self.base_chain_monitor.add_callback(
                self.opportunity_handler.handle_opportunity
            )
        
        if self.solana_monitor:
            self.solana_monitor.add_callback(
                self.opportunity_handler.handle_opportunity
            )
        
        if self.jupiter_monitor:
            self.jupiter_monitor.add_callback(
                self.opportunity_handler.handle_opportunity
            )
        
        if self.raydium_monitor:
            self.raydium_monitor.add_callback(
                self.opportunity_handler.handle_opportunity
            )

    # Fix 1: Update the dashboard server to handle port conflicts
    # Add this to core/enhanced_trading_system.py in the _initialize_dashboard method

    async def _initialize_dashboard(self) -> None:
        """
        Initialize the web dashboard with port conflict handling.
        
        Sets up the web server and dashboard components for real-time monitoring.
        
        Raises:
            Exception: If dashboard initialization fails
        """
        try:
            self.logger.info("🔧 Initializing dashboard...")
            
            # Initialize dashboard server with trading system reference
            await dashboard_server.initialize(self)
            
            # Start the FastAPI server in background with port fallback
            import uvicorn
            
            # Import the FastAPI app
            from api.dashboard_server import app
            
            # Try multiple ports if 8000 is in use
            ports_to_try = [8000, 8001, 8002, 8003, 8004]
            server_started = False
            
            for port in ports_to_try:
                try:
                    self.logger.info(f"🌐 Attempting to start dashboard on port {port}...")
                    
                    # Create server config
                    config = uvicorn.Config(
                        app=app,
                        host="0.0.0.0",
                        port=port,
                        log_level="warning",  # Reduce uvicorn log noise
                        access_log=False
                    )
                    
                    # Create and store server instance
                    self.dashboard_uvicorn_server = uvicorn.Server(config)
                    
                    # Start server in background task
                    self.dashboard_task = asyncio.create_task(
                        self.dashboard_uvicorn_server.serve()
                    )
                    
                    # Give it a moment to start and check if it's successful
                    await asyncio.sleep(2)
                    
                    # Check if the task failed immediately (port conflict)
                    if self.dashboard_task.done():
                        exception = self.dashboard_task.exception()
                        if exception and "10048" in str(exception):  # Port in use error
                            self.logger.warning(f"❌ Port {port} is in use, trying next port...")
                            continue
                        else:
                            # Some other error
                            raise exception
                    else:
                        # Server started successfully
                        server_started = True
                        self.dashboard_port = port
                        self.logger.info(f"✅ Dashboard initialized on port {port}")
                        self.logger.info(f"   🌐 Access at: http://localhost:{port}")
                        break
                        
                except Exception as e:
                    self.logger.warning(f"Failed to start on port {port}: {e}")
                    if "10048" in str(e):  # Port in use
                        continue
                    else:
                        # Some other error, don't try more ports
                        break
            
            if not server_started:
                self.logger.warning("⚠️ Could not start dashboard on any port - continuing without dashboard")
                self.dashboard_uvicorn_server = None
                self.dashboard_task = None
                
        except Exception as e:
            self.logger.error(f"Failed to initialize dashboard: {e}")
            # Don't raise - continue without dashboard
            self.dashboard_uvicorn_server = None
            self.dashboard_task = None


    async def _create_realistic_test_opportunity(self) -> Optional[TradingOpportunity]:
        """
        Create a realistic test opportunity with varied data and proper address validation.
        
        Returns:
            Optional[TradingOpportunity]: Test opportunity or None if creation failed
        """
        try:
            # Define realistic test tokens
            test_tokens = [
                ("DOGE2", "DogeClassic", "ethereum"),
                ("PEPE", "PepeCoin", "ethereum"), 
                ("FLOKI", "Floki", "base"),
                ("SHIB2", "ShibaInu2", "base"),
                ("WIF", "dogwifhat", "solana"),
                ("BONK2", "Bonk2", "solana"),
                ("MEME", "MemeCoin", "ethereum"),
                ("CHAD", "ChadCoin", "base"),
                ("MOON", "MoonToken", "solana"),
                ("ROCKET", "RocketCoin", "ethereum"),
                ("DIAMOND", "DiamondHands", "base"),
                ("HODL", "HodlToken", "solana"),
                ("LAMBO", "LamboCoin", "ethereum"),
                ("APE2", "ApeToken2", "base"),
                ("CATS", "CatsCoin", "solana")
            ]
            
            # Select random token
            symbol, name, chain = random.choice(test_tokens)
            
            # Generate realistic addresses based on chain with proper validation
            if chain == "solana":
                # For Solana, create a proper mock address that passes validation
                # Solana addresses are typically 32-44 chars, but our validation expects Ethereum format
                # So we'll create Ethereum-style addresses for Solana tokens for testing
                test_address = f"0x{''.join(random.choices('0123456789abcdef', k=40))}"
            else:
                # Ethereum/Base addresses (standard format)
                test_address = f"0x{''.join(random.choices('0123456789abcdef', k=40))}"
            
            # Validate the address format before proceeding
            if not test_address or len(test_address) != 42 or not test_address.startswith('0x'):
                self.logger.warning(f"Generated invalid address format: {test_address}")
                # Fallback to a known good format
                test_address = f"0x{''.join(random.choices('0123456789abcdef', k=40))}"
            
            # Create token info with address validation
            try:
                token_info = TokenInfo(
                    address=test_address,
                    symbol=symbol,
                    name=name,
                    decimals=18,
                    total_supply=random.randint(100_000_000, 10_000_000_000)
                )
            except ValueError as e:
                self.logger.error(f"Failed to create TokenInfo with address {test_address}: {e}")
                return None
            
            # Generate realistic liquidity
            liquidity_usd = random.uniform(1000, 500000)
            
            # Create liquidity info
            dex_names = {
                "ethereum": ["Uniswap V2", "Uniswap V3", "SushiSwap"],
                "base": ["BaseSwap", "Uniswap V3", "PancakeSwap"],
                "solana": ["Raydium", "Orca", "Jupiter"]
            }
            
            liquidity_info = LiquidityInfo(
                pair_address=test_address,
                dex_name=random.choice(dex_names[chain]),
                token0=test_address,
                token1="0x0000000000000000000000000000000000000000" if chain != "solana" else "0x" + "1" * 40,  # Use valid format for Solana too
                reserve0=float(liquidity_usd / 2),
                reserve1=float(liquidity_usd / 2),
                liquidity_usd=liquidity_usd,
                created_at=datetime.now() - timedelta(minutes=random.randint(1, 60)),
                block_number=random.randint(18000000, 19000000)
            )
            
            # Create contract analysis
            contract_analysis = ContractAnalysis(
                is_honeypot=random.choice([True, False]),
                is_mintable=random.choice([True, False]),
                is_pausable=random.choice([True, False]),
                has_blacklist=random.choice([True, False]),
                ownership_renounced=random.choice([True, False]),
                liquidity_locked=random.choice([True, False]),
                lock_duration=random.randint(30, 365) * 24 * 3600 if random.choice([True, False]) else None,
                risk_score=random.uniform(0.1, 0.9),
                risk_level=random.choice(list(RiskLevel)),
                analysis_notes=[
                    random.choice([
                        "Standard ERC-20 contract",
                        "Custom token with additional features",
                        "Fork of popular token contract",
                        "Verified contract on blockchain explorer",
                        "High transaction volume detected"
                    ])
                ]
            )
            
            # Create social metrics
            social_metrics = SocialMetrics(
                twitter_followers=random.randint(100, 50000) if random.choice([True, False]) else None,
                telegram_members=random.randint(50, 10000) if random.choice([True, False]) else None,
                discord_members=random.randint(20, 5000) if random.choice([True, False]) else None,
                reddit_subscribers=random.randint(10, 2000) if random.choice([True, False]) else None,
                website_url=f"https://{symbol.lower()}.com" if random.choice([True, False]) else None,
                social_score=random.uniform(0.1, 1.0),
                sentiment_score=random.uniform(-0.5, 0.8)
            )
            
            # Create realistic metadata
            confidence_levels = ['LOW', 'MEDIUM', 'HIGH']
            actions = ['BUY', 'MONITOR', 'HOLD', 'AVOID']
            risk_levels = ['low', 'medium', 'high', 'critical']
            
            metadata = {
                'chain': chain,
                'source': 'test_generator',
                'is_test': True,
                'recommendation': {
                    'action': random.choice(actions),
                    'confidence': random.choice(confidence_levels),
                    'reasoning': random.choice([
                        'Strong social metrics and community',
                        'High liquidity and trading volume',
                        'Verified contract with good tokenomics',
                        'Trending on social media platforms',
                        'Low risk score with locked liquidity',
                        'Active development team'
                    ])
                },
                'trading_score': {
                    'overall_score': random.uniform(0.2, 0.95),
                    'risk_score': random.uniform(0.1, 0.8),
                    'liquidity_score': random.uniform(0.3, 1.0),
                    'volatility_score': random.uniform(0.1, 0.9),
                    'social_score': social_metrics.social_score,
                    'technical_score': random.uniform(0.2, 0.8)
                },
                'risk_level': random.choice(risk_levels),
                'analysis_timestamp': datetime.now().isoformat(),
                'market_cap_usd': liquidity_usd * random.uniform(2, 50),
                'volume_24h_usd': liquidity_usd * random.uniform(0.1, 5),
                'price_change_24h': random.uniform(-50, 200),
                'holder_count': random.randint(100, 10000),
                'contract_verified': random.choice([True, False])
            }
            
            # Create trading opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=contract_analysis,
                social_metrics=social_metrics,
                detected_at=datetime.now(),
                metadata=metadata
            )
            
            # Set additional attributes
            opportunity.chain = chain
            opportunity.confidence_score = metadata['trading_score']['overall_score']
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Failed to create test opportunity: {e}")
            return None












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
            if not self.disable_dashboard:
                try:
                    if self.dashboard_uvicorn_server:
                        self.dashboard_uvicorn_server.should_exit = True
                    if self.dashboard_task and not self.dashboard_task.done():
                        self.dashboard_task.cancel()
                        try:
                            await self.dashboard_task
                        except asyncio.CancelledError:
                            pass
                    await dashboard_server.stop()
                    self.logger.info("✅ Dashboard stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping dashboard: {e}")
            
            # Stop telegram components
            if self.telegram_manager:
                try:
                    await self.telegram_manager.shutdown()
                except Exception as e:
                    self.logger.error(f"Error stopping telegram manager: {e}")
            
            # Cleanup any remaining async sessions
            await self._cleanup_async_sessions()
            
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

    async def _cleanup_async_sessions(self) -> None:
        """
        Cleanup any remaining aiohttp sessions to prevent warnings.
        
        Ensures all HTTP sessions are properly closed during shutdown.
        """
        try:
            self.logger.debug("🧹 Cleaning up HTTP sessions...")
            
            # Close sessions in analyzers
            analyzers = [self.contract_analyzer, self.social_analyzer]
            for analyzer in analyzers:
                if analyzer and hasattr(analyzer, 'session') and analyzer.session:
                    try:
                        if not analyzer.session.closed:
                            await analyzer.session.close()
                    except Exception:
                        pass
            
            # Close sessions in monitors
            monitors = [
                self.new_token_monitor,
                self.base_chain_monitor, 
                self.solana_monitor,
                self.jupiter_monitor,
                self.raydium_monitor
            ]
            
            for monitor in monitors:
                if monitor and hasattr(monitor, 'session') and monitor.session:
                    try:
                        if not monitor.session.closed:
                            await monitor.session.close()
                    except Exception:
                        pass
            
            # Give time for cleanup to complete
            await asyncio.sleep(0.1)
            
            # Force garbage collection
            import gc
            gc.collect()
            
            self.logger.debug("✅ HTTP session cleanup completed")
            
        except Exception as e:
            self.logger.debug(f"Session cleanup error (non-critical): {e}")

    async def run_with_signal_handling(self) -> None:
        """
        Run the trading system with proper signal handling.
        
        This method provides the main entry point for running the system
        with graceful shutdown on Ctrl+C and other signals.
        """
        import signal
        
        try:
            # Set up signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                signal_name = signal.Signals(signum).name
                self.logger.info(f"🛑 Received {signal_name} signal, initiating shutdown...")
                self.shutdown_requested = True
                
                # Create shutdown task if we're in an event loop
                try:
                    loop = asyncio.get_running_loop()
                    if not loop.is_closed():
                        loop.create_task(self.shutdown())
                except RuntimeError:
                    self.logger.warning("No event loop running, forcing exit...")
                    import sys
                    sys.exit(0)
            
            # Register signal handlers
            signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
            signal.signal(signal.SIGTERM, signal_handler)  # Termination request
            
            if sys.platform != "win32":
                # Unix-specific signals
                signal.signal(signal.SIGHUP, signal_handler)   # Hangup
                signal.signal(signal.SIGQUIT, signal_handler)  # Quit
            
            self.logger.info("✅ Signal handlers registered (Ctrl+C will work gracefully)")
            
            # Initialize the system
            await self.initialize()
            
            # Send startup notification
            if self.telegram_manager.notifications_enabled:
                await self.telegram_manager.send_system_startup()
            
            # Start all monitors
            self.logger.info("🚀 Starting all monitoring systems...")
            self.running = True
            
            monitor_tasks = []
            
            # Start monitors if they exist
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
                        task = asyncio.create_task(monitor.start())
                        monitor_tasks.append(task)
                        self.logger.info(f"✅ {monitor.__class__.__name__} started")
                    except Exception as e:
                        self.logger.error(f"Failed to start {monitor.__class__.__name__}: {e}")
            
            # Start system monitoring
            if self.system_monitoring:
                try:
                    monitoring_task = asyncio.create_task(self.system_monitoring.start())
                    monitor_tasks.append(monitoring_task)
                    self.logger.info("✅ System monitoring started")
                except Exception as e:
                    self.logger.error(f"Failed to start system monitoring: {e}")
            
            # Start dashboard if enabled
            if not self.disable_dashboard:
                try:
                    # Dashboard server doesn't have start() method, it's initialized in _initialize_dashboard
                    # Just log that it's available
                    self.logger.info("✅ Dashboard server available at http://localhost:8000")
                except Exception as e:
                    self.logger.error(f"Dashboard server error: {e}")
            
            self.logger.info(f"🎯 System running with {len(monitor_tasks)} active components")
            self.logger.info("💡 Press Ctrl+C to stop the system gracefully")
            
            # Main system loop
            try:
                while self.running and not self.shutdown_requested:
                    await asyncio.sleep(1)
                    
                    # Check if any critical tasks have failed
                    failed_tasks = [task for task in monitor_tasks if task.done() and task.exception()]
                    if failed_tasks:
                        self.logger.warning(f"Detected {len(failed_tasks)} failed tasks")
                        for task in failed_tasks:
                            try:
                                self.logger.error(f"Task failed: {task.exception()}")
                            except Exception:
                                pass
                
                self.logger.info("🛑 Main loop stopping...")
                
            except KeyboardInterrupt:
                self.logger.info("🛑 KeyboardInterrupt received")
            
            # Cancel all monitor tasks
            self.logger.info("Stopping all monitor tasks...")
            for task in monitor_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete cancellation
            if monitor_tasks:
                await asyncio.gather(*monitor_tasks, return_exceptions=True)
            
            self.logger.info("✅ All monitor tasks stopped")
            
        except Exception as e:
            self.logger.error(f"💥 Error in main run loop: {e}")
            raise
        finally:
            # Ensure cleanup happens
            try:
                await self.shutdown()
            except Exception as e:
                self.logger.error(f"Error during final shutdown: {e}")

    async def start(self) -> None:
        """
        Alternative start method for simpler usage.
        
        This is an alias for run_with_signal_handling for compatibility.
        """
        await self.run_with_signal_handling()

    def update_analysis_stats(self, opportunity) -> None:
        """
        Update analysis statistics for tracking.
        
        Args:
            opportunity: The trading opportunity being processed
        """
        try:
            # Update basic stats
            self.analysis_stats['total_analyzed'] += 1
            self.analysis_stats['opportunities_found'] += 1
            self.analysis_stats['last_update'] = datetime.now()
            
            # Track by chain
            chain = getattr(opportunity, 'chain', 'unknown')
            if hasattr(opportunity, 'metadata') and opportunity.metadata:
                chain = opportunity.metadata.get('chain', chain)
            
            if chain not in self.analysis_stats['by_chain']:
                self.analysis_stats['by_chain'][chain] = 0
            self.analysis_stats['by_chain'][chain] += 1
            
            # Track by source
            source = getattr(opportunity, 'source', 'unknown')
            if hasattr(opportunity, 'metadata') and opportunity.metadata:
                source = opportunity.metadata.get('source', source)
            
            if source not in self.analysis_stats['by_source']:
                self.analysis_stats['by_source'][source] = 0
            self.analysis_stats['by_source'][source] += 1
            
            # Track high confidence opportunities
            confidence_score = 0
            if hasattr(opportunity, 'confidence_score'):
                confidence_score = float(opportunity.confidence_score)
            elif hasattr(opportunity, 'metadata') and opportunity.metadata:
                confidence_score = opportunity.metadata.get('confidence_score', 0)
            
            if confidence_score >= 80:
                self.analysis_stats['high_confidence'] += 1
                
        except Exception as e:
            self.logger.debug(f"Error updating analysis stats: {e}")

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