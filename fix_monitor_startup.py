#!/usr/bin/env python3
"""
Monitor initialization fix to ensure opportunities are generated for the dashboard.

This file addresses the root cause: monitors are initialized but not started,
which is why no opportunities appear on the dashboard.

File: fix_monitor_startup.py
Class: MonitorStartupFix
Methods: fix_monitor_initialization, start_all_monitors, generate_test_opportunities
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger_manager
from models.token import TradingOpportunity, TokenInfo, LiquidityInfo, ContractAnalysis, SocialMetrics, RiskLevel
from core.enhanced_trading_system import EnhancedTradingSystem


class MonitorStartupFix:
    """
    Fix class to ensure monitors are properly started and generating opportunities.
    
    The core issue is that monitors are initialized but not started in the main loop,
    causing the dashboard to show no opportunities.
    """
    
    def __init__(self) -> None:
        """Initialize the monitor startup fix."""
        self.logger = logger_manager.get_logger("MonitorStartupFix")
        self.system: Optional[EnhancedTradingSystem] = None
        self.monitor_tasks: List[asyncio.Task] = []
        self.is_running: bool = False
    
    async def fix_monitor_initialization(
        self, 
        auto_trading: bool = False,
        disable_dashboard: bool = False,
        generate_test_data: bool = True
    ) -> None:
        """
        Fix the monitor initialization by properly starting all monitors.
        
        Args:
            auto_trading: Enable automated trading
            disable_dashboard: Disable web dashboard
            generate_test_data: Generate test opportunities for demonstration
            
        Raises:
            Exception: If system initialization fails
        """
        try:
            self.logger.info("🔧 FIXING MONITOR INITIALIZATION...")
            self.logger.info("=" * 60)
            
            # Initialize the enhanced trading system
            self.system = EnhancedTradingSystem(
                auto_trading_enabled=auto_trading,
                disable_dashboard=disable_dashboard,
                disable_telegram=True  # Disable for testing
            )
            
            # Initialize the system components
            await self.system.initialize()
            
            # FIX: Start all monitors properly
            await self._start_all_monitors()
            
            # Generate test opportunities if requested
            if generate_test_data:
                await self._generate_test_opportunities()
            
            # Start the main monitoring loop
            await self._run_monitoring_loop()
            
        except Exception as e:
            self.logger.error(f"❌ Monitor fix failed: {e}")
            raise
        finally:
            await self._cleanup()
    
    async def _start_all_monitors(self) -> None:
        """
        Start all monitors with proper error handling.
        
        This is the KEY FIX - ensures monitors are actually started
        and running their monitoring loops.
        """
        try:
            self.logger.info("🚀 STARTING ALL MONITORS...")
            
            monitors_to_start = []
            
            # Collect all available monitors
            if hasattr(self.system, 'new_token_monitor') and self.system.new_token_monitor:
                monitors_to_start.append(("Ethereum NewToken", self.system.new_token_monitor))
            
            if hasattr(self.system, 'base_chain_monitor') and self.system.base_chain_monitor:
                monitors_to_start.append(("Base Chain", self.system.base_chain_monitor))
            
            if hasattr(self.system, 'solana_monitor') and self.system.solana_monitor:
                monitors_to_start.append(("Solana", self.system.solana_monitor))
            
            if hasattr(self.system, 'jupiter_monitor') and self.system.jupiter_monitor:
                monitors_to_start.append(("Jupiter", self.system.jupiter_monitor))
            
            if hasattr(self.system, 'raydium_monitor') and self.system.raydium_monitor:
                monitors_to_start.append(("Raydium", self.system.raydium_monitor))
            
            # Start each monitor in a separate task
            for monitor_name, monitor in monitors_to_start:
                try:
                    self.logger.info(f"   🔌 Starting {monitor_name} monitor...")
                    
                    # Create a task for this monitor's start() method
                    task = asyncio.create_task(
                        monitor.start(),
                        name=f"Monitor_{monitor_name}"
                    )
                    
                    # Store reference to monitor object for cleanup
                    task._monitor_obj = monitor
                    
                    self.monitor_tasks.append(task)
                    self.logger.info(f"   ✅ {monitor_name} monitor task created")
                    
                except Exception as e:
                    self.logger.error(f"   ❌ Failed to start {monitor_name} monitor: {e}")
            
            self.logger.info(f"✅ Started {len(self.monitor_tasks)} monitor tasks")
            self.is_running = True
            
            # Give monitors a moment to initialize
            await asyncio.sleep(2)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start monitors: {e}")
            raise
    
    async def _generate_test_opportunities(self) -> None:
        """
        Generate test opportunities to populate the dashboard.
        
        This helps demonstrate that the system is working while waiting
        for real opportunities to be detected.
        """
        try:
            self.logger.info("🧪 GENERATING TEST OPPORTUNITIES...")
            
            if not hasattr(self.system, 'opportunity_handler') or not self.system.opportunity_handler:
                self.logger.warning("No opportunity handler available for test data")
                return
            
            # Generate a variety of test opportunities
            test_scenarios = [
                ("high_confidence", "High confidence opportunity"),
                ("medium_confidence", "Medium confidence opportunity"),
                ("low_confidence", "Low confidence opportunity"),
                ("ethereum_token", "Ethereum new token"),
                ("base_token", "Base chain token"),
                ("solana_token", "Solana token")
            ]
            
            for scenario, description in test_scenarios:
                try:
                    self.logger.info(f"   📊 Generating {description}...")
                    await self.system.opportunity_handler.generate_specific_test_scenario(scenario)
                    await asyncio.sleep(1)  # Space out generation
                    
                except Exception as e:
                    self.logger.warning(f"   ⚠️  Failed to generate {scenario}: {e}")
            
            self.logger.info("✅ Test opportunities generated")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to generate test opportunities: {e}")
    
    async def _run_monitoring_loop(self) -> None:
        """
        Run the main monitoring loop to keep the system active.
        
        This loop keeps the system running and periodically generates
        new test opportunities to demonstrate functionality.
        """
        try:
            self.logger.info("🔄 STARTING MAIN MONITORING LOOP...")
            
            # Import the global dashboard server
            from api.dashboard_core import dashboard_server
            
            if not dashboard_server:
                self.logger.warning("Dashboard not available - running in monitoring mode only")
            else:
                self.logger.info(f"📊 Dashboard available at: http://localhost:8000")
            
            loop_count = 0
            
            while self.is_running:
                try:
                    loop_count += 1
                    
                    # Log status every 30 seconds
                    if loop_count % 30 == 0:
                        await self._log_system_status()
                    
                    # Generate periodic test opportunities (every 60 seconds)
                    if loop_count % 60 == 0:
                        await self._generate_periodic_test_opportunity()
                    
                    # Check monitor health every 5 minutes
                    if loop_count % 300 == 0:
                        await self._check_monitor_health()
                    
                    await asyncio.sleep(1)
                    
                except KeyboardInterrupt:
                    self.logger.info("🛑 Received shutdown signal")
                    break
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(5)
            
        except Exception as e:
            self.logger.error(f"❌ Monitoring loop failed: {e}")
        finally:
            self.is_running = False
    
    async def _log_system_status(self) -> None:
        """Log current system status."""
        try:
            active_tasks = len([task for task in self.monitor_tasks if not task.done()])
            total_tasks = len(self.monitor_tasks)
            
            self.logger.info(f"📈 System Status: {active_tasks}/{total_tasks} monitors active")
            
            # Import the global dashboard server
            from api.dashboard_core import dashboard_server
            
            if dashboard_server and hasattr(dashboard_server, 'opportunities_queue'):
                queue_size = len(dashboard_server.opportunities_queue)
                if hasattr(dashboard_server, 'stats'):
                    stats = dashboard_server.stats
                    self.logger.info(f"   📊 Dashboard: {queue_size} opportunities in queue")
                    self.logger.info(f"   📈 Stats: {stats.get('total_opportunities', 0)} total, " +
                                   f"{stats.get('high_confidence', 0)} high confidence")
                else:
                    self.logger.info(f"   📊 Dashboard: {queue_size} opportunities in queue")
            else:
                self.logger.debug("Dashboard not available for status check")
            
        except Exception as e:
            self.logger.debug(f"Error logging status: {e}")
    
    async def _generate_periodic_test_opportunity(self) -> None:
        """Generate periodic test opportunities to keep dashboard active."""
        try:
            if hasattr(self.system, 'opportunity_handler') and self.system.opportunity_handler:
                await self.system.opportunity_handler.generate_test_opportunities(count=1)
                self.logger.debug("Generated periodic test opportunity")
        except Exception as e:
            self.logger.debug(f"Error generating periodic opportunity: {e}")
    
    async def _check_monitor_health(self) -> None:
        """Check health of all monitor tasks."""
        try:
            dead_tasks = [task for task in self.monitor_tasks if task.done()]
            
            if dead_tasks:
                self.logger.warning(f"⚠️  {len(dead_tasks)} monitor tasks have stopped")
                
                # Log which tasks stopped
                for i, task in enumerate(self.monitor_tasks):
                    if task.done():
                        task_name = task.get_name() if hasattr(task, 'get_name') else f"Task_{i}"
                        self.logger.warning(f"   💀 {task_name} stopped")
                        
                        # Try to get the exception
                        try:
                            if task.exception():
                                self.logger.error(f"   ❌ {task_name} exception: {task.exception()}")
                        except Exception:
                            pass
            else:
                self.logger.debug("✅ All monitor tasks healthy")
                
        except Exception as e:
            self.logger.debug(f"Error checking monitor health: {e}")
    
    async def _cleanup(self) -> None:
        """Clean up resources and stop all monitors."""
        try:
            self.logger.info("🧹 CLEANING UP...")
            
            self.is_running = False
            
            # Stop all monitors gracefully first
            for monitor in self.monitor_tasks:
                if not monitor.done():
                    try:
                        # Try to stop monitor gracefully if it has a stop method
                        monitor_obj = getattr(monitor, '_monitor_obj', None)
                        if monitor_obj and hasattr(monitor_obj, 'stop'):
                            monitor_obj.stop()
                    except Exception as e:
                        self.logger.debug(f"Error stopping monitor gracefully: {e}")
            
            # Give monitors time to stop gracefully
            await asyncio.sleep(2)
            
            # Cancel remaining tasks
            for task in self.monitor_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to finish with timeout
            if self.monitor_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self.monitor_tasks, return_exceptions=True),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    self.logger.warning("Some monitor tasks did not stop cleanly")
            
            # Close any HTTP sessions if system has them
            if self.system:
                try:
                    # Check for session cleanup methods
                    if hasattr(self.system, '_cleanup_sessions'):
                        await self.system._cleanup_sessions()
                    elif hasattr(self.system, 'shutdown'):
                        await self.system.shutdown()
                    
                    # Close individual component sessions
                    components = [
                        'new_token_monitor', 'base_chain_monitor', 'solana_monitor',
                        'jupiter_monitor', 'raydium_monitor', 'contract_analyzer', 
                        'social_analyzer'
                    ]
                    
                    for comp_name in components:
                        comp = getattr(self.system, comp_name, None)
                        if comp and hasattr(comp, 'session'):
                            try:
                                session = getattr(comp, 'session', None)
                                if session and hasattr(session, 'close') and not session.closed:
                                    await session.close()
                            except Exception as e:
                                self.logger.debug(f"Error closing {comp_name} session: {e}")
                
                except Exception as e:
                    self.logger.error(f"Error during system cleanup: {e}")
            
            # Force garbage collection to clean up any remaining resources
            import gc
            gc.collect()
            
            self.logger.info("✅ Cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


async def main() -> None:
    """
    Main function to run the monitor fix.
    
    This function starts the fixed monitoring system that will properly
    generate opportunities for the dashboard.
    """
    logger = logger_manager.get_logger("MonitorFix")
    
    try:
        logger.info("🚀 STARTING MONITOR FIX...")
        logger.info("This will fix the dashboard opportunity display issue")
        logger.info("=" * 60)
        
        # Create and run the fix
        fix = MonitorStartupFix()
        
        await fix.fix_monitor_initialization(
            auto_trading=False,          # Disable auto trading for safety
            disable_dashboard=False,     # Enable dashboard to see results
            generate_test_data=True      # Generate test data for demonstration
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested by user")
    except Exception as e:
        logger.error(f"❌ Monitor fix failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())


if __name__ == "__main__":
    """Entry point for running the monitor fix."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Shutdown complete")
    except Exception as e:
        print(f"❌ Fatal error: {e}")