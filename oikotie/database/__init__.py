"""
Database package for Oikotie Real Estate Analytics Platform.

This package provides database management utilities, schema definitions,
and migration capabilities for the DuckDB-based analytics database.
"""

from .manager import EnhancedDatabaseManager
from .schema import DatabaseSchema
from .migrations import MigrationManager

__all__ = ['EnhancedDatabaseManager', 'DatabaseSchema', 'MigrationManager']