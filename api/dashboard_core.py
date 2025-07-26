#!/usr/bin/env python3
"""
Core dashboard server class with WebSocket handling and business logic.
Contains the main DashboardServer class and core functionality.

File: api/dashboard_core.py
Class: DashboardServer
Methods: WebSocket management, opportunity handling, system integration

UPDATE: Added missing dashboard_server instance to fix import errors
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from decimal import Decimal
from fastapi import WebSocket, WebSocketDisconnect

from models.token import TradingOpportunity, TokenInfo, LiquidityInfo, ContractAnalysis, SocialMetrics
from models.watchlist import watchlist_manager
from api.dashboard_models import WatchlistAddRequest
from utils.logger import logger_manager


class JSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles datetime and Decimal objects.
    """
    
    def default(self, obj: Any) -> Any:
        """
        Convert objects to JSON-serializable format.
        
        Args:
            obj: Object to serialize
            
        Returns:
            Any: JSON-serializable representation
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, '__dict__'):
            return self._clean_object_dict(obj.__dict__)
        else:
            return super().default(obj)
    
    def _clean_object_dict(self, obj_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean object dictionary for JSON serialization.
        
        Args:
            obj_dict: Object dictionary to clean
            
        Returns:
            Dict[str, Any]: Cleaned dictionary
        """
        cleaned = {}
        for key, value in obj_dict.items():
            if isinstance(value, datetime):
                cleaned[key] = value.isoformat()
            elif isinstance(value, Decimal):
                cleaned[key] = float(value)
            elif isinstance(value, (list, tuple)):
                cleaned[key] = [self._clean_value(item) for item in value]
            elif isinstance(value, dict):
                cleaned[key] = self._clean_object_dict(value)
            elif hasattr(value, '__dict__'):
                cleaned[key] = self._clean_object_dict(value.__dict__)
            else:
                cleaned[key] = value
        return cleaned
    
    def _clean_value(self, value: Any) -> Any:
        """
        Clean individual value for JSON serialization.
        
        Args:
            value: Value to clean
            
        Returns:
            Any: Cleaned value
        """
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, dict):
            return self._clean_object_dict(value)
        elif hasattr(value, '__dict__'):
            return self._clean_object_dict(value.__dict__)
        else:
            return value


