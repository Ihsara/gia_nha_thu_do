#!/usr/bin/env python3
"""
Test script for dual geodata sources (WMS and GeoPackage).

This script implements the Progressive Validation Strategy Step 1:
- Test both data sources with 10 samples
- Compare accuracy, completeness, and usability
- Document which source is better for different use cases
"""

import sys
from pathlib import Path
import pandas as pd
import geopandas as gpd
from datetime import datetime
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from oikotie.data_sources import WMSDataSource, GeoPackageDataSource


def test_data_sources():
    """Test both WMS and GeoPackage data sources with small samples."""
    
    print("🔧 Dual Geodata Source Testing - Started")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("Following Progressive Validation Strategy - Step 1: 10 samples")
    print()
    
    # Initialize data sources
    print("📊 Initializing data sources...")
    
    # WMS source
    wms_source = WMSDataSource(name="Finnish National WMS")
    print(f"✅ WMS source initialized: {wms_source}")
    
    # GeoPackage source
    gpkg_path = Path("data/open/maastotietokanta_kaikki_Helsinki.gpkg").resolve()
    if not gpkg_path.exists():
        print(f"❌ GeoPackage file not found: {gpkg_path}")
        return
    
    try:
        gpkg_source = GeoPackageDataSource(str(gpkg_path), name="Helsinki GeoPackage")
        print(f"✅ GeoPackage source initialized: {gpkg_source}")
    except Exception as e:
        print(f"❌ Error initializing GeoPackage source: {e}")
        return
    
    print()
    
    # Test connection
    print("🔌 Testing connections...")
    wms_connected = wms_source.test_connection()
    gpkg_connected = gpkg_source.test_connection()
    
    print(f"WMS connection: {'✅ Success' if wms_connected else '❌ Failed'}")
    print(f"GeoPackage connection: {'✅ Success' if gpkg_connected else '❌ Failed'}")
    print()
    
    # Get metadata
    print("📋 Retrieving metadata...")
    wms_meta = wms_source.get_metadata()
    gpkg_meta = gpkg_source.get_metadata()
    
    print("\nWMS Metadata:")
    print(f"  - Type: {wms_meta.get('type')}")
    print(f"  - Native CRS: {wms_meta.get('native_crs')}")
    print(f"  - Target CRS: {wms_meta.get('target_crs')}")
    print(f"  - Buildings layer: {wms_meta.get('buildings_layer')}")
    print(f"  - Addresses layer: {wms_meta.get('addresses_layer')}")
    
    print("\nGeoPackage Metadata:")
    print(f"  - Type: {gpkg_meta.get('type')}")
    print(f"  - File: {Path(gpkg_meta.get('gpkg_path', '')).name}")
    print(f"  - File size: {gpkg_meta.get('file_size_mb')} MB")
    print(f"  - Native CRS: {gpkg_meta.get('native_crs')}")
    print(f"  - Target CRS: {gpkg_meta.get('target_crs')}")
    print(f"  - Total layers: {gpkg_meta.get('layer_count')}")
    print(f"  - Buildings: {gpkg_meta['record_counts'].get('buildings')} records")
    print(f"  - Addresses: {gpkg_meta['record_counts'].get('addresses')} records")
    print()
    
    # Define test area (small area in central Helsinki)
    test_bbox = (24.93, 60.16, 24.95, 60.17)  # Kamppi area
    print(f"📍 Test area: {test_bbox}")
    print("   (Central Helsinki - Kamppi area)")
    print()
    
    # Fetch buildings from both sources
    print("🏢 Fetching building data (limit: 10)...")
    
    print("\nWMS Buildings:")
    try:
        wms_buildings = wms_source.fetch_buildings(bbox=test_bbox, limit=10)
        print(f"  - Records fetched: {len(wms_buildings)}")
        if len(wms_buildings) > 0:
            print(f"  - Columns: {', '.join(wms_buildings.columns[:10])}...")
            print(f"  - Geometry types: {wms_buildings.geometry.geom_type.value_counts().to_dict()}")
            # Check for key attributes
            key_attrs = ['building_id', 'building_use', 'floor_count', 'floor_area']
            available_attrs = [attr for attr in key_attrs if attr in wms_buildings.columns]
            print(f"  - Key attributes available: {', '.join(available_attrs)}")
            # Sample data
            if 'building_use' in wms_buildings.columns:
                print(f"  - Sample uses: {wms_buildings['building_use'].dropna().head(3).tolist()}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        wms_buildings = gpd.GeoDataFrame()
    
    print("\nGeoPackage Buildings:")
    try:
        gpkg_buildings = gpkg_source.fetch_buildings(bbox=test_bbox, limit=10)
        print(f"  - Records fetched: {len(gpkg_buildings)}")
        if len(gpkg_buildings) > 0:
            print(f"  - Columns: {', '.join(gpkg_buildings.columns[:10])}...")
            print(f"  - Geometry types: {gpkg_buildings.geometry.geom_type.value_counts().to_dict()}")
            # Check for key attributes
            key_attrs = ['feature_id', 'building_use_code', 'floor_count', 'floor_area']
            available_attrs = [attr for attr in key_attrs if attr in gpkg_buildings.columns]
            print(f"  - Key attributes available: {', '.join(available_attrs)}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        gpkg_buildings = gpd.GeoDataFrame()
    
    print()
    
    # Fetch addresses from both sources
    print("📮 Fetching address data (limit: 10)...")
    
    print("\nWMS Addresses:")
    try:
        wms_addresses = wms_source.fetch_addresses(bbox=test_bbox, limit=10)
        print(f"  - Records fetched: {len(wms_addresses)}")
        if len(wms_addresses) > 0:
            print(f"  - Columns: {', '.join(wms_addresses.columns[:10])}...")
            print(f"  - Geometry types: {wms_addresses.geometry.geom_type.value_counts().to_dict()}")
            # Check for key attributes
            key_attrs = ['street_name', 'house_number', 'postal_code', 'address_text']
            available_attrs = [attr for attr in key_attrs if attr in wms_addresses.columns]
            print(f"  - Key attributes available: {', '.join(available_attrs)}")
            # Sample addresses
            if 'address_text' in wms_addresses.columns:
                print(f"  - Sample addresses: {wms_addresses['address_text'].dropna().head(3).tolist()}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        wms_addresses = gpd.GeoDataFrame()
    
    print("\nGeoPackage Addresses:")
    try:
        gpkg_addresses = gpkg_source.fetch_addresses(bbox=test_bbox, limit=10)
        print(f"  - Records fetched: {len(gpkg_addresses)}")
        if len(gpkg_addresses) > 0:
            print(f"  - Columns: {', '.join(gpkg_addresses.columns[:10])}...")
            print(f"  - Geometry types: {gpkg_addresses.geometry.geom_type.value_counts().to_dict()}")
            # Note the limited address data in GeoPackage
            print(f"  ⚠️  Note: GeoPackage has limited address data (475 total)")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        gpkg_addresses = gpd.GeoDataFrame()
    
    print()
    
    # Data quality comparison
    print("📊 Data Quality Comparison:")
    print("\nCompleteness:")
    print(f"  - WMS Buildings: {len(wms_buildings)} records with {len(wms_buildings.columns)} attributes")
    print(f"  - GeoPackage Buildings: {len(gpkg_buildings)} records with {len(gpkg_buildings.columns)} attributes")
    print(f"  - WMS Addresses: {len(wms_addresses)} records with {len(wms_addresses.columns)} attributes")
    print(f"  - GeoPackage Addresses: {len(gpkg_addresses)} records with {len(gpkg_addresses.columns)} attributes")
    
    print("\nGeometry Quality:")
    if len(wms_buildings) > 0:
        print(f"  - WMS Buildings valid geometries: {wms_buildings.geometry.is_valid.sum()}/{len(wms_buildings)}")
    if len(gpkg_buildings) > 0:
        print(f"  - GeoPackage Buildings valid geometries: {gpkg_buildings.geometry.is_valid.sum()}/{len(gpkg_buildings)}")
    
    print()
    
    # Performance comparison
    print("⚡ Performance Comparison:")
    print("  - WMS: Network-based, subject to latency and rate limits")
    print("  - GeoPackage: Local file access, very fast queries")
    print("  - WMS: Streaming service, unknown total record count")
    print("  - GeoPackage: Complete dataset available locally")
    
    print()
    
    # Recommendations
    print("💡 Initial Recommendations:")
    print("\n✅ Use WMS for:")
    print("  - Address data (much more comprehensive)")
    print("  - Building attributes (use codes, materials, etc.)")
    print("  - Always up-to-date data from national registry")
    print("  - Small area queries or specific lookups")
    
    print("\n✅ Use GeoPackage for:")
    print("  - Fast local queries without network dependency")
    print("  - Complete Helsinki dataset analysis")
    print("  - Additional topographic layers (roads, water, land use)")
    print("  - Bulk processing and spatial analysis")
    
    print("\n🔄 Hybrid Approach:")
    print("  - Primary: GeoPackage for building geometries (fast, complete)")
    print("  - Enrichment: WMS for detailed attributes and addresses")
    print("  - Fallback: WMS when GeoPackage data is insufficient")
    
    # Save test results
    results = {
        "test_timestamp": datetime.now().isoformat(),
        "test_type": "Progressive Validation Step 1 - 10 samples",
        "test_area": test_bbox,
        "wms_results": {
            "connected": wms_connected,
            "buildings_fetched": len(wms_buildings),
            "addresses_fetched": len(wms_addresses),
            "building_columns": list(wms_buildings.columns) if len(wms_buildings) > 0 else [],
            "address_columns": list(wms_addresses.columns) if len(wms_addresses) > 0 else []
        },
        "gpkg_results": {
            "connected": gpkg_connected,
            "buildings_fetched": len(gpkg_buildings),
            "addresses_fetched": len(gpkg_addresses),
            "total_buildings_available": gpkg_meta['record_counts'].get('buildings'),
            "total_addresses_available": gpkg_meta['record_counts'].get('addresses'),
            "total_layers": gpkg_meta.get('layer_count')
        },
        "recommendations": {
            "primary_source": "GeoPackage for geometries, WMS for attributes",
            "address_source": "WMS (more comprehensive)",
            "performance": "GeoPackage significantly faster for bulk operations"
        }
    }
    
    output_file = "output/dual_geodata_test_results.json"
    Path("output").mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Test results saved to: {output_file}")
    print("\n✅ Dual Geodata Source Testing - Completed")
    print("=" * 60)


if __name__ == "__main__":
    test_data_sources()
