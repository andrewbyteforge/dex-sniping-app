#!/usr/bin/env python3
"""
Simple test runner to demonstrate the dashboard fix.

This is a minimal script that just starts the system and generates
test opportunities to show on the dashboard.

File: test_dashboard.py
Usage: python test_dashboard.py
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger_manager
from fix_monitor_startup import MonitorStartupFix


async def main() -> None:
    """Simple main function to test the dashboard fix."""
    logger = logger_manager.get_logger("DashboardTest")
    
    try:
        logger.info("🚀 TESTING DASHBOARD FIX")
        logger.info("=" * 50)
        logger.info("This will:")
        logger.info("1. Start the trading system")
        logger.info("2. Initialize all monitors")
        logger.info("3. Generate test opportunities")
        logger.info("4. Show the dashboard at http://localhost:8000")
        logger.info("=" * 50)
        
        # Create the fix
        fix = MonitorStartupFix()
        
        # Run the fix
        await fix.fix_monitor_initialization(
            auto_trading=False,      # Safe mode
            disable_dashboard=False, # Show dashboard
            generate_test_data=True  # Generate test opportunities
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Test stopped by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())


if __name__ == "__main__":
    """Entry point."""
    print("🧪 Dashboard Test Runner")
    print("Press Ctrl+C to stop")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Test completed")
    except Exception as e:
        print(f"❌ Test failed: {e}")