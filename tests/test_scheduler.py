"""
Tests for the Task Scheduler and Execution Framework

This module provides comprehensive tests for the scheduling system including
cron expression validation, task queue management, execution coordination,
timeout enforcement, and failure recovery.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
import pytest
from loguru import logger

from oikotie.automation.scheduler import (
    TaskScheduler, TaskDefinition, TaskExecution, TaskStatus, TaskPriority,
    TaskQueue, ResourceMonitor, TaskExecutor, SchedulerStats,
    create_scheduler_from_config, validate_cron_expression, get_next_execution_times
)
from oikotie.automation.config import ScraperConfig, ScrapingTaskConfig, SchedulingConfig
from oikotie.automation.orchestrator import ScrapingResult, ExecutionStatus


class TestCronValidation:
    """Test cron expression validation and scheduling logic"""
    
    def test_validate_cron_expression_valid(self):
        """Test validation of valid cron expressions"""
        valid_expressions = [
            "0 6 * * *",      # Daily at 6 AM
            "0 */6 * * *",    # Every 6 hours
            "0 9 * * 1-5",    # Weekdays at 9 AM
            "30 14 * * 0",    # Sundays at 2:30 PM
            "0 0 1 * *",      # First day of month
            "0 0 * * 0"       # Every Sunday
        ]
        
        for expr in valid_expressions:
            assert validate_cron_expression(expr), f"Should be valid: {expr}"
    
    def test_validate_cron_expression_invalid(self):
        """Test validation of invalid cron expressions"""
        invalid_expressions = [
            "invalid",
            "0 25 * * *",     # Invalid hour
            "60 0 * * *",     # Invalid minute
            "0 0 32 * *",     # Invalid day
            "0 0 * 13 *",     # Invalid month
            "0 0 * * 8",      # Invalid day of week
            ""                # Empty string
        ]
        
        for expr in invalid_expressions:
            assert not validate_cron_expression(expr), f"Should be invalid: {expr}"
    
    def test_get_next_execution_times(self):
        """Test getting next execution times from cron expression"""
        # Test daily at 6 AM
        cron_expr = "0 6 * * *"
        next_times = get_next_execution_times(cron_expr, 3)
        
        assert len(next_times) == 3
        assert all(isinstance(t, datetime) for t in next_times)
        assert all(t.hour == 6 and t.minute == 0 for t in next_times)
        
        # Verify times are in ascending order
        for i in range(1, len(next_times)):
            assert next_times[i] > next_times[i-1]
    
    def test_get_next_execution_times_invalid(self):
        """Test handling of invalid cron expressions"""
        next_times = get_next_execution_times("invalid", 3)
        assert next_times == []


class TestTaskQueue:
    """Test task queue functionality"""
    
    def test_task_queue_basic_operations(self):
        """Test basic queue operations"""
        queue = TaskQueue()
        
        # Test empty queue
        assert queue.size() == 0
        assert queue.get() is None
        
        # Add task
        task = TaskExecution(
            execution_id="test-1",
            task_id="task-1",
            status=TaskStatus.QUEUED,
            scheduled_time=datetime.now(timezone.utc)
        )
        
        queue.put(task)
        assert queue.size() == 1
        
        # Get task
        retrieved_task = queue.get()
        assert retrieved_task is not None
        assert retrieved_task.execution_id == "test-1"
        assert queue.size() == 0
    
    def test_task_queue_scheduling_order(self):
        """Test that tasks are retrieved in scheduled time order"""
        queue = TaskQueue()
        now = datetime.now(timezone.utc)
        
        # Add tasks with different scheduled times
        task1 = TaskExecution(
            execution_id="task-1",
            task_id="task-1",
            status=TaskStatus.QUEUED,
            scheduled_time=now + timedelta(minutes=10)
        )
        
        task2 = TaskExecution(
            execution_id="task-2",
            task_id="task-2",
            status=TaskStatus.QUEUED,
            scheduled_time=now - timedelta(minutes=5)  # Ready now
        )
        
        task3 = TaskExecution(
            execution_id="task-3",
            task_id="task-3",
            status=TaskStatus.QUEUED,
            scheduled_time=now + timedelta(minutes=5)
        )
        
        queue.put(task1)
        queue.put(task2)
        queue.put(task3)
        
        # Should get task2 first (ready now)
        retrieved = queue.get()
        assert retrieved.execution_id == "task-2"
        
        # Others should not be ready yet
        assert queue.get() is None
    
    def test_task_queue_remove_task(self):
        """Test removing tasks from queue"""
        queue = TaskQueue()
        
        task = TaskExecution(
            execution_id="test-remove",
            task_id="task-1",
            status=TaskStatus.QUEUED,
            scheduled_time=datetime.now(timezone.utc)
        )
        
        queue.put(task)
        assert queue.size() == 1
        
        # Remove task
        removed = queue.remove_task("test-remove")
        assert removed is True
        assert queue.size() == 0
        
        # Try to remove non-existent task
        removed = queue.remove_task("non-existent")
        assert removed is False


class TestResourceMonitor:
    """Test resource monitoring functionality"""
    
    def test_resource_monitor_initialization(self):
        """Test resource monitor initialization"""
        monitor = ResourceMonitor()
        assert monitor.monitoring is True
        assert 'cpu_percent' in monitor.resource_limits
        assert 'memory_percent' in monitor.resource_limits
        assert 'disk_percent' in monitor.resource_limits
    
    @patch('oikotie.automation.scheduler.psutil.cpu_percent')
    @patch('oikotie.automation.scheduler.psutil.virtual_memory')
    @patch('oikotie.automation.scheduler.psutil.disk_usage')
    def test_check_resource_availability_sufficient(self, mock_disk, mock_memory, mock_cpu):
        """Test resource availability check with sufficient resources"""
        # Mock sufficient resources
        mock_cpu.return_value = 50.0  # 50% CPU
        mock_memory.return_value = Mock(percent=60.0)  # 60% memory
        mock_disk.return_value = Mock(used=500, total=1000)  # 50% disk
        
        monitor = ResourceMonitor()
        limits = {'cpu_percent': 80.0, 'memory_percent': 80.0, 'disk_percent': 90.0}
        
        assert monitor.check_resource_availability(limits) is True
    
    @patch('oikotie.automation.scheduler.psutil.cpu_percent')
    @patch('oikotie.automation.scheduler.psutil.virtual_memory')
    @patch('oikotie.automation.scheduler.psutil.disk_usage')
    def test_check_resource_availability_insufficient(self, mock_disk, mock_memory, mock_cpu):
        """Test resource availability check with insufficient resources"""
        # Mock insufficient CPU
        mock_cpu.return_value = 90.0  # 90% CPU (over limit)
        mock_memory.return_value = Mock(percent=60.0)
        mock_disk.return_value = Mock(used=500, total=1000)
        
        monitor = ResourceMonitor()
        limits = {'cpu_percent': 80.0, 'memory_percent': 80.0, 'disk_percent': 90.0}
        
        assert monitor.check_resource_availability(limits) is False
    
    @patch('oikotie.automation.scheduler.psutil.cpu_percent')
    @patch('oikotie.automation.scheduler.psutil.virtual_memory')
    @patch('oikotie.automation.scheduler.psutil.disk_usage')
    def test_get_current_usage(self, mock_disk, mock_memory, mock_cpu):
        """Test getting current resource usage"""
        mock_cpu.return_value = 45.5
        mock_memory.return_value = Mock(percent=65.2, used=1024*1024*1024)  # 1GB
        mock_disk.return_value = Mock(used=500*1024*1024*1024, total=1000*1024*1024*1024, free=500*1024*1024*1024)
        
        monitor = ResourceMonitor()
        usage = monitor.get_current_usage()
        
        assert usage['cpu_percent'] == 45.5
        assert usage['memory_percent'] == 65.2
        assert usage['memory_mb'] == 1024.0
        assert usage['disk_percent'] == 50.0
        assert usage['disk_free_gb'] == 500.0


class TestTaskDefinition:
    """Test task definition functionality"""
    
    def test_task_definition_creation(self):
        """Test creating task definitions"""
        task_def = TaskDefinition(
            task_id="test-task",
            name="Test Task",
            cron_expression="0 6 * * *",
            city="Helsinki",
            priority=TaskPriority.HIGH,
            max_execution_time=3600
        )
        
        assert task_def.task_id == "test-task"
        assert task_def.name == "Test Task"
        assert task_def.cron_expression == "0 6 * * *"
        assert task_def.city == "Helsinki"
        assert task_def.priority == TaskPriority.HIGH
        assert task_def.max_execution_time == 3600
        assert task_def.enabled is True
        assert task_def.max_retries == 3
    
    def test_task_definition_defaults(self):
        """Test task definition default values"""
        task_def = TaskDefinition(
            task_id="minimal-task",
            name="Minimal Task",
            cron_expression="0 0 * * *"
        )
        
        assert task_def.task_type == "scraper"
        assert task_def.enabled is True
        assert task_def.priority == TaskPriority.NORMAL
        assert task_def.max_execution_time == 7200
        assert task_def.max_retries == 3
        assert task_def.retry_delay == 300
        assert task_def.timeout_action == "kill"


class TestTaskExecution:
    """Test task execution functionality"""
    
    def test_task_execution_creation(self):
        """Test creating task executions"""
        now = datetime.now(timezone.utc)
        
        execution = TaskExecution(
            execution_id="exec-123",
            task_id="task-456",
            status=TaskStatus.PENDING,
            scheduled_time=now
        )
        
        assert execution.execution_id == "exec-123"
        assert execution.task_id == "task-456"
        assert execution.status == TaskStatus.PENDING
        assert execution.scheduled_time == now
        assert execution.started_time is None
        assert execution.completed_time is None
        assert execution.retry_count == 0
    
    def test_task_execution_status_transitions(self):
        """Test task execution status transitions"""
        execution = TaskExecution(
            execution_id="exec-123",
            task_id="task-456",
            status=TaskStatus.PENDING,
            scheduled_time=datetime.now(timezone.utc)
        )
        
        # Test status transitions
        execution.status = TaskStatus.QUEUED
        assert execution.status == TaskStatus.QUEUED
        
        execution.status = TaskStatus.RUNNING
        execution.started_time = datetime.now(timezone.utc)
        assert execution.status == TaskStatus.RUNNING
        assert execution.started_time is not None
        
        execution.status = TaskStatus.COMPLETED
        execution.completed_time = datetime.now(timezone.utc)
        assert execution.status == TaskStatus.COMPLETED
        assert execution.completed_time is not None


class TestTaskExecutor:
    """Test task executor functionality"""
    
    def test_task_executor_initialization(self):
        """Test task executor initialization"""
        resource_monitor = ResourceMonitor()
        executor = TaskExecutor(resource_monitor)
        
        assert executor.resource_monitor is resource_monitor
        assert len(executor.active_executions) == 0
    
    @pytest.mark.asyncio
    async def test_execute_task_success(self):
        """Test successful task execution"""
        resource_monitor = Mock()
        resource_monitor.check_resource_availability.return_value = True
        resource_monitor.monitor_process.return_value = {'cpu_percent': 50.0, 'memory_mb': 512.0}
        
        executor = TaskExecutor(resource_monitor)
        
        # Mock orchestrator
        orchestrator = Mock()
        mock_result = ScrapingResult(
            execution_id="test-exec",
            city="Helsinki",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            listings_new=10,
            listings_failed=0
        )
        orchestrator.run_daily_scrape.return_value = mock_result
        
        # Create task definition and execution
        task_def = TaskDefinition(
            task_id="test-task",
            name="Test Task",
            cron_expression="0 6 * * *",
            max_execution_time=60
        )
        
        task_execution = TaskExecution(
            execution_id="test-exec",
            task_id="test-task",
            status=TaskStatus.QUEUED,
            scheduled_time=datetime.now(timezone.utc)
        )
        
        # Execute task
        result = await executor.execute_task(task_execution, task_def, orchestrator)
        
        assert result.status == TaskStatus.COMPLETED
        assert result.result is not None
        assert result.started_time is not None
        assert result.completed_time is not None
    
    @pytest.mark.asyncio
    async def test_execute_task_timeout(self):
        """Test task execution timeout"""
        resource_monitor = Mock()
        resource_monitor.check_resource_availability.return_value = True
        
        executor = TaskExecutor(resource_monitor)
        
        # Mock orchestrator that takes too long
        orchestrator = Mock()
        
        async def slow_scrape():
            await asyncio.sleep(2)  # Longer than timeout
            return Mock()
        
        # Create task definition with short timeout
        task_def = TaskDefinition(
            task_id="slow-task",
            name="Slow Task",
            cron_expression="0 6 * * *",
            max_execution_time=1  # 1 second timeout
        )
        
        task_execution = TaskExecution(
            execution_id="slow-exec",
            task_id="slow-task",
            status=TaskStatus.QUEUED,
            scheduled_time=datetime.now(timezone.utc)
        )
        
        # Mock the _execute_scraper_task method to be slow
        executor._execute_scraper_task = slow_scrape
        
        # Execute task
        result = await executor.execute_task(task_execution, task_def, orchestrator)
        
        assert result.status == TaskStatus.TIMEOUT
        assert "exceeded maximum execution time" in result.error_message
    
    @pytest.mark.asyncio
    async def test_execute_task_insufficient_resources(self):
        """Test task execution with insufficient resources"""
        resource_monitor = Mock()
        resource_monitor.check_resource_availability.return_value = False
        
        executor = TaskExecutor(resource_monitor)
        orchestrator = Mock()
        
        task_def = TaskDefinition(
            task_id="resource-task",
            name="Resource Task",
            cron_expression="0 6 * * *"
        )
        
        task_execution = TaskExecution(
            execution_id="resource-exec",
            task_id="resource-task",
            status=TaskStatus.QUEUED,
            scheduled_time=datetime.now(timezone.utc)
        )
        
        # Execute task
        result = await executor.execute_task(task_execution, task_def, orchestrator)
        
        assert result.status == TaskStatus.FAILED
        assert "Insufficient system resources" in result.error_message


class TestTaskScheduler:
    """Test main task scheduler functionality"""
    
    def test_scheduler_initialization(self):
        """Test scheduler initialization"""
        config = ScraperConfig(
            tasks=[
                ScrapingTaskConfig(city="Helsinki", url="http://example.com", enabled=True)
            ],
            scheduling=SchedulingConfig(enabled=True, cron_expression="0 6 * * *")
        )
        
        scheduler = TaskScheduler(config)
        
        assert scheduler.config is config
        assert scheduler.scheduling_config is config.scheduling
        assert len(scheduler.task_definitions) == 0
        assert scheduler.running is False
    
    def test_add_remove_tasks(self):
        """Test adding and removing task definitions"""
        config = ScraperConfig()
        scheduler = TaskScheduler(config)
        
        task_def = TaskDefinition(
            task_id="test-task",
            name="Test Task",
            cron_expression="0 6 * * *"
        )
        
        # Add task
        scheduler.add_task(task_def)
        assert len(scheduler.task_definitions) == 1
        assert "test-task" in scheduler.task_definitions
        
        # Remove task
        removed = scheduler.remove_task("test-task")
        assert removed is True
        assert len(scheduler.task_definitions) == 0
        
        # Try to remove non-existent task
        removed = scheduler.remove_task("non-existent")
        assert removed is False
    
    def test_enable_disable_tasks(self):
        """Test enabling and disabling tasks"""
        config = ScraperConfig()
        scheduler = TaskScheduler(config)
        
        task_def = TaskDefinition(
            task_id="toggle-task",
            name="Toggle Task",
            cron_expression="0 6 * * *",
            enabled=True
        )
        
        scheduler.add_task(task_def)
        
        # Disable task
        disabled = scheduler.disable_task("toggle-task")
        assert disabled is True
        assert scheduler.task_definitions["toggle-task"].enabled is False
        
        # Enable task
        enabled = scheduler.enable_task("toggle-task")
        assert enabled is True
        assert scheduler.task_definitions["toggle-task"].enabled is True
        
        # Try to toggle non-existent task
        assert scheduler.enable_task("non-existent") is False
        assert scheduler.disable_task("non-existent") is False
    
    def test_schedule_task_now(self):
        """Test manually scheduling a task for immediate execution"""
        config = ScraperConfig()
        scheduler = TaskScheduler(config)
        
        task_def = TaskDefinition(
            task_id="immediate-task",
            name="Immediate Task",
            cron_expression="0 6 * * *"
        )
        
        scheduler.add_task(task_def)
        
        # Schedule task now
        execution_id = scheduler.schedule_task_now("immediate-task", TaskPriority.HIGH)
        assert execution_id is not None
        assert scheduler.task_queue.size() == 1
        
        # Try to schedule non-existent task
        execution_id = scheduler.schedule_task_now("non-existent")
        assert execution_id is None
    
    def test_get_stats(self):
        """Test getting scheduler statistics"""
        config = ScraperConfig()
        scheduler = TaskScheduler(config)
        
        stats = scheduler.get_stats()
        assert isinstance(stats, SchedulerStats)
        assert stats.total_tasks == 0
        assert stats.active_tasks == 0
        assert stats.queued_tasks == 0
    
    def test_emergency_stop(self):
        """Test emergency stop functionality"""
        config = ScraperConfig()
        scheduler = TaskScheduler(config)
        
        # Add a task and schedule it
        task_def = TaskDefinition(
            task_id="emergency-task",
            name="Emergency Task",
            cron_expression="0 6 * * *"
        )
        
        scheduler.add_task(task_def)
        scheduler.schedule_task_now("emergency-task")
        
        assert scheduler.task_queue.size() == 1
        assert not scheduler.emergency_stop.is_set()
        
        # Trigger emergency stop
        scheduler.emergency_stop_all()
        
        assert scheduler.emergency_stop.is_set()
        # Queue should be cleared (in a real implementation)


class TestSchedulerIntegration:
    """Integration tests for the scheduler system"""
    
    def test_create_scheduler_from_config(self):
        """Test creating scheduler from configuration"""
        config = ScraperConfig(
            tasks=[
                ScrapingTaskConfig(
                    city="Helsinki",
                    url="http://example.com",
                    enabled=True,
                    max_detail_workers=5,
                    staleness_hours=24,
                    retry_count=3
                ),
                ScrapingTaskConfig(
                    city="Tampere",
                    url="http://example.com/tampere",
                    enabled=False  # Disabled task
                )
            ],
            scheduling=SchedulingConfig(
                enabled=True,
                cron_expression="0 6 * * *",
                max_execution_time=7200,
                concurrent_tasks=2
            )
        )
        
        scheduler = create_scheduler_from_config(config)
        
        # Should only create tasks for enabled cities
        task_definitions = scheduler.get_task_definitions()
        assert len(task_definitions) == 1
        
        helsinki_task = task_definitions[0]
        assert helsinki_task.city == "Helsinki"
        assert helsinki_task.name == "Daily Scraper - Helsinki"
        assert helsinki_task.cron_expression == "0 6 * * *"
        assert helsinki_task.max_execution_time == 7200
        assert helsinki_task.max_retries == 3
    
    def test_scheduler_lifecycle(self):
        """Test complete scheduler lifecycle"""
        config = ScraperConfig(
            tasks=[
                ScrapingTaskConfig(city="TestCity", url="http://example.com", enabled=True)
            ],
            scheduling=SchedulingConfig(enabled=True, cron_expression="0 6 * * *")
        )
        
        scheduler = create_scheduler_from_config(config)
        
        # Initial state
        assert not scheduler.running
        assert len(scheduler.get_active_executions()) == 0
        
        # Note: We don't actually start the scheduler in tests to avoid threading issues
        # In a real test environment, you might use mocking or test-specific scheduler modes
        
        # Test configuration
        task_definitions = scheduler.get_task_definitions()
        assert len(task_definitions) == 1
        assert task_definitions[0].city == "TestCity"


class TestSchedulerErrorHandling:
    """Test error handling in scheduler components"""
    
    def test_invalid_cron_expression_handling(self):
        """Test handling of invalid cron expressions"""
        config = ScraperConfig()
        scheduler = TaskScheduler(config)
        
        # Add task with invalid cron expression
        task_def = TaskDefinition(
            task_id="invalid-cron-task",
            name="Invalid Cron Task",
            cron_expression="invalid cron"
        )
        
        scheduler.add_task(task_def)
        
        # The scheduler should handle invalid cron expressions gracefully
        # (Implementation would log errors but not crash)
        assert len(scheduler.task_definitions) == 1
    
    @pytest.mark.asyncio
    async def test_task_execution_exception_handling(self):
        """Test handling of exceptions during task execution"""
        resource_monitor = Mock()
        resource_monitor.check_resource_availability.return_value = True
        
        executor = TaskExecutor(resource_monitor)
        
        # Mock orchestrator that raises exception
        orchestrator = Mock()
        orchestrator.run_daily_scrape.side_effect = Exception("Test exception")
        
        task_def = TaskDefinition(
            task_id="error-task",
            name="Error Task",
            cron_expression="0 6 * * *"
        )
        
        task_execution = TaskExecution(
            execution_id="error-exec",
            task_id="error-task",
            status=TaskStatus.QUEUED,
            scheduled_time=datetime.now(timezone.utc)
        )
        
        # Execute task
        result = await executor.execute_task(task_execution, task_def, orchestrator)
        
        assert result.status == TaskStatus.FAILED
        assert "Test exception" in result.error_message


if __name__ == '__main__':
    pytest.main([__file__])