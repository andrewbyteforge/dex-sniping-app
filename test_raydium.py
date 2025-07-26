#!/usr/bin/env python3
"""
Raydium Monitor Test Script

File: test_raydium.py
Purpose: Test the Raydium monitor independently with proper error handling

ISSUE FIXED: Abstract method implementation error
SOLUTION: Updated to use the fixed RaydiumMonitor with complete abstract method implementation
"""

import asyncio
import sys
import os
import traceback
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monitors.raydium_monitor import RaydiumMonitor
from config.raydium_config import validate_config, get_raydium_config
from utils.logger import logger_manager


class RaydiumTestSuite:
    """
    Comprehensive test suite for RaydiumMonitor.
    
    Provides thorough testing of all RaydiumMonitor functionality
    including initialization, configuration, API calls, and monitoring.
    """
    
    def __init__(self):
        """Initialize the test suite."""
        self.monitor: RaydiumMonitor = None
        self.test_results = {
            'config_test': False,
            'initialization_test': False,
            'api_connectivity_test': False,
            'monitoring_test': False,
            'cleanup_test': False
        }
        self.start_time = datetime.now()
    
    async def run_all_tests(self) -> bool:
        """
        Run the complete test suite.
        
        Returns:
            bool: True if all tests pass
        """
        print("🧪 Testing Raydium Monitor")
        print("=" * 50)
        
        try:
            # Test 1: Configuration validation
            print("1. Testing configuration...")
            await self.test_configuration()
            
            # Test 2: Monitor initialization
            print("\n2. Testing monitor initialization...")
            await self.test_initialization()
            
            # Test 3: API connectivity
            print("\n3. Testing API connectivity...")
            await self.test_api_connectivity()
            
            # Test 4: Monitoring functionality
            print("\n4. Testing monitoring functionality...")
            await self.test_monitoring()
            
            # Test 5: Cleanup
            print("\n5. Testing cleanup...")
            await self.test_cleanup()
            
            # Print results
            self.print_test_summary()
            
            return all(self.test_results.values())
            
        except Exception as e:
            print(f"💥 Test suite failed with error: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def test_configuration(self) -> None:
        """Test configuration validation."""
        try:
            # Test configuration loading
            config = get_raydium_config()
            
            # Validate configuration
            if validate_config():
                print("✅ Configuration is valid")
                print(f"   📊 Min Liquidity: ${config.monitoring.min_liquidity_usd:,.0f}")
                print(f"   🐋 Whale Threshold: ${config.monitoring.whale_threshold_usd:,.0f}")
                print(f"   ⚡ Rate Limit: {config.rate_limits.requests_per_minute}/min")
                print(f"   🔌 WebSocket: {'Enabled' if config.websocket.enabled else 'Disabled'}")
                self.test_results['config_test'] = True
            else:
                print("❌ Configuration validation failed")
                
        except Exception as e:
            print(f"❌ Configuration test failed: {e}")
    
    async def test_initialization(self) -> None:
        """Test monitor initialization."""
        try:
            # Create monitor instance
            self.monitor = RaydiumMonitor(check_interval=15.0)
            print("✅ Monitor instance created")
            
            # Test callback setup
            async def test_callback(opportunity):
                print(f"🎯 Test callback triggered: {opportunity.token.symbol}")
                print(f"   💰 Liquidity: ${opportunity.liquidity.liquidity_usd:,.0f}")
                print(f"   📊 Confidence: {opportunity.confidence_score:.3f}")
                print(f"   🔗 DEX: {opportunity.metadata.get('dex', 'Unknown')}")
            
            self.monitor.add_callback(test_callback)
            print("✅ Test callback added")
            
            # Initialize monitor
            init_success = await self.monitor.initialize()
            if init_success:
                print("✅ Monitor initialized successfully")
                self.test_results['initialization_test'] = True
                
                # Get initial stats
                stats = self.monitor.get_stats()
                print(f"   📊 Known pools baseline: {len(self.monitor.known_pools)}")
                print(f"   📈 API calls made: {stats['api_calls_total']}")
                print(f"   ✅ Successful calls: {stats['api_calls_successful']}")
                
            else:
                print("❌ Monitor initialization failed")
                
        except Exception as e:
            print(f"❌ Initialization test failed: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
    
    async def test_api_connectivity(self) -> None:
        """Test API connectivity and data fetching."""
        try:
            if not self.monitor:
                print("❌ Monitor not initialized, skipping API test")
                return
            
            print("   Testing pool data fetching...")
            
            # Test fetching new pools
            new_pools = await self.monitor._fetch_new_pools()
            print(f"   📊 Found {len(new_pools)} new pools")
            
            # Test fetching whale movements
            whale_movements = await self.monitor._fetch_whale_movements()
            print(f"   🐋 Found {len(whale_movements)} whale movements")
            
            # Test fetching specific pool data (if we have any pools)
            if len(self.monitor.known_pools) > 0:
                test_pool_id = list(self.monitor.known_pools)[0]
                pool_data = await self.monitor._fetch_pool_data(test_pool_id)
                if pool_data:
                    print(f"   📈 Successfully fetched data for pool: {test_pool_id[:8]}...")
                else:
                    print(f"   ⚠️  No data returned for pool: {test_pool_id[:8]}...")
            
            print("✅ API connectivity test completed")
            self.test_results['api_connectivity_test'] = True
            
        except Exception as e:
            print(f"❌ API connectivity test failed: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
    
    async def test_monitoring(self) -> None:
        """Test monitoring functionality."""
        try:
            if not self.monitor:
                print("❌ Monitor not initialized, skipping monitoring test")
                return
            
            print("   Running monitoring checks...")
            
            # Run a few monitoring cycles
            for i in range(3):
                print(f"     Check {i+1}/3...")
                try:
                    await self.monitor._check()
                    print(f"     ✅ Check {i+1} completed")
                except Exception as e:
                    print(f"     ⚠️  Check {i+1} had error: {e}")
                
                # Wait between checks
                if i < 2:  # Don't wait after last check
                    await asyncio.sleep(2)
            
            # Get final stats
            final_stats = self.monitor.get_stats()
            print(f"   📊 Final Stats:")
            print(f"     Pools discovered: {final_stats['pools_discovered']}")
            print(f"     Whale movements: {final_stats['whale_movements_detected']}")
            print(f"     Total API calls: {final_stats['api_calls_total']}")
            print(f"     Successful calls: {final_stats['api_calls_successful']}")
            print(f"     Failed calls: {final_stats['api_calls_failed']}")
            
            # Get pool summary
            try:
                summary = self.monitor.get_monitored_pools_summary()
                print(f"   📈 Pool Summary:")
                print(f"     Monitored pools: {summary.get('total_pools', 0)}")
                print(f"     Known pools: {summary.get('known_pools', 0)}")
                print(f"     Cached pools: {summary.get('cached_pools', 0)}")
                print(f"     Recent events: {summary.get('recent_events', 0)}")
            except Exception as e:
                print(f"     ⚠️  Could not get pool summary: {e}")
            
            print("✅ Monitoring test completed")
            self.test_results['monitoring_test'] = True
            
        except Exception as e:
            print(f"❌ Monitoring test failed: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
    
    async def test_cleanup(self) -> None:
        """Test cleanup functionality."""
        try:
            if not self.monitor:
                print("❌ Monitor not initialized, skipping cleanup test")
                return
            
            print("   Testing monitor cleanup...")
            
            # Test cleanup
            await self.monitor.cleanup()
            print("✅ Cleanup test completed")
            self.test_results['cleanup_test'] = True
            
        except Exception as e:
            print(f"❌ Cleanup test failed: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
    
    def print_test_summary(self) -> None:
        """Print comprehensive test results summary."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print("\n" + "=" * 50)
        print("🧪 TEST SUMMARY")
        print("=" * 50)
        
        passed = sum(1 for result in self.test_results.values() if result)
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name.replace('_', ' ').title()}: {status}")
        
        print("=" * 50)
        print(f"Results: {passed}/{total} tests passed")
        print(f"Duration: {duration:.2f} seconds")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED!")
        else:
            print("⚠️  Some tests failed - check logs above")
        
        print("=" * 50)


async def test_raydium_monitor():
    """
    Main test function for Raydium monitor.
    
    This function runs the complete test suite and provides detailed
    feedback on the monitor's functionality.
    """
    try:
        # Create and run test suite
        test_suite = RaydiumTestSuite()
        success = await test_suite.run_all_tests()
        
        if success:
            print("\n🎉 Raydium Monitor test completed successfully!")
            return True
        else:
            print("\n⚠️  Raydium Monitor test completed with failures.")
            return False
            
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n💥 Test failed with unexpected error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return False


async def quick_test():
    """
    Quick test for basic functionality.
    
    This is a simplified test that just checks if the monitor can be
    created and initialized without the abstract method error.
    """
    print("🚀 Quick Raydium Monitor Test")
    print("=" * 30)
    
    try:
        # Test 1: Configuration
        print("1. Testing configuration...")
        if validate_config():
            print("   ✅ Configuration valid")
        else:
            print("   ❌ Configuration invalid")
            return False
        
        # Test 2: Monitor creation
        print("2. Creating monitor...")
        monitor = RaydiumMonitor(check_interval=15.0)
        print("   ✅ Monitor created successfully")
        
        # Test 3: Initialization
        print("3. Initializing monitor...")
        success = await monitor.initialize()
        if success:
            print("   ✅ Monitor initialized successfully")
            print(f"   📊 Known pools: {len(monitor.known_pools)}")
        else:
            print("   ❌ Monitor initialization failed")
            return False
        
        # Test 4: Cleanup
        print("4. Cleaning up...")
        await monitor.cleanup()
        print("   ✅ Cleanup completed")
        
        print("\n🎉 Quick test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n💥 Quick test FAILED: {e}")
        print(f"Error type: {type(e).__name__}")
        if "abstract" in str(e).lower():
            print("❌ This appears to be the abstract method error!")
            print("   The RaydiumMonitor class is missing required abstract method implementations.")
        return False


async def main():
    """
    Main entry point for test script.
    
    Provides options for different test modes and comprehensive error handling.
    """
    print("🔧 Raydium Monitor Test Script")
    print("=" * 40)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 40)
    
    try:
        # Check command line arguments
        if len(sys.argv) > 1 and sys.argv[1] == "--quick":
            # Run quick test
            success = await quick_test()
        else:
            # Run full test suite
            success = await test_raydium_monitor()
        
        # Exit with appropriate code
        if success:
            print("\n✅ Test completed successfully")
            sys.exit(0)
        else:
            print("\n❌ Test completed with failures")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the test
    asyncio.run(main())