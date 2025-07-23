#!/usr/bin/env python3
"""
Fix the dashboard initialization issue in main_production_enhanced.py
"""

import os
import re


def check_dashboard_init():
    """Check and fix dashboard initialization in main file."""
    
    main_file = "main_production_enhanced.py"
    
    print(f"🔍 Checking {main_file} for dashboard initialization issues...\n")
    
    if not os.path.exists(main_file):
        print(f"❌ {main_file} not found!")
        return
    
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for the dashboard initialization method
    if "_initialize_web_dashboard" in content:
        print("✅ Dashboard initialization method found")
        
        # Check if it's properly starting the server
        if "uvicorn.run" in content or "threading.Thread" in content:
            print("✅ Server startup code found")
        else:
            print("❌ Server startup code missing!")
            print("   The dashboard is being initialized but not started")
    else:
        print("❌ Dashboard initialization method not found!")
    
    # Create a working starter
    create_working_main()


def create_working_main():
    """Create a fixed version that properly starts the dashboard."""
    
    print("\n📝 Creating main_production_fixed.py with working dashboard...\n")
    
    fixed_code = '''#!/usr/bin/env python3
"""
Fixed production main with working dashboard integration.
"""

import asyncio
import sys
import os
from datetime import datetime
import threading
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the original EnhancedProductionSystem
from main_production_enhanced import EnhancedProductionSystem

# Import dashboard components
from api.dashboard_server import app
from api.dashboard_core import dashboard_server
import uvicorn


class FixedProductionSystem(EnhancedProductionSystem):
    """Enhanced production system with fixed dashboard initialization."""
    
    async def _initialize_web_dashboard(self) -> None:
        """Initialize the web dashboard with proper server startup."""
        if self.disable_dashboard:
            self.logger.info("Dashboard disabled by configuration")
            return
            
        try:
            self.logger.info("Initializing web dashboard...")
            
            # Set the trading system reference
            dashboard_server.trading_system = self
            
            # Initialize dashboard
            await dashboard_server.initialize()
            
            # Define the server run function
            def run_dashboard_server():
                try:
                    self.logger.info("Starting dashboard server...")
                    # Use port 8080 which we know works
                    uvicorn.run(
                        app,
                        host="0.0.0.0",
                        port=8080,
                        log_level="error",
                        access_log=False
                    )
                except Exception as e:
                    self.logger.error(f"Dashboard server error: {e}")
            
            # Start server in background thread
            self.dashboard_thread = threading.Thread(
                target=run_dashboard_server,
                daemon=True,
                name="DashboardServer"
            )
            self.dashboard_thread.start()
            
            # Wait a moment for server to start
            await asyncio.sleep(2)
            
            self.logger.info("✅ Web dashboard initialized")
            self.logger.info("   🌐 Dashboard: http://localhost:8080")
            self.components_initialized["dashboard"] = True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize dashboard: {e}")
            self.logger.info("System will continue without dashboard")
            self.components_initialized["dashboard"] = False


async def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="DEX Sniping Bot - Production System")
    parser.add_argument("--auto-trade", action="store_true", help="Enable automatic trading")
    parser.add_argument("--no-dashboard", action="store_true", help="Disable web dashboard")
    parser.add_argument("--chains", type=str, help="Comma-separated list of chains to monitor")
    parser.add_argument("--simulation-mode", action="store_true", help="Run in simulation mode")
    
    args = parser.parse_args()
    
    # Create and run the fixed system
    system = FixedProductionSystem(
        auto_trading_enabled=args.auto_trade,
        disable_dashboard=args.no_dashboard
    )
    
    try:
        await system.start()
    except KeyboardInterrupt:
        print("\\n\\nShutting down gracefully...")
        await system.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n\\nShutdown complete")
'''
    
    with open('main_production_fixed.py', 'w') as f:
        f.write(fixed_code)
    
    print("✅ Created main_production_fixed.py")
    print("\n🚀 To run with working dashboard:")
    print("   python main_production_fixed.py")
    print("\n📊 Dashboard will be at: http://localhost:8080")


def create_simple_runner():
    """Create an even simpler runner."""
    
    simple_code = '''#!/usr/bin/env python3
"""
Simple runner that starts everything properly.
"""

import subprocess
import sys
import time
import os


def main():
    print("=" * 70)
    print("🚀 DEX Sniping Bot - Simple Starter")
    print("=" * 70)
    
    # Kill any existing Python processes on our ports
    print("\\n🧹 Cleaning up old processes...")
    os.system("taskkill /F /IM python.exe 2>nul")
    time.sleep(2)
    
    print("\\n📊 Starting Dashboard...")
    dashboard_process = subprocess.Popen(
        [sys.executable, "run_dashboard_only.py"],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    time.sleep(3)
    
    print("\\n🤖 Starting Bot...")
    bot_process = subprocess.Popen(
        [sys.executable, "main_production_enhanced.py", "--no-dashboard"],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    print("\\n✅ System Started!")
    print("\\n📊 Dashboard: http://localhost:8080")
    print("\\nPress Ctrl+C to stop everything\\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\\n\\nShutting down...")
        dashboard_process.terminate()
        bot_process.terminate()


if __name__ == "__main__":
    main()
'''
    
    with open('start_system.py', 'w') as f:
        f.write(simple_code)
    
    print("\n✅ Created start_system.py")
    print("\n🎯 Simplest way to start:")
    print("   python start_system.py")
    print("\n   This will open two consoles - one for bot, one for dashboard")


if __name__ == "__main__":
    check_dashboard_init()
    create_simple_runner()