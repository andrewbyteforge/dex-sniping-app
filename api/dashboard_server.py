# api/dashboard_server.py (Complete Updated Version)
"""
FastAPI server providing REST API and WebSocket for the dashboard interface.
Connects the web dashboard to the trading execution system with watchlist support.
"""

import asyncio
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from models.token import TradingOpportunity, RiskLevel, TokenInfo, LiquidityInfo, ContractAnalysis, SocialMetrics
from models.watchlist import watchlist_manager, WatchlistStatus
from utils.logger import logger_manager

# Pydantic models for API
class TradeRequest(BaseModel):
    """Request model for trade execution."""
    token_address: str
    token_symbol: str
    amount: float
    chain: str = "ethereum"
    order_type: str = "market"

class OpportunityResponse(BaseModel):
    """Response model for opportunities."""
    token_symbol: str
    token_address: str
    chain: str
    risk_level: str
    recommendation: str
    confidence: str
    score: float
    liquidity_usd: float
    age_minutes: int

class WatchlistAddRequest(BaseModel):
    """Request model for adding to watchlist."""
    token_address: str
    token_symbol: str
    chain: str
    reason: str = "Manual addition"
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: str = ""

# Create FastAPI app
app = FastAPI(
    title="DEX Sniping Dashboard",
    version="2.0.0",
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

class DashboardServer:
    """
    Dashboard server that provides API endpoints and WebSocket connections
    for real-time communication with the trading system.
    """
    
    def __init__(self):
        """Initialize the dashboard server."""
        self.logger = logger_manager.get_logger("DashboardServer")
        self.trading_executor = None
        self.position_manager = None
        self.risk_manager = None
        self.connected_clients: List[WebSocket] = []
        self.opportunities_queue: List[TradingOpportunity] = []
        
        # Statistics
        self.stats = {
            "total_opportunities": 0,
            "high_confidence": 0,
            "active_chains": 3,
            "analysis_rate": 0,
            "uptime_start": datetime.now()
        }
        
    async def initialize(self) -> None:
        """
        Initialize the dashboard server.
        
        Raises:
            Exception: If initialization fails
        """
        try:
            self.logger.info("Initializing dashboard server...")
            # Start periodic cleanup task
            asyncio.create_task(self._periodic_cleanup_task())
            self.logger.info("Dashboard server initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize dashboard server: {e}")
            raise

    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        """
        Broadcast message to all connected WebSocket clients.
        
        Args:
            message: Message to broadcast
        """
        if not self.connected_clients:
            return
            
        disconnected_clients = []
        
        try:
            message_str = json.dumps(message)
        except Exception as json_error:
            self.logger.error(f"Error serializing message: {json_error}")
            return
        
        for client in self.connected_clients.copy():
            try:
                # Check if client is still connected
                if hasattr(client, 'client_state') and client.client_state.value == 3:
                    disconnected_clients.append(client)
                    continue
                    
                await client.send_text(message_str)
                
            except Exception as e:
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ['disconnect', 'closed', 'connection']):
                    self.logger.debug(f"Client disconnected during broadcast: {e}")
                else:
                    self.logger.warning(f"Error sending to client: {e}")
                disconnected_clients.append(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in self.connected_clients:
                self.connected_clients.remove(client)
                
        if disconnected_clients:
            self.logger.info(f"Removed {len(disconnected_clients)} disconnected clients")

    async def add_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Add a new trading opportunity and broadcast to clients.
        
        Args:
            opportunity: The trading opportunity to add
        """
        try:
            # Add to queue (keep last 100)
            self.opportunities_queue.append(opportunity)
            if len(self.opportunities_queue) > 100:
                self.opportunities_queue.pop(0)
                
            # Update stats
            self.stats["total_opportunities"] += 1
            
            recommendation = opportunity.metadata.get("recommendation", {})
            if recommendation.get("confidence") == "HIGH":
                self.stats["high_confidence"] += 1
                
            # Create safe opportunity data for broadcast
            opp_data = {
                "token_symbol": opportunity.token.symbol or "UNKNOWN",
                "token_address": opportunity.token.address,
                "chain": opportunity.metadata.get("chain", "ethereum"),
                "risk_level": opportunity.contract_analysis.risk_level.value,
                "recommendation": recommendation.get("action", "UNKNOWN"),
                "confidence": recommendation.get("confidence", "UNKNOWN"),
                "score": recommendation.get("score", 0.0),
                "liquidity_usd": opportunity.liquidity.liquidity_usd,
                "dex_name": opportunity.liquidity.dex_name,
                "pair_address": opportunity.liquidity.pair_address,
                "detected_at": opportunity.detected_at.isoformat(),
                "reasons": recommendation.get("reasons", []),
                "warnings": recommendation.get("warnings", [])
            }
                
            # Broadcast to connected clients
            await self.broadcast_message({
                "type": "new_opportunity",
                "data": opp_data
            })
            
            self.logger.debug(f"Added opportunity: {opportunity.token.symbol}")
            
        except Exception as e:
            self.logger.error(f"Error adding opportunity: {e}")

    async def update_analysis_rate(self, rate: int) -> None:
        """
        Update the analysis rate statistic.
        
        Args:
            rate: New analysis rate value
        """
        try:
            self.stats["analysis_rate"] = rate
            
            # Broadcast updated stats
            await self.broadcast_message({
                "type": "stats_update",
                "data": {
                    "analysis_rate": rate,
                    "total_opportunities": self.stats["total_opportunities"],
                    "high_confidence": self.stats["high_confidence"]
                }
            })
        except Exception as e:
            self.logger.error(f"Error updating analysis rate: {e}")
    
    async def _periodic_cleanup_task(self) -> None:
        """Periodic task to clean up dead WebSocket connections."""
        while True:
            try:
                await asyncio.sleep(30)  # Clean up every 30 seconds
                await self._cleanup_dead_connections()
            except Exception as e:
                self.logger.error(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_dead_connections(self) -> None:
        """Clean up dead WebSocket connections."""
        try:
            if not self.connected_clients:
                return
                
            dead_clients = []
            
            for client in self.connected_clients.copy():
                try:
                    if (hasattr(client, 'client_state') and 
                        client.client_state.value == 3):  # DISCONNECTED
                        dead_clients.append(client)
                except Exception:
                    dead_clients.append(client)
            
            for client in dead_clients:
                if client in self.connected_clients:
                    self.connected_clients.remove(client)
            
            if dead_clients:
                self.logger.info(f"Cleaned up {len(dead_clients)} dead connections")
                
        except Exception as e:
            self.logger.error(f"Error during connection cleanup: {e}")

# Global dashboard instance
dashboard_server = DashboardServer()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await dashboard_server.initialize()

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the main dashboard page."""
    try:
        # Check if custom template exists
        template_path = "web/templates/dashboard.html"
        if os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return HTMLResponse(content=content)
            except Exception as file_error:
                dashboard_server.logger.error(f"Error reading template: {file_error}")
        
        # Return enhanced basic dashboard with watchlist
        return HTMLResponse(content=get_enhanced_dashboard_html())
        
    except Exception as e:
        dashboard_server.logger.error(f"Dashboard page error: {e}")
        return HTMLResponse(
            content=f"<h1>Dashboard Error</h1><p>Error: {e}</p>", 
            status_code=500
        )

def get_enhanced_dashboard_html() -> str:
    """Get enhanced dashboard HTML with watchlist functionality."""
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
            .container { max-width: 1400px; margin: 0 auto; }
            .header {
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
                backdrop-filter: blur(10px);
            }
            .main-grid {
                display: grid;
                grid-template-columns: 2fr 1fr;
                gap: 20px;
                margin-bottom: 20px;
            }
            .left-panel {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            .right-panel {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
            }
            .stat-card {
                background: rgba(255,255,255,0.1);
                padding: 15px;
                border-radius: 10px;
                text-align: center;
                backdrop-filter: blur(10px);
            }
            .stat-value { font-size: 1.8em; font-weight: bold; color: #4CAF50; }
            .stat-label { margin-top: 5px; opacity: 0.8; font-size: 0.9em; }
            
            .opportunities, .watchlist-panel {
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
                padding: 20px;
                backdrop-filter: blur(10px);
            }
            
            .section-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            
            .section-title {
                font-size: 1.2em;
                font-weight: bold;
            }
            
            .controls {
                display: flex;
                gap: 8px;
            }
            
            .action-btn {
                padding: 6px 12px;
                border: none;
                border-radius: 6px;
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
            .action-btn.success { background: rgba(76, 175, 80, 0.8); }
            .action-btn.success:hover { background: rgba(76, 175, 80, 1); }
            .action-btn.danger { background: rgba(244, 67, 54, 0.8); }
            .action-btn.danger:hover { background: rgba(244, 67, 54, 1); }
            
            .opportunity-item, .watchlist-item {
                background: rgba(255,255,255,0.1);
                margin: 8px 0;
                padding: 12px;
                border-radius: 8px;
                border-left: 4px solid #4CAF50;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .opportunity-item:hover, .watchlist-item:hover {
                background: rgba(255,255,255,0.2);
                transform: translateY(-1px);
            }
            
            .watchlist-item {
                border-left-color: #2196F3;
            }
            
            .item-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            
            .token-symbol {
                font-size: 1.1em;
                font-weight: bold;
                color: #4CAF50;
            }
            
            .watchlist-item .token-symbol {
                color: #2196F3;
            }
            
            .risk-badge {
                padding: 3px 6px;
                border-radius: 12px;
                font-size: 10px;
                font-weight: bold;
                text-transform: uppercase;
            }
            .risk-low { background: rgba(76, 175, 80, 0.3); color: #4CAF50; }
            .risk-medium { background: rgba(255, 193, 7, 0.3); color: #FFC107; }
            .risk-high { background: rgba(244, 67, 54, 0.3); color: #F44336; }
            .risk-critical { background: rgba(139, 0, 0, 0.3); color: #8B0000; }
            .risk-unknown { background: rgba(158, 158, 158, 0.3); color: #9E9E9E; }
            
            .item-details {
                font-size: 0.85em;
                opacity: 0.9;
                line-height: 1.4;
            }
            
            .chain-badge {
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 9px;
                margin-right: 6px;
                background: rgba(33, 150, 243, 0.3);
                color: #2196F3;
            }
            
            .recommendation {
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 9px;
                margin-left: 6px;
                font-weight: bold;
            }
            .rec-strong-buy { background: rgba(76, 175, 80, 0.3); color: #4CAF50; }
            .rec-buy { background: rgba(33, 150, 243, 0.3); color: #2196F3; }
            .rec-small-buy { background: rgba(33, 150, 243, 0.2); color: #2196F3; }
            .rec-watch { background: rgba(255, 193, 7, 0.3); color: #FFC107; }
            .rec-avoid { background: rgba(244, 67, 54, 0.3); color: #F44336; }
            .rec-unknown { background: rgba(158, 158, 158, 0.3); color: #9E9E9E; }
            
            .item-actions {
                margin-top: 8px;
                display: flex;
                gap: 6px;
            }
            
            .connection-status {
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 8px 12px;
                border-radius: 5px;
                font-size: 12px;
                z-index: 999;
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
            .modal-overlay.show { display: flex; }
            .modal-content {
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                max-width: 600px;
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
                font-size: 20px;
            }
            .modal-close {
                background: none;
                border: none;
                color: white;
                font-size: 24px;
                cursor: pointer;
                padding: 0;
                width: 30px;
                height: 30px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.3s ease;
            }
            .modal-close:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            .modal-body {
                padding: 20px;
            }
            .form-group {
                margin-bottom: 15px;
            }
            .form-group label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            .form-group input, .form-group textarea, .form-group select {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 6px;
                background: rgba(255, 255, 255, 0.1);
                color: white;
                font-size: 14px;
            }
            .form-group input::placeholder, .form-group textarea::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
            .form-group textarea {
                resize: vertical;
                min-height: 60px;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            @keyframes slideIn {
                from { transform: translateY(-50px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            
            @media (max-width: 1024px) {
                .main-grid {
                    grid-template-columns: 1fr;
                }
                .stats {
                    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>DEX Sniping Dashboard v2.0</h1>
                <p>Real-time multi-chain token monitoring with intelligent analysis & watchlist</p>
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
                <div class="stat-card">
                    <div class="stat-value" id="watchlist-count">0</div>
                    <div class="stat-label">Watchlist Items</div>
                </div>
            </div>
            
            <div class="main-grid">
                <div class="left-panel">
                    <div class="opportunities">
                        <div class="section-header">
                            <span class="section-title">Live Opportunities</span>
                            <div class="controls">
                                <button class="action-btn" onclick="clearOpportunities()">Clear</button>
                            </div>
                        </div>
                        <div id="opportunity-list">
                            <p>Connecting to live feed...</p>
                        </div>
                    </div>
                </div>
                
                <div class="right-panel">
                    <div class="watchlist-panel">
                        <div class="section-header">
                            <span class="section-title">Watchlist</span>
                            <div class="controls">
                                <button class="action-btn success" onclick="showAddToWatchlistModal()">Add</button>
                                <button class="action-btn" onclick="refreshWatchlist()">Refresh</button>
                                <button class="action-btn danger" onclick="clearWatchlist()">Clear</button>
                            </div>
                        </div>
                        <div id="watchlist-list">
                            <p>Loading watchlist...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div id="connection-status" class="connection-status disconnected">
            Connecting...
        </div>
        
        <!-- Add to Watchlist Modal -->
        <div id="add-watchlist-modal" class="modal-overlay">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Add to Watchlist</h2>
                    <button class="modal-close" onclick="closeAddWatchlistModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <form onsubmit="submitAddToWatchlist(event)">
                        <div class="form-group">
                            <label for="watchlist-token-address">Token Address *</label>
                            <input type="text" id="watchlist-token-address" required 
                                   placeholder="0x... or Solana address">
                        </div>
                        <div class="form-group">
                            <label for="watchlist-token-symbol">Token Symbol *</label>
                            <input type="text" id="watchlist-token-symbol" required 
                                   placeholder="e.g., DOGE, PEPE">
                        </div>
                        <div class="form-group">
                            <label for="watchlist-chain">Chain *</label>
                            <select id="watchlist-chain" required>
                                <option value="ETHEREUM">Ethereum</option>
                                <option value="BASE">Base</option>
                                <option value="SOLANA">Solana</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="watchlist-reason">Reason</label>
                            <input type="text" id="watchlist-reason" 
                                   placeholder="Why are you watching this token?">
                        </div>
                        <div class="form-group">
                            <label for="watchlist-target-price">Target Price (USD)</label>
                            <input type="number" id="watchlist-target-price" step="0.000001" 
                                   placeholder="0.001">
                        </div>
                        <div class="form-group">
                            <label for="watchlist-stop-loss">Stop Loss (USD)</label>
                            <input type="number" id="watchlist-stop-loss" step="0.000001" 
                                   placeholder="0.0005">
                        </div>
                        <div class="form-group">
                            <label for="watchlist-notes">Notes</label>
                            <textarea id="watchlist-notes" 
                                      placeholder="Additional notes or analysis..."></textarea>
                        </div>
                        <div class="controls">
                            <button type="submit" class="action-btn success">Add to Watchlist</button>
                            <button type="button" class="action-btn" onclick="closeAddWatchlistModal()">Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        
        <script>
            let ws = null;
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 5;
            let opportunities = [];
            let watchlist = [];
            
            // WebSocket connection
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
                try {
                    switch (data.type) {
                        case 'new_opportunity':
                            addOpportunityToList(data.data);
                            break;
                        case 'stats_update':
                            updateStats(data.data);
                            break;
                        case 'watchlist_updated':
                            refreshWatchlist();
                            break;
                        default:
                            console.log('Unknown message type:', data.type);
                    }
                } catch (error) {
                    console.error('Error handling WebSocket message:', error);
                }
            }
            
            function addOpportunityToList(opportunity) {
                try {
                    const list = document.getElementById('opportunity-list');
                    
                    opportunities.unshift(opportunity);
                    if (opportunities.length > 20) {
                        opportunities.pop();
                    }
                    
                    const item = document.createElement('div');
                    item.className = 'opportunity-item';
                    
                    const tokenSymbol = opportunity.token_symbol || 'UNKNOWN';
                    const chain = opportunity.chain || 'unknown';
                    const riskLevel = opportunity.risk_level || 'unknown';
                    const recommendation = opportunity.recommendation || 'UNKNOWN';
                    const confidence = opportunity.confidence || 'UNKNOWN';
                    const score = opportunity.score || 0;
                    const liquidityUsd = opportunity.liquidity_usd || 0;
                    const detectedAt = new Date(opportunity.detected_at);
                    
                    item.innerHTML = `
                        <div class="item-header">
                            <span class="token-symbol">${tokenSymbol}</span>
                            <span class="risk-badge risk-${riskLevel}">${riskLevel.toUpperCase()}</span>
                        </div>
                        <div class="item-details">
                            <span class="chain-badge">${chain.toUpperCase()}</span>
                            Rec: <span class="recommendation rec-${recommendation.toLowerCase().replace('_', '-')}">${recommendation}</span><br>
                            Score: ${score.toFixed(2)} | Liq: $${liquidityUsd.toLocaleString()}<br>
                            <small>${detectedAt.toLocaleTimeString()}</small>
                        </div>
                        <div class="item-actions">
                            <button class="action-btn success" onclick="addOpportunityToWatchlist('${opportunity.token_address}', '${tokenSymbol}', '${chain}')">Watch</button>
                            <button class="action-btn" onclick="executeTrade('${tokenSymbol}')">Trade</button>
                        </div>
                    `;
                    
                    list.insertBefore(item, list.firstChild);
                    
                    while (list.children.length > 10) {
                        list.removeChild(list.lastChild);
                    }
                    
                } catch (error) {
                    console.error('Error adding opportunity:', error);
                }
            }
            
            // Watchlist functions
            async function refreshWatchlist() {
                try {
                    const response = await fetch('/api/watchlist');
                    const data = await response.json();
                    watchlist = data.items || [];
                    renderWatchlist();
                    updateWatchlistCount();
                } catch (error) {
                    console.error('Error refreshing watchlist:', error);
                    showNotification('Error refreshing watchlist', 'error');
                }
            }
            
            function renderWatchlist() {
                try {
                    const list = document.getElementById('watchlist-list');
                    
                    if (watchlist.length === 0) {
                        list.innerHTML = '<p>No tokens in watchlist...</p>';
                        return;
                    }
                    
                    list.innerHTML = '';
                    
                    watchlist.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'watchlist-item';
                        
                        const addedAt = new Date(item.added_at);
                        const targetPrice = item.target_price ? `$${item.target_price}` : 'N/A';
                        
                        div.innerHTML = `
                            <div class="item-header">
                                <span class="token-symbol">${item.token_symbol}</span>
                                <span class="chain-badge">${item.chain}</span>
                            </div>
                            <div class="item-details">
                                Target: ${targetPrice} | Status: ${item.status}<br>
                                <small>Added: ${addedAt.toLocaleDateString()}</small><br>
                                <small>${item.reason}</small>
                            </div>
                            <div class="item-actions">
                                <button class="action-btn danger" onclick="removeFromWatchlist('${item.token_address}', '${item.chain}')">Remove</button>
                            </div>
                        `;
                        
                        list.appendChild(div);
                    });
                } catch (error) {
                    console.error('Error rendering watchlist:', error);
                }
            }
            
            function showAddToWatchlistModal() {
                document.getElementById('add-watchlist-modal').classList.add('show');
            }
            
            function closeAddWatchlistModal() {
                document.getElementById('add-watchlist-modal').classList.remove('show');
                // Clear form
                document.getElementById('watchlist-token-address').value = '';
                document.getElementById('watchlist-token-symbol').value = '';
                document.getElementById('watchlist-reason').value = '';
                document.getElementById('watchlist-target-price').value = '';
                document.getElementById('watchlist-stop-loss').value = '';
                document.getElementById('watchlist-notes').value = '';
            }
            
            async function submitAddToWatchlist(event) {
                event.preventDefault();
                
                try {
                    const formData = {
                        token_address: document.getElementById('watchlist-token-address').value,
                        token_symbol: document.getElementById('watchlist-token-symbol').value,
                        chain: document.getElementById('watchlist-chain').value,
                        reason: document.getElementById('watchlist-reason').value || 'Manual addition',
                        target_price: document.getElementById('watchlist-target-price').value ? 
                                     parseFloat(document.getElementById('watchlist-target-price').value) : null,
                        stop_loss: document.getElementById('watchlist-stop-loss').value ? 
                                  parseFloat(document.getElementById('watchlist-stop-loss').value) : null,
                        notes: document.getElementById('watchlist-notes').value
                    };
                    
                    const response = await fetch('/api/watchlist/add', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(formData)
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        showNotification('Added to watchlist successfully', 'success');
                        closeAddWatchlistModal();
                        refreshWatchlist();
                    } else {
                        showNotification(result.message || 'Failed to add to watchlist', 'error');
                    }
                } catch (error) {
                    console.error('Error adding to watchlist:', error);
                    showNotification('Error adding to watchlist', 'error');
                }
            }
            
            async function addOpportunityToWatchlist(tokenAddress, tokenSymbol, chain) {
                try {
                    const formData = {
                        token_address: tokenAddress,
                        token_symbol: tokenSymbol,
                        chain: chain,
                        reason: 'Added from opportunity'
                    };
                    
                    const response = await fetch('/api/watchlist/add', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(formData)
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        showNotification(`${tokenSymbol} added to watchlist`, 'success');
                        refreshWatchlist();
                    } else {
                        showNotification(result.message || 'Failed to add to watchlist', 'error');
                    }
                } catch (error) {
                    console.error('Error adding to watchlist:', error);
                    showNotification('Error adding to watchlist', 'error');
                }
            }
            
            async function removeFromWatchlist(tokenAddress, chain) {
                try {
                    const response = await fetch(`/api/watchlist/remove?token_address=${encodeURIComponent(tokenAddress)}&chain=${encodeURIComponent(chain)}`, {
                        method: 'DELETE'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        showNotification('Removed from watchlist', 'success');
                        refreshWatchlist();
                    } else {
                        showNotification(result.message || 'Failed to remove from watchlist', 'error');
                    }
                } catch (error) {
                    console.error('Error removing from watchlist:', error);
                    showNotification('Error removing from watchlist', 'error');
                }
            }
            
            async function clearWatchlist() {
                if (confirm('Are you sure you want to clear the entire watchlist?')) {
                    try {
                        for (const item of watchlist) {
                            await removeFromWatchlist(item.token_address, item.chain);
                        }
                        showNotification('Watchlist cleared', 'success');
                    } catch (error) {
                        console.error('Error clearing watchlist:', error);
                        showNotification('Error clearing watchlist', 'error');
                    }
                }
            }
            
            function updateWatchlistCount() {
                document.getElementById('watchlist-count').textContent = watchlist.length;
            }
            
            // Utility functions
            function clearOpportunities() {
                document.getElementById('opportunity-list').innerHTML = '<p>Opportunities cleared...</p>';
                opportunities = [];
            }
            
            function executeTrade(tokenSymbol) {
                showNotification(`Trade execution for ${tokenSymbol} - Feature coming soon!`, 'info');
            }
            
            function updateStats(stats) {
                try {
                    if (stats.analysis_rate !== undefined) {
                        document.getElementById('analysis-rate').textContent = stats.analysis_rate;
                    }
                } catch (error) {
                    console.error('Error updating stats:', error);
                }
            }
            
            function updateConnectionStatus(connected) {
                try {
                    const statusEl = document.getElementById('connection-status');
                    if (connected) {
                        statusEl.textContent = 'Connected';
                        statusEl.className = 'connection-status connected';
                    } else {
                        statusEl.textContent = 'Disconnected';
                        statusEl.className = 'connection-status disconnected';
                    }
                } catch (error) {
                    console.error('Error updating connection status:', error);
                }
            }
            
            function showNotification(message, type = 'info') {
                try {
                    const notification = document.createElement('div');
                    const bgColor = type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3';
                    
                    notification.style.cssText = `
                        position: fixed;
                        top: 70px;
                        right: 20px;
                        background: ${bgColor};
                        color: white;
                        padding: 10px 20px;
                        border-radius: 5px;
                        z-index: 1001;
                        animation: slideInRight 0.3s ease;
                        max-width: 300px;
                        word-wrap: break-word;
                    `;
                    notification.textContent = message;
                    document.body.appendChild(notification);
                    
                    setTimeout(() => {
                        if (notification.parentNode) {
                            notification.remove();
                        }
                    }, 3000);
                } catch (error) {
                    console.error('Error showing notification:', error);
                }
            }
            
            // Fetch initial data
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
            
            // Close modals when clicking outside
            document.getElementById('add-watchlist-modal').addEventListener('click', function(e) {
                if (e.target === this) {
                    closeAddWatchlistModal();
                }
            });
            
            // Initialize
            try {
                connectWebSocket();
                fetchStats();
                refreshWatchlist();
                setInterval(fetchStats, 10000);
                setInterval(refreshWatchlist, 30000); // Refresh watchlist every 30s
            } catch (error) {
                console.error('Error during initialization:', error);
            }
        </script>
    </body>
    </html>
    """

@app.get("/api/stats")
async def get_stats():
    """Get current system statistics."""
    try:
        uptime = datetime.now() - dashboard_server.stats["uptime_start"]
        portfolio = {}
        
        if dashboard_server.position_manager:
            try:
                portfolio = dashboard_server.position_manager.get_portfolio_summary()
            except Exception as portfolio_error:
                dashboard_server.logger.debug(f"Portfolio error: {portfolio_error}")
                portfolio = {"status": "unavailable"}
        
        return {
            "total_opportunities": dashboard_server.stats["total_opportunities"],
            "high_confidence": dashboard_server.stats["high_confidence"], 
            "active_chains": dashboard_server.stats["active_chains"],
            "analysis_rate": dashboard_server.stats["analysis_rate"],
            "uptime_hours": uptime.total_seconds() / 3600,
            "portfolio": portfolio,
            "connected_clients": len(dashboard_server.connected_clients)
        }
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting stats: {e}")
        return {
            "error": str(e),
            "connected_clients": len(dashboard_server.connected_clients),
            "status": "error"
        }

@app.get("/api/opportunities", response_model=List[OpportunityResponse])
async def get_opportunities():
    """Get current trading opportunities."""
    try:
        opportunities = []
        
        for opp in dashboard_server.opportunities_queue[-20:]:  # Last 20
            try:
                age_minutes = (datetime.now() - opp.detected_at).total_seconds() / 60
                
                opportunities.append(OpportunityResponse(
                    token_symbol=opp.token.symbol or "UNKNOWN",
                    token_address=opp.token.address,
                    chain=opp.metadata.get("chain", "ethereum"),
                    risk_level=opp.contract_analysis.risk_level.value,
                    recommendation=opp.metadata.get("recommendation", {}).get("action", "UNKNOWN"),
                    confidence=opp.metadata.get("recommendation", {}).get("confidence", "UNKNOWN"),
                    score=opp.metadata.get("recommendation", {}).get("score", 0.0),
                    liquidity_usd=opp.liquidity.liquidity_usd,
                    age_minutes=int(age_minutes)
                ))
            except Exception as opp_error:
                dashboard_server.logger.debug(f"Error processing opportunity: {opp_error}")
                continue
            
        return opportunities
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting opportunities: {e}")
        return []

# Watchlist API endpoints
@app.get("/api/watchlist")
async def get_watchlist(status: Optional[str] = None):
    """Get watchlist items, optionally filtered by status."""
    try:
        status_filter = None
        if status:
            try:
                status_filter = WatchlistStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        items = watchlist_manager.get_watchlist(status_filter)
        
        return {
            "items": [item.to_dict() for item in items],
            "total": len(items),
            "status_filter": status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        dashboard_server.logger.error(f"Error getting watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/watchlist/add")
async def add_to_watchlist(request: WatchlistAddRequest):
    """Add a token to the watchlist."""
    try:
        # Create opportunity object for watchlist
        token_address = request.token_address
        chain = request.chain.upper()
        
        # Handle different address formats for different chains
        if 'SOLANA' in chain:
            # For Solana, create a custom token object that bypasses validation
            token_info = type('SolanaTokenInfo', (), {
                'address': token_address,
                'symbol': request.token_symbol,
                'name': request.token_symbol,
                'decimals': 6,
                'total_supply': 1000000000
            })()
        else:
            # For EVM chains, use the regular TokenInfo with validation
            token_info = TokenInfo(
                address=token_address,
                symbol=request.token_symbol,
                name=request.token_symbol
            )
        
        liquidity_info = LiquidityInfo(
            pair_address='',
            dex_name='Unknown',
            token0=token_address,
            token1='',
            reserve0=0.0,
            reserve1=0.0,
            liquidity_usd=0.0,
            created_at=datetime.now(),
            block_number=0
        )
        
        opportunity = TradingOpportunity(
            token=token_info,
            liquidity=liquidity_info,
            contract_analysis=ContractAnalysis(),
            social_metrics=SocialMetrics()
        )
        
        opportunity.metadata['chain'] = chain
        
        success = watchlist_manager.add_to_watchlist(
            opportunity=opportunity,
            reason=request.reason,
            target_price=request.target_price,
            stop_loss=request.stop_loss,
            notes=request.notes
        )
        
        if success:
            # Broadcast to connected clients
            await dashboard_server.broadcast_message({
                "type": "watchlist_updated",
                "data": {
                    "action": "added",
                    "token_symbol": request.token_symbol,
                    "token_address": token_address
                }
            })
            
            return {"success": True, "message": "Added to watchlist"}
        else:
            return {"success": False, "message": "Token already in watchlist"}
        
    except Exception as e:
        dashboard_server.logger.error(f"Error adding to watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/watchlist/remove")
async def remove_from_watchlist(token_address: str, chain: str):
    """Remove a token from the watchlist."""
    try:
        success = watchlist_manager.remove_from_watchlist(token_address, chain)
        
        if success:
            # Broadcast to connected clients
            await dashboard_server.broadcast_message({
                "type": "watchlist_updated",
                "data": {
                    "action": "removed",
                    "token_address": token_address,
                    "chain": chain
                }
            })
            
            return {"success": True, "message": "Removed from watchlist"}
        else:
            return {"success": False, "message": "Token not found in watchlist"}
        
    except Exception as e:
        dashboard_server.logger.error(f"Error removing from watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/watchlist/stats")
async def get_watchlist_stats():
    """Get watchlist statistics."""
    try:
        stats = watchlist_manager.get_stats()
        return stats
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting watchlist stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    dashboard_server.connected_clients.append(websocket)
    dashboard_server.logger.info(f"WebSocket client connected. Total: {len(dashboard_server.connected_clients)}")
    
    try:
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "WebSocket connection established"
        }))
        
        while True:
            try:
                # Use receive_json with timeout to handle disconnects gracefully
                message = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                
                # Handle different message types
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif message.get("type") == "subscribe":
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "message": "Successfully subscribed to updates"
                    }))
                    
            except asyncio.TimeoutError:
                        # Send ping to keep connection alive
                        try:
                            await websocket.send_text(json.dumps({"type": "ping"}))
                        except Exception:
                            # If we can't send ping, connection is dead
                            break
                            
                    except json.JSONDecodeError as json_error:
                        dashboard_server.logger.warning(f"Invalid JSON from WebSocket client: {json_error}")
                        try:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "Invalid JSON format"
                            }))
                        except Exception:
                            # If we can't send error message, connection is dead
                            break
                            
                    except Exception as message_error:
                        # Check if this is a disconnect-related error
                        error_msg = str(message_error).lower()
                        if any(keyword in error_msg for keyword in ['disconnect', 'closed', 'connection']):
                            dashboard_server.logger.debug(f"WebSocket connection closed: {message_error}")
                            break
                        else:
                            dashboard_server.logger.error(f"WebSocket message processing error: {message_error}")
                            # Continue the loop for non-disconnect errors
                        
            except WebSocketDisconnect:
                dashboard_server.logger.info("WebSocket client disconnected normally")
            except Exception as e:
                dashboard_server.logger.error(f"WebSocket error: {e}")
            finally:
                # Always clean up the client connection
                if websocket in dashboard_server.connected_clients:
                    dashboard_server.connected_clients.remove(websocket)
                dashboard_server.logger.info(f"WebSocket cleanup complete. Remaining clients: {len(dashboard_server.connected_clients)}")

@app.get("/api/trades")
async def get_trade_history():
    """Get recent trade history."""
    try:
        trades = []
        
        # Try to get trades from position manager
        if (dashboard_server.position_manager and 
            hasattr(dashboard_server.position_manager, 'closed_positions')):
            
            try:
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
                        dashboard_server.logger.error(f"Error processing individual trade: {trade_error}")
                        continue
            except Exception as position_error:
                dashboard_server.logger.error(f"Error accessing position manager data: {position_error}")
        
        return {"trades": trades, "status": "success"}
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting trade history: {e}")
        return {"trades": [], "error": str(e), "status": "error"}

@app.get("/api/positions")
async def get_positions():
    """Get current trading positions."""
    try:
        positions = []
        
        if (dashboard_server.position_manager and 
            hasattr(dashboard_server.position_manager, 'active_positions')):
            
            try:
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
                        dashboard_server.logger.error(f"Error processing position {position_id}: {pos_error}")
                        continue
            except Exception as positions_error:
                dashboard_server.logger.error(f"Error accessing active positions: {positions_error}")
        
        return {"positions": positions, "status": "success"}
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting positions: {e}")
        return {"positions": [], "error": str(e), "status": "error"}

@app.post("/api/trade")
async def execute_trade(trade_request: TradeRequest):
    """Execute a manual trade."""
    try:
        dashboard_server.logger.info(f"Manual trade request: {trade_request.token_symbol}")
        
        if not dashboard_server.trading_executor:
            return {"success": False, "message": "Trading executor not available"}
        
        # Execute the trade
        result = await dashboard_server.trading_executor.manual_trade(
            token_address=trade_request.token_address,
            amount=trade_request.amount,
            chain=trade_request.chain
        )
        
        if result:
            # Broadcast trade execution to connected clients
            await dashboard_server.broadcast_message({
                "type": "trade_executed",
                "data": {
                    "token_symbol": trade_request.token_symbol,
                    "amount": trade_request.amount,
                    "status": result.status.value if hasattr(result, 'status') else 'unknown',
                    "tx_hash": getattr(result, 'tx_hash', None)
                }
            })
            
            return {
                "success": True,
                "trade_id": getattr(result, 'id', 'unknown'),
                "message": f"Trade executed for {trade_request.token_symbol}"
            }
        else:
            return {
                "success": False,
                "message": "Trade execution failed"
            }
            
    except Exception as e:
        dashboard_server.logger.error(f"Error executing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/status")
async def get_system_status():
    """Get detailed system status."""
        try:
            uptime = datetime.now() - dashboard_server.stats["uptime_start"]
            
            return {
                "status": "running",
                "uptime_seconds": uptime.total_seconds(),
                "connected_clients": len(dashboard_server.connected_clients),
                "trading_executor_initialized": dashboard_server.trading_executor is not None,
                "position_manager_initialized": dashboard_server.position_manager is not None,
                "opportunities_in_queue": len(dashboard_server.opportunities_queue),
                "watchlist_items": len(watchlist_manager.get_watchlist()),
                "chains": {
                    "ethereum": {"status": "active"},
                    "base": {"status": "active"},
                    "solana": {"status": "active"}
                }
            }
            
        except Exception as e:
            dashboard_server.logger.error(f"Error getting system status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/data")
async def export_data():
    """Export trading data for analysis."""
    try:
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "stats": dashboard_server.stats,
            "opportunities": [
                {
                    "token_symbol": opp.token.symbol,
                    "token_address": opp.token.address,
                    "chain": opp.metadata.get("chain"),
                    "risk_level": opp.contract_analysis.risk_level.value,
                    "recommendation": opp.metadata.get("recommendation", {}),
                    "detected_at": opp.detected_at.isoformat(),
                    "liquidity_usd": opp.liquidity.liquidity_usd
                }
                for opp in dashboard_server.opportunities_queue
            ],
            "watchlist": [item.to_dict() for item in watchlist_manager.get_watchlist()],
            "trade_history": [],  # Will be populated if trading system is available
            "positions": []  # Will be populated if position manager is available
        }
        
        # Add trading data if available
        if dashboard_server.position_manager:
            try:
                if hasattr(dashboard_server.position_manager, 'closed_positions'):
                    export_data["trade_history"] = [
                        {
                            "position_id": getattr(exit, 'position_id', 'unknown'),
                            "exit_time": getattr(exit, 'exit_time', datetime.now()).isoformat(),
                            "realized_pnl": float(getattr(exit, 'realized_pnl', 0))
                        }
                        for exit in dashboard_server.position_manager.closed_positions
                    ]
                
                if hasattr(dashboard_server.position_manager, 'active_positions'):
                    export_data["positions"] = [
                        {
                            "position_id": position_id,
                            "token_symbol": getattr(position, 'token_symbol', 'UNKNOWN'),
                            "entry_amount": float(getattr(position, 'entry_amount', 0)),
                            "entry_price": float(getattr(position, 'entry_price', 0)),
                            "unrealized_pnl": float(getattr(position, 'unrealized_pnl', 0))
                        }
                        for position_id, position in dashboard_server.position_manager.active_positions.items()
                    ]
            except Exception as trading_error:
                dashboard_server.logger.debug(f"Error exporting trading data: {trading_error}")
        
        return export_data
        
    except Exception as e:
        dashboard_server.logger.error(f"Error exporting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    """Development server entry point."""
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=False
        )
    except Exception as e:
        print(f"Failed to start dashboard server: {e}")
        raise