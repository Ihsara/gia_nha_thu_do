#!/usr/bin/env python3
"""
Debug spatial join issue between listings and property polygons
"""

import duckdb
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.geometry import Point
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_spatial_join():
    """Debug the spatial join between listings and polygons"""
    
    # Connect to database
    conn = duckdb.connect("data/real_estate.duckdb")
    
    # Get sample listings with coordinates
    listings_query = """
    SELECT 
        l.address,
        al.lat as latitude,
        al.lon as longitude
    FROM listings l
    LEFT JOIN address_locations al ON l.address = al.address
    WHERE al.lat IS NOT NULL AND al.lon IS NOT NULL
    LIMIT 10
    """
    
    listings_df = conn.execute(listings_query).fetchdf()
    logger.info(f"Sample listings:\n{listings_df[['address', 'latitude', 'longitude']].to_string()}")
    
    # Get sample polygons
    polygons_query = """
    SELECT 
        kiinteistorajalaji,
        geometry_wkt
    FROM helsinki_02_kiinteistorajansijaintitiedot
    WHERE geometry_wkt IS NOT NULL
    LIMIT 5
    """
    
    polygons_df = conn.execute(polygons_query).fetchdf()
    logger.info(f"Found {len(polygons_df)} sample polygons")
    
    # Convert to geometries
    polygons_df['geometry'] = polygons_df['geometry_wkt'].apply(wkt.loads)
    polygons_gdf = gpd.GeoDataFrame(polygons_df, geometry='geometry')
    
    # Check polygon coordinate ranges
    for i, row in polygons_df.head(3).iterrows():
        geom = row['geometry']
        bounds = geom.bounds
        logger.info(f"Polygon {i} bounds: {bounds}")
        logger.info(f"Polygon {i} type: {geom.geom_type}")
        
        # Sample some coordinates from the polygon
        if hasattr(geom, 'exterior'):
            coords = list(geom.exterior.coords)[:5]  # First 5 coordinates
            logger.info(f"Polygon {i} sample coordinates: {coords}")
    
    # Test coordinate system detection
    sample_geom = polygons_gdf.iloc[0]['geometry']
    bounds = sample_geom.bounds
    logger.info(f"Sample polygon bounds: {bounds}")
    
    if -180 <= bounds[0] <= 180 and -90 <= bounds[1] <= 90:
        logger.info("Coordinates appear to be in WGS84 format (lat/lon)")
        polygons_gdf.crs = "EPSG:4326"
    else:
        logger.info("Coordinates appear to be in projected format - converting from Finnish National Grid")
        polygons_gdf.crs = "EPSG:3067"
        polygons_gdf = polygons_gdf.to_crs("EPSG:4326")
        
        # Check after conversion
        sample_geom_converted = polygons_gdf.iloc[0]['geometry']
        bounds_converted = sample_geom_converted.bounds
        logger.info(f"Converted polygon bounds: {bounds_converted}")
    
    # Create listing points
    geometry = [Point(lon, lat) for lon, lat in 
               zip(listings_df['longitude'], listings_df['latitude'])]
    listings_gdf = gpd.GeoDataFrame(listings_df, geometry=geometry, crs="EPSG:4326")
    
    # Test spatial relationships
    logger.info("\nTesting spatial relationships:")
    
    # Test if Helsinki center is within any polygon
    helsinki_center = Point(24.9384, 60.1699)
    center_within = polygons_gdf.contains(helsinki_center).any()
    logger.info(f"Helsinki center within any polygon: {center_within}")
    
    # Test specific listing points
    for i, listing in listings_gdf.head(5).iterrows():
        point = listing['geometry']
        within_any = polygons_gdf.contains(point).any()
        intersects_any = polygons_gdf.intersects(point).any()
        logger.info(f"Listing {i} ({listing['address']}) at {point.x:.6f}, {point.y:.6f}:")
        logger.info(f"  Within any polygon: {within_any}")
        logger.info(f"  Intersects any polygon: {intersects_any}")
    
    # Test spatial join
    logger.info("\nTesting spatial joins:")
    join_within = gpd.sjoin(listings_gdf, polygons_gdf, how='inner', predicate='within')
    join_intersects = gpd.sjoin(listings_gdf, polygons_gdf, how='inner', predicate='intersects')
    
    logger.info(f"Within join matches: {len(join_within)}")
    logger.info(f"Intersects join matches: {len(join_intersects)}")
    
    conn.close()

if __name__ == "__main__":
    debug_spatial_join()
