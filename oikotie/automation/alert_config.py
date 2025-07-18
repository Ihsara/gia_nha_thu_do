"""
Alert Configuration Management for Daily Scraper Automation

This module provides configuration management for the alerting system,
including loading, validation, and management of alert conditions and
notification channels.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from loguru import logger

from .alerting import (
    AlertingConfiguration, AlertCondition, NotificationChannelConfig,
    AlertSeverity, AlertConditionType, NotificationChannel
)


class AlertConfigManager:
    """Manager for alert configuration loading and validation."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize alert configuration manager.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or "config/alert_config.json"
        self.config: Optional[AlertingConfiguration] = None
        
    def load_configuration(self) -> AlertingConfiguration:
        """
        Load alert configuration from file.
        
        Returns:
            AlertingConfiguration instance
        """
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            logger.warning(f"Alert config file not found: {config_file}, creating default")
            return self._create_default_configuration()
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            config = self._parse_configuration(config_data)
            self.config = config
            
            logger.info(f"Loaded alert configuration with {len(config.alert_conditions)} conditions "
                       f"and {len(config.notification_channels)} channels")
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to load alert configuration: {e}")
            logger.info("Using default configuration")
            return self._create_default_configuration()
    
    def _parse_configuration(self, config_data: Dict[str, Any]) -> AlertingConfiguration:
        """
        Parse configuration data into AlertingConfiguration.
        
        Args:
            config_data: Raw configuration data
            
        Returns:
            Parsed AlertingConfiguration
        """
        # Parse alert conditions
        alert_conditions = []
        for condition_data in config_data.get('alert_conditions', []):
            try:
                condition = AlertCondition(
                    name=condition_data['name'],
                    condition_type=AlertConditionType(condition_data['condition_type']),
                    threshold_value=float(condition_data['threshold_value']),
                    comparison_operator=condition_data['comparison_operator'],
                    severity=AlertSeverity(condition_data['severity']),
                    enabled=condition_data.get('enabled', True),
                    description=condition_data.get('description', ''),
                    escalation_minutes=condition_data.get('escalation_minutes', 30),
                    max_escalations=condition_data.get('max_escalations', 3),
                    dedup_window_minutes=condition_data.get('dedup_window_minutes', 60)
                )
                alert_conditions.append(condition)
                
            except (KeyError, ValueError) as e:
                logger.error(f"Invalid alert condition configuration: {e}")
                continue
        
        # Parse notification channels
        notification_channels = []
        for channel_data in config_data.get('notification_channels', []):
            try:
                channel = NotificationChannelConfig(
                    channel_type=NotificationChannel(channel_data['channel_type']),
                    enabled=channel_data.get('enabled', True),
                    config=channel_data.get('config', {}),
                    retry_attempts=channel_data.get('retry_attempts', 3),
                    retry_delay_seconds=channel_data.get('retry_delay_seconds', 5),
                    timeout_seconds=channel_data.get('timeout_seconds', 30)
                )
                notification_channels.append(channel)
                
            except (KeyError, ValueError) as e:
                logger.error(f"Invalid notification channel configuration: {e}")
                continue
        
        # Create configuration
        config = AlertingConfiguration(
            enabled=config_data.get('enabled', True),
            alert_conditions=alert_conditions,
            notification_channels=notification_channels,
            max_alerts_per_hour=config_data.get('max_alerts_per_hour', 50),
            alert_history_days=config_data.get('alert_history_days', 30),
            enable_escalation=config_data.get('enable_escalation', True),
            enable_deduplication=config_data.get('enable_deduplication', True),
            default_channels_by_severity=config_data.get('default_channels_by_severity', {
                "info": ["email"],
                "warning": ["email", "slack"],
                "critical": ["email", "slack", "webhook"],
                "emergency": ["email", "slack", "webhook", "sms"]
            })
        )
        
        return config
    
    def _create_default_configuration(self) -> AlertingConfiguration:
        """
        Create default alert configuration.
        
        Returns:
            Default AlertingConfiguration
        """
        # Default alert conditions
        default_conditions = [
            AlertCondition(
                name="High Error Rate",
                condition_type=AlertConditionType.ERROR_RATE,
                threshold_value=0.1,  # 10%
                comparison_operator=">",
                severity=AlertSeverity.WARNING,
                description="Alert when error rate exceeds 10%"
            ),
            AlertCondition(
                name="Critical Error Rate",
                condition_type=AlertConditionType.ERROR_RATE,
                threshold_value=0.25,  # 25%
                comparison_operator=">",
                severity=AlertSeverity.CRITICAL,
                description="Alert when error rate exceeds 25%"
            ),
            AlertCondition(
                name="Low Success Rate",
                condition_type=AlertConditionType.SUCCESS_RATE,
                threshold_value=0.8,  # 80%
                comparison_operator="<",
                severity=AlertSeverity.WARNING,
                description="Alert when success rate falls below 80%"
            ),
            AlertCondition(
                name="Critical Success Rate",
                condition_type=AlertConditionType.SUCCESS_RATE,
                threshold_value=0.5,  # 50%
                comparison_operator="<",
                severity=AlertSeverity.CRITICAL,
                description="Alert when success rate falls below 50%"
            ),
            AlertCondition(
                name="Long Execution Time",
                condition_type=AlertConditionType.EXECUTION_TIME,
                threshold_value=7200,  # 2 hours
                comparison_operator=">",
                severity=AlertSeverity.WARNING,
                description="Alert when execution takes longer than 2 hours"
            ),
            AlertCondition(
                name="Execution Failure",
                condition_type=AlertConditionType.EXECUTION_FAILURE,
                threshold_value=1.0,
                comparison_operator=">=",
                severity=AlertSeverity.CRITICAL,
                description="Alert when execution fails completely"
            ),
            AlertCondition(
                name="Low Data Quality",
                condition_type=AlertConditionType.DATA_QUALITY,
                threshold_value=0.9,  # 90%
                comparison_operator="<",
                severity=AlertSeverity.WARNING,
                description="Alert when data quality falls below 90%"
            ),
            AlertCondition(
                name="Geocoding Failure",
                condition_type=AlertConditionType.GEOCODING_FAILURE,
                threshold_value=0.85,  # 85%
                comparison_operator="<",
                severity=AlertSeverity.WARNING,
                description="Alert when geocoding success rate falls below 85%"
            ),
            AlertCondition(
                name="High Memory Usage",
                condition_type=AlertConditionType.SYSTEM_RESOURCE,
                threshold_value=4096,  # 4GB
                comparison_operator=">",
                severity=AlertSeverity.WARNING,
                description="Alert when memory usage exceeds 4GB"
            ),
            AlertCondition(
                name="Database Errors",
                condition_type=AlertConditionType.DATABASE_ERROR,
                threshold_value=5,
                comparison_operator=">",
                severity=AlertSeverity.CRITICAL,
                description="Alert when database errors exceed 5"
            ),
            AlertCondition(
                name="Network Errors",
                condition_type=AlertConditionType.NETWORK_ERROR,
                threshold_value=10,
                comparison_operator=">",
                severity=AlertSeverity.WARNING,
                description="Alert when network errors exceed 10"
            )
        ]
        
        # Default notification channels (with placeholder configs)
        default_channels = [
            NotificationChannelConfig(
                channel_type=NotificationChannel.EMAIL,
                enabled=False,  # Disabled by default until configured
                config={
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "use_tls": True,
                    "username": "",
                    "password": "",
                    "from_address": "",
                    "to_addresses": []
                }
            ),
            NotificationChannelConfig(
                channel_type=NotificationChannel.SLACK,
                enabled=False,  # Disabled by default until configured
                config={
                    "webhook_url": ""
                }
            ),
            NotificationChannelConfig(
                channel_type=NotificationChannel.WEBHOOK,
                enabled=False,  # Disabled by default until configured
                config={
                    "url": "",
                    "headers": {
                        "Content-Type": "application/json"
                    }
                }
            )
        ]
        
        config = AlertingConfiguration(
            enabled=True,
            alert_conditions=default_conditions,
            notification_channels=default_channels
        )
        
        # Save default configuration
        self.save_configuration(config)
        
        return config
    
    def save_configuration(self, config: AlertingConfiguration) -> bool:
        """
        Save alert configuration to file.
        
        Args:
            config: Configuration to save
            
        Returns:
            True if saved successfully
        """
        try:
            config_file = Path(self.config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to serializable format
            config_data = {
                "enabled": config.enabled,
                "max_alerts_per_hour": config.max_alerts_per_hour,
                "alert_history_days": config.alert_history_days,
                "enable_escalation": config.enable_escalation,
                "enable_deduplication": config.enable_deduplication,
                "default_channels_by_severity": config.default_channels_by_severity,
                "alert_conditions": [],
                "notification_channels": []
            }
            
            # Serialize alert conditions
            for condition in config.alert_conditions:
                condition_data = {
                    "name": condition.name,
                    "condition_type": condition.condition_type.value,
                    "threshold_value": condition.threshold_value,
                    "comparison_operator": condition.comparison_operator,
                    "severity": condition.severity.value,
                    "enabled": condition.enabled,
                    "description": condition.description,
                    "escalation_minutes": condition.escalation_minutes,
                    "max_escalations": condition.max_escalations,
                    "dedup_window_minutes": condition.dedup_window_minutes
                }
                config_data["alert_conditions"].append(condition_data)
            
            # Serialize notification channels
            for channel in config.notification_channels:
                channel_data = {
                    "channel_type": channel.channel_type.value,
                    "enabled": channel.enabled,
                    "config": channel.config,
                    "retry_attempts": channel.retry_attempts,
                    "retry_delay_seconds": channel.retry_delay_seconds,
                    "timeout_seconds": channel.timeout_seconds
                }
                config_data["notification_channels"].append(channel_data)
            
            # Write to file
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Saved alert configuration to {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save alert configuration: {e}")
            return False
    
    def validate_configuration(self, config: AlertingConfiguration) -> List[str]:
        """
        Validate alert configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate alert conditions
        condition_names = set()
        for condition in config.alert_conditions:
            # Check for duplicate names
            if condition.name in condition_names:
                errors.append(f"Duplicate alert condition name: {condition.name}")
            condition_names.add(condition.name)
            
            # Validate threshold values
            if condition.threshold_value < 0:
                errors.append(f"Negative threshold value in condition '{condition.name}': {condition.threshold_value}")
            
            # Validate comparison operators
            if condition.comparison_operator not in ['>', '<', '>=', '<=', '==']:
                errors.append(f"Invalid comparison operator in condition '{condition.name}': {condition.comparison_operator}")
            
            # Validate escalation settings
            if condition.escalation_minutes <= 0:
                errors.append(f"Invalid escalation minutes in condition '{condition.name}': {condition.escalation_minutes}")
            
            if condition.max_escalations < 0:
                errors.append(f"Invalid max escalations in condition '{condition.name}': {condition.max_escalations}")
        
        # Validate notification channels
        for channel in config.notification_channels:
            if channel.enabled:
                # Validate email configuration
                if channel.channel_type == NotificationChannel.EMAIL:
                    email_config = channel.config
                    required_fields = ['smtp_server', 'from_address', 'to_addresses']
                    for field in required_fields:
                        if not email_config.get(field):
                            errors.append(f"Missing email configuration field: {field}")
                    
                    if not isinstance(email_config.get('to_addresses', []), list):
                        errors.append("Email 'to_addresses' must be a list")
                
                # Validate Slack configuration
                elif channel.channel_type == NotificationChannel.SLACK:
                    if not channel.config.get('webhook_url'):
                        errors.append("Missing Slack webhook_url configuration")
                
                # Validate webhook configuration
                elif channel.channel_type == NotificationChannel.WEBHOOK:
                    if not channel.config.get('url'):
                        errors.append("Missing webhook URL configuration")
        
        # Validate global settings
        if config.max_alerts_per_hour <= 0:
            errors.append(f"Invalid max_alerts_per_hour: {config.max_alerts_per_hour}")
        
        if config.alert_history_days <= 0:
            errors.append(f"Invalid alert_history_days: {config.alert_history_days}")
        
        return errors
    
    def add_alert_condition(self, condition: AlertCondition) -> bool:
        """
        Add a new alert condition.
        
        Args:
            condition: Alert condition to add
            
        Returns:
            True if added successfully
        """
        if not self.config:
            self.config = self.load_configuration()
        
        # Check for duplicate names
        for existing_condition in self.config.alert_conditions:
            if existing_condition.name == condition.name:
                logger.error(f"Alert condition with name '{condition.name}' already exists")
                return False
        
        self.config.alert_conditions.append(condition)
        return self.save_configuration(self.config)
    
    def remove_alert_condition(self, condition_name: str) -> bool:
        """
        Remove an alert condition.
        
        Args:
            condition_name: Name of condition to remove
            
        Returns:
            True if removed successfully
        """
        if not self.config:
            self.config = self.load_configuration()
        
        original_count = len(self.config.alert_conditions)
        self.config.alert_conditions = [
            c for c in self.config.alert_conditions 
            if c.name != condition_name
        ]
        
        if len(self.config.alert_conditions) == original_count:
            logger.error(f"Alert condition '{condition_name}' not found")
            return False
        
        return self.save_configuration(self.config)
    
    def update_alert_condition(self, condition_name: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing alert condition.
        
        Args:
            condition_name: Name of condition to update
            updates: Dictionary of fields to update
            
        Returns:
            True if updated successfully
        """
        if not self.config:
            self.config = self.load_configuration()
        
        for condition in self.config.alert_conditions:
            if condition.name == condition_name:
                # Update fields
                for field, value in updates.items():
                    if hasattr(condition, field):
                        setattr(condition, field, value)
                    else:
                        logger.warning(f"Unknown field '{field}' for alert condition")
                
                return self.save_configuration(self.config)
        
        logger.error(f"Alert condition '{condition_name}' not found")
        return False
    
    def add_notification_channel(self, channel: NotificationChannelConfig) -> bool:
        """
        Add a new notification channel.
        
        Args:
            channel: Notification channel to add
            
        Returns:
            True if added successfully
        """
        if not self.config:
            self.config = self.load_configuration()
        
        # Check for duplicate channel types (only one per type for now)
        for existing_channel in self.config.notification_channels:
            if existing_channel.channel_type == channel.channel_type:
                logger.error(f"Notification channel of type '{channel.channel_type.value}' already exists")
                return False
        
        self.config.notification_channels.append(channel)
        return self.save_configuration(self.config)
    
    def update_notification_channel(self, channel_type: NotificationChannel, 
                                  updates: Dict[str, Any]) -> bool:
        """
        Update an existing notification channel.
        
        Args:
            channel_type: Type of channel to update
            updates: Dictionary of fields to update
            
        Returns:
            True if updated successfully
        """
        if not self.config:
            self.config = self.load_configuration()
        
        for channel in self.config.notification_channels:
            if channel.channel_type == channel_type:
                # Update fields
                for field, value in updates.items():
                    if field == 'config':
                        # Merge config dictionaries
                        channel.config.update(value)
                    elif hasattr(channel, field):
                        setattr(channel, field, value)
                    else:
                        logger.warning(f"Unknown field '{field}' for notification channel")
                
                return self.save_configuration(self.config)
        
        logger.error(f"Notification channel of type '{channel_type.value}' not found")
        return False
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current configuration.
        
        Returns:
            Dictionary with configuration summary
        """
        if not self.config:
            self.config = self.load_configuration()
        
        enabled_conditions = [c for c in self.config.alert_conditions if c.enabled]
        enabled_channels = [c for c in self.config.notification_channels if c.enabled]
        
        return {
            "alerting_enabled": self.config.enabled,
            "total_conditions": len(self.config.alert_conditions),
            "enabled_conditions": len(enabled_conditions),
            "total_channels": len(self.config.notification_channels),
            "enabled_channels": len(enabled_channels),
            "escalation_enabled": self.config.enable_escalation,
            "deduplication_enabled": self.config.enable_deduplication,
            "max_alerts_per_hour": self.config.max_alerts_per_hour,
            "alert_history_days": self.config.alert_history_days,
            "conditions_by_severity": {
                severity.value: len([c for c in enabled_conditions if c.severity == severity])
                for severity in AlertSeverity
            },
            "channels_by_type": {
                channel_type.value: any(c.channel_type == channel_type and c.enabled 
                                      for c in self.config.notification_channels)
                for channel_type in NotificationChannel
            }
        }


def create_sample_configuration() -> AlertingConfiguration:
    """
    Create a sample configuration for testing purposes.
    
    Returns:
        Sample AlertingConfiguration
    """
    manager = AlertConfigManager()
    return manager._create_default_configuration()


def validate_alert_config_file(config_path: str) -> List[str]:
    """
    Validate an alert configuration file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        List of validation errors
    """
    manager = AlertConfigManager(config_path)
    try:
        config = manager.load_configuration()
        return manager.validate_configuration(config)
    except Exception as e:
        return [f"Failed to load configuration: {e}"]