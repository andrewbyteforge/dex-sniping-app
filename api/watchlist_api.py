# api/watchlist_api.py
"""
Watchlist API endpoints for DEX sniping dashboard.
Handles server-side watchlist storage and management.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import json
import os
import asyncio
from pathlib import Path

# Pydantic models for API
class WatchlistToken(BaseModel):
    """Model for a token in the watchlist."""
    token_symbol: str = Field(..., description="Token symbol")
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")
    risk_level: str = Field(default="unknown", description="Risk assessment level")
    recommendation: str = Field(default="UNKNOWN", description="Trading recommendation")
    confidence: str = Field(default="UNKNOWN", description="Confidence level")
    score: float = Field(default=0.0, ge=0.0, le=1.0, description="Analysis score")
    liquidity_usd: float = Field(default=0.0, ge=0.0, description="Liquidity in USD")
    added_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="When added to watchlist")
    dex_name: str = Field(default="Unknown", description="DEX name")
    reasons: List[str] = Field(default_factory=list, description="Analysis reasons")
    warnings: List[str] = Field(default_factory=list, description="Risk warnings")

class WatchlistResponse(BaseModel):
    """Response model for watchlist operations."""
    success: bool
    message: str
    count: int
    tokens: List[WatchlistToken] = Field(default_factory=list)

class AddTokenRequest(BaseModel):
    """Request model for adding a token to watchlist."""
    token_symbol: str
    token_address: str
    chain: str = "unknown"
    risk_level: str = "unknown"
    recommendation: str = "UNKNOWN"
    confidence: str = "UNKNOWN"
    score: float = 0.0
    liquidity_usd: float = 0.0
    dex_name: str = "Unknown"
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

# Create router
router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

class WatchlistManager:
    """
    Server-side watchlist management.
    Handles persistent storage and operations for user watchlists.
    """
    
    def __init__(self, storage_dir: str = "data"):
        """
        Initialize the watchlist manager.
        
        Args:
            storage_dir (str): Directory to store watchlist files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.max_items = 100
        self.watchlists: Dict[str, List[Dict]] = {}  # In-memory cache
        
    def _get_user_file(self, user_id: str = "default") -> Path:
        """
        Get the file path for a user's watchlist.
        
        Args:
            user_id (str): User identifier
            
        Returns:
            Path: Path to user's watchlist file
        """
        return self.storage_dir / f"watchlist_{user_id}.json"
    
    async def load_watchlist(self, user_id: str = "default") -> List[Dict]:
        """
        Load watchlist from storage.
        
        Args:
            user_id (str): User identifier
            
        Returns:
            List[Dict]: User's watchlist tokens
            
        Raises:
            Exception: If loading fails
        """
        try:
            user_file = self._get_user_file(user_id)
            
            if not user_file.exists():
                self.watchlists[user_id] = []
                return []
            
            with open(user_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Validate data structure
            if isinstance(data, dict) and 'tokens' in data:
                tokens = data['tokens']
            elif isinstance(data, list):
                tokens = data
            else:
                tokens = []
            
            # Cache in memory
            self.watchlists[user_id] = tokens
            return tokens
            
        except Exception as e:
            print(f"Error loading watchlist for {user_id}: {e}")
            self.watchlists[user_id] = []
            return []
    
    async def save_watchlist(self, user_id: str = "default") -> bool:
        """
        Save watchlist to storage.
        
        Args:
            user_id (str): User identifier
            
        Returns:
            bool: Success status
            
        Raises:
            Exception: If saving fails
        """
        try:
            user_file = self._get_user_file(user_id)
            tokens = self.watchlists.get(user_id, [])
            
            data = {
                "user_id": user_id,
                "updated_at": datetime.now().isoformat(),
                "count": len(tokens),
                "tokens": tokens
            }
            
            # Write atomically
            temp_file = user_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            temp_file.replace(user_file)
            return True
            
        except Exception as e:
            print(f"Error saving watchlist for {user_id}: {e}")
            return False
    
    async def add_token(self, token_data: Dict, user_id: str = "default") -> tuple[bool, str]:
        """
        Add a token to the watchlist.
        
        Args:
            token_data (Dict): Token information
            user_id (str): User identifier
            
        Returns:
            tuple[bool, str]: Success status and message
        """
        try:
            # Load current watchlist
            await self.load_watchlist(user_id)
            tokens = self.watchlists.get(user_id, [])
            
            # Check if already exists
            token_address = token_data.get('token_address', '')
            exists = any(token.get('token_address') == token_address for token in tokens)
            
            if exists:
                return False, f"Token {token_data.get('token_symbol', 'unknown')} already in watchlist"
            
            # Add timestamp
            token_data['added_at'] = datetime.now().isoformat()
            
            # Add to beginning of list
            tokens.insert(0, token_data)
            
            # Limit size
            if len(tokens) > self.max_items:
                tokens = tokens[:self.max_items]
                
            self.watchlists[user_id] = tokens
            
            # Save to storage
            success = await self.save_watchlist(user_id)
            
            if success:
                return True, f"Added {token_data.get('token_symbol', 'token')} to watchlist"
            else:
                return False, "Failed to save watchlist"
                
        except Exception as e:
            return False, f"Error adding token: {str(e)}"
    
    async def remove_token(self, token_address: str, user_id: str = "default") -> tuple[bool, str]:
        """
        Remove a token from the watchlist.
        
        Args:
            token_address (str): Token contract address
            user_id (str): User identifier
            
        Returns:
            tuple[bool, str]: Success status and message
        """
        try:
            # Load current watchlist
            await self.load_watchlist(user_id)
            tokens = self.watchlists.get(user_id, [])
            
            # Find and remove token
            original_count = len(tokens)
            tokens = [token for token in tokens if token.get('token_address') != token_address]
            
            if len(tokens) == original_count:
                return False, "Token not found in watchlist"
            
            self.watchlists[user_id] = tokens
            
            # Save to storage
            success = await self.save_watchlist(user_id)
            
            if success:
                return True, "Token removed from watchlist"
            else:
                return False, "Failed to save watchlist"
                
        except Exception as e:
            return False, f"Error removing token: {str(e)}"
    
    async def clear_watchlist(self, user_id: str = "default") -> tuple[bool, str]:
        """
        Clear all tokens from the watchlist.
        
        Args:
            user_id (str): User identifier
            
        Returns:
            tuple[bool, str]: Success status and message
        """
        try:
            self.watchlists[user_id] = []
            success = await self.save_watchlist(user_id)
            
            if success:
                return True, "Watchlist cleared"
            else:
                return False, "Failed to clear watchlist"
                
        except Exception as e:
            return False, f"Error clearing watchlist: {str(e)}"
    
    async def get_watchlist(self, user_id: str = "default") -> List[Dict]:
        """
        Get the current watchlist.
        
        Args:
            user_id (str): User identifier
            
        Returns:
            List[Dict]: Current watchlist tokens
        """
        try:
            await self.load_watchlist(user_id)
            return self.watchlists.get(user_id, [])
        except Exception as e:
            print(f"Error getting watchlist: {e}")
            return []

# Global watchlist manager instance
watchlist_manager = WatchlistManager()

# Dependency to get current user (simplified - no auth for now)
async def get_current_user() -> str:
    """Get current user ID (simplified implementation)."""
    return "default"

@router.get("/", response_model=WatchlistResponse)
async def get_watchlist(user_id: str = Depends(get_current_user)):
    """
    Get the user's current watchlist.
    
    Args:
        user_id (str): User identifier
        
    Returns:
        WatchlistResponse: Current watchlist data
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        tokens = await watchlist_manager.get_watchlist(user_id)
        
        # Convert to Pydantic models
        watchlist_tokens = []
        for token_data in tokens:
            try:
                watchlist_token = WatchlistToken(**token_data)
                watchlist_tokens.append(watchlist_token)
            except Exception as validation_error:
                print(f"Error validating token data: {validation_error}")
                continue
        
        return WatchlistResponse(
            success=True,
            message="Watchlist retrieved successfully",
            count=len(watchlist_tokens),
            tokens=watchlist_tokens
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get watchlist: {str(e)}")

@router.post("/add", response_model=WatchlistResponse)
async def add_token_to_watchlist(
    request: AddTokenRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Add a token to the watchlist.
    
    Args:
        request (AddTokenRequest): Token data to add
        user_id (str): User identifier
        
    Returns:
        WatchlistResponse: Operation result
        
    Raises:
        HTTPException: If addition fails
    """
    try:
        token_data = request.dict()
        success, message = await watchlist_manager.add_token(token_data, user_id)
        
        if success:
            tokens = await watchlist_manager.get_watchlist(user_id)
            watchlist_tokens = [WatchlistToken(**token) for token in tokens]
            
            return WatchlistResponse(
                success=True,
                message=message,
                count=len(watchlist_tokens),
                tokens=watchlist_tokens
            )
        else:
            return WatchlistResponse(
                success=False,
                message=message,
                count=0,
                tokens=[]
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add token: {str(e)}")

@router.delete("/{token_address}", response_model=WatchlistResponse)
async def remove_token_from_watchlist(
    token_address: str,
    user_id: str = Depends(get_current_user)
):
    """
    Remove a token from the watchlist.
    
    Args:
        token_address (str): Token contract address to remove
        user_id (str): User identifier
        
    Returns:
        WatchlistResponse: Operation result
        
    Raises:
        HTTPException: If removal fails
    """
    try:
        success, message = await watchlist_manager.remove_token(token_address, user_id)
        
        tokens = await watchlist_manager.get_watchlist(user_id)
        watchlist_tokens = [WatchlistToken(**token) for token in tokens]
        
        return WatchlistResponse(
            success=success,
            message=message,
            count=len(watchlist_tokens),
            tokens=watchlist_tokens
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove token: {str(e)}")

@router.delete("/", response_model=WatchlistResponse)
async def clear_watchlist_endpoint(user_id: str = Depends(get_current_user)):
    """
    Clear all tokens from the watchlist.
    
    Args:
        user_id (str): User identifier
        
    Returns:
        WatchlistResponse: Operation result
        
    Raises:
        HTTPException: If clearing fails
    """
    try:
        success, message = await watchlist_manager.clear_watchlist(user_id)
        
        return WatchlistResponse(
            success=success,
            message=message,
            count=0,
            tokens=[]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear watchlist: {str(e)}")

@router.get("/export", response_model=dict)
async def export_watchlist(user_id: str = Depends(get_current_user)):
    """
    Export the user's watchlist.
    
    Args:
        user_id (str): User identifier
        
    Returns:
        dict: Exported watchlist data
        
    Raises:
        HTTPException: If export fails
    """
    try:
        tokens = await watchlist_manager.get_watchlist(user_id)
        
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "user_id": user_id,
            "count": len(tokens),
            "tokens": tokens,
            "version": "1.0"
        }
        
        return export_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export watchlist: {str(e)}")

@router.get("/stats", response_model=dict)
async def get_watchlist_stats(user_id: str = Depends(get_current_user)):
    """
    Get watchlist statistics.
    
    Args:
        user_id (str): User identifier
        
    Returns:
        dict: Watchlist statistics
        
    Raises:
        HTTPException: If stats retrieval fails
    """
    try:
        tokens = await watchlist_manager.get_watchlist(user_id)
        
        # Calculate statistics
        total_tokens = len(tokens)
        chains = {}
        risk_levels = {}
        recommendations = {}
        
        for token in tokens:
            # Count by chain
            chain = token.get('chain', 'unknown')
            chains[chain] = chains.get(chain, 0) + 1
            
            # Count by risk level
            risk = token.get('risk_level', 'unknown')
            risk_levels[risk] = risk_levels.get(risk, 0) + 1
            
            # Count by recommendation
            rec = token.get('recommendation', 'UNKNOWN')
            recommendations[rec] = recommendations.get(rec, 0) + 1
        
        return {
            "total_tokens": total_tokens,
            "chains": chains,
            "risk_levels": risk_levels,
            "recommendations": recommendations,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")