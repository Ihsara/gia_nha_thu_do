"""
Oikotie Visualization Package
=============================

Comprehensive visualization tools for real estate data analysis and dashboard creation.
Supports multiple cities, configurable geometry bounds, and extensible visualization types.

Package Structure:
- dashboard/: Interactive dashboard components
- maps/: Map-based visualizations  
- utils/: Shared visualization utilities
- cli/: Command-line interface

Currently Available:
- dashboard.enhanced: EnhancedDashboard class
"""

__version__ = "1.0.0"
__author__ = "Oikotie Development Team"

# Only import modules that actually exist
try:
    from .dashboard.enhanced import EnhancedDashboard
    __all__ = ["EnhancedDashboard"]
except ImportError:
    __all__ = []

# Future imports (when modules are created):
# from .dashboard.builder import DashboardBuilder
# from .maps.property_map import PropertyMap
# from .utils.config import VisualizationConfig
