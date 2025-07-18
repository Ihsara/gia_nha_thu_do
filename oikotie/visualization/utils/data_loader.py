#!/usr/bin/env python3
"""
Data loading utilities for the Oikotie visualization package.

This module provides database connection utilities, data loading functions,
and common data processing operations.
"""

import duckdb
import pandas as pd
import geopandas as gpd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json
from functools import lru_cache
import logging

from .config import DatabaseConfig


class DataLoader:
    """Main data loading class for database operations."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.config = DatabaseConfig()
        if db_path:
            self.config.duckdb_path = Path(db_path)
        
        if not self.config.validate_database():
            raise FileNotFoundError(f"Database not found: {self.config.duckdb_path}")
        
        self.connection = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging for data operations."""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def connect(self) -> duckdb.DuckDBPyConnection:
        """Establish database connection."""
        if self.connection is None:
            try:
                self.connection = duckdb.connect(
                    str(self.config.duckdb_path),
                    read_only=self.config.read_only
                )
                self.logger.info(f"✅ Connected to database: {self.config.duckdb_path}")
            except Exception as e:
                self.logger.error(f"❌ Database connection failed: {e}")
                raise
        return self.connection
    
    def disconnect(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.logger.info("🔌 Database connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def get_table_info(self, table_name: str) -> pd.DataFrame:
        """Get information about a table structure."""
        conn = self.connect()
        query = f"DESCRIBE {table_name}"
        return conn.execute(query).fetchdf()
    
    def get_table_count(self, table_name: str) -> int:
        """Get row count for a table."""
        conn = self.connect()
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        result = conn.execute(query).fetchone()
        return result[0] if result else 0
    
    @lru_cache(maxsize=10)
    def get_listings_sample(self, limit: int = 10, city_filter: Optional[str] = None) -> pd.DataFrame:
        """Get a sample of listings data."""
        conn = self.connect()
        
        query = f"SELECT * FROM {self.config.listings_table}"
        if city_filter:
            query += f" WHERE address LIKE '%{city_filter}%'"
        query += f" LIMIT {limit}"
        
        self.logger.info(f"Loading {limit} listings (filter: {city_filter})")
        return conn.execute(query).fetchdf()
    
    @lru_cache(maxsize=10)
    def get_buildings_sample(self, limit: int = 100, bbox: Optional[Tuple[float, float, float, float]] = None) -> gpd.GeoDataFrame:
        """Get a sample of buildings data."""
        conn = self.connect()
        
        query = f"SELECT * FROM {self.config.buildings_table}"
        if bbox:
            min_x, min_y, max_x, max_y = bbox
            query += f" WHERE ST_Within(ST_GeomFromText(geometry), ST_GeomFromText('POLYGON(({min_x} {min_y}, {max_x} {min_y}, {max_x} {max_y}, {min_x} {max_y}, {min_x} {min_y}))')) "
        query += f" LIMIT {limit}"
        
        self.logger.info(f"Loading {limit} buildings (bbox: {bbox})")
        df = conn.execute(query).fetchdf()
        
        # Convert to GeoDataFrame
        if 'geometry' in df.columns and len(df) > 0:
            df['geometry'] = gpd.GeoSeries.from_wkt(df['geometry'])
            return gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
        return gpd.GeoDataFrame(df)
    
    def get_full_listings(self, city_filter: Optional[str] = None) -> pd.DataFrame:
        """Get all listings data."""
        conn = self.connect()
        
        query = f"SELECT * FROM {self.config.listings_table}"
        if city_filter:
            query += f" WHERE address LIKE '%{city_filter}%'"
        
        self.logger.info(f"Loading all listings (filter: {city_filter})")
        return conn.execute(query).fetchdf()
    
    def get_address_geocoded(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Get address location data."""
        conn = self.connect()
        
        query = f"SELECT * FROM {self.config.addresses_table}"
        if limit:
            query += f" LIMIT {limit}"
        
        self.logger.info(f"Loading address data (limit: {limit})")
        return conn.execute(query).fetchdf()


# Convenience functions for quick data access
def load_sample_data(limit: int = 10, city: str = "Helsinki") -> Dict[str, Any]:
    """Load sample data for quick testing and validation."""
    with DataLoader() as loader:
        listings = loader.get_listings_sample(limit=limit, city_filter=city)
        buildings = loader.get_buildings_sample(limit=limit*10)
        
        return {
            'listings': listings,
            'buildings': buildings,
            'summary': {
                'listings_count': len(listings),
                'buildings_count': len(buildings),
                'city_filter': city
            }
        }


def validate_database_schema() -> Dict[str, Any]:
    """Validate database schema and return structure info."""
    with DataLoader() as loader:
        tables = ['listings', 'osm_buildings', 'address_locations']
        schema_info = {}
        
        for table in tables:
            try:
                info = loader.get_table_info(table)
                count = loader.get_table_count(table)
                schema_info[table] = {
                    'columns': info.to_dict('records'),
                    'row_count': count,
                    'exists': True
                }
            except Exception as e:
                schema_info[table] = {
                    'error': str(e),
                    'exists': False
                }
        
        return schema_info


if __name__ == "__main__":
    print("🔧 Data Loader Demo")
    print("=" * 30)
    
    try:
        # Test database connection
        with DataLoader() as loader:
            print("✅ Database connection successful")
            
            # Test sample data loading
            sample = load_sample_data(limit=5)
            print(f"📊 Sample data loaded:")
            print(f"  - Listings: {sample['summary']['listings_count']}")
            print(f"  - Buildings: {sample['summary']['buildings_count']}")
            
            # Test schema validation
            schema = validate_database_schema()
            print(f"🗄️ Database schema:")
            for table, info in schema.items():
                if info['exists']:
                    print(f"  - {table}: {info['row_count']} rows")
                else:
                    print(f"  - {table}: ❌ {info['error']}")
                    
    except Exception as e:
        print(f"❌ Error: {e}")
