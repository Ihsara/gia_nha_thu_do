#!/usr/bin/env python3
"""
Phase 3C.1: District-Specific Tolerance Analysis
Purpose: Analyze 1,529 unmatched listings by postal code/district for tolerance optimization
Created: 2025-07-12 00:14
Usage: uv run python quickcheck/phase3c1_district_tolerance_analysis.py
"""

import sys
import json
import time
from pathlib import Path
from collections import defaultdict, Counter

import duckdb
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from oikotie.visualization.utils.data_loader import DataLoader
from oikotie.utils.enhanced_spatial_matching import EnhancedSpatialMatcher

def analyze_unmatched_by_district():
    """Analyze unmatched listings by postal code and district"""
    print("🔍 Phase 3C.1: District-Specific Tolerance Analysis")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        # Load data
        print("📋 Loading Helsinki listings and address data...")
        data_loader = DataLoader()
        
        # Get address-geocoded listings (same as Phase 3B.2)
        with data_loader as loader:
            conn = loader.connect()
            query = """
            SELECT DISTINCT 
                l.address,
                l.price_eur as price,
                l.listing_type,
                l.postal_code,
                al.lat,
                al.lon
            FROM listings l
            INNER JOIN address_locations al ON l.address = al.address
            WHERE al.lat IS NOT NULL 
                AND al.lon IS NOT NULL
                AND l.address LIKE '%Helsinki%'
            ORDER BY l.address
            """
            
            listings_df = pd.read_sql_query(query, conn)
        
        print(f"✅ Loaded {len(listings_df)} Helsinki listings with coordinates")
        
        # Load OSM buildings
        print("🏢 Loading OSM building footprints...")
        buildings_path = Path("data/helsinki_buildings_20250711_041142.geojson")
        if not buildings_path.exists():
            raise FileNotFoundError(f"OSM buildings file not found: {buildings_path}")
        
        buildings_gdf = gpd.read_file(buildings_path)
        print(f"✅ Loaded {len(buildings_gdf)} Helsinki building footprints")
        
        # Convert listings to GeoDataFrame
        print("🗺️ Converting listings to spatial data...")
        geometry = [Point(row.lon, row.lat) for row in listings_df.itertuples()]
        listings_gdf = gpd.GeoDataFrame(listings_df, geometry=geometry, crs="EPSG:4326")
        
        # Initialize Enhanced Spatial Matcher with current optimized settings
        print("⚙️ Initializing Enhanced Spatial Matcher (20.0m tolerance)...")
        matcher = EnhancedSpatialMatcher(
            tolerance_m=20.0,
            target_crs="EPSG:3067"
        )
        
        # Perform spatial matching to identify unmatched listings
        print("🎯 Performing spatial matching to identify unmatched listings...")
        match_results_df = matcher.enhanced_spatial_match(
            points_gdf=listings_gdf, 
            buildings_gdf=buildings_gdf,
            point_id_col='address',
            building_id_col='osm_id'
        )
        
        # Merge match results with original listings data for full information
        print("🔗 Merging match results with original listing data...")
        combined_df = listings_df.merge(match_results_df, on='address', how='left')
        print(f"✅ Combined data: {len(combined_df)} records")
        
        # Fill missing match_type for unmatched listings
        combined_df['match_type'] = combined_df['match_type'].fillna('no_match')
        
        # Check if tolerance_used_m column exists, if not create it
        if 'tolerance_used_m' not in combined_df.columns:
            combined_df['tolerance_used_m'] = 0.0
        else:
            combined_df['tolerance_used_m'] = combined_df['tolerance_used_m'].fillna(0.0)
        
        # Print column info for debugging
        print(f"📋 Combined dataframe columns: {list(combined_df.columns)}")
        print(f"📊 Sample match types: {combined_df['match_type'].value_counts()}")
        
        # Analyze match results by district
        print("\n📊 Analyzing match results by district...")
        
        # Count matches by type and district
        district_analysis = defaultdict(lambda: {
            'total': 0,
            'direct_matches': 0,
            'tolerance_matches': 0,
            'no_matches': 0,
            'match_rate': 0.0,
            'avg_tolerance_distance': 0.0,
            'max_tolerance_distance': 0.0
        })
        
        postcode_analysis = defaultdict(lambda: {
            'total': 0,
            'direct_matches': 0,
            'tolerance_matches': 0,
            'no_matches': 0,
            'match_rate': 0.0,
            'avg_tolerance_distance': 0.0,
            'max_tolerance_distance': 0.0
        })
        
        tolerance_distances = defaultdict(list)
        unmatched_listings = []
        
        for i, row in combined_df.iterrows():
            # Extract postal code from address string
            address = row.get('address', '')
            postcode = 'Unknown'
            
            # Handle addresses with newlines or commas
            if address:
                # Split by both commas and newlines
                parts = address.replace('\n', ', ').split(', ')
                for part in parts:
                    part = part.strip()
                    if len(part) == 5 and part.startswith('00') and part.isdigit():
                        postcode = part
                        break
                
                # Also try extracting from postal_code column directly
                if postcode == 'Unknown' and pd.notna(row.get('postal_code')):
                    postal_code_val = str(row.get('postal_code', '')).strip()
                    if len(postal_code_val) == 5 and postal_code_val.startswith('00') and postal_code_val.isdigit():
                        postcode = postal_code_val
            
            # Extract district from postal code or address
            district = 'Unknown'
            if postcode != 'Unknown':
                # Basic Helsinki district mapping based on postal codes
                postal_int = int(postcode)
                if 100 <= postal_int <= 180:
                    district = 'Central Helsinki'
                elif 200 <= postal_int <= 280:
                    district = 'North Helsinki'
                elif 300 <= postal_int <= 380:
                    district = 'Northwest Helsinki'
                elif 400 <= postal_int <= 480:
                    district = 'Northeast Helsinki'
                elif 500 <= postal_int <= 580:
                    district = 'East Helsinki'
                elif 600 <= postal_int <= 680:
                    district = 'Southeast Helsinki'
                elif 700 <= postal_int <= 780:
                    district = 'South Helsinki'
                elif 800 <= postal_int <= 880:
                    district = 'West Helsinki'
                elif 900 <= postal_int <= 980:
                    district = 'Southwest Helsinki'
                else:
                    district = f'Postal_{postcode}'
            
            # Update district stats
            district_analysis[district]['total'] += 1
            postcode_analysis[postcode]['total'] += 1
            
            match_type = row.get('match_type', 'no_match')
            if match_type == 'direct_contains':
                district_analysis[district]['direct_matches'] += 1
                postcode_analysis[postcode]['direct_matches'] += 1
            elif match_type == 'tolerance_buffer':
                district_analysis[district]['tolerance_matches'] += 1
                postcode_analysis[postcode]['tolerance_matches'] += 1
                distance = row.get('tolerance_used_m', 0)
                tolerance_distances[district].append(distance)
                tolerance_distances[postcode].append(distance)
            else:  # no_match
                district_analysis[district]['no_matches'] += 1
                postcode_analysis[postcode]['no_matches'] += 1
                unmatched_listings.append({
                    'address': row['address'],
                    'latitude': row['lat'],
                    'longitude': row['lon'],
                    'district': district,
                    'postcode': postcode,
                    'price': row.get('price'),
                    'listing_type': row.get('listing_type')
                })
        
        # Calculate match rates and distance statistics
        for district, stats in district_analysis.items():
            if stats['total'] > 0:
                matched = stats['direct_matches'] + stats['tolerance_matches']
                stats['match_rate'] = (matched / stats['total']) * 100
                
                if tolerance_distances[district]:
                    stats['avg_tolerance_distance'] = sum(tolerance_distances[district]) / len(tolerance_distances[district])
                    stats['max_tolerance_distance'] = max(tolerance_distances[district])
        
        for postcode, stats in postcode_analysis.items():
            if stats['total'] > 0:
                matched = stats['direct_matches'] + stats['tolerance_matches']
                stats['match_rate'] = (matched / stats['total']) * 100
                
                if tolerance_distances[postcode]:
                    stats['avg_tolerance_distance'] = sum(tolerance_distances[postcode]) / len(tolerance_distances[postcode])
                    stats['max_tolerance_distance'] = max(tolerance_distances[postcode])
        
        # Generate analysis report
        print("\n" + "="*60)
        print("📈 DISTRICT-SPECIFIC TOLERANCE OPTIMIZATION ANALYSIS")
        print("="*60)
        
        print(f"\n🎯 Overall Results:")
        total_listings = len(listings_df)
        total_unmatched = len(unmatched_listings)
        overall_match_rate = ((total_listings - total_unmatched) / total_listings) * 100
        print(f"   Total Listings: {total_listings}")
        print(f"   Unmatched Listings: {total_unmatched} ({(total_unmatched/total_listings)*100:.1f}%)")
        print(f"   Overall Match Rate: {overall_match_rate:.2f}%")
        
        # District analysis
        print(f"\n🏘️ Match Rate by District (sorted by unmatched count):")
        district_sorted = sorted(district_analysis.items(), 
                               key=lambda x: x[1]['no_matches'], reverse=True)
        
        for district, stats in district_sorted[:10]:  # Top 10 problematic districts
            if stats['total'] >= 5:  # Only show districts with meaningful sample size
                print(f"   {district:20} | {stats['total']:4d} listings | "
                      f"{stats['match_rate']:5.1f}% | {stats['no_matches']:3d} unmatched | "
                      f"Avg tolerance: {stats['avg_tolerance_distance']:4.1f}m")
        
        # Postal code analysis
        print(f"\n📮 Match Rate by Postal Code (worst performing):")
        postcode_sorted = sorted(postcode_analysis.items(), 
                                key=lambda x: x[1]['match_rate'] if x[1]['total'] >= 3 else 100)
        
        for postcode, stats in postcode_sorted[:15]:  # Top 15 problematic postal codes
            if stats['total'] >= 3:  # Only show postal codes with meaningful sample size
                print(f"   {postcode:6} | {stats['total']:3d} listings | "
                      f"{stats['match_rate']:5.1f}% | {stats['no_matches']:2d} unmatched | "
                      f"Avg tolerance: {stats['avg_tolerance_distance']:4.1f}m")
        
        # Phase 3C.1 optimization recommendations
        print(f"\n💡 Phase 3C.1 Optimization Recommendations:")
        
        # Identify districts/postcodes that could benefit from higher tolerance
        high_tolerance_candidates = []
        for district, stats in district_analysis.items():
            if (stats['total'] >= 5 and stats['no_matches'] >= 2 and 
                stats['avg_tolerance_distance'] > 15.0):
                high_tolerance_candidates.append((district, stats))
        
        if high_tolerance_candidates:
            print(f"\n🎯 Districts needing higher tolerance (current avg > 15m):")
            for district, stats in sorted(high_tolerance_candidates, 
                                        key=lambda x: x[1]['no_matches'], reverse=True)[:5]:
                suggested_tolerance = min(50.0, stats['max_tolerance_distance'] * 1.2)
                print(f"   {district:20} | Suggest {suggested_tolerance:.0f}m tolerance "
                      f"(current max: {stats['max_tolerance_distance']:.1f}m)")
        
        # Save detailed results
        results = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'phase': 'Phase 3C.1 - District Tolerance Analysis',
            'overall_stats': {
                'total_listings': total_listings,
                'unmatched_listings': total_unmatched,
                'overall_match_rate': overall_match_rate
            },
            'district_analysis': dict(district_analysis),
            'postcode_analysis': dict(postcode_analysis),
            'unmatched_listings': unmatched_listings,
            'optimization_recommendations': {
                'high_tolerance_candidates': [
                    {
                        'district': district,
                        'current_max_distance': stats['max_tolerance_distance'],
                        'suggested_tolerance': min(50.0, stats['max_tolerance_distance'] * 1.2),
                        'unmatched_count': stats['no_matches']
                    }
                    for district, stats in high_tolerance_candidates[:5]
                ]
            }
        }
        
        # Save results file
        results_file = f"data/phase3c1_district_analysis_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved: {results_file}")
        
        # Next steps
        print(f"\n🚀 Phase 3C.1 Next Steps:")
        print(f"   1. Implement custom tolerance per district/postal code")
        print(f"   2. Test higher tolerance values for identified problem areas")
        print(f"   3. Validate improvements using progressive validation framework")
        print(f"   4. Target: 81% → 83% match rate improvement")
        
        processing_time = time.time() - start_time
        print(f"\n✅ Phase 3C.1 District Analysis completed in {processing_time:.1f} seconds")
        
        return results
        
    except Exception as e:
        print(f"❌ Error in Phase 3C.1 analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """Main execution function"""
    analyze_unmatched_by_district()

if __name__ == "__main__":
    main()
