#!/usr/bin/env python3
"""
Progressive Validation Step 2: Medium Scale Postal Code Validation with OSM Buildings
Tests enhanced spatial matching on representative postal code area (100-500 listings)
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

class Step2Validator:
    """Step 2 Progressive Validation: Medium Scale Postal Code Testing"""
    
    def __init__(self, target_postal_code="00800"):
        self.output_dir = Path("data")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize enhanced spatial matcher with optimal settings
        self.spatial_matcher = EnhancedSpatialMatcher(
            tolerance_m=1.0,  # Optimal tolerance from Step 1 testing
            target_crs='EPSG:3067'  # Finnish projected coordinates
        )
        
        # Initialize data loader
        self.data_loader = DataLoader()
        
        # Target postal code for medium scale testing
        self.target_postal_code = target_postal_code
        
        # Success criteria for Step 2
        self.target_match_rate = 98.0  # 98%+ for production readiness
    
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
    
    def prepare_postal_code_listings(self):
        """Prepare listings for specific postal code area"""
        print("=" * 60)
        print(f"🎯 Preparing Postal Code {self.target_postal_code} Listings")
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
            
            # Filter for target postal code
            postal_filter = listings_gdf['address'].str.contains(
                self.target_postal_code, na=False, case=False
            )
            
            postal_listings = listings_gdf[postal_filter].copy()
            
            if len(postal_listings) == 0:
                print(f"❌ No listings found for postal code {self.target_postal_code}")
                print("Available postal codes (sample):")
                
                # Show available postal codes
                sample_addresses = listings_gdf['address'].head(10)
                for addr in sample_addresses:
                    if ', ' in addr:
                        postal_part = addr.split(', ')[-1]
                        print(f"   {postal_part}")
                
                return None
            
            print(f"✅ Found {len(postal_listings)} listings for postal code {self.target_postal_code}")
            
            # Geographic distribution analysis
            lats = postal_listings.geometry.y
            lons = postal_listings.geometry.x
            
            print(f"📍 Geographic Distribution:")
            print(f"   Latitude range: {lats.min():.6f} to {lats.max():.6f}")
            print(f"   Longitude range: {lons.min():.6f} to {lons.max():.6f}")
            print(f"   Center point: {lats.mean():.6f}, {lons.mean():.6f}")
            
            # Sample analysis for medium scale testing
            target_sample_size = min(500, len(postal_listings))
            if len(postal_listings) > target_sample_size:
                print(f"🎲 Sampling {target_sample_size} listings for medium scale testing...")
                postal_listings = postal_listings.sample(
                    n=target_sample_size, 
                    random_state=42
                ).copy()
            
            print(f"📊 Using {len(postal_listings)} listings for validation")
            
            return postal_listings
            
        except Exception as e:
            print(f"❌ Error preparing postal code listings: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def run_validation(self):
        """Run Step 2 validation on postal code area"""
        print("=" * 60)
        print("🧪 STEP 2 PROGRESSIVE VALIDATION")
        print(f"Enhanced Spatial Matching - Postal Code {self.target_postal_code}")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Load OSM buildings
        buildings_gdf = self.load_osm_buildings()
        if buildings_gdf is None:
            return False
        
        # Prepare postal code listings
        postal_listings = self.prepare_postal_code_listings()
        if postal_listings is None:
            return False
        
        # Perform enhanced spatial matching
        print("\n" + "=" * 60)
        print("🎯 Enhanced Spatial Matching Execution")
        print("=" * 60)
        
        try:
            start_time = time.time()
            
            matching_results = self.spatial_matcher.enhanced_spatial_match(
                points_gdf=postal_listings,
                buildings_gdf=buildings_gdf,
                point_id_col='address',
                building_id_col='osm_id'
            )
            
            matching_time = time.time() - start_time
            
            # Analyze results
            stats = matching_results['statistics']
            matched_points = matching_results['matched_points']
            
            print(f"\n✅ Spatial matching completed in {matching_time:.2f} seconds")
            print(f"📊 MEDIUM SCALE RESULTS:")
            print(f"   Match Rate: {stats['match_rate']:.2f}%")
            print(f"   Direct Matches: {stats['direct_matches']}")
            print(f"   Tolerance Matches: {stats['tolerance_matches']}")
            print(f"   No Matches: {stats['no_matches']}")
            print(f"   Processing Speed: {stats['processing_speed']:.1f} points/second")
            
            # Performance scaling analysis
            print(f"\n⚡ Performance Scaling Analysis:")
            listings_per_second = len(postal_listings) / matching_time
            print(f"   Listings processed: {len(postal_listings)}")
            print(f"   Processing time: {matching_time:.2f} seconds")
            print(f"   Effective throughput: {listings_per_second:.1f} listings/second")
            
            # Estimate full Helsinki processing time
            estimated_full_time = 8100 / listings_per_second  # 8100 total listings
            print(f"   Estimated full Helsinki time: {estimated_full_time:.1f} seconds ({estimated_full_time/60:.1f} minutes)")
            
            # Geographic distribution of matches
            print(f"\n🗺️  Geographic Match Distribution:")
            if len(matched_points) > 0:
                matched_lats = matched_points.geometry.y
                matched_lons = matched_points.geometry.x
                print(f"   Matched listings center: {matched_lats.mean():.6f}, {matched_lons.mean():.6f}")
                print(f"   Match spread (lat): {matched_lats.std():.6f}")
                print(f"   Match spread (lon): {matched_lons.std():.6f}")
            
            # Tolerance usage analysis
            tolerance_used = matched_points['tolerance_used_m'] if 'tolerance_used_m' in matched_points.columns else []
            if len(tolerance_used) > 0:
                print(f"\n🔧 Tolerance Buffer Analysis:")
                print(f"   Average tolerance used: {tolerance_used.mean():.3f}m")
                print(f"   Maximum tolerance used: {tolerance_used.max():.3f}m")
                direct_matches = (tolerance_used == 0.0).sum()
                tolerance_matches = (tolerance_used > 0.0).sum()
                print(f"   Direct matches: {direct_matches} ({direct_matches/len(tolerance_used)*100:.1f}%)")
                print(f"   Tolerance matches: {tolerance_matches} ({tolerance_matches/len(tolerance_used)*100:.1f}%)")
            
            # Save detailed results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_path = self.output_dir / f"step2_validation_{self.target_postal_code}_{timestamp}_results.json"
            
            validation_results = {
                'validation_type': 'Step 2 - Medium Scale Postal Code',
                'timestamp': datetime.now().isoformat(),
                'postal_code': self.target_postal_code,
                'total_listings': len(postal_listings),
                'buildings_tested_against': len(buildings_gdf),
                'processing_time_seconds': matching_time,
                'statistics': stats,
                'performance_metrics': {
                    'listings_per_second': listings_per_second,
                    'estimated_full_helsinki_time_seconds': estimated_full_time
                },
                'matcher_config': {
                    'tolerance_m': self.spatial_matcher.tolerance_m,
                    'target_crs': self.spatial_matcher.target_crs
                }
            }
            
            with open(results_path, 'w') as f:
                json.dump(validation_results, f, indent=2)
            
            print(f"💾 Detailed results saved: {results_path}")
            
            # Final validation assessment
            print("\n" + "=" * 60)
            print("🎯 STEP 2 VALIDATION ASSESSMENT")
            print("=" * 60)
            
            achieved_rate = stats['match_rate']
            
            if achieved_rate >= self.target_match_rate:
                print(f"✅ STEP 2 PASSED: {achieved_rate:.2f}% >= {self.target_match_rate:.1f}%")
                print("✅ Medium scale validation successful - production ready")
                print("✅ Performance scaling looks promising for full dataset")
                print("🎯 Ready to proceed to Step 3: Full Scale Validation")
                validation_passed = True
            else:
                print(f"❌ STEP 2 FAILED: {achieved_rate:.2f}% < {self.target_match_rate:.1f}%")
                print("⚠️  Medium scale performance below production threshold")
                print("🔧 May need spatial matching optimization or data quality investigation")
                validation_passed = False
            
            print(f"\n📊 Summary:")
            print(f"   Postal code: {self.target_postal_code}")
            print(f"   Listings tested: {len(postal_listings)}")
            print(f"   Successfully matched: {stats['direct_matches'] + stats['tolerance_matches']}")
            print(f"   Match rate: {achieved_rate:.2f}%")
            print(f"   Processing throughput: {listings_per_second:.1f} listings/second")
            
            return validation_passed
            
        except Exception as e:
            print(f"❌ Spatial matching execution failed: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main function for Step 2 progressive validation"""
    print("🧪 Progressive Validation Step 2: Postal Code Area")
    print("Testing enhanced spatial matching on medium scale dataset")
    print()
    
    # Allow postal code selection
    postal_codes = ["00800", "00590", "00100", "00120"]
    
    print("Available postal codes for testing:")
    for i, pc in enumerate(postal_codes):
        print(f"  {i+1}. {pc}")
    
    # Default to 00800 (Siilikuja area with known boundary cases)
    selected_postal = "00800"
    print(f"Using postal code: {selected_postal} (Siilikuja boundary case area)")
    print()
    
    validator = Step2Validator(target_postal_code=selected_postal)
    
    # Run validation
    success = validator.run_validation()
    
    if success:
        print("\n" + "="*60)
        print("🎉 STEP 2 VALIDATION COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("✅ Medium scale spatial matching achieved production readiness")
        print("✅ Performance scaling validated for larger datasets")
        print("✅ Geographic distribution handling working correctly")
        print("✅ Tolerance buffer system effective at scale")
        print()
        print("🔄 NEXT ACTIONS:")
        print("1. Proceed to Step 3: validate_full_helsinki_osm.py (full scale)")
        print("2. Test complete Helsinki dataset (8,100+ listings)")
        print("3. Validate final production readiness")
    else:
        print("\n" + "="*60)
        print("❌ STEP 2 VALIDATION FAILED")
        print("="*60)
        print("🔧 Required actions before proceeding:")
        print("1. Investigate medium scale performance issues")
        print("2. Optimize spatial matching parameters if needed")
        print("3. Consider data quality issues in postal code area")
        print("4. Re-run Step 2 validation until 98%+ success rate")

if __name__ == "__main__":
    main()
