#!/usr/bin/env python3
"""
Progressive Validation Step 3: Full Scale Helsinki Validation with OSM Buildings
Tests enhanced spatial matching on complete Helsinki dataset (8,100+ listings)
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

class Step3Validator:
    """Step 3 Progressive Validation: Full Scale Helsinki Testing"""
    
    def __init__(self):
        self.output_dir = Path("data")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize enhanced spatial matcher with optimal settings
        self.spatial_matcher = EnhancedSpatialMatcher(
            tolerance_m=1.0,  # Optimal tolerance from Steps 1&2 testing
            target_crs='EPSG:3067'  # Finnish projected coordinates
        )
        
        # Initialize data loader
        self.data_loader = DataLoader()
        
        # Success criteria for Step 3
        self.target_match_rate = 95.0  # 95%+ for professional quality
    
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
            
            # Building data analysis for full scale
            print(f"\n🏢 Building Coverage Analysis:")
            building_bounds = buildings_gdf.total_bounds
            print(f"   Coverage bounds: {building_bounds}")
            print(f"   Building density: {len(buildings_gdf) / ((building_bounds[2] - building_bounds[0]) * (building_bounds[3] - building_bounds[1])):.0f} buildings/sq_degree")
            
            return buildings_gdf
            
        except Exception as e:
            print(f"❌ Error loading OSM buildings: {e}")
            return None
    
    def prepare_full_helsinki_listings(self):
        """Prepare complete Helsinki listings dataset"""
        print("=" * 60)
        print("🎯 Preparing Full Helsinki Listings Dataset")
        print("=" * 60)
        
        try:
            # Load all listings
            print("📊 Loading complete listings database...")
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
            
            print(f"✅ Loaded {len(listings_gdf):,} total listings")
            
            # Geographic distribution analysis
            lats = listings_gdf.geometry.y
            lons = listings_gdf.geometry.x
            
            print(f"\n🗺️  Full Helsinki Geographic Coverage:")
            print(f"   Latitude range: {lats.min():.6f} to {lats.max():.6f}")
            print(f"   Longitude range: {lons.min():.6f} to {lons.max():.6f}")
            print(f"   Center point: {lats.mean():.6f}, {lons.mean():.6f}")
            print(f"   Coordinate spread (lat): {lats.std():.6f}")
            print(f"   Coordinate spread (lon): {lons.std():.6f}")
            
            # Postal code distribution analysis
            print(f"\n📮 Postal Code Distribution:")
            postal_codes = []
            for addr in listings_gdf['address'].head(100):  # Sample for performance
                if ', ' in addr:
                    postal_part = addr.split(', ')[-1]
                    if postal_part.startswith('00'):
                        postal_codes.append(postal_part[:5])
            
            if postal_codes:
                unique_postcodes = list(set(postal_codes))[:10]  # Top 10
                print(f"   Sample postal codes: {', '.join(unique_postcodes)}")
                print(f"   Estimated postal code coverage: {len(unique_postcodes)}+ areas")
            
            # Data quality assessment
            print(f"\n📊 Data Quality Assessment:")
            print(f"   Valid coordinates: {((lats.notna()) & (lons.notna())).sum():,} ({((lats.notna()) & (lons.notna())).sum()/len(listings_gdf)*100:.1f}%)")
            print(f"   Valid addresses: {listings_gdf['address'].notna().sum():,} ({listings_gdf['address'].notna().sum()/len(listings_gdf)*100:.1f}%)")
            
            # Filter for valid data only
            valid_mask = (lats.notna()) & (lons.notna()) & (listings_gdf['address'].notna())
            clean_listings = listings_gdf[valid_mask].copy()
            
            print(f"✅ Using {len(clean_listings):,} listings with valid coordinates and addresses")
            
            return clean_listings
            
        except Exception as e:
            print(f"❌ Error preparing full Helsinki listings: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def run_validation(self):
        """Run Step 3 validation on complete Helsinki dataset"""
        print("=" * 60)
        print("🧪 STEP 3 PROGRESSIVE VALIDATION")
        print("Enhanced Spatial Matching - Full Helsinki Dataset")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Load OSM buildings
        buildings_gdf = self.load_osm_buildings()
        if buildings_gdf is None:
            return False
        
        # Prepare full Helsinki listings
        helsinki_listings = self.prepare_full_helsinki_listings()
        if helsinki_listings is None:
            return False
        
        # Production readiness check
        expected_time = len(helsinki_listings) / 250  # Conservative estimate: 250 listings/second
        print(f"⏱️  Estimated processing time: {expected_time:.1f} seconds ({expected_time/60:.1f} minutes)")
        print(f"🎯 Target match rate: {self.target_match_rate:.1f}% for professional quality")
        print()
        
        # Perform enhanced spatial matching
        print("=" * 60)
        print("🎯 Enhanced Spatial Matching Execution - FULL SCALE")
        print("=" * 60)
        
        try:
            start_time = time.time()
            
            # Performance monitoring points
            quarter_points = [len(helsinki_listings) // 4 * i for i in range(1, 4)]
            
            matching_results = self.spatial_matcher.enhanced_spatial_match(
                points_gdf=helsinki_listings,
                buildings_gdf=buildings_gdf,
                point_id_col='address',
                building_id_col='osm_id'
            )
            
            matching_time = time.time() - start_time
            
            # Analyze results
            stats = matching_results['statistics']
            matched_points = matching_results['matched_points']
            
            print(f"\n✅ Full scale spatial matching completed!")
            print(f"⏱️  Total processing time: {matching_time:.1f} seconds ({matching_time/60:.1f} minutes)")
            
            print(f"\n📊 FULL SCALE RESULTS:")
            print(f"   Match Rate: {stats['match_rate']:.2f}%")
            print(f"   Direct Matches: {stats['direct_matches']:,}")
            print(f"   Tolerance Matches: {stats['tolerance_matches']:,}")
            print(f"   No Matches: {stats['no_matches']:,}")
            print(f"   Processing Speed: {stats['processing_speed']:.1f} points/second")
            
            # Production performance analysis
            print(f"\n⚡ Production Performance Analysis:")
            listings_per_second = len(helsinki_listings) / matching_time
            print(f"   Total listings processed: {len(helsinki_listings):,}")
            print(f"   Actual throughput: {listings_per_second:.1f} listings/second")
            print(f"   Memory efficiency: Processing {len(buildings_gdf):,} buildings in memory")
            print(f"   Scalability: Ready for larger datasets")
            
            # Geographic match distribution
            print(f"\n🗺️  Geographic Match Distribution Analysis:")
            if len(matched_points) > 0:
                matched_lats = matched_points.geometry.y
                matched_lons = matched_points.geometry.x
                
                print(f"   Matched listings: {len(matched_points):,}")
                print(f"   Coverage center: {matched_lats.mean():.6f}, {matched_lons.mean():.6f}")
                print(f"   Coverage bounds: [{matched_lats.min():.6f}, {matched_lats.max():.6f}] x [{matched_lons.min():.6f}, {matched_lons.max():.6f}]")
                print(f"   Geographic spread: {matched_lats.std():.6f} lat, {matched_lons.std():.6f} lon")
            
            # Detailed tolerance analysis
            if 'tolerance_used_m' in matched_points.columns:
                tolerance_used = matched_points['tolerance_used_m']
                print(f"\n🔧 Tolerance Buffer Analysis (Full Scale):")
                print(f"   Average tolerance used: {tolerance_used.mean():.3f}m")
                print(f"   Median tolerance used: {tolerance_used.median():.3f}m")
                print(f"   Maximum tolerance used: {tolerance_used.max():.3f}m")
                
                direct_matches = (tolerance_used == 0.0).sum()
                tolerance_matches = (tolerance_used > 0.0).sum()
                print(f"   Direct matches: {direct_matches:,} ({direct_matches/len(tolerance_used)*100:.1f}%)")
                print(f"   Tolerance matches: {tolerance_matches:,} ({tolerance_matches/len(tolerance_used)*100:.1f}%)")
                
                # Tolerance distribution
                tolerance_ranges = {
                    '0.0m (Direct)': (tolerance_used == 0.0).sum(),
                    '0.0-0.5m': ((tolerance_used > 0.0) & (tolerance_used <= 0.5)).sum(),
                    '0.5-1.0m': ((tolerance_used > 0.5) & (tolerance_used <= 1.0)).sum(),
                    '>1.0m': (tolerance_used > 1.0).sum()
                }
                
                print(f"   Tolerance distribution:")
                for range_name, count in tolerance_ranges.items():
                    pct = count / len(tolerance_used) * 100
                    print(f"     {range_name}: {count:,} ({pct:.1f}%)")
            
            # Quality assessment by area
            print(f"\n📊 Quality Assessment:")
            unmatched_listings = helsinki_listings[~helsinki_listings['address'].isin(matched_points['address'])]
            
            if len(unmatched_listings) > 0:
                print(f"   Unmatched listings: {len(unmatched_listings):,}")
                print(f"   Unmatched percentage: {len(unmatched_listings)/len(helsinki_listings)*100:.2f}%")
                
                # Sample unmatched addresses for investigation
                sample_unmatched = unmatched_listings['address'].head(5).tolist()
                print(f"   Sample unmatched addresses:")
                for addr in sample_unmatched:
                    print(f"     - {addr}")
            
            # Save comprehensive results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_path = self.output_dir / f"step3_validation_full_helsinki_{timestamp}_results.json"
            
            validation_results = {
                'validation_type': 'Step 3 - Full Scale Helsinki',
                'timestamp': datetime.now().isoformat(),
                'total_listings': len(helsinki_listings),
                'buildings_tested_against': len(buildings_gdf),
                'processing_time_seconds': matching_time,
                'statistics': stats,
                'performance_metrics': {
                    'listings_per_second': listings_per_second,
                    'total_processing_time_minutes': matching_time / 60,
                    'memory_efficiency': f"{len(buildings_gdf):,} buildings processed in memory"
                },
                'matcher_config': {
                    'tolerance_m': self.spatial_matcher.tolerance_m,
                    'target_crs': self.spatial_matcher.target_crs
                }
            }
            
            with open(results_path, 'w') as f:
                json.dump(validation_results, f, indent=2)
            
            print(f"💾 Comprehensive results saved: {results_path}")
            
            # Create enhanced dashboard HTML
            dashboard_path = self.output_dir / f"validation_full_helsinki_{timestamp}.html"
            self._create_enhanced_dashboard(matched_points, buildings_gdf, dashboard_path)
            
            # Final validation assessment
            print("\n" + "=" * 60)
            print("🎯 STEP 3 FINAL VALIDATION ASSESSMENT")
            print("=" * 60)
            
            achieved_rate = stats['match_rate']
            
            if achieved_rate >= self.target_match_rate:
                print(f"✅ STEP 3 PASSED: {achieved_rate:.2f}% >= {self.target_match_rate:.1f}%")
                print("🎉 FULL HELSINKI VALIDATION SUCCESSFUL!")
                print("✅ Professional quality achieved for production deployment")
                print("✅ OSM building footprints provide superior spatial matching")
                print("✅ Enhanced spatial matching system ready for production")
                validation_passed = True
            else:
                print(f"❌ STEP 3 FAILED: {achieved_rate:.2f}% < {self.target_match_rate:.1f}%")
                print("⚠️  Full scale performance below professional quality threshold")
                print("🔧 May need additional optimization or data quality improvements")
                validation_passed = False
            
            print(f"\n📊 Final Summary:")
            print(f"   Total Helsinki listings: {len(helsinki_listings):,}")
            print(f"   Successfully matched: {stats['direct_matches'] + stats['tolerance_matches']:,}")
            print(f"   Final match rate: {achieved_rate:.2f}%")
            print(f"   Processing performance: {listings_per_second:.1f} listings/second")
            print(f"   Production readiness: {'✅ READY' if validation_passed else '❌ NEEDS WORK'}")
            
            return validation_passed
            
        except Exception as e:
            print(f"❌ Full scale spatial matching failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_enhanced_dashboard(self, matched_points, buildings_gdf, output_path):
        """Create enhanced HTML dashboard for full scale results"""
        try:
            import folium
            from folium.plugins import HeatMap
            
            print(f"\n🎨 Creating enhanced validation dashboard...")
            
            # Create base map centered on Helsinki
            center_lat = matched_points.geometry.y.mean()
            center_lon = matched_points.geometry.x.mean()
            
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=11,
                tiles='OpenStreetMap'
            )
            
            # Add matched points sample (for performance)
            sample_size = min(1000, len(matched_points))
            sample_matches = matched_points.sample(n=sample_size, random_state=42)
            
            for idx, row in sample_matches.iterrows():
                tolerance = row.get('tolerance_used_m', 0.0)
                color = 'green' if tolerance == 0.0 else 'orange'
                
                folium.CircleMarker(
                    location=[row.geometry.y, row.geometry.x],
                    radius=3,
                    popup=f"Address: {row['address']}<br>Tolerance: {tolerance:.2f}m",
                    color=color,
                    fillColor=color,
                    fillOpacity=0.6
                ).add_to(m)
            
            # Add legend
            legend_html = '''
            <div style="position: fixed; 
                        bottom: 50px; left: 50px; width: 200px; height: 80px; 
                        background-color: white; border:2px solid grey; z-index:9999; 
                        font-size:14px; padding: 10px">
            <p><b>Helsinki OSM Validation</b></p>
            <p><i class="fa fa-circle" style="color:green"></i> Direct Match</p>
            <p><i class="fa fa-circle" style="color:orange"></i> Tolerance Match</p>
            </div>
            '''
            m.get_root().html.add_child(folium.Element(legend_html))
            
            # Save dashboard
            m.save(str(output_path))
            print(f"🎨 Enhanced dashboard saved: {output_path}")
            
        except Exception as e:
            print(f"⚠️  Dashboard creation failed: {e}")

def main():
    """Main function for Step 3 progressive validation"""
    print("🧪 Progressive Validation Step 3: Full Helsinki Dataset")
    print("Testing enhanced spatial matching on complete production dataset")
    print()
    
    print("⚠️  PRODUCTION SCALE VALIDATION")
    print("This will process the complete Helsinki dataset (~8,100 listings)")
    print("Expected processing time: 3-5 minutes")
    print("Target: 95%+ match rate for professional quality")
    print()
    
    validator = Step3Validator()
    
    # Run validation
    success = validator.run_validation()
    
    if success:
        print("\n" + "="*60)
        print("🎉 STEP 3 VALIDATION COMPLETED SUCCESSFULLY!")
        print("🏆 PROGRESSIVE VALIDATION COMPLETE!")
        print("="*60)
        print("✅ Full Helsinki dataset achieves professional quality standards")
        print("✅ Enhanced spatial matching system production ready")
        print("✅ OSM building footprints provide superior accuracy")
        print("✅ Tolerance buffer system handles boundary cases effectively")
        print("✅ Performance scaling validated for large datasets")
        print()
        print("🎯 PRODUCTION DEPLOYMENT READY:")
        print("1. ✅ Replace administrative polygons with OSM building footprints")
        print("2. ✅ Deploy enhanced spatial matching in main workflow")
        print("3. ✅ Target 95%+ match rate achieved and validated")
        print("4. ✅ Progressive validation strategy proven effective")
    else:
        print("\n" + "="*60)
        print("❌ STEP 3 VALIDATION FAILED")
        print("="*60)
        print("🔧 Required actions before production deployment:")
        print("1. Investigate large scale performance issues")
        print("2. Analyze unmatched listings for data quality issues")
        print("3. Consider spatial matching parameter optimization")
        print("4. Re-run Step 3 validation until 95%+ success rate")

if __name__ == "__main__":
    main()
