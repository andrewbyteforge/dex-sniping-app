#!/usr/bin/env python3
"""
Direct Node Manager for optimized blockchain connections.
Manages high-performance node connections and load balancing with WebSocket compatibility.

This file replaces the existing infrastructure/node_manager.py to fix WebSocket import issues.

File: infrastructure/node_manager.py
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import time
import json
import os

from web3 import Web3
from web3.providers import HTTPProvider

# Handle WebSocket provider import compatibility across Web3.py versions
try:
    from web3.providers import WebsocketProvider
    WEBSOCKET_AVAILABLE = True
except ImportError:
    try:
        from web3.providers.websocket import WebsocketProvider
        WEBSOCKET_AVAILABLE = True
    except ImportError:
        try:
            from web3 import WebsocketProvider
            WEBSOCKET_AVAILABLE = True
        except ImportError:
            WEBSOCKET_AVAILABLE = False
            WebsocketProvider = None

from utils.logger import logger_manager


class NodeType(Enum):
    """Node connection types."""
    HTTP = "http"
    WEBSOCKET = "websocket"
    IPC = "ipc"


class ConnectionStatus(Enum):
    """Node connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    CONNECTING = "connecting"


@dataclass
class NodeMetrics:
    """
    Node performance metrics tracking.
    
    Attributes:
        latency_ms: Average latency in milliseconds
        success_rate: Success rate as decimal (0.0 to 1.0)
        total_requests: Total number of requests made
        failed_requests: Number of failed requests
        last_request_time: Timestamp of last request
        connection_uptime: How long connection has been active
        block_height: Latest block number seen
        sync_status: Whether node is synced
    """
    latency_ms: float = 0.0
    success_rate: float = 1.0
    total_requests: int = 0
    failed_requests: int = 0
    last_request_time: Optional[datetime] = None
    connection_uptime: timedelta = field(default_factory=lambda: timedelta())
    block_height: int = 0
    sync_status: bool = True

    def calculate_success_rate(self) -> float:
        """Calculate current success rate."""
        if self.total_requests == 0:
            return 1.0
        return (self.total_requests - self.failed_requests) / self.total_requests

    def update_metrics(self, success: bool, latency: float) -> None:
        """Update metrics with new request data."""
        self.total_requests += 1
        if not success:
            self.failed_requests += 1
        
        self.success_rate = self.calculate_success_rate()
        self.latency_ms = latency
        self.last_request_time = datetime.now()


@dataclass
class NodeConfig:
    """
    Node configuration settings.
    
    Attributes:
        name: Human-readable node name
        url: Node endpoint URL
        node_type: Type of connection (HTTP/WebSocket/IPC)
        chain_id: Blockchain chain ID
        priority: Node priority (higher number = higher priority)
        max_requests_per_second: Rate limiting
        timeout_seconds: Request timeout
        api_key: API key if required
        auth_header: Authorization header if required
        enabled: Whether this node is enabled
    """
    name: str
    url: str
    node_type: NodeType
    chain_id: int
    priority: int = 1  # Higher number = higher priority
    max_requests_per_second: int = 100
    timeout_seconds: int = 10
    api_key: Optional[str] = None
    auth_header: Optional[str] = None
    enabled: bool = True

    def __post_init__(self):
        """Post-initialization validation and compatibility fixes."""
        # Convert WebSocket URLs to HTTP if WebSocket not available
        if self.node_type == NodeType.WEBSOCKET and not WEBSOCKET_AVAILABLE:
            logger = logger_manager.get_logger("NodeConfig")
            logger.warning(f"WebSocket not available for node {self.name}, falling back to HTTP")
            self.node_type = NodeType.HTTP
            
            # Convert WebSocket URL to HTTP
            if self.url.startswith("ws://"):
                self.url = self.url.replace("ws://", "http://")
            elif self.url.startswith("wss://"):
                self.url = self.url.replace("wss://", "https://")


