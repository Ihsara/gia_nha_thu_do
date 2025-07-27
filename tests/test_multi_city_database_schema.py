"""
Comprehensive Database Schema Validation Tests for Multi-City Support

This module provides comprehensive testing for the enhanced database schema
that supports multi-city operations, coordinate validation, and data lineage tracking.
"""

import pytest
import duckdb
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

from oikotie.database.multi_city_migration import MultiCityMigrationManager
from oikotie.database.coordinate_validation import CoordinateValidator, ValidationStatus
from oikotie.database.schema import DatabaseSchema


class TestMultiCityDatabaseSchema:
    """Test suite for multi-city database schema enhancements"""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def migration_manager(self, temp_db_path):
        """Create migration manager with temporary database"""
        return MultiCityMigrationManager(temp_db_path)
    
    @pytest.fixture
    def coordinate_validator(self, temp_db_path):
        """Create coordinate validator with temporary database"""
        return CoordinateValidator(temp_db_path)
    
    @pytest.fixture
    def sample_listings_data(self):
        """Sample listings data for testing"""
        return [
            {
                'url': 'https://example.com/listing1',
                'city': 'Helsinki',
                'address': 'Mannerheimintie 1, Helsinki',
                'latitude': 60.1699,
                'longitude': 24.9384,
                'price_eur': 500000,
                'scraped_at': datetime.now()
            },
            {
                'url': 'https://example.com/listing2',
                'city': 'Espoo',
                'address': 'Keskustori 1, Espoo',
                'latitude': 60.2055,
                'longitude': 24.6559,
                'price_eur': 450000,
                'scraped_at': datetime.now()
            },
            {
                'url': 'https://example.com/listing3',
                'city': 'Helsinki',
                'address': 'Invalid coordinates',
                'latitude': 70.0,  # Outside Helsinki bounds
                'longitude': 30.0,  # Outside Helsinki bounds
                'price_eur': 300000,
                'scraped_at': datetime.now()
            }
        ]
    
    def test_migration_manager_initialization(self, migration_manager):
        """Test migration manager initialization"""
        assert migration_manager is not None
        assert len(migration_manager.city_bounds) == 2
        assert 'Helsinki' in migration_manager.city_bounds
        assert 'Espoo' in migration_manager.city_bounds
        assert len(migration_manager.multi_city_migrations) > 0
    
    def test_city_bounds_definition(self, migration_manager):
        """Test city bounds are correctly defined"""
        helsinki_bounds = migration_manager.city_bounds['Helsinki']
        assert helsinki_bounds.name == 'Helsinki'
        assert helsinki_bounds.min_lat == 60.0
        assert helsinki_bounds.max_lat == 60.5
        assert helsinki_bounds.min_lon == 24.5
        assert helsinki_bounds.max_lon == 25.5
        
        espoo_bounds = migration_manager.city_bounds['Espoo']
        assert espoo_bounds.name == 'Espoo'
        assert espoo_bounds.min_lat == 60.1
        assert espoo_bounds.max_lat == 60.4
        assert espoo_bounds.min_lon == 24.4
        assert espoo_bounds.max_lon == 24.9
    
    def test_coordinate_validation_valid_coordinates(self, coordinate_validator):
        """Test coordinate validation with valid coordinates"""
        # Valid Helsinki coordinates
        result = coordinate_validator.validate_coordinates('Helsinki', 60.1699, 24.9384)
        assert result.is_valid is True
        assert result.status == ValidationStatus.VALID
        assert result.error_message is None
        
        # Valid Espoo coordinates
        result = coordinate_validator.validate_coordinates('Espoo', 60.2055, 24.6559)
        assert result.is_valid is True
        assert result.status == ValidationStatus.VALID
        assert result.error_message is None
    
    def test_coordinate_validation_invalid_coordinates(self, coordinate_validator):
        """Test coordinate validation with invalid coordinates"""
        # Invalid Helsinki coordinates (outside bounds)
        result = coordinate_validator.validate_coordinates('Helsinki', 70.0, 30.0)
        assert result.is_valid is False
        assert result.status == ValidationStatus.INVALID
        assert 'outside Helsinki bounds' in result.error_message
        
        # Invalid Espoo coordinates (outside bounds)
        result = coordinate_validator.validate_coordinates('Espoo', 59.0, 23.0)
        assert result.is_valid is False
        assert result.status == ValidationStatus.INVALID
        assert 'outside Espoo bounds' in result.error_message
    
    def test_coordinate_validation_unsupported_city(self, coordinate_validator):
        """Test coordinate validation with unsupported city"""
        result = coordinate_validator.validate_coordinates('Tampere', 61.4978, 23.7610)
        assert result.is_valid is False
        assert result.status == ValidationStatus.ERROR
        assert 'Unsupported city' in result.error_message
    
    def test_coordinate_validation_invalid_values(self, coordinate_validator):
        """Test coordinate validation with invalid coordinate values"""
        # None values
        result = coordinate_validator.validate_coordinates('Helsinki', None, 24.9384)
        assert result.is_valid is False
        assert result.status == ValidationStatus.ERROR
        
        # Out of range latitude
        result = coordinate_validator.validate_coordinates('Helsinki', 91.0, 24.9384)
        assert result.is_valid is False
        assert result.status == ValidationStatus.ERROR
        assert 'Invalid latitude' in result.error_message
        
        # Out of range longitude
        result = coordinate_validator.validate_coordinates('Helsinki', 60.1699, 181.0)
        assert result.is_valid is False
        assert result.status == ValidationStatus.ERROR
        assert 'Invalid longitude' in result.error_message
    
    def test_database_schema_creation(self, temp_db_path):
        """Test database schema creation with multi-city enhancements"""
        # Create base schema
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        # Apply multi-city migrations
        migration_manager = MultiCityMigrationManager(temp_db_path)
        success = migration_manager.apply_multi_city_migrations()
        assert success is True
        
        # Verify tables exist
        with duckdb.connect(temp_db_path, read_only=True) as con:
            tables = con.execute("SHOW TABLES").fetchall()
            table_names = [table[0] for table in tables]
            
            # Check core tables
            assert 'listings' in table_names
            assert 'city_coordinate_bounds' in table_names
            assert 'city_data_sources' in table_names
            assert 'city_geocoding_results' in table_names
            assert 'city_api_usage' in table_names
    
    def test_listings_table_enhanced_columns(self, temp_db_path):
        """Test that listings table has enhanced multi-city columns"""
        # Create schema and apply migrations
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        # Check listings table schema
        with duckdb.connect(temp_db_path, read_only=True) as con:
            columns = con.execute("DESCRIBE listings").fetchall()
            column_names = [col[0] for col in columns]
            
            # Check for enhanced multi-city columns
            assert 'city_validated' in column_names
            assert 'coordinate_source' in column_names
            assert 'geospatial_quality_score' in column_names
            assert 'coordinate_validation_error' in column_names
            assert 'last_coordinate_validation' in column_names
    
    def test_city_coordinate_bounds_table(self, temp_db_path):
        """Test city coordinate bounds table creation and data"""
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        with duckdb.connect(temp_db_path, read_only=True) as con:
            # Check table exists and has data
            bounds = con.execute("SELECT * FROM city_coordinate_bounds ORDER BY city").fetchall()
            assert len(bounds) == 2
            
            # Check Espoo bounds
            espoo_bounds = [b for b in bounds if b[0] == 'Espoo'][0]
            assert espoo_bounds[1] == 60.1  # min_latitude
            assert espoo_bounds[2] == 60.4  # max_latitude
            assert espoo_bounds[3] == 24.4  # min_longitude
            assert espoo_bounds[4] == 24.9  # max_longitude
            
            # Check Helsinki bounds
            helsinki_bounds = [b for b in bounds if b[0] == 'Helsinki'][0]
            assert helsinki_bounds[1] == 60.0  # min_latitude
            assert helsinki_bounds[2] == 60.5  # max_latitude
            assert helsinki_bounds[3] == 24.5  # min_longitude
            assert helsinki_bounds[4] == 25.5  # max_longitude
    
    def test_spatial_indexes_creation(self, temp_db_path):
        """Test that spatial indexes are created for multi-city queries"""
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        with duckdb.connect(temp_db_path, read_only=True) as con:
            # Check that indexes exist (DuckDB specific query)
            try:
                # This is a basic check - DuckDB doesn't have a standard way to list indexes
                # We'll verify by running queries that would use the indexes
                con.execute("SELECT COUNT(*) FROM listings WHERE city = 'Helsinki'")
                con.execute("SELECT COUNT(*) FROM listings WHERE city_validated = TRUE")
                con.execute("SELECT COUNT(*) FROM listings WHERE geospatial_quality_score > 0.5")
                # If these queries run without error, the table structure is correct
                assert True
            except Exception as e:
                pytest.fail(f"Index-related query failed: {e}")
    
    def test_data_lineage_tables_creation(self, temp_db_path):
        """Test data lineage tables creation"""
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        with duckdb.connect(temp_db_path, read_only=True) as con:
            # Test city_data_sources table
            con.execute("SELECT COUNT(*) FROM city_data_sources")
            
            # Test city_geocoding_results table
            con.execute("SELECT COUNT(*) FROM city_geocoding_results")
            
            # Test city_api_usage table
            con.execute("SELECT COUNT(*) FROM city_api_usage")
            
            # Test that we can insert sample data
            con.execute("""
                INSERT INTO city_data_sources 
                (city, data_source_type, api_endpoint, records_count, data_quality_score)
                VALUES ('Helsinki', 'test_source', 'http://test.api', 100, 0.95)
            """)
            
            count = con.execute("SELECT COUNT(*) FROM city_data_sources").fetchone()[0]
            assert count == 1
    
    def test_validation_views_creation(self, temp_db_path):
        """Test that validation views are created correctly"""
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        with duckdb.connect(temp_db_path, read_only=True) as con:
            # Test city_validation_summary view
            try:
                con.execute("SELECT * FROM city_validation_summary")
                assert True
            except Exception as e:
                pytest.fail(f"city_validation_summary view not accessible: {e}")
            
            # Test invalid_coordinates view
            try:
                con.execute("SELECT * FROM invalid_coordinates")
                assert True
            except Exception as e:
                pytest.fail(f"invalid_coordinates view not accessible: {e}")
    
    def test_batch_coordinate_validation(self, temp_db_path, sample_listings_data):
        """Test batch coordinate validation functionality"""
        # Setup database
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        # Insert sample data
        with duckdb.connect(temp_db_path) as con:
            for listing in sample_listings_data:
                con.execute("""
                    INSERT INTO listings (url, city, address, latitude, longitude, price_eur, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    listing['url'], listing['city'], listing['address'],
                    listing['latitude'], listing['longitude'], listing['price_eur'],
                    listing['scraped_at']
                ])
        
        # Run coordinate validation
        coordinate_validator = CoordinateValidator(temp_db_path)
        stats = coordinate_validator.update_database_validation()
        
        # Verify results
        assert stats['total_processed'] == 3
        assert stats['valid_coordinates'] == 2  # Helsinki and Espoo valid coords
        assert stats['invalid_coordinates'] == 1  # Helsinki invalid coords
        
        # Check database state
        with duckdb.connect(temp_db_path, read_only=True) as con:
            validated_listings = con.execute("""
                SELECT url, city, city_validated, coordinate_validation_error
                FROM listings
                ORDER BY url
            """).fetchall()
            
            assert len(validated_listings) == 3
            
            # Check specific validations
            for url, city, validated, error in validated_listings:
                if 'listing1' in url:  # Valid Helsinki
                    assert validated is True
                    assert error is None
                elif 'listing2' in url:  # Valid Espoo
                    assert validated is True
                    assert error is None
                elif 'listing3' in url:  # Invalid Helsinki
                    assert validated is False
                    assert 'outside Helsinki bounds' in error
    
    def test_city_statistics_generation(self, temp_db_path, sample_listings_data):
        """Test city statistics generation"""
        # Setup database with sample data
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        # Insert sample data
        with duckdb.connect(temp_db_path) as con:
            for listing in sample_listings_data:
                con.execute("""
                    INSERT INTO listings (url, city, address, latitude, longitude, price_eur, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    listing['url'], listing['city'], listing['address'],
                    listing['latitude'], listing['longitude'], listing['price_eur'],
                    listing['scraped_at']
                ])
        
        # Run validation and get statistics
        coordinate_validator = CoordinateValidator(temp_db_path)
        coordinate_validator.update_database_validation()
        
        stats = migration_manager.get_city_statistics()
        
        # Verify statistics
        assert 'Helsinki' in stats
        assert 'Espoo' in stats
        
        helsinki_stats = stats['Helsinki']
        assert helsinki_stats['total_listings'] == 2
        assert helsinki_stats['validated_listings'] == 1  # One valid, one invalid
        assert helsinki_stats['validation_rate'] == 50.0
        
        espoo_stats = stats['Espoo']
        assert espoo_stats['total_listings'] == 1
        assert espoo_stats['validated_listings'] == 1
        assert espoo_stats['validation_rate'] == 100.0
    
    def test_migration_rollback(self, temp_db_path):
        """Test migration rollback functionality"""
        migration_manager = MultiCityMigrationManager(temp_db_path)
        
        # Apply migrations
        success = migration_manager.apply_multi_city_migrations()
        assert success is True
        
        # Verify tables exist
        with duckdb.connect(temp_db_path, read_only=True) as con:
            tables_before = con.execute("SHOW TABLES").fetchall()
            table_names_before = [table[0] for table in tables_before]
            assert 'city_coordinate_bounds' in table_names_before
        
        # Rollback specific migration
        city_bounds_migration = None
        for migration in migration_manager.multi_city_migrations:
            if 'coordinate_validation_function' in migration.version:
                city_bounds_migration = migration
                break
        
        if city_bounds_migration:
            success = migration_manager.rollback_migration(city_bounds_migration)
            assert success is True
    
    def test_data_source_entry_creation(self, temp_db_path):
        """Test city data source entry creation"""
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        # Create data source entries
        success1 = migration_manager.create_city_data_source_entry(
            city='Helsinki',
            source_type='osm_buildings',
            api_endpoint='https://overpass-api.de/api/interpreter',
            records_count=1500,
            quality_score=0.95
        )
        assert success1 is True
        
        success2 = migration_manager.create_city_data_source_entry(
            city='Espoo',
            source_type='municipal_data',
            api_endpoint='https://kartat.espoo.fi/api',
            records_count=800,
            quality_score=0.92
        )
        assert success2 is True
        
        # Verify entries
        with duckdb.connect(temp_db_path, read_only=True) as con:
            entries = con.execute("""
                SELECT city, data_source_type, records_count, data_quality_score
                FROM city_data_sources
                ORDER BY city
            """).fetchall()
            
            assert len(entries) == 2
            
            espoo_entry = entries[0]
            assert espoo_entry[0] == 'Espoo'
            assert espoo_entry[1] == 'municipal_data'
            assert espoo_entry[2] == 800
            assert espoo_entry[3] == 0.92
            
            helsinki_entry = entries[1]
            assert helsinki_entry[0] == 'Helsinki'
            assert helsinki_entry[1] == 'osm_buildings'
            assert helsinki_entry[2] == 1500
            assert helsinki_entry[3] == 0.95


class TestCoordinateValidationReporting:
    """Test coordinate validation reporting functionality"""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_validation_summary_generation(self, temp_db_path):
        """Test validation summary generation"""
        # Setup database
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        coordinate_validator = CoordinateValidator(temp_db_path)
        
        # Insert test data
        with duckdb.connect(temp_db_path) as con:
            con.execute("""
                INSERT INTO listings (url, city, latitude, longitude, city_validated, geospatial_quality_score)
                VALUES 
                ('url1', 'Helsinki', 60.2, 24.9, TRUE, 1.0),
                ('url2', 'Helsinki', 70.0, 30.0, FALSE, 0.0),
                ('url3', 'Espoo', 60.25, 24.7, TRUE, 1.0)
            """)
        
        # Get validation summary
        summary = coordinate_validator.get_validation_summary()
        
        assert 'Helsinki' in summary
        assert 'Espoo' in summary
        
        helsinki_summary = summary['Helsinki']
        assert helsinki_summary['total_listings'] == 2
        assert helsinki_summary['valid_coordinates'] == 1
        assert helsinki_summary['invalid_coordinates'] == 1
        assert helsinki_summary['validation_rate'] == 50.0
        
        espoo_summary = summary['Espoo']
        assert espoo_summary['total_listings'] == 1
        assert espoo_summary['valid_coordinates'] == 1
        assert espoo_summary['validation_rate'] == 100.0
    
    def test_invalid_coordinates_retrieval(self, temp_db_path):
        """Test retrieval of invalid coordinates"""
        # Setup database
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        coordinate_validator = CoordinateValidator(temp_db_path)
        
        # Insert test data with invalid coordinates
        with duckdb.connect(temp_db_path) as con:
            con.execute("""
                INSERT INTO listings (url, city, address, latitude, longitude, city_validated, coordinate_validation_error)
                VALUES 
                ('url1', 'Helsinki', 'Invalid Address 1', 70.0, 30.0, FALSE, 'Outside Helsinki bounds'),
                ('url2', 'Espoo', 'Invalid Address 2', 59.0, 23.0, FALSE, 'Outside Espoo bounds'),
                ('url3', 'Helsinki', 'Valid Address', 60.2, 24.9, TRUE, NULL)
            """)
        
        # Get invalid coordinates
        invalid_coords = coordinate_validator.get_invalid_coordinates()
        
        assert len(invalid_coords) == 2
        
        # Check that only invalid coordinates are returned
        for coord in invalid_coords:
            assert coord['latitude'] in [70.0, 59.0]
            assert coord['error'] is not None
    
    def test_validation_report_creation(self, temp_db_path):
        """Test validation report creation"""
        # Setup database
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        coordinate_validator = CoordinateValidator(temp_db_path)
        
        # Insert test data
        with duckdb.connect(temp_db_path) as con:
            con.execute("""
                INSERT INTO listings (url, city, address, latitude, longitude, city_validated, geospatial_quality_score)
                VALUES 
                ('url1', 'Helsinki', 'Test Address 1', 60.2, 24.9, TRUE, 1.0),
                ('url2', 'Espoo', 'Test Address 2', 60.25, 24.7, TRUE, 1.0)
            """)
        
        # Create validation report
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            report_path = f.name
        
        try:
            report_content = coordinate_validator.create_validation_report(report_path)
            
            # Verify report content
            assert '# Coordinate Validation Report' in report_content
            assert '## Summary by City' in report_content
            assert '### Helsinki' in report_content
            assert '### Espoo' in report_content
            assert '## City Coordinate Bounds' in report_content
            
            # Verify file was created
            assert os.path.exists(report_path)
            
            with open(report_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
                assert file_content == report_content
                
        finally:
            # Cleanup
            if os.path.exists(report_path):
                os.unlink(report_path)


class TestDatabaseSchemaValidation:
    """Comprehensive database schema validation tests"""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_complete_schema_migration_workflow(self, temp_db_path):
        """Test complete schema migration workflow from start to finish"""
        # Step 1: Create base schema
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        # Step 2: Apply base migrations
        migration_manager = MultiCityMigrationManager(temp_db_path)
        base_success = migration_manager.migrate_up()
        assert base_success is True
        
        # Step 3: Apply multi-city migrations
        multi_city_success = migration_manager.apply_multi_city_migrations()
        assert multi_city_success is True
        
        # Step 4: Validate final schema
        with duckdb.connect(temp_db_path, read_only=True) as con:
            # Check all required tables exist
            tables = con.execute("SHOW TABLES").fetchall()
            table_names = [table[0] for table in tables]
            
            required_tables = [
                'listings', 'scraping_executions', 'city_coordinate_bounds',
                'city_data_sources', 'city_geocoding_results', 'city_api_usage'
            ]
            
            for table in required_tables:
                assert table in table_names, f"Required table {table} not found"
            
            # Check listings table has all required columns
            columns = con.execute("DESCRIBE listings").fetchall()
            column_names = [col[0] for col in columns]
            
            required_columns = [
                'url', 'city', 'latitude', 'longitude', 'city_validated',
                'coordinate_source', 'geospatial_quality_score',
                'coordinate_validation_error', 'last_coordinate_validation'
            ]
            
            for column in required_columns:
                assert column in column_names, f"Required column {column} not found in listings table"
    
    def test_spatial_indexes_performance(self, temp_db_path):
        """Test that spatial indexes improve query performance"""
        # Setup database with sample data
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        # Insert sample data for performance testing
        with duckdb.connect(temp_db_path) as con:
            # Insert test data
            for i in range(1000):
                city = 'Helsinki' if i % 2 == 0 else 'Espoo'
                lat = 60.1 + (i % 100) * 0.001
                lon = 24.5 + (i % 100) * 0.001
                
                con.execute("""
                    INSERT INTO listings (url, city, latitude, longitude, scraped_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, [f'https://test.com/listing{i}', city, lat, lon])
            
            # Test queries that should benefit from indexes
            import time
            
            # Query by city and coordinates
            start_time = time.time()
            result = con.execute("""
                SELECT COUNT(*) FROM listings 
                WHERE city = 'Helsinki' AND latitude BETWEEN 60.1 AND 60.2
            """).fetchone()
            query_time = time.time() - start_time
            
            assert result[0] > 0
            assert query_time < 1.0  # Should be fast with proper indexing
            
            # Query by city and validation status
            start_time = time.time()
            result = con.execute("""
                SELECT COUNT(*) FROM listings 
                WHERE city = 'Espoo' AND city_validated IS NOT NULL
            """).fetchone()
            query_time = time.time() - start_time
            
            assert query_time < 1.0  # Should be fast with proper indexing
    
    def test_constraint_validation(self, temp_db_path):
        """Test database constraints and validation rules"""
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        with duckdb.connect(temp_db_path) as con:
            # Test city coordinate bounds table constraints
            con.execute("""
                INSERT INTO city_coordinate_bounds 
                (city, min_latitude, max_latitude, min_longitude, max_longitude)
                VALUES ('TestCity', 60.0, 60.5, 24.0, 25.0)
            """)
            
            # Verify data was inserted correctly
            result = con.execute("""
                SELECT city, min_latitude, max_latitude, min_longitude, max_longitude
                FROM city_coordinate_bounds WHERE city = 'TestCity'
            """).fetchone()
            
            assert result is not None
            assert result[0] == 'TestCity'
            assert result[1] == 60.0
            assert result[2] == 60.5
            assert result[3] == 24.0
            assert result[4] == 25.0
    
    def test_data_lineage_tracking(self, temp_db_path):
        """Test data lineage tracking functionality"""
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        with duckdb.connect(temp_db_path) as con:
            # Test city_data_sources table
            con.execute("""
                INSERT INTO city_data_sources 
                (city, data_source_type, api_endpoint, records_count, data_quality_score)
                VALUES ('Helsinki', 'osm_buildings', 'https://overpass-api.de', 1500, 0.95)
            """)
            
            # Test city_geocoding_results table
            con.execute("""
                INSERT INTO city_geocoding_results 
                (city, address, geocoded_latitude, geocoded_longitude, geocoding_source, validation_status)
                VALUES ('Helsinki', 'Mannerheimintie 1', 60.1699, 24.9384, 'osm', 'valid')
            """)
            
            # Test city_api_usage table
            con.execute("""
                INSERT INTO city_api_usage 
                (city, api_endpoint, request_timestamp, response_status, records_fetched)
                VALUES ('Helsinki', 'https://api.example.com', CURRENT_TIMESTAMP, 200, 100)
            """)
            
            # Verify all data was inserted correctly
            data_sources = con.execute("SELECT COUNT(*) FROM city_data_sources").fetchone()[0]
            geocoding_results = con.execute("SELECT COUNT(*) FROM city_geocoding_results").fetchone()[0]
            api_usage = con.execute("SELECT COUNT(*) FROM city_api_usage").fetchone()[0]
            
            assert data_sources == 1
            assert geocoding_results == 1
            assert api_usage == 1
    
    def test_validation_views_functionality(self, temp_db_path):
        """Test validation views provide correct data"""
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        # Insert test data
        with duckdb.connect(temp_db_path) as con:
            con.execute("""
                INSERT INTO listings (url, city, latitude, longitude, city_validated, geospatial_quality_score)
                VALUES 
                ('url1', 'Helsinki', 60.2, 24.9, TRUE, 0.9),
                ('url2', 'Helsinki', 70.0, 30.0, FALSE, 0.1),
                ('url3', 'Espoo', 60.25, 24.7, TRUE, 0.95),
                ('url4', 'Espoo', 59.0, 23.0, FALSE, 0.0)
            """)
            
            # Test city_validation_summary view
            summary = con.execute("SELECT * FROM city_validation_summary ORDER BY city").fetchall()
            assert len(summary) == 2
            
            # Check Espoo summary
            espoo_summary = [s for s in summary if s[0] == 'Espoo'][0]
            assert espoo_summary[1] == 2  # total_listings
            assert espoo_summary[2] == 1  # validated_listings
            assert espoo_summary[3] == 1  # unvalidated_listings
            
            # Check Helsinki summary
            helsinki_summary = [s for s in summary if s[0] == 'Helsinki'][0]
            assert helsinki_summary[1] == 2  # total_listings
            assert helsinki_summary[2] == 1  # validated_listings
            assert helsinki_summary[3] == 1  # unvalidated_listings
            
            # Test invalid_coordinates view
            invalid_coords = con.execute("""
                SELECT COUNT(*) FROM invalid_coordinates 
                WHERE validation_error != 'Valid'
            """).fetchone()[0]
            
            assert invalid_coords == 2  # Two invalid coordinate entries
    
    def test_migration_rollback_safety(self, temp_db_path):
        """Test that migrations can be safely rolled back"""
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        
        # Apply all migrations
        success = migration_manager.apply_multi_city_migrations()
        assert success is True
        
        # Verify tables exist
        with duckdb.connect(temp_db_path, read_only=True) as con:
            tables_before = con.execute("SHOW TABLES").fetchall()
            table_names_before = [table[0] for table in tables_before]
            assert 'city_coordinate_bounds' in table_names_before
            assert 'city_data_sources' in table_names_before
        
        # Test rollback of a specific migration
        coordinate_bounds_migration = None
        for migration in migration_manager.multi_city_migrations:
            if 'coordinate_validation_function' in migration.version:
                coordinate_bounds_migration = migration
                break
        
        if coordinate_bounds_migration:
            # Rollback should work without errors
            rollback_success = migration_manager.rollback_migration(coordinate_bounds_migration)
            assert rollback_success is True
    
    def test_performance_with_large_dataset(self, temp_db_path):
        """Test performance with larger dataset simulation"""
        schema = DatabaseSchema(temp_db_path)
        schema.create_all_tables()
        
        migration_manager = MultiCityMigrationManager(temp_db_path)
        migration_manager.apply_multi_city_migrations()
        
        # Insert larger dataset for performance testing
        import time
        
        start_time = time.time()
        
        with duckdb.connect(temp_db_path) as con:
            # Batch insert for better performance
            batch_data = []
            for i in range(5000):
                city = 'Helsinki' if i % 3 == 0 else 'Espoo'
                lat = 60.1 + (i % 1000) * 0.0001
                lon = 24.5 + (i % 1000) * 0.0001
                
                batch_data.append((
                    f'https://test.com/listing{i}',
                    city,
                    f'Test Address {i}',
                    lat,
                    lon,
                    100000 + i * 1000,  # price
                    50 + i % 100,       # size
                    datetime.now()
                ))
            
            # Insert in batches
            batch_size = 1000
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i + batch_size]
                con.executemany("""
                    INSERT INTO listings (url, city, address, latitude, longitude, price_eur, size_m2, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, batch)
        
        insert_time = time.time() - start_time
        
        # Test query performance
        start_time = time.time()
        
        with duckdb.connect(temp_db_path, read_only=True) as con:
            # Complex multi-city query
            result = con.execute("""
                SELECT city, COUNT(*) as count, AVG(price_eur) as avg_price, AVG(size_m2) as avg_size
                FROM listings 
                WHERE latitude BETWEEN 60.1 AND 60.3 
                  AND longitude BETWEEN 24.5 AND 24.8
                  AND price_eur > 150000
                GROUP BY city
                ORDER BY city
            """).fetchall()
            
            query_time = time.time() - start_time
            
            # Verify results
            assert len(result) > 0
            assert query_time < 2.0  # Should complete within 2 seconds
            assert insert_time < 10.0  # Batch insert should be reasonably fast
            
            # Test coordinate validation query performance
            start_time = time.time()
            
            validation_result = con.execute("""
                SELECT city, COUNT(*) as total,
                       COUNT(CASE WHEN city_validated = TRUE THEN 1 END) as validated
                FROM listings
                GROUP BY city
            """).fetchall()
            
            validation_query_time = time.time() - start_time
            
            assert len(validation_result) > 0
            assert validation_query_time < 1.0  # Should be fast with proper indexing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])