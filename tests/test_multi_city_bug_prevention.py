"""
Bug Prevention Tests for Multi-City Automation System

This module provides comprehensive bug prevention tests that must pass before
running expensive multi-city automation operations (>10 minutes runtime).
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from oikotie.automation.multi_city_orchestrator import (
    MultiCityScraperOrchestrator,
    CityConfig,
    create_multi_city_orchestrator
)
from oikotie.automation.circuit_breaker import CircuitBreaker, CircuitBreakerState
from oikotie.automation.audit_logger import AuditLogger, AuditEvent, AuditEventType


class TestConfigurationValidation:
    """Test configuration loading and validation."""
    
    def test_valid_configuration_loading(self):
        """Test loading valid configuration file."""
        config = {
            "tasks": [
                {
                    "city": "Helsinki",
                    "enabled": True,
                    "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
                    "max_detail_workers": 5,
                    "rate_limit_seconds": 1.0
                }
            ],
            "global_settings": {
                "database_path": "data/real_estate.duckdb"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            config_path = f.name
        
        try:
            with patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager'):
                with patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager'):
                    with patch('oikotie.automation.multi_city_orchestrator.AuditLogger'):
                        orchestrator = MultiCityScraperOrchestrator(
                            config_path=config_path,
                            enable_cluster_coordination=False
                        )
                        
                        assert len(orchestrator.city_configs) == 1
                        assert orchestrator.city_configs[0].city == "Helsinki"
                        assert orchestrator.city_configs[0].enabled is True
        finally:
            Path(config_path).unlink()
    
    def test_missing_configuration_file(self):
        """Test handling of missing configuration file."""
        with patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager'):
            with patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager'):
                with patch('oikotie.automation.multi_city_orchestrator.AuditLogger'):
                    orchestrator = MultiCityScraperOrchestrator(
                        config_path="nonexistent_config.json",
                        enable_cluster_coordination=False
                    )
                    
                    # Should handle gracefully with empty configuration
                    assert len(orchestrator.city_configs) == 0
    
    def test_invalid_json_configuration(self):
        """Test handling of invalid JSON configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            config_path = f.name
        
        try:
            with patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager'):
                with patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager'):
                    with patch('oikotie.automation.multi_city_orchestrator.AuditLogger'):
                        orchestrator = MultiCityScraperOrchestrator(
                            config_path=config_path,
                            enable_cluster_coordination=False
                        )
                        
                        # Should handle gracefully with empty configuration
                        assert len(orchestrator.city_configs) == 0
        finally:
            Path(config_path).unlink()
    
    def test_empty_tasks_configuration(self):
        """Test handling of configuration with empty tasks."""
        config = {
            "tasks": [],
            "global_settings": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            config_path = f.name
        
        try:
            with patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager'):
                with patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager'):
                    with patch('oikotie.automation.multi_city_orchestrator.AuditLogger'):
                        orchestrator = MultiCityScraperOrchestrator(
                            config_path=config_path,
                            enable_cluster_coordination=False
                        )
                        
                        assert len(orchestrator.city_configs) == 0
                        
                        # Should complete gracefully with no cities
                        result = orchestrator.run_daily_automation()
                        assert result.total_cities == 0
                        assert result.status.value in ['completed']
        finally:
            Path(config_path).unlink()


class TestCircuitBreakerBasicFunctionality:
    """Test basic circuit breaker functionality."""
    
    def test_circuit_breaker_creation(self):
        """Test circuit breaker can be created with default parameters."""
        cb = CircuitBreaker()
        
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60
        assert cb.success_threshold == 3
    
    def test_circuit_breaker_state_transitions(self):
        """Test basic state transitions work correctly."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        # Start in closed state
        assert cb.state == CircuitBreakerState.CLOSED
        
        # Record failures to trip circuit
        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED
        
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        
        # Reset should return to closed
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_circuit_breaker_metrics(self):
        """Test circuit breaker metrics are collected correctly."""
        cb = CircuitBreaker()
        
        cb.record_success()
        cb.record_failure()
        
        metrics = cb.get_metrics()
        
        assert metrics.success_count == 1
        assert metrics.failure_count == 1
        assert metrics.total_requests == 2
        assert metrics.state == CircuitBreakerState.CLOSED


class TestAuditLoggerBasicFunctionality:
    """Test basic audit logger functionality."""
    
    def test_audit_logger_creation(self):
        """Test audit logger can be created."""
        audit_logger = AuditLogger(log_to_file=False)
        
        assert audit_logger is not None
        assert audit_logger.log_to_file is False
    
    def test_audit_event_creation(self):
        """Test audit events can be created."""
        event = AuditEvent(
            event_type=AuditEventType.AUTOMATION_START,
            execution_id="test-123",
            city="Helsinki"
        )
        
        assert event.event_type == AuditEventType.AUTOMATION_START
        assert event.execution_id == "test-123"
        assert event.city == "Helsinki"
        assert event.timestamp is not None
    
    def test_audit_event_logging(self):
        """Test audit events can be logged without errors."""
        audit_logger = AuditLogger(log_to_file=False)
        
        event = AuditEvent(
            event_type=AuditEventType.AUTOMATION_START,
            execution_id="test-123"
        )
        
        # Should not raise any exceptions
        audit_logger.log_event(event)
    
    def test_execution_context_creation(self):
        """Test execution context can be created."""
        audit_logger = AuditLogger(log_to_file=False)
        
        context = audit_logger.create_execution_context("test-execution")
        
        assert context.execution_id == "test-execution"
        assert context.audit_logger == audit_logger


class TestDatabaseConnectivity:
    """Test database connectivity and basic operations."""
    
    @patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager')
    def test_database_manager_initialization(self, mock_db_manager):
        """Test database manager can be initialized."""
        mock_db_instance = Mock()
        mock_db_manager.return_value = mock_db_instance
        
        with patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager'):
            with patch('oikotie.automation.multi_city_orchestrator.AuditLogger'):
                orchestrator = MultiCityScraperOrchestrator(
                    config_path="test_config.json",
                    enable_cluster_coordination=False
                )
                
                assert orchestrator.db_manager == mock_db_instance
                mock_db_manager.assert_called_once()


class TestRedisConnectivity:
    """Test Redis connectivity for cluster coordination."""
    
    @patch('redis.from_url')
    def test_redis_connection_success(self, mock_redis_from_url):
        """Test successful Redis connection."""
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_from_url.return_value = mock_redis_client
        
        with patch('oikotie.automation.multi_city_orchestrator.ClusterCoordinator'):
            with patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager'):
                with patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager'):
                    with patch('oikotie.automation.multi_city_orchestrator.AuditLogger'):
                        orchestrator = MultiCityScraperOrchestrator(
                            config_path="test_config.json",
                            redis_url="redis://localhost:6379",
                            enable_cluster_coordination=True
                        )
                        
                        # Should attempt to create cluster coordinator
                        assert orchestrator.enable_cluster_coordination is True
    
    @patch('redis.from_url')
    def test_redis_connection_failure_graceful_degradation(self, mock_redis_from_url):
        """Test graceful degradation when Redis connection fails."""
        mock_redis_from_url.side_effect = Exception("Redis connection failed")
        
        with patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager'):
            with patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager'):
                with patch('oikotie.automation.multi_city_orchestrator.AuditLogger'):
                    orchestrator = MultiCityScraperOrchestrator(
                        config_path="test_config.json",
                        redis_url="redis://localhost:6379",
                        enable_cluster_coordination=True
                    )
                    
                    # Should gracefully disable cluster coordination
                    assert orchestrator.enable_cluster_coordination is False
                    assert orchestrator.cluster_coordinator is None


class TestFactoryFunction:
    """Test factory function for creating orchestrator."""
    
    @patch('oikotie.automation.multi_city_orchestrator.MultiCityScraperOrchestrator')
    def test_create_multi_city_orchestrator_basic(self, mock_orchestrator_class):
        """Test factory function creates orchestrator with basic parameters."""
        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        result = create_multi_city_orchestrator()
        
        assert result == mock_orchestrator
        mock_orchestrator_class.assert_called_once_with(
            config_path='config/config.json',
            redis_url=None,
            enable_cluster_coordination=True
        )
    
    @patch('oikotie.automation.multi_city_orchestrator.MultiCityScraperOrchestrator')
    def test_create_multi_city_orchestrator_with_parameters(self, mock_orchestrator_class):
        """Test factory function creates orchestrator with custom parameters."""
        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        result = create_multi_city_orchestrator(
            config_path="custom_config.json",
            redis_url="redis://custom:6379",
            enable_cluster_coordination=False
        )
        
        assert result == mock_orchestrator
        mock_orchestrator_class.assert_called_once_with(
            config_path="custom_config.json",
            redis_url="redis://custom:6379",
            enable_cluster_coordination=False
        )


class TestThreadSafety:
    """Test thread safety of critical components."""
    
    def test_circuit_breaker_thread_safety(self):
        """Test circuit breaker is thread-safe."""
        import threading
        import time
        
        cb = CircuitBreaker(failure_threshold=10)
        results = []
        
        def record_operations():
            for _ in range(50):
                cb.record_success()
                cb.record_failure()
                time.sleep(0.001)  # Small delay to encourage race conditions
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=record_operations)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify final state is consistent
        metrics = cb.get_metrics()
        assert metrics.total_requests == 500  # 5 threads * 50 operations * 2 (success + failure)
        # Note: failure_count tracks consecutive failures, not total failures
        # So success_count + failure_count may not equal total_requests
        assert metrics.success_count > 0
        assert metrics.total_requests > 0
    
    def test_orchestrator_execution_lock(self):
        """Test orchestrator execution lock prevents concurrent executions."""
        config = {
            "tasks": [
                {
                    "city": "Helsinki",
                    "enabled": True,
                    "url": "https://example.com/helsinki"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            config_path = f.name
        
        try:
            with patch('oikotie.automation.multi_city_orchestrator.EnhancedDatabaseManager'):
                with patch('oikotie.automation.multi_city_orchestrator.DataGovernanceManager'):
                    with patch('oikotie.automation.multi_city_orchestrator.AuditLogger'):
                        orchestrator = MultiCityScraperOrchestrator(
                            config_path=config_path,
                            enable_cluster_coordination=False
                        )
                        
                        # Initially no execution
                        assert orchestrator.get_execution_status() is None
                        
                        # Mock execution to check status during execution
                        def mock_execute_cities_sequentially(cities, execution_id):
                            assert orchestrator.get_execution_status() == execution_id
                            return []
                        
                        with patch.object(orchestrator, '_execute_cities_sequentially', 
                                        side_effect=mock_execute_cities_sequentially):
                            result = orchestrator.run_daily_automation()
                            
                            # After execution, status should be cleared
                            assert orchestrator.get_execution_status() is None
        finally:
            Path(config_path).unlink()


def run_bug_prevention_tests():
    """
    Run all bug prevention tests and return results.
    
    Returns:
        bool: True if all tests pass, False otherwise
    """
    import subprocess
    import sys
    
    try:
        # Run pytest on this file
        result = subprocess.run([
            sys.executable, '-m', 'pytest', __file__, '-v', '--tb=short'
        ], capture_output=True, text=True)
        
        print("Bug Prevention Test Results:")
        print("=" * 50)
        print(result.stdout)
        
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Failed to run bug prevention tests: {e}")
        return False


if __name__ == "__main__":
    # Run bug prevention tests when executed directly
    success = run_bug_prevention_tests()
    
    if success:
        print("\n✅ All bug prevention tests passed!")
        print("Multi-city automation system is ready for expensive operations.")
    else:
        print("\n❌ Bug prevention tests failed!")
        print("Do not run expensive operations until issues are resolved.")
        exit(1)