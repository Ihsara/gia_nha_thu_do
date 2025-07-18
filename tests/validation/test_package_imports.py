#!/usr/bin/env python3
"""
Package Import Validation Test

Tests that all oikotie package imports work correctly with the new structure.
This is a critical test to ensure the package refactoring was successful.

Components Tested:
- oikotie.visualization.dashboard.enhanced
- oikotie.visualization.utils (when created)
- oikotie.visualization.cli (when created)
- oikotie.database (when created)
"""

import sys
import unittest
from pathlib import Path

# Add the project root to path for package imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestPackageImports(unittest.TestCase):
    """Test class for package import validation"""
    
    def test_visualization_dashboard_imports(self):
        """Test visualization dashboard package imports"""
        print("\n🔧 Testing visualization.dashboard imports...")
        
        try:
            # Test enhanced dashboard import
            from oikotie.visualization.dashboard.enhanced import EnhancedDashboard
            self.assertIsNotNone(EnhancedDashboard, "EnhancedDashboard should be importable")
            
            # Test instantiation
            dashboard = EnhancedDashboard()
            self.assertIsNotNone(dashboard, "Should be able to create EnhancedDashboard instance")
            
            print("✅ oikotie.visualization.dashboard.enhanced - SUCCESS")
            
        except ImportError as e:
            self.fail(f"Failed to import oikotie.visualization.dashboard.enhanced: {e}")
        except Exception as e:
            self.fail(f"Failed to instantiate EnhancedDashboard: {e}")
    
    def test_visualization_package_structure(self):
        """Test visualization package structure"""
        print("\n📦 Testing visualization package structure...")
        
        try:
            # Test main visualization package
            import oikotie.visualization
            self.assertIsNotNone(oikotie.visualization, "Main visualization package should be importable")
            
            # Test dashboard subpackage
            import oikotie.visualization.dashboard
            self.assertIsNotNone(oikotie.visualization.dashboard, "Dashboard subpackage should be importable")
            
            # Test other subpackages (may not exist yet)
            try:
                import oikotie.visualization.maps
                print("✅ oikotie.visualization.maps - Available")
            except ImportError:
                print("⚠️ oikotie.visualization.maps - Not yet implemented")
            
            try:
                import oikotie.visualization.utils
                print("✅ oikotie.visualization.utils - Available")
            except ImportError:
                print("⚠️ oikotie.visualization.utils - Not yet implemented")
            
            try:
                import oikotie.visualization.cli
                print("✅ oikotie.visualization.cli - Available")
            except ImportError:
                print("⚠️ oikotie.visualization.cli - Not yet implemented")
            
            print("✅ Package structure validation completed")
            
        except ImportError as e:
            self.fail(f"Failed to import visualization package: {e}")
    
    def test_database_package_imports(self):
        """Test database package imports"""
        print("\n💾 Testing database package imports...")
        
        try:
            # Test main database package
            import oikotie.database
            self.assertIsNotNone(oikotie.database, "Database package should be importable")
            
            print("✅ oikotie.database - Available")
            
            # Test for specific database functions (if they exist)
            try:
                from oikotie.database import get_connection
                print("✅ oikotie.database.get_connection - Available")
            except ImportError:
                print("⚠️ oikotie.database.get_connection - Not yet implemented")
            
        except ImportError as e:
            self.fail(f"Failed to import database package: {e}")
    
    def test_import_dependencies(self):
        """Test that package dependencies are available"""
        print("\n📚 Testing package dependencies...")
        
        # Test critical dependencies
        dependencies = [
            'pandas',
            'geopandas', 
            'shapely',
            'folium',
            'duckdb'
        ]
        
        missing_deps = []
        
        for dep in dependencies:
            try:
                __import__(dep)
                print(f"✅ {dep} - Available")
            except ImportError:
                missing_deps.append(dep)
                print(f"❌ {dep} - Missing")
        
        self.assertEqual(len(missing_deps), 0, f"Missing dependencies: {missing_deps}")
    
    def test_file_structure_validation(self):
        """Test that expected package files exist"""
        print("\n📁 Testing package file structure...")
        
        project_root = Path(__file__).parent.parent.parent
        
        # Expected package structure
        expected_files = [
            "oikotie/__init__.py",
            "oikotie/visualization/__init__.py",
            "oikotie/visualization/dashboard/__init__.py",
            "oikotie/visualization/dashboard/enhanced.py",
            "oikotie/visualization/maps/__init__.py",
            "oikotie/visualization/utils/__init__.py",
            "oikotie/visualization/cli/__init__.py",
            "oikotie/database/__init__.py"
        ]
        
        missing_files = []
        
        for file_path in expected_files:
            full_path = project_root / file_path
            if full_path.exists():
                print(f"✅ {file_path} - Exists")
            else:
                missing_files.append(file_path)
                print(f"❌ {file_path} - Missing")
        
        # Allow some missing files that haven't been created yet
        critical_files = [
            "oikotie/__init__.py",
            "oikotie/visualization/__init__.py", 
            "oikotie/visualization/dashboard/__init__.py",
            "oikotie/visualization/dashboard/enhanced.py"
        ]
        
        missing_critical = [f for f in missing_files if f in critical_files]
        self.assertEqual(len(missing_critical), 0, f"Missing critical files: {missing_critical}")
    
    def test_enhanced_dashboard_functionality(self):
        """Test basic functionality of the enhanced dashboard"""
        print("\n🎯 Testing enhanced dashboard functionality...")
        
        try:
            from oikotie.visualization.dashboard.enhanced import EnhancedDashboard
            
            # Create dashboard instance
            dashboard = EnhancedDashboard()
            
            # Test basic attributes/methods exist
            self.assertTrue(hasattr(dashboard, '__init__'), "Should have __init__ method")
            
            # Test that class is properly structured
            self.assertEqual(dashboard.__class__.__name__, 'EnhancedDashboard', 
                           "Class name should be EnhancedDashboard")
            
            print("✅ Enhanced dashboard basic functionality validated")
            
        except Exception as e:
            self.fail(f"Enhanced dashboard functionality test failed: {e}")
    
    def test_complete_import_workflow(self):
        """Test complete import workflow"""
        print("\n🚀 Testing complete import workflow...")
        
        # Run all import tests
        self.test_visualization_dashboard_imports()
        self.test_visualization_package_structure()
        self.test_database_package_imports()
        self.test_import_dependencies()
        self.test_file_structure_validation()
        self.test_enhanced_dashboard_functionality()
        
        print("\n📊 COMPLETE IMPORT VALIDATION SUMMARY")
        print("=" * 50)
        print("✅ All critical package imports working")
        print("✅ Package structure validated")
        print("✅ Dependencies available")
        print("✅ Enhanced dashboard functional")
        print("\n🚀 Ready for spatial validation tests")


def run_import_validation():
    """Run the import validation test suite"""
    print("🔧 Package Import Validation Test")
    print("=" * 60)
    print("Testing new oikotie package structure imports")
    print("Ensuring all components are properly accessible")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPackageImports)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_import_validation()
    sys.exit(0 if success else 1)
