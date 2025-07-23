# api/dashboard_server.py (Full FastAPI Version)
"""
FastAPI server providing REST API and WebSocket for the dashboard interface.
Connects the web dashboard to the trading execution system.
"""

import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
import uvicorn
import os
from models.token import TradingOpportunity, RiskLevel
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
    Dashboard server that provides API endpoints and WebSocket connections
    for real-time communication with the trading system.
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
        self.opportunities_queue: List[TradingOpportunity] = []
        
        # Statistics
        self.stats = {
            "total_opportunities": 0,
            "high_confidence": 0,
            "active_chains": 3,
            "analysis_rate": 0,
            "uptime_start": datetime.now()
        }

    def get_safe_portfolio_summary(self) -> Dict[str]:
        """
        Safely get portfolio summary from available components.
        
        Returns:
            Portfolio summary dictionary
        """
        try:
            # Try position manager first (most comprehensive)
            if self.position_manager:
                return self.position_manager.get_portfolio_summary()
            
            # Try trading executor
            elif self.trading_executor and hasattr(self.trading_executor, 'get_portfolio_summary'):
                return self.trading_executor.get_portfolio_summary()
            
            # Fallback to default
            else:
                return {
                    'total_positions': 0,
                    'total_trades': 0,
                    'successful_trades': 0,
                    'success_rate': 0.0,
                    'total_profit': 0.0,
                    'daily_losses': 0.0,
                    'active_orders': 0,
                    'status': 'No trading components connected'
                }
                
        except Exception as e:
            self.logger.error(f"Error getting safe portfolio summary: {e}")
            return {
                'total_positions': 0,
                'total_trades': 0,
                'error': str(e)
            }

    def get_safe_risk_status(self) -> Dict[str, Any]:
        """
        Safely get risk management status.
        
        Returns:
            Risk status dictionary
        """
        try:
            if self.risk_manager:
                return self.risk_manager.get_portfolio_status()
            else:
                return {
                    'total_positions': 0,
                    'current_exposure_usd': 0.0,
                    'max_exposure_usd': 0.0,
                    'daily_pnl': 0.0,
                    'status': 'No risk manager connected'
                }
                
        except Exception as e:
            self.logger.error(f"Error getting risk status: {e}")
            return {'error': str(e)}
        
    async def initialize(self):
        """Initialize the trading executor and start services."""
        try:
            self.logger.info("Initializing full dashboard server...")
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

    async def add_opportunity(self, opportunity: TradingOpportunity):
        """Add a new trading opportunity and broadcast to clients."""
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
                
            # Broadcast to connected clients
            await self.broadcast_message({
                "type": "new_opportunity",
                "data": {
                    "token_symbol": opportunity.token.symbol or "UNKNOWN",
                    "token_address": opportunity.token.address,
                    "chain": opportunity.metadata.get("chain", "ethereum"),
                    "risk_level": opportunity.contract_analysis.risk_level.value,
                    "recommendation": recommendation.get("action", "UNKNOWN"),
                    "confidence": recommendation.get("confidence", "UNKNOWN"),
                    "score": recommendation.get("score", 0.0),
                    "liquidity_usd": opportunity.liquidity.liquidity_usd,
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            self.logger.debug(f"Added opportunity: {opportunity.token.symbol}")
            
        except Exception as e:
            self.logger.error(f"Error adding opportunity: {e}")

    async def update_analysis_rate(self, rate: int):
        """Update the analysis rate statistic."""
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

# Global instance
dashboard_server = DashboardServer()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await dashboard_server.initialize()

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
                </style>
            </head>
            <body>
                <h1>🚀 DEX Sniping Dashboard</h1>
                <div class="card">
                    <h2>System Status</h2>
                    <p>✅ Dashboard server running</p>
                    <p>📊 Analysis engine active</p>
                    <p>💹 Trading system ready</p>
                </div>
                
                <div class="card">
                    <h2>API Endpoints</h2>
                    <p>GET /api/stats - System statistics</p>
                    <p>GET /api/opportunities - Current opportunities</p>
                    <p>GET /api/positions - Trading positions</p>
                    <p>POST /api/trade - Execute manual trade</p>
                    <p>WebSocket /ws - Real-time updates</p>
                </div>
                
                <div class="card">
                    <h2>Instructions</h2>
                    <p>1. Place the full dashboard.html in web/templates/</p>
                    <p>2. Refresh this page to see the full interface</p>
                    <p>3. Use /api endpoints for programmatic access</p>
                </div>
                
                <script>
                    // Simple WebSocket connection test
                    const ws = new WebSocket('ws://localhost:8000/ws');
                    ws.onopen = () => console.log('WebSocket connected');
                    ws.onmessage = (event) => console.log('Received:', JSON.parse(event.data));
                </script>
            </body>
            </html>
            """)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Dashboard Error</h1><p>{e}</p>")

@app.get("/api/stats")
async def get_stats():
    """Get current system statistics with safe component access."""
    try:
        # Get portfolio summary safely
        portfolio = dashboard_server.get_safe_portfolio_summary()
        
        # Get risk status safely
        risk_status = dashboard_server.get_safe_risk_status()
        
        # Calculate uptime
        uptime = datetime.now() - dashboard_server.stats["uptime_start"]
        
        return {
            "total_opportunities": dashboard_server.stats["total_opportunities"],
            "high_confidence": dashboard_server.stats["high_confidence"], 
            "active_chains": dashboard_server.stats["active_chains"],
            "analysis_rate": dashboard_server.stats["analysis_rate"],
            "uptime_hours": round(uptime.total_seconds() / 3600, 2),
            "portfolio": portfolio,
            "risk_status": risk_status,
            "connected_clients": len(dashboard_server.connected_clients),
            "components_status": {
                "trading_executor": dashboard_server.trading_executor is not None,
                "position_manager": dashboard_server.position_manager is not None,
                "risk_manager": dashboard_server.risk_manager is not None
            }
        }
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting stats: {e}")
        # Return basic stats even if there's an error
        return {
            "total_opportunities": 0,
            "high_confidence": 0,
            "active_chains": 0,
            "analysis_rate": 0,
            "uptime_hours": 0,
            "portfolio": {"error": str(e)},
            "connected_clients": len(dashboard_server.connected_clients),
            "error": "Stats calculation failed"
        }





@app.get("/api/opportunities", response_model=List[OpportunityResponse])
async def get_opportunities():
    """Get current trading opportunities."""
    try:
        opportunities = []
        
        for opp in dashboard_server.opportunities_queue[-20:]:  # Last 20
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
            
        return opportunities
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/positions", response_model=List[PositionResponse])
async def get_positions():
    """Get current trading positions with safe access."""
    try:
        positions = []
        
        if dashboard_server.position_manager:
            # Get positions from position manager
            for position_id, position in dashboard_server.position_manager.active_positions.items():
                positions.append(PositionResponse(
                    token_symbol=position.token_symbol,
                    amount=float(position.entry_amount),
                    entry_price=float(position.entry_price),
                    current_price=float(position.current_price),
                    pnl=float(position.unrealized_pnl),
                    pnl_percentage=position.unrealized_pnl_percentage
                ))
        elif dashboard_server.trading_executor:
            # Fallback to trading executor
            if hasattr(dashboard_server.trading_executor, 'positions'):
                for position in dashboard_server.trading_executor.positions.values():
                    positions.append(PositionResponse(
                        token_symbol=position.token_symbol,
                        amount=float(position.amount),
                        entry_price=float(position.entry_price),
                        current_price=float(position.current_price),
                        pnl=float(position.pnl),
                        pnl_percentage=position.pnl_percentage
                    ))
            
        return positions
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting positions: {e}")
        # Return empty list on error rather than raising exception
        return []






@app.get("/api/trades")
async def get_trade_history():
    """Get recent trade history with safe access."""
    try:
        trades = []
        
        if dashboard_server.position_manager:
            # Get closed positions from position manager
            for exit in dashboard_server.position_manager.closed_positions[-50:]:  # Last 50
                trades.append({
                    "id": exit.position_id,
                    "token_symbol": dashboard_server.position_manager._get_token_from_position_id(exit.position_id),
                    "trade_type": "sell",  # Exit trades
                    "amount": float(exit.exit_amount),
                    "status": "completed",
                    "created_at": exit.exit_time.isoformat(),
                    "executed_at": exit.exit_time.isoformat(),
                    "tx_hash": exit.exit_tx_hash,
                    "chain": dashboard_server.position_manager._get_chain_from_position_id(exit.position_id),
                    "pnl": float(exit.realized_pnl),
                    "pnl_percentage": exit.realized_pnl_percentage
                })
        elif dashboard_server.trading_executor:
            # Fallback to trading executor
            if hasattr(dashboard_server.trading_executor, 'trade_history'):
                for trade in dashboard_server.trading_executor.trade_history[-50:]:
                    trades.append({
                        "id": trade.id,
                        "token_symbol": trade.token_symbol,
                        "trade_type": trade.trade_type.value,
                        "amount": float(trade.amount),
                        "status": trade.status.value,
                        "created_at": trade.created_at.isoformat(),
                        "executed_at": trade.executed_at.isoformat() if trade.executed_at else None,
                        "tx_hash": trade.tx_hash,
                        "chain": trade.chain
                    })
            
        return {"trades": trades}
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting trade history: {e}")
        return {"trades": [], "error": str(e)}





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
                    "status": result.status.value,
                    "tx_hash": result.tx_hash
                }
            })
            
            return {
                "success": True,
                "trade_id": result.id,
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
            "opportunities_in_queue": len(dashboard_server.opportunities_queue),
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
            "trade_history": [
                {
                    "id": trade.id,
                    "token_symbol": trade.token_symbol,
                    "trade_type": trade.trade_type.value,
                    "amount": float(trade.amount),
                    "status": trade.status.value,
                    "created_at": trade.created_at.isoformat(),
                    "executed_at": trade.executed_at.isoformat() if trade.executed_at else None,
                    "chain": trade.chain
                }
                for trade in dashboard_server.trading_executor.trade_history
            ] if dashboard_server.trading_executor else [],
            "positions": [
                {
                    "token_symbol": pos.token_symbol,
                    "amount": float(pos.amount),
                    "entry_price": float(pos.entry_price),
                    "current_price": float(pos.current_price),
                    "pnl": float(pos.pnl),
                    "entry_time": pos.entry_time.isoformat()
                }
                for pos in dashboard_server.trading_executor.positions.values()
            ] if dashboard_server.trading_executor else []
        }
        
        return export_data
        
    except Exception as e:
        dashboard_server.logger.error(f"Error exporting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "dashboard_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )