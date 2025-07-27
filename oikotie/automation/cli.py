"""
Command-line interface for Oikotie Daily Scraper Automation.

This module provides CLI commands for running the scraper in different deployment modes,
managing configuration, and monitoring system health.
"""

import sys
import json
import time
import signal
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import click
from loguru import logger

from .deployment import DeploymentManager, DeploymentType, create_deployment_manager
from .orchestrator import EnhancedScraperOrchestrator, load_config_and_create_orchestrators
from .cluster import ClusterCoordinator, create_cluster_coordinator, HealthStatus, NodeStatus
from .status_cli import status as status_commands
from .security_cli import security_cli


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--log-level', default='INFO', help='Log level (DEBUG, INFO, WARNING, ERROR)')
@click.pass_context
def cli(ctx, config, log_level):
    """Oikotie Daily Scraper Automation CLI."""
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    
    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['log_level'] = log_level


@cli.command()
@click.option('--daily', is_flag=True, help='Run daily scraping workflow')
@click.option('--cluster', is_flag=True, help='Run in cluster mode')
@click.option('--city', help='Specific city to scrape')
@click.option('--deployment-type', type=click.Choice(['standalone', 'container', 'cluster']), 
              help='Override deployment type detection')
@click.pass_context
def run(ctx, daily, cluster, city, deployment_type):
    """Run the scraper automation system."""
    try:
        # Create deployment manager
        deployment_manager = create_deployment_manager(ctx.obj.get('config_path'))
        
        # Override deployment type if specified
        if deployment_type:
            deployment_type_enum = DeploymentType(deployment_type)
            config = deployment_manager.configure_for_environment(deployment_type_enum)
        else:
            config = deployment_manager.get_configuration()
        
        logger.info(f"Starting scraper in {config.deployment_type.value} mode")
        
        if cluster or config.deployment_type == DeploymentType.CLUSTER:
            run_cluster_mode(deployment_manager, city)
        elif daily:
            run_daily_mode(deployment_manager, city)
        else:
            run_interactive_mode(deployment_manager, city)
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to run scraper: {e}")
        sys.exit(1)


def run_daily_mode(deployment_manager: DeploymentManager, city: Optional[str] = None):
    """Run daily scraping workflow."""
    logger.info("Starting daily scraping workflow")
    
    try:
        # Load orchestrators
        orchestrators = load_config_and_create_orchestrators()
        
        if city:
            # Filter to specific city
            orchestrators = [o for o in orchestrators if o.config.city.lower() == city.lower()]
            if not orchestrators:
                logger.error(f"No configuration found for city: {city}")
                return
        
        if not orchestrators:
            logger.error("No enabled scraping tasks found in configuration")
            return
        
        # Register shutdown handler
        def shutdown_handler():
            logger.info("Shutting down orchestrators...")
            # In a full implementation, we would gracefully stop ongoing scraping
        
        deployment_manager.register_shutdown_handler(shutdown_handler)
        
        # Run daily scraping for each city
        results = []
        for orchestrator in orchestrators:
            logger.info(f"Starting daily scrape for {orchestrator.config.city}")
            result = orchestrator.run_daily_scrape()
            results.append(result)
            
            logger.info(f"Completed {orchestrator.config.city}: "
                       f"{result.listings_new} new, {result.listings_failed} failed")
        
        # Summary
        total_new = sum(r.listings_new for r in results)
        total_failed = sum(r.listings_failed for r in results)
        logger.success(f"Daily scraping completed: {total_new} new listings, {total_failed} failed")
        
    except Exception as e:
        logger.error(f"Daily scraping failed: {e}")
        raise


def run_cluster_mode(deployment_manager: DeploymentManager, city: Optional[str] = None):
    """Run in cluster coordination mode."""
    config = deployment_manager.get_configuration()
    
    if not config.cluster_coordination_enabled:
        logger.error("Cluster coordination not enabled")
        return
    
    logger.info("Starting cluster coordination mode")
    
    try:
        # Create cluster coordinator
        coordinator = create_cluster_coordinator(config.redis_url, config.node_id)
        if not coordinator:
            logger.error("Failed to create cluster coordinator")
            return
        
        # Register node with cluster
        node_health = HealthStatus(
            node_id=config.node_id,
            status=NodeStatus.HEALTHY,
            last_heartbeat=time.time(),
            cpu_usage=0.0,
            memory_usage_mb=0.0,
            active_work_items=0,
            completed_work_items=0,
            failed_work_items=0,
            uptime_seconds=0.0
        )
        
        coordinator.register_node(node_health)
        
        # Register shutdown handler
        def shutdown_handler():
            logger.info("Coordinating cluster shutdown...")
            coordinator.coordinate_shutdown()
        
        deployment_manager.register_shutdown_handler(shutdown_handler)
        
        # Main cluster worker loop
        logger.info("Starting cluster worker loop")
        run_cluster_worker_loop(coordinator, deployment_manager, city)
        
    except Exception as e:
        logger.error(f"Cluster mode failed: {e}")
        raise


