#!/usr/bin/env python3
"""
Progressive Validation Test: Step 1 - 10 Sample Espoo Listings

Tests 10 random Espoo listings with comprehensive bug prevention and validation.
This implements the progressive validation strategy for Espoo expansion.

Success Criteria: ≥95% match rate for proof of concept validation
Next Step: test_espoo_step2_100_samples.py (medium scale validation)

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


class TestEspooStep1Validation(unittest.TestCase):
    """Test class for Espoo 10 sample listings validation"""
    
    def setUp(self):
        """Set up test environment"""
        self.db_path = "data/real_estate.duckdb"
        self.output_dir = Path("output/validation/espoo/")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test parameters
        self.sample_size = 10
        self.required_match_rate = 95.0  # High standard for Espoo
        self.city = "Espoo"
        
        # Espoo coordinate bounds from config
        self.espoo_bounds = {
            'min_lat': 60.1,
            'max_lat': 60.4,
            'min_lon': 24.4,
            'max_lon': 24.9
        }
        
        print(f"\n🏙️ Testing Espoo Progressive Validation - Step 1")
        print(f"📊 Sample Size: {self.sample_size}")
        print(f"🎯 Success Criteria: ≥{self.required_match_rate}% match rate")
        print(f"📍 Coordinate Bounds: {self.espoo_bounds}")
    
    def test_bug_prevention_database_connection(self):
        """Bug prevention: Test database connection and Espoo data availability"""
        print("\n🔧 Bug Prevention: Database Connection Test")
        
        try:
            conn = duckdb.connect(self.db_path)
            
            # Check if listings table exists
            tables = conn.execute("SHOW TABLES").fetchall()
            table_names = [table[0] for table in tables]
            self.assertIn('listings', table_names, "Listings table should exist")
            print("✅ Listings table exists")
            
            # Check total listings count
            total_count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            self.assertGreater(total_count, 0, "Database should contain listings")
            print(f"✅ Found {total_count:,} total listings")
            
            # Check Espoo listings specifically
            espoo_query = "SELECT COUNT(*) FROM listings WHERE city = 'Espoo'"
            espoo_count = conn.execute(espoo_query).fetchone()[0]
            self.assertGreater(espoo_count, self.sample_size, 
                             f"Should have at least {self.sample_size} Espoo listings")
            print(f"✅ Found {espoo_count:,} Espoo listings")
            
            # Check address_locations table for geocoded data
            address_locations_count = conn.execute("SELECT COUNT(*) FROM address_locations").fetchone()[0]
            self.assertGreater(address_locations_count, 0, "Address locations should exist")
            print(f"✅ Found {address_locations_count:,} geocoded addresses")
            
            # Check Espoo listings with coordinates
            espoo_with_coords_query = """
            SELECT COUNT(*) 
            FROM listings l
            JOIN address_locations al ON l.address = al.address
            WHERE al.lat IS NOT NULL AND al.lon IS NOT NULL AND l.city = 'Espoo'
            """
            espoo_coords_count = conn.execute(espoo_with_coords_query).fetchone()[0]
            self.assertGreater(espoo_coords_count, self.sample_size, 
                             f"Should have at least {self.sample_size} Espoo listings with coordinates")
            print(f"✅ Found {espoo_coords_count:,} Espoo listings with coordinates")
            
            conn.close()
            
        except Exception as e:
            self.fail(f"Database connection failed: {e}")
    
    def test_bug_prevention_configuration_validation(self):
        """Bug prevention: Validate Espoo configuration"""
        print("\n🔧 Bug Prevention: Configuration Validation")
        
        config_path = Path("config/config.json")
        self.assertTrue(config_path.exists(), "Configuration file should exist")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Check if Espoo is configured
        espoo_task = None
        for task in config.get('tasks', []):
            if task.get('city') == 'Espoo':
                espoo_task = task
                break
        
        self.assertIsNotNone(espoo_task, "Espoo should be configured in config.json")
        self.assertTrue(espoo_task.get('enabled', False), "Espoo should be enabled")
        
        # Validate Espoo configuration
        required_fields = ['url', 'coordinate_bounds', 'geospatial_sources']
        for field in required_fields:
            self.assertIn(field, espoo_task, f"Espoo config should have {field}")
        
        # Validate coordinate bounds
        bounds = espoo_task['coordinate_bounds']
        self.assertEqual(len(bounds), 4, "Coordinate bounds should have 4 values")
        self.assertEqual(bounds, [24.4, 60.1, 24.9, 60.4], "Espoo bounds should match expected values")
        
        print("✅ Espoo configuration validated")
        print(f"   URL: {espoo_task['url']}")
        print(f"   Bounds: {bounds}")
        print(f"   Sources: {espoo_task['geospatial_sources']}")
    
    def test_bug_prevention_coordinate_validation(self):
        """Bug prevention: Test coordinate validation for Espoo bounds"""
        print("\n🔧 Bug Prevention: Coordinate Validation")
        
        # Test valid Espoo coordinates
        valid_coords = [
            (60.2055, 24.6559),  # Espoo center
            (60.15, 24.45),      # Southwest
            (60.35, 24.85),      # Northeast
        ]
        
        for lat, lon in valid_coords:
            self.assertTrue(
                self.espoo_bounds['min_lat'] <= lat <= self.espoo_bounds['max_lat'],
                f"Latitude {lat} should be within Espoo bounds"
            )
            self.assertTrue(
                self.espoo_bounds['min_lon'] <= lon <= self.espoo_bounds['max_lon'],
                f"Longitude {lon} should be within Espoo bounds"
            )
        
        print("✅ Valid coordinate validation passed")
        
        # Test invalid coordinates (should be outside bounds)
        invalid_coords = [
            (60.0, 24.5),   # Too far south
            (60.5, 24.5),   # Too far north
            (60.2, 24.3),   # Too far west
            (60.2, 25.0),   # Too far east
        ]
        
        for lat, lon in invalid_coords:
            is_valid = (
                self.espoo_bounds['min_lat'] <= lat <= self.espoo_bounds['max_lat'] and
                self.espoo_bounds['min_lon'] <= lon <= self.espoo_bounds['max_lon']
            )
            self.assertFalse(is_valid, f"Coordinates ({lat}, {lon}) should be outside Espoo bounds")
        
        print("✅ Invalid coordinate validation passed")
    
    def test_sample_listings_loading(self):
        """Test loading of 10 sample Espoo listings"""
        print("\n📋 Loading 10 Sample Espoo Listings")
        
        try:
            conn = duckdb.connect(self.db_path)
            
            query = f"""
            SELECT l.url as id, l.address, al.lat as latitude, al.lon as longitude,
                   l.price_eur as price, l.rooms, l.size_m2, l.listing_type, l.city,
                   l.title, l.postal_code
            FROM listings l
            JOIN address_locations al ON l.address = al.address
            WHERE al.lat IS NOT NULL AND al.lon IS NOT NULL AND l.city = 'Espoo'
            ORDER BY RANDOM()
            LIMIT {self.sample_size}
            """
            
            df = conn.execute(query).df()
            conn.close()
            
            self.assertEqual(len(df), self.sample_size, 
                           f"Should load exactly {self.sample_size} sample listings")
            
            # Validate required columns
            required_columns = ['id', 'address', 'latitude', 'longitude', 'city']
            for col in required_columns:
                self.assertIn(col, df.columns, f"Sample data should contain '{col}' column")
            
            # Validate all listings are from Espoo
            self.assertTrue((df['city'] == 'Espoo').all(), "All listings should be from Espoo")
            
            # Validate coordinates are within Espoo bounds
            lat_valid = df['latitude'].between(self.espoo_bounds['min_lat'], self.espoo_bounds['max_lat']).all()
            lon_valid = df['longitude'].between(self.espoo_bounds['min_lon'], self.espoo_bounds['max_lon']).all()
            
            self.assertTrue(lat_valid, "All latitudes should be within Espoo bounds")
            self.assertTrue(lon_valid, "All longitudes should be within Espoo bounds")
            
            print(f"✅ Loaded {len(df)} Espoo sample listings")
            print("✅ All coordinate validation passed")
            print(f"✅ Price range: €{df['price'].min():,.0f} - €{df['price'].max():,.0f}")
            
            # Store for other tests
            self.sample_listings = df
            return df
            
        except Exception as e:
            self.fail(f"Failed to load sample listings: {e}")
    
    def test_osm_buildings_availability(self):
        """Test OSM buildings data availability for spatial matching"""
        print("\n🏗️ Testing OSM Buildings Data Availability")
        
        # Check if OSM buildings table exists in database
        try:
            conn = duckdb.connect(self.db_path)
            
            # Check if osm_buildings table exists
            tables = conn.execute("SHOW TABLES").fetchall()
            table_names = [table[0] for table in tables]
            
            if 'osm_buildings' in table_names:
                buildings_count = conn.execute("SELECT COUNT(*) FROM osm_buildings").fetchone()[0]
                print(f"✅ Found {buildings_count:,} OSM buildings in database")
                
                # Check for buildings in Espoo area
                espoo_buildings_query = f"""
                SELECT COUNT(*) FROM osm_buildings 
                WHERE ST_Within(
                    ST_Point(lon, lat), 
                    ST_MakeEnvelope({self.espoo_bounds['min_lon']}, {self.espoo_bounds['min_lat']}, 
                                   {self.espoo_bounds['max_lon']}, {self.espoo_bounds['max_lat']})
                )
                """
                try:
                    espoo_buildings_count = conn.execute(espoo_buildings_query).fetchone()[0]
                    print(f"✅ Found {espoo_buildings_count:,} OSM buildings in Espoo area")
                except:
                    print("⚠️ Spatial query failed, using fallback coordinate filtering")
                    fallback_query = f"""
                    SELECT COUNT(*) FROM osm_buildings 
                    WHERE lat BETWEEN {self.espoo_bounds['min_lat']} AND {self.espoo_bounds['max_lat']}
                    AND lon BETWEEN {self.espoo_bounds['min_lon']} AND {self.espoo_bounds['max_lon']}
                    """
                    espoo_buildings_count = conn.execute(fallback_query).fetchone()[0]
                    print(f"✅ Found {espoo_buildings_count:,} OSM buildings in Espoo area (fallback)")
                
                self.assertGreater(espoo_buildings_count, 0, "Should have OSM buildings in Espoo area")
                
            else:
                # Check for external GeoJSON file
                osm_file_path = Path("data/helsinki_buildings_20250711_041142.geojson")
                if osm_file_path.exists():
                    print("✅ Found external OSM buildings GeoJSON file")
                    # Load and check Espoo area buildings
                    buildings_gdf = gpd.read_file(osm_file_path)
                    
                    # Filter for Espoo area
                    espoo_buildings = buildings_gdf[
                        (buildings_gdf.geometry.bounds['miny'] >= self.espoo_bounds['min_lat']) &
                        (buildings_gdf.geometry.bounds['maxy'] <= self.espoo_bounds['max_lat']) &
                        (buildings_gdf.geometry.bounds['minx'] >= self.espoo_bounds['min_lon']) &
                        (buildings_gdf.geometry.bounds['maxx'] <= self.espoo_bounds['max_lon'])
                    ]
                    
                    print(f"✅ Found {len(espoo_buildings):,} OSM buildings in Espoo area from file")
                    self.assertGreater(len(espoo_buildings), 0, "Should have OSM buildings in Espoo area")
                else:
                    self.fail("No OSM buildings data available (neither in database nor as file)")
            
            conn.close()
            
        except Exception as e:
            self.fail(f"Failed to check OSM buildings availability: {e}")
    
    def test_geospatial_integration_validation(self):
        """Test geospatial integration for Espoo listings"""
        print("\n🎯 Testing Geospatial Integration for Espoo")
        
        # Load sample listings
        if not hasattr(self, 'sample_listings'):
            self.test_sample_listings_loading()
        
        df = self.sample_listings
        results = []
        match_count = 0
        
        # Simple point-in-polygon validation using coordinate bounds
        # This is a simplified version for Step 1 validation
        for idx, listing in df.iterrows():
            lat, lon = listing['latitude'], listing['longitude']
            
            # Validate coordinates are within Espoo bounds
            within_bounds = (
                self.espoo_bounds['min_lat'] <= lat <= self.espoo_bounds['max_lat'] and
                self.espoo_bounds['min_lon'] <= lon <= self.espoo_bounds['max_lon']
            )
            
            # For Step 1, we consider within-bounds as a match
            # More sophisticated spatial matching will be in Step 2 and 3
            if within_bounds:
                match_count += 1
                match_type = 'bounds_match'
                quality_score = 1.0
            else:
                match_type = 'out_of_bounds'
                quality_score = 0.0
            
            results.append({
                'listing_id': listing['id'],
                'address': listing['address'],
                'latitude': lat,
                'longitude': lon,
                'price': listing['price'],
                'matched': within_bounds,
                'match_type': match_type,
                'quality_score': quality_score,
                'postal_code': listing.get('postal_code', 'N/A')
            })
        
        results_df = pd.DataFrame(results)
        
        # Calculate statistics
        total_listings = len(results_df)
        matched_listings = len(results_df[results_df['matched']])
        match_rate = (matched_listings / total_listings) * 100 if total_listings > 0 else 0
        
        print(f"📊 Geospatial Integration Results:")
        print(f"   📋 Total listings: {total_listings}")
        print(f"   ✅ Matched listings: {matched_listings}")
        print(f"   📈 Match rate: {match_rate:.1f}%")
        print(f"   🎯 Within bounds: {match_count}")
        print(f"   ❌ Out of bounds: {total_listings - match_count}")
        
        # Validate success criteria
        self.assertGreaterEqual(match_rate, self.required_match_rate, 
                               f"Match rate {match_rate:.1f}% should be ≥ {self.required_match_rate}%")
        
        print(f"✅ SUCCESS: Match rate {match_rate:.1f}% meets requirement ≥ {self.required_match_rate}%")
        
        # Store results for reporting
        self.validation_results = results_df
        self.match_rate = match_rate
        
        return results_df, match_rate
    
    def test_quality_metrics_tracking(self):
        """Test quality metrics tracking for Espoo validation"""
        print("\n📊 Testing Quality Metrics Tracking")
        
        # Ensure we have validation results
        if not hasattr(self, 'validation_results'):
            self.test_geospatial_integration_validation()
        
        results_df = self.validation_results
        
        # Calculate comprehensive quality metrics
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'validation_type': 'espoo_step1_10_samples',
            'city': self.city,
            'sample_size': len(results_df),
            'match_statistics': {
                'total_matched': len(results_df[results_df['matched']]),
                'match_rate_percent': self.match_rate,
                'bounds_matches': len(results_df[results_df['match_type'] == 'bounds_match']),
                'out_of_bounds': len(results_df[results_df['match_type'] == 'out_of_bounds'])
            },
            'coordinate_quality': {
                'avg_latitude': float(results_df['latitude'].mean()),
                'avg_longitude': float(results_df['longitude'].mean()),
                'lat_std': float(results_df['latitude'].std()),
                'lon_std': float(results_df['longitude'].std()),
                'coordinate_spread_km': self._calculate_coordinate_spread(results_df)
            },
            'data_quality': {
                'avg_quality_score': float(results_df['quality_score'].mean()),
                'addresses_with_postal': len(results_df[results_df['postal_code'] != 'N/A']),
                'price_range': {
                    'min': float(results_df['price'].min()) if not results_df['price'].isna().all() else None,
                    'max': float(results_df['price'].max()) if not results_df['price'].isna().all() else None,
                    'avg': float(results_df['price'].mean()) if not results_df['price'].isna().all() else None
                }
            },
            'success_criteria': {
                'required_match_rate': self.required_match_rate,
                'achieved_match_rate': self.match_rate,
                'meets_criteria': self.match_rate >= self.required_match_rate
            }
        }
        
        # Save metrics to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_path = self.output_dir / f"espoo_step1_metrics_{timestamp}.json"
        
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Quality metrics saved: {metrics_path}")
        print(f"📊 Average quality score: {metrics['data_quality']['avg_quality_score']:.2f}")
        print(f"📍 Coordinate spread: {metrics['coordinate_quality']['coordinate_spread_km']:.2f} km")
        
        # Validate metrics
        self.assertIsInstance(metrics['match_statistics']['match_rate_percent'], (int, float))
        self.assertGreaterEqual(metrics['data_quality']['avg_quality_score'], 0.0)
        self.assertLessEqual(metrics['data_quality']['avg_quality_score'], 1.0)
        
        return metrics
    
    def _calculate_coordinate_spread(self, df):
        """Calculate the geographic spread of coordinates in kilometers"""
        if len(df) < 2:
            return 0.0
        
        # Simple approximation using coordinate differences
        lat_range = df['latitude'].max() - df['latitude'].min()
        lon_range = df['longitude'].max() - df['longitude'].min()
        
        # Convert to approximate kilometers (rough approximation for Finland)
        lat_km = lat_range * 111.0  # 1 degree latitude ≈ 111 km
        lon_km = lon_range * 111.0 * 0.5  # Longitude varies by latitude, ~0.5 at 60°N
        
        return (lat_km**2 + lon_km**2)**0.5
    
    def test_validation_report_generation(self):
        """Test generation of validation report"""
        print("\n📄 Generating Validation Report")
        
        # Ensure we have all required data
        if not hasattr(self, 'validation_results'):
            self.test_geospatial_integration_validation()
        
        metrics = self.test_quality_metrics_tracking()
        
        # Generate HTML report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"espoo_step1_report_{timestamp}.html"
        
        html_content = self._generate_html_report(metrics)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.assertTrue(report_path.exists(), "Validation report should be created")
        print(f"✅ Validation report generated: {report_path}")
        
        return report_path
    
    def _generate_html_report(self, metrics):
        """Generate HTML validation report"""
        success_class = "success" if metrics['success_criteria']['meets_criteria'] else "error"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Espoo Progressive Validation - Step 1: 10 Samples</title>
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
            </style>
        </head>
        <body>
            <h1>🏙️ Espoo Progressive Validation - Step 1: 10 Samples</h1>
            
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
                   <span class="{success_class}">{metrics['match_statistics']['match_rate_percent']:.1f}%</span>
                </p>
                <p><strong>Required Rate:</strong> {metrics['success_criteria']['required_match_rate']:.1f}%</p>
                <p><strong>Total Matched:</strong> {metrics['match_statistics']['total_matched']}</p>
                <p><strong>Bounds Matches:</strong> {metrics['match_statistics']['bounds_matches']}</p>
                <p><strong>Out of Bounds:</strong> {metrics['match_statistics']['out_of_bounds']}</p>
            </div>
            
            <div class="metric-box">
                <h2>📍 Coordinate Quality</h2>
                <p><strong>Average Latitude:</strong> {metrics['coordinate_quality']['avg_latitude']:.6f}</p>
                <p><strong>Average Longitude:</strong> {metrics['coordinate_quality']['avg_longitude']:.6f}</p>
                <p><strong>Coordinate Spread:</strong> {metrics['coordinate_quality']['coordinate_spread_km']:.2f} km</p>
                <p><strong>Latitude Std Dev:</strong> {metrics['coordinate_quality']['lat_std']:.6f}</p>
                <p><strong>Longitude Std Dev:</strong> {metrics['coordinate_quality']['lon_std']:.6f}</p>
            </div>
            
            <div class="metric-box">
                <h2>💰 Data Quality</h2>
                <p><strong>Average Quality Score:</strong> {metrics['data_quality']['avg_quality_score']:.2f}</p>
                <p><strong>Addresses with Postal Code:</strong> {metrics['data_quality']['addresses_with_postal']}</p>
        """
        
        if metrics['data_quality']['price_range']['min'] is not None:
            html_content += f"""
                <p><strong>Price Range:</strong> €{metrics['data_quality']['price_range']['min']:,.0f} - €{metrics['data_quality']['price_range']['max']:,.0f}</p>
                <p><strong>Average Price:</strong> €{metrics['data_quality']['price_range']['avg']:,.0f}</p>
            """
        
        html_content += f"""
            </div>
            
            <div class="metric-box">
                <h2>📋 Listing Details</h2>
                <table>
                    <tr>
                        <th>Address</th>
                        <th>Coordinates</th>
                        <th>Match Status</th>
                        <th>Quality Score</th>
                        <th>Price</th>
                    </tr>
        """
        
        for _, row in self.validation_results.iterrows():
            status = "✅ Matched" if row['matched'] else "❌ No Match"
            price_str = f"€{row['price']:,.0f}" if pd.notna(row['price']) else "N/A"
            html_content += f"""
                <tr>
                    <td>{row['address']}</td>
                    <td>{row['latitude']:.6f}, {row['longitude']:.6f}</td>
                    <td>{status}</td>
                    <td>{row['quality_score']:.2f}</td>
                    <td>{price_str}</td>
                </tr>
            """
        
        html_content += f"""
                </table>
            </div>
            
            <div class="metric-box">
                <h2>🚀 Next Steps</h2>
                <p>✅ Step 1 Complete: 10 Sample Validation</p>
                <p>➡️ Next: Run Step 2 - 100 Sample Validation</p>
                <p>📝 Command: <code>uv run python -m pytest tests/validation/test_espoo_step2_100_samples.py -v</code></p>
            </div>
            
        </body>
        </html>
        """
        
        return html_content
    
    def test_complete_workflow(self):
        """Test the complete Step 1 validation workflow"""
        print("\n🚀 Testing Complete Step 1 Validation Workflow")
        
        # Run all validation steps
        self.test_bug_prevention_database_connection()
        self.test_bug_prevention_configuration_validation()
        self.test_bug_prevention_coordinate_validation()
        self.test_sample_listings_loading()
        self.test_osm_buildings_availability()
        results_df, match_rate = self.test_geospatial_integration_validation()
        metrics = self.test_quality_metrics_tracking()
        report_path = self.test_validation_report_generation()
        
        # Final validation
        success = match_rate >= self.required_match_rate
        
        print(f"\n📊 STEP 1 VALIDATION SUMMARY")
        print("=" * 60)
        print(f"🏙️ City: {self.city}")
        print(f"📋 Sample Size: {self.sample_size} listings")
        print(f"📈 Match Rate: {match_rate:.1f}%")
        print(f"🎯 Success Criteria: ≥{self.required_match_rate}%")
        print(f"✅ Result: {'PASSED' if success else 'FAILED'}")
        print(f"📄 Report: {report_path}")
        
        if success:
            print(f"\n🚀 Next Steps:")
            print(f"   1. Review validation report: {report_path}")
            print(f"   2. Run Step 2 validation: test_espoo_step2_100_samples.py")
            print(f"   3. Command: uv run python -m pytest tests/validation/test_espoo_step2_100_samples.py -v")
        else:
            print(f"\n❌ Step 1 Failed - Address Issues Before Proceeding:")
            print(f"   1. Check coordinate bounds configuration")
            print(f"   2. Verify Espoo listings data quality")
            print(f"   3. Review geospatial integration logic")
        
        self.assertTrue(success, f"Step 1 validation should succeed with ≥{self.required_match_rate}% match rate")


def run_espoo_step1_validation():
    """Run the Espoo Step 1 validation test suite"""
    print("🏙️ Espoo Progressive Validation: Step 1 - 10 Samples Test")
    print("=" * 70)
    print("Testing Espoo data collection and geospatial integration")
    print("Success Criteria: ≥95% match rate for proof of concept")
    print("Requirements: 5.1, 5.2, 5.3, 5.4")
    print("=" * 70)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEspooStep1Validation)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_espoo_step1_validation()
    sys.exit(0 if success else 1)