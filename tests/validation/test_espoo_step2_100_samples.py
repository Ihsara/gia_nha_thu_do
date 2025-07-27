#!/usr/bin/env python3
"""
Progressive Validation Test: Step 2 - 100 Sample Espoo Listings

Tests 100 random Espoo listings with comprehensive geospatial integration.
This implements medium-scale validation with OSM building footprint matching.

Success Criteria: ≥98% match rate for medium scale validation
Next Step: test_espoo_step3_full_scale.py (full production validation)

Requirements: 5.1, 5.2, 5.3, 5.4
"""

import sys
import unittest
from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import duckdb
import random
from datetime import datetime
import json
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp

# Add the project root to path for package imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import from package structure
try:
    from oikotie.database.models import DatabaseManager
    from oikotie.utils import extract_postal_code
except ImportError as e:
    print(f"❌ Package import failed: {e}")
    print("💡 Ensure package structure is properly initialized")
    sys.exit(1)


class TestEspooStep2Validation(unittest.TestCase):
    """Test class for Espoo 100 sample listings validation with geospatial integration"""
    
    def setUp(self):
        """Set up test environment"""
        self.db_path = "data/real_estate.duckdb"
        self.osm_buildings_path = "data/helsinki_buildings_20250711_041142.geojson"
        self.output_dir = Path("output/validation/espoo/")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test parameters
        self.sample_size = 100
        self.required_match_rate = 98.0  # High standard for medium scale
        self.city = "Espoo"
        self.max_workers = min(4, mp.cpu_count())
        
        # Espoo coordinate bounds from config
        self.espoo_bounds = {
            'min_lat': 60.1,
            'max_lat': 60.4,
            'min_lon': 24.4,
            'max_lon': 24.9
        }
        
        print(f"\n🏙️ Testing Espoo Progressive Validation - Step 2")
        print(f"📊 Sample Size: {self.sample_size}")
        print(f"🎯 Success Criteria: ≥{self.required_match_rate}% match rate")
        print(f"🔧 Max Workers: {self.max_workers}")
        print(f"📍 Coordinate Bounds: {self.espoo_bounds}")
    
    def test_bug_prevention_prerequisites(self):
        """Bug prevention: Ensure Step 1 validation passed before running Step 2"""
        print("\n🔧 Bug Prevention: Prerequisites Check")
        
        # Check if Step 1 results exist
        step1_results = list(self.output_dir.glob("espoo_step1_*.json"))
        if step1_results:
            latest_step1 = max(step1_results, key=lambda x: x.stat().st_mtime)
            with open(latest_step1, 'r') as f:
                step1_metrics = json.load(f)
            
            step1_success = step1_metrics.get('success_criteria', {}).get('meets_criteria', False)
            step1_match_rate = step1_metrics.get('match_statistics', {}).get('match_rate_percent', 0)
            
            print(f"✅ Step 1 results found: {latest_step1.name}")
            print(f"   Match Rate: {step1_match_rate:.1f}%")
            print(f"   Success: {'✅ PASSED' if step1_success else '❌ FAILED'}")
            
            if not step1_success:
                print("⚠️ WARNING: Step 1 did not pass, but continuing with Step 2")
        else:
            print("⚠️ No Step 1 results found - recommend running Step 1 first")
        
        # Verify database and data availability
        conn = duckdb.connect(self.db_path)
        
        # Check Espoo listings count
        espoo_count = conn.execute(
            "SELECT COUNT(*) FROM listings WHERE city = 'Espoo'"
        ).fetchone()[0]
        self.assertGreater(espoo_count, self.sample_size, 
                          f"Need at least {self.sample_size} Espoo listings")
        
        # Check geocoded Espoo listings
        espoo_coords_count = conn.execute("""
            SELECT COUNT(*) 
            FROM listings l
            JOIN address_locations al ON l.address = al.address
            WHERE al.lat IS NOT NULL AND al.lon IS NOT NULL AND l.city = 'Espoo'
        """).fetchone()[0]
        self.assertGreater(espoo_coords_count, self.sample_size, 
                          f"Need at least {self.sample_size} geocoded Espoo listings")
        
        conn.close()
        print(f"✅ Prerequisites validated: {espoo_coords_count:,} geocoded Espoo listings available")
    
    def test_osm_buildings_loading_and_filtering(self):
        """Test loading and filtering OSM buildings for Espoo area"""
        print("\n🏗️ Loading and Filtering OSM Buildings for Espoo")
        
        try:
            # Load OSM buildings
            buildings_gdf = gpd.read_file(self.osm_buildings_path)
            print(f"✅ Loaded {len(buildings_gdf):,} total OSM buildings")
            
            # Ensure proper CRS
            if buildings_gdf.crs is None or buildings_gdf.crs.to_string() != 'EPSG:4326':
                buildings_gdf = buildings_gdf.to_crs('EPSG:4326')
                print("✅ Converted to EPSG:4326")
            
            # Filter buildings to Espoo area (with buffer for edge cases)
            buffer = 0.01  # ~1km buffer
            espoo_bounds_buffered = {
                'min_lat': self.espoo_bounds['min_lat'] - buffer,
                'max_lat': self.espoo_bounds['max_lat'] + buffer,
                'min_lon': self.espoo_bounds['min_lon'] - buffer,
                'max_lon': self.espoo_bounds['max_lon'] + buffer
            }
            
            # Filter using bounding box
            espoo_buildings = buildings_gdf[
                (buildings_gdf.geometry.bounds['miny'] >= espoo_bounds_buffered['min_lat']) &
                (buildings_gdf.geometry.bounds['maxy'] <= espoo_bounds_buffered['max_lat']) &
                (buildings_gdf.geometry.bounds['minx'] >= espoo_bounds_buffered['min_lon']) &
                (buildings_gdf.geometry.bounds['maxx'] <= espoo_bounds_buffered['max_lon'])
            ]
            
            print(f"✅ Filtered to {len(espoo_buildings):,} buildings in Espoo area")
            
            # Analyze building attributes
            buildings_with_names = espoo_buildings[
                espoo_buildings['name'].notna() & (espoo_buildings['name'] != '')
            ]
            print(f"📋 Buildings with names: {len(buildings_with_names):,}")
            
            if len(buildings_with_names) > 0:
                print("🏢 Sample building names:")
                for name in buildings_with_names['name'].head(5):
                    print(f"   → {name}")
            
            # Store for spatial matching
            self.espoo_buildings = espoo_buildings
            self.assertGreater(len(espoo_buildings), 0, "Should have buildings in Espoo area")
            
            return espoo_buildings
            
        except Exception as e:
            self.fail(f"Failed to load OSM buildings: {e}")
    
    def test_sample_listings_loading_medium_scale(self):
        """Test loading of 100 sample Espoo listings with enhanced validation"""
        print("\n📋 Loading 100 Sample Espoo Listings")
        
        try:
            conn = duckdb.connect(self.db_path)
            
            # Enhanced query with more details for medium scale testing
            query = f"""
            SELECT l.url as id, l.address, al.lat as latitude, al.lon as longitude,
                   l.price_eur as price, l.rooms, l.size_m2, l.listing_type, l.city,
                   l.title, l.postal_code, l.year_built, l.scraped_at,
                   al.geocoding_accuracy, al.geocoding_source
            FROM listings l
            JOIN address_locations al ON l.address = al.address
            WHERE al.lat IS NOT NULL AND al.lon IS NOT NULL AND l.city = 'Espoo'
            AND al.lat BETWEEN {self.espoo_bounds['min_lat']} AND {self.espoo_bounds['max_lat']}
            AND al.lon BETWEEN {self.espoo_bounds['min_lon']} AND {self.espoo_bounds['max_lon']}
            ORDER BY RANDOM()
            LIMIT {self.sample_size}
            """
            
            df = conn.execute(query).df()
            conn.close()
            
            self.assertEqual(len(df), self.sample_size, 
                           f"Should load exactly {self.sample_size} sample listings")
            
            # Enhanced validation
            self.assertTrue((df['city'] == 'Espoo').all(), "All listings should be from Espoo")
            
            # Coordinate validation
            lat_valid = df['latitude'].between(self.espoo_bounds['min_lat'], self.espoo_bounds['max_lat']).all()
            lon_valid = df['longitude'].between(self.espoo_bounds['min_lon'], self.espoo_bounds['max_lon']).all()
            
            self.assertTrue(lat_valid, "All latitudes should be within Espoo bounds")
            self.assertTrue(lon_valid, "All longitudes should be within Espoo bounds")
            
            # Data quality analysis
            price_available = df['price'].notna().sum()
            postal_available = df['postal_code'].notna().sum()
            rooms_available = df['rooms'].notna().sum()
            
            print(f"✅ Loaded {len(df)} Espoo sample listings")
            print(f"📊 Data Quality:")
            print(f"   💰 Price available: {price_available}/{len(df)} ({price_available/len(df)*100:.1f}%)")
            print(f"   📮 Postal code: {postal_available}/{len(df)} ({postal_available/len(df)*100:.1f}%)")
            print(f"   🏠 Rooms info: {rooms_available}/{len(df)} ({rooms_available/len(df)*100:.1f}%)")
            
            if price_available > 0:
                print(f"   💰 Price range: €{df['price'].min():,.0f} - €{df['price'].max():,.0f}")
            
            # Store for other tests
            self.sample_listings = df
            return df
            
        except Exception as e:
            self.fail(f"Failed to load sample listings: {e}")
    
    def test_enhanced_spatial_matching(self):
        """Test enhanced spatial matching with OSM building footprints"""
        print("\n🎯 Enhanced Spatial Matching with OSM Buildings")
        
        # Ensure prerequisites
        if not hasattr(self, 'sample_listings'):
            self.test_sample_listings_loading_medium_scale()
        if not hasattr(self, 'espoo_buildings'):
            self.test_osm_buildings_loading_and_filtering()
        
        df = self.sample_listings
        buildings_gdf = self.espoo_buildings
        
        print(f"Processing {len(df)} listings against {len(buildings_gdf):,} buildings...")
        
        # Use parallel processing for better performance
        results = []
        
        # Split listings into chunks for parallel processing
        chunk_size = max(1, len(df) // self.max_workers)
        chunks = [df[i:i + chunk_size] for i in range(0, len(df), chunk_size)]
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_chunk = {
                executor.submit(self._process_listings_chunk, chunk, buildings_gdf): chunk
                for chunk in chunks
            }
            
            for future in as_completed(future_to_chunk):
                chunk_results = future.result()
                results.extend(chunk_results)
        
        results_df = pd.DataFrame(results)
        
        # Calculate comprehensive statistics
        total_listings = len(results_df)
        matched_listings = len(results_df[results_df['matched']])
        match_rate = (matched_listings / total_listings) * 100 if total_listings > 0 else 0
        
        direct_matches = len(results_df[results_df['match_type'] == 'direct'])
        buffer_matches = len(results_df[results_df['match_type'] == 'buffer'])
        no_matches = total_listings - matched_listings
        
        print(f"\n📊 Enhanced Spatial Matching Results:")
        print(f"   📋 Total listings: {total_listings}")
        print(f"   ✅ Overall match rate: {match_rate:.2f}%")
        print(f"   🎯 Direct matches: {direct_matches} ({direct_matches/total_listings*100:.1f}%)")
        print(f"   🔍 Buffer matches: {buffer_matches} ({buffer_matches/total_listings*100:.1f}%)")
        print(f"   ❌ No matches: {no_matches} ({no_matches/total_listings*100:.1f}%)")
        
        if buffer_matches > 0:
            avg_buffer_distance = results_df[results_df['match_type'] == 'buffer']['distance_m'].mean()
            print(f"   📏 Avg buffer distance: {avg_buffer_distance:.1f}m")
        
        # Validate success criteria
        self.assertGreaterEqual(match_rate, self.required_match_rate, 
                               f"Match rate {match_rate:.2f}% should be ≥ {self.required_match_rate}%")
        
        print(f"✅ SUCCESS: Match rate {match_rate:.2f}% meets requirement ≥ {self.required_match_rate}%")
        
        # Store results
        self.validation_results = results_df
        self.match_rate = match_rate
        
        return results_df, match_rate
    
    def _process_listings_chunk(self, chunk_df, buildings_gdf):
        """Process a chunk of listings for spatial matching"""
        chunk_results = []
        
        for idx, listing in chunk_df.iterrows():
            # Create point geometry
            point = Point(listing['longitude'], listing['latitude'])
            
            # Step 1: Direct containment check
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                containing_buildings = buildings_gdf[buildings_gdf.contains(point)]
            
            if not containing_buildings.empty:
                # Direct match found
                building = containing_buildings.iloc[0]
                building_name = building.get('name', '')
                
                chunk_results.append({
                    'listing_id': listing['id'],
                    'address': listing['address'],
                    'latitude': listing['latitude'],
                    'longitude': listing['longitude'],
                    'price': listing['price'],
                    'match_type': 'direct',
                    'building_id': building.get('osm_id', 'N/A'),
                    'building_name': building_name,
                    'distance_m': 0.0,
                    'matched': True,
                    'quality_score': 1.0
                })
            else:
                # Step 2: Buffer search
                buffer_distance = 0.001  # ~100m
                buffered_point = point.buffer(buffer_distance)
                
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    intersecting_buildings = buildings_gdf[buildings_gdf.intersects(buffered_point)]
                
                if not intersecting_buildings.empty:
                    # Find closest building
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        distances = intersecting_buildings.geometry.distance(point)
                    
                    closest_idx = distances.idxmin()
                    closest_building = intersecting_buildings.loc[closest_idx]
                    closest_distance = distances.loc[closest_idx] * 111000  # Convert to meters
                    
                    building_name = closest_building.get('name', '')
                    
                    chunk_results.append({
                        'listing_id': listing['id'],
                        'address': listing['address'],
                        'latitude': listing['latitude'],
                        'longitude': listing['longitude'],
                        'price': listing['price'],
                        'match_type': 'buffer',
                        'building_id': closest_building.get('osm_id', 'N/A'),
                        'building_name': building_name,
                        'distance_m': closest_distance,
                        'matched': True,
                        'quality_score': max(0.1, 1.0 - (closest_distance / 100.0))  # Quality decreases with distance
                    })
                else:
                    # No match
                    chunk_results.append({
                        'listing_id': listing['id'],
                        'address': listing['address'],
                        'latitude': listing['latitude'],
                        'longitude': listing['longitude'],
                        'price': listing['price'],
                        'match_type': 'none',
                        'building_id': None,
                        'building_name': None,
                        'distance_m': float('inf'),
                        'matched': False,
                        'quality_score': 0.0
                    })
        
        return chunk_results
    
    def test_performance_benchmarking(self):
        """Test performance benchmarks for medium scale processing"""
        print("\n⚡ Performance Benchmarking")
        
        # Measure processing time
        start_time = time.time()
        
        # Run spatial matching if not already done
        if not hasattr(self, 'validation_results'):
            self.test_enhanced_spatial_matching()
        
        processing_time = time.time() - start_time
        
        # Calculate performance metrics
        listings_per_second = self.sample_size / processing_time if processing_time > 0 else 0
        
        performance_metrics = {
            'sample_size': self.sample_size,
            'processing_time_seconds': processing_time,
            'listings_per_second': listings_per_second,
            'max_workers': self.max_workers,
            'buildings_processed': len(self.espoo_buildings) if hasattr(self, 'espoo_buildings') else 0
        }
        
        print(f"📊 Performance Metrics:")
        print(f"   ⏱️ Processing time: {processing_time:.2f} seconds")
        print(f"   🚀 Listings per second: {listings_per_second:.2f}")
        print(f"   🔧 Workers used: {self.max_workers}")
        print(f"   🏗️ Buildings processed: {performance_metrics['buildings_processed']:,}")
        
        # Performance validation
        max_acceptable_time = 300  # 5 minutes for 100 listings
        self.assertLess(processing_time, max_acceptable_time, 
                       f"Processing should complete within {max_acceptable_time} seconds")
        
        min_acceptable_rate = 0.5  # At least 0.5 listings per second
        self.assertGreater(listings_per_second, min_acceptable_rate,
                          f"Should process at least {min_acceptable_rate} listings per second")
        
        print("✅ Performance benchmarks met")
        
        # Store performance metrics
        self.performance_metrics = performance_metrics
        return performance_metrics
    
    def test_comprehensive_quality_metrics(self):
        """Test comprehensive quality metrics tracking for medium scale"""
        print("\n📊 Comprehensive Quality Metrics")
        
        # Ensure we have validation results
        if not hasattr(self, 'validation_results'):
            self.test_enhanced_spatial_matching()
        if not hasattr(self, 'performance_metrics'):
            self.test_performance_benchmarking()
        
        results_df = self.validation_results
        
        # Calculate comprehensive quality metrics
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'validation_type': 'espoo_step2_100_samples',
            'city': self.city,
            'sample_size': len(results_df),
            'match_statistics': {
                'total_matched': len(results_df[results_df['matched']]),
                'match_rate_percent': self.match_rate,
                'direct_matches': len(results_df[results_df['match_type'] == 'direct']),
                'buffer_matches': len(results_df[results_df['match_type'] == 'buffer']),
                'no_matches': len(results_df[results_df['match_type'] == 'none']),
                'avg_quality_score': float(results_df['quality_score'].mean())
            },
            'spatial_analysis': {
                'avg_buffer_distance': float(results_df[results_df['match_type'] == 'buffer']['distance_m'].mean()) if len(results_df[results_df['match_type'] == 'buffer']) > 0 else 0,
                'max_buffer_distance': float(results_df[results_df['match_type'] == 'buffer']['distance_m'].max()) if len(results_df[results_df['match_type'] == 'buffer']) > 0 else 0,
                'buildings_with_names': len(results_df[results_df['building_name'].notna() & (results_df['building_name'] != '')]),
                'coordinate_spread_km': self._calculate_coordinate_spread(results_df)
            },
            'data_quality': {
                'addresses_with_postal': len(self.sample_listings[self.sample_listings['postal_code'].notna()]),
                'price_availability_percent': (self.sample_listings['price'].notna().sum() / len(self.sample_listings)) * 100,
                'rooms_availability_percent': (self.sample_listings['rooms'].notna().sum() / len(self.sample_listings)) * 100,
                'price_range': {
                    'min': float(self.sample_listings['price'].min()) if not self.sample_listings['price'].isna().all() else None,
                    'max': float(self.sample_listings['price'].max()) if not self.sample_listings['price'].isna().all() else None,
                    'avg': float(self.sample_listings['price'].mean()) if not self.sample_listings['price'].isna().all() else None
                }
            },
            'performance_metrics': self.performance_metrics,
            'success_criteria': {
                'required_match_rate': self.required_match_rate,
                'achieved_match_rate': self.match_rate,
                'meets_criteria': self.match_rate >= self.required_match_rate
            }
        }
        
        # Save metrics to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_path = self.output_dir / f"espoo_step2_metrics_{timestamp}.json"
        
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Quality metrics saved: {metrics_path}")
        print(f"📊 Average quality score: {metrics['match_statistics']['avg_quality_score']:.3f}")
        print(f"📍 Coordinate spread: {metrics['spatial_analysis']['coordinate_spread_km']:.2f} km")
        print(f"🏗️ Buildings with names: {metrics['spatial_analysis']['buildings_with_names']}")
        
        # Store for reporting
        self.comprehensive_metrics = metrics
        return metrics
    
    def _calculate_coordinate_spread(self, df):
        """Calculate the geographic spread of coordinates in kilometers"""
        if len(df) < 2:
            return 0.0
        
        lat_range = df['latitude'].max() - df['latitude'].min()
        lon_range = df['longitude'].max() - df['longitude'].min()
        
        # Convert to approximate kilometers (rough approximation for Finland)
        lat_km = lat_range * 111.0  # 1 degree latitude ≈ 111 km
        lon_km = lon_range * 111.0 * 0.5  # Longitude varies by latitude, ~0.5 at 60°N
        
        return (lat_km**2 + lon_km**2)**0.5
    
    def test_validation_report_generation(self):
        """Test generation of comprehensive validation report"""
        print("\n📄 Generating Comprehensive Validation Report")
        
        # Ensure we have all required data
        if not hasattr(self, 'comprehensive_metrics'):
            self.test_comprehensive_quality_metrics()
        
        metrics = self.comprehensive_metrics
        
        # Generate HTML report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"espoo_step2_report_{timestamp}.html"
        
        html_content = self._generate_comprehensive_html_report(metrics)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.assertTrue(report_path.exists(), "Validation report should be created")
        print(f"✅ Comprehensive validation report generated: {report_path}")
        
        return report_path
    
    def _generate_comprehensive_html_report(self, metrics):
        """Generate comprehensive HTML validation report"""
        success_class = "success" if metrics['success_criteria']['meets_criteria'] else "error"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Espoo Progressive Validation - Step 2: 100 Samples</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .success {{ color: green; font-weight: bold; }}
                .warning {{ color: orange; font-weight: bold; }}
                .error {{ color: red; font-weight: bold; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .metric-box {{ 
                    border: 1px solid #ddd; 
                    padding: 15px; 
                    margin: 10px 0; 
                    border-radius: 5px; 
                    background-color: #f9f9f9; 
                }}
                .performance {{ background-color: #e8f5e8; }}
                .spatial {{ background-color: #e8f0ff; }}
            </style>
        </head>
        <body>
            <h1>🏙️ Espoo Progressive Validation - Step 2: 100 Samples</h1>
            
            <div class="metric-box">
                <h2>📊 Test Summary</h2>
                <p><strong>Validation Type:</strong> {metrics['validation_type']}</p>
                <p><strong>City:</strong> {metrics['city']}</p>
                <p><strong>Sample Size:</strong> {metrics['sample_size']}</p>
                <p><strong>Timestamp:</strong> {metrics['timestamp']}</p>
                <p><strong>Overall Result:</strong> 
                   <span class="{success_class}">
                   {'✅ PASSED' if metrics['success_criteria']['meets_criteria'] else '❌ FAILED'}
                   </span>
                </p>
            </div>
            
            <div class="metric-box">
                <h2>🎯 Match Statistics</h2>
                <p><strong>Match Rate:</strong> 
                   <span class="{success_class}">{metrics['match_statistics']['match_rate_percent']:.2f}%</span>
                </p>
                <p><strong>Required Rate:</strong> {metrics['success_criteria']['required_match_rate']:.1f}%</p>
                <p><strong>Total Matched:</strong> {metrics['match_statistics']['total_matched']}</p>
                <p><strong>Direct Matches:</strong> {metrics['match_statistics']['direct_matches']}</p>
                <p><strong>Buffer Matches:</strong> {metrics['match_statistics']['buffer_matches']}</p>
                <p><strong>No Matches:</strong> {metrics['match_statistics']['no_matches']}</p>
                <p><strong>Average Quality Score:</strong> {metrics['match_statistics']['avg_quality_score']:.3f}</p>
            </div>
            
            <div class="metric-box spatial">
                <h2>🗺️ Spatial Analysis</h2>
                <p><strong>Coordinate Spread:</strong> {metrics['spatial_analysis']['coordinate_spread_km']:.2f} km</p>
                <p><strong>Buildings with Names:</strong> {metrics['spatial_analysis']['buildings_with_names']}</p>
        """
        
        if metrics['spatial_analysis']['avg_buffer_distance'] > 0:
            html_content += f"""
                <p><strong>Average Buffer Distance:</strong> {metrics['spatial_analysis']['avg_buffer_distance']:.1f}m</p>
                <p><strong>Max Buffer Distance:</strong> {metrics['spatial_analysis']['max_buffer_distance']:.1f}m</p>
            """
        
        html_content += f"""
            </div>
            
            <div class="metric-box performance">
                <h2>⚡ Performance Metrics</h2>
                <p><strong>Processing Time:</strong> {metrics['performance_metrics']['processing_time_seconds']:.2f} seconds</p>
                <p><strong>Listings per Second:</strong> {metrics['performance_metrics']['listings_per_second']:.2f}</p>
                <p><strong>Workers Used:</strong> {metrics['performance_metrics']['max_workers']}</p>
                <p><strong>Buildings Processed:</strong> {metrics['performance_metrics']['buildings_processed']:,}</p>
            </div>
            
            <div class="metric-box">
                <h2>💰 Data Quality</h2>
                <p><strong>Price Availability:</strong> {metrics['data_quality']['price_availability_percent']:.1f}%</p>
                <p><strong>Rooms Availability:</strong> {metrics['data_quality']['rooms_availability_percent']:.1f}%</p>
                <p><strong>Addresses with Postal:</strong> {metrics['data_quality']['addresses_with_postal']}</p>
        """
        
        if metrics['data_quality']['price_range']['min'] is not None:
            html_content += f"""
                <p><strong>Price Range:</strong> €{metrics['data_quality']['price_range']['min']:,.0f} - €{metrics['data_quality']['price_range']['max']:,.0f}</p>
                <p><strong>Average Price:</strong> €{metrics['data_quality']['price_range']['avg']:,.0f}</p>
            """
        
        html_content += f"""
            </div>
            
            <div class="metric-box">
                <h2>📋 Sample Results</h2>
                <table>
                    <tr>
                        <th>Address</th>
                        <th>Match Type</th>
                        <th>Building Name</th>
                        <th>Distance (m)</th>
                        <th>Quality Score</th>
                        <th>Price</th>
                    </tr>
        """
        
        # Show first 20 results
        for _, row in self.validation_results.head(20).iterrows():
            distance_str = f"{row['distance_m']:.1f}" if row['distance_m'] != float('inf') else "N/A"
            building_name = row['building_name'] if pd.notna(row['building_name']) and row['building_name'] else "N/A"
            price_str = f"€{row['price']:,.0f}" if pd.notna(row['price']) else "N/A"
            
            html_content += f"""
                <tr>
                    <td>{row['address']}</td>
                    <td>{row['match_type']}</td>
                    <td>{building_name}</td>
                    <td>{distance_str}</td>
                    <td>{row['quality_score']:.3f}</td>
                    <td>{price_str}</td>
                </tr>
            """
        
        if len(self.validation_results) > 20:
            html_content += f"""
                <tr>
                    <td colspan="6"><em>... and {len(self.validation_results) - 20} more results</em></td>
                </tr>
            """
        
        html_content += f"""
                </table>
            </div>
            
            <div class="metric-box">
                <h2>🚀 Next Steps</h2>
                <p>✅ Step 1 Complete: 10 Sample Validation</p>
                <p>✅ Step 2 Complete: 100 Sample Validation</p>
                <p>➡️ Next: Run Step 3 - Full Scale Validation</p>
                <p>📝 Command: <code>uv run python -m pytest tests/validation/test_espoo_step3_full_scale.py -v</code></p>
            </div>
            
        </body>
        </html>
        """
        
        return html_content
    
    def test_complete_workflow(self):
        """Test the complete Step 2 validation workflow"""
        print("\n🚀 Testing Complete Step 2 Validation Workflow")
        
        # Run all validation steps
        self.test_bug_prevention_prerequisites()
        buildings_gdf = self.test_osm_buildings_loading_and_filtering()
        df = self.test_sample_listings_loading_medium_scale()
        results_df, match_rate = self.test_enhanced_spatial_matching()
        performance_metrics = self.test_performance_benchmarking()
        comprehensive_metrics = self.test_comprehensive_quality_metrics()
        report_path = self.test_validation_report_generation()
        
        # Final validation
        success = match_rate >= self.required_match_rate
        
        print(f"\n📊 STEP 2 VALIDATION SUMMARY")
        print("=" * 70)
        print(f"🏙️ City: {self.city}")
        print(f"📋 Sample Size: {self.sample_size} listings")
        print(f"📈 Match Rate: {match_rate:.2f}%")
        print(f"🎯 Success Criteria: ≥{self.required_match_rate}%")
        print(f"⚡ Processing Time: {performance_metrics['processing_time_seconds']:.2f}s")
        print(f"🚀 Listings/sec: {performance_metrics['listings_per_second']:.2f}")
        print(f"✅ Result: {'PASSED' if success else 'FAILED'}")
        print(f"📄 Report: {report_path}")
        
        if success:
            print(f"\n🚀 Next Steps:")
            print(f"   1. Review comprehensive report: {report_path}")
            print(f"   2. Run Step 3 validation: test_espoo_step3_full_scale.py")
            print(f"   3. Command: uv run python -m pytest tests/validation/test_espoo_step3_full_scale.py -v")
        else:
            print(f"\n❌ Step 2 Failed - Address Issues Before Proceeding:")
            print(f"   1. Review spatial matching logic")
            print(f"   2. Check OSM building data coverage")
            print(f"   3. Analyze no-match cases for patterns")
        
        self.assertTrue(success, f"Step 2 validation should succeed with ≥{self.required_match_rate}% match rate")


def run_espoo_step2_validation():
    """Run the Espoo Step 2 validation test suite"""
    print("🏙️ Espoo Progressive Validation: Step 2 - 100 Samples Test")
    print("=" * 80)
    print("Testing medium-scale Espoo geospatial integration with OSM buildings")
    print("Success Criteria: ≥98% match rate for medium scale validation")
    print("Requirements: 5.1, 5.2, 5.3, 5.4")
    print("=" * 80)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEspooStep2Validation)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_espoo_step2_validation()
    sys.exit(0 if success else 1)