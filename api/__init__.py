# api/__init__.py
"""
API layer for dashboard and trading interface.
Contains the web dashboard, REST API, and WebSocket functionality.
"""

from .dashboard_server import app, dashboard_server
from .dashboard_core import DashboardServer
from .dashboard_models import (
    TradeRequest,
    OpportunityResponse,
    WatchlistAddRequest,
    PositionResponse,
    WatchlistItemResponse,
    StatsResponse,
    SystemStatusResponse,
    TradeHistoryResponse,
    ExportDataResponse
)
from .dashboard_html import get_enhanced_dashboard_html

__all__ = [
    'app',
    'dashboard_server',
    'DashboardServer',
    'TradeRequest',
    'OpportunityResponse', 
    'WatchlistAddRequest',
    'PositionResponse',
    'WatchlistItemResponse',
    'StatsResponse',
    'SystemStatusResponse',
    'TradeHistoryResponse',
    'ExportDataResponse',
    'get_enhanced_dashboard_html'
]