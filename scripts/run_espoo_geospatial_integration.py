#!/usr/bin/env python3
"""
Espoo Geospatial Integration Script

This script runs the complete Espoo geospatial integration process:
1. Sets up the database schema
2. Geocodes Espoo addresses
3. Matches Espoo listings to building footprints
4. Validates spatial data quality

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import sys
import argparse
from pathlib import Path
import time
from datetime import datetime
import json
import pandas as pd
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


def run_integration(sample_size=None, output_dir=None):
    """
    Run the complete Espoo geospatial integration process.
    
    Args:
        sample_size: Optional limit on number of listings to process
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
    log_file = output_dir / f"espoo_geospatial_{timestamp}.log"
    setup_logger(log_file)
    
    logger.info(f"Starting Espoo geospatial integration")
    logger.info(f"Sample size: {'All' if sample_size is None else sample_size}")
    logger.info(f"Output directory: {output_dir}")
    
    try:
        # Step 1: Set up database schema
        logger.info("Step 1: Setting up database schema")
        setup_geospatial_schema()
        
        # Step 2: Initialize geospatial manager
        logger.info("Step 2: Initializing geospatial manager")
        manager = MultiCityGeospatialManager()
        integrator = manager.get_integrator(city)
        
        if integrator is None:
            logger.error(f"No geospatial integrator available for {city}")
            return False
        
        # Step 3: Connect to database
        logger.info("Step 3: Connecting to database")
        db_path = "data/real_estate.duckdb"
        conn = duckdb.connect(db_path)
        
        # Step 4: Get listings to process
        logger.info("Step 4: Getting listings to process")
        
        query = f"""
            SELECT l.url, l.address, l.city, l.postal_code, l.price_eur as price,
                   l.size_m2, l.rooms, l.listing_type
            FROM listings l
            WHERE l.city = '{city}'
        """
        
        if sample_size:
            query += f" ORDER BY RANDOM() LIMIT {sample_size}"
        
        listings_df = conn.execute(query).df()
        
        if listings_df.empty:
            logger.warning(f"No {city} listings found in database")
            return False
        
        logger.info(f"Found {len(listings_df)} {city} listings to process")
        
        # Step 5: Geocode addresses
        logger.info("Step 5: Geocoding addresses")
        addresses = listings_df['address'].dropna().unique().tolist()
        
        if addresses:
            geocoded = integrator.geocode_addresses(addresses)
            
            # Calculate geocoding success rate
            success_count = sum(1 for _, lat, lon, _ in geocoded if lat is not None and lon is not None)
            success_rate = (success_count / len(addresses)) * 100 if addresses else 0
            
            logger.success(f"Geocoded {success_count}/{len(addresses)} addresses ({success_rate:.1f}%)")
            
            # Add coordinates to listings
            coord_map = {addr: (lat, lon) for addr, lat, lon, _ in geocoded if lat is not None and lon is not None}
            
            for idx, row in listings_df.iterrows():
                if row['address'] in coord_map:
                    lat, lon = coord_map[row['address']]
                    listings_df.loc[idx, 'latitude'] = lat
                    listings_df.loc[idx, 'longitude'] = lon
        
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
        results_file = output_dir / f"espoo_geospatial_results_{timestamp}.csv"
        listings_df.to_csv(results_file, index=False)
        
        # Create summary report
        summary = {
            "timestamp": timestamp,
            "city": city,
            "total_listings": len(listings_df),
            "geocoding": {
                "addresses_processed": len(addresses),
                "successfully_geocoded": success_count if 'success_count' in locals() else 0,
                "geocoding_rate": success_rate if 'success_rate' in locals() else 0
            },
            "building_matching": {
                "listings_with_coordinates": len(listings_with_coords) if 'listings_with_coords' in locals() else 0,
                "matched_to_buildings": match_count if 'match_count' in locals() else 0,
                "matching_rate": match_rate if 'match_rate' in locals() else 0
            },
            "spatial_validation": {
                "valid_coordinates": valid_coords_count if 'valid_coords_count' in locals() else 0,
                "within_city_bounds": within_bounds_count if 'within_bounds_count' in locals() else 0,
                "valid_coordinates_rate": valid_coords_rate if 'valid_coords_rate' in locals() else 0,
                "within_bounds_rate": within_bounds_rate if 'within_bounds_rate' in locals() else 0
            },
            "execution_time_seconds": time.time() - start_time
        }
        
        summary_file = output_dir / f"espoo_geospatial_summary_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.success(f"Results saved to {results_file}")
        logger.success(f"Summary saved to {summary_file}")
        
        # Step 9: Close database connection
        conn.close()
        
        # Final success check
        if 'success_rate' in locals() and success_rate >= 95.0:
            logger.success(f"✅ SUCCESS: Geocoding rate {success_rate:.1f}% meets requirement ≥95%")
        else:
            logger.warning(f"⚠️ WARNING: Geocoding rate {success_rate if 'success_rate' in locals() else 0:.1f}% below target 95%")
        
        execution_time = time.time() - start_time
        logger.info(f"Integration completed in {execution_time:.1f} seconds")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during integration: {e}", exc_info=True)
        return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Run Espoo geospatial integration")
    parser.add_argument("--sample", type=int, help="Number of listings to process (default: all)")
    parser.add_argument("--output", help="Output directory for results")
    
    args = parser.parse_args()
    
    run_integration(args.sample, args.output)


if __name__ == "__main__":
    main()