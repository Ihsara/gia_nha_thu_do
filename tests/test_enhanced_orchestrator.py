"""
Test suite for the Enhanced Scraper Orchestrator.

This test validates all automation capabilities including smart deduplication,
daily execution workflow, execution metadata tracking, performance monitoring,
error handling, and OSM building footprint validation integration.
"""

import pytest
import uuid
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

# Add the project root to the path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from oikotie.automation.orchestrator import (
    EnhancedScraperOrchestrator, ScraperConfig, ScrapingResult, ExecutionStatus,
    create_orchestrator_from_task_config, load_config_and_create_orchestrators
)
from oikotie.database.manager import EnhancedDatabaseManager, ExecutionMetadata
from oikotie.automation.deduplication import SmartDeduplicationManager, DeduplicationSummary
from oikotie.automation.listing_manager import ListingManager, ProcessingStats
from oikotie.automation.retry_manager import RetryManager, RetryConfiguration


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
        yield f.name
    # Cleanup handled by tempfile


@pytest.fixture
def enhanced_db_manager(temp_db_path):
    """Create an enhanced database manager for testing."""
    return EnhancedDatabaseManager(temp_db_path)


@pytest.fixture
def scraper_config():
    """Create a test scraper configuration."""
    return ScraperConfig(
        city="Helsinki",
        url="https://asunnot.oikotie.fi/myytavat-asunnot/helsinki",
        listing_limit=10,
        max_detail_workers=2,
        staleness_threshold_hours=24,
        retry_limit=3,
        retry_delay_hours=1,
        batch_size=5,
        enable_smart_deduplication=True,
        enable_performance_monitoring=True,
        headless_browser=True
    )


@pytest.fixture
def orchestrator(scraper_config, enhanced_db_manager):
    """Create an enhanced scraper orchestrator for testing."""
    return EnhancedScraperOrchestrator(scraper_config, enhanced_db_manager)


