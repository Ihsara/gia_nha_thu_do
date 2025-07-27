"""
Multi-City Database Schema Migration for Espoo Expansion

This module provides database migration capabilities to enhance the schema
for improved multi-city support, including city-specific validation,
coordinate bounds checking, and data lineage tracking.
"""

import duckdb
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
from loguru import logger
from dataclasses import dataclass

from .migrations import Migration, MigrationManager


@dataclass
class CityBounds:
    """City coordinate bounds for validation"""
    name: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


class MultiCityMigrationManager(MigrationManager):
    """Enhanced migration manager for multi-city support"""
    
    def __init__(self, db_path: str = "data/real_estate.duckdb"):
        super().__init__(db_path)
        self.city_bounds = self._define_city_bounds()
        self.multi_city_migrations = self._define_multi_city_migrations()
    
    def _define_city_bounds(self) -> Dict[str, CityBounds]:
        """Define coordinate bounds for supported cities"""
        return {
            'Helsinki': CityBounds('Helsinki', 60.0, 60.5, 24.5, 25.5),
            'Espoo': CityBounds('Espoo', 60.1, 60.4, 24.4, 24.9)
        }
    
    def _define_multi_city_migrations(self) -> List[Migration]:
        """Define multi-city specific migrations"""
        return [
            Migration(
                version="006_add_city_validation_columns",
                description="Add city-specific validation columns to listings table",
                upgrade_sql="""
                    -- Add city validation columns
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS city_validated BOOLEAN DEFAULT FALSE;
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS coordinate_source VARCHAR(50);
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS geospatial_quality_score REAL;
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS coordinate_validation_error TEXT;
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_coordinate_validation TIMESTAMP;
                """,
                downgrade_sql="""
                    ALTER TABLE listings DROP COLUMN IF EXISTS city_validated;
                    ALTER TABLE listings DROP COLUMN IF EXISTS coordinate_source;
                    ALTER TABLE listings DROP COLUMN IF EXISTS geospatial_quality_score;
                    ALTER TABLE listings DROP COLUMN IF EXISTS coordinate_validation_error;
                    ALTER TABLE listings DROP COLUMN IF EXISTS last_coordinate_validation;
                """,
                validation_sql="SELECT city_validated, coordinate_source FROM listings LIMIT 1;"
            ),
            Migration(
                version="007_create_coordinate_validation_function",
                description="Create coordinate bounds validation function for multi-city support",
                upgrade_sql="""
                    -- Create city bounds reference table
                    CREATE TABLE IF NOT EXISTS city_coordinate_bounds (
                        city VARCHAR(50) PRIMARY KEY,
                        min_latitude REAL NOT NULL,
                        max_latitude REAL NOT NULL,
                        min_longitude REAL NOT NULL,
                        max_longitude REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- Insert city bounds data
                    INSERT OR REPLACE INTO city_coordinate_bounds 
                    (city, min_latitude, max_latitude, min_longitude, max_longitude) VALUES
                    ('Helsinki', 60.0, 60.5, 24.5, 25.5),
                    ('Espoo', 60.1, 60.4, 24.4, 24.9);
                """,
                downgrade_sql="""
                    DROP TABLE IF EXISTS city_coordinate_bounds;
                """,
                validation_sql="SELECT COUNT(*) FROM city_coordinate_bounds;"
            ),
            Migration(
                version="008_add_multi_city_spatial_indexes",
                description="Add spatial indexes optimized for multi-city queries",
                upgrade_sql="""
                    -- Create multi-city spatial indexes
                    CREATE INDEX IF NOT EXISTS idx_listings_city_coordinates ON listings(city, latitude, longitude);
                    CREATE INDEX IF NOT EXISTS idx_listings_city_validated ON listings(city, city_validated);
                    CREATE INDEX IF NOT EXISTS idx_listings_geospatial_quality ON listings(geospatial_quality_score);
                    CREATE INDEX IF NOT EXISTS idx_listings_coordinate_source ON listings(coordinate_source);
                    CREATE INDEX IF NOT EXISTS idx_listings_city_scraped_validated ON listings(city, scraped_at, city_validated);
                    
                    -- Note: Spatial index on geometry column would be created here if geometry column exists
                    -- DuckDB spatial indexes are handled automatically when spatial extension is loaded
                    
                    -- Create compound indexes for common multi-city queries
                    CREATE INDEX IF NOT EXISTS idx_listings_city_price_size ON listings(city, price_eur, size_m2);
                    CREATE INDEX IF NOT EXISTS idx_listings_city_listing_type ON listings(city, listing_type);
                """,
                downgrade_sql="""
                    DROP INDEX IF EXISTS idx_listings_city_coordinates;
                    DROP INDEX IF EXISTS idx_listings_city_validated;
                    DROP INDEX IF EXISTS idx_listings_geospatial_quality;
                    DROP INDEX IF EXISTS idx_listings_coordinate_source;
                    DROP INDEX IF EXISTS idx_listings_city_scraped_validated;
                    -- Note: Spatial indexes are managed automatically by DuckDB spatial extension
                    DROP INDEX IF EXISTS idx_listings_city_price_size;
                    DROP INDEX IF EXISTS idx_listings_city_listing_type;
                """,
                validation_sql="SELECT COUNT(*) FROM listings WHERE city IN ('Helsinki', 'Espoo');"
            ),
            Migration(
                version="009_create_city_data_lineage_tables",
                description="Create city-specific data lineage tracking tables",
                upgrade_sql="""
                    -- Enhanced data lineage table for multi-city support
                    CREATE TABLE IF NOT EXISTS city_data_sources (
                        id INTEGER PRIMARY KEY,
                        city VARCHAR(50) NOT NULL,
                        data_source_type VARCHAR(50) NOT NULL,
                        api_endpoint TEXT,
                        last_updated TIMESTAMP,
                        data_quality_score REAL,
                        records_count INTEGER,
                        success_rate REAL,
                        error_count INTEGER DEFAULT 0,
                        last_error TEXT,
                        rate_limit_info JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- City-specific geocoding results tracking
                    CREATE TABLE IF NOT EXISTS city_geocoding_results (
                        id INTEGER PRIMARY KEY,
                        city VARCHAR(50) NOT NULL,
                        address TEXT NOT NULL,
                        original_latitude REAL,
                        original_longitude REAL,
                        geocoded_latitude REAL,
                        geocoded_longitude REAL,
                        geocoding_source VARCHAR(50),
                        geocoding_confidence REAL,
                        geocoding_timestamp TIMESTAMP,
                        validation_status VARCHAR(20), -- 'valid', 'invalid', 'pending'
                        validation_error TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- City-specific API usage tracking
                    CREATE TABLE IF NOT EXISTS city_api_usage (
                        id INTEGER PRIMARY KEY,
                        city VARCHAR(50) NOT NULL,
                        api_endpoint VARCHAR(200) NOT NULL,
                        request_timestamp TIMESTAMP NOT NULL,
                        response_status INTEGER,
                        response_time_ms INTEGER,
                        records_fetched INTEGER,
                        rate_limit_remaining INTEGER,
                        rate_limit_reset TIMESTAMP,
                        request_parameters JSON,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- Create indexes for performance
                    CREATE INDEX IF NOT EXISTS idx_city_data_sources_city ON city_data_sources(city);
                    CREATE INDEX IF NOT EXISTS idx_city_data_sources_type ON city_data_sources(data_source_type);
                    CREATE INDEX IF NOT EXISTS idx_city_geocoding_city ON city_geocoding_results(city);
                    CREATE INDEX IF NOT EXISTS idx_city_geocoding_address ON city_geocoding_results(address);
                    CREATE INDEX IF NOT EXISTS idx_city_geocoding_status ON city_geocoding_results(validation_status);
                    CREATE INDEX IF NOT EXISTS idx_city_api_usage_city ON city_api_usage(city);
                    CREATE INDEX IF NOT EXISTS idx_city_api_usage_endpoint ON city_api_usage(api_endpoint);
                    CREATE INDEX IF NOT EXISTS idx_city_api_usage_timestamp ON city_api_usage(request_timestamp);
                """,
                downgrade_sql="""
                    DROP TABLE IF EXISTS city_data_sources;
                    DROP TABLE IF EXISTS city_geocoding_results;
                    DROP TABLE IF EXISTS city_api_usage;
                """,
                validation_sql="SELECT COUNT(*) FROM city_data_sources; SELECT COUNT(*) FROM city_geocoding_results; SELECT COUNT(*) FROM city_api_usage;"
            ),
            Migration(
                version="010_add_multi_city_constraints",
                description="Add database constraints for multi-city data integrity",
                upgrade_sql="""
                    -- Add check constraints for coordinate validation
                    -- Note: DuckDB doesn't support CHECK constraints in the same way as PostgreSQL
                    -- We'll use triggers or application-level validation instead
                    
                    -- Create validation view for monitoring
                    CREATE OR REPLACE VIEW city_validation_summary AS
                    SELECT 
                        city,
                        COUNT(*) as total_listings,
                        COUNT(CASE WHEN city_validated = TRUE THEN 1 END) as validated_listings,
                        COUNT(CASE WHEN city_validated = FALSE THEN 1 END) as unvalidated_listings,
                        AVG(geospatial_quality_score) as avg_quality_score,
                        COUNT(CASE WHEN coordinate_validation_error IS NOT NULL THEN 1 END) as error_count
                    FROM listings 
                    WHERE city IS NOT NULL
                    GROUP BY city;
                    
                    -- Create coordinate bounds validation view
                    CREATE OR REPLACE VIEW invalid_coordinates AS
                    SELECT 
                        url,
                        city,
                        address,
                        latitude,
                        longitude,
                        CASE 
                            WHEN city = 'Helsinki' AND (latitude NOT BETWEEN 60.0 AND 60.5 OR longitude NOT BETWEEN 24.5 AND 25.5) THEN 'Outside Helsinki bounds'
                            WHEN city = 'Espoo' AND (latitude NOT BETWEEN 60.1 AND 60.4 OR longitude NOT BETWEEN 24.4 AND 24.9) THEN 'Outside Espoo bounds'
                            WHEN city NOT IN ('Helsinki', 'Espoo') THEN 'Unsupported city'
                            ELSE 'Valid'
                        END as validation_error
                    FROM listings 
                    WHERE city IS NOT NULL
                      AND latitude IS NOT NULL 
                      AND longitude IS NOT NULL;
                """,
                downgrade_sql="""
                    DROP VIEW IF EXISTS city_validation_summary;
                    DROP VIEW IF EXISTS invalid_coordinates;
                """,
                validation_sql="SELECT * FROM city_validation_summary; SELECT COUNT(*) FROM invalid_coordinates WHERE validation_error != 'Valid';"
            )
        ]
    
    def apply_multi_city_migrations(self) -> bool:
        """Apply all multi-city specific migrations"""
        logger.info("Applying multi-city database schema enhancements")
        
        # First apply base migrations if needed
        if not self.migrate_up():
            logger.error("Failed to apply base migrations")
            return False
        
        # Apply multi-city migrations
        for migration in self.multi_city_migrations:
            if not self.apply_migration(migration):
                logger.error(f"Failed to apply multi-city migration: {migration.version}")
                return False
        
        logger.success("Multi-city database schema enhancements applied successfully")
        return True
    
    def validate_coordinate_bounds(self, city: str, latitude: float, longitude: float) -> Tuple[bool, str]:
        """Validate coordinates against city bounds"""
        if city not in self.city_bounds:
            return False, f"Unsupported city: {city}"
        
        bounds = self.city_bounds[city]
        
        if not (bounds.min_lat <= latitude <= bounds.max_lat):
            return False, f"Latitude {latitude} outside {city} bounds ({bounds.min_lat}-{bounds.max_lat})"
        
        if not (bounds.min_lon <= longitude <= bounds.max_lon):
            return False, f"Longitude {longitude} outside {city} bounds ({bounds.min_lon}-{bounds.max_lon})"
        
        return True, "Valid coordinates"
    
    def update_coordinate_validation(self) -> int:
        """Update coordinate validation for all listings"""
        logger.info("Updating coordinate validation for all listings")
        
        updated_count = 0
        
        try:
            with duckdb.connect(self.db_path) as con:
                # Get all listings with coordinates
                listings = con.execute("""
                    SELECT url, city, latitude, longitude 
                    FROM listings 
                    WHERE city IS NOT NULL 
                      AND latitude IS NOT NULL 
                      AND longitude IS NOT NULL
                      AND city_validated IS NULL
                """).fetchall()
                
                for url, city, lat, lon in listings:
                    is_valid, error_msg = self.validate_coordinate_bounds(city, lat, lon)
                    
                    con.execute("""
                        UPDATE listings 
                        SET city_validated = ?,
                            coordinate_validation_error = ?,
                            last_coordinate_validation = CURRENT_TIMESTAMP
                        WHERE url = ?
                    """, [is_valid, None if is_valid else error_msg, url])
                    
                    updated_count += 1
                
                logger.success(f"Updated coordinate validation for {updated_count} listings")
                
        except Exception as e:
            logger.error(f"Failed to update coordinate validation: {e}")
            return 0
        
        return updated_count
    
    def get_city_statistics(self) -> Dict[str, Dict]:
        """Get statistics for each city"""
        try:
            with duckdb.connect(self.db_path, read_only=True) as con:
                stats = {}
                
                # Get basic city statistics
                city_stats = con.execute("""
                    SELECT 
                        city,
                        COUNT(*) as total_listings,
                        COUNT(CASE WHEN city_validated = TRUE THEN 1 END) as validated_listings,
                        COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END) as with_coordinates,
                        AVG(geospatial_quality_score) as avg_quality_score,
                        MIN(scraped_at) as first_scraped,
                        MAX(scraped_at) as last_scraped
                    FROM listings 
                    WHERE city IS NOT NULL
                    GROUP BY city
                """).fetchall()
                
                for row in city_stats:
                    city, total, validated, with_coords, avg_quality, first, last = row
                    stats[city] = {
                        'total_listings': total,
                        'validated_listings': validated,
                        'with_coordinates': with_coords,
                        'validation_rate': (validated / total * 100) if total > 0 else 0,
                        'coordinate_rate': (with_coords / total * 100) if total > 0 else 0,
                        'avg_quality_score': avg_quality,
                        'first_scraped': first,
                        'last_scraped': last
                    }
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get city statistics: {e}")
            return {}
    
    def create_city_data_source_entry(self, city: str, source_type: str, 
                                    api_endpoint: str = None, 
                                    records_count: int = 0,
                                    quality_score: float = None) -> bool:
        """Create or update city data source entry"""
        try:
            with duckdb.connect(self.db_path) as con:
                con.execute("""
                    INSERT OR REPLACE INTO city_data_sources 
                    (city, data_source_type, api_endpoint, records_count, data_quality_score, last_updated, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, [city, source_type, api_endpoint, records_count, quality_score])
                
                logger.debug(f"Created/updated data source entry for {city}: {source_type}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create city data source entry: {e}")
            return False


def create_multi_city_migration_script() -> str:
    """Create a standalone migration script for multi-city support"""
    script_content = '''#!/usr/bin/env python3
"""
Standalone Multi-City Database Migration Script

This script applies all necessary database schema changes to support
multi-city operations for the Oikotie Real Estate Analytics Platform.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from oikotie.database.multi_city_migration import MultiCityMigrationManager
from loguru import logger

def main():
    """Apply multi-city database migrations"""
    logger.info("Starting multi-city database migration")
    
    try:
        # Initialize migration manager
        migrator = MultiCityMigrationManager()
        
        # Apply migrations
        success = migrator.apply_multi_city_migrations()
        
        if success:
            # Update coordinate validation
            updated_count = migrator.update_coordinate_validation()
            logger.info(f"Updated coordinate validation for {updated_count} listings")
            
            # Show statistics
            stats = migrator.get_city_statistics()
            logger.info("City statistics after migration:")
            for city, city_stats in stats.items():
                logger.info(f"  {city}: {city_stats['total_listings']} listings, "
                          f"{city_stats['validation_rate']:.1f}% validated")
            
            logger.success("Multi-city database migration completed successfully")
            return 0
        else:
            logger.error("Multi-city database migration failed")
            return 1
            
    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
    
    return script_content


def run_multi_city_migration():
    """Run the multi-city migration process"""
    migrator = MultiCityMigrationManager()
    return migrator.apply_multi_city_migrations()