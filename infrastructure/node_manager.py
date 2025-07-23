"""
Direct blockchain node connection manager for ultra-fast data access.
Manages WebSocket connections, node failover, and optimized data streaming.
"""

from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import time
from web3 import Web3
try:
    # Try modern import first (Web3.py v6+)
    from web3.providers import WebsocketProvider, HTTPProvider
except ImportError:
    # Fall back to older import style
    try:
        from web3.providers.websocket import WebsocketProvider
        from web3.providers.rpc import HTTPProvider
    except ImportError:
        # Final fallback for compatibility
        from web3 import HTTPProvider
        WebsocketProvider = None

try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    # Older versions might have it elsewhere
    geth_poa_middleware = None

import aiohttp

from utils.logger import logger_manager


class NodeType(Enum):
    """Types of blockchain nodes."""
    ARCHIVE = "archive"
    FULL = "full"
    LIGHT = "light"
    DEDICATED = "dedicated"
    SHARED = "shared"


class ConnectionStatus(Enum):
    """Node connection status."""
    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    SYNCING = "syncing"


@dataclass
class NodeConfig:
    """Configuration for a blockchain node."""
    url: str
    ws_url: Optional[str]
    node_type: NodeType
    chain: str
    priority: int = 1  # Lower = higher priority
    max_connections: int = 10
    timeout: int = 30
    health_check_interval: int = 60


@dataclass
class NodeMetrics:
    """Performance metrics for a node."""
    latency_ms: float
    requests_per_second: float
    error_rate: float
    last_block: int
    sync_status: str
    uptime_percentage: float
    response_times: List[float]


