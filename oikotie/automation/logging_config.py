"""
Structured Logging Configuration for Daily Scraper Automation

This module provides comprehensive logging configuration with structured output,
log aggregation capabilities, and integration with monitoring systems.
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from loguru import logger
import threading
from collections import deque


class StructuredFormatter:
    """Custom formatter for structured JSON logging."""
    
    def __init__(self, include_extra: bool = True):
        """
        Initialize structured formatter.
        
        Args:
            include_extra: Whether to include extra fields in log records
        """
        self.include_extra = include_extra
    
    def format(self, record: Dict[str, Any]) -> str:
        """
        Format log record as structured JSON.
        
        Args:
            record: Log record dictionary
            
        Returns:
            Formatted JSON string
        """
        # Extract basic fields
        log_entry = {
            'timestamp': record['time'].isoformat(),
            'level': record['level'].name,
            'logger': record['name'],
            'message': record['message'],
            'module': record.get('module', ''),
            'function': record.get('function', ''),
            'line': record.get('line', 0)
        }
        
        # Add process and thread info
        process_info = record.get('process', {})
        thread_info = record.get('thread', {})
        
        log_entry['process'] = {
            'id': getattr(process_info, 'id', 0) if hasattr(process_info, 'id') else process_info.get('id', 0) if isinstance(process_info, dict) else 0,
            'name': getattr(process_info, 'name', '') if hasattr(process_info, 'name') else process_info.get('name', '') if isinstance(process_info, dict) else ''
        }
        log_entry['thread'] = {
            'id': getattr(thread_info, 'id', 0) if hasattr(thread_info, 'id') else thread_info.get('id', 0) if isinstance(thread_info, dict) else 0,
            'name': getattr(thread_info, 'name', '') if hasattr(thread_info, 'name') else thread_info.get('name', '') if isinstance(thread_info, dict) else ''
        }
        
        # Add exception info if present
        if record.get('exception'):
            log_entry['exception'] = {
                'type': record['exception'].type.__name__ if record['exception'].type else None,
                'value': str(record['exception'].value) if record['exception'].value else None,
                'traceback': record['exception'].traceback if record['exception'].traceback else None
            }
        
        # Add extra fields if enabled
        if self.include_extra and 'extra' in record:
            log_entry['extra'] = record['extra']
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class LogAggregator:
    """Log aggregation system for collecting and analyzing logs."""
    
    def __init__(self, max_logs: int = 10000):
        """
        Initialize log aggregator.
        
        Args:
            max_logs: Maximum number of logs to keep in memory
        """
        self.max_logs = max_logs
        self.logs: deque = deque(maxlen=max_logs)
        self.error_logs: deque = deque(maxlen=1000)  # Keep more errors
        self.lock = threading.Lock()
        
        # Statistics
        self.log_counts = {
            'DEBUG': 0,
            'INFO': 0,
            'WARNING': 0,
            'ERROR': 0,
            'CRITICAL': 0
        }
        
        logger.info(f"Log aggregator initialized with capacity for {max_logs} logs")
    
    def add_log(self, record: Dict[str, Any]) -> None:
        """
        Add a log record to the aggregator.
        
        Args:
            record: Log record dictionary
        """
        with self.lock:
            # Parse the structured log entry
            try:
                if isinstance(record, str):
                    log_entry = json.loads(record)
                else:
                    log_entry = record
                
                # Add to main log collection
                self.logs.append(log_entry)
                
                # Track error logs separately
                level = log_entry.get('level', 'INFO')
                if level in ['ERROR', 'CRITICAL']:
                    self.error_logs.append(log_entry)
                
                # Update statistics
                self.log_counts[level] = self.log_counts.get(level, 0) + 1
                
            except (json.JSONDecodeError, KeyError) as e:
                # Fallback for non-structured logs
                fallback_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'level': 'INFO',
                    'message': str(record),
                    'parse_error': str(e)
                }
                self.logs.append(fallback_entry)
    
    def get_recent_logs(self, count: int = 100, level_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent log entries.
        
        Args:
            count: Number of logs to return
            level_filter: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            
        Returns:
            List of log entries
        """
        with self.lock:
            logs = list(self.logs)
            
            # Filter by level if specified
            if level_filter:
                logs = [log for log in logs if log.get('level') == level_filter.upper()]
            
            # Return most recent entries
            return logs[-count:] if count < len(logs) else logs
    
    def get_error_logs(self, count: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent error logs.
        
        Args:
            count: Number of error logs to return
            
        Returns:
            List of error log entries
        """
        with self.lock:
            error_logs = list(self.error_logs)
            return error_logs[-count:] if count < len(error_logs) else error_logs
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """
        Get log statistics.
        
        Returns:
            Dictionary with log statistics
        """
        with self.lock:
            total_logs = sum(self.log_counts.values())
            
            return {
                'total_logs': total_logs,
                'logs_by_level': self.log_counts.copy(),
                'error_rate': (self.log_counts.get('ERROR', 0) + self.log_counts.get('CRITICAL', 0)) / max(total_logs, 1),
                'current_buffer_size': len(self.logs),
                'max_buffer_size': self.max_logs,
                'error_buffer_size': len(self.error_logs)
            }
    
    def search_logs(self, query: str, count: int = 100) -> List[Dict[str, Any]]:
        """
        Search logs for a specific query.
        
        Args:
            query: Search query string
            count: Maximum number of results to return
            
        Returns:
            List of matching log entries
        """
        with self.lock:
            matching_logs = []
            query_lower = query.lower()
            
            for log_entry in reversed(self.logs):  # Search from most recent
                message = log_entry.get('message', '').lower()
                logger_name = log_entry.get('logger', '').lower()
                module = log_entry.get('module', '').lower()
                
                if (query_lower in message or 
                    query_lower in logger_name or 
                    query_lower in module):
                    matching_logs.append(log_entry)
                    
                    if len(matching_logs) >= count:
                        break
            
            return matching_logs
    
    def export_logs(self, filepath: str, count: Optional[int] = None) -> bool:
        """
        Export logs to a file.
        
        Args:
            filepath: Path to export file
            count: Number of logs to export (all if None)
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            with self.lock:
                logs_to_export = list(self.logs)
                
                if count:
                    logs_to_export = logs_to_export[-count:]
            
            with open(filepath, 'w', encoding='utf-8') as f:
                for log_entry in logs_to_export:
                    f.write(json.dumps(log_entry, default=str) + '\n')
            
            logger.info(f"Exported {len(logs_to_export)} logs to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export logs to {filepath}: {e}")
            return False


class LoggingConfiguration:
    """Comprehensive logging configuration manager."""
    
    def __init__(self, 
                 log_directory: str = "logs",
                 enable_structured_logging: bool = True,
                 enable_log_aggregation: bool = True,
                 log_level: str = "INFO"):
        """
        Initialize logging configuration.
        
        Args:
            log_directory: Directory for log files
            enable_structured_logging: Enable structured JSON logging
            enable_log_aggregation: Enable in-memory log aggregation
            log_level: Minimum log level
        """
        self.log_directory = Path(log_directory)
        self.enable_structured_logging = enable_structured_logging
        self.enable_log_aggregation = enable_log_aggregation
        self.log_level = log_level
        
        # Create log directory
        self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize log aggregator if enabled
        self.log_aggregator: Optional[LogAggregator] = None
        if enable_log_aggregation:
            self.log_aggregator = LogAggregator()
        
        # Initialize structured formatter if enabled
        self.structured_formatter: Optional[StructuredFormatter] = None
        if enable_structured_logging:
            self.structured_formatter = StructuredFormatter()
        
        logger.info(f"Logging configuration initialized - Level: {log_level}, Structured: {enable_structured_logging}")
    
    def configure_logging(self) -> None:
        """Configure loguru logging with comprehensive settings."""
        # Remove default handler
        logger.remove()
        
        # Console handler with appropriate formatting
        if self.enable_structured_logging:
            # Structured console output for production
            logger.add(
                sys.stdout,
                format=self._format_structured_log,
                level=self.log_level,
                colorize=False,
                serialize=False
            )
        else:
            # Human-readable console output for development
            logger.add(
                sys.stdout,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                level=self.log_level,
                colorize=True
            )
        
        # File handlers
        self._configure_file_handlers()
        
        # Log aggregation handler
        if self.log_aggregator:
            logger.add(
                self._log_aggregation_sink,
                format=self._format_structured_log if self.enable_structured_logging else "{message}",
                level="DEBUG",  # Capture all levels for aggregation
                serialize=False
            )
        
        logger.info("Loguru logging configuration applied")
    
    def _configure_file_handlers(self) -> None:
        """Configure file-based log handlers."""
        # Main application log
        main_log_file = self.log_directory / "scraper_automation.log"
        logger.add(
            str(main_log_file),
            format=self._format_structured_log if self.enable_structured_logging else 
                   "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=self.log_level,
            rotation="100 MB",
            retention="30 days",
            compression="gz",
            serialize=False
        )
        
        # Error-only log
        error_log_file = self.log_directory / "scraper_errors.log"
        logger.add(
            str(error_log_file),
            format=self._format_structured_log if self.enable_structured_logging else 
                   "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
            level="ERROR",
            rotation="50 MB",
            retention="60 days",
            compression="gz",
            serialize=False
        )
        
        # Performance log (for monitoring integration)
        performance_log_file = self.log_directory / "scraper_performance.log"
        logger.add(
            str(performance_log_file),
            format=self._format_structured_log if self.enable_structured_logging else "{message}",
            level="INFO",
            rotation="50 MB",
            retention="14 days",
            compression="gz",
            serialize=False,
            filter=lambda record: "performance" in record.get("extra", {}).get("category", "")
        )
    
    def _format_structured_log(self, record: Dict[str, Any]) -> str:
        """Format log record using structured formatter."""
        if self.structured_formatter:
            return self.structured_formatter.format(record)
        return record.get('message', '')
    
    def _log_aggregation_sink(self, message: str) -> None:
        """Sink function for log aggregation."""
        if self.log_aggregator:
            self.log_aggregator.add_log(message)
    
    def get_log_aggregator(self) -> Optional[LogAggregator]:
        """Get the log aggregator instance."""
        return self.log_aggregator
    
    def create_execution_logger(self, execution_id: str, city: str) -> Any:
        """
        Create a logger with execution context.
        
        Args:
            execution_id: Execution identifier
            city: City being processed
            
        Returns:
            Logger with execution context
        """
        return logger.bind(
            execution_id=execution_id,
            city=city,
            category="execution"
        )
    
    def create_performance_logger(self) -> Any:
        """
        Create a logger for performance metrics.
        
        Returns:
            Logger for performance metrics
        """
        return logger.bind(category="performance")
    
    def create_monitoring_logger(self) -> Any:
        """
        Create a logger for monitoring events.
        
        Returns:
            Logger for monitoring events
        """
        return logger.bind(category="monitoring")
    
    def export_configuration(self) -> Dict[str, Any]:
        """
        Export logging configuration.
        
        Returns:
            Dictionary with logging configuration
        """
        return {
            'log_directory': str(self.log_directory),
            'log_level': self.log_level,
            'structured_logging': self.enable_structured_logging,
            'log_aggregation': self.enable_log_aggregation,
            'log_files': {
                'main': str(self.log_directory / "scraper_automation.log"),
                'errors': str(self.log_directory / "scraper_errors.log"),
                'performance': str(self.log_directory / "scraper_performance.log")
            },
            'aggregator_stats': self.log_aggregator.get_log_statistics() if self.log_aggregator else None
        }


def setup_monitoring_logging(log_level: str = "INFO", 
                           structured: bool = True,
                           log_dir: str = "logs") -> LoggingConfiguration:
    """
    Setup comprehensive logging for monitoring and observability.
    
    Args:
        log_level: Minimum log level
        structured: Enable structured JSON logging
        log_dir: Log directory path
        
    Returns:
        Configured LoggingConfiguration instance
    """
    config = LoggingConfiguration(
        log_directory=log_dir,
        enable_structured_logging=structured,
        enable_log_aggregation=True,
        log_level=log_level
    )
    
    config.configure_logging()
    
    logger.success("Monitoring logging configuration completed")
    return config


def create_monitoring_context(**kwargs) -> Dict[str, Any]:
    """
    Create monitoring context for structured logging.
    
    Args:
        **kwargs: Context fields
        
    Returns:
        Context dictionary for logging
    """
    context = {
        'timestamp': datetime.now().isoformat(),
        'monitoring': True
    }
    context.update(kwargs)
    return context


# Example usage functions for demonstration
def log_execution_start(execution_id: str, city: str, config: Dict[str, Any]) -> None:
    """Log execution start with structured context."""
    logger.bind(**create_monitoring_context(
        execution_id=execution_id,
        city=city,
        event="execution_start",
        config=config
    )).info(f"Starting scraper execution for {city}")


def log_performance_metric(metric_name: str, value: float, unit: str, **context) -> None:
    """Log performance metric with structured context."""
    logger.bind(**create_monitoring_context(
        metric_name=metric_name,
        metric_value=value,
        metric_unit=unit,
        event="performance_metric",
        **context
    )).info(f"Performance metric: {metric_name} = {value} {unit}")


def log_data_quality_issue(issue_type: str, description: str, city: str, **context) -> None:
    """Log data quality issue with structured context."""
    logger.bind(**create_monitoring_context(
        issue_type=issue_type,
        city=city,
        event="data_quality_issue",
        **context
    )).warning(f"Data quality issue in {city}: {description}")