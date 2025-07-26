#!/usr/bin/env python3
"""
Monitor debug and test script to check monitor functionality.

File: debug_monitors.py
Usage: python debug_monitors.py
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger_manager
from core.enhanced_trading_system import EnhancedTradingSystem


async def test_monitors():
    """Test monitor functionality and opportunity generation."""
    logger = logger_manager.get_logger("MonitorTest")
    
    try:
        logger.info("🔧 Starting monitor functionality test...")
        
        # Create trading system
        system = EnhancedTradingSystem(
            auto_trading_enabled=False,
            disable_dashboard=True,
            disable_telegram=True
        )
        
        # Initialize system
        await system.initialize()
        
        # Test opportunity handler directly
        logger.info("🧪 Testing opportunity handler...")
        
        # Generate a few test opportunities
        await system.opportunity_handler.generate_test_opportunities(count=5, interval=1.0)
        
        # Test specific scenarios
        logger.info("🎭 Testing specific scenarios...")
        await system.opportunity_handler.generate_specific_test_scenario("high_confidence")
        
        logger.info("✅ Monitor test completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Monitor test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_dashboard_integration():
    """Test dashboard integration with test opportunities."""
    logger = logger_manager.get_logger("DashboardTest")
    
    try:
        logger.info("🌐 Starting dashboard integration test...")
        
        # Create trading system with dashboard
        system = EnhancedTradingSystem(
            auto_trading_enabled=False,
            disable_dashboard=False,  # Enable dashboard
            disable_telegram=True
        )
        
        # Initialize system
        await system.initialize()
        
        # Wait for dashboard to start
        await asyncio.sleep(3)
        
        logger.info("📊 Dashboard should be available at: http://localhost:8000")
        
        # Generate continuous test opportunities
        logger.info("🔄 Starting continuous opportunity generation...")
        
        # Run for 60 seconds with 1 opportunity every 5 seconds
        start_time = datetime.now()
        opportunity_count = 0
        
        while (datetime.now() - start_time).seconds < 60:
            try:
                await system.opportunity_handler.generate_test_opportunities(count=1, interval=0.1)
                opportunity_count += 1
                logger.info(f"📈 Generated opportunity #{opportunity_count} - Check dashboard!")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error generating opportunity: {e}")
                
        logger.info(f"✅ Dashboard test completed - Generated {opportunity_count} opportunities")
        
    except Exception as e:
        logger.error(f"❌ Dashboard test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_monitor_callbacks():
    """Test monitor callback functionality."""
    logger = logger_manager.get_logger("CallbackTest")
    
    try:
        logger.info("🔗 Testing monitor callbacks...")
        
        # Create a simple callback function
        callback_count = 0
        
        async def test_callback(opportunity):
            nonlocal callback_count
            callback_count += 1
            logger.info(f"✅ Callback #{callback_count} received: {opportunity.token.symbol}")
        
        # Import monitor
        from monitors.base_monitor import BaseMonitor
        
        # Create a test monitor
        class TestMonitor(BaseMonitor):
            def __init__(self):
                super().__init__("TestMonitor", check_interval=2.0)
                self.test_count = 0
            
            async def _initialize(self):
                self.logger.info("Test monitor initialized")
            
            async def _check(self):
                self.test_count += 1
                self.logger.info(f"Test monitor check #{self.test_count}")
                
                # Create fake opportunity data
                fake_opportunity = type('FakeOpportunity', (), {
                    'token': type('Token', (), {'symbol': f'TEST{self.test_count}'})()
                })()
                
                # Notify callbacks
                await self._notify_callbacks(fake_opportunity)
            
            async def _cleanup(self):
                self.logger.info("Test monitor cleaned up")
        
        # Create and configure test monitor
        test_monitor = TestMonitor()
        test_monitor.add_callback(test_callback)
        
        # Run monitor for a short time
        logger.info("🚀 Starting test monitor...")
        monitor_task = asyncio.create_task(test_monitor.start())
        
        # Let it run for 10 seconds
        await asyncio.sleep(10)
        
        # Stop monitor
        test_monitor.stop()
        
        try:
            await asyncio.wait_for(monitor_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Monitor task didn't stop cleanly")
        
        logger.info(f"✅ Callback test completed - Received {callback_count} callbacks")
        
    except Exception as e:
        logger.error(f"❌ Callback test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main test function."""
    print("🧪 MONITOR TESTING SUITE")
    print("=" * 50)
    
    try:
        # Test 1: Basic monitor functionality
        print("\n1️⃣ Testing basic monitor functionality...")
        await test_monitors()
        
        # Test 2: Monitor callbacks
        print("\n2️⃣ Testing monitor callbacks...")
        await test_monitor_callbacks()
        
        # Test 3: Dashboard integration (optional)
        print("\n3️⃣ Testing dashboard integration...")
        print("   This will start the dashboard and generate test opportunities")
        print("   Open http://localhost:8000 in your browser to see results")
        
        response = input("   Run dashboard test? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            await test_dashboard_integration()
        else:
            print("   Skipping dashboard test")
        
        print("\n✅ ALL TESTS COMPLETED")
        
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)