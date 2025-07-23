# api/dashboard_models.py
"""
Pydantic models for dashboard API requests and responses.
Contains all data models used by the dashboard endpoints.
"""

from typing import Optional
from pydantic import BaseModel


class TradeRequest(BaseModel):
    """
    Request model for trade execution.
    
    Attributes:
        token_address: The token contract address
        token_symbol: The token symbol (e.g., DOGE, PEPE)  
        amount: The amount to trade
        chain: The blockchain network (default: ethereum)
        order_type: The type of order (default: market)
    """
    
    token_address: str
    token_symbol: str
    amount: float
    chain: str = "ethereum"
    order_type: str = "market"


class OpportunityResponse(BaseModel):
    """
    Response model for trading opportunities.
    
    Attributes:
        token_symbol: The token symbol
        token_address: The token contract address
        chain: The blockchain network
        risk_level: The assessed risk level
        recommendation: The trading recommendation
        confidence: The confidence level of the recommendation
        score: The opportunity score (0.0 to 1.0)
        liquidity_usd: The liquidity in USD
        age_minutes: Age of the opportunity in minutes
    """
    
    token_symbol: str
    token_address: str
    chain: str
    risk_level: str
    recommendation: str
    confidence: str
    score: float
    liquidity_usd: float
    age_minutes: int


class WatchlistAddRequest(BaseModel):
    """
    Request model for adding tokens to watchlist.
    
    Attributes:
        token_address: The token contract address
        token_symbol: The token symbol
        chain: The blockchain network
        reason: Reason for watching this token
        target_price: Optional target price in USD
        stop_loss: Optional stop loss price in USD
        notes: Additional notes about the token
    """
    
    token_address: str
    token_symbol: str
    chain: str
    reason: str = "Manual addition"
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: str = ""


class PositionResponse(BaseModel):
    """
    Response model for trading positions.
    
    Attributes:
        token_symbol: The token symbol
        amount: The position amount
        entry_price: The entry price
        current_price: The current price
        pnl: The profit/loss amount
        pnl_percentage: The profit/loss percentage
    """
    
    token_symbol: str
    amount: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_percentage: float


class WatchlistItemResponse(BaseModel):
    """
    Response model for watchlist items.
    
    Attributes:
        token_symbol: The token symbol
        token_address: The token contract address
        chain: The blockchain network
        status: The watchlist item status
        reason: Reason for watching
        target_price: Target price if set
        stop_loss: Stop loss price if set
        notes: Additional notes
        added_at: When the item was added
        last_updated: When the item was last updated
    """
    
    token_symbol: str
    token_address: str
    chain: str
    status: str
    reason: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: str = ""
    added_at: str
    last_updated: str


class StatsResponse(BaseModel):
    """
    Response model for system statistics.
    
    Attributes:
        total_opportunities: Total number of opportunities detected
        high_confidence: Number of high confidence opportunities
        active_chains: Number of active blockchain networks
        analysis_rate: Analysis rate per minute
        uptime_hours: System uptime in hours
        connected_clients: Number of connected WebSocket clients
        portfolio: Portfolio summary data
    """
    
    total_opportunities: int
    high_confidence: int
    active_chains: int
    analysis_rate: int
    uptime_hours: float
    connected_clients: int
    portfolio: dict


class SystemStatusResponse(BaseModel):
    """
    Response model for detailed system status.
    
    Attributes:
        status: Overall system status
        uptime_seconds: System uptime in seconds
        connected_clients: Number of connected clients
        trading_executor_initialized: Whether trading executor is available
        position_manager_initialized: Whether position manager is available
        opportunities_in_queue: Number of opportunities in queue
        watchlist_items: Number of items in watchlist
        chains: Status of each blockchain network
    """
    
    status: str
    uptime_seconds: float
    connected_clients: int
    trading_executor_initialized: bool
    position_manager_initialized: bool
    opportunities_in_queue: int
    watchlist_items: int
    chains: dict


class TradeHistoryResponse(BaseModel):
    """
    Response model for trade history.
    
    Attributes:
        trades: List of trade records
        status: Response status
        error: Error message if any
    """
    
    trades: list
    status: str
    error: Optional[str] = None


class ExportDataResponse(BaseModel):
    """
    Response model for data export.
    
    Attributes:
        timestamp: Export timestamp
        stats: System statistics
        opportunities: List of opportunities
        watchlist: List of watchlist items
        trade_history: List of trades
        positions: List of positions
    """
    
    timestamp: str
    stats: dict
    opportunities: list
    watchlist: list
    trade_history: list
    positions: list