class DirectNodeManager:
    """
    Manages direct connections to blockchain nodes for maximum speed.
    Provides load balancing, failover, and optimized data access.
    """
    
    def __init__(self) -> None:
        """Initialize the direct node connection manager."""
        self.logger = logger_manager.get_logger("DirectNodeManager")
        
        # Node configurations by chain
        self.node_configs: Dict[str, List[NodeConfig]] = {
            "ethereum": [],
            "base": [],
            "solana": []
        }
        
        # Active connections
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.websocket_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        
        # Connection pools
        self.connection_pools: Dict[str, List[Web3]] = {}
        
        # Performance tracking
        self.node_metrics: Dict[str, NodeMetrics] = {}
        self.request_counts: Dict[str, int] = {}
        self.last_health_check: Dict[str, datetime] = {}
        
        # Event subscriptions
        self.event_subscriptions: Dict[str, Set[Callable]] = {}
        self.block_subscriptions: Dict[str, Set[Callable]] = {}
        
        # Connection management
        self.reconnect_tasks: Dict[str, asyncio.Task] = {}
        self.monitoring_active = False
        
    async def initialize(self) -> None:
        """Initialize node connections and start monitoring."""
        try:
            self.logger.info("Initializing direct node connection manager...")
            
            # Load node configurations
            await self._load_node_configurations()
            
            # Establish initial connections
            await self._establish_connections()
            
            # Start monitoring and health checks
            await self._start_monitoring()
            
            self.logger.info("Direct node manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize node manager: {e}")
            raise
    
    async def add_node(self, config: NodeConfig) -> None:
        """
        Add a new node configuration.
        
        Args:
            config: Node configuration to add
        """
        try:
            chain = config.chain.lower()
            
            if chain not in self.node_configs:
                self.node_configs[chain] = []
            
            self.node_configs[chain].append(config)
            
            # Sort by priority
            self.node_configs[chain].sort(key=lambda x: x.priority)
            
            # Establish connection
            await self._connect_to_node(config)
            
            self.logger.info(f"Added node: {config.url} for {chain}")
            
        except Exception as e:
            self.logger.error(f"Failed to add node {config.url}: {e}")
    
    async def get_web3_connection(
        self, 
        chain: str, 
        prefer_websocket: bool = True
    ) -> Optional[Web3]:
        """
        Get an optimized Web3 connection for a chain.
        
        Args:
            chain: Blockchain name
            prefer_websocket: Prefer WebSocket over HTTP
            
        Returns:
            Web3 instance or None
        """
        try:
            chain = chain.lower()
            
            # Get from connection pool
            if chain in self.connection_pools and self.connection_pools[chain]:
                # Return least loaded connection
                return self._get_least_loaded_connection(chain)
            
            # Create new connection if needed
            configs = self.node_configs.get(chain, [])
            for config in configs:
                if prefer_websocket and config.ws_url:
                    w3 = await self._create_websocket_connection(config)
                else:
                    w3 = await self._create_http_connection(config)
                
                if w3 and w3.is_connected():
                    return w3
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get Web3 connection for {chain}: {e}")
            return None
    
    async def subscribe_to_blocks(
        self, 
        chain: str, 
        callback: Callable[[Dict], None]
    ) -> str:
        """
        Subscribe to new blocks on a chain.
        
        Args:
            chain: Blockchain name
            callback: Function to call with new blocks
            
        Returns:
            Subscription ID
        """
        try:
            chain = chain.lower()
            
            if chain not in self.block_subscriptions:
                self.block_subscriptions[chain] = set()
            
            self.block_subscriptions[chain].add(callback)
            
            # Start block monitoring if not already active
            if not self._is_block_monitoring_active(chain):
                asyncio.create_task(self._monitor_blocks(chain))
            
            subscription_id = f"blocks_{chain}_{len(self.block_subscriptions[chain])}"
            
            self.logger.info(f"Added block subscription for {chain}")
            
            return subscription_id
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to blocks: {e}")
            raise
    
    async def subscribe_to_events(
        self,
        chain: str,
        contract_address: str,
        event_signature: str,
        callback: Callable[[Dict], None]
    ) -> str:
        """
        Subscribe to contract events.
        
        Args:
            chain: Blockchain name
            contract_address: Contract to monitor
            event_signature: Event signature to filter
            callback: Function to call with events
            
        Returns:
            Subscription ID
        """
        try:
            subscription_key = f"{chain}_{contract_address}_{event_signature}"
            
            if subscription_key not in self.event_subscriptions:
                self.event_subscriptions[subscription_key] = set()
                
                # Start event monitoring
                asyncio.create_task(
                    self._monitor_events(chain, contract_address, event_signature)
                )
            
            self.event_subscriptions[subscription_key].add(callback)
            
            subscription_id = f"events_{subscription_key}_{len(self.event_subscriptions[subscription_key])}"
            
            self.logger.info(f"Added event subscription: {subscription_id}")
            
            return subscription_id
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to events: {e}")
            raise
    
    async def execute_batch_calls(
        self,
        chain: str,
        calls: List[Dict[str, Any]]
    ) -> List[Any]:
        """
        Execute multiple calls in a single batch for efficiency.
        
        Args:
            chain: Blockchain name
            calls: List of call parameters
            
        Returns:
            List of results
        """
        try:
            w3 = await self.get_web3_connection(chain)
            if not w3:
                raise ConnectionError(f"No connection available for {chain}")
            
            # Use multicall if available
            if hasattr(w3.eth, 'multicall'):
                return await self._execute_multicall(w3, calls)
            
            # Fall back to parallel execution
            tasks = [self._execute_single_call(w3, call) for call in calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Batch call execution failed: {e}")
            raise
    
    def get_node_metrics(self, chain: str) -> Dict[str, NodeMetrics]:
        """
        Get performance metrics for nodes on a chain.
        
        Args:
            chain: Blockchain name
            
        Returns:
            Dictionary of node URLs to metrics
        """
        chain = chain.lower()
        metrics = {}
        
        for config in self.node_configs.get(chain, []):
            if config.url in self.node_metrics:
                metrics[config.url] = self.node_metrics[config.url]
        
        return metrics
    
    async def _load_node_configurations(self) -> None:
        """Load node configurations from settings."""
        # Try to load from environment/settings first
        import os
        from config.settings import settings
        
        # Default configurations for different chains
        default_configs = {
            "ethereum": [],
            "base": [],
            "solana": []
        }
        
        # Load Ethereum RPC from environment
        eth_rpc = os.getenv("ETHEREUM_RPC_URL", "https://ethereum-rpc.publicnode.com")
        if eth_rpc:
            default_configs["ethereum"].append(
                NodeConfig(
                    url=eth_rpc,
                    ws_url=None,  # Free RPCs usually don't have WebSocket
                    node_type=NodeType.SHARED,
                    chain="ethereum",
                    priority=1
                )
            )
            
            # Add backup free Ethereum RPCs
            backup_eth_rpcs = [
                "https://rpc.ankr.com/eth",
                "https://eth.public-rpc.com",
                "https://ethereum.blockpi.network/v1/rpc/public"
            ]
            for i, rpc in enumerate(backup_eth_rpcs, 2):
                if rpc != eth_rpc:  # Don't add duplicates
                    default_configs["ethereum"].append(
                        NodeConfig(
                            url=rpc,
                            ws_url=None,
                            node_type=NodeType.SHARED,
                            chain="ethereum",
                            priority=i
                        )
                    )
        
        # Load Base RPC
        base_rpc = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
        if base_rpc:
            default_configs["base"].append(
                NodeConfig(
                    url=base_rpc,
                    ws_url=None,
                    node_type=NodeType.SHARED,
                    chain="base",
                    priority=1
                )
            )
        
        # Solana RPC
        solana_rpc = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        if solana_rpc:
            default_configs["solana"].append(
                NodeConfig(
                    url=solana_rpc,
                    ws_url=None,
                    node_type=NodeType.SHARED,
                    chain="solana",
                    priority=1
                )
            )
        
        # Apply configurations
        for chain, configs in default_configs.items():
            if configs:
                self.node_configs[chain] = configs
                self.logger.info(f"Loaded {len(configs)} nodes for {chain}")
    
    async def _establish_connections(self) -> None:
        """Establish initial connections to all configured nodes."""
        tasks = []
        
        for chain, configs in self.node_configs.items():
            # Only connect to the first (highest priority) node per chain initially
            if configs:
                config = configs[0]  # Just the first one
                tasks.append(self._connect_to_node_with_timeout(config))
        
        # Wait for connections with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=10.0  # 10 second total timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning("Some node connections timed out, continuing...")
    
    async def _connect_to_node_with_timeout(self, config: NodeConfig) -> None:
        """Connect to a node with timeout."""
        try:
            await asyncio.wait_for(
                self._connect_to_node(config),
                timeout=5.0  # 5 seconds per node
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Connection timeout for {config.url}")
        except Exception as e:
            self.logger.error(f"Connection failed for {config.url}: {e}")
    
    async def _connect_to_node(self, config: NodeConfig) -> None:
        """Establish connection to a specific node."""
        try:
            self.logger.debug(f"Connecting to node: {config.url}")
            
            # Create connection pool
            if config.chain not in self.connection_pools:
                self.connection_pools[config.chain] = []
            
            # Create just one connection initially (faster startup)
            if config.ws_url and WebsocketProvider is not None:
                w3 = await self._create_websocket_connection(config)
            else:
                w3 = await self._create_http_connection(config)
            
            if w3 and w3.is_connected():
                self.connection_pools[config.chain].append(w3)
                self.logger.info(f"Connected to node: {config.url}")
            else:
                self.logger.warning(f"Failed to connect to node: {config.url}")
            
            # Initialize metrics
            self.node_metrics[config.url] = NodeMetrics(
                latency_ms=0.0,
                requests_per_second=0.0,
                error_rate=0.0,
                last_block=0,
                sync_status="unknown",
                uptime_percentage=100.0,
                response_times=[]
            )
            
        except Exception as e:
            self.logger.error(f"Failed to connect to node {config.url}: {e}")
    
    async def _create_websocket_connection(self, config: NodeConfig) -> Optional[Web3]:
        """Create WebSocket Web3 connection."""
        try:
            if WebsocketProvider is None:
                self.logger.warning("WebSocket provider not available, using HTTP fallback")
                return await self._create_http_connection(config)
            
            provider = WebsocketProvider(
                config.ws_url,
                websocket_timeout=config.timeout,
                websocket_kwargs={
                    "max_size": 1024 * 1024 * 10,  # 10MB
                    "compression": None
                }
            )
            
            w3 = Web3(provider)
            
            # Add middleware for specific chains if available
            if geth_poa_middleware and config.chain in ["base", "polygon"]:
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            # Test connection
            if w3.is_connected():
                return w3
            
            return None
            
        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {e}")
            return None
    
    async def _create_http_connection(self, config: NodeConfig) -> Optional[Web3]:
        """Create HTTP Web3 connection."""
        try:
            provider = HTTPProvider(
                config.url,
                request_kwargs={"timeout": config.timeout}
            )
            
            w3 = Web3(provider)
            
            # Add middleware for specific chains if available
            if geth_poa_middleware and config.chain in ["base", "polygon"]:
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            # Test connection
            if w3.is_connected():
                return w3
            
            return None
            
        except Exception as e:
            self.logger.error(f"HTTP connection failed: {e}")
            return None
    
    def _get_least_loaded_connection(self, chain: str) -> Optional[Web3]:
        """Get the least loaded connection from the pool."""
        connections = self.connection_pools.get(chain, [])
        
        if not connections:
            return None
        
        # For now, return first available
        # In production, would track request counts per connection
        return connections[0]
    
    async def _monitor_blocks(self, chain: str) -> None:
        """Monitor new blocks on a chain."""
        try:
            w3 = await self.get_web3_connection(chain, prefer_websocket=True)
            if not w3:
                return
            
            last_block = w3.eth.block_number
            
            while chain in self.block_subscriptions:
                try:
                    current_block = w3.eth.block_number
                    
                    if current_block > last_block:
                        # Fetch new blocks
                        for block_num in range(last_block + 1, current_block + 1):
                            block = w3.eth.get_block(block_num, full_transactions=True)
                            
                            # Notify subscribers
                            for callback in self.block_subscriptions[chain]:
                                try:
                                    await callback(block)
                                except Exception as e:
                                    self.logger.error(f"Block callback error: {e}")
                        
                        last_block = current_block
                    
                    await asyncio.sleep(0.5)  # Poll frequently
                    
                except Exception as e:
                    self.logger.error(f"Block monitoring error for {chain}: {e}")
                    await asyncio.sleep(5)
                    
        except Exception as e:
            self.logger.error(f"Fatal block monitoring error: {e}")
    
    async def _monitor_events(
        self,
        chain: str,
        contract_address: str,
        event_signature: str
    ) -> None:
        """Monitor contract events."""
        try:
            w3 = await self.get_web3_connection(chain)
            if not w3:
                return
            
            # Create event filter
            event_filter = w3.eth.filter({
                "address": contract_address,
                "topics": [event_signature]
            })
            
            subscription_key = f"{chain}_{contract_address}_{event_signature}"
            
            while subscription_key in self.event_subscriptions:
                try:
                    # Get new events
                    events = event_filter.get_new_entries()
                    
                    for event in events:
                        # Notify subscribers
                        for callback in self.event_subscriptions[subscription_key]:
                            try:
                                await callback(event)
                            except Exception as e:
                                self.logger.error(f"Event callback error: {e}")
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"Event monitoring error: {e}")
                    await asyncio.sleep(5)
                    
        except Exception as e:
            self.logger.error(f"Fatal event monitoring error: {e}")
    
    async def _start_monitoring(self) -> None:
        """Start node health monitoring."""
        self.monitoring_active = True
        asyncio.create_task(self._monitor_node_health())
        asyncio.create_task(self._monitor_performance())
    
    async def _monitor_node_health(self) -> None:
        """Monitor health of all nodes."""
        while self.monitoring_active:
            try:
                for chain, configs in self.node_configs.items():
                    for config in configs:
                        await self._check_node_health(config)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _check_node_health(self, config: NodeConfig) -> None:
        """Check health of a specific node."""
        try:
            start_time = time.time()
            
            # Try to get latest block
            w3 = await self._create_http_connection(config)
            if w3 and w3.is_connected():
                block_number = w3.eth.block_number
                latency = (time.time() - start_time) * 1000
                
                # Update metrics
                if config.url in self.node_metrics:
                    metrics = self.node_metrics[config.url]
                    metrics.latency_ms = latency
                    metrics.last_block = block_number
                    metrics.sync_status = "synced"
                    
                    # Update response times
                    metrics.response_times.append(latency)
                    if len(metrics.response_times) > 100:
                        metrics.response_times = metrics.response_times[-100:]
            else:
                # Mark as disconnected
                if config.url in self.node_metrics:
                    self.node_metrics[config.url].sync_status = "disconnected"
                    
        except Exception as e:
            self.logger.error(f"Health check failed for {config.url}: {e}")
            if config.url in self.node_metrics:
                self.node_metrics[config.url].error_rate += 0.01
    
    async def _monitor_performance(self) -> None:
        """Monitor performance metrics."""
        while self.monitoring_active:
            try:
                # Calculate performance metrics
                for url, metrics in self.node_metrics.items():
                    if metrics.response_times:
                        # Calculate average latency
                        avg_latency = sum(metrics.response_times) / len(metrics.response_times)
                        metrics.latency_ms = avg_latency
                
                await asyncio.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(30)
    
    def _is_block_monitoring_active(self, chain: str) -> bool:
        """Check if block monitoring is active for a chain."""
        # Check if monitoring task exists and is running
        return chain in self.block_subscriptions and len(self.block_subscriptions[chain]) > 0
    
    async def _execute_multicall(self, w3: Web3, calls: List[Dict]) -> List[Any]:
        """Execute multiple calls using multicall."""
        # This would implement actual multicall
        # For now, execute sequentially
        results = []
        for call in calls:
            result = await self._execute_single_call(w3, call)
            results.append(result)
        return results
    
    async def _execute_single_call(self, w3: Web3, call: Dict) -> Any:
        """Execute a single call."""
        try:
            return w3.eth.call(call)
        except Exception as e:
            self.logger.error(f"Call execution failed: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Clean up all connections."""
        try:
            self.monitoring_active = False
            
            # Close WebSocket connections
            for ws in self.websocket_connections.values():
                await ws.close()
            
            # Clear connection pools
            self.connection_pools.clear()
            
            self.logger.info("Node manager cleaned up")
            
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")