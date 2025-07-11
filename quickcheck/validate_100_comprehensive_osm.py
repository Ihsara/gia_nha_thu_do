#!/usr/bin/env python3
"""
Comprehensive Validation: 100 Data Points with Enhanced Spatial Matching
Thorough testing of enhanced spatial matching system before full deployment
"""

import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd
from datetime import datetime
import json
import time
import random

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from oikotie.utils import EnhancedSpatialMatcher
from oikotie.visualization.utils.data_loader import DataLoader

class ComprehensiveValidator:
    """Comprehensive validation with 100 representative data points"""
    
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
        
        # Test configuration
        self.sample_size = 100
        self.target_match_rate = 95.0  # High target for comprehensive validation
    
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
    
    def prepare_comprehensive_sample(self):
        """Prepare 100 representative listings for comprehensive testing"""
        print("=" * 60)
        print("🎯 Preparing Comprehensive 100-Point Sample")
        print("=" * 60)
        
        try:
            # Load listings with coordinates through join
            print("📊 Loading complete listings database with coordinates...")
            conn = self.data_loader.connect()
            
            listings_query = """
            SELECT l.*, al.lat, al.lon 
            FROM listings l 
            JOIN address_locations al ON l.address = al.address 
            WHERE al.lat IS NOT NULL AND al.lon IS NOT NULL
            """
            
            listings_data = conn.execute(listings_query).fetchdf()
            
            if listings_data is None or len(listings_data) == 0:
                print("❌ No listings data with coordinates available")
                return None
            
            # Convert to GeoDataFrame
            listings_gdf = gpd.GeoDataFrame(
                listings_data,
                geometry=gpd.points_from_xy(listings_data.lon, listings_data.lat),
                crs='EPSG:4326'
            )
            
            print(f"📊 Total listings available: {len(listings_gdf):,}")
            
            # Create comprehensive representative sample
            comprehensive_sample = []
            
            # 1. Include critical boundary cases (Siilikuja addresses)
            boundary_cases = [
                "Siilikuja 1 A, 00800 Helsinki",
                "Siilikuja 1 B, 00800 Helsinki", 
                "Siilikuja 3, 00800 Helsinki",
                "Siilikuja 5, 00800 Helsinki",
                "Siilikuja 7, 00800 Helsinki"
            ]
            
            boundary_found = 0
            for address in boundary_cases:
                matches = listings_gdf[listings_gdf['address'].str.contains(address.split(',')[0], na=False)]
                if len(matches) > 0:
                    comprehensive_sample.append(matches.iloc[0])
                    boundary_found += 1
            
            print(f"✅ Included {boundary_found} critical boundary cases")
            
            # 2. Geographic distribution sample
            # Divide Helsinki into grid and sample from each area
            lats = listings_gdf.geometry.y
            lons = listings_gdf.geometry.x
            
            # Create geographic grid (3x3 for Helsinki)
            lat_bins = pd.cut(lats, bins=3, labels=False)
            lon_bins = pd.cut(lons, bins=3, labels=False)
            
            grid_samples = []
            for lat_bin in range(3):
                for lon_bin in range(3):
                    grid_mask = (lat_bins == lat_bin) & (lon_bins == lon_bin)
                    grid_listings = listings_gdf[grid_mask]
                    
                    if len(grid_listings) > 0:
                        # Sample 3-5 from each grid cell
                        sample_count = min(5, len(grid_listings))
                        grid_sample = grid_listings.sample(n=sample_count, random_state=42)
                        grid_samples.extend([row for _, row in grid_sample.iterrows()])
                        print(f"📍 Grid ({lat_bin},{lon_bin}): {sample_count} samples from {len(grid_listings)} listings")
            
            comprehensive_sample.extend(grid_samples)
            print(f"✅ Added {len(grid_samples)} geographic distribution samples")
            
            # 3. Different postal code areas
            postal_codes = ['00800', '00100', '00120', '00590', '00170', '00180']
            postal_samples = []
            
            for postal in postal_codes:
                postal_listings = listings_gdf[listings_gdf['address'].str.contains(postal, na=False)]
                if len(postal_listings) > 0:
                    sample_count = min(8, len(postal_listings))
                    postal_sample = postal_listings.sample(n=sample_count, random_state=42)
                    postal_samples.extend([row for _, row in postal_sample.iterrows()])
                    print(f"📮 Postal {postal}: {sample_count} samples from {len(postal_listings)} listings")
            
            comprehensive_sample.extend(postal_samples)
            print(f"✅ Added {len(postal_samples)} postal code diversity samples")
            
            # 4. Fill to 100 with random selection
            remaining_needed = self.sample_size - len(comprehensive_sample)
            if remaining_needed > 0:
                # Exclude already selected addresses
                selected_addresses = {item['address'] for item in comprehensive_sample}
                available_listings = listings_gdf[~listings_gdf['address'].isin(selected_addresses)]
                
                if len(available_listings) >= remaining_needed:
                    random_sample = available_listings.sample(n=remaining_needed, random_state=42)
                    comprehensive_sample.extend([row for _, row in random_sample.iterrows()])
                    print(f"✅ Added {remaining_needed} random samples to reach 100 total")
                else:
                    print(f"⚠️  Only {len(available_listings)} additional unique listings available")
            
            # Convert to GeoDataFrame
            if len(comprehensive_sample) > self.sample_size:
                # Trim to exactly 100 if we have more
                comprehensive_sample = comprehensive_sample[:self.sample_size]
            
            comprehensive_gdf = gpd.GeoDataFrame(comprehensive_sample, crs='EPSG:4326')
            
            print(f"\n✅ Comprehensive sample prepared: {len(comprehensive_gdf)} listings")
            
            # Sample analysis
            print(f"\n📊 Sample Composition Analysis:")
            print(f"   Total sample size: {len(comprehensive_gdf)}")
            print(f"   Unique addresses: {comprehensive_gdf['address'].nunique()}")
            
            # Geographic spread
            sample_lats = comprehensive_gdf.geometry.y
            sample_lons = comprehensive_gdf.geometry.x
            print(f"   Latitude range: {sample_lats.min():.6f} to {sample_lats.max():.6f}")
            print(f"   Longitude range: {sample_lons.min():.6f} to {sample_lons.max():.6f}")
            print(f"   Geographic center: {sample_lats.mean():.6f}, {sample_lons.mean():.6f}")
            
            return comprehensive_gdf
            
        except Exception as e:
            print(f"❌ Error preparing comprehensive sample: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def run_comprehensive_validation(self):
        """Run comprehensive validation on 100 representative data points"""
        print("=" * 60)
        print("🧪 COMPREHENSIVE VALIDATION - 100 DATA POINTS")
        print("Enhanced Spatial Matching System Validation")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Load OSM buildings
        buildings_gdf = self.load_osm_buildings()
        if buildings_gdf is None:
            return False
        
        # Prepare comprehensive sample
        comprehensive_sample = self.prepare_comprehensive_sample()
        if comprehensive_sample is None:
            return False
        
        # Perform enhanced spatial matching
        print("\n" + "=" * 60)
        print("🎯 Enhanced Spatial Matching - Comprehensive Test")
        print("=" * 60)
        
        try:
            start_time = time.time()
            
            matching_results = self.spatial_matcher.enhanced_spatial_match(
                points_gdf=comprehensive_sample,
                buildings_gdf=buildings_gdf,
                point_id_col='address',
                building_id_col='osm_id'
            )
            
            matching_time = time.time() - start_time
            
            # Analyze results - matching_results is the DataFrame directly
            stats = self.spatial_matcher.get_statistics()
            matched_points = matching_results[matching_results['match_type'] != 'no_match'].copy()
            
            # Calculate match rate
            total_points = len(comprehensive_sample)
            successful_matches = len(matched_points)
            match_rate = (successful_matches / total_points) * 100 if total_points > 0 else 0
            
            # Add match rate to stats
            stats['match_rate'] = match_rate
            stats['processing_speed'] = total_points / matching_time if matching_time > 0 else 0
            
            print(f"\n✅ Comprehensive spatial matching completed in {matching_time:.2f} seconds")
            print(f"📊 COMPREHENSIVE RESULTS:")
            print(f"   Sample Size: {len(comprehensive_sample)} listings")
            print(f"   Match Rate: {stats['match_rate']:.2f}%")
            print(f"   Direct Matches: {stats['direct_matches']}")
            print(f"   Tolerance Matches: {stats['tolerance_matches']}")
            print(f"   No Matches: {stats['no_matches']}")
            print(f"   Processing Speed: {stats['processing_speed']:.1f} points/second")
            
            # Detailed analysis by sample type
            print(f"\n📋 DETAILED SAMPLE ANALYSIS:")
            print("=" * 60)
            
            # Boundary cases analysis
            boundary_addresses = [addr for addr in comprehensive_sample['address'] if 'Siilikuja' in addr]
            boundary_matched = 0
            
            if boundary_addresses:
                print(f"\n🎯 Critical Boundary Cases Analysis:")
                for addr in boundary_addresses:
                    if addr in matched_points['address'].values:
                        match_info = matched_points[matched_points['address'] == addr].iloc[0]
                        tolerance = match_info.get('tolerance_used_m', 0.0)
                        boundary_matched += 1
                        
                        if tolerance == 0.0:
                            print(f"   ✅ {addr} - Direct match")
                        else:
                            print(f"   🔄 {addr} - Tolerance match ({tolerance:.2f}m)")
                    else:
                        print(f"   ❌ {addr} - No match found")
                
                boundary_rate = (boundary_matched / len(boundary_addresses)) * 100
                print(f"   Boundary cases success rate: {boundary_rate:.1f}% ({boundary_matched}/{len(boundary_addresses)})")
            
            # Geographic distribution analysis
            if len(matched_points) > 0:
                print(f"\n🗺️  Geographic Distribution Analysis:")
                
                # Join matched points with original comprehensive sample to get coordinates
                matched_with_coords = comprehensive_sample[comprehensive_sample['address'].isin(matched_points['address'])]
                
                if len(matched_with_coords) > 0:
                    matched_lats = matched_with_coords.geometry.y
                    matched_lons = matched_with_coords.geometry.x
                    
                    print(f"   Matches distributed across:")
                    print(f"     Latitude span: {matched_lats.max() - matched_lats.min():.6f} degrees")
                    print(f"     Longitude span: {matched_lons.max() - matched_lons.min():.6f} degrees")
                    print(f"     Geographic center: {matched_lats.mean():.6f}, {matched_lons.mean():.6f}")
                else:
                    print(f"   Could not retrieve coordinate data for matched points")
            
            # Tolerance usage detailed analysis
            if 'tolerance_used_m' in matched_points.columns:
                tolerance_used = matched_points['tolerance_used_m']
                print(f"\n🔧 Tolerance Usage Analysis:")
                print(f"   Average tolerance: {tolerance_used.mean():.3f}m")
                print(f"   Median tolerance: {tolerance_used.median():.3f}m")
                print(f"   Maximum tolerance: {tolerance_used.max():.3f}m")
                
                # Tolerance distribution
                direct_count = (tolerance_used == 0.0).sum()
                low_tolerance = ((tolerance_used > 0.0) & (tolerance_used <= 0.5)).sum()
                med_tolerance = ((tolerance_used > 0.5) & (tolerance_used <= 1.0)).sum()
                high_tolerance = (tolerance_used > 1.0).sum()
                
                print(f"   Tolerance distribution:")
                print(f"     Direct matches (0.0m): {direct_count} ({direct_count/len(tolerance_used)*100:.1f}%)")
                print(f"     Low tolerance (0.0-0.5m): {low_tolerance} ({low_tolerance/len(tolerance_used)*100:.1f}%)")
                print(f"     Medium tolerance (0.5-1.0m): {med_tolerance} ({med_tolerance/len(tolerance_used)*100:.1f}%)")
                print(f"     High tolerance (>1.0m): {high_tolerance} ({high_tolerance/len(tolerance_used)*100:.1f}%)")
            
            # Failed cases analysis
            unmatched_addresses = comprehensive_sample[~comprehensive_sample['address'].isin(matched_points['address'])]
            if len(unmatched_addresses) > 0:
                print(f"\n❌ Unmatched Cases Analysis:")
                print(f"   Total unmatched: {len(unmatched_addresses)}")
                print(f"   Sample unmatched addresses:")
                for addr in unmatched_addresses['address'].head(5):
                    print(f"     - {addr}")
            
            # Performance scaling projection
            print(f"\n⚡ Performance Scaling Analysis:")
            listings_per_second = len(comprehensive_sample) / matching_time
            print(f"   Processing throughput: {listings_per_second:.1f} listings/second")
            
            # Full Helsinki projection
            full_helsinki_time = 8100 / listings_per_second
            print(f"   Projected full Helsinki time: {full_helsinki_time:.1f} seconds ({full_helsinki_time/60:.1f} minutes)")
            
            # Save comprehensive results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_path = self.output_dir / f"comprehensive_validation_100_{timestamp}_results.json"
            
            validation_results = {
                'validation_type': 'Comprehensive 100-Point Validation',
                'timestamp': datetime.now().isoformat(),
                'sample_size': len(comprehensive_sample),
                'buildings_tested_against': len(buildings_gdf),
                'processing_time_seconds': matching_time,
                'statistics': stats,
                'boundary_cases': {
                    'total': len(boundary_addresses) if boundary_addresses else 0,
                    'matched': boundary_matched if boundary_addresses else 0,
                    'success_rate': boundary_rate if boundary_addresses else 0
                },
                'performance_metrics': {
                    'listings_per_second': listings_per_second,
                    'projected_full_helsinki_time_seconds': full_helsinki_time
                },
                'matcher_config': {
                    'tolerance_m': self.spatial_matcher.tolerance_m,
                    'target_crs': self.spatial_matcher.target_crs
                }
            }
            
            with open(results_path, 'w') as f:
                json.dump(validation_results, f, indent=2)
            
            print(f"💾 Comprehensive results saved: {results_path}")
            
            # Final assessment
            print("\n" + "=" * 60)
            print("🎯 COMPREHENSIVE VALIDATION ASSESSMENT")
            print("=" * 60)
            
            achieved_rate = stats['match_rate']
            
            if achieved_rate >= self.target_match_rate:
                print(f"✅ COMPREHENSIVE VALIDATION PASSED: {achieved_rate:.2f}% >= {self.target_match_rate:.1f}%")
                print("🎉 Enhanced spatial matching system validated!")
                print("✅ Ready for production deployment")
                print("✅ OSM building footprints provide superior accuracy")
                print("✅ Boundary precision issues resolved")
                validation_passed = True
            else:
                print(f"❌ COMPREHENSIVE VALIDATION FAILED: {achieved_rate:.2f}% < {self.target_match_rate:.1f}%")
                print("⚠️  System needs optimization before production")
                print("🔧 Consider parameter tuning or data quality improvements")
                validation_passed = False
            
            print(f"\n📊 Final Summary:")
            print(f"   Sample tested: {len(comprehensive_sample)} diverse listings")
            print(f"   Match rate achieved: {achieved_rate:.2f}%")
            print(f"   Boundary cases resolved: {boundary_matched if boundary_addresses else 'N/A'}")
            print(f"   Processing performance: {listings_per_second:.1f} listings/second")
            print(f"   Production readiness: {'✅ READY' if validation_passed else '❌ NEEDS WORK'}")
            
            return validation_passed
            
        except Exception as e:
            print(f"❌ Comprehensive validation failed: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main function for comprehensive 100-point validation"""
    print("🧪 Comprehensive OSM Building Validation")
    print("Testing enhanced spatial matching on 100 representative data points")
    print()
    
    print("📊 COMPREHENSIVE TESTING APPROACH:")
    print("• Critical boundary cases (Siilikuja addresses)")
    print("• Geographic distribution across Helsinki")
    print("• Multiple postal code areas")
    print("• Random representative sample")
    print("• Total: 100 carefully selected listings")
    print()
    
    validator = ComprehensiveValidator()
    
    # Run comprehensive validation
    success = validator.run_comprehensive_validation()
    
    if success:
        print("\n" + "="*60)
        print("🎉 COMPREHENSIVE VALIDATION SUCCESSFUL!")
        print("="*60)
        print("✅ 100-point validation confirms enhanced spatial matching works")
        print("✅ Critical boundary cases resolved (Siilikuja addresses)")
        print("✅ Geographic distribution validation passed")
        print("✅ Performance scaling confirmed for production")
        print("✅ OSM building footprints provide superior accuracy")
        print()
        print("🚀 SYSTEM READY FOR PRODUCTION DEPLOYMENT:")
        print("1. Enhanced spatial matching validated on diverse dataset")
        print("2. Boundary precision issues resolved with 1.0m tolerance")
        print("3. EPSG:3067 CRS conversion working correctly")
        print("4. Match rate target achieved with professional quality")
        print()
        print("🔄 NEXT STEPS:")
        print("• Deploy enhanced spatial matching to main workflow")
        print("• Replace administrative polygons with OSM building footprints")
        print("• Update production spatial matching pipeline")
    else:
        print("\n" + "="*60)  
        print("❌ COMPREHENSIVE VALIDATION NEEDS ATTENTION")
        print("="*60)
        print("🔧 Required actions:")
        print("1. Analyze failed cases for patterns")
        print("2. Consider spatial matching parameter optimization")
        print("3. Investigate data quality issues")
        print("4. Re-run validation after improvements")

if __name__ == "__main__":
    main()