class DirectNodeManager:
    """
    High-performance node manager for direct blockchain connections.
    Provides load balancing, failover, and performance optimization with WebSocket compatibility.
    """
    
    def __init__(self) -> None:
        """Initialize direct node manager."""
        self.logger = logger_manager.get_logger("DirectNodeManager")
        self.initialized = False
        
        # Node configurations by chain
        self.node_configs: Dict[str, List[NodeConfig]] = {}
        
        # Active connections
        self.web3_connections: Dict[str, Web3] = {}
        self.websocket_connections: Dict[str, Any] = {}
        
        # Node metrics and health tracking
        self.node_metrics: Dict[str, NodeMetrics] = {}
        self.node_status: Dict[str, ConnectionStatus] = {}
        
        # Load balancing
        self.request_counts: Dict[str, int] = {}
        self.last_used_node: Dict[str, str] = {}
        
        # Performance optimization
        self.connection_pools: Dict[str, List[Web3]] = {}
        self.pool_size = 3  # Number of connections per node
        
        # Monitoring
        self.health_check_interval = 30  # seconds
        self.metrics_update_interval = 60  # seconds
        
        # Statistics
        self.manager_stats = {
            "total_requests": 0,
            "failed_requests": 0,
            "average_latency": 0.0,
            "uptime_start": datetime.now(),
            "node_switches": 0,
            "connections_established": 0,
            "connections_failed": 0
        }
        
        # WebSocket availability warning
        if not WEBSOCKET_AVAILABLE:
            self.logger.warning(
                "⚠️ WebSocket support not available in current Web3.py version. "
                "WebSocket nodes will fallback to HTTP. "
                "Consider upgrading: pip install web3[websockets]"
            )

    async def initialize(self) -> None:
        """Initialize the node manager."""
        try:
            self.logger.info("Initializing direct node manager...")
            
            # Load node configurations from environment
            await self._load_node_configurations()
            
            # Establish initial connections
            await self._establish_connections()
            
            # Start health monitoring
            asyncio.create_task(self._start_health_monitoring())
            
            # Start metrics collection
            asyncio.create_task(self._start_metrics_collection())
            
            self.initialized = True
            self.logger.info("✅ Direct node manager initialized")
            
            # Log connection summary
            self._log_connection_summary()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize node manager: {e}")
            raise

    async def _load_node_configurations(self) -> None:
        """Load node configurations from environment variables and defaults."""
        # Default node configurations for supported chains
        default_configs = {
            "ethereum": [
                NodeConfig(
                    name="ethereum_primary_http",
                    url="https://ethereum-rpc.publicnode.com",
                    node_type=NodeType.HTTP,
                    chain_id=1,
                    priority=3,
                    timeout_seconds=10
                ),
                NodeConfig(
                    name="ethereum_secondary_http", 
                    url="https://eth.llamarpc.com",
                    node_type=NodeType.HTTP,
                    chain_id=1,
                    priority=2,
                    timeout_seconds=15
                ),
                NodeConfig(
                    name="ethereum_backup_http",
                    url="https://rpc.ankr.com/eth",
                    node_type=NodeType.HTTP,
                    chain_id=1,
                    priority=1,
                    timeout_seconds=20
                )
            ],
            "base": [
                NodeConfig(
                    name="base_primary_http",
                    url="https://mainnet.base.org",
                    node_type=NodeType.HTTP,
                    chain_id=8453,
                    priority=3,
                    timeout_seconds=10
                ),
                NodeConfig(
                    name="base_secondary_http",
                    url="https://base-rpc.publicnode.com",
                    node_type=NodeType.HTTP,
                    chain_id=8453,
                    priority=2,
                    timeout_seconds=15
                )
            ],
            "bsc": [
                NodeConfig(
                    name="bsc_primary_http",
                    url="https://bsc-dataseed.binance.org",
                    node_type=NodeType.HTTP,
                    chain_id=56,
                    priority=3,
                    timeout_seconds=10
                ),
                NodeConfig(
                    name="bsc_secondary_http",
                    url="https://bsc-rpc.publicnode.com",
                    node_type=NodeType.HTTP,
                    chain_id=56,
                    priority=2,
                    timeout_seconds=15
                )
            ]
        }
        
        # Add WebSocket configurations if available
        if WEBSOCKET_AVAILABLE:
            websocket_configs = {
                "ethereum": [
                    NodeConfig(
                        name="ethereum_websocket",
                        url="wss://ethereum-rpc.publicnode.com",
                        node_type=NodeType.WEBSOCKET,
                        chain_id=1,
                        priority=5,  # Higher priority for WebSocket
                        timeout_seconds=30
                    )
                ],
                "base": [
                    NodeConfig(
                        name="base_websocket",
                        url="wss://base-rpc.publicnode.com",
                        node_type=NodeType.WEBSOCKET,
                        chain_id=8453,
                        priority=5,
                        timeout_seconds=30
                    )
                ]
            }
            
            # Merge WebSocket configs with default configs
            for chain, ws_configs in websocket_configs.items():
                if chain in default_configs:
                    default_configs[chain] = ws_configs + default_configs[chain]
                else:
                    default_configs[chain] = ws_configs
        
        self.node_configs = default_configs
        
        # Load custom configurations from environment
        self._load_custom_configs_from_env()
        
        total_configs = sum(len(configs) for configs in self.node_configs.values())
        self.logger.info(f"Loaded {total_configs} node configurations")

    def _load_custom_configs_from_env(self) -> None:
        """Load custom node configurations from environment variables."""
        # Check for custom RPC URLs in environment
        custom_configs = {}
        
        # Ethereum custom RPC
        if eth_rpc := os.getenv("ETHEREUM_RPC_URL"):
            custom_configs.setdefault("ethereum", []).append(
                NodeConfig(
                    name="ethereum_custom",
                    url=eth_rpc,
                    node_type=NodeType.WEBSOCKET if eth_rpc.startswith("ws") else NodeType.HTTP,
                    chain_id=1,
                    priority=10,  # Highest priority for custom
                    timeout_seconds=10
                )
            )
        
        # Base custom RPC
        if base_rpc := os.getenv("BASE_RPC_URL"):
            custom_configs.setdefault("base", []).append(
                NodeConfig(
                    name="base_custom",
                    url=base_rpc,
                    node_type=NodeType.WEBSOCKET if base_rpc.startswith("ws") else NodeType.HTTP,
                    chain_id=8453,
                    priority=10,
                    timeout_seconds=10
                )
            )
        
        # BSC custom RPC
        if bsc_rpc := os.getenv("BSC_RPC_URL"):
            custom_configs.setdefault("bsc", []).append(
                NodeConfig(
                    name="bsc_custom",
                    url=bsc_rpc,
                    node_type=NodeType.WEBSOCKET if bsc_rpc.startswith("ws") else NodeType.HTTP,
                    chain_id=56,
                    priority=10,
                    timeout_seconds=10
                )
            )
        
        # Merge custom configs (prepend for highest priority)
        for chain, custom_chain_configs in custom_configs.items():
            if chain in self.node_configs:
                self.node_configs[chain] = custom_chain_configs + self.node_configs[chain]
            else:
                self.node_configs[chain] = custom_chain_configs
        
        if custom_configs:
            custom_count = sum(len(configs) for configs in custom_configs.values())
            self.logger.info(f"Added {custom_count} custom node configurations from environment")

    async def _establish_connections(self) -> None:
        """Establish connections to all configured nodes."""
        connection_tasks = []
        
        for chain, configs in self.node_configs.items():
            for config in configs:
                if config.enabled:
                    task = asyncio.create_task(self._create_connection(config, chain))
                    connection_tasks.append(task)
        
        # Wait for all connection attempts
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        # Process results
        successful_connections = 0
        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                connection_key, web3 = result
                if web3:
                    self.web3_connections[connection_key] = web3
                    self.node_status[connection_key] = ConnectionStatus.CONNECTED
                    self.node_metrics[connection_key] = NodeMetrics()
                    successful_connections += 1
                    self.manager_stats["connections_established"] += 1
                else:
                    self.manager_stats["connections_failed"] += 1
            elif isinstance(result, Exception):
                self.logger.debug(f"Connection task failed: {result}")
                self.manager_stats["connections_failed"] += 1
        
        self.logger.info(f"Established {successful_connections} successful connections")

    async def _create_connection(self, config: NodeConfig, chain: str) -> Tuple[str, Optional[Web3]]:
        """
        Create a Web3 connection for a node configuration.
        
        Args:
            config: Node configuration
            chain: Chain name
            
        Returns:
            Tuple of (connection_key, web3_instance)
        """
        connection_key = f"{chain}_{config.name}"
        
        try:
            if config.node_type == NodeType.HTTP:
                # Create HTTP provider
                provider_kwargs = {
                    "request_kwargs": {
                        "timeout": config.timeout_seconds
                    }
                }
                
                if config.auth_header:
                    provider_kwargs["request_kwargs"]["headers"] = {
                        "Authorization": config.auth_header
                    }
                
                provider = HTTPProvider(config.url, **provider_kwargs)
                web3 = Web3(provider)
                
            elif config.node_type == NodeType.WEBSOCKET and WEBSOCKET_AVAILABLE:
                # Create WebSocket provider
                provider = WebsocketProvider(
                    config.url,
                    websocket_timeout=config.timeout_seconds
                )
                web3 = Web3(provider)
                
            else:
                if config.node_type == NodeType.WEBSOCKET:
                    self.logger.warning(f"WebSocket not available for {config.name}, skipping")
                else:
                    self.logger.warning(f"Unsupported node type: {config.node_type}")
                return connection_key, None
            
            # Test connection
            if web3.is_connected():
                # Test with a simple call
                try:
                    block_number = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: web3.eth.block_number
                    )
                    self.logger.info(f"✅ Connected to {config.name} ({chain}) - Block: {block_number}")
                    return connection_key, web3
                except Exception as e:
                    self.logger.warning(f"Connection test failed for {config.name}: {e}")
                    return connection_key, None
            else:
                self.logger.warning(f"Web3 not connected for {config.name}")
                return connection_key, None
                
        except Exception as e:
            self.logger.error(f"Failed to create connection for {config.name}: {e}")
            return connection_key, None

    async def get_web3_connection(self, chain: str) -> Optional[Web3]:
        """
        Get the best available Web3 connection for a chain.
        
        Args:
            chain: Chain identifier (ethereum, base, bsc, etc.)
            
        Returns:
            Web3 instance or None if no connection available
        """
        try:
            # Find all connections for the chain
            chain_connections = [
                (key, web3) for key, web3 in self.web3_connections.items()
                if key.startswith(f"{chain}_") and self.node_status.get(key) == ConnectionStatus.CONNECTED
            ]
            
            if not chain_connections:
                self.logger.warning(f"No active connections available for {chain}")
                return None
            
            # Sort by priority (from node configuration) and health
            def connection_score(conn_tuple):
                key, web3 = conn_tuple
                # Extract config name from key
                config_name = key.replace(f"{chain}_", "")
                
                # Find matching config for priority
                priority = 1
                for config in self.node_configs.get(chain, []):
                    if config.name == config_name:
                        priority = config.priority
                        break
                
                # Get metrics for health score
                metrics = self.node_metrics.get(key, NodeMetrics())
                health_score = metrics.success_rate * 100 - metrics.latency_ms / 10
                
                return (priority, health_score)
            
            # Return best connection
            best_connection = max(chain_connections, key=connection_score)
            return best_connection[1]
            
        except Exception as e:
            self.logger.error(f"Error getting Web3 connection for {chain}: {e}")
            return None

    async def _start_health_monitoring(self) -> None:
        """Start health monitoring loop."""
        async def health_monitor():
            while self.initialized:
                try:
                    await asyncio.sleep(self.health_check_interval)
                    await self._perform_health_checks()
                except Exception as e:
                    self.logger.error(f"Health monitoring error: {e}")
        
        asyncio.create_task(health_monitor())
        self.logger.debug("Health monitoring started")

    async def _start_metrics_collection(self) -> None:
        """Start metrics collection loop."""
        async def metrics_collector():
            while self.initialized:
                try:
                    await asyncio.sleep(self.metrics_update_interval)
                    self._update_manager_stats()
                except Exception as e:
                    self.logger.error(f"Metrics collection error: {e}")
        
        asyncio.create_task(metrics_collector())
        self.logger.debug("Metrics collection started")

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all connections."""
        check_tasks = []
        
        for connection_key, web3 in self.web3_connections.items():
            if self.node_status.get(connection_key) == ConnectionStatus.CONNECTED:
                task = asyncio.create_task(self._test_connection_health(connection_key, web3))
                check_tasks.append(task)
        
        if check_tasks:
            await asyncio.gather(*check_tasks, return_exceptions=True)

    async def _test_connection_health(self, connection_key: str, web3: Web3) -> None:
        """Test health of a single connection."""
        try:
            start_time = time.time()
            
            # Test basic connectivity
            block_number = await asyncio.get_event_loop().run_in_executor(
                None, lambda: web3.eth.block_number
            )
            
            latency = (time.time() - start_time) * 1000
            
            # Update metrics
            if connection_key in self.node_metrics:
                self.node_metrics[connection_key].update_metrics(True, latency)
                self.node_metrics[connection_key].block_height = block_number
            
            self.logger.debug(f"Health check passed for {connection_key}: {latency:.1f}ms")
            
        except Exception as e:
            # Update failure metrics
            if connection_key in self.node_metrics:
                self.node_metrics[connection_key].update_metrics(False, 0)
            
            self.node_status[connection_key] = ConnectionStatus.ERROR
            self.logger.warning(f"Health check failed for {connection_key}: {e}")

    def _update_manager_stats(self) -> None:
        """Update manager-level statistics."""
        # Calculate average latency across all connections
        total_latency = 0
        connected_count = 0
        
        for key, metrics in self.node_metrics.items():
            if self.node_status.get(key) == ConnectionStatus.CONNECTED:
                total_latency += metrics.latency_ms
                connected_count += 1
        
        self.manager_stats["average_latency"] = (
            total_latency / connected_count if connected_count > 0 else 0
        )

    def _log_connection_summary(self) -> None:
        """Log summary of established connections."""
        summary_lines = ["📊 NODE CONNECTION SUMMARY:"]
        
        for chain, configs in self.node_configs.items():
            connected_count = sum(
                1 for key in self.web3_connections.keys()
                if key.startswith(f"{chain}_") and self.node_status.get(key) == ConnectionStatus.CONNECTED
            )
            total_count = len(configs)
            
            summary_lines.append(f"   {chain.upper()}: {connected_count}/{total_count} connected")
            
            # List individual connections
            for config in configs:
                connection_key = f"{chain}_{config.name}"
                status = self.node_status.get(connection_key, ConnectionStatus.DISCONNECTED)
                status_emoji = "✅" if status == ConnectionStatus.CONNECTED else "❌"
                
                summary_lines.append(f"     {status_emoji} {config.name} ({config.node_type.value})")
        
        for line in summary_lines:
            self.logger.info(line)

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive connection statistics.
        
        Returns:
            Dictionary containing connection statistics
        """
        stats = {
            "total_nodes": len(self.web3_connections),
            "connected_nodes": sum(
                1 for status in self.node_status.values() 
                if status == ConnectionStatus.CONNECTED
            ),
            "chains": list(self.node_configs.keys()),
            "websocket_available": WEBSOCKET_AVAILABLE,
            "manager_stats": dict(self.manager_stats),
            "node_details": {}
        }
        
        for connection_key, metrics in self.node_metrics.items():
            stats["node_details"][connection_key] = {
                "status": self.node_status.get(connection_key, ConnectionStatus.DISCONNECTED).value,
                "latency_ms": metrics.latency_ms,
                "success_rate": metrics.success_rate,
                "total_requests": metrics.total_requests,
                "failed_requests": metrics.failed_requests,
                "block_height": metrics.block_height
            }
        
        return stats

    async def shutdown(self) -> None:
        """Shutdown all connections gracefully."""
        try:
            self.logger.info("Shutting down DirectNodeManager...")
            self.initialized = False
            
            # Close WebSocket connections if any
            for connection_key, web3 in self.web3_connections.items():
                try:
                    # For WebSocket connections, we might need special cleanup
                    if hasattr(web3.provider, 'disconnect'):
                        await web3.provider.disconnect()
                except Exception as e:
                    self.logger.debug(f"Error disconnecting {connection_key}: {e}")
            
            self.web3_connections.clear()
            self.node_status.clear()
            
            self.logger.info("✅ DirectNodeManager shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    def __str__(self) -> str:
        """String representation of the node manager."""
        connected = sum(1 for status in self.node_status.values() if status == ConnectionStatus.CONNECTED)
        total = len(self.node_status)
        return f"DirectNodeManager(connected={connected}/{total}, chains={list(self.node_configs.keys())})"