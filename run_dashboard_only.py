"""
Run dashboard server independently for testing.
Fixed import to avoid __init__.py conflicts.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import directly from the module to avoid __init__.py issues
import importlib.util

def load_dashboard_module():
    """Load dashboard module directly."""
    try:
        spec = importlib.util.spec_from_file_location(
            "dashboard_server", 
            "api/dashboard_server.py"
        )
        dashboard_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dashboard_module)
        return dashboard_module.app, dashboard_module.dashboard_server
    except Exception as e:
        print(f"Failed to load dashboard module: {e}")
        raise

async def main():
    """Run dashboard server standalone."""
    print("🚀 Starting Dashboard Server (Standalone Mode)")
    print("Dashboard will be available at: http://localhost:8000")
    print("Press Ctrl+C to stop")
    
    try:
        # Load dashboard module
        app, dashboard_server = load_dashboard_module()
        
        # Initialize dashboard
        await dashboard_server.initialize()
        
        # Create some test data
        test_opportunity = type('TestOpp', (), {
            'token': type('Token', (), {
                'symbol': 'TEST',
                'address': '0x123456789abcdef'
            })(),
            'metadata': {
                'chain': 'ETHEREUM',
                'recommendation': {
                    'action': 'STRONG_BUY',
                    'confidence': 'HIGH',
                    'score': 0.85
                }
            },
            'liquidity': type('Liquidity', (), {
                'liquidity_usd': 50000,
                'dex_name': 'Uniswap V2',
                'pair_address': '0xabcdef123456789'
            })(),
            'contract_analysis': type('Analysis', (), {
                'risk_level': type('Risk', (), {'value': 'low'})()
            })()
        })()
        
        await dashboard_server.add_opportunity(test_opportunity)
        print("✅ Test opportunity added")
        
        # Start server
        import uvicorn
        
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()
        
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDashboard stopped")