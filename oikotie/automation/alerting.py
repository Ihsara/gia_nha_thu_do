"""
Alerting and Notification System for Daily Scraper Automation

This module provides configurable alert conditions, multiple notification channels,
immediate alerting for critical errors, alert escalation and de-duplication logic,
and comprehensive alert configuration management.
"""

import json
import smtplib
import requests
import hashlib
import duckdb
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger

from .metrics import ExecutionMetrics, PerformanceMetrics, DataQualityMetrics, ErrorMetrics
from ..database.manager import EnhancedDatabaseManager


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertConditionType(Enum):
    """Types of alert conditions."""
    ERROR_RATE = "error_rate"
    SUCCESS_RATE = "success_rate"
    EXECUTION_TIME = "execution_time"
    DATA_QUALITY = "data_quality"
    SYSTEM_RESOURCE = "system_resource"
    EXECUTION_FAILURE = "execution_failure"
    GEOCODING_FAILURE = "geocoding_failure"
    DATABASE_ERROR = "database_error"
    NETWORK_ERROR = "network_error"


class NotificationChannel(Enum):
    """Available notification channels."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"  # Future implementation


@dataclass
class AlertCondition:
    """Configuration for an alert condition."""
    name: str
    condition_type: AlertConditionType
    threshold_value: float
    comparison_operator: str  # '>', '<', '>=', '<=', '=='
    severity: AlertSeverity
    enabled: bool = True
    description: str = ""
    
    # Escalation settings
    escalation_minutes: int = 30  # Time before escalation
    max_escalations: int = 3
    
    # De-duplication settings
    dedup_window_minutes: int = 60  # Don't repeat same alert within this window
    
    def evaluate(self, value: float) -> bool:
        """
        Evaluate if the condition is met.
        
        Args:
            value: Value to compare against threshold
            
        Returns:
            True if alert condition is met
        """
        if not self.enabled:
            return False
        
        if self.comparison_operator == '>':
            return value > self.threshold_value
        elif self.comparison_operator == '<':
            return value < self.threshold_value
        elif self.comparison_operator == '>=':
            return value >= self.threshold_value
        elif self.comparison_operator == '<=':
            return value <= self.threshold_value
        elif self.comparison_operator == '==':
            return abs(value - self.threshold_value) < 0.001  # Float comparison
        else:
            logger.warning(f"Unknown comparison operator: {self.comparison_operator}")
            return False


@dataclass
class NotificationChannelConfig:
    """Configuration for a notification channel."""
    channel_type: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Channel-specific settings
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    timeout_seconds: int = 30


@dataclass
class Alert:
    """An active alert instance."""
    alert_id: str
    condition_name: str
    severity: AlertSeverity
    message: str
    triggered_at: datetime
    city: Optional[str] = None
    execution_id: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    
    # Alert lifecycle
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    # Escalation tracking
    escalation_level: int = 0
    last_escalated_at: Optional[datetime] = None
    
    def get_alert_hash(self) -> str:
        """Generate hash for de-duplication."""
        hash_input = f"{self.condition_name}:{self.city}:{self.message}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def should_escalate(self, escalation_minutes: int) -> bool:
        """Check if alert should be escalated."""
        if self.resolved or self.acknowledged:
            return False
        
        if self.last_escalated_at is None:
            # First escalation check
            return (datetime.now() - self.triggered_at).total_seconds() > (escalation_minutes * 60)
        else:
            # Subsequent escalations
            return (datetime.now() - self.last_escalated_at).total_seconds() > (escalation_minutes * 60)


@dataclass
class AlertingConfiguration:
    """Configuration for the alerting system."""
    enabled: bool = True
    alert_conditions: List[AlertCondition] = field(default_factory=list)
    notification_channels: List[NotificationChannelConfig] = field(default_factory=list)
    
    # Global settings
    max_alerts_per_hour: int = 50
    alert_history_days: int = 30
    enable_escalation: bool = True
    enable_deduplication: bool = True
    
    # Default notification settings
    default_channels_by_severity: Dict[str, List[str]] = field(default_factory=lambda: {
        "info": ["email"],
        "warning": ["email", "slack"],
        "critical": ["email", "slack", "webhook"],
        "emergency": ["email", "slack", "webhook", "sms"]
    })


class AlertManager:
    """Comprehensive alert management system."""
    
    def __init__(self, 
                 config: Optional[AlertingConfiguration] = None,
                 db_manager: Optional[EnhancedDatabaseManager] = None):
        """
        Initialize alert manager.
        
        Args:
            config: Alerting configuration
            db_manager: Database manager for persistence
        """
        self.config = config or AlertingConfiguration()
        self.db_manager = db_manager or EnhancedDatabaseManager()
        
        # Active alerts tracking
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._notification_handlers: Dict[NotificationChannel, Callable] = {}
        
        # Rate limiting
        self._alert_count_last_hour = 0
        self._last_hour_reset = datetime.now()
        
        # Initialize notification handlers
        self._setup_notification_handlers()
        
        # Initialize database schema
        self._initialize_alert_schema()
        
        logger.info("Alert manager initialized with {} conditions and {} channels",
                   len(self.config.alert_conditions), len(self.config.notification_channels))
    
    def _setup_notification_handlers(self) -> None:
        """Setup notification channel handlers."""
        self._notification_handlers = {
            NotificationChannel.EMAIL: self._send_email_notification,
            NotificationChannel.SLACK: self._send_slack_notification,
            NotificationChannel.WEBHOOK: self._send_webhook_notification,
            NotificationChannel.SMS: self._send_sms_notification
        }
    
    def _initialize_alert_schema(self) -> None:
        """Initialize database schema for alerts."""
        try:
            with duckdb.connect(str(self.db_manager.db_path)) as con:
                # Create alerts table
                con.execute("""
                    CREATE TABLE IF NOT EXISTS alerts (
                        alert_id VARCHAR(50) PRIMARY KEY,
                        condition_name VARCHAR(100) NOT NULL,
                        severity VARCHAR(20) NOT NULL,
                        message TEXT NOT NULL,
                        triggered_at TIMESTAMP NOT NULL,
                        city VARCHAR(50),
                        execution_id VARCHAR(50),
                        metric_value REAL,
                        threshold_value REAL,
                        acknowledged BOOLEAN DEFAULT FALSE,
                        acknowledged_at TIMESTAMP,
                        acknowledged_by VARCHAR(100),
                        resolved BOOLEAN DEFAULT FALSE,
                        resolved_at TIMESTAMP,
                        escalation_level INTEGER DEFAULT 0,
                        last_escalated_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create alert notifications table
                con.execute("""
                    CREATE TABLE IF NOT EXISTS alert_notifications (
                        id INTEGER PRIMARY KEY,
                        alert_id VARCHAR(50) NOT NULL,
                        channel_type VARCHAR(20) NOT NULL,
                        sent_at TIMESTAMP NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0
                    )
                """)
            
            logger.debug("Alert database schema initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize alert schema: {e}")
    
    def evaluate_execution_metrics(self, metrics: ExecutionMetrics) -> List[Alert]:
        """
        Evaluate execution metrics against alert conditions.
        
        Args:
            metrics: Execution metrics to evaluate
            
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        
        for condition in self.config.alert_conditions:
            if not condition.enabled:
                continue
            
            alert = None
            
            if condition.condition_type == AlertConditionType.ERROR_RATE:
                if condition.evaluate(metrics.error_rate):
                    alert = self._create_alert(
                        condition, 
                        f"High error rate detected: {metrics.error_rate:.2%} (threshold: {condition.threshold_value:.2%})",
                        metrics.city, metrics.execution_id, metrics.error_rate, condition.threshold_value
                    )
            
            elif condition.condition_type == AlertConditionType.SUCCESS_RATE:
                if condition.evaluate(metrics.success_rate):
                    alert = self._create_alert(
                        condition,
                        f"Low success rate detected: {metrics.success_rate:.2%} (threshold: {condition.threshold_value:.2%})",
                        metrics.city, metrics.execution_id, metrics.success_rate, condition.threshold_value
                    )
            
            elif condition.condition_type == AlertConditionType.EXECUTION_TIME:
                duration = metrics.duration_seconds or 0
                if condition.evaluate(duration):
                    alert = self._create_alert(
                        condition,
                        f"Execution time exceeded threshold: {duration:.1f}s (threshold: {condition.threshold_value:.1f}s)",
                        metrics.city, metrics.execution_id, duration, condition.threshold_value
                    )
            
            elif condition.condition_type == AlertConditionType.EXECUTION_FAILURE:
                if metrics.status in ['failed', 'error'] and condition.evaluate(1.0):
                    alert = self._create_alert(
                        condition,
                        f"Execution failed for {metrics.city}: {metrics.status}",
                        metrics.city, metrics.execution_id, 1.0, condition.threshold_value
                    )
            
            if alert:
                triggered_alerts.append(alert)
        
        return triggered_alerts
    
    def evaluate_data_quality_metrics(self, metrics: DataQualityMetrics) -> List[Alert]:
        """
        Evaluate data quality metrics against alert conditions.
        
        Args:
            metrics: Data quality metrics to evaluate
            
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        
        for condition in self.config.alert_conditions:
            if not condition.enabled:
                continue
            
            alert = None
            
            if condition.condition_type == AlertConditionType.DATA_QUALITY:
                if condition.evaluate(metrics.completeness_score):
                    alert = self._create_alert(
                        condition,
                        f"Data quality below threshold: {metrics.completeness_score:.2%} (threshold: {condition.threshold_value:.2%})",
                        metrics.city, metrics.execution_id, metrics.completeness_score, condition.threshold_value
                    )
            
            elif condition.condition_type == AlertConditionType.GEOCODING_FAILURE:
                if condition.evaluate(metrics.geocoding_success_rate):
                    alert = self._create_alert(
                        condition,
                        f"Geocoding success rate below threshold: {metrics.geocoding_success_rate:.2%} (threshold: {condition.threshold_value:.2%})",
                        metrics.city, metrics.execution_id, metrics.geocoding_success_rate, condition.threshold_value
                    )
            
            if alert:
                triggered_alerts.append(alert)
        
        return triggered_alerts
    
    def evaluate_performance_metrics(self, metrics: PerformanceMetrics) -> List[Alert]:
        """
        Evaluate performance metrics against alert conditions.
        
        Args:
            metrics: Performance metrics to evaluate
            
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        
        for condition in self.config.alert_conditions:
            if not condition.enabled:
                continue
            
            alert = None
            
            if condition.condition_type == AlertConditionType.SYSTEM_RESOURCE:
                # Check memory usage
                if condition.name.lower().find('memory') != -1:
                    if condition.evaluate(metrics.memory_usage_mb):
                        alert = self._create_alert(
                            condition,
                            f"High memory usage: {metrics.memory_usage_mb:.1f}MB (threshold: {condition.threshold_value:.1f}MB)",
                            None, metrics.execution_id, metrics.memory_usage_mb, condition.threshold_value
                        )
                
                # Check CPU usage
                elif condition.name.lower().find('cpu') != -1:
                    if condition.evaluate(metrics.cpu_usage_percent):
                        alert = self._create_alert(
                            condition,
                            f"High CPU usage: {metrics.cpu_usage_percent:.1f}% (threshold: {condition.threshold_value:.1f}%)",
                            None, metrics.execution_id, metrics.cpu_usage_percent, condition.threshold_value
                        )
            
            if alert:
                triggered_alerts.append(alert)
        
        return triggered_alerts
    
    def evaluate_error_metrics(self, metrics: ErrorMetrics) -> List[Alert]:
        """
        Evaluate error metrics against alert conditions.
        
        Args:
            metrics: Error metrics to evaluate
            
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        
        for condition in self.config.alert_conditions:
            if not condition.enabled:
                continue
            
            alert = None
            
            if condition.condition_type == AlertConditionType.DATABASE_ERROR:
                if condition.evaluate(metrics.database_errors):
                    alert = self._create_alert(
                        condition,
                        f"Database errors detected: {metrics.database_errors} (threshold: {condition.threshold_value})",
                        None, metrics.execution_id, float(metrics.database_errors), condition.threshold_value
                    )
            
            elif condition.condition_type == AlertConditionType.NETWORK_ERROR:
                if condition.evaluate(metrics.network_errors):
                    alert = self._create_alert(
                        condition,
                        f"Network errors detected: {metrics.network_errors} (threshold: {condition.threshold_value})",
                        None, metrics.execution_id, float(metrics.network_errors), condition.threshold_value
                    )
            
            if alert:
                triggered_alerts.append(alert)
        
        return triggered_alerts
    
    def _create_alert(self, condition: AlertCondition, message: str, 
                     city: Optional[str] = None, execution_id: Optional[str] = None,
                     metric_value: Optional[float] = None, threshold_value: Optional[float] = None) -> Alert:
        """
        Create a new alert instance.
        
        Args:
            condition: Alert condition that triggered
            message: Alert message
            city: City associated with alert
            execution_id: Execution ID associated with alert
            metric_value: Actual metric value
            threshold_value: Threshold value that was exceeded
            
        Returns:
            New Alert instance
        """
        alert_id = f"{condition.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(message) % 10000:04d}"
        
        alert = Alert(
            alert_id=alert_id,
            condition_name=condition.name,
            severity=condition.severity,
            message=message,
            triggered_at=datetime.now(),
            city=city,
            execution_id=execution_id,
            metric_value=metric_value,
            threshold_value=threshold_value
        )
        
        return alert
    
    def process_alerts(self, alerts: List[Alert]) -> None:
        """
        Process a list of alerts (de-duplication, rate limiting, notifications).
        
        Args:
            alerts: List of alerts to process
        """
        if not self.config.enabled:
            logger.debug("Alerting is disabled, skipping alert processing")
            return
        
        # Rate limiting check
        self._check_rate_limits()
        
        for alert in alerts:
            try:
                # De-duplication check
                if self.config.enable_deduplication and self._is_duplicate_alert(alert):
                    logger.debug(f"Skipping duplicate alert: {alert.alert_id}")
                    continue
                
                # Rate limiting check
                if self._alert_count_last_hour >= self.config.max_alerts_per_hour:
                    logger.warning(f"Alert rate limit exceeded, skipping alert: {alert.alert_id}")
                    continue
                
                # Process the alert
                self._process_single_alert(alert)
                self._alert_count_last_hour += 1
                
            except Exception as e:
                logger.error(f"Failed to process alert {alert.alert_id}: {e}")
    
    def _is_duplicate_alert(self, alert: Alert) -> bool:
        """
        Check if alert is a duplicate within the de-duplication window.
        
        Args:
            alert: Alert to check
            
        Returns:
            True if alert is a duplicate
        """
        alert_hash = alert.get_alert_hash()
        
        # Check active alerts
        for active_alert in self._active_alerts.values():
            if (active_alert.get_alert_hash() == alert_hash and 
                not active_alert.resolved and
                (datetime.now() - active_alert.triggered_at).total_seconds() < (60 * 60)):  # 1 hour window
                return True
        
        # Check recent history
        cutoff_time = datetime.now() - timedelta(hours=1)
        for historical_alert in self._alert_history:
            if (historical_alert.get_alert_hash() == alert_hash and
                historical_alert.triggered_at > cutoff_time):
                return True
        
        return False
    
    def _process_single_alert(self, alert: Alert) -> None:
        """
        Process a single alert (store, notify, track).
        
        Args:
            alert: Alert to process
        """
        # Store alert in database
        self._store_alert(alert)
        
        # Add to active alerts
        self._active_alerts[alert.alert_id] = alert
        
        # Send notifications
        self._send_notifications(alert)
        
        # Log alert
        logger.warning(f"Alert triggered: {alert.condition_name} - {alert.message}")
    
    def _store_alert(self, alert: Alert) -> None:
        """
        Store alert in database.
        
        Args:
            alert: Alert to store
        """
        try:
            with duckdb.connect(str(self.db_manager.db_path)) as con:
                con.execute("""
                    INSERT INTO alerts (
                        alert_id, condition_name, severity, message, triggered_at,
                        city, execution_id, metric_value, threshold_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert.alert_id, alert.condition_name, alert.severity.value,
                    alert.message, alert.triggered_at, alert.city, alert.execution_id,
                    alert.metric_value, alert.threshold_value
                ))
            
        except Exception as e:
            logger.error(f"Failed to store alert {alert.alert_id}: {e}")
    
    def _send_notifications(self, alert: Alert) -> None:
        """
        Send notifications for an alert.
        
        Args:
            alert: Alert to send notifications for
        """
        # Determine which channels to use based on severity
        channels_to_use = self.config.default_channels_by_severity.get(
            alert.severity.value, ["email"]
        )
        
        for channel_name in channels_to_use:
            try:
                channel_type = NotificationChannel(channel_name)
                channel_config = self._get_channel_config(channel_type)
                
                if channel_config and channel_config.enabled:
                    success = self._send_notification(alert, channel_type, channel_config)
                    self._log_notification(alert.alert_id, channel_type, success)
                
            except ValueError:
                logger.warning(f"Unknown notification channel: {channel_name}")
            except Exception as e:
                logger.error(f"Failed to send notification via {channel_name}: {e}")
    
    def _get_channel_config(self, channel_type: NotificationChannel) -> Optional[NotificationChannelConfig]:
        """
        Get configuration for a notification channel.
        
        Args:
            channel_type: Type of notification channel
            
        Returns:
            Channel configuration or None if not found
        """
        for config in self.config.notification_channels:
            if config.channel_type == channel_type:
                return config
        return None
    
    def _send_notification(self, alert: Alert, channel_type: NotificationChannel, 
                          config: NotificationChannelConfig) -> bool:
        """
        Send notification via specified channel.
        
        Args:
            alert: Alert to send
            channel_type: Type of notification channel
            config: Channel configuration
            
        Returns:
            True if notification sent successfully
        """
        handler = self._notification_handlers.get(channel_type)
        if not handler:
            logger.error(f"No handler for notification channel: {channel_type}")
            return False
        
        for attempt in range(config.retry_attempts):
            try:
                success = handler(alert, config)
                if success:
                    return True
                
            except Exception as e:
                logger.warning(f"Notification attempt {attempt + 1} failed for {channel_type}: {e}")
                
                if attempt < config.retry_attempts - 1:
                    import time
                    time.sleep(config.retry_delay_seconds)
        
        return False
    
    def _send_email_notification(self, alert: Alert, config: NotificationChannelConfig) -> bool:
        """
        Send email notification.
        
        Args:
            alert: Alert to send
            config: Email channel configuration
            
        Returns:
            True if email sent successfully
        """
        try:
            email_config = config.config
            
            # Create email message
            msg = MIMEMultipart()
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.condition_name}"
            msg['From'] = email_config.get('from_address', '')
            msg['To'] = ', '.join(email_config.get('to_addresses', []))
            
            # Create email body
            body = f"""
Alert Details:
- Condition: {alert.condition_name}
- Severity: {alert.severity.value.upper()}
- Message: {alert.message}
- Triggered: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}
- City: {alert.city or 'N/A'}
- Execution ID: {alert.execution_id or 'N/A'}

Metric Details:
- Current Value: {alert.metric_value}
- Threshold: {alert.threshold_value}

Alert ID: {alert.alert_id}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(email_config['smtp_server'], email_config.get('smtp_port', 587)) as server:
                if email_config.get('use_tls', True):
                    server.starttls()
                if email_config.get('username') and email_config.get('password'):
                    server.login(email_config['username'], email_config['password'])
                server.send_message(msg)
            
            logger.info(f"Email notification sent for alert {alert.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
    
    def _send_slack_notification(self, alert: Alert, config: NotificationChannelConfig) -> bool:
        """
        Send Slack notification.
        
        Args:
            alert: Alert to send
            config: Slack channel configuration
            
        Returns:
            True if Slack message sent successfully
        """
        try:
            slack_config = config.config
            webhook_url = slack_config.get('webhook_url')
            
            if not webhook_url:
                logger.error("Slack webhook URL not configured")
                return False
            
            # Determine emoji based on severity
            emoji_map = {
                AlertSeverity.INFO: ":information_source:",
                AlertSeverity.WARNING: ":warning:",
                AlertSeverity.CRITICAL: ":exclamation:",
                AlertSeverity.EMERGENCY: ":rotating_light:"
            }
            
            emoji = emoji_map.get(alert.severity, ":bell:")
            
            # Create Slack message
            message = {
                "text": f"{emoji} Alert: {alert.condition_name}",
                "attachments": [
                    {
                        "color": "danger" if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY] else "warning",
                        "fields": [
                            {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                            {"title": "City", "value": alert.city or "N/A", "short": True},
                            {"title": "Message", "value": alert.message, "short": False},
                            {"title": "Triggered", "value": alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S'), "short": True},
                            {"title": "Alert ID", "value": alert.alert_id, "short": True}
                        ]
                    }
                ]
            }
            
            # Send to Slack
            response = requests.post(
                webhook_url, 
                json=message, 
                timeout=config.timeout_seconds
            )
            response.raise_for_status()
            
            logger.info(f"Slack notification sent for alert {alert.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
    
    def _send_webhook_notification(self, alert: Alert, config: NotificationChannelConfig) -> bool:
        """
        Send webhook notification.
        
        Args:
            alert: Alert to send
            config: Webhook channel configuration
            
        Returns:
            True if webhook sent successfully
        """
        try:
            webhook_config = config.config
            url = webhook_config.get('url')
            
            if not url:
                logger.error("Webhook URL not configured")
                return False
            
            # Create webhook payload
            payload = {
                "alert_id": alert.alert_id,
                "condition_name": alert.condition_name,
                "severity": alert.severity.value,
                "message": alert.message,
                "triggered_at": alert.triggered_at.isoformat(),
                "city": alert.city,
                "execution_id": alert.execution_id,
                "metric_value": alert.metric_value,
                "threshold_value": alert.threshold_value
            }
            
            # Get headers
            headers = webhook_config.get('headers', {'Content-Type': 'application/json'})
            
            # Send webhook
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=config.timeout_seconds
            )
            response.raise_for_status()
            
            logger.info(f"Webhook notification sent for alert {alert.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False
    
    def _send_sms_notification(self, alert: Alert, config: NotificationChannelConfig) -> bool:
        """
        Send SMS notification (placeholder for future implementation).
        
        Args:
            alert: Alert to send
            config: SMS channel configuration
            
        Returns:
            False (not implemented)
        """
        logger.warning("SMS notifications not yet implemented")
        return False
    
    def _log_notification(self, alert_id: str, channel_type: NotificationChannel, success: bool, error_message: str = None) -> None:
        """
        Log notification attempt.
        
        Args:
            alert_id: Alert ID
            channel_type: Notification channel type
            success: Whether notification was successful
            error_message: Error message if failed
        """
        try:
            self.db_manager.execute_query("""
                INSERT INTO alert_notifications (
                    alert_id, channel_type, sent_at, success, error_message
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                alert_id, channel_type.value, datetime.now(), success, error_message
            ))
            
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")
    
    def _check_rate_limits(self) -> None:
        """Check and reset rate limits if needed."""
        now = datetime.now()
        
        # Reset hourly counter if needed
        if (now - self._last_hour_reset).total_seconds() > 3600:
            self._alert_count_last_hour = 0
            self._last_hour_reset = now
    
    def process_escalations(self) -> None:
        """Process alert escalations."""
        if not self.config.enable_escalation:
            return
        
        for alert in list(self._active_alerts.values()):
            if alert.resolved or alert.acknowledged:
                continue
            
            # Find the condition for escalation settings
            condition = None
            for c in self.config.alert_conditions:
                if c.name == alert.condition_name:
                    condition = c
                    break
            
            if not condition:
                continue
            
            # Check if escalation is needed
            if alert.should_escalate(condition.escalation_minutes):
                if alert.escalation_level < condition.max_escalations:
                    self._escalate_alert(alert, condition)
                else:
                    logger.warning(f"Alert {alert.alert_id} reached maximum escalation level")
    
    def _escalate_alert(self, alert: Alert, condition: AlertCondition) -> None:
        """
        Escalate an alert.
        
        Args:
            alert: Alert to escalate
            condition: Alert condition with escalation settings
        """
        alert.escalation_level += 1
        alert.last_escalated_at = datetime.now()
        
        # Update in database
        try:
            self.db_manager.execute_query("""
                UPDATE alerts 
                SET escalation_level = ?, last_escalated_at = ?
                WHERE alert_id = ?
            """, (alert.escalation_level, alert.last_escalated_at, alert.alert_id))
            
        except Exception as e:
            logger.error(f"Failed to update alert escalation: {e}")
        
        # Create escalation message
        escalated_message = f"ESCALATED (Level {alert.escalation_level}): {alert.message}"
        
        # Create escalated alert
        escalated_alert = Alert(
            alert_id=f"{alert.alert_id}_ESC_{alert.escalation_level}",
            condition_name=alert.condition_name,
            severity=alert.severity,
            message=escalated_message,
            triggered_at=datetime.now(),
            city=alert.city,
            execution_id=alert.execution_id,
            metric_value=alert.metric_value,
            threshold_value=alert.threshold_value,
            escalation_level=alert.escalation_level
        )
        
        # Send escalated notifications
        self._send_notifications(escalated_alert)
        
        logger.warning(f"Alert {alert.alert_id} escalated to level {alert.escalation_level}")
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID to acknowledge
            acknowledged_by: Who acknowledged the alert
            
        Returns:
            True if acknowledged successfully
        """
        try:
            # Update in database
            self.db_manager.execute_query("""
                UPDATE alerts 
                SET acknowledged = TRUE, acknowledged_at = ?, acknowledged_by = ?
                WHERE alert_id = ?
            """, (datetime.now(), acknowledged_by, alert_id))
            
            # Update in memory
            if alert_id in self._active_alerts:
                alert = self._active_alerts[alert_id]
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now()
                alert.acknowledged_by = acknowledged_by
            
            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID to resolve
            
        Returns:
            True if resolved successfully
        """
        try:
            # Update in database
            self.db_manager.execute_query("""
                UPDATE alerts 
                SET resolved = TRUE, resolved_at = ?
                WHERE alert_id = ?
            """, (datetime.now(), alert_id))
            
            # Update in memory and move to history
            if alert_id in self._active_alerts:
                alert = self._active_alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = datetime.now()
                
                # Move to history
                self._alert_history.append(alert)
                del self._active_alerts[alert_id]
            
            logger.info(f"Alert {alert_id} resolved")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resolve alert {alert_id}: {e}")
            return False
    
    def get_active_alerts(self) -> List[Alert]:
        """
        Get list of active alerts.
        
        Returns:
            List of active alerts
        """
        return list(self._active_alerts.values())
    
    def get_alert_history(self, days: int = 7) -> List[Alert]:
        """
        Get alert history from database.
        
        Args:
            days: Number of days of history to retrieve
            
        Returns:
            List of historical alerts
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            results = self.db_manager.execute_query("""
                SELECT alert_id, condition_name, severity, message, triggered_at,
                       city, execution_id, metric_value, threshold_value,
                       acknowledged, acknowledged_at, acknowledged_by,
                       resolved, resolved_at, escalation_level, last_escalated_at
                FROM alerts 
                WHERE triggered_at >= ?
                ORDER BY triggered_at DESC
            """, (cutoff_date,))
            
            alerts = []
            for row in results:
                alert = Alert(
                    alert_id=row[0],
                    condition_name=row[1],
                    severity=AlertSeverity(row[2]),
                    message=row[3],
                    triggered_at=row[4],
                    city=row[5],
                    execution_id=row[6],
                    metric_value=row[7],
                    threshold_value=row[8],
                    acknowledged=row[9],
                    acknowledged_at=row[10],
                    acknowledged_by=row[11],
                    resolved=row[12],
                    resolved_at=row[13],
                    escalation_level=row[14] or 0,
                    last_escalated_at=row[15]
                )
                alerts.append(alert)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to get alert history: {e}")
            return []
    
    def get_alert_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get alert statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with alert statistics
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get basic counts
            results = self.db_manager.execute_query("""
                SELECT 
                    COUNT(*) as total_alerts,
                    COUNT(CASE WHEN resolved = TRUE THEN 1 END) as resolved_alerts,
                    COUNT(CASE WHEN acknowledged = TRUE THEN 1 END) as acknowledged_alerts,
                    COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_alerts,
                    COUNT(CASE WHEN severity = 'warning' THEN 1 END) as warning_alerts,
                    COUNT(CASE WHEN severity = 'info' THEN 1 END) as info_alerts,
                    COUNT(CASE WHEN severity = 'emergency' THEN 1 END) as emergency_alerts
                FROM alerts 
                WHERE triggered_at >= ?
            """, (cutoff_date,))
            
            if results:
                row = results[0]
                stats = {
                    "period_days": days,
                    "total_alerts": row[0],
                    "resolved_alerts": row[1],
                    "acknowledged_alerts": row[2],
                    "resolution_rate": row[1] / max(row[0], 1),
                    "acknowledgment_rate": row[2] / max(row[0], 1),
                    "alerts_by_severity": {
                        "critical": row[3],
                        "warning": row[4],
                        "info": row[5],
                        "emergency": row[6]
                    }
                }
            else:
                stats = {
                    "period_days": days,
                    "total_alerts": 0,
                    "resolved_alerts": 0,
                    "acknowledged_alerts": 0,
                    "resolution_rate": 0.0,
                    "acknowledgment_rate": 0.0,
                    "alerts_by_severity": {
                        "critical": 0,
                        "warning": 0,
                        "info": 0,
                        "emergency": 0
                    }
                }
            
            # Get top conditions
            condition_results = self.db_manager.execute_query("""
                SELECT condition_name, COUNT(*) as count
                FROM alerts 
                WHERE triggered_at >= ?
                GROUP BY condition_name
                ORDER BY count DESC
                LIMIT 10
            """, (cutoff_date,))
            
            stats["top_conditions"] = [
                {"condition": row[0], "count": row[1]}
                for row in condition_results
            ]
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get alert statistics: {e}")
            return {}
    
    def test_notification_channel(self, channel_type: NotificationChannel) -> bool:
        """
        Test a notification channel.
        
        Args:
            channel_type: Type of channel to test
            
        Returns:
            True if test successful
        """
        # Create test alert
        test_alert = Alert(
            alert_id=f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            condition_name="Test Alert",
            severity=AlertSeverity.INFO,
            message="This is a test alert to verify notification channel configuration",
            triggered_at=datetime.now()
        )
        
        # Get channel config
        channel_config = self._get_channel_config(channel_type)
        if not channel_config:
            logger.error(f"No configuration found for channel type: {channel_type}")
            return False
        
        if not channel_config.enabled:
            logger.error(f"Channel type {channel_type} is disabled")
            return False
        
        # Send test notification
        try:
            success = self._send_notification(test_alert, channel_type, channel_config)
            if success:
                logger.info(f"Test notification sent successfully via {channel_type.value}")
            else:
                logger.error(f"Test notification failed for {channel_type.value}")
            
            return success
            
        except Exception as e:
            logger.error(f"Test notification failed for {channel_type.value}: {e}")
            return False
    
    def cleanup_old_alerts(self) -> int:
        """
        Clean up old alerts based on retention policy.
        
        Returns:
            Number of alerts cleaned up
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.alert_history_days)
            
            # Get count before deletion
            count_result = self.db_manager.execute_query("""
                SELECT COUNT(*) FROM alerts WHERE triggered_at < ?
            """, (cutoff_date,))
            
            count_to_delete = count_result[0][0] if count_result else 0
            
            if count_to_delete > 0:
                # Delete old alerts
                self.db_manager.execute_query("""
                    DELETE FROM alerts WHERE triggered_at < ?
                """, (cutoff_date,))
                
                # Delete associated notifications
                self.db_manager.execute_query("""
                    DELETE FROM alert_notifications 
                    WHERE alert_id NOT IN (SELECT alert_id FROM alerts)
                """)
                
                logger.info(f"Cleaned up {count_to_delete} old alerts")
            
            return count_to_delete
            
        except Exception as e:
            logger.error(f"Failed to cleanup old alerts: {e}")
            return 0


def create_alert_manager(config_path: Optional[str] = None, 
                        db_manager: Optional[EnhancedDatabaseManager] = None) -> AlertManager:
    """
    Create and configure an AlertManager instance.
    
    Args:
        config_path: Path to alert configuration file
        db_manager: Database manager instance
        
    Returns:
        Configured AlertManager instance
    """
    from .alert_config import AlertConfigManager
    
    # Load configuration
    config_manager = AlertConfigManager(config_path)
    config = config_manager.load_configuration()
    
    # Create alert manager
    alert_manager = AlertManager(config, db_manager)
    
    return alert_manager


def evaluate_scraping_result_for_alerts(result, alert_manager: AlertManager) -> None:
    """
    Evaluate a scraping result and trigger alerts if needed.
    
    Args:
        result: Scraping result to evaluate
        alert_manager: Alert manager to use for evaluation
    """
    from .metrics import ExecutionMetrics, DataQualityMetrics, PerformanceMetrics, ErrorMetrics
    
    try:
        # Convert result to metrics objects
        execution_metrics = ExecutionMetrics(
            execution_id=result.execution_id,
            city=result.city,
            status=result.status,
            duration_seconds=result.execution_time_seconds,
            listings_processed=result.listings_processed,
            listings_new=result.listings_new,
            listings_updated=result.listings_updated,
            listings_failed=result.listings_failed,
            success_rate=result.success_rate,
            error_rate=result.error_rate
        )
        
        data_quality_metrics = DataQualityMetrics(
            execution_id=result.execution_id,
            city=result.city,
            completeness_score=getattr(result, 'data_quality_score', 1.0),
            geocoding_success_rate=getattr(result, 'geocoding_success_rate', 1.0),
            validation_errors=getattr(result, 'validation_errors', 0),
            duplicate_rate=getattr(result, 'duplicate_rate', 0.0)
        )
        
        performance_metrics = PerformanceMetrics(
            execution_id=result.execution_id,
            memory_usage_mb=getattr(result, 'memory_usage_mb', 0.0),
            cpu_usage_percent=getattr(result, 'cpu_usage_percent', 0.0),
            network_requests=getattr(result, 'network_requests', 0),
            database_operations=getattr(result, 'database_operations', 0)
        )
        
        error_metrics = ErrorMetrics(
            execution_id=result.execution_id,
            database_errors=getattr(result, 'database_errors', 0),
            network_errors=getattr(result, 'network_errors', 0),
            parsing_errors=getattr(result, 'parsing_errors', 0),
            validation_errors=getattr(result, 'validation_errors', 0)
        )
        
        # Evaluate metrics and collect alerts
        all_alerts = []
        all_alerts.extend(alert_manager.evaluate_execution_metrics(execution_metrics))
        all_alerts.extend(alert_manager.evaluate_data_quality_metrics(data_quality_metrics))
        all_alerts.extend(alert_manager.evaluate_performance_metrics(performance_metrics))
        all_alerts.extend(alert_manager.evaluate_error_metrics(error_metrics))
        
        # Process alerts
        if all_alerts:
            alert_manager.process_alerts(all_alerts)
            logger.info(f"Processed {len(all_alerts)} alerts for execution {result.execution_id}")
        
        # Process escalations
        alert_manager.process_escalations()
        
    except Exception as e:
        logger.error(f"Failed to evaluate scraping result for alerts: {e}")


# Export main classes and functions
__all__ = [
    'AlertManager',
    'Alert',
    'AlertCondition',
    'AlertSeverity',
    'AlertConditionType',
    'NotificationChannel',
    'NotificationChannelConfig',
    'AlertingConfiguration',
    'create_alert_manager',
    'evaluate_scraping_result_for_alerts'
]