# api/dashboard_core.py
"""
Core dashboard server class with WebSocket handling and business logic.
Contains the main DashboardServer class and core functionality.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

from models.token import TradingOpportunity, TokenInfo, LiquidityInfo, ContractAnalysis, SocialMetrics
from models.watchlist import watchlist_manager
from api.dashboard_models import WatchlistAddRequest
from utils.logger import logger_manager


class DashboardServer:
    """
    Core dashboard server that provides WebSocket connections and business logic
    for real-time communication with the trading system.
    """
    
    def __init__(self) -> None:
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
            # Debug logging for new opportunities
            if message.get("type") == "new_opportunity":
                data = message.get("data", {})
                self.logger.debug(f"Broadcasting opportunity: {data.get('token_symbol')} - Liquidity: {data.get('liquidity_usd')} (type: {type(data.get('liquidity_usd'))})")
                
            message_str = json.dumps(message)
        except Exception as json_error:
            self.logger.error(f"Error serializing message: {json_error}")
            self.logger.error(f"Message content: {message}")
            return
        
        for client in self.connected_clients.copy():
            try:
                # Check if client is still connected using multiple methods
                client_disconnected = False
                
                # Method 1: Check client_state if available
                if hasattr(client, 'client_state'):
                    try:
                        # WebSocket states: 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
                        if client.client_state.value in [2, 3]:  # CLOSING or CLOSED
                            client_disconnected = True
                    except Exception:
                        # If we can't check state, assume client might be disconnected
                        client_disconnected = True
                
                # Method 2: Try to send the message
                if not client_disconnected:
                    try:
                        await client.send_text(message_str)
                    except Exception as send_error:
                        error_str = str(send_error).lower()
                        
                        # Check for specific disconnect indicators
                        disconnect_indicators = [
                            'disconnect', 'closed', 'connection', 'reset',
                            '1001', '1000', '1006',  # WebSocket close codes
                            'broken pipe', 'connection aborted'
                        ]
                        
                        if any(indicator in error_str for indicator in disconnect_indicators):
                            self.logger.debug(f"Client disconnected during broadcast: {send_error}")
                        else:
                            self.logger.warning(f"Error sending to client: {send_error}")
                        
                        client_disconnected = True
                
                if client_disconnected:
                    disconnected_clients.append(client)
                    
            except Exception as e:
                self.logger.warning(f"Error processing client during broadcast: {e}")
                disconnected_clients.append(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in self.connected_clients:
                self.connected_clients.remove(client)
                
        if disconnected_clients:
            self.logger.debug(f"Removed {len(disconnected_clients)} disconnected clients during broadcast")

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
                
            # Create safe opportunity data for broadcast with proper value extraction
            try:
                # Safely extract liquidity USD value
                liquidity_usd = 0.0
                if hasattr(opportunity.liquidity, 'liquidity_usd') and opportunity.liquidity.liquidity_usd:
                    liquidity_usd = float(opportunity.liquidity.liquidity_usd)
                
                # Safely extract DEX name
                dex_name = "Unknown DEX"
                if hasattr(opportunity.liquidity, 'dex_name') and opportunity.liquidity.dex_name:
                    dex_name = str(opportunity.liquidity.dex_name)
                
                # Safely extract pair address
                pair_address = ""
                if hasattr(opportunity.liquidity, 'pair_address') and opportunity.liquidity.pair_address:
                    pair_address = str(opportunity.liquidity.pair_address)
                
                # Safely extract block number
                block_number = None
                if hasattr(opportunity.liquidity, 'block_number') and opportunity.liquidity.block_number:
                    block_number = int(opportunity.liquidity.block_number)
                
                # Safely extract token information
                token_symbol = "UNKNOWN"
                if hasattr(opportunity.token, 'symbol') and opportunity.token.symbol:
                    token_symbol = str(opportunity.token.symbol)
                
                token_address = ""
                if hasattr(opportunity.token, 'address') and opportunity.token.address:
                    token_address = str(opportunity.token.address)
                
                token_name = None
                if hasattr(opportunity.token, 'name') and opportunity.token.name:
                    token_name = str(opportunity.token.name)
                
                # Safely extract analysis data
                risk_level = "unknown"
                if hasattr(opportunity.contract_analysis, 'risk_level') and opportunity.contract_analysis.risk_level:
                    risk_level = str(opportunity.contract_analysis.risk_level.value)
                
                opp_data = {
                    "token_symbol": token_symbol,
                    "token_address": token_address,
                    "token_name": token_name,
                    "chain": opportunity.metadata.get("chain", "ethereum"),
                    "risk_level": risk_level,
                    "recommendation": recommendation.get("action", "UNKNOWN"),
                    "confidence": recommendation.get("confidence", "UNKNOWN"),
                    "score": float(recommendation.get("score", 0.0)),
                    "liquidity_usd": liquidity_usd,
                    "dex_name": dex_name,
                    "pair_address": pair_address,
                    "block_number": block_number,
                    "detected_at": opportunity.detected_at.isoformat(),
                    "reasons": recommendation.get("reasons", []),
                    "warnings": recommendation.get("warnings", [])
                }
                
                # Add additional metadata if available
                if "market_cap_usd" in opportunity.metadata:
                    opp_data["market_cap_usd"] = float(opportunity.metadata["market_cap_usd"])
                
                if "volume_24h_usd" in opportunity.metadata:
                    opp_data["volume_24h_usd"] = float(opportunity.metadata["volume_24h_usd"])
                
                if "solana_source" in opportunity.metadata:
                    opp_data["solana_source"] = str(opportunity.metadata["solana_source"])
                
            except Exception as data_error:
                self.logger.error(f"Error creating opportunity data: {data_error}")
                # Fallback to minimal data
                opp_data = {
                    "token_symbol": getattr(opportunity.token, 'symbol', 'UNKNOWN') or 'UNKNOWN',
                    "token_address": getattr(opportunity.token, 'address', '') or '',
                    "chain": opportunity.metadata.get("chain", "ethereum"),
                    "risk_level": "unknown",
                    "recommendation": "UNKNOWN",
                    "confidence": "UNKNOWN", 
                    "score": 0.0,
                    "liquidity_usd": 0.0,
                    "dex_name": "Unknown DEX",
                    "pair_address": "",
                    "detected_at": opportunity.detected_at.isoformat(),
                    "reasons": [],
                    "warnings": []
                }
                
            # Broadcast to connected clients
            await self.broadcast_message({
                "type": "new_opportunity",
                "data": opp_data
            })
            
            self.logger.debug(f"Added opportunity: {token_symbol} (${liquidity_usd:,.2f} liquidity)")
            
        except Exception as e:
            self.logger.error(f"Error adding opportunity: {e}")
            # Log the opportunity structure for debugging
            try:
                self.logger.debug(f"Opportunity structure: token={type(opportunity.token)}, liquidity={type(opportunity.liquidity)}")
            except Exception:
                self.logger.debug("Could not log opportunity structure")

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

    async def add_token_to_watchlist(self, request: WatchlistAddRequest) -> bool:
        """
        Add a token to the watchlist with proper opportunity creation.
        
        Args:
            request: Watchlist addition request
            
        Returns:
            True if added successfully, False if already exists
        """
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
                await self.broadcast_message({
                    "type": "watchlist_updated",
                    "data": {
                        "action": "added",
                        "token_symbol": request.token_symbol,
                        "token_address": token_address
                    }
                })
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error adding to watchlist: {e}")
            raise

    async def handle_websocket_connection(self, websocket: WebSocket) -> None:
        """
        Handle a new WebSocket connection with comprehensive error handling.
        
        Args:
            websocket: The WebSocket connection to handle
        """
        await websocket.accept()
        self.connected_clients.append(websocket)
        self.logger.info(f"WebSocket client connected. Total: {len(self.connected_clients)}")
        
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
                        self.logger.debug("WebSocket ping failed - connection closed")
                        break
                        
                except json.JSONDecodeError as json_error:
                    self.logger.warning(f"Invalid JSON from WebSocket client: {json_error}")
                    try:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Invalid JSON format"
                        }))
                    except Exception:
                        # If we can't send error message, connection is dead
                        self.logger.debug("WebSocket error response failed - connection closed")
                        break
                        
                except Exception as message_error:
                    # Handle specific WebSocket close codes
                    error_str = str(message_error)
                    
                    # Check for WebSocket close codes
                    if "(1001," in error_str:
                        self.logger.debug("WebSocket client going away (1001) - tab closed/refreshed")
                        break
                    elif "(1000," in error_str:
                        self.logger.debug("WebSocket client closed normally (1000)")
                        break
                    elif "(1006," in error_str:
                        self.logger.debug("WebSocket connection closed abnormally (1006)")
                        break
                    
                    # Check for other disconnect-related errors
                    error_msg = error_str.lower()
                    disconnect_keywords = [
                        'disconnect', 'closed', 'connection', 'reset', 
                        'broken pipe', 'connection aborted', 'connection reset'
                    ]
                    
                    if any(keyword in error_msg for keyword in disconnect_keywords):
                        self.logger.debug(f"WebSocket connection terminated: {message_error}")
                        break
                    else:
                        self.logger.error(f"WebSocket message processing error: {message_error}")
                        # Continue the loop for non-disconnect errors
                    
        except WebSocketDisconnect as disconnect_error:
            # This is the normal FastAPI WebSocket disconnect exception
            self.logger.debug(f"WebSocket client disconnected normally: {disconnect_error}")
        except ConnectionResetError:
            self.logger.debug("WebSocket connection reset by client")
        except ConnectionAbortedError:
            self.logger.debug("WebSocket connection aborted")
        except Exception as e:
            # Log unexpected errors but don't let them crash the system
            error_str = str(e)
            if any(code in error_str for code in ['1001', '1000', '1006']):
                self.logger.debug(f"WebSocket closed with code: {e}")
            else:
                self.logger.warning(f"Unexpected WebSocket error: {e}")
        finally:
            # Always clean up the client connection
            if websocket in self.connected_clients:
                self.connected_clients.remove(websocket)
            self.logger.debug(f"WebSocket cleanup complete. Remaining clients: {len(self.connected_clients)}")
    
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
                    # Check multiple indicators of disconnected state
                    is_dead = False
                    
                    # Check client_state if available
                    if hasattr(client, 'client_state'):
                        try:
                            # WebSocket states: 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
                            if client.client_state.value in [2, 3]:  # CLOSING or CLOSED
                                is_dead = True
                        except Exception:
                            # If we can't read the state, consider it potentially dead
                            is_dead = True
                    
                    # Additional check: try to send a ping
                    if not is_dead:
                        try:
                            # Send a very small message to test connection
                            await asyncio.wait_for(
                                client.send_text(json.dumps({"type": "heartbeat"})), 
                                timeout=1.0
                            )
                        except Exception:
                            # If ping fails, connection is dead
                            is_dead = True
                    
                    if is_dead:
                        dead_clients.append(client)
                        
                except Exception as check_error:
                    # If we can't check the client, assume it's dead
                    self.logger.debug(f"Error checking client state: {check_error}")
                    dead_clients.append(client)
            
            # Remove dead clients
            for client in dead_clients:
                if client in self.connected_clients:
                    self.connected_clients.remove(client)
            
            if dead_clients:
                self.logger.debug(f"Cleaned up {len(dead_clients)} dead connections")
                
        except Exception as e:
            self.logger.error(f"Error during connection cleanup: {e}")


# Global dashboard instance
dashboard_server = DashboardServer()