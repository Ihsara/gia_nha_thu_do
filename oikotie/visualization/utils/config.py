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
        bbox=(24.5, 60.0, 25.5, 60.5),
        database_filter="city = 'Helsinki' OR address LIKE '%Helsinki%'"
    ),
    'espoo': CityConfig(
        name='Espoo',
        center_lat=60.2055,
        center_lon=24.6522,
        zoom_level=12,
        bbox=(24.4, 60.1, 24.9, 60.4),
        database_filter="city = 'Espoo' OR address LIKE '%Espoo%'"
    ),
    'tampere': CityConfig(
        name='Tampere', 
        center_lat=61.4991,
        center_lon=23.7871,
        zoom_level=12,
        bbox=(23.6, 61.4, 23.9, 61.6),
        database_filter="city = 'Tampere' OR address LIKE '%Tampere%'"
    ),
    'turku': CityConfig(
        name='Turku',
        center_lat=60.4518,
        center_lon=22.2666,
        zoom_level=12,
        bbox=(22.1, 60.3, 22.4, 60.6),
        database_filter="city = 'Turku' OR address LIKE '%Turku%'"
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


def validate_city_config(city_config: CityConfig) -> bool:
    """Validate a city configuration for completeness and correctness."""
    try:
        # Check required fields
        if not city_config.name or not isinstance(city_config.name, str):
            raise ValueError(f"Invalid city name: {city_config.name}")
        
        # Check coordinates are valid
        if not (-90 <= city_config.center_lat <= 90):
            raise ValueError(f"Invalid latitude: {city_config.center_lat}")
        
        if not (-180 <= city_config.center_lon <= 180):
            raise ValueError(f"Invalid longitude: {city_config.center_lon}")
        
        # Check zoom level is reasonable
        if not (1 <= city_config.zoom_level <= 20):
            raise ValueError(f"Invalid zoom level: {city_config.zoom_level}")
        
        # Check bounding box if provided
        if city_config.bbox:
            if len(city_config.bbox) != 4:
                raise ValueError(f"Bounding box must have 4 coordinates: {city_config.bbox}")
            
            min_lon, min_lat, max_lon, max_lat = city_config.bbox
            
            if not (min_lon < max_lon and min_lat < max_lat):
                raise ValueError(f"Invalid bounding box coordinates: {city_config.bbox}")
            
            if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
                raise ValueError(f"Invalid longitude bounds: {min_lon}, {max_lon}")
            
            if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
                raise ValueError(f"Invalid latitude bounds: {min_lat}, {max_lat}")
        
        # Check database filter if provided
        if city_config.database_filter and not isinstance(city_config.database_filter, str):
            raise ValueError(f"Database filter must be a string: {city_config.database_filter}")
        
        return True
        
    except Exception as e:
        print(f"❌ City configuration validation failed for {city_config.name}: {e}")
        return False


def get_available_cities() -> list:
    """Get list of available city names."""
    return list(CITY_CONFIGS.keys())


def validate_all_city_configs() -> Dict[str, bool]:
    """Validate all predefined city configurations."""
    results = {}
    for city_name, city_config in CITY_CONFIGS.items():
        results[city_name] = validate_city_config(city_config)
    return results


def get_city_database_filter(city: str) -> str:
    """Get database filter query for a specific city."""
    city_config = get_city_config(city)
    return city_config.database_filter or f"city = '{city_config.name}'"


def get_city_bounds(city: str) -> tuple:
    """Get bounding box coordinates for a specific city."""
    city_config = get_city_config(city)
    if not city_config.bbox:
        raise ValueError(f"No bounding box defined for city: {city}")
    return city_config.bbox


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
    print("\n🏙️ Available Cities:")
    for city_name in get_available_cities():
        city = get_city_config(city_name)
        print(f"  • {city.name}: {city.center_lat}, {city.center_lon} (zoom: {city.zoom_level})")
        print(f"    Bounds: {city.bbox}")
        print(f"    Filter: {city.database_filter}")
    
    # Test configuration validation
    print("\n✅ Configuration Validation:")
    validation_results = validate_all_city_configs()
    for city_name, is_valid in validation_results.items():
        status = "✅ Valid" if is_valid else "❌ Invalid"
        print(f"  • {city_name}: {status}")
    
    # Test specific city functions
    print("\n🔍 Testing Espoo Configuration:")
    try:
        espoo_config = get_city_config('espoo')
        print(f"  • Name: {espoo_config.name}")
        print(f"  • Center: {espoo_config.center_lat}, {espoo_config.center_lon}")
        print(f"  • Bounds: {get_city_bounds('espoo')}")
        print(f"  • Database Filter: {get_city_database_filter('espoo')}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test output configuration
    print(f"\n📁 Output Configuration:")
    output = OutputConfig()
    print(f"  • Dashboard dir: {output.dashboard_dir}")
    print(f"  • Maps dir: {output.maps_dir}")
    
    # Test database configuration
    print(f"\n🗄️ Database Configuration:")
    db = DatabaseConfig()
    print(f"  • Database: {db.duckdb_path} ({'✅ exists' if db.validate_database() else '❌ missing'})")
    print(f"  • Listings table: {db.listings_table}")
