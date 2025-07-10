#!/usr/bin/env python3
"""
Debug script to understand why spatial join is failing
"""

import duckdb
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.geometry import Point

def debug_data():
    conn = duckdb.connect('data/real_estate.duckdb')
    
    print('=== LISTINGS DATA ===')
    listings = conn.execute('SELECT COUNT(*) as total, COUNT(CASE WHEN deleted_ts IS NULL THEN 1 END) as active FROM listings').fetchone()
    print(f'Total listings: {listings[0]}, Active listings: {listings[1]}')

    print('\n=== ADDRESS LOCATIONS ===')
    addr_locs = conn.execute('SELECT COUNT(*) as total, COUNT(lat) as with_lat, COUNT(lon) as with_lon FROM address_locations').fetchone()
    print(f'Total address locations: {addr_locs[0]}, With lat: {addr_locs[1]}, With lon: {addr_locs[2]}')

    print('\n=== PROPERTY POLYGONS ===')
    poly_count = conn.execute('SELECT COUNT(*) as total, COUNT(geometry_wkt) as with_geom FROM helsinki_02_kiinteistorajansijaintitiedot').fetchone()
    print(f'Total polygon records: {poly_count[0]}, With geometry: {poly_count[1]}')

    print('\n=== POLYGON TYPES ===')
    types = conn.execute('SELECT kiinteistorajalaji, COUNT(*) FROM helsinki_02_kiinteistorajansijaintitiedot GROUP BY kiinteistorajalaji ORDER BY COUNT(*) DESC').fetchall()
    for t in types:
        print(f'Type {t[0]}: {t[1]} records')

    print('\n=== LISTING COORDINATES ===')
    coords = conn.execute('''
    SELECT 
        MIN(al.lat) as min_lat, MAX(al.lat) as max_lat,
        MIN(al.lon) as min_lon, MAX(al.lon) as max_lon,
        COUNT(*) as listings_with_coords
    FROM listings l 
    LEFT JOIN address_locations al ON l.address = al.address 
    WHERE l.deleted_ts IS NULL AND al.lat IS NOT NULL AND al.lon IS NOT NULL
    ''').fetchone()
    print(f'Lat range: {coords[0]} to {coords[1]}')
    print(f'Lon range: {coords[2]} to {coords[3]}')
    print(f'Listings with coordinates: {coords[4]}')

    # Sample some actual listings with coordinates
    print('\n=== SAMPLE LISTINGS WITH COORDINATES ===')
    sample_listings = conn.execute('''
    SELECT l.address, l.city, al.lat, al.lon 
    FROM listings l 
    LEFT JOIN address_locations al ON l.address = al.address 
    WHERE l.deleted_ts IS NULL AND al.lat IS NOT NULL AND al.lon IS NOT NULL
    LIMIT 10
    ''').fetchall()
    
    for listing in sample_listings:
        print(f'Address: {listing[0]}, City: {listing[1]}, Lat: {listing[2]}, Lon: {listing[3]}')

    # Check coordinate system of polygons
    print('\n=== SAMPLE POLYGON GEOMETRIES ===')
    sample_polygons = conn.execute('''
    SELECT kiinteistorajalaji, LEFT(geometry_wkt, 100) as geom_sample 
    FROM helsinki_02_kiinteistorajansijaintitiedot 
    WHERE geometry_wkt IS NOT NULL 
    LIMIT 5
    ''').fetchall()
    
    for poly in sample_polygons:
        print(f'Type {poly[0]}: {poly[1]}...')

    conn.close()

if __name__ == "__main__":
    debug_data()
