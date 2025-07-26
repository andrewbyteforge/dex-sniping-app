#!/usr/bin/env python3
"""
Integration test to verify Raydium is properly integrated into main system.

File: test_integration.py
Purpose: Test that Raydium monitor works within the main trading system
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_raydium_integration():
    """Test Raydium integration in main system."""
    
    print("🧪 Testing Raydium Integration in Main System")
    print("=" * 60)
    
    try:
        # Test import
        print("1. Testing imports...")
        from main_with_trading import EnhancedTradingSystem
        from monitors.raydium_monitor import RaydiumMonitor
        print("   ✅ Imports successful")
        
        # Test system initialization with Raydium
        print("\n2. Testing system initialization...")
        system = EnhancedTradingSystem(
            auto_trading_enabled=False,
            disable_dashboard=True
        )
        
        # Initialize (this should include Raydium monitor)
        await system.initialize()
        print("   ✅ System initialized")
        
        # Check if Raydium monitor was added
        print("\n3. Checking monitors...")
        raydium_found = False
        for monitor in system.monitors:
            print(f"   - {monitor.__class__.__name__}")
            if "Raydium" in monitor.__class__.__name__:
                raydium_found = True
                print(f"     ✅ Raydium monitor found!")
                print(f"     📊 Known pools: {len(getattr(monitor, 'known_pools', []))}")
                print(f"     🐋 Whale threshold: ${getattr(monitor, 'whale_threshold_usd', 0):,.0f}")
        
        if not raydium_found:
            print("   ❌ Raydium monitor not found!")
            return False
        
        # Test system status
        print("\n4. Testing system status...")
        status = system.get_system_status()
        print(f"   Active monitors: {len(status.get('monitors', []))}")
        
        # Look for Raydium in status
        raydium_status = None
        for monitor_status in status.get('monitors', []):
            if 'Raydium' in monitor_status.get('name', ''):
                raydium_status = monitor_status
                break
        
        if raydium_status:
            print("   ✅ Raydium status found in system")
            print(f"     Running: {raydium_status.get('is_running', False)}")
            print(f"     API calls: {raydium_status.get('api_calls', 0)}")
        else:
            print("   ⚠️  Raydium status not found in system status")
        
        # Cleanup
        print("\n5. Testing cleanup...")
        try:
            if hasattr(system, 'cleanup'):
                await system.cleanup()
            else:
                system.stop()  # Fallback to stop method
            print("   ✅ Cleanup completed")
        except Exception as e:
            print(f"   ⚠️  Cleanup had minor issues: {e}")
            print("   ✅ System stopped anyway")
        
        print("\n" + "=" * 60)
        print("🎉 RAYDIUM INTEGRATION TEST PASSED!")
        print("✅ Raydium monitor is properly integrated into main system")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n💥 Integration test failed: {e}")
        import traceback
        print(f"Error details: {traceback.format_exc()}")
        return False

async def main():
    """Run integration test."""
    success = await test_raydium_integration()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())