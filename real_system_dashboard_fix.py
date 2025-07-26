#!/usr/bin/env python3
"""
Fix for the real system's dashboard integration.

This fixes the OpportunityHandler to properly integrate with the global dashboard_server
instance used by the real EnhancedTradingSystem.

File: real_system_dashboard_fix.py
Class: DashboardIntegrationFix
Methods: fix_opportunity_handler_integration
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Any, Dict

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger_manager
from api.dashboard_core import dashboard_server


class DashboardIntegrationFix:
    """
    Fix the real system's dashboard integration by patching the OpportunityHandler.
    """
    
    def __init__(self) -> None:
        """Initialize the dashboard integration fix."""
        self.logger = logger_manager.get_logger("DashboardIntegrationFix")
    
    async def apply_fix(self) -> None:
        """
        Apply the dashboard integration fix to the running system.
        """
        try:
            self.logger.info("🔧 APPLYING DASHBOARD INTEGRATION FIX")
            self.logger.info("=" * 60)
            
            # Import the OpportunityHandler class
            from core.opportunity_handler import OpportunityHandler
            
            # Create the fixed integration method
            async def fixed_integrate_dashboard_safe(self, opportunity) -> None:
                """
                Fixed dashboard integration that uses the global dashboard_server.
                """
                try:
                    # Extract data safely with defaults and type validation
                    token_symbol = str(getattr(opportunity.token, 'symbol', 'UNKNOWN'))
                    token_address = str(getattr(opportunity.token, 'address', ''))
                    
                    # Ensure chain is a string
                    chain = 'ethereum'
                    if hasattr(opportunity, 'chain') and opportunity.chain:
                        chain = str(opportunity.chain).lower()
                    elif 'chain' in opportunity.metadata:
                        chain_value = opportunity.metadata['chain']
                        if isinstance(chain_value, str):
                            chain = chain_value.lower()
                    
                    # Extract liquidity info safely
                    liquidity_usd = 0.0
                    if hasattr(opportunity, 'liquidity') and opportunity.liquidity:
                        try:
                            liquidity_value = getattr(opportunity.liquidity, 'liquidity_usd', 0)
                            liquidity_usd = float(liquidity_value) if liquidity_value is not None else 0.0
                        except (TypeError, ValueError):
                            liquidity_usd = 0.0
                    
                    # Create opportunity data structure with safe extraction
                    opp_data = {
                        "token_symbol": token_symbol,
                        "token_address": token_address,
                        "chain": chain,
                        "risk_level": str(opportunity.metadata.get("risk_level", "unknown")),
                        "recommendation": str(opportunity.metadata.get("recommendation", {}).get("action", "MONITOR")),
                        "confidence": str(opportunity.metadata.get("recommendation", {}).get("confidence", "LOW")),
                        "score": float(opportunity.metadata.get("trading_score", {}).get("overall_score", 0.0)),
                        "liquidity_usd": liquidity_usd,
                        "detected_at": datetime.now().isoformat(),
                        "age_minutes": 0
                    }
                    
                    # Update dashboard stats directly using global dashboard_server
                    if dashboard_server and hasattr(dashboard_server, 'stats'):
                        stats = dashboard_server.stats
                        if isinstance(stats, dict):
                            stats["total_opportunities"] = stats.get("total_opportunities", 0) + 1
                            
                            if opp_data["confidence"] == "HIGH":
                                stats["high_confidence"] = stats.get("high_confidence", 0) + 1
                    
                    # Add to opportunities queue directly using global dashboard_server
                    if dashboard_server and hasattr(dashboard_server, 'opportunities_queue'):
                        queue = dashboard_server.opportunities_queue
                        if isinstance(queue, list):
                            queue.append(opportunity)
                            
                            # Keep queue size manageable
                            if len(queue) > 100:
                                queue.pop(0)
                    
                    # Broadcast to WebSocket clients directly using global dashboard_server
                    if dashboard_server and hasattr(dashboard_server, 'broadcast_message'):
                        try:
                            await dashboard_server.broadcast_message({
                                "type": "new_opportunity",
                                "data": opp_data
                            })
                        except Exception as broadcast_error:
                            self.logger.warning(f"WebSocket broadcast failed: {broadcast_error}")
                    
                    self.logger.info(f"✅ Successfully integrated {token_symbol} with dashboard")
                    
                except Exception as e:
                    self.logger.error(f"Dashboard integration failed: {e}")
                    # Don't raise - let the opportunity processing continue
            
            # Monkey patch the OpportunityHandler method
            OpportunityHandler._integrate_dashboard_safe = fixed_integrate_dashboard_safe
            
            self.logger.info("✅ Dashboard integration fix applied successfully!")
            self.logger.info("🎯 Real opportunities should now appear on the dashboard")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to apply dashboard integration fix: {e}")
            raise
    
    async def verify_fix(self) -> bool:
        """
        Verify that the fix is working by checking dashboard state.
        """
        try:
            self.logger.info("🔍 Verifying dashboard integration fix...")
            
            # Check dashboard server state
            if dashboard_server:
                queue_size = len(dashboard_server.opportunities_queue)
                stats = dashboard_server.stats
                
                self.logger.info(f"📊 Dashboard queue: {queue_size} opportunities")
                self.logger.info(f"📈 Dashboard stats: {stats}")
                
                # Check if we have opportunities
                if queue_size > 0:
                    self.logger.info("✅ Fix verification successful - opportunities found in dashboard")
                    return True
                else:
                    self.logger.warning("⚠️  No opportunities in dashboard yet - monitors may still be starting")
                    return False
            else:
                self.logger.error("❌ Dashboard server not available")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Fix verification failed: {e}")
            return False


async def main() -> None:
    """
    Main function to apply the dashboard integration fix.
    """
    logger = logger_manager.get_logger("DashboardFix")
    
    try:
        logger.info("🚀 STARTING DASHBOARD INTEGRATION FIX")
        logger.info("This will fix the real system's dashboard integration")
        logger.info("=" * 60)
        
        # Create and apply the fix
        fix = DashboardIntegrationFix()
        await fix.apply_fix()
        
        # Wait a moment for the fix to take effect
        await asyncio.sleep(2)
        
        # Verify the fix
        success = await fix.verify_fix()
        
        if success:
            logger.info("🎉 DASHBOARD INTEGRATION FIX SUCCESSFUL!")
            logger.info("Real opportunities should now appear on the dashboard")
        else:
            logger.info("⏳ Fix applied - waiting for new opportunities to test integration")
        
        logger.info("🌐 Check your dashboard at: http://localhost:8000")
        
    except Exception as e:
        logger.error(f"❌ Dashboard integration fix failed: {e}")


if __name__ == "__main__":
    """Entry point for the dashboard integration fix."""
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Fix failed: {e}")