#!/usr/bin/env python3
"""
Quick connection test and fix for DEX sniping system.
Run this to diagnose and fix the RPC connection issue.
"""

import os
import sys
from pathlib import Path

def create_env_file():
    """Create a working .env file with free RPC."""
    env_content = """# DEX Sniping - Free RPC Configuration
ETHEREUM_RPC_URL=https://ethereum-rpc.publicnode.com
POLYGON_RPC_URL=https://polygon-rpc.com
BSC_RPC_URL=https://bsc-dataseed.binance.org/
ARBITRUM_RPC_URL=https://arb1.arbitrum.io/rpc

# Optional API keys (all free tiers)
ETHERSCAN_API_KEY=
MORALIS_API_KEY=
COINGECKO_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
"""
    
    env_path = Path(".env")
    
    if env_path.exists():
        print("📁 Found existing .env file")
        
        # Check if it has ETHEREUM_RPC_URL
        with open(env_path, 'r') as f:
            content = f.read()
            
        if 'ETHEREUM_RPC_URL=' not in content:
            print("⚠️  Adding missing ETHEREUM_RPC_URL to .env")
            with open(env_path, 'a') as f:
                f.write('\n# Added by connection test\n')
                f.write('ETHEREUM_RPC_URL=https://ethereum-rpc.publicnode.com\n')
        else:
            print("✅ .env already has ETHEREUM_RPC_URL")
    else:
        print("📝 Creating new .env file with free RPC")
        with open(env_path, 'w') as f:
            f.write(env_content)
    
    return env_path

def test_rpc_connection():
    """Test RPC connection with the current settings."""
    try:
        # Import and test settings
        from config.settings import settings
        from web3 import Web3
        
        print(f"🔗 Testing RPC: {settings.networks.ethereum_rpc_url}")
        
        w3 = Web3(Web3.HTTPProvider(settings.networks.ethereum_rpc_url))
        
        if w3.is_connected():
            block = w3.eth.block_number
            print(f"✅ SUCCESS! Connected to Ethereum - Block: {block}")
            return True
        else:
            print("❌ Failed to connect")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_alternative_rpcs():
    """Test alternative free RPC endpoints."""
    print("\n🔄 Testing alternative free RPCs...")
    
    free_rpcs = [
        "https://ethereum-rpc.publicnode.com",
        "https://rpc.ankr.com/eth", 
        "https://eth.public-rpc.com",
        "https://ethereum.blockpi.network/v1/rpc/public",
        "https://rpc.payload.de"
    ]
    
    try:
        from web3 import Web3
        
        for rpc in free_rpcs:
            print(f"   Testing: {rpc}")
            try:
                w3 = Web3(Web3.HTTPProvider(rpc))
                if w3.is_connected():
                    block = w3.eth.block_number
                    print(f"   ✅ Working! Block: {block}")
                    return rpc
                else:
                    print(f"   ❌ Failed")
            except Exception as e:
                print(f"   ❌ Error: {str(e)[:30]}...")
    
    except ImportError:
        print("❌ web3 not installed. Run: pip install web3")
        return None
    
    return None

def update_env_with_working_rpc(working_rpc):
    """Update .env file with a working RPC."""
    env_path = Path(".env")
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        # Update or add ETHEREUM_RPC_URL
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('ETHEREUM_RPC_URL='):
                lines[i] = f'ETHEREUM_RPC_URL={working_rpc}\n'
                updated = True
                break
        
        if not updated:
            lines.append(f'\nETHEREUM_RPC_URL={working_rpc}\n')
        
        with open(env_path, 'w') as f:
            f.writelines(lines)
        
        print(f"✅ Updated .env with working RPC: {working_rpc}")
    else:
        print("❌ .env file not found")

def main():
    """Main diagnostic and fix function."""
    print("🚀 DEX SNIPING - CONNECTION DIAGNOSTIC & FIX")
    print("=" * 50)
    
    # Step 1: Ensure .env file exists
    print("Step 1: Checking .env file...")
    env_path = create_env_file()
    
    # Step 2: Test current RPC
    print("\nStep 2: Testing current RPC connection...")
    if test_rpc_connection():
        print("\n🎉 SUCCESS! Your connection is working.")
        print("You can now run your DEX sniping system.")
        return
    
    # Step 3: Find working RPC
    print("\nStep 3: Finding working RPC...")
    working_rpc = test_alternative_rpcs()
    
    if working_rpc:
        print(f"\n✅ Found working RPC: {working_rpc}")
        update_env_with_working_rpc(working_rpc)
        
        # Test again
        print("\nStep 4: Testing updated configuration...")
        if test_rpc_connection():
            print("\n🎉 FIXED! Your connection is now working.")
        else:
            print("\n❌ Still having issues. Check your internet connection.")
    else:
        print("\n❌ No working RPCs found. Check your internet connection.")
        print("\n💡 Try these manual steps:")
        print("1. Check your internet connection")
        print("2. Try a VPN if you're in a restricted region")
        print("3. Use a paid RPC service (Alchemy/Infura free tiers)")

if __name__ == "__main__":
    main()