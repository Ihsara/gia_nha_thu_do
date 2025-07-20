"""
Metrics Collection System for Daily Scraper Automation

This module provides comprehensive metrics collection for execution, performance,
and data quality monitoring. It integrates with the enhanced database manager
to track historical trends and provide actionable insights.
"""

import json
import time
from .psutil_compat import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from loguru import logger

from ..database.manager import EnhancedDatabaseManager


class MetricType(Enum):
    """Types of metrics collected by the system."""
    EXECUTION = "execution"
    PERFORMANCE = "performance"
    DATA_QUALITY = "data_quality"
    ERROR = "error"
    SYSTEM = "system"


@dataclass
class ExecutionMetrics:
    """Metrics related to scraping execution."""
    execution_id: str
    city: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    status: str = "running"
    
    # URL and listing metrics
    total_urls_discovered: int = 0
    urls_processed: int = 0
    listings_new: int = 0
    listings_updated: int = 0
    listings_skipped: int = 0
    listings_failed: int = 0
    
    # Success rates
    success_rate: float = 0.0
    error_rate: float = 0.0
    skip_rate: float = 0.0
    
    # Processing efficiency
    average_time_per_url: float = 0.0
    urls_per_minute: float = 0.0
    
    def calculate_derived_metrics(self) -> None:
        """Calculate derived metrics from base values."""
        if self.urls_processed > 0:
            self.success_rate = (self.listings_new + self.listings_updated) / self.urls_processed
            self.error_rate = self.listings_failed / self.urls_processed
            self.skip_rate = self.listings_skipped / self.urls_processed
        
        if self.completed_at and self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
            
        if self.duration_seconds and self.duration_seconds > 0 and self.urls_processed > 0:
            self.average_time_per_url = self.duration_seconds / self.urls_processed
            self.urls_per_minute = (self.urls_processed / self.duration_seconds) * 60


@dataclass
class PerformanceMetrics:
    """System performance metrics during execution."""
    execution_id: str
    timestamp: datetime
    
    # Memory metrics (MB)
    memory_usage_mb: float = 0.0
    memory_peak_mb: float = 0.0
    memory_available_mb: float = 0.0
    
    # CPU metrics (percentage)
    cpu_usage_percent: float = 0.0
    cpu_peak_percent: float = 0.0
    
    # Network metrics
    network_requests_count: int = 0
    network_bytes_sent: int = 0
    network_bytes_received: int = 0
    
    # Database metrics
    database_operations_count: int = 0
    database_query_time_ms: float = 0.0
    
    # Browser metrics
    browser_instances: int = 0
    browser_memory_mb: float = 0.0


@dataclass
class DataQualityMetrics:
    """Data quality assessment metrics."""
    execution_id: str
    city: str
    timestamp: datetime
    
    # Address and geocoding quality
    total_addresses: int = 0
    geocoded_addresses: int = 0
    geocoding_success_rate: float = 0.0
    geocoding_failures: int = 0
    
    # Data completeness
    complete_listings: int = 0
    incomplete_listings: int = 0
    completeness_score: float = 0.0
    
    # Data validation
    valid_listings: int = 0
    invalid_listings: int = 0
    validation_errors: List[str] = field(default_factory=list)
    
    # Duplicate detection
    duplicate_listings: int = 0
    duplicate_rate: float = 0.0
    
    # Spatial data quality
    spatial_matches: int = 0
    spatial_match_rate: float = 0.0
    
    def calculate_derived_metrics(self) -> None:
        """Calculate derived quality metrics."""
        if self.total_addresses > 0:
            self.geocoding_success_rate = self.geocoded_addresses / self.total_addresses
        
        total_listings = self.complete_listings + self.incomplete_listings
        if total_listings > 0:
            self.completeness_score = self.complete_listings / total_listings
            self.duplicate_rate = self.duplicate_listings / total_listings
        
        if self.valid_listings + self.invalid_listings > 0:
            validation_total = self.valid_listings + self.invalid_listings
            # Validation success rate is implicit in valid_listings count
        
        if self.total_addresses > 0:
            self.spatial_match_rate = self.spatial_matches / self.total_addresses


