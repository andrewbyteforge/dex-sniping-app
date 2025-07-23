# api/__init__.py
"""
API layer for dashboard and trading interface.
Updated to match new dashboard structure.
"""

# Import only what exists in the current version
try:
    from .dashboard_server import dashboard_server, app
    __all__ = ['dashboard_server', 'app']
except ImportError as e:
    print(f"Warning: Dashboard server import failed: {e}")
    __all__ = []