# models/watchlist.py
"""
Watchlist management for tracking tokens marked for watching.
Provides storage and retrieval of watchlist items with metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import os

from models.token import TradingOpportunity, RiskLevel
from utils.logger import logger_manager


class WatchlistStatus(Enum):
    """Status of watchlist items."""
    WATCHING = "watching"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    REMOVED = "removed"


@dataclass
class WatchlistItem:
    """Represents an item in the watchlist."""
    token_address: str
    token_symbol: str
    token_name: Optional[str]
    chain: str
    added_at: datetime
    reason: str
    score: float
    risk_level: str
    price_when_added: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    status: WatchlistStatus = WatchlistStatus.WATCHING
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert watchlist item to dictionary for serialization."""
        return {
            'token_address': self.token_address,
            'token_symbol': self.token_symbol,
            'token_name': self.token_name,
            'chain': self.chain,
            'added_at': self.added_at.isoformat(),
            'reason': self.reason,
            'score': self.score,
            'risk_level': self.risk_level,
            'price_when_added': self.price_when_added,
            'target_price': self.target_price,
            'stop_loss': self.stop_loss,
            'status': self.status.value,
            'notes': self.notes,
            'metadata': self.metadata,
            'last_updated': self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WatchlistItem':
        """Create watchlist item from dictionary."""
        return cls(
            token_address=data['token_address'],
            token_symbol=data['token_symbol'],
            token_name=data.get('token_name'),
            chain=data['chain'],
            added_at=datetime.fromisoformat(data['added_at']),
            reason=data['reason'],
            score=data['score'],
            risk_level=data['risk_level'],
            price_when_added=data.get('price_when_added'),
            target_price=data.get('target_price'),
            stop_loss=data.get('stop_loss'),
            status=WatchlistStatus(data.get('status', 'watching')),
            notes=data.get('notes', ''),
            metadata=data.get('metadata', {}),
            last_updated=datetime.fromisoformat(data.get('last_updated', datetime.now().isoformat()))
        )


class WatchlistManager:
    """
    Manages the watchlist for tokens marked for watching.
    Provides storage, retrieval, and management of watchlist items.
    """
    
    def __init__(self, storage_file: str = "data/watchlist.json"):
        """Initialize the watchlist manager."""
        self.storage_file = storage_file
        self.logger = logger_manager.get_logger("WatchlistManager")
        self.watchlist: Dict[str, WatchlistItem] = {}
        self._ensure_storage_directory()
        self._load_watchlist()
    
    def _ensure_storage_directory(self) -> None:
        """Ensure the storage directory exists."""
        try:
            directory = os.path.dirname(self.storage_file)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
        except Exception as e:
            self.logger.error(f"Failed to create storage directory: {e}")
    
    def _load_watchlist(self) -> None:
        """Load watchlist from storage file."""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for item_data in data.get('watchlist', []):
                    try:
                        item = WatchlistItem.from_dict(item_data)
                        key = f"{item.chain}:{item.token_address}"
                        self.watchlist[key] = item
                    except Exception as e:
                        self.logger.error(f"Failed to load watchlist item: {e}")
                        
                self.logger.info(f"Loaded {len(self.watchlist)} watchlist items")
            else:
                self.logger.info("No existing watchlist file found")
                
        except Exception as e:
            self.logger.error(f"Failed to load watchlist: {e}")
            self.watchlist = {}
    
    def _save_watchlist(self) -> None:
        """Save watchlist to storage file."""
        try:
            data = {
                'watchlist': [item.to_dict() for item in self.watchlist.values()],
                'last_saved': datetime.now().isoformat()
            }
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            self.logger.debug(f"Saved {len(self.watchlist)} watchlist items")
            
        except Exception as e:
            self.logger.error(f"Failed to save watchlist: {e}")
    
    def add_to_watchlist(
        self, 
        opportunity: TradingOpportunity, 
        reason: str = "Manual addition",
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        notes: str = ""
    ) -> bool:
        """
        Add a trading opportunity to the watchlist.
        
        Args:
            opportunity: The trading opportunity to watch
            reason: Reason for adding to watchlist
            target_price: Optional target price for alerts
            stop_loss: Optional stop loss price
            notes: Additional notes
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            chain = opportunity.metadata.get('chain', 'unknown')
            key = f"{chain}:{opportunity.token.address}"
            
            # Check if already in watchlist
            if key in self.watchlist:
                self.logger.warning(f"Token already in watchlist: {opportunity.token.symbol}")
                return False
            
            # Get recommendation data
            recommendation = opportunity.metadata.get('recommendation', {})
            
            # Create watchlist item
            item = WatchlistItem(
                token_address=opportunity.token.address,
                token_symbol=opportunity.token.symbol or "UNKNOWN",
                token_name=opportunity.token.name,
                chain=chain,
                added_at=datetime.now(),
                reason=reason,
                score=recommendation.get('score', 0.0),
                risk_level=opportunity.contract_analysis.risk_level.value,
                target_price=target_price,
                stop_loss=stop_loss,
                notes=notes,
                metadata={
                    'liquidity_usd': opportunity.liquidity.liquidity_usd,
                    'dex_name': opportunity.liquidity.dex_name,
                    'social_score': opportunity.social_metrics.social_score,
                    'confidence': recommendation.get('confidence'),
                    'action': recommendation.get('action')
                }
            )
            
            self.watchlist[key] = item
            self._save_watchlist()
            
            self.logger.info(f"Added to watchlist: {opportunity.token.symbol} ({reason})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add to watchlist: {e}")
            return False
    
    def remove_from_watchlist(self, token_address: str, chain: str) -> bool:
        """
        Remove a token from the watchlist.
        
        Args:
            token_address: Token contract address
            chain: Blockchain name
            
        Returns:
            True if removed successfully, False otherwise
        """
        try:
            key = f"{chain}:{token_address}"
            
            if key in self.watchlist:
                item = self.watchlist[key]
                item.status = WatchlistStatus.REMOVED
                item.last_updated = datetime.now()
                del self.watchlist[key]
                
                self._save_watchlist()
                self.logger.info(f"Removed from watchlist: {item.token_symbol}")
                return True
            else:
                self.logger.warning(f"Token not found in watchlist: {token_address}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to remove from watchlist: {e}")
            return False
    
    def get_watchlist(self, status_filter: Optional[WatchlistStatus] = None) -> List[WatchlistItem]:
        """
        Get all watchlist items, optionally filtered by status.
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of watchlist items
        """
        try:
            items = list(self.watchlist.values())
            
            if status_filter:
                items = [item for item in items if item.status == status_filter]
            
            # Sort by most recently added
            items.sort(key=lambda x: x.added_at, reverse=True)
            
            return items
            
        except Exception as e:
            self.logger.error(f"Failed to get watchlist: {e}")
            return []
    
    def get_watchlist_item(self, token_address: str, chain: str) -> Optional[WatchlistItem]:
        """
        Get a specific watchlist item.
        
        Args:
            token_address: Token contract address
            chain: Blockchain name
            
        Returns:
            Watchlist item if found, None otherwise
        """
        try:
            key = f"{chain}:{token_address}"
            return self.watchlist.get(key)
            
        except Exception as e:
            self.logger.error(f"Failed to get watchlist item: {e}")
            return None
    
    def update_watchlist_item(
        self, 
        token_address: str, 
        chain: str, 
        **updates
    ) -> bool:
        """
        Update a watchlist item with new data.
        
        Args:
            token_address: Token contract address
            chain: Blockchain name
            **updates: Fields to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            key = f"{chain}:{token_address}"
            
            if key not in self.watchlist:
                self.logger.warning(f"Watchlist item not found: {token_address}")
                return False
            
            item = self.watchlist[key]
            
            # Update allowed fields
            allowed_updates = [
                'notes', 'target_price', 'stop_loss', 'status', 'price_when_added'
            ]
            
            for field, value in updates.items():
                if field in allowed_updates:
                    if field == 'status' and isinstance(value, str):
                        value = WatchlistStatus(value)
                    setattr(item, field, value)
            
            item.last_updated = datetime.now()
            self._save_watchlist()
            
            self.logger.info(f"Updated watchlist item: {item.token_symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update watchlist item: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get watchlist statistics."""
        try:
            total = len(self.watchlist)
            by_status = {}
            by_chain = {}
            by_risk = {}
            
            for item in self.watchlist.values():
                # Count by status
                status = item.status.value
                by_status[status] = by_status.get(status, 0) + 1
                
                # Count by chain
                chain = item.chain
                by_chain[chain] = by_chain.get(chain, 0) + 1
                
                # Count by risk level
                risk = item.risk_level
                by_risk[risk] = by_risk.get(risk, 0) + 1
            
            return {
                'total_items': total,
                'by_status': by_status,
                'by_chain': by_chain,
                'by_risk_level': by_risk,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get watchlist stats: {e}")
            return {'total_items': 0, 'error': str(e)}


# Global watchlist manager instance
watchlist_manager = WatchlistManager()