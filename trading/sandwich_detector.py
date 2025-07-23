"""
Sandwich attack detection and prevention system.
Monitors mempool for potential sandwich attacks and provides protection strategies.
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from web3 import Web3
from web3.types import TxData, HexBytes
import json

from utils.logger import logger_manager


@dataclass
class SandwichThreat:
    """
    Represents a potential sandwich attack threat.
    
    Attributes:
        threat_id: Unique threat identifier
        frontrun_tx: Potential frontrunning transaction
        backrun_tx: Potential backrunning transaction
        target_token: Token being targeted
        threat_level: Severity of threat (0-100)
        detected_at: Detection timestamp
        dex_router: DEX router being used
        estimated_loss: Estimated loss if sandwiched
    """
    threat_id: str
    frontrun_tx: Optional[TxData] = None
    backrun_tx: Optional[TxData] = None
    target_token: Optional[str] = None
    threat_level: float = 0.0
    detected_at: datetime = field(default_factory=datetime.now)
    dex_router: Optional[str] = None
    estimated_loss: Optional[Decimal] = None
    
    def is_active(self) -> bool:
        """Check if threat is still active."""
        return (datetime.now() - self.detected_at).seconds < 60


@dataclass
class MempoolTransaction:
    """
    Transaction in mempool with analysis metadata.
    
    Attributes:
        tx_hash: Transaction hash
        from_address: Sender address
        to_address: Target address
        value: Transaction value
        gas_price: Gas price
        input_data: Transaction input data
        detected_at: First seen timestamp
        is_dex_swap: Whether this is a DEX swap
        token_in: Input token address
        token_out: Output token address
        amount_in: Input amount
        router_method: Router method being called
    """
    tx_hash: str
    from_address: str
    to_address: str
    value: int
    gas_price: int
    input_data: str
    detected_at: datetime = field(default_factory=datetime.now)
    is_dex_swap: bool = False
    token_in: Optional[str] = None
    token_out: Optional[str] = None
    amount_in: Optional[Decimal] = None
    router_method: Optional[str] = None


class SandwichDetector:
    """
    Detects and prevents sandwich attacks by monitoring mempool transactions.
    """
    
    # Known DEX router addresses
    DEX_ROUTERS = {
        "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D": "Uniswap V2",
        "0xE592427A0AEce92De3Edee1F18E0157C05861564": "Uniswap V3",
        "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F": "Sushiswap",
        "0x1111111254EEB25477B68fb85Ed929f73A960582": "1inch"
    }
    
    # Swap method signatures
    SWAP_SIGNATURES = {
        "0x7ff36ab5": "swapExactETHForTokens",
        "0x18cbafe5": "swapExactTokensForETH",
        "0x38ed1739": "swapExactTokensForTokens",
        "0x8803dbee": "swapTokensForExactTokens",
        "0xfb3bdb41": "swapETHForExactTokens",
        "0x5c11d795": "swapExactTokensForTokensSupportingFeeOnTransferTokens"
    }
    
    def __init__(self):
        """Initialize the sandwich detector."""
        self.logger = logger_manager.get_logger("SandwichDetector")
        
        # Web3 connection
        self.w3: Optional[Web3] = None
        
        # Mempool monitoring
        self.mempool_txs: Dict[str, MempoolTransaction] = {}
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # Threat detection
        self.active_threats: Dict[str, SandwichThreat] = {}
        self.known_attackers: Set[str] = set()
        self.protected_txs: Set[str] = set()
        
        # Statistics
        self.threats_detected = 0
        self.attacks_prevented = 0
        
    async def initialize(self, w3: Web3) -> None:
        """
        Initialize the sandwich detector.
        
        Args:
            w3: Web3 connection with mempool access
        """
        try:
            self.logger.info("Initializing Sandwich Detector...")
            
            self.w3 = w3
            
            # Load known attackers from database/file
            self._load_known_attackers()
            
            # Start mempool monitoring
            self.monitoring_task = asyncio.create_task(
                self._monitor_mempool()
            )
            
            self.monitoring_active = True
            self.logger.info("✅ Sandwich Detector initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            raise
    
    def _load_known_attackers(self) -> None:
        """Load list of known sandwich attack addresses."""
        # In production, load from database
        # For now, use some known MEV bot addresses
        self.known_attackers = {
            "0x00000000000000000000000000000000000dead",  # Example
            # Add more known attacker addresses
        }
    
    async def check_sandwich_risk(
        self,
        tx_params: Dict,
        protection_window: int = 30
    ) -> Tuple[bool, Optional[SandwichThreat]]:
        """
        Check if a transaction is at risk of sandwich attack.
        
        Args:
            tx_params: Transaction parameters to check
            protection_window: Time window to check for threats (seconds)
            
        Returns:
            Tuple of (is_at_risk, threat_details)
        """
        try:
            # Parse transaction
            parsed_tx = self._parse_transaction(tx_params)
            if not parsed_tx.is_dex_swap:
                return False, None
            
            # Check for active threats
            for threat_id, threat in self.active_threats.items():
                if not threat.is_active():
                    continue
                
                # Check if same token and DEX
                if (threat.target_token == parsed_tx.token_out and
                    threat.dex_router == parsed_tx.to_address):
                    
                    # Calculate threat level
                    threat.threat_level = self._calculate_threat_level(
                        parsed_tx, threat
                    )
                    
                    if threat.threat_level > 50:
                        return True, threat
            
            # Check mempool for suspicious patterns
            suspicious_txs = self._find_suspicious_transactions(parsed_tx)
            if suspicious_txs:
                # Create new threat
                threat = self._create_threat_from_txs(
                    parsed_tx, suspicious_txs
                )
                self.active_threats[threat.threat_id] = threat
                self.threats_detected += 1
                
                return True, threat
            
            return False, None
            
        except Exception as e:
            self.logger.error(f"Risk check failed: {e}")
            return False, None
    
    def _parse_transaction(self, tx_params: Dict) -> MempoolTransaction:
        """Parse transaction parameters into MempoolTransaction."""
        tx = MempoolTransaction(
            tx_hash="pending",
            from_address=tx_params.get('from', ''),
            to_address=tx_params.get('to', ''),
            value=tx_params.get('value', 0),
            gas_price=tx_params.get('gasPrice', 0),
            input_data=tx_params.get('data', '0x')
        )
        
        # Check if DEX transaction
        if tx.to_address in self.DEX_ROUTERS:
            tx.is_dex_swap = True
            tx.router_method = self._decode_method(tx.input_data)
            
            # Extract token addresses and amounts
            # This would decode the actual input data
            # For now, simplified
            
        return tx
    
    def _decode_method(self, input_data: str) -> Optional[str]:
        """Decode method signature from input data."""
        if len(input_data) < 10:
            return None
        
        method_sig = input_data[:10]
        return self.SWAP_SIGNATURES.get(method_sig)
    
    def _calculate_threat_level(
        self,
        target_tx: MempoolTransaction,
        threat: SandwichThreat
    ) -> float:
        """
        Calculate threat level (0-100).
        
        Args:
            target_tx: Transaction being evaluated
            threat: Existing threat
            
        Returns:
            Threat level score
        """
        score = 0.0
        
        # Check if frontrun transaction has higher gas
        if threat.frontrun_tx:
            if threat.frontrun_tx['gasPrice'] > target_tx.gas_price:
                score += 30
        
        # Check if from known attacker
        if threat.frontrun_tx and threat.frontrun_tx['from'] in self.known_attackers:
            score += 40
        
        # Check transaction patterns
        # Large trade size increases risk
        if target_tx.amount_in and target_tx.amount_in > Decimal('10'):
            score += 20
        
        # Same block timing
        time_diff = (datetime.now() - threat.detected_at).seconds
        if time_diff < 5:
            score += 10
        
        return min(100, score)
    
    def _find_suspicious_transactions(
        self,
        target_tx: MempoolTransaction
    ) -> List[MempoolTransaction]:
        """Find suspicious transactions in mempool."""
        suspicious = []
        
        for tx_hash, mempool_tx in self.mempool_txs.items():
            # Skip if too old
            if (datetime.now() - mempool_tx.detected_at).seconds > 60:
                continue
            
            # Check for sandwich pattern
            if (mempool_tx.is_dex_swap and
                mempool_tx.to_address == target_tx.to_address and
                mempool_tx.gas_price > target_tx.gas_price):
                
                # Check if targeting same token
                if (mempool_tx.token_out == target_tx.token_out or
                    mempool_tx.token_in == target_tx.token_out):
                    suspicious.append(mempool_tx)
        
        return suspicious
    
    def _create_threat_from_txs(
        self,
        target_tx: MempoolTransaction,
        suspicious_txs: List[MempoolTransaction]
    ) -> SandwichThreat:
        """Create threat object from suspicious transactions."""
        import uuid
        
        threat = SandwichThreat(
            threat_id=str(uuid.uuid4()),
            target_token=target_tx.token_out,
            dex_router=target_tx.to_address
        )
        
        # Identify potential frontrun/backrun
        for tx in suspicious_txs:
            if tx.gas_price > target_tx.gas_price:
                threat.frontrun_tx = {
                    'hash': tx.tx_hash,
                    'from': tx.from_address,
                    'gasPrice': tx.gas_price
                }
        
        # Calculate threat level
        threat.threat_level = self._calculate_threat_level(
            target_tx, threat
        )
        
        return threat
    
    async def _monitor_mempool(self) -> None:
        """Monitor mempool for sandwich attacks."""
        while self.monitoring_active:
            try:
                # Clean old transactions
                self._clean_old_transactions()
                
                # Check for sandwich patterns
                self._detect_sandwich_patterns()
                
                # Update threat levels
                self._update_threat_levels()
                
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Mempool monitoring error: {e}")
                await asyncio.sleep(5)
    
    def _clean_old_transactions(self) -> None:
        """Remove old transactions from tracking."""
        current_time = datetime.now()
        to_remove = []
        
        for tx_hash, tx in self.mempool_txs.items():
            if (current_time - tx.detected_at).seconds > 120:
                to_remove.append(tx_hash)
        
        for tx_hash in to_remove:
            del self.mempool_txs[tx_hash]
    
    def _detect_sandwich_patterns(self) -> None:
        """Detect sandwich attack patterns in mempool."""
        # Group transactions by DEX and token
        dex_groups = {}
        
        for tx in self.mempool_txs.values():
            if not tx.is_dex_swap:
                continue
            
            key = (tx.to_address, tx.token_out)
            if key not in dex_groups:
                dex_groups[key] = []
            dex_groups[key].append(tx)
        
        # Look for sandwich patterns
        for (dex, token), txs in dex_groups.items():
            if len(txs) < 2:
                continue
            
            # Sort by gas price
            txs.sort(key=lambda x: x.gas_price, reverse=True)
            
            # Check for sandwich setup
            for i in range(len(txs) - 1):
                high_gas_tx = txs[i]
                
                # Look for victim transaction
                for j in range(i + 1, len(txs)):
                    low_gas_tx = txs[j]
                    
                    # Check if potential sandwich
                    if self._is_sandwich_setup(high_gas_tx, low_gas_tx):
                        self._create_sandwich_threat(
                            high_gas_tx, low_gas_tx, token, dex
                        )
    
    def _is_sandwich_setup(
        self,
        tx1: MempoolTransaction,
        tx2: MempoolTransaction
    ) -> bool:
        """Check if two transactions form a sandwich setup."""
        # Gas price difference
        if tx1.gas_price <= tx2.gas_price * 1.1:
            return False
        
        # Same sender (potential attacker)
        if tx1.from_address == tx2.from_address:
            return False
        
        # Check amounts (frontrun usually smaller)
        if tx1.amount_in and tx2.amount_in:
            if tx1.amount_in > tx2.amount_in * 2:
                return False
        
        return True
    
    def _create_sandwich_threat(
        self,
        frontrun: MempoolTransaction,
        victim: MempoolTransaction,
        token: str,
        dex: str
    ) -> None:
        """Create and record sandwich threat."""
        import uuid
        
        threat = SandwichThreat(
            threat_id=str(uuid.uuid4()),
            frontrun_tx={
                'hash': frontrun.tx_hash,
                'from': frontrun.from_address,
                'gasPrice': frontrun.gas_price
            },
            target_token=token,
            dex_router=dex,
            threat_level=75.0
        )
        
        self.active_threats[threat.threat_id] = threat
        self.threats_detected += 1
        
        self.logger.warning(
            f"🚨 Sandwich threat detected: {threat.threat_id} "
            f"Token: {token}, DEX: {self.DEX_ROUTERS.get(dex, dex)}"
        )
    
    def _update_threat_levels(self) -> None:
        """Update threat levels for active threats."""
        to_remove = []
        
        for threat_id, threat in self.active_threats.items():
            if not threat.is_active():
                to_remove.append(threat_id)
            else:
                # Decay threat level over time
                age_seconds = (datetime.now() - threat.detected_at).seconds
                threat.threat_level *= (1 - age_seconds / 120)
        
        for threat_id in to_remove:
            del self.active_threats[threat_id]
    
    async def add_mempool_transaction(self, tx_data: TxData) -> None:
        """
        Add transaction to mempool tracking.
        
        Args:
            tx_data: Transaction data from mempool
        """
        try:
            tx = MempoolTransaction(
                tx_hash=tx_data.get('hash', '').hex() if isinstance(tx_data.get('hash'), HexBytes) else str(tx_data.get('hash', '')),
                from_address=tx_data.get('from', ''),
                to_address=tx_data.get('to', ''),
                value=tx_data.get('value', 0),
                gas_price=tx_data.get('gasPrice', 0),
                input_data=tx_data.get('input', '0x')
            )
            
            # Check if DEX transaction
            if tx.to_address in self.DEX_ROUTERS:
                tx.is_dex_swap = True
                tx.router_method = self._decode_method(tx.input_data)
            
            self.mempool_txs[tx.tx_hash] = tx
            
        except Exception as e:
            self.logger.error(f"Failed to add mempool tx: {e}")
    
    def get_protection_strategy(
        self,
        threat: SandwichThreat
    ) -> Dict[str, Any]:
        """
        Get protection strategy for a sandwich threat.
        
        Args:
            threat: Sandwich threat to protect against
            
        Returns:
            Protection strategy recommendations
        """
        strategy = {
            'use_flashbots': True,
            'increase_gas': False,
            'delay_execution': False,
            'split_trade': False,
            'recommendations': []
        }
        
        if threat.threat_level > 80:
            # High threat - use all protections
            strategy['increase_gas'] = True
            strategy['split_trade'] = True
            strategy['recommendations'].append(
                "High sandwich risk - use Flashbots bundle"
            )
            
        elif threat.threat_level > 50:
            # Medium threat
            strategy['delay_execution'] = True
            strategy['recommendations'].append(
                "Medium risk - consider delaying or using private mempool"
            )
        
        # Known attacker
        if (threat.frontrun_tx and 
            threat.frontrun_tx.get('from') in self.known_attackers):
            strategy['recommendations'].append(
                "Known attacker detected - use maximum protection"
            )
        
        return strategy
    
    def record_attack_prevented(self, tx_hash: str) -> None:
        """
        Record that an attack was prevented.
        
        Args:
            tx_hash: Protected transaction hash
        """
        self.protected_txs.add(tx_hash)
        self.attacks_prevented += 1
        self.logger.info(f"✅ Sandwich attack prevented for tx: {tx_hash}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get sandwich detection statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            'threats_detected': self.threats_detected,
            'attacks_prevented': self.attacks_prevented,
            'active_threats': len(self.active_threats),
            'known_attackers': len(self.known_attackers),
            'mempool_txs_tracked': len(self.mempool_txs),
            'protected_txs': len(self.protected_txs)
        }
    
    async def shutdown(self) -> None:
        """Shutdown the sandwich detector."""
        self.logger.info("Shutting down Sandwich Detector...")
        
        self.monitoring_active = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
        
        self.logger.info("Sandwich Detector shutdown complete")