"""
Scheduling and Task Execution Framework for Daily Scraper Automation

This module provides a comprehensive scheduling system with cron-like expressions,
task queue management, execution coordination, timeout enforcement, monitoring,
and failure recovery capabilities.
"""

import asyncio
import json
import signal
import time
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from threading import Thread, Event, Lock
from typing import Any, Callable, Dict, List, Optional, Set, Union
from .psutil_compat import psutil
from croniter import croniter
from loguru import logger

from .config import ScraperConfig, SchedulingConfig
from .orchestrator import EnhancedScraperOrchestrator, ScrapingResult, ExecutionStatus
from .metrics import MetricsCollector
from .alerting import AlertManager


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskDefinition:
    """Definition of a scheduled task"""
    task_id: str
    name: str
    cron_expression: str
    task_type: str = "scraper"
    city: Optional[str] = None
    enabled: bool = True
    priority: TaskPriority = TaskPriority.NORMAL
    max_execution_time: int = 7200  # 2 hours in seconds
    max_retries: int = 3
    retry_delay: int = 300  # 5 minutes
    timeout_action: str = "kill"  # "kill" or "graceful"
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskExecution:
    """Runtime task execution instance"""
    execution_id: str
    task_id: str
    status: TaskStatus
    scheduled_time: datetime
    started_time: Optional[datetime] = None
    completed_time: Optional[datetime] = None
    next_retry_time: Optional[datetime] = None
    retry_count: int = 0
    result: Optional[Any] = None
    error_message: Optional[str] = None
    resource_usage: Dict[str, float] = field(default_factory=dict)
    process_id: Optional[int] = None
    node_id: Optional[str] = None


@dataclass
class SchedulerStats:
    """Scheduler statistics"""
    total_tasks: int = 0
    active_tasks: int = 0
    queued_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    average_execution_time: float = 0.0
    success_rate: float = 0.0
    last_execution: Optional[datetime] = None


class TaskQueue:
    """Thread-safe task queue with priority support"""
    
    def __init__(self):
        self._queue: List[TaskExecution] = []
        self._lock = Lock()
        self._condition = asyncio.Condition()
    
    def put(self, task: TaskExecution) -> None:
        """Add task to queue with priority ordering"""
        with self._lock:
            # Insert task based on priority and scheduled time
            inserted = False
            for i, existing_task in enumerate(self._queue):
                existing_def = self._get_task_definition(existing_task.task_id)
                new_def = self._get_task_definition(task.task_id)
                
                if (new_def and existing_def and 
                    new_def.priority.value > existing_def.priority.value):
                    self._queue.insert(i, task)
                    inserted = True
                    break
                elif (task.scheduled_time < existing_task.scheduled_time and
                      new_def and existing_def and
                      new_def.priority.value == existing_def.priority.value):
                    self._queue.insert(i, task)
                    inserted = True
                    break
            
            if not inserted:
                self._queue.append(task)
    
    def get(self, timeout: Optional[float] = None) -> Optional[TaskExecution]:
        """Get next ready task from queue"""
        with self._lock:
            current_time = datetime.now(timezone.utc)
            
            for i, task in enumerate(self._queue):
                if task.scheduled_time <= current_time:
                    return self._queue.pop(i)
            
            return None
    
    def size(self) -> int:
        """Get queue size"""
        with self._lock:
            return len(self._queue)
    
    def get_pending_tasks(self) -> List[TaskExecution]:
        """Get list of pending tasks"""
        with self._lock:
            return self._queue.copy()
    
    def remove_task(self, execution_id: str) -> bool:
        """Remove task from queue"""
        with self._lock:
            for i, task in enumerate(self._queue):
                if task.execution_id == execution_id:
                    self._queue.pop(i)
                    return True
            return False
    
    def _get_task_definition(self, task_id: str) -> Optional[TaskDefinition]:
        """Helper to get task definition (would be injected in real implementation)"""
        # This would be injected from the scheduler
        return None


