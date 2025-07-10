#!/usr/bin/env python3
"""
Fix polygon geometries for spatial join by converting LineStrings to Polygons
"""

import duckdb
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.geometry import Point, Polygon, LineString
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_and_fix_geometries():
    """Analyze geometry types and convert LineStrings to Polygons where possible"""
    
    # Connect to database
    conn = duckdb.connect("data/real_estate.duckdb")
    
    # Get all boundary data
    query = """
    SELECT 
        kiinteistorajalaji,
        lahdeaineisto,
        interpolointitapa,
        geometry_wkt
    FROM helsinki_02_kiinteistorajansijaintitiedot
    WHERE geometry_wkt IS NOT NULL
    """
    
    df = conn.execute(query).fetchdf()
    logger.info(f"Total boundary records: {len(df)}")
    
    # Convert WKT to geometry
    df['geometry'] = df['geometry_wkt'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
    
    # Analyze geometry types
    geom_types = gdf['geometry'].geom_type.value_counts()
    logger.info(f"Geometry types: {geom_types.to_dict()}")
    
    # Analyze by boundary type
    boundary_types = gdf['kiinteistorajalaji'].value_counts()
    logger.info(f"Boundary types: {boundary_types.to_dict()}")
    
    # Check geometry types per boundary type
    for boundary_type in gdf['kiinteistorajalaji'].unique():
        subset = gdf[gdf['kiinteistorajalaji'] == boundary_type]
        subset_geom_types = subset['geometry'].geom_type.value_counts()
        logger.info(f"Boundary type {boundary_type}: {subset_geom_types.to_dict()}")
    
    # Try to convert LineStrings to Polygons
    converted_polygons = []
    failed_conversions = 0
    
    for idx, row in gdf.iterrows():
        geom = row['geometry']
        
        if geom.geom_type == 'LineString':
            # Check if LineString is closed (first and last points are the same)
            if geom.is_closed:
                try:
                    # Convert closed LineString to Polygon
                    polygon = Polygon(geom.coords)
                    if polygon.is_valid and polygon.area > 0:
                        new_row = row.copy()
                        new_row['geometry'] = polygon
                        converted_polygons.append(new_row)
                    else:
                        failed_conversions += 1
                except Exception as e:
                    failed_conversions += 1
            else:
                failed_conversions += 1
        elif geom.geom_type == 'Polygon':
            # Keep existing polygons
            converted_polygons.append(row)
    
    logger.info(f"Converted/kept {len(converted_polygons)} polygons")
    logger.info(f"Failed conversions: {failed_conversions}")
    
    if converted_polygons:
        # Create new GeoDataFrame with converted polygons
        polygons_gdf = gpd.GeoDataFrame(converted_polygons, crs="EPSG:4326")
        
        # Test spatial join with converted polygons
        test_listings_query = """
        SELECT 
            l.address,
            al.lat as latitude,
            al.lon as longitude
        FROM listings l
        LEFT JOIN address_locations al ON l.address = al.address
        WHERE al.lat IS NOT NULL AND al.lon IS NOT NULL
        LIMIT 100
        """
        
        listings_df = conn.execute(test_listings_query).fetchdf()
        geometry = [Point(lon, lat) for lon, lat in 
                   zip(listings_df['longitude'], listings_df['latitude'])]
        listings_gdf = gpd.GeoDataFrame(listings_df, geometry=geometry, crs="EPSG:4326")
        
        # Test spatial join
        logger.info("Testing spatial join with converted polygons...")
        join_result = gpd.sjoin(listings_gdf, polygons_gdf, how='inner', predicate='within')
        logger.info(f"Spatial join matches: {len(join_result)}")
        
        if len(join_result) > 0:
            logger.info("SUCCESS: Spatial join working with converted polygons!")
            logger.info(f"Sample matches:")
            for i, row in join_result.head(5).iterrows():
                logger.info(f"  {row['address']} -> Boundary type {row['kiinteistorajalaji']}")
        else:
            logger.warning("No matches found even with converted polygons")
            
            # Try with buffer as fallback
            logger.info("Trying buffer approach...")
            listings_buffered = listings_gdf.copy()
            listings_buffered['geometry'] = listings_buffered['geometry'].buffer(0.0001)  # ~10m buffer
            
            buffer_join = gpd.sjoin(listings_buffered, polygons_gdf, how='inner', predicate='intersects')
            logger.info(f"Buffer intersects matches: {len(buffer_join)}")
    
    conn.close()
    return len(converted_polygons) > 0

if __name__ == "__main__":
    analyze_and_fix_geometries()
