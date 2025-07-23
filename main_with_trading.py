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
        """Initialize Phase 2 analysis components."""
        try:
            self.logger.info("INITIALIZING Phase 2 analyzers...")
            
            # Initialize Web3 for contract analysis
            from config.settings import settings
            self.w3 = Web3(Web3.HTTPProvider(settings.networks.ethereum_rpc_url))
            
            if not self.w3.is_connected():
                raise ConnectionError("Failed to connect to Ethereum for analysis")
                
            # Initialize analyzers
            self.contract_analyzer = ContractAnalyzer(self.w3)
            await self.contract_analyzer.initialize()
            
            self.social_analyzer = SocialAnalyzer()
            await self.social_analyzer.initialize()
            
            self.trading_scorer = TradingScorer()
            
            self.logger.info("✅ Phase 2 analyzers initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize analyzers: {e}")
            raise
            
    async def _initialize_trading_system(self) -> None:
        """Initialize full trading system."""
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
            
            self.trading_executor = TradingExecutor(trade_config)
            await self.trading_executor.initialize()
            
            self.logger.info("✅ Full trading system initialized")
            self.logger.info(f"   - Auto Execute: {trade_config.auto_execute}")
            self.logger.info(f"   - Max Slippage: {trade_config.max_slippage * 100}%")
            self.logger.info(f"   - Position Size: {trade_config.position_size_eth} ETH")
            self.logger.info(f"   - Stop Loss: {trade_config.stop_loss_percentage * 100}%")
            self.logger.info(f"   - Take Profit: {trade_config.take_profit_percentage * 100}%")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading system: {e}")
            raise
            
    dashboard_server_instance = None

    # Update the FullEnhancedSystem class _initialize_web_dashboard method:

    async def _initialize_web_dashboard(self) -> None:
        """Initialize full web dashboard with FastAPI."""
        global dashboard_server_instance
        
        try:
            self.logger.info("INITIALIZING full web dashboard...")
            
            # Import the full dashboard server
            from api.dashboard_server import app, dashboard_server
            
            # Set the global reference so we can access it
            dashboard_server_instance = dashboard_server
            self.dashboard_server = dashboard_server
            
            # Connect trading executor
            self.dashboard_server.trading_executor = self.trading_executor
            await self.dashboard_server.initialize()
            
            # Start FastAPI web server
            import uvicorn
            
            config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=8000,
                log_level="info",
                access_log=False  # Reduce log noise
            )
            server = uvicorn.Server(config)
            
            # Start server in background task
            self.web_server_task = asyncio.create_task(server.serve())
            
            self.logger.info("✅ Full web dashboard initialized")
            self.logger.info("   🌐 Dashboard URL: http://localhost:8000")
            self.logger.info("   📊 Real-time WebSocket updates enabled")
            self.logger.info("   💹 Trading execution interface active")
            
            # Give the server a moment to start
            await asyncio.sleep(2)
            
        except Exception as e:
            self.logger.error(f"Failed to initialize web dashboard: {e}")
            self.logger.warning("Continuing without web dashboard - using console only")








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
                        eth_monitor = NewTokenMonitor(check_interval=interval)
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
                        base_monitor = BaseChainMonitor(check_interval=interval)
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
                pump_monitor = SolanaMonitor(check_interval=5.0)
                pump_monitor.add_callback(self._handle_solana_pump_opportunity)
                self.monitors.append(pump_monitor)
                self.logger.info("✅ Solana Pump.fun monitor")
            except Exception as e:
                self.logger.warning(f"Solana Pump.fun monitor failed: {e}")
                
            try:
                jupiter_monitor = JupiterSolanaMonitor(check_interval=10.0)
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
        """Handle Ethereum opportunity with full analysis and trading."""
        try:
            self.opportunities_by_chain["Ethereum"] += 1
            opportunity.metadata['chain'] = 'ETHEREUM'
            
            # Enhanced analysis
            await self._perform_enhanced_analysis(opportunity)
            
            # Log analyzed opportunity
            await self._log_analyzed_opportunity(opportunity, "ETHEREUM", "ETH")
            
            # IMPORTANT: Add to dashboard with proper error handling
            await self._add_to_dashboard_safe(opportunity)
            
            # Execute trading if recommended
            await self._evaluate_for_trading(opportunity)
            
        except Exception as e:
            self.logger.error(f"Error handling Ethereum opportunity: {e}")







    async def _handle_base_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Base opportunity with full analysis and trading."""
        try:
            self.opportunities_by_chain["Base"] += 1
            opportunity.metadata['chain'] = 'BASE'
            
            await self._perform_enhanced_analysis(opportunity)
            await self._log_analyzed_opportunity(opportunity, "BASE", "ETH")
            
            # IMPORTANT: Add to dashboard with proper error handling
            await self._add_to_dashboard_safe(opportunity)
            
            await self._evaluate_for_trading(opportunity)
            
        except Exception as e:
            self.logger.error(f"Error handling Base opportunity: {e}")
            



    async def _handle_solana_pump_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Solana Pump.fun opportunity."""
        try:
            self.opportunities_by_chain["Solana-Pump"] += 1
            opportunity.metadata['chain'] = 'SOLANA-PUMP'
            opportunity.metadata['solana_source'] = 'Pump.fun'
            
            await self._perform_enhanced_analysis(opportunity)
            await self._log_analyzed_opportunity(opportunity, "SOLANA-PUMP", "SOL")
            
            # IMPORTANT: Add to dashboard with proper error handling
            await self._add_to_dashboard_safe(opportunity)
            
        except Exception as e:
            self.logger.error(f"Error handling Solana Pump opportunity: {e}")



    async def _handle_solana_jupiter_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Solana Jupiter opportunity."""
        try:
            self.opportunities_by_chain["Solana-Jupiter"] += 1
            opportunity.metadata['chain'] = 'SOLANA-JUPITER'
            opportunity.metadata['solana_source'] = 'Jupiter'
            
            await self._perform_enhanced_analysis(opportunity)
            await self._log_analyzed_opportunity(opportunity, "SOLANA-JUPITER", "SOL")
            
            # IMPORTANT: Add to dashboard with proper error handling
            await self._add_to_dashboard_safe(opportunity)
            
        except Exception as e:
            self.logger.error(f"Error handling Solana Jupiter opportunity: {e}")





    async def _perform_enhanced_analysis(self, opportunity: TradingOpportunity) -> None:
        """Perform complete enhanced analysis on opportunity."""
        try:
            self.analysis_stats["total_analyzed"] += 1
            
            # Contract analysis (for EVM chains)
            if 'SOLANA' not in opportunity.metadata.get('chain', ''):
                opportunity.contract_analysis = await self.contract_analyzer.analyze_contract(opportunity)
            
            # Social analysis
            opportunity.social_metrics = await self.social_analyzer.analyze_social_metrics(opportunity)
            
            # Generate trading recommendation
            score = self.trading_scorer.score_opportunity(opportunity)
            recommendation = self.trading_scorer.generate_recommendation(opportunity)
            
            # Update metadata
            opportunity.metadata['recommendation'] = recommendation
            opportunity.metadata['analysis_timestamp'] = datetime.now()
            
            # Update statistics
            action = recommendation.get('action', 'UNKNOWN')
            if action in self.analysis_stats["recommendations"]:
                self.analysis_stats["recommendations"][action] += 1
                
            if recommendation.get('confidence') == 'HIGH':
                self.analysis_stats["high_confidence"] += 1
                
        except Exception as e:
            self.logger.error(f"Enhanced analysis failed: {e}")
            # Set safe defaults
            opportunity.contract_analysis.risk_level = RiskLevel.HIGH
            opportunity.metadata['recommendation'] = {
                'action': 'AVOID',
                'confidence': 'HIGH',
                'score': 0.0,
                'reasons': ['Analysis failed'],
                'warnings': ['Could not analyze token safety']
            }
            
    async def _evaluate_for_trading(self, opportunity: TradingOpportunity) -> None:
        """Evaluate opportunity for trading execution."""
        try:
            if not self.trading_executor:
                return
                
            recommendation = opportunity.metadata.get('recommendation', {})
            action = recommendation.get('action')
            confidence = recommendation.get('confidence')
            
            # Execute on high-confidence strong buys
            if action == 'STRONG_BUY' and confidence == 'HIGH':
                self.logger.info(f"🎯 EXECUTING TRADE: {opportunity.token.symbol}")
                
                trade_result = await self.trading_executor.execute_opportunity(opportunity)
                
                if trade_result:
                    self.analysis_stats["trades_executed"] += 1
                    self.logger.info(f"✅ TRADE EXECUTED: {opportunity.token.symbol} - Order ID: {trade_result.id}")
                    
                    # Broadcast to dashboard
                    if self.dashboard_server:
                        await self.dashboard_server.broadcast_message({
                            "type": "trade_executed",
                            "data": {
                                "token_symbol": opportunity.token.symbol,
                                "trade_id": trade_result.id,
                                "status": trade_result.status.value
                            }
                        })
                else:
                    self.logger.info(f"❌ TRADE DECLINED: {opportunity.token.symbol} - Risk management")
            else:
                self.logger.debug(f"Trade evaluation: {opportunity.token.symbol} - {action} ({confidence})")
                    
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
        """Safely add opportunity to dashboard with error handling."""
        try:
            # Try multiple ways to get the dashboard server
            dashboard = None
            
            # Method 1: Use instance variable
            if hasattr(self, 'dashboard_server') and self.dashboard_server:
                dashboard = self.dashboard_server
            
            # Method 2: Use global reference
            elif dashboard_server_instance:
                dashboard = dashboard_server_instance
            
            # Method 3: Import and use directly
            if not dashboard:
                try:
                    from api.dashboard_server import dashboard_server
                    dashboard = dashboard_server
                except ImportError:
                    pass
            
            if dashboard:
                await dashboard.add_opportunity(opportunity)
                self.logger.debug(f"✅ Added {opportunity.token.symbol} to dashboard")
            else:
                self.logger.warning("Dashboard server not available for opportunity update")
                
        except Exception as e:
            self.logger.error(f"Failed to add opportunity to dashboard: {e}")
            # Don't let dashboard errors stop the main system
                
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