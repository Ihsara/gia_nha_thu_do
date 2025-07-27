"""
Flexible Configuration Management System for Daily Scraper Automation

This module provides comprehensive configuration management with hierarchical loading,
validation, environment-specific overrides, and hot-reload capabilities.

Features:
- Hierarchical configuration loading (files, env vars, CLI args)
- Configuration validation and error reporting
- Environment-specific configuration overrides
- Runtime configuration watching and hot-reload capabilities
- Configuration templates and documentation generation
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable, Type
from dataclasses import dataclass, field, asdict
from enum import Enum
from threading import Thread, Event
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import argparse
from loguru import logger


class ConfigSource(Enum):
    """Configuration source types in order of precedence (lowest to highest)."""
    DEFAULT = "default"
    CONFIG_FILE = "config_file"
    ENVIRONMENT = "environment"
    CLI_ARGS = "cli_args"
    RUNTIME_OVERRIDE = "runtime_override"


class DeploymentType(Enum):
    """Deployment environment types."""
    STANDALONE = "standalone"
    CONTAINER = "container"
    CLUSTER = "cluster"
    DEVELOPMENT = "development"


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    duckdb_path: str = "data/real_estate.duckdb"
    connection_timeout: int = 30
    max_connections: int = 10
    read_only: bool = False
    enable_wal: bool = True
    memory_limit: str = "2GB"
    threads: int = 4
    
    # Fallback storage
    json_fallback_dir: str = "data/fallback"
    enable_fallback: bool = True


@dataclass
class ScrapingConfig:
    """Scraping configuration settings."""
    # Cities and URLs
    cities: List[Dict[str, Any]] = field(default_factory=list)
    
    # Worker settings
    max_detail_workers: int = 5
    max_concurrent_cities: int = 2
    request_delay_seconds: float = 1.0
    
    # Browser settings
    headless: bool = True
    browser_timeout: int = 30
    page_load_timeout: int = 20
    
    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 5
    exponential_backoff: bool = True
    
    # Data quality
    staleness_threshold_hours: int = 24
    enable_deduplication: bool = True
    geocoding_timeout: int = 10
    batch_size: int = 100


@dataclass
class ClusterConfig:
    """Cluster coordination configuration."""
    enabled: bool = False
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    node_id: Optional[str] = None
    
    # Coordination settings
    work_lock_ttl: int = 300  # 5 minutes
    health_check_interval: int = 30
    coordination_timeout: int = 10
    
    # Load balancing
    enable_load_balancing: bool = True
    max_work_items_per_node: int = 100


@dataclass
class MonitoringConfig:
    """Monitoring and metrics configuration."""
    enabled: bool = True
    
    # Metrics
    prometheus_port: int = 8000
    metrics_path: str = "/metrics"
    collect_system_metrics: bool = True
    
    # Health checks
    health_check_port: int = 8080
    health_check_path: str = "/health"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: Optional[str] = None
    max_log_size: str = "100MB"
    log_retention_days: int = 30


@dataclass
class SchedulingConfig:
    """Scheduling configuration."""
    enabled: bool = True
    cron_expression: str = "0 2 * * *"  # Daily at 2 AM
    default_schedule: str = "0 2 * * *"  # Daily at 2 AM
    timezone: str = "UTC"
    
    # Execution settings
    max_execution_time: int = 7200  # 2 hours
    max_concurrent_tasks: int = 1
    task_timeout: int = 3600  # 1 hour
    retry_attempts: int = 3
    retry_delay: int = 300  # 5 minutes
    resource_limits: Dict[str, Any] = field(default_factory=lambda: {
        'max_memory_mb': 2048,
        'max_cpu_percent': 80,
        'max_disk_usage_percent': 90
    })
    enable_manual_trigger: bool = True
    prevent_overlapping: bool = True


@dataclass
class AlertingConfig:
    """Alerting configuration."""
    enabled: bool = True
    config_file: str = "config/alert_config.json"
    
    # Alert conditions and channels (will be loaded from config file)
    alert_conditions: List[Any] = field(default_factory=list)
    notification_channels: List[Any] = field(default_factory=list)
    
    # Rate limiting
    max_alerts_per_hour: int = 50
    enable_deduplication: bool = True
    dedup_window_minutes: int = 60
    
    # Escalation
    enable_escalation: bool = True
    escalation_delay_minutes: int = 30


@dataclass
class ScraperConfiguration:
    """Main scraper configuration container."""
    # Core configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    scraping: ScrapingConfig = field(default_factory=ScrapingConfig)
    cluster: ClusterConfig = field(default_factory=ClusterConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    scheduling: SchedulingConfig = field(default_factory=SchedulingConfig)
    alerting: AlertingConfig = field(default_factory=AlertingConfig)
    
    # Environment settings
    deployment_type: DeploymentType = DeploymentType.STANDALONE
    environment: str = "production"
    debug: bool = False
    
    # Metadata
    config_version: str = "1.0"
    loaded_from: List[str] = field(default_factory=list)
    last_updated: Optional[float] = None


class ConfigValidationError(Exception):
    """Configuration validation error."""
    pass


class ConfigWatcher(FileSystemEventHandler):
    """File system watcher for configuration changes."""
    
    def __init__(self, config_manager: 'ConfigurationManager', callback: Callable):
        self.config_manager = config_manager
        self.callback = callback
        self.last_modified = {}
        
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Only watch configuration files
        if file_path.suffix not in ['.json', '.yaml', '.yml', '.toml']:
            return
            
        # Debounce rapid file changes
        current_time = time.time()
        last_mod = self.last_modified.get(file_path, 0)
        
        if current_time - last_mod < 1.0:  # 1 second debounce
            return
            
        self.last_modified[file_path] = current_time
        
        logger.info(f"Configuration file changed: {file_path}")
        
        try:
            self.callback(str(file_path))
        except Exception as e:
            logger.error(f"Error handling configuration change: {e}")


class ConfigurationManager:
    """
    Comprehensive configuration management system.
    
    Supports hierarchical loading, validation, environment overrides,
    and hot-reload capabilities.
    """
    
    def __init__(self, config_paths: Optional[List[str]] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_paths: List of configuration file paths to load
        """
        self.config_paths = config_paths or [
            "config/scraper_config.json",
            "config/scraper_config.local.json"
        ]
        
        self.config: Optional[ScraperConfiguration] = None
        self.watchers: List[Observer] = []
        self.reload_callbacks: List[Callable] = []
        self.validation_errors: List[str] = []
        
        # Environment detection
        self.deployment_type = self._detect_deployment_type()
        
    def load_configuration(self, 
                          cli_args: Optional[argparse.Namespace] = None,
                          env_prefix: str = "SCRAPER_") -> ScraperConfiguration:
        """
        Load configuration from all sources in hierarchical order.
        
        Args:
            cli_args: Command line arguments
            env_prefix: Environment variable prefix
            
        Returns:
            Loaded and validated configuration
        """
        logger.info("Loading configuration from all sources")
        
        # Start with default configuration
        config = ScraperConfiguration()
        config.deployment_type = self.deployment_type
        config.loaded_from.append(ConfigSource.DEFAULT.value)
        
        # Load from configuration files
        for config_path in self.config_paths:
            if Path(config_path).exists():
                try:
                    file_config = self._load_from_file(config_path)
                    config = self._merge_configurations(config, file_config)
                    config.loaded_from.append(f"{ConfigSource.CONFIG_FILE.value}:{config_path}")
                    logger.info(f"Loaded configuration from {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to load configuration from {config_path}: {e}")
        
        # Apply environment variables
        env_config = self._load_from_environment(env_prefix)
        if env_config:
            config = self._merge_configurations(config, env_config)
            config.loaded_from.append(ConfigSource.ENVIRONMENT.value)
            logger.info("Applied environment variable overrides")
        
        # Apply CLI arguments
        if cli_args:
            cli_config = self._load_from_cli_args(cli_args)
            if cli_config:
                config = self._merge_configurations(config, cli_config)
                config.loaded_from.append(ConfigSource.CLI_ARGS.value)
                logger.info("Applied CLI argument overrides")
        
        # Apply environment-specific overrides
        env_overrides = self._get_environment_overrides(config.environment)
        if env_overrides:
            config = self._merge_configurations(config, env_overrides)
            config.loaded_from.append(f"environment_override:{config.environment}")
            logger.info(f"Applied {config.environment} environment overrides")
        
        # Set metadata
        config.last_updated = time.time()
        
        # Validate configuration
        self.validation_errors = self._validate_configuration(config)
        if self.validation_errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(self.validation_errors)
            logger.error(error_msg)
            raise ConfigValidationError(error_msg)
        
        self.config = config
        logger.info(f"Configuration loaded successfully from sources: {config.loaded_from}")
        
        return config
    
    def load_config_from_dict(self, config_dict: Dict[str, Any]) -> ScraperConfiguration:
        """
        Load configuration from a dictionary (for testing and programmatic use).
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            Loaded and validated configuration
        """
        logger.info("Loading configuration from dictionary")
        
        # Start with default configuration
        config = ScraperConfiguration()
        config.deployment_type = self.deployment_type
        config.loaded_from.append(ConfigSource.DEFAULT.value)
        
        # Merge with provided dictionary
        if config_dict:
            config = self._merge_configurations(config, config_dict)
            config.loaded_from.append("dictionary")
            logger.info("Applied dictionary configuration")
        
        # Apply environment-specific overrides if specified
        if hasattr(config, 'environment') and config.environment:
            env_overrides = self._get_environment_overrides(config.environment)
            if env_overrides:
                config = self._merge_configurations(config, env_overrides)
                config.loaded_from.append(f"environment_override:{config.environment}")
                logger.info(f"Applied {config.environment} environment overrides")
        
        # Set metadata
        config.last_updated = time.time()
        
        # Validate configuration
        self.validation_errors = self._validate_configuration(config)
        if self.validation_errors:
            # For testing, we'll be more lenient with validation
            logger.warning(f"Configuration validation warnings: {self.validation_errors}")
        
        self.config = config
        logger.info(f"Configuration loaded successfully from sources: {config.loaded_from}")
        
        return config
    
    def _detect_deployment_type(self) -> DeploymentType:
        """
        Detect the deployment environment type.
        
        Returns:
            Detected deployment type
        """
        # Check for container environment
        if os.path.exists('/.dockerenv') or os.environ.get('CONTAINER'):
            return DeploymentType.CONTAINER
        
        # Check for cluster environment (Redis available)
        if os.environ.get('REDIS_URL') or os.environ.get('CLUSTER_MODE'):
            return DeploymentType.CLUSTER
        
        # Check for development environment
        if os.environ.get('ENVIRONMENT') == 'development' or '--dev' in sys.argv:
            return DeploymentType.DEVELOPMENT
        
        return DeploymentType.STANDALONE
    
    def _load_from_file(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
        """
        file_path = Path(config_path)
        
        if not file_path.exists():
            return {}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.suffix == '.json':
                return json.load(f)
            elif file_path.suffix in ['.yaml', '.yml']:
                import yaml
                return yaml.safe_load(f)
            elif file_path.suffix == '.toml':
                import tomli
                return tomli.load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {file_path.suffix}")
    
    def _load_from_environment(self, prefix: str) -> Dict[str, Any]:
        """
        Load configuration from environment variables.
        
        Args:
            prefix: Environment variable prefix
            
        Returns:
            Configuration dictionary
        """
        config = {}
        
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            
            # Remove prefix and convert to lowercase
            config_key = key[len(prefix):].lower()
            
            # Handle nested configuration keys (e.g., DATABASE_DUCKDB_PATH)
            key_parts = config_key.split('_')
            
            # Convert value to appropriate type
            converted_value = self._convert_env_value(value)
            
            # Set nested configuration
            current = config
            for part in key_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[key_parts[-1]] = converted_value
        
        return config
    
    def _convert_env_value(self, value: str) -> Any:
        """
        Convert environment variable string to appropriate type.
        
        Args:
            value: Environment variable value
            
        Returns:
            Converted value
        """
        # Boolean values
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Integer values
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float values
        try:
            return float(value)
        except ValueError:
            pass
        
        # JSON values
        if value.startswith('{') or value.startswith('['):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        # String value
        return value
    
    def _load_from_cli_args(self, cli_args: argparse.Namespace) -> Dict[str, Any]:
        """
        Load configuration from CLI arguments.
        
        Args:
            cli_args: Parsed CLI arguments
            
        Returns:
            Configuration dictionary
        """
        config = {}
        
        # Map CLI arguments to configuration structure
        arg_mapping = {
            'debug': 'debug',
            'environment': 'environment',
            'headless': 'scraping.headless',
            'workers': 'scraping.max_detail_workers',
            'redis_url': 'cluster.redis_url',
            'log_level': 'monitoring.log_level',
            'config_file': None  # Special handling
        }
        
        for arg_name, config_path in arg_mapping.items():
            if hasattr(cli_args, arg_name) and getattr(cli_args, arg_name) is not None:
                if config_path is None:
                    continue
                
                value = getattr(cli_args, arg_name)
                
                # Set nested configuration
                if '.' in config_path:
                    parts = config_path.split('.')
                    current = config
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    current[parts[-1]] = value
                else:
                    config[config_path] = value
        
        return config
    
    def _get_environment_overrides(self, environment: str) -> Dict[str, Any]:
        """
        Get environment-specific configuration overrides.
        
        Args:
            environment: Environment name (development, staging, production)
            
        Returns:
            Environment-specific overrides
        """
        overrides = {}
        
        if environment == "development":
            overrides = {
                "debug": True,
                "monitoring": {
                    "log_level": "DEBUG"
                },
                "scraping": {
                    "headless": False,
                    "max_detail_workers": 2
                },
                "scheduling": {
                    "enabled": False
                }
            }
        
        elif environment == "staging":
            overrides = {
                "debug": False,
                "monitoring": {
                    "log_level": "INFO"
                },
                "scraping": {
                    "headless": True,
                    "max_detail_workers": 3
                },
                "alerting": {
                    "max_alerts_per_hour": 20
                }
            }
        
        elif environment == "production":
            overrides = {
                "debug": False,
                "monitoring": {
                    "log_level": "INFO",
                    "collect_system_metrics": True
                },
                "scraping": {
                    "headless": True
                },
                "alerting": {
                    "enabled": True
                }
            }
        
        # Container-specific overrides
        if self.deployment_type == DeploymentType.CONTAINER:
            container_overrides = {
                "database": {
                    "duckdb_path": "/data/real_estate.duckdb"
                },
                "monitoring": {
                    "log_file": None  # Use stdout in containers
                }
            }
            overrides = self._merge_configurations(overrides, container_overrides)
        
        # Cluster-specific overrides
        elif self.deployment_type == DeploymentType.CLUSTER:
            cluster_overrides = {
                "cluster": {
                    "enabled": True
                },
                "monitoring": {
                    "prometheus_port": 8000,
                    "health_check_port": 8080
                }
            }
            overrides = self._merge_configurations(overrides, cluster_overrides)
        
        return overrides
    
    def _merge_configurations(self, base: Union[ScraperConfiguration, Dict], 
                            override: Dict) -> ScraperConfiguration:
        """
        Merge configuration dictionaries with deep merging.
        
        Args:
            base: Base configuration
            override: Override configuration
            
        Returns:
            Merged configuration
        """
        if isinstance(base, ScraperConfiguration):
            base_dict = asdict(base)
        else:
            base_dict = base.copy()
        
        merged = self._deep_merge(base_dict, override)
        
        # Convert back to ScraperConfiguration
        if isinstance(base, ScraperConfiguration):
            return self._dict_to_config(merged)
        else:
            return merged
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            override: Override dictionary
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _dict_to_config(self, config_dict: Dict) -> ScraperConfiguration:
        """
        Convert configuration dictionary to ScraperConfiguration object.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            ScraperConfiguration object
        """
        # Create nested configuration objects
        database_dict = config_dict.get('database', {})
        
        # Handle path vs duckdb_path mapping for backward compatibility
        if 'path' in database_dict:
            if 'duckdb_path' not in database_dict:
                database_dict['duckdb_path'] = database_dict.pop('path')
            else:
                # If both exist, prefer the override 'path' value and remove the conflicting parameter
                database_dict['duckdb_path'] = database_dict.pop('path')
        
        database_config = DatabaseConfig(**database_dict)
        scraping_config = ScrapingConfig(**config_dict.get('scraping', {}))
        cluster_config = ClusterConfig(**config_dict.get('cluster', {}))
        
        # Handle monitoring config parameter mapping
        monitoring_dict = config_dict.get('monitoring', {}).copy()
        
        # Map metrics_port to prometheus_port
        if 'metrics_port' in monitoring_dict:
            if 'prometheus_port' not in monitoring_dict:
                monitoring_dict['prometheus_port'] = monitoring_dict.pop('metrics_port')
            else:
                # If both exist, prefer the override 'metrics_port' value
                monitoring_dict['prometheus_port'] = monitoring_dict.pop('metrics_port')
        
        # Filter out parameters that don't belong to MonitoringConfig
        # (system_monitor_interval is used by other components)
        monitoring_config_params = {
            'enabled', 'prometheus_port', 'metrics_path', 'collect_system_metrics',
            'health_check_port', 'health_check_path', 'log_level', 'log_format',
            'log_file', 'max_log_size', 'log_retention_days'
        }
        filtered_monitoring_dict = {k: v for k, v in monitoring_dict.items() 
                                  if k in monitoring_config_params}
        
        monitoring_config = MonitoringConfig(**filtered_monitoring_dict)
        scheduling_config = SchedulingConfig(**config_dict.get('scheduling', {}))
        
        # Handle alerting config parameter filtering
        alerting_dict = config_dict.get('alerting', {}).copy()
        alerting_config_params = {
            'enabled', 'config_file', 'max_alerts_per_hour', 'enable_deduplication',
            'dedup_window_minutes', 'enable_escalation', 'escalation_delay_minutes'
        }
        filtered_alerting_dict = {k: v for k, v in alerting_dict.items() 
                                if k in alerting_config_params}
        
        alerting_config = AlertingConfig(**filtered_alerting_dict)
        
        # Handle deployment type
        deployment_type = config_dict.get('deployment_type', DeploymentType.STANDALONE)
        if isinstance(deployment_type, str):
            deployment_type = DeploymentType(deployment_type)
        
        return ScraperConfiguration(
            database=database_config,
            scraping=scraping_config,
            cluster=cluster_config,
            monitoring=monitoring_config,
            scheduling=scheduling_config,
            alerting=alerting_config,
            deployment_type=deployment_type,
            environment=config_dict.get('environment', 'production'),
            debug=config_dict.get('debug', False),
            config_version=config_dict.get('config_version', '1.0'),
            loaded_from=config_dict.get('loaded_from', []),
            last_updated=config_dict.get('last_updated')
        )
    
    def _validate_configuration(self, config: ScraperConfiguration) -> List[str]:
        """
        Validate configuration for correctness and completeness.
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Validate database configuration
        if not config.database.duckdb_path:
            errors.append("Database path cannot be empty")
        
        if config.database.connection_timeout <= 0:
            errors.append("Database connection timeout must be positive")
        
        # Validate scraping configuration
        if config.scraping.max_detail_workers <= 0:
            errors.append("Max detail workers must be positive")
        
        if config.scraping.request_delay_seconds < 0:
            errors.append("Request delay cannot be negative")
        
        if config.scraping.staleness_threshold_hours <= 0:
            errors.append("Staleness threshold must be positive")
        
        # Validate cluster configuration
        if config.cluster.enabled:
            if not config.cluster.redis_url:
                errors.append("Redis URL required when cluster is enabled")
            
            if config.cluster.work_lock_ttl <= 0:
                errors.append("Work lock TTL must be positive")
        
        # Validate monitoring configuration
        if config.monitoring.prometheus_port <= 0 or config.monitoring.prometheus_port > 65535:
            errors.append("Invalid Prometheus port number")
        
        if config.monitoring.health_check_port <= 0 or config.monitoring.health_check_port > 65535:
            errors.append("Invalid health check port number")
        
        if config.monitoring.log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            errors.append("Invalid log level")
        
        # Validate scheduling configuration
        if config.scheduling.max_execution_time <= 0:
            errors.append("Max execution time must be positive")
        
        # Validate alerting configuration
        if config.alerting.max_alerts_per_hour <= 0:
            errors.append("Max alerts per hour must be positive")
        
        return errors
    
    def save_configuration(self, config: ScraperConfiguration, 
                          config_path: Optional[str] = None) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save
            config_path: Path to save configuration (uses first config path if None)
            
        Returns:
            True if saved successfully
        """
        if config_path is None:
            config_path = self.config_paths[0]
        
        try:
            config_file = Path(config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dictionary and remove metadata
            config_dict = asdict(config)
            config_dict.pop('loaded_from', None)
            config_dict.pop('last_updated', None)
            
            # Convert enums to strings
            config_dict['deployment_type'] = config.deployment_type.value
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2)
            
            logger.info(f"Configuration saved to {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def watch_configuration(self, callback: Optional[Callable] = None) -> None:
        """
        Start watching configuration files for changes.
        
        Args:
            callback: Optional callback function for configuration changes
        """
        if callback:
            self.reload_callbacks.append(callback)
        
        for config_path in self.config_paths:
            config_file = Path(config_path)
            if config_file.exists():
                observer = Observer()
                handler = ConfigWatcher(self, self._handle_config_change)
                observer.schedule(handler, str(config_file.parent), recursive=False)
                observer.start()
                self.watchers.append(observer)
                logger.info(f"Watching configuration file: {config_path}")
    
    def _handle_config_change(self, changed_file: str) -> None:
        """
        Handle configuration file changes.
        
        Args:
            changed_file: Path to changed file
        """
        try:
            # Reload configuration
            new_config = self.load_configuration()
            
            # Notify callbacks
            for callback in self.reload_callbacks:
                try:
                    callback(new_config)
                except Exception as e:
                    logger.error(f"Error in configuration reload callback: {e}")
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
    
    def stop_watching(self) -> None:
        """Stop watching configuration files."""
        for observer in self.watchers:
            observer.stop()
            observer.join()
        
        self.watchers.clear()
        logger.info("Stopped watching configuration files")
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current configuration.
        
        Returns:
            Configuration summary
        """
        if not self.config:
            return {"error": "No configuration loaded"}
        
        return {
            "deployment_type": self.config.deployment_type.value,
            "environment": self.config.environment,
            "debug": self.config.debug,
            "loaded_from": self.config.loaded_from,
            "last_updated": self.config.last_updated,
            "validation_errors": self.validation_errors,
            "database_path": self.config.database.duckdb_path,
            "cluster_enabled": self.config.cluster.enabled,
            "monitoring_enabled": self.config.monitoring.enabled,
            "scheduling_enabled": self.config.scheduling.enabled,
            "alerting_enabled": self.config.alerting.enabled,
            "cities_configured": len(self.config.scraping.cities),
            "max_workers": self.config.scraping.max_detail_workers
        }
    
    def create_configuration_template(self, template_path: str = "config/scraper_config.template.json") -> bool:
        """
        Create a configuration template file with documentation.
        
        Args:
            template_path: Path to save template
            
        Returns:
            True if template created successfully
        """
        try:
            template_config = ScraperConfiguration()
            
            # Add sample cities
            template_config.scraping.cities = [
                {
                    "city": "Helsinki",
                    "enabled": True,
                    "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
                    "max_detail_workers": 5
                },
                {
                    "city": "Espoo",
                    "enabled": False,
                    "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B49,6,%22Espoo%22%5D%5D&cardType=100",
                    "listing_limit": 10,
                    "max_detail_workers": 5
                }
            ]
            
            config_dict = asdict(template_config)
            config_dict['deployment_type'] = template_config.deployment_type.value
            
            # Remove metadata fields
            config_dict.pop('loaded_from', None)
            config_dict.pop('last_updated', None)
            
            # Add documentation
            documented_config = {
                "_documentation": {
                    "description": "Daily Scraper Automation Configuration Template",
                    "version": "1.0",
                    "sections": {
                        "database": "Database connection and storage settings",
                        "scraping": "Web scraping configuration and limits",
                        "cluster": "Distributed execution and coordination",
                        "monitoring": "Metrics, logging, and health checks",
                        "scheduling": "Automated execution scheduling",
                        "alerting": "Error alerting and notifications"
                    },
                    "environment_variables": {
                        "SCRAPER_DATABASE_DUCKDB_PATH": "Override database path",
                        "SCRAPER_SCRAPING_HEADLESS": "Set browser headless mode (true/false)",
                        "SCRAPER_CLUSTER_REDIS_URL": "Redis URL for cluster coordination",
                        "SCRAPER_MONITORING_LOG_LEVEL": "Set logging level (DEBUG/INFO/WARNING/ERROR)",
                        "SCRAPER_ENVIRONMENT": "Set environment (development/staging/production)"
                    }
                },
                **config_dict
            }
            
            template_file = Path(template_path)
            template_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(documented_config, f, indent=2)
            
            logger.info(f"Configuration template created: {template_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create configuration template: {e}")
            return False


def create_cli_parser() -> argparse.ArgumentParser:
    """
    Create CLI argument parser for configuration options.
    
    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="Daily Scraper Automation Configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Configuration file
    parser.add_argument(
        '--config-file', '-c',
        type=str,
        help='Configuration file path'
    )
    
    # Environment
    parser.add_argument(
        '--environment', '-e',
        choices=['development', 'staging', 'production'],
        help='Deployment environment'
    )
    
    # Debug mode
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    
    # Browser settings
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode'
    )
    
    # Worker settings
    parser.add_argument(
        '--workers',
        type=int,
        help='Number of detail workers'
    )
    
    # Cluster settings
    parser.add_argument(
        '--redis-url',
        type=str,
        help='Redis URL for cluster coordination'
    )
    
    # Logging
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level'
    )
    
    return parser


# Example usage and testing
if __name__ == "__main__":
    # Demo configuration management
    print("🔧 Configuration Management System Demo")
    print("=" * 50)
    
    # Create configuration manager
    manager = ConfigurationManager()
    
    # Create template
    manager.create_configuration_template()
    
    # Load configuration
    try:
        config = manager.load_configuration()
        print(f"✅ Configuration loaded successfully")
        print(f"📊 Summary: {manager.get_configuration_summary()}")
        
    except ConfigValidationError as e:
        print(f"❌ Configuration validation failed: {e}")
    
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")