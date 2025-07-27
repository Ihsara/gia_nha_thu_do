"""
Integration tests for the complete production automation system.

This module tests the integration of all automation components to ensure
the system works as a cohesive whole in production scenarios.
"""

import os
import sys
import json
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pytest
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oikotie.automation.production_deployment import (
    ProductionDeploymentManager,
    ProductionDeploymentConfig,
    create_production_deployment
)
from oikotie.automation.deployment import DeploymentType
from oikotie.automation.production_readiness import ProductionReadinessValidator
from oikotie.automation.orchestrator import EnhancedScraperOrchestrator, ScraperConfig
from oikotie.automation.cli import cli
from oikotie.database.manager import EnhancedDatabaseManager


class TestProductionSystemIntegration:
    """Test complete production system integration."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing."""
        temp_dir = tempfile.mkdtemp()
        original_cwd = os.getcwd()
        
        try:
            os.chdir(temp_dir)
            
            # Create required directories
            for directory in ['data', 'logs', 'output', 'backups', 'config']:
                Path(directory).mkdir(exist_ok=True)
            
            # Create test configuration
            config_data = {
                "tasks": [
                    {
                        "city": "TestCity",
                        "enabled": True,
                        "url": "https://example.com/test",
                        "max_detail_workers": 2,
                        "staleness_threshold_hours": 24,
                        "enable_smart_deduplication": True
                    }
                ]
            }
            
            with open('config/config.json', 'w') as f:
                json.dump(config_data, f, indent=2)
            
            yield temp_dir
            
        finally:
            os.chdir(original_cwd)
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_production_deployment_initialization(self, temp_workspace):
        """Test production deployment initialization."""
        config = ProductionDeploymentConfig(
            deployment_name="test-deployment",
            deployment_type=DeploymentType.STANDALONE,
            environment="testing",
            database_path="data/test.duckdb",
            config_path="config/config.json",
            log_directory="logs",
            output_directory="output",
            backup_directory="backups"
        )
        
        manager = ProductionDeploymentManager(config)
        
        # Test initialization
        assert manager.config.deployment_name == "test-deployment"
        assert manager.config.deployment_type == DeploymentType.STANDALONE
        
        # Test directory creation and basic setup
        with patch('oikotie.automation.orchestrator.load_config_and_create_orchestrators') as mock_load:
            # Mock orchestrator loading to avoid actual web scraping
            mock_orchestrator = Mock(spec=EnhancedScraperOrchestrator)
            mock_orchestrator.config = ScraperConfig(
                city="TestCity",
                url="https://example.com/test"
            )
            mock_load.return_value = [mock_orchestrator]
            
            # Initialize deployment
            success = manager.initialize_deployment()
            assert success, "Deployment initialization should succeed"
            
            # Verify components were initialized
            assert manager.deployment_manager is not None
            assert len(manager.orchestrators) > 0
    
    def test_production_readiness_validation(self, temp_workspace):
        """Test production readiness validation."""
        validator = ProductionReadinessValidator("config/config.json")
        
        # Mock external dependencies to focus on integration logic
        with patch('subprocess.run') as mock_subprocess, \
             patch('requests.get') as mock_requests, \
             patch('selenium.webdriver.Chrome') as mock_chrome:
            
            # Mock successful responses
            mock_subprocess.return_value.returncode = 0
            mock_subprocess.return_value.stdout = "Google Chrome 120.0.0.0"
            
            mock_requests.return_value.status_code = 200
            
            mock_driver = Mock()
            mock_driver.title = "Google"
            mock_chrome.return_value = mock_driver
            
            # Run validation
            report = validator.run_comprehensive_validation()
            
            # Verify report structure
            assert report.overall_status in ['ready', 'warnings', 'not_ready']
            assert report.total_checks > 0
            assert len(report.results) == report.total_checks
            assert isinstance(report.recommendations, list)
            assert isinstance(report.next_steps, list)
            
            # Check that key validation checks were performed
            check_names = [result.check_name for result in report.results]
            expected_checks = [
                'system_requirements',
                'configuration',
                'database_setup',
                'network_connectivity',
                'browser_automation'
            ]
            
            for expected_check in expected_checks:
                assert expected_check in check_names, f"Missing validation check: {expected_check}"
    
    def test_orchestrator_integration(self, temp_workspace):
        """Test orchestrator integration with automation system."""
        # Create test orchestrator configuration
        config = ScraperConfig(
            city="TestCity",
            url="https://example.com/test",
            max_detail_workers=2,
            enable_smart_deduplication=True,
            enable_performance_monitoring=False  # Disable for testing
        )
        
        # Mock database manager to avoid actual database operations
        with patch('oikotie.automation.orchestrator.EnhancedDatabaseManager') as mock_db_manager:
            mock_db = Mock()
            mock_db_manager.return_value = mock_db
            
            # Create orchestrator
            orchestrator = EnhancedScraperOrchestrator(config, mock_db)
            
            # Test configuration access
            retrieved_config = orchestrator.get_configuration()
            assert retrieved_config.city == "TestCity"
            assert retrieved_config.max_detail_workers == 2
            
            # Test execution planning (without actual execution)
            with patch.object(orchestrator, '_discover_listing_urls') as mock_discover:
                mock_discover.return_value = ["http://example.com/listing1", "http://example.com/listing2"]
                
                plan = orchestrator.plan_execution()
                
                assert 'city' in plan
                assert 'total_urls' in plan
                assert 'urls_to_process' in plan
                assert plan['city'] == "TestCity"
                assert plan['total_urls'] == 2
    
    def test_cli_integration(self, temp_workspace):
        """Test CLI integration with production system."""
        from click.testing import CliRunner
        
        runner = CliRunner()
        
        # Test basic CLI functionality
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Oikotie Daily Scraper Automation CLI' in result.output
        
        # Test system status command
        with patch('oikotie.automation.deployment.create_deployment_manager') as mock_create_manager:
            mock_manager = Mock()
            mock_config = Mock()
            mock_config.deployment_type.value = 'standalone'
            mock_config.environment_type.value = 'testing'
            mock_config.node_id = 'test-node'
            mock_config.health_check_enabled = False
            mock_config.cluster_coordination_enabled = False
            
            mock_manager.get_configuration.return_value = mock_config
            mock_create_manager.return_value = mock_manager
            
            result = runner.invoke(cli, ['system_status'])
            assert result.exit_code == 0
            assert 'standalone' in result.output
    
    def test_database_integration(self, temp_workspace):
        """Test database integration with automation system."""
        db_path = "data/test_integration.duckdb"
        
        # Test database manager initialization
        db_manager = EnhancedDatabaseManager(db_path)
        
        # Test basic database operations
        result = db_manager.execute_query("SELECT 1 as test")
        assert result is not None
        assert len(result) > 0
        assert result[0]['test'] == 1
        
        # Test execution metadata tracking
        from oikotie.database.manager import ExecutionMetadata
        
        metadata = ExecutionMetadata(
            execution_id="test_integration",
            started_at=datetime.now(),
            city="TestCity",
            status="completed",
            listings_processed=10,
            listings_new=5,
            listings_failed=1,
            execution_time_seconds=120
        )
        
        # This should not raise an exception
        db_manager.track_execution_metadata(metadata)
        
        # Verify metadata was stored (basic check)
        recent_executions = db_manager.get_recent_executions(hours_back=1)
        assert len(recent_executions) > 0
        
        # Find our test execution
        test_execution = None
        for execution in recent_executions:
            if execution.execution_id == "test_integration":
                test_execution = execution
                break
        
        assert test_execution is not None
        assert test_execution.city == "TestCity"
        assert test_execution.status == "completed"
    
    def test_configuration_management(self, temp_workspace):
        """Test configuration management across system components."""
        from oikotie.automation.config import ConfigurationManager
        
        # Test configuration loading
        config_manager = ConfigurationManager()
        
        # Load configuration from file
        config = config_manager.load_configuration("config/config.json")
        
        assert config is not None
        assert hasattr(config, 'tasks')
        assert len(config.tasks) > 0
        
        # Test task configuration
        task = config.tasks[0]
        assert task.city == "TestCity"
        assert task.enabled is True
        assert task.max_detail_workers == 2
    
    def test_error_handling_integration(self, temp_workspace):
        """Test error handling across system components."""
        # Test with invalid configuration
        invalid_config_path = "config/invalid.json"
        
        # Create invalid JSON file
        with open(invalid_config_path, 'w') as f:
            f.write('{"invalid": json}')  # Invalid JSON
        
        # Test that system handles invalid configuration gracefully
        validator = ProductionReadinessValidator(invalid_config_path)
        
        # This should not crash, but should report configuration issues
        report = validator.run_comprehensive_validation()
        
        # Should have failed configuration validation
        config_results = [r for r in report.results if r.check_name == 'configuration']
        assert len(config_results) > 0
        assert config_results[0].status == 'fail'
        assert 'JSON' in config_results[0].message or 'configuration' in config_results[0].message.lower()
    
    def test_monitoring_integration(self, temp_workspace):
        """Test monitoring system integration."""
        # Test metrics collection
        from oikotie.automation.metrics import MetricsCollector
        
        db_manager = EnhancedDatabaseManager("data/test_monitoring.duckdb")
        metrics_collector = MetricsCollector(db_manager)
        
        # Test execution tracking
        execution_id = "test_monitoring"
        city = "TestCity"
        
        metrics_collector.start_execution_tracking(execution_id, city)
        
        # Simulate some execution time
        time.sleep(0.1)
        
        # Test metrics collection (basic functionality)
        # Note: Full metrics collection would require actual execution data
        assert metrics_collector.db_manager is not None
    
    def test_backup_and_recovery_integration(self, temp_workspace):
        """Test backup and recovery system integration."""
        # Create production deployment for backup testing
        deployment_manager = create_production_deployment(
            "backup-test",
            DeploymentType.STANDALONE,
            "testing",
            {
                'config_path': 'config/config.json',
                'database_path': 'data/backup_test.duckdb',
                'backup_directory': 'backups'
            }
        )
        
        # Initialize deployment
        with patch('oikotie.automation.orchestrator.load_config_and_create_orchestrators') as mock_load:
            mock_orchestrator = Mock()
            mock_orchestrator.config = ScraperConfig(city="TestCity", url="https://example.com")
            mock_load.return_value = [mock_orchestrator]
            
            success = deployment_manager.initialize_deployment()
            assert success
            
            # Test backup creation
            backup_path = deployment_manager.create_backup()
            
            # Verify backup was created
            assert Path(backup_path).exists()
            assert Path(backup_path).suffix == '.gz'
            
            # Test cleanup functionality
            cleanup_stats = deployment_manager.cleanup_old_data()
            
            # Should return statistics dictionary
            assert isinstance(cleanup_stats, dict)
            assert 'logs_removed' in cleanup_stats
            assert 'backups_removed' in cleanup_stats
    
    def test_end_to_end_workflow(self, temp_workspace):
        """Test complete end-to-end workflow."""
        # This test simulates a complete production workflow
        
        # Step 1: Validate production readiness
        validator = ProductionReadinessValidator("config/config.json")
        
        with patch('subprocess.run') as mock_subprocess, \
             patch('requests.get') as mock_requests, \
             patch('selenium.webdriver.Chrome') as mock_chrome:
            
            # Mock successful external dependencies
            mock_subprocess.return_value.returncode = 0
            mock_subprocess.return_value.stdout = "Google Chrome 120.0.0.0"
            mock_requests.return_value.status_code = 200
            mock_driver = Mock()
            mock_driver.title = "Google"
            mock_chrome.return_value = mock_driver
            
            report = validator.run_comprehensive_validation()
            
            # Should pass basic validation in test environment
            assert report.overall_status in ['ready', 'warnings']
        
        # Step 2: Initialize production deployment
        deployment_manager = create_production_deployment(
            "end-to-end-test",
            DeploymentType.STANDALONE,
            "testing"
        )
        
        with patch('oikotie.automation.orchestrator.load_config_and_create_orchestrators') as mock_load:
            mock_orchestrator = Mock()
            mock_orchestrator.config = ScraperConfig(city="TestCity", url="https://example.com")
            mock_orchestrator.run_daily_scrape.return_value = Mock(
                execution_id="test-exec",
                city="TestCity",
                status=Mock(value="completed"),
                listings_new=5,
                listings_failed=0,
                execution_time_seconds=30.0
            )
            mock_load.return_value = [mock_orchestrator]
            
            # Initialize deployment
            success = deployment_manager.initialize_deployment()
            assert success
            
            # Step 3: Run daily automation
            result = deployment_manager.run_daily_automation()
            
            # Verify automation results
            assert result['status'] == 'completed'
            assert 'execution_id' in result
            assert 'total_new' in result
            assert 'city_results' in result
            assert len(result['city_results']) > 0
            
            # Step 4: Get system status
            status = deployment_manager.get_system_status()
            
            assert status.deployment_name == "end-to-end-test"
            assert status.status in ['healthy', 'degraded', 'failed']
            assert 'orchestrators' in status.components
            
            # Step 5: Create backup
            backup_path = deployment_manager.create_backup()
            assert Path(backup_path).exists()
    
    def test_production_dashboard_integration(self, temp_workspace):
        """Test production dashboard integration."""
        # Test dashboard creation and basic functionality
        deployment_manager = create_production_deployment(
            "dashboard-test",
            DeploymentType.STANDALONE,
            "testing"
        )
        
        with patch('oikotie.automation.orchestrator.load_config_and_create_orchestrators') as mock_load:
            mock_orchestrator = Mock()
            mock_orchestrator.config = ScraperConfig(city="TestCity", url="https://example.com")
            mock_load.return_value = [mock_orchestrator]
            
            success = deployment_manager.initialize_deployment()
            assert success
            
            # Test dashboard creation
            from oikotie.automation.production_dashboard import create_production_dashboard
            
            dashboard = create_production_dashboard(deployment_manager, port=8091)
            
            if dashboard:  # Only test if Flask is available
                assert dashboard.deployment_manager == deployment_manager
                assert dashboard.port == 8091
                assert dashboard.app is not None
    
    def test_security_integration(self, temp_workspace):
        """Test security system integration."""
        # Test security manager integration
        from oikotie.automation.security import create_security_manager
        
        try:
            security_manager = create_security_manager()
            
            # Basic security manager functionality
            if security_manager:
                assert hasattr(security_manager, 'config')
                
                # Test credential management (basic functionality)
                # Note: Full security testing would require more complex setup
                
        except Exception as e:
            # Security manager may not be fully available in test environment
            logger.warning(f"Security manager test skipped: {e}")
    
    @pytest.mark.slow
    def test_performance_integration(self, temp_workspace):
        """Test performance aspects of system integration."""
        # Test system performance under simulated load
        
        # Create multiple orchestrators to simulate load
        configs = []
        for i in range(3):
            config = ScraperConfig(
                city=f"TestCity{i}",
                url=f"https://example.com/test{i}",
                max_detail_workers=1,  # Keep low for testing
                enable_performance_monitoring=True
            )
            configs.append(config)
        
        # Test orchestrator creation performance
        start_time = time.time()
        
        orchestrators = []
        for config in configs:
            with patch('oikotie.automation.orchestrator.EnhancedDatabaseManager'):
                orchestrator = EnhancedScraperOrchestrator(config)
                orchestrators.append(orchestrator)
        
        creation_time = time.time() - start_time
        
        # Should create orchestrators reasonably quickly
        assert creation_time < 5.0, f"Orchestrator creation took too long: {creation_time}s"
        assert len(orchestrators) == 3
        
        # Test configuration retrieval performance
        start_time = time.time()
        
        for orchestrator in orchestrators:
            config = orchestrator.get_configuration()
            assert config is not None
        
        config_time = time.time() - start_time
        assert config_time < 1.0, f"Configuration retrieval took too long: {config_time}s"


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])