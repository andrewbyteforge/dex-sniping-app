"""
Fast startup version of production system.
Skips some optimizations for quicker initialization.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Just run the simpler multichain system with trading
from main_with_trading import FullEnhancedSystem

async def main():
    """Run the system with fast startup."""
    print("🚀 Starting DEX Sniping System (Fast Mode)")
    print("=" * 60)
    
    system = FullEnhancedSystem()
    
    try:
        await system.start()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        system.stop()
    except Exception as e:
        print(f"System error: {e}")
        system.stop()
        raise

if __name__ == "__main__":
    # Set shorter timeouts for faster startup
    import socket
    socket.setdefaulttimeout(5)  # 5 second socket timeout
    
    asyncio.run(main())