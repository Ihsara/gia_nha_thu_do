"""
Integration tests for missing methods to achieve 100% test compatibility.

This test suite specifically validates the three missing methods:
1. plan_execution() in EnhancedScraperOrchestrator
2. validate_schedule() in TaskScheduler  
3. get_current_system_metrics() in ComprehensiveMonitor
"""

import pytest
import json
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from oikotie.automation.orchestrator import EnhancedScraperOrchestrator, ScraperConfig
from oikotie.automation.scheduler import TaskScheduler, TaskDefinition, TaskPriority
from oikotie.automation.monitoring import ComprehensiveMonitor
from oikotie.automation.config import ScraperConfig as MainConfig, SchedulingConfig
from oikotie.database.manager import EnhancedDatabaseManager


# Test fixtures
@pytest.fixture
def temp_db_path():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)

@pytest.fixture
def db_manager(temp_db_path):
    """Create database manager for testing."""
    return EnhancedDatabaseManager(db_path=temp_db_path)

@pytest.fixture
def orchestrator_config():
    """Create orchestrator configuration for testing."""
    return ScraperConfig(
        city="Helsinki",
        url="https://www.oikotie.fi/myytavat-asunnot/helsinki",
        listing_limit=10,
        max_detail_workers=2,
        staleness_threshold_hours=24,
        retry_limit=3,
        retry_delay_hours=1,
        batch_size=50,
        enable_smart_deduplication=True,
        enable_performance_monitoring=True,
        headless_browser=True
    )

@pytest.fixture
def scheduler_config():
    """Create scheduler configuration for testing."""
    return MainConfig(
        tasks=[],
        scheduling=SchedulingConfig(
            enabled=True,
            concurrent_tasks=2,
            max_queue_size=100,
            health_check_interval=60,
            metrics_retention_days=30
        )
    )

@pytest.fixture
def task_definition():
    """Create task definition for testing."""
    return TaskDefinition(
        task_id="test_task_001",
        name="Test Helsinki Scraper",
        cron_expression="0 9 * * *",  # Daily at 9 AM
        task_type="scraper",
        city="Helsinki",
        enabled=True,
        priority=TaskPriority.NORMAL,
        max_execution_time=3600,  # 1 hour
        max_retries=3,
        retry_delay=300,  # 5 minutes
        timeout_action="graceful",
        resource_limits={
            'max_memory_mb': 2048,
            'max_cpu_percent': 80
        },
        metadata={'test': True}
    )


