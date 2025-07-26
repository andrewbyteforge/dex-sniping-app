#!/usr/bin/env python3
"""
Enhanced main trading system entry point.
Now with modular architecture and Telegram signal integration.

File: main_with_trading.py
Functions: main, argument parsing, system startup
"""

import asyncio
import sys
import os
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.enhanced_trading_system import EnhancedTradingSystem
from trading.trading_executor import TradingMode
from utils.logger import logger_manager

# Get logger
logger = logger_manager.get_logger("MainSystem")


async def main():
    """
    Enhanced main function with Telegram signal integration and modular architecture.
    """
    parser = argparse.ArgumentParser(description='Enhanced DEX Trading System with Telegram Integration')
    parser.add_argument('--mode', choices=['paper', 'live'], default='paper',
                      help='Trading mode (default: paper)')
    parser.add_argument('--auto-trading', action='store_true',
                      help='Enable automatic trading')
    parser.add_argument('--disable-dashboard', action='store_true',
                      help='Disable web dashboard')
    parser.add_argument('--disable-telegram', action='store_true',
                      help='Disable Telegram notifications')
    parser.add_argument('--enable-telegram-signals', action='store_true',
                      help='Enable Telegram channel signal monitoring')
    parser.add_argument('--test-telegram', action='store_true',
                      help='Send test Telegram notification and exit')
    parser.add_argument('--generate-test-opportunities', action='store_true',
                      help='Generate test opportunities for dashboard testing')
    
    args = parser.parse_args()
    
    # Convert mode to enum
    trading_mode = TradingMode.PAPER_ONLY if args.mode == 'paper' else TradingMode.LIVE_TRADING
    
    try:
        logger.info("🚀 Starting Enhanced DEX Trading System")
        logger.info(f"   Mode: {args.mode}")
        logger.info(f"   Auto Trading: {'ENABLED' if args.auto_trading else 'DISABLED'}")
        logger.info(f"   Telegram Notifications: {'DISABLED' if args.disable_telegram else 'ENABLED'}")
        logger.info(f"   Telegram Signals: {'ENABLED' if args.enable_telegram_signals else 'DISABLED'}")
        logger.info(f"   Dashboard: {'DISABLED' if args.disable_dashboard else 'ENABLED'}")
        
        # Create enhanced trading system
        system = EnhancedTradingSystem(
            auto_trading_enabled=args.auto_trading,
            trading_mode=trading_mode,
            disable_dashboard=args.disable_dashboard,
            disable_telegram=args.disable_telegram,
            enable_telegram_signals=args.enable_telegram_signals
        )
        
        # Handle special modes
        if args.test_telegram:
            logger.info("🧪 Testing Telegram integration...")
            await system._initialize_telegram_integration()
            await system.telegram_manager.test_notifications()
            if system.telegram_manager.notifications_enabled:
                print("✅ Telegram test notification sent!")
            else:
                print("❌ Telegram not configured or disabled")
            return
        
        # Start the system with signal handling
        if args.generate_test_opportunities:
            # Start system and generate test opportunities
            logger.info("🧪 Starting system with test opportunity generation...")
            
            # Start system initialization in background
            init_task = asyncio.create_task(system.initialize())
            
            # Start test opportunity generation
            test_task = asyncio.create_task(system.opportunity_handler.generate_test_opportunities())
            
            # Run main system
            main_task = asyncio.create_task(system.run_with_signal_handling())
            
            # Wait for all tasks
            await asyncio.gather(init_task, test_task, main_task, return_exceptions=True)
        else:
            # Normal system startup
            await system.run_with_signal_handling()
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user (Ctrl+C)")
        logger.info("System interrupted by user")
        sys.exit(0)
    except Exception as e:
        error_msg = f"💥 System error: {e}"
        print(error_msg)
        logger.error(error_msg)
        sys.exit(1)


def display_startup_banner():
    """Display startup banner with system information."""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                      ENHANCED DEX TRADING SYSTEM v2.0                       ║
║                                                                              ║
║  🎯 Multi-Chain Monitoring: Ethereum • Base • Solana                       ║
║  📊 Advanced Analysis: Contract • Social • Technical                        ║
║  🤖 Automated Trading: Risk Management • Position Sizing                    ║
║  📱 Telegram Integration: Notifications • Signal Monitoring                 ║
║  🌐 Web Dashboard: Real-time Monitoring • Analytics                         ║
║                                                                              ║
║  ⚠️  USE AT YOUR OWN RISK - CRYPTOCURRENCY TRADING IS HIGHLY RISKY         ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def check_requirements():
    """Check if all requirements are installed."""
    try:
        required_modules = [
            'web3', 'aiohttp', 'asyncio', 'telethon'
        ]
        
        missing_modules = []
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            print(f"❌ Missing required modules: {', '.join(missing_modules)}")
            print("Install with: pip install -r requirements.txt")
            return False
        
        return True
        
    except Exception as e:
        print(f"Error checking requirements: {e}")
        return False


def display_usage_examples():
    """Display usage examples."""
    examples = """
🚀 USAGE EXAMPLES:

Basic Usage:
  python main_with_trading.py --mode paper
  
With Auto-Trading:
  python main_with_trading.py --mode paper --auto-trading
  
With Telegram Signals:
  python main_with_trading.py --mode paper --enable-telegram-signals
  
Live Trading (DANGEROUS):
  python main_with_trading.py --mode live --auto-trading
  
Testing:
  python main_with_trading.py --test-telegram
  python main_with_trading.py --generate-test-opportunities
  
Console Only:
  python main_with_trading.py --mode paper --disable-dashboard
  
Full Features:
  python main_with_trading.py --mode paper --auto-trading --enable-telegram-signals

📱 TELEGRAM SETUP:
  1. Create bot with @BotFather
  2. Get API credentials from https://my.telegram.org
  3. Add to .env file:
     TELEGRAM_BOT_TOKEN=your_token
     TELEGRAM_CHAT_ID=your_chat_id
     TELEGRAM_API_ID=your_api_id
     TELEGRAM_API_HASH=your_api_hash

🌐 WEB DASHBOARD:
  Access at: http://localhost:8000
  Features: Live monitoring, analytics, controls
    """
    print(examples)


if __name__ == "__main__":
    try:
        # Display startup banner
        display_startup_banner()
        
        # Check if help requested
        if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
            display_usage_examples()
            sys.exit(0)
        
        # Check requirements
        if not check_requirements():
            sys.exit(1)
        
        # Run main system
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n🛑 System interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)