#!/usr/bin/env python3
"""
Multi-City Configuration Management

This module provides utilities for loading, validating, and managing
multi-city configuration for the Oikotie Real Estate Analytics Platform.

Author: Kiro AI Assistant
Created: 2025-01-19
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class CityConfiguration:
    """City-specific configuration container"""
    city: str
    enabled: bool
    url: str
    max_detail_workers: int
    rate_limit_seconds: float
    coordinate_bounds: Tuple[float, float, float, float]
    geospatial_sources: List[str]
    data_governance: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CityConfiguration':
        """Create CityConfiguration from dictionary"""
        return cls(
            city=data['city'],
            enabled=data['enabled'],
            url=data['url'],
            max_detail_workers=data['max_detail_workers'],
            rate_limit_seconds=data['rate_limit_seconds'],
            coordinate_bounds=tuple(data['coordinate_bounds']),
            geospatial_sources=data['geospatial_sources'],
            data_governance=data['data_governance']
        )
    
    def validate_coordinate_bounds(self) -> bool:
        """Validate coordinate bounds for this city"""
        bounds = self.coordinate_bounds
        
        if len(bounds) != 4:
            logger.error(f"{self.city}: Coordinate bounds must have 4 values [min_lon, min_lat, max_lon, max_lat]")
            return False
        
        min_lon, min_lat, max_lon, max_lat = bounds
        
        # Check that min < max
        if min_lon >= max_lon:
            logger.error(f"{self.city}: Minimum longitude ({min_lon}) must be less than maximum longitude ({max_lon})")
            return False
        
        if min_lat >= max_lat:
            logger.error(f"{self.city}: Minimum latitude ({min_lat}) must be less than maximum latitude ({max_lat})")
            return False
        
        # Validate specific city bounds
        expected_bounds = {
            "Helsinki": (24.5, 60.0, 25.5, 60.5),
            "Espoo": (24.4, 60.1, 24.9, 60.4)
        }
        
        if self.city in expected_bounds:
            expected = expected_bounds[self.city]
            if bounds != expected:
                logger.warning(f"{self.city} bounds {bounds} differ from expected {expected}")
        
        # Check that coordinates are within Finland
        if not (19.0 <= min_lon <= 32.0 and 19.0 <= max_lon <= 32.0):
            logger.error(f"{self.city}: Longitude bounds {min_lon}-{max_lon} are outside Finland")
            return False
        
        if not (59.0 <= min_lat <= 71.0 and 59.0 <= max_lat <= 71.0):
            logger.error(f"{self.city}: Latitude bounds {min_lat}-{max_lat} are outside Finland")
            return False
        
        return True
    
    def is_coordinate_within_bounds(self, lat: float, lon: float) -> bool:
        """Check if a coordinate is within this city's bounds"""
        min_lon, min_lat, max_lon, max_lat = self.coordinate_bounds
        return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


@dataclass
class GlobalSettings:
    """Global configuration settings"""
    database_path: str
    output_directory: str
    log_level: str
    cluster_coordination: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GlobalSettings':
        """Create GlobalSettings from dictionary"""
        return cls(
            database_path=data['database_path'],
            output_directory=data['output_directory'],
            log_level=data['log_level'],
            cluster_coordination=data.get('cluster_coordination')
        )


