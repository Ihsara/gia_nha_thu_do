#!/usr/bin/env python3
"""
Progressive Validation Step 1: 10 Critical Boundary Cases with OSM Buildings
Tests enhanced spatial matching on 10 carefully selected boundary cases including Siilikuja addresses
"""

import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd
from datetime import datetime
import json
import time

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from oikotie.utils import EnhancedSpatialMatcher
from oikotie.visualization.utils.data_loader import DataLoader

class Step1Validator:
    """Step 1 Progressive Validation: 10 Critical Boundary Cases"""
    
    def __init__(self):
        self.output_dir = Path("data")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize enhanced spatial matcher with optimal settings
        self.spatial_matcher = EnhancedSpatialMatcher(
            tolerance_m=1.0,  # Optimal tolerance from testing
            target_crs='EPSG:3067'  # Finnish projected coordinates
        )
        
        # Initialize data loader
        self.data_loader = DataLoader()
        
        # Define critical boundary case addresses
        self.critical_addresses = [
            "Siilikuja 1 A, 00800 Helsinki",
            "Siilikuja 1 B, 00800 Helsinki", 
            "Siilikuja 3, 00800 Helsinki",
            "Siilikuja 5, 00800 Helsinki",
            "Siilikuja 7, 00800 Helsinki",
            "Uudenmaankatu 16-20, 00120 Helsinki",
            "Mannerheimintie 12, 00100 Helsinki",
            "Aleksanterinkatu 52, 00100 Helsinki",
            "Pohjoisesplanadi 37, 00100 Helsinki",
            "Kampinkatu 1, 00100 Helsinki"
        ]
    
    def load_osm_buildings(self):
        """Load the latest OSM building data"""
        print("=" * 60)
        print("📊 Loading OSM Building Data")
        print("=" * 60)
        
        try:
            # Look for latest OSM building file
            geojson_files = list(self.output_dir.glob("helsinki_buildings_*.geojson"))
            
            if not geojson_files:
                print("❌ No OSM building data found. Please run OSM building download first.")
                print("   Run: uv run python quickcheck/osm_building_pipeline.py")
                return None
            
            # Use the most recent file
            latest_file = max(geojson_files, key=lambda x: x.stat().st_mtime)
            print(f"📂 Loading: {latest_file.name}")
            
            buildings_gdf = gpd.read_file(latest_file)
            print(f"✅ Loaded {len(buildings_gdf):,} OSM buildings")
            print(f"📍 CRS: {buildings_gdf.crs}")
            
            return buildings_gdf
            
        except Exception as e:
            print(f"❌ Error loading OSM buildings: {e}")
            return None
    
    def prepare_critical_listings(self):
        """Prepare critical boundary case listings for testing"""
        print("=" * 60)
        print("🎯 Preparing Critical Boundary Cases")
        print("=" * 60)
        
        try:
            # Load all listings
            print("📊 Loading listings database...")
            listings_data = self.data_loader.load_listings_data()
            
            if listings_data is None or len(listings_data) == 0:
                print("❌ No listings data available")
                return None
            
            # Convert to GeoDataFrame
            listings_gdf = gpd.GeoDataFrame(
                listings_data,
                geometry=gpd.points_from_xy(listings_data.longitude, listings_data.latitude),
                crs='EPSG:4326'
            )
            
            print(f"📊 Total listings available: {len(listings_gdf):,}")
            
            # Filter for critical addresses
            critical_listings = []
            found_addresses = []
            
            for address in self.critical_addresses:
                # Try exact match first
                exact_matches = listings_gdf[listings_gdf['address'] == address]
                
                if len(exact_matches) > 0:
                    critical_listings.append(exact_matches.iloc[0])
                    found_addresses.append(address)
                else:
                    # Try partial match for complex addresses
                    address_parts = address.split(',')[0].strip()  # Get just the street part
                    partial_matches = listings_gdf[listings_gdf['address'].str.contains(address_parts, na=False)]
                    
                    if len(partial_matches) > 0:
                        # Take the first match
                        critical_listings.append(partial_matches.iloc[0])
                        found_addresses.append(partial_matches.iloc[0]['address'])
                        print(f"📍 Partial match: {address} → {partial_matches.iloc[0]['address']}")
                    else:
                        print(f"⚠️  No match found for: {address}")
            
            if not critical_listings:
                print("❌ No critical addresses found in listings data")
                return None
            
            # Create GeoDataFrame from found listings
            critical_gdf = gpd.GeoDataFrame(critical_listings, crs='EPSG:4326')
            
            print(f"✅ Found {len(critical_gdf)} critical boundary cases:")
            for i, addr in enumerate(found_addresses):
                print(f"  {i+1:2d}. {addr}")
            
            return critical_gdf
            
        except Exception as e:
            print(f"❌ Error preparing critical listings: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def run_validation(self):
        """Run Step 1 validation on critical boundary cases"""
        print("=" * 60)
        print("🧪 STEP 1 PROGRESSIVE VALIDATION")
        print("Enhanced Spatial Matching - 10 Critical Boundary Cases")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Load OSM buildings
        buildings_gdf = self.load_osm_buildings()
        if buildings_gdf is None:
            return False
        
        # Prepare critical listings
        critical_listings = self.prepare_critical_listings()
        if critical_listings is None:
            return False
        
        # Perform enhanced spatial matching
        print("\n" + "=" * 60)
        print("🎯 Enhanced Spatial Matching Execution")
        print("=" * 60)
        
        try:
            start_time = time.time()
            
            matching_results = self.spatial_matcher.enhanced_spatial_match(
                points_gdf=critical_listings,
                buildings_gdf=buildings_gdf,
                point_id_col='address',
                building_id_col='osm_id'
            )
            
            matching_time = time.time() - start_time
            
            # Analyze results
            stats = matching_results['statistics']
            matched_points = matching_results['matched_points']
            
            print(f"\n✅ Spatial matching completed in {matching_time:.2f} seconds")
            print(f"📊 CRITICAL RESULTS:")
            print(f"   Match Rate: {stats['match_rate']:.1f}%")
            print(f"   Direct Matches: {stats['direct_matches']}")
            print(f"   Tolerance Matches: {stats['tolerance_matches']}")
            print(f"   No Matches: {stats['no_matches']}")
            print(f"   Processing Speed: {stats['processing_speed']:.1f} points/second")
            
            # Detailed analysis of each critical case
            print(f"\n📋 DETAILED BOUNDARY CASE ANALYSIS:")
            print("=" * 60)
            
            success_cases = []
            boundary_cases = []
            failed_cases = []
            
            for i, row in critical_listings.iterrows():
                address = row['address']
                matched_row = matched_points[matched_points['address'] == address]
                
                if len(matched_row) > 0:
                    match_info = matched_row.iloc[0]
                    tolerance_used = match_info.get('tolerance_used_m', 0.0)
                    
                    if tolerance_used == 0.0:
                        success_cases.append(address)
                        print(f"✅ {address}")
                        print(f"   Direct match (no tolerance needed)")
                    else:
                        boundary_cases.append(address)
                        print(f"🔄 {address}")
                        print(f"   Tolerance match ({tolerance_used:.2f}m buffer)")
                else:
                    failed_cases.append(address)
                    print(f"❌ {address}")
                    print(f"   No spatial match found")
                
                print()
            
            # Save detailed results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_path = self.output_dir / f"step1_validation_{timestamp}_results.json"
            
            validation_results = {
                'validation_type': 'Step 1 - Critical Boundary Cases',
                'timestamp': datetime.now().isoformat(),
                'total_cases': len(critical_listings),
                'buildings_tested_against': len(buildings_gdf),
                'processing_time_seconds': matching_time,
                'statistics': stats,
                'matcher_config': {
                    'tolerance_m': self.spatial_matcher.tolerance_m,
                    'target_crs': self.spatial_matcher.target_crs
                },
                'case_analysis': {
                    'success_cases': success_cases,
                    'boundary_cases': boundary_cases,
                    'failed_cases': failed_cases
                },
                'addresses_tested': found_addresses
            }
            
            with open(results_path, 'w') as f:
                json.dump(validation_results, f, indent=2)
            
            print(f"💾 Detailed results saved: {results_path}")
            
            # Final validation assessment
            print("\n" + "=" * 60)
            print("🎯 STEP 1 VALIDATION ASSESSMENT")
            print("=" * 60)
            
            target_match_rate = 100.0  # Step 1 target: 100% for boundary cases
            achieved_rate = stats['match_rate']
            
            if achieved_rate >= target_match_rate:
                print(f"✅ STEP 1 PASSED: {achieved_rate:.1f}% >= {target_match_rate:.1f}%")
                print("✅ All critical boundary cases resolved successfully")
                print("🎯 Ready to proceed to Step 2: Medium Scale Validation")
                validation_passed = True
            else:
                print(f"❌ STEP 1 FAILED: {achieved_rate:.1f}% < {target_match_rate:.1f}%")
                print("⚠️  Some critical boundary cases still unresolved")
                print("🔧 Enhanced spatial matching may need further optimization")
                validation_passed = False
            
            print(f"\n📊 Summary:")
            print(f"   Total boundary cases tested: {len(critical_listings)}")
            print(f"   Successfully resolved: {len(success_cases) + len(boundary_cases)}")
            print(f"   Direct matches: {len(success_cases)}")
            print(f"   Tolerance matches: {len(boundary_cases)}")
            print(f"   Still failed: {len(failed_cases)}")
            
            return validation_passed
            
        except Exception as e:
            print(f"❌ Spatial matching execution failed: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main function for Step 1 progressive validation"""
    print("🧪 Progressive Validation Step 1: OSM Buildings")
    print("Testing enhanced spatial matching on critical boundary cases")
    print()
    
    validator = Step1Validator()
    
    # Run validation
    success = validator.run_validation()
    
    if success:
        print("\n" + "="*60)
        print("🎉 STEP 1 VALIDATION COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("✅ Critical boundary cases resolved with enhanced spatial matching")
        print("✅ OSM building footprints working correctly")
        print("✅ EPSG:3067 CRS conversion functioning properly")
        print("✅ Tolerance buffer system effective for boundary precision")
        print()
        print("🔄 NEXT ACTIONS:")
        print("1. Proceed to Step 2: validate_postal_osm.py (medium scale)")
        print("2. Test representative postal code area")
        print("3. Validate scalability with larger dataset")
    else:
        print("\n" + "="*60)
        print("❌ STEP 1 VALIDATION FAILED")
        print("="*60)
        print("🔧 Required actions before proceeding:")
        print("1. Investigate failed boundary cases")
        print("2. Optimize enhanced spatial matching parameters")
        print("3. Consider alternative spatial matching strategies")
        print("4. Re-run Step 1 validation until 100% success rate")

if __name__ == "__main__":
    main()