class DashboardServer:
    """
    Core dashboard server that provides WebSocket connections and business logic
    for real-time communication with the trading system.
    
    Features:
    - WebSocket connection management with JSON serialization
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
        
        # Custom JSON encoder for WebSocket messages
        self.json_encoder = JSONEncoder()
        
        # Statistics
        self.stats = {
            "total_opportunities": 0,
            "high_confidence": 0,
            "active_chains": 3,
            "analysis_rate": 0,
            "uptime_start": datetime.now(),
            "connected_clients": 0
        }

    def _serialize_for_json(self, data: Any) -> Any:
        """
        Serialize data structure for JSON transmission.
        
        Args:
            data: Data to serialize
            
        Returns:
            Any: JSON-serializable data
        """
        try:
            if isinstance(data, datetime):
                return data.isoformat()
            elif isinstance(data, Decimal):
                return float(data)
            elif isinstance(data, dict):
                return {key: self._serialize_for_json(value) for key, value in data.items()}
            elif isinstance(data, (list, tuple)):
                return [self._serialize_for_json(item) for item in data]
            elif hasattr(data, '__dict__'):
                return self._serialize_for_json(data.__dict__)
            else:
                # Test if directly serializable
                json.dumps(data)
                return data
        except (TypeError, ValueError):
            # If not serializable, convert to string
            return str(data)

    async def add_opportunity(self, opportunity: TradingOpportunity) -> None:
        """
        Add a new opportunity to the dashboard and broadcast to clients.
        
        Args:
            opportunity: Trading opportunity to add
        """
        try:
            # Add to queue
            self.opportunities_queue.append(opportunity)
            
            # Keep queue size manageable
            if len(self.opportunities_queue) > 100:
                self.opportunities_queue.pop(0)
            
            # Update stats
            self.stats["total_opportunities"] += 1
            
            # Check confidence level
            if hasattr(opportunity, 'metadata') and isinstance(opportunity.metadata, dict):
                confidence = opportunity.metadata.get("recommendation", {}).get("confidence", "LOW")
                if confidence == "HIGH":
                    self.stats["high_confidence"] += 1
            
            # Broadcast to WebSocket clients
            opportunity_data = self._extract_opportunity_data_safe(opportunity)
            await self.broadcast_message({
                "type": "new_opportunity",
                "data": opportunity_data
            })
            
            self.logger.debug(f"Added opportunity to dashboard: {opportunity_data['token_symbol']}")
            
        except Exception as e:
            self.logger.error(f"Error adding opportunity to dashboard: {e}")

    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        """
        Broadcast message to all connected WebSocket clients with proper JSON serialization.
        
        Args:
            message: Message dictionary to broadcast
        """
        if not self.connected_clients or not self.is_running:
            return
        
        try:
            # Update client count in stats
            self.stats["connected_clients"] = len(self.connected_clients)
            
            # Add timestamp if not present and serialize it properly
            if "timestamp" not in message:
                message["timestamp"] = datetime.now().isoformat()
            elif isinstance(message["timestamp"], datetime):
                message["timestamp"] = message["timestamp"].isoformat()
            
            # Serialize the entire message for JSON compatibility
            serialized_message = self._serialize_for_json(message)
            
            # Convert to JSON string using custom encoder
            try:
                json_message = json.dumps(serialized_message, cls=JSONEncoder, ensure_ascii=False)
            except (TypeError, ValueError) as json_error:
                self.logger.error(f"JSON serialization failed: {json_error}")
                # Fallback: create simple error message
                fallback_message = {
                    "type": "error",
                    "message": "Failed to serialize message",
                    "timestamp": datetime.now().isoformat()
                }
                json_message = json.dumps(fallback_message)
            
            # Send to all clients (with error handling)
            failed_clients = []
            successful_sends = 0
            
            for client in self.connected_clients.copy():
                try:
                    await asyncio.wait_for(
                        client.send_text(json_message),
                        timeout=2.0  # Increased timeout for large messages
                    )
                    successful_sends += 1
                except asyncio.TimeoutError:
                    self.logger.debug(f"Client send timeout")
                    failed_clients.append(client)
                except ConnectionResetError:
                    self.logger.debug(f"Client connection reset")
                    failed_clients.append(client)
                except Exception as e:
                    self.logger.debug(f"Failed to send message to client: {e}")
                    failed_clients.append(client)
            
            # Remove failed clients
            for client in failed_clients:
                if client in self.connected_clients:
                    self.connected_clients.remove(client)
            
            if failed_clients:
                self.logger.debug(f"Removed {len(failed_clients)} disconnected clients")
            
            if successful_sends > 0:
                self.logger.debug(f"Successfully broadcasted message to {successful_sends} clients")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting message: {e}")

    async def handle_websocket_connection(self, websocket: WebSocket) -> None:
        """
        Handle a WebSocket connection lifecycle with improved error handling.
        
        Args:
            websocket: WebSocket connection to handle
        """
        try:
            # Accept the connection
            await websocket.accept()
            self.connected_clients.append(websocket)
            
            client_count = len(self.connected_clients)
            self.logger.info(f"✅ WebSocket client connected (total: {client_count})")
            
            # Send welcome message with current stats (properly serialized)
            welcome_message = {
                "type": "connection_established",
                "message": "Connected to DEX Trading Dashboard",
                "stats": self._serialize_for_json(self.stats.copy()),
                "server_status": "running" if self.is_running else "stopping"
            }
            
            try:
                welcome_json = json.dumps(welcome_message, cls=JSONEncoder)
                await websocket.send_text(welcome_json)
            except Exception as welcome_error:
                self.logger.warning(f"Failed to send welcome message: {welcome_error}")
            
            # Send recent opportunities if any (with proper serialization)
            if self.opportunities_queue:
                try:
                    recent_opportunities = self.opportunities_queue[-10:]  # Last 10
                    for opportunity in recent_opportunities:
                        await self._send_opportunity_to_client_safe(websocket, opportunity)
                except Exception as opp_error:
                    self.logger.warning(f"Failed to send recent opportunities: {opp_error}")
            
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

    async def _send_opportunity_to_client_safe(self, websocket: WebSocket, opportunity: TradingOpportunity) -> None:
        """
        Safely send opportunity data to a specific WebSocket client.
        
        Args:
            websocket: WebSocket client connection
            opportunity: Trading opportunity to send
        """
        try:
            # Extract opportunity data safely
            opportunity_data = self._extract_opportunity_data_safe(opportunity)
            
            # Create message
            message = {
                "type": "new_opportunity",
                "data": opportunity_data
            }
            
            # Serialize and send
            json_message = json.dumps(message, cls=JSONEncoder)
            await asyncio.wait_for(websocket.send_text(json_message), timeout=2.0)
            
        except asyncio.TimeoutError:
            self.logger.debug("Timeout sending opportunity to client")
        except Exception as e:
            self.logger.debug(f"Failed to send opportunity to client: {e}")

    def _extract_opportunity_data_safe(self, opportunity: TradingOpportunity) -> Dict[str, Any]:
        """
        Safely extract opportunity data for transmission.
        
        Args:
            opportunity: Trading opportunity to extract data from
            
        Returns:
            Dict[str, Any]: Safe opportunity data
        """
        try:
            # Extract basic information with safety checks
            token_symbol = "UNKNOWN"
            token_address = ""
            
            if hasattr(opportunity, 'token') and opportunity.token:
                if hasattr(opportunity.token, 'symbol') and opportunity.token.symbol:
                    token_symbol = str(opportunity.token.symbol)
                if hasattr(opportunity.token, 'address') and opportunity.token.address:
                    token_address = str(opportunity.token.address)
            
            # Extract chain information
            chain = "unknown"
            if hasattr(opportunity, 'chain') and opportunity.chain:
                chain = str(opportunity.chain).lower()
            elif hasattr(opportunity, 'metadata') and isinstance(opportunity.metadata, dict):
                chain_value = opportunity.metadata.get('chain')
                if isinstance(chain_value, str):
                    chain = chain_value.lower()
            
            # Extract liquidity information
            liquidity_usd = 0.0
            if hasattr(opportunity, 'liquidity') and opportunity.liquidity:
                if hasattr(opportunity.liquidity, 'liquidity_usd'):
                    try:
                        liquidity_usd = float(opportunity.liquidity.liquidity_usd)
                    except (TypeError, ValueError):
                        liquidity_usd = 0.0
            
            # Extract metadata safely
            metadata = {}
            if hasattr(opportunity, 'metadata') and isinstance(opportunity.metadata, dict):
                metadata = opportunity.metadata
            
            # Extract timestamp
            detected_at = datetime.now().isoformat()
            if hasattr(opportunity, 'detected_at') and opportunity.detected_at:
                if isinstance(opportunity.detected_at, datetime):
                    detected_at = opportunity.detected_at.isoformat()
                elif isinstance(opportunity.detected_at, str):
                    detected_at = opportunity.detected_at
            
            # Build safe data structure
            return {
                "token_symbol": token_symbol,
                "token_address": token_address,
                "chain": chain,
                "risk_level": str(metadata.get("risk_level", "unknown")),
                "recommendation": str(metadata.get("recommendation", {}).get("action", "MONITOR")),
                "confidence": str(metadata.get("recommendation", {}).get("confidence", "LOW")),
                "score": float(metadata.get("trading_score", {}).get("overall_score", 0.0)),
                "liquidity_usd": liquidity_usd,
                "detected_at": detected_at,
                "age_minutes": 0
            }
            
        except Exception as e:
            self.logger.warning(f"Error extracting opportunity data: {e}")
            return {
                "token_symbol": "ERROR",
                "token_address": "",
                "chain": "unknown",
                "risk_level": "unknown",
                "recommendation": "MONITOR",
                "confidence": "LOW",
                "score": 0.0,
                "liquidity_usd": 0.0,
                "detected_at": datetime.now().isoformat(),
                "age_minutes": 0
            }

    async def _handle_client_messages(self, websocket: WebSocket) -> None:
        """
        Handle incoming messages from a WebSocket client with improved error handling.
        
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
                        error_response = {
                            "type": "error",
                            "message": "Invalid JSON format",
                            "timestamp": datetime.now().isoformat()
                        }
                        await websocket.send_text(json.dumps(error_response))
                        
                except asyncio.TimeoutError:
                    # Send heartbeat on timeout
                    try:
                        heartbeat = {
                            "type": "heartbeat",
                            "timestamp": datetime.now().isoformat()
                        }
                        await websocket.send_text(json.dumps(heartbeat))
                    except Exception as heartbeat_error:
                        self.logger.debug(f"Failed to send heartbeat: {heartbeat_error}")
                        break
                    
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
        Process a message from a WebSocket client with proper error handling.
        
        Args:
            websocket: WebSocket client connection
            data: Parsed message data
        """
        try:
            message_type = data.get("type", "unknown")
            
            if message_type == "subscribe":
                # Handle subscription request
                topics = data.get("topics", [])
                response = {
                    "type": "subscription_confirmed",
                    "topics": topics,
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send_text(json.dumps(response))
                
            elif message_type == "ping":
                # Handle ping request
                response = {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send_text(json.dumps(response))
                
            elif message_type == "request_stats":
                # Send current stats
                response = {
                    "type": "stats_update",
                    "data": self._serialize_for_json(self.stats),
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send_text(json.dumps(response, cls=JSONEncoder))
                
            else:
                # Unknown message type
                response = {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send_text(json.dumps(response))
                
        except Exception as e:
            self.logger.error(f"Error processing client message: {e}")
            try:
                error_response = {
                    "type": "error",
                    "message": "Failed to process message",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send_text(json.dumps(error_response))
            except:
                # If we can't even send an error response, the connection is probably dead
                pass

    async def initialize(self, trading_system=None) -> None:
        """
        Initialize the dashboard server with improved error handling.
        
        Args:
            trading_system: Reference to trading system
        """
        try:
            self.logger.info("🚀 Initializing Dashboard Server...")
            
            # Set references safely
            if trading_system:
                self.trading_executor = getattr(trading_system, 'trading_executor', None)
                self.position_manager = getattr(trading_system, 'position_manager', None) 
                self.risk_manager = getattr(trading_system, 'risk_manager', None)
            
            # Update server state
            self.is_running = True
            self.stats["uptime_start"] = datetime.now()
            
            self.logger.info("✅ Dashboard Server initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize dashboard server: {e}")
            raise

    async def stop(self) -> None:
        """
        Stop the dashboard server gracefully.
        """
        try:
            self.logger.info("🛑 Stopping Dashboard Server...")
            self.is_running = False
            
            # Close all WebSocket connections
            if self.connected_clients:
                close_tasks = []
                for client in self.connected_clients.copy():
                    try:
                        # Send closing message
                        closing_message = {
                            "type": "server_shutdown",
                            "message": "Server is shutting down",
                            "timestamp": datetime.now().isoformat()
                        }
                        await client.send_text(json.dumps(closing_message))
                        close_tasks.append(client.close())
                    except:
                        pass  # Ignore errors during shutdown
                
                # Wait for all connections to close
                if close_tasks:
                    await asyncio.gather(*close_tasks, return_exceptions=True)
                
                self.connected_clients.clear()
            
            # Cancel cleanup task if running
            if self.cleanup_task and not self.cleanup_task.done():
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            self.logger.info("✅ Dashboard Server stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping dashboard server: {e}")

    async def shutdown(self) -> None:
        """
        Alias for stop() method for backward compatibility.
        """
        await self.stop()


# Create global dashboard server instance
dashboard_server = DashboardServer()