class ResourceMonitor:
    """Monitor system resources and enforce limits"""
    
    def __init__(self):
        self.monitoring = True
        self.resource_limits = {
            'cpu_percent': 80.0,
            'memory_percent': 80.0,
            'disk_percent': 90.0
        }
    
    def check_resource_availability(self, limits: Dict[str, Any]) -> bool:
        """Check if system has enough resources for task"""
        try:
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > limits.get('cpu_percent', self.resource_limits['cpu_percent']):
                logger.warning(f"CPU usage too high: {cpu_percent}%")
                return False
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > limits.get('memory_percent', self.resource_limits['memory_percent']):
                logger.warning(f"Memory usage too high: {memory.percent}%")
                return False
            
            # Check disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > limits.get('disk_percent', self.resource_limits['disk_percent']):
                logger.warning(f"Disk usage too high: {disk_percent}%")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking resources: {e}")
            return True  # Allow execution if we can't check
    
    def get_current_usage(self) -> Dict[str, float]:
        """Get current resource usage"""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': memory.percent,
                'memory_mb': memory.used / 1024 / 1024,
                'disk_percent': (disk.used / disk.total) * 100,
                'disk_free_gb': disk.free / 1024 / 1024 / 1024
            }
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            return {}
    
    def monitor_process(self, pid: int, limits: Dict[str, Any]) -> Dict[str, float]:
        """Monitor specific process resource usage"""
        try:
            process = psutil.Process(pid)
            
            # Get process resource usage
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            usage = {
                'cpu_percent': cpu_percent,
                'memory_mb': memory_mb,
                'num_threads': process.num_threads()
            }
            
            # Check limits
            if limits.get('max_cpu_percent') and cpu_percent > limits['max_cpu_percent']:
                logger.warning(f"Process {pid} CPU usage exceeded: {cpu_percent}%")
            
            if limits.get('max_memory_mb') and memory_mb > limits['max_memory_mb']:
                logger.warning(f"Process {pid} memory usage exceeded: {memory_mb}MB")
            
            return usage
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"Cannot monitor process {pid}: {e}")
            return {}