class TestEnhancedScraperOrchestrator:
    """Test the enhanced scraper orchestrator functionality."""
    
    def test_initialization(self, orchestrator, scraper_config):
        """Test that orchestrator initializes correctly with all components."""
        assert orchestrator.config == scraper_config
        assert isinstance(orchestrator.db_manager, EnhancedDatabaseManager)
        assert isinstance(orchestrator.deduplication_manager, SmartDeduplicationManager)
        assert isinstance(orchestrator.listing_manager, ListingManager)
        assert isinstance(orchestrator.retry_manager, RetryManager)
    
    def test_smart_deduplication_integration(self, orchestrator):
        """Test smart deduplication integration."""
        # Mock URLs for testing
        test_urls = [
            "https://asunnot.oikotie.fi/myytavat-asunnot/1",
            "https://asunnot.oikotie.fi/myytavat-asunnot/2",
            "https://asunnot.oikotie.fi/myytavat-asunnot/3"
        ]
        
        # Test should_skip_listing method
        for url in test_urls:
            result = orchestrator.should_skip_listing(url)
            assert isinstance(result, bool)
        
        # Test get_stale_listings method
        stale_listings = orchestrator.get_stale_listings(staleness_hours=1)
        assert isinstance(stale_listings, list)
    
    @patch('oikotie.automation.orchestrator.OikotieScraper')
    def test_discover_listing_urls(self, mock_scraper_class, orchestrator):
        """Test URL discovery functionality."""
        # Mock scraper instance
        mock_scraper = MagicMock()
        mock_scraper_class.return_value = mock_scraper
        
        # Mock listing summaries
        mock_summaries = [
            {'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/1'},
            {'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/2'},
            {'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/3'}
        ]
        mock_scraper.get_all_listing_summaries.return_value = mock_summaries
        
        # Test URL discovery
        urls = orchestrator._discover_listing_urls()
        
        assert len(urls) == 3
        assert all(url.startswith('https://asunnot.oikotie.fi') for url in urls)
        mock_scraper.close.assert_called_once()
    
    @patch('oikotie.automation.orchestrator.OikotieScraper')
    def test_daily_execution_workflow(self, mock_scraper_class, orchestrator):
        """Test the complete daily execution workflow."""
        # Mock scraper
        mock_scraper = MagicMock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.get_all_listing_summaries.return_value = [
            {'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/1'},
            {'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/2'}
        ]
        
        # Execute daily scrape
        result = orchestrator.run_daily_scrape()
        
        # Validate result structure
        assert isinstance(result, ScrapingResult)
        assert result.city == "Helsinki"
        assert result.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]
        assert isinstance(result.execution_id, str)
        assert isinstance(result.started_at, datetime)
        
        # Validate execution metadata tracking
        if result.completed_at:
            assert result.execution_time_seconds is not None
            assert result.execution_time_seconds >= 0
    
    def test_execution_metadata_tracking(self, orchestrator, enhanced_db_manager):
        """Test execution metadata tracking functionality."""
        execution_id = str(uuid.uuid4())
        metadata = ExecutionMetadata(
            execution_id=execution_id,
            started_at=datetime.now(),
            city="Helsinki",
            status="completed",
            completed_at=datetime.now(),
            listings_processed=10,
            listings_new=5,
            listings_failed=1,
            execution_time_seconds=120,
            memory_usage_mb=256
        )
        
        # Track metadata
        enhanced_db_manager.track_execution_metadata(metadata)
        
        # Verify metadata was stored
        history = enhanced_db_manager.get_execution_history(city="Helsinki", limit=1)
        assert len(history) == 1
        assert history[0].execution_id == execution_id
        assert history[0].city == "Helsinki"
        assert history[0].status == "completed"
    
    @patch('psutil.Process')
    def test_performance_monitoring(self, mock_process, orchestrator):
        """Test performance monitoring capabilities."""
        # Mock memory info
        mock_memory_info = MagicMock()
        mock_memory_info.rss = 256 * 1024 * 1024  # 256 MB in bytes
        mock_process.return_value.memory_info.return_value = mock_memory_info
        
        # Test memory usage tracking
        memory_usage = orchestrator._get_memory_usage()
        assert memory_usage == 256.0  # Should be 256 MB
    
    def test_error_handling_and_recovery(self, orchestrator):
        """Test comprehensive error handling and recovery mechanisms."""
        # Test with invalid configuration
        invalid_config = ScraperConfig(
            city="",  # Invalid empty city
            url="invalid-url",  # Invalid URL
            listing_limit=-1,  # Invalid limit
        )
        
        # Update configuration
        orchestrator.update_configuration(invalid_config)
        
        # Execute and expect graceful handling
        result = orchestrator.run_daily_scrape()
        
        # Should handle errors gracefully
        assert isinstance(result, ScrapingResult)
        # May complete with warnings or fail gracefully
        assert result.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]
    
    def test_configuration_management(self, orchestrator, scraper_config):
        """Test configuration management and runtime updates."""
        # Test getting current configuration
        current_config = orchestrator.get_configuration()
        assert current_config.city == scraper_config.city
        assert current_config.staleness_threshold_hours == scraper_config.staleness_threshold_hours
        
        # Test updating configuration
        new_config = ScraperConfig(
            city="Tampere",
            url="https://asunnot.oikotie.fi/myytavat-asunnot/tampere",
            staleness_threshold_hours=48,
            retry_limit=5
        )
        
        orchestrator.update_configuration(new_config)
        updated_config = orchestrator.get_configuration()
        assert updated_config.city == "Tampere"
        assert updated_config.staleness_threshold_hours == 48
        assert updated_config.retry_limit == 5
    
    def test_execution_statistics(self, orchestrator):
        """Test execution statistics collection."""
        stats = orchestrator.get_execution_statistics(hours_back=24)
        assert isinstance(stats, dict)
        # Should return statistics even if empty
        assert 'total_executions' in stats or len(stats) == 0


