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
            
            # First approve router to spend tokens
            approval_tx = await self.approve_token(
                token_address,
                router_address,
                amount_tokens,
                wallet_name,
                chain,
                gas_price
            )
            
            if not approval_tx:
                raise Exception("Token approval failed")
            
            # Wait for approval confirmation
            w3.eth.wait_for_transaction_receipt(approval_tx, timeout=60)
            
            # Get router contract
            router_contract = self._get_router_contract(chain, router)
            
            # Build swap path
            weth_address = self.WETH[chain]
            path = [
                Web3.to_checksum_address(token_address),
                Web3.to_checksum_address(weth_address)
            ]
            
            wallet_address = self.wallet_manager.get_wallet_address(wallet_name)
            deadline = int(datetime.now().timestamp()) + (deadline_minutes * 60)
            
            # Build transaction
            tx = router_contract.functions.swapExactTokensForETH(
                Web3.to_wei(amount_tokens, 'ether'),  # amountIn
                Web3.to_wei(min_eth, 'ether'),        # amountOutMin
                path,                                  # path
                wallet_address,                        # to
                deadline                              # deadline
            ).build_transaction({
                'from': wallet_address,
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
            self.logger.error(f"Swap tokens for ETH failed: {e}")
            return None
    
    async def get_amounts_out(
        self,
        amount_in: Decimal,
        path: List[str],
        chain: str,
        router: str = "uniswap_v2"
    ) -> Optional[List[Decimal]]:
        """
        Get expected output amounts for a swap path.
        
        Args:
            amount_in: Input amount
            path: Token addresses in swap path
            chain: Chain identifier
            router: Router to use
            
        Returns:
            List of output amounts for each step
        """
        try:
            w3 = self.web3_connections.get(chain)
            if not w3:
                raise ValueError(f"No Web3 connection for {chain}")
            
            router_contract = self._get_router_contract(chain, router)
            
            # Convert addresses to checksum
            path_checksum = [Web3.to_checksum_address(addr) for addr in path]
            
            # Call getAmountsOut
            amounts = router_contract.functions.getAmountsOut(
                Web3.to_wei(amount_in, 'ether'),
                path_checksum
            ).call()
            
            # Convert to decimals
            return [Decimal(str(amount)) / Decimal(10**18) for amount in amounts]
            
        except Exception as e:
            self.logger.error(f"Get amounts out failed: {e}")
            return None
    
    def _get_router_contract(self, chain: str, router: str) -> Contract:
        """Get or create router contract instance."""
        key = f"{chain}_{router}"
        
        if key not in self.contracts:
            w3 = self.web3_connections[chain]
            router_address = self.ROUTERS[chain][router]
            
            # Uniswap V2 Router ABI (minimal)
            router_abi = [
                {
                    "inputs": [
                        {"name": "amountOutMin", "type": "uint256"},
                        {"name": "path", "type": "address[]"},
                        {"name": "to", "type": "address"},
                        {"name": "deadline", "type": "uint256"}
                    ],
                    "name": "swapExactETHForTokens",
                    "outputs": [{"name": "amounts", "type": "uint256[]"}],
                    "stateMutability": "payable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {"name": "amountIn", "type": "uint256"},
                        {"name": "amountOutMin", "type": "uint256"},
                        {"name": "path", "type": "address[]"},
                        {"name": "to", "type": "address"},
                        {"name": "deadline", "type": "uint256"}
                    ],
                    "name": "swapExactTokensForETH",
                    "outputs": [{"name": "amounts", "type": "uint256[]"}],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {"name": "amountIn", "type": "uint256"},
                        {"name": "path", "type": "address[]"}
                    ],
                    "name": "getAmountsOut",
                    "outputs": [{"name": "amounts", "type": "uint256[]"}],
                    "stateMutability": "view",
                    "type": "function"
                }
            ]
            
            self.contracts[key] = w3.eth.contract(
                address=Web3.to_checksum_address(router_address),
                abi=router_abi
            )
        
        return self.contracts[key]
    
    async def estimate_gas_for_swap(
        self,
        token_address: str,
        amount_in: Decimal,
        is_buy: bool,
        wallet_name: str,
        chain: str,
        router: str = "uniswap_v2"
    ) -> Optional[int]:
        """
        Estimate gas for a swap transaction.
        
        Args:
            token_address: Token address
            amount_in: Input amount (ETH if buying, tokens if selling)
            is_buy: True if buying tokens, False if selling
            wallet_name: Wallet to use
            chain: Chain identifier
            router: Router to use
            
        Returns:
            Estimated gas units
        """
        try:
            w3 = self.web3_connections.get(chain)
            if not w3:
                return None
            
            router_contract = self._get_router_contract(chain, router)
            wallet_address = self.wallet_manager.get_wallet_address(wallet_name)
            
            # Build path
            weth_address = self.WETH[chain]
            if is_buy:
                path = [weth_address, token_address]
            else:
                path = [token_address, weth_address]
            
            # Estimate based on transaction type
            if is_buy:
                # Estimate for buying tokens
                return 250000  # Conservative estimate
            else:
                # Estimate for selling tokens (includes approval)
                return 350000  # Higher due to approval + swap
                
        except Exception as e:
            self.logger.error(f"Gas estimation failed: {e}")
            return 300000  # Default conservative estimate