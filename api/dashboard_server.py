"""
Simplified and fixed dashboard server for DEX sniping system.
Focuses on reliability and basic functionality.
"""

import asyncio
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Simple logging without complex dependencies
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DashboardServer")

# Create FastAPI app with minimal config
app = FastAPI(
    title="DEX Sniping Dashboard",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimpleDashboardServer:
    """Simplified dashboard server with minimal dependencies."""
    
    def __init__(self):
        """Initialize the simple dashboard server."""
        self.connected_clients: List[WebSocket] = []
        self.opportunities: List[Dict] = []
        self.stats = {
            "total_opportunities": 0,
            "high_confidence": 0,
            "active_chains": 3,
            "analysis_rate": 0,
            "uptime_start": datetime.now()
        }
        
        # Trading components (will be set by main system)
        self.trading_executor = None
        self.risk_manager = None
        self.position_manager = None
        
        logger.info("Simple dashboard server initialized")

    async def initialize(self):
        """Initialize the dashboard server."""
        try:
            logger.info("Dashboard server ready")
        except Exception as e:
            logger.error(f"Dashboard initialization error: {e}")
            raise

    async def add_opportunity(self, opportunity):
        """Add opportunity with safe error handling."""
        try:
            # Convert opportunity to simple dict
            if hasattr(opportunity, 'token'):
                opp_data = {
                    'token_symbol': getattr(opportunity.token, 'symbol', 'UNKNOWN'),
                    'token_address': getattr(opportunity.token, 'address', 'unknown'),
                    'chain': opportunity.metadata.get('chain', 'unknown') if hasattr(opportunity, 'metadata') else 'unknown',
                    'detected_at': datetime.now().isoformat(),
                    'risk_level': 'unknown',
                    'recommendation': 'UNKNOWN',
                    'confidence': 'UNKNOWN',
                    'score': 0.0,
                    'liquidity_usd': 0
                }
                
                # Try to get additional data safely
                try:
                    if hasattr(opportunity, 'liquidity'):
                        opp_data['liquidity_usd'] = getattr(opportunity.liquidity, 'liquidity_usd', 0)
                        opp_data['dex_name'] = getattr(opportunity.liquidity, 'dex_name', 'Unknown')
                        opp_data['pair_address'] = getattr(opportunity.liquidity, 'pair_address', 'unknown')
                except:
                    pass
                
                try:
                    if hasattr(opportunity, 'contract_analysis'):
                        risk_level = getattr(opportunity.contract_analysis, 'risk_level', None)
                        if risk_level and hasattr(risk_level, 'value'):
                            opp_data['risk_level'] = risk_level.value
                except:
                    pass
                
                try:
                    if hasattr(opportunity, 'metadata'):
                        recommendation = opportunity.metadata.get('recommendation', {})
                        opp_data['recommendation'] = recommendation.get('action', 'UNKNOWN')
                        opp_data['confidence'] = recommendation.get('confidence', 'UNKNOWN')
                        opp_data['score'] = recommendation.get('score', 0.0)
                        opp_data['reasons'] = recommendation.get('reasons', [])
                        opp_data['warnings'] = recommendation.get('warnings', [])
                except:
                    pass
                
            else:
                # Fallback for invalid objects
                opp_data = {
                    'token_symbol': 'UNKNOWN',
                    'token_address': 'unknown',
                    'chain': 'unknown',
                    'detected_at': datetime.now().isoformat(),
                    'risk_level': 'unknown',
                    'recommendation': 'UNKNOWN',
                    'confidence': 'UNKNOWN',
                    'score': 0.0,
                    'liquidity_usd': 0
                }
            
            # Add to opportunities list (keep last 100)
            self.opportunities.append(opp_data)
            if len(self.opportunities) > 100:
                self.opportunities.pop(0)
            
            # Update stats
            self.stats["total_opportunities"] += 1
            if opp_data.get('confidence') == 'HIGH':
                self.stats["high_confidence"] += 1
            
            # Broadcast to clients
            await self.broadcast_to_clients({
                "type": "new_opportunity",
                "data": opp_data
            })
            
            logger.info(f"Added opportunity: {opp_data['token_symbol']}")
            
        except Exception as e:
            logger.error(f"Error adding opportunity: {e}")

    async def broadcast_to_clients(self, message: Dict):
        """Broadcast message to connected WebSocket clients."""
        if not self.connected_clients:
            return
        
        disconnected = []
        message_str = json.dumps(message)
        
        for client in self.connected_clients:
            try:
                await client.send_text(message_str)
            except:
                disconnected.append(client)
        
        # Remove disconnected clients
        for client in disconnected:
            if client in self.connected_clients:
                self.connected_clients.remove(client)

    async def update_analysis_rate(self, rate: int):
        """Update analysis rate."""
        try:
            self.stats["analysis_rate"] = rate
            await self.broadcast_to_clients({
                "type": "stats_update",
                "data": {"analysis_rate": rate}
            })
        except Exception as e:
            logger.error(f"Error updating analysis rate: {e}")

    def get_safe_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary safely."""
        try:
            if self.position_manager and hasattr(self.position_manager, 'get_portfolio_summary'):
                return self.position_manager.get_portfolio_summary()
            else:
                return {
                    'total_positions': 0,
                    'total_trades': 0,
                    'success_rate': 0.0,
                    'total_pnl': 0.0,
                    'status': 'No position manager connected'
                }
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            return {'error': str(e)}

# Global dashboard instance
dashboard_server = SimpleDashboardServer()

@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    try:
        await dashboard_server.initialize()
        logger.info("Dashboard startup complete")
    except Exception as e:
        logger.error(f"Dashboard startup error: {e}")

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the main dashboard page."""
    try:
        # Check if custom template exists
        template_path = "web/templates/dashboard.html"
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        
        # Return basic dashboard
        return HTMLResponse(content=get_basic_dashboard_html())
        
    except Exception as e:
        logger.error(f"Dashboard page error: {e}")
        return HTMLResponse(content=f"<h1>Dashboard Error</h1><p>{e}</p>", status_code=500)

def get_basic_dashboard_html() -> str:
    """Get basic dashboard HTML with detailed modal functionality."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DEX Sniping Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: white;
                min-height: 100vh;
                padding: 20px;
            }
            .container { max-width: 1200px; margin: 0 auto; }
            .header {
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
                backdrop-filter: blur(10px);
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                backdrop-filter: blur(10px);
            }
            .stat-value { font-size: 2em; font-weight: bold; color: #4CAF50; }
            .stat-label { margin-top: 5px; opacity: 0.8; }
            .opportunities {
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
                padding: 20px;
                backdrop-filter: blur(10px);
            }
            .opportunity-item {
                background: rgba(255,255,255,0.1);
                margin: 10px 0;
                padding: 15px;
                border-radius: 8px;
                border-left: 4px solid #4CAF50;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .opportunity-item:hover {
                background: rgba(255,255,255,0.2);
                transform: translateY(-2px);
            }
            .opportunity-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            .token-symbol {
                font-size: 1.2em;
                font-weight: bold;
                color: #4CAF50;
            }
            .risk-badge {
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
            }
            .risk-low { background: rgba(76, 175, 80, 0.3); color: #4CAF50; }
            .risk-medium { background: rgba(255, 193, 7, 0.3); color: #FFC107; }
            .risk-high { background: rgba(244, 67, 54, 0.3); color: #F44336; }
            .risk-unknown { background: rgba(158, 158, 158, 0.3); color: #9E9E9E; }
            
            .opportunity-details {
                font-size: 0.9em;
                opacity: 0.9;
                line-height: 1.4;
            }
            .chain-badge {
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 10px;
                margin-right: 8px;
                background: rgba(33, 150, 243, 0.3);
                color: #2196F3;
            }
            .recommendation {
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 10px;
                margin-left: 8px;
                font-weight: bold;
            }
            .rec-strong_buy, .rec-strong-buy { background: rgba(76, 175, 80, 0.3); color: #4CAF50; }
            .rec-buy { background: rgba(33, 150, 243, 0.3); color: #2196F3; }
            .rec-watch { background: rgba(255, 193, 7, 0.3); color: #FFC107; }
            .rec-avoid { background: rgba(244, 67, 54, 0.3); color: #F44336; }
            .rec-unknown { background: rgba(158, 158, 158, 0.3); color: #9E9E9E; }
            
            .opportunity-actions {
                margin-top: 10px;
                display: flex;
                gap: 8px;
            }
            .action-btn {
                padding: 4px 12px;
                border: none;
                border-radius: 4px;
                background: rgba(33, 150, 243, 0.8);
                color: white;
                cursor: pointer;
                font-size: 12px;
                transition: all 0.3s ease;
            }
            .action-btn:hover {
                background: rgba(33, 150, 243, 1);
                transform: translateY(-1px);
            }
            .action-btn.details {
                background: rgba(156, 39, 176, 0.8);
            }
            .action-btn.details:hover {
                background: rgba(156, 39, 176, 1);
            }
            
            .status { color: #4CAF50; font-weight: bold; }
            .error { color: #f44336; }
            .connection-status {
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
            }
            .connected { background: #4CAF50; }
            .disconnected { background: #f44336; }
            
            /* Modal Styles */
            .modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.8);
                backdrop-filter: blur(5px);
                z-index: 1000;
                display: none;
                justify-content: center;
                align-items: center;
                animation: fadeIn 0.3s ease;
            }
            .modal-overlay.show {
                display: flex;
            }
            .modal-content {
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                max-width: 800px;
                max-height: 90vh;
                width: 90%;
                overflow-y: auto;
                animation: slideIn 0.3s ease;
            }
            .modal-header {
                padding: 20px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .modal-header h2 {
                margin: 0;
                color: #4CAF50;
                font-size: 24px;
            }
            .modal-close {
                background: none;
                border: none;
                color: white;
                font-size: 28px;
                cursor: pointer;
                padding: 0;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .modal-close:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            .modal-body {
                padding: 20px;
            }
            .detail-section {
                margin-bottom: 20px;
                padding: 15px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            .detail-section h3 {
                margin: 0 0 10px 0;
                color: #4CAF50;
                font-size: 16px;
                border-bottom: 1px solid rgba(76, 175, 80, 0.3);
                padding-bottom: 5px;
            }
            .detail-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 10px;
            }
            .detail-item {
                display: flex;
                flex-direction: column;
                gap: 3px;
            }
            .detail-item label {
                font-weight: 600;
                color: rgba(255, 255, 255, 0.7);
                font-size: 12px;
                text-transform: uppercase;
            }
            .detail-item span {
                color: white;
                font-size: 14px;
                word-break: break-all;
            }
            .address-text {
                font-family: monospace;
                font-size: 12px !important;
                color: #2196F3 !important;
            }
            .copy-btn {
                background: rgba(33, 150, 243, 0.3);
                border: 1px solid rgba(33, 150, 243, 0.5);
                color: #2196F3;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 10px;
                cursor: pointer;
                margin-top: 3px;
                align-self: flex-start;
            }
            .copy-btn:hover {
                background: rgba(33, 150, 243, 0.5);
            }
            .external-links {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-top: 10px;
            }
            .external-link {
                display: inline-block;
                padding: 6px 12px;
                background: rgba(33, 150, 243, 0.3);
                border: 1px solid rgba(33, 150, 243, 0.5);
                color: #2196F3;
                text-decoration: none;
                border-radius: 4px;
                font-size: 12px;
                transition: all 0.3s ease;
            }
            .external-link:hover {
                background: rgba(33, 150, 243, 0.5);
                transform: translateY(-1px);
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            @keyframes slideIn {
                from { transform: translateY(-50px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            
            @media (max-width: 768px) {
                .modal-content { width: 95%; margin: 20px; }
                .detail-grid { grid-template-columns: 1fr; }
                .opportunity-header { flex-direction: column; align-items: flex-start; gap: 5px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 DEX Sniping Dashboard</h1>
                <p>Real-time multi-chain token monitoring</p>
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
                    <div class="stat-value" id="analysis-rate">0</div>
                    <div class="stat-label">Analysis/Min</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="connected-clients">0</div>
                    <div class="stat-label">Connected Clients</div>
                </div>
            </div>
            
            <div class="opportunities">
                <h2>🎯 Live Opportunities</h2>
                <div id="opportunity-list">
                    <p>Connecting to live feed...</p>
                </div>
            </div>
        </div>
        
        <div id="connection-status" class="connection-status disconnected">
            Connecting...
        </div>
        
        <!-- Details Modal -->
        <div id="details-modal" class="modal-overlay">
            <div class="modal-content">
                <div class="modal-header">
                    <h2 id="modal-title">Token Details</h2>
                    <button class="modal-close" onclick="closeDetailsModal()">&times;</button>
                </div>
                <div class="modal-body" id="modal-body">
                    <!-- Content will be populated by JavaScript -->
                </div>
            </div>
        </div>
        
        <script>
            let ws = null;
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 5;
            let opportunities = []; // Store opportunities for details view
            
            function connectWebSocket() {
                try {
                    ws = new WebSocket('ws://localhost:8000/ws');
                    
                    ws.onopen = function() {
                        console.log('WebSocket connected');
                        updateConnectionStatus(true);
                        reconnectAttempts = 0;
                    };
                    
                    ws.onmessage = function(event) {
                        try {
                            const data = JSON.parse(event.data);
                            handleWebSocketMessage(data);
                        } catch (e) {
                            console.error('Error parsing message:', e);
                        }
                    };
                    
                    ws.onclose = function() {
                        console.log('WebSocket disconnected');
                        updateConnectionStatus(false);
                        
                        if (reconnectAttempts < maxReconnectAttempts) {
                            reconnectAttempts++;
                            setTimeout(connectWebSocket, 3000 * reconnectAttempts);
                        }
                    };
                    
                    ws.onerror = function(error) {
                        console.error('WebSocket error:', error);
                        updateConnectionStatus(false);
                    };
                    
                } catch (error) {
                    console.error('WebSocket connection error:', error);
                    updateConnectionStatus(false);
                }
            }
            
            function handleWebSocketMessage(data) {
                switch (data.type) {
                    case 'new_opportunity':
                        addOpportunityToList(data.data);
                        break;
                    case 'stats_update':
                        updateStats(data.data);
                        break;
                }
            }
            
            function addOpportunityToList(opportunity) {
                const list = document.getElementById('opportunity-list');
                
                // Add to opportunities array for details view
                opportunities.unshift(opportunity);
                if (opportunities.length > 50) {
                    opportunities.pop();
                }
                
                const item = document.createElement('div');
                item.className = 'opportunity-item';
                item.innerHTML = `
                    <div class="opportunity-header">
                        <span class="token-symbol">${opportunity.token_symbol}</span>
                        <span class="risk-badge risk-${opportunity.risk_level}">${opportunity.risk_level}</span>
                    </div>
                    <div class="opportunity-details">
                        <span class="chain-badge">${opportunity.chain}</span>
                        Recommendation: <span class="recommendation rec-${opportunity.recommendation.toLowerCase().replace('_', '-')}">${opportunity.recommendation}</span><br>
                        Confidence: ${opportunity.confidence} | Score: ${opportunity.score.toFixed(2)}<br>
                        Liquidity: $${opportunity.liquidity_usd.toLocaleString()}<br>
                        <small>Detected: ${new Date(opportunity.detected_at).toLocaleTimeString()}</small>
                    </div>
                    <div class="opportunity-actions">
                        <button class="action-btn" onclick="executeTrade('${opportunity.token_symbol}')">Trade</button>
                        <button class="action-btn details" onclick="showTokenDetails('${opportunity.token_address}')">Details</button>
                    </div>
                `;
                
                list.insertBefore(item, list.firstChild);
                
                // Keep only last 10 opportunities visible
                while (list.children.length > 10) {
                    list.removeChild(list.lastChild);
                }
                
                // Update opportunity count
                const totalEl = document.getElementById('total-opportunities');
                totalEl.textContent = parseInt(totalEl.textContent) + 1;
                
                if (opportunity.confidence === 'HIGH') {
                    const highConfEl = document.getElementById('high-confidence');
                    highConfEl.textContent = parseInt(highConfEl.textContent) + 1;
                }
            }
            
            function showTokenDetails(tokenAddress) {
                const opportunity = opportunities.find(opp => opp.token_address === tokenAddress);
                if (!opportunity) {
                    alert('Opportunity details not found');
                    return;
                }
                
                // Update modal title
                document.getElementById('modal-title').textContent = `${opportunity.token_symbol} - Detailed Analysis`;
                
                // Build modal content
                const modalBody = document.getElementById('modal-body');
                modalBody.innerHTML = `
                    <div class="detail-section">
                        <h3>Token Information</h3>
                        <div class="detail-grid">
                            <div class="detail-item">
                                <label>Symbol:</label>
                                <span>${opportunity.token_symbol}</span>
                            </div>
                            <div class="detail-item">
                                <label>Address:</label>
                                <span class="address-text">${opportunity.token_address}</span>
                                <button class="copy-btn" onclick="copyToClipboard('${opportunity.token_address}')">Copy</button>
                            </div>
                            <div class="detail-item">
                                <label>Chain:</label>
                                <span class="chain-badge">${opportunity.chain}</span>
                            </div>
                            <div class="detail-item">
                                <label>Detected:</label>
                                <span>${new Date(opportunity.detected_at).toLocaleString()}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="detail-section">
                        <h3>Risk Analysis</h3>
                        <div class="detail-grid">
                            <div class="detail-item">
                                <label>Risk Level:</label>
                                <span class="risk-badge risk-${opportunity.risk_level}">${opportunity.risk_level.toUpperCase()}</span>
                            </div>
                            <div class="detail-item">
                                <label>Confidence Score:</label>
                                <span>${opportunity.score.toFixed(3)}/1.0</span>
                            </div>
                            <div class="detail-item">
                                <label>Recommendation:</label>
                                <span class="recommendation rec-${opportunity.recommendation.toLowerCase().replace('_', '-')}">${opportunity.recommendation}</span>
                            </div>
                            <div class="detail-item">
                                <label>Confidence:</label>
                                <span>${opportunity.confidence}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="detail-section">
                        <h3>Liquidity Information</h3>
                        <div class="detail-grid">
                            <div class="detail-item">
                                <label>DEX:</label>
                                <span>${opportunity.dex_name || 'Unknown'}</span>
                            </div>
                            <div class="detail-item">
                                <label>Liquidity USD:</label>
                                <span>$${opportunity.liquidity_usd.toLocaleString()}</span>
                            </div>
                            ${opportunity.pair_address ? `
                            <div class="detail-item">
                                <label>Pair Address:</label>
                                <span class="address-text">${opportunity.pair_address}</span>
                                <button class="copy-btn" onclick="copyToClipboard('${opportunity.pair_address}')">Copy</button>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                    
                    ${opportunity.reasons && opportunity.reasons.length > 0 ? `
                    <div class="detail-section">
                        <h3>Analysis Reasons</h3>
                        <ul style="margin-left: 20px; line-height: 1.6;">
                            ${opportunity.reasons.map(reason => `<li>${reason}</li>`).join('')}
                        </ul>
                    </div>
                    ` : ''}
                    
                    ${opportunity.warnings && opportunity.warnings.length > 0 ? `
                    <div class="detail-section">
                        <h3>Risk Warnings</h3>
                        <ul style="margin-left: 20px; line-height: 1.6; color: #f44336;">
                            ${opportunity.warnings.map(warning => `<li>${warning}</li>`).join('')}
                        </ul>
                    </div>
                    ` : ''}
                    
                    <div class="detail-section">
                        <h3>External Links</h3>
                        <div class="external-links">
                            ${getExternalLinks(opportunity)}
                        </div>
                    </div>
                `;
                
                // Show modal
                document.getElementById('details-modal').classList.add('show');
            }
            
            function getExternalLinks(opportunity) {
                const links = [];
                const address = opportunity.token_address;
                const chain = opportunity.chain.toLowerCase();
                
                if (chain.includes('ethereum')) {
                    links.push(`<a href="https://etherscan.io/token/${address}" target="_blank" class="external-link">Etherscan</a>`);
                    links.push(`<a href="https://dexscreener.com/ethereum/${address}" target="_blank" class="external-link">DexScreener</a>`);
                } else if (chain.includes('base')) {
                    links.push(`<a href="https://basescan.org/token/${address}" target="_blank" class="external-link">BaseScan</a>`);
                    links.push(`<a href="https://dexscreener.com/base/${address}" target="_blank" class="external-link">DexScreener</a>`);
                } else if (chain.includes('solana')) {
                    links.push(`<a href="https://solscan.io/token/${address}" target="_blank" class="external-link">Solscan</a>`);
                    links.push(`<a href="https://dexscreener.com/solana/${address}" target="_blank" class="external-link">DexScreener</a>`);
                }
                
                links.push(`<a href="https://www.coingecko.com/en/search_redirect?id=${opportunity.token_symbol}" target="_blank" class="external-link">CoinGecko</a>`);
                
                return links.join('');
            }
            
            function closeDetailsModal() {
                document.getElementById('details-modal').classList.remove('show');
            }
            
            function copyToClipboard(text) {
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(text).then(() => {
                        showNotification('Copied to clipboard!');
                    });
                } else {
                    // Fallback for older browsers
                    const textArea = document.createElement('textarea');
                    textArea.value = text;
                    document.body.appendChild(textArea);
                    textArea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textArea);
                    showNotification('Copied to clipboard!');
                }
            }
            
            function showNotification(message) {
                const notification = document.createElement('div');
                notification.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: #4CAF50;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 5px;
                    z-index: 1001;
                    animation: slideInRight 0.3s ease;
                `;
                notification.textContent = message;
                document.body.appendChild(notification);
                
                setTimeout(() => {
                    notification.remove();
                }, 3000);
            }
            
            function executeTrade(tokenSymbol) {
                showNotification(`Trade execution for ${tokenSymbol} - Feature coming soon!`);
            }
            
            function updateStats(stats) {
                if (stats.analysis_rate !== undefined) {
                    document.getElementById('analysis-rate').textContent = stats.analysis_rate;
                }
            }
            
            function updateConnectionStatus(connected) {
                const statusEl = document.getElementById('connection-status');
                if (connected) {
                    statusEl.textContent = 'Connected';
                    statusEl.className = 'connection-status connected';
                } else {
                    statusEl.textContent = 'Disconnected';
                    statusEl.className = 'connection-status disconnected';
                }
            }
            
            // Close modal when clicking outside
            document.getElementById('details-modal').addEventListener('click', function(e) {
                if (e.target === this) {
                    closeDetailsModal();
                }
            });
            
            // Fetch initial stats
            async function fetchStats() {
                try {
                    const response = await fetch('/api/stats');
                    const stats = await response.json();
                    
                    document.getElementById('total-opportunities').textContent = stats.total_opportunities || 0;
                    document.getElementById('high-confidence').textContent = stats.high_confidence || 0;
                    document.getElementById('analysis-rate').textContent = stats.analysis_rate || 0;
                    document.getElementById('connected-clients').textContent = stats.connected_clients || 0;
                    
                } catch (error) {
                    console.error('Error fetching stats:', error);
                }
            }
            
            // Initialize
            connectWebSocket();
            fetchStats();
            setInterval(fetchStats, 10000); // Update stats every 10 seconds
        </script>
    </body>
    </html>
    """















@app.get("/api/stats")
async def get_stats():
    """Get system statistics."""
    try:
        uptime = datetime.now() - dashboard_server.stats["uptime_start"]
        portfolio = dashboard_server.get_safe_portfolio_summary()
        
        return {
            "total_opportunities": dashboard_server.stats["total_opportunities"],
            "high_confidence": dashboard_server.stats["high_confidence"],
            "active_chains": dashboard_server.stats["active_chains"],
            "analysis_rate": dashboard_server.stats["analysis_rate"],
            "uptime_hours": round(uptime.total_seconds() / 3600, 2),
            "connected_clients": len(dashboard_server.connected_clients),
            "portfolio": portfolio
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"error": str(e), "connected_clients": len(dashboard_server.connected_clients)}

@app.get("/api/opportunities")
async def get_opportunities():
    """Get recent opportunities."""
    try:
        return dashboard_server.opportunities[-20:]  # Last 20
    except Exception as e:
        logger.error(f"Opportunities error: {e}")
        return []
    


@app.get("/api/trades")
async def get_trade_history():
    """Get recent trade history."""
    try:
        trades = []
        
        # Try to get trades from position manager
        if dashboard_server.position_manager and hasattr(dashboard_server.position_manager, 'closed_positions'):
            for exit in dashboard_server.position_manager.closed_positions[-20:]:  # Last 20
                try:
                    trades.append({
                        "id": getattr(exit, 'position_id', 'unknown'),
                        "token_symbol": getattr(exit, 'position_id', 'UNKNOWN').split('_')[0],
                        "trade_type": "close",
                        "amount": float(getattr(exit, 'exit_amount', 0)),
                        "status": "completed",
                        "created_at": getattr(exit, 'exit_time', datetime.now()).isoformat(),
                        "executed_at": getattr(exit, 'exit_time', datetime.now()).isoformat(),
                        "tx_hash": getattr(exit, 'exit_tx_hash', None),
                        "chain": "unknown",
                        "pnl": float(getattr(exit, 'realized_pnl', 0))
                    })
                except Exception as trade_error:
                    logger.error(f"Error processing trade: {trade_error}")
                    continue
        
        # If no trades from position manager, return empty with success
        return {"trades": trades, "status": "success"}
        
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        return {"trades": [], "error": str(e), "status": "error"}

@app.get("/api/positions")
async def get_positions():
    """Get current trading positions."""
    try:
        positions = []
        
        if dashboard_server.position_manager and hasattr(dashboard_server.position_manager, 'active_positions'):
            for position_id, position in dashboard_server.position_manager.active_positions.items():
                try:
                    positions.append({
                        "token_symbol": getattr(position, 'token_symbol', 'UNKNOWN'),
                        "amount": float(getattr(position, 'entry_amount', 0)),
                        "entry_price": float(getattr(position, 'entry_price', 0)),
                        "current_price": float(getattr(position, 'current_price', 0)),
                        "pnl": float(getattr(position, 'unrealized_pnl', 0)),
                        "pnl_percentage": getattr(position, 'unrealized_pnl_percentage', 0.0)
                    })
                except Exception as pos_error:
                    logger.error(f"Error processing position {position_id}: {pos_error}")
                    continue
        
        return {"positions": positions, "status": "success"}
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return {"positions": [], "error": str(e), "status": "error"}






@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    dashboard_server.connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(dashboard_server.connected_clients)}")
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                
    except WebSocketDisconnect:
        if websocket in dashboard_server.connected_clients:
            dashboard_server.connected_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {len(dashboard_server.connected_clients)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in dashboard_server.connected_clients:
            dashboard_server.connected_clients.remove(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")