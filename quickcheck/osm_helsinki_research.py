#!/usr/bin/env python3
"""
OSM Helsinki Building Data Research Script
Tests OpenStreetMap Overpass API for Helsinki building footprint availability
"""

import requests
import json
from datetime import datetime

def test_osm_building_data():
    """Test OSM Overpass API for Helsinki building data availability"""
    
    print("=" * 60)
    print("OSM Helsinki Building Data Research")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # OSM Overpass API configuration
    overpass_url = 'http://overpass-api.de/api/interpreter'
    
    # Helsinki bounding box: roughly covers Helsinki city center and surrounding areas
    # Format: [south, west, north, east] = [lat_min, lon_min, lat_max, lon_max]
    bbox = [60.1, 24.8, 60.3, 25.1]  # Helsinki area
    
    overpass_query = f'''[out:json][timeout:25];
(
  way[building][bbox:{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}];
  relation[building][bbox:{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}];
);
(._;>;);
out geom;'''

    print(f"Testing OSM Overpass API...")
    print(f"Query URL: {overpass_url}")
    print(f"Bounding box: Helsinki area {bbox}")
    print(f"Query timeout: 25 seconds")
    print()

    try:
        print("Sending request to OSM Overpass API...")
        response = requests.post(overpass_url, data=overpass_query, timeout=30)
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ OSM API request successful!")
            
            # Parse the JSON response
            data = response.json()
            elements = data.get('elements', [])
            
            # Count different types of elements
            ways = [e for e in elements if e.get('type') == 'way' and 'building' in e.get('tags', {})]
            relations = [e for e in elements if e.get('type') == 'relation' and 'building' in e.get('tags', {})]
            nodes = [e for e in elements if e.get('type') == 'node']
            
            print()
            print("📊 Data Summary:")
            print(f"  Total elements: {len(elements)}")
            print(f"  Building ways: {len(ways)}")
            print(f"  Building relations: {len(relations)}")
            print(f"  Nodes: {len(nodes)}")
            
            # Analyze building types
            if ways:
                print()
                print("🏢 Sample Building Analysis:")
                
                # Analyze first few buildings
                sample_size = min(5, len(ways))
                for i, way in enumerate(ways[:sample_size]):
                    tags = way.get('tags', {})
                    geometry = way.get('geometry', [])
                    
                    print(f"  Building {i+1} (ID: {way.get('id')}):")
                    print(f"    Building type: {tags.get('building', 'unspecified')}")
                    print(f"    Geometry nodes: {len(geometry)}")
                    
                    # Show additional tags if available
                    interesting_tags = ['addr:street', 'addr:housenumber', 'addr:postcode', 'levels', 'height']
                    for tag in interesting_tags:
                        if tag in tags:
                            print(f"    {tag}: {tags[tag]}")
                
                # Building type statistics
                building_types = {}
                for way in ways:
                    building_type = way.get('tags', {}).get('building', 'unspecified')
                    building_types[building_type] = building_types.get(building_type, 0) + 1
                
                print()
                print("📈 Building Type Statistics:")
                for building_type, count in sorted(building_types.items(), key=lambda x: x[1], reverse=True):
                    print(f"  {building_type}: {count} buildings")
            
            # Estimate data completeness
            print()
            print("💡 Assessment for Polygon Matching:")
            if len(ways) > 1000:
                print("  ✅ Excellent building coverage - high potential for accurate matching")
            elif len(ways) > 500:
                print("  ✅ Good building coverage - suitable for polygon matching")
            elif len(ways) > 100:
                print("  ⚠️  Moderate building coverage - may work but check quality")
            else:
                print("  ❌ Low building coverage - may not be suitable for comprehensive matching")
            
            return True, len(ways), len(relations)
            
        else:
            print(f"❌ OSM API request failed!")
            print(f"Error response: {response.text[:200]}")
            return False, 0, 0
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout - OSM Overpass API may be slow or unavailable")
        print("This could be due to high server load. Try again later.")
        return False, 0, 0
        
    except requests.exceptions.ConnectionError:
        print("🌐 Connection Error - Unable to reach OSM Overpass API")
        print("Check internet connection and try again.")
        return False, 0, 0
        
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        return False, 0, 0

def test_osmnx_library():
    """Test if OSMnx library is available and working"""
    print()
    print("=" * 60)
    print("OSMnx Library Test")
    print("=" * 60)
    
    try:
        import osmnx as ox
        print("✅ OSMnx library is available!")
        print(f"OSMnx version: {ox.__version__}")
        
        # Test basic functionality with a small area
        print()
        print("Testing OSMnx building download for small Helsinki area...")
        
        # Define a small area around Helsinki city center
        place_name = "Kamppi, Helsinki, Finland"
        
        try:
            # Download buildings for a small area
            buildings = ox.features_from_place(place_name, tags={'building': True})
            print(f"✅ Successfully downloaded {len(buildings)} buildings from {place_name}")
            
            # Show sample building info
            if len(buildings) > 0:
                sample = buildings.iloc[0]
                print()
                print("Sample building properties:")
                for key, value in sample.items():
                    if pd.notna(value) and key != 'geometry':
                        print(f"  {key}: {value}")
            
            return True, len(buildings)
            
        except Exception as e:
            print(f"❌ OSMnx building download failed: {e}")
            return False, 0
            
    except ImportError:
        print("❌ OSMnx library not available")
        print("Install with: uv add osmnx")
        return False, 0
    except Exception as e:
        print(f"❌ OSMnx library error: {e}")
        return False, 0

if __name__ == "__main__":
    # Import pandas for OSMnx test
    try:
        import pandas as pd
    except ImportError:
        print("Pandas not available - some features may be limited")
        pd = None
    
    # Run tests
    success1, ways_count, relations_count = test_osm_building_data()
    success2, osmnx_buildings = test_osmnx_library() if pd else (False, 0)
    
    # Summary
    print()
    print("=" * 60)
    print("RESEARCH SUMMARY")
    print("=" * 60)
    
    if success1:
        print(f"✅ OSM Overpass API: {ways_count} building ways, {relations_count} building relations")
    else:
        print("❌ OSM Overpass API: Failed")
    
    if success2:
        print(f"✅ OSMnx Library: {osmnx_buildings} buildings downloaded successfully")
    else:
        print("❌ OSMnx Library: Not available or failed")
    
    print()
    print("🎯 RECOMMENDATION:")
    if success1 and ways_count > 500:
        print("Use OSM Overpass API for building data - good coverage available")
        print("Next step: Implement OSM building download and integration pipeline")
    elif success2 and osmnx_buildings > 100:
        print("Use OSMnx library for building data - easier integration")
        print("Next step: Install OSMnx and implement building download pipeline")
    else:
        print("Consider alternative data sources or smaller test areas")
        print("Next step: Research Helsinki city open data for building footprints")
    
    print()
    print("Script completed successfully!")
