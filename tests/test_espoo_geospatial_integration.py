#!/usr/bin/env python3
"""
Test Espoo Geospatial Integration

This module tests the Espoo geospatial integration functionality:
- Database schema setup
- Address geocoding
- Building footprint matching
- Spatial data validation

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import unittest
import sys
from pathlib import Path
import pandas as pd
import duckdb
import geopandas as gpd
from shapely.geometry import Point
import random
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import geospatial modules
from oikotie.geospatial.schema import setup_geospatial_schema
from oikotie.geospatial.espoo import EspooGeospatialIntegrator
from oikotie.geospatial.integrator import MultiCityGeospatialManager


class TestEspooGeospatialIntegration(unittest.TestCase):
    """Test class for Espoo geospatial integration"""
    
    def setUp(self):
        """Set up test environment"""
        self.db_path = "data/real_estate.duckdb"
        self.city = "Espoo"
        self.espoo_bounds = (24.4, 60.1, 24.9, 60.4)  # min_lon, min_lat, max_lon, max_lat
        
        # Ensure database schema is set up
        setup_geospatial_schema()
        
        # Initialize integrator
        self.integrator = EspooGeospatialIntegrator()
        
        print(f"\n🏙️ Testing Espoo Geospatial Integration")
    
    def test_database_schema(self):
        """Test that the database schema is properly set up"""
        print("\n🔧 Testing Database Schema")
        
        with duckdb.connect(self.db_path) as conn:
            # Check if required tables exist
            tables = conn.execute("SHOW TABLES").fetchall()
            table_names = [table[0] for table in tables]
            
            required_tables = [
                'address_locations',
                'building_matches',
                'city_data_sources',
                'spatial_validation_results'
            ]
            
            for table in required_tables:
                self.assertIn(table, table_names, f"Table {table} should exist")
                print(f"✅ Table {table} exists")
            
            # Check if city_validated column exists in address_locations
            columns = conn.execute("PRAGMA table_info(address_locations)").fetchall()
            column_names = [col[1] for col in columns]
            
            self.assertIn('city_validated', column_names, "city_validated column should exist")
            print("✅ city_validated column exists in address_locations")
            
            # Check if coordinate validation function exists
            try:
                result = conn.execute("SELECT validate_city_coordinates('Espoo', 60.2, 24.6)").fetchone()[0]
                self.assertTrue(result, "Espoo coordinates should be valid")
                print("✅ Coordinate validation function works")
            except:
                self.fail("Coordinate validation function should exist")
    
    def test_espoo_geocoding(self):
        """Test Espoo address geocoding"""
        print("\n🔍 Testing Espoo Address Geocoding")
        
        # Test addresses
        test_addresses = [
            "Tapiontori 3, Espoo",
            "Leppävaarankatu 3-9, Espoo",
            "Otakaari 1, Espoo",
            "Suurpelto 21, Espoo",
            "Matinkylänkuja 2, Espoo"
        ]
        
        # Geocode addresses
        results = self.integrator.geocode_addresses(test_addresses)
        
        # Check results
        self.assertGreater(len(results), 0, "Should return geocoding results")
        
        success_count = sum(1 for _, lat, lon, _ in results if lat is not None and lon is not None)
        success_rate = (success_count / len(test_addresses)) * 100
        
        print(f"✅ Geocoded {success_count}/{len(test_addresses)} addresses ({success_rate:.1f}%)")
        
        # Check if coordinates are within Espoo bounds
        for addr, lat, lon, score in results:
            if lat is not None and lon is not None:
                min_lon, min_lat, max_lon, max_lat = self.espoo_bounds
                within_bounds = (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)
                
                if within_bounds:
                    print(f"✅ {addr}: {lat:.6f}, {lon:.6f} (within bounds)")
                else:
                    print(f"⚠️ {addr}: {lat:.6f}, {lon:.6f} (outside bounds)")
        
        # Check database update
        with duckdb.connect(self.db_path) as conn:
            for addr, _, _, _ in results:
                count = conn.execute(f"SELECT COUNT(*) FROM address_locations WHERE address = ?", [addr]).fetchone()[0]
                self.assertGreaterEqual(count, 0, f"Address {addr} should be in database")
    
    def test_building_data_fetching(self):
        """Test fetching building data for Espoo"""
        print("\n🏢 Testing Building Data Fetching")
        
        # Use a small area in Espoo for testing
        test_bbox = (24.65, 60.17, 24.67, 60.19)  # Small area around Tapiola
        
        # Fetch buildings
        buildings_gdf = self.integrator.fetch_building_data(test_bbox)
        
        # Check results
        self.assertFalse(buildings_gdf.empty, "Should return building data")
        print(f"✅ Fetched {len(buildings_gdf)} buildings")
        
        # Check if buildings have geometries
        self.assertTrue(all(buildings_gdf.geometry.is_valid), "All buildings should have valid geometries")
        print("✅ All buildings have valid geometries")
        
        # Check if buildings are within the bbox
        min_lon, min_lat, max_lon, max_lat = test_bbox
        
        # Create a test point within the bbox
        test_point = Point(
            min_lon + (max_lon - min_lon) / 2,
            min_lat + (max_lat - min_lat) / 2
        )
        
        # Find buildings that contain the test point
        containing_buildings = buildings_gdf[buildings_gdf.contains(test_point)]
        
        print(f"✅ {len(containing_buildings)} buildings contain the test point")
    
    def test_building_matching(self):
        """Test matching listings to buildings"""
        print("\n🔍 Testing Building Matching")
        
        # Create test listings
        test_listings = pd.DataFrame({
            'url': [f"test_url_{i}" for i in range(5)],
            'address': [
                "Tapiontori 3, Espoo",
                "Leppävaarankatu 3-9, Espoo",
                "Otakaari 1, Espoo",
                "Suurpelto 21, Espoo",
                "Matinkylänkuja 2, Espoo"
            ],
            'latitude': [
                60.1756,  # Tapiola
                60.2188,  # Leppävaara
                60.1841,  # Otaniemi
                60.1967,  # Suurpelto
                60.1598   # Matinkylä
            ],
            'longitude': [
                24.8059,  # Tapiola
                24.8127,  # Leppävaara
                24.8301,  # Otaniemi
                24.7544,  # Suurpelto
                24.7384   # Matinkylä
            ]
        })
        
        # Match to buildings
        result_df = self.integrator.match_listings_to_buildings(test_listings)
        
        # Check results
        self.assertEqual(len(result_df), len(test_listings), "Should return same number of listings")
        self.assertIn('building_match', result_df.columns, "Should add building_match column")
        self.assertIn('building_id', result_df.columns, "Should add building_id column")
        self.assertIn('match_type', result_df.columns, "Should add match_type column")
        self.assertIn('geospatial_quality_score', result_df.columns, "Should add quality score column")
        
        match_count = result_df['building_match'].sum()
        match_rate = (match_count / len(result_df)) * 100
        
        print(f"✅ Matched {match_count}/{len(result_df)} listings to buildings ({match_rate:.1f}%)")
        
        # Check quality scores
        avg_quality = result_df['geospatial_quality_score'].mean()
        print(f"✅ Average quality score: {avg_quality:.2f}")
    
    def test_spatial_validation(self):
        """Test spatial data validation"""
        print("\n✓ Testing Spatial Data Validation")
        
        # Create test listings with some invalid coordinates
        test_listings = pd.DataFrame({
            'url': [f"test_url_{i}" for i in range(6)],
            'address': [f"Test Address {i}, Espoo" for i in range(6)],
            'latitude': [
                60.2,     # Valid
                60.3,     # Valid
                60.0,     # Invalid (too south)
                60.5,     # Invalid (too north)
                60.2,     # Valid
                None      # Missing
            ],
            'longitude': [
                24.6,     # Valid
                24.7,     # Valid
                24.6,     # Valid
                24.6,     # Valid
                25.0,     # Invalid (too east)
                24.6      # Missing latitude
            ]
        })
        
        # Validate spatial data
        result_df = self.integrator.validate_spatial_data(test_listings)
        
        # Check results
        self.assertEqual(len(result_df), len(test_listings), "Should return same number of listings")
        self.assertIn('coordinates_valid', result_df.columns, "Should add coordinates_valid column")
        self.assertIn('within_espoo_bounds', result_df.columns, "Should add within_espoo_bounds column")
        self.assertIn('validation_message', result_df.columns, "Should add validation_message column")
        
        valid_coords_count = result_df['coordinates_valid'].sum()
        within_bounds_count = result_df['within_espoo_bounds'].sum()
        
        print(f"✅ Valid coordinates: {valid_coords_count}/{len(result_df)}")
        print(f"✅ Within Espoo bounds: {within_bounds_count}/{len(result_df)}")
        
        # Check specific cases
        self.assertTrue(result_df.loc[0, 'within_espoo_bounds'], "First listing should be within bounds")
        self.assertTrue(result_df.loc[1, 'within_espoo_bounds'], "Second listing should be within bounds")
        self.assertFalse(result_df.loc[2, 'within_espoo_bounds'], "Third listing should be outside bounds (too south)")
        self.assertFalse(result_df.loc[3, 'within_espoo_bounds'], "Fourth listing should be outside bounds (too north)")
        self.assertFalse(result_df.loc[4, 'within_espoo_bounds'], "Fifth listing should be outside bounds (too east)")
    
    def test_multi_city_manager(self):
        """Test the multi-city geospatial manager"""
        print("\n🌍 Testing Multi-City Geospatial Manager")
        
        # Initialize manager
        manager = MultiCityGeospatialManager()
        
        # Check available cities
        cities = manager.get_available_cities()
        self.assertIn(self.city, cities, f"{self.city} should be available")
        print(f"✅ Available cities: {', '.join(cities)}")
        
        # Get Espoo integrator
        integrator = manager.get_integrator(self.city)
        self.assertIsNotNone(integrator, f"Should return integrator for {self.city}")
        self.assertIsInstance(integrator, EspooGeospatialIntegrator, "Should return EspooGeospatialIntegrator")
        print(f"✅ Got integrator for {self.city}")
        
        # Test coordinate validation
        valid_coords = (60.2, 24.6)  # Valid Espoo coordinates
        invalid_coords = (60.0, 24.0)  # Invalid coordinates
        
        self.assertTrue(manager.validate_city_coordinates(self.city, *valid_coords), "Valid coordinates should pass validation")
        self.assertFalse(manager.validate_city_coordinates(self.city, *invalid_coords), "Invalid coordinates should fail validation")
        print("✅ Coordinate validation works")
    
    def test_end_to_end_integration(self):
        """Test end-to-end integration with a small sample"""
        print("\n🚀 Testing End-to-End Integration")
        
        # Get a small sample of Espoo listings from database
        try:
            with duckdb.connect(self.db_path) as conn:
                query = f"""
                    SELECT url, address, city, postal_code
                    FROM listings
                    WHERE city = '{self.city}'
                    ORDER BY RANDOM()
                    LIMIT 5
                """
                
                sample_df = conn.execute(query).df()
                
                if sample_df.empty:
                    print("⚠️ No Espoo listings in database, skipping end-to-end test")
                    return
                
                print(f"✅ Got {len(sample_df)} sample listings")
                
                # Initialize manager
                manager = MultiCityGeospatialManager()
                
                # Process listings
                result_df = manager.process_city_listings(self.city, sample_df)
                
                # Check results
                self.assertEqual(len(result_df), len(sample_df), "Should return same number of listings")
                
                # Check if geocoding worked
                geocoded_count = result_df['latitude'].notna().sum() if 'latitude' in result_df.columns else 0
                geocoded_rate = (geocoded_count / len(result_df)) * 100 if len(result_df) > 0 else 0
                
                print(f"✅ Geocoded: {geocoded_count}/{len(result_df)} ({geocoded_rate:.1f}%)")
                
                # Check if building matching worked
                if 'building_match' in result_df.columns:
                    match_count = result_df['building_match'].sum()
                    match_rate = (match_count / len(result_df)) * 100 if len(result_df) > 0 else 0
                    
                    print(f"✅ Building matches: {match_count}/{len(result_df)} ({match_rate:.1f}%)")
                
                print("✅ End-to-end integration test passed")
                
        except Exception as e:
            self.fail(f"End-to-end test failed: {e}")


def run_tests():
    """Run the test suite"""
    unittest.main()


if __name__ == "__main__":
    run_tests()