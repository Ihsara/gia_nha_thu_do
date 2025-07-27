#!/usr/bin/env python3
"""
Production deployment script for Oikotie Daily Scraper Automation.

This script provides a complete production deployment workflow including
validation, deployment, and post-deployment verification.
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oikotie.automation.production_deployment import (
    create_production_deployment,
    ProductionDeploymentConfig
)
from oikotie.automation.deployment import DeploymentType
from oikotie.automation.production_readiness import ProductionReadinessValidator
from oikotie.automation.production_dashboard import create_production_dashboard


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Also log to file
    log_file = f"deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logger.add(
        log_file,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB"
    )
    
    logger.info(f"Logging initialized - log file: {log_file}")


def check_prerequisites() -> bool:
    """Check system prerequisites for deployment."""
    logger.info("Checking system prerequisites...")
    
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 9):
        issues.append(f"Python {sys.version_info.major}.{sys.version_info.minor} < 3.9 (required)")
    
    # Check required directories
    required_dirs = ['config', 'data', 'logs', 'output', 'backups']
    for directory in required_dirs:
        if not Path(directory).exists():
            logger.info(f"Creating directory: {directory}")
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Check configuration file
    if not Path('config/config.json').exists():
        issues.append("Configuration file config/config.json not found")
    
    # Check uv availability
    try:
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            issues.append("uv package manager not available")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        issues.append("uv package manager not found")
    
    # Check Chrome/Chromium
    chrome_paths = [
        'google-chrome',
        'chromium-browser',
        'chromium',
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
    ]
    
    chrome_found = False
    for chrome_path in chrome_paths:
        try:
            result = subprocess.run([chrome_path, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info(f"Found Chrome: {result.stdout.strip()}")
                chrome_found = True
                break
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
    
    if not chrome_found:
        issues.append("Chrome/Chromium browser not found")
    
    if issues:
        logger.error("Prerequisites check failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False
    
    logger.success("Prerequisites check passed")
    return True


def install_dependencies() -> bool:
    """Install project dependencies."""
    logger.info("Installing dependencies...")
    
    try:
        # Install dependencies using uv
        result = subprocess.run(
            ['uv', 'sync', '--all-extras'],
            check=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        logger.success("Dependencies installed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Dependency installation failed: {e}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Dependency installation timed out")
        return False


def run_production_validation(config_path: str) -> bool:
    """Run production readiness validation."""
    logger.info("Running production readiness validation...")
    
    try:
        validator = ProductionReadinessValidator(config_path)
        report = validator.run_comprehensive_validation()
        
        # Generate report file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"production_readiness_report_{timestamp}.md"
        validator.generate_report_file(report, report_path)
        
        logger.info(f"Validation report generated: {report_path}")
        logger.info(f"Validation summary: {report.passed_checks} passed, {report.failed_checks} failed, {report.warning_checks} warnings")
        
        if report.overall_status == 'not_ready':
            logger.error("❌ System is NOT ready for production deployment")
            logger.error("Please address failed checks before proceeding")
            return False
        elif report.overall_status == 'warnings':
            logger.warning("⚠️  System has warnings but may be ready for production")
            logger.warning("Review warnings and proceed with caution")
            
            # Ask user if they want to continue with warnings
            response = input("Continue with warnings? (y/N): ").strip().lower()
            if response != 'y':
                logger.info("Deployment cancelled by user")
                return False
        else:
            logger.success("✅ System is ready for production deployment")
        
        return True
        
    except Exception as e:
        logger.error(f"Production validation failed: {e}")
        return False


def deploy_production_system(deployment_name: str, 
                           deployment_type: DeploymentType,
                           environment: str,
                           config_path: str) -> Optional[Any]:
    """Deploy the production system."""
    logger.info(f"Deploying production system: {deployment_name}")
    
    try:
        # Create deployment manager
        config_overrides = {
            'config_path': config_path,
            'database_path': 'data/real_estate.duckdb',
            'log_directory': 'logs',
            'output_directory': 'output',
            'backup_directory': 'backups'
        }
        
        deployment_manager = create_production_deployment(
            deployment_name,
            deployment_type,
            environment,
            config_overrides
        )
        
        # Initialize deployment
        logger.info("Initializing deployment...")
        if not deployment_manager.initialize_deployment():
            logger.error("Failed to initialize deployment")
            return None
        
        # Start production system
        logger.info("Starting production system...")
        if not deployment_manager.start_production_system():
            logger.error("Failed to start production system")
            return None
        
        # Generate documentation
        logger.info("Generating production documentation...")
        doc_path = deployment_manager.generate_production_documentation()
        logger.info(f"Production documentation: {doc_path}")
        
        logger.success("Production system deployed successfully")
        return deployment_manager
        
    except Exception as e:
        logger.error(f"Production deployment failed: {e}")
        return None


def run_post_deployment_tests(deployment_manager: Any) -> bool:
    """Run post-deployment verification tests."""
    logger.info("Running post-deployment verification...")
    
    try:
        # Test system status
        status = deployment_manager.get_system_status()
        logger.info(f"System status: {status.status}")
        
        if status.status == 'failed':
            logger.error("System status check failed")
            for error in status.errors:
                logger.error(f"  - {error}")
            return False
        
        # Test orchestrator functionality
        if not deployment_manager.orchestrators:
            logger.error("No orchestrators available")
            return False
        
        logger.info(f"Found {len(deployment_manager.orchestrators)} orchestrators")
        
        # Test execution planning (without actual execution)
        for orchestrator in deployment_manager.orchestrators:
            try:
                plan = orchestrator.plan_execution()
                logger.info(f"Execution plan for {plan['city']}: {plan['urls_to_process']} URLs to process")
            except Exception as e:
                logger.warning(f"Execution planning failed for {orchestrator.config.city}: {e}")
        
        # Test backup functionality
        logger.info("Testing backup functionality...")
        backup_path = deployment_manager.create_backup()
        logger.info(f"Test backup created: {backup_path}")
        
        logger.success("Post-deployment verification passed")
        return True
        
    except Exception as e:
        logger.error(f"Post-deployment verification failed: {e}")
        return False


def start_monitoring_dashboard(deployment_manager: Any, port: int = 8090) -> bool:
    """Start the monitoring dashboard."""
    logger.info(f"Starting monitoring dashboard on port {port}...")
    
    try:
        dashboard = create_production_dashboard(deployment_manager, port)
        
        if not dashboard:
            logger.warning("Dashboard not available (Flask may not be installed)")
            return False
        
        logger.info(f"Dashboard available at: http://localhost:{port}")
        logger.info("Press Ctrl+C to stop the dashboard")
        
        # Start dashboard (this will block)
        dashboard.start_dashboard()
        
        return True
        
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")
        return True
    except Exception as e:
        logger.error(f"Dashboard failed: {e}")
        return False


def run_daily_automation(deployment_manager: Any) -> bool:
    """Run daily automation workflow."""
    logger.info("Running daily automation workflow...")
    
    try:
        result = deployment_manager.run_daily_automation()
        
        logger.info(f"Daily automation completed: {result['status']}")
        logger.info(f"Execution ID: {result['execution_id']}")
        logger.info(f"Total new listings: {result['total_new']}")
        logger.info(f"Total failed: {result['total_failed']}")
        
        if result['status'] == 'completed':
            logger.success("Daily automation completed successfully")
            return True
        else:
            logger.error("Daily automation failed")
            return False
        
    except Exception as e:
        logger.error(f"Daily automation failed: {e}")
        return False


def main():
    """Main deployment workflow."""
    parser = argparse.ArgumentParser(description="Oikotie Production Deployment")
    parser.add_argument("--name", default="oikotie-production", help="Deployment name")
    parser.add_argument("--type", choices=["standalone", "container", "cluster"], 
                       default="standalone", help="Deployment type")
    parser.add_argument("--environment", default="production", help="Environment name")
    parser.add_argument("--config", default="config/config.json", help="Configuration file path")
    parser.add_argument("--skip-validation", action="store_true", help="Skip production readiness validation")
    parser.add_argument("--skip-dependencies", action="store_true", help="Skip dependency installation")
    parser.add_argument("--dashboard", action="store_true", help="Start monitoring dashboard after deployment")
    parser.add_argument("--dashboard-port", type=int, default=8090, help="Dashboard port")
    parser.add_argument("--run-daily", action="store_true", help="Run daily automation after deployment")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    logger.info("=" * 60)
    logger.info("Oikotie Daily Scraper Automation - Production Deployment")
    logger.info("=" * 60)
    logger.info(f"Deployment: {args.name}")
    logger.info(f"Type: {args.type}")
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Configuration: {args.config}")
    
    try:
        # Step 1: Check prerequisites
        if not check_prerequisites():
            logger.error("Prerequisites check failed")
            sys.exit(1)
        
        # Step 2: Install dependencies
        if not args.skip_dependencies:
            if not install_dependencies():
                logger.error("Dependency installation failed")
                sys.exit(1)
        else:
            logger.info("Skipping dependency installation")
        
        # Step 3: Run production validation
        if not args.skip_validation:
            if not run_production_validation(args.config):
                logger.error("Production validation failed")
                sys.exit(1)
        else:
            logger.warning("Skipping production validation")
        
        # Step 4: Deploy production system
        deployment_type = DeploymentType(args.type)
        deployment_manager = deploy_production_system(
            args.name,
            deployment_type,
            args.environment,
            args.config
        )
        
        if not deployment_manager:
            logger.error("Production deployment failed")
            sys.exit(1)
        
        # Step 5: Run post-deployment tests
        if not run_post_deployment_tests(deployment_manager):
            logger.error("Post-deployment verification failed")
            sys.exit(1)
        
        # Step 6: Run daily automation if requested
        if args.run_daily:
            if not run_daily_automation(deployment_manager):
                logger.error("Daily automation test failed")
                sys.exit(1)
        
        # Step 7: Start dashboard if requested
        if args.dashboard:
            start_monitoring_dashboard(deployment_manager, args.dashboard_port)
        
        logger.success("=" * 60)
        logger.success("Production deployment completed successfully!")
        logger.success("=" * 60)
        
        # Print next steps
        print("\n🎉 Deployment Complete!")
        print("\nNext Steps:")
        print(f"1. Review production documentation in output/")
        print(f"2. Monitor system health at http://localhost:8080/health")
        if args.dashboard:
            print(f"3. Access dashboard at http://localhost:{args.dashboard_port}")
        print(f"4. Schedule daily automation using cron or task scheduler")
        print(f"5. Set up monitoring and alerting")
        
        print("\nUseful Commands:")
        print(f"  # Check system status")
        print(f"  uv run python -m oikotie.automation.cli system_status")
        print(f"  # Run daily automation")
        print(f"  uv run python -m oikotie.automation.cli run --daily")
        print(f"  # Start dashboard")
        print(f"  uv run python -m oikotie.automation.cli production dashboard")
        print(f"  # Create backup")
        print(f"  uv run python -c \"from oikotie.automation.production_deployment import create_production_deployment; m=create_production_deployment('{args.name}'); print(m.create_backup())\"")
        
    except KeyboardInterrupt:
        logger.info("Deployment interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Deployment failed with unexpected error: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()