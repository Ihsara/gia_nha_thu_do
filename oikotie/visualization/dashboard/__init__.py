"""
Dashboard module for Oikotie visualization package.
Provides interactive dashboard builders with enhanced UI features.

Currently Available:
- enhanced: EnhancedDashboard class
"""

# Only import modules that actually exist
try:
    from .enhanced import EnhancedDashboard
    __all__ = ['EnhancedDashboard']
except ImportError:
    __all__ = []

# Future imports (when modules are created):
# from .builder import DashboardBuilder
