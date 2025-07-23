"""
Test the dashboard server independently to debug connection issues.
"""

import asyncio
import uvicorn
from api.dashboard_server import app, dashboard_server

async def test_dashboard():
    """Test dashboard server independently."""
    print("🔧 TESTING DASHBOARD STANDALONE")
    print("=" * 50)
    
    try:
        # Initialize dashboard
        await dashboard_server.initialize()
        print("✅ Dashboard initialized")
        
        # Test adding a mock opportunity
        mock_opportunity = type('MockOpportunity', (), {
            'token': type('MockToken', (), {
                'symbol': 'TEST',
                'address': '0x123...'
            })(),
            'metadata': {'chain': 'ETHEREUM'},
            'liquidity': type('MockLiquidity', (), {
                'liquidity_usd': 10000
            })(),
            'contract_analysis': type('MockAnalysis', (), {
                'risk_level': type('RiskLevel', (), {'value': 'medium'})()
            })()
        })()
        
        await dashboard_server.add_opportunity(mock_opportunity)
        print("✅ Test opportunity added")
        
        # Test stats
        stats = dashboard_server.get_safe_portfolio_summary()
        print(f"✅ Portfolio stats: {stats}")
        
        print("\n🚀 Starting dashboard server on http://localhost:8000")
        print("Press Ctrl+C to stop")
        
        # Start server
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            access_log=True
        )
        
        server = uvicorn.Server(config)
        await server.serve()
        
    except Exception as e:
        print(f"❌ Dashboard test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(test_dashboard())
    except KeyboardInterrupt:
        print("\nDashboard test stopped")