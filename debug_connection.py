#!/usr/bin/env python3
"""
Debug script to test RPC connection and environment loading.
"""

import os
import sys
from dotenv import load_dotenv
from web3 import Web3

def test_env_loading():
    """Test if .env file is being loaded correctly."""
    print("=== TESTING ENVIRONMENT LOADING ===")
    
    # Load .env file
    load_dotenv()
    
    # Check if .env file exists
    env_path = ".env"
    if os.path.exists(env_path):
        print(f"✅ .env file found at: {os.path.abspath(env_path)}")
        
        # Read and display .env content
        with open(env_path, 'r') as f:
            content = f.read()
            print(f"📄 .env content:\n{content}")
    else:
        print(f"❌ .env file NOT found at: {os.path.abspath(env_path)}")
        return False
    
    # Check environment variable
    rpc_url = os.getenv('ETHEREUM_RPC_URL')
    if rpc_url:
        print(f"✅ ETHEREUM_RPC_URL loaded: {rpc_url}")
        return rpc_url
    else:
        print("❌ ETHEREUM_RPC_URL not found in environment")
        return None

def test_rpc_connection(rpc_url):
    """Test connection to RPC endpoint."""
    print(f"\n=== TESTING RPC CONNECTION ===")
    print(f"🔗 Connecting to: {rpc_url}")
    
    try:
        # Create Web3 instance
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # Test connection
        if w3.is_connected():
            print("✅ Successfully connected to Ethereum node!")
            
            # Get additional info
            try:
                block_number = w3.eth.block_number
                print(f"📊 Current block number: {block_number}")
                
                chain_id = w3.eth.chain_id
                print(f"🔗 Chain ID: {chain_id}")
                
                return True
            except Exception as e:
                print(f"⚠️  Connected but error getting info: {e}")
                return True
        else:
            print("❌ Failed to connect to Ethereum node")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_multiple_rpcs():
    """Test multiple RPC endpoints to find working ones."""
    print(f"\n=== TESTING MULTIPLE RPC ENDPOINTS ===")
    
    test_rpcs = [
        "https://rpc.ankr.com/eth",
        "https://eth-mainnet.g.alchemy.com/v2/demo",
        "https://mainnet.infura.io/v3/demo",
        "https://eth.llamarpc.com",
        "https://rpc.payload.de",
        "https://eth-rpc.gateway.pokt.network",
    ]
    
    working_rpcs = []
    
    for rpc in test_rpcs:
        print(f"\n🔍 Testing: {rpc}")
        try:
            w3 = Web3(Web3.HTTPProvider(rpc))
            if w3.is_connected():
                try:
                    block = w3.eth.block_number
                    print(f"✅ WORKING! Block: {block}")
                    working_rpcs.append(rpc)
                except:
                    print("🔗 Connected but slow/limited")
            else:
                print("❌ Failed to connect")
        except Exception as e:
            print(f"❌ Error: {str(e)[:50]}...")
    
    return working_rpcs

def main():
    """Main debug function."""
    print("🔧 DEX SNIPING - RPC CONNECTION DEBUG")
    print("=" * 50)
    
    # Test 1: Environment loading
    rpc_url = test_env_loading()
    
    # Test 2: RPC connection with loaded URL
    if rpc_url:
        success = test_rpc_connection(rpc_url)
        if success:
            print("\n🎉 SUCCESS! Your setup is working correctly.")
            return
    
    # Test 3: Try multiple RPC endpoints
    print("\n🔍 Your RPC isn't working. Let's find working alternatives...")
    working_rpcs = test_multiple_rpcs()
    
    if working_rpcs:
        print(f"\n✅ WORKING RPC ENDPOINTS FOUND:")
        for i, rpc in enumerate(working_rpcs, 1):
            print(f"   {i}. {rpc}")
        
        print(f"\n📝 UPDATE YOUR .env FILE WITH ONE OF THESE:")
        print(f"ETHEREUM_RPC_URL={working_rpcs[0]}")
    else:
        print("\n❌ No working RPC endpoints found. Check your internet connection.")

if __name__ == "__main__":
    main()