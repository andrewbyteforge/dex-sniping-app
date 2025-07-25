"""
DEX interaction manager for executing trades on various decentralized exchanges.
Handles router interactions, token approvals, and swap execution.
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime
import json
from web3 import Web3
from web3.contract import Contract
from web3.types import TxParams, Wei
from eth_typing import ChecksumAddress

from trading.wallet_manager import WalletManager
from utils.logger import logger_manager


class DEXManager:
    """
    Manages interactions with decentralized exchanges.
    Supports Uniswap V2, V3, Sushiswap, and Base DEXs.
    """
    
    # DEX Router addresses
    ROUTERS = {
        "ethereum": {
            "uniswap_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
            "sushiswap": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F"
        },
        "base": {
            "uniswap_v2": "0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24",
            "baseswap": "0x327Df1E6de05895d2ab08513aaDD9313Fe505d86"
        }
    }
    
    # WETH addresses
    WETH = {
        "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "base": "0x4200000000000000000000000000000000000006"
    }
    
    def __init__(self, wallet_manager: WalletManager) -> None:
        """
        Initialize DEX manager.
        
        Args:
            wallet_manager: Wallet manager instance
        """
        self.logger = logger_manager.get_logger("DEXManager")
        self.wallet_manager = wallet_manager
        self.contracts: Dict[str, Contract] = {}
        self.web3_connections: Dict[str, Web3] = {}
        
    def add_web3_connection(self, chain: str, w3: Web3) -> None:
        """Add Web3 connection for a chain."""
        self.web3_connections[chain] = w3
        self.wallet_manager.add_web3_connection(chain, w3)
        self.logger.debug(f"Added Web3 connection for {chain}")
    
    async def approve_token(
        self,
        token_address: str,
        spender_address: str,
        amount: Decimal,
        wallet_name: str,
        chain: str,
        gas_price: Optional[Wei] = None
    ) -> Optional[str]:
        """
        Approve token spending.
        
        Args:
            token_address: Token to approve
            spender_address: Address to approve (router)
            amount: Amount to approve (use large number for infinite)
            wallet_name: Wallet to use
            chain: Chain identifier
            gas_price: Optional gas price
            
        Returns:
            Transaction hash if successful
        """
        try:
            w3 = self.web3_connections.get(chain)
            if not w3:
                raise ValueError(f"No Web3 connection for {chain}")
            
            # ERC20 approve ABI
            approve_abi = [{
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }]
            
            token_contract = w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=approve_abi
            )
            
            # Convert amount to wei (assuming 18 decimals, adjust as needed)
            amount_wei = Web3.to_wei(amount, 'ether')
            
            # Build transaction
            tx = token_contract.functions.approve(
                Web3.to_checksum_address(spender_address),
                amount_wei
            ).build_transaction({
                'from': self.wallet_manager.get_wallet_address(wallet_name),
                'gas': 100000,
                'gasPrice': gas_price or w3.eth.gas_price
            })
            
            # Sign and send
            signed_tx = self.wallet_manager.sign_transaction(wallet_name, tx, chain)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            self.logger.info(f"Token approval sent: {tx_hash.hex()}")
            return tx_hash.hex()
            
        except Exception as e:
            self.logger.error(f"Token approval failed: {e}")
            return None
    
    async def swap_eth_for_tokens(
        self,
        token_address: str,
        amount_eth: Decimal,
        min_tokens: Decimal,
        wallet_name: str,
        chain: str,
        router: str = "uniswap_v2",
        deadline_minutes: int = 20,
        gas_price: Optional[Wei] = None,
        gas_limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Swap ETH for tokens.
        
        Args:
            token_address: Token to buy
            amount_eth: ETH amount to spend
            min_tokens: Minimum tokens to receive
            wallet_name: Wallet to use
            chain: Chain identifier
            router: Router to use
            deadline_minutes: Transaction deadline
            gas_price: Optional gas price
            gas_limit: Optional gas limit
            
        Returns:
            Transaction result dictionary
        """
        try:
            w3 = self.web3_connections.get(chain)
            if not w3:
                raise ValueError(f"No Web3 connection for {chain}")
            
            router_address = self.ROUTERS.get(chain, {}).get(router)
            if not router_address:
                raise ValueError(f"Router {router} not found for {chain}")
            
            # Get router contract
            router_contract = self._get_router_contract(chain, router)
            
            # Build swap path
            weth_address = self.WETH[chain]
            path = [
                Web3.to_checksum_address(weth_address),
                Web3.to_checksum_address(token_address)
            ]
            
            wallet_address = self.wallet_manager.get_wallet_address(wallet_name)
            deadline = int(datetime.now().timestamp()) + (deadline_minutes * 60)
            
            # Build transaction
            tx = router_contract.functions.swapExactETHForTokens(
                Web3.to_wei(min_tokens, 'ether'),  # amountOutMin
                path,                               # path
                wallet_address,                     # to
                deadline                           # deadline
            ).build_transaction({
                'from': wallet_address,
                'value': Web3.to_wei(amount_eth, 'ether'),
                'gas': gas_limit or 300000,
                'gasPrice': gas_price or w3.eth.gas_price
            })
            
            # Sign and send
            signed_tx = self.wallet_manager.sign_transaction(wallet_name, tx, chain)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            self.logger.info(f"Swap transaction sent: {tx_hash.hex()}")
            
            # Wait for receipt
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            return {
                'success': receipt['status'] == 1,
                'tx_hash': tx_hash.hex(),
                'gas_used': receipt['gasUsed'],
                'block_number': receipt['blockNumber']
            }
            
        except Exception as e:
            self.logger.error(f"Swap ETH for tokens failed: {e}")
            return None
    
    async def swap_tokens_for_eth(
        self,
        token_address: str,
        amount_tokens: Decimal,
        min_eth: Decimal,
        wallet_name: str,
        chain: str,
        router: str = "uniswap_v2",
        deadline_minutes: int = 20,
        gas_price: Optional[Wei] = None,
        gas_limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Swap tokens for ETH.
        
        Args:
            token_address: Token to sell
            amount_tokens: Token amount to sell
            min_eth: Minimum ETH to receive
            wallet_name: Wallet to use
            chain: Chain identifier
            router: Router to use
            deadline_minutes: Transaction deadline
            gas_price: Optional gas price
            gas_limit: Optional gas limit
            
        Returns:
            Transaction result dictionary
        """
        try:
            w3 = self.web3_connections.get(chain)
            if not w3:
                raise ValueError(f"No Web3 connection for {chain}")
            
            router_address = self.ROUTERS.get(chain, {}).get(router)
            if not router_address:
                raise ValueError(f"Router {router} not found for {chain}")
            
            # Get router contract
            router_contract = self._get_router_contract(chain, router)
            
            # Build swap path (token -> WETH)
            weth_address = self.WETH[chain]
            path = [
                Web3.to_checksum_address(token_address),
                Web3.to_checksum_address(weth_address)
            ]
            
            wallet_address = self.wallet_manager.get_wallet_address(wallet_name)
            deadline = int(datetime.now().timestamp()) + (deadline_minutes * 60)
            
            # Convert amounts to wei
            amount_tokens_wei = Web3.to_wei(amount_tokens, 'ether')
            min_eth_wei = Web3.to_wei(min_eth, 'ether')
            
            # Build transaction
            tx = router_contract.functions.swapExactTokensForETH(
                amount_tokens_wei,  # amountIn
                min_eth_wei,        # amountOutMin
                path,               # path
                wallet_address,     # to
                deadline           # deadline
            ).build_transaction({
                'from': wallet_address,
                'gas': gas_limit or 300000,
                'gasPrice': gas_price or w3.eth.gas_price
            })
            
            # Sign and send
            signed_tx = self.wallet_manager.sign_transaction(wallet_name, tx, chain)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            result = {
                'tx_hash': tx_hash.hex(),
                'amount_tokens': float(amount_tokens),
                'min_eth': float(min_eth),
                'gas_used': tx.get('gas', 0),
                'gas_price': tx.get('gasPrice', 0),
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"Token -> ETH swap sent: {tx_hash.hex()}")
            return result
            
        except Exception as e:
            self.logger.error(f"Token -> ETH swap failed: {e}")
            return None










    async def get_amounts_out(
        self,
        amount_in: Decimal,
        path: List[str],
        chain: str,
        router: str = "uniswap_v2"
    ) -> Optional[List[Decimal]]:
        """
        Get amounts out for a swap path.
        
        Args:
            amount_in: Input amount
            path: Token swap path
            chain: Chain identifier
            router: Router to query
            
        Returns:
            List of amounts out for each step
        """
        try:
            w3 = self.web3_connections.get(chain)
            if not w3:
                raise ValueError(f"No Web3 connection for {chain}")
            
            router_contract = self._get_router_contract(chain, router)
            
            # Convert path to checksum addresses
            checksum_path = [Web3.to_checksum_address(addr) for addr in path]
            
            # Convert amount to wei
            amount_in_wei = Web3.to_wei(amount_in, 'ether')
            
            # Query amounts out
            amounts_out = router_contract.functions.getAmountsOut(
                amount_in_wei,
                checksum_path
            ).call()
            
            # Convert back to Decimal
            result = [Decimal(str(amount)) / Decimal("1e18") for amount in amounts_out]
            
            return result
            
        except Exception as e:
            self.logger.error(f"Get amounts out failed: {e}")
            return None

    async def get_token_allowance(
        self,
        token_address: str,
        owner_address: str,
        spender_address: str,
        chain: str
    ) -> Decimal:
        """
        Get token allowance for spender.
        
        Args:
            token_address: Token contract address
            owner_address: Token owner address
            spender_address: Spender address
            chain: Chain identifier
            
        Returns:
            Current allowance amount
        """
        try:
            w3 = self.web3_connections.get(chain)
            if not w3:
                raise ValueError(f"No Web3 connection for {chain}")
            
            # ERC20 allowance ABI
            allowance_abi = [{
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }]
            
            token_contract = w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=allowance_abi
            )
            
            allowance_wei = token_contract.functions.allowance(
                Web3.to_checksum_address(owner_address),
                Web3.to_checksum_address(spender_address)
            ).call()
            
            # Convert to Decimal (assuming 18 decimals)
            return Decimal(str(allowance_wei)) / Decimal("1e18")
            
        except Exception as e:
            self.logger.error(f"Get allowance failed: {e}")
            return Decimal("0")
        









    def _get_router_contract(self, chain: str, router: str):
        """Get router contract instance."""
        try:
            w3 = self.web3_connections[chain]
            router_address = self.ROUTERS[chain][router]
            
            # Basic Uniswap V2 Router ABI (essential methods only)
            router_abi = [
                {
                    "constant": False,
                    "inputs": [
                        {"name": "amountOutMin", "type": "uint256"},
                        {"name": "path", "type": "address[]"},
                        {"name": "to", "type": "address"},
                        {"name": "deadline", "type": "uint256"}
                    ],
                    "name": "swapExactETHForTokens",
                    "outputs": [{"name": "amounts", "type": "uint256[]"}],
                    "payable": True,
                    "type": "function"
                },
                {
                    "constant": False,
                    "inputs": [
                        {"name": "amountIn", "type": "uint256"},
                        {"name": "amountOutMin", "type": "uint256"},
                        {"name": "path", "type": "address[]"},
                        {"name": "to", "type": "address"},
                        {"name": "deadline", "type": "uint256"}
                    ],
                    "name": "swapExactTokensForETH",
                    "outputs": [{"name": "amounts", "type": "uint256[]"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [
                        {"name": "amountIn", "type": "uint256"},
                        {"name": "path", "type": "address[]"}
                    ],
                    "name": "getAmountsOut",
                    "outputs": [{"name": "amounts", "type": "uint256[]"}],
                    "type": "function"
                }
            ]
            
            return w3.eth.contract(
                address=Web3.to_checksum_address(router_address),
                abi=router_abi
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get router contract: {e}")
            raise


    async def get_pair_reserves(
        self,
        token_a: str,
        token_b: str,
        chain: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get liquidity pair reserves.
        
        Args:
            token_a: First token address
            token_b: Second token address
            chain: Chain identifier
            
        Returns:
            Pair reserves information
        """
        try:
            w3 = self.web3_connections.get(chain)
            if not w3:
                raise ValueError(f"No Web3 connection for {chain}")
            
            # Uniswap V2 Factory address (simplified)
            factory_addresses = {
                "ethereum": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
                "base": "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6"
            }
            
            factory_address = factory_addresses.get(chain)
            if not factory_address:
                return None
            
            # Factory ABI (getPair method)
            factory_abi = [{
                "constant": True,
                "inputs": [
                    {"name": "tokenA", "type": "address"},
                    {"name": "tokenB", "type": "address"}
                ],
                "name": "getPair",
                "outputs": [{"name": "pair", "type": "address"}],
                "type": "function"
            }]
            
            factory_contract = w3.eth.contract(
                address=Web3.to_checksum_address(factory_address),
                abi=factory_abi
            )
            
            # Get pair address
            pair_address = factory_contract.functions.getPair(
                Web3.to_checksum_address(token_a),
                Web3.to_checksum_address(token_b)
            ).call()
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                return None
            
            # Pair ABI (getReserves method)
            pair_abi = [{
                "constant": True,
                "inputs": [],
                "name": "getReserves",
                "outputs": [
                    {"name": "_reserve0", "type": "uint112"},
                    {"name": "_reserve1", "type": "uint112"},
                    {"name": "_blockTimestampLast", "type": "uint32"}
                ],
                "type": "function"
            }]
            
            pair_contract = w3.eth.contract(
                address=Web3.to_checksum_address(pair_address),
                abi=pair_abi
            )
            
            reserves = pair_contract.functions.getReserves().call()
            
            return {
                "pair_address": pair_address,
                "reserve0": reserves[0],
                "reserve1": reserves[1],
                "block_timestamp_last": reserves[2],
                "token_a": token_a,
                "token_b": token_b
            }
            
        except Exception as e:
            self.logger.error(f"Get pair reserves failed: {e}")
            return None










    async def estimate_gas_for_swap(
        self,
        token_address: str,
        amount_eth: Decimal,
        wallet_name: str,
        chain: str,
        router: str = "uniswap_v2"
    ) -> Optional[int]:
        """
        Estimate gas for a swap transaction.
        
        Args:
            token_address: Token to swap
            amount_eth: ETH amount
            wallet_name: Wallet to use
            chain: Chain identifier
            router: Router to use
            
        Returns:
            Estimated gas limit
        """
        try:
            w3 = self.web3_connections.get(chain)
            if not w3:
                return None
            
            router_contract = self._get_router_contract(chain, router)
            
            # Build transaction for estimation
            weth_address = self.WETH[chain]
            path = [
                Web3.to_checksum_address(weth_address),
                Web3.to_checksum_address(token_address)
            ]
            
            wallet_address = self.wallet_manager.get_wallet_address(wallet_name)
            deadline = int(datetime.now().timestamp()) + 1200  # 20 minutes
            
            # Estimate gas
            gas_estimate = router_contract.functions.swapExactETHForTokens(
                0,  # amountOutMin (0 for estimation)
                path,
                wallet_address,
                deadline
            ).estimate_gas({
                'from': wallet_address,
                'value': Web3.to_wei(amount_eth, 'ether')
            })
            
            # Add 20% buffer
            return int(gas_estimate * 1.2)
            
        except Exception as e:
            self.logger.warning(f"Gas estimation failed: {e}")
            return 300000  # Conservative fallback