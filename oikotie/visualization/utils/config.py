#!/usr/bin/env python3
"""
Configuration utilities for the Oikotie visualization package.

This module provides city configurations, default settings, and output path management
for all visualization components.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import os


class CityConfig:
    """Configuration class for different cities."""
    
    def __init__(
        self,
        name: str,
        center_lat: float,
        center_lon: float,
        zoom_level: int = 12,
        bbox: Optional[tuple] = None,
        database_filter: Optional[str] = None
    ):
        self.name = name
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.zoom_level = zoom_level
        self.bbox = bbox
        self.database_filter = database_filter


# Predefined city configurations
CITY_CONFIGS = {
    'helsinki': CityConfig(
        name='Helsinki',
        center_lat=60.1695,
        center_lon=24.9354,
        zoom_level=12,
        bbox=(24.7, 60.1, 25.2, 60.3),
        database_filter="address LIKE '%Helsinki%'"
    ),
    'tampere': CityConfig(
        name='Tampere', 
        center_lat=61.4991,
        center_lon=23.7871,
        zoom_level=12,
        bbox=(23.6, 61.4, 23.9, 61.6),
        database_filter="address LIKE '%Tampere%'"
    ),
    'turku': CityConfig(
        name='Turku',
        center_lat=60.4518,
        center_lon=22.2666,
        zoom_level=12,
        bbox=(22.1, 60.3, 22.4, 60.6),
        database_filter="address LIKE '%Turku%'"
    )
}


class OutputConfig:
    """Configuration for output paths and file management."""
    
    def __init__(self, base_output_dir: str = "output"):
        self.base_output_dir = Path(base_output_dir)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create all required output directories."""
        subdirs = [
            'visualization/dashboard',
            'visualization/maps', 
            'validation',
            'data/exports',
            'logs'
        ]
        
        for subdir in subdirs:
            full_path = self.base_output_dir / subdir
            full_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def dashboard_dir(self) -> Path:
        """Dashboard output directory."""
        return self.base_output_dir / 'visualization' / 'dashboard'
    
    @property
    def maps_dir(self) -> Path:
        """Maps output directory."""
        return self.base_output_dir / 'visualization' / 'maps'
    
    @property
    def validation_dir(self) -> Path:
        """Validation output directory."""
        return self.base_output_dir / 'validation'
    
    @property
    def data_dir(self) -> Path:
        """Data exports directory."""
        return self.base_output_dir / 'data' / 'exports'
    
    @property
    def logs_dir(self) -> Path:
        """Logs directory."""
        return self.base_output_dir / 'logs'


class DatabaseConfig:
    """Database configuration settings."""
    
    def __init__(self):
        self.duckdb_path = Path("data/real_estate.duckdb")
        self.cache_dir = Path("cache")
        
        # Table names
        self.listings_table = "listings"
        self.buildings_table = "osm_buildings"
        self.addresses_table = "address_locations"
        
        # Connection settings
        self.connection_timeout = 30
        self.read_only = True
    
    def validate_database(self) -> bool:
        """Check if database file exists and is accessible."""
        return self.duckdb_path.exists() and self.duckdb_path.is_file()


def get_city_config(city: str) -> CityConfig:
    """Get configuration for a specific city."""
    city_lower = city.lower()
    if city_lower not in CITY_CONFIGS:
        raise ValueError(f"Unknown city: {city}. Available: {list(CITY_CONFIGS.keys())}")
    return CITY_CONFIGS[city_lower]


def get_default_config() -> Dict[str, Any]:
    """Get default configuration dictionary."""
    return {
        'city': get_city_config('helsinki'),
        'output': OutputConfig(),
        'database': DatabaseConfig()
    }


if __name__ == "__main__":
    # Demo usage
    print("🔧 Oikotie Configuration Demo")
    print("=" * 40)
    
    # Test city configurations
    for city_name in CITY_CONFIGS.keys():
        city = get_city_config(city_name)
        print(f"🏙️ {city.name}: {city.center_lat}, {city.center_lon}")
    
    # Test output configuration
    output = OutputConfig()
    print(f"📁 Dashboard dir: {output.dashboard_dir}")
    
    # Test database configuration
    db = DatabaseConfig()
    print(f"🗄️ Database: {db.duckdb_path} ({'✅ exists' if db.validate_database() else '❌ missing'})")
