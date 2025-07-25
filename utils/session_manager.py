"""
Session cleanup fix for monitors to prevent unclosed client session warnings.

This code should be added to the main production enhanced file or created as a 
separate utility to ensure proper cleanup of aiohttp sessions.

File: utils/session_manager.py (NEW FILE)
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any
from datetime import datetime


class SessionManager:
    """
    Centralized session manager for all monitors to prevent unclosed sessions.
    Handles creation, reuse, and proper cleanup of aiohttp sessions.
    """
    
    def __init__(self) -> None:
        """Initialize the session manager."""
        self.logger = logging.getLogger("SessionManager")
        self.sessions: Dict[str, aiohttp.ClientSession] = {}
        self.session_stats: Dict[str, Dict[str, Any]] = {}
        
    async def get_session(self, name: str, timeout: float = 30.0) -> aiohttp.ClientSession:
        """
        Get or create a session for a monitor.
        
        Args:
            name: Unique name for the session (e.g., monitor name)
            timeout: Request timeout in seconds
            
        Returns:
            aiohttp.ClientSession instance
        """
        if name not in self.sessions or self.sessions[name].closed:
            # Create new session
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            self.sessions[name] = aiohttp.ClientSession(timeout=timeout_config)
            
            # Track session creation
            self.session_stats[name] = {
                "created_at": datetime.now(),
                "requests_made": 0,
                "last_used": datetime.now()
            }
            
            self.logger.info(f"Created new session for {name}")
        
        # Update usage stats
        self.session_stats[name]["last_used"] = datetime.now()
        self.session_stats[name]["requests_made"] += 1
        
        return self.sessions[name]
    
    async def close_session(self, name: str) -> None:
        """
        Close a specific session.
        
        Args:
            name: Name of the session to close
        """
        if name in self.sessions and not self.sessions[name].closed:
            await self.sessions[name].close()
            self.logger.info(f"Closed session for {name}")
            
        # Clean up references
        self.sessions.pop(name, None)
        self.session_stats.pop(name, None)
    
    async def close_all_sessions(self) -> None:
        """Close all active sessions."""
        self.logger.info("Closing all active sessions...")
        
        close_tasks = []
        for name, session in list(self.sessions.items()):
            if not session.closed:
                close_tasks.append(self.close_session(name))
        
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        self.sessions.clear()
        self.session_stats.clear()
        self.logger.info("All sessions closed")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about all sessions."""
        return {
            "active_sessions": len([s for s in self.sessions.values() if not s.closed]),
            "total_sessions": len(self.session_stats),
            "session_details": self.session_stats.copy()
        }


# Global session manager instance
session_manager = SessionManager()


class EnhancedProductionSystemCleanup:
    """
    Additional cleanup methods for the EnhancedProductionSystem class.
    
    ADD THESE METHODS TO THE EXISTING EnhancedProductionSystem CLASS
    in main_production_enhanced.py
    """
    
    async def _cleanup(self) -> None:
        """
        Enhanced cleanup method with proper session management.
        
        REPLACE THE EXISTING _cleanup METHOD in EnhancedProductionSystem
        """
        try:
            self.logger.info("=" * 50)
            self.logger.info("🧹 STARTING SYSTEM CLEANUP")
            self.logger.info("=" * 50)
            
            # Stop all monitors first
            if hasattr(self, 'monitors') and self.monitors:
                self.logger.info(f"Stopping {len(self.monitors)} monitors...")
                
                # Stop monitors gracefully
                for monitor in self.monitors:
                    try:
                        if hasattr(monitor, 'stop'):
                            monitor.stop()
                        if hasattr(monitor, '_cleanup'):
                            await monitor._cleanup()
                    except Exception as e:
                        self.logger.error(f"Error stopping monitor {getattr(monitor, 'name', 'unknown')}: {e}")
                
                # Wait a moment for monitors to finish
                await asyncio.sleep(1)
                self.logger.info("✅ Monitors stopped")
            
            # Close all sessions using session manager
            try:
                await session_manager.close_all_sessions()
                self.logger.info("✅ All HTTP sessions closed")
            except Exception as e:
                self.logger.error(f"Error closing sessions: {e}")
            
            # Cleanup trading components
            trading_components = [
                ('execution_engine', 'Execution Engine'),
                ('enhanced_execution_engine', 'Enhanced Execution Engine'),
                ('risk_manager', 'Risk Manager'),
                ('position_manager', 'Position Manager'),
                ('mev_protection', 'MEV Protection'),
                ('gas_optimizer', 'Gas Optimizer'),
                ('tx_simulator', 'Transaction Simulator')
            ]
            
            for attr_name, display_name in trading_components:
                try:
                    component = getattr(self, attr_name, None)
                    if component and hasattr(component, 'cleanup'):
                        await component.cleanup()
                        self.logger.info(f"✅ {display_name} cleaned up")
                except Exception as e:
                    self.logger.error(f"Error cleaning up {display_name}: {e}")
            
            # Cleanup analyzers
            analyzer_components = [
                ('contract_analyzer', 'Contract Analyzer'),
                ('social_analyzer', 'Social Analyzer'),
                ('trading_scorer', 'Trading Scorer')
            ]
            
            for attr_name, display_name in analyzer_components:
                try:
                    component = getattr(self, attr_name, None)
                    if component and hasattr(component, 'cleanup'):
                        await component.cleanup()
                        self.logger.info(f"✅ {display_name} cleaned up")
                except Exception as e:
                    self.logger.error(f"Error cleaning up {display_name}: {e}")
            
            # Final session check and cleanup
            try:
                # Give a moment for any lingering tasks
                await asyncio.sleep(0.5)
                
                # Check for any remaining unclosed sessions
                remaining_sessions = []
                for task in asyncio.all_tasks():
                    if hasattr(task, '_client_session') or 'aiohttp' in str(task):
                        remaining_sessions.append(task)
                
                if remaining_sessions:
                    self.logger.warning(f"Found {len(remaining_sessions)} potential unclosed sessions")
                    # Cancel them
                    for task in remaining_sessions:
                        if not task.done():
                            task.cancel()
                
            except Exception as e:
                self.logger.error(f"Error in final session cleanup: {e}")
            
            # Log final statistics
            self._log_final_statistics()
            
            self.logger.info("=" * 50)
            self.logger.info("✅ SYSTEM CLEANUP COMPLETED")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"CRITICAL ERROR during cleanup: {e}")
            # Force close any remaining sessions
            try:
                await session_manager.close_all_sessions()
            except:
                pass

    def _log_final_statistics(self) -> None:
        """Log final system statistics before shutdown."""
        try:
            if hasattr(self, 'system_stats') and self.system_stats:
                uptime = datetime.now() - self.system_stats.get("start_time", datetime.now())
                
                self.logger.info("📊 FINAL SYSTEM STATISTICS:")
                self.logger.info(f"   Total uptime: {uptime}")
                self.logger.info(f"   Monitors initialized: {len(getattr(self, 'monitors', []))}")
                
                # Get monitor stats if available
                try:
                    monitor_stats = self.get_monitor_stats()
                    total_opportunities = sum(
                        stats.get('opportunities_found', 0) 
                        for stats in monitor_stats.values()
                    )
                    total_processed = sum(
                        stats.get('pairs_processed', stats.get('tokens_processed', 0))
                        for stats in monitor_stats.values()
                    )
                    
                    self.logger.info(f"   Total opportunities found: {total_opportunities}")
                    self.logger.info(f"   Total items processed: {total_processed}")
                    
                except Exception:
                    pass  # Don't fail on stats gathering
                
        except Exception as e:
            self.logger.error(f"Error logging final statistics: {e}")

    async def emergency_shutdown(self) -> None:
        """
        Emergency shutdown that forces cleanup of all resources.
        
        Use this if normal cleanup fails.
        """
        self.logger.warning("🚨 EMERGENCY SHUTDOWN INITIATED")
        
        try:
            # Force stop all monitors
            if hasattr(self, 'monitors'):
                for monitor in self.monitors:
                    try:
                        monitor.is_running = False
                        if hasattr(monitor, 'session') and monitor.session:
                            if not monitor.session.closed:
                                await monitor.session.close()
                    except:
                        pass
            
            # Force close all sessions
            await session_manager.close_all_sessions()
            
            # Cancel all remaining tasks
            tasks = [task for task in asyncio.all_tasks() if not task.done()]
            if tasks:
                self.logger.warning(f"Cancelling {len(tasks)} remaining tasks")
                for task in tasks:
                    task.cancel()
                
                # Wait briefly for cancellation
                await asyncio.gather(*tasks, return_exceptions=True)
            
            self.logger.warning("🚨 EMERGENCY SHUTDOWN COMPLETED")
            
        except Exception as e:
            self.logger.error(f"Error during emergency shutdown: {e}")


# USAGE EXAMPLE FOR MAIN FILE:
"""
To use this in main_production_enhanced.py, add this to the main() function:

async def main():
    system = None
    try:
        # ... existing code ...
        system = EnhancedProductionSystem(...)
        await system.start()
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        if system:
            try:
                await system._cleanup()
            except Exception as cleanup_error:
                logger.error(f"Cleanup failed, attempting emergency shutdown: {cleanup_error}")
                await system.emergency_shutdown()
"""