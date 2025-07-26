#!/usr/bin/env python3
"""
Raydium Monitor Test Script

File: test_raydium.py
Purpose: Test the Raydium monitor independently
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monitors.raydium_monitor import RaydiumMonitor
from config.raydium_config import validate_config
from utils.logger import logger_manager


async def test_raydium_monitor():
    """Test the Raydium monitor functionality."""
    
    print("🧪 Testing Raydium Monitor")
    print("=" * 50)
    
    # Test configuration
    print("1. Testing configuration...")
    if validate_config():
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration validation failed")
        return
    
    # Initialize monitor
    print("\n2. Initializing Raydium monitor...")
    monitor = RaydiumMonitor(check_interval=15.0)
    
    # Test callback
    async def test_callback(opportunity):
        print(f"🎯 Test opportunity received: {opportunity.token.symbol}")
        print(f"   💰 Liquidity: ${opportunity.liquidity.liquidity_usd:,.0f}")
        print(f"   📊 Confidence: {opportunity.confidence_score:.3f}")
        print(f"   🔗 DEX: {opportunity.metadata.get('dex', 'Unknown')}")
    
    monitor.add_callback(test_callback)
    
    # Initialize
    if await monitor.initialize():
        print("✅ Monitor initialized successfully")
        
        # Get initial stats
        stats = monitor.get_stats()
        print(f"\n3. Initial Stats:")
        print(f"   Known pools: {len(monitor.known_pools)}")
        print(f"   Whale threshold: ${stats['whale_threshold_usd']:,.0f}")
        print(f"   API calls: {stats['api_calls_total']}")
        
        # Run a few checks
        print("\n4. Running test checks...")
        for i in range(3):
            print(f"   Check {i+1}/3...")
            await monitor._check()
            await asyncio.sleep(2)
        
        # Get final stats
        final_stats = monitor.get_stats()
        print(f"\n5. Final Stats:")
        print(f"   Pools discovered: {final_stats['pools_discovered']}")
        print(f"   Whale movements: {final_stats['whale_movements_detected']}")
        print(f"   API calls: {final_stats['api_calls_total']}")
        print(f"   Success rate: {final_stats['api_calls_successful']}/{final_stats['api_calls_total']}")
        
        # Get pool summary
        summary = monitor.get_monitored_pools_summary()
        print(f"\n6. Pool Summary:")
        print(f"   Total pools: {summary['total_pools']}")
        print(f"   Known pools: {summary['known_pools']}")
        print(f"   Recent events: {summary['recent_events']}")
        
        if summary['top_pools_by_liquidity']:
            print(f"   Top pools by liquidity:")
            for pool in summary['top_pools_by_liquidity'][:3]:
                print(f"     {pool['symbol']}: ${pool['liquidity_usd']:,.0f}")
        
        # Cleanup
        await monitor._cleanup()
        print("\n✅ Test completed successfully")
        
    else:
        print("❌ Monitor initialization failed")


async def test_api_connectivity():
    """Test basic API connectivity."""
    import aiohttp
    from config.raydium_config import get_api_url
    
    print("\n🌐 Testing API Connectivity")
    print("-" * 30)
    
    endpoints = [
        ("/v2/main/pairs", "Pool pairs"),
        ("/v2/main/info", "Pool info"),
        ("/v2/main/price", "Price data")
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint, description in endpoints:
            try:
                url = get_api_url(endpoint)
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        print(f"✅ {description}: HTTP {response.status}")
                    else:
                        print(f"⚠️  {description}: HTTP {response.status}")
            except Exception as e:
                print(f"❌ {description}: Error - {e}")


if __name__ == "__main__":
    async def main():
        print("🔧 Raydium Monitor Test Suite")
        print("=" * 50)
        
        # Test API connectivity first
        await test_api_connectivity()
        
        # Test monitor functionality
        await test_raydium_monitor()
        
        print("\n🎉 All tests completed!")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()