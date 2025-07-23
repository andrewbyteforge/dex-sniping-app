"""
Simplified and fixed dashboard server for DEX sniping system.
Focuses on reliability and basic functionality with comprehensive error handling.
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
    """
    Simplified dashboard server with minimal dependencies and comprehensive error handling.
    Focuses on reliability and basic functionality for DEX sniping operations.
    """
    
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
        """
        Initialize the dashboard server.
        
        Returns:
            None
            
        Raises:
            Exception: If initialization fails
        """
        try:
            logger.info("Dashboard server ready")
        except Exception as e:
            logger.error(f"Dashboard initialization error: {e}")
            raise

    async def add_opportunity(self, opportunity):
        """
        Add opportunity with comprehensive error handling and data validation.
        
        Args:
            opportunity: The trading opportunity object to add
            
        Returns:
            None
            
        Raises:
            Exception: If opportunity processing fails completely
        """
        try:
            # Convert opportunity to simple dict with safe attribute access
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
                
                # Try to get additional data safely with individual error handling
                try:
                    if hasattr(opportunity, 'liquidity') and opportunity.liquidity:
                        opp_data['liquidity_usd'] = float(getattr(opportunity.liquidity, 'liquidity_usd', 0) or 0)
                        opp_data['dex_name'] = getattr(opportunity.liquidity, 'dex_name', 'Unknown')
                        opp_data['pair_address'] = getattr(opportunity.liquidity, 'pair_address', 'unknown')
                except Exception as liquidity_error:
                    logger.debug(f"Error extracting liquidity data: {liquidity_error}")
                
                try:
                    if hasattr(opportunity, 'contract_analysis') and opportunity.contract_analysis:
                        risk_level = getattr(opportunity.contract_analysis, 'risk_level', None)
                        if risk_level and hasattr(risk_level, 'value'):
                            opp_data['risk_level'] = risk_level.value
                        elif risk_level:
                            opp_data['risk_level'] = str(risk_level)
                except Exception as contract_error:
                    logger.debug(f"Error extracting contract analysis: {contract_error}")
                
                try:
                    if hasattr(opportunity, 'metadata') and isinstance(opportunity.metadata, dict):
                        recommendation = opportunity.metadata.get('recommendation', {})
                        if isinstance(recommendation, dict):
                            opp_data['recommendation'] = recommendation.get('action', 'UNKNOWN')
                            opp_data['confidence'] = recommendation.get('confidence', 'UNKNOWN')
                            opp_data['score'] = float(recommendation.get('score', 0.0))
                            opp_data['reasons'] = recommendation.get('reasons', [])
                            opp_data['warnings'] = recommendation.get('warnings', [])
                except Exception as metadata_error:
                    logger.debug(f"Error extracting metadata: {metadata_error}")
                
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
                    'liquidity_usd': 0,
                    'dex_name': 'Unknown',
                    'pair_address': 'unknown',
                    'reasons': [],
                    'warnings': []
                }
            
            # Add to opportunities list (keep last 100)
            self.opportunities.append(opp_data)
            if len(self.opportunities) > 100:
                self.opportunities.pop(0)
            
            # Update stats safely
            self.stats["total_opportunities"] += 1
            if opp_data.get('confidence') == 'HIGH':
                self.stats["high_confidence"] += 1
            
            # Broadcast to clients with error handling
            try:
                await self.broadcast_to_clients({
                    "type": "new_opportunity",
                    "data": opp_data
                })
            except Exception as broadcast_error:
                logger.error(f"Error broadcasting opportunity: {broadcast_error}")
            
            logger.info(f"Added opportunity: {opp_data['token_symbol']} on {opp_data['chain']}")
            
        except Exception as e:
            logger.error(f"Error adding opportunity: {e}")
            # Don't re-raise to prevent system crashes

    async def broadcast_to_clients(self, message: Dict):
        """
        Broadcast message to connected WebSocket clients with improved error handling.
        
        Args:
            message (Dict): Message to broadcast to all connected clients
            
        Returns:
            None
        """
        if not self.connected_clients:
            return
        
        disconnected = []
        
        try:
            message_str = json.dumps(message)
        except Exception as json_error:
            logger.error(f"Error serializing message: {json_error}")
            return
        
        # Create a copy of the list to avoid modification during iteration
        clients_to_send = self.connected_clients.copy()
        
        for client in clients_to_send:
            try:
                # Check if client is still connected before sending
                if client.client_state.value == 3:  # DISCONNECTED state
                    disconnected.append(client)
                    continue
                    
                await client.send_text(message_str)
                
            except Exception as send_error:
                error_msg = str(send_error).lower()
                if any(keyword in error_msg for keyword in ['disconnect', 'closed', 'connection']):
                    logger.debug(f"Client disconnected during broadcast: {send_error}")
                else:
                    logger.warning(f"Error sending to client: {send_error}")
                disconnected.append(client)
        
        # Remove disconnected clients
        for client in disconnected:
            if client in self.connected_clients:
                self.connected_clients.remove(client)
                
        if disconnected:
            logger.info(f"Removed {len(disconnected)} disconnected clients. Active: {len(self.connected_clients)}")

    async def cleanup_dead_connections(self):
        """
        Proactively clean up dead WebSocket connections.
        
        Returns:
            None
        """
        try:
            if not self.connected_clients:
                return
                
            dead_clients = []
            
            for client in self.connected_clients.copy():
                try:
                    # Check client state
                    if hasattr(client, 'client_state') and client.client_state.value == 3:  # DISCONNECTED
                        dead_clients.append(client)
                    elif hasattr(client, 'application_state') and client.application_state.value in [2, 3]:  # DISCONNECTING or DISCONNECTED
                        dead_clients.append(client)
                except Exception as check_error:
                    logger.debug(f"Error checking client state: {check_error}")
                    # If we can't check the state, assume it's dead
                    dead_clients.append(client)
            
            # Remove dead clients
            for client in dead_clients:
                if client in self.connected_clients:
                    self.connected_clients.remove(client)
            
            if dead_clients:
                logger.info(f"Cleaned up {len(dead_clients)} dead connections. Active: {len(self.connected_clients)}")
                
        except Exception as e:
            logger.error(f"Error during connection cleanup: {e}")

    async def update_analysis_rate(self, rate: int):
        """
        Update analysis rate and broadcast to clients with connection cleanup.
        
        Args:
            rate (int): New analysis rate value
            
        Returns:
            None
        """
        try:
            self.stats["analysis_rate"] = rate
            
            # Clean up dead connections before broadcasting
            await self.cleanup_dead_connections()
            
            await self.broadcast_to_clients({
                "type": "stats_update",
                "data": {"analysis_rate": rate}
            })
        except Exception as e:
            logger.error(f"Error updating analysis rate: {e}")

    def get_safe_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get portfolio summary with comprehensive error handling.
        
        Returns:
            Dict[str, Any]: Portfolio summary or error information
        """
        try:
            if self.position_manager and hasattr(self.position_manager, 'get_portfolio_summary'):
                try:
                    return self.position_manager.get_portfolio_summary()
                except Exception as portfolio_error:
                    logger.error(f"Error getting portfolio from position manager: {portfolio_error}")
                    return {
                        'total_positions': 0,
                        'total_trades': 0,
                        'success_rate': 0.0,
                        'total_pnl': 0.0,
                        'status': f'Position manager error: {str(portfolio_error)}'
                    }
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
            return {'error': str(e), 'status': 'Portfolio summary failed'}

