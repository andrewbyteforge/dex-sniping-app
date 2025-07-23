# api/__init__.py
"""
API layer for dashboard and trading interface.
"""

# Import only what exists in the minimal version
from .dashboard_server import DashboardServer

__all__ = ['DashboardServer']