def run_cluster_worker_loop(coordinator: ClusterCoordinator, 
                           deployment_manager: DeploymentManager,
                           city_filter: Optional[str] = None):
    """Run the main cluster worker loop."""
    from .psutil_compat import psutil
    from datetime import datetime
    
    start_time = datetime.now()
    heartbeat_interval = 30  # seconds
    last_heartbeat = 0
    
    while True:
        try:
            current_time = time.time()
            
            # Send heartbeat
            if current_time - last_heartbeat > heartbeat_interval:
                uptime = (datetime.now() - start_time).total_seconds()
                memory_usage = psutil.virtual_memory().used / 1024 / 1024  # MB
                cpu_usage = psutil.cpu_percent(interval=1)
                
                health = HealthStatus(
                    node_id=coordinator.node_id,
                    status=NodeStatus.HEALTHY,
                    last_heartbeat=datetime.now(),
                    cpu_usage=cpu_usage,
                    memory_usage_mb=memory_usage,
                    active_work_items=0,  # TODO: Track actual work items
                    completed_work_items=0,
                    failed_work_items=0,
                    uptime_seconds=uptime
                )
                
                coordinator.send_heartbeat(health)
                last_heartbeat = current_time
            
            # Get next work item
            work_item = coordinator.get_next_work_item()
            if work_item:
                logger.info(f"Processing work item: {work_item.id}")
                
                try:
                    # Process work item based on type
                    if work_item.type == 'city_scrape':
                        result = process_city_scrape_work(work_item, city_filter)
                        coordinator.complete_work_item(work_item, result)
                    else:
                        logger.warning(f"Unknown work item type: {work_item.type}")
                        coordinator.fail_work_item(work_item, f"Unknown work type: {work_item.type}")
                
                except Exception as e:
                    logger.error(f"Failed to process work item {work_item.id}: {e}")
                    coordinator.fail_work_item(work_item, str(e))
            
            else:
                # No work available, sleep briefly
                time.sleep(5)
            
            # Cleanup stale work periodically
            if current_time % 300 < 5:  # Every 5 minutes
                coordinator.cleanup_stale_work()
        
        except KeyboardInterrupt:
            logger.info("Cluster worker loop interrupted")
            break
        except Exception as e:
            logger.error(f"Error in cluster worker loop: {e}")
            time.sleep(10)  # Wait before retrying


def process_city_scrape_work(work_item, city_filter: Optional[str] = None) -> Dict[str, Any]:
    """Process a city scraping work item."""
    city = work_item.data.get('city')
    
    if city_filter and city.lower() != city_filter.lower():
        return {'status': 'skipped', 'reason': 'city_filter'}
    
    # Load configuration for the city
    orchestrators = load_config_and_create_orchestrators()
    city_orchestrator = None
    
    for orchestrator in orchestrators:
        if orchestrator.config.city.lower() == city.lower():
            city_orchestrator = orchestrator
            break
    
    if not city_orchestrator:
        raise Exception(f"No configuration found for city: {city}")
    
    # Run daily scrape
    result = city_orchestrator.run_daily_scrape()
    
    return {
        'status': 'completed',
        'city': city,
        'listings_new': result.listings_new,
        'listings_failed': result.listings_failed,
        'execution_time': result.execution_time_seconds
    }


