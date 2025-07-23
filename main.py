# Enhanced main.py with multi-chain support
"""
Enhanced main.py for multi-chain DEX sniping system.
Coordinates monitoring across Ethereum, Base, and Solana.
"""

import asyncio
import sys
import os
from typing import List, Dict
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger_manager
from monitors.new_token_monitor import NewTokenMonitor
from monitors.base_chain_monitor import BaseChainMonitor
from monitors.solana_monitor import SolanaMonitor
from models.token import TradingOpportunity
from config.chains import multichain_settings, ChainType

class MultiChainDexSnipingSystem:
    """
    Multi-chain DEX sniping system coordinator.
    Manages monitoring across Ethereum, Base, and Solana simultaneously.
    """
    
    def __init__(self):
        """Initialize the multi-chain system."""
        self.logger = logger_manager.get_logger("MultiChainSystem")
        self.monitors: List = []
        self.is_running = False
        
        # Track opportunities by chain
        self.opportunities_by_chain: Dict[str, int] = {
            "Ethereum": 0,
            "Base": 0,
            "Solana": 0
        }
        
        self.start_time: datetime = None
        
    async def start(self) -> None:
        """Start the multi-chain monitoring system."""
        try:
            self.logger.info("STARTING MULTI-CHAIN DEX SNIPING SYSTEM - PHASE 1.5")
            self.logger.info("=" * 70)
            self.start_time = datetime.now()
            self.is_running = True
            
            # Display configuration
            self._log_system_info()
            
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
        """Stop all chain monitors."""
        self.logger.info("STOPPING multi-chain system...")
        self.is_running = False
        
        for monitor in self.monitors:
            monitor.stop()
            
    async def _initialize_monitors(self) -> None:
        """Initialize monitors for all supported chains."""
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
            
            # Solana monitor
            solana_monitor = SolanaMonitor(check_interval=1.0)
            solana_monitor.add_callback(self._handle_solana_opportunity)
            self.monitors.append(solana_monitor)
            
            self.logger.info(f"SUCCESS: Initialized {len(self.monitors)} chain monitors")
            self.logger.info("  - Ethereum (Uniswap V2): 12s blocks, high quality")
            self.logger.info("  - Base (BaseSwap): 2s blocks, low fees")
            self.logger.info("  - Solana (Pump.fun): <1s, high volume")
            
        except Exception as e:
            self.logger.error(f"FAILED to initialize monitors: {e}")
            raise
            
    async def _run_monitoring_loop(self) -> None:
        """Run all chain monitors concurrently."""
        self.logger.info("STARTING multi-chain monitoring...")
        
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
                        
    async def _handle_ethereum_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Ethereum opportunities."""
        self.opportunities_by_chain["Ethereum"] += 1
        await self._log_opportunity(opportunity, "ETHEREUM", "ETH")
        
    async def _handle_base_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Base chain opportunities."""
        self.opportunities_by_chain["Base"] += 1
        await self._log_opportunity(opportunity, "BASE", "ETH")
        
    async def _handle_solana_opportunity(self, opportunity: TradingOpportunity) -> None:
        """Handle Solana opportunities."""
        self.opportunities_by_chain["Solana"] += 1
        await self._log_opportunity(opportunity, "SOLANA", "SOL")
        
    async def _log_opportunity(self, opportunity: TradingOpportunity, chain: str, gas_token: str) -> None:
        """Log opportunity with chain-specific formatting."""
        total_ops = sum(self.opportunities_by_chain.values())
        
        self.logger.info(f"{chain} TARGET " + "="*45)
        self.logger.info(f"NEW {chain} OPPORTUNITY #{total_ops}")
        self.logger.info(f"TOKEN: {opportunity.token.symbol or 'Unknown'}")
        self.logger.info(f"ADDRESS: {opportunity.token.address}")
        self.logger.info(f"PAIR: {opportunity.liquidity.pair_address}")
        self.logger.info(f"DEX: {opportunity.liquidity.dex_name}")
        self.logger.info(f"CHAIN: {chain} ({gas_token})")
        self.logger.info(f"DETECTED: {opportunity.detected_at.strftime('%H:%M:%S')}")
        
        if opportunity.token.name:
            self.logger.info(f"NAME: {opportunity.token.name}")
        if opportunity.token.total_supply:
            self.logger.info(f"SUPPLY: {opportunity.token.total_supply:,}")
            
        # Chain-specific information
        if chain == "SOLANA":
            market_cap = opportunity.metadata.get('market_cap_usd', 0)
            if market_cap:
                self.logger.info(f"MARKET CAP: ${market_cap:,.2f}")
            reply_count = opportunity.metadata.get('reply_count', 0)
            if reply_count:
                self.logger.info(f"SOCIAL ACTIVITY: {reply_count} replies")
                
        self.logger.info(f"{chain} TARGET " + "="*45)
        
    async def _log_periodic_status(self) -> None:
        """Log multi-chain system status."""
        if not self.start_time:
            return
            
        uptime = datetime.now() - self.start_time
        
        # Log every 5 minutes
        if uptime.total_seconds() % 300 < 5:
            total_opportunities = sum(self.opportunities_by_chain.values())
            
            self.logger.info("MULTI-CHAIN STATUS " + "="*30)
            self.logger.info(f"UPTIME: {str(uptime).split('.')[0]}")
            self.logger.info(f"TOTAL OPPORTUNITIES: {total_opportunities}")
            
            for chain, count in self.opportunities_by_chain.items():
                percentage = (count / total_opportunities * 100) if total_opportunities > 0 else 0
                self.logger.info(f"  {chain}: {count} ({percentage:.1f}%)")
                
            self.logger.info("MONITORS:")
            for monitor in self.monitors:
                status = monitor.get_status()
                self.logger.info(f"  {status['name']}: {'Running' if status['is_running'] else 'Stopped'}")
                
    def _log_system_info(self) -> None:
        """Log multi-chain system configuration."""
        self.logger.info("MULTI-CHAIN CONFIGURATION:")
        
        for chain_type in multichain_settings.get_active_chains():
            if chain_type == ChainType.SOLANA:
                self.logger.info(f"  SOLANA: Pump.fun API + Raydium")
                self.logger.info(f"    Max Position: {multichain_settings.max_position_per_chain[chain_type]} SOL")
            else:
                config = multichain_settings.get_chain_config(chain_type)
                self.logger.info(f"  {config.name.upper()}: {config.block_time}s blocks")
                self.logger.info(f"    Max Position: {multichain_settings.max_position_per_chain[chain_type]} {config.gas_token}")
                self.logger.info(f"    Min Liquidity: ${config.min_liquidity_usd:,}")
                
        self.logger.info("-" * 70)
        
    async def _cleanup(self) -> None:
        """Cleanup all chain monitors."""
        self.logger.info("CLEANING UP multi-chain system...")
        
        try:
            for monitor in self.monitors:
                monitor.stop()
                
            if self.start_time:
                runtime = datetime.now() - self.start_time
                total_ops = sum(self.opportunities_by_chain.values())
                
                self.logger.info("FINAL MULTI-CHAIN STATISTICS:")
                self.logger.info(f"  TOTAL RUNTIME: {str(runtime).split('.')[0]}")
                self.logger.info(f"  TOTAL OPPORTUNITIES: {total_ops}")
                
                for chain, count in self.opportunities_by_chain.items():
                    rate = count / (runtime.total_seconds() / 3600) if runtime.total_seconds() > 0 else 0
                    self.logger.info(f"  {chain}: {count} ({rate:.2f}/hour)")
                    
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
        finally:
            self.logger.info("MULTI-CHAIN SYSTEM SHUTDOWN COMPLETE")


async def main():
    """Main entry point for multi-chain system."""
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
        print("MULTI-CHAIN SYSTEM STOPPED")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSYSTEM INTERRUPTED")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
    finally:
        print("CHECK LOGS FOR DETAILED INFORMATION")