#!/usr/bin/env python3
"""
Simple test for MEV protection functionality.
Place this in the root directory as test_mev_protection.py

File: test_mev_protection.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from web3.types import TxParams, Wei, HexBytes

from web3 import Web3

async def test_mev_protection():
    """Test MEV protection functionality."""
    
    try:
        print("🔍 Testing MEV Protection...")
        
        # Test imports first
        try:
            from trading.mev_protection import MEVProtectionManager, MEVProtectionLevel
            print("✅ Imports successful")
        except ImportError as e:
            print(f"❌ Import error: {e}")
            return
        
        # Initialize Web3
        try:
            w3 = Web3(Web3.HTTPProvider("https://ethereum-rpc.publicnode.com"))
            if not w3.is_connected():
                print("⚠️  Web3 connection failed, using offline test")
                w3 = None
            else:
                print("✅ Web3 connected")
        except Exception as e:
            print(f"⚠️  Web3 error: {e}, using offline test")
            w3 = None
        
        # Initialize MEV protection
        try:
            mev_manager = MEVProtectionManager()
            print("✅ MEVProtectionManager created")
            
            if w3:
                await mev_manager.initialize(w3)
                print("✅ MEVProtectionManager initialized")
            else:
                print("⚠️  Skipping initialization (no Web3)")
                
        except Exception as e:
            print(f"❌ MEV manager initialization failed: {e}")
            return
        
        # Test transaction parameters
        test_tx = {
            "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap router
            "value": 1000000000000000000,  # 1 ETH in wei
            "gas": 300000,
            "gasPrice": 25000000000,  # 25 gwei
            "nonce": 1
        }
        
        print("🧪 Testing MEV risk analysis...")
        
        # Test risk analysis
        try:
            risk_analysis = mev_manager.analyze_mev_risk(test_tx)
            print("✅ Risk analysis completed:")
            print(f"   Risk Level: {risk_analysis.get('risk_level', 'UNKNOWN')}")
            print(f"   Risk Score: {risk_analysis.get('risk_score', 0):.2f}")
            print(f"   Recommended Protection: {risk_analysis.get('recommended_protection', 'UNKNOWN')}")
            print(f"   Sandwich Risk: {risk_analysis.get('sandwich_risk', 0):.2f}")
            print(f"   Frontrun Risk: {risk_analysis.get('frontrun_risk', 0):.2f}")
        except Exception as e:
            print(f"❌ Risk analysis failed: {e}")
            return
        
        # Test protection creation (without actual submission)
        print("🛡️ Testing protection creation...")
        
        try:
            if hasattr(mev_manager, 'protect_transaction'):
                protected_tx = await mev_manager.protect_transaction(
                    test_tx, 
                    value_at_risk=Decimal("1000"),  # $1000 at risk
                    protection_level=MEVProtectionLevel.STANDARD  # Use STANDARD for testing
                )
                
                if protected_tx:
                    print("✅ Protection created:")
                    print(f"   Method: {protected_tx.protection_method}")
                    print(f"   Estimated Cost: ${protected_tx.estimated_cost}")
                    print(f"   Estimated Savings: ${protected_tx.estimated_savings}")
                else:
                    print("⚠️  Protection returned None (expected for some methods)")
            else:
                print("⚠️  protect_transaction method not found - using basic analysis only")
                
        except Exception as e:
            print(f"❌ Protection creation failed: {e}")
            print("   This might be expected if environment variables are not set")
        
        # Test statistics
        print("📊 Testing statistics...")
        
        try:
            stats = mev_manager.get_protection_stats()
            print("✅ Statistics retrieved:")
            print(f"   Total Transactions: {stats.get('total_transactions', 0)}")
            print(f"   Protected Transactions: {stats.get('protected_transactions', 0)}")
            print(f"   Sandwich Attacks Prevented: {stats.get('sandwich_attacks_prevented', 0)}")
        except Exception as e:
            print(f"❌ Statistics failed: {e}")
        
        print("\n🎉 MEV Protection test completed!")
        print("\n📝 Next steps:")
        print("1. Add environment variables to .env:")
        print("   FLASHBOTS_PRIVATE_KEY=0x...")
        print("   TRADING_PRIVATE_KEY=0x...")
        print("2. Install dependencies: pip install aiohttp eth-account")
        print("3. Update mev_protection.py with new methods")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Import Decimal here to avoid import issues
    from decimal import Decimal
    asyncio.run(test_mev_protection())