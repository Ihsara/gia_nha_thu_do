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

# Data governance imports temporarily disabled for testing
# from .data_governance import (
#     DataGovernanceManager,
#     DataSource,
#     DataQualityLevel,
#     DataQualityScore,
#     RetentionPolicy,
#     ComplianceReport,
#     create_data_governance_config
# )

# from .governance_integration import (
#     GovernanceIntegratedOrchestrator,
#     GovernanceIntegrationConfig,
#     create_governance_integrated_orchestrator,
#     migrate_existing_orchestrator_to_governance
# )

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
    'create_cli_parser',
    'DataGovernanceManager',
    'DataSource',
    'DataQualityLevel',
    'DataQualityScore',
    'RetentionPolicy',
    'ComplianceReport',
    'create_data_governance_config',
    'GovernanceIntegratedOrchestrator',
    'GovernanceIntegrationConfig',
    'create_governance_integrated_orchestrator',
    'migrate_existing_orchestrator_to_governance'
]

__version__ = "1.0.0"