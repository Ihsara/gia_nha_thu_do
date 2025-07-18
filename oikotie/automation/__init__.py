"""
Daily Scraper Automation Package

This package provides comprehensive automation capabilities for the Oikotie scraper,
including configuration management, scheduling, monitoring, and deployment flexibility.
"""

from .config import (
    ConfigurationManager,
    ScraperConfig,
    ScrapingTaskConfig,
    DatabaseConfig,
    ClusterConfig,
    MonitoringConfig,
    SchedulingConfig,
    DeploymentType,
    ConfigSource,
    ConfigValidationError,
    create_cli_parser
)

__all__ = [
    'ConfigurationManager',
    'ScraperConfig',
    'ScrapingTaskConfig',
    'DatabaseConfig',
    'ClusterConfig',
    'MonitoringConfig',
    'SchedulingConfig',
    'DeploymentType',
    'ConfigSource',
    'ConfigValidationError',
    'create_cli_parser'
]

__version__ = "1.0.0"