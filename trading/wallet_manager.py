"""
Wallet management for secure transaction signing and account management.
Handles private keys, transaction signing, and balance tracking.
"""

import os
from typing import Dict, Optional, List, Tuple
from decimal import Decimal
from eth_account import Account
from eth_account.datastructures import SignedTransaction
from web3 import Web3
from web3.types import TxParams, Wei
import json

from utils.logger import logger_manager


class WalletManager:
    """
    Manages wallet operations including signing transactions and tracking balances.
    Supports multiple wallets for different strategies or chains.
    """
    
    def __init__(self) -> None:
        """Initialize wallet manager."""
        self.logger = logger_manager.get_logger("WalletManager")
        self.wallets: Dict[str, Account] = {}
        self.web3_connections: Dict[str, Web3] = {}
        self.nonce_tracker: Dict[str, int] = {}
        
        # Security warning
        self.logger.warning("⚠️  WALLET MANAGER INITIALIZED - Handle private keys with extreme care!")
        
    def add_wallet(self, name: str, private_key: str) -> str:
        """
        Add a wallet to the manager.
        
        Args:
            name: Wallet identifier
            private_key: Private key (with or without 0x prefix)
            
        Returns:
            Wallet address
        """
        try:
            # Ensure private key has 0x prefix
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            
            # Create account from private key
            account = Account.from_key(private_key)
            self.wallets[name] = account
            
            self.logger.info(f"Added wallet '{name}': {account.address}")
            return account.address
            
        except Exception as e:
            self.logger.error(f"Failed to add wallet '{name}': {e}")
            raise
    
    def add_web3_connection(self, chain: str, w3: Web3) -> None:
        """
        Add a Web3 connection for a specific chain.
        
        Args:
            chain: Chain identifier (ethereum, base, etc.)
            w3: Web3 instance
        """
        self.web3_connections[chain] = w3
        self.logger.debug(f"Added Web3 connection for {chain}")
    
    def get_wallet_address(self, name: str) -> Optional[str]:
        """Get wallet address by name."""
        account = self.wallets.get(name)
        return account.address if account else None
    
    async def get_balance(
        self, 
        wallet_name: str, 
        chain: str,
        token_address: Optional[str] = None
    ) -> Decimal:
        """
        Get wallet balance for native token or ERC20.
        
        Args:
            wallet_name: Wallet identifier
            chain: Chain to check balance on
            token_address: ERC20 token address (None for native token)
            
        Returns:
            Balance in token units
        """
        try:
            account = self.wallets.get(wallet_name)
            if not account:
                raise ValueError(f"Wallet '{wallet_name}' not found")
            
            w3 = self.web3_connections.get(chain)
            if not w3:
                raise ValueError(f"No Web3 connection for {chain}")
            
            if token_address:
                # ERC20 balance
                balance = await self._get_token_balance(
                    w3, account.address, token_address
                )
            else:
                # Native token balance
                balance_wei = w3.eth.get_balance(account.address)
                balance = Decimal(str(balance_wei)) / Decimal(10**18)
            
            return balance
            
        except Exception as e:
            self.logger.error(f"Failed to get balance: {e}")
            return Decimal("0")
    
    async def _get_token_balance(
        self, 
        w3: Web3, 
        wallet_address: str, 
        token_address: str
    ) -> Decimal:
        """Get ERC20 token balance."""
        # Minimal ERC20 ABI for balanceOf
        erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]
        
        try:
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=erc20_abi
            )
            
            balance = contract.functions.balanceOf(wallet_address).call()
            decimals = contract.functions.decimals().call()
            
            return Decimal(str(balance)) / Decimal(10**decimals)
            
        except Exception as e:
            self.logger.error(f"Failed to get token balance: {e}")
            return Decimal("0")
    
    def sign_transaction(
        self,
        wallet_name: str,
        tx_params: TxParams,
        chain: str
    ) -> SignedTransaction:
        """
        Sign a transaction with the specified wallet.
        
        Args:
            wallet_name: Wallet to sign with
            tx_params: Transaction parameters
            chain: Chain identifier
            
        Returns:
            Signed transaction
        """
        try:
            account = self.wallets.get(wallet_name)
            if not account:
                raise ValueError(f"Wallet '{wallet_name}' not found")
            
            w3 = self.web3_connections.get(chain)
            if not w3:
                raise ValueError(f"No Web3 connection for {chain}")
            
            # Ensure from address matches wallet
            if 'from' in tx_params and tx_params['from'] != account.address:
                raise ValueError("Transaction 'from' doesn't match wallet address")
            
            tx_params['from'] = account.address
            
            # Get nonce if not provided
            if 'nonce' not in tx_params:
                tx_params['nonce'] = self._get_next_nonce(wallet_name, chain)
            
            # Sign transaction
            signed_tx = account.sign_transaction(tx_params)
            
            self.logger.info(f"Signed transaction from {wallet_name} on {chain}")
            return signed_tx
            
        except Exception as e:
            self.logger.error(f"Failed to sign transaction: {e}")
            raise
    
    def _get_next_nonce(self, wallet_name: str, chain: str) -> int:
        """Get next nonce for wallet, with local tracking."""
        account = self.wallets[wallet_name]
        w3 = self.web3_connections[chain]
        
        key = f"{chain}_{wallet_name}"
        
        # Get on-chain nonce
        on_chain_nonce = w3.eth.get_transaction_count(account.address, 'pending')
        
        # Get tracked nonce
        tracked_nonce = self.nonce_tracker.get(key, 0)
        
        # Use the higher value
        nonce = max(on_chain_nonce, tracked_nonce)
        
        # Update tracker
        self.nonce_tracker[key] = nonce + 1
        
        return nonce
    
    def reset_nonce(self, wallet_name: str, chain: str) -> None:
        """Reset nonce tracking for a wallet."""
        key = f"{chain}_{wallet_name}"
        if key in self.nonce_tracker:
            del self.nonce_tracker[key]
        self.logger.info(f"Reset nonce for {wallet_name} on {chain}")
    
    def export_addresses(self) -> Dict[str, str]:
        """Export all wallet addresses (no private keys)."""
        return {
            name: account.address 
            for name, account in self.wallets.items()
        }
    
    def has_sufficient_balance(
        self,
        wallet_name: str,
        chain: str,
        amount: Decimal,
        token_address: Optional[str] = None,
        include_gas: bool = True
    ) -> Tuple[bool, Decimal]:
        """
        Check if wallet has sufficient balance for transaction.
        
        Args:
            wallet_name: Wallet to check
            chain: Chain identifier
            amount: Amount needed
            token_address: Token address (None for native)
            include_gas: Include gas costs in calculation
            
        Returns:
            Tuple of (has_sufficient, actual_balance)
        """
        try:
            balance = asyncio.run(
                self.get_balance(wallet_name, chain, token_address)
            )
            
            if include_gas and not token_address:
                # Reserve 0.01 ETH for gas
                gas_reserve = Decimal("0.01")
                required = amount + gas_reserve
            else:
                required = amount
            
            return balance >= required, balance
            
        except Exception as e:
            self.logger.error(f"Balance check failed: {e}")
            return False, Decimal("0")
    
    @staticmethod
    def create_new_wallet() -> Tuple[str, str]:
        """
        Create a new wallet.
        
        Returns:
            Tuple of (address, private_key)
        """
        account = Account.create()
        return account.address, account.key.hex()
    
    def load_from_env(self) -> None:
        """Load wallets from environment variables."""
        # Main trading wallet
        main_key = os.getenv("TRADING_PRIVATE_KEY")
        if main_key:
            self.add_wallet("main", main_key)
            self.logger.info("Loaded main wallet from environment")
        
        # Additional wallets
        for i in range(1, 5):
            key = os.getenv(f"TRADING_PRIVATE_KEY_{i}")
            if key:
                self.add_wallet(f"wallet_{i}", key)
                self.logger.info(f"Loaded wallet_{i} from environment")