# Global dashboard instance
dashboard_server = SimpleDashboardServer()

@app.on_event("startup")
async def startup_event():
    """
    Startup event handler with periodic connection cleanup.
    
    Returns:
        None
        
    Raises:
        Exception: If startup fails
    """
    try:
        await dashboard_server.initialize()
        
        # Start periodic cleanup task
        asyncio.create_task(periodic_cleanup_task())
        
        logger.info("Dashboard startup complete with periodic cleanup enabled")
    except Exception as e:
        logger.error(f"Dashboard startup error: {e}")

async def periodic_cleanup_task():
    """
    Periodic task to clean up dead WebSocket connections.
    
    Returns:
        None
    """
    while True:
        try:
            await asyncio.sleep(30)  # Clean up every 30 seconds
            await dashboard_server.cleanup_dead_connections()
        except Exception as e:
            logger.error(f"Error in periodic cleanup task: {e}")
            await asyncio.sleep(60)  # Wait longer on error

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """
    Serve the main dashboard page with error handling.
    
    Returns:
        HTMLResponse: Dashboard HTML content
        
    Raises:
        HTTPException: If dashboard cannot be served
    """
    try:
        # Check if custom template exists
        template_path = "web/templates/dashboard.html"
        if os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return HTMLResponse(content=content)
            except Exception as file_error:
                logger.error(f"Error reading custom template: {file_error}")
                # Fall back to basic dashboard
        
        # Return basic dashboard
        return HTMLResponse(content=get_basic_dashboard_html())
        
    except Exception as e:
        logger.error(f"Dashboard page error: {e}")
        return HTMLResponse(
            content=f"<h1>Dashboard Error</h1><p>Error: {e}</p><p>Check server logs for details.</p>", 
            status_code=500
        )

