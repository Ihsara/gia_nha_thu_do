#!/usr/bin/env python3
"""
Espoo Geospatial Integration Validation Script

This script validates the Espoo geospatial integration by:
1. Creating test listings for Espoo
2. Running the geospatial integration process
3. Validating the results

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import sys
import argparse
from pathlib import Path
import time
from datetime import datetime
import json
import pandas as pd
import geopandas as gpd
import duckdb
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import geospatial modules
from oikotie.geospatial.schema import setup_geospatial_schema
from oikotie.geospatial.integrator import MultiCityGeospatialManager


def setup_logger(log_file=None):
    """Configure logger with console and optional file output"""
    logger.remove()
    
    # Console logger
    logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan> - <level>{message}</level>")
    
    # File logger if specified
    if log_file:
        logger.add(log_file, rotation="10 MB", retention="1 week", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {function} - {message}")


def create_test_listings(conn, count=10):
    """Create test listings for Espoo"""
    logger.info(f"Creating {count} test listings for Espoo")
    
    # Ensure listings table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            url VARCHAR PRIMARY KEY,
            source VARCHAR,
            city VARCHAR NOT NULL,
            title VARCHAR,
            address VARCHAR,
            postal_code VARCHAR,
            listing_type VARCHAR,
            price_eur FLOAT,
            size_m2 FLOAT,
            rooms INTEGER,
            year_built INTEGER,
            overview VARCHAR,
            full_description VARCHAR,
            other_details_json VARCHAR,
            scraped_at TIMESTAMP,
            insert_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_ts TIMESTAMP,
            deleted_ts TIMESTAMP,
            latitude FLOAT,
            longitude FLOAT
        );
    """)
    
    # Test addresses in Espoo
    test_addresses = [
        "Tapiontori 3, Espoo",
        "Leppävaarankatu 3-9, Espoo",
        "Otakaari 1, Espoo",
        "Suurpelto 21, Espoo",
        "Matinkylänkuja 2, Espoo",
        "Espoonlahdentie 10, Espoo",
        "Kauppakeskus Sello, Espoo",
        "Keilaniemi 1, Espoo",
        "Haukilahdenranta 4, Espoo",
        "Westendintie 1, Espoo"
    ]
    
    # Test coordinates in Espoo (approximate)
    test_coordinates = [
        (60.1756, 24.8059),  # Tapiola
        (60.2188, 24.8127),  # Leppävaara
        (60.1841, 24.8301),  # Otaniemi
        (60.1967, 24.7544),  # Suurpelto
        (60.1598, 24.7384),  # Matinkylä
        (60.1492, 24.6651),  # Espoonlahti
        (60.2179, 24.8122),  # Sello
        (60.1762, 24.8361),  # Keilaniemi
        (60.1631, 24.7769),  # Haukilahti
        (60.1603, 24.8022)   # Westend
    ]
    
    # Create test listings
    listings = []
    for i in range(min(count, len(test_addresses))):
        listings.append({
            'url': f"test_espoo_{i}",
            'source': 'test',
            'city': 'Espoo',
            'title': f"Test Espoo Listing {i}",
            'address': test_addresses[i],
            'postal_code': f"02{100+i}",
            'listing_type': 'apartment',
            'price_eur': 300000 + i * 50000,
            'size_m2': 50 + i * 10,
            'rooms': 2 + (i % 3),
            'year_built': 2000 + (i % 20),
            'overview': f"Test listing {i} in Espoo",
            'scraped_at': 'CURRENT_TIMESTAMP',
            'latitude': test_coordinates[i][0],
            'longitude': test_coordinates[i][1]
        })
    
    # Insert test listings
    for listing in listings:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO listings (
                    url, source, city, title, address, postal_code, listing_type,
                    price_eur, size_m2, rooms, year_built, overview, scraped_at,
                    latitude, longitude
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
            """, (
                listing['url'], listing['source'], listing['city'], listing['title'],
                listing['address'], listing['postal_code'], listing['listing_type'],
                listing['price_eur'], listing['size_m2'], listing['rooms'],
                listing['year_built'], listing['overview'],
                listing['latitude'], listing['longitude']
            ))
        except Exception as e:
            logger.error(f"Error inserting test listing: {e}")
    
    logger.success(f"Created {len(listings)} test listings for Espoo")
    return listings


def run_validation(output_dir=None):
    """
    Run the Espoo geospatial integration validation.
    
    Args:
        output_dir: Optional output directory for results
    """
    start_time = time.time()
    city = "Espoo"
    
    # Set up output directory
    if output_dir is None:
        output_dir = Path("output/geospatial")
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_dir / f"espoo_validation_{timestamp}.log"
    setup_logger(log_file)
    
    logger.info(f"Starting Espoo geospatial integration validation")
    logger.info(f"Output directory: {output_dir}")
    
    try:
        # Step 1: Set up database schema
        logger.info("Step 1: Setting up database schema")
        setup_geospatial_schema()
        
        # Step 2: Connect to database
        logger.info("Step 2: Connecting to database")
        db_path = "data/real_estate.duckdb"
        conn = duckdb.connect(db_path)
        
        # Step 3: Create test listings
        logger.info("Step 3: Creating test listings")
        test_listings = create_test_listings(conn, count=10)
        
        # Step 4: Initialize geospatial manager
        logger.info("Step 4: Initializing geospatial manager")
        manager = MultiCityGeospatialManager()
        integrator = manager.get_integrator(city)
        
        if integrator is None:
            logger.error(f"No geospatial integrator available for {city}")
            return False
        
        # Step 5: Get listings to process
        logger.info("Step 5: Getting listings to process")
        
        query = f"""
            SELECT l.url, l.address, l.city, l.postal_code, l.price_eur as price,
                   l.size_m2, l.rooms, l.listing_type, l.latitude, l.longitude
            FROM listings l
            WHERE l.city = '{city}'
        """
        
        listings_df = conn.execute(query).df()
        
        if listings_df.empty:
            logger.warning(f"No {city} listings found in database")
            return False
        
        logger.info(f"Found {len(listings_df)} {city} listings to process")
        
        # Step 6: Match to buildings
        logger.info("Step 6: Matching listings to buildings")
        listings_with_coords = listings_df[listings_df['latitude'].notna() & listings_df['longitude'].notna()]
        
        if not listings_with_coords.empty:
            listings_with_buildings = integrator.match_listings_to_buildings(listings_with_coords)
            
            # Calculate building match rate
            match_count = listings_with_buildings['building_match'].sum() if 'building_match' in listings_with_buildings.columns else 0
            match_rate = (match_count / len(listings_with_buildings)) * 100 if len(listings_with_buildings) > 0 else 0
            
            logger.success(f"Building matching: {match_count}/{len(listings_with_buildings)} matched ({match_rate:.1f}%)")
            
            # Update listings DataFrame with building match results
            for col in ['building_match', 'building_id', 'match_type', 'geospatial_quality_score']:
                if col in listings_with_buildings.columns:
                    listings_df.loc[listings_with_buildings.index, col] = listings_with_buildings[col]
        
        # Step 7: Validate spatial data
        logger.info("Step 7: Validating spatial data")
        listings_with_coords = listings_df[listings_df['latitude'].notna() & listings_df['longitude'].notna()]
        
        if not listings_with_coords.empty:
            validated_df = integrator.validate_spatial_data(listings_with_coords)
            
            # Calculate validation statistics
            valid_coords_count = validated_df['coordinates_valid'].sum()
            within_bounds_count = validated_df['within_espoo_bounds'].sum()
            
            valid_coords_rate = (valid_coords_count / len(validated_df)) * 100
            within_bounds_rate = (within_bounds_count / len(validated_df)) * 100
            
            logger.success(f"Spatial validation:")
            logger.success(f"  Valid coordinates: {valid_coords_count}/{len(validated_df)} ({valid_coords_rate:.1f}%)")
            logger.success(f"  Within {city} bounds: {within_bounds_count}/{len(validated_df)} ({within_bounds_rate:.1f}%)")
            
            # Update listings DataFrame with validation results
            for col in ['coordinates_valid', 'within_espoo_bounds', 'validation_message']:
                if col in validated_df.columns:
                    listings_df.loc[validated_df.index, col] = validated_df[col]
        
        # Step 8: Save results
        logger.info("Step 8: Saving results")
        results_file = output_dir / f"espoo_validation_results_{timestamp}.csv"
        listings_df.to_csv(results_file, index=False)
        
        # Create summary report
        # Convert numpy types to Python native types for JSON serialization
        def convert_to_native(obj):
            if hasattr(obj, 'item'):
                return obj.item()  # Convert numpy types to native Python types
            return obj
        
        summary = {
            "timestamp": timestamp,
            "city": city,
            "total_listings": int(len(listings_df)),
            "building_matching": {
                "listings_with_coordinates": int(len(listings_with_coords) if 'listings_with_coords' in locals() else 0),
                "matched_to_buildings": int(convert_to_native(match_count) if 'match_count' in locals() else 0),
                "matching_rate": float(match_rate) if 'match_rate' in locals() else 0.0
            },
            "spatial_validation": {
                "valid_coordinates": int(convert_to_native(valid_coords_count) if 'valid_coords_count' in locals() else 0),
                "within_city_bounds": int(convert_to_native(within_bounds_count) if 'within_bounds_count' in locals() else 0),
                "valid_coordinates_rate": float(valid_coords_rate) if 'valid_coords_rate' in locals() else 0.0,
                "within_bounds_rate": float(within_bounds_rate) if 'within_bounds_rate' in locals() else 0.0
            },
            "execution_time_seconds": float(time.time() - start_time)
        }
        
        summary_file = output_dir / f"espoo_validation_summary_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.success(f"Results saved to {results_file}")
        logger.success(f"Summary saved to {summary_file}")
        
        # Step 9: Close database connection
        conn.close()
        
        # Final success check
        if 'match_rate' in locals() and match_rate >= 95.0:
            logger.success(f"✅ SUCCESS: Building match rate {match_rate:.1f}% meets requirement ≥95%")
        else:
            logger.warning(f"⚠️ WARNING: Building match rate {match_rate if 'match_rate' in locals() else 0:.1f}% below target 95%")
        
        if 'valid_coords_rate' in locals() and valid_coords_rate >= 95.0:
            logger.success(f"✅ SUCCESS: Valid coordinates rate {valid_coords_rate:.1f}% meets requirement ≥95%")
        else:
            logger.warning(f"⚠️ WARNING: Valid coordinates rate {valid_coords_rate if 'valid_coords_rate' in locals() else 0:.1f}% below target 95%")
        
        execution_time = time.time() - start_time
        logger.info(f"Validation completed in {execution_time:.1f} seconds")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during validation: {e}", exc_info=True)
        return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Run Espoo geospatial integration validation")
    parser.add_argument("--output", help="Output directory for results")
    
    args = parser.parse_args()
    
    run_validation(args.output)


if __name__ == "__main__":
    main()