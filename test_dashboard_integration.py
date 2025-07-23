#!/usr/bin/env python3
"""
Test dashboard integration and identify issues.
"""

import asyncio
import sys
import os
import threading
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def test_dashboard_startup():
    """Test starting the dashboard server."""
    print("Testing dashboard startup...\n")
    
    try:
        # Import dashboard components
        from api.dashboard_server import app
        from api.dashboard_core import dashboard_server
        import uvicorn
        
        print("✅ Dashboard modules imported successfully")
        
        # Initialize dashboard server
        await dashboard_server.initialize()
        print("✅ Dashboard server initialized")
        
        # Test starting uvicorn in a thread
        def run_server():
            try:
                print("\n🚀 Starting dashboard server on http://localhost:8080")
                uvicorn.run(
                    app,
                    host="0.0.0.0",
                    port=8080,
                    log_level="info"
                )
            except Exception as e:
                print(f"❌ Server error: {e}")
        
        # Start server in background thread
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # Wait a bit for server to start
        print("\nWaiting for server to start...")
        await asyncio.sleep(3)
        
        # Test if server is responding
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:8080/api/stats') as response:
                    if response.status == 200:
                        print("\n✅ Dashboard is running and responding!")
                        print("🌐 Access it at: http://localhost:8080")
                        data = await response.json()
                        print(f"\nStats: {data}")
                    else:
                        print(f"\n❌ Dashboard returned status: {response.status}")
        except Exception as e:
            print(f"\n❌ Could not connect to dashboard: {e}")
        
        # Keep running for testing
        print("\n📊 Dashboard should now be accessible at http://localhost:8080")
        print("Press Ctrl+C to stop...")
        
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"\n❌ Error during startup: {e}")
        import traceback
        traceback.print_exc()


async def test_main_with_dashboard():
    """Test the main application with dashboard."""
    print("\nTesting main application with dashboard...\n")
    
    try:
        # Check if main_production_enhanced.py initializes dashboard correctly
        from main_production_enhanced import EnhancedProductionSystem
        
        # Create system with dashboard enabled
        system = EnhancedProductionSystem(
            auto_trading_enabled=False,
            disable_dashboard=False  # Enable dashboard
        )
        
        # Check if web dashboard task exists
        if hasattr(system, 'web_dashboard_task'):
            print("✅ Dashboard task found in main system")
        else:
            print("❌ Dashboard task not found in main system")
            print("   The main file might not be starting the dashboard properly")
        
    except Exception as e:
        print(f"❌ Error testing main system: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run dashboard tests."""
    print("=" * 70)
    print("🔍 Dashboard Integration Test")
    print("=" * 70)
    
    print("\nWhat would you like to test?")
    print("1. Test dashboard startup only")
    print("2. Test main application dashboard integration")
    print("3. Run both tests")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    try:
        if choice == "1":
            asyncio.run(test_dashboard_startup())
        elif choice == "2":
            asyncio.run(test_main_with_dashboard())
        elif choice == "3":
            asyncio.run(test_dashboard_startup())
            print("\n" + "-" * 70 + "\n")
            asyncio.run(test_main_with_dashboard())
        else:
            print("Invalid choice")
            
    except KeyboardInterrupt:
        print("\n\n✋ Test stopped by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")


if __name__ == "__main__":
    main()