class TestEnhancedScraperOrchestratorPlanExecution:
    """Test plan_execution() method in EnhancedScraperOrchestrator."""
    
    def test_plan_execution_with_city_parameter(self, orchestrator_config, db_manager):
        """Test plan_execution with explicit city parameter."""
        orchestrator = EnhancedScraperOrchestrator(orchestrator_config, db_manager)
        
        # Mock the URL discovery to avoid actual web scraping
        with patch.object(orchestrator, '_discover_listing_urls') as mock_discover:
            mock_discover.return_value = [
                'https://www.oikotie.fi/kohde/12345',
                'https://www.oikotie.fi/kohde/12346',
                'https://www.oikotie.fi/kohde/12347'
            ]
            
            # Mock deduplication manager
            with patch.object(orchestrator.deduplication_manager, 'analyze_urls') as mock_analyze:
                mock_analyze.return_value = Mock(
                    total_urls=3,
                    urls_to_process=2,
                    urls_to_skip=1
                )
                
                with patch.object(orchestrator.deduplication_manager, 'get_urls_to_process') as mock_get_urls:
                    mock_get_urls.return_value = [
                        'https://www.oikotie.fi/kohde/12345',
                        'https://www.oikotie.fi/kohde/12346'
                    ]
                    
                    # Mock listing manager
                    with patch.object(orchestrator.listing_manager, 'create_processing_plan') as mock_plan:
                        mock_batch = Mock()
                        mock_batch.batch_id = 'batch_001'
                        mock_batch.priority = Mock()
                        mock_batch.priority.name = 'NORMAL'
                        mock_batch.urls = ['https://www.oikotie.fi/kohde/12345']
                        mock_plan.return_value = [mock_batch]
                        
                        # Test with explicit city
                        result = orchestrator.plan_execution("Tampere")
                        
                        assert result is not None
                        assert isinstance(result, dict)
                        assert result['city'] == "Tampere"
                        assert result['total_urls'] == 3
                        assert result['urls_to_process'] == 2
                        assert result['urls_to_skip'] == 1
                        assert result['processing_batches'] == 1
                        assert result['deduplication_enabled'] is True
                        assert 'estimated_execution_time_seconds' in result
                        assert 'batch_details' in result
                        assert len(result['batch_details']) == 1
    
    def test_plan_execution_without_city_parameter(self, orchestrator_config, db_manager):
        """Test plan_execution without city parameter (uses config city)."""
        orchestrator = EnhancedScraperOrchestrator(orchestrator_config, db_manager)
        
        with patch.object(orchestrator, '_discover_listing_urls') as mock_discover:
            mock_discover.return_value = ['https://www.oikotie.fi/kohde/12345']
            
            with patch.object(orchestrator.deduplication_manager, 'analyze_urls'):
                with patch.object(orchestrator.deduplication_manager, 'get_urls_to_process') as mock_get_urls:
                    mock_get_urls.return_value = ['https://www.oikotie.fi/kohde/12345']
                    
                    with patch.object(orchestrator.listing_manager, 'create_processing_plan') as mock_plan:
                        mock_plan.return_value = []
                        
                        # Test without explicit city (should use config city)
                        result = orchestrator.plan_execution()
                        
                        assert result is not None
                        assert result['city'] == orchestrator_config.city  # Should use config city
    
    def test_plan_execution_error_handling(self, orchestrator_config, db_manager):
        """Test plan_execution error handling."""
        orchestrator = EnhancedScraperOrchestrator(orchestrator_config, db_manager)
        
        # Mock an exception during URL discovery
        with patch.object(orchestrator, '_discover_listing_urls') as mock_discover:
            mock_discover.side_effect = Exception("Network error")
            
            result = orchestrator.plan_execution("TestCity")
            
            assert result is not None
            assert result['city'] == "TestCity"
            assert 'error' in result
            assert result['total_urls'] == 0
            assert result['urls_to_process'] == 0


