# main_with_trading.py (Full Version with Web Dashboard)
"""
Full enhanced main.py with web dashboard and trading execution.
Complete multi-chain DEX sniping system with UI and automated trading.
"""

import asyncio
import sys
import os
from typing import List, Dict
from datetime import datetime
from web3 import Web3

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger_manager
from monitors.new_token_monitor import NewTokenMonitor
from monitors.base_chain_monitor import BaseChainMonitor
from monitors.solana_monitor import SolanaMonitor
from monitors.jupiter_solana_monitor import JupiterSolanaMonitor
from models.token import TradingOpportunity, RiskLevel
from config.chains import multichain_settings, ChainType

# Phase 2: Import analysis components
from analyzers.contract_analyzer import ContractAnalyzer
from analyzers.social_analyzer import SocialAnalyzer
from analyzers.trading_scorer import TradingScorer

# Phase 3: Import full trading and dashboard components
from trading.executor import TradingExecutor, TradeConfig

class FullEnhancedSystem:
    """
    Complete enhanced multi-chain system with analysis, trading, and web dashboard.
    Full production system with UI and automated execution capabilities.
    """
    
    def __init__(self):
        """Initialize the full enhanced system."""
        self.logger = logger_manager.get_logger("FullEnhancedSystem")
        self.monitors: List = []
        self.is_running = False
        
        # Track opportunities by chain and source
        self.opportunities_by_chain: Dict[str, int] = {
            "Ethereum": 0,
            "Base": 0,
            "Solana-Pump": 0,
            "Solana-Jupiter": 0
        }
        
        # Analysis tracking
        self.analysis_stats = {
            "total_analyzed": 0,
            "high_confidence": 0,
            "trades_executed": 0,
            "recommendations": {
                "STRONG_BUY": 0,
                "BUY": 0,
                "SMALL_BUY": 0,
                "WATCH": 0,
                "AVOID": 0
            }
        }
        
        self.start_time: datetime = None
        
        # Phase 2: Analysis components
        self.contract_analyzer: ContractAnalyzer = None
        self.social_analyzer: SocialAnalyzer = None
        self.trading_scorer: TradingScorer = None
        self.w3: Web3 = None
        
        # Phase 3: Full trading and dashboard components
        self.trading_executor: TradingExecutor = None
        self.dashboard_server = None
        self.web_server_task = None
        
    async def start(self) -> None:
        """Start the full enhanced system."""
        try:
            self.logger.info("🚀 STARTING FULL ENHANCED SYSTEM - Complete Trading Platform!")
            self.logger.info("=" * 80)
            self.start_time = datetime.now()
            self.is_running = True
            
            # Display configuration
            self._log_system_info()
            
            # Initialize components in order
            await self._initialize_analyzers()
            await self._initialize_trading_system()
            await self._initialize_web_dashboard()
            await self._initialize_monitors()
            
            # Start main monitoring loop
            await self._run_monitoring_loop()
            
        except Exception as e:
            self.logger.error(f"FATAL ERROR in full enhanced system: {e}")
            raise
        finally:
            await self._cleanup()
            
    async def _initialize_analyzers(self) -> None:
        """Initialize Phase 2 analysis components with robust RPC handling."""
        try:
            self.logger.info("INITIALIZING Phase 2 analyzers...")
            
            # Initialize Web3 with robust connection handling
            from config.settings import settings
            
            # Try multiple RPC endpoints for reliability
            rpc_urls = settings.get_rpc_urls('ethereum')
            
            self.w3 = None
            connection_successful = False
            
            for i, rpc_url in enumerate(rpc_urls):
                try:
                    self.logger.info(f"Attempting Ethereum connection {i+1}/{len(rpc_urls)}: {rpc_url}")
                    
                    # Create Web3 instance with timeout
                    from web3 import Web3
                    import requests
                    
                    # Test the RPC endpoint first with a simple HTTP request
                    response = requests.get(rpc_url, timeout=10)
                    if response.status_code not in [200, 405]:  # 405 is also acceptable for some RPCs
                        self.logger.warning(f"RPC {rpc_url} returned status {response.status_code}")
                        continue
                    
                    # Create Web3 instance
                    self.w3 = Web3(Web3.HTTPProvider(rpc_url))
                    
                    # Test connection with actual Web3 call
                    if self.w3.is_connected():
                        # Try to get block number to verify connection works
                        block_number = self.w3.eth.block_number
                        if block_number > 0:
                            self.logger.info(f"✅ Ethereum connection successful! Block: {block_number}")
                            connection_successful = True
                            break
                        else:
                            self.logger.warning(f"RPC connected but returned invalid block number: {block_number}")
                            
                except requests.exceptions.Timeout:
                    self.logger.warning(f"RPC timeout: {rpc_url}")
                    continue
                except requests.exceptions.ConnectionError:
                    self.logger.warning(f"RPC connection failed: {rpc_url}")
                    continue
                except Exception as e:
                    self.logger.warning(f"RPC error {rpc_url}: {str(e)[:50]}...")
                    continue
            
            # If no connection worked, proceed with limited functionality
            if not connection_successful:
                self.logger.warning("Could not establish Ethereum connection - proceeding with limited analysis")
                self.logger.warning("Contract analysis will be disabled, social analysis will still work")
                
                # Create a dummy Web3 instance to prevent crashes
                self.w3 = None
            
            # Initialize analyzers with error handling
            try:
                if self.w3:
                    self.contract_analyzer = ContractAnalyzer(self.w3)
                    await self.contract_analyzer.initialize()
                    self.logger.info("✅ Contract analyzer initialized")
                else:
                    self.contract_analyzer = None
                    self.logger.warning("⚠️ Contract analyzer disabled (no Ethereum connection)")
            except Exception as e:
                self.logger.error(f"Contract analyzer initialization failed: {e}")
                self.contract_analyzer = None
            
            try:
                self.social_analyzer = SocialAnalyzer()
                await self.social_analyzer.initialize()
                self.logger.info("✅ Social analyzer initialized")
            except Exception as e:
                self.logger.error(f"Social analyzer initialization failed: {e}")
                self.social_analyzer = None
            
            try:
                self.trading_scorer = TradingScorer()
                self.logger.info("✅ Trading scorer initialized")
            except Exception as e:
                self.logger.error(f"Trading scorer initialization failed: {e}")
                self.trading_scorer = None
            
            # Report initialization status
            initialized_components = []
            if self.contract_analyzer:
                initialized_components.append("Contract Analyzer")
            if self.social_analyzer:
                initialized_components.append("Social Analyzer")
            if self.trading_scorer:
                initialized_components.append("Trading Scorer")
            
            if initialized_components:
                self.logger.info(f"✅ Phase 2 analyzers partially initialized: {', '.join(initialized_components)}")
            else:
                self.logger.warning("⚠️ No analyzers initialized - system will run with basic monitoring only")
            
        except Exception as e:
            self.logger.error(f"Analyzer initialization error: {e}")
            # Don't fail the entire system - continue with limited functionality
            self.contract_analyzer = None
            self.social_analyzer = None
            self.trading_scorer = None
            self.w3 = None
            self.logger.warning("Continuing with basic monitoring only")
            
    async def _initialize_trading_system(self) -> None:
        """Initialize full trading system with graceful error handling."""
        try:
            self.logger.info("INITIALIZING full trading system...")
            
            # Configure trading system
            trade_config = TradeConfig(
                auto_execute=False,  # Start with manual approval for safety
                max_slippage=0.05,   # 5% max slippage
                position_size_eth=0.1,  # 0.1 ETH default position
                stop_loss_percentage=0.15,  # 15% stop loss
                take_profit_percentage=0.50  # 50% take profit
            )
            
            try:
                self.trading_executor = TradingExecutor(trade_config)
                await self.trading_executor.initialize()
                
                self.logger.info("✅ Full trading system initialized")
                self.logger.info(f"   - Auto Execute: {trade_config.auto_execute}")
                self.logger.info(f"   - Max Slippage: {trade_config.max_slippage * 100}%")
                self.logger.info(f"   - Position Size: {trade_config.position_size_eth} ETH")
                self.logger.info(f"   - Stop Loss: {trade_config.stop_loss_percentage * 100}%")
                self.logger.info(f"   - Take Profit: {trade_config.take_profit_percentage * 100}%")
                
            except Exception as e:
                self.logger.error(f"Trading executor initialization failed: {e}")
                self.trading_executor = None
                self.logger.warning("⚠️ Trading system disabled - continuing with monitoring only")
            
        except Exception as e:
            self.logger.error(f"Trading system initialization error: {e}")
            self.trading_executor = None
            self.logger.warning("⚠️ Trading system disabled - continuing with monitoring only")

    dashboard_server_instance = None

    # Update the FullEnhancedSystem class _initialize_web_dashboard method:

    async def _initialize_web_dashboard(self) -> None:
        """
        Initialize full web dashboard with FastAPI.
        
        Raises:
            ImportError: If dashboard modules are not available
            Exception: If server initialization fails
        """
        try:
            self.logger.info("INITIALIZING full web dashboard...")
            
            # Import the full dashboard server
            from api.dashboard_server import app, dashboard_server
            
            # Store reference to dashboard server
            self.dashboard_server = dashboard_server
            
            # Connect trading executor to dashboard
            if self.trading_executor:
                self.dashboard_server.trading_executor = self.trading_executor
            
            # Initialize dashboard server
            await self.dashboard_server.initialize()
            
            # Configure and start FastAPI server
            import uvicorn
            
            config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=8000,
                log_level="warning",  # Reduce noise
                access_log=False
            )
            
            server = uvicorn.Server(config)
            
            # Start server in background task
            self.web_server_task = asyncio.create_task(server.serve())
            
            self.logger.info("SUCCESS: Full web dashboard initialized")
            self.logger.info("   Dashboard URL: http://localhost:8000")
            self.logger.info("   Real-time WebSocket updates enabled")
            self.logger.info("   Trading execution interface active")
            
            # Allow server to fully start
            await asyncio.sleep(2)
            
        except ImportError as e:
            self.logger.error(f"Dashboard modules not found: {e}")
            self.logger.warning("Install FastAPI: pip install fastapi uvicorn")
            self.dashboard_server = None
        except Exception as e:
            self.logger.error(f"Failed to initialize web dashboard: {e}")
            self.logger.warning("Continuing without web dashboard - console only")
            self.dashboard_server = None






    async def _initialize_monitors(self) -> None:
        """Initialize all chain monitors."""
        try:
            self.logger.info("INITIALIZING monitors...")
            
            # Get chain configurations with fallbacks
            try:
                eth_config = multichain_settings.get_chain_config(ChainType.ETHEREUM)
            except KeyError:
                self.logger.warning("Ethereum config not found")
                eth_config = None
                
            try:
                base_config = multichain_settings.get_chain_config(ChainType.BASE)
            except KeyError:
                self.logger.warning("Base config not found")
                base_config = None
            
            # Ethereum monitor
            if eth_config:
                try:
                    enabled = getattr(eth_config, 'enabled', True)
                    interval = getattr(eth_config, 'check_interval', 5.0)
                    dex_name = getattr(eth_config, 'dex_name', 'Uniswap V2')
                    
                    if enabled:
                        eth_monitor = NewTokenMonitor()
                        eth_monitor.add_callback(self._handle_ethereum_opportunity)
                        self.monitors.append(eth_monitor)
                        self.logger.info(f"✅ Ethereum monitor: {dex_name}")
                    else:
                        self.logger.info("⚠️ Ethereum monitor: DISABLED by config")
                except Exception as e:
                    self.logger.error(f"Failed to initialize Ethereum monitor: {e}")
            else:
                self.logger.info("⚠️ Ethereum monitor: No config available")
                
            # Base monitor  
            if base_config:
                try:
                    enabled = getattr(base_config, 'enabled', True)
                    interval = getattr(base_config, 'check_interval', 2.0)
                    dex_name = getattr(base_config, 'dex_name', 'Uniswap V2')
                    
                    if enabled:
                        base_monitor = BaseChainMonitor()
                        base_monitor.add_callback(self._handle_base_opportunity)
                        self.monitors.append(base_monitor)
                        self.logger.info(f"✅ Base monitor: {dex_name}")
                    else:
                        self.logger.info("⚠️ Base monitor: DISABLED by config")
                except Exception as e:
                    self.logger.error(f"Failed to initialize Base monitor: {e}")
            else:
                self.logger.info("⚠️ Base monitor: No config available")
                
            # Solana monitors
            try:
                pump_monitor = SolanaMonitor()
                pump_monitor.add_callback(self._handle_solana_pump_opportunity)
                self.monitors.append(pump_monitor)
                self.logger.info("✅ Solana Pump.fun monitor")
            except Exception as e:
                self.logger.warning(f"Solana Pump.fun monitor failed: {e}")
                
            try:
                jupiter_monitor = JupiterSolanaMonitor()
                jupiter_monitor.add_callback(self._handle_solana_jupiter_opportunity)
                self.monitors.append(jupiter_monitor)
                self.logger.info("✅ Solana Jupiter monitor")
            except Exception as e:
                self.logger.warning(f"Solana Jupiter monitor failed: {e}")
                
            if len(self.monitors) == 0:
                self.logger.warning("No monitors initialized!")
            else:
                self.logger.info(f"Successfully initialized {len(self.monitors)} monitors")
            
        except Exception as e:
            self.logger.error(f"Monitor initialization error: {e}")
            
    async def _run_monitoring_loop(self) -> None:
        """Run the main monitoring loop with web dashboard."""
        try:
            self.logger.info("🎯 STARTING full monitoring loop...")
            
            # Start all monitors
            monitor_tasks = []
            for monitor in self.monitors:
                task = asyncio.create_task(monitor.start())
                monitor_tasks.append(task)
                self.logger.info(f"Started monitor: {monitor.name}")
                
            # Start statistics reporting
            stats_task = asyncio.create_task(self._report_statistics())
            
            # Combine all tasks including web server
            all_tasks = monitor_tasks + [stats_task]
            if self.web_server_task:
                all_tasks.append(self.web_server_task)
            
            # Wait for all tasks
            await asyncio.gather(*all_tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"Monitoring loop error: {e}")
            raise
            
    async def _handle_ethereum_opportunity(self, opportunity: TradingOpportunity) -> None:
            """
            Handle Ethereum opportunity with full analysis and trading.
            
            Args:
                opportunity: The Ethereum trading opportunity to process
            """
            try:
                self.opportunities_by_chain["Ethereum"] += 1
                opportunity.metadata['chain'] = 'ETHEREUM'
                
                # Enhanced analysis
                await self._perform_enhanced_analysis(opportunity)
                
                # Log analyzed opportunity
                await self._log_analyzed_opportunity(opportunity, "ETHEREUM", "ETH")
                
                # Add to dashboard with proper error handling
                await self._add_to_dashboard_safe(opportunity)
                
                # Execute trading if recommended
                await self._evaluate_for_trading(opportunity)
                
            except Exception as e:
                self.logger.error(f"Error handling Ethereum opportunity: {e}")






    async def _handle_base_opportunity(self, opportunity: TradingOpportunity) -> None:
            """
            Handle Base opportunity with full analysis and trading.
            
            Args:
                opportunity: The Base trading opportunity to process
            """
            try:
                self.opportunities_by_chain["Base"] += 1
                opportunity.metadata['chain'] = 'BASE'
                
                await self._perform_enhanced_analysis(opportunity)
                await self._log_analyzed_opportunity(opportunity, "BASE", "ETH")
                
                # Add to dashboard with proper error handling
                await self._add_to_dashboard_safe(opportunity)
                
                await self._evaluate_for_trading(opportunity)
                
            except Exception as e:
                self.logger.error(f"Error handling Base opportunity: {e}")
            



    async def _handle_solana_pump_opportunity(self, opportunity: TradingOpportunity) -> None:
            """
            Handle Solana Pump.fun opportunity.
            
            Args:
                opportunity: The Solana Pump.fun trading opportunity to process
            """
            try:
                self.opportunities_by_chain["Solana-Pump"] += 1
                opportunity.metadata['chain'] = 'SOLANA-PUMP'
                opportunity.metadata['solana_source'] = 'Pump.fun'
                
                await self._perform_enhanced_analysis(opportunity)
                await self._log_analyzed_opportunity(opportunity, "SOLANA-PUMP", "SOL")
                
                # Add to dashboard with proper error handling
                await self._add_to_dashboard_safe(opportunity)
                
            except Exception as e:
                self.logger.error(f"Error handling Solana Pump opportunity: {e}")



    async def _handle_solana_jupiter_opportunity(self, opportunity: TradingOpportunity) -> None:
            """
            Handle Solana Jupiter opportunity.
            
            Args:
                opportunity: The Solana Jupiter trading opportunity to process
            """
            try:
                self.opportunities_by_chain["Solana-Jupiter"] += 1
                opportunity.metadata['chain'] = 'SOLANA-JUPITER'
                opportunity.metadata['solana_source'] = 'Jupiter'
                
                await self._perform_enhanced_analysis(opportunity)
                await self._log_analyzed_opportunity(opportunity, "SOLANA-JUPITER", "SOL")
                
                # Add to dashboard with proper error handling
                await self._add_to_dashboard_safe(opportunity)
                
            except Exception as e:
                self.logger.error(f"Error handling Solana Jupiter opportunity: {e}")





    async def _perform_enhanced_analysis(self, opportunity: TradingOpportunity) -> None:
        """Perform complete enhanced analysis on opportunity with graceful degradation."""
        try:
            self.analysis_stats["total_analyzed"] += 1
            
            # Initialize default analysis objects if they don't exist
            if not hasattr(opportunity, 'contract_analysis') or not opportunity.contract_analysis:
                from models.token import ContractAnalysis
                opportunity.contract_analysis = ContractAnalysis()
                
            if not hasattr(opportunity, 'social_metrics') or not opportunity.social_metrics:
                from models.token import SocialMetrics
                opportunity.social_metrics = SocialMetrics()
            
            # Contract analysis (for EVM chains only, and only if analyzer available)
            chain = opportunity.metadata.get('chain', '')
            if 'SOLANA' not in chain and self.contract_analyzer:
                try:
                    self.logger.debug(f"Running contract analysis for {opportunity.token.symbol}")
                    opportunity.contract_analysis = await self.contract_analyzer.analyze_contract(opportunity)
                except Exception as e:
                    self.logger.error(f"Contract analysis failed for {opportunity.token.symbol}: {e}")
                    # Keep default analysis object
            elif 'SOLANA' not in chain:
                self.logger.debug(f"Contract analysis skipped - no analyzer available")
                # Set basic risk assessment for EVM tokens without analysis
                from models.token import RiskLevel
                opportunity.contract_analysis.risk_level = RiskLevel.MEDIUM
                opportunity.contract_analysis.risk_score = 0.5
                opportunity.contract_analysis.analysis_notes.append("Contract analysis unavailable - Ethereum connection failed")
            
            # Social analysis (if analyzer available)
            if self.social_analyzer:
                try:
                    self.logger.debug(f"Running social analysis for {opportunity.token.symbol}")
                    opportunity.social_metrics = await self.social_analyzer.analyze_social_metrics(opportunity)
                except Exception as e:
                    self.logger.error(f"Social analysis failed for {opportunity.token.symbol}: {e}")
                    # Keep default social metrics
            else:
                self.logger.debug(f"Social analysis skipped - no analyzer available")
                # Set neutral social metrics
                opportunity.social_metrics.social_score = 0.3
                opportunity.social_metrics.sentiment_score = 0.0
            
            # Generate trading recommendation (if scorer available)
            if self.trading_scorer:
                try:
                    self.logger.debug(f"Generating recommendation for {opportunity.token.symbol}")
                    score = self.trading_scorer.score_opportunity(opportunity)
                    recommendation = self.trading_scorer.generate_recommendation(opportunity)
                except Exception as e:
                    self.logger.error(f"Trading scoring failed for {opportunity.token.symbol}: {e}")
                    # Generate basic recommendation
                    recommendation = {
                        'action': 'WATCH',
                        'confidence': 'LOW',
                        'score': 0.3,
                        'risk_level': opportunity.contract_analysis.risk_level.value,
                        'suggested_position': 0.0,
                        'reasons': ['Limited analysis available'],
                        'warnings': ['Analysis components unavailable']
                    }
            else:
                self.logger.debug(f"Trading scoring skipped - no scorer available")
                # Generate basic recommendation
                recommendation = {
                    'action': 'WATCH',
                    'confidence': 'LOW', 
                    'score': 0.3,
                    'risk_level': opportunity.contract_analysis.risk_level.value,
                    'suggested_position': 0.0,
                    'reasons': ['Basic monitoring only'],
                    'warnings': ['Full analysis unavailable']
                }
            
            # Update metadata
            opportunity.metadata['recommendation'] = recommendation
            opportunity.metadata['analysis_timestamp'] = datetime.now()
            opportunity.metadata['analysis_mode'] = 'full' if (self.contract_analyzer and self.social_analyzer and self.trading_scorer) else 'limited'
            
            # Update statistics
            action = recommendation.get('action', 'UNKNOWN')
            if action in self.analysis_stats["recommendations"]:
                self.analysis_stats["recommendations"][action] += 1
                
            if recommendation.get('confidence') == 'HIGH':
                self.analysis_stats["high_confidence"] += 1
            
            self.logger.debug(f"Analysis complete for {opportunity.token.symbol}: {action} ({recommendation.get('confidence')})")
            
        except Exception as e:
            self.logger.error(f"Enhanced analysis failed for {opportunity.token.symbol}: {e}")
            
            # Ensure we have minimal required objects
            try:
                from models.token import ContractAnalysis, SocialMetrics, RiskLevel
                
                if not hasattr(opportunity, 'contract_analysis'):
                    opportunity.contract_analysis = ContractAnalysis()
                opportunity.contract_analysis.risk_level = RiskLevel.HIGH
                opportunity.contract_analysis.risk_score = 0.8
                opportunity.contract_analysis.analysis_notes.append(f"Analysis failed: {str(e)}")
                
                if not hasattr(opportunity, 'social_metrics'):
                    opportunity.social_metrics = SocialMetrics()
                opportunity.social_metrics.social_score = 0.1
                
                # Set safe default recommendation
                opportunity.metadata['recommendation'] = {
                    'action': 'AVOID',
                    'confidence': 'HIGH',
                    'score': 0.0,
                    'risk_level': 'HIGH',
                    'suggested_position': 0.0,
                    'reasons': ['Analysis system error'],
                    'warnings': ['Could not analyze token safety']
                }
                opportunity.metadata['analysis_timestamp'] = datetime.now()
                opportunity.metadata['analysis_mode'] = 'error'
                
            except Exception as fallback_error:
                self.logger.error(f"Even fallback analysis failed: {fallback_error}")











    async def _evaluate_for_trading(self, opportunity: TradingOpportunity) -> None:
            """
            Evaluate opportunity for trading execution.
            
            Args:
                opportunity: The trading opportunity to evaluate
            """
            try:
                if not self.trading_executor:
                    self.logger.debug("Trading executor not available")
                    return
                    
                recommendation = opportunity.metadata.get('recommendation', {})
                action = recommendation.get('action')
                confidence = recommendation.get('confidence')
                
                # Execute on high-confidence strong buys
                if action == 'STRONG_BUY' and confidence == 'HIGH':
                    self.logger.info(f"EXECUTING TRADE: {opportunity.token.symbol}")
                    
                    trade_result = await self.trading_executor.execute_opportunity(opportunity)
                    
                    if trade_result:
                        self.analysis_stats["trades_executed"] += 1
                        self.logger.info(
                            f"TRADE EXECUTED: {opportunity.token.symbol} - Order ID: {trade_result.id}"
                        )
                        
                        # Broadcast to dashboard
                        if hasattr(self, 'dashboard_server') and self.dashboard_server:
                            try:
                                await self.dashboard_server.broadcast_message({
                                    "type": "trade_executed",
                                    "data": {
                                        "token_symbol": opportunity.token.symbol,
                                        "trade_id": trade_result.id,
                                        "status": trade_result.status.value
                                    }
                                })
                            except Exception as broadcast_error:
                                self.logger.warning(f"Failed to broadcast trade execution: {broadcast_error}")
                    else:
                        self.logger.info(
                            f"TRADE DECLINED: {opportunity.token.symbol} - Risk management"
                        )
                else:
                    self.logger.debug(
                        f"Trade evaluation: {opportunity.token.symbol} - {action} ({confidence})"
                    )
                        
            except Exception as e:
                self.logger.error(f"Trading evaluation failed: {e}")








    async def _log_analyzed_opportunity(self, opportunity: TradingOpportunity, chain: str, gas_token: str) -> None:
        """Log opportunity with complete analysis results."""
        try:
            recommendation = opportunity.metadata.get('recommendation', {})
            analysis = opportunity.contract_analysis
            social = opportunity.social_metrics
            
            self.logger.info(f"{chain} TARGET " + "=" * 60)
            
            # Fix chain counting
            chain_key = chain.replace('-', '_').replace('_', '-')
            if chain_key not in self.opportunities_by_chain:
                chain_key = chain
            count = self.opportunities_by_chain.get(chain_key, 0)
            
            self.logger.info(f"NEW {chain} OPPORTUNITY #{count}")
            self.logger.info(f"TOKEN: {opportunity.token.symbol}")
            self.logger.info(f"ADDRESS: {opportunity.token.address}")
            self.logger.info(f"CHAIN: {chain} ({gas_token})")
            
            if opportunity.token.name:
                self.logger.info(f"NAME: {opportunity.token.name}")
                
            self.logger.info("")
            self.logger.info("ENHANCED ANALYSIS RESULTS:")
            self.logger.info(f"|- SECURITY: [{analysis.risk_level.value.upper()}] (Score: {analysis.risk_score:.2f})")
            self.logger.info(f"|- SOCIAL: Score {social.social_score:.2f} | Sentiment {social.sentiment_score:.2f}")
            self.logger.info(f"|- LIQUIDITY: ${opportunity.liquidity.liquidity_usd:,.0f}")
            
            # Recommendation
            action = recommendation.get('action', 'UNKNOWN')
            confidence = recommendation.get('confidence', 'UNKNOWN')
            score = recommendation.get('score', 0.0)
            
            self.logger.info(f"|- RECOMMENDATION: {action} ({confidence} confidence, score: {score:.2f})")
            
            # Trading decision
            if self.trading_executor and action == 'STRONG_BUY' and confidence == 'HIGH':
                self.logger.info(f"|- TRADING: ✅ QUALIFIED FOR EXECUTION")
            else:
                self.logger.info(f"|- TRADING: 🔍 Manual review or evaluation only")
                
            self.logger.info("=" * 80)
            
        except Exception as e:
            self.logger.error(f"Error logging opportunity: {e}")
            
    async def _report_statistics(self) -> None:
        """Report enhanced system statistics."""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # Report every 30 seconds
                
                uptime = datetime.now() - self.start_time
                analysis_rate = self.analysis_stats["total_analyzed"] / max(uptime.total_seconds() / 60, 1)
                
                self.logger.info("📊 FULL ENHANCED SYSTEM STATISTICS:")
                self.logger.info(f"   Uptime: {uptime}")
                self.logger.info(f"   Analysis Rate: {analysis_rate:.1f}/min")
                self.logger.info(f"   Total Analyzed: {self.analysis_stats['total_analyzed']}")
                self.logger.info(f"   High Confidence: {self.analysis_stats['high_confidence']}")
                self.logger.info(f"   Trades Executed: {self.analysis_stats['trades_executed']}")
                
                # Chain breakdown
                self.logger.info("   Chain Opportunities:")
                for chain, count in self.opportunities_by_chain.items():
                    if count > 0:
                        self.logger.info(f"     {chain}: {count}")
                        
                # Recommendation breakdown
                self.logger.info("   Recommendations:")
                for action, count in self.analysis_stats["recommendations"].items():
                    if count > 0:
                        self.logger.info(f"     {action}: {count}")
                        
                # Portfolio summary
                if self.trading_executor:
                    portfolio = self.trading_executor.get_portfolio_summary()
                    if portfolio['total_positions'] > 0 or portfolio['total_trades'] > 0:
                        self.logger.info(f"   Portfolio: {portfolio['total_positions']} positions, {portfolio['success_rate']:.1f}% success rate")
                        
                # Web dashboard status
                if self.dashboard_server:
                    self.logger.info(f"   Dashboard: {len(self.dashboard_server.connected_clients)} connected clients")
                    
                # Update dashboard
                if self.dashboard_server:
                    await self.dashboard_server.update_analysis_rate(int(analysis_rate))
                    
            except Exception as e:
                self.logger.error(f"Statistics reporting error: {e}")
                await asyncio.sleep(60)

    async def _add_to_dashboard_safe(self, opportunity: TradingOpportunity) -> None:
        """
        Safely add opportunity to dashboard with comprehensive error handling.
        
        Args:
            opportunity: The trading opportunity to add to dashboard
            
        Note:
            This method will not raise exceptions - dashboard errors won't stop the main system
        """
        try:
            if not self.dashboard_server:
                self.logger.debug("Dashboard server not initialized - skipping update")
                return
                
            # Validate opportunity has required data
            if not opportunity or not opportunity.token:
                self.logger.warning("Invalid opportunity data for dashboard")
                return
                
            # Add to dashboard
            await self.dashboard_server.add_opportunity(opportunity)
            
            # Log success
            token_symbol = opportunity.token.symbol or "UNKNOWN"
            self.logger.debug(f"Added {token_symbol} to dashboard queue")
            
            # Update dashboard statistics
            if hasattr(self.dashboard_server, 'stats'):
                self.dashboard_server.stats['total_opportunities'] += 1
                
        except AttributeError as e:
            self.logger.error(f"Dashboard server missing method: {e}")
        except asyncio.CancelledError:
            # Don't log cancellation during shutdown
            raise
        except Exception as e:
            self.logger.error(f"Failed to add opportunity to dashboard: {e}")
            # Continue without dashboard update - don't interrupt main flow








    def _log_system_info(self) -> None:
        """Log complete system information."""
        self.logger.info("FULL ENHANCED MULTI-CHAIN DEX SNIPING SYSTEM")
        self.logger.info("Features: Analysis + Trading + Web Dashboard")
        self.logger.info("")
        self.logger.info("MONITORING CONFIGURATION:")
        self.logger.info("  Ethereum: Uniswap V2 (5s intervals)")
        self.logger.info("  Base: Uniswap V2 (2s intervals)")
        self.logger.info("  Solana: Pump.fun + Jupiter (5s + 10s)")
        self.logger.info("")
        self.logger.info("ANALYSIS FEATURES:")
        self.logger.info("  - Contract security analysis")
        self.logger.info("  - Honeypot detection")
        self.logger.info("  - Social sentiment scoring")
        self.logger.info("  - Intelligent recommendations")
        self.logger.info("  - Risk-based position sizing")
        self.logger.info("")
        self.logger.info("TRADING FEATURES:")
        self.logger.info("  - Automated execution (configurable)")
        self.logger.info("  - Risk management")
        self.logger.info("  - Stop loss / Take profit")
        self.logger.info("  - Position tracking")
        self.logger.info("  - Multi-chain support")
        self.logger.info("")
        self.logger.info("WEB DASHBOARD FEATURES:")
        self.logger.info("  - Real-time opportunity monitoring")
        self.logger.info("  - Live trading interface")
        self.logger.info("  - Portfolio tracking")
        self.logger.info("  - Performance analytics")
        self.logger.info("  - WebSocket real-time updates")
        self.logger.info("")
        self.logger.info("🌐 Access Dashboard: http://localhost:8000")
        self.logger.info("-" * 80)
        
    def stop(self) -> None:
        """Stop the full system."""
        self.logger.info("STOPPING full enhanced system...")
        self.is_running = False
        
        for monitor in self.monitors:
            monitor.stop()
            
        if self.web_server_task:
            self.web_server_task.cancel()
            
    async def _cleanup(self) -> None:
        """Cleanup all system resources."""
        try:
            self.logger.info("Cleaning up full enhanced system...")
            
            # Cleanup analyzers
            if self.contract_analyzer:
                await self.contract_analyzer.cleanup()
            if self.social_analyzer:
                await self.social_analyzer.cleanup()
                
            # Cleanup trading system
            if self.trading_executor:
                # Save state, close positions, etc.
                pass
                
            # Cleanup monitors
            for monitor in self.monitors:
                await monitor.cleanup()
                
            # Cancel web server
            if self.web_server_task:
                self.web_server_task.cancel()
                
            self.logger.info("Full system cleanup complete")
            
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

async def main():
    """Main entry point for the full enhanced system."""
    system = FullEnhancedSystem()
    
    try:
        await system.start()
    except KeyboardInterrupt:
        print("\n⚠️ Shutdown requested by user")
        system.stop()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        system.stop()
        raise

if __name__ == "__main__":
    asyncio.run(main())