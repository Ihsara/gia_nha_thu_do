#!/usr/bin/env python3
"""
Phase 3C.2: Custom Tolerance Implementation
Purpose: Implement district-specific tolerance optimization based on Phase 3C.1 analysis
Created: 2025-07-12 00:32
Usage: uv run python quickcheck/phase3c2_custom_tolerance_implementation.py
"""

import sys
import json
import time
from pathlib import Path
from collections import defaultdict

import duckdb
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import numpy as np

from oikotie.visualization.utils.data_loader import DataLoader
from oikotie.utils.enhanced_spatial_matching import EnhancedSpatialMatcher

class CustomToleranceMatcher:
    """Enhanced spatial matcher with district-specific tolerance optimization"""
    
    def __init__(self, base_tolerance_m=20.0, target_crs="EPSG:3067"):
        self.base_tolerance_m = base_tolerance_m
        self.target_crs = target_crs
        
        # District-specific tolerance mapping based on Phase 3C.1 analysis
        self.district_tolerance_map = {
            # Problem districts requiring higher tolerance
            'Central Helsinki': 35.0,      # 45.6% → target 75%+
            'Southwest Helsinki': 35.0,    # 41.5% → target 75%+
            'Postal_00970': 50.0,         # 0.0% → target 60%+
            'Postal_00990': 50.0,         # 0.0% → target 60%+
            'Postal_00960': 50.0,         # 0.0% → target 60%+
            'Postal_00980': 40.0,         # 0.2% → target 65%+
            'Postal_00950': 30.0,         # 15.0% → target 70%+
            'Postal_00180': 30.0,         # 17.1% → target 70%+
            
            # Well-performing districts - maintain current performance
            'Northeast Helsinki': 20.0,    # 90.3% - keep efficient
            'South Helsinki': 20.0,        # 95.4% - keep efficient
            'Northwest Helsinki': 20.0,    # 94.6% - keep efficient
            'Southeast Helsinki': 20.0,    # 88.2% - keep efficient
            'East Helsinki': 20.0,         # 81.9% - keep efficient
            'West Helsinki': 25.0,         # 81.0% - slight increase
            
            # Fallback for unknown districts
            'Unknown': 25.0
        }
        
        # Postal code specific tolerance mapping for fine-grained control
        self.postal_tolerance_map = {
            # Critical postal codes with 0% match rates
            '00970': 50.0,
            '00990': 50.0, 
            '00960': 50.0,
            '00890': 45.0,
            '00980': 40.0,
            
            # Low performing postal codes
            '00950': 30.0,
            '00180': 30.0,
            '00880': 25.0,
            '00430': 25.0,
            '00580': 25.0,
            '00640': 25.0
        }
    
    def extract_district_and_postal(self, address, postal_code_col=None):
        """Extract district and postal code from address or postal_code column"""
        postcode = 'Unknown'
        
        # Extract postal code from address string
        if address:
            parts = address.replace('\n', ', ').split(', ')
            for part in parts:
                part = part.strip()
                if len(part) == 5 and part.startswith('00') and part.isdigit():
                    postcode = part
                    break
        
        # Also try postal_code column if available
        if postcode == 'Unknown' and postal_code_col and pd.notna(postal_code_col):
            postal_code_val = str(postal_code_col).strip()
            if len(postal_code_val) == 5 and postal_code_val.startswith('00') and postal_code_val.isdigit():
                postcode = postal_code_val
        
        # Map postal code to district
        district = 'Unknown'
        if postcode != 'Unknown':
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
        
        return district, postcode
    
    def get_optimal_tolerance(self, district, postcode):
        """Get optimal tolerance for specific district and postal code"""
        # Prioritize postal code specific tolerance
        if postcode in self.postal_tolerance_map:
            return self.postal_tolerance_map[postcode]
        
        # Fall back to district tolerance
        if district in self.district_tolerance_map:
            return self.district_tolerance_map[district]
        
        # Default tolerance
        return self.base_tolerance_m
    
    def custom_tolerance_spatial_match(self, listings_gdf, buildings_gdf, point_id_col='address', building_id_col='osm_id'):
        """Perform spatial matching with custom tolerance per district/postal code"""
        print("🔧 Custom Tolerance Spatial Matching - Started")
        print("=" * 60)
        
        start_time = time.time()
        
        # Group listings by tolerance requirements
        tolerance_groups = defaultdict(list)
        tolerance_stats = defaultdict(int)
        
        print("📊 Analyzing tolerance requirements by district/postal code...")
        
        for idx, row in listings_gdf.iterrows():
            district, postcode = self.extract_district_and_postal(
                row.get('address', ''), 
                row.get('postal_code')
            )
            
            optimal_tolerance = self.get_optimal_tolerance(district, postcode)
            tolerance_groups[optimal_tolerance].append(idx)
            tolerance_stats[optimal_tolerance] += 1
        
        print("\n🎯 Tolerance Distribution:")
        for tolerance, count in sorted(tolerance_stats.items()):
            print(f"   {tolerance:4.1f}m tolerance: {count:4d} listings ({count/len(listings_gdf)*100:5.1f}%)")
        
        # Process each tolerance group separately
        all_results = []
        total_matched = 0
        processing_stats = {
            'direct_matches': 0,
            'tolerance_matches': 0,
            'no_matches': 0,
            'total_processed': 0
        }
        
        print(f"\n🚀 Processing {len(tolerance_groups)} tolerance groups...")
        
        for tolerance, indices in tolerance_groups.items():
            if not indices:
                continue
                
            print(f"\n   Processing {len(indices)} listings with {tolerance}m tolerance...")
            
            # Create subset for this tolerance group
            subset_gdf = listings_gdf.iloc[indices].copy()
            
            # Initialize matcher for this tolerance
            matcher = EnhancedSpatialMatcher(
                tolerance_m=tolerance,
                target_crs=self.target_crs
            )
            
            # Perform spatial matching for this group
            try:
                group_results = matcher.enhanced_spatial_match(
                    points_gdf=subset_gdf,
                    buildings_gdf=buildings_gdf,
                    point_id_col=point_id_col,
                    building_id_col=building_id_col
                )
                
                # Add tolerance information to results
                group_results['applied_tolerance_m'] = tolerance
                
                # Update statistics
                group_matched = len(group_results[group_results['match_type'] != 'no_match'])
                total_matched += group_matched
                
                # Count match types
                direct_count = len(group_results[group_results['match_type'] == 'direct_contains'])
                tolerance_count = len(group_results[group_results['match_type'] == 'tolerance_buffer'])
                no_match_count = len(group_results[group_results['match_type'] == 'no_match'])
                
                processing_stats['direct_matches'] += direct_count
                processing_stats['tolerance_matches'] += tolerance_count
                processing_stats['no_matches'] += no_match_count
                processing_stats['total_processed'] += len(group_results)
                
                print(f"      → {group_matched}/{len(subset_gdf)} matched ({group_matched/len(subset_gdf)*100:.1f}%)")
                
                all_results.append(group_results)
                
            except Exception as e:
                print(f"      ❌ Error processing tolerance group {tolerance}m: {e}")
                continue
        
        # Combine all results
        if all_results:
            combined_results = pd.concat(all_results, ignore_index=True)
        else:
            # Create empty results dataframe with expected columns
            combined_results = pd.DataFrame(columns=[
                point_id_col, building_id_col, 'match_type', 'distance_m',
                'is_direct_match', 'is_tolerance_match', 'applied_tolerance_m'
            ])
        
        # Calculate final statistics
        total_processing_time = time.time() - start_time
        overall_match_rate = (total_matched / len(listings_gdf)) * 100 if len(listings_gdf) > 0 else 0
        processing_speed = len(listings_gdf) / total_processing_time if total_processing_time > 0 else 0
        
        # Print final results
        print(f"\n📊 Custom Tolerance Matching Results:")
        print(f"   Total points processed: {processing_stats['total_processed']}")
        print(f"   Successfully matched: {total_matched}")
        print(f"   Match rate: {overall_match_rate:.2f}%")
        
        print(f"\n📈 Match Type Breakdown:")
        print(f"   Direct contains matches: {processing_stats['direct_matches']} ({processing_stats['direct_matches']/len(listings_gdf)*100:.1f}%)")
        print(f"   Tolerance buffer matches: {processing_stats['tolerance_matches']} ({processing_stats['tolerance_matches']/len(listings_gdf)*100:.1f}%)")
        print(f"   No matches: {processing_stats['no_matches']} ({processing_stats['no_matches']/len(listings_gdf)*100:.1f}%)")
        
        print(f"\n⏱️  Performance Metrics:")
        print(f"   Total processing time: {total_processing_time:.2f}s")
        print(f"   Processing speed: {processing_speed:.1f} points/second")
        
        # Calculate improvement over baseline 20m tolerance
        baseline_match_rate = 80.98  # From Phase 3B.2 results
        improvement = overall_match_rate - baseline_match_rate
        print(f"\n💡 Optimization Benefits:")
        print(f"   Baseline (20m): {baseline_match_rate:.2f}%")
        print(f"   Custom tolerance: {overall_match_rate:.2f}%")
        print(f"   Improvement: {improvement:+.2f} percentage points")
        
        return combined_results, {
            'total_processed': processing_stats['total_processed'],
            'total_matched': total_matched,
            'match_rate': overall_match_rate,
            'improvement_over_baseline': improvement,
            'processing_time': total_processing_time,
            'processing_speed': processing_speed,
            'tolerance_distribution': dict(tolerance_stats),
            'match_type_breakdown': {
                'direct_matches': processing_stats['direct_matches'],
                'tolerance_matches': processing_stats['tolerance_matches'],
                'no_matches': processing_stats['no_matches']
            }
        }

