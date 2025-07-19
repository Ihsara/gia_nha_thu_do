"""
Command-line interface for the Task Scheduler

This module provides CLI commands for managing the scheduling and task execution framework,
including starting the scheduler, managing tasks, monitoring executions, and emergency controls.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
import click
from loguru import logger
from tabulate import tabulate

from .scheduler import (
    TaskScheduler, TaskDefinition, TaskPriority, TaskStatus,
    create_scheduler_from_config, validate_cron_expression, get_next_execution_times
)
from .config import ConfigurationManager
from .metrics import MetricsCollector
from .alerting import AlertManager


@click.group()
@click.pass_context
def scheduler(ctx):
    """Task scheduler management commands."""
    pass


@scheduler.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--daemon', '-d', is_flag=True, help='Run as daemon (background process)')
@click.option('--log-level', default='INFO', help='Log level (DEBUG, INFO, WARNING, ERROR)')
@click.pass_context
def start(ctx, config, daemon, log_level):
    """Start the task scheduler."""
    try:
        # Configure logging
        logger.remove()
        logger.add(sys.stderr, level=log_level)
        
        # Load configuration
        config_manager = ConfigurationManager()
        scraper_config = config_manager.load_config(
            config_files=[config] if config else None
        )
        
        # Create scheduler components
        metrics_collector = MetricsCollector() if scraper_config.monitoring.metrics_enabled else None
        alert_manager = AlertManager(scraper_config) if scraper_config.monitoring.alert_channels else None
        
        # Create and configure scheduler
        task_scheduler = create_scheduler_from_config(
            scraper_config, metrics_collector, alert_manager
        )
        
        logger.info(f"Starting scheduler with {len(task_scheduler.get_task_definitions())} tasks")
        
        if daemon:
            logger.info("Running in daemon mode")
            # In a full implementation, this would properly daemonize the process
            
        # Start scheduler
        task_scheduler.start()
        
        try:
            # Keep running until interrupted
            while task_scheduler.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            task_scheduler.stop()
            
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        sys.exit(1)


@scheduler.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def status(ctx, config):
    """Show scheduler status and statistics."""
    try:
        # This would connect to a running scheduler instance
        # For now, we'll show configuration-based status
        
        config_manager = ConfigurationManager()
        scraper_config = config_manager.load_config(
            config_files=[config] if config else None
        )
        
        print("=== Scheduler Status ===")
        print(f"Scheduling Enabled: {scraper_config.scheduling.enabled}")
        print(f"Cron Expression: {scraper_config.scheduling.cron_expression}")
        print(f"Timezone: {scraper_config.scheduling.timezone}")
        print(f"Max Execution Time: {scraper_config.scheduling.max_execution_time}s")
        print(f"Concurrent Tasks: {scraper_config.scheduling.concurrent_tasks}")
        
        print("\n=== Configured Tasks ===")
        task_data = []
        for i, task in enumerate(scraper_config.tasks):
            if task.enabled:
                task_data.append([
                    f"scraper_{task.city.lower()}_{i}",
                    f"Daily Scraper - {task.city}",
                    task.city,
                    "Enabled" if task.enabled else "Disabled",
                    scraper_config.scheduling.cron_expression
                ])
        
        if task_data:
            headers = ["Task ID", "Name", "City", "Status", "Schedule"]
            print(tabulate(task_data, headers=headers, tablefmt="grid"))
        else:
            print("No enabled tasks found")
        
        # Show next execution times
        if scraper_config.scheduling.enabled and validate_cron_expression(scraper_config.scheduling.cron_expression):
            print("\n=== Next Execution Times ===")
            next_times = get_next_execution_times(scraper_config.scheduling.cron_expression, 5)
            for i, next_time in enumerate(next_times, 1):
                print(f"{i}. {next_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        sys.exit(1)


@scheduler.command()
@click.argument('task_id')
@click.option('--priority', type=click.Choice(['low', 'normal', 'high', 'critical']), 
              default='normal', help='Task priority')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def run_now(ctx, task_id, priority, config):
    """Manually trigger a task to run immediately."""
    try:
        # In a full implementation, this would connect to the running scheduler
        # For now, we'll create a temporary scheduler and run the task
        
        config_manager = ConfigurationManager()
        scraper_config = config_manager.load_config(
            config_files=[config] if config else None
        )
        
        task_scheduler = create_scheduler_from_config(scraper_config)
        
        # Map priority string to enum
        priority_map = {
            'low': TaskPriority.LOW,
            'normal': TaskPriority.NORMAL,
            'high': TaskPriority.HIGH,
            'critical': TaskPriority.CRITICAL
        }
        
        execution_id = task_scheduler.schedule_task_now(task_id, priority_map[priority])
        
        if execution_id:
            print(f"Task {task_id} scheduled for immediate execution")
            print(f"Execution ID: {execution_id}")
            
            # Start scheduler briefly to execute the task
            task_scheduler.start()
            
            # Wait for task to complete (with timeout)
            timeout = 300  # 5 minutes
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                active_executions = task_scheduler.get_active_executions()
                if not any(ex.execution_id == execution_id for ex in active_executions):
                    # Task completed, check history
                    history = task_scheduler.get_execution_history(10)
                    for execution in history:
                        if execution.execution_id == execution_id:
                            print(f"Task completed with status: {execution.status.value}")
                            if execution.error_message:
                                print(f"Error: {execution.error_message}")
                            break
                    break
                
                time.sleep(2)
            else:
                print("Task execution timeout - check scheduler logs")
            
            task_scheduler.stop()
        else:
            print(f"Failed to schedule task: {task_id}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to run task: {e}")
        sys.exit(1)


@scheduler.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--limit', '-l', default=20, help='Number of recent executions to show')
@click.pass_context
def history(ctx, config, limit):
    """Show recent task execution history."""
    try:
        # In a full implementation, this would query the scheduler's execution history
        # For now, we'll show a placeholder
        
        print("=== Recent Task Executions ===")
        print("(This would show actual execution history from a running scheduler)")
        
        # Example format
        headers = ["Execution ID", "Task", "Status", "Started", "Duration", "Result"]
        example_data = [
            ["abc123...", "Daily Scraper - Helsinki", "COMPLETED", "2024-01-15 06:00:00", "45m 23s", "15 new listings"],
            ["def456...", "Daily Scraper - Tampere", "FAILED", "2024-01-15 06:00:00", "2m 15s", "Network error"],
        ]
        
        print(tabulate(example_data, headers=headers, tablefmt="grid"))
        
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        sys.exit(1)


@scheduler.command()
@click.argument('execution_id')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def cancel(ctx, execution_id, config):
    """Cancel a running or queued task execution."""
    try:
        # In a full implementation, this would connect to the running scheduler
        print(f"Cancelling execution: {execution_id}")
        print("(This would cancel the execution in a running scheduler)")
        
    except Exception as e:
        logger.error(f"Failed to cancel execution: {e}")
        sys.exit(1)


@scheduler.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.confirmation_option(prompt='Are you sure you want to emergency stop all tasks?')
@click.pass_context
def emergency_stop(ctx, config):
    """Emergency stop all running tasks immediately."""
    try:
        # In a full implementation, this would connect to the running scheduler
        print("EMERGENCY STOP - All tasks will be cancelled immediately")
        print("(This would trigger emergency stop in a running scheduler)")
        
    except Exception as e:
        logger.error(f"Failed to emergency stop: {e}")
        sys.exit(1)


@scheduler.command()
@click.argument('task_id')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def enable(ctx, task_id, config):
    """Enable a task."""
    try:
        print(f"Enabling task: {task_id}")
        print("(This would enable the task in a running scheduler)")
        
    except Exception as e:
        logger.error(f"Failed to enable task: {e}")
        sys.exit(1)


@scheduler.command()
@click.argument('task_id')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def disable(ctx, task_id, config):
    """Disable a task."""
    try:
        print(f"Disabling task: {task_id}")
        print("(This would disable the task in a running scheduler)")
        
    except Exception as e:
        logger.error(f"Failed to disable task: {e}")
        sys.exit(1)


@scheduler.command()
@click.argument('cron_expression')
@click.option('--count', '-n', default=5, help='Number of next execution times to show')
@click.pass_context
def validate_cron(ctx, cron_expression, count):
    """Validate a cron expression and show next execution times."""
    try:
        if validate_cron_expression(cron_expression):
            print(f"✓ Valid cron expression: {cron_expression}")
            
            print(f"\nNext {count} execution times:")
            next_times = get_next_execution_times(cron_expression, count)
            for i, next_time in enumerate(next_times, 1):
                print(f"{i}. {next_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        else:
            print(f"✗ Invalid cron expression: {cron_expression}")
            print("\nCron expression format: minute hour day month day_of_week")
            print("Examples:")
            print("  0 6 * * *     - Daily at 6:00 AM")
            print("  0 */6 * * *   - Every 6 hours")
            print("  0 9 * * 1-5   - Weekdays at 9:00 AM")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to validate cron expression: {e}")
        sys.exit(1)


@scheduler.command()
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.pass_context
def export_config(ctx, output):
    """Export scheduler configuration template."""
    try:
        template = {
            "scheduling": {
                "enabled": True,
                "cron_expression": "0 6 * * *",
                "timezone": "Europe/Helsinki",
                "max_execution_time": 7200,
                "concurrent_tasks": 1
            },
            "tasks": [
                {
                    "city": "Helsinki",
                    "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
                    "enabled": True,
                    "max_detail_workers": 5,
                    "staleness_hours": 24,
                    "retry_count": 3
                }
            ],
            "monitoring": {
                "metrics_enabled": True,
                "log_level": "INFO",
                "alert_channels": ["email"]
            }
        }
        
        config_json = json.dumps(template, indent=2)
        
        if output:
            with open(output, 'w') as f:
                f.write(config_json)
            print(f"Scheduler configuration template written to {output}")
        else:
            print(config_json)
            
    except Exception as e:
        logger.error(f"Failed to export config: {e}")
        sys.exit(1)


@scheduler.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def test_config(ctx, config):
    """Test scheduler configuration for validity."""
    try:
        config_manager = ConfigurationManager()
        scraper_config = config_manager.load_config(
            config_files=[config] if config else None
        )
        
        print("=== Configuration Test Results ===")
        
        # Test scheduling configuration
        if scraper_config.scheduling.enabled:
            if validate_cron_expression(scraper_config.scheduling.cron_expression):
                print("✓ Cron expression is valid")
            else:
                print("✗ Invalid cron expression")
                return
        else:
            print("⚠ Scheduling is disabled")
        
        # Test task configurations
        enabled_tasks = [task for task in scraper_config.tasks if task.enabled]
        print(f"✓ Found {len(enabled_tasks)} enabled tasks")
        
        for task in enabled_tasks:
            if not task.city or not task.url:
                print(f"✗ Task missing required fields: {task.city}")
            else:
                print(f"✓ Task configuration valid: {task.city}")
        
        # Test resource limits
        if scraper_config.scheduling.max_execution_time > 0:
            print("✓ Execution timeout configured")
        else:
            print("⚠ No execution timeout set")
        
        print("\n✓ Configuration test completed successfully")
        
    except Exception as e:
        logger.error(f"Configuration test failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    scheduler()