class TestTaskSchedulerValidateSchedule:
    """Test validate_schedule() method in TaskScheduler."""
    
    def test_validate_schedule_all_tasks(self, scheduler_config, task_definition):
        """Test validate_schedule for all tasks."""
        scheduler = TaskScheduler(scheduler_config)
        scheduler.add_task(task_definition)
        
        # Add another task with invalid cron
        invalid_task = TaskDefinition(
            task_id="invalid_task",
            name="Invalid Task",
            cron_expression="invalid cron",
            task_type="scraper",
            city="Helsinki"
        )
        scheduler.add_task(invalid_task)
        
        result = scheduler.validate_schedule()
        
        assert result is not None
        assert isinstance(result, dict)
        assert 'timestamp' in result
        assert 'overall_valid' in result
        assert result['overall_valid'] is False  # Should be false due to invalid task
        assert result['tasks_validated'] == 2
        assert result['tasks_valid'] == 1
        assert result['tasks_invalid'] == 1
        assert 'validation_details' in result
        assert task_definition.task_id in result['validation_details']
        assert invalid_task.task_id in result['validation_details']
        
        # Check valid task details
        valid_details = result['validation_details'][task_definition.task_id]
        assert valid_details['valid'] is True
        assert valid_details['cron_valid'] is True
        assert 'next_execution' in valid_details
        
        # Check invalid task details
        invalid_details = result['validation_details'][invalid_task.task_id]
        assert invalid_details['valid'] is False
        assert invalid_details['cron_valid'] is False
        assert len(invalid_details['errors']) > 0
    
    def test_validate_schedule_specific_task(self, scheduler_config, task_definition):
        """Test validate_schedule for a specific task."""
        scheduler = TaskScheduler(scheduler_config)
        scheduler.add_task(task_definition)
        
        result = scheduler.validate_schedule(task_definition.task_id)
        
        assert result is not None
        assert result['tasks_validated'] == 1
        assert result['tasks_valid'] == 1
        assert result['tasks_invalid'] == 0
        assert result['overall_valid'] is True
        assert task_definition.task_id in result['validation_details']
        
        task_details = result['validation_details'][task_definition.task_id]
        assert task_details['valid'] is True
        assert task_details['cron_valid'] is True
        assert 'next_execution' in task_details
        assert 'execution_frequency' in task_details
    
    def test_validate_schedule_nonexistent_task(self, scheduler_config):
        """Test validate_schedule for nonexistent task."""
        scheduler = TaskScheduler(scheduler_config)
        
        result = scheduler.validate_schedule("nonexistent_task")
        
        assert result is not None
        assert result['tasks_validated'] == 0
        assert result['tasks_valid'] == 0
        assert result['tasks_invalid'] == 0
        assert result['overall_valid'] is True
        assert len(result['validation_details']) == 0
    
    def test_validate_single_task_resource_limits(self, scheduler_config):
        """Test validation of task resource limits."""
        scheduler = TaskScheduler(scheduler_config)
        
        # Task with invalid resource limits
        task_with_bad_limits = TaskDefinition(
            task_id="bad_limits_task",
            name="Bad Limits Task",
            cron_expression="0 9 * * *",
            task_type="scraper",
            city="Helsinki",
            resource_limits={
                'max_memory_mb': -100,  # Invalid: negative
                'max_cpu_percent': 150  # Invalid: > 100
            }
        )
        scheduler.add_task(task_with_bad_limits)
        
        result = scheduler.validate_schedule(task_with_bad_limits.task_id)
        
        task_details = result['validation_details'][task_with_bad_limits.task_id]
        assert task_details['valid'] is False
        assert len(task_details['errors']) >= 2  # Should have errors for both limits
    
    def test_validate_single_task_execution_limits(self, scheduler_config):
        """Test validation of task execution limits."""
        scheduler = TaskScheduler(scheduler_config)
        
        # Task with invalid execution limits
        task_with_bad_exec = TaskDefinition(
            task_id="bad_exec_task",
            name="Bad Execution Task",
            cron_expression="0 9 * * *",
            task_type="scraper",
            city="Helsinki",
            max_execution_time=-1,  # Invalid: negative
            max_retries=-5,  # Invalid: negative
            retry_delay=-10  # Invalid: negative
        )
        scheduler.add_task(task_with_bad_exec)
        
        result = scheduler.validate_schedule(task_with_bad_exec.task_id)
        
        task_details = result['validation_details'][task_with_bad_exec.task_id]
        assert task_details['valid'] is False
        assert len(task_details['errors']) >= 3  # Should have errors for all three limits


