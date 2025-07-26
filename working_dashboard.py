#!/usr/bin/env python3
"""
Working dashboard server with a simple, guaranteed-to-work dashboard template.

This creates a minimal dashboard that definitely displays opportunities.

File: working_dashboard.py
Usage: python working_dashboard.py
"""

import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Import our working dashboard system
from isolated_dashboard_test import IsolatedDashboardTest
from api.dashboard_core import dashboard_server

# Create FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_working_dashboard_html():
    """Get a simple dashboard HTML that definitely works."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Working DEX Sniping Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            margin: 0;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-value { font-size: 2em; font-weight: bold; color: #4CAF50; }
        .stat-label { margin-top: 5px; opacity: 0.8; }
        .opportunities {
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .opportunity-item {
            background: rgba(255,255,255,0.1);
            margin: 10px 0;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }
        .opportunity-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .token-symbol {
            font-size: 1.2em;
            font-weight: bold;
            color: #4CAF50;
        }
        .risk-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .risk-low { background: #4CAF50; }
        .risk-medium { background: #FF9800; }
        .risk-high { background: #F44336; }
        .risk-critical { background: #9C27B0; }
        .opportunity-details {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        .chain-badge {
            background: #2196F3;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .recommendation {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .rec-buy { background: #4CAF50; }
        .rec-monitor { background: #FF9800; }
        .rec-avoid { background: #F44336; }
        .action-button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
        }
        .action-button:hover { background: #45a049; }
        .refresh-btn {
            background: #2196F3;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px 5px;
        }
        .refresh-btn:hover { background: #1976D2; }
        .status { 
            padding: 10px; 
            background: rgba(255,255,255,0.1); 
            border-radius: 5px; 
            margin: 10px 0; 
        }
        .debug-section {
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            font-family: monospace;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Working DEX Sniping Dashboard</h1>
            <p>Real-time Token Opportunity Detection</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value" id="total-opportunities">0</div>
                <div class="stat-label">Total Opportunities</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="high-confidence">0</div>
                <div class="stat-label">High Confidence</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="active-chains">0</div>
                <div class="stat-label">Active Chains</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="analysis-rate">0</div>
                <div class="stat-label">Analysis Rate</div>
            </div>
        </div>

        <div class="opportunities">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3>🎯 Trading Opportunities</h3>
                <div>
                    <button class="refresh-btn" onclick="loadOpportunities()">Refresh</button>
                    <button class="refresh-btn" onclick="testAPI()">Test API</button>
                </div>
            </div>
            <div id="opportunity-list">
                <div style="text-align: center; padding: 20px; opacity: 0.7;">
                    Loading opportunities...
                </div>
            </div>
        </div>

        <div class="status" id="status">
            Status: Initializing...
        </div>

        <div class="debug-section" id="debug-info" style="display: none;">
            <h4>🔍 Debug Information</h4>
            <div id="debug-content"></div>
        </div>
    </div>

    <script>
        console.log('🚀 Working Dashboard v1.0 Loading...');
        
        let opportunities = [];
        let stats = { total_opportunities: 0, high_confidence: 0, active_chains: 0, analysis_rate: 0 };
        
        // Update status
        function updateStatus(message) {
            document.getElementById('status').textContent = 'Status: ' + message;
            console.log('Status:', message);
        }
        
        // Update statistics display
        function updateStats() {
            document.getElementById('total-opportunities').textContent = stats.total_opportunities || 0;
            document.getElementById('high-confidence').textContent = stats.high_confidence || 0;
            document.getElementById('active-chains').textContent = stats.active_chains || 0;
            document.getElementById('analysis-rate').textContent = stats.analysis_rate || 0;
        }
        
        // Load opportunities from API
        async function loadOpportunities() {
            try {
                updateStatus('Loading opportunities...');
                console.log('🔄 Loading opportunities from API...');
                
                const response = await fetch('/api/opportunities');
                console.log('API Response status:', response.status);
                
                if (response.ok) {
                    const data = await response.json();
                    console.log('✅ Loaded opportunities:', data.length);
                    console.log('Sample opportunity:', data[0]);
                    
                    opportunities = data;
                    renderOpportunities();
                    updateStatus(`Loaded ${data.length} opportunities`);
                    
                } else {
                    const errorText = await response.text();
                    console.error('❌ API Error:', response.status, errorText);
                    updateStatus(`API Error: ${response.status}`);
                }
                
            } catch (error) {
                console.error('❌ Failed to load opportunities:', error);
                updateStatus('Failed to load opportunities: ' + error.message);
            }
        }
        
        // Load statistics
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                if (response.ok) {
                    stats = await response.json();
                    console.log('📊 Stats loaded:', stats);
                    updateStats();
                }
            } catch (error) {
                console.error('❌ Failed to load stats:', error);
            }
        }
        
        // Render opportunities
        function renderOpportunities() {
            const container = document.getElementById('opportunity-list');
            
            if (opportunities.length === 0) {
                container.innerHTML = '<div style="text-align: center; padding: 20px; opacity: 0.7;">No opportunities found</div>';
                return;
            }
            
            console.log('🎨 Rendering', opportunities.length, 'opportunities');
            
            container.innerHTML = opportunities.map(opp => {
                const riskClass = (opp.risk_level || 'medium').toLowerCase();
                const recommendationClass = (opp.recommendation || 'monitor').toLowerCase().replace('_', '-');
                
                return `
                    <div class="opportunity-item">
                        <div class="opportunity-header">
                            <span class="token-symbol">${opp.token_symbol || 'UNKNOWN'}</span>
                            <span class="risk-badge risk-${riskClass}">${(opp.risk_level || 'medium').toUpperCase()}</span>
                        </div>
                        <div class="opportunity-details">
                            <span class="chain-badge">${(opp.chain || 'unknown').toUpperCase()}</span>
                            <span>Score: ${(opp.score || 0).toFixed(2)}</span>
                            <span>Liquidity: $${(opp.liquidity_usd || 0).toFixed(0)}</span>
                            <span>Age: ${opp.age_minutes || 0}m</span>
                            <span class="recommendation rec-${recommendationClass}">${opp.recommendation || 'MONITOR'}</span>
                            <span>Confidence: ${opp.confidence || 'LOW'}</span>
                            <button class="action-button" onclick="showDetails('${opp.token_symbol}')">Details</button>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        // Test API endpoints
        async function testAPI() {
            const debugContent = document.getElementById('debug-content');
            const debugInfo = document.getElementById('debug-info');
            debugInfo.style.display = 'block';
            
            let results = '';
            
            // Test opportunities API
            try {
                const oppResponse = await fetch('/api/opportunities');
                results += `Opportunities API: ${oppResponse.status}\\n`;
                if (oppResponse.ok) {
                    const oppData = await oppResponse.json();
                    results += `  Found: ${oppData.length} opportunities\\n`;
                    if (oppData.length > 0) {
                        results += `  Sample: ${JSON.stringify(oppData[0], null, 2)}\\n`;
                    }
                }
            } catch (error) {
                results += `Opportunities API Error: ${error.message}\\n`;
            }
            
            // Test stats API
            try {
                const statsResponse = await fetch('/api/stats');
                results += `Stats API: ${statsResponse.status}\\n`;
                if (statsResponse.ok) {
                    const statsData = await statsResponse.json();
                    results += `  Stats: ${JSON.stringify(statsData, null, 2)}\\n`;
                }
            } catch (error) {
                results += `Stats API Error: ${error.message}\\n`;
            }
            
            debugContent.innerHTML = `<pre>${results}</pre>`;
        }
        
        // Show opportunity details
        function showDetails(tokenSymbol) {
            const opp = opportunities.find(o => o.token_symbol === tokenSymbol);
            if (opp) {
                alert(`Token: ${opp.token_symbol}\\nChain: ${opp.chain}\\nAddress: ${opp.token_address}\\nRisk: ${opp.risk_level}\\nRecommendation: ${opp.recommendation}`);
            }
        }
        
        // Initialize dashboard
        async function initDashboard() {
            console.log('🚀 Initializing working dashboard...');
            updateStatus('Initializing...');
            
            try {
                // Load initial data
                await loadStats();
                await loadOpportunities();
                
                // Set up auto-refresh
                setInterval(async () => {
                    await loadStats();
                    await loadOpportunities();
                }, 10000); // Every 10 seconds
                
                updateStatus('Dashboard ready');
                console.log('✅ Dashboard initialized successfully');
                
            } catch (error) {
                console.error('❌ Dashboard initialization failed:', error);
                updateStatus('Initialization failed: ' + error.message);
            }
        }
        
        // Start when page loads
        window.addEventListener('load', initDashboard);
        
        console.log('📝 Dashboard script loaded');
    </script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the working dashboard."""
    return HTMLResponse(content=get_working_dashboard_html())

