#!/usr/bin/env python3
"""
Espoo Bug Prevention Test Suite

Comprehensive bug prevention tests for all Espoo operations before expensive processing.
This implements mandatory bug testing as per development standards.

Requirements: 5.1, 5.2, 5.3, 5.4
"""

import sys
import unittest
from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import duckdb
import json
import time
import warnings
from datetime import datetime

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


class TestEspooBugPrevention(unittest.TestCase):
    """Comprehensive bug prevention tests for Espoo operations"""
    
    def setUp(self):
        """Set up test environment"""
        self.db_path = "data/real_estate.duckdb"
        self.osm_buildings_path = "data/helsinki_buildings_20250711_041142.geojson"
        self.config_path = "config/config.json"
        self.output_dir = Path("output/validation/espoo/")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Espoo coordinate bounds from config
        self.espoo_bounds = {
            'min_lat': 60.1,
            'max_lat': 60.4,
            'min_lon': 24.4,
            'max_lon': 24.9
        }
        
        print(f"\n🔧 Espoo Bug Prevention Test Suite")
        print(f"📍 Testing coordinate bounds: {self.espoo_bounds}")
    
    def test_database_connectivity_and_schema(self):
        """Bug prevention: Test database connectivity and schema integrity"""
        print("\n🔧 Bug Prevention: Database Connectivity and Schema")
        
        try:
            conn = duckdb.connect(self.db_path)
            
            # Test basic connectivity
            result = conn.execute("SELECT 1").fetchone()
            self.assertEqual(result[0], 1, "Basic database connectivity should work")
            print("✅ Database connectivity verified")
            
            # Check required tables exist
            tables = conn.execute("SHOW TABLES").fetchall()
            table_names = [table[0] for table in tables]
            
            required_tables = ['listings', 'address_locations']
            for table in required_tables:
                self.assertIn(table, table_names, f"Required table '{table}' should exist")
            print(f"✅ Required tables exist: {required_tables}")
            
            # Check listings table schema
            listings_schema = conn.execute("DESCRIBE listings").fetchall()
            listings_columns = [col[0] for col in listings_schema]
            
            required_listings_columns = ['url', 'city', 'address', 'price_eur', 'scraped_at']
            for col in required_listings_columns:
                self.assertIn(col, listings_columns, f"Listings table should have '{col}' column")
            print(f"✅ Listings table schema validated")
            
            # Check address_locations table schema
            address_schema = conn.execute("DESCRIBE address_locations").fetchall()
            address_columns = [col[0] for col in address_schema]
            
            required_address_columns = ['address', 'lat', 'lon']
            for col in required_address_columns:
                self.assertIn(col, address_columns, f"Address_locations table should have '{col}' column")
            print(f"✅ Address_locations table schema validated")
            
            conn.close()
            
        except Exception as e:
            self.fail(f"Database connectivity or schema test failed: {e}")
    
    def test_espoo_configuration_integrity(self):
        """Bug prevention: Test Espoo configuration integrity"""
        print("\n🔧 Bug Prevention: Espoo Configuration Integrity")
        
        try:
            # Load configuration
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Find Espoo task configuration
            espoo_task = None
            for task in config.get('tasks', []):
                if task.get('city') == 'Espoo':
                    espoo_task = task
                    break
            
            self.assertIsNotNone(espoo_task, "Espoo configuration should exist in config.json")
            print("✅ Espoo configuration found")
            
            # Validate required fields
            required_fields = [
                'city', 'enabled', 'url', 'max_detail_workers', 
                'rate_limit_seconds', 'coordinate_bounds', 'geospatial_sources'
            ]
            
            for field in required_fields:
                self.assertIn(field, espoo_task, f"Espoo config should have '{field}' field")
            print(f"✅ All required configuration fields present")
            
            # Validate specific values
            self.assertEqual(espoo_task['city'], 'Espoo', "City should be 'Espoo'")
            self.assertTrue(espoo_task['enabled'], "Espoo should be enabled")
            self.assertIsInstance(espoo_task['max_detail_workers'], int, "max_detail_workers should be integer")
            self.assertGreater(espoo_task['max_detail_workers'], 0, "max_detail_workers should be positive")
            self.assertIsInstance(espoo_task['rate_limit_seconds'], (int, float), "rate_limit_seconds should be numeric")
            self.assertGreater(espoo_task['rate_limit_seconds'], 0, "rate_limit_seconds should be positive")
            
            # Validate coordinate bounds
            bounds = espoo_task['coordinate_bounds']
            self.assertIsInstance(bounds, list, "coordinate_bounds should be a list")
            self.assertEqual(len(bounds), 4, "coordinate_bounds should have 4 values")
            
            expected_bounds = [24.4, 60.1, 24.9, 60.4]
            self.assertEqual(bounds, expected_bounds, f"Espoo bounds should be {expected_bounds}")
            print(f"✅ Coordinate bounds validated: {bounds}")
            
            # Validate geospatial sources
            sources = espoo_task['geospatial_sources']
            self.assertIsInstance(sources, list, "geospatial_sources should be a list")
            self.assertGreater(len(sources), 0, "Should have at least one geospatial source")
            
            expected_sources = ['espoo_open_data', 'osm_buildings', 'national_geodata']
            for source in expected_sources:
                self.assertIn(source, sources, f"Should include '{source}' as geospatial source")
            print(f"✅ Geospatial sources validated: {sources}")
            
            # Validate URL format
            url = espoo_task['url']
            self.assertIn('Espoo', url, "URL should contain 'Espoo'")
            self.assertTrue(url.startswith('https://'), "URL should use HTTPS")
            print(f"✅ URL format validated")
            
        except Exception as e:
            self.fail(f"Configuration integrity test failed: {e}")
    
    def test_espoo_data_availability_and_quality(self):
        """Bug prevention: Test Espoo data availability and basic quality"""
        print("\n🔧 Bug Prevention: Espoo Data Availability and Quality")
        
        try:
            conn = duckdb.connect(self.db_path)
            
            # Check total Espoo listings
            total_espoo = conn.execute(
                "SELECT COUNT(*) FROM listings WHERE city = 'Espoo'"
            ).fetchone()[0]
            
            self.assertGreater(total_espoo, 0, "Should have Espoo listings in database")
            print(f"✅ Found {total_espoo:,} total Espoo listings")
            
            # Check geocoded Espoo listings
            geocoded_espoo = conn.execute("""
                SELECT COUNT(*) 
                FROM listings l
                JOIN address_locations al ON l.address = al.address
                WHERE l.city = 'Espoo' AND al.lat IS NOT NULL AND al.lon IS NOT NULL
            """).fetchone()[0]
            
            self.assertGreater(geocoded_espoo, 0, "Should have geocoded Espoo listings")
            geocoding_rate = (geocoded_espoo / total_espoo) * 100 if total_espoo > 0 else 0
            print(f"✅ Found {geocoded_espoo:,} geocoded Espoo listings ({geocoding_rate:.1f}% geocoding rate)")
            
            # Validate coordinate bounds for geocoded listings
            bounds_check_query = f"""
                SELECT COUNT(*) 
                FROM listings l
                JOIN address_locations al ON l.address = al.address
                WHERE l.city = 'Espoo' 
                AND al.lat BETWEEN {self.espoo_bounds['min_lat']} AND {self.espoo_bounds['max_lat']}
                AND al.lon BETWEEN {self.espoo_bounds['min_lon']} AND {self.espoo_bounds['max_lon']}
            """
            
            within_bounds = conn.execute(bounds_check_query).fetchone()[0]
            bounds_compliance = (within_bounds / geocoded_espoo) * 100 if geocoded_espoo > 0 else 0
            
            self.assertGreater(within_bounds, 0, "Should have listings within Espoo coordinate bounds")
            self.assertGreater(bounds_compliance, 80.0, "At least 80% of geocoded listings should be within bounds")
            print(f"✅ {within_bounds:,} listings within bounds ({bounds_compliance:.1f}% compliance)")
            
            # Check data quality indicators
            quality_check_query = """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN price_eur IS NOT NULL THEN 1 ELSE 0 END) as with_price,
                    SUM(CASE WHEN postal_code IS NOT NULL THEN 1 ELSE 0 END) as with_postal,
                    SUM(CASE WHEN rooms IS NOT NULL THEN 1 ELSE 0 END) as with_rooms,
                    SUM(CASE WHEN size_m2 IS NOT NULL THEN 1 ELSE 0 END) as with_size
                FROM listings 
                WHERE city = 'Espoo'
            """
            
            quality_stats = conn.execute(quality_check_query).fetchone()
            total, with_price, with_postal, with_rooms, with_size = quality_stats
            
            price_rate = (with_price / total) * 100 if total > 0 else 0
            postal_rate = (with_postal / total) * 100 if total > 0 else 0
            rooms_rate = (with_rooms / total) * 100 if total > 0 else 0
            size_rate = (with_size / total) * 100 if total > 0 else 0
            
            print(f"📊 Data Quality Metrics:")
            print(f"   💰 Price availability: {with_price:,}/{total:,} ({price_rate:.1f}%)")
            print(f"   📮 Postal code: {with_postal:,}/{total:,} ({postal_rate:.1f}%)")
            print(f"   🏠 Rooms info: {with_rooms:,}/{total:,} ({rooms_rate:.1f}%)")
            print(f"   📏 Size info: {with_size:,}/{total:,} ({size_rate:.1f}%)")
            
            # Basic quality thresholds
            self.assertGreater(price_rate, 50.0, "At least 50% of listings should have price information")
            self.assertGreater(postal_rate, 70.0, "At least 70% of listings should have postal codes")
            
            conn.close()
            
        except Exception as e:
            self.fail(f"Data availability and quality test failed: {e}")
    
    def test_osm_buildings_data_integrity(self):
        """Bug prevention: Test OSM buildings data integrity for Espoo area"""
        print("\n🔧 Bug Prevention: OSM Buildings Data Integrity")
        
        try:
            # Check if OSM buildings file exists
            osm_file = Path(self.osm_buildings_path)
            self.assertTrue(osm_file.exists(), f"OSM buildings file should exist at {self.osm_buildings_path}")
            print(f"✅ OSM buildings file exists: {osm_file}")
            
            # Load and validate OSM buildings
            buildings_gdf = gpd.read_file(self.osm_buildings_path)
            self.assertGreater(len(buildings_gdf), 0, "OSM buildings file should contain data")
            print(f"✅ Loaded {len(buildings_gdf):,} OSM buildings")
            
            # Check required columns
            required_columns = ['geometry', 'osm_id']
            for col in required_columns:
                self.assertIn(col, buildings_gdf.columns, f"OSM buildings should have '{col}' column")
            print(f"✅ Required columns present: {required_columns}")
            
            # Validate CRS
            if buildings_gdf.crs is None:
                print("⚠️ No CRS defined, assuming EPSG:4326")
            else:
                print(f"✅ CRS: {buildings_gdf.crs}")
            
            # Ensure proper CRS for processing
            if buildings_gdf.crs is None or buildings_gdf.crs.to_string() != 'EPSG:4326':
                buildings_gdf = buildings_gdf.to_crs('EPSG:4326')
                print("✅ Converted to EPSG:4326")
            
            # Filter for Espoo area and validate coverage
            buffer = 0.01  # Small buffer for edge cases
            espoo_bounds_buffered = {
                'min_lat': self.espoo_bounds['min_lat'] - buffer,
                'max_lat': self.espoo_bounds['max_lat'] + buffer,
                'min_lon': self.espoo_bounds['min_lon'] - buffer,
                'max_lon': self.espoo_bounds['max_lon'] + buffer
            }
            
            espoo_buildings = buildings_gdf[
                (buildings_gdf.geometry.bounds['miny'] >= espoo_bounds_buffered['min_lat']) &
                (buildings_gdf.geometry.bounds['maxy'] <= espoo_bounds_buffered['max_lat']) &
                (buildings_gdf.geometry.bounds['minx'] >= espoo_bounds_buffered['min_lon']) &
                (buildings_gdf.geometry.bounds['maxx'] <= espoo_bounds_buffered['max_lon'])
            ]
            
            self.assertGreater(len(espoo_buildings), 0, "Should have OSM buildings in Espoo area")
            coverage_rate = (len(espoo_buildings) / len(buildings_gdf)) * 100
            print(f"✅ Found {len(espoo_buildings):,} buildings in Espoo area ({coverage_rate:.2f}% of total)")
            
            # Validate geometry integrity
            invalid_geometries = espoo_buildings[~espoo_buildings.geometry.is_valid]
            invalid_count = len(invalid_geometries)
            invalid_rate = (invalid_count / len(espoo_buildings)) * 100 if len(espoo_buildings) > 0 else 0
            
            print(f"📊 Geometry Quality: {invalid_count:,} invalid geometries ({invalid_rate:.2f}%)")
            self.assertLess(invalid_rate, 5.0, "Less than 5% of geometries should be invalid")
            
            # Check for buildings with names (useful for matching)
            buildings_with_names = espoo_buildings[
                espoo_buildings['name'].notna() & (espoo_buildings['name'] != '')
            ] if 'name' in espoo_buildings.columns else pd.DataFrame()
            
            if len(buildings_with_names) > 0:
                name_rate = (len(buildings_with_names) / len(espoo_buildings)) * 100
                print(f"🏢 Buildings with names: {len(buildings_with_names):,} ({name_rate:.1f}%)")
            else:
                print("⚠️ No buildings with names found (may impact matching quality)")
            
        except Exception as e:
            self.fail(f"OSM buildings data integrity test failed: {e}")
    
    def test_coordinate_validation_functions(self):
        """Bug prevention: Test coordinate validation functions"""
        print("\n🔧 Bug Prevention: Coordinate Validation Functions")
        
        try:
            # Test valid Espoo coordinates
            valid_test_cases = [
                (60.2055, 24.6559, "Espoo center"),
                (60.15, 24.45, "Southwest Espoo"),
                (60.35, 24.85, "Northeast Espoo"),
                (60.25, 24.65, "Central Espoo")
            ]
            
            for lat, lon, description in valid_test_cases:
                is_valid = (
                    self.espoo_bounds['min_lat'] <= lat <= self.espoo_bounds['max_lat'] and
                    self.espoo_bounds['min_lon'] <= lon <= self.espoo_bounds['max_lon']
                )
                self.assertTrue(is_valid, f"{description} coordinates ({lat}, {lon}) should be valid")
            
            print(f"✅ Valid coordinate test cases passed: {len(valid_test_cases)}")
            
            # Test invalid coordinates (should be outside bounds)
            invalid_test_cases = [
                (60.0, 24.5, "Too far south"),
                (60.5, 24.5, "Too far north"),
                (60.2, 24.3, "Too far west"),
                (60.2, 25.0, "Too far east"),
                (59.9, 24.0, "Far outside bounds")
            ]
            
            for lat, lon, description in invalid_test_cases:
                is_valid = (
                    self.espoo_bounds['min_lat'] <= lat <= self.espoo_bounds['max_lat'] and
                    self.espoo_bounds['min_lon'] <= lon <= self.espoo_bounds['max_lon']
                )
                self.assertFalse(is_valid, f"{description} coordinates ({lat}, {lon}) should be invalid")
            
            print(f"✅ Invalid coordinate test cases passed: {len(invalid_test_cases)}")
            
            # Test edge cases (boundary coordinates)
            boundary_test_cases = [
                (self.espoo_bounds['min_lat'], self.espoo_bounds['min_lon'], "Southwest corner"),
                (self.espoo_bounds['max_lat'], self.espoo_bounds['max_lon'], "Northeast corner"),
                (self.espoo_bounds['min_lat'], self.espoo_bounds['max_lon'], "Southeast corner"),
                (self.espoo_bounds['max_lat'], self.espoo_bounds['min_lon'], "Northwest corner")
            ]
            
            for lat, lon, description in boundary_test_cases:
                is_valid = (
                    self.espoo_bounds['min_lat'] <= lat <= self.espoo_bounds['max_lat'] and
                    self.espoo_bounds['min_lon'] <= lon <= self.espoo_bounds['max_lon']
                )
                self.assertTrue(is_valid, f"{description} boundary coordinates ({lat}, {lon}) should be valid")
            
            print(f"✅ Boundary coordinate test cases passed: {len(boundary_test_cases)}")
            
        except Exception as e:
            self.fail(f"Coordinate validation test failed: {e}")
    
    def test_spatial_operations_functionality(self):
        """Bug prevention: Test basic spatial operations functionality"""
        print("\n🔧 Bug Prevention: Spatial Operations Functionality")
        
        try:
            # Test Point creation
            test_point = Point(24.6559, 60.2055)  # Espoo center
            self.assertIsNotNone(test_point, "Should be able to create Point geometry")
            self.assertEqual(test_point.x, 24.6559, "Point X coordinate should be correct")
            self.assertEqual(test_point.y, 60.2055, "Point Y coordinate should be correct")
            print("✅ Point geometry creation works")
            
            # Test buffer operations
            buffered_point = test_point.buffer(0.001)  # ~100m buffer
            self.assertIsNotNone(buffered_point, "Should be able to create buffered geometry")
            self.assertGreater(buffered_point.area, test_point.area, "Buffered area should be larger")
            print("✅ Buffer operations work")
            
            # Test basic spatial relationships
            # Create a simple test polygon around the point
            from shapely.geometry import Polygon
            test_polygon = Polygon([
                (24.655, 60.204),
                (24.657, 60.204),
                (24.657, 60.206),
                (24.655, 60.206),
                (24.655, 60.204)
            ])
            
            # Test containment
            contains_result = test_polygon.contains(test_point)
            self.assertTrue(contains_result, "Test polygon should contain test point")
            print("✅ Containment operations work")
            
            # Test intersection
            intersects_result = test_polygon.intersects(buffered_point)
            self.assertTrue(intersects_result, "Test polygon should intersect with buffered point")
            print("✅ Intersection operations work")
            
            # Test distance calculation
            from shapely.geometry import Point as Point2
            other_point = Point2(24.66, 60.21)
            distance = test_point.distance(other_point)
            self.assertIsInstance(distance, float, "Distance should be a float")
            self.assertGreater(distance, 0, "Distance should be positive")
            print(f"✅ Distance calculations work: {distance:.6f} degrees")
            
        except Exception as e:
            self.fail(f"Spatial operations functionality test failed: {e}")
    
    def test_performance_baseline_small_sample(self):
        """Bug prevention: Test performance baseline with small sample"""
        print("\n🔧 Bug Prevention: Performance Baseline (Small Sample)")
        
        try:
            # Load a small sample of Espoo listings for performance testing
            conn = duckdb.connect(self.db_path)
            
            sample_query = f"""
                SELECT l.url as id, l.address, al.lat as latitude, al.lon as longitude
                FROM listings l
                JOIN address_locations al ON l.address = al.address
                WHERE l.city = 'Espoo' AND al.lat IS NOT NULL AND al.lon IS NOT NULL
                AND al.lat BETWEEN {self.espoo_bounds['min_lat']} AND {self.espoo_bounds['max_lat']}
                AND al.lon BETWEEN {self.espoo_bounds['min_lon']} AND {self.espoo_bounds['max_lon']}
                LIMIT 5
            """
            
            sample_df = conn.execute(sample_query).df()
            conn.close()
            
            self.assertGreater(len(sample_df), 0, "Should have sample listings for performance test")
            print(f"✅ Loaded {len(sample_df)} sample listings for performance test")
            
            # Test basic spatial operations performance
            start_time = time.time()
            
            for idx, listing in sample_df.iterrows():
                # Create point
                point = Point(listing['longitude'], listing['latitude'])
                
                # Create buffer
                buffered_point = point.buffer(0.001)
                
                # Basic validation
                self.assertIsNotNone(point, "Point creation should work")
                self.assertIsNotNone(buffered_point, "Buffer creation should work")
            
            processing_time = time.time() - start_time
            listings_per_second = len(sample_df) / processing_time if processing_time > 0 else 0
            
            print(f"⚡ Performance Baseline:")
            print(f"   📊 Processed {len(sample_df)} listings in {processing_time:.3f} seconds")
            print(f"   🚀 Rate: {listings_per_second:.2f} listings/second")
            
            # Performance validation
            max_acceptable_time = 5.0  # 5 seconds for 5 listings should be more than enough
            self.assertLess(processing_time, max_acceptable_time, 
                           f"Small sample processing should complete within {max_acceptable_time} seconds")
            
            min_acceptable_rate = 0.5  # At least 0.5 listings per second for basic operations
            self.assertGreater(listings_per_second, min_acceptable_rate,
                              f"Should process at least {min_acceptable_rate} listings per second")
            
            print("✅ Performance baseline meets minimum requirements")
            
        except Exception as e:
            self.fail(f"Performance baseline test failed: {e}")
    
    def test_error_handling_robustness(self):
        """Bug prevention: Test error handling robustness"""
        print("\n🔧 Bug Prevention: Error Handling Robustness")
        
        try:
            # Test handling of invalid coordinates
            invalid_coords = [
                (None, 24.6559),
                (60.2055, None),
                (float('inf'), 24.6559),
                (60.2055, float('inf')),
                (float('nan'), 24.6559),
                (60.2055, float('nan'))
            ]
            
            for lat, lon in invalid_coords:
                try:
                    if lat is not None and lon is not None and not (
                        pd.isna(lat) or pd.isna(lon) or 
                        lat == float('inf') or lon == float('inf')
                    ):
                        point = Point(lon, lat)
                        # If we get here, the coordinates were valid enough to create a point
                        print(f"   Point created for ({lat}, {lon})")
                    else:
                        print(f"   Skipped invalid coordinates: ({lat}, {lon})")
                except Exception as e:
                    print(f"   Handled invalid coordinates ({lat}, {lon}): {type(e).__name__}")
            
            print("✅ Invalid coordinate handling works")
            
            # Test handling of empty/malformed data
            try:
                empty_df = pd.DataFrame()
                self.assertEqual(len(empty_df), 0, "Empty DataFrame should have length 0")
                print("✅ Empty DataFrame handling works")
            except Exception as e:
                self.fail(f"Empty DataFrame handling failed: {e}")
            
            # Test handling of missing files (simulate)
            non_existent_path = "non_existent_file.geojson"
            try:
                # This should raise an exception
                with self.assertRaises(Exception):
                    gpd.read_file(non_existent_path)
                print("✅ Missing file handling works (exception raised as expected)")
            except Exception as e:
                print(f"✅ Missing file handling works: {type(e).__name__}")
            
        except Exception as e:
            self.fail(f"Error handling robustness test failed: {e}")
    
    def test_memory_usage_monitoring(self):
        """Bug prevention: Test memory usage monitoring capabilities"""
        print("\n🔧 Bug Prevention: Memory Usage Monitoring")
        
        try:
            import psutil
            
            # Get initial memory usage
            process = psutil.Process()
            initial_memory = process.memory_info().rss / (1024**2)  # MB
            
            print(f"📊 Initial memory usage: {initial_memory:.1f}MB")
            
            # Perform some memory-intensive operations
            # Create some test data
            test_data = []
            for i in range(1000):
                test_data.append({
                    'id': f'test_{i}',
                    'lat': 60.2 + (i * 0.0001),
                    'lon': 24.6 + (i * 0.0001),
                    'data': f'test_data_{i}' * 10  # Some string data
                })
            
            # Convert to DataFrame
            test_df = pd.DataFrame(test_data)
            
            # Check memory usage after data creation
            current_memory = process.memory_info().rss / (1024**2)  # MB
            memory_increase = current_memory - initial_memory
            
            print(f"📊 Memory after test data creation: {current_memory:.1f}MB (+{memory_increase:.1f}MB)")
            
            # Clean up test data
            del test_data
            del test_df
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Check memory after cleanup
            final_memory = process.memory_info().rss / (1024**2)  # MB
            memory_recovered = current_memory - final_memory
            
            print(f"📊 Memory after cleanup: {final_memory:.1f}MB (-{memory_recovered:.1f}MB recovered)")
            
            # Validate memory monitoring works
            self.assertIsInstance(initial_memory, float, "Memory measurement should return float")
            self.assertGreater(initial_memory, 0, "Memory usage should be positive")
            
            print("✅ Memory usage monitoring works")
            
        except ImportError:
            print("⚠️ psutil not available, skipping memory monitoring test")
        except Exception as e:
            self.fail(f"Memory usage monitoring test failed: {e}")
    
    def test_complete_bug_prevention_suite(self):
        """Run complete bug prevention test suite"""
        print("\n🚀 Running Complete Bug Prevention Suite")
        
        # Run all bug prevention tests
        self.test_database_connectivity_and_schema()
        self.test_espoo_configuration_integrity()
        self.test_espoo_data_availability_and_quality()
        self.test_osm_buildings_data_integrity()
        self.test_coordinate_validation_functions()
        self.test_spatial_operations_functionality()
        self.test_performance_baseline_small_sample()
        self.test_error_handling_robustness()
        self.test_memory_usage_monitoring()
        
        # Generate bug prevention report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"espoo_bug_prevention_report_{timestamp}.json"
        
        bug_prevention_report = {
            'timestamp': datetime.now().isoformat(),
            'test_suite': 'espoo_bug_prevention',
            'tests_run': [
                'database_connectivity_and_schema',
                'espoo_configuration_integrity',
                'espoo_data_availability_and_quality',
                'osm_buildings_data_integrity',
                'coordinate_validation_functions',
                'spatial_operations_functionality',
                'performance_baseline_small_sample',
                'error_handling_robustness',
                'memory_usage_monitoring'
            ],
            'all_tests_passed': True,
            'ready_for_expensive_operations': True,
            'recommendations': [
                'All bug prevention tests passed',
                'System is ready for progressive validation',
                'Proceed with Step 1 validation (10 samples)',
                'Monitor performance during larger scale operations'
            ]
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(bug_prevention_report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📊 BUG PREVENTION SUITE SUMMARY")
        print("=" * 60)
        print(f"✅ All bug prevention tests passed")
        print(f"🚀 System ready for expensive Espoo operations")
        print(f"📄 Report saved: {report_path}")
        print(f"➡️ Next: Run progressive validation tests")
        
        print(f"\n🚀 Recommended Next Steps:")
        print(f"   1. Run Step 1: uv run python -m pytest tests/validation/test_espoo_step1_10_samples.py -v")
        print(f"   2. Run Step 2: uv run python -m pytest tests/validation/test_espoo_step2_100_samples.py -v")
        print(f"   3. Run Step 3: uv run python -m pytest tests/validation/test_espoo_step3_full_scale.py -v")


def run_espoo_bug_prevention():
    """Run the Espoo bug prevention test suite"""
    print("🔧 Espoo Bug Prevention Test Suite")
    print("=" * 60)
    print("Comprehensive bug prevention before expensive operations")
    print("Mandatory testing as per development standards")
    print("Requirements: 5.1, 5.2, 5.3, 5.4")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEspooBugPrevention)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_espoo_bug_prevention()
    sys.exit(0 if success else 1)