def run_interactive_mode(deployment_manager: DeploymentManager, city: Optional[str] = None):
    """Run in interactive mode for development/testing."""
    logger.info("Starting interactive mode")
    
    try:
        orchestrators = load_config_and_create_orchestrators()
        
        if city:
            orchestrators = [o for o in orchestrators if o.config.city.lower() == city.lower()]
        
        if not orchestrators:
            logger.error("No orchestrators available")
            return
        
        logger.info(f"Available cities: {[o.config.city for o in orchestrators]}")
        
        # Simple interactive loop
        while True:
            try:
                command = input("\nEnter command (run/status/quit): ").strip().lower()
                
                if command == 'quit' or command == 'q':
                    break
                elif command == 'run' or command == 'r':
                    for orchestrator in orchestrators:
                        logger.info(f"Running scraper for {orchestrator.config.city}")
                        result = orchestrator.run_daily_scrape()
                        print(f"Result: {result.listings_new} new, {result.listings_failed} failed")
                elif command == 'status' or command == 's':
                    config = deployment_manager.get_configuration()
                    print(f"Deployment: {config.deployment_type.value}")
                    print(f"Environment: {config.environment_type.value}")
                    print(f"Node ID: {config.node_id}")
                else:
                    print("Unknown command. Use 'run', 'status', or 'quit'")
            
            except KeyboardInterrupt:
                break
            except EOFError:
                break
        
        logger.info("Interactive mode ended")
        
    except Exception as e:
        logger.error(f"Interactive mode failed: {e}")
        raise


@cli.command()
@click.pass_context
def system_status(ctx):
    """Show system deployment status and health information."""
    try:
        deployment_manager = create_deployment_manager(ctx.obj.get('config_path'))
        config = deployment_manager.get_configuration()
        
        print(f"Deployment Type: {config.deployment_type.value}")
        print(f"Environment: {config.environment_type.value}")
        print(f"Node ID: {config.node_id}")
        print(f"Health Checks: {'Enabled' if config.health_check_enabled else 'Disabled'}")
        print(f"Cluster Mode: {'Enabled' if config.cluster_coordination_enabled else 'Disabled'}")
        
        if config.cluster_coordination_enabled and config.redis_url:
            coordinator = create_cluster_coordinator(config.redis_url, config.node_id)
            if coordinator:
                stats = coordinator.get_cluster_stats()
                print(f"\nCluster Stats:")
                print(f"  Nodes: {stats.get('nodes', {}).get('total', 0)}")
                print(f"  Work Queued: {stats.get('work', {}).get('queued', 0)}")
                print(f"  Work Processing: {stats.get('work', {}).get('processing', 0)}")
        
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        sys.exit(1)


# Add status reporting commands as a subgroup
cli.add_command(status_commands, name='reports')

# Add security management commands as a subgroup
cli.add_command(security_cli, name='security')

# Add alert management commands as a subgroup
from .alert_cli import alerts as alert_commands
cli.add_command(alert_commands, name='alerts')

# Add scheduler management commands as a subgroup
from .scheduler_cli import scheduler as scheduler_commands
cli.add_command(scheduler_commands, name='scheduler')


@cli.group()
@click.pass_context
def production(ctx):
    """Production deployment and management commands."""
    pass


@production.command()
@click.option('--name', default='oikotie-production', help='Deployment name')
@click.option('--type', 'deployment_type', type=click.Choice(['standalone', 'container', 'cluster']), 
              default='standalone', help='Deployment type')
@click.option('--environment', default='production', help='Environment name')
@click.option('--action', type=click.Choice(['deploy', 'start', 'status', 'backup', 'cleanup']),
              default='deploy', help='Action to perform')
@click.pass_context
def deploy(ctx, name, deployment_type, environment, action):
    """Deploy and manage production system."""
    try:
        from .production_deployment import create_production_deployment, DeploymentType
        
        # Create deployment manager
        config_overrides = {}
        if ctx.obj.get('config_path'):
            config_overrides['config_path'] = ctx.obj['config_path']
        
        deployment_type_enum = DeploymentType(deployment_type)
        manager = create_production_deployment(
            name, deployment_type_enum, environment, config_overrides
        )
        
        if action == 'deploy':
            # Full deployment
            if manager.initialize_deployment():
                if manager.start_production_system():
                    logger.success("Production deployment completed successfully")
                    doc_path = manager.generate_production_documentation()
                    logger.info(f"Documentation generated: {doc_path}")
                else:
                    logger.error("Failed to start production system")
                    sys.exit(1)
            else:
                logger.error("Failed to initialize deployment")
                sys.exit(1)
        
        elif action == 'start':
            if manager.start_production_system():
                logger.success("Production system started")
            else:
                logger.error("Failed to start production system")
                sys.exit(1)
        
        elif action == 'status':
            status = manager.get_system_status()
            print(json.dumps(asdict(status), indent=2, default=str))
        
        elif action == 'backup':
            backup_path = manager.create_backup()
            print(f"Backup created: {backup_path}")
        
        elif action == 'cleanup':
            stats = manager.cleanup_old_data()
            print(f"Cleanup completed: {stats}")
    
    except Exception as e:
        logger.error(f"Production deployment failed: {e}")
        sys.exit(1)


