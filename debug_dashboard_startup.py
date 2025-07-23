#!/usr/bin/env python3
"""
Debug dashboard startup issues with detailed error reporting.
"""

import asyncio
import sys
import os
import traceback

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def debug_dashboard():
    """Debug dashboard startup with detailed error reporting."""
    print("🔍 Debugging Dashboard Startup...\n")
    
    # Step 1: Test imports
    print("1. Testing imports...")
    try:
        from api.dashboard_server import app
        print("   ✅ dashboard_server imported")
    except Exception as e:
        print(f"   ❌ Failed to import dashboard_server: {e}")
        traceback.print_exc()
        return
    
    try:
        from api.dashboard_core import dashboard_server
        print("   ✅ dashboard_core imported")
    except Exception as e:
        print(f"   ❌ Failed to import dashboard_core: {e}")
        traceback.print_exc()
        return
    
    try:
        import uvicorn
        print("   ✅ uvicorn imported")
    except Exception as e:
        print(f"   ❌ Failed to import uvicorn: {e}")
        return
    
    # Step 2: Test dashboard initialization
    print("\n2. Testing dashboard initialization...")
    try:
        await dashboard_server.initialize()
        print("   ✅ Dashboard initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize dashboard: {e}")
        traceback.print_exc()
        return
    
    # Step 3: Test server startup
    print("\n3. Testing server startup...")
    try:
        import threading
        import time
        
        server_started = False
        error_occurred = None
        
        def run_server():
            nonlocal server_started, error_occurred
            try:
                print("   Starting Uvicorn server...")
                # Try with minimal settings
                uvicorn.run(
                    app,
                    host="127.0.0.1",  # Try localhost only first
                    port=8080,
                    log_level="debug",  # Show all logs
                    access_log=True
                )
                server_started = True
            except Exception as e:
                error_occurred = e
                print(f"   ❌ Server error: {e}")
                traceback.print_exc()
        
        # Start in thread
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        
        # Wait a bit
        print("   Waiting for server to start...")
        await asyncio.sleep(5)
        
        if error_occurred:
            print(f"\n❌ Server failed to start: {error_occurred}")
        else:
            print("\n✅ Server thread started")
            
            # Test connection
            print("\n4. Testing connection...")
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://127.0.0.1:8080/') as response:
                        if response.status == 200:
                            print("   ✅ Dashboard is responding!")
                            print("\n🎉 Success! Access dashboard at: http://localhost:8080")
                        else:
                            print(f"   ❌ Dashboard returned status: {response.status}")
            except Exception as e:
                print(f"   ❌ Connection failed: {e}")
                print("\n   This might be a firewall or antivirus issue.")
                print("   Try:")
                print("   1. Temporarily disable Windows Defender/antivirus")
                print("   2. Add Python to firewall exceptions")
                print("   3. Run as administrator")
        
        # Keep running
        print("\nPress Ctrl+C to stop...")
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 70)
    print("🔧 Dashboard Startup Debugger")
    print("=" * 70)
    
    try:
        asyncio.run(debug_dashboard())
    except KeyboardInterrupt:
        print("\n\nStopped by user")