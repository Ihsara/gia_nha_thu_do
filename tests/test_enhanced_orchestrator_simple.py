#!/usr/bin/env python3
"""
Simple test suite for the Enhanced Scraper Orchestrator.

This test validates core functionality without complex database setup
to avoid file locking issues on Windows.
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


class TestScraperConfig:
    """Test scraper configuration functionality."""
    
    def test_scraper_config_creation(self):
        """Test creating scraper configuration."""
        config = ScraperConfig(
            city="Helsinki",
            url="https://asunnot.oikotie.fi/myytavat-asunnot/helsinki",
            listing_limit=50,
            staleness_threshold_hours=24,
            enable_smart_deduplication=True
        )
        
        assert config.city == "Helsinki"
        assert config.listing_limit == 50
        assert config.staleness_threshold_hours == 24
        assert config.enable_smart_deduplication is True
        assert config.enable_performance_monitoring is True  # Default value
    
    def test_scraper_config_defaults(self):
        """Test scraper configuration default values."""
        config = ScraperConfig(
            city="Test",
            url="https://example.com"
        )
        
        assert config.listing_limit is None
        assert config.max_detail_workers == 5
        assert config.staleness_threshold_hours == 24
        assert config.retry_limit == 3
        assert config.batch_size == 100
        assert config.enable_smart_deduplication is True
        assert config.enable_performance_monitoring is True
        assert config.headless_browser is True


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
        
        # Mock the database manager to avoid file locking issues
        with patch('oikotie.automation.orchestrator.EnhancedDatabaseManager'):
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
        
        # Mock the database manager to avoid file locking issues
        with patch('oikotie.automation.orchestrator.EnhancedDatabaseManager'):
            orchestrators = load_config_and_create_orchestrators(str(config_path))
            
            # Should create orchestrators only for enabled tasks
            assert len(orchestrators) == 2
            cities = [orch.config.city for orch in orchestrators]
            assert 'Helsinki' in cities
            assert 'Tampere' in cities
            assert 'Turku' not in cities


class TestEnhancedOrchestratorMocked:
    """Test enhanced orchestrator with mocked dependencies."""
    
    @patch('oikotie.automation.orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.orchestrator.SmartDeduplicationManager')
    @patch('oikotie.automation.orchestrator.ListingManager')
    @patch('oikotie.automation.orchestrator.RetryManager')
    def test_orchestrator_initialization(self, mock_retry, mock_listing, mock_dedup, mock_db):
        """Test orchestrator initialization with mocked components."""
        config = ScraperConfig(
            city="Helsinki",
            url="https://asunnot.oikotie.fi/myytavat-asunnot/helsinki"
        )
        
        orchestrator = EnhancedScraperOrchestrator(config)
        
        assert orchestrator.config == config
        assert mock_db.called
        assert mock_dedup.called
        assert mock_listing.called
        assert mock_retry.called
    
    @patch('oikotie.automation.orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.orchestrator.OikotieScraper')
    def test_discover_listing_urls_mocked(self, mock_scraper_class, mock_db):
        """Test URL discovery with mocked scraper."""
        config = ScraperConfig(
            city="Helsinki",
            url="https://asunnot.oikotie.fi/myytavat-asunnot/helsinki"
        )
        
        orchestrator = EnhancedScraperOrchestrator(config)
        
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
    
    @patch('oikotie.automation.orchestrator.EnhancedDatabaseManager')
    def test_configuration_management_mocked(self, mock_db):
        """Test configuration management with mocked database."""
        config = ScraperConfig(
            city="Helsinki",
            url="https://asunnot.oikotie.fi/myytavat-asunnot/helsinki",
            staleness_threshold_hours=24
        )
        
        orchestrator = EnhancedScraperOrchestrator(config)
        
        # Test getting current configuration
        current_config = orchestrator.get_configuration()
        assert current_config.city == "Helsinki"
        assert current_config.staleness_threshold_hours == 24
        
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
    
    @patch('oikotie.automation.orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.orchestrator.OikotieScraper')
    def test_daily_scrape_workflow_mocked(self, mock_scraper_class, mock_db):
        """Test daily scrape workflow with mocked components."""
        config = ScraperConfig(
            city="Helsinki",
            url="https://asunnot.oikotie.fi/myytavat-asunnot/helsinki",
            listing_limit=5
        )
        
        orchestrator = EnhancedScraperOrchestrator(config)
        
        # Mock scraper
        mock_scraper = MagicMock()
        mock_scraper_class.return_value = mock_scraper
        mock_scraper.get_all_listing_summaries.return_value = [
            {'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/1'},
            {'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/2'}
        ]
        
        # Mock deduplication manager
        orchestrator.deduplication_manager.analyze_urls = MagicMock()
        orchestrator.deduplication_manager.analyze_urls.return_value = MagicMock(
            total_urls=2,
            process_new=2,
            skip_recent=0,
            skip_failed=0,
            process_stale=0,
            process_retry=0,
            decisions=[]
        )
        orchestrator.deduplication_manager.get_urls_to_process = MagicMock(return_value=[
            'https://asunnot.oikotie.fi/myytavat-asunnot/1',
            'https://asunnot.oikotie.fi/myytavat-asunnot/2'
        ])
        orchestrator.deduplication_manager.log_deduplication_decisions = MagicMock()
        
        # Mock listing manager
        orchestrator.listing_manager.create_processing_plan = MagicMock(return_value=[])
        orchestrator.listing_manager.execute_processing_plan = MagicMock()
        orchestrator.listing_manager.execute_processing_plan.return_value = MagicMock(
            total_urls=2,
            processed_urls=2,
            successful_urls=2,
            failed_urls=0,
            skipped_urls=0,
            processing_time_seconds=1.0,
            average_time_per_url=0.5,
            error_rate=0.0
        )
        
        # Mock database manager
        orchestrator.db_manager.track_execution_metadata = MagicMock()
        
        # Execute daily scrape
        result = orchestrator.run_daily_scrape()
        
        # Validate result
        assert isinstance(result, ScrapingResult)
        assert result.city == "Helsinki"
        assert result.status == ExecutionStatus.COMPLETED
        assert result.total_urls_discovered == 2
        assert isinstance(result.execution_id, str)
        assert isinstance(result.started_at, datetime)
        assert result.completed_at is not None
        assert result.execution_time_seconds is not None
        assert result.execution_time_seconds >= 0


class TestConfigurationValidation:
    """Test configuration validation."""
    
    def test_valid_configurations(self):
        """Test various valid configurations."""
        valid_configs = [
            {
                'city': 'Helsinki',
                'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/helsinki'
            },
            {
                'city': 'Tampere',
                'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/tampere',
                'listing_limit': 100,
                'staleness_threshold_hours': 48
            },
            {
                'city': 'Turku',
                'url': 'https://asunnot.oikotie.fi/myytavat-asunnot/turku',
                'enable_smart_deduplication': False,
                'enable_performance_monitoring': False
            }
        ]
        
        for config_dict in valid_configs:
            config = ScraperConfig(**config_dict)
            assert config.city == config_dict['city']
            assert config.url == config_dict['url']
    
    def test_configuration_edge_cases(self):
        """Test configuration with edge case values."""
        # Test with minimal configuration
        config = ScraperConfig(city="Test", url="https://example.com")
        assert config.city == "Test"
        assert config.url == "https://example.com"
        
        # Test with zero values (should be allowed)
        config = ScraperConfig(
            city="Test",
            url="https://example.com",
            listing_limit=0,
            staleness_threshold_hours=1,
            retry_limit=1
        )
        assert config.listing_limit == 0
        assert config.staleness_threshold_hours == 1
        assert config.retry_limit == 1


class TestScrapingResult:
    """Test scraping result data structure."""
    
    def test_scraping_result_creation(self):
        """Test creating scraping result."""
        execution_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        result = ScrapingResult(
            execution_id=execution_id,
            city="Helsinki",
            status=ExecutionStatus.COMPLETED,
            started_at=start_time,
            completed_at=datetime.now(),
            total_urls_discovered=10,
            urls_processed=8,
            listings_new=5,
            listings_updated=2,
            listings_skipped=1,
            listings_failed=0,
            execution_time_seconds=120.5
        )
        
        assert result.execution_id == execution_id
        assert result.city == "Helsinki"
        assert result.status == ExecutionStatus.COMPLETED
        assert result.total_urls_discovered == 10
        assert result.urls_processed == 8
        assert result.listings_new == 5
        assert result.execution_time_seconds == 120.5
    
    def test_execution_status_enum(self):
        """Test execution status enumeration."""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.CANCELLED.value == "cancelled"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])