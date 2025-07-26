#!/usr/bin/env python3
"""
Enhanced main trading system with comprehensive automated execution.

Integrates monitoring, analysis, risk management, and automated trading
with real-time dashboard and performance tracking.
"""

import asyncio
import sys
import os
import argparse
import random
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger_manager
from models.token import TradingOpportunity, RiskLevel

# Core monitoring and analysis
from monitors.new_token_monitor import NewTokenMonitor
from monitors.base_chain_monitor import BaseChainMonitor  
from monitors.solana_monitor import SolanaMonitor
from monitors.jupiter_solana_monitor import JupiterSolanaMonitor
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


class EnhancedTradingSystem:
    """
    Enhanced multi-chain DEX sniping system with automated trading execution.
    
    Features:
    - Multi-chain monitoring (Ethereum, Base, Solana)
    - Comprehensive risk assessment and position sizing
    - Automated trading execution with risk management
    - Real-time dashboard with performance tracking
    - Advanced analytics and reporting
    """

    def __init__(
        self, 
        auto_trading_enabled: bool = False,
        trading_mode: TradingMode = TradingMode.PAPER_ONLY,
        disable_dashboard: bool = False
    ) -> None:
        """
        Initialize the enhanced trading system.
        
        Args:
            auto_trading_enabled: Enable automated trade execution
            trading_mode: Trading execution mode
            disable_dashboard: Disable web dashboard
        """
        self.logger = logger_manager.get_logger("EnhancedTradingSystem")
        self.auto_trading_enabled = auto_trading_enabled
        self.trading_mode = trading_mode
        self.disable_dashboard = disable_dashboard
        
        # System state
        self.is_running = False
        self.start_time = datetime.now()
        
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
        
        # Performance tracking
        self.analysis_stats = {
            "total_analyzed": 0,
            "high_confidence": 0,
            "trades_executed": 0,
            "successful_trades": 0,
            "total_pnl": Decimal('0'),
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

    async def initialize(self) -> None:
        """Initialize all system components."""
        try:
            self.logger.info("🚀 Initializing Enhanced Trading System")
            
            # Initialize trading components first
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
            raise

    async def _initialize_trading_system(self) -> None:
        """Initialize the trading execution system."""
        try:
            self.logger.info("Initializing trading execution system...")
            
            # Create portfolio limits based on trading mode
            if self.trading_mode == TradingMode.LIVE_TRADING:
                # Conservative limits for live trading
                portfolio_limits = PortfolioLimits(
                    max_total_exposure_usd=500.0,  # $500 max exposure
                    max_single_position_usd=50.0,  # $50 max per position
                    max_daily_loss_usd=100.0,      # $100 max daily loss
                    max_positions_per_chain=3,     # 3 positions per chain
                    max_total_positions=8,         # 8 total positions
                    max_trades_per_hour=5,         # 5 trades per hour
                    max_trades_per_day=20          # 20 trades per day
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
                # Create a mock Web3 instance for testing
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
                # TradingScorer doesn't need initialize method
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
        """Enhanced monitor initialization with better callback handling."""
        try:
            self.logger.info("Initializing blockchain monitors...")
            
            # Ethereum monitor
            try:
                eth_monitor = NewTokenMonitor()
                eth_monitor.add_callback(self._handle_opportunity)
                self.monitors.append(eth_monitor)
                self.logger.info("✅ Ethereum monitor initialized")
            except Exception as e:
                self.logger.warning(f"Ethereum monitor failed: {e}")
            
            # Base chain monitor
            try:
                base_monitor = BaseChainMonitor()
                base_monitor.add_callback(self._handle_opportunity)
                self.monitors.append(base_monitor)
                self.logger.info("✅ Base monitor initialized")
            except Exception as e:
                self.logger.warning(f"Base monitor failed: {e}")
            
            # Solana monitor with enhanced settings
            try:
                sol_monitor = SolanaMonitor(check_interval=10.0)  # Slower for stability
                sol_monitor.add_callback(self._handle_opportunity)
                
                # Set additional properties if available
                if hasattr(sol_monitor, 'set_scorer') and hasattr(self, 'analyzers'):
                    sol_monitor.set_scorer(self.analyzers.get('trading_scorer'))
                if hasattr(sol_monitor, 'set_auto_trading'):
                    sol_monitor.set_auto_trading(self.auto_trading_enabled)
                
                self.monitors.append(sol_monitor)
                self.logger.info("✅ Solana monitor initialized")
            except Exception as e:
                self.logger.warning(f"Solana monitor failed: {e}")
            
            # Jupiter monitor
            try:
                jupiter_monitor = JupiterSolanaMonitor()
                jupiter_monitor.add_callback(self._handle_opportunity)
                self.monitors.append(jupiter_monitor)
                self.logger.info("✅ Jupiter monitor initialized")
            except Exception as e:
                self.logger.warning(f"Jupiter monitor failed: {e}")
            
            active_monitors = len(self.monitors)
            self.logger.info(f"✅ {active_monitors}/4 monitors initialized successfully")
            
            if active_monitors == 0:
                self.logger.error("No monitors initialized successfully")
                raise Exception("Failed to initialize any monitors")
            
            # Start test opportunity generation for dashboard verification
            self.logger.info("🧪 Starting test opportunity generation...")
            asyncio.create_task(self._generate_test_opportunities())
            
        except Exception as e:
            self.logger.error(f"Failed to initialize monitors: {e}")
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

    async def start(self) -> None:
        """Start the enhanced trading system."""
        try:
            await self.initialize()
            
            self.is_running = True
            self._log_system_startup()
            
            # Start all monitors
            monitor_tasks = []
            for monitor in self.monitors:
                task = asyncio.create_task(monitor.start())
                monitor_tasks.append(task)
            
            # Start system monitoring and reporting
            monitoring_task = asyncio.create_task(self._system_monitoring_loop())
            
            # Start position monitoring (handled by trading executor)
            
            # Wait for all tasks
            all_tasks = monitor_tasks + [monitoring_task]
            if self.web_server_task:
                all_tasks.append(self.web_server_task)
            
            await asyncio.gather(*all_tasks)
            
        except KeyboardInterrupt:
            self.logger.info("🛑 Shutdown requested by user")
        except Exception as e:
            self.logger.error(f"❌ System error: {e}")
        finally:
            await self.stop()

    async def _handle_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Enhanced opportunity handler with robust dashboard integration.
        
        Args:
            opportunity: Trading opportunity from monitors
        """
        try:
            # Validate opportunity structure
            if not opportunity or not hasattr(opportunity, 'token'):
                self.logger.warning("Invalid opportunity received - skipping")
                return

            token_symbol = getattr(opportunity.token, 'symbol', 'UNKNOWN')
            token_address = getattr(opportunity.token, 'address', 'UNKNOWN')
            
            self.logger.info(f"🔍 Processing opportunity: {token_symbol} ({token_address[:10]}...)")
            
            # Ensure opportunity has required attributes
            if not hasattr(opportunity, 'metadata') or not opportunity.metadata:
                opportunity.metadata = {}
                
            if not hasattr(opportunity, 'chain') or not opportunity.chain:
                # Try to infer chain from metadata or set default
                opportunity.chain = opportunity.metadata.get('chain', 'ethereum')
            
            # Ensure opportunity has timestamp - check multiple possible attributes
            timestamp = None
            for attr_name in ['timestamp', 'detected_at', 'created_at']:
                if hasattr(opportunity, attr_name):
                    timestamp = getattr(opportunity, attr_name)
                    break
            
            if not timestamp:
                # Set timestamp if missing
                timestamp = datetime.now()
                opportunity.timestamp = timestamp
                if hasattr(opportunity, 'detected_at'):
                    opportunity.detected_at = timestamp
            
            # Ensure price field exists
            if not hasattr(opportunity.token, 'price'):
                opportunity.token.price = 1.0  # Default price
            
            # Update analysis statistics
            self.analysis_stats["total_analyzed"] += 1
            
            # Track by chain
            chain = opportunity.metadata.get('chain', 'unknown').lower()
            if chain in self.opportunities_by_chain:
                self.opportunities_by_chain[chain] += 1
            
            # Perform comprehensive analysis
            enhanced_opportunity = await self._analyze_opportunity(opportunity)
            
            # Execute trading logic if enabled
            if self.auto_trading_enabled and self.trading_executor:
                try:
                    decision = await self.trading_executor.assess_opportunity(enhanced_opportunity)
                    self.execution_metrics["opportunities_assessed"] += 1
                    
                    if hasattr(decision, 'value'):
                        decision_value = decision.value
                    else:
                        decision_value = str(decision)
                    
                    if decision_value == "EXECUTE":
                        self.execution_metrics["trades_approved"] += 1
                        self.logger.info(f"✅ Trade approved for {token_symbol}")
                    elif decision_value == "REJECT":
                        self.execution_metrics["trades_rejected"] += 1
                        self.logger.debug(f"❌ Trade rejected for {token_symbol}")
                    
                except Exception as trading_error:
                    self.logger.error(f"Trading assessment failed for {token_symbol}: {trading_error}")
            
            # **CRITICAL FIX**: Always add to dashboard, regardless of trading mode
            await self._add_to_dashboard_guaranteed(enhanced_opportunity)
            
            # Log successful processing
            self.logger.debug(f"✅ Successfully processed opportunity: {token_symbol}")
            
        except Exception as e:
            token_symbol = getattr(opportunity.token, 'symbol', 'UNKNOWN') if hasattr(opportunity, 'token') else 'UNKNOWN'
            self.logger.error(f"Error handling opportunity {token_symbol}: {e}")
            import traceback
            self.logger.debug(f"Full traceback: {traceback.format_exc()}")

    async def _add_to_dashboard_guaranteed(self, opportunity: TradingOpportunity) -> None:
        """
        Guaranteed dashboard update with comprehensive error handling.
        
        Args:
            opportunity: Trading opportunity to add to dashboard
        """
        try:
            # Skip if dashboard is disabled
            if self.disable_dashboard:
                return
                
            # Method 1: Try dashboard server add_opportunity method
            if hasattr(self, 'dashboard_server') and self.dashboard_server:
                try:
                    await self.dashboard_server.add_opportunity(opportunity)
                    self.logger.debug(f"✅ Dashboard updated via server: {opportunity.token.symbol}")
                    return  # Success - exit early
                except Exception as server_error:
                    self.logger.warning(f"Dashboard server update failed: {server_error}")
            
            # Method 2: Manual dashboard update as fallback
            if hasattr(self, 'dashboard_server') and self.dashboard_server:
                try:
                    await self._manual_dashboard_update(opportunity)
                    self.logger.debug(f"✅ Dashboard updated manually: {opportunity.token.symbol}")
                    return
                except Exception as manual_error:
                    self.logger.warning(f"Manual dashboard update failed: {manual_error}")
            
            # Method 3: Log the failure but don't break the system
            self.logger.warning(f"All dashboard update methods failed for {opportunity.token.symbol}")
            
        except Exception as e:
            # Final safety net - never let dashboard errors break opportunity processing
            self.logger.error(f"Critical dashboard update error: {e}")

    async def _manual_dashboard_update(self, opportunity: TradingOpportunity) -> None:
        """
        Manual dashboard update as fallback method.
        
        Args:
            opportunity: Trading opportunity to broadcast
        """
        try:
            # Extract data safely with defaults
            token_symbol = getattr(opportunity.token, 'symbol', 'UNKNOWN')
            token_address = getattr(opportunity.token, 'address', '')
            chain = opportunity.metadata.get('chain', 'ethereum')
            
            # Extract liquidity info safely
            liquidity_usd = 0.0
            if hasattr(opportunity, 'liquidity') and opportunity.liquidity:
                liquidity_usd = float(getattr(opportunity.liquidity, 'liquidity_usd', 0))
            
            # Create opportunity data structure
            opp_data = {
                "token_symbol": token_symbol,
                "token_address": token_address,
                "chain": chain.lower(),
                "risk_level": opportunity.metadata.get("risk_level", "unknown"),
                "recommendation": opportunity.metadata.get("recommendation", {}).get("action", "MONITOR"),
                "confidence": opportunity.metadata.get("recommendation", {}).get("confidence", "LOW"),
                "score": opportunity.metadata.get("trading_score", {}).get("overall_score", 0.0),
                "liquidity_usd": liquidity_usd,
                "detected_at": datetime.now().isoformat(),
                "age_minutes": 0
            }
            
            # Update dashboard stats manually
            if hasattr(self.dashboard_server, 'stats'):
                self.dashboard_server.stats["total_opportunities"] += 1
                
                if opp_data["confidence"] == "HIGH":
                    self.dashboard_server.stats["high_confidence"] += 1
            
            # Add to opportunities queue manually
            if hasattr(self.dashboard_server, 'opportunities_queue'):
                self.dashboard_server.opportunities_queue.append(opportunity)
                
                # Keep queue size manageable
                if len(self.dashboard_server.opportunities_queue) > 100:
                    self.dashboard_server.opportunities_queue.pop(0)
            
            # Broadcast to WebSocket clients
            if hasattr(self.dashboard_server, 'broadcast_message'):
                await self.dashboard_server.broadcast_message({
                    "type": "new_opportunity",
                    "data": opp_data
                })
            
            self.logger.debug(f"Manual dashboard update successful: {token_symbol}")
            
        except Exception as e:
            self.logger.error(f"Manual dashboard update failed: {e}")
            raise

    async def _generate_test_opportunities(self) -> None:
        """
        Generate test opportunities for dashboard testing.
        This helps verify that the dashboard integration is working.
        """
        try:
            await asyncio.sleep(15)  # Wait for system to fully initialize
            
            self.logger.info("🧪 Generating test opportunities for dashboard verification...")
            
            # Generate test opportunities to verify dashboard
            test_tokens = [
                ("TESTMEME", "ethereum", 150000.0),
                ("MOCKCOIN", "solana", 75000.0), 
                ("BASETEST", "base", 200000.0)
            ]
            
            for i, (symbol, chain, liquidity) in enumerate(test_tokens):
                try:
                    await asyncio.sleep(10)  # Stagger opportunities
                    
                    # Create test opportunity
                    test_opportunity = await self._create_test_opportunity(symbol, chain, liquidity)
                    
                    if test_opportunity:
                        # Process through normal pipeline
                        await self._handle_opportunity(test_opportunity)
                        self.logger.info(f"🧪 Test opportunity {i+1}/3 processed: {symbol}")
                    
                except Exception as test_error:
                    self.logger.error(f"Test opportunity {i+1} failed: {test_error}")
            
            self.logger.info("🧪 Test opportunity generation completed")
            
        except Exception as e:
            self.logger.error(f"Test opportunity generation failed: {e}")

    async def _create_test_opportunity(self, symbol: str, chain: str, liquidity: float) -> Optional[TradingOpportunity]:
        """
        Create a test trading opportunity for dashboard testing.
        
        Args:
            symbol: Token symbol
            chain: Blockchain name
            liquidity: Liquidity amount in USD
            
        Returns:
            TradingOpportunity or None if creation fails
        """
        try:
            from models.token import TokenInfo, LiquidityInfo, ContractAnalysis, SocialMetrics
            
            # Generate test address based on chain
            if chain == "solana":
                # Solana addresses don't follow 0x format and have different validation
                test_address = f"{symbol}{''.join(random.choices('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz', k=40))}"
            else:
                # EVM chains (Ethereum, Base) use 0x format
                test_address = f"0x{''.join(random.choices('0123456789abcdef', k=40))}"
            
            # Create test token info - NOTE: discovered_at is NOT a TokenInfo parameter
            if chain == "solana":
                # For Solana, we need to create a custom token-like object since TokenInfo validates for 0x format
                class SolanaTokenInfo:
                    def __init__(self, address, symbol, name, decimals=9, total_supply=1000000000):
                        self.address = address
                        self.symbol = symbol
                        self.name = name
                        self.decimals = decimals
                        self.total_supply = total_supply
                        self.price = 1.0  # Default price
                
                token_info = SolanaTokenInfo(
                    address=test_address,
                    symbol=symbol,
                    name=f"Test {symbol}",
                    decimals=9,  # Common for Solana
                    total_supply=1000000000
                )
            else:
                # For EVM chains, use regular TokenInfo
                token_info = TokenInfo(
                    address=test_address,
                    symbol=symbol,
                    name=f"Test {symbol}",
                    decimals=18,
                    total_supply=1000000000
                )
            
            # Create test liquidity info  
            liquidity_info = LiquidityInfo(
                pair_address=test_address,
                dex_name=f"Test DEX ({chain})",
                token0=test_address,
                token1="0x0000000000000000000000000000000000000000" if chain != "solana" else "So11111111111111111111111111111111111111112",
                reserve0=float(liquidity / 2),
                reserve1=float(liquidity / 2),
                liquidity_usd=liquidity,
                created_at=datetime.now(),
                block_number=0
            )
            
            # Create test contract analysis
            contract_analysis = ContractAnalysis(
                is_honeypot=False,
                is_mintable=random.choice([True, False]),
                is_pausable=random.choice([True, False]),
                has_blacklist=False,
                ownership_renounced=random.choice([True, False]),
                liquidity_locked=True,
                lock_duration=86400 * 30,  # 30 days
                risk_score=random.uniform(0.1, 0.6),
                risk_level=RiskLevel.MEDIUM
            )
            
            # Create test social metrics
            social_metrics = SocialMetrics(
                twitter_followers=random.randint(100, 10000),
                telegram_members=random.randint(50, 5000),
                social_score=random.uniform(0.3, 0.8),
                sentiment_score=random.uniform(-0.5, 0.8)
            )
            
            # Create test opportunity
            opportunity = TradingOpportunity(
                token=token_info,
                liquidity=liquidity_info,
                contract_analysis=contract_analysis,
                social_metrics=social_metrics,
                detected_at=datetime.now(),  # This IS a valid parameter for TradingOpportunity
                confidence_score=random.uniform(0.3, 0.8),
                metadata={
                    'chain': chain,
                    'source': 'test_generator',
                    'is_test': True,
                    'recommendation': {
                        'action': random.choice(['BUY', 'MONITOR', 'HOLD']),
                        'confidence': random.choice(['LOW', 'MEDIUM', 'HIGH'])
                    },
                    'trading_score': {
                        'overall_score': random.uniform(0.2, 0.9),
                        'risk_score': random.uniform(0.1, 0.7)
                    }
                }
            )
            
            # Add chain information
            opportunity.chain = chain
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Failed to create test opportunity: {e}")
            import traceback
            self.logger.debug(f"Test opportunity creation traceback: {traceback.format_exc()}")
            return None






    async def _analyze_opportunity(self, opportunity: TradingOpportunity) -> TradingOpportunity:
        """
        Perform comprehensive analysis on trading opportunity.
        
        Args:
            opportunity: Base opportunity to analyze
            
        Returns:
            TradingOpportunity: Enhanced opportunity with analysis results
        """
        try:
            enhanced_metadata = opportunity.metadata.copy()
            
            # Ensure opportunity has timestamp
            if not hasattr(opportunity, 'timestamp') or not opportunity.timestamp:
                opportunity.timestamp = datetime.now()
            
            # Contract security analysis
            if self.analyzers.get('contract'):
                try:
                    contract_analysis = await self.analyzers['contract'].analyze_contract(opportunity)
                    enhanced_metadata['contract_analysis'] = contract_analysis.__dict__ if hasattr(contract_analysis, '__dict__') else contract_analysis
                except Exception as e:
                    self.logger.warning(f"Contract analysis failed: {e}")
                    enhanced_metadata['contract_analysis'] = {'error': str(e)}
            else:
                # Mock contract analysis for testing
                enhanced_metadata['contract_analysis'] = {
                    'is_honeypot': False,
                    'ownership_risk': 0.3,
                    'liquidity_locked': True,
                    'is_verified': True,
                    'risk_score': 0.4
                }
            
            # Social sentiment analysis
            if self.analyzers.get('social'):
                try:
                    social_metrics = await self.analyzers['social'].analyze_social_metrics(opportunity)
                    enhanced_metadata['social_metrics'] = social_metrics.__dict__ if hasattr(social_metrics, '__dict__') else social_metrics
                except Exception as e:
                    self.logger.warning(f"Social analysis failed: {e}")
                    enhanced_metadata['social_metrics'] = {'error': str(e)}
            else:
                # Mock social analysis for testing
                enhanced_metadata['social_metrics'] = {
                    'sentiment': random.choice(['positive', 'neutral', 'negative']),
                    'volume_score': random.uniform(0.2, 0.8),
                    'community_quality': random.uniform(0.3, 0.9),
                    'high_bot_activity': random.choice([True, False])
                }
            
            # Trading score and recommendation
            if self.analyzers.get('trading_scorer'):
                try:
                    # TradingScorer.score_opportunity returns a float, not a coroutine
                    trading_score_result = self.analyzers['trading_scorer'].score_opportunity(opportunity)
                    
                    # Check if it's a coroutine and await if needed
                    if hasattr(trading_score_result, '__await__'):
                        trading_score = await trading_score_result
                    else:
                        trading_score = trading_score_result
                    
                    # Convert float score to dict format
                    if isinstance(trading_score, (float, int)):
                        enhanced_metadata['trading_score'] = {
                            'overall_score': float(trading_score),
                            'risk_score': 1.0 - float(trading_score),  # Inverse relationship
                            'opportunity_score': float(trading_score)
                        }
                        
                        # Create recommendation based on score
                        if trading_score >= 0.7:
                            action = 'BUY'
                            confidence = 'HIGH'
                        elif trading_score >= 0.5:
                            action = 'HOLD'
                            confidence = 'MEDIUM'
                        elif trading_score >= 0.3:
                            action = 'HOLD'
                            confidence = 'LOW'
                        else:
                            action = 'AVOID'
                            confidence = 'HIGH'
                            
                        enhanced_metadata['recommendation'] = {
                            'action': action,
                            'confidence': confidence,
                            'reasoning': f"Score-based analysis suggests {action} with {confidence} confidence (score: {trading_score:.3f})"
                        }
                    else:
                        enhanced_metadata['trading_score'] = trading_score
                        
                        # Extract recommendation if it exists
                        recommendation = trading_score.get('recommendation', {}) if isinstance(trading_score, dict) else {}
                        if recommendation:
                            enhanced_metadata['recommendation'] = recommendation
                    
                    # Update statistics
                    action = enhanced_metadata.get('recommendation', {}).get('action', 'HOLD')
                    confidence = enhanced_metadata.get('recommendation', {}).get('confidence', 'MEDIUM')
                    
                    if action in self.analysis_stats["recommendations"]:
                        self.analysis_stats["recommendations"][action] += 1
                    
                    if confidence == 'HIGH':
                        self.analysis_stats["high_confidence"] += 1
                        
                except Exception as e:
                    self.logger.warning(f"Trading score analysis failed: {e}")
                    enhanced_metadata['trading_score'] = {'error': str(e)}
            else:
                # Mock trading score for testing
                action = random.choice(['BUY', 'HOLD', 'SELL', 'AVOID'])
                confidence = random.choice(['HIGH', 'MEDIUM', 'LOW'])
                
                enhanced_metadata['trading_score'] = {
                    'overall_score': random.uniform(0.1, 0.9),
                    'risk_score': random.uniform(0.2, 0.8),
                    'opportunity_score': random.uniform(0.3, 0.9)
                }
                
                enhanced_metadata['recommendation'] = {
                    'action': action,
                    'confidence': confidence,
                    'reasoning': f"Mock analysis suggests {action} with {confidence} confidence"
                }
                
                # Update statistics
                if action in self.analysis_stats["recommendations"]:
                    self.analysis_stats["recommendations"][action] += 1
                
                if confidence == 'HIGH':
                    self.analysis_stats["high_confidence"] += 1
            
            # Create enhanced opportunity with correct parameters
            enhanced_opportunity = TradingOpportunity(
                token=opportunity.token,
                liquidity=opportunity.liquidity,
                contract_analysis=getattr(opportunity, 'contract_analysis', None),
                social_metrics=getattr(opportunity, 'social_metrics', None),
                detected_at=opportunity.timestamp,
                metadata=enhanced_metadata
            )
            
            # Add chain as metadata since it's not a constructor parameter
            enhanced_opportunity.metadata['chain'] = getattr(opportunity, 'chain', 'ethereum')
            
            return enhanced_opportunity
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive analysis: {e}")
            import traceback
            self.logger.debug(f"Full traceback: {traceback.format_exc()}")
            return opportunity

    async def _handle_trading_alert(self, alert_data: Dict[str, Any]) -> None:
        """
        Handle trading alerts from the execution system.
        
        Args:
            alert_data: Alert information
        """
        try:
            alert_type = alert_data.get('type', 'UNKNOWN')
            
            # Update statistics based on alert type
            if alert_type == 'TRADE_EXECUTED':
                self.analysis_stats["trades_executed"] += 1
                self.execution_metrics["position_count"] += 1
                
                position_data = alert_data.get('position')
                if position_data:
                    self.logger.info(f"🎯 TRADE EXECUTED: {position_data.get('token_symbol', 'UNKNOWN')}")
                    
            elif alert_type.startswith('POSITION_CLOSED'):
                self.execution_metrics["position_count"] = max(0, self.execution_metrics["position_count"] - 1)
                
                position_data = alert_data.get('position')
                if position_data:
                    # Update P&L tracking
                    pnl = position_data.get('unrealized_pnl', 0)
                    if isinstance(pnl, (int, float, Decimal)):
                        self.analysis_stats["total_pnl"] += Decimal(str(pnl))
                        self.execution_metrics["daily_pnl"] += float(pnl)
                        
                        if pnl > 0:
                            self.analysis_stats["successful_trades"] += 1
                    
                    self.logger.info(f"🚪 POSITION CLOSED: {position_data.get('token_symbol', 'UNKNOWN')}")
            
            elif alert_type == 'TRADE_FAILED':
                error_msg = alert_data.get('error_message', 'Unknown error')
                self.logger.error(f"❌ TRADE FAILED: {error_msg}")
            
            # Broadcast alert to dashboard
            if self.dashboard_server:
                await self.dashboard_server.broadcast_message({
                    "type": "trading_alert",
                    "data": alert_data
                })
                
        except Exception as e:
            self.logger.error(f"Error handling trading alert: {e}")

    async def _system_monitoring_loop(self) -> None:
        """Main system monitoring and reporting loop."""
        self.logger.info("🔄 Starting system monitoring loop")
        
        while self.is_running:
            try:
                await asyncio.sleep(30)  # Report every 30 seconds
                
                await self._update_performance_metrics()
                await self._log_system_statistics()
                await self._update_dashboard_metrics()
                
            except asyncio.CancelledError:
                self.logger.info("System monitoring cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in system monitoring: {e}")
                await asyncio.sleep(60)

    async def _update_performance_metrics(self) -> None:
        """Update system performance metrics."""
        try:
            # Update execution metrics
            if self.risk_manager:
                exposure_data = self.risk_manager.get_current_exposure()
                self.execution_metrics.update({
                    "average_risk_score": exposure_data.get('average_risk_score', 0.0),
                    "position_count": exposure_data.get('total_positions', 0),
                    "daily_pnl": exposure_data.get('daily_pnl', 0.0)
                })
            
            # Calculate success rates
            if self.analysis_stats["trades_executed"] > 0:
                success_rate = (self.analysis_stats["successful_trades"] / 
                               self.analysis_stats["trades_executed"]) * 100
                self.execution_metrics["success_rate"] = success_rate
            
        except Exception as e:
            self.logger.error(f"Error updating performance metrics: {e}")

    async def _log_system_statistics(self) -> None:
        """Log comprehensive system statistics."""
        try:
            uptime = datetime.now() - self.start_time
            analysis_rate = self.analysis_stats["total_analyzed"] / max(uptime.total_seconds() / 60, 1)
            
            self.logger.info("📊 ENHANCED TRADING SYSTEM STATISTICS:")
            self.logger.info(f"   Uptime: {uptime}")
            self.logger.info(f"   Analysis Rate: {analysis_rate:.1f}/min")
            self.logger.info(f"   Total Analyzed: {self.analysis_stats['total_analyzed']}")
            self.logger.info(f"   High Confidence: {self.analysis_stats['high_confidence']}")
            
            # Trading execution stats
            self.logger.info("   TRADING EXECUTION:")
            self.logger.info(f"     Mode: {self.trading_mode.value}")
            self.logger.info(f"     Assessed: {self.execution_metrics['opportunities_assessed']}")
            self.logger.info(f"     Approved: {self.execution_metrics['trades_approved']}")
            self.logger.info(f"     Executed: {self.analysis_stats['trades_executed']}")
            self.logger.info(f"     Successful: {self.analysis_stats['successful_trades']}")
            
            if 'success_rate' in self.execution_metrics:
                self.logger.info(f"     Success Rate: {self.execution_metrics['success_rate']:.1f}%")
            
            # P&L tracking
            total_pnl = float(self.analysis_stats["total_pnl"])
            daily_pnl = self.execution_metrics["daily_pnl"]
            self.logger.info(f"     Total P&L: ${total_pnl:.2f}")
            self.logger.info(f"     Daily P&L: ${daily_pnl:.2f}")
            
            # Chain breakdown
            self.logger.info("   CHAIN OPPORTUNITIES:")
            for chain, count in self.opportunities_by_chain.items():
                if count > 0:
                    self.logger.info(f"     {chain.capitalize()}: {count}")
            
            # Recommendation breakdown
            self.logger.info("   RECOMMENDATIONS:")
            for action, count in self.analysis_stats["recommendations"].items():
                if count > 0:
                    self.logger.info(f"     {action}: {count}")
            
            # Portfolio status
            if self.position_manager:
                try:
                    portfolio = self.trading_executor.get_portfolio_summary()
                    active_positions = portfolio.get('total_positions', 0)
                    total_exposure = portfolio.get('total_exposure_usd', 0)
                    
                    if active_positions > 0:
                        self.logger.info(f"   PORTFOLIO: {active_positions} positions, ${total_exposure:.2f} exposure")
                except Exception:
                    pass  # Ignore portfolio errors in logging
            
            # Dashboard status
            if self.dashboard_server and not self.disable_dashboard:
                connected_clients = len(self.dashboard_server.connected_clients)
                self.logger.info(f"   DASHBOARD: {connected_clients} connected clients")
                
        except Exception as e:
            self.logger.error(f"Error logging system statistics: {e}")

    async def _update_dashboard_metrics(self) -> None:
        """Update dashboard with latest metrics."""
        try:
            if self.dashboard_server and not self.disable_dashboard:
                # Update analysis rate
                uptime = datetime.now() - self.start_time
                analysis_rate = self.analysis_stats["total_analyzed"] / max(uptime.total_seconds() / 60, 1)
                
                await self.dashboard_server.update_analysis_rate(int(analysis_rate))
                
                # Update trading metrics
                if hasattr(self.dashboard_server, 'update_trading_metrics'):
                    await self.dashboard_server.update_trading_metrics(self.execution_metrics)
                    
        except Exception as e:
            self.logger.debug(f"Dashboard metrics update failed: {e}")

    def _log_system_startup(self) -> None:
        """Log system startup information."""
        self.logger.info("=" * 80)
        self.logger.info("🚀 ENHANCED MULTI-CHAIN DEX SNIPING SYSTEM")
        self.logger.info("Features: Advanced Analysis + Automated Trading + Risk Management")
        self.logger.info("")
        self.logger.info("MONITORING CONFIGURATION:")
        self.logger.info("  Ethereum: Uniswap V2 (5s intervals)")
        self.logger.info("  Base: Uniswap V2 (2s intervals)")
        self.logger.info("  Solana: Pump.fun + Jupiter (5s + 10s)")
        self.logger.info("")
        self.logger.info("ENHANCED FEATURES:")
        self.logger.info("  - Multi-factor risk assessment")
        self.logger.info("  - Dynamic position sizing")
        self.logger.info("  - Automated execution with safeguards")
        self.logger.info("  - Real-time portfolio management")
        self.logger.info("  - Advanced stop-loss/take-profit")
        self.logger.info("  - Market condition adaptation")
        self.logger.info("")
        self.logger.info("TRADING CONFIGURATION:")
        self.logger.info(f"  Mode: {self.trading_mode.value}")
        self.logger.info(f"  Auto Execution: {'ENABLED' if self.auto_trading_enabled else 'DISABLED'}")
        
        if self.risk_manager:
            limits = self.risk_manager.current_limits
            self.logger.info(f"  Max Exposure: ${limits.max_total_exposure_usd}")
            self.logger.info(f"  Max Position: ${limits.max_single_position_usd}")
            self.logger.info(f"  Daily Loss Limit: ${limits.max_daily_loss_usd}")
            
        if not self.disable_dashboard:
            self.logger.info("")
            self.logger.info("🌐 WEB DASHBOARD: http://localhost:8000")
            
        self.logger.info("=" * 80)

    async def stop(self) -> None:
        """Stop the enhanced trading system."""
        try:
            self.logger.info("🛑 Stopping Enhanced Trading System...")
            self.is_running = False
            
            # Stop monitors
            for monitor in self.monitors:
                if hasattr(monitor, 'stop'):
                    monitor.stop()
            
            # Stop trading system
            if self.trading_executor:
                await self.trading_executor.cleanup()
            
            # Stop web server
            if self.web_server_task:
                self.web_server_task.cancel()
                try:
                    await self.web_server_task
                except asyncio.CancelledError:
                    pass
            
            # Cleanup analyzers
            for analyzer in self.analyzers.values():
                if hasattr(analyzer, 'cleanup'):
                    await analyzer.cleanup()
            
            self.logger.info("✅ Enhanced Trading System stopped")
            
        except Exception as e:
            self.logger.error(f"Error during system stop: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            Dictionary containing system status information
        """
        try:
            uptime = datetime.now() - self.start_time
            
            status = {
                'system': {
                    'running': self.is_running,
                    'uptime_seconds': uptime.total_seconds(),
                    'trading_mode': self.trading_mode.value,
                    'auto_trading': self.auto_trading_enabled
                },
                'analysis': self.analysis_stats.copy(),
                'execution': self.execution_metrics.copy(),
                'chains': self.opportunities_by_chain.copy(),
                'components': {
                    'monitors': len(self.monitors),
                    'analyzers': len(self.analyzers),
                    'risk_manager': self.risk_manager is not None,
                    'position_manager': self.position_manager is not None,
                    'trading_executor': self.trading_executor is not None,
                    'dashboard': self.dashboard_server is not None
                }
            }
            
            # Add portfolio information if available
            if self.trading_executor:
                try:
                    portfolio = self.trading_executor.get_portfolio_summary()
                    status['portfolio'] = portfolio
                except Exception:
                    status['portfolio'] = {'error': 'Portfolio data unavailable'}
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {'error': str(e)}


async def main():
    """Main entry point for enhanced trading system."""
    parser = argparse.ArgumentParser(description='Enhanced DEX Sniping System')
    parser.add_argument('--auto-trade', action='store_true',
                       help='Enable automated trading execution')
    parser.add_argument('--live-trading', action='store_true',
                       help='Enable live trading with real funds (requires --auto-trade)')
    parser.add_argument('--paper-only', action='store_true',
                       help='Paper trading only (default)')
    parser.add_argument('--no-dashboard', action='store_true',
                       help='Disable web dashboard')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set up logging
    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine trading mode
    if args.live_trading and args.auto_trade:
        trading_mode = TradingMode.LIVE_TRADING
        print("\n⚠️  WARNING: LIVE TRADING MODE ENABLED ⚠️")
        print("This will execute real trades with actual funds!")
        print("Make sure you understand the risks involved.")
        
        confirmation = input("\nType 'I UNDERSTAND THE RISKS' to continue: ")
        if confirmation != "I UNDERSTAND THE RISKS":
            print("Live trading cancelled.")
            return
            
    elif args.auto_trade:
        trading_mode = TradingMode.PAPER_ONLY
        print("📄 Paper trading mode - Automated execution without real funds")
    else:
        trading_mode = TradingMode.PAPER_ONLY
        print("📄 Analysis mode - No automated execution")
    
    try:
        # Create and start system
        system = EnhancedTradingSystem(
            auto_trading_enabled=args.auto_trade,
            trading_mode=trading_mode,
            disable_dashboard=args.no_dashboard
        )
        
        await system.start()
        
    except KeyboardInterrupt:
        print("\n⚠️ Shutdown requested by user")
    except Exception as e:
        print(f"\n❌ System error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
    finally:
        print("\nSystem stopped.")


if __name__ == "__main__":
    asyncio.run(main())