class TaskExecutor:
    """Execute tasks with timeout and resource monitoring"""
    
    def __init__(self, resource_monitor: ResourceMonitor):
        self.resource_monitor = resource_monitor
        self.active_executions: Dict[str, TaskExecution] = {}
        self.execution_lock = Lock()
    
    async def execute_task(self, 
                          task_execution: TaskExecution,
                          task_definition: TaskDefinition,
                          orchestrator: EnhancedScraperOrchestrator) -> TaskExecution:
        """Execute a task with monitoring and timeout"""
        execution_id = task_execution.execution_id
        
        logger.info(f"Starting task execution: {execution_id} ({task_definition.name})")
        
        # Update execution status
        task_execution.status = TaskStatus.RUNNING
        task_execution.started_time = datetime.now(timezone.utc)
        
        with self.execution_lock:
            self.active_executions[execution_id] = task_execution
        
        try:
            # Check resource availability
            if not self.resource_monitor.check_resource_availability(task_definition.resource_limits):
                raise Exception("Insufficient system resources")
            
            # Execute task with timeout
            result = await asyncio.wait_for(
                self._execute_scraper_task(orchestrator, task_execution),
                timeout=task_definition.max_execution_time
            )
            
            # Update execution with result
            task_execution.status = TaskStatus.COMPLETED
            task_execution.result = result
            task_execution.completed_time = datetime.now(timezone.utc)
            
            logger.success(f"Task completed: {execution_id}")
            
        except asyncio.TimeoutError:
            logger.error(f"Task timeout: {execution_id}")
            task_execution.status = TaskStatus.TIMEOUT
            task_execution.error_message = f"Task exceeded maximum execution time of {task_definition.max_execution_time}s"
            
            # Handle timeout action
            if task_definition.timeout_action == "kill":
                await self._kill_task(task_execution)
            else:
                await self._graceful_stop_task(task_execution)
        
        except Exception as e:
            logger.error(f"Task failed: {execution_id} - {e}")
            task_execution.status = TaskStatus.FAILED
            task_execution.error_message = str(e)
        
        finally:
            task_execution.completed_time = task_execution.completed_time or datetime.now(timezone.utc)
            
            # Get final resource usage
            if task_execution.process_id:
                task_execution.resource_usage = self.resource_monitor.monitor_process(
                    task_execution.process_id, task_definition.resource_limits
                )
            
            with self.execution_lock:
                self.active_executions.pop(execution_id, None)
        
        return task_execution
    
    async def _execute_scraper_task(self, 
                                   orchestrator: EnhancedScraperOrchestrator,
                                   task_execution: TaskExecution) -> ScrapingResult:
        """Execute scraper task asynchronously"""
        # Run the scraper in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        
        def run_scraper():
            return orchestrator.run_daily_scrape()
        
        # Execute in thread pool
        result = await loop.run_in_executor(None, run_scraper)
        return result
    
    async def _kill_task(self, task_execution: TaskExecution):
        """Forcefully kill a task"""
        if task_execution.process_id:
            try:
                process = psutil.Process(task_execution.process_id)
                process.kill()
                logger.warning(f"Killed task process: {task_execution.process_id}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    
    async def _graceful_stop_task(self, task_execution: TaskExecution):
        """Gracefully stop a task"""
        if task_execution.process_id:
            try:
                process = psutil.Process(task_execution.process_id)
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=30)
                except psutil.TimeoutExpired:
                    process.kill()
                    logger.warning(f"Force killed task after graceful timeout: {task_execution.process_id}")
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    
    def get_active_executions(self) -> List[TaskExecution]:
        """Get list of currently active executions"""
        with self.execution_lock:
            return list(self.active_executions.values())
    
    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an active execution"""
        with self.execution_lock:
            if execution_id in self.active_executions:
                task_execution = self.active_executions[execution_id]
                task_execution.status = TaskStatus.CANCELLED
                
                # Kill the process if running
                asyncio.create_task(self._kill_task(task_execution))
                return True
            return False


class TaskScheduler:
    """Main task scheduler with cron-like scheduling and execution management"""
    
    def __init__(self, 
                 config: ScraperConfig,
                 metrics_collector: Optional[MetricsCollector] = None,
                 alert_manager: Optional[AlertManager] = None):
        self.config = config
        self.scheduling_config = config.scheduling
        self.metrics_collector = metrics_collector
        self.alert_manager = alert_manager
        
        # Core components
        self.task_queue = TaskQueue()
        self.resource_monitor = ResourceMonitor()
        self.task_executor = TaskExecutor(self.resource_monitor)
        
        # Task management
        self.task_definitions: Dict[str, TaskDefinition] = {}
        self.execution_history: List[TaskExecution] = []
        self.running = False
        self.scheduler_thread: Optional[Thread] = None
        self.executor_thread: Optional[Thread] = None
        self.stop_event = Event()
        
        # Statistics
        self.stats = SchedulerStats()
        self.stats_lock = Lock()
        
        # Emergency stop
        self.emergency_stop = Event()
        
        logger.info("Task scheduler initialized")
    
    def add_task(self, task_definition: TaskDefinition) -> None:
        """Add a task definition to the scheduler"""
        self.task_definitions[task_definition.task_id] = task_definition
        logger.info(f"Added task: {task_definition.name} ({task_definition.task_id})")
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task definition"""
        if task_id in self.task_definitions:
            del self.task_definitions[task_id]
            logger.info(f"Removed task: {task_id}")
            return True
        return False
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a task"""
        if task_id in self.task_definitions:
            self.task_definitions[task_id].enabled = True
            logger.info(f"Enabled task: {task_id}")
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a task"""
        if task_id in self.task_definitions:
            self.task_definitions[task_id].enabled = False
            logger.info(f"Disabled task: {task_id}")
            return True
        return False
    
    def schedule_task_now(self, task_id: str, priority: Optional[TaskPriority] = None) -> Optional[str]:
        """Manually schedule a task for immediate execution"""
        if task_id not in self.task_definitions:
            logger.error(f"Task not found: {task_id}")
            return None
        
        task_def = self.task_definitions[task_id]
        if priority:
            task_def.priority = priority
        
        execution_id = str(uuid.uuid4())
        task_execution = TaskExecution(
            execution_id=execution_id,
            task_id=task_id,
            status=TaskStatus.QUEUED,
            scheduled_time=datetime.now(timezone.utc)
        )
        
        self.task_queue.put(task_execution)
        logger.info(f"Manually scheduled task: {task_id} (execution: {execution_id})")
        
        return execution_id
    
    def start(self) -> None:
        """Start the scheduler"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self.emergency_stop.clear()
        
        # Start scheduler thread
        self.scheduler_thread = Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        # Start executor thread
        self.executor_thread = Thread(target=self._executor_loop, daemon=True)
        self.executor_thread.start()
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info("Task scheduler started")
    
    def stop(self, timeout: int = 30) -> None:
        """Stop the scheduler gracefully"""
        if not self.running:
            return
        
        logger.info("Stopping task scheduler...")
        self.running = False
        self.stop_event.set()
        
        # Wait for threads to finish
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=timeout)
        
        if self.executor_thread and self.executor_thread.is_alive():
            self.executor_thread.join(timeout=timeout)
        
        # Cancel any active executions
        active_executions = self.task_executor.get_active_executions()
        for execution in active_executions:
            self.task_executor.cancel_execution(execution.execution_id)
        
        logger.info("Task scheduler stopped")
    
    def emergency_stop_all(self) -> None:
        """Emergency stop all tasks immediately"""
        logger.critical("EMERGENCY STOP activated - stopping all tasks immediately")
        self.emergency_stop.set()
        
        # Cancel all active executions
        active_executions = self.task_executor.get_active_executions()
        for execution in active_executions:
            self.task_executor.cancel_execution(execution.execution_id)
        
        # Clear task queue
        while self.task_queue.size() > 0:
            task = self.task_queue.get()
            if task:
                task.status = TaskStatus.CANCELLED
        
        # Send alert
        if self.alert_manager:
            self.alert_manager.send_alert(
                "emergency_stop",
                "Emergency stop activated - all tasks cancelled",
                severity="critical"
            )
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.stop()
    
    def _scheduler_loop(self) -> None:
        """Main scheduler loop that generates task executions"""
        logger.info("Scheduler loop started")
        
        while self.running and not self.stop_event.is_set():
            try:
                if self.emergency_stop.is_set():
                    break
                
                current_time = datetime.now(timezone.utc)
                
                # Check each task definition for scheduling
                for task_id, task_def in self.task_definitions.items():
                    if not task_def.enabled:
                        continue
                    
                    # Check if task should be scheduled
                    if self._should_schedule_task(task_def, current_time):
                        execution_id = str(uuid.uuid4())
                        
                        # Calculate next execution time
                        cron = croniter(task_def.cron_expression, current_time)
                        next_time = cron.get_next(datetime)
                        
                        task_execution = TaskExecution(
                            execution_id=execution_id,
                            task_id=task_id,
                            status=TaskStatus.QUEUED,
                            scheduled_time=next_time
                        )
                        
                        self.task_queue.put(task_execution)
                        logger.info(f"Scheduled task: {task_def.name} for {next_time}")
                
                # Update statistics
                self._update_stats()
                
                # Sleep for a short interval
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(10)
        
        logger.info("Scheduler loop ended")
    
    def _executor_loop(self) -> None:
        """Main executor loop that processes queued tasks"""
        logger.info("Executor loop started")
        
        while self.running and not self.stop_event.is_set():
            try:
                if self.emergency_stop.is_set():
                    break
                
                # Get next ready task
                task_execution = self.task_queue.get()
                if not task_execution:
                    time.sleep(5)
                    continue
                
                # Get task definition
                task_def = self.task_definitions.get(task_execution.task_id)
                if not task_def or not task_def.enabled:
                    logger.warning(f"Task definition not found or disabled: {task_execution.task_id}")
                    continue
                
                # Check concurrent task limits
                active_count = len(self.task_executor.get_active_executions())
                if active_count >= self.scheduling_config.concurrent_tasks:
                    # Put task back in queue for later
                    task_execution.scheduled_time = datetime.now(timezone.utc) + timedelta(minutes=1)
                    self.task_queue.put(task_execution)
                    time.sleep(10)
                    continue
                
                # Create orchestrator for the task
                orchestrator = self._create_orchestrator_for_task(task_def)
                if not orchestrator:
                    logger.error(f"Failed to create orchestrator for task: {task_execution.task_id}")
                    task_execution.status = TaskStatus.FAILED
                    task_execution.error_message = "Failed to create orchestrator"
                    continue
                
                # Execute task asynchronously
                asyncio.run(self._execute_task_async(task_execution, task_def, orchestrator))
                
            except Exception as e:
                logger.error(f"Error in executor loop: {e}")
                time.sleep(10)
        
        logger.info("Executor loop ended")
    
    async def _execute_task_async(self, 
                                 task_execution: TaskExecution,
                                 task_def: TaskDefinition,
                                 orchestrator: EnhancedScraperOrchestrator) -> None:
        """Execute task asynchronously and handle results"""
        try:
            # Execute the task
            completed_execution = await self.task_executor.execute_task(
                task_execution, task_def, orchestrator
            )
            
            # Add to execution history
            self.execution_history.append(completed_execution)
            
            # Handle retry logic
            if (completed_execution.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT] and
                completed_execution.retry_count < task_def.max_retries):
                
                self._schedule_retry(completed_execution, task_def)
            
            # Send alerts for failures
            if (completed_execution.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT] and
                self.alert_manager):
                
                self.alert_manager.send_alert(
                    "task_failure",
                    f"Task {task_def.name} failed: {completed_execution.error_message}",
                    severity="high" if completed_execution.status == TaskStatus.TIMEOUT else "medium"
                )
            
            # Collect metrics
            if self.metrics_collector:
                self.metrics_collector.record_task_execution(completed_execution, task_def)
            
        except Exception as e:
            logger.error(f"Error executing task {task_execution.task_id}: {e}")
    
    def _should_schedule_task(self, task_def: TaskDefinition, current_time: datetime) -> bool:
        """Check if a task should be scheduled based on cron expression"""
        try:
            cron = croniter(task_def.cron_expression, current_time)
            next_time = cron.get_next(datetime)
            
            # Check if we're within the scheduling window (1 minute tolerance)
            time_diff = abs((next_time - current_time).total_seconds())
            return time_diff <= 60
            
        except Exception as e:
            logger.error(f"Error checking schedule for task {task_def.task_id}: {e}")
            return False
    
    def _schedule_retry(self, failed_execution: TaskExecution, task_def: TaskDefinition) -> None:
        """Schedule a retry for a failed task"""
        retry_delay = task_def.retry_delay * (2 ** failed_execution.retry_count)  # Exponential backoff
        retry_time = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
        
        retry_execution = TaskExecution(
            execution_id=str(uuid.uuid4()),
            task_id=failed_execution.task_id,
            status=TaskStatus.QUEUED,
            scheduled_time=retry_time,
            retry_count=failed_execution.retry_count + 1
        )
        
        self.task_queue.put(retry_execution)
        logger.info(f"Scheduled retry for task {task_def.name} in {retry_delay}s (attempt {retry_execution.retry_count + 1})")
    
    def _create_orchestrator_for_task(self, task_def: TaskDefinition) -> Optional[EnhancedScraperOrchestrator]:
        """Create orchestrator instance for a task"""
        try:
            # Find matching scraper config
            for task_config in self.config.tasks:
                if task_config.city == task_def.city:
                    from .orchestrator import ScraperConfig as OrchestratorConfig
                    
                    orchestrator_config = OrchestratorConfig(
                        city=task_config.city,
                        url=task_config.url,
                        listing_limit=task_config.listing_limit,
                        max_detail_workers=task_config.max_detail_workers,
                        staleness_threshold_hours=task_config.staleness_hours,
                        retry_limit=task_config.retry_count,
                        headless_browser=True
                    )
                    
                    return EnhancedScraperOrchestrator(orchestrator_config)
            
            logger.error(f"No scraper config found for city: {task_def.city}")
            return None
            
        except Exception as e:
            logger.error(f"Error creating orchestrator: {e}")
            return None
    
    def _update_stats(self) -> None:
        """Update scheduler statistics"""
        with self.stats_lock:
            self.stats.total_tasks = len(self.task_definitions)
            self.stats.active_tasks = len(self.task_executor.get_active_executions())
            self.stats.queued_tasks = self.task_queue.size()
            
            # Calculate completion stats from recent history
            recent_executions = [
                ex for ex in self.execution_history[-100:]  # Last 100 executions
                if ex.completed_time and ex.completed_time > datetime.now(timezone.utc) - timedelta(hours=24)
            ]
            
            if recent_executions:
                completed = [ex for ex in recent_executions if ex.status == TaskStatus.COMPLETED]
                failed = [ex for ex in recent_executions if ex.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT]]
                
                self.stats.completed_tasks = len(completed)
                self.stats.failed_tasks = len(failed)
                self.stats.success_rate = len(completed) / len(recent_executions) if recent_executions else 0.0
                
                # Calculate average execution time
                execution_times = [
                    (ex.completed_time - ex.started_time).total_seconds()
                    for ex in completed if ex.started_time and ex.completed_time
                ]
                self.stats.average_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
                
                # Update last execution time
                if recent_executions:
                    self.stats.last_execution = max(ex.completed_time for ex in recent_executions if ex.completed_time)
    
    def get_stats(self) -> SchedulerStats:
        """Get current scheduler statistics"""
        with self.stats_lock:
            return self.stats
    
    def get_task_definitions(self) -> List[TaskDefinition]:
        """Get all task definitions"""
        return list(self.task_definitions.values())
    
    def get_execution_history(self, limit: int = 100) -> List[TaskExecution]:
        """Get recent execution history"""
        return self.execution_history[-limit:]
    
    def get_active_executions(self) -> List[TaskExecution]:
        """Get currently active executions"""
        return self.task_executor.get_active_executions()
    
    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a specific execution"""
        # Try to remove from queue first
        if self.task_queue.remove_task(execution_id):
            logger.info(f"Cancelled queued execution: {execution_id}")
            return True
        
        # Try to cancel active execution
        return self.task_executor.cancel_execution(execution_id)


