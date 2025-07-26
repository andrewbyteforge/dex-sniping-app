#!/usr/bin/env python3
"""
Core dashboard server class with WebSocket handling and business logic.
Contains the main DashboardServer class and core functionality.

File: api/dashboard_core.py
Class: DashboardServer
Methods: WebSocket management, opportunity handling, system integration

UPDATE: Added missing stop/shutdown methods to fix shutdown errors
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
    
    Features:
    - WebSocket connection management
    - Real-time opportunity broadcasting
    - Trading system integration
    - Client state management
    - Graceful shutdown support
    """
    
    def __init__(self) -> None:
        """Initialize the dashboard server."""
        self.logger = logger_manager.get_logger("DashboardServer")
        self.trading_executor = None
        self.position_manager = None
        self.risk_manager = None
        self.connected_clients: List[WebSocket] = []
        self.opportunities_queue: List[TradingOpportunity] = []
        
        # Server state
        self.is_running = False
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.stats = {
            "total_opportunities": 0,
            "high_confidence": 0,
            "active_chains": 3,
            "analysis_rate": 0,
            "uptime_start": datetime.now(),
            "connected_clients": 0
        }
        
    async def initialize(self, trading_system=None) -> None:
        """
        Initialize the dashboard server.
        
        Args:
            trading_system: Optional reference to trading system
            
        Raises:
            Exception: If initialization fails
        """
        try:
            self.logger.info("Initializing dashboard server...")
            
            # Store trading system reference if provided
            if trading_system:
                self.trading_executor = getattr(trading_system, 'trading_executor', None)
                self.position_manager = getattr(trading_system, 'position_manager', None)
                self.risk_manager = getattr(trading_system, 'risk_manager', None)
            
            # Start server
            self.is_running = True
            
            # Start periodic cleanup task
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup_task())
            
            self.logger.info("✅ Dashboard server initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize dashboard server: {e}")
            raise

    async def stop(self) -> None:
        """
        Stop the dashboard server gracefully.
        
        Closes all WebSocket connections and cleans up resources.
        """
        try:
            self.logger.info("🛑 Stopping dashboard server...")
            
            # Set running flag to false
            self.is_running = False
            
            # Cancel cleanup task
            if self.cleanup_task and not self.cleanup_task.done():
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Close all WebSocket connections
            await self._close_all_connections()
            
            # Clear data structures
            self.opportunities_queue.clear()
            
            self.logger.info("✅ Dashboard server stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping dashboard server: {e}")

    async def shutdown(self) -> None:
        """
        Shutdown the dashboard server (alias for stop).
        
        Provides compatibility for different shutdown method names.
        """
        await self.stop()

    async def _close_all_connections(self) -> None:
        """
        Close all WebSocket connections gracefully.
        
        Sends disconnect notification and closes connections.
        """
        try:
            if not self.connected_clients:
                return
            
            self.logger.info(f"Closing {len(self.connected_clients)} WebSocket connections...")
            
            # Send shutdown notification to all clients
            shutdown_message = {
                "type": "system_status",
                "status": "shutting_down",
                "message": "Server is shutting down",
                "timestamp": datetime.now().isoformat()
            }
            
            # Try to notify clients gracefully
            disconnect_tasks = []
            for client in self.connected_clients.copy():
                try:
                    # Send shutdown message
                    await asyncio.wait_for(
                        client.send_text(json.dumps(shutdown_message)),
                        timeout=1.0
                    )
                    
                    # Close connection
                    disconnect_tasks.append(self._close_client_connection(client))
                    
                except Exception as e:
                    self.logger.debug(f"Error notifying client during shutdown: {e}")
                    # Force close if notification fails
                    disconnect_tasks.append(self._close_client_connection(client))
            
            # Wait for all disconnections (with timeout)
            if disconnect_tasks:
                await asyncio.gather(*disconnect_tasks, return_exceptions=True)
            
            # Clear the client list
            self.connected_clients.clear()
            
            self.logger.info("✅ All WebSocket connections closed")
            
        except Exception as e:
            self.logger.error(f"Error closing WebSocket connections: {e}")
            # Force clear the list
            self.connected_clients.clear()

    async def _close_client_connection(self, client: WebSocket) -> None:
        """
        Close a single client connection safely.
        
        Args:
            client: WebSocket client to close
        """
        try:
            # Try to close the connection gracefully
            await asyncio.wait_for(client.close(), timeout=2.0)
        except Exception as e:
            self.logger.debug(f"Error closing client connection: {e}")
        finally:
            # Remove from client list if still present
            if client in self.connected_clients:
                self.connected_clients.remove(client)

    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        """
        Broadcast message to all connected WebSocket clients.
        
        Args:
            message: Message dictionary to broadcast
        """
        if not self.connected_clients or not self.is_running:
            return
        
        try:
            # Update client count in stats
            self.stats["connected_clients"] = len(self.connected_clients)
            
            # Add timestamp if not present
            if "timestamp" not in message:
                message["timestamp"] = datetime.now().isoformat()
            
            # Convert to JSON
            json_message = json.dumps(message)
            
            # Send to all clients (with error handling)
            failed_clients = []
            for client in self.connected_clients.copy():
                try:
                    await asyncio.wait_for(
                        client.send_text(json_message),
                        timeout=1.0
                    )
                except Exception as e:
                    self.logger.debug(f"Failed to send message to client: {e}")
                    failed_clients.append(client)
            
            # Remove failed clients
            for client in failed_clients:
                if client in self.connected_clients:
                    self.connected_clients.remove(client)
            
            if failed_clients:
                self.logger.debug(f"Removed {len(failed_clients)} disconnected clients")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting message: {e}")

    async def handle_websocket_connection(self, websocket: WebSocket) -> None:
        """
        Handle a WebSocket connection lifecycle.
        
        Args:
            websocket: WebSocket connection to handle
        """
        try:
            # Accept the connection
            await websocket.accept()
            self.connected_clients.append(websocket)
            
            client_count = len(self.connected_clients)
            self.logger.info(f"✅ WebSocket client connected (total: {client_count})")
            
            # Send welcome message with current stats
            welcome_message = {
                "type": "connection_established",
                "message": "Connected to DEX Trading Dashboard",
                "stats": self.stats.copy(),
                "server_status": "running" if self.is_running else "stopping"
            }
            await websocket.send_text(json.dumps(welcome_message))
            
            # Send recent opportunities if any
            if self.opportunities_queue:
                recent_opportunities = self.opportunities_queue[-10:]  # Last 10
                for opportunity in recent_opportunities:
                    await self._send_opportunity_to_client(websocket, opportunity)
            
            # Handle incoming messages
            await self._handle_client_messages(websocket)
            
        except WebSocketDisconnect:
            self.logger.debug("WebSocket client disconnected normally")
        except ConnectionResetError:
            self.logger.debug("WebSocket connection reset by client")
        except Exception as e:
            self.logger.error(f"WebSocket connection error: {e}")
        finally:
            # Clean up connection
            if websocket in self.connected_clients:
                self.connected_clients.remove(websocket)
            
            remaining_clients = len(self.connected_clients)
            self.logger.debug(f"WebSocket cleanup complete (remaining: {remaining_clients})")

    async def _handle_client_messages(self, websocket: WebSocket) -> None:
        """
        Handle incoming messages from a WebSocket client.
        
        Args:
            websocket: WebSocket connection
        """
        try:
            while self.is_running and websocket in self.connected_clients:
                try:
                    # Receive message with timeout
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    
                    # Parse JSON
                    try:
                        data = json.loads(message)
                        await self._process_client_message(websocket, data)
                    except json.JSONDecodeError as json_error:
                        self.logger.warning(f"Invalid JSON from client: {json_error}")
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Invalid JSON format"
                        }))
                        
                except asyncio.TimeoutError:
                    # Send heartbeat on timeout
                    await websocket.send_text(json.dumps({"type": "heartbeat"}))
                    
                except WebSocketDisconnect:
                    self.logger.debug("Client disconnected during message handling")
                    break
                    
                except Exception as e:
                    self.logger.error(f"Error handling client message: {e}")
                    break
                    
        except Exception as e:
            self.logger.error(f"Error in client message handler: {e}")

    async def _process_client_message(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """
        Process a message from a WebSocket client.
        
        Args:
            websocket: WebSocket connection
            data: Parsed message data
        """
        try:
            message_type = data.get("type", "unknown")
            
            if message_type == "get_stats":
                # Send current statistics
                await websocket.send_text(json.dumps({
                    "type": "stats_response",
                    "stats": self.stats.copy()
                }))
                
            elif message_type == "get_opportunities":
                # Send recent opportunities
                recent_count = data.get("count", 10)
                recent_opportunities = self.opportunities_queue[-recent_count:]
                
                for opportunity in recent_opportunities:
                    await self._send_opportunity_to_client(websocket, opportunity)
                    
            elif message_type == "heartbeat":
                # Respond to heartbeat
                await websocket.send_text(json.dumps({"type": "heartbeat_response"}))
                
            else:
                self.logger.debug(f"Unknown message type from client: {message_type}")
                
        except Exception as e:
            self.logger.error(f"Error processing client message: {e}")

    async def _send_opportunity_to_client(self, websocket: WebSocket, opportunity: TradingOpportunity) -> None:
        """
        Send an opportunity to a specific client.
        
        Args:
            websocket: WebSocket connection
            opportunity: Trading opportunity to send
        """
        try:
            message = {
                "type": "new_opportunity",
                "data": {
                    "symbol": opportunity.token_info.symbol,
                    "name": opportunity.token_info.name,
                    "address": opportunity.token_info.address,
                    "chain": opportunity.token_info.chain,
                    "confidence_score": float(opportunity.confidence_score),
                    "risk_level": opportunity.risk_level.value,
                    "detected_at": opportunity.detected_at.isoformat(),
                    "source": opportunity.source
                }
            }
            
            await websocket.send_text(json.dumps(message))
            
        except Exception as e:
            self.logger.error(f"Error sending opportunity to client: {e}")

    async def add_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Add a new trading opportunity and broadcast to clients.
        
        Args:
            opportunity: New trading opportunity
        """
        try:
            # Add to queue (keep last 100 opportunities)
            self.opportunities_queue.append(opportunity)
            if len(self.opportunities_queue) > 100:
                self.opportunities_queue.pop(0)
            
            # Update statistics
            self.stats["total_opportunities"] += 1
            if opportunity.confidence_score >= 80:
                self.stats["high_confidence"] += 1
            
            # Broadcast to all clients
            if self.connected_clients and self.is_running:
                message = {
                    "type": "new_opportunity",
                    "data": {
                        "symbol": opportunity.token_info.symbol,
                        "name": opportunity.token_info.name,
                        "address": opportunity.token_info.address,
                        "chain": opportunity.token_info.chain,
                        "confidence_score": float(opportunity.confidence_score),
                        "risk_level": opportunity.risk_level.value,
                        "detected_at": opportunity.detected_at.isoformat(),
                        "source": opportunity.source
                    }
                }
                
                await self.broadcast_message(message)
            
        except Exception as e:
            self.logger.error(f"Error adding opportunity: {e}")

    async def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Update dashboard metrics.
        
        Args:
            metrics: New metrics to update
        """
        try:
            # Update statistics
            self.stats.update(metrics)
            self.stats["connected_clients"] = len(self.connected_clients)
            
            # Broadcast metrics update to clients
            if self.connected_clients and self.is_running:
                await self.broadcast_message({
                    "type": "metrics_update",
                    "metrics": self.stats.copy()
                })
                
        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")

    async def _periodic_cleanup_task(self) -> None:
        """
        Periodic task to clean up dead WebSocket connections.
        
        Runs while the server is active and cleans up disconnected clients.
        """
        try:
            while self.is_running:
                try:
                    await asyncio.sleep(30)  # Clean up every 30 seconds
                    await self._cleanup_dead_connections()
                except Exception as e:
                    self.logger.error(f"Error in periodic cleanup: {e}")
                    await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.logger.debug("Periodic cleanup task cancelled")
    
    async def _cleanup_dead_connections(self) -> None:
        """
        Clean up dead WebSocket connections.
        
        Identifies and removes disconnected clients from the active list.
        """
        try:
            if not self.connected_clients:
                return
                
            dead_clients = []
            
            for client in self.connected_clients.copy():
                try:
                    # Test connection with a heartbeat
                    await asyncio.wait_for(
                        client.send_text(json.dumps({"type": "heartbeat"})),
                        timeout=1.0
                    )
                except Exception:
                    # If heartbeat fails, connection is dead
                    dead_clients.append(client)
            
            # Remove dead clients
            for client in dead_clients:
                if client in self.connected_clients:
                    self.connected_clients.remove(client)
            
            if dead_clients:
                self.logger.debug(f"Cleaned up {len(dead_clients)} dead connections")
                
        except Exception as e:
            self.logger.error(f"Error during connection cleanup: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current dashboard server status.
        
        Returns:
            Dictionary containing server status and statistics
        """
        return {
            "is_running": self.is_running,
            "connected_clients": len(self.connected_clients),
            "total_opportunities": self.stats["total_opportunities"],
            "high_confidence_opportunities": self.stats["high_confidence"],
            "uptime_start": self.stats["uptime_start"].isoformat(),
            "server_version": "2.0.0"
        }


# Global dashboard instance
dashboard_server = DashboardServer()