"""
Flexible Configuration Management System for Daily Scraper Automation

This module provides hierarchical configuration loading, validation, and runtime management
for the automated scraper system. It supports multiple configuration sources with proper
precedence and environment-specific overrides.

Configuration Hierarchy (highest to lowest precedence):
1. Command-line arguments
2. Environment variables
3. Environment-specific config files
4. Base configuration files
5. Default configuration (embedded)
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from threading import Thread, Event
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import argparse
from loguru import logger


class DeploymentType(Enum):
    """Supported deployment types"""
    STANDALONE = "standalone"
    CONTAINER = "container"
    CLUSTER = "cluster"


class ConfigSource(Enum):
    """Configuration source types"""
    DEFAULT = "default"
    FILE = "file"
    ENV_FILE = "env_file"
    ENV_VAR = "env_var"
    CLI_ARG = "cli_arg"


@dataclass
class ScrapingTaskConfig:
    """Configuration for a single scraping task"""
    city: str
    url: str
    enabled: bool = True
    listing_limit: Optional[int] = None
    max_detail_workers: int = 5
    staleness_hours: int = 24
    retry_count: int = 3
    retry_backoff_factor: float = 2.0


@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = "data/real_estate.duckdb"
    connection_timeout: int = 30
    max_connections: int = 10
    backup_enabled: bool = True
    backup_interval_hours: int = 24


@dataclass
class ClusterConfig:
    """Cluster coordination configuration"""
    enabled: bool = False
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    node_id: Optional[str] = None
    heartbeat_interval: int = 30
    work_lock_ttl: int = 300


@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration"""
    metrics_enabled: bool = True
    prometheus_port: int = 8000
    health_check_port: int = 8001
    log_level: str = "INFO"
    log_file_retention: int = 30
    alert_channels: List[str] = field(default_factory=list)


@dataclass
class SchedulingConfig:
    """Scheduling configuration"""
    enabled: bool = True
    cron_expression: str = "0 6 * * *"  # Daily at 6 AM
    timezone: str = "Europe/Helsinki"
    max_execution_time: int = 7200  # 2 hours
    concurrent_tasks: int = 1