def create_scheduler_from_config(config: ScraperConfig,
                               metrics_collector: Optional[MetricsCollector] = None,
                               alert_manager: Optional[AlertManager] = None) -> TaskScheduler:
    """Create and configure task scheduler from configuration"""
    scheduler = TaskScheduler(config, metrics_collector, alert_manager)
    
    # Create task definitions from scraper config
    for i, task_config in enumerate(config.tasks):
        if task_config.enabled:
            task_def = TaskDefinition(
                task_id=f"scraper_{task_config.city.lower()}_{i}",
                name=f"Daily Scraper - {task_config.city}",
                cron_expression=config.scheduling.cron_expression,
                task_type="scraper",
                city=task_config.city,
                enabled=True,
                max_execution_time=config.scheduling.max_execution_time,
                max_retries=task_config.retry_count,
                resource_limits={
                    'max_cpu_percent': 80.0,
                    'max_memory_mb': 2048.0
                }
            )
            
            scheduler.add_task(task_def)
    
    return scheduler


def validate_cron_expression(cron_expr: str) -> bool:
    """Validate cron expression format"""
    try:
        croniter(cron_expr)
        return True
    except Exception:
        return False


def get_next_execution_times(cron_expr: str, count: int = 5) -> List[datetime]:
    """Get next N execution times for a cron expression"""
    try:
        cron = croniter(cron_expr, datetime.now(timezone.utc))
        return [cron.get_next(datetime) for _ in range(count)]
    except Exception:
        return []