class MultiCityConfig:
    """Enhanced configuration system for multi-city support"""
    
    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self._raw_config = self._load_config()
        self.cities = self._load_city_configs()
        self.global_settings = self._load_global_settings()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            return {}
    
    def _load_city_configs(self) -> Dict[str, CityConfiguration]:
        """Load city configurations"""
        cities = {}
        
        if 'tasks' not in self._raw_config:
            logger.error("Configuration missing 'tasks' section")
            return cities
        
        for task_config in self._raw_config['tasks']:
            try:
                city_config = CityConfiguration.from_dict(task_config)
                cities[city_config.city] = city_config
            except KeyError as e:
                logger.error(f"Missing required field in city configuration: {e}")
            except Exception as e:
                logger.error(f"Error loading city configuration: {e}")
        
        return cities
    
    def _load_global_settings(self) -> Optional[GlobalSettings]:
        """Load global settings"""
        if 'global_settings' not in self._raw_config:
            logger.warning("No global settings found in configuration")
            return None
        
        try:
            return GlobalSettings.from_dict(self._raw_config['global_settings'])
        except Exception as e:
            logger.error(f"Error loading global settings: {e}")
            return None
    
    def get_city_config(self, city: str) -> Optional[CityConfiguration]:
        """Get configuration for specific city"""
        return self.cities.get(city)
    
    def get_enabled_cities(self) -> List[str]:
        """Get list of enabled cities for processing"""
        return [city for city, config in self.cities.items() if config.enabled]
    
    def get_all_cities(self) -> List[str]:
        """Get list of all configured cities"""
        return list(self.cities.keys())
    
    def is_city_enabled(self, city: str) -> bool:
        """Check if a city is enabled"""
        config = self.get_city_config(city)
        return config.enabled if config else False
    
    def validate_configurations(self) -> bool:
        """Validate all city configurations"""
        logger.info("Starting multi-city configuration validation")
        
        if not self.cities:
            logger.error("No city configurations found")
            return False
        
        # Check for required cities
        required_cities = ['Helsinki', 'Espoo']
        for required_city in required_cities:
            if required_city not in self.cities:
                logger.error(f"Missing configuration for required city: {required_city}")
                return False
        
        # Validate each city configuration
        validation_results = []
        for city, config in self.cities.items():
            result = self._validate_city_config(config)
            validation_results.append(result)
        
        # Validate global settings if present
        if self.global_settings:
            global_result = self._validate_global_settings(self.global_settings)
            validation_results.append(global_result)
        
        # Check for enabled cities
        enabled_cities = self.get_enabled_cities()
        if len(enabled_cities) == 0:
            logger.warning("No cities are enabled in configuration")
        else:
            logger.info(f"Enabled cities: {enabled_cities}")
        
        overall_result = all(validation_results)
        
        if overall_result:
            logger.success("Multi-city configuration validation PASSED")
        else:
            logger.error("Multi-city configuration validation FAILED")
        
        return overall_result
    
    def _validate_city_config(self, config: CityConfiguration) -> bool:
        """Validate configuration for a single city"""
        logger.info(f"Validating configuration for {config.city}")
        
        # Validate URL
        if not config.url.startswith('https://asunnot.oikotie.fi/'):
            logger.error(f"{config.city}: URL must start with 'https://asunnot.oikotie.fi/'")
            return False
        
        if config.city.lower() not in config.url.lower():
            logger.warning(f"{config.city}: City name not found in URL, please verify")
        
        # Validate coordinate bounds
        if not config.validate_coordinate_bounds():
            return False
        
        # Validate geospatial sources
        if not config.geospatial_sources:
            logger.error(f"{config.city}: 'geospatial_sources' must be non-empty list")
            return False
        
        expected_sources = ['osm_buildings', 'national_geodata']
        city_specific_source = f"{config.city.lower()}_open_data"
        
        if city_specific_source not in config.geospatial_sources:
            logger.warning(f"{config.city}: Missing city-specific data source '{city_specific_source}'")
        
        for expected in expected_sources:
            if expected not in config.geospatial_sources:
                logger.error(f"{config.city}: Missing required geospatial source '{expected}'")
                return False
        
        # Validate data governance
        governance = config.data_governance
        required_governance = ['max_requests_per_second', 'bulk_download_preference', 'cache_duration_hours']
        for field in required_governance:
            if field not in governance:
                logger.error(f"{config.city}: Missing data governance field '{field}'")
                return False
        
        if governance['max_requests_per_second'] != 1:
            logger.error(f"{config.city}: 'max_requests_per_second' must be 1 for compliance")
            return False
        
        logger.info(f"{config.city}: Configuration validation passed")
        return True
    
    def _validate_global_settings(self, settings: GlobalSettings) -> bool:
        """Validate global settings"""
        logger.info("Validating global settings")
        
        # Validate database path
        if not settings.database_path.endswith('.duckdb'):
            logger.error("Database path must end with '.duckdb'")
            return False
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if settings.log_level not in valid_log_levels:
            logger.error(f"Log level must be one of: {valid_log_levels}")
            return False
        
        logger.info("Global settings validation passed")
        return True


def load_multi_city_config(config_path: str = "config/config.json") -> MultiCityConfig:
    """Load and validate multi-city configuration"""
    config = MultiCityConfig(config_path)
    
    if not config.validate_configurations():
        logger.error("Configuration validation failed")
        raise ValueError("Invalid configuration")
    
    return config


def validate_city_coordinates(city: str, lat: float, lon: float, config: Optional[MultiCityConfig] = None) -> bool:
    """Validate that coordinates are within the specified city's bounds"""
    if config is None:
        config = load_multi_city_config()
    
    city_config = config.get_city_config(city)
    if not city_config:
        logger.error(f"No configuration found for city: {city}")
        return False
    
    return city_config.is_coordinate_within_bounds(lat, lon)


if __name__ == "__main__":
    """Command-line interface for configuration validation"""
    try:
        config = load_multi_city_config()
        logger.success("Configuration loaded and validated successfully!")
        
        enabled_cities = config.get_enabled_cities()
        logger.info(f"Enabled cities: {enabled_cities}")
        
        for city in enabled_cities:
            city_config = config.get_city_config(city)
            logger.info(f"{city}: {city_config.coordinate_bounds}")
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)