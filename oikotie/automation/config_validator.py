#!/usr/bin/env python3
"""
Configuration Validation Utility

This module provides standalone configuration validation functionality
that can be used independently of the main configuration management system.

Usage:
    from oikotie.automation.config_validator import validate_config_file
    
    errors = validate_config_file("config/scraper_config.json")
    if errors:
        print("Configuration errors found:")
        for error in errors:
            print(f"  - {error}")
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger


class ConfigValidator:
    """Standalone configuration validator"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_config_dict(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate a configuration dictionary.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            List of validation error messages
        """
        self.errors = []
        self.warnings = []
        
        # Validate top-level structure
        self._validate_top_level(config)
        
        # Validate tasks
        if 'tasks' in config:
            self._validate_tasks(config['tasks'])
        
        # Validate database configuration
        if 'database' in config:
            self._validate_database(config['database'])
        
        # Validate cluster configuration
        if 'cluster' in config:
            self._validate_cluster(config['cluster'])
        
        # Validate monitoring configuration
        if 'monitoring' in config:
            self._validate_monitoring(config['monitoring'])
        
        # Validate scheduling configuration
        if 'scheduling' in config:
            self._validate_scheduling(config['scheduling'])
        
        # Validate alerting configuration
        if 'alerting' in config:
            self._validate_alerting(config['alerting'])
        
        return self.errors
    
    def _validate_top_level(self, config: Dict[str, Any]):
        """Validate top-level configuration structure"""
        
        # Check for required sections
        if 'tasks' not in config:
            self.errors.append("Missing required section: 'tasks'")
        
        if 'database' not in config:
            self.errors.append("Missing required section: 'database'")
        
        # Validate deployment type
        if 'deployment_type' in config:
            valid_types = ['standalone', 'container', 'cluster', 'development']
            if config['deployment_type'] not in valid_types:
                self.errors.append(f"Invalid deployment_type: {config['deployment_type']}. Must be one of: {valid_types}")
        
        # Validate environment
        if 'environment' in config:
            if not isinstance(config['environment'], str) or not config['environment'].strip():
                self.errors.append("Environment must be a non-empty string")
        
        # Validate debug flag
        if 'debug' in config:
            if not isinstance(config['debug'], bool):
                self.errors.append("Debug flag must be a boolean")
    
    def _validate_tasks(self, tasks: List[Dict[str, Any]]):
        """Validate tasks configuration"""
        
        if not isinstance(tasks, list):
            self.errors.append("Tasks must be a list")
            return
        
        if len(tasks) == 0:
            self.errors.append("At least one task must be configured")
            return
        
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                self.errors.append(f"Task {i}: must be an object")
                continue
            
            # Required fields
            if 'city' not in task or not task['city']:
                self.errors.append(f"Task {i}: 'city' is required and cannot be empty")
            
            if 'url' not in task or not task['url']:
                self.errors.append(f"Task {i}: 'url' is required and cannot be empty")
            
            # Optional fields with validation
            if 'enabled' in task and not isinstance(task['enabled'], bool):
                self.errors.append(f"Task {i}: 'enabled' must be a boolean")
            
            if 'max_detail_workers' in task:
                workers = task['max_detail_workers']
                if not isinstance(workers, int) or workers < 1:
                    self.errors.append(f"Task {i}: 'max_detail_workers' must be a positive integer")
                elif workers > 20:
                    self.warnings.append(f"Task {i}: 'max_detail_workers' is very high ({workers}), consider reducing")
            
            if 'staleness_hours' in task:
                staleness = task['staleness_hours']
                if not isinstance(staleness, (int, float)) or staleness <= 0:
                    self.errors.append(f"Task {i}: 'staleness_hours' must be a positive number")
            
            if 'listing_limit' in task and task['listing_limit'] is not None:
                limit = task['listing_limit']
                if not isinstance(limit, int) or limit < 1:
                    self.errors.append(f"Task {i}: 'listing_limit' must be a positive integer or null")
            
            if 'retry_count' in task:
                retries = task['retry_count']
                if not isinstance(retries, int) or retries < 0:
                    self.errors.append(f"Task {i}: 'retry_count' must be a non-negative integer")
            
            if 'retry_backoff_factor' in task:
                backoff = task['retry_backoff_factor']
                if not isinstance(backoff, (int, float)) or backoff < 1:
                    self.errors.append(f"Task {i}: 'retry_backoff_factor' must be >= 1")
    
    def _validate_database(self, database: Dict[str, Any]):
        """Validate database configuration"""
        
        if not isinstance(database, dict):
            self.errors.append("Database configuration must be an object")
            return
        
        # Required fields
        if 'path' not in database or not database['path']:
            self.errors.append("Database 'path' is required and cannot be empty")
        
        # Optional fields with validation
        if 'connection_timeout' in database:
            timeout = database['connection_timeout']
            if not isinstance(timeout, int) or timeout <= 0:
                self.errors.append("Database 'connection_timeout' must be a positive integer")
        
        if 'max_connections' in database:
            max_conn = database['max_connections']
            if not isinstance(max_conn, int) or max_conn <= 0:
                self.errors.append("Database 'max_connections' must be a positive integer")
        
        if 'backup_enabled' in database and not isinstance(database['backup_enabled'], bool):
            self.errors.append("Database 'backup_enabled' must be a boolean")
        
        if 'backup_interval_hours' in database:
            interval = database['backup_interval_hours']
            if not isinstance(interval, int) or interval <= 0:
                self.errors.append("Database 'backup_interval_hours' must be a positive integer")
    
    def _validate_cluster(self, cluster: Dict[str, Any]):
        """Validate cluster configuration"""
        
        if not isinstance(cluster, dict):
            self.errors.append("Cluster configuration must be an object")
            return
        
        # If cluster is enabled, validate required fields
        if cluster.get('enabled', False):
            if 'redis_host' not in cluster or not cluster['redis_host']:
                self.errors.append("Cluster 'redis_host' is required when cluster is enabled")
            
            if 'redis_port' in cluster:
                port = cluster['redis_port']
                if not isinstance(port, int) or port < 1 or port > 65535:
                    self.errors.append("Cluster 'redis_port' must be between 1 and 65535")
            
            if 'redis_db' in cluster:
                db = cluster['redis_db']
                if not isinstance(db, int) or db < 0:
                    self.errors.append("Cluster 'redis_db' must be a non-negative integer")
        
        # Validate optional fields
        if 'heartbeat_interval' in cluster:
            interval = cluster['heartbeat_interval']
            if not isinstance(interval, int) or interval <= 0:
                self.errors.append("Cluster 'heartbeat_interval' must be a positive integer")
        
        if 'work_lock_ttl' in cluster:
            ttl = cluster['work_lock_ttl']
            if not isinstance(ttl, int) or ttl <= 0:
                self.errors.append("Cluster 'work_lock_ttl' must be a positive integer")
    
    def _validate_monitoring(self, monitoring: Dict[str, Any]):
        """Validate monitoring configuration"""
        
        if not isinstance(monitoring, dict):
            self.errors.append("Monitoring configuration must be an object")
            return
        
        # Validate log level
        if 'log_level' in monitoring:
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if monitoring['log_level'] not in valid_levels:
                self.errors.append(f"Monitoring 'log_level' must be one of: {valid_levels}")
        
        # Validate ports
        if 'prometheus_port' in monitoring:
            port = monitoring['prometheus_port']
            if not isinstance(port, int) or port < 1024 or port > 65535:
                self.errors.append("Monitoring 'prometheus_port' must be between 1024 and 65535")
        
        if 'health_check_port' in monitoring:
            port = monitoring['health_check_port']
            if not isinstance(port, int) or port < 1024 or port > 65535:
                self.errors.append("Monitoring 'health_check_port' must be between 1024 and 65535")
        
        # Check for port conflicts
        if ('prometheus_port' in monitoring and 'health_check_port' in monitoring and
            monitoring['prometheus_port'] == monitoring['health_check_port']):
            self.errors.append("Monitoring ports cannot be the same (prometheus_port and health_check_port)")
        
        # Validate retention
        if 'log_file_retention' in monitoring:
            retention = monitoring['log_file_retention']
            if not isinstance(retention, int) or retention <= 0:
                self.errors.append("Monitoring 'log_file_retention' must be a positive integer")
        
        # Validate alert channels
        if 'alert_channels' in monitoring:
            channels = monitoring['alert_channels']
            if not isinstance(channels, list):
                self.errors.append("Monitoring 'alert_channels' must be a list")
            else:
                valid_channels = ['email', 'slack', 'webhook', 'sms']
                for channel in channels:
                    if channel not in valid_channels:
                        self.errors.append(f"Invalid alert channel: {channel}. Must be one of: {valid_channels}")
    
    def _validate_scheduling(self, scheduling: Dict[str, Any]):
        """Validate scheduling configuration"""
        
        if not isinstance(scheduling, dict):
            self.errors.append("Scheduling configuration must be an object")
            return
        
        # If scheduling is enabled, validate cron expression
        if scheduling.get('enabled', False):
            if 'cron_expression' not in scheduling or not scheduling['cron_expression']:
                self.errors.append("Scheduling 'cron_expression' is required when scheduling is enabled")
            else:
                # Basic cron validation (5 or 6 fields)
                cron = scheduling['cron_expression']
                parts = cron.split()
                if len(parts) not in [5, 6]:
                    self.errors.append(f"Invalid cron expression: {cron}. Must have 5 or 6 fields")
        
        # Validate execution time
        if 'max_execution_time' in scheduling:
            max_time = scheduling['max_execution_time']
            if not isinstance(max_time, int) or max_time <= 0:
                self.errors.append("Scheduling 'max_execution_time' must be a positive integer")
        
        # Validate concurrent tasks
        if 'concurrent_tasks' in scheduling:
            concurrent = scheduling['concurrent_tasks']
            if not isinstance(concurrent, int) or concurrent <= 0:
                self.errors.append("Scheduling 'concurrent_tasks' must be a positive integer")
        
        # Validate timezone
        if 'timezone' in scheduling:
            tz = scheduling['timezone']
            if not isinstance(tz, str) or not tz.strip():
                self.errors.append("Scheduling 'timezone' must be a non-empty string")
    
    def _validate_alerting(self, alerting: Dict[str, Any]):
        """Validate alerting configuration"""
        
        if not isinstance(alerting, dict):
            self.errors.append("Alerting configuration must be an object")
            return
        
        # Validate rate limiting
        if 'max_alerts_per_hour' in alerting:
            max_alerts = alerting['max_alerts_per_hour']
            if not isinstance(max_alerts, int) or max_alerts <= 0:
                self.errors.append("Alerting 'max_alerts_per_hour' must be a positive integer")
        
        if 'dedup_window_minutes' in alerting:
            window = alerting['dedup_window_minutes']
            if not isinstance(window, int) or window <= 0:
                self.errors.append("Alerting 'dedup_window_minutes' must be a positive integer")
        
        # Validate escalation
        if 'escalation_delay_minutes' in alerting:
            delay = alerting['escalation_delay_minutes']
            if not isinstance(delay, int) or delay <= 0:
                self.errors.append("Alerting 'escalation_delay_minutes' must be a positive integer")
    
    def get_warnings(self) -> List[str]:
        """Get validation warnings"""
        return self.warnings


def validate_config_file(config_path: str) -> List[str]:
    """
    Validate a configuration file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        List of validation error messages
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        validator = ConfigValidator()
        errors = validator.validate_config_dict(config)
        
        return errors
        
    except FileNotFoundError:
        return [f"Configuration file not found: {config_path}"]
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in configuration file: {e}"]
    except Exception as e:
        return [f"Error reading configuration file: {e}"]


def validate_config_string(config_json: str) -> List[str]:
    """
    Validate a configuration JSON string.
    
    Args:
        config_json: JSON string containing configuration
        
    Returns:
        List of validation error messages
    """
    try:
        config = json.loads(config_json)
        validator = ConfigValidator()
        return validator.validate_config_dict(config)
        
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]
    except Exception as e:
        return [f"Error parsing configuration: {e}"]


def main():
    """CLI entry point for configuration validation"""
    if len(sys.argv) != 2:
        print("Usage: python config_validator.py <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    print(f"Validating configuration file: {config_file}")
    
    errors = validate_config_file(config_file)
    
    if errors:
        print(f"\n❌ Configuration validation failed ({len(errors)} errors):")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("\n✅ Configuration validation passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()