class TestComprehensiveMonitorGetCurrentSystemMetrics:
    """Test get_current_system_metrics() method in ComprehensiveMonitor."""
    
    def test_get_current_system_metrics_success(self, db_manager):
        """Test successful retrieval of current system metrics."""
        monitor = ComprehensiveMonitor(
            db_manager=db_manager,
            metrics_port=8081,  # Use different port to avoid conflicts
            system_monitor_interval=30
        )
        
        # Mock system monitor to return test data
        mock_system_metrics = Mock()
        mock_system_metrics.timestamp = datetime.now()
        mock_system_metrics.cpu_percent = 45.5
        mock_system_metrics.memory_percent = 60.2
        mock_system_metrics.memory_used_mb = 2048.0
        mock_system_metrics.memory_available_mb = 1024.0
        mock_system_metrics.disk_usage_percent = 75.0
        mock_system_metrics.disk_free_gb = 50.0
        mock_system_metrics.network_bytes_sent = 1000000
        mock_system_metrics.network_bytes_recv = 2000000
        mock_system_metrics.active_connections = 10
        mock_system_metrics.load_average = 1.5
        
        with patch.object(monitor.system_monitor, 'get_current_metrics') as mock_get_metrics:
            mock_get_metrics.return_value = mock_system_metrics
            
            with patch.object(monitor.health_checker, 'run_health_checks') as mock_health:
                mock_health.return_value = {
                    'overall_healthy': True,
                    'checks': {
                        'database': {'healthy': True},
                        'disk_space': {'healthy': True},
                        'memory': {'healthy': True}
                    }
                }
                
                with patch.object(monitor.system_monitor, 'get_metrics_summary') as mock_summary:
                    mock_summary.return_value = {
                        'cpu_avg': 40.0,
                        'memory_avg': 55.0,
                        'sample_count': 10
                    }
                    
                    result = monitor.get_current_system_metrics()
                    
                    assert result is not None
                    assert isinstance(result, dict)
                    assert 'timestamp' in result
                    assert 'system_metrics' in result
                    assert 'health_status' in result
                    assert 'resource_summary' in result
                    assert 'monitoring_status' in result
                    
                    # Check system metrics
                    sys_metrics = result['system_metrics']
                    assert sys_metrics['cpu_percent'] == 45.5
                    assert sys_metrics['memory_percent'] == 60.2
                    assert sys_metrics['memory_used_mb'] == 2048.0
                    
                    # Check health status
                    health_status = result['health_status']
                    assert health_status['overall_healthy'] is True
                    
                    # Check monitoring status
                    monitoring_status = result['monitoring_status']
                    assert 'system_monitor_active' in monitoring_status
                    assert 'metrics_server_active' in monitoring_status
                    assert 'prometheus_available' in monitoring_status
                    assert 'psutil_available' in monitoring_status
    
    def test_get_current_system_metrics_with_application_metrics(self, db_manager):
        """Test get_current_system_metrics with application metrics."""
        monitor = ComprehensiveMonitor(
            db_manager=db_manager,
            metrics_port=8082,
            system_monitor_interval=30
        )
        
        # Add mock metrics collector
        mock_metrics_collector = Mock()
        mock_metrics_collector.get_current_metrics.return_value = {
            'active_executions': 2,
            'total_executions': 100,
            'success_rate': 0.95
        }
        monitor.metrics_collector = mock_metrics_collector
        
        with patch.object(monitor.system_monitor, 'get_current_metrics') as mock_get_metrics:
            mock_get_metrics.return_value = Mock(
                timestamp=datetime.now(),
                cpu_percent=30.0,
                memory_percent=40.0
            )
            
            with patch.object(monitor.health_checker, 'run_health_checks') as mock_health:
                mock_health.return_value = {'overall_healthy': True}
                
                with patch.object(monitor.system_monitor, 'get_metrics_summary') as mock_summary:
                    mock_summary.return_value = {}
                    
                    result = monitor.get_current_system_metrics()
                    
                    assert 'application_metrics' in result
                    app_metrics = result['application_metrics']
                    assert app_metrics['active_executions'] == 2
                    assert app_metrics['total_executions'] == 100
                    assert app_metrics['success_rate'] == 0.95
    
    def test_get_current_system_metrics_error_handling(self, db_manager):
        """Test get_current_system_metrics error handling."""
        monitor = ComprehensiveMonitor(
            db_manager=db_manager,
            metrics_port=8083,
            system_monitor_interval=30
        )
        
        # Mock system monitor to raise exception
        with patch.object(monitor.system_monitor, 'get_current_metrics') as mock_get_metrics:
            mock_get_metrics.side_effect = Exception("System monitoring failed")
            
            result = monitor.get_current_system_metrics()
            
            assert result is not None
            assert 'error' in result
            assert 'timestamp' in result
            assert result['system_metrics'] == {}
            assert result['health_status']['overall_healthy'] is False
            assert 'error' in result['health_status']
    
    def test_get_current_system_metrics_partial_failure(self, db_manager):
        """Test get_current_system_metrics with partial component failures."""
        monitor = ComprehensiveMonitor(
            db_manager=db_manager,
            metrics_port=8084,
            system_monitor_interval=30
        )
        
        # Mock successful system metrics but failed health check
        mock_system_metrics = Mock()
        mock_system_metrics.timestamp = datetime.now()
        mock_system_metrics.cpu_percent = 25.0
        
        with patch.object(monitor.system_monitor, 'get_current_metrics') as mock_get_metrics:
            mock_get_metrics.return_value = mock_system_metrics
            
            with patch.object(monitor.health_checker, 'run_health_checks') as mock_health:
                mock_health.side_effect = Exception("Health check failed")
                
                with patch.object(monitor.system_monitor, 'get_metrics_summary') as mock_summary:
                    mock_summary.return_value = {'cpu_avg': 20.0}
                    
                    # Should not raise exception, but handle gracefully
                    result = monitor.get_current_system_metrics()
                    
                    assert result is not None
                    assert 'error' in result
                    assert result['system_metrics'] == {}  # Should be empty due to overall failure


