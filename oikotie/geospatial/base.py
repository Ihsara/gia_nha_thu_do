"""
Base geospatial integration classes for Oikotie Real Estate Analytics Platform.

This module provides the base classes for city-specific geospatial integrators,
defining common interfaces and shared functionality.
"""

import time
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional, Any, Union
from pathlib import Path
import json
import duckdb
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
from loguru import logger

# Constants
DB_PATH = Path("data/real_estate.duckdb")
CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class DataGovernanceManager:
    """
    Manages data governance rules for API access and data storage.
    Ensures compliance with rate limiting and caching requirements.
    """
    
    def __init__(self, city: str):
        """Initialize with city-specific governance rules"""
        self.city = city
        self.last_request_time = 0
        self.config = self._load_governance_config()
    
    def _load_governance_config(self) -> Dict[str, Any]:
        """Load governance configuration from config file"""
        try:
            with open("config/config.json", "r") as f:
                config = json.load(f)
                
            # Find city-specific configuration
            for task in config.get("tasks", []):
                if task.get("city") == self.city:
                    return task.get("data_governance", {
                        "max_requests_per_second": 1,
                        "bulk_download_preference": True,
                        "cache_duration_hours": 24
                    })
            
            # Default configuration if city not found
            logger.warning(f"No governance config found for {self.city}, using defaults")
            return {
                "max_requests_per_second": 1,
                "bulk_download_preference": True,
                "cache_duration_hours": 24
            }
        except Exception as e:
            logger.error(f"Error loading governance config: {e}")
            return {
                "max_requests_per_second": 1,
                "bulk_download_preference": True,
                "cache_duration_hours": 24
            }
    
    def enforce_rate_limit(self):
        """Enforce rate limiting based on governance rules"""
        max_requests_per_second = self.config.get("max_requests_per_second", 1)
        min_interval = 1.0 / max_requests_per_second if max_requests_per_second > 0 else 1.0
        
        # Calculate time since last request
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        # If we need to wait, do so
        if elapsed < min_interval:
            wait_time = min_interval - elapsed
            # Add small random jitter (0-100ms) to prevent synchronized requests
            wait_time += random.uniform(0, 0.1)
            time.sleep(wait_time)
        
        # Update last request time
        self.last_request_time = time.time()
    
    def get_cache_path(self, data_source: str, identifier: str) -> Path:
        """Get cache file path for a specific data source and identifier"""
        cache_subdir = CACHE_DIR / self.city.lower() / data_source
        cache_subdir.mkdir(parents=True, exist_ok=True)
        
        # Create a safe filename from the identifier
        safe_id = "".join(c if c.isalnum() else "_" for c in identifier)
        return cache_subdir / f"{safe_id}.json"
    
    def is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache is still valid based on cache duration setting"""
        if not cache_path.exists():
            return False
        
        cache_duration_hours = self.config.get("cache_duration_hours", 24)
        cache_age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        
        return cache_age_hours < cache_duration_hours
    
    def log_data_lineage(self, data_source: str, records_count: int, quality_score: float = 1.0):
        """Log data lineage information to the database"""
        try:
            with duckdb.connect(str(DB_PATH)) as conn:
                # Insert lineage record with a generated ID
                conn.execute("""
                    INSERT INTO city_data_sources 
                    (id, city, data_source_type, last_updated, data_quality_score, records_count)
                    SELECT 
                        COALESCE(MAX(id), 0) + 1,
                        ?, ?, CURRENT_TIMESTAMP, ?, ?
                    FROM city_data_sources
                """, (self.city, data_source, quality_score, records_count))
                
                logger.info(f"Logged data lineage for {self.city} {data_source}: {records_count} records")
        except Exception as e:
            logger.error(f"Failed to log data lineage: {e}")


class GeospatialIntegrator(ABC):
    """
    Abstract base class for city-specific geospatial integrators.
    Defines the interface and common functionality for all city integrators.
    """
    
    def __init__(self, city: str):
        """Initialize with city name"""
        self.city = city
        self.data_governance = DataGovernanceManager(city)
        self.coordinate_bounds = self._get_coordinate_bounds()
    
    def _get_coordinate_bounds(self) -> Tuple[float, float, float, float]:
        """Get coordinate bounds for the city from config"""
        try:
            with open("config/config.json", "r") as f:
                config = json.load(f)
                
            # Find city-specific configuration
            for task in config.get("tasks", []):
                if task.get("city") == self.city:
                    bounds = task.get("coordinate_bounds")
                    if bounds and len(bounds) == 4:
                        return tuple(bounds)  # (min_lon, min_lat, max_lon, max_lat)
            
            logger.warning(f"No coordinate bounds found for {self.city}")
            return (0.0, 0.0, 0.0, 0.0)
        except Exception as e:
            logger.error(f"Error loading coordinate bounds: {e}")
            return (0.0, 0.0, 0.0, 0.0)
    
    def validate_coordinates(self, lat: float, lon: float) -> bool:
        """Validate if coordinates are within city bounds"""
        min_lon, min_lat, max_lon, max_lat = self.coordinate_bounds
        return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)
    
    def get_db_connection(self):
        """Get a connection to the DuckDB database"""
        return duckdb.connect(str(DB_PATH), read_only=False)
    
    @abstractmethod
    def geocode_addresses(self, addresses: List[str]) -> List[Tuple[str, float, float, float]]:
        """
        Geocode a list of addresses.
        
        Args:
            addresses: List of address strings to geocode
            
        Returns:
            List of tuples (address, lat, lon, quality_score)
        """
        pass
    
    @abstractmethod
    def fetch_building_data(self, bbox: Optional[Tuple[float, float, float, float]] = None) -> gpd.GeoDataFrame:
        """
        Fetch building footprint data for the city.
        
        Args:
            bbox: Optional bounding box (min_lon, min_lat, max_lon, max_lat)
                 If None, uses the city's default bounds
                 
        Returns:
            GeoDataFrame with building polygons
        """
        pass
    
    @abstractmethod
    def match_listings_to_buildings(self, listings_df: pd.DataFrame) -> pd.DataFrame:
        """
        Match listings to building footprints.
        
        Args:
            listings_df: DataFrame with listings data including lat/lon coordinates
            
        Returns:
            DataFrame with added building match information
        """
        pass
    
    def calculate_quality_score(self, listing: Dict[str, Any], match_result: Dict[str, Any]) -> float:
        """
        Calculate quality score for a geospatial match.
        
        Args:
            listing: Dictionary with listing information
            match_result: Dictionary with match results
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        # Base score starts at 0.5
        score = 0.5
        
        # If coordinates are within city bounds, add 0.2
        if self.validate_coordinates(listing.get('latitude', 0), listing.get('longitude', 0)):
            score += 0.2
        
        # If matched to a building, add 0.2
        if match_result.get('building_match', False):
            score += 0.2
        
        # If address components match (like postal code), add 0.1
        if match_result.get('address_components_match', False):
            score += 0.1
        
        return min(1.0, max(0.0, score))
    
    def update_database_with_matches(self, matches: List[Dict[str, Any]]):
        """
        Update database with building match results.
        
        Args:
            matches: List of dictionaries with match information
        """
        try:
            with self.get_db_connection() as conn:
                # Ensure the table exists
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS building_matches (
                        listing_url VARCHAR PRIMARY KEY,
                        city VARCHAR NOT NULL,
                        building_id VARCHAR,
                        match_type VARCHAR,
                        quality_score REAL,
                        match_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Prepare data for batch insert/update
                data = [(
                    match['listing_url'],
                    self.city,
                    match.get('building_id', None),
                    match.get('match_type', 'unknown'),
                    match.get('quality_score', 0.0)
                ) for match in matches]
                
                # Use a transaction for better performance
                conn.execute("BEGIN TRANSACTION")
                
                # Insert or replace records
                conn.executemany("""
                    INSERT OR REPLACE INTO building_matches
                    (listing_url, city, building_id, match_type, quality_score)
                    VALUES (?, ?, ?, ?, ?)
                """, data)
                
                conn.execute("COMMIT")
                
                logger.success(f"Updated {len(matches)} building matches for {self.city}")
        except Exception as e:
            logger.error(f"Failed to update building matches: {e}")