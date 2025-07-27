"""
Database schema enhancements for geospatial data integration.

This module provides functions to set up and migrate the database schema
for improved multi-city geospatial support.
"""

import duckdb
from pathlib import Path
from loguru import logger

# Constants
DB_PATH = Path("data/real_estate.duckdb")


def get_db_connection():
    """Establishes and returns a connection to the DuckDB database."""
    return duckdb.connect(database=str(DB_PATH), read_only=False)


def setup_geospatial_tables():
    """
    Set up geospatial tables in the database.
    
    Creates or updates tables for:
    - address_locations: Geocoded addresses with city validation
    - building_matches: Matches between listings and building footprints
    - city_data_sources: Data lineage tracking for geospatial data
    """
    logger.info("Setting up geospatial tables in database")
    
    try:
        with get_db_connection() as conn:
            # Create or update address_locations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS address_locations (
                    address VARCHAR PRIMARY KEY,
                    lat DOUBLE,
                    lon DOUBLE,
                    city_validated BOOLEAN DEFAULT FALSE,
                    coordinate_source VARCHAR(50),
                    geocoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Add columns if they don't exist
            try:
                conn.execute("ALTER TABLE address_locations ADD COLUMN IF NOT EXISTS city_validated BOOLEAN DEFAULT FALSE;")
                conn.execute("ALTER TABLE address_locations ADD COLUMN IF NOT EXISTS coordinate_source VARCHAR(50);")
                conn.execute("ALTER TABLE address_locations ADD COLUMN IF NOT EXISTS geocoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
            except:
                logger.debug("Some columns already exist in address_locations")
            
            # Create building_matches table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS building_matches (
                    listing_url VARCHAR PRIMARY KEY,
                    city VARCHAR NOT NULL,
                    building_id VARCHAR,
                    match_type VARCHAR,
                    quality_score REAL,
                    match_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create city_data_sources table for data lineage
            conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS city_data_sources_id_seq;
                
                CREATE TABLE IF NOT EXISTS city_data_sources (
                    id INTEGER PRIMARY KEY DEFAULT nextval('city_data_sources_id_seq'),
                    city VARCHAR(50) NOT NULL,
                    data_source_type VARCHAR(50) NOT NULL,
                    api_endpoint TEXT,
                    last_updated TIMESTAMP,
                    data_quality_score REAL,
                    records_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create spatial_validation_results table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spatial_validation_results (
                    listing_url VARCHAR PRIMARY KEY,
                    city VARCHAR NOT NULL,
                    coordinates_valid BOOLEAN,
                    within_city_bounds BOOLEAN,
                    validation_message TEXT,
                    geospatial_quality_score REAL,
                    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_address_locations_city ON address_locations(city_validated);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_building_matches_city ON building_matches(city);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_building_matches_quality ON building_matches(quality_score);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spatial_validation_city ON spatial_validation_results(city);")
            
            logger.success("Geospatial tables setup complete")
            
    except Exception as e:
        logger.error(f"Error setting up geospatial tables: {e}")
        raise


def create_city_coordinate_validation_function():
    """
    Create a SQL function to validate city coordinates.
    
    This function checks if coordinates are within the bounds of a specific city.
    """
    logger.info("Creating city coordinate validation function")
    
    try:
        with get_db_connection() as conn:
            # DuckDB doesn't support user-defined functions in the same way as PostgreSQL
            # Instead, we'll create a SQL macro which works similarly
            conn.execute("""
                CREATE OR REPLACE MACRO validate_city_coordinates(city, lat, lon) AS
                    CASE
                        WHEN city = 'Helsinki' THEN
                            lat BETWEEN 60.0 AND 60.5 AND lon BETWEEN 24.5 AND 25.5
                        WHEN city = 'Espoo' THEN
                            lat BETWEEN 60.1 AND 60.4 AND lon BETWEEN 24.4 AND 24.9
                        ELSE
                            FALSE
                    END
            """)
            
            # Test the function
            result = conn.execute("SELECT validate_city_coordinates('Espoo', 60.2, 24.6)").fetchone()[0]
            logger.info(f"Test validation for Espoo coordinates: {result}")
            
            logger.success("City coordinate validation function created")
            
    except Exception as e:
        logger.error(f"Error creating coordinate validation function: {e}")
        raise


def add_spatial_constraints():
    """
    Add spatial constraints to the listings table.
    
    This ensures that coordinates are valid for their respective cities.
    """
    logger.info("Adding spatial constraints to listings table")
    
    try:
        with get_db_connection() as conn:
            # Check if the constraint already exists
            constraint_exists = conn.execute("""
                SELECT COUNT(*) FROM pragma_table_info('listings') 
                WHERE name = 'valid_city_coordinates'
            """).fetchone()[0] > 0
            
            if not constraint_exists:
                # Add city_validated column if it doesn't exist
                try:
                    conn.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS city_validated BOOLEAN DEFAULT FALSE;")
                    conn.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS coordinate_source VARCHAR(50);")
                    conn.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS geospatial_quality_score REAL;")
                except:
                    logger.debug("Some columns already exist in listings")
                
                # We can't add CHECK constraints in DuckDB after table creation,
                # so we'll create a trigger instead to enforce the constraint
                try:
                    conn.execute("""
                        CREATE OR REPLACE TRIGGER validate_listing_coordinates
                        BEFORE INSERT ON listings
                        FOR EACH ROW
                        WHEN NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL
                        BEGIN
                            SELECT
                                CASE WHEN NOT validate_city_coordinates(NEW.city, NEW.latitude, NEW.longitude)
                                THEN RAISE(ABORT, 'Invalid coordinates for city')
                                END;
                        END;
                    """)
                    logger.success("Spatial constraints added to listings table")
                except Exception as e:
                    logger.warning(f"Could not create trigger: {e}")
                    logger.warning("DuckDB may not support triggers, using alternative approach")
                    
                    # Alternative approach: Create a view that filters valid coordinates
                    conn.execute("""
                        CREATE OR REPLACE VIEW valid_listings AS
                        SELECT * FROM listings
                        WHERE latitude IS NULL OR longitude IS NULL OR 
                              validate_city_coordinates(city, latitude, longitude);
                    """)
                    logger.success("Created valid_listings view as alternative to constraints")
            else:
                logger.info("Spatial constraints already exist")
            
    except Exception as e:
        logger.error(f"Error adding spatial constraints: {e}")
        # Don't raise here, as this is not critical functionality
        logger.warning("Continuing without spatial constraints")


def setup_geospatial_schema():
    """
    Set up the complete geospatial schema.
    
    This function should be called during application initialization
    to ensure all geospatial tables and functions are properly set up.
    """
    logger.info("Setting up geospatial schema")
    
    # Step 1: Set up tables
    setup_geospatial_tables()
    
    # Step 2: Create validation function
    create_city_coordinate_validation_function()
    
    # Step 3: Add spatial constraints
    add_spatial_constraints()
    
    logger.success("Geospatial schema setup complete")


if __name__ == "__main__":
    logger.info("Running geospatial schema setup")
    setup_geospatial_schema()
    logger.info("Schema setup complete")