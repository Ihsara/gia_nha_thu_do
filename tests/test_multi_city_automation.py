"""
Test Suite for Multi-City Automation System

This module provides comprehensive tests for the enhanced multi-city automation
system including cluster coordination, circuit breakers, and audit logging.
"""

import pytest
import json
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from oikotie.automation.multi_city_orchestrator import (
    MultiCityScraperOrchestrator,
    CityConfig,
    CityExecutionResult,
    ExecutionStatus,
    create_multi_city_orchestrator
)
from oikotie.automation.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerOpenException
)
from oikotie.automation.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity
)


@pytest.fixture
def mock_config_file(tmp_path):
    """Create a mock configuration file for testing."""
    config = {
        "tasks": [
            {
                "city": "Helsinki",
                "enabled": True,
                "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
                "max_detail_workers": 3,
                "rate_limit_seconds": 1.0,
                "coordinate_bounds": [24.5, 60.0, 25.5, 60.5],
                "geospatial_sources": ["helsinki_open_data", "osm_buildings"],
                "priority": 2
            },
            {
                "city": "Espoo",
                "enabled": True,
                "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B49,6,%22Espoo%22%5D%5D&cardType=100",
                "max_detail_workers": 3,
                "rate_limit_seconds": 1.0,
                "coordinate_bounds": [24.4, 60.1, 24.9, 60.4],
                "geospatial_sources": ["espoo_open_data", "osm_buildings"],
                "priority": 1
            },
            {
                "city": "Vantaa",
                "enabled": False,
                "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B92,6,%22Vantaa%22%5D%5D&cardType=100",
                "max_detail_workers": 3,
                "rate_limit_seconds": 1.0,
                "priority": 1
            }
        ],
        "global_settings": {
            "database_path": "data/real_estate.duckdb",
            "output_directory": "output",
            "log_level": "INFO",
            "cluster_coordination": {
                "redis_url": "redis://localhost:6379",
                "heartbeat_interval": 30,
                "work_distribution_strategy": "round_robin"
            }
        }
    }
    
    config_file = tmp_path / "config.json"
    with open(config_file, 'w') as f:
        json.dump(config, f)
    
    return str(config_file)


@pytest.fixture
def mock_db_manager():
    """Mock database manager for testing."""
    mock_db = Mock()
    mock_db.db_path = "test.db"
    return mock_db


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    mock_redis = Mock()
    mock_redis.ping.return_value = True
    mock_redis.set.return_value = True
    mock_redis.get.return_value = None
    mock_redis.delete.return_value = 1
    mock_redis.keys.return_value = []
    mock_redis.hgetall.return_value = {}
    mock_redis.hset.return_value = 1
    mock_redis.hdel.return_value = 1
    mock_redis.hlen.return_value = 0
    mock_redis.llen.return_value = 0
    mock_redis.lpush.return_value = 1
    mock_redis.rpop.return_value = None
    mock_redis.expire.return_value = True
    mock_redis.pipeline.return_value = mock_redis
    mock_redis.execute.return_value = [1] * 10
    mock_redis.eval.return_value = 1
    mock_redis.zadd.return_value = 1
    mock_redis.zrangebyscore.return_value = []
    mock_redis.zremrangebyscore.return_value = 0
    return mock_redis


class TestCityConfig:
    """Test CityConfig data class."""
    
    def test_city_config_creation(self):
        """Test CityConfig creation and initialization."""
        config = CityConfig(
            city="Helsinki",
            enabled=True,
            url="https://example.com/helsinki",
            max_detail_workers=5,
            rate_limit_seconds=2.0,
            coordinate_bounds=(24.5, 60.0, 25.5, 60.5),
            geospatial_sources=["source1", "source2"],
            priority=2
        )
        
        assert config.city == "Helsinki"
        assert config.enabled is True
        assert config.url == "https://example.com/helsinki"
        assert config.max_detail_workers == 5
        assert config.rate_limit_seconds == 2.0
        assert config.coordinate_bounds == (24.5, 60.0, 25.5, 60.5)
        assert config.geospatial_sources == ["source1", "source2"]
        assert config.priority == 2
    
    def test_city_config_defaults(self):
        """Test CityConfig default values."""
        config = CityConfig(
            city="TestCity",
            enabled=True,
            url="https://example.com/test"
        )
        
        assert config.max_detail_workers == 5
        assert config.rate_limit_seconds == 1.0
        assert config.coordinate_bounds is None
        assert config.geospatial_sources == []
        assert config.data_governance == {}
        assert config.priority == 1


