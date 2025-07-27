"""
Dashboard module for Oikotie visualization package.
Provides interactive dashboard builders with enhanced UI features.

Currently Available:
- enhanced: EnhancedDashboard class
- multi_city: MultiCityDashboard class (supports Espoo and comparative visualizations)
"""

# Only import modules that actually exist
try:
    from .enhanced import EnhancedDashboard
    from .multi_city import MultiCityDashboard
    __all__ = ['EnhancedDashboard', 'MultiCityDashboard']
except ImportError as e:
    print(f"Warning: Could not import all dashboard modules: {e}")
    __all__ = []

# Future imports (when modules are created):
# from .builder import DashboardBuilder