def test_custom_tolerance_optimization():
    """Test custom tolerance optimization with Phase 3C.1 insights"""
    print("🔍 Phase 3C.2: Custom Tolerance Implementation")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        # Load data using same approach as Phase 3C.1
        print("📋 Loading Helsinki listings and address data...")
        data_loader = DataLoader()
        
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
        
        # Initialize Custom Tolerance Matcher
        print("⚙️ Initializing Custom Tolerance Matcher...")
        custom_matcher = CustomToleranceMatcher(
            base_tolerance_m=20.0,
            target_crs="EPSG:3067"
        )
        
        # Perform custom tolerance spatial matching
        print("🎯 Performing custom tolerance spatial matching...")
        match_results, performance_stats = custom_matcher.custom_tolerance_spatial_match(
            listings_gdf=listings_gdf,
            buildings_gdf=buildings_gdf,
            point_id_col='address',
            building_id_col='osm_id'
        )
        
        # Save results
        results = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'phase': 'Phase 3C.2 - Custom Tolerance Implementation',
            'performance_stats': performance_stats,
            'tolerance_mapping': {
                'district_tolerance_map': custom_matcher.district_tolerance_map,
                'postal_tolerance_map': custom_matcher.postal_tolerance_map
            },
            'baseline_comparison': {
                'phase_3b2_match_rate': 80.98,
                'custom_tolerance_match_rate': performance_stats['match_rate'],
                'improvement': performance_stats['improvement_over_baseline']
            }
        }
        
        # Save detailed results
        results_file = f"data/phase3c2_custom_tolerance_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved: {results_file}")
        
        # Save match results CSV for analysis
        if not match_results.empty:
            match_results_file = f"data/phase3c2_match_results_{time.strftime('%Y%m%d_%H%M%S')}.csv"
            match_results.to_csv(match_results_file, index=False)
            print(f"💾 Match results saved: {match_results_file}")
        
        # Phase 3C.2 summary and next steps
        print(f"\n🚀 Phase 3C.2 Summary:")
        improvement = performance_stats['improvement_over_baseline']
        if improvement > 0:
            print(f"   ✅ SUCCESS: {improvement:+.2f} percentage point improvement")
            print(f"   📈 New match rate: {performance_stats['match_rate']:.2f}%")
            print(f"   🎯 Target for Phase 3C.3: Further optimize high-value areas")
        else:
            print(f"   📊 ANALYSIS: {improvement:+.2f} percentage point change")
            print(f"   🔍 Insight: Custom tolerance approach requires refinement")
            print(f"   🎯 Next: Analyze tolerance effectiveness by district")
        
        print(f"\n🏗️ Phase 3C.3 Recommendations:")
        print(f"   1. Analyze per-district improvements from custom tolerance")
        print(f"   2. Fine-tune tolerance values based on Phase 3C.2 results")
        print(f"   3. Implement machine learning for dynamic tolerance optimization")
        print(f"   4. Progressive validation with improved tolerance settings")
        
        processing_time = time.time() - start_time
        print(f"\n✅ Phase 3C.2 Custom Tolerance Implementation completed in {processing_time:.1f} seconds")
        
        return results
        
    except Exception as e:
        print(f"❌ Error in Phase 3C.2 implementation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """Main execution function"""
    test_custom_tolerance_optimization()

if __name__ == "__main__":
    main()
