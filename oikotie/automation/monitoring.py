"""
Comprehensive Monitoring and Observability System for Daily Scraper Automation

This module provides Prometheus-compatible metrics export, performance monitoring,
data quality tracking, and structured logging capabilities for operational visibility.
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict, deque
from loguru import logger
import socket
import os

# Import psutil with centralized compatibility handling
from .psutil_compat import psutil, PSUTIL_AVAILABLE

try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, CollectorRegistry, 
        generate_latest, CONTENT_TYPE_LATEST, start_http_server
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus_client not available - metrics export will be limited")
    PROMETHEUS_AVAILABLE = False
    
    # Mock classes for when prometheus_client is not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class CollectorRegistry:
        def __init__(self, *args, **kwargs): pass
    
    def generate_latest(registry=None):
        return b"# Prometheus client not available\n"
    
    def start_http_server(port, registry=None):
        pass

from .metrics import MetricsCollector, ExecutionMetrics, PerformanceMetrics, DataQualityMetrics
from ..database.manager import EnhancedDatabaseManager


@dataclass
class SystemMetrics:
    """System-level performance metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    active_connections: int
    load_average: Optional[float] = None  # Unix systems only


@dataclass
class ApplicationMetrics:
    """Application-level metrics."""
    timestamp: datetime
    active_executions: int
    total_executions: int
    failed_executions: int
    average_execution_time: float
    current_memory_mb: float
    peak_memory_mb: float
    database_connections: int
    cache_hit_rate: float


class PrometheusMetricsExporter:
    """Prometheus-compatible metrics exporter."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize Prometheus metrics exporter.
        
        Args:
            registry: Prometheus collector registry (creates new if None)
        """
        self.registry = registry or CollectorRegistry()
        
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus client not available - using mock metrics")
            return
        
        # Execution metrics
        self.execution_counter = Counter(
            'scraper_executions_total',
            'Total number of scraper executions',
            ['city', 'status'],
            registry=self.registry
        )
        
        self.execution_duration = Histogram(
            'scraper_execution_duration_seconds',
            'Duration of scraper executions',
            ['city'],
            registry=self.registry
        )
        
        self.listings_processed = Counter(
            'scraper_listings_processed_total',
            'Total number of listings processed',
            ['city', 'result'],
            registry=self.registry
        )
        
        # System metrics
        self.system_cpu_percent = Gauge(
            'system_cpu_usage_percent',
            'System CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_percent = Gauge(
            'system_memory_usage_percent',
            'System memory usage percentage',
            registry=self.registry
        )
        
        self.system_memory_used_mb = Gauge(
            'system_memory_used_megabytes',
            'System memory used in megabytes',
            registry=self.registry
        )
        
        self.system_disk_usage_percent = Gauge(
            'system_disk_usage_percent',
            'System disk usage percentage',
            registry=self.registry
        )
        
        self.network_bytes_sent = Counter(
            'network_bytes_sent_total',
            'Total network bytes sent',
            registry=self.registry
        )
        
        self.network_bytes_recv = Counter(
            'network_bytes_received_total',
            'Total network bytes received',
            registry=self.registry
        )
        
        # Data quality metrics
        self.data_quality_score = Gauge(
            'scraper_data_quality_score',
            'Data quality score (0-1)',
            ['city', 'metric_type'],
            registry=self.registry
        )
        
        self.geocoding_success_rate = Gauge(
            'scraper_geocoding_success_rate',
            'Geocoding success rate (0-1)',
            ['city'],
            registry=self.registry
        )
        
        # Error metrics
        self.error_counter = Counter(
            'scraper_errors_total',
            'Total number of errors',
            ['city', 'error_type'],
            registry=self.registry
        )
        
        # Application metrics
        self.active_executions = Gauge(
            'scraper_active_executions',
            'Number of currently active executions',
            registry=self.registry
        )
        
        self.database_connections = Gauge(
            'scraper_database_connections',
            'Number of active database connections',
            registry=self.registry
        )
        
        logger.info("Prometheus metrics exporter initialized")
    
    def record_execution_start(self, city: str) -> None:
        """Record the start of an execution."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.active_executions.inc()
        logger.debug(f"Recorded execution start for {city}")
    
    def record_execution_complete(self, result: 'ScrapingResult') -> None:
        """Record completion of an execution."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        # Update counters
        self.execution_counter.labels(
            city=result.city,
            status=result.status.value
        ).inc()
        
        # Record duration
        if result.execution_time_seconds:
            self.execution_duration.labels(city=result.city).observe(result.execution_time_seconds)
        
        # Record listing results
        self.listings_processed.labels(city=result.city, result='new').inc(result.listings_new)
        self.listings_processed.labels(city=result.city, result='updated').inc(result.listings_updated)
        self.listings_processed.labels(city=result.city, result='skipped').inc(result.listings_skipped)
        self.listings_processed.labels(city=result.city, result='failed').inc(result.listings_failed)
        
        # Update active executions
        self.active_executions.dec()
        
        logger.debug(f"Recorded execution completion for {result.city}")
    
    def update_system_metrics(self, metrics: SystemMetrics) -> None:
        """Update system-level metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.system_cpu_percent.set(metrics.cpu_percent)
        self.system_memory_percent.set(metrics.memory_percent)
        self.system_memory_used_mb.set(metrics.memory_used_mb)
        self.system_disk_usage_percent.set(metrics.disk_usage_percent)
        
        # Network counters (these should only increase)
        # Note: We need to track previous values to calculate deltas
        # For now, we'll set them directly (not ideal for counters)
        
    def update_data_quality_metrics(self, city: str, metrics: DataQualityMetrics) -> None:
        """Update data quality metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.data_quality_score.labels(city=city, metric_type='completeness').set(metrics.completeness_score)
        self.geocoding_success_rate.labels(city=city).set(metrics.geocoding_success_rate)
        
        if metrics.validation_errors:
            self.error_counter.labels(city=city, error_type='validation').inc(len(metrics.validation_errors))
    
    def record_error(self, city: str, error_type: str, count: int = 1) -> None:
        """Record an error occurrence."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.error_counter.labels(city=city, error_type=error_type).inc(count)
    
    def get_metrics_text(self) -> str:
        """Get metrics in Prometheus text format."""
        if not PROMETHEUS_AVAILABLE:
            return "# Prometheus client not available\n"
        
        return generate_latest(self.registry).decode('utf-8')


class SystemMonitor:
    """System performance monitor."""
    
    def __init__(self, collection_interval: int = 30):
        """
        Initialize system monitor.
        
        Args:
            collection_interval: Interval between metric collections in seconds
        """
        self.collection_interval = collection_interval
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.metrics_history: deque = deque(maxlen=1000)  # Keep last 1000 samples
        self.callbacks: List[Callable[[SystemMetrics], None]] = []
        
        # Network baseline for calculating deltas
        self._last_network_stats = None
        
        logger.info(f"System monitor initialized with {collection_interval}s interval")
    
    def add_callback(self, callback: Callable[[SystemMetrics], None]) -> None:
        """Add a callback to be called when metrics are collected."""
        self.callbacks.append(callback)
    
    def start_monitoring(self) -> None:
        """Start system monitoring in background thread."""
        if self.is_monitoring:
            logger.warning("System monitoring already running")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("System monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop system monitoring."""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        logger.info("System monitoring stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                metrics = self._collect_system_metrics()
                self.metrics_history.append(metrics)
                
                # Call registered callbacks
                for callback in self.callbacks:
                    try:
                        callback(metrics)
                    except Exception as e:
                        logger.error(f"Error in metrics callback: {e}")
                
                time.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in system monitoring loop: {e}")
                time.sleep(self.collection_interval)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Disk usage for current directory
            disk_usage = psutil.disk_usage('.')
            disk_usage_percent = (disk_usage.used / disk_usage.total) * 100
            disk_free_gb = disk_usage.free / (1024**3)
            
            # Network I/O
            network_bytes_sent = 0
            network_bytes_recv = 0
            try:
                network_io = psutil.net_io_counters()
                if network_io:
                    network_bytes_sent = network_io.bytes_sent
                    network_bytes_recv = network_io.bytes_recv
            except (AttributeError, OSError):
                pass
            
            # Active network connections
            active_connections = 0
            try:
                connections = psutil.net_connections()
                active_connections = len([c for c in connections if c.status == 'ESTABLISHED'])
            except (psutil.AccessDenied, OSError):
                pass
            
            # Load average (Unix systems only)
            load_average = None
            try:
                if hasattr(os, 'getloadavg'):
                    load_average = os.getloadavg()[0]  # 1-minute load average
            except (OSError, AttributeError):
                pass
            
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024**2),
                memory_available_mb=memory.available / (1024**2),
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                active_connections=active_connections,
                load_average=load_average
            )
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0,
                network_bytes_sent=0,
                network_bytes_recv=0,
                active_connections=0
            )
    
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Get the most recent system metrics."""
        if self.metrics_history:
            return self.metrics_history[-1]
        return None
    
    def get_metrics_summary(self, minutes_back: int = 30) -> Dict[str, Any]:
        """Get summary statistics for recent metrics."""
        if not self.metrics_history:
            return {}
        
        cutoff_time = datetime.now() - timedelta(minutes=minutes_back)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {}
        
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        
        return {
            'sample_count': len(recent_metrics),
            'time_range_minutes': minutes_back,
            'cpu_avg': sum(cpu_values) / len(cpu_values),
            'cpu_max': max(cpu_values),
            'cpu_min': min(cpu_values),
            'memory_avg': sum(memory_values) / len(memory_values),
            'memory_max': max(memory_values),
            'memory_min': min(memory_values),
            'latest_disk_free_gb': recent_metrics[-1].disk_free_gb,
            'latest_active_connections': recent_metrics[-1].active_connections
        }


class HealthChecker:
    """Health check system for monitoring application health."""
    
    def __init__(self, db_manager: Optional[EnhancedDatabaseManager] = None):
        """
        Initialize health checker.
        
        Args:
            db_manager: Database manager for health checks
        """
        self.db_manager = db_manager or EnhancedDatabaseManager()
        self.health_checks: Dict[str, Callable[[], bool]] = {}
        self.last_check_results: Dict[str, Dict[str, Any]] = {}
        
        # Register default health checks
        self._register_default_checks()
        
        logger.info("Health checker initialized")
    
    def _register_default_checks(self) -> None:
        """Register default health checks."""
        self.register_check('database', self._check_database_health)
        self.register_check('disk_space', self._check_disk_space)
        self.register_check('memory', self._check_memory_usage)
        self.register_check('system_load', self._check_system_load)
    
    def register_check(self, name: str, check_func: Callable[[], bool]) -> None:
        """
        Register a health check function.
        
        Args:
            name: Name of the health check
            check_func: Function that returns True if healthy, False otherwise
        """
        self.health_checks[name] = check_func
        logger.debug(f"Registered health check: {name}")
    
    def _check_database_health(self) -> bool:
        """Check database connectivity and basic operations."""
        try:
            # Test database connection
            with self.db_manager.get_connection() as conn:
                result = conn.execute("SELECT 1").fetchone()
                return result is not None
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def _check_disk_space(self) -> bool:
        """Check available disk space."""
        try:
            disk_usage = psutil.disk_usage('.')
            free_percent = (disk_usage.free / disk_usage.total) * 100
            return free_percent > 10  # Require at least 10% free space
        except Exception as e:
            logger.error(f"Disk space health check failed: {e}")
            return False
    
    def _check_memory_usage(self) -> bool:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            return memory.percent < 90  # Require less than 90% memory usage
        except Exception as e:
            logger.error(f"Memory health check failed: {e}")
            return False
    
    def _check_system_load(self) -> bool:
        """Check system load average (Unix systems only)."""
        try:
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()[0]  # 1-minute load average
                cpu_count = psutil.cpu_count()
                return load_avg < (cpu_count * 2)  # Load should be less than 2x CPU count
            return True  # Skip check on non-Unix systems
        except Exception as e:
            logger.error(f"System load health check failed: {e}")
            return True  # Don't fail on systems without load average
    
    def run_health_checks(self) -> Dict[str, Any]:
        """
        Run all registered health checks.
        
        Returns:
            Dictionary with health check results
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'overall_healthy': True,
            'checks': {}
        }
        
        for check_name, check_func in self.health_checks.items():
            try:
                start_time = time.time()
                is_healthy = check_func()
                duration_ms = (time.time() - start_time) * 1000
                
                check_result = {
                    'healthy': is_healthy,
                    'duration_ms': round(duration_ms, 2),
                    'timestamp': datetime.now().isoformat()
                }
                
                results['checks'][check_name] = check_result
                
                if not is_healthy:
                    results['overall_healthy'] = False
                
                # Store for history
                self.last_check_results[check_name] = check_result
                
            except Exception as e:
                logger.error(f"Health check {check_name} failed with exception: {e}")
                results['checks'][check_name] = {
                    'healthy': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                results['overall_healthy'] = False
        
        logger.debug(f"Health checks completed - Overall healthy: {results['overall_healthy']}")
        return results
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of recent health check results."""
        return {
            'last_check_time': max(
                (result.get('timestamp', '') for result in self.last_check_results.values()),
                default='Never'
            ),
            'total_checks': len(self.health_checks),
            'healthy_checks': len([r for r in self.last_check_results.values() if r.get('healthy', False)]),
            'failed_checks': [name for name, result in self.last_check_results.items() 
                            if not result.get('healthy', True)]
        }


class MonitoringServer:
    """HTTP server for exposing monitoring endpoints."""
    
    def __init__(self, 
                 port: int = 8080,
                 prometheus_exporter: Optional[PrometheusMetricsExporter] = None,
                 health_checker: Optional[HealthChecker] = None):
        """
        Initialize monitoring server.
        
        Args:
            port: Port to run the server on
            prometheus_exporter: Prometheus metrics exporter
            health_checker: Health checker instance
        """
        self.port = port
        self.prometheus_exporter = prometheus_exporter or PrometheusMetricsExporter()
        self.health_checker = health_checker or HealthChecker()
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        logger.info(f"Monitoring server initialized on port {port}")
    
    def start_server(self) -> None:
        """Start the monitoring server."""
        if self.is_running:
            logger.warning("Monitoring server already running")
            return
        
        try:
            if PROMETHEUS_AVAILABLE:
                # Start Prometheus HTTP server
                start_http_server(self.port, registry=self.prometheus_exporter.registry)
                logger.info(f"Prometheus metrics server started on port {self.port}")
            else:
                logger.warning("Prometheus client not available - starting basic HTTP server")
                self._start_basic_server()
            
            self.is_running = True
            
        except Exception as e:
            logger.error(f"Failed to start monitoring server: {e}")
            raise
    
    def _start_basic_server(self) -> None:
        """Start a basic HTTP server when Prometheus client is not available."""
        import http.server
        import socketserver
        from urllib.parse import urlparse, parse_qs
        
        class MonitoringHandler(http.server.BaseHTTPRequestHandler):
            def __init__(self, *args, health_checker=None, **kwargs):
                self.health_checker = health_checker
                super().__init__(*args, **kwargs)
            
            def do_GET(self):
                if self.path == '/health':
                    self._handle_health()
                elif self.path == '/metrics':
                    self._handle_metrics()
                else:
                    self._handle_not_found()
            
            def _handle_health(self):
                try:
                    health_results = self.health_checker.run_health_checks()
                    status_code = 200 if health_results['overall_healthy'] else 503
                    
                    self.send_response(status_code)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(health_results, indent=2).encode())
                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    error_response = {'error': str(e), 'healthy': False}
                    self.wfile.write(json.dumps(error_response).encode())
            
            def _handle_metrics(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                metrics_text = "# Basic metrics (Prometheus client not available)\n"
                metrics_text += f"# Server running on port {self.server.server_port}\n"
                self.wfile.write(metrics_text.encode())
            
            def _handle_not_found(self):
                self.send_response(404)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Not Found')
            
            def log_message(self, format, *args):
                # Suppress default logging
                pass
        
        # Create handler with health checker
        handler = lambda *args, **kwargs: MonitoringHandler(*args, health_checker=self.health_checker, **kwargs)
        
        def run_server():
            with socketserver.TCPServer(("", self.port), handler) as httpd:
                logger.info(f"Basic monitoring server started on port {self.port}")
                httpd.serve_forever()
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
    
    def stop_server(self) -> None:
        """Stop the monitoring server."""
        self.is_running = False
        logger.info("Monitoring server stopped")
    
    def get_metrics_url(self) -> str:
        """Get the URL for metrics endpoint."""
        return f"http://localhost:{self.port}/metrics"
    
    def get_health_url(self) -> str:
        """Get the URL for health endpoint."""
        return f"http://localhost:{self.port}/health"


class ComprehensiveMonitor:
    """Comprehensive monitoring system that integrates all monitoring components."""
    
    def __init__(self, 
                 db_manager: Optional[EnhancedDatabaseManager] = None,
                 metrics_port: int = 8080,
                 system_monitor_interval: int = 30):
        """
        Initialize comprehensive monitoring system.
        
        Args:
            db_manager: Database manager for metrics storage
            metrics_port: Port for metrics server
            system_monitor_interval: System monitoring interval in seconds
        """
        self.db_manager = db_manager or EnhancedDatabaseManager()
        
        # Initialize components
        self.prometheus_exporter = PrometheusMetricsExporter()
        self.system_monitor = SystemMonitor(collection_interval=system_monitor_interval)
        self.health_checker = HealthChecker(db_manager=self.db_manager)
        self.monitoring_server = MonitoringServer(
            port=metrics_port,
            prometheus_exporter=self.prometheus_exporter,
            health_checker=self.health_checker
        )
        self.metrics_collector = MetricsCollector(db_manager=self.db_manager)
        
        # Connect system monitor to Prometheus exporter
        self.system_monitor.add_callback(self.prometheus_exporter.update_system_metrics)
        
        logger.info("Comprehensive monitoring system initialized")
    
    def start_monitoring(self) -> None:
        """Start all monitoring components."""
        try:
            # Start system monitoring
            self.system_monitor.start_monitoring()
            
            # Start metrics server
            self.monitoring_server.start_server()
            
            logger.success("Comprehensive monitoring started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start comprehensive monitoring: {e}")
            self.stop_monitoring()
            raise
    
    def stop_monitoring(self) -> None:
        """Stop all monitoring components."""
        try:
            self.system_monitor.stop_monitoring()
            self.monitoring_server.stop_server()
            
            logger.info("Comprehensive monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")
    
    def record_execution_start(self, city: str) -> None:
        """Record the start of a scraping execution."""
        self.prometheus_exporter.record_execution_start(city)
    
    def get_current_system_metrics(self) -> Dict[str, Any]:
        """
        Get current system metrics from all monitoring components.
        
        Returns:
            Dictionary with current system metrics
        """
        try:
            # Get system metrics from system monitor
            current_system_metrics = self.system_monitor.get_current_metrics()
            
            # Get health check results
            health_results = self.health_checker.run_health_checks()
            
            # Get resource usage from system monitor
            resource_summary = self.system_monitor.get_metrics_summary(minutes_back=5)
            
            # Combine all metrics
            combined_metrics = {
                'timestamp': datetime.now().isoformat(),
                'system_metrics': asdict(current_system_metrics) if current_system_metrics and hasattr(current_system_metrics, '__dataclass_fields__') else {},
                'health_status': health_results,
                'resource_summary': resource_summary,
                'monitoring_status': {
                    'system_monitor_active': self.system_monitor.is_monitoring,
                    'metrics_server_active': self.monitoring_server.is_running,
                    'prometheus_available': PROMETHEUS_AVAILABLE,
                    'psutil_available': PSUTIL_AVAILABLE
                }
            }
            
            # Add application-specific metrics if available
            if hasattr(self, 'metrics_collector') and self.metrics_collector:
                try:
                    app_metrics = self.metrics_collector.get_current_metrics()
                    combined_metrics['application_metrics'] = app_metrics
                except Exception as e:
                    logger.warning(f"Failed to get application metrics: {e}")
                    combined_metrics['application_metrics'] = {'error': str(e)}
            
            return combined_metrics
            
        except Exception as e:
            logger.error(f"Failed to get current system metrics: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'system_metrics': {},
                'health_status': {'overall_healthy': False, 'error': str(e)},
                'resource_summary': {},
                'monitoring_status': {
                    'system_monitor_active': False,
                    'metrics_server_active': False,
                    'prometheus_available': PROMETHEUS_AVAILABLE,
                    'psutil_available': PSUTIL_AVAILABLE
                }
            }

    def record_execution_complete(self, result: 'ScrapingResult') -> None:
        """Record completion of a scraping execution."""
        self.prometheus_exporter.record_execution_complete(result)
        
        # Update data quality metrics if available
        if hasattr(result, 'data_quality_metrics') and result.data_quality_metrics:
            self.prometheus_exporter.update_data_quality_metrics(
                result.city, result.data_quality_metrics
            )
    
    def run_health_checks(self) -> Dict[str, Any]:
        """Run comprehensive health checks and return results."""
        return self.health_checker.run_health_checks()
    

        return None
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return self.system_monitor.get_metrics_summary()
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get comprehensive monitoring status."""
        return {
            'timestamp': datetime.now().isoformat(),
            'system_monitor_active': self.system_monitor.is_monitoring,
            'metrics_server_active': self.monitoring_server.is_running,
            'metrics_url': self.monitoring_server.get_metrics_url(),
            'health_url': self.monitoring_server.get_health_url(),
            'system_metrics_summary': self.system_monitor.get_metrics_summary(),
            'health_summary': self.health_checker.get_health_summary(),
            'prometheus_available': PROMETHEUS_AVAILABLE
        }
    
    def export_monitoring_config(self) -> Dict[str, Any]:
        """Export monitoring configuration for external systems."""
        return {
            'prometheus': {
                'enabled': PROMETHEUS_AVAILABLE,
                'metrics_endpoint': f"http://localhost:{self.monitoring_server.port}/metrics",
                'scrape_interval': '30s',
                'scrape_timeout': '10s'
            },
            'health_checks': {
                'endpoint': f"http://localhost:{self.monitoring_server.port}/health",
                'checks': list(self.health_checker.health_checks.keys())
            },
            'system_monitoring': {
                'interval_seconds': self.system_monitor.collection_interval,
                'metrics_history_size': self.system_monitor.metrics_history.maxlen
            }
        }