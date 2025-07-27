"""
Production deployment and system integration for Oikotie Daily Scraper Automation.

This module provides comprehensive production deployment capabilities, integrating all
automation components into a cohesive system ready for production use.
"""

import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger

from .deployment import DeploymentManager, DeploymentType, create_deployment_manager
from .orchestrator import EnhancedScraperOrchestrator, load_config_and_create_orchestrators
from .cluster import ClusterCoordinator, create_cluster_coordinator
from .monitoring import ComprehensiveMonitor
from .reporting import StatusReporter
from .security import SecurityManager, create_security_manager
from .config import ConfigurationManager, ScraperConfig


@dataclass
class ProductionDeploymentConfig:
    """Configuration for production deployment."""
    deployment_name: str
    deployment_type: DeploymentType
    environment: str
    database_path: str
    config_path: str
    log_directory: str
    output_directory: str
    backup_directory: str
    enable_monitoring: bool = True
    enable_security: bool = True
    enable_clustering: bool = False
    redis_url: Optional[str] = None
    health_check_port: int = 8080
    metrics_port: int = 9090
    max_workers: int = 5
    retention_days: int = 30


@dataclass
class DeploymentStatus:
    """Status of production deployment."""
    deployment_name: str
    status: str  # 'initializing', 'healthy', 'degraded', 'failed'
    started_at: datetime
    last_check: datetime
    components: Dict[str, str]  # component_name -> status
    metrics: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