class TestIntegrationCompatibility:
    """Integration tests to ensure all methods work together."""
    
    def test_all_missing_methods_integration(self, orchestrator_config, scheduler_config, task_definition, db_manager):
        """Test that all three missing methods work together in an integration scenario."""
        # Create all components
        orchestrator = EnhancedScraperOrchestrator(orchestrator_config, db_manager)
        scheduler = TaskScheduler(scheduler_config)
        monitor = ComprehensiveMonitor(db_manager=db_manager, metrics_port=8085)
        
        # Add task to scheduler
        scheduler.add_task(task_definition)
        
        # Mock external dependencies
        with patch.object(orchestrator, '_discover_listing_urls') as mock_discover:
            mock_discover.return_value = ['https://www.oikotie.fi/kohde/12345']
            
            with patch.object(orchestrator.deduplication_manager, 'analyze_urls'):
                with patch.object(orchestrator.deduplication_manager, 'get_urls_to_process') as mock_get_urls:
                    mock_get_urls.return_value = ['https://www.oikotie.fi/kohde/12345']
                    
                    with patch.object(orchestrator.listing_manager, 'create_processing_plan') as mock_plan:
                        mock_plan.return_value = []
                        
                        with patch.object(monitor.system_monitor, 'get_current_metrics') as mock_metrics:
                            mock_metrics.return_value = Mock(timestamp=datetime.now(), cpu_percent=30.0)
                            
                            with patch.object(monitor.health_checker, 'run_health_checks') as mock_health:
                                mock_health.return_value = {'overall_healthy': True}
                                
                                with patch.object(monitor.system_monitor, 'get_metrics_summary') as mock_summary:
                                    mock_summary.return_value = {}
                                    
                                    # Test all three methods
                                    plan_result = orchestrator.plan_execution()
                                    schedule_result = scheduler.validate_schedule()
                                    metrics_result = monitor.get_current_system_metrics()
                                    
                                    # Verify all methods returned valid results
                                    assert plan_result is not None
                                    assert isinstance(plan_result, dict)
                                    assert 'city' in plan_result
                                    
                                    assert schedule_result is not None
                                    assert isinstance(schedule_result, dict)
                                    assert 'overall_valid' in schedule_result
                                    
                                    assert metrics_result is not None
                                    assert isinstance(metrics_result, dict)
                                    assert 'timestamp' in metrics_result
                                    
                                    # Verify integration works
                                    assert plan_result['city'] == orchestrator_config.city
                                    assert schedule_result['tasks_validated'] == 1
                                    assert 'system_metrics' in metrics_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])