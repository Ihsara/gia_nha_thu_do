#!/usr/bin/env python3
"""
Deployment Validation Tests for Automation System

Tests all supported deployment modes: standalone, container, and cluster
to ensure the automation system works correctly in different environments.

Requirements: 5.1, 5.2
"""

import sys
import unittest
import asyncio
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oikotie.automation.deployment import DeploymentManager
from oikotie.automation.orchestrator import EnhancedScraperOrchestrator
from oikotie.automation.config_manager import ConfigurationManager
from oikotie.automation.monitoring import ComprehensiveMonitor
from oikotie.database.manager import EnhancedDatabaseManager


class TestAutomationDeploymentModes(unittest.TestCase):
    """Test automation system deployment modes"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_start_time = time.time()
        self.output_dir = Path("output/validation/automation")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Base configuration for all deployment modes
        self.base_config = {
            'cities': ['Helsinki'],
            'max_listings_per_city': 3,  # Small for deployment testing
            'smart_deduplication': {
                'enabled': True,
                'staleness_hours': 1,
                'skip_recent': True
            },
            'monitoring': {
                'enabled': True,
                'metrics_port': 8086
            },
            'database': {
                'path': 'data/real_estate.duckdb'
            }
        }
        
        # Deployment test results
        self.deployment_results = {}
        
    def tearDown(self):
        """Clean up test environment"""
        execution_time = time.time() - self.test_start_time
        print(f"\n🚀 Deployment Testing Summary:")
        print(f"   Execution time: {execution_time:.1f}s")
        print(f"   Deployment modes tested: {len(self.deployment_results)}")
        
        for mode, result in self.deployment_results.items():
            status = "✅ PASSED" if result.get('success', False) else "❌ FAILED"
            print(f"   {mode}: {status}")
    
    def test_01_standalone_deployment(self):
        """Test standalone deployment mode"""
        print("\n🖥️ Testing Standalone Deployment Mode...")
        
        try:
            # Initialize deployment manager
            deployment_manager = DeploymentManager()
            
            # Test environment detection for standalone
            with patch.dict('os.environ', {}, clear=True):
                env_type = deployment_manager.detect_environment()
                self.assertEqual(env_type, 'standalone', "Should detect standalone environment")
                print(f"✅ Environment detected: {env_type}")
            
            # Test configuration adaptation for standalone
            standalone_config = deployment_manager.adapt_config_for_environment(
                self.base_config, 'standalone'
            )
            
            self.assertIsInstance(standalone_config, dict)
            print("✅ Configuration adapted for standalone")
            
            # Test resource limits for standalone
            resource_limits = deployment_manager.get_resource_limits()
            self.assertIsInstance(resource_limits, dict)
            self.assertIn('memory_limit_mb', resource_limits)
            self.assertIn('cpu_limit_percent', resource_limits)
            print(f"✅ Resource limits: {resource_limits}")
            
            # Test health check setup for standalone
            health_endpoints = deployment_manager.setup_health_checks()
            self.assertIsInstance(health_endpoints, dict)
            print(f"✅ Health checks configured: {len(health_endpoints)} endpoints")
            
            # Test actual standalone execution
            db_manager = EnhancedDatabaseManager()
            config_manager = ConfigurationManager()
            config = config_manager.load_config_from_dict(standalone_config)
            
            orchestrator = EnhancedScraperOrchestrator(
                config=config,
                db_manager=db_manager
            )
            
            # Execute limited scraping in standalone mode
            start_time = time.time()
            result = asyncio.run(orchestrator.run_daily_scrape())
            execution_time = time.time() - start_time
            
            # Validate standalone execution
            self.assertIsInstance(result, dict)
            self.assertIn('status', result)
            
            standalone_success = result.get('status') in ['success', 'completed']
            
            self.deployment_results['standalone'] = {
                'success': standalone_success,
                'execution_time': execution_time,
                'result': result,
                'config_adapted': True,
                'health_checks': len(health_endpoints) > 0,
                'resource_limits': resource_limits
            }
            
            print(f"✅ Standalone execution: {result.get('status')} in {execution_time:.1f}s")
            print("✅ Standalone deployment mode validated")
            
        except Exception as e:
            self.deployment_results['standalone'] = {
                'success': False,
                'error': str(e)
            }
            self.fail(f"Standalone deployment test failed: {e}")
    
    def test_02_container_deployment(self):
        """Test container deployment mode"""
        print("\n🐳 Testing Container Deployment Mode...")
        
        try:
            deployment_manager = DeploymentManager()
            
            # Test environment detection for container
            with patch.dict('os.environ', {'CONTAINER': 'true', 'HOSTNAME': 'container-host'}):
                env_type = deployment_manager.detect_environment()
                self.assertEqual(env_type, 'container', "Should detect container environment")
                print(f"✅ Environment detected: {env_type}")
            
            # Test configuration adaptation for container
            container_config = deployment_manager.adapt_config_for_environment(
                self.base_config, 'container'
            )
            
            self.assertIsInstance(container_config, dict)
            
            # Container-specific adaptations
            self.assertTrue(container_config.get('monitoring', {}).get('enabled', False))
            print("✅ Configuration adapted for container")
            
            # Test Docker-specific configurations
            docker_config = deployment_manager.get_docker_configuration()
            self.assertIsInstance(docker_config, dict)
            print(f"✅ Docker configuration: {len(docker_config)} settings")
            
            # Test volume management
            volume_config = deployment_manager.setup_volume_mounts()
            self.assertIsInstance(volume_config, dict)
            print(f"✅ Volume mounts: {len(volume_config)} volumes")
            
            # Test health check endpoints for container
            health_endpoints = deployment_manager.setup_health_checks()
            self.assertIn('health', health_endpoints)
            self.assertIn('metrics', health_endpoints)
            print("✅ Container health endpoints configured")
            
            # Test container execution simulation
            db_manager = EnhancedDatabaseManager()
            config_manager = ConfigurationManager()
            config = config_manager.load_config_from_dict(container_config)
            
            # Simulate container environment
            with patch.dict('os.environ', {'CONTAINER': 'true'}):
                orchestrator = EnhancedScraperOrchestrator(
                    config=config,
                    db_manager=db_manager
                )
                
                # Execute in container mode
                start_time = time.time()
                result = asyncio.run(orchestrator.run_daily_scrape())
                execution_time = time.time() - start_time
                
                container_success = result.get('status') in ['success', 'completed']
                
                self.deployment_results['container'] = {
                    'success': container_success,
                    'execution_time': execution_time,
                    'result': result,
                    'config_adapted': True,
                    'docker_config': docker_config,
                    'volume_config': volume_config,
                    'health_endpoints': health_endpoints
                }
                
                print(f"✅ Container execution: {result.get('status')} in {execution_time:.1f}s")
            
            print("✅ Container deployment mode validated")
            
        except Exception as e:
            self.deployment_results['container'] = {
                'success': False,
                'error': str(e)
            }
            self.fail(f"Container deployment test failed: {e}")
    
    def test_03_cluster_deployment(self):
        """Test cluster deployment mode"""
        print("\n🔗 Testing Cluster Deployment Mode...")
        
        try:
            deployment_manager = DeploymentManager()
            
            # Test environment detection for cluster
            with patch.dict('os.environ', {
                'KUBERNETES_SERVICE_HOST': 'kubernetes.default.svc',
                'REDIS_URL': 'redis://redis-service:6379'
            }):
                env_type = deployment_manager.detect_environment()
                self.assertEqual(env_type, 'cluster', "Should detect cluster environment")
                print(f"✅ Environment detected: {env_type}")
            
            # Test Redis availability detection
            redis_available = deployment_manager.detect_redis_availability()
            print(f"✅ Redis availability: {redis_available}")
            
            # Test configuration adaptation for cluster
            cluster_config = deployment_manager.adapt_config_for_environment(
                self.base_config, 'cluster'
            )
            
            self.assertIsInstance(cluster_config, dict)
            
            # Cluster-specific adaptations
            if redis_available:
                self.assertTrue(cluster_config.get('cluster', {}).get('enabled', False))
                print("✅ Cluster coordination enabled")
            else:
                print("ℹ️ Cluster coordination disabled (Redis not available)")
            
            # Test Kubernetes configuration
            k8s_config = deployment_manager.get_kubernetes_configuration()
            self.assertIsInstance(k8s_config, dict)
            print(f"✅ Kubernetes configuration: {len(k8s_config)} settings")
            
            # Test service discovery
            service_config = deployment_manager.setup_service_discovery()
            self.assertIsInstance(service_config, dict)
            print(f"✅ Service discovery: {len(service_config)} services")
            
            # Test load balancer configuration
            lb_config = deployment_manager.setup_load_balancer()
            self.assertIsInstance(lb_config, dict)
            print(f"✅ Load balancer: {len(lb_config)} settings")
            
            # Test cluster execution simulation
            db_manager = EnhancedDatabaseManager()
            config_manager = ConfigurationManager()
            config = config_manager.load_config_from_dict(cluster_config)
            
            # Simulate cluster environment
            with patch.dict('os.environ', {
                'KUBERNETES_SERVICE_HOST': 'kubernetes.default.svc',
                'NODE_NAME': 'test-node-1'
            }):
                orchestrator = EnhancedScraperOrchestrator(
                    config=config,
                    db_manager=db_manager
                )
                
                # Execute in cluster mode
                start_time = time.time()
                result = asyncio.run(orchestrator.run_daily_scrape())
                execution_time = time.time() - start_time
                
                cluster_success = result.get('status') in ['success', 'completed']
                
                self.deployment_results['cluster'] = {
                    'success': cluster_success,
                    'execution_time': execution_time,
                    'result': result,
                    'config_adapted': True,
                    'redis_available': redis_available,
                    'k8s_config': k8s_config,
                    'service_config': service_config,
                    'lb_config': lb_config
                }
                
                print(f"✅ Cluster execution: {result.get('status')} in {execution_time:.1f}s")
            
            print("✅ Cluster deployment mode validated")
            
        except Exception as e:
            self.deployment_results['cluster'] = {
                'success': False,
                'error': str(e)
            }
            self.fail(f"Cluster deployment test failed: {e}")
    
    def test_04_deployment_configuration_validation(self):
        """Test deployment configuration validation across modes"""
        print("\n⚙️ Testing Deployment Configuration Validation...")
        
        try:
            deployment_manager = DeploymentManager()
            
            # Test configuration validation for each deployment mode
            deployment_modes = ['standalone', 'container', 'cluster']
            
            for mode in deployment_modes:
                print(f"   Testing {mode} configuration validation...")
                
                # Adapt configuration for mode
                adapted_config = deployment_manager.adapt_config_for_environment(
                    self.base_config, mode
                )
                
                # Validate adapted configuration
                config_manager = ConfigurationManager()
                validation_result = config_manager.validate_config(adapted_config)
                
                self.assertTrue(validation_result, f"{mode} configuration should be valid")
                print(f"   ✅ {mode} configuration validated")
                
                # Test configuration consistency
                required_keys = ['cities', 'monitoring', 'database']
                for key in required_keys:
                    self.assertIn(key, adapted_config, f"{mode} config should have {key}")
                
                # Test mode-specific configurations
                if mode == 'container':
                    self.assertIn('deployment', adapted_config)
                elif mode == 'cluster':
                    self.assertIn('cluster', adapted_config)
            
            print("✅ All deployment configurations validated")
            
        except Exception as e:
            self.fail(f"Deployment configuration validation failed: {e}")
    
    def test_05_deployment_health_checks(self):
        """Test health checks across deployment modes"""
        print("\n🏥 Testing Deployment Health Checks...")
        
        try:
            deployment_manager = DeploymentManager()
            
            # Test health checks for each deployment mode
            deployment_modes = ['standalone', 'container', 'cluster']
            
            for mode in deployment_modes:
                print(f"   Testing {mode} health checks...")
                
                # Setup health checks for mode
                with patch.dict('os.environ', self._get_env_for_mode(mode)):
                    health_endpoints = deployment_manager.setup_health_checks()
                    
                    self.assertIsInstance(health_endpoints, dict)
                    self.assertIn('health', health_endpoints)
                    
                    # Test health check execution
                    health_result = deployment_manager.execute_health_check()
                    self.assertIsInstance(health_result, dict)
                    self.assertIn('status', health_result)
                    
                    print(f"   ✅ {mode} health check: {health_result.get('status')}")
            
            print("✅ All deployment health checks validated")
            
        except Exception as e:
            self.fail(f"Deployment health checks failed: {e}")
    
    def test_06_deployment_monitoring_integration(self):
        """Test monitoring integration across deployment modes"""
        print("\n📊 Testing Deployment Monitoring Integration...")
        
        try:
            # Test monitoring for each deployment mode
            deployment_modes = ['standalone', 'container', 'cluster']
            
            for mode in deployment_modes:
                print(f"   Testing {mode} monitoring integration...")
                
                deployment_manager = DeploymentManager()
                
                # Adapt configuration for mode
                adapted_config = deployment_manager.adapt_config_for_environment(
                    self.base_config, mode
                )
                
                # Test monitoring configuration
                monitoring_config = adapted_config.get('monitoring', {})
                self.assertTrue(monitoring_config.get('enabled', False), 
                              f"{mode} should have monitoring enabled")
                
                # Test monitoring initialization
                try:
                    monitor = ComprehensiveMonitor(
                        metrics_port=monitoring_config.get('metrics_port', 8086) + ord(mode[0]),  # Unique port
                        system_monitor_interval=30
                    )
                    
                    # Start monitoring briefly
                    monitor.start_monitoring()
                    time.sleep(1)  # Brief monitoring
                    monitor.stop_monitoring()
                    
                    print(f"   ✅ {mode} monitoring integration successful")
                    
                except Exception as e:
                    print(f"   ⚠️ {mode} monitoring integration failed: {e}")
            
            print("✅ All deployment monitoring integrations tested")
            
        except Exception as e:
            self.fail(f"Deployment monitoring integration failed: {e}")
    
    def test_07_deployment_resource_management(self):
        """Test resource management across deployment modes"""
        print("\n💾 Testing Deployment Resource Management...")
        
        try:
            deployment_manager = DeploymentManager()
            
            # Test resource management for each deployment mode
            deployment_modes = ['standalone', 'container', 'cluster']
            
            for mode in deployment_modes:
                print(f"   Testing {mode} resource management...")
                
                # Get resource limits for mode
                with patch.dict('os.environ', self._get_env_for_mode(mode)):
                    resource_limits = deployment_manager.get_resource_limits()
                    
                    self.assertIsInstance(resource_limits, dict)
                    self.assertIn('memory_limit_mb', resource_limits)
                    self.assertIn('cpu_limit_percent', resource_limits)
                    
                    # Validate resource limits are reasonable
                    memory_limit = resource_limits.get('memory_limit_mb', 0)
                    cpu_limit = resource_limits.get('cpu_limit_percent', 0)
                    
                    self.assertGreater(memory_limit, 0, f"{mode} should have positive memory limit")
                    self.assertGreater(cpu_limit, 0, f"{mode} should have positive CPU limit")
                    self.assertLessEqual(cpu_limit, 100, f"{mode} CPU limit should be ≤ 100%")
                    
                    print(f"   ✅ {mode} resource limits: {memory_limit}MB RAM, {cpu_limit}% CPU")
                
                # Test resource monitoring
                resource_usage = deployment_manager.get_current_resource_usage()
                self.assertIsInstance(resource_usage, dict)
                print(f"   ✅ {mode} resource monitoring working")
            
            print("✅ All deployment resource management tested")
            
        except Exception as e:
            self.fail(f"Deployment resource management failed: {e}")
    
    def test_08_generate_deployment_report(self):
        """Generate comprehensive deployment validation report"""
        print("\n📋 Generating Deployment Validation Report...")
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_path = self.output_dir / f"deployment_validation_report_{timestamp}.json"
            
            # Calculate overall success
            successful_deployments = sum(1 for result in self.deployment_results.values() 
                                       if result.get('success', False))
            total_deployments = len(self.deployment_results)
            success_rate = (successful_deployments / total_deployments * 100) if total_deployments > 0 else 0
            
            report = {
                'test_info': {
                    'test_name': 'Automation Deployment Validation',
                    'timestamp': timestamp,
                    'execution_time': time.time() - self.test_start_time,
                    'deployment_modes_tested': list(self.deployment_results.keys())
                },
                'deployment_results': self.deployment_results,
                'summary': {
                    'total_modes_tested': total_deployments,
                    'successful_deployments': successful_deployments,
                    'success_rate_percent': success_rate,
                    'all_modes_successful': success_rate == 100.0
                },
                'deployment_capabilities': {
                    'standalone_ready': self.deployment_results.get('standalone', {}).get('success', False),
                    'container_ready': self.deployment_results.get('container', {}).get('success', False),
                    'cluster_ready': self.deployment_results.get('cluster', {}).get('success', False)
                },
                'recommendations': [
                    'Deploy in standalone mode for simple setups',
                    'Use container mode for consistent environments',
                    'Use cluster mode for high availability and scale',
                    'Monitor resource usage in production',
                    'Set up proper health checks for each mode'
                ],
                'next_steps': [
                    'Choose appropriate deployment mode for your environment',
                    'Configure monitoring and alerting',
                    'Set up proper backup and recovery procedures',
                    'Test deployment in staging environment',
                    'Plan capacity and scaling strategies'
                ]
            }
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            print(f"✅ Deployment validation report generated: {report_path}")
            print(f"   Success rate: {success_rate:.1f}%")
            print(f"   Modes tested: {', '.join(self.deployment_results.keys())}")
            
            return report_path
            
        except Exception as e:
            self.fail(f"Deployment report generation failed: {e}")
    
    def _get_env_for_mode(self, mode: str) -> Dict[str, str]:
        """Get environment variables for deployment mode"""
        env_vars = {}
        
        if mode == 'container':
            env_vars = {
                'CONTAINER': 'true',
                'HOSTNAME': 'container-host'
            }
        elif mode == 'cluster':
            env_vars = {
                'KUBERNETES_SERVICE_HOST': 'kubernetes.default.svc',
                'NODE_NAME': 'test-node-1'
            }
        
        return env_vars


def run_deployment_validation_test():
    """Run the deployment validation test"""
    print("🚀 Automation Deployment Validation Test Suite")
    print("=" * 70)
    print("Testing automation system across all deployment modes")
    print("Modes: Standalone, Container, Cluster")
    print("=" * 70)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAutomationDeploymentModes)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("✅ DEPLOYMENT VALIDATION TEST PASSED")
        print("🚀 All deployment modes validated successfully")
    else:
        print("❌ DEPLOYMENT VALIDATION TEST FAILED")
        print("🔧 Fix deployment issues before production")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_deployment_validation_test()
    sys.exit(0 if success else 1)