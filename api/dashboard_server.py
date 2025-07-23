# api/dashboard_server.py (Full Fix)
"""
FastAPI server providing REST API and WebSocket for the dashboard interface.
Fixed version with proper imports and component handling.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
import uvicorn
import os

# Fix imports to match actual project structure
try:
    from models.token import TradingOpportunity, RiskLevel
except ImportError:
    # Fallback if models aren't available
    TradingOpportunity = None
    RiskLevel = None

from utils.logger import logger_manager

# Pydantic models for API
class TradeRequest(BaseModel):
    token_address: str
    token_symbol: str
    amount: float
    chain: str = "ethereum"
    order_type: str = "market"

class PositionResponse(BaseModel):
    token_symbol: str
    amount: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_percentage: float

class OpportunityResponse(BaseModel):
    token_symbol: str
    token_address: str
    chain: str
    risk_level: str
    recommendation: str
    confidence: str
    score: float
    liquidity_usd: float
    age_minutes: int

# Create FastAPI app
app = FastAPI(title="DEX Sniping Dashboard API", version="1.0.0")

# Templates for serving HTML
templates = Jinja2Templates(directory="web/templates")

# Static files (CSS, JS, images)
if os.path.exists("web/static"):
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

class DashboardServer:
    """
    Dashboard server with fixed component handling.
    """
    
    def __init__(self):
        """Initialize the dashboard server."""
        self.logger = logger_manager.get_logger("DashboardServer")
        
        # Trading system components (will be set by main system)
        self.trading_executor = None
        self.risk_manager = None
        self.position_manager = None
        
        # WebSocket clients
        self.connected_clients: List[WebSocket] = []
        self.opportunities_queue: List = []  # Use generic list instead of TradingOpportunity
        
        # Statistics
        self.stats = {
            "total_opportunities": 0,
            "high_confidence": 0,
            "active_chains": 3,
            "analysis_rate": 0,
            "uptime_start": datetime.now()
        }

    async def initialize(self):
        """Initialize the trading executor and start services."""
        try:
            self.logger.info("Initializing dashboard server...")
            self.logger.info("Dashboard server initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize dashboard server: {e}")
            raise

    async def broadcast_message(self, message: dict):
        """Broadcast message to all connected WebSocket clients."""
        if not self.connected_clients:
            return
            
        disconnected_clients = []
        
        for client in self.connected_clients:
            try:
                await client.send_text(json.dumps(message))
            except Exception as e:
                self.logger.warning(f"Failed to send message to client: {e}")
                disconnected_clients.append(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in self.connected_clients:
                self.connected_clients.remove(client)

    async def add_opportunity(self, opportunity):
        """Add a new trading opportunity and broadcast to clients."""
        try:
            # Convert opportunity to simple dict for storage
            if hasattr(opportunity, 'token') and hasattr(opportunity.token, 'symbol'):
                opp_data = {
                    'token_symbol': opportunity.token.symbol or "UNKNOWN",
                    'token_address': opportunity.token.address,
                    'chain': opportunity.metadata.get('chain', 'ethereum'),
                    'detected_at': datetime.now().isoformat(),
                    'liquidity_usd': getattr(opportunity.liquidity, 'liquidity_usd', 0) if hasattr(opportunity, 'liquidity') else 0
                }
                
                # Add risk and recommendation data if available
                if hasattr(opportunity, 'contract_analysis') and opportunity.contract_analysis:
                    opp_data['risk_level'] = opportunity.contract_analysis.risk_level.value if hasattr(opportunity.contract_analysis, 'risk_level') else 'unknown'
                else:
                    opp_data['risk_level'] = 'unknown'
                    
                recommendation = opportunity.metadata.get('recommendation', {}) if hasattr(opportunity, 'metadata') else {}
                opp_data['recommendation'] = recommendation.get('action', 'UNKNOWN')
                opp_data['confidence'] = recommendation.get('confidence', 'UNKNOWN')
                opp_data['score'] = recommendation.get('score', 0.0)
                
            else:
                # Fallback for invalid opportunity objects
                opp_data = {
                    'token_symbol': 'UNKNOWN',
                    'token_address': 'unknown',
                    'chain': 'unknown',
                    'risk_level': 'unknown',
                    'recommendation': 'UNKNOWN',
                    'confidence': 'UNKNOWN',
                    'score': 0.0,
                    'liquidity_usd': 0,
                    'detected_at': datetime.now().isoformat()
                }
            
            # Add to queue (keep last 100)
            self.opportunities_queue.append(opp_data)
            if len(self.opportunities_queue) > 100:
                self.opportunities_queue.pop(0)
                
            # Update stats
            self.stats["total_opportunities"] += 1
            
            if opp_data.get('confidence') == "HIGH":
                self.stats["high_confidence"] += 1
                
            # Broadcast to connected clients
            await self.broadcast_message({
                "type": "new_opportunity",
                "data": opp_data
            })
            
            self.logger.debug(f"Added opportunity: {opp_data['token_symbol']}")
            
        except Exception as e:
            self.logger.error(f"Error adding opportunity: {e}")

    async def update_analysis_rate(self, rate: int):
        """Update the analysis rate statistic."""
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

    def get_safe_portfolio_summary(self) -> Dict[str, Any]:
        """Safely get portfolio summary from available components."""
        try:
            # Try position manager first
            if self.position_manager and hasattr(self.position_manager, 'get_portfolio_summary'):
                return self.position_manager.get_portfolio_summary()
            
            # Try trading executor
            elif self.trading_executor and hasattr(self.trading_executor, 'get_portfolio_summary'):
                return self.trading_executor.get_portfolio_summary()
            
            # Fallback to basic stats
            else:
                return {
                    'total_positions': 0,
                    'total_trades': 0,
                    'successful_trades': 0,
                    'success_rate': 0.0,
                    'total_profit': 0.0,
                    'daily_losses': 0.0,
                    'active_orders': 0,
                    'status': 'Trading components not connected'
                }
                
        except Exception as e:
            self.logger.error(f"Error getting portfolio summary: {e}")
            return {
                'total_positions': 0,
                'total_trades': 0,
                'error': str(e)
            }

# Global instance
dashboard_server = DashboardServer()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    try:
        await dashboard_server.initialize()
    except Exception as e:
        print(f"Dashboard startup error: {e}")

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serve the main dashboard page."""
    try:
        # If template exists, use it
        if os.path.exists("web/templates/dashboard.html"):
            return templates.TemplateResponse("dashboard.html", {"request": request})
        else:
            # Return simple HTML if template doesn't exist
            return HTMLResponse(content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>DEX Sniping Dashboard</title>
                <style>
                    body { font-family: Arial; background: #1a1b3e; color: white; padding: 20px; }
                    .card { background: rgba(255,255,255,0.1); padding: 20px; margin: 10px; border-radius: 10px; }
                    .opportunity { border-left: 4px solid #00ff88; margin: 10px 0; padding: 10px; }
                    .stats { display: flex; gap: 20px; }
                    .status { color: #00ff88; }
                </style>
            </head>
            <body>
                <h1>🚀 DEX Sniping Dashboard</h1>
                <div class="card">
                    <h2>System Status</h2>
                    <p class="status">✅ Dashboard server running</p>
                    <p class="status">📊 Analysis engine active</p>
                    <p class="status">💹 Trading system ready</p>
                </div>
                
                <div class="card">
                    <h2>API Endpoints</h2>
                    <p>GET /api/stats - System statistics</p>
                    <p>GET /api/opportunities - Current opportunities</p>
                    <p>GET /api/positions - Trading positions</p>
                    <p>WebSocket /ws - Real-time updates</p>
                </div>
                
                <div class="card">
                    <h2>Recent Activity</h2>
                    <div id="activity">Loading...</div>
                </div>
                
                <script>
                    // Simple WebSocket connection
                    try {
                        const ws = new WebSocket('ws://localhost:8000/ws');
                        ws.onopen = () => {
                            console.log('WebSocket connected');
                            document.getElementById('activity').innerHTML = '<p class="status">✅ Real-time connection active</p>';
                        };
                        ws.onmessage = (event) => {
                            const data = JSON.parse(event.data);
                            console.log('Received:', data);
                            
                            if (data.type === 'new_opportunity') {
                                const activity = document.getElementById('activity');
                                const opp = data.data;
                                activity.innerHTML = `
                                    <div class="opportunity">
                                        <strong>${opp.token_symbol}</strong> on ${opp.chain}<br>
                                        Risk: ${opp.risk_level} | Recommendation: ${opp.recommendation}<br>
                                        <small>Detected: ${new Date(opp.detected_at).toLocaleTimeString()}</small>
                                    </div>
                                ` + activity.innerHTML;
                            }
                        };
                        ws.onerror = (error) => {
                            console.error('WebSocket error:', error);
                            document.getElementById('activity').innerHTML = '<p style="color: red;">❌ Connection error</p>';
                        };
                    } catch (error) {
                        console.error('WebSocket setup error:', error);
                        document.getElementById('activity').innerHTML = '<p style="color: red;">❌ WebSocket not supported</p>';
                    }
                    
                    // Fetch stats periodically
                    setInterval(async () => {
                        try {
                            const response = await fetch('/api/stats');
                            const stats = await response.json();
                            console.log('Stats:', stats);
                        } catch (error) {
                            console.error('Stats fetch error:', error);
                        }
                    }, 5000);
                </script>
            </body>
            </html>
            """)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Dashboard Error</h1><p>{e}</p>", status_code=500)

@app.get("/api/stats")
async def get_stats():
    """Get current system statistics."""
    try:
        portfolio = dashboard_server.get_safe_portfolio_summary()
        
        uptime = datetime.now() - dashboard_server.stats["uptime_start"]
        
        return {
            "total_opportunities": dashboard_server.stats["total_opportunities"],
            "high_confidence": dashboard_server.stats["high_confidence"], 
            "active_chains": dashboard_server.stats["active_chains"],
            "analysis_rate": dashboard_server.stats["analysis_rate"],
            "uptime_hours": round(uptime.total_seconds() / 3600, 2),
            "portfolio": portfolio,
            "connected_clients": len(dashboard_server.connected_clients),
            "components_status": {
                "trading_executor": dashboard_server.trading_executor is not None,
                "position_manager": dashboard_server.position_manager is not None,
                "risk_manager": dashboard_server.risk_manager is not None
            }
        }
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting stats: {e}")
        return {
            "error": str(e),
            "total_opportunities": 0,
            "connected_clients": len(dashboard_server.connected_clients)
        }

@app.get("/api/opportunities")
async def get_opportunities():
    """Get current trading opportunities."""
    try:
        opportunities = []
        
        for opp in dashboard_server.opportunities_queue[-20:]:  # Last 20
            try:
                detected_time = datetime.fromisoformat(opp.get('detected_at', datetime.now().isoformat()))
                age_minutes = (datetime.now() - detected_time).total_seconds() / 60
                
                opportunities.append({
                    "token_symbol": opp.get('token_symbol', 'UNKNOWN'),
                    "token_address": opp.get('token_address', 'unknown'),
                    "chain": opp.get('chain', 'unknown'),
                    "risk_level": opp.get('risk_level', 'unknown'),
                    "recommendation": opp.get('recommendation', 'UNKNOWN'),
                    "confidence": opp.get('confidence', 'UNKNOWN'),
                    "score": opp.get('score', 0.0),
                    "liquidity_usd": opp.get('liquidity_usd', 0),
                    "age_minutes": int(age_minutes)
                })
            except Exception as opp_error:
                dashboard_server.logger.error(f"Error processing opportunity: {opp_error}")
                continue
            
        return opportunities
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting opportunities: {e}")
        return []

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
                    dashboard_server.logger.error(f"Error processing position {position_id}: {pos_error}")
                    continue
            
        return positions
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting positions: {e}")
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
                    dashboard_server.logger.error(f"Error processing trade: {trade_error}")
                    continue
            
        return {"trades": trades}
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting trade history: {e}")
        return {"trades": [], "error": str(e)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    dashboard_server.connected_clients.append(websocket)
    dashboard_server.logger.info(f"New WebSocket client connected. Total: {len(dashboard_server.connected_clients)}")
    
    try:
        while True:
            # Keep connection alive and listen for client messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif message.get("type") == "subscribe":
                # Client wants to subscribe to specific updates
                await websocket.send_text(json.dumps({
                    "type": "subscribed",
                    "message": "Subscribed to real-time updates"
                }))
                
    except WebSocketDisconnect:
        dashboard_server.connected_clients.remove(websocket)
        dashboard_server.logger.info(f"WebSocket client disconnected. Remaining: {len(dashboard_server.connected_clients)}")
    except Exception as e:
        dashboard_server.logger.error(f"WebSocket error: {e}")
        if websocket in dashboard_server.connected_clients:
            dashboard_server.connected_clients.remove(websocket)

if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "dashboard_server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )

    @app.get("/api/opportunity/{token_address}")
async def get_opportunity_details(token_address: str):
    """Get detailed information about a specific opportunity."""
    try:
        # Find opportunity by token address
        for opp in dashboard_server.opportunities_queue:
            if opp.get('token_address') == token_address:
                # Add additional details that might not be in the basic opportunity data
                detailed_opp = opp.copy()
                
                # Add timestamp information
                detected_time = datetime.fromisoformat(opp.get('detected_at', datetime.now().isoformat()))
                detailed_opp['age_seconds'] = (datetime.now() - detected_time).total_seconds()
                
                # Add analysis timestamp if available
                if 'analysis_timestamp' in opp:
                    analysis_time = datetime.fromisoformat(opp['analysis_timestamp'])
                    detailed_opp['analysis_age_seconds'] = (datetime.now() - analysis_time).total_seconds()
                
                return detailed_opp
        
        # If not found, return 404
        raise HTTPException(status_code=404, detail="Opportunity not found")
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting opportunity details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chain/{chain_name}/stats")
async def get_chain_stats(chain_name: str):
    """Get statistics for a specific chain."""
    try:
        chain_opportunities = [
            opp for opp in dashboard_server.opportunities_queue 
            if opp.get('chain', '').upper() == chain_name.upper()
        ]
        
        total_count = len(chain_opportunities)
        high_confidence_count = len([
            opp for opp in chain_opportunities 
            if opp.get('confidence') == 'HIGH'
        ])
        
        # Calculate average score
        scores = [opp.get('score', 0) for opp in chain_opportunities if opp.get('score')]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # Get recommendation distribution
        recommendations = {}
        for opp in chain_opportunities:
            rec = opp.get('recommendation', 'UNKNOWN')
            recommendations[rec] = recommendations.get(rec, 0) + 1
        
        return {
            "chain": chain_name.upper(),
            "total_opportunities": total_count,
            "high_confidence_count": high_confidence_count,
            "average_score": round(avg_score, 3),
            "recommendation_distribution": recommendations,
            "recent_opportunities": chain_opportunities[-10:]  # Last 10
        }
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting chain stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))