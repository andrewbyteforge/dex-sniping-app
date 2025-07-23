"""
Direct node connection manager for ultra-fast blockchain access.
Manages WebSocket connections, node failover, and latency optimization.
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import websockets
from web3 import Web3
from web3.providers import WebsocketProvider, HTTPProvider
from web3.types import BlockData, TxData

from utils.logger import logger_manager


class NodeType(Enum):
    """Type of node connection."""
    WEBSOCKET = "websocket"
    HTTP = "http"
    IPC = "ipc"


class NodeStatus(Enum):
    """Status of a node connection."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SYNCING = "syncing"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass
class NodeConfig:
    """
    Configuration for a node connection.
    
    Attributes:
        url: Node endpoint URL
        chain: Blockchain name
        node_type: Type of connection
        priority: Priority level (lower is higher priority)
        max_requests_per_second: Rate limit
        timeout: Request timeout in seconds
        is_archive: Whether this is an archive node
        supports_trace: Whether node supports trace methods
        supports_debug: Whether node supports debug methods
        metadata: Additional node metadata
    """
    url: str
    chain: str
    node_type: NodeType
    priority: int = 10
    max_requests_per_second: int = 100
    timeout: int = 30
    is_archive: bool = False
    supports_trace: bool = False
    supports_debug: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeConnection:
    """
    Active node connection with performance tracking.
    
    Attributes:
        config: Node configuration
        web3: Web3 instance
        status: Current connection status
        connected_at: Connection timestamp
        last_block: Last block number seen
        latency_ms: Current latency in milliseconds
        request_count: Total requests made
        error_count: Total errors encountered
        last_error: Last error message
        websocket: WebSocket connection if applicable
    """
    config: NodeConfig
    web3: Web3
    status: NodeStatus = NodeStatus.DISCONNECTED
    connected_at: Optional[datetime] = None
    last_block: int = 0
    latency_ms: float = 0.0
    request_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    websocket: Optional[websockets.WebSocketClientProtocol] = None
    
    def get_health_score(self) -> float:
        """
        Calculate node health score (0-100).
        
        Returns:
            Health score based on latency, errors, and uptime
        """
        if self.status != NodeStatus.CONNECTED:
            return 0.0
        
        # Base score
        score = 100.0
        
        # Deduct for latency (target < 50ms)
        if self.latency_ms > 200:
            score -= 40
        elif self.latency_ms > 100:
            score -= 20
        elif self.latency_ms > 50:
            score -= 10
        
        # Deduct for errors
        if self.request_count > 0:
            error_rate = self.error_count / self.request_count
            score -= min(30, error_rate * 100)
        
        # Bonus for uptime
        if self.connected_at:
            uptime = (datetime.now() - self.connected_at).total_seconds()
            if uptime > 3600:  # 1 hour
                score += 10
        
        return max(0, min(100, score))


