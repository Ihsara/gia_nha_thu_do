"""
Comprehensive Audit Logging and Data Lineage Tracking

This module provides comprehensive audit logging capabilities for the multi-city
automation system, including execution tracking, error logging, and data lineage.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from loguru import logger

from ..database.manager import EnhancedDatabaseManager


class AuditEventType(Enum):
    """Audit event type enumeration."""
    AUTOMATION_START = "automation_start"
    AUTOMATION_COMPLETE = "automation_complete"
    AUTOMATION_ERROR = "automation_error"
    CITY_EXECUTION_START = "city_execution_start"
    CITY_EXECUTION_SUCCESS = "city_execution_success"
    CITY_EXECUTION_ERROR = "city_execution_error"
    CLUSTER_COORDINATION = "cluster_coordination"
    WORK_DISTRIBUTION = "work_distribution"
    CIRCUIT_BREAKER_TRIP = "circuit_breaker_trip"
    RATE_LIMIT_HIT = "rate_limit_hit"
    RETRY_ATTEMPT = "retry_attempt"
    DATA_QUALITY_CHECK = "data_quality_check"
    CONFIGURATION_CHANGE = "configuration_change"
    SYSTEM_HEALTH_CHECK = "system_health_check"


class AuditSeverity(Enum):
    """Audit event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents an audit event."""
    event_type: AuditEventType
    timestamp: datetime = None
    execution_id: Optional[str] = None
    city: Optional[str] = None
    node_id: Optional[str] = None
    severity: AuditSeverity = AuditSeverity.INFO
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.details is None:
            self.details = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        """Create audit event from dictionary."""
        data['event_type'] = AuditEventType(data['event_type'])
        data['severity'] = AuditSeverity(data['severity'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class DataLineageEntry:
    """Represents a data lineage entry."""
    entry_id: str
    timestamp: datetime
    table_name: str
    record_id: str
    operation: str  # INSERT, UPDATE, DELETE
    data_source: str
    execution_id: Optional[str] = None
    parent_record_id: Optional[str] = None
    transformation_applied: Optional[str] = None
    quality_score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.entry_id is None:
            self.entry_id = str(uuid.uuid4())
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert lineage entry to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class ExecutionTrace:
    """Represents an execution trace for debugging."""
    trace_id: str
    execution_id: str
    timestamp: datetime
    component: str
    operation: str
    duration_ms: Optional[int] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_info: Optional[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.trace_id is None:
            self.trace_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert execution trace to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class AuditLogger:
    """
    Comprehensive audit logger for multi-city automation system.
    
    Provides:
    - Event logging with structured data
    - Data lineage tracking
    - Execution tracing for debugging
    - Performance monitoring
    - Compliance reporting
    """
    
    def __init__(self, 
                 db_manager: Optional[EnhancedDatabaseManager] = None,
                 log_to_file: bool = True,
                 log_file_path: Optional[str] = None):
        """
        Initialize audit logger.
        
        Args:
            db_manager: Database manager for persistent storage
            log_to_file: Whether to log to file
            log_file_path: Custom log file path
        """
        self.db_manager = db_manager
        self.log_to_file = log_to_file
        
        # Setup file logging if enabled
        if log_to_file:
            if log_file_path is None:
                log_file_path = "logs/audit_{time:YYYY-MM-DD}.log"
            
            # Configure loguru for audit logging
            logger.add(
                log_file_path,
                rotation="1 day",
                retention="30 days",
                level="DEBUG",
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | AUDIT | {message}",
                filter=lambda record: record.get("audit", False)
            )
        
        # Initialize database tables if needed
        self._initialize_audit_tables()
        
        logger.info("Audit logger initialized")
    
    def log_event(self, event: AuditEvent) -> None:
        """
        Log an audit event.
        
        Args:
            event: Audit event to log
        """
        try:
            # Log to structured logger
            logger.bind(audit=True).info(
                f"AUDIT: {event.event_type.value} | "
                f"execution_id={event.execution_id} | "
                f"city={event.city} | "
                f"severity={event.severity.value} | "
                f"details={json.dumps(event.details)}"
            )
            
            # Store in database if available
            if self.db_manager:
                self._store_audit_event(event)
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
    
    def log_data_lineage(self, lineage_entry: DataLineageEntry) -> None:
        """
        Log a data lineage entry.
        
        Args:
            lineage_entry: Data lineage entry to log
        """
        try:
            # Log to structured logger
            logger.bind(audit=True).info(
                f"LINEAGE: {lineage_entry.operation} | "
                f"table={lineage_entry.table_name} | "
                f"record_id={lineage_entry.record_id} | "
                f"source={lineage_entry.data_source} | "
                f"execution_id={lineage_entry.execution_id}"
            )
            
            # Store in database if available
            if self.db_manager:
                self._store_lineage_entry(lineage_entry)
            
        except Exception as e:
            logger.error(f"Failed to log data lineage: {e}")
    
    def log_execution_trace(self, trace: ExecutionTrace) -> None:
        """
        Log an execution trace for debugging.
        
        Args:
            trace: Execution trace to log
        """
        try:
            # Log to structured logger
            logger.bind(audit=True).debug(
                f"TRACE: {trace.component}.{trace.operation} | "
                f"execution_id={trace.execution_id} | "
                f"duration_ms={trace.duration_ms} | "
                f"error={trace.error_info is not None}"
            )
            
            # Store in database if available
            if self.db_manager:
                self._store_execution_trace(trace)
            
        except Exception as e:
            logger.error(f"Failed to log execution trace: {e}")
    
    def create_execution_context(self, execution_id: str) -> 'ExecutionContext':
        """
        Create an execution context for tracking related events.
        
        Args:
            execution_id: Execution ID to track
            
        Returns:
            ExecutionContext instance
        """
        return ExecutionContext(self, execution_id)
    
    def get_audit_events(self, 
                        execution_id: Optional[str] = None,
                        city: Optional[str] = None,
                        event_type: Optional[AuditEventType] = None,
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 100) -> List[AuditEvent]:
        """
        Retrieve audit events with filtering.
        
        Args:
            execution_id: Filter by execution ID
            city: Filter by city
            event_type: Filter by event type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of events to return
            
        Returns:
            List of audit events
        """
        if not self.db_manager:
            logger.warning("No database manager available for audit event retrieval")
            return []
        
        try:
            # This would be implemented with actual database queries
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Failed to retrieve audit events: {e}")
            return []
    
    def get_data_lineage(self, 
                        record_id: str,
                        table_name: Optional[str] = None) -> List[DataLineageEntry]:
        """
        Get data lineage for a specific record.
        
        Args:
            record_id: Record ID to trace
            table_name: Optional table name filter
            
        Returns:
            List of data lineage entries
        """
        if not self.db_manager:
            logger.warning("No database manager available for lineage retrieval")
            return []
        
        try:
            # This would be implemented with actual database queries
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Failed to retrieve data lineage: {e}")
            return []
    
    def generate_audit_report(self, 
                            execution_id: str,
                            include_traces: bool = False) -> Dict[str, Any]:
        """
        Generate comprehensive audit report for an execution.
        
        Args:
            execution_id: Execution ID to report on
            include_traces: Include execution traces in report
            
        Returns:
            Audit report dictionary
        """
        try:
            report = {
                'execution_id': execution_id,
                'generated_at': datetime.now().isoformat(),
                'events': [],
                'lineage_entries': [],
                'summary': {
                    'total_events': 0,
                    'error_events': 0,
                    'warning_events': 0,
                    'cities_processed': set(),
                    'execution_duration': None
                }
            }
            
            # Get audit events for execution
            events = self.get_audit_events(execution_id=execution_id, limit=1000)
            report['events'] = [event.to_dict() for event in events]
            
            # Calculate summary statistics
            report['summary']['total_events'] = len(events)
            report['summary']['error_events'] = sum(
                1 for event in events 
                if event.severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]
            )
            report['summary']['warning_events'] = sum(
                1 for event in events 
                if event.severity == AuditSeverity.WARNING
            )
            report['summary']['cities_processed'] = list(set(
                event.city for event in events 
                if event.city is not None
            ))
            
            # Calculate execution duration
            start_events = [e for e in events if e.event_type == AuditEventType.AUTOMATION_START]
            end_events = [e for e in events if e.event_type == AuditEventType.AUTOMATION_COMPLETE]
            
            if start_events and end_events:
                start_time = min(e.timestamp for e in start_events)
                end_time = max(e.timestamp for e in end_events)
                report['summary']['execution_duration'] = (end_time - start_time).total_seconds()
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate audit report: {e}")
            return {
                'execution_id': execution_id,
                'generated_at': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def _initialize_audit_tables(self) -> None:
        """Initialize audit tables in database."""
        if not self.db_manager:
            return
        
        try:
            # This would create the actual audit tables
            # For now, just log that we would initialize them
            logger.debug("Audit tables would be initialized here")
            
        except Exception as e:
            logger.error(f"Failed to initialize audit tables: {e}")
    
    def _store_audit_event(self, event: AuditEvent) -> None:
        """Store audit event in database."""
        try:
            # This would store the event in the database
            # For now, just log that we would store it
            logger.debug(f"Would store audit event: {event.event_type.value}")
            
        except Exception as e:
            logger.error(f"Failed to store audit event: {e}")
    
    def _store_lineage_entry(self, lineage_entry: DataLineageEntry) -> None:
        """Store data lineage entry in database."""
        try:
            # This would store the lineage entry in the database
            # For now, just log that we would store it
            logger.debug(f"Would store lineage entry: {lineage_entry.operation}")
            
        except Exception as e:
            logger.error(f"Failed to store lineage entry: {e}")
    
    def _store_execution_trace(self, trace: ExecutionTrace) -> None:
        """Store execution trace in database."""
        try:
            # This would store the trace in the database
            # For now, just log that we would store it
            logger.debug(f"Would store execution trace: {trace.component}.{trace.operation}")
            
        except Exception as e:
            logger.error(f"Failed to store execution trace: {e}")


class ExecutionContext:
    """
    Context manager for tracking related audit events within an execution.
    """
    
    def __init__(self, audit_logger: AuditLogger, execution_id: str):
        """
        Initialize execution context.
        
        Args:
            audit_logger: Audit logger instance
            execution_id: Execution ID to track
        """
        self.audit_logger = audit_logger
        self.execution_id = execution_id
        self.start_time = datetime.now()
        self.traces: List[ExecutionTrace] = []
    
    def log_event(self, 
                  event_type: AuditEventType,
                  city: Optional[str] = None,
                  severity: AuditSeverity = AuditSeverity.INFO,
                  message: Optional[str] = None,
                  details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log an audit event within this execution context.
        
        Args:
            event_type: Type of audit event
            city: City associated with event
            severity: Event severity
            message: Event message
            details: Additional event details
        """
        event = AuditEvent(
            event_type=event_type,
            execution_id=self.execution_id,
            city=city,
            severity=severity,
            message=message,
            details=details
        )
        self.audit_logger.log_event(event)
    
    def log_lineage(self,
                   table_name: str,
                   record_id: str,
                   operation: str,
                   data_source: str,
                   parent_record_id: Optional[str] = None,
                   transformation_applied: Optional[str] = None,
                   quality_score: Optional[float] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Log data lineage within this execution context.
        
        Args:
            table_name: Name of the table
            record_id: Record identifier
            operation: Operation performed (INSERT, UPDATE, DELETE)
            data_source: Source of the data
            parent_record_id: Parent record ID if applicable
            transformation_applied: Description of transformation
            quality_score: Data quality score
            metadata: Additional metadata
        """
        lineage_entry = DataLineageEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            table_name=table_name,
            record_id=record_id,
            operation=operation,
            data_source=data_source,
            execution_id=self.execution_id,
            parent_record_id=parent_record_id,
            transformation_applied=transformation_applied,
            quality_score=quality_score,
            metadata=metadata
        )
        self.audit_logger.log_data_lineage(lineage_entry)
    
    def trace_operation(self, 
                       component: str, 
                       operation: str) -> 'OperationTracer':
        """
        Create an operation tracer for detailed execution tracking.
        
        Args:
            component: Component name
            operation: Operation name
            
        Returns:
            OperationTracer context manager
        """
        return OperationTracer(self.audit_logger, self.execution_id, component, operation)


class OperationTracer:
    """
    Context manager for tracing individual operations.
    """
    
    def __init__(self, 
                 audit_logger: AuditLogger,
                 execution_id: str,
                 component: str,
                 operation: str):
        """
        Initialize operation tracer.
        
        Args:
            audit_logger: Audit logger instance
            execution_id: Execution ID
            component: Component name
            operation: Operation name
        """
        self.audit_logger = audit_logger
        self.execution_id = execution_id
        self.component = component
        self.operation = operation
        self.start_time: Optional[datetime] = None
        self.trace: Optional[ExecutionTrace] = None
    
    def __enter__(self) -> 'OperationTracer':
        """Enter the operation tracing context."""
        self.start_time = datetime.now()
        self.trace = ExecutionTrace(
            trace_id=str(uuid.uuid4()),
            execution_id=self.execution_id,
            timestamp=self.start_time,
            component=self.component,
            operation=self.operation
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the operation tracing context."""
        if self.trace and self.start_time:
            end_time = datetime.now()
            self.trace.duration_ms = int((end_time - self.start_time).total_seconds() * 1000)
            
            if exc_type is not None:
                self.trace.error_info = {
                    'exception_type': exc_type.__name__,
                    'exception_message': str(exc_val),
                    'traceback': str(exc_tb) if exc_tb else None
                }
            
            self.audit_logger.log_execution_trace(self.trace)
    
    def set_input_data(self, input_data: Dict[str, Any]) -> None:
        """Set input data for the operation."""
        if self.trace:
            self.trace.input_data = input_data
    
    def set_output_data(self, output_data: Dict[str, Any]) -> None:
        """Set output data for the operation."""
        if self.trace:
            self.trace.output_data = output_data
    
    def set_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """Set performance metrics for the operation."""
        if self.trace:
            self.trace.performance_metrics = metrics