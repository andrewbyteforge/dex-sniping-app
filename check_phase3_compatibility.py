"""
Check environment compatibility for Phase 3 optimizations.
"""

import sys
import importlib
from typing import Dict, Tuple

def check_import(module_name: str, feature: str) -> Tuple[bool, str]:
    """Check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        return True, f"✅ {feature}"
    except ImportError as e:
        return False, f"❌ {feature}: {str(e)}"

def check_web3_features() -> Dict[str, bool]:
    """Check specific Web3 features."""
    features = {}
    
    try:
        from web3 import Web3
        features['web3_basic'] = True
        
        # Check WebSocket provider
        try:
            from web3.providers import WebsocketProvider
            features['websocket_modern'] = True
        except ImportError:
            try:
                from web3.providers.websocket import WebsocketProvider
                features['websocket_legacy'] = True
            except ImportError:
                features['websocket'] = False
        
        # Check middleware
        try:
            from web3.middleware import geth_poa_middleware
            features['poa_middleware'] = True
        except ImportError:
            features['poa_middleware'] = False
            
    except ImportError:
        features['web3_basic'] = False
    
    return features

def main():
    """Run compatibility checks."""
    print("🔍 PHASE 3 COMPATIBILITY CHECK")
    print("=" * 50)
    
    # Core requirements
    print("\n📦 Core Requirements:")
    core_modules = [
        ("web3", "Web3.py"),
        ("aiohttp", "Async HTTP"),
        ("asyncio", "Async support"),
        ("decimal", "Decimal math"),
        ("dataclasses", "Dataclasses"),
    ]
    
    core_ok = True
    for module, feature in core_modules:
        ok, msg = check_import(module, feature)
        print(f"   {msg}")
        if not ok:
            core_ok = False
    
    # Web3 specific features
    print("\n🔧 Web3 Features:")
    web3_features = check_web3_features()
    
    if web3_features.get('web3_basic'):
        print("   ✅ Web3 basic functionality")
        
        if web3_features.get('websocket_modern'):
            print("   ✅ WebSocket support (modern)")
        elif web3_features.get('websocket_legacy'):
            print("   ✅ WebSocket support (legacy)")
        else:
            print("   ⚠️  WebSocket support not available (will use HTTP)")
        
        if web3_features.get('poa_middleware'):
            print("   ✅ PoA middleware support")
        else:
            print("   ⚠️  PoA middleware not available (Base/Polygon may have issues)")
    else:
        print("   ❌ Web3 not installed!")
    
    # Optional enhancements
    print("\n🚀 Optional Enhancements:")
    optional_modules = [
        ("websockets", "WebSocket client"),
        ("eth_account", "Ethereum accounts"),
        ("rlp", "RLP encoding"),
    ]
    
    for module, feature in optional_modules:
        ok, msg = check_import(module, feature)
        print(f"   {msg}")
    
    # Phase 3 components
    print("\n📂 Phase 3 Components:")
    phase3_components = [
        ("trading.mev_protection", "MEV Protection"),
        ("trading.gas_optimizer", "Gas Optimizer"),
        ("trading.transaction_simulator", "Transaction Simulator"),
        ("infrastructure.node_manager", "Node Manager"),
    ]
    
    components_ok = True
    for module, feature in phase3_components:
        ok, msg = check_import(module, feature)
        print(f"   {msg}")
        if not ok:
            components_ok = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY:")
    
    if core_ok and components_ok:
        print("✅ All core components are ready!")
        print("✅ You can run: python test_phase3_optimizations.py")
    else:
        print("⚠️  Some components need attention")
        print("\n📝 To fix issues:")
        print("1. Install missing packages:")
        print("   pip install web3 aiohttp websockets eth-account")
        print("2. Make sure all Phase 3 files are in place")
        print("3. Check that __init__.py files exist in all directories")
    
    # Web3 version info
    try:
        import web3
        print(f"\n📌 Web3 version: {web3.__version__}")
    except:
        pass
    
    # Python version
    print(f"📌 Python version: {sys.version.split()[0]}")


if __name__ == "__main__":
    main()