class ProductionDeploymentManager:
    """Manages production deployment and system integration."""
    
    def __init__(self, config: ProductionDeploymentConfig):
        """
        Initialize production deployment manager.
        
        Args:
            config: Production deployment configuration
        """
        self.config = config
        self.deployment_manager: Optional[DeploymentManager] = None
        self.orchestrators: List[EnhancedScraperOrchestrator] = []
        self.cluster_coordinator: Optional[ClusterCoordinator] = None
        self.comprehensive_monitor: Optional[ComprehensiveMonitor] = None
        self.status_reporter: Optional[StatusReporter] = None
        self.security_manager: Optional[SecurityManager] = None
        self.start_time = datetime.now()
        
        logger.info(f"Production deployment manager initialized: {config.deployment_name}")
    
    def initialize_deployment(self) -> bool:
        """
        Initialize complete production deployment.
        
        Returns:
            True if initialization successful, False otherwise
        """
        logger.info(f"Initializing production deployment: {self.config.deployment_name}")
        
        try:
            # Step 1: Create required directories
            self._create_directories()
            
            # Step 2: Initialize deployment manager
            self._initialize_deployment_manager()
            
            # Step 3: Initialize security if enabled
            if self.config.enable_security:
                self._initialize_security()
            
            # Step 4: Initialize orchestrators
            self._initialize_orchestrators()
            
            # Step 5: Initialize cluster coordination if enabled
            if self.config.enable_clustering:
                self._initialize_cluster_coordination()
            
            # Step 6: Initialize monitoring if enabled
            if self.config.enable_monitoring:
                self._initialize_monitoring()
            
            # Step 7: Initialize status reporting
            self._initialize_status_reporting()
            
            # Step 8: Validate deployment
            validation_result = self._validate_deployment()
            if not validation_result:
                logger.error("Deployment validation failed")
                return False
            
            logger.success(f"Production deployment initialized successfully: {self.config.deployment_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize production deployment: {e}")
            return False
    
    def _create_directories(self) -> None:
        """Create required directories for deployment."""
        directories = [
            self.config.log_directory,
            self.config.output_directory,
            self.config.backup_directory,
            Path(self.config.database_path).parent,
            Path(self.config.config_path).parent
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {directory}")
    
    def _initialize_deployment_manager(self) -> None:
        """Initialize deployment manager."""
        logger.info("Initializing deployment manager")
        
        self.deployment_manager = create_deployment_manager(self.config.config_path)
        
        # Override deployment type if specified
        if self.deployment_manager:
            config = self.deployment_manager.configure_for_environment(self.config.deployment_type)
            config.health_check_port = self.config.health_check_port
            config.database_path = self.config.database_path
            config.max_workers = self.config.max_workers
            
            logger.info(f"Deployment manager configured for {config.deployment_type.value}")
    
    def _initialize_security(self) -> None:
        """Initialize security manager."""
        logger.info("Initializing security manager")
        
        try:
            self.security_manager = create_security_manager()
            logger.info("Security manager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize security manager: {e}")
    
    def _initialize_orchestrators(self) -> None:
        """Initialize scraper orchestrators."""
        logger.info("Initializing scraper orchestrators")
        
        try:
            self.orchestrators = load_config_and_create_orchestrators(self.config.config_path)
            
            if not self.orchestrators:
                raise Exception("No enabled orchestrators found in configuration")
            
            logger.info(f"Initialized {len(self.orchestrators)} orchestrators")
            
            # Log orchestrator details
            for orchestrator in self.orchestrators:
                logger.info(f"  - {orchestrator.config.city}: {orchestrator.config.url}")
                
        except Exception as e:
            logger.error(f"Failed to initialize orchestrators: {e}")
            raise
    
    def _initialize_cluster_coordination(self) -> None:
        """Initialize cluster coordination."""
        logger.info("Initializing cluster coordination")
        
        if not self.config.redis_url:
            logger.warning("Redis URL not configured, cluster coordination disabled")
            return
        
        try:
            node_id = self.deployment_manager.get_node_id() if self.deployment_manager else "unknown"
            self.cluster_coordinator = create_cluster_coordinator(self.config.redis_url, node_id)
            
            if self.cluster_coordinator:
                logger.info("Cluster coordination initialized")
            else:
                logger.warning("Failed to create cluster coordinator")
                
        except Exception as e:
            logger.warning(f"Failed to initialize cluster coordination: {e}")
    
    def _initialize_monitoring(self) -> None:
        """Initialize comprehensive monitoring."""
        logger.info("Initializing comprehensive monitoring")
        
        try:
            from ..database.manager import EnhancedDatabaseManager
            
            db_manager = EnhancedDatabaseManager(self.config.database_path)
            
            self.comprehensive_monitor = ComprehensiveMonitor(
                db_manager=db_manager,
                metrics_port=self.config.metrics_port,
                system_monitor_interval=30
            )
            
            # Start monitoring
            self.comprehensive_monitor.start_monitoring()
            logger.info(f"Comprehensive monitoring started on port {self.config.metrics_port}")
            
        except Exception as e:
            logger.warning(f"Failed to initialize monitoring: {e}")
    
    def _initialize_status_reporting(self) -> None:
        """Initialize status reporting."""
        logger.info("Initializing status reporting")
        
        try:
            from ..database.manager import EnhancedDatabaseManager
            from .metrics import MetricsCollector
            
            db_manager = EnhancedDatabaseManager(self.config.database_path)
            metrics_collector = MetricsCollector(db_manager)
            
            self.status_reporter = StatusReporter(
                metrics_collector=metrics_collector,
                output_directory=self.config.output_directory
            )
            
            logger.info("Status reporting initialized")
            
        except Exception as e:
            logger.warning(f"Failed to initialize status reporting: {e}")
    
    def _validate_deployment(self) -> bool:
        """
        Validate deployment configuration and components.
        
        Returns:
            True if validation passes, False otherwise
        """
        logger.info("Validating deployment configuration")
        
        validation_errors = []
        
        # Validate directories
        required_dirs = [
            self.config.log_directory,
            self.config.output_directory,
            self.config.backup_directory
        ]
        
        for directory in required_dirs:
            if not Path(directory).exists():
                validation_errors.append(f"Required directory missing: {directory}")
        
        # Validate database path
        db_parent = Path(self.config.database_path).parent
        if not db_parent.exists():
            validation_errors.append(f"Database directory missing: {db_parent}")
        
        # Validate configuration file
        if not Path(self.config.config_path).exists():
            validation_errors.append(f"Configuration file missing: {self.config.config_path}")
        
        # Validate orchestrators
        if not self.orchestrators:
            validation_errors.append("No orchestrators initialized")
        
        # Validate cluster coordination (if enabled)
        if self.config.enable_clustering and not self.cluster_coordinator:
            validation_errors.append("Cluster coordination enabled but coordinator not initialized")
        
        # Validate monitoring (if enabled)
        if self.config.enable_monitoring and not self.comprehensive_monitor:
            validation_errors.append("Monitoring enabled but monitor not initialized")
        
        # Log validation results
        if validation_errors:
            logger.error("Deployment validation failed:")
            for error in validation_errors:
                logger.error(f"  - {error}")
            return False
        else:
            logger.success("Deployment validation passed")
            return True
    
    def start_production_system(self) -> bool:
        """
        Start the complete production system.
        
        Returns:
            True if system started successfully, False otherwise
        """
        logger.info("Starting production system")
        
        try:
            # Start health checks
            if self.deployment_manager:
                self.deployment_manager.setup_health_checks()
                self.deployment_manager.start_health_server()
                logger.info("Health check server started")
            
            # Start cluster coordination
            if self.cluster_coordinator:
                self.cluster_coordinator.start_health_monitoring()
                logger.info("Cluster health monitoring started")
            
            # Register shutdown handlers
            self._register_shutdown_handlers()
            
            logger.success("Production system started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start production system: {e}")
            return False
    
    def run_daily_automation(self) -> Dict[str, Any]:
        """
        Execute daily automation workflow.
        
        Returns:
            Dictionary with execution results
        """
        logger.info("Starting daily automation workflow")
        
        execution_id = f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        results = {
            'execution_id': execution_id,
            'started_at': start_time.isoformat(),
            'city_results': [],
            'total_new': 0,
            'total_failed': 0,
            'total_execution_time': 0,
            'status': 'running'
        }
        
        try:
            # Execute scraping for each city
            for orchestrator in self.orchestrators:
                logger.info(f"Starting daily scrape for {orchestrator.config.city}")
                
                city_result = orchestrator.run_daily_scrape()
                
                city_summary = {
                    'city': city_result.city,
                    'status': city_result.status.value,
                    'listings_new': city_result.listings_new,
                    'listings_failed': city_result.listings_failed,
                    'execution_time': city_result.execution_time_seconds
                }
                
                results['city_results'].append(city_summary)
                results['total_new'] += city_result.listings_new
                results['total_failed'] += city_result.listings_failed
                
                logger.info(f"Completed {orchestrator.config.city}: "
                           f"{city_result.listings_new} new, {city_result.listings_failed} failed")
            
            # Calculate totals
            end_time = datetime.now()
            results['completed_at'] = end_time.isoformat()
            results['total_execution_time'] = (end_time - start_time).total_seconds()
            results['status'] = 'completed'
            
            # Generate status report
            if self.status_reporter:
                report = self.status_reporter.generate_daily_report(results)
                logger.info(f"Daily report generated: {report}")
            
            logger.success(f"Daily automation completed: "
                          f"{results['total_new']} new listings, "
                          f"{results['total_failed']} failed, "
                          f"{results['total_execution_time']:.1f}s")
            
        except Exception as e:
            logger.error(f"Daily automation failed: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
            results['completed_at'] = datetime.now().isoformat()
        
        return results
    
    def get_system_status(self) -> DeploymentStatus:
        """
        Get comprehensive system status.
        
        Returns:
            Current deployment status
        """
        components = {}
        metrics = {}
        errors = []
        warnings = []
        
        # Check deployment manager
        if self.deployment_manager:
            try:
                health = self.deployment_manager._get_health_status()
                components['deployment_manager'] = health.status
                metrics['uptime_seconds'] = health.uptime_seconds
                metrics['memory_usage_mb'] = health.memory_usage_mb
                metrics['cpu_usage_percent'] = health.cpu_usage_percent
            except Exception as e:
                components['deployment_manager'] = 'error'
                errors.append(f"Deployment manager error: {e}")
        else:
            components['deployment_manager'] = 'not_initialized'
            warnings.append("Deployment manager not initialized")
        
        # Check orchestrators
        components['orchestrators'] = 'healthy' if self.orchestrators else 'not_initialized'
        metrics['orchestrator_count'] = len(self.orchestrators)
        
        # Check cluster coordinator
        if self.config.enable_clustering:
            if self.cluster_coordinator:
                try:
                    stats = self.cluster_coordinator.get_cluster_stats()
                    components['cluster_coordinator'] = 'healthy'
                    metrics['cluster_nodes'] = stats.get('nodes', {}).get('total', 0)
                except Exception as e:
                    components['cluster_coordinator'] = 'error'
                    errors.append(f"Cluster coordinator error: {e}")
            else:
                components['cluster_coordinator'] = 'not_initialized'
                warnings.append("Cluster coordination enabled but not initialized")
        
        # Check monitoring
        if self.config.enable_monitoring:
            components['monitoring'] = 'healthy' if self.comprehensive_monitor else 'not_initialized'
        
        # Check status reporter
        components['status_reporter'] = 'healthy' if self.status_reporter else 'not_initialized'
        
        # Determine overall status
        if errors:
            overall_status = 'failed'
        elif warnings:
            overall_status = 'degraded'
        else:
            overall_status = 'healthy'
        
        return DeploymentStatus(
            deployment_name=self.config.deployment_name,
            status=overall_status,
            started_at=self.start_time,
            last_check=datetime.now(),
            components=components,
            metrics=metrics,
            errors=errors,
            warnings=warnings
        )
    
    def create_backup(self) -> str:
        """
        Create system backup.
        
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{self.config.deployment_name}_backup_{timestamp}"
        backup_path = Path(self.config.backup_directory) / f"{backup_name}.tar.gz"
        
        logger.info(f"Creating system backup: {backup_path}")
        
        try:
            import tarfile
            
            with tarfile.open(backup_path, 'w:gz') as tar:
                # Backup database
                if Path(self.config.database_path).exists():
                    tar.add(self.config.database_path, arcname='database.duckdb')
                
                # Backup configuration
                if Path(self.config.config_path).exists():
                    tar.add(self.config.config_path, arcname='config.json')
                
                # Backup logs (recent only)
                log_dir = Path(self.config.log_directory)
                if log_dir.exists():
                    for log_file in log_dir.glob('*.log'):
                        # Only backup recent logs (last 7 days)
                        if (datetime.now() - datetime.fromtimestamp(log_file.stat().st_mtime)).days <= 7:
                            tar.add(log_file, arcname=f"logs/{log_file.name}")
            
            logger.success(f"Backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise
    
    def cleanup_old_data(self) -> Dict[str, int]:
        """
        Clean up old data based on retention policy.
        
        Returns:
            Dictionary with cleanup statistics
        """
        logger.info(f"Cleaning up data older than {self.config.retention_days} days")
        
        cleanup_stats = {
            'logs_removed': 0,
            'backups_removed': 0,
            'reports_removed': 0
        }
        
        cutoff_time = datetime.now().timestamp() - (self.config.retention_days * 24 * 3600)
        
        try:
            # Clean up old logs
            log_dir = Path(self.config.log_directory)
            if log_dir.exists():
                for log_file in log_dir.glob('*.log'):
                    if log_file.stat().st_mtime < cutoff_time:
                        log_file.unlink()
                        cleanup_stats['logs_removed'] += 1
            
            # Clean up old backups
            backup_dir = Path(self.config.backup_directory)
            if backup_dir.exists():
                for backup_file in backup_dir.glob('*.tar.gz'):
                    if backup_file.stat().st_mtime < cutoff_time:
                        backup_file.unlink()
                        cleanup_stats['backups_removed'] += 1
            
            # Clean up old reports
            output_dir = Path(self.config.output_directory)
            if output_dir.exists():
                for report_file in output_dir.glob('*.html'):
                    if report_file.stat().st_mtime < cutoff_time:
                        report_file.unlink()
                        cleanup_stats['reports_removed'] += 1
            
            logger.info(f"Cleanup completed: {cleanup_stats}")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
        
        return cleanup_stats
    
    def _register_shutdown_handlers(self) -> None:
        """Register shutdown handlers for graceful shutdown."""
        def shutdown_handler():
            logger.info("Shutting down production system")
            
            # Stop monitoring
            if self.comprehensive_monitor:
                try:
                    self.comprehensive_monitor.stop_monitoring()
                    logger.info("Monitoring stopped")
                except Exception as e:
                    logger.error(f"Failed to stop monitoring: {e}")
            
            # Stop cluster coordination
            if self.cluster_coordinator:
                try:
                    self.cluster_coordinator.coordinate_shutdown()
                    logger.info("Cluster coordination stopped")
                except Exception as e:
                    logger.error(f"Failed to stop cluster coordination: {e}")
        
        if self.deployment_manager:
            self.deployment_manager.register_shutdown_handler(shutdown_handler)
    
    def generate_production_documentation(self) -> str:
        """
        Generate comprehensive production documentation.
        
        Returns:
            Path to generated documentation
        """
        doc_path = Path(self.config.output_directory) / "production_documentation.md"
        
        logger.info(f"Generating production documentation: {doc_path}")
        
        try:
            status = self.get_system_status()
            
            documentation = f"""# Production Deployment Documentation

## Deployment Information
- **Name**: {self.config.deployment_name}
- **Type**: {self.config.deployment_type.value}
- **Environment**: {self.config.environment}
- **Started**: {self.start_time.isoformat()}
- **Status**: {status.status}

## Configuration
- **Database Path**: {self.config.database_path}
- **Config Path**: {self.config.config_path}
- **Log Directory**: {self.config.log_directory}
- **Output Directory**: {self.config.output_directory}
- **Backup Directory**: {self.config.backup_directory}

## System Components
"""
            
            for component, component_status in status.components.items():
                documentation += f"- **{component}**: {component_status}\n"
            
            documentation += f"""
## Metrics
"""
            for metric, value in status.metrics.items():
                documentation += f"- **{metric}**: {value}\n"
            
            if status.errors:
                documentation += f"""
## Errors
"""
                for error in status.errors:
                    documentation += f"- {error}\n"
            
            if status.warnings:
                documentation += f"""
## Warnings
"""
                for warning in status.warnings:
                    documentation += f"- {warning}\n"
            
            documentation += f"""
## Orchestrators
"""
            for orchestrator in self.orchestrators:
                documentation += f"""
### {orchestrator.config.city}
- **URL**: {orchestrator.config.url}
- **Max Workers**: {orchestrator.config.max_detail_workers}
- **Staleness Threshold**: {orchestrator.config.staleness_threshold_hours} hours
- **Smart Deduplication**: {orchestrator.config.enable_smart_deduplication}
"""
            
            documentation += f"""
## Operational Procedures

### Daily Operations
1. Check system status: Monitor health endpoints
2. Review daily reports: Check output directory
3. Monitor resource usage: CPU, memory, disk
4. Verify data quality: Run validation checks

### Maintenance
1. **Backup**: Run `create_backup()` method
2. **Cleanup**: Run `cleanup_old_data()` method
3. **Updates**: Follow deployment update procedures
4. **Monitoring**: Check comprehensive monitoring dashboard

### Troubleshooting
1. Check system logs in {self.config.log_directory}
2. Verify database connectivity
3. Check cluster coordination (if enabled)
4. Review error documentation in docs/errors/

## Generated: {datetime.now().isoformat()}
"""
            
            with open(doc_path, 'w', encoding='utf-8') as f:
                f.write(documentation)
            
            logger.success(f"Production documentation generated: {doc_path}")
            return str(doc_path)
            
        except Exception as e:
            logger.error(f"Failed to generate documentation: {e}")
            raise


def create_production_deployment(
    deployment_name: str,
    deployment_type: DeploymentType = DeploymentType.STANDALONE,
    environment: str = "production",
    config_overrides: Optional[Dict[str, Any]] = None
) -> ProductionDeploymentManager:
    """
    Create a production deployment manager with default configuration.
    
    Args:
        deployment_name: Name for the deployment
        deployment_type: Type of deployment
        environment: Environment name
        config_overrides: Optional configuration overrides
        
    Returns:
        Configured ProductionDeploymentManager
    """
    # Default configuration
    config = ProductionDeploymentConfig(
        deployment_name=deployment_name,
        deployment_type=deployment_type,
        environment=environment,
        database_path="data/real_estate.duckdb",
        config_path="config/config.json",
        log_directory="logs",
        output_directory="output",
        backup_directory="backups"
    )
    
    # Apply overrides
    if config_overrides:
        for key, value in config_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return ProductionDeploymentManager(config)


def main():
    """Main entry point for production deployment."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Oikotie Production Deployment Manager")
    parser.add_argument("--name", default="oikotie-production", help="Deployment name")
    parser.add_argument("--type", choices=["standalone", "container", "cluster"], 
                       default="standalone", help="Deployment type")
    parser.add_argument("--environment", default="production", help="Environment name")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--action", choices=["deploy", "start", "status", "backup", "cleanup"],
                       default="deploy", help="Action to perform")
    
    args = parser.parse_args()
    
    # Create deployment manager
    config_overrides = {}
    if args.config:
        config_overrides['config_path'] = args.config
    
    deployment_type = DeploymentType(args.type)
    manager = create_production_deployment(
        args.name, deployment_type, args.environment, config_overrides
    )
    
    try:
        if args.action == "deploy":
            # Full deployment
            if manager.initialize_deployment():
                if manager.start_production_system():
                    logger.success("Production deployment completed successfully")
                    manager.generate_production_documentation()
                else:
                    logger.error("Failed to start production system")
                    sys.exit(1)
            else:
                logger.error("Failed to initialize deployment")
                sys.exit(1)
        
        elif args.action == "start":
            # Start existing deployment
            if manager.start_production_system():
                logger.success("Production system started")
            else:
                logger.error("Failed to start production system")
                sys.exit(1)
        
        elif args.action == "status":
            # Show status
            status = manager.get_system_status()
            print(json.dumps(asdict(status), indent=2, default=str))
        
        elif args.action == "backup":
            # Create backup
            backup_path = manager.create_backup()
            print(f"Backup created: {backup_path}")
        
        elif args.action == "cleanup":
            # Cleanup old data
            stats = manager.cleanup_old_data()
            print(f"Cleanup completed: {stats}")
    
    except KeyboardInterrupt:
        logger.info("Deployment interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()