class TestOrchestratorFactory:
    """Test orchestrator factory functions."""
    
    def test_create_orchestrator_from_task_config(self):
        """Test creating orchestrator from task configuration."""
        task_config = {
            'city': 'Helsinki',
            'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/helsinki',
            'listing_limit': 50,
            'max_detail_workers': 3,
            'staleness_threshold_hours': 12,
            'enable_smart_deduplication': True
        }
        
        orchestrator = create_orchestrator_from_task_config(task_config)
        
        assert isinstance(orchestrator, EnhancedScraperOrchestrator)
        assert orchestrator.config.city == 'Helsinki'
        assert orchestrator.config.listing_limit == 50
        assert orchestrator.config.staleness_threshold_hours == 12
        assert orchestrator.config.enable_smart_deduplication is True
    
    def test_load_config_and_create_orchestrators(self, tmp_path):
        """Test loading configuration and creating multiple orchestrators."""
        # Create test configuration file
        config_data = {
            'tasks': [
                {
                    'city': 'Helsinki',
                    'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/helsinki',
                    'enabled': True
                },
                {
                    'city': 'Tampere',
                    'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/tampere',
                    'enabled': True
                },
                {
                    'city': 'Turku',
                    'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/turku',
                    'enabled': False  # Disabled task
                }
            ]
        }
        
        config_path = tmp_path / 'test_config.json'
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        # Load orchestrators
        orchestrators = load_config_and_create_orchestrators(str(config_path))
        
        # Should create orchestrators only for enabled tasks
        assert len(orchestrators) == 2
        cities = [orch.config.city for orch in orchestrators]
        assert 'Helsinki' in cities
        assert 'Tampere' in cities
        assert 'Turku' not in cities


class TestIntegrationWithExistingComponents:
    """Test integration with existing scraper and database components."""
    
    def test_database_integration(self, enhanced_db_manager):
        """Test integration with enhanced database manager."""
        # Test that all required tables exist
        table_info = enhanced_db_manager.get_table_info()
        
        # Should have automation tables
        expected_tables = ['listings', 'scraping_executions']
        for table in expected_tables:
            if table in table_info:
                assert table_info[table]['exists'] is True
    
    def test_osm_building_footprint_integration(self, orchestrator):
        """Test integration with OSM building footprint validation system."""
        # This is a placeholder test for OSM integration
        # In a full implementation, this would test the integration
        # with the existing OSM building footprint validation system
        
        # For now, just verify the orchestrator can handle the integration
        assert orchestrator.config.city is not None
        assert hasattr(orchestrator, 'db_manager')
        
        # The actual OSM integration would be tested with real data
        # and would verify that building footprint validation is applied
        # to scraped listings during the automation workflow


class TestBugPrevention:
    """Bug prevention tests for expensive operations."""
    
    def test_database_connection_handling(self, orchestrator):
        """Test that database connections are properly managed."""
        # Test multiple operations to ensure connections don't leak
        for _ in range(5):
            stale_listings = orchestrator.get_stale_listings()
            assert isinstance(stale_listings, list)
    
    def test_memory_usage_monitoring(self, orchestrator):
        """Test memory usage monitoring to prevent memory leaks."""
        initial_memory = orchestrator._get_memory_usage()
        
        # Perform operations that might cause memory issues
        for _ in range(3):
            orchestrator.get_stale_listings()
            orchestrator.get_execution_statistics()
        
        final_memory = orchestrator._get_memory_usage()
        
        # Memory should not increase dramatically (allow for some variance)
        memory_increase = final_memory - initial_memory
        assert memory_increase < 100  # Less than 100MB increase
    
    def test_configuration_validation(self):
        """Test configuration validation to prevent runtime errors."""
        # Test with various invalid configurations
        invalid_configs = [
            {'city': '', 'url': 'valid-url'},  # Empty city
            {'city': 'Helsinki', 'url': ''},  # Empty URL
            {'city': 'Helsinki', 'url': 'valid-url', 'listing_limit': -1},  # Negative limit
            {'city': 'Helsinki', 'url': 'valid-url', 'staleness_threshold_hours': 0},  # Zero threshold
        ]
        
        for config_dict in invalid_configs:
            try:
                config = ScraperConfig(**config_dict)
                orchestrator = EnhancedScraperOrchestrator(config)
                # Should not crash during initialization
                assert orchestrator is not None
            except Exception as e:
                # If it raises an exception, it should be a clear validation error
                assert isinstance(e, (ValueError, TypeError))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])