@dataclass
class ErrorMetrics:
    """Error tracking and categorization metrics."""
    execution_id: str
    timestamp: datetime
    
    # Error categories
    network_errors: int = 0
    parsing_errors: int = 0
    database_errors: int = 0
    validation_errors: int = 0
    system_errors: int = 0
    
    # Error details
    error_details: List[Dict[str, Any]] = field(default_factory=list)
    critical_errors: int = 0
    recoverable_errors: int = 0
    
    # Error patterns
    most_common_errors: List[Tuple[str, int]] = field(default_factory=list)
    error_trends: Dict[str, List[int]] = field(default_factory=dict)
    
    def add_error(self, error_type: str, error_message: str, is_critical: bool = False) -> None:
        """Add an error to the metrics."""
        error_detail = {
            'type': error_type,
            'message': error_message,
            'timestamp': datetime.now().isoformat(),
            'critical': is_critical
        }
        self.error_details.append(error_detail)
        
        # Increment category counters
        if error_type == 'network':
            self.network_errors += 1
        elif error_type == 'parsing':
            self.parsing_errors += 1
        elif error_type == 'database':
            self.database_errors += 1
        elif error_type == 'validation':
            self.validation_errors += 1
        else:
            self.system_errors += 1
        
        if is_critical:
            self.critical_errors += 1
        else:
            self.recoverable_errors += 1