@dataclass
class ScraperConfig:
    """Complete scraper configuration"""
    # Core configuration
    tasks: List[ScrapingTaskConfig] = field(default_factory=list)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cluster: ClusterConfig = field(default_factory=ClusterConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    scheduling: SchedulingConfig = field(default_factory=SchedulingConfig)
    
    # System configuration
    deployment_type: DeploymentType = DeploymentType.STANDALONE
    environment: str = "development"
    debug: bool = False
    
    # Runtime metadata
    config_version: str = "1.0"
    loaded_from: List[str] = field(default_factory=list)
    last_modified: Optional[float] = None


class ConfigValidationError(Exception):
    """Configuration validation error"""
    pass


class ConfigWatcher(FileSystemEventHandler):
    """File system watcher for configuration changes"""
    
    def __init__(self, config_manager: 'ConfigurationManager', callback: Callable):
        self.config_manager = config_manager
        self.callback = callback
        self.last_reload = 0
        self.reload_debounce = 1.0  # 1 second debounce
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # Check if it's a config file
        if not any(event.src_path.endswith(ext) for ext in ['.json', '.yaml', '.yml']):
            return
        
        # Debounce rapid file changes
        current_time = time.time()
        if current_time - self.last_reload < self.reload_debounce:
            return
        
        self.last_reload = current_time
        logger.info(f"Configuration file changed: {event.src_path}")
        
        try:
            self.callback()
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")


class ConfigurationManager:
    """
    Flexible configuration management system with hierarchical loading,
    validation, and runtime watching capabilities.
    """
    
    def __init__(self, base_config_dir: str = "config"):
        self.base_config_dir = Path(base_config_dir)
        self.config: Optional[ScraperConfig] = None
        self.observer: Optional[Observer] = None
        self.watch_enabled = False
        self.reload_callbacks: List[Callable] = []
        
        # Default configuration paths
        self.default_config_files = [
            "config.json",
            "scraper_config.json",
            "automation_config.json"
        ]
        
        # Environment-specific config patterns
        self.env_config_patterns = [
            "{env}_config.json",
            "config_{env}.json",
            "{env}/config.json"
        ]
    
    def load_config(self, 
                   config_files: Optional[List[str]] = None,
                   environment: Optional[str] = None,
                   cli_args: Optional[argparse.Namespace] = None) -> ScraperConfig:
        """
        Load configuration from multiple sources with proper precedence.
        
        Args:
            config_files: Specific config files to load
            environment: Environment name for env-specific configs
            cli_args: Command-line arguments
            
        Returns:
            Complete configuration object
        """
        logger.info("Loading configuration from multiple sources...")
        
        # Start with default configuration
        config = self._get_default_config()
        config.loaded_from.append("default")
        
        # Detect environment if not provided
        if environment is None:
            environment = self._detect_environment()
        config.environment = environment
        
        # Load base configuration files
        config_files = config_files or self.default_config_files
        for config_file in config_files:
            config_path = self.base_config_dir / config_file
            if config_path.exists():
                file_config = self._load_config_file(config_path)
                config = self._merge_configs(config, file_config)
                config.loaded_from.append(f"file:{config_path}")
        
        # Load environment-specific configuration
        env_config = self._load_environment_config(environment)
        if env_config:
            config = self._merge_configs(config, env_config)
            config.loaded_from.append(f"env_file:{environment}")
        
        # Apply environment variable overrides
        env_overrides = self._load_environment_variables()
        if env_overrides:
            config = self._apply_env_overrides(config, env_overrides)
            config.loaded_from.append("env_vars")
        
        # Apply CLI argument overrides
        if cli_args:
            config = self._apply_cli_overrides(config, cli_args)
            config.loaded_from.append("cli_args")
        
        # Validate final configuration
        self._validate_config(config)
        
        # Set last modified timestamp
        config.last_modified = time.time()
        
        self.config = config
        logger.info(f"Configuration loaded successfully from: {', '.join(config.loaded_from)}")
        
        return config
    
    def _get_default_config(self) -> ScraperConfig:
        """Get default configuration with sensible defaults"""
        return ScraperConfig(
            tasks=[
                ScrapingTaskConfig(
                    city="Helsinki",
                    url="https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
                    enabled=True,
                    max_detail_workers=5,
                    staleness_hours=24
                )
            ],
            database=DatabaseConfig(),
            cluster=ClusterConfig(),
            monitoring=MonitoringConfig(),
            scheduling=SchedulingConfig()
        )
    
    def _detect_environment(self) -> str:
        """Detect deployment environment"""
        # Check environment variable first (highest priority)
        env_var = os.environ.get('ENVIRONMENT')
        if env_var:
            return env_var
        
        # Check for container environment
        if os.path.exists('/.dockerenv') or os.environ.get('CONTAINER'):
            return "container"
        
        # Check for cluster environment
        if os.environ.get('KUBERNETES_SERVICE_HOST') or os.environ.get('CLUSTER_MODE'):
            return "cluster"
        
        # Check for development environment (pytest)
        if sys.argv[0].endswith('pytest'):
            return "development"
        
        return "development"
    
    def _load_config_file(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from a JSON file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            logger.debug(f"Loaded configuration from {config_path}")
            return config_data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load config file {config_path}: {e}")
            return {}
    
    def _load_environment_config(self, environment: str) -> Optional[Dict[str, Any]]:
        """Load environment-specific configuration"""
        for pattern in self.env_config_patterns:
            config_file = pattern.format(env=environment)
            config_path = self.base_config_dir / config_file
            
            if config_path.exists():
                logger.info(f"Loading environment-specific config: {config_path}")
                return self._load_config_file(config_path)
        
        return None
    
    def _load_environment_variables(self) -> Dict[str, Any]:
        """Load configuration overrides from environment variables"""
        env_overrides = {}
        
        # Define environment variable mappings
        env_mappings = {
            'SCRAPER_DEBUG': ('debug', bool),
            'SCRAPER_LOG_LEVEL': ('monitoring.log_level', str),
            'SCRAPER_DB_PATH': ('database.path', str),
            'SCRAPER_REDIS_HOST': ('cluster.redis_host', str),
            'SCRAPER_REDIS_PORT': ('cluster.redis_port', int),
            'SCRAPER_CLUSTER_ENABLED': ('cluster.enabled', bool),
            'SCRAPER_METRICS_PORT': ('monitoring.prometheus_port', int),
            'SCRAPER_HEALTH_PORT': ('monitoring.health_check_port', int),
            'SCRAPER_CRON': ('scheduling.cron_expression', str),
            'SCRAPER_TIMEZONE': ('scheduling.timezone', str),
        }
        
        for env_var, (config_path, value_type) in env_mappings.items():
            env_value = os.environ.get(env_var)
            if env_value is not None:
                try:
                    # Convert value to appropriate type
                    if value_type == bool:
                        converted_value = env_value.lower() in ('true', '1', 'yes', 'on')
                    elif value_type == int:
                        converted_value = int(env_value)
                    else:
                        converted_value = env_value
                    
                    # Set nested configuration value
                    self._set_nested_value(env_overrides, config_path, converted_value)
                    logger.debug(f"Environment override: {config_path} = {converted_value}")
                    
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid environment variable {env_var}={env_value}: {e}")
        
        return env_overrides
    
    def _set_nested_value(self, config_dict: Dict[str, Any], path: str, value: Any):
        """Set a nested configuration value using dot notation"""
        keys = path.split('.')
        current = config_dict
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _merge_configs(self, base_config: ScraperConfig, override_config: Dict[str, Any]) -> ScraperConfig:
        """Merge configuration dictionaries with proper precedence"""
        # Convert base config to dict for merging
        base_dict = asdict(base_config)
        
        # Handle task merging specially to support partial task updates
        if 'tasks' in override_config:
            merged_tasks = self._merge_tasks(base_dict.get('tasks', []), override_config['tasks'])
            override_config = override_config.copy()
            override_config['tasks'] = merged_tasks
        
        # Deep merge the configurations
        merged_dict = self._deep_merge(base_dict, override_config)
        
        # Convert back to ScraperConfig
        return self._dict_to_config(merged_dict)
    
    def _merge_tasks(self, base_tasks: List[Dict[str, Any]], override_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge task configurations, supporting partial task updates by city"""
        # Create a mapping of base tasks by city
        base_task_map = {task.get('city'): task for task in base_tasks if isinstance(task, dict)}
        
        # Start with base tasks
        merged_tasks = []
        processed_cities = set()
        
        # Process override tasks
        for override_task in override_tasks:
            if not isinstance(override_task, dict) or 'city' not in override_task:
                # If override task doesn't have city, add as-is
                merged_tasks.append(override_task)
                continue
            
            city = override_task['city']
            processed_cities.add(city)
            
            if city in base_task_map:
                # Merge with existing task
                base_task = base_task_map[city].copy()
                base_task.update(override_task)
                merged_tasks.append(base_task)
            else:
                # New task
                merged_tasks.append(override_task)
        
        # Add remaining base tasks that weren't overridden
        for city, base_task in base_task_map.items():
            if city not in processed_cities:
                merged_tasks.append(base_task)
        
        return merged_tasks
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> ScraperConfig:
        """Convert dictionary to ScraperConfig object"""
        try:
            # Handle tasks separately as they need special conversion
            tasks_data = config_dict.get('tasks', [])
            tasks = []
            for task_data in tasks_data:
                if isinstance(task_data, dict):
                    # Filter out any extra fields that aren't part of ScrapingTaskConfig
                    valid_fields = {
                        'city', 'url', 'enabled', 'listing_limit', 'max_detail_workers',
                        'staleness_hours', 'retry_count', 'retry_backoff_factor'
                    }
                    filtered_data = {k: v for k, v in task_data.items() if k in valid_fields}
                    tasks.append(ScrapingTaskConfig(**filtered_data))
                else:
                    tasks.append(task_data)
            
            # Handle other nested configs with proper field filtering
            database_data = config_dict.get('database', {})
            if isinstance(database_data, dict):
                valid_db_fields = {
                    'path', 'connection_timeout', 'max_connections', 'backup_enabled', 'backup_interval_hours'
                }
                filtered_db_data = {k: v for k, v in database_data.items() if k in valid_db_fields}
                database = DatabaseConfig(**filtered_db_data)
            else:
                database = database_data
            
            cluster_data = config_dict.get('cluster', {})
            if isinstance(cluster_data, dict):
                valid_cluster_fields = {
                    'enabled', 'redis_host', 'redis_port', 'redis_db', 'redis_password',
                    'node_id', 'heartbeat_interval', 'work_lock_ttl'
                }
                filtered_cluster_data = {k: v for k, v in cluster_data.items() if k in valid_cluster_fields}
                cluster = ClusterConfig(**filtered_cluster_data)
            else:
                cluster = cluster_data
            
            monitoring_data = config_dict.get('monitoring', {})
            if isinstance(monitoring_data, dict):
                valid_monitoring_fields = {
                    'metrics_enabled', 'prometheus_port', 'health_check_port', 'log_level',
                    'log_file_retention', 'alert_channels'
                }
                filtered_monitoring_data = {k: v for k, v in monitoring_data.items() if k in valid_monitoring_fields}
                monitoring = MonitoringConfig(**filtered_monitoring_data)
            else:
                monitoring = monitoring_data
            
            scheduling_data = config_dict.get('scheduling', {})
            if isinstance(scheduling_data, dict):
                valid_scheduling_fields = {
                    'enabled', 'cron_expression', 'timezone', 'max_execution_time', 'concurrent_tasks'
                }
                filtered_scheduling_data = {k: v for k, v in scheduling_data.items() if k in valid_scheduling_fields}
                scheduling = SchedulingConfig(**filtered_scheduling_data)
            else:
                scheduling = scheduling_data
            
            # Handle deployment type conversion
            deployment_type = config_dict.get('deployment_type', 'standalone')
            if isinstance(deployment_type, str):
                deployment_type = DeploymentType(deployment_type)
            
            # Create main config
            config = ScraperConfig(
                tasks=tasks,
                database=database,
                cluster=cluster,
                monitoring=monitoring,
                scheduling=scheduling,
                deployment_type=deployment_type,
                environment=config_dict.get('environment', 'development'),
                debug=config_dict.get('debug', False),
                config_version=config_dict.get('config_version', '1.0'),
                loaded_from=config_dict.get('loaded_from', []),
                last_modified=config_dict.get('last_modified')
            )
            
            return config
            
        except Exception as e:
            logger.error(f"Error converting dict to config: {e}")
            logger.error(f"Config dict keys: {list(config_dict.keys())}")
            if 'cluster' in config_dict:
                logger.error(f"Cluster data: {config_dict['cluster']}")
            raise ConfigValidationError(f"Invalid configuration structure: {e}")
    
    def _apply_env_overrides(self, config: ScraperConfig, env_overrides: Dict[str, Any]) -> ScraperConfig:
        """Apply environment variable overrides to configuration"""
        config_dict = asdict(config)
        merged_dict = self._deep_merge(config_dict, env_overrides)
        return self._dict_to_config(merged_dict)
    
    def _apply_cli_overrides(self, config: ScraperConfig, cli_args: argparse.Namespace) -> ScraperConfig:
        """Apply command-line argument overrides to configuration"""
        overrides = {}
        
        # Map CLI arguments to configuration paths
        cli_mappings = {
            'debug': 'debug',
            'log_level': 'monitoring.log_level',
            'db_path': 'database.path',
            'cluster_mode': 'cluster.enabled',
            'redis_host': 'cluster.redis_host',
            'redis_port': 'cluster.redis_port',
            'cron': 'scheduling.cron_expression',
            'environment': 'environment'
        }
        
        for cli_arg, config_path in cli_mappings.items():
            if hasattr(cli_args, cli_arg):
                value = getattr(cli_args, cli_arg)
                # Only apply CLI overrides for values that were explicitly set
                # For boolean flags, check if they were actually provided
                if cli_arg in ['cluster_mode'] and isinstance(value, bool):
                    # For boolean flags, only apply if they were explicitly set to True
                    # (argparse sets them to False by default even if not provided)
                    if value is True:
                        self._set_nested_value(overrides, config_path, value)
                elif value is not None:
                    self._set_nested_value(overrides, config_path, value)
        
        if overrides:
            config_dict = asdict(config)
            merged_dict = self._deep_merge(config_dict, overrides)
            return self._dict_to_config(merged_dict)
        
        return config
    
    def _validate_config(self, config: ScraperConfig):
        """Validate configuration completeness and correctness"""
        errors = []
        
        # Validate tasks
        if not config.tasks:
            errors.append("No scraping tasks configured")
        
        for i, task in enumerate(config.tasks):
            if not task.city:
                errors.append(f"Task {i}: city is required")
            if not task.url:
                errors.append(f"Task {i}: url is required")
            if task.max_detail_workers < 1:
                errors.append(f"Task {i}: max_detail_workers must be >= 1")
            if task.staleness_hours < 1:
                errors.append(f"Task {i}: staleness_hours must be >= 1")
        
        # Validate database config
        if not config.database.path:
            errors.append("Database path is required")
        
        # Validate cluster config
        if config.cluster.enabled:
            if not config.cluster.redis_host:
                errors.append("Redis host is required for cluster mode")
            if config.cluster.redis_port < 1 or config.cluster.redis_port > 65535:
                errors.append("Redis port must be between 1 and 65535")
        
        # Validate monitoring config
        if config.monitoring.prometheus_port < 1024 or config.monitoring.prometheus_port > 65535:
            errors.append("Prometheus port must be between 1024 and 65535")
        if config.monitoring.health_check_port < 1024 or config.monitoring.health_check_port > 65535:
            errors.append("Health check port must be between 1024 and 65535")
        
        # Validate scheduling config
        if config.scheduling.enabled and not config.scheduling.cron_expression:
            errors.append("Cron expression is required when scheduling is enabled")
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ConfigValidationError(error_msg)
        
        logger.info("Configuration validation passed")
    
    def start_watching(self, reload_callback: Optional[Callable] = None):
        """Start watching configuration files for changes"""
        if self.watch_enabled:
            logger.warning("Configuration watching is already enabled")
            return
        
        if reload_callback:
            self.reload_callbacks.append(reload_callback)
        
        # Set up file system watcher
        self.observer = Observer()
        event_handler = ConfigWatcher(self, self._handle_config_reload)
        
        # Watch the config directory
        if self.base_config_dir.exists():
            self.observer.schedule(event_handler, str(self.base_config_dir), recursive=True)
            self.observer.start()
            self.watch_enabled = True
            logger.info(f"Started watching configuration directory: {self.base_config_dir}")
        else:
            logger.warning(f"Configuration directory does not exist: {self.base_config_dir}")
    
    def stop_watching(self):
        """Stop watching configuration files"""
        if self.observer and self.watch_enabled:
            self.observer.stop()
            self.observer.join()
            self.watch_enabled = False
            logger.info("Stopped watching configuration files")
    
    def _handle_config_reload(self):
        """Handle configuration reload after file changes"""
        try:
            logger.info("Reloading configuration due to file changes...")
            old_config = self.config
            
            # Reload configuration
            new_config = self.load_config(
                environment=old_config.environment if old_config else None
            )
            
            # Notify callbacks
            for callback in self.reload_callbacks:
                try:
                    callback(old_config, new_config)
                except Exception as e:
                    logger.error(f"Error in reload callback: {e}")
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
    
    def get_config(self) -> Optional[ScraperConfig]:
        """Get current configuration"""
        return self.config
    
    def export_config(self, format: str = "json", include_defaults: bool = False) -> str:
        """Export current configuration in specified format"""
        if not self.config:
            raise ValueError("No configuration loaded")
        
        config_dict = asdict(self.config)
        
        # Remove runtime metadata if not including defaults
        if not include_defaults:
            config_dict.pop('loaded_from', None)
            config_dict.pop('last_modified', None)
        
        if format.lower() == "json":
            return json.dumps(config_dict, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def generate_template(self, template_type: str = "basic") -> str:
        """Generate configuration template"""
        if template_type == "basic":
            template = {
                "tasks": [
                    {
                        "city": "Helsinki",
                        "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
                        "enabled": True,
                        "max_detail_workers": 5,
                        "staleness_hours": 24
                    }
                ],
                "database": {
                    "path": "data/real_estate.duckdb",
                    "connection_timeout": 30
                },
                "monitoring": {
                    "log_level": "INFO",
                    "metrics_enabled": True
                },
                "scheduling": {
                    "enabled": True,
                    "cron_expression": "0 6 * * *"
                }
            }
        elif template_type == "cluster":
            template = {
                "tasks": [
                    {
                        "city": "Helsinki",
                        "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
                        "enabled": True,
                        "max_detail_workers": 3
                    }
                ],
                "cluster": {
                    "enabled": True,
                    "redis_host": "redis-service",
                    "redis_port": 6379,
                    "heartbeat_interval": 30
                },
                "monitoring": {
                    "metrics_enabled": True,
                    "prometheus_port": 8000,
                    "health_check_port": 8001
                }
            }
        else:
            raise ValueError(f"Unknown template type: {template_type}")
        
        return json.dumps(template, indent=2)


def create_cli_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser for configuration"""
    parser = argparse.ArgumentParser(description="Daily Scraper Automation Configuration")
    
    # Configuration file options
    parser.add_argument('--config', '-c', type=str, nargs='+',
                       help='Configuration file(s) to load')
    parser.add_argument('--environment', '-e', type=str,
                       help='Environment name (development, production, etc.)')
    
    # Override options
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Set log level')
    parser.add_argument('--db-path', type=str,
                       help='Database file path')
    
    # Cluster options
    parser.add_argument('--cluster-mode', action='store_true',
                       help='Enable cluster mode')
    parser.add_argument('--redis-host', type=str,
                       help='Redis host for cluster coordination')
    parser.add_argument('--redis-port', type=int,
                       help='Redis port for cluster coordination')
    
    # Scheduling options
    parser.add_argument('--cron', type=str,
                       help='Cron expression for scheduling')
    
    # Utility options
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate configuration, do not run')
    parser.add_argument('--export-config', action='store_true',
                       help='Export final configuration and exit')
    parser.add_argument('--generate-template', type=str, choices=['basic', 'cluster'],
                       help='Generate configuration template')
    
    return parser


# Example usage and testing functions
if __name__ == "__main__":
    # Example usage
    config_manager = ConfigurationManager()
    
    # Parse CLI arguments
    parser = create_cli_parser()
    args = parser.parse_args()
    
    if args.generate_template:
        print(config_manager.generate_template(args.generate_template))
        sys.exit(0)
    
    try:
        # Load configuration
        config = config_manager.load_config(
            config_files=args.config,
            environment=args.environment,
            cli_args=args
        )
        
        if args.validate_only:
            print("Configuration validation passed!")
            sys.exit(0)
        
        if args.export_config:
            print(config_manager.export_config())
            sys.exit(0)
        
        # Start configuration watching
        config_manager.start_watching()
        
        print(f"Configuration loaded successfully!")
        print(f"Environment: {config.environment}")
        print(f"Tasks: {len(config.tasks)}")
        print(f"Cluster mode: {config.cluster.enabled}")
        
    except ConfigValidationError as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)