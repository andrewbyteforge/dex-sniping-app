"""
Safe launcher for production system with better error handling.
"""

import asyncio
import sys
import os
import argparse
import traceback

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def main():
    """Safe main entry point with comprehensive error handling."""
    parser = argparse.ArgumentParser(description='Production DEX Sniping System (Safe Mode)')
    parser.add_argument('--auto-trade', action='store_true', 
                       help='Enable automated trading execution')
    parser.add_argument('--demo-mode', action='store_true',
                       help='Run in demo mode (no real trades)')
    parser.add_argument('--no-dashboard', action='store_true',
                       help='Disable web dashboard (console only)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Safety confirmation for auto-trading
    if args.auto_trade and not args.demo_mode:
        print("\n⚠️  WARNING: AUTO-TRADING ENABLED WITH REAL FUNDS ⚠️")
        print("This will automatically execute trades with real money.")
        print("Make sure you understand the risks and have proper funding limits set.")
        
        confirmation = input("\nType 'I UNDERSTAND THE RISKS' to continue: ")
        if confirmation != "I UNDERSTAND THE RISKS":
            print("Auto-trading cancelled. Run with --demo-mode for testing.")
            return
    
    try:
        # Import and initialize system
        from main_production import ProductionTradingSystem
        
        system = ProductionTradingSystem(
            auto_trading_enabled=args.auto_trade,
            disable_dashboard=args.no_dashboard
        )
        
        print(f"🚀 Starting Production System")
        print(f"Auto Trading: {'ON' if args.auto_trade else 'OFF'}")
        print(f"Dashboard: {'OFF' if args.no_dashboard else 'ON'}")
        print(f"Mode: {'DEMO' if args.demo_mode else 'LIVE'}")
        print("=" * 60)
        
        await system.start()
        
    except KeyboardInterrupt:
        print("\n⚠️ Shutdown requested by user")
        if 'system' in locals():
            system.stop()
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        print("Make sure all required components are available")
        traceback.print_exc()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        if 'system' in locals():
            system.stop()
        
        if args.debug:
            traceback.print_exc()
        else:
            print("Run with --debug for detailed error information")
    finally:
        print("\nProduction system stopped. Check logs for detailed information.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSystem interrupted by user")
    except Exception as e:
        print(f"Launcher error: {e}")
        sys.exit(1)