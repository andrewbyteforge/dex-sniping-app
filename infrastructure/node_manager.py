"""
Direct Node Manager for optimized blockchain connections.
Manages high-performance node connections and load balancing.
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import aiohttp
import time
from web3 import Web3
from web3.providers import HTTPProvider, WebsocketProvider
import websockets
import json
import os

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
    """Node performance metrics."""
    latency_ms: float = 0.0
    success_rate: float = 1.0
    total_requests: int = 0
    failed_requests: int = 0
    last_request_time: Optional[datetime] = None
    connection_uptime: timedelta = field(default_factory=lambda: timedelta())
    block_height: int = 0
    sync_status: bool = True


@dataclass
class NodeConfig:
    """Node configuration."""
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


class DirectNodeManager:
    """
    High-performance node manager for direct blockchain connections.
    Provides load balancing, failover, and performance optimization.
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
        """Load node configurations from environment variables."""
        try:
            # Ethereum mainnet nodes
            ethereum_nodes = []
            
            # Infura
            infura_key = os.getenv("INFURA_API_KEY")
            if infura_key:
                ethereum_nodes.append(NodeConfig(
                    name="infura_mainnet",
                    url=f"https://mainnet.infura.io/v3/{infura_key}",
                    node_type=NodeType.HTTP,
                    chain_id=1,
                    priority=2,
                    max_requests_per_second=100
                ))
                ethereum_nodes.append(NodeConfig(
                    name="infura_mainnet_ws",
                    url=f"wss://mainnet.infura.io/ws/v3/{infura_key}",
                    node_type=NodeType.WEBSOCKET,
                    chain_id=1,
                    priority=3,
                    max_requests_per_second=200
                ))
            
            # Alchemy
            alchemy_key = os.getenv("ALCHEMY_API_KEY")
            if alchemy_key:
                ethereum_nodes.append(NodeConfig(
                    name="alchemy_mainnet",
                    url=f"https://eth-mainnet.alchemyapi.io/v2/{alchemy_key}",
                    node_type=NodeType.HTTP,
                    chain_id=1,
                    priority=3,
                    max_requests_per_second=200
                ))
                ethereum_nodes.append(NodeConfig(
                    name="alchemy_mainnet_ws",
                    url=f"wss://eth-mainnet.alchemyapi.io/v2/{alchemy_key}",
                    node_type=NodeType.WEBSOCKET,
                    chain_id=1,
                    priority=4,
                    max_requests_per_second=300
                ))
            
            # QuickNode
            quicknode_url = os.getenv("QUICKNODE_ETHEREUM_URL")
            if quicknode_url:
                ethereum_nodes.append(NodeConfig(
                    name="quicknode_mainnet",
                    url=quicknode_url,
                    node_type=NodeType.HTTP,
                    chain_id=1,
                    priority=4,
                    max_requests_per_second=500
                ))
            
            # Custom node
            custom_ethereum_url = os.getenv("CUSTOM_ETHEREUM_RPC_URL")
            if custom_ethereum_url:
                ethereum_nodes.append(NodeConfig(
                    name="custom_ethereum",
                    url=custom_ethereum_url,
                    node_type=NodeType.HTTP,
                    chain_id=1,
                    priority=5,  # Highest priority for custom nodes
                    max_requests_per_second=1000
                ))
            
            if ethereum_nodes:
                self.node_configs["ethereum"] = ethereum_nodes
                self.logger.info(f"Loaded {len(ethereum_nodes)} Ethereum nodes")
            
            # Base chain nodes
            base_nodes = []
            base_rpc_url = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
            base_nodes.append(NodeConfig(
                name="base_mainnet",
                url=base_rpc_url,
                node_type=NodeType.HTTP,
                chain_id=8453,
                priority=1,
                max_requests_per_second=100
            ))
            
            if base_nodes:
                self.node_configs["base"] = base_nodes
                self.logger.info(f"Loaded {len(base_nodes)} Base nodes")
            
            # BSC nodes
            bsc_nodes = []
            bsc_rpc_url = os.getenv("BSC_RPC_URL", "https://bsc-dataseed1.binance.org")
            bsc_nodes.append(NodeConfig(
                name="bsc_mainnet",
                url=bsc_rpc_url,
                node_type=NodeType.HTTP,
                chain_id=56,
                priority=1,
                max_requests_per_second=100
            ))
            
            if bsc_nodes:
                self.node_configs["bsc"] = bsc_nodes
                self.logger.info(f"Loaded {len(bsc_nodes)} BSC nodes")
            
        except Exception as e:
            self.logger.error(f"Node configuration loading failed: {e}")
            # Add fallback configurations
            await self._add_fallback_configurations()
    
    async def _add_fallback_configurations(self) -> None:
        """Add fallback node configurations."""
        try:
            self.logger.warning("Adding fallback node configurations...")
            
            # Ethereum fallback
            if "ethereum" not in self.node_configs:
                self.node_configs["ethereum"] = [
                    NodeConfig(
                        name="ethereum_fallback",
                        url="https://eth.public-rpc.com",
                        node_type=NodeType.HTTP,
                        chain_id=1,
                        priority=1,
                        max_requests_per_second=50
                    )
                ]
            
            # Base fallback
            if "base" not in self.node_configs:
                self.node_configs["base"] = [
                    NodeConfig(
                        name="base_fallback",
                        url="https://mainnet.base.org",
                        node_type=NodeType.HTTP,
                        chain_id=8453,
                        priority=1,
                        max_requests_per_second=50
                    )
                ]
                
        except Exception as e:
            self.logger.error(f"Fallback configuration failed: {e}")
    
    async def _establish_connections(self) -> None:
        """Establish connections to all configured nodes."""
        try:
            for chain, nodes in self.node_configs.items():
                self.logger.info(f"Establishing connections for {chain}...")
                
                # Sort nodes by priority (highest first)
                sorted_nodes = sorted(nodes, key=lambda x: x.priority, reverse=True)
                
                for node in sorted_nodes:
                    try:
                        if not node.enabled:
                            continue
                            
                        connection = await self._create_connection(node)
                        if connection:
                            connection_key = f"{chain}_{node.name}"
                            self.web3_connections[connection_key] = connection
                            
                            # Initialize metrics
                            self.node_metrics[connection_key] = NodeMetrics()
                            self.node_status[connection_key] = ConnectionStatus.CONNECTED
                            self.request_counts[connection_key] = 0
                            
                            # Test connection
                            await self._test_connection(connection_key, connection)
                            
                            self.manager_stats["connections_established"] += 1
                            self.logger.info(f"✅ Connected to {node.name} ({chain})")
                        else:
                            self.manager_stats["connections_failed"] += 1
                            self.logger.warning(f"❌ Failed to connect to {node.name} ({chain})")
                            
                    except Exception as e:
                        self.logger.error(f"Connection failed for {node.name}: {e}")
                        self.manager_stats["connections_failed"] += 1
                
                # Set primary connection for chain
                chain_connections = [k for k in self.web3_connections.keys() if k.startswith(chain)]
                if chain_connections:
                    # Use highest priority working connection
                    primary_connection = chain_connections[0]
                    self.web3_connections[chain] = self.web3_connections[primary_connection]
                    self.last_used_node[chain] = primary_connection
                    
        except Exception as e:
            self.logger.error(f"Connection establishment failed: {e}")
    
    async def _create_connection(self, node: NodeConfig) -> Optional[Web3]:
        """Create Web3 connection for a node."""
        try:
            if node.node_type == NodeType.HTTP:
                # Create HTTP provider with custom headers
                provider_kwargs = {
                    "request_kwargs": {
                        "timeout": node.timeout_seconds
                    }
                }
                
                if node.auth_header:
                    provider_kwargs["request_kwargs"]["headers"] = {
                        "Authorization": node.auth_header
                    }
                
                provider = HTTPProvider(node.url, **provider_kwargs)
                web3 = Web3(provider)
                
            elif node.node_type == NodeType.WEBSOCKET:
                # Create WebSocket provider
                provider = WebsocketProvider(
                    node.url,
                    websocket_timeout=node.timeout_seconds
                )
                web3 = Web3(provider)
                
            else:
                self.logger.warning(f"Unsupported node type: {node.node_type}")
                return None
            
            # Verify connection
            if web3.is_connected():
                return web3
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to create connection for {node.name}: {e}")
            return None
    
    async def _test_connection(self, connection_key: str, web3: Web3) -> None:
        """Test a Web3 connection."""
        try:
            start_time = time.time()
            
            # Test basic connectivity
            block_number = await web3.eth.block_number
            chain_id = await web3.eth.chain_id
            
            latency = (time.time() - start_time) * 1000  # Convert to ms
            
            # Update metrics
            metrics = self.node_metrics[connection_key]
            metrics.latency_ms = latency
            metrics.block_height = block_number
            metrics.last_request_time = datetime.now()
            metrics.total_requests += 1
            
            self.logger.debug(
                f"Connection test successful: {connection_key} "
                f"(Block: {block_number}, Chain: {chain_id}, Latency: {latency:.1f}ms)"
            )
            
        except Exception as e:
            self.logger.error(f"Connection test failed for {connection_key}: {e}")
            self.node_status[connection_key] = ConnectionStatus.ERROR
            
            # Update failure metrics
            if connection_key in self.node_metrics:
                self.node_metrics[connection_key].failed_requests += 1
    
    async def get_web3_connection(self, chain: str) -> Optional[Web3]:
        """
        Get optimized Web3 connection for a chain.
        
        Args:
            chain: Chain identifier (ethereum, base, bsc, etc.)
            
        Returns:
            Web3 connection or None if unavailable
        """
        try:
            if not self.initialized:
                self.logger.warning("Node manager not initialized")
                return None
            
            # Get best available connection
            connection_key = await self._select_best_node(chain)
            
            if connection_key and connection_key in self.web3_connections:
                connection = self.web3_connections[connection_key]
                
                # Update usage tracking
                self.request_counts[connection_key] += 1
                self.last_used_node[chain] = connection_key
                self.manager_stats["total_requests"] += 1
                
                return connection
            else:
                self.logger.warning(f"No available connections for {chain}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get Web3 connection for {chain}: {e}")
            return None
    
    async def _select_best_node(self, chain: str) -> Optional[str]:
        """Select the best node for a chain based on performance metrics."""
        try:
            # Get all connections for the chain
            chain_connections = [
                k for k in self.web3_connections.keys() 
                if k.startswith(chain) and k != chain
            ]
            
            if not chain_connections:
                return None
            
            # Filter to only healthy connections
            healthy_connections = [
                k for k in chain_connections
                if self.node_status.get(k) == ConnectionStatus.CONNECTED
            ]
            
            if not healthy_connections:
                # Try to use any available connection
                return chain_connections[0] if chain_connections else None
            
            # Score connections based on performance
            connection_scores = {}
            for conn_key in healthy_connections:
                score = self._calculate_node_score(conn_key)
                connection_scores[conn_key] = score
            
            # Select highest scoring connection
            best_connection = max(connection_scores.items(), key=lambda x: x[1])[0]
            
            return best_connection
            
        except Exception as e:
            self.logger.error(f"Node selection failed for {chain}: {e}")
            # Return first available connection as fallback
            chain_connections = [k for k in self.web3_connections.keys() if k.startswith(chain)]
            return chain_connections[0] if chain_connections else None
    
    def _calculate_node_score(self, connection_key: str) -> float:
        """Calculate performance score for a node."""
        try:
            metrics = self.node_metrics.get(connection_key)
            if not metrics:
                return 0.0
            
            # Base score
            score = 100.0
            
            # Latency penalty (lower latency = higher score)
            if metrics.latency_ms > 0:
                latency_penalty = min(metrics.latency_ms / 10, 50)  # Max 50 point penalty
                score -= latency_penalty
            
            # Success rate bonus
            if metrics.total_requests > 0:
                success_rate = 1.0 - (metrics.failed_requests / metrics.total_requests)
                score *= success_rate
            
            # Recent usage penalty (load balancing)
            recent_requests = self.request_counts.get(connection_key, 0)
            if recent_requests > 100:  # High usage threshold
                usage_penalty = min((recent_requests - 100) / 10, 20)  # Max 20 point penalty
                score -= usage_penalty
            
            # Priority bonus (from node config)
            node_config = self._get_node_config(connection_key)
            if node_config:
                priority_bonus = node_config.priority * 5
                score += priority_bonus
            
            return max(0.0, score)
            
        except Exception as e:
            self.logger.debug(f"Score calculation failed for {connection_key}: {e}")
            return 0.0
    
    def _get_node_config(self, connection_key: str) -> Optional[NodeConfig]:
        """Get node configuration by connection key."""
        try:
            # Parse connection key to get chain and node name
            parts = connection_key.split("_", 1)
            if len(parts) != 2:
                return None
            
            chain, node_name = parts
            
            if chain not in self.node_configs:
                return None
            
            # Find matching node config
            for node in self.node_configs[chain]:
                if node.name == node_name:
                    return node
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Node config lookup failed for {connection_key}: {e}")
            return None
    
    async def _start_health_monitoring(self) -> None:
        """Start monitoring node health."""
        try:
            self.logger.info("Starting node health monitoring...")
            
            while self.initialized:
                try:
                    await self._check_node_health()
                    await asyncio.sleep(self.health_check_interval)
                    
                except Exception as e:
                    self.logger.error(f"Health monitoring error: {e}")
                    await asyncio.sleep(self.health_check_interval * 2)
                    
        except Exception as e:
            self.logger.error(f"Health monitoring failed: {e}")
    
    async def _check_node_health(self) -> None:
        """Check health of all node connections."""
        try:
            for connection_key, web3 in self.web3_connections.items():
                if connection_key in ["ethereum", "base", "bsc"]:  # Skip chain aliases
                    continue
                
                try:
                    # Test connection
                    if web3.is_connected():
                        await self._test_connection(connection_key, web3)
                        
                        # Update status if it was previously errored
                        if self.node_status.get(connection_key) != ConnectionStatus.CONNECTED:
                            self.node_status[connection_key] = ConnectionStatus.CONNECTED
                            self.logger.info(f"Node {connection_key} recovered")
                            
                    else:
                        self.node_status[connection_key] = ConnectionStatus.DISCONNECTED
                        self.logger.warning(f"Node {connection_key} disconnected")
                        
                except Exception as e:
                    self.node_status[connection_key] = ConnectionStatus.ERROR
                    self.logger.error(f"Health check failed for {connection_key}: {e}")
                    
                    # Update failure metrics
                    if connection_key in self.node_metrics:
                        self.node_metrics[connection_key].failed_requests += 1
                        
        except Exception as e:
            self.logger.error(f"Node health check failed: {e}")
    
    async def _start_metrics_collection(self) -> None:
        """Start collecting performance metrics."""
        try:
            self.logger.info("Starting metrics collection...")
            
            while self.initialized:
                try:
                    await self._update_performance_metrics()
                    await self._reset_request_counters()
                    await asyncio.sleep(self.metrics_update_interval)
                    
                except Exception as e:
                    self.logger.error(f"Metrics collection error: {e}")
                    await asyncio.sleep(self.metrics_update_interval * 2)
                    
        except Exception as e:
            self.logger.error(f"Metrics collection failed: {e}")
    
    async def _update_performance_metrics(self) -> None:
        """Update overall performance metrics."""
        try:
            # Calculate average latency
            latencies = [
                metrics.latency_ms for metrics in self.node_metrics.values()
                if metrics.latency_ms > 0
            ]
            
            if latencies:
                self.manager_stats["average_latency"] = sum(latencies) / len(latencies)
            
            # Update success rates
            for connection_key, metrics in self.node_metrics.items():
                if metrics.total_requests > 0:
                    success_rate = 1.0 - (metrics.failed_requests / metrics.total_requests)
                    metrics.success_rate = success_rate
                    
        except Exception as e:
            self.logger.debug(f"Performance metrics update failed: {e}")
    
    async def _reset_request_counters(self) -> None:
        """Reset request counters for load balancing."""
        try:
            # Reset counters every hour to allow load rebalancing
            for connection_key in self.request_counts:
                self.request_counts[connection_key] = 0
                
        except Exception as e:
            self.logger.debug(f"Request counter reset failed: {e}")
    
    def _log_connection_summary(self) -> None:
        """Log summary of established connections."""
        try:
            self.logger.info("=" * 50)
            self.logger.info("NODE CONNECTION SUMMARY")
            self.logger.info("=" * 50)
            
            for chain, nodes in self.node_configs.items():
                chain_connections = [
                    k for k in self.web3_connections.keys() 
                    if k.startswith(chain) and k != chain
                ]
                
                self.logger.info(f"{chain.upper()}: {len(chain_connections)} connections")
                
                for conn_key in chain_connections:
                    status = self.node_status.get(conn_key, ConnectionStatus.DISCONNECTED)
                    metrics = self.node_metrics.get(conn_key)
                    
                    latency_info = ""
                    if metrics and metrics.latency_ms > 0:
                        latency_info = f" ({metrics.latency_ms:.1f}ms)"
                    
                    self.logger.info(f"  • {conn_key}: {status.value}{latency_info}")
            
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.debug(f"Connection summary logging failed: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "manager_stats": self.manager_stats.copy(),
            "node_metrics": {k: {
                "latency_ms": v.latency_ms,
                "success_rate": v.success_rate,
                "total_requests": v.total_requests,
                "failed_requests": v.failed_requests,
                "block_height": v.block_height,
                "sync_status": v.sync_status
            } for k, v in self.node_metrics.items()},
            "node_status": {k: v.value for k, v in self.node_status.items()},
            "active_connections": len(self.web3_connections)
        }