def get_basic_dashboard_html() -> str:
    """
    Get basic dashboard HTML with detailed modal functionality and comprehensive error handling.
    
    Returns:
        str: Complete HTML dashboard content
    """
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
                margin-bottom: 20px;
            }
            
            .watchlist-panel {
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
                padding: 20px;
                backdrop-filter: blur(10px);
            }
            
            .watchlist-controls {
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
                justify-content: flex-end;
            }
            
            .watchlist-item {
                background: rgba(255,255,255,0.1);
                margin: 8px 0;
                padding: 12px;
                border-radius: 8px;
                border-left: 4px solid #2196F3;
                display: flex;
                justify-content: space-between;
                align-items: center;
                transition: all 0.3s ease;
            }
            
            .watchlist-item:hover {
                background: rgba(255,255,255,0.2);
                transform: translateY(-1px);
            }
            
            .watchlist-token {
                display: flex;
                flex-direction: column;
                gap: 3px;
            }
            
            .watchlist-symbol {
                font-size: 1.1em;
                font-weight: bold;
                color: #2196F3;
            }
            
            .watchlist-details {
                font-size: 0.8em;
                opacity: 0.8;
            }
            
            .watchlist-actions {
                display: flex;
                gap: 5px;
            }
            
            .watchlist-price {
                color: #4CAF50;
                font-weight: bold;
                margin-right: 10px;
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
            .risk-critical { background: rgba(139, 0, 0, 0.3); color: #8B0000; }
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
            .rec-small_buy, .rec-small-buy { background: rgba(33, 150, 243, 0.2); color: #2196F3; }
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
                transition: background 0.3s ease;
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
                font-family: 'Courier New', monospace;
                font-size: 12px !important;
                color: #2196F3 !important;
                background: rgba(0, 0, 0, 0.3);
                padding: 3px 6px;
                border-radius: 3px;
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
                transition: background 0.3s ease;
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
            
            /* Scrollbar styling */
            .modal-content::-webkit-scrollbar {
                width: 8px;
            }
            .modal-content::-webkit-scrollbar-track {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            .modal-content::-webkit-scrollbar-thumb {
                background: rgba(255, 255, 255, 0.3);
                border-radius: 4px;
            }
            .modal-content::-webkit-scrollbar-thumb:hover {
                background: rgba(255, 255, 255, 0.5);
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
                .stats { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 DEX Sniping Dashboard</h1>
                <p>Real-time multi-chain token monitoring with intelligent analysis</p>
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
            
            <!-- Watchlist Panel -->
            <div class="watchlist-panel">
                <h2>👁️ Watchlist</h2>
                <div class="watchlist-controls">
                    <button class="action-btn" onclick="clearWatchlist()">Clear All</button>
                    <button class="action-btn" onclick="exportWatchlist()">Export</button>
                </div>
                <div id="watchlist-list">
                    <p>No tokens in watchlist...</p>
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
            let watchlist = []; // Store watchlist tokens
            
            // Load watchlist from localStorage on startup
            function loadWatchlist() {
                try {
                    const saved = localStorage.getItem('dex_watchlist');
                    if (saved) {
                        watchlist = JSON.parse(saved);
                        renderWatchlist();
                    }
                } catch (error) {
                    console.error('Error loading watchlist:', error);
                    watchlist = [];
                }
            }
            
            // Save watchlist to localStorage
            function saveWatchlist() {
                try {
                    localStorage.setItem('dex_watchlist', JSON.stringify(watchlist));
                } catch (error) {
                    console.error('Error saving watchlist:', error);
                }
            }
            
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
                    
                    // Add to opportunities array for details view
                    opportunities.unshift(opportunity);
                    if (opportunities.length > 50) {
                        opportunities.pop();
                    }
                    
                    const item = document.createElement('div');
                    item.className = 'opportunity-item';
                    
                    // Safe data extraction with fallbacks
                    const tokenSymbol = opportunity.token_symbol || 'UNKNOWN';
                    const chain = opportunity.chain || 'unknown';
                    const riskLevel = opportunity.risk_level || 'unknown';
                    const recommendation = opportunity.recommendation || 'UNKNOWN';
                    const confidence = opportunity.confidence || 'UNKNOWN';
                    const score = opportunity.score || 0;
                    const liquidityUsd = opportunity.liquidity_usd || 0;
                    const detectedAt = opportunity.detected_at ? new Date(opportunity.detected_at) : new Date();
                    
                    item.innerHTML = `
                        <div class="opportunity-header">
                            <span class="token-symbol">${tokenSymbol}</span>
                            <span class="risk-badge risk-${riskLevel}">${riskLevel.toUpperCase()}</span>
                        </div>
                        <div class="opportunity-details">
                            <span class="chain-badge">${chain.toUpperCase()}</span>
                            Recommendation: <span class="recommendation rec-${recommendation.toLowerCase().replace('_', '-')}">${recommendation}</span><br>
                            Confidence: ${confidence} | Score: ${score.toFixed(2)}<br>
                            Liquidity: $${liquidityUsd.toLocaleString()}<br>
                            <small>Detected: ${detectedAt.toLocaleTimeString()}</small>
                        </div>
                        <div class="opportunity-actions">
                            <button class="action-btn" onclick="executeTrade('${tokenSymbol}')">Trade</button>
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
                    
                    if (confidence === 'HIGH') {
                        const highConfEl = document.getElementById('high-confidence');
                        highConfEl.textContent = parseInt(highConfEl.textContent) + 1;
                    }
                    
                } catch (error) {
                    console.error('Error adding opportunity to list:', error);
                }
            }
            
            function showTokenDetails(tokenAddress, opportunityData = null) {
                try {
                    let opportunity;
                    
                    if (opportunityData) {
                        // Use provided data (e.g., from watchlist)
                        opportunity = opportunityData;
                    } else {
                        // Find in current opportunities
                        opportunity = opportunities.find(opp => opp.token_address === tokenAddress);
                        if (!opportunity) {
                            showNotification('Opportunity details not found', 'error');
                            return;
                        }
                    }
                    
                    // Update modal title
                    document.getElementById('modal-title').textContent = `${opportunity.token_symbol} - Detailed Analysis`;
                    
                    // Build modal content with safe data access
                    const modalBody = document.getElementById('modal-body');
                    const reasons = opportunity.reasons || [];
                    const warnings = opportunity.warnings || [];
                    
                    modalBody.innerHTML = `
                        <div class="detail-section">
                            <h3>Token Information</h3>
                            <div class="detail-grid">
                                <div class="detail-item">
                                    <label>Symbol:</label>
                                    <span>${opportunity.token_symbol || 'UNKNOWN'}</span>
                                </div>
                                <div class="detail-item">
                                    <label>Address:</label>
                                    <span class="address-text">${opportunity.token_address || 'unknown'}</span>
                                    <button class="copy-btn" onclick="copyToClipboard('${opportunity.token_address}')">Copy</button>
                                </div>
                                <div class="detail-item">
                                    <label>Chain:</label>
                                    <span class="chain-badge">${opportunity.chain || 'unknown'}</span>
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
                                    <span class="risk-badge risk-${opportunity.risk_level}">${(opportunity.risk_level || 'unknown').toUpperCase()}</span>
                                </div>
                                <div class="detail-item">
                                    <label>Confidence Score:</label>
                                    <span>${(opportunity.score || 0).toFixed(3)}/1.0</span>
                                </div>
                                <div class="detail-item">
                                    <label>Recommendation:</label>
                                    <span class="recommendation rec-${(opportunity.recommendation || 'unknown').toLowerCase().replace('_', '-')}">${opportunity.recommendation || 'UNKNOWN'}</span>
                                </div>
                                <div class="detail-item">
                                    <label>Confidence:</label>
                                    <span>${opportunity.confidence || 'UNKNOWN'}</span>
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
                                    <span>$${(opportunity.liquidity_usd || 0).toLocaleString()}</span>
                                </div>
                                ${opportunity.pair_address && opportunity.pair_address !== 'unknown' ? `
                                <div class="detail-item">
                                    <label>Pair Address:</label>
                                    <span class="address-text">${opportunity.pair_address}</span>
                                    <button class="copy-btn" onclick="copyToClipboard('${opportunity.pair_address}')">Copy</button>
                                </div>
                                ` : ''}
                            </div>
                        </div>
                        
                        ${reasons.length > 0 ? `
                        <div class="detail-section">
                            <h3>Analysis Reasons</h3>
                            <ul style="margin-left: 20px; line-height: 1.6; color: #4CAF50;">
                                ${reasons.map(reason => `<li>${reason}</li>`).join('')}
                            </ul>
                        </div>
                        ` : ''}
                        
                        ${warnings.length > 0 ? `
                        <div class="detail-section">
                            <h3>Risk Warnings</h3>
                            <ul style="margin-left: 20px; line-height: 1.6; color: #f44336;">
                                ${warnings.map(warning => `<li>${warning}</li>`).join('')}
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
                    
                } catch (error) {
                    console.error('Error showing token details:', error);
                    showNotification('Error loading token details', 'error');
                }
            }
            
            function getExternalLinks(opportunity) {
                try {
                    const links = [];
                    const address = opportunity.token_address || '';
                    const chain = (opportunity.chain || '').toLowerCase();
                    
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
                    
                    const symbol = opportunity.token_symbol || '';
                    if (symbol) {
                        links.push(`<a href="https://www.coingecko.com/en/search_redirect?id=${symbol}" target="_blank" class="external-link">CoinGecko</a>`);
                    }
                    
                    return links.join('');
                } catch (error) {
                    console.error('Error generating external links:', error);
                    return '<span>External links unavailable</span>';
                }
            }
            
            function closeDetailsModal() {
                try {
                    document.getElementById('details-modal').classList.remove('show');
                } catch (error) {
                    console.error('Error closing modal:', error);
                }
            }
            
            function copyToClipboard(text) {
                try {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        navigator.clipboard.writeText(text).then(() => {
                            showNotification('Copied to clipboard!', 'success');
                        }).catch((error) => {
                            console.error('Clipboard API failed:', error);
                            fallbackCopyToClipboard(text);
                        });
                    } else {
                        fallbackCopyToClipboard(text);
                    }
                } catch (error) {
                    console.error('Copy to clipboard error:', error);
                    showNotification('Copy failed', 'error');
                }
            }
            
            function fallbackCopyToClipboard(text) {
                try {
                    const textArea = document.createElement('textarea');
                    textArea.value = text;
                    document.body.appendChild(textArea);
                    textArea.select();
                    const success = document.execCommand('copy');
                    document.body.removeChild(textArea);
                    
                    if (success) {
                        showNotification('Copied to clipboard!', 'success');
                    } else {
                        showNotification('Copy failed', 'error');
                    }
                } catch (error) {
                    console.error('Fallback copy failed:', error);
                    showNotification('Copy not supported', 'error');
                }
            }
            
            function showNotification(message, type = 'info') {
                try {
                    const notification = document.createElement('div');
                    const bgColor = type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3';
                    
                    notification.style.cssText = `
                        position: fixed;
                        top: 20px;
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
            
            function executeTrade(tokenSymbol) {
                try {
                    showNotification(`Trade execution for ${tokenSymbol} - Feature coming soon!`, 'info');
                } catch (error) {
                    console.error('Error in executeTrade:', error);
                }
            }
            
            function updateStats(stats) {
                try {
                    if (stats.analysis_rate !== undefined) {
                        const rateEl = document.getElementById('analysis-rate');
                        if (rateEl) {
                            rateEl.textContent = stats.analysis_rate;
                        }
                    }
                } catch (error) {
                    console.error('Error updating stats:', error);
                }
            }
            
            function updateConnectionStatus(connected) {
                try {
                    const statusEl = document.getElementById('connection-status');
                    if (statusEl) {
                        if (connected) {
                            statusEl.textContent = 'Connected';
                            statusEl.className = 'connection-status connected';
                        } else {
                            statusEl.textContent = 'Disconnected';
                            statusEl.className = 'connection-status disconnected';
                        }
                    }
                } catch (error) {
                    console.error('Error updating connection status:', error);
                }
            }
            
            // Close modal when clicking outside
            document.getElementById('details-modal').addEventListener('click', function(e) {
                try {
                    if (e.target === this) {
                        closeDetailsModal();
                    }
                } catch (error) {
                    console.error('Error in modal click handler:', error);
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
            try {
                loadWatchlist(); // Load saved watchlist
                connectWebSocket();
                fetchStats();
                setInterval(fetchStats, 10000); // Update stats every 10 seconds
            } catch (error) {
                console.error('Error during initialization:', error);
            }
        </script>
    </body>
    </html>
    """

@app.get("/api/stats")
async def get_stats():
    """
    Get system statistics with comprehensive error handling.
    
    Returns:
        Dict: System statistics or error information
        
    Raises:
        HTTPException: If stats cannot be retrieved
    """
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
        # Return partial data instead of failing completely
        return {
            "error": str(e), 
            "connected_clients": len(dashboard_server.connected_clients) if dashboard_server.connected_clients else 0,
            "total_opportunities": dashboard_server.stats.get("total_opportunities", 0),
            "status": "error"
        }

@app.get("/api/opportunities")
async def get_opportunities():
    """
    Get recent opportunities with error handling.
    
    Returns:
        List[Dict]: Recent opportunities or empty list on error
        
    Raises:
        HTTPException: If opportunities cannot be retrieved
    """
    try:
        # Return last 20 opportunities safely
        opportunities = dashboard_server.opportunities[-20:] if dashboard_server.opportunities else []
        return opportunities
    except Exception as e:
        logger.error(f"Opportunities error: {e}")
        return []

@app.get("/api/trades")
async def get_trade_history():
    """
    Get recent trade history with comprehensive error handling.
    
    Returns:
        Dict: Trade history or error information
        
    Raises:
        HTTPException: If trades cannot be retrieved
    """
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
                        logger.error(f"Error processing individual trade: {trade_error}")
                        continue
            except Exception as position_error:
                logger.error(f"Error accessing position manager data: {position_error}")
        
        # Return trades with success status
        return {"trades": trades, "status": "success"}
        
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        return {"trades": [], "error": str(e), "status": "error"}

@app.get("/api/positions")
async def get_positions():
    """
    Get current trading positions with comprehensive error handling.
    
    Returns:
        Dict: Current positions or error information
        
    Raises:
        HTTPException: If positions cannot be retrieved
    """
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
                        logger.error(f"Error processing position {position_id}: {pos_error}")
                        continue
            except Exception as positions_error:
                logger.error(f"Error accessing active positions: {positions_error}")
        
        return {"positions": positions, "status": "success"}
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return {"positions": [], "error": str(e), "status": "error"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates with improved disconnect handling.
    
    Args:
        websocket (WebSocket): WebSocket connection
        
    Returns:
        None
        
    Raises:
        WebSocketDisconnect: When client disconnects
    """
    await websocket.accept()
    dashboard_server.connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(dashboard_server.connected_clients)}")
    
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
                else:
                    logger.debug(f"Unknown WebSocket message type: {message.get('type')}")
                    
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    # If we can't send ping, connection is dead
                    break
                    
            except json.JSONDecodeError as json_error:
                logger.warning(f"Invalid JSON from WebSocket client: {json_error}")
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
                    logger.debug(f"WebSocket connection closed: {message_error}")
                    break
                else:
                    logger.error(f"WebSocket message processing error: {message_error}")
                    # Continue the loop for non-disconnect errors
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Always clean up the client connection
        if websocket in dashboard_server.connected_clients:
            dashboard_server.connected_clients.remove(websocket)
        logger.info(f"WebSocket cleanup complete. Remaining clients: {len(dashboard_server.connected_clients)}")

if __name__ == "__main__":
    try:
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise