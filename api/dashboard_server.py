# api/dashboard_server.py (Main FastAPI Routes)
"""
FastAPI server providing REST API routes for the dashboard interface.
Main entry point for the web dashboard with route definitions.
"""

import asyncio
import json
import os
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.dashboard_core import DashboardServer, dashboard_server
from api.dashboard_models import (
    TradeRequest, 
    OpportunityResponse, 
    WatchlistAddRequest
)
from api.dashboard_html import get_enhanced_dashboard_html
from models.watchlist import watchlist_manager, WatchlistStatus
from utils.logger import logger_manager


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


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize services on startup."""
    try:
        await dashboard_server.initialize()
    except Exception as e:
        logger_manager.get_logger("FastAPI").error(f"Startup failed: {e}")
        raise


@app.get("/", response_class=HTMLResponse)
async def get_dashboard() -> HTMLResponse:
    """
    Serve the main dashboard page.
    
    Returns:
        HTMLResponse with the dashboard content
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
                dashboard_server.logger.error(f"Error reading template: {file_error}")
        
        # Return enhanced basic dashboard with watchlist
        return HTMLResponse(content=get_enhanced_dashboard_html())
        
    except Exception as e:
        dashboard_server.logger.error(f"Dashboard page error: {e}")
        return HTMLResponse(
            content=f"<h1>Dashboard Error</h1><p>Error: {e}</p>", 
            status_code=500
        )


@app.get("/api/stats")
async def get_stats() -> dict:
    """
    Get current system statistics.
    
    Returns:
        Dictionary containing system statistics
    """
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
async def get_opportunities() -> List[OpportunityResponse]:
    """
    Get current trading opportunities from the queue.
    
    Returns:
        List of OpportunityResponse objects with recent opportunities
        
    Raises:
        HTTPException: If there's an error retrieving opportunities
    """
    try:
        opportunities = []
        
        # Get last 20 opportunities from queue
        recent_opportunities = list(dashboard_server.opportunities_queue)[-20:]
        
        for opp in recent_opportunities:
            try:
                # Calculate age in minutes
                age_minutes = int((datetime.now() - opp.detected_at).total_seconds() / 60)
                
                # Extract recommendation safely
                recommendation = opp.metadata.get("recommendation", {})
                
                # Create response object with validation
                opportunity_response = OpportunityResponse(
                    token_symbol=opp.token.symbol or "UNKNOWN",
                    token_address=opp.token.address,
                    chain=opp.metadata.get("chain", "ethereum").lower(),
                    risk_level=opp.contract_analysis.risk_level.value if opp.contract_analysis else "unknown",
                    recommendation=recommendation.get("action", "UNKNOWN"),
                    confidence=recommendation.get("confidence", "UNKNOWN"),
                    score=float(recommendation.get("score", 0.0)),
                    liquidity_usd=float(opp.liquidity.liquidity_usd) if opp.liquidity else 0.0,
                    age_minutes=age_minutes
                )
                
                opportunities.append(opportunity_response)
                
            except Exception as e:
                dashboard_server.logger.warning(f"Skipping malformed opportunity: {e}")
                continue
        
        dashboard_server.logger.debug(f"Returning {len(opportunities)} opportunities")
        return opportunities
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting opportunities: {e}")
        # Return empty list instead of error to keep dashboard functional
        return []

# Watchlist API endpoints
@app.get("/api/watchlist")
async def get_watchlist(status: Optional[str] = None) -> dict:
    """
    Get watchlist items, optionally filtered by status.
    
    Args:
        status: Optional status filter
        
    Returns:
        Dictionary containing watchlist items
    """
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
async def add_to_watchlist(request: WatchlistAddRequest) -> dict:
    """
    Add a token to the watchlist.
    
    Args:
        request: Watchlist addition request
        
    Returns:
        Dictionary with success status and message
    """
    try:
        success = await dashboard_server.add_token_to_watchlist(request)
        
        if success:
            return {"success": True, "message": "Added to watchlist"}
        else:
            return {"success": False, "message": "Token already in watchlist"}
        
    except Exception as e:
        dashboard_server.logger.error(f"Error adding to watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/watchlist/remove")
async def remove_from_watchlist(token_address: str, chain: str) -> dict:
    """
    Remove a token from the watchlist.
    
    Args:
        token_address: Token contract address
        chain: Blockchain name
        
    Returns:
        Dictionary with success status and message
    """
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
async def get_watchlist_stats() -> dict:
    """
    Get watchlist statistics.
    
    Returns:
        Dictionary containing watchlist statistics
    """
    try:
        stats = watchlist_manager.get_stats()
        return stats
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting watchlist stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time updates.
    
    Args:
        websocket: The WebSocket connection
    """
    await dashboard_server.handle_websocket_connection(websocket)


# Fix for api/dashboard_server.py - replace the problematic sections

@app.get("/api/trades")
async def get_trade_history() -> dict:
    """
    Get recent trade history.
    
    Returns:
        Dictionary containing trade history
    """
    try:
        trades = []
        
        # Try to get trades from position manager
        if (dashboard_server.position_manager and 
            hasattr(dashboard_server.position_manager, 'closed_positions')):
            
            try:
                # Fix: Use list() to convert to list first, then slice
                closed_positions = dashboard_server.position_manager.closed_positions
                if hasattr(closed_positions, 'values'):
                    # It's a dict, get values
                    positions_list = list(closed_positions.values())
                else:
                    # It's already a list
                    positions_list = list(closed_positions)
                
                # Now safely slice the last 20
                recent_positions = positions_list[-20:] if len(positions_list) > 20 else positions_list
                
                for exit in recent_positions:
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
                        dashboard_server.logger.debug(f"Error processing individual trade: {trade_error}")
                        continue
            except Exception as position_error:
                dashboard_server.logger.error(f"Error accessing position manager data: {position_error}")
        
        return {"trades": trades, "status": "success"}
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting trade history: {e}")
        return {"trades": [], "error": str(e), "status": "error"}


@app.get("/api/positions")
async def get_positions() -> dict:
    """
    Get current trading positions.
    
    Returns:
        Dictionary containing current positions
    """
    try:
        positions = []
        
        if (dashboard_server.position_manager and 
            hasattr(dashboard_server.position_manager, 'active_positions')):
            
            try:
                # Fix: Safely iterate through active positions
                active_positions = dashboard_server.position_manager.active_positions
                if hasattr(active_positions, 'items'):
                    for position_id, position in active_positions.items():
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
                            dashboard_server.logger.debug(f"Error processing position {position_id}: {pos_error}")
                            continue
            except Exception as positions_error:
                dashboard_server.logger.error(f"Error accessing active positions: {positions_error}")
        
        return {"positions": positions, "status": "success"}
        
    except Exception as e:
        dashboard_server.logger.error(f"Error getting positions: {e}")
        return {"positions": [], "error": str(e), "status": "error"}















@app.post("/api/trade")
async def execute_trade(trade_request: TradeRequest) -> dict:
    """
    Execute a manual trade.
    
    Args:
        trade_request: The trade request parameters
        
    Returns:
        Dictionary containing trade execution result
    """
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
async def get_system_status() -> dict:
    """
    Get detailed system status.
    
    Returns:
        Dictionary containing detailed system status
    """
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
async def export_data() -> dict:
    """
    Export trading data for analysis.
    
    Returns:
        Dictionary containing exported data
    """
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