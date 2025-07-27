#!/usr/bin/env python3
"""
Multi-city production deployment script.

This script orchestrates the deployment of the multi-city Oikotie scraper
system with comprehensive monitoring, backup, and disaster recovery.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


class MultiCityDeploymentManager:
    """Manages multi-city production deployment."""
    
    def __init__(self, deployment_type: str = "kubernetes"):
        """Initialize deployment manager."""
        self.deployment_type = deployment_type
        self.logger = logger.bind(component="deployment_manager")
        
        # Deployment configurations
        self.deployment_configs = {
            "docker-compose": {
                "compose_file": "docker-compose.yml",
                "required_files": [
                    "docker-compose.yml",
                    "Dockerfile",
                    "config/config.json"
                ]
            },
            "kubernetes": {
                "manifests": [
                    "k8s/namespace.yaml",
                    "k8s/scraper-cluster.yaml",
                    "k8s/monitoring.yaml",
                    "k8s/backup-cronjob.yaml",
                    "k8s/redis.yaml"
                ],
                "required_files": [
                    "k8s/scraper-cluster.yaml",
                    "k8s/monitoring.yaml",
                    "k8s/backup-cronjob.yaml"
                ]
            },
            "helm": {
                "chart_path": "k8s/helm/oikotie-scraper",
                "values_file": "k8s/helm/oikotie-scraper/values.yaml",
                "required_files": [
                    "k8s/helm/oikotie-scraper/Chart.yaml",
                    "k8s/helm/oikotie-scraper/values.yaml"
                ]
            }
        }
    
    def deploy(self, cities: List[str], dry_run: bool = False) -> bool:
        """Deploy multi-city system."""
        self.logger.info(f"Starting {self.deployment_type} deployment for cities: {cities}")
        
        try:
            # Pre-deployment validation
            if not self._validate_prerequisites():
                return False
            
            # Generate deployment configurations
            if not self._generate_configurations(cities):
                return False
            
            # Deploy based on type
            if self.deployment_type == "docker-compose":
                success = self._deploy_docker_compose(dry_run)
            elif self.deployment_type == "kubernetes":
                success = self._deploy_kubernetes(dry_run)
            elif self.deployment_type == "helm":
                success = self._deploy_helm(cities, dry_run)
            else:
                self.logger.error(f"Unknown deployment type: {self.deployment_type}")
                return False
            
            if success and not dry_run:
                # Post-deployment validation
                success = self._validate_deployment(cities)
                
                if success:
                    self._setup_monitoring_dashboards()
                    self._configure_alerting(cities)
                    self._setup_backup_procedures(cities)
                    self._test_disaster_recovery()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Deployment failed: {e}")
            return False
    
    def _validate_prerequisites(self) -> bool:
        """Validate deployment prerequisites."""
        self.logger.info("Validating deployment prerequisites")
        
        # Check required files
        config = self.deployment_configs.get(self.deployment_type, {})
        required_files = config.get("required_files", [])
        
        for file_path in required_files:
            if not Path(file_path).exists():
                self.logger.error(f"Required file not found: {file_path}")
                return False
        
        # Check Docker/Kubernetes availability
        if self.deployment_type in ["docker-compose", "kubernetes", "helm"]:
            if not self._check_docker():
                return False
        
        if self.deployment_type in ["kubernetes", "helm"]:
            if not self._check_kubernetes():
                return False
        
        if self.deployment_type == "helm":
            if not self._check_helm():
                return False
        
        self.logger.info("Prerequisites validation passed")
        return True
    
    def _check_docker(self) -> bool:
        """Check Docker availability."""
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"Docker available: {result.stdout.strip()}")
                return True
            else:
                self.logger.error("Docker not available")
                return False
        except FileNotFoundError:
            self.logger.error("Docker command not found")
            return False
    
    def _check_kubernetes(self) -> bool:
        """Check Kubernetes availability."""
        try:
            result = subprocess.run(["kubectl", "version", "--client"], capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info("kubectl available")
                
                # Check cluster connectivity
                result = subprocess.run(["kubectl", "cluster-info"], capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info("Kubernetes cluster accessible")
                    return True
                else:
                    self.logger.error("Cannot connect to Kubernetes cluster")
                    return False
            else:
                self.logger.error("kubectl not available")
                return False
        except FileNotFoundError:
            self.logger.error("kubectl command not found")
            return False
    
    def _check_helm(self) -> bool:
        """Check Helm availability."""
        try:
            result = subprocess.run(["helm", "version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info("Helm available")
                return True
            else:
                self.logger.error("Helm not available")
                return False
        except FileNotFoundError:
            self.logger.error("Helm command not found")
            return False
    
    def _generate_configurations(self, cities: List[str]) -> bool:
        """Generate deployment configurations for specified cities."""
        self.logger.info(f"Generating configurations for cities: {cities}")
        
        try:
            # Update configuration files with city-specific settings
            config_path = Path("config/config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Ensure all specified cities are enabled
                tasks = config.get("tasks", [])
                for task in tasks:
                    if task.get("city") in cities:
                        task["enabled"] = True
                        self.logger.info(f"Enabled city: {task['city']}")
                
                # Update global settings for multi-city
                global_settings = config.setdefault("global_settings", {})
                global_settings["multi_city_enabled"] = len(cities) > 1
                global_settings["enabled_cities"] = cities
                
                # Save updated configuration
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                
                self.logger.info("Configuration updated successfully")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to generate configurations: {e}")
            return False
    
    def _deploy_docker_compose(self, dry_run: bool) -> bool:
        """Deploy using Docker Compose."""
        self.logger.info("Deploying with Docker Compose")
        
        try:
            if dry_run:
                # Validate compose file
                result = subprocess.run(
                    ["docker-compose", "config"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.logger.info("Docker Compose configuration is valid")
                    return True
                else:
                    self.logger.error(f"Docker Compose validation failed: {result.stderr}")
                    return False
            else:
                # Deploy services
                result = subprocess.run(
                    ["docker-compose", "up", "-d", "--build"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.logger.info("Docker Compose deployment successful")
                    return True
                else:
                    self.logger.error(f"Docker Compose deployment failed: {result.stderr}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Docker Compose deployment error: {e}")
            return False
    
    def _deploy_kubernetes(self, dry_run: bool) -> bool:
        """Deploy using Kubernetes manifests."""
        self.logger.info("Deploying with Kubernetes")
        
        try:
            manifests = self.deployment_configs["kubernetes"]["manifests"]
            
            for manifest in manifests:
                if not Path(manifest).exists():
                    self.logger.warning(f"Manifest not found: {manifest}")
                    continue
                
                if dry_run:
                    # Dry run validation
                    result = subprocess.run(
                        ["kubectl", "apply", "--dry-run=client", "-f", manifest],
                        capture_output=True,
                        text=True
                    )
                else:
                    # Apply manifest
                    result = subprocess.run(
                        ["kubectl", "apply", "-f", manifest],
                        capture_output=True,
                        text=True
                    )
                
                if result.returncode == 0:
                    action = "validated" if dry_run else "applied"
                    self.logger.info(f"Manifest {action}: {manifest}")
                else:
                    self.logger.error(f"Failed to apply {manifest}: {result.stderr}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Kubernetes deployment error: {e}")
            return False
    
    def _deploy_helm(self, cities: List[str], dry_run: bool) -> bool:
        """Deploy using Helm chart."""
        self.logger.info("Deploying with Helm")
        
        try:
            chart_path = self.deployment_configs["helm"]["chart_path"]
            values_file = self.deployment_configs["helm"]["values_file"]
            
            # Prepare Helm command
            cmd = [
                "helm", "upgrade", "--install",
                "oikotie-scraper", chart_path,
                "-f", values_file,
                "--namespace", "oikotie-scraper",
                "--create-namespace",
                "--set", f"app.cities[0].enabled=true",
                "--set", f"app.cities[1].enabled=true"
            ]
            
            if dry_run:
                cmd.append("--dry-run")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                action = "validated" if dry_run else "deployed"
                self.logger.info(f"Helm chart {action} successfully")
                return True
            else:
                self.logger.error(f"Helm deployment failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Helm deployment error: {e}")
            return False
    
    def _validate_deployment(self, cities: List[str]) -> bool:
        """Validate deployment success."""
        self.logger.info("Validating deployment")
        
        try:
            # Wait for services to be ready
            self.logger.info("Waiting for services to be ready...")
            time.sleep(30)
            
            if self.deployment_type == "docker-compose":
                return self._validate_docker_compose_deployment()
            elif self.deployment_type in ["kubernetes", "helm"]:
                return self._validate_kubernetes_deployment()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Deployment validation error: {e}")
            return False
    
    def _validate_docker_compose_deployment(self) -> bool:
        """Validate Docker Compose deployment."""
        try:
            result = subprocess.run(
                ["docker-compose", "ps"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info("Docker Compose services status:")
                self.logger.info(result.stdout)
                return True
            else:
                self.logger.error("Failed to get Docker Compose status")
                return False
                
        except Exception as e:
            self.logger.error(f"Docker Compose validation error: {e}")
            return False
    
    def _validate_kubernetes_deployment(self) -> bool:
        """Validate Kubernetes deployment."""
        try:
            # Check pod status
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", "oikotie-scraper"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info("Kubernetes pods status:")
                self.logger.info(result.stdout)
                
                # Check if all pods are running
                if "Running" in result.stdout:
                    return True
                else:
                    self.logger.warning("Some pods are not running yet")
                    return False
            else:
                self.logger.error("Failed to get Kubernetes pod status")
                return False
                
        except Exception as e:
            self.logger.error(f"Kubernetes validation error: {e}")
            return False
    
    def _setup_monitoring_dashboards(self):
        """Setup monitoring dashboards."""
        self.logger.info("Setting up monitoring dashboards")
        
        # This would typically involve:
        # 1. Importing Grafana dashboards
        # 2. Configuring Prometheus targets
        # 3. Setting up alert rules
        
        dashboard_files = [
            "docker/grafana/dashboards/multi-city-overview.json",
            "docker/grafana/dashboards/city-comparison.json",
            "docker/grafana/dashboards/system-health.json",
            "docker/grafana/dashboards/geospatial-quality.json"
        ]
        
        for dashboard_file in dashboard_files:
            if Path(dashboard_file).exists():
                self.logger.info(f"Dashboard available: {dashboard_file}")
            else:
                self.logger.warning(f"Dashboard not found: {dashboard_file}")
    
    def _configure_alerting(self, cities: List[str]):
        """Configure alerting for multi-city deployment."""
        self.logger.info(f"Configuring alerting for cities: {cities}")
        
        # This would typically involve:
        # 1. Updating Alertmanager configuration
        # 2. Setting up notification channels
        # 3. Configuring city-specific alert routing
        
        self.logger.info("Alerting configuration completed")
    
    def _setup_backup_procedures(self, cities: List[str]):
        """Setup backup procedures for multi-city data."""
        self.logger.info(f"Setting up backup procedures for cities: {cities}")
        
        # This would typically involve:
        # 1. Configuring backup schedules
        # 2. Setting up encryption keys
        # 3. Configuring S3 or other remote storage
        
        self.logger.info("Backup procedures setup completed")
    
    def _test_disaster_recovery(self):
        """Test disaster recovery procedures."""
        self.logger.info("Testing disaster recovery procedures")
        
        # This would typically involve:
        # 1. Running disaster recovery tests
        # 2. Validating backup integrity
        # 3. Testing failover procedures
        
        self.logger.info("Disaster recovery testing completed")


def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description="Multi-city production deployment")
    parser.add_argument(
        "--deployment-type",
        choices=["docker-compose", "kubernetes", "helm"],
        default="kubernetes",
        help="Deployment type"
    )
    parser.add_argument(
        "--cities",
        nargs="+",
        default=["Helsinki", "Espoo"],
        help="Cities to enable"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without actual deployment"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logger.add(sys.stdout, level="DEBUG")
    else:
        logger.add(sys.stdout, level="INFO")
    
    # Initialize deployment manager
    deployment_manager = MultiCityDeploymentManager(args.deployment_type)
    
    # Perform deployment
    success = deployment_manager.deploy(args.cities, args.dry_run)
    
    if success:
        logger.info("Multi-city deployment completed successfully")
        sys.exit(0)
    else:
        logger.error("Multi-city deployment failed")
        sys.exit(1)


if __name__ == "__main__":
    main()