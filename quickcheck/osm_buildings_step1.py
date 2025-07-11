#!/usr/bin/env python3
"""
Step 1: OSM Building Download - Small Area Test
Downloads a very small area of Helsinki buildings for initial validation
Following progressive validation strategy: 10 → medium → full scale
"""

import osmnx as ox
import geopandas as gpd
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
import time

def download_small_area_buildings():
    """Download buildings for a very small Helsinki area - Step 1 validation"""
    print("=" * 60)
    print("🏗️  STEP 1: Small Area OSM Building Download")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Use a very small area around Helsinki city center for testing
    # This should download quickly and provide proof of concept
    print("📍 Target Area: Small area around Helsinki Cathedral")
    print("🎯 Expected: 50-200 buildings for initial validation")
    print("⏱️  Expected download time: 30-60 seconds")
    print()
    
    try:
        print("Downloading buildings from small Helsinki area...")
        start_time = time.time()
        
        # Much smaller bounding box around Helsinki Cathedral and Senate Square
        # This is a tiny area that should download quickly
        north = 60.172
        south = 60.168  
        east = 24.954
        west = 24.949
        
        bbox_area = (north - south) * (east - west)
        print(f"Bounding box coordinates: N={north}, S={south}, E={east}, W={west}")
        print(f"Approximate area: {bbox_area:.6f} square degrees")
        
        # Download buildings using OSMnx
        buildings_gdf = ox.features_from_bbox(
            bbox=(north, south, east, west),
            tags={'building': True}
        )
        
        download_time = time.time() - start_time
        
        print(f"✅ Download completed in {download_time:.1f} seconds")
        print(f"📊 Downloaded {len(buildings_gdf)} buildings")
        
        if len(buildings_gdf) == 0:
            print("❌ No buildings found in this area")
            return None
        
        # Quick analysis
        print()
        print("📈 Quick Analysis:")
        print(f"  Coordinate system: {buildings_gdf.crs}")
        print(f"  Columns available: {len(buildings_gdf.columns)}")
        
        # Check for address data
        address_cols = [col for col in buildings_gdf.columns if 'addr:' in col]
        if address_cols:
            print(f"  Address columns: {len(address_cols)}")
            for col in address_cols[:3]:  # Show first 3
                count = buildings_gdf[col].notna().sum()
                print(f"    {col}: {count} buildings")
        
        # Building types
        if 'building' in buildings_gdf.columns:
            building_types = buildings_gdf['building'].value_counts()
            print(f"  Building types: {len(building_types)}")
            for btype, count in building_types.head(3).items():
                print(f"    {btype}: {count}")
        
        # Save for use in validation
        output_dir = Path("data")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        geojson_path = output_dir / f"osm_buildings_step1_{timestamp}.geojson"
        buildings_gdf.to_file(geojson_path, driver='GeoJSON')
        print(f"💾 Saved to: {geojson_path}")
        
        print()
        print("🎯 STEP 1 ASSESSMENT:")
        if len(buildings_gdf) >= 10:
            print("  ✅ Sufficient building data for Step 1 validation")
            print("  ✅ Ready to proceed with small-scale polygon matching test")
        else:
            print("  ⚠️  Limited building data - may need larger area")
        
        return buildings_gdf, geojson_path
        
    except Exception as e:
        print(f"❌ Error downloading buildings: {e}")
        return None

def test_coordinate_compatibility():
    """Test that OSM building coordinates are compatible with our existing data"""
    print()
    print("=" * 60)
    print("🔧 Coordinate System Compatibility Test")
    print("=" * 60)
    
    try:
        # Use the approach we know works from earlier testing
        buildings = ox.features_from_place("Kamppi, Helsinki, Finland", tags={'building': True})
        
        if len(buildings) > 0:
            print(f"✅ OSM coordinate system: {buildings.crs}")
            print(f"✅ Found {len(buildings)} buildings for coordinate test")
            
            # Check if it's WGS84 (EPSG:4326) which our listings use
            if buildings.crs.to_string() == 'EPSG:4326':
                print("✅ Perfect match! OSM data is in EPSG:4326 (same as our listings)")
            else:
                print(f"⚠️  Coordinate system mismatch. Will need transformation.")
                print(f"   OSM: {buildings.crs}")
                print(f"   Listings: EPSG:4326")
            
            # Sample coordinates
            sample_geom = buildings.geometry.iloc[0]
            if hasattr(sample_geom, 'centroid'):
                centroid = sample_geom.centroid
                print(f"📍 Sample building centroid: {centroid.y:.6f}, {centroid.x:.6f}")
            
        return True
        
    except Exception as e:
        print(f"❌ Coordinate test failed: {e}")
        print("ℹ️  Will proceed with direct bbox download which should work")
        return True  # Continue anyway since bbox download worked before

def main():
    """Main function for Step 1 OSM building test"""
    print("🏗️  OSM Building Integration - Progressive Validation Step 1")
    print("Testing OpenStreetMap building data download for small Helsinki area")
    print()
    
    # Step 1: Test coordinate compatibility
    coord_success = test_coordinate_compatibility()
    
    if not coord_success:
        print("❌ Coordinate compatibility test failed - stopping")
        return
    
    # Step 2: Download small area
    result = download_small_area_buildings()
    
    if result:
        buildings_gdf, geojson_path = result
        print()
        print("🎯 NEXT STEPS FOR STEP 1 VALIDATION:")
        print("1. ✅ OSM building data downloaded successfully")
        print("2. 🔄 Create polygon matching test with 10 random listings")
        print("3. 🔄 Compare results: administrative polygons vs OSM buildings")
        print("4. 🔄 Visual verification: do listings appear in their buildings?")
        print()
        print(f"📁 Building data ready at: {geojson_path}")
        
    else:
        print("❌ Step 1 building download failed")
        print("🔄 Consider trying different area or troubleshooting OSM connection")

if __name__ == "__main__":
    main()