class DirectNodeManager:
    """
    Manages direct node connections for ultra-fast blockchain access.
    Provides WebSocket connections, automatic failover, and latency optimization.
    """
    
    def __init__(self):
        """Initialize the direct node manager."""
        self.logger = logger_manager.get_logger("DirectNodeManager")
        
        # Node configurations by chain
        self.node_configs: Dict[str, List[NodeConfig]] = {
            'ethereum': [],
            'base': [],
            'bsc': [],
            'arbitrum': [],
            'polygon': []
        }
        
        # Active connections
        self.connections: Dict[str, List[NodeConnection]] = {}
        self.primary_connections: Dict[str, NodeConnection] = {}
        
        # WebSocket subscriptions
        self.subscriptions: Dict[str, List[Callable]] = {
            'newBlocks': [],
            'pendingTransactions': [],
            'logs': []
        }
        
        # Performance tracking
        self.latency_history: Dict[str, List[float]] = {}
        self.block_times: Dict[str, float] = {}
        
        # Monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        self.health_check_interval = 30  # seconds
        
    async def initialize(self) -> None:
        """
        Initialize node connections and start monitoring.
        """
        try:
            self.logger.info("Initializing Direct Node Manager...")
            
            # Load node configurations
            self._load_node_configs()
            
            # Connect to all configured nodes
            await self._connect_all_nodes()
            
            # Select primary nodes
            self._select_primary_nodes()
            
            # Start monitoring
            self.monitoring_task = asyncio.create_task(self._monitor_connections())
            
            self.logger.info(
                f"✅ Direct Node Manager initialized with "
                f"{sum(len(conns) for conns in self.connections.values())} connections"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Direct Node Manager: {e}")
            raise
    
    def _load_node_configs(self) -> None:
        """Load node configurations from environment and defaults."""
        import os
        
        # Default public nodes (as fallback)
        default_nodes = {
            'ethereum': [
                NodeConfig(
                    url="wss://ethereum-rpc.publicnode.com",
                    chain="ethereum",
                    node_type=NodeType.WEBSOCKET,
                    priority=20
                ),
                NodeConfig(
                    url="https://rpc.ankr.com/eth",
                    chain="ethereum",
                    node_type=NodeType.HTTP,
                    priority=30
                )
            ],
            'base': [
                NodeConfig(
                    url="wss://base-rpc.publicnode.com",
                    chain="base",
                    node_type=NodeType.WEBSOCKET,
                    priority=20
                ),
                NodeConfig(
                    url="https://mainnet.base.org",
                    chain="base",
                    node_type=NodeType.HTTP,
                    priority=30
                )
            ],
            'bsc': [
                NodeConfig(
                    url="wss://bsc-rpc.publicnode.com",
                    chain="bsc",
                    node_type=NodeType.WEBSOCKET,
                    priority=20
                ),
                NodeConfig(
                    url="https://bsc-dataseed.binance.org",
                    chain="bsc",
                    node_type=NodeType.HTTP,
                    priority=30
                )
            ]
        }
        
        # Load premium nodes from environment
        for chain in self.node_configs.keys():
            # Check for premium WebSocket nodes
            ws_url = os.getenv(f"{chain.upper()}_WS_URL")
            if ws_url:
                self.node_configs[chain].append(
                    NodeConfig(
                        url=ws_url,
                        chain=chain,
                        node_type=NodeType.WEBSOCKET,
                        priority=1,  # Highest priority
                        is_archive=True,
                        supports_trace=True
                    )
                )
            
            # Check for premium HTTP nodes
            for i in range(1, 4):  # Support up to 3 premium nodes
                http_url = os.getenv(f"{chain.upper()}_NODE_URL_{i}")
                if http_url:
                    self.node_configs[chain].append(
                        NodeConfig(
                            url=http_url,
                            chain=chain,
                            node_type=NodeType.HTTP,
                            priority=5 + i,
                            is_archive=True
                        )
                    )
        
        # Add default nodes as fallback
        for chain, configs in default_nodes.items():
            if chain in self.node_configs:
                self.node_configs[chain].extend(configs)
        
        # Sort by priority
        for chain in self.node_configs:
            self.node_configs[chain].sort(key=lambda x: x.priority)
    
    async def _connect_all_nodes(self) -> None:
        """Connect to all configured nodes."""
        for chain, configs in self.node_configs.items():
            self.connections[chain] = []
            
            for config in configs:
                try:
                    connection = await self._connect_node(config)
                    if connection:
                        self.connections[chain].append(connection)
                        self.logger.info(
                            f"✅ Connected to {config.node_type.value} node "
                            f"for {chain} (priority: {config.priority})"
                        )
                except Exception as e:
                    self.logger.error(
                        f"Failed to connect to {config.url}: {e}"
                    )
    
    async def _connect_node(self, config: NodeConfig) -> Optional[NodeConnection]:
        """
        Connect to a single node.
        
        Args:
            config: Node configuration
            
        Returns:
            NodeConnection if successful, None otherwise
        """
        try:
            start_time = time.time()
            
            if config.node_type == NodeType.WEBSOCKET:
                # WebSocket connection
                provider = WebsocketProvider(
                    config.url,
                    websocket_timeout=config.timeout
                )
                web3 = Web3(provider)
                
                # Test WebSocket subscription
                ws = await websockets.connect(config.url)
                
            else:
                # HTTP connection
                provider = HTTPProvider(
                    config.url,
                    request_kwargs={'timeout': config.timeout}
                )
                web3 = Web3(provider)
                ws = None
            
            # Test connection
            if not web3.is_connected():
                raise Exception("Web3 not connected")
            
            # Get latest block to test
            latest_block = web3.eth.block_number
            latency = (time.time() - start_time) * 1000
            
            connection = NodeConnection(
                config=config,
                web3=web3,
                status=NodeStatus.CONNECTED,
                connected_at=datetime.now(),
                last_block=latest_block,
                latency_ms=latency,
                websocket=ws
            )
            
            # Setup WebSocket subscriptions if applicable
            if ws and config.node_type == NodeType.WEBSOCKET:
                asyncio.create_task(
                    self._handle_websocket_messages(connection)
                )
            
            return connection
            
        except Exception as e:
            self.logger.error(f"Node connection failed: {e}")
            return None
    
    def _select_primary_nodes(self) -> None:
        """Select primary node for each chain based on health scores."""
        for chain, connections in self.connections.items():
            if connections:
                # Sort by health score
                connections.sort(
                    key=lambda x: x.get_health_score(), 
                    reverse=True
                )
                self.primary_connections[chain] = connections[0]
                self.logger.info(
                    f"Selected primary node for {chain}: "
                    f"{connections[0].config.url} "
                    f"(health: {connections[0].get_health_score():.1f})"
                )
    
    async def get_web3_connection(
        self, 
        chain: str,
        require_archive: bool = False,
        require_trace: bool = False
    ) -> Optional[Web3]:
        """
        Get best Web3 connection for chain.
        
        Args:
            chain: Blockchain name
            require_archive: Whether archive node is required
            require_trace: Whether trace support is required
            
        Returns:
            Web3 instance or None
        """
        if chain not in self.connections:
            return None
        
        # Filter connections based on requirements
        suitable_connections = [
            conn for conn in self.connections[chain]
            if conn.status == NodeStatus.CONNECTED
            and (not require_archive or conn.config.is_archive)
            and (not require_trace or conn.config.supports_trace)
        ]
        
        if not suitable_connections:
            return None
        
        # Return best connection
        suitable_connections.sort(
            key=lambda x: x.get_health_score(),
            reverse=True
        )
        
        return suitable_connections[0].web3
    
    async def subscribe_to_new_blocks(
        self,
        chain: str,
        callback: Callable[[BlockData], None]
    ) -> bool:
        """
        Subscribe to new block events.
        
        Args:
            chain: Blockchain to subscribe to
            callback: Function to call with new blocks
            
        Returns:
            Success status
        """
        connection = self.primary_connections.get(chain)
        if not connection or connection.config.node_type != NodeType.WEBSOCKET:
            return False
        
        self.subscriptions['newBlocks'].append(callback)
        
        # Send subscription request
        if connection.websocket:
            await connection.websocket.send(json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": ["newHeads"]
            }))
        
        return True
    
    async def subscribe_to_pending_transactions(
        self,
        chain: str,
        callback: Callable[[str], None]
    ) -> bool:
        """
        Subscribe to pending transactions.
        
        Args:
            chain: Blockchain to subscribe to
            callback: Function to call with transaction hashes
            
        Returns:
            Success status
        """
        connection = self.primary_connections.get(chain)
        if not connection or connection.config.node_type != NodeType.WEBSOCKET:
            return False
        
        self.subscriptions['pendingTransactions'].append(callback)
        
        # Send subscription request
        if connection.websocket:
            await connection.websocket.send(json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "eth_subscribe",
                "params": ["newPendingTransactions"]
            }))
        
        return True
    
    async def _handle_websocket_messages(self, connection: NodeConnection) -> None:
        """Handle incoming WebSocket messages."""
        if not connection.websocket:
            return
        
        try:
            async for message in connection.websocket:
                data = json.loads(message)
                
                # Handle subscription notifications
                if data.get('method') == 'eth_subscription':
                    params = data.get('params', {})
                    subscription = params.get('subscription')
                    result = params.get('result')
                    
                    # New block
                    if subscription and result and 'number' in result:
                        for callback in self.subscriptions['newBlocks']:
                            asyncio.create_task(callback(result))
                    
                    # Pending transaction
                    elif subscription and isinstance(result, str):
                        for callback in self.subscriptions['pendingTransactions']:
                            asyncio.create_task(callback(result))
                
        except Exception as e:
            self.logger.error(f"WebSocket handler error: {e}")
            connection.status = NodeStatus.ERROR
            connection.last_error = str(e)
    
    async def _monitor_connections(self) -> None:
        """Monitor node connections and perform health checks."""
        while True:
            try:
                for chain, connections in self.connections.items():
                    for connection in connections:
                        # Health check
                        await self._health_check(connection)
                    
                    # Re-select primary if needed
                    if chain in self.primary_connections:
                        current_primary = self.primary_connections[chain]
                        if current_primary.get_health_score() < 50:
                            self._select_primary_nodes()
                
                # Log status
                self._log_connection_status()
                
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(5)
    
    async def _health_check(self, connection: NodeConnection) -> None:
        """Perform health check on connection."""
        try:
            start_time = time.time()
            
            # Check if still connected
            if not connection.web3.is_connected():
                connection.status = NodeStatus.DISCONNECTED
                return
            
            # Get latest block
            latest_block = connection.web3.eth.block_number
            latency = (time.time() - start_time) * 1000
            
            # Update metrics
            connection.last_block = latest_block
            connection.latency_ms = latency
            connection.request_count += 1
            
            # Track latency history
            chain = connection.config.chain
            if chain not in self.latency_history:
                self.latency_history[chain] = []
            self.latency_history[chain].append(latency)
            
            # Keep only recent history
            if len(self.latency_history[chain]) > 100:
                self.latency_history[chain].pop(0)
            
        except Exception as e:
            connection.error_count += 1
            connection.last_error = str(e)
            if connection.error_count > 5:
                connection.status = NodeStatus.ERROR
    
    def _log_connection_status(self) -> None:
        """Log current connection status."""
        status_lines = ["Node Connection Status:"]
        
        for chain, connections in self.connections.items():
            connected = sum(1 for c in connections if c.status == NodeStatus.CONNECTED)
            primary = self.primary_connections.get(chain)
            
            if primary:
                status_lines.append(
                    f"  {chain}: {connected}/{len(connections)} connected, "
                    f"Primary latency: {primary.latency_ms:.1f}ms"
                )
            else:
                status_lines.append(
                    f"  {chain}: {connected}/{len(connections)} connected, "
                    f"No primary selected"
                )
        
        self.logger.debug("\n".join(status_lines))
    
    def get_latency_stats(self, chain: str) -> Dict[str, float]:
        """
        Get latency statistics for a chain.
        
        Args:
            chain: Blockchain name
            
        Returns:
            Dictionary with min, max, avg latency
        """
        if chain not in self.latency_history or not self.latency_history[chain]:
            return {'min': 0, 'max': 0, 'avg': 0}
        
        latencies = self.latency_history[chain]
        return {
            'min': min(latencies),
            'max': max(latencies),
            'avg': sum(latencies) / len(latencies)
        }
    
    async def shutdown(self) -> None:
        """Shutdown all connections gracefully."""
        self.logger.info("Shutting down Direct Node Manager...")
        
        # Cancel monitoring
        if self.monitoring_task:
            self.monitoring_task.cancel()
        
        # Close all WebSocket connections
        for chain, connections in self.connections.items():
            for connection in connections:
                if connection.websocket:
                    await connection.websocket.close()
        
        self.logger.info("Direct Node Manager shutdown complete")