@production.command()
@click.option('--port', default=8090, help='Dashboard port')
@click.pass_context
def dashboard(ctx, port):
    """Start production monitoring dashboard."""
    try:
        from .production_deployment import create_production_deployment, DeploymentType
        from .production_dashboard import create_production_dashboard
        
        # Create deployment manager
        config_overrides = {}
        if ctx.obj.get('config_path'):
            config_overrides['config_path'] = ctx.obj['config_path']
        
        deployment_manager = create_production_deployment(
            'dashboard-deployment',
            DeploymentType.STANDALONE,
            'production',
            config_overrides
        )
        
        # Initialize deployment
        if not deployment_manager.initialize_deployment():
            logger.error("Failed to initialize deployment for dashboard")
            sys.exit(1)
        
        # Create and start dashboard
        dashboard = create_production_dashboard(deployment_manager, port)
        if dashboard:
            logger.info(f"Starting production dashboard on http://localhost:{port}")
            dashboard.start_dashboard()
        else:
            logger.error("Failed to create production dashboard")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Dashboard failed: {e}")
        sys.exit(1)


@production.command()
@click.option('--output', help='Output report file path')
@click.option('--json-output', is_flag=True, help='Output JSON format')
@click.pass_context
def validate(ctx, output, json_output):
    """Run production readiness validation."""
    try:
        from .production_readiness import ProductionReadinessValidator
        
        # Create validator
        validator = ProductionReadinessValidator(ctx.obj.get('config_path'))
        
        # Run validation
        logger.info("Running production readiness validation...")
        report = validator.run_comprehensive_validation()
        
        # Output results
        if json_output:
            print(json.dumps(asdict(report), indent=2, default=str))
        else:
            # Generate markdown report
            report_path = validator.generate_report_file(report, output)
            logger.info(f"Production readiness report: {report_path}")
            
            # Print summary
            print(f"\nValidation Summary:")
            print(f"Overall Status: {report.overall_status.upper()}")
            print(f"Checks: {report.passed_checks} passed, {report.failed_checks} failed, {report.warning_checks} warnings")
            
            if report.overall_status == 'not_ready':
                print("\n❌ System is NOT ready for production deployment")
                print("Please address failed checks before proceeding.")
            elif report.overall_status == 'warnings':
                print("\n⚠️  System has warnings but may be ready for production")
                print("Review warnings and proceed with caution.")
            else:
                print("\n✅ System is ready for production deployment")
        
        # Exit with appropriate code
        if report.overall_status == 'not_ready':
            sys.exit(1)
        elif report.overall_status == 'warnings':
            sys.exit(2)
    
    except Exception as e:
        logger.error(f"Production validation failed: {e}")
        sys.exit(1)


# Add production commands as a subgroup
cli.add_command(production)


@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.pass_context
def config(ctx, output):
    """Generate configuration template."""
    try:
        deployment_manager = create_deployment_manager()
        config = deployment_manager.get_configuration()
        
        template = {
            "deployment": {
                "health_check_port": config.health_check_port,
                "database_path": config.database_path,
                "log_level": config.log_level,
                "max_workers": config.max_workers,
                "headless_browser": config.headless_browser,
                "enable_metrics": config.enable_metrics,
                "graceful_shutdown_timeout": config.graceful_shutdown_timeout
            },
            "tasks": [
                {
                    "city": "Helsinki",
                    "enabled": True,
                    "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
                    "max_detail_workers": 5,
                    "staleness_threshold_hours": 24,
                    "retry_limit": 3,
                    "batch_size": 100
                }
            ]
        }
        
        config_json = json.dumps(template, indent=2)
        
        if output:
            with open(output, 'w') as f:
                f.write(config_json)
            print(f"Configuration template written to {output}")
        else:
            print(config_json)
    
    except Exception as e:
        logger.error(f"Failed to generate config: {e}")
        sys.exit(1)


@cli.command()
@click.option('--port', default=8080, help='Health check port')
@click.pass_context
def health(ctx, port):
    """Start standalone health check server."""
    try:
        deployment_manager = create_deployment_manager(ctx.obj.get('config_path'))
        config = deployment_manager.get_configuration()
        config.health_check_port = port
        config.health_check_enabled = True
        
        app = deployment_manager.setup_health_checks()
        if app:
            logger.info(f"Starting health check server on port {port}")
            app.run(host='0.0.0.0', port=port, debug=False)
        else:
            logger.error("Failed to setup health checks")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Failed to start health server: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()