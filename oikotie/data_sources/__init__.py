"""
Data source abstractions for Finnish geodata integration.

This module provides interfaces and implementations for accessing geodata from
multiple sources including WMS services and local GeoPackage files.
"""

from .base import GeoDataSource
from .wms_source import WMSDataSource
from .geopackage_source import GeoPackageDataSource

__all__ = [
    'GeoDataSource',
    'WMSDataSource',
    'GeoPackageDataSource'
]
