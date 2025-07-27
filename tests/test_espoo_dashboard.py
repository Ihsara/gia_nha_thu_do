#!/usr/bin/env python3
"""
Unit tests for Espoo dashboard functionality
"""

import unittest
from pathlib import Path
import os
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from oikotie.visualization.dashboard.espoo_dashboard import EspooDashboard
from oikotie.visualization.dashboard.multi_city import MultiCityDashboard
from oikotie.visualization.dashboard.city_selector import CitySelector
from oikotie.visualization.utils.config import get_city_config


class TestEspooDashboard(unittest.TestCase):
    """Test cases for Espoo dashboard functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Use a temporary output directory for tests
        self.test_output_dir = Path("output/test_espoo_dashboard")
        self.test_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize dashboard with test output directory
        self.espoo_dashboard = EspooDashboard(output_dir=self.test_output_dir)
        self.multi_city_dashboard = MultiCityDashboard(output_dir=self.test_output_dir)
        self.city_selector = CitySelector(output_dir=self.test_output_dir)
    
    def test_espoo_config(self):
        """Test Espoo city configuration"""
        espoo_config = get_city_config('espoo')
        
        # Verify Espoo configuration
        self.assertEqual(espoo_config.name, 'Espoo')
        self.assertIsNotNone(espoo_config.center_lat)
        self.assertIsNotNone(espoo_config.center_lon)
        self.assertIsNotNone(espoo_config.bbox)
        
        # Verify Espoo bounding box
        min_lon, min_lat, max_lon, max_lat = espoo_config.bbox
        self.assertLess(min_lon, max_lon)
        self.assertLess(min_lat, max_lat)
        
        # Verify Espoo database filter
        self.assertIn('Espoo', espoo_config.database_filter)
    
    def test_load_espoo_data(self):
        """Test loading Espoo data"""
        # Load a small sample of Espoo data
        espoo_data = self.espoo_dashboard.load_city_data('Espoo', sample_size=5)
        
        # Verify data was loaded
        self.assertFalse(espoo_data.empty)
        
        # Verify city is correct
        self.assertTrue(all(city == 'Espoo' for city in espoo_data['city']))
        
        # Verify required columns exist
        required_columns = ['id', 'address', 'latitude', 'longitude', 'price', 'size_m2']
        for column in required_columns:
            self.assertIn(column, espoo_data.columns)
    
    def test_load_espoo_buildings(self):
        """Test loading Espoo building footprints"""
        # Get Espoo city configuration
        espoo_config = get_city_config('espoo')
        
        # Load Espoo building footprints
        buildings_gdf = self.espoo_dashboard.load_building_footprints('Espoo', espoo_config.bbox)
        
        # Verify buildings were loaded
        self.assertFalse(buildings_gdf.empty)
        
        # Verify geometry column exists
        self.assertIn('geometry', buildings_gdf.columns)
    
    def test_create_espoo_dashboard(self):
        """Test creating Espoo dashboard"""
        # Create Espoo dashboard with minimal sample size
        dashboard_path = self.espoo_dashboard.create_espoo_dashboard(sample_size=3)
        
        # Verify dashboard was created
        self.assertIsNotNone(dashboard_path)
        self.assertTrue(Path(dashboard_path).exists())
        
        # Verify dashboard is HTML
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('<!DOCTYPE html>', content)
            self.assertIn('Espoo Enhanced Dashboard', content)
    
    def test_create_comparative_dashboard(self):
        """Test creating comparative dashboard with Espoo"""
        # Create comparative dashboard with minimal sample size
        dashboard_path = self.multi_city_dashboard.create_comparative_dashboard(['Helsinki', 'Espoo'], sample_size=3)
        
        # Verify dashboard was created
        self.assertIsNotNone(dashboard_path)
        self.assertTrue(Path(dashboard_path).exists())
        
        # Verify dashboard is HTML
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('<!DOCTYPE html>', content)
            self.assertIn('Comparative Dashboard', content)
    
    def test_city_selector(self):
        """Test city selector with Espoo"""
        # Create city selector
        selector_path = self.city_selector.create_dashboard_index()
        
        # Verify selector was created
        self.assertIsNotNone(selector_path)
        self.assertTrue(Path(selector_path).exists())
        
        # Verify selector is HTML
        with open(selector_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('<!DOCTYPE html>', content)
            self.assertIn('Multi-City Dashboard', content)
            self.assertIn('Espoo', content)
    
    def tearDown(self):
        """Clean up test environment"""
        # Remove test output directory
        import shutil
        if self.test_output_dir.exists():
            shutil.rmtree(self.test_output_dir)


if __name__ == '__main__':
    unittest.main()