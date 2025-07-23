#!/usr/bin/env python3
"""
Simple dashboard starter that handles import issues.
Run this from the main project directory.
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Now we can import and run
if __name__ == "__main__":
    try:
        from api.dashboard_server import app
        import uvicorn
        
        print("=" * 70)
        print("🚀 Starting DEX Sniping Bot Dashboard")
        print("=" * 70)
        print("\n📊 Dashboard will be available at: http://localhost:8080")
        print("\nPress Ctrl+C to stop\n")
        
        # Run the server
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8080,
            log_level="info",
            access_log=True
        )
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\nMake sure you run this from the main project directory:")
        print("cd 'C:\\Users\\acart\\Desktop\\Crypto trader\\dex_sniping'")
        print("python start_dashboard_simple.py")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()