"""
Command-line interface for geospatial data integration.

This module provides CLI commands for geocoding, building matching,
and other geospatial operations.
"""

import argparse
import sys
import pandas as pd
import duckdb
from pathlib import Path
from loguru import logger
import json
from datetime import datetime

from oikotie.geospatial.integrator import MultiCityGeospatialManager
from oikotie.geospatial.schema import setup_geospatial_schema


def setup_logger():
    """Configure logger for CLI usage"""
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan> - <level>{message}</level>")


def geocode_city_addresses(city: str, limit: int = None):
    """
    Geocode addresses for a specific city.
    
    Args:
        city: City name
        limit: Optional limit on number of addresses to process
    """
    logger.info(f"Geocoding addresses for {city}")
    
    # Initialize geospatial manager
    manager = MultiCityGeospatialManager()
    integrator = manager.get_integrator(city)
    
    if integrator is None:
        logger.error(f"No geospatial integrator available for {city}")
        return
    
    # Connect to database
    db_path = "data/real_estate.duckdb"
    conn = duckdb.connect(db_path)
    
    # Get addresses that need geocoding
    query = f"""
        SELECT DISTINCT l.address
        FROM listings l
        LEFT JOIN address_locations al ON l.address = al.address
        WHERE l.city = '{city}'
        AND l.address IS NOT NULL
        AND al.address IS NULL
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    addresses_df = conn.execute(query).df()
    addresses = addresses_df['address'].tolist()
    
    if not addresses:
        logger.info(f"No new addresses to geocode for {city}")
        return
    
    logger.info(f"Found {len(addresses)} addresses to geocode")
    
    # Geocode addresses
    geocoded = integrator.geocode_addresses(addresses)
    
    # Calculate success rate
    success_count = sum(1 for _, lat, lon, _ in geocoded if lat is not None and lon is not None)
    success_rate = (success_count / len(addresses)) * 100 if addresses else 0
    
    logger.success(f"Geocoded {success_count}/{len(addresses)} addresses ({success_rate:.1f}%)")
    
    # Close connection
    conn.close()


def match_buildings(city: str, limit: int = None):
    """
    Match listings to building footprints for a specific city.
    
    Args:
        city: City name
        limit: Optional limit on number of listings to process
    """
    logger.info(f"Matching {city} listings to buildings")
    
    # Initialize geospatial manager
    manager = MultiCityGeospatialManager()
    
    # Connect to database
    db_path = "data/real_estate.duckdb"
    conn = duckdb.connect(db_path)
    
    # Get listings with coordinates that need building matching
    query = f"""
        SELECT l.url, l.address, al.lat as latitude, al.lon as longitude, l.price_eur as price
        FROM listings l
        JOIN address_locations al ON l.address = al.address
        LEFT JOIN building_matches bm ON l.url = bm.listing_url
        WHERE l.city = '{city}'
        AND al.lat IS NOT NULL AND al.lon IS NOT NULL
        AND bm.listing_url IS NULL
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    listings_df = conn.execute(query).df()
    
    if listings_df.empty:
        logger.info(f"No new listings to match for {city}")
        return
    
    logger.info(f"Found {len(listings_df)} listings to match with buildings")
    
    # Process listings
    result_df = manager.process_city_listings(city, listings_df)
    
    # Calculate success metrics
    match_count = result_df['building_match'].sum() if 'building_match' in result_df.columns else 0
    match_rate = (match_count / len(result_df)) * 100 if len(result_df) > 0 else 0
    
    logger.success(f"Building matching complete: {match_count}/{len(result_df)} matched ({match_rate:.1f}%)")
    
    # Save results to file for inspection
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("output/validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"{city.lower()}_building_matches_{timestamp}.csv"
    result_df.to_csv(output_file, index=False)
    
    logger.info(f"Results saved to {output_file}")
    
    # Close connection
    conn.close()


def validate_spatial_data(city: str, limit: int = None):
    """
    Validate spatial data for a specific city.
    
    Args:
        city: City name
        limit: Optional limit on number of listings to validate
    """
    logger.info(f"Validating spatial data for {city}")
    
    # Initialize geospatial manager
    manager = MultiCityGeospatialManager()
    integrator = manager.get_integrator(city)
    
    if integrator is None:
        logger.error(f"No geospatial integrator available for {city}")
        return
    
    # Connect to database
    db_path = "data/real_estate.duckdb"
    conn = duckdb.connect(db_path)
    
    # Get listings with coordinates to validate
    query = f"""
        SELECT l.url, l.address, al.lat as latitude, al.lon as longitude
        FROM listings l
        JOIN address_locations al ON l.address = al.address
        WHERE l.city = '{city}'
        AND al.lat IS NOT NULL AND al.lon IS NOT NULL
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    listings_df = conn.execute(query).df()
    
    if listings_df.empty:
        logger.info(f"No listings to validate for {city}")
        return
    
    logger.info(f"Validating {len(listings_df)} listings")
    
    # Validate spatial data
    result_df = integrator.validate_spatial_data(listings_df)
    
    # Calculate validation statistics
    valid_coords_count = result_df['coordinates_valid'].sum()
    within_bounds_count = result_df['within_espoo_bounds'].sum()
    
    valid_coords_rate = (valid_coords_count / len(result_df)) * 100
    within_bounds_rate = (within_bounds_count / len(result_df)) * 100
    
    logger.success(f"Validation complete:")
    logger.success(f"  Valid coordinates: {valid_coords_count}/{len(result_df)} ({valid_coords_rate:.1f}%)")
    logger.success(f"  Within {city} bounds: {within_bounds_count}/{len(result_df)} ({within_bounds_rate:.1f}%)")
    
    # Save results to database
    try:
        data = []
        
        for _, row in result_df.iterrows():
            data.append((
                row['url'],
                city,
                row['coordinates_valid'],
                row['within_espoo_bounds'],
                row['validation_message'],
                0.8 if row['within_espoo_bounds'] else 0.5
            ))
        
        conn.execute("BEGIN TRANSACTION")
        
        conn.executemany("""
            INSERT OR REPLACE INTO spatial_validation_results
            (listing_url, city, coordinates_valid, within_city_bounds, validation_message, geospatial_quality_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, data)
        
        conn.execute("COMMIT")
        
        logger.success(f"Updated {len(data)} validation results in database")
    except Exception as e:
        logger.error(f"Error updating validation results: {e}")
    
    # Close connection
    conn.close()


def setup_schema():
    """Set up the geospatial database schema"""
    logger.info("Setting up geospatial database schema")
    setup_geospatial_schema()
    logger.success("Schema setup complete")


def main():
    """Main CLI entry point"""
    setup_logger()
    
    parser = argparse.ArgumentParser(description="Geospatial data integration tools")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Geocode command
    geocode_parser = subparsers.add_parser("geocode", help="Geocode addresses")
    geocode_parser.add_argument("city", help="City name (e.g., Espoo)")
    geocode_parser.add_argument("--limit", type=int, help="Limit number of addresses to process")
    
    # Match buildings command
    match_parser = subparsers.add_parser("match", help="Match listings to buildings")
    match_parser.add_argument("city", help="City name (e.g., Espoo)")
    match_parser.add_argument("--limit", type=int, help="Limit number of listings to process")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate spatial data")
    validate_parser.add_argument("city", help="City name (e.g., Espoo)")
    validate_parser.add_argument("--limit", type=int, help="Limit number of listings to validate")
    
    # Setup schema command
    subparsers.add_parser("setup", help="Set up geospatial database schema")
    
    args = parser.parse_args()
    
    if args.command == "geocode":
        geocode_city_addresses(args.city, args.limit)
    elif args.command == "match":
        match_buildings(args.city, args.limit)
    elif args.command == "validate":
        validate_spatial_data(args.city, args.limit)
    elif args.command == "setup":
        setup_schema()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()