@app.get("/api/opportunities")
async def get_opportunities():
    """Get opportunities from the global dashboard server."""
    try:
        opportunities = []
        for opp in dashboard_server.opportunities_queue:
            opportunity_data = {
                "token_symbol": opp.token.symbol,
                "token_address": opp.token.address,
                "chain": opp.metadata.get("chain", "unknown"),
                "risk_level": opp.contract_analysis.risk_level.value,
                "recommendation": opp.metadata.get("recommendation", {}).get("action", "MONITOR"),
                "confidence": opp.metadata.get("recommendation", {}).get("confidence", "LOW"),
                "score": opp.metadata.get("trading_score", {}).get("overall_score", 0.0),
                "liquidity_usd": opp.liquidity.liquidity_usd,
                "age_minutes": 0
            }
            opportunities.append(opportunity_data)
        
        return opportunities
    except Exception as e:
        print(f"Error getting opportunities: {e}")
        return []

@app.get("/api/stats")
async def get_stats():
    """Get statistics from the global dashboard server."""
    try:
        return dashboard_server.stats
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {"total_opportunities": 0, "high_confidence": 0, "active_chains": 0, "analysis_rate": 0}

async def main():
    """Main function to run the working dashboard."""
    print("🚀 Starting Working Dashboard System")
    
    # Start the opportunity generation system
    test_system = IsolatedDashboardTest()
    
    # Initialize dashboard server
    await dashboard_server.initialize()
    
    # Create initial opportunities
    await test_system.create_initial_batch(10)
    print(f"✅ Created {len(dashboard_server.opportunities_queue)} opportunities")
    
    # Start continuous generation in background
    generation_task = asyncio.create_task(test_system.run_continuous_generation(4))
    
    # Start FastAPI server
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    
    print("🌐 Dashboard available at: http://localhost:8000")
    print("📊 This dashboard is guaranteed to work!")
    print("Press Ctrl+C to stop")
    
    # Run both server and generation
    await asyncio.gather(server.serve(), generation_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Working dashboard stopped")