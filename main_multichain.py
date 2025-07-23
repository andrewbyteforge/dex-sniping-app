# Enhanced main.py with Phase 2 analysis integration
"""
Enhanced main.py for multi-chain DEX sniping system with Phase 2 analysis.
Coordinates monitoring across Ethereum, Base, and Solana with intelligent analysis.
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

class MultiChainDexSnipingSystem:
    """
    Multi-chain DEX sniping system coordinator with Phase 2 analysis.
    Manages monitoring across Ethereum, Base, and Solana with intelligent analysis.
    """
    
    def __init__(self):
        """Initialize the multi-chain system with Phase 2 analysis."""
        self.logger = logger_manager.get_logger("MultiChainSystem")
        self.monitors: List = []
        self.is_running = False
        
        # Track opportunities by chain and source
        self.opportunities_by_chain: Dict[str, int] = {
            "Ethereum": 0,
            "Base": 0,
            "Solana-Pump": 0,      # Pump.fun source
            "Solana-Jupiter": 0    # Jupiter backup source
        }
        
        # Phase 2: Analysis tracking
        self.analysis_stats = {
            "total_analyzed": 0,
            "high_confidence": 0,
            "recommendations": {
                "STRONG_BUY": 0,
                "BUY": 0,
                "SMALL_BUY": 0,
                "WATCH": 0,
                "AVOID": 0
            }
        }
        
        self.start_time: datetime = None
        self.solana_sources_active = {"pump": False, "jupiter": False}
        
        # Phase 2: Initialize analyzers
        self.contract_analyzer: ContractAnalyzer = None
        self.social_analyzer: SocialAnalyzer = None
        self.trading_scorer: TradingScorer = None
        self.w3: Web3 = None  # Will be initialized for Ethereum analysis
        
    async def start(self) -> None:
        """Start the multi-chain monitoring system with Phase 2 analysis."""
        try:
            self.logger.info("STARTING MULTI-CHAIN DEX SNIPING SYSTEM - PHASE 2")
            self.logger.info("=" * 70)
            self.logger.info("ENHANCED: Multi-chain monitoring + intelligent analysis")
            self.logger.info("FEATURES: Contract analysis, social sentiment, risk scoring")
            self.start_time = datetime.now()
            self.is_running = True
            
            # Display configuration
            self._log_system_info()
            
            # Phase 2: Initialize analysis components
            await self._initialize_analyzers()
            
            # Initialize all chain monitors
            await self._initialize_monitors()
            
            # Start monitoring
            await self._run_monitoring_loop()
            
        except Exception as e:
            self.logger.error(f"FATAL ERROR in multi-chain system: {e}")
            raise
        finally:
            await self._cleanup()
            
    def stop(self) -> None:
        """Stop all chain monitors and analyzers."""
        self.logger.info("STOPPING multi-chain system...")
        self.is_running = False
        
        for monitor in self.monitors:
            monitor.stop()
            
    async def _initialize_analyzers(self) -> None:
        """Initialize Phase 2 analysis components."""
        try:
            self.logger.info("INITIALIZING Phase 2 analyzers...")
            
            # Initialize Web3 for contract analysis
            ethereum_rpc = multichain_settings.get_chain_config(ChainType.ETHEREUM).rpc_url
            self.w3 = Web3(Web3.HTTPProvider(ethereum_rpc))
            
            # Initialize analyzers
            self.contract_analyzer = ContractAnalyzer(self.w3)
            await self.contract_analyzer.initialize()
            
            self.social_analyzer = SocialAnalyzer()
            await self.social_analyzer.initialize()
            
            self.trading_scorer = TradingScorer()
            
            self.logger.info("SUCCESS: Phase 2 analyzers initialized")
            self.logger.info("  - Contract Analyzer: Security & honeypot detection")
            self.logger.info("  - Social Analyzer: Community sentiment analysis")
            self.logger.info("  - Trading Scorer: Opportunity scoring & recommendations")
            
        except Exception as e:
            self.logger.error(f"FAILED to initialize analyzers: {e}")
            raise
            
    async def _initialize_monitors(self) -> None:
        """Initialize monitors for all supported chains with dual Solana."""
        self.logger.info("INITIALIZING multi-chain monitors...")
        
        try:
            # Ethereum monitor
            eth_monitor = NewTokenMonitor(check_interval=5.0)
            eth_monitor.add_callback(self._handle_ethereum_opportunity)
            self.monitors.append(eth_monitor)
            
            # Base chain monitor
            base_monitor = BaseChainMonitor(check_interval=2.0)
            base_monitor.add_callback(self._handle_base_opportunity)
            self.monitors.append(base_monitor)
            
            # Solana monitor #1: Pump.fun (primary)
            pump_monitor = SolanaMonitor(check_interval=2.0)
            pump_monitor.add_callback(self._handle_pump_solana_opportunity)
            self.monitors.append(pump_monitor)
            
            # Solana monitor #2: Jupiter (backup)
            jupiter_monitor = JupiterSolanaMonitor(check_interval=5.0)
            jupiter_monitor.add_callback(self._handle_jupiter_solana_opportunity)
            self.monitors.append(jupiter_monitor)
            
            self.logger.info(f"SUCCESS: Initialized {len(self.monitors)} chain monitors")
            self.logger.info("  - Ethereum (Uniswap V2): 12s blocks, high quality")
            self.logger.info("  - Base (BaseSwap): 2s blocks, low fees")
            self.logger.info("  - Solana-Pump (Pump.fun): Real-time launches")
            self.logger.info("  - Solana-Jupiter (Backup): Verified tokens")
            
        except Exception as e:
            self.logger.error(f"FAILED to initialize monitors: {e}")
            raise
            
    async def _run_monitoring_loop(self) -> None:
        """Run all chain monitors concurrently."""
        self.logger.info("STARTING multi-chain monitoring with analysis...")
        
        # Start all monitors concurrently
        monitor_tasks = []
        for monitor in self.monitors:
            task = asyncio.create_task(monitor.start())
            monitor_tasks.append(task)
            
        try:
            while self.is_running and monitor_tasks:
                # Check monitor health
                done, pending = await asyncio.wait(
                    monitor_tasks, 
                    timeout=5.0, 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Handle completed monitors
                for task in done:
                    try:
                        await task
                    except Exception as e:
                        self.logger.error(f"Monitor failed: {e}")
                    monitor_tasks.remove(task)
                    
                # Log periodic status
                await self._log_periodic_status()
                
        except Exception as e:
            self.logger.error(f"Error in multi-chain monitoring loop: {e}")
        finally:
            # Cancel remaining tasks
            for task in monitor_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                        
    # Phase 2: Enhanced opportunity handlers with analysis
    async def _handle_ethereum_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Ethereum opportunities with Phase 2 analysis."""
        self.opportunities_by_chain["Ethereum"] += 1
        await self._analyze_and_log_opportunity(opportunity, "ETHEREUM", "ETH")
        
    async def _handle_base_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Base chain opportunities with Phase 2 analysis."""
        self.opportunities_by_chain["Base"] += 1
        await self._analyze_and_log_opportunity(opportunity, "BASE", "ETH")
        
    async def _handle_pump_solana_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Pump.fun Solana opportunities with Phase 2 analysis."""
        self.opportunities_by_chain["Solana-Pump"] += 1
        self.solana_sources_active["pump"] = True
        
        # Add source identifier to metadata
        opportunity.metadata["solana_source"] = "Pump.fun"
        await self._analyze_and_log_opportunity(opportunity, "SOLANA-PUMP", "SOL")
        
    async def _handle_jupiter_solana_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Jupiter Solana opportunities with Phase 2 analysis."""
        self.opportunities_by_chain["Solana-Jupiter"] += 1
        self.solana_sources_active["jupiter"] = True
        
        # Add source identifier to metadata
        opportunity.metadata["solana_source"] = "Jupiter"
        await self._analyze_and_log_opportunity(opportunity, "SOLANA-JUPITER", "SOL")
        
    async def _analyze_and_log_opportunity(self, opportunity: TradingOpportunity, chain: str, gas_token: str) -> None:
        """Phase 2: Analyze opportunity and log with intelligence."""
        try:
            # Run comprehensive analysis
            await self._analyze_opportunity(opportunity)
            
            # Log with analysis results
            await self._log_analyzed_opportunity(opportunity, chain, gas_token)
            
        except Exception as e:
            self.logger.error(f"Analysis failed for {opportunity.token.symbol}: {e}")
            # Fall back to basic logging
            await self._log_basic_opportunity(opportunity, chain, gas_token)
            
    async def _analyze_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Run comprehensive Phase 2 analysis on the opportunity."""
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
            self.logger.error(f"Detailed analysis failed: {e}")
            # Set default safe values
            opportunity.contract_analysis.risk_level = RiskLevel.HIGH
            opportunity.metadata['recommendation'] = {
                'action': 'AVOID',
                'confidence': 'HIGH',
                'score': 0.0,
                'reasons': ['Analysis failed'],
                'warnings': ['Could not analyze token safety']
            }
            
    async def _log_analyzed_opportunity(self, opportunity: TradingOpportunity, chain: str, gas_token: str) -> None:
        """Log opportunity with Phase 2 analysis results - Windows compatible."""
        try:
            total_ops = sum(self.opportunities_by_chain.values())
            
            # Handle emojis for Windows compatibility
            def clean_text(text):
                if text:
                    import re
                    return re.sub(r'[^\x00-\x7F]+', '[EMOJI]', str(text))
                return text
            
            token_symbol = clean_text(opportunity.token.symbol) or 'Unknown'
            token_name = clean_text(opportunity.token.name) if hasattr(opportunity.token, 'name') and opportunity.token.name else None
            
            # Get analysis results
            recommendation = opportunity.metadata.get('recommendation', {})
            action = recommendation.get('action', 'UNKNOWN')
            confidence = recommendation.get('confidence', 'UNKNOWN')
            score = recommendation.get('score', 0.0)
            risk_level = recommendation.get('risk_level', 'UNKNOWN')
            
            # Get risk and action emojis (safe for Windows)
            action_emoji = {
                'STRONG_BUY': '[STRONG_BUY]',
                'BUY': '[BUY]',
                'SMALL_BUY': '[SMALL_BUY]',
                'WATCH': '[WATCH]',
                'AVOID': '[AVOID]'
            }.get(action, '[UNKNOWN]')
            
            risk_emoji = {
                'LOW': '[LOW_RISK]',
                'MEDIUM': '[MED_RISK]',
                'HIGH': '[HIGH_RISK]',
                'CRITICAL': '[CRITICAL]'
            }.get(risk_level, '[UNKNOWN]')
            
            # Main opportunity header
            self.logger.info(f"{chain} TARGET " + "="*45)
            self.logger.info(f"NEW {chain} OPPORTUNITY #{total_ops}")
            self.logger.info(f"TOKEN: {token_symbol}")
            self.logger.info(f"ADDRESS: {opportunity.token.address}")
            self.logger.info(f"PAIR: {opportunity.liquidity.pair_address}")
            self.logger.info(f"DEX: {opportunity.liquidity.dex_name}")
            self.logger.info(f"CHAIN: {chain} ({gas_token})")
            self.logger.info(f"DETECTED: {opportunity.detected_at.strftime('%H:%M:%S')}")
            
            if token_name:
                self.logger.info(f"NAME: {token_name}")
            if hasattr(opportunity.token, 'total_supply') and opportunity.token.total_supply:
                self.logger.info(f"SUPPLY: {opportunity.token.total_supply:,}")
            
            # Phase 2: Analysis results
            self.logger.info("")
            self.logger.info("ANALYSIS RESULTS:")
            self.logger.info(f"|- SECURITY: {risk_emoji} (Risk: {risk_level})")
            
            # Contract analysis details (Windows-safe characters)
            if hasattr(opportunity, 'contract_analysis') and opportunity.contract_analysis:
                analysis = opportunity.contract_analysis
                if analysis.ownership_renounced:
                    self.logger.info("|  |- [OK] Ownership renounced")
                else:
                    self.logger.info("|  |- [WARN] Owner can control contract")
                    
                if not analysis.is_honeypot:
                    self.logger.info("|  |- [OK] No honeypot detected")
                else:
                    self.logger.info("|  |- [WARN] HONEYPOT DETECTED")
                    
                if analysis.liquidity_locked:
                    self.logger.info("|  '- [OK] Liquidity locked")
                else:
                    self.logger.info("|  '- [WARN] Liquidity not locked")
            
            # Social metrics
            if hasattr(opportunity, 'social_metrics') and opportunity.social_metrics:
                social = opportunity.social_metrics
                social_score = social.social_score or 0.0
                sentiment = social.sentiment_score or 0.0
                
                social_level = "HIGH" if social_score > 0.7 else "MEDIUM" if social_score > 0.4 else "LOW"
                sentiment_text = "Positive" if sentiment > 0.2 else "Negative" if sentiment < -0.2 else "Neutral"
                
                self.logger.info(f"|- SOCIAL: {social_level} (Score: {social_score:.2f})")
                self.logger.info(f"|  |- Sentiment: {sentiment_text} ({sentiment:+.2f})")
                
                if social.twitter_followers:
                    self.logger.info(f"|  |- Twitter: ~{social.twitter_followers} followers")
                if social.telegram_members:
                    self.logger.info(f"|  '- Telegram: ~{social.telegram_members} members")
            
            # Trading recommendation
            self.logger.info(f"'- RECOMMENDATION: {action_emoji}")
            self.logger.info(f"   |- Action: {action}")
            self.logger.info(f"   |- Confidence: {confidence}")
            self.logger.info(f"   |- Score: {score:.2f}/1.0")
            
            suggested_position = recommendation.get('suggested_position', 0)
            if suggested_position > 0:
                self.logger.info(f"   '- Suggested Position: {suggested_position:.3f} {gas_token}")
            else:
                self.logger.info(f"   '- Suggested Position: NONE")
            
            # Show reasons and warnings (Windows-safe)
            reasons = recommendation.get('reasons', [])
            if reasons:
                self.logger.info("")
                self.logger.info("REASONS:")
                for reason in reasons[:3]:  # Show top 3 reasons
                    # Replace Unicode characters with ASCII-safe alternatives
                    safe_reason = reason.replace("✓", "[OK]").replace("⚠", "[WARN]").replace("🚨", "[CRITICAL]")
                    self.logger.info(f"  {safe_reason}")
            
            warnings = recommendation.get('warnings', [])
            if warnings:
                self.logger.info("")
                self.logger.info("WARNINGS:")
                for warning in warnings[:3]:  # Show top 3 warnings
                    # Replace Unicode characters with ASCII-safe alternatives
                    safe_warning = warning.replace("✓", "[OK]").replace("⚠", "[WARN]").replace("🚨", "[CRITICAL]")
                    self.logger.info(f"  {safe_warning}")
            
            # Chain-specific information
            if "SOLANA" in chain:
                source = opportunity.metadata.get('solana_source', 'Unknown')
                self.logger.info(f"")
                self.logger.info(f"SOURCE: {source}")
                
                market_cap = opportunity.metadata.get('market_cap_usd', 0)
                if market_cap:
                    self.logger.info(f"MARKET CAP: ${market_cap:,.2f}")
                    
                volume_24h = opportunity.metadata.get('volume_24h_usd', 0)
                if volume_24h:
                    self.logger.info(f"24H VOLUME: ${volume_24h:,.2f}")
            
            self.logger.info(f"{chain} TARGET " + "="*45)
            
        except Exception as e:
            self.logger.error(f"Error logging opportunity: {e}")
            # Fallback to basic logging
            await self._log_basic_opportunity(opportunity, chain, gas_token)









    async def _log_basic_opportunity(self, opportunity: TradingOpportunity, chain: str, gas_token: str) -> None:
        """Fallback to basic logging if analysis fails."""
        total_ops = sum(self.opportunities_by_chain.values())
        
        def clean_text(text):
            if text:
                import re
                return re.sub(r'[^\x00-\x7F]+', '[EMOJI]', str(text))
            return text
        
        token_symbol = clean_text(opportunity.token.symbol) or 'Unknown'
        
        self.logger.info(f"{chain} TARGET " + "="*45)
        self.logger.info(f"NEW {chain} OPPORTUNITY #{total_ops}")
        self.logger.info(f"TOKEN: {token_symbol}")
        self.logger.info(f"ADDRESS: {opportunity.token.address}")
        self.logger.info(f"CHAIN: {chain} ({gas_token})")
        self.logger.info(f"DETECTED: {opportunity.detected_at.strftime('%H:%M:%S')}")
        self.logger.info("ANALYSIS: FAILED - Manual review required")
        self.logger.info(f"{chain} TARGET " + "="*45)
        
    async def _log_periodic_status(self) -> None:
        """Log multi-chain system status with Phase 2 analysis stats."""
        if not self.start_time:
            return
            
        uptime = datetime.now() - self.start_time
        
        # Log every 5 minutes
        if uptime.total_seconds() % 300 < 5:
            total_opportunities = sum(self.opportunities_by_chain.values())
            
            self.logger.info("MULTI-CHAIN STATUS " + "="*30)
            self.logger.info(f"UPTIME: {str(uptime).split('.')[0]}")
            self.logger.info(f"TOTAL OPPORTUNITIES: {total_opportunities}")
            
            # Phase 2: Analysis statistics
            analyzed = self.analysis_stats["total_analyzed"]
            high_conf = self.analysis_stats["high_confidence"]
            
            self.logger.info("ANALYSIS STATS:")
            self.logger.info(f"  Total Analyzed: {analyzed}")
            self.logger.info(f"  High Confidence: {high_conf}")
            
            # Recommendation breakdown
            recs = self.analysis_stats["recommendations"]
            if any(recs.values()):
                self.logger.info("  Recommendations:")
                for action, count in recs.items():
                    if count > 0:
                        self.logger.info(f"    {action}: {count}")
            
            # Chain breakdown
            solana_pump = self.opportunities_by_chain["Solana-Pump"]
            solana_jupiter = self.opportunities_by_chain["Solana-Jupiter"]
            total_solana = solana_pump + solana_jupiter
            
            self.logger.info("OPPORTUNITIES BY CHAIN:")
            eth_count = self.opportunities_by_chain["Ethereum"]
            base_count = self.opportunities_by_chain["Base"]
            
            if total_opportunities > 0:
                eth_pct = (eth_count / total_opportunities * 100)
                base_pct = (base_count / total_opportunities * 100)
                solana_pct = (total_solana / total_opportunities * 100)
                
                self.logger.info(f"  Ethereum: {eth_count} ({eth_pct:.1f}%)")
                self.logger.info(f"  Base: {base_count} ({base_pct:.1f}%)")
                self.logger.info(f"  Solana Total: {total_solana} ({solana_pct:.1f}%)")
                
    def _log_system_info(self) -> None:
        """Log multi-chain system configuration with Phase 2 features."""
        self.logger.info("MULTI-CHAIN CONFIGURATION:")
        
        for chain_type in multichain_settings.get_active_chains():
            if chain_type == ChainType.SOLANA:
                self.logger.info(f"  SOLANA: Dual monitoring system")
                self.logger.info(f"    Primary: Pump.fun API (real-time launches)")
                self.logger.info(f"    Backup: Jupiter API (verified tokens)")
                self.logger.info(f"    Max Position: {multichain_settings.max_position_per_chain[chain_type]} SOL")
            else:
                config = multichain_settings.get_chain_config(chain_type)
                self.logger.info(f"  {config.name.upper()}: {config.block_time}s blocks")
                self.logger.info(f"    Max Position: {multichain_settings.max_position_per_chain[chain_type]} {config.gas_token}")
                self.logger.info(f"    Min Liquidity: ${config.min_liquidity_usd:,}")
        
        # Phase 2 features
        self.logger.info("")
        self.logger.info("PHASE 2 ANALYSIS FEATURES:")
        self.logger.info("  - Contract security analysis")
        self.logger.info("  - Honeypot detection")
        self.logger.info("  - Social sentiment scoring")
        self.logger.info("  - Intelligent recommendations")
        self.logger.info("  - Risk-based position sizing")
                
        self.logger.info("-" * 70)
        
    async def _cleanup(self) -> None:
        """Cleanup all chain monitors and analyzers."""
        self.logger.info("CLEANING UP multi-chain system...")
        
        try:
            # Stop monitors
            for monitor in self.monitors:
                monitor.stop()
                
            # Cleanup analyzers
            if self.contract_analyzer:
                await self.contract_analyzer.cleanup()
            if self.social_analyzer:
                await self.social_analyzer.cleanup()
                
            if self.start_time:
                runtime = datetime.now() - self.start_time
                total_ops = sum(self.opportunities_by_chain.values())
                
                self.logger.info("FINAL MULTI-CHAIN STATISTICS:")
                self.logger.info(f"  TOTAL RUNTIME: {str(runtime).split('.')[0]}")
                self.logger.info(f"  TOTAL OPPORTUNITIES: {total_ops}")
                self.logger.info(f"  TOTAL ANALYZED: {self.analysis_stats['total_analyzed']}")
                
                # Show detailed breakdown
                for chain, count in self.opportunities_by_chain.items():
                    if count > 0:
                        rate = count / (runtime.total_seconds() / 3600) if runtime.total_seconds() > 0 else 0
                        self.logger.info(f"  {chain}: {count} ({rate:.2f}/hour)")
                
                # Show recommendation summary
                recs = self.analysis_stats["recommendations"]
                if any(recs.values()):
                    self.logger.info("RECOMMENDATION SUMMARY:")
                    for action, count in recs.items():
                        if count > 0:
                            self.logger.info(f"  {action}: {count}")
                    
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
        finally:
            self.logger.info("MULTI-CHAIN SYSTEM SHUTDOWN COMPLETE")


async def main():
    """Main entry point for Phase 2 multi-chain system."""
    system = None
    
    try:
        system = MultiChainDexSnipingSystem()
        await system.start()
        
    except KeyboardInterrupt:
        print("\nRECEIVED INTERRUPT SIGNAL")
        if system:
            system.stop()
            
    except Exception as e:
        logger = logger_manager.get_logger("main")
        logger.error(f"FATAL ERROR: {e}")
        if system:
            system.stop()
        raise
        
    finally:
        print("PHASE 2 MULTI-CHAIN SYSTEM STOPPED")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSYSTEM INTERRUPTED")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
    finally:
        print("CHECK LOGS FOR DETAILED ANALYSIS INFORMATION")