class TestCircuitBreaker:
    """Test CircuitBreaker functionality."""
    
    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            success_threshold=2
        )
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30
        assert cb.success_threshold == 2
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0
    
    def test_circuit_breaker_success_recording(self):
        """Test recording successful operations."""
        cb = CircuitBreaker(failure_threshold=3)
        
        cb.record_success()
        assert cb.success_count == 1
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.last_success_time is not None
    
    def test_circuit_breaker_failure_recording(self):
        """Test recording failed operations."""
        cb = CircuitBreaker(failure_threshold=3)
        
        # Record failures below threshold
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.state == CircuitBreakerState.CLOSED
        
        cb.record_failure()
        assert cb.failure_count == 2
        assert cb.state == CircuitBreakerState.CLOSED
        
        # Record failure that exceeds threshold
        cb.record_failure()
        assert cb.failure_count == 3
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.last_failure_time is not None
    
    def test_circuit_breaker_call_protection(self):
        """Test circuit breaker call protection."""
        cb = CircuitBreaker(failure_threshold=2)
        
        def failing_function():
            raise Exception("Test failure")
        
        def successful_function():
            return "success"
        
        # Test successful calls
        result = cb.call(successful_function)
        assert result == "success"
        assert cb.success_count == 1
        
        # Test failing calls
        with pytest.raises(Exception, match="Test failure"):
            cb.call(failing_function)
        assert cb.failure_count == 1
        
        # Trip the circuit breaker
        with pytest.raises(Exception, match="Test failure"):
            cb.call(failing_function)
        assert cb.state == CircuitBreakerState.OPEN
        
        # Test that circuit breaker blocks calls
        with pytest.raises(CircuitBreakerOpenException):
            cb.call(successful_function)
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery mechanism."""
        cb = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=1,  # 1 second for testing
            success_threshold=2
        )
        
        def failing_function():
            raise Exception("Test failure")
        
        def successful_function():
            return "success"
        
        # Trip the circuit breaker
        with pytest.raises(Exception):
            cb.call(failing_function)
        with pytest.raises(Exception):
            cb.call(failing_function)
        
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # First call should transition to half-open
        result = cb.call(successful_function)
        assert result == "success"
        assert cb.state == CircuitBreakerState.HALF_OPEN
        
        # Second successful call should close the circuit
        result = cb.call(successful_function)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_circuit_breaker_metrics(self):
        """Test circuit breaker metrics collection."""
        cb = CircuitBreaker(failure_threshold=3)
        
        cb.record_success()
        cb.record_failure()
        cb.record_success()
        
        metrics = cb.get_metrics()
        
        assert metrics.state == CircuitBreakerState.CLOSED
        assert metrics.failure_count == 1
        assert metrics.success_count == 2
        assert metrics.total_requests == 3
        assert metrics.last_failure_time is not None
        assert metrics.last_success_time is not None
    
    def test_circuit_breaker_reset(self):
        """Test circuit breaker manual reset."""
        cb = CircuitBreaker(failure_threshold=1)
        
        # Trip the circuit breaker
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        
        # Reset the circuit breaker
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0


class TestAuditLogger:
    """Test AuditLogger functionality."""
    
    def test_audit_logger_initialization(self, mock_db_manager):
        """Test audit logger initialization."""
        audit_logger = AuditLogger(
            db_manager=mock_db_manager,
            log_to_file=False
        )
        
        assert audit_logger.db_manager == mock_db_manager
        assert audit_logger.log_to_file is False
    
    def test_audit_event_logging(self, mock_db_manager):
        """Test audit event logging."""
        audit_logger = AuditLogger(
            db_manager=mock_db_manager,
            log_to_file=False
        )
        
        event = AuditEvent(
            event_type=AuditEventType.AUTOMATION_START,
            execution_id="test-execution-123",
            city="Helsinki",
            severity=AuditSeverity.INFO,
            message="Test automation start",
            details={"test": "data"}
        )
        
        # Should not raise an exception
        audit_logger.log_event(event)
    
    def test_execution_context(self, mock_db_manager):
        """Test execution context functionality."""
        audit_logger = AuditLogger(
            db_manager=mock_db_manager,
            log_to_file=False
        )
        
        execution_id = "test-execution-456"
        context = audit_logger.create_execution_context(execution_id)
        
        assert context.execution_id == execution_id
        assert context.audit_logger == audit_logger
        
        # Test logging through context
        context.log_event(
            event_type=AuditEventType.CITY_EXECUTION_START,
            city="Espoo",
            message="Starting city execution"
        )
        
        # Test lineage logging through context
        context.log_lineage(
            table_name="listings",
            record_id="listing-123",
            operation="INSERT",
            data_source="oikotie_scraper"
        )


class TestMultiCityScraperOrchestrator:
    """Test MultiCityScraperOrchestrator functionality."""
    
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager')
    @patch('oikotie.automation.multi_city_orchestrator.AuditLogger')
    def test_orchestrator_initialization(self, mock_audit, mock_governance, mock_db, mock_config_file):
        """Test orchestrator initialization."""
        orchestrator = MultiCityScraperOrchestrator(
            config_path=mock_config_file,
            enable_cluster_coordination=False
        )
        
        assert len(orchestrator.city_configs) == 3  # Helsinki, Espoo, Vantaa
        assert orchestrator.enable_cluster_coordination is False
        assert orchestrator.cluster_coordinator is None
        
        # Check that enabled cities are loaded correctly
        enabled_cities = [c for c in orchestrator.city_configs if c.enabled]
        assert len(enabled_cities) == 2  # Helsinki and Espoo
        assert {c.city for c in enabled_cities} == {"Helsinki", "Espoo"}
    
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager')
    @patch('oikotie.automation.multi_city_orchestrator.AuditLogger')
    @patch('oikotie.automation.multi_city_orchestrator.create_cluster_coordinator')
    def test_orchestrator_with_cluster_coordination(self, mock_cluster, mock_audit, mock_governance, mock_db, mock_config_file, mock_redis_client):
        """Test orchestrator initialization with cluster coordination."""
        mock_coordinator = Mock()
        mock_cluster.return_value = mock_coordinator
        
        orchestrator = MultiCityScraperOrchestrator(
            config_path=mock_config_file,
            redis_url="redis://localhost:6379",
            enable_cluster_coordination=True
        )
        
        assert orchestrator.enable_cluster_coordination is True
        assert orchestrator.cluster_coordinator == mock_coordinator
        mock_coordinator.start_health_monitoring.assert_called_once()
    
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager')
    @patch('oikotie.automation.multi_city_orchestrator.AuditLogger')
    def test_city_priority_sorting(self, mock_audit, mock_governance, mock_db, mock_config_file):
        """Test that cities are sorted by priority."""
        orchestrator = MultiCityScraperOrchestrator(
            config_path=mock_config_file,
            enable_cluster_coordination=False
        )
        
        enabled_cities = [c for c in orchestrator.city_configs if c.enabled]
        enabled_cities.sort(key=lambda x: x.priority, reverse=True)
        
        # Helsinki has priority 2, Espoo has priority 1
        assert enabled_cities[0].city == "Helsinki"
        assert enabled_cities[1].city == "Espoo"
    
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager')
    @patch('oikotie.automation.multi_city_orchestrator.AuditLogger')
    def test_retry_managers_initialization(self, mock_audit, mock_governance, mock_db, mock_config_file):
        """Test retry managers are initialized for enabled cities."""
        with patch('oikotie.automation.multi_city_orchestrator.RetryManager') as mock_retry:
            orchestrator = MultiCityScraperOrchestrator(
                config_path=mock_config_file,
                enable_cluster_coordination=False
            )
            
            # Should create retry managers for enabled cities only
            assert len(orchestrator.retry_managers) == 2
            assert "Helsinki" in orchestrator.retry_managers
            assert "Espoo" in orchestrator.retry_managers
            assert "Vantaa" not in orchestrator.retry_managers
    
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager')
    @patch('oikotie.automation.multi_city_orchestrator.AuditLogger')
    def test_circuit_breakers_initialization(self, mock_audit, mock_governance, mock_db, mock_config_file):
        """Test circuit breakers are initialized for enabled cities."""
        with patch('oikotie.automation.multi_city_orchestrator.CircuitBreaker') as mock_cb:
            orchestrator = MultiCityScraperOrchestrator(
                config_path=mock_config_file,
                enable_cluster_coordination=False
            )
            
            # Should create circuit breakers for enabled cities only
            assert len(orchestrator.circuit_breakers) == 2
            assert "Helsinki" in orchestrator.circuit_breakers
            assert "Espoo" in orchestrator.circuit_breakers
            assert "Vantaa" not in orchestrator.circuit_breakers
    
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager')
    @patch('oikotie.automation.multi_city_orchestrator.AuditLogger')
    def test_sequential_execution(self, mock_audit, mock_governance, mock_db, mock_config_file):
        """Test sequential city execution without cluster coordination."""
        orchestrator = MultiCityScraperOrchestrator(
            config_path=mock_config_file,
            enable_cluster_coordination=False
        )
        
        # Mock the single city execution method
        def mock_execute_single_city(city_config, execution_id):
            from oikotie.automation.multi_city_orchestrator import CityExecutionMetrics, CityExecutionResult
            return CityExecutionMetrics(
                city=city_config.city,
                execution_id=execution_id,
                status=CityExecutionResult.SUCCESS,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                listings_new=10,
                listings_failed=1
            )
        
        with patch.object(orchestrator, '_execute_single_city', side_effect=mock_execute_single_city):
            result = orchestrator.run_daily_automation()
            
            assert result.status == ExecutionStatus.COMPLETED
            assert result.total_cities == 2  # Helsinki and Espoo
            assert result.successful_cities == 2
            assert result.failed_cities == 0
            assert result.total_listings_new == 20  # 10 per city
            assert len(result.city_results) == 2
    
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager')
    @patch('oikotie.automation.multi_city_orchestrator.AuditLogger')
    def test_execution_with_failures(self, mock_audit, mock_governance, mock_db, mock_config_file):
        """Test execution handling when some cities fail."""
        orchestrator = MultiCityScraperOrchestrator(
            config_path=mock_config_file,
            enable_cluster_coordination=False
        )
        
        # Mock single city execution with one failure
        def mock_execute_single_city(city_config, execution_id):
            from oikotie.automation.multi_city_orchestrator import CityExecutionMetrics, CityExecutionResult
            
            if city_config.city == "Helsinki":
                return CityExecutionMetrics(
                    city=city_config.city,
                    execution_id=execution_id,
                    status=CityExecutionResult.SUCCESS,
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    listings_new=10,
                    listings_failed=1
                )
            else:  # Espoo fails
                return CityExecutionMetrics(
                    city=city_config.city,
                    execution_id=execution_id,
                    status=CityExecutionResult.FAILED,
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    listings_new=0,
                    listings_failed=5,
                    error_summary="Network error"
                )
        
        with patch.object(orchestrator, '_execute_single_city', side_effect=mock_execute_single_city):
            result = orchestrator.run_daily_automation()
            
            assert result.status == ExecutionStatus.DEGRADED  # Some succeeded, some failed
            assert result.total_cities == 2
            assert result.successful_cities == 1
            assert result.failed_cities == 1
            assert result.total_listings_new == 10  # Only from Helsinki
            assert result.total_listings_failed == 6  # 1 from Helsinki + 5 from Espoo
    
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager')
    @patch('oikotie.automation.multi_city_orchestrator.AuditLogger')
    def test_execution_status_tracking(self, mock_audit, mock_governance, mock_db, mock_config_file):
        """Test execution status tracking."""
        orchestrator = MultiCityScraperOrchestrator(
            config_path=mock_config_file,
            enable_cluster_coordination=False
        )
        
        # Initially no execution
        assert orchestrator.get_execution_status() is None
        
        # Mock execution that tracks status
        def mock_execute_cities_sequentially(cities, execution_id):
            # Check that execution ID is set during execution
            assert orchestrator.get_execution_status() == execution_id
            return []
        
        with patch.object(orchestrator, '_execute_cities_sequentially', side_effect=mock_execute_cities_sequentially):
            result = orchestrator.run_daily_automation()
            
            # After execution, status should be cleared
            assert orchestrator.get_execution_status() is None
    
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager')
    @patch('oikotie.automation.multi_city_orchestrator.AuditLogger')
    def test_shutdown_coordination(self, mock_audit, mock_governance, mock_db, mock_config_file):
        """Test graceful shutdown coordination."""
        mock_cluster_coordinator = Mock()
        
        orchestrator = MultiCityScraperOrchestrator(
            config_path=mock_config_file,
            enable_cluster_coordination=False
        )
        orchestrator.cluster_coordinator = mock_cluster_coordinator
        
        orchestrator.shutdown()
        
        mock_cluster_coordinator.coordinate_shutdown.assert_called_once()


class TestMultiCityOrchestratorFactory:
    """Test multi-city orchestrator factory function."""
    
    @patch('oikotie.automation.multi_city_orchestrator.MultiCityScraperOrchestrator')
    def test_create_multi_city_orchestrator(self, mock_orchestrator_class, mock_config_file):
        """Test factory function creates orchestrator with correct parameters."""
        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        result = create_multi_city_orchestrator(
            config_path=mock_config_file,
            redis_url="redis://localhost:6379",
            enable_cluster_coordination=True
        )
        
        assert result == mock_orchestrator
        mock_orchestrator_class.assert_called_once_with(
            config_path=mock_config_file,
            redis_url="redis://localhost:6379",
            enable_cluster_coordination=True
        )


class TestIntegration:
    """Integration tests for multi-city automation system."""
    
    @patch('oikotie.automation.multi_city_orchestrator.OikotieScraper')
    @patch('oikotie.automation.multi_city_orchestrator.worker_scrape_details')
    @patch('oikotie.automation.multi_city_orchestrator.DatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    @patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager')
    @patch('oikotie.automation.multi_city_orchestrator.AuditLogger')
    def test_end_to_end_scraping_simulation(self, mock_audit, mock_governance, mock_enhanced_db, 
                                          mock_db, mock_worker, mock_scraper_class, mock_config_file):
        """Test end-to-end scraping simulation."""
        # Mock scraper behavior
        mock_scraper = Mock()
        mock_scraper_class.return_value = mock_scraper
        
        # Mock listing summaries discovery
        mock_scraper.get_all_listing_summaries.return_value = [
            {'url': 'https://example.com/listing1', 'title': 'Listing 1'},
            {'url': 'https://example.com/listing2', 'title': 'Listing 2'},
            {'url': 'https://example.com/listing3', 'title': 'Listing 3'}
        ]
        
        # Mock worker processing
        mock_worker.return_value = [
            {'url': 'https://example.com/listing1', 'details': {'price': '100000'}},
            {'url': 'https://example.com/listing2', 'details': {'price': '200000'}},
            {'url': 'https://example.com/listing3', 'details': {'error': 'Failed to parse'}}
        ]
        
        # Mock database manager
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        # Mock data governance
        mock_governance_instance = Mock()
        mock_governance_instance.enforce_rate_limits.return_value = True
        mock_governance.return_value = mock_governance_instance
        
        # Create orchestrator and run automation
        orchestrator = MultiCityScraperOrchestrator(
            config_path=mock_config_file,
            enable_cluster_coordination=False
        )
        
        result = orchestrator.run_daily_automation()
        
        # Verify results
        assert result.status in [ExecutionStatus.COMPLETED, ExecutionStatus.DEGRADED]
        assert result.total_cities == 2  # Helsinki and Espoo
        assert len(result.city_results) == 2
        
        # Verify scraper was called for each enabled city
        assert mock_scraper.get_all_listing_summaries.call_count == 2
        
        # Verify database save was called for each city
        assert mock_db_instance.save_listings.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])