class MetricsCollector:
    """Comprehensive metrics collection system."""
    
    def __init__(self, db_manager: Optional[EnhancedDatabaseManager] = None):
        """
        Initialize metrics collector.
        
        Args:
            db_manager: Enhanced database manager for persistence
        """
        self.db_manager = db_manager or EnhancedDatabaseManager()
        self._performance_samples: List[PerformanceMetrics] = []
        self._start_time: Optional[datetime] = None
        self._peak_memory: float = 0.0
        self._peak_cpu: float = 0.0
        
        logger.info("Metrics collector initialized")
    
    def start_execution_tracking(self, execution_id: str, city: str) -> None:
        """
        Start tracking metrics for an execution.
        
        Args:
            execution_id: Unique execution identifier
            city: City being processed
        """
        self._start_time = datetime.now()
        self._peak_memory = 0.0
        self._peak_cpu = 0.0
        self._performance_samples.clear()
        
        logger.info(f"Started metrics tracking for execution {execution_id}")
    
    def collect_execution_metrics(self, execution_result: Any) -> ExecutionMetrics:
        """
        Collect comprehensive execution metrics from scraping result.
        
        Args:
            execution_result: Result object from scraping execution
            
        Returns:
            ExecutionMetrics with comprehensive execution data
        """
        metrics = ExecutionMetrics(
            execution_id=execution_result.execution_id,
            city=execution_result.city,
            started_at=execution_result.started_at,
            completed_at=execution_result.completed_at,
            status=execution_result.status.value if hasattr(execution_result.status, 'value') else str(execution_result.status),
            total_urls_discovered=getattr(execution_result, 'total_urls_discovered', 0),
            urls_processed=getattr(execution_result, 'urls_processed', 0),
            listings_new=getattr(execution_result, 'listings_new', 0),
            listings_updated=getattr(execution_result, 'listings_updated', 0),
            listings_skipped=getattr(execution_result, 'listings_skipped', 0),
            listings_failed=getattr(execution_result, 'listings_failed', 0)
        )
        
        # Calculate derived metrics
        metrics.calculate_derived_metrics()
        
        logger.info(f"Collected execution metrics for {metrics.execution_id}: "
                   f"{metrics.success_rate:.2%} success rate, "
                   f"{metrics.urls_per_minute:.1f} URLs/min")
        
        return metrics
    
    def collect_performance_metrics(self, execution_id: str) -> PerformanceMetrics:
        """
        Collect current system performance metrics.
        
        Args:
            execution_id: Execution identifier for tracking
            
        Returns:
            PerformanceMetrics with current system state
        """
        try:
            # Get system metrics
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get network stats (simplified, with fallback)
            network_bytes_sent = 0
            network_bytes_received = 0
            try:
                network_io = psutil.net_io_counters()
                if network_io:
                    network_bytes_sent = network_io.bytes_sent
                    network_bytes_received = network_io.bytes_recv
            except (AttributeError, OSError):
                # Fallback for systems where network counters aren't available
                pass
            
            metrics = PerformanceMetrics(
                execution_id=execution_id,
                timestamp=datetime.now(),
                memory_usage_mb=memory.used / 1024 / 1024,
                memory_available_mb=memory.available / 1024 / 1024,
                cpu_usage_percent=cpu_percent,
                network_bytes_sent=network_bytes_sent,
                network_bytes_received=network_bytes_received
            )
            
            # Update peaks
            self._peak_memory = max(self._peak_memory, metrics.memory_usage_mb)
            self._peak_cpu = max(self._peak_cpu, metrics.cpu_usage_percent)
            
            metrics.memory_peak_mb = self._peak_memory
            metrics.cpu_peak_percent = self._peak_cpu
            
            # Store sample for trend analysis
            self._performance_samples.append(metrics)
            
            return metrics
            
        except Exception as e:
            logger.warning(f"Failed to collect performance metrics: {e}")
            return PerformanceMetrics(execution_id=execution_id, timestamp=datetime.now())
    
    def collect_data_quality_metrics(self, execution_id: str, city: str) -> DataQualityMetrics:
        """
        Collect data quality metrics from database.
        
        Args:
            execution_id: Execution identifier
            city: City being analyzed
            
        Returns:
            DataQualityMetrics with quality assessment
        """
        try:
            # Get data quality information from database
            quality_data = self.db_manager.get_data_quality_metrics(city, execution_id)
            
            metrics = DataQualityMetrics(
                execution_id=execution_id,
                city=city,
                timestamp=datetime.now(),
                total_addresses=quality_data.get('total_addresses', 0),
                geocoded_addresses=quality_data.get('geocoded_addresses', 0),
                complete_listings=quality_data.get('complete_listings', 0),
                incomplete_listings=quality_data.get('incomplete_listings', 0),
                valid_listings=quality_data.get('valid_listings', 0),
                invalid_listings=quality_data.get('invalid_listings', 0),
                duplicate_listings=quality_data.get('duplicate_listings', 0),
                spatial_matches=quality_data.get('spatial_matches', 0),
                validation_errors=quality_data.get('validation_errors', [])
            )
            
            # Calculate derived metrics
            metrics.calculate_derived_metrics()
            
            logger.info(f"Collected data quality metrics for {city}: "
                       f"{metrics.geocoding_success_rate:.2%} geocoding success, "
                       f"{metrics.completeness_score:.2%} completeness")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect data quality metrics: {e}")
            return DataQualityMetrics(execution_id=execution_id, city=city, timestamp=datetime.now())
    
    def collect_error_metrics(self, execution_id: str, error_logs: List[Dict[str, Any]]) -> ErrorMetrics:
        """
        Collect and categorize error metrics.
        
        Args:
            execution_id: Execution identifier
            error_logs: List of error log entries
            
        Returns:
            ErrorMetrics with categorized error information
        """
        metrics = ErrorMetrics(
            execution_id=execution_id,
            timestamp=datetime.now()
        )
        
        # Process error logs
        error_counts = {}
        for error_log in error_logs:
            error_type = self._categorize_error(error_log.get('message', ''))
            error_message = error_log.get('message', 'Unknown error')
            is_critical = error_log.get('level', '').upper() in ['ERROR', 'CRITICAL']
            
            metrics.add_error(error_type, error_message, is_critical)
            
            # Count for common errors
            error_key = f"{error_type}:{error_message[:50]}"
            error_counts[error_key] = error_counts.get(error_key, 0) + 1
        
        # Set most common errors
        metrics.most_common_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        logger.info(f"Collected error metrics for {execution_id}: "
                   f"{metrics.critical_errors} critical, {metrics.recoverable_errors} recoverable")
        
        return metrics
    
    def _categorize_error(self, error_message: str) -> str:
        """
        Categorize error based on message content.
        
        Args:
            error_message: Error message to categorize
            
        Returns:
            Error category string
        """
        error_message_lower = error_message.lower()
        
        # Check for network errors first (most specific)
        if any(keyword in error_message_lower for keyword in ['network', 'connection', 'timeout', 'http']):
            return 'network'
        # Check for parsing errors
        elif any(keyword in error_message_lower for keyword in ['parse', 'json', 'xml', 'html', 'format']):
            return 'parsing'
        # Check for database errors (but not if it contains connection - that's network)
        elif any(keyword in error_message_lower for keyword in ['database', 'sql', 'duckdb', 'table']) and 'connection' not in error_message_lower:
            return 'database'
        # Check for validation errors (but not if it contains format - that's parsing)
        elif any(keyword in error_message_lower for keyword in ['validation', 'invalid', 'constraint']) and 'format' not in error_message_lower:
            return 'validation'
        else:
            return 'system'
    
    def get_historical_trends(self, city: str, days_back: int = 30) -> Dict[str, List[Any]]:
        """
        Get historical trend data for analysis.
        
        Args:
            city: City to analyze
            days_back: Number of days of history to retrieve
            
        Returns:
            Dictionary with historical trend data
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Get execution history from database
            executions = self.db_manager.get_execution_history(city, start_date, end_date)
            
            trends = {
                'dates': [],
                'success_rates': [],
                'execution_times': [],
                'listings_processed': [],
                'error_rates': [],
                'data_quality_scores': []
            }
            
            for execution in executions:
                trends['dates'].append(execution.started_at.date().isoformat())
                trends['success_rates'].append(execution.get('success_rate', 0))
                trends['execution_times'].append(execution.get('execution_time_seconds', 0))
                trends['listings_processed'].append(execution.get('listings_processed', 0))
                trends['error_rates'].append(execution.get('error_rate', 0))
                trends['data_quality_scores'].append(execution.get('data_quality_score', 0))
            
            logger.info(f"Retrieved {len(executions)} historical executions for {city}")
            return trends
            
        except Exception as e:
            logger.error(f"Failed to get historical trends: {e}")
            return {}
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary from collected samples.
        
        Returns:
            Dictionary with performance summary statistics
        """
        if not self._performance_samples:
            return {}
        
        memory_values = [s.memory_usage_mb for s in self._performance_samples]
        cpu_values = [s.cpu_usage_percent for s in self._performance_samples]
        
        return {
            'memory_avg_mb': sum(memory_values) / len(memory_values),
            'memory_peak_mb': max(memory_values),
            'memory_min_mb': min(memory_values),
            'cpu_avg_percent': sum(cpu_values) / len(cpu_values),
            'cpu_peak_percent': max(cpu_values),
            'cpu_min_percent': min(cpu_values),
            'sample_count': len(self._performance_samples),
            'duration_minutes': (datetime.now() - self._start_time).total_seconds() / 60 if self._start_time else 0
        }
    
    def export_metrics(self, execution_id: str, format: str = 'json') -> Dict[str, Any]:
        """
        Export all collected metrics for an execution.
        
        Args:
            execution_id: Execution to export metrics for
            format: Export format ('json', 'dict')
            
        Returns:
            Exported metrics data
        """
        try:
            # This would typically query the database for stored metrics
            # For now, return a summary structure
            metrics_data = {
                'execution_id': execution_id,
                'export_timestamp': datetime.now().isoformat(),
                'performance_summary': self.get_performance_summary(),
                'sample_count': len(self._performance_samples)
            }
            
            logger.info(f"Exported metrics for execution {execution_id}")
            return metrics_data
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return {}