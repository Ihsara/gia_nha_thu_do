"""
Test suite for the flexible configuration management system.

This module tests all aspects of the configuration system including:
- Hierarchical configuration loading
- Environment variable overrides
- CLI argument processing
- Configuration validation
- Runtime configuration watching
- Template generation
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import argparse

from oikotie.automation.config import (
    ConfigurationManager,
    ScraperConfig,
    ScrapingTaskConfig,
    DatabaseConfig,
    ClusterConfig,
    MonitoringConfig,
    SchedulingConfig,
    DeploymentType,
    ConfigValidationError,
    create_cli_parser
)


class TestConfigurationManager:
    """Test the ConfigurationManager class"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir(exist_ok=True)
        self.config_manager = ConfigurationManager(str(self.config_dir))
    
    def teardown_method(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_default_configuration(self):
        """Test loading default configuration"""
        config = self.config_manager._get_default_config()
        
        assert isinstance(config, ScraperConfig)
        assert len(config.tasks) == 1
        assert config.tasks[0].city == "Helsinki"
        assert config.database.path == "data/real_estate.duckdb"
        assert config.monitoring.log_level == "INFO"
        assert config.scheduling.cron_expression == "0 6 * * *"
    
    def test_load_config_file(self):
        """Test loading configuration from JSON file"""
        config_data = {
            "tasks": [
                {
                    "city": "TestCity",
                    "url": "https://example.com",
                    "enabled": True,
                    "max_detail_workers": 3
                }
            ],
            "database": {
                "path": "test.db"
            }
        }
        
        config_file = self.config_dir / "test_config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        loaded_config = self.config_manager._load_config_file(config_file)
        assert loaded_config["tasks"][0]["city"] == "TestCity"
        assert loaded_config["database"]["path"] == "test.db"
    
    def test_environment_detection(self):
        """Test environment detection logic"""
        # Test default environment
        env = self.config_manager._detect_environment()
        assert env == "development"
        
        # Test container environment
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            env = self.config_manager._detect_environment()
            assert env == "container"
        
        # Test environment variable override
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            env = self.config_manager._detect_environment()
            assert env == "production"
    
    def test_environment_variables_loading(self):
        """Test loading configuration from environment variables"""
        env_vars = {
            'SCRAPER_DEBUG': 'true',
            'SCRAPER_LOG_LEVEL': 'DEBUG',
            'SCRAPER_DB_PATH': '/custom/path.db',
            'SCRAPER_REDIS_HOST': 'custom-redis',
            'SCRAPER_REDIS_PORT': '6380',
            'SCRAPER_CLUSTER_ENABLED': 'true'
        }
        
        with patch.dict(os.environ, env_vars):
            env_overrides = self.config_manager._load_environment_variables()
        
        assert env_overrides['debug'] is True
        assert env_overrides['monitoring']['log_level'] == 'DEBUG'
        assert env_overrides['database']['path'] == '/custom/path.db'
        assert env_overrides['cluster']['redis_host'] == 'custom-redis'
        assert env_overrides['cluster']['redis_port'] == 6380
        assert env_overrides['cluster']['enabled'] is True
    
    def test_cli_argument_overrides(self):
        """Test CLI argument overrides"""
        parser = create_cli_parser()
        args = parser.parse_args([
            '--debug',
            '--log-level', 'ERROR',
            '--db-path', '/cli/path.db',
            '--cluster-mode',
            '--redis-host', 'cli-redis'
        ])
        
        config = self.config_manager._get_default_config()
        updated_config = self.config_manager._apply_cli_overrides(config, args)
        
        assert updated_config.debug is True
        assert updated_config.monitoring.log_level == 'ERROR'
        assert updated_config.database.path == '/cli/path.db'
        assert updated_config.cluster.enabled is True
        assert updated_config.cluster.redis_host == 'cli-redis'
    
    def test_configuration_merging(self):
        """Test deep merging of configurations"""
        base_config = self.config_manager._get_default_config()
        
        override_config = {
            "database": {
                "connection_timeout": 60
            },
            "monitoring": {
                "log_level": "ERROR",
                "prometheus_port": 9000
            },
            "new_field": "test_value"
        }
        
        merged_config = self.config_manager._merge_configs(base_config, override_config)
        
        # Check that existing values are preserved
        assert merged_config.database.path == "data/real_estate.duckdb"
        # Check that overrides are applied
        assert merged_config.database.connection_timeout == 60
        assert merged_config.monitoring.log_level == "ERROR"
        assert merged_config.monitoring.prometheus_port == 9000
        # Check that health_check_port is preserved
        assert merged_config.monitoring.health_check_port == 8001
    
    def test_configuration_validation_success(self):
        """Test successful configuration validation"""
        config = self.config_manager._get_default_config()
        # Should not raise any exception
        self.config_manager._validate_config(config)
    
    def test_configuration_validation_failures(self):
        """Test configuration validation failures"""
        # Test empty tasks
        config = ScraperConfig(tasks=[])
        with pytest.raises(ConfigValidationError, match="No scraping tasks configured"):
            self.config_manager._validate_config(config)
        
        # Test invalid task
        invalid_task = ScrapingTaskConfig(city="", url="", max_detail_workers=0)
        config = ScraperConfig(tasks=[invalid_task])
        with pytest.raises(ConfigValidationError):
            self.config_manager._validate_config(config)
        
        # Test invalid cluster config
        config = self.config_manager._get_default_config()
        config.cluster.enabled = True
        config.cluster.redis_host = ""
        with pytest.raises(ConfigValidationError, match="Redis host is required"):
            self.config_manager._validate_config(config)
    
    def test_hierarchical_config_loading(self):
        """Test complete hierarchical configuration loading"""
        # Create base config file
        base_config = {
            "tasks": [
                {
                    "city": "BaseCity",
                    "url": "https://base.com",
                    "enabled": True,
                    "max_detail_workers": 2
                }
            ],
            "database": {
                "path": "base.db"
            }
        }
        
        base_file = self.config_dir / "config.json"
        with open(base_file, 'w') as f:
            json.dump(base_config, f)
        
        # Create environment-specific config
        env_config = {
            "tasks": [
                {
                    "city": "BaseCity",
                    "max_detail_workers": 5
                }
            ],
            "database": {
                "connection_timeout": 45
            }
        }
        
        env_file = self.config_dir / "development_config.json"
        with open(env_file, 'w') as f:
            json.dump(env_config, f)
        
        # Set environment variables
        env_vars = {
            'SCRAPER_LOG_LEVEL': 'DEBUG'
        }
        
        # Create CLI args
        parser = create_cli_parser()
        cli_args = parser.parse_args(['--debug'])
        
        with patch.dict(os.environ, env_vars):
            config = self.config_manager.load_config(
                environment="development",
                cli_args=cli_args
            )
        
        # Verify hierarchical loading
        assert config.tasks[0].city == "BaseCity"  # From base config
        assert config.tasks[0].max_detail_workers == 5  # From env config
        assert config.database.path == "base.db"  # From base config
        assert config.database.connection_timeout == 45  # From env config
        assert config.monitoring.log_level == "DEBUG"  # From env var
        assert config.debug is True  # From CLI args
        
        # Verify load sources are tracked
        assert "file:" in str(config.loaded_from)
        assert "env_file:development" in config.loaded_from
        assert "env_vars" in config.loaded_from
        assert "cli_args" in config.loaded_from
    
    def test_template_generation(self):
        """Test configuration template generation"""
        # Test basic template
        basic_template = self.config_manager.generate_template("basic")
        basic_data = json.loads(basic_template)
        
        assert "tasks" in basic_data
        assert "database" in basic_data
        assert "monitoring" in basic_data
        assert "scheduling" in basic_data
        assert basic_data["tasks"][0]["city"] == "Helsinki"
        
        # Test cluster template
        cluster_template = self.config_manager.generate_template("cluster")
        cluster_data = json.loads(cluster_template)
        
        assert "cluster" in cluster_data
        assert cluster_data["cluster"]["enabled"] is True
        assert cluster_data["cluster"]["redis_host"] == "redis-service"
    
    def test_config_export(self):
        """Test configuration export functionality"""
        config = self.config_manager.load_config()
        
        # Test JSON export
        exported_json = self.config_manager.export_config("json")
        exported_data = json.loads(exported_json)
        
        assert "tasks" in exported_data
        assert "database" in exported_data
        assert exported_data["environment"] == config.environment
        
        # Test export without defaults
        exported_clean = self.config_manager.export_config("json", include_defaults=False)
        clean_data = json.loads(exported_clean)
        
        assert "loaded_from" not in clean_data
        assert "last_modified" not in clean_data
    
    def test_nested_value_setting(self):
        """Test setting nested configuration values"""
        config_dict = {}
        
        self.config_manager._set_nested_value(config_dict, "database.path", "/test/path")
        self.config_manager._set_nested_value(config_dict, "cluster.redis.host", "test-host")
        self.config_manager._set_nested_value(config_dict, "simple_value", "test")
        
        assert config_dict["database"]["path"] == "/test/path"
        assert config_dict["cluster"]["redis"]["host"] == "test-host"
        assert config_dict["simple_value"] == "test"
    
    def test_config_watching_setup(self):
        """Test configuration file watching setup"""
        # Mock the Observer to avoid actual file watching in tests
        with patch('oikotie.automation.config.Observer') as mock_observer:
            mock_observer_instance = MagicMock()
            mock_observer.return_value = mock_observer_instance
            
            # Start watching
            callback = MagicMock()
            self.config_manager.start_watching(callback)
            
            assert self.config_manager.watch_enabled is True
            assert callback in self.config_manager.reload_callbacks
            mock_observer_instance.schedule.assert_called_once()
            mock_observer_instance.start.assert_called_once()
            
            # Stop watching
            self.config_manager.stop_watching()
            mock_observer_instance.stop.assert_called_once()
            mock_observer_instance.join.assert_called_once()
            assert self.config_manager.watch_enabled is False


class TestCLIParser:
    """Test the CLI argument parser"""
    
    def test_basic_cli_parsing(self):
        """Test basic CLI argument parsing"""
        parser = create_cli_parser()
        
        args = parser.parse_args([
            '--config', 'test1.json', 'test2.json',
            '--environment', 'production',
            '--debug',
            '--log-level', 'DEBUG',
            '--cluster-mode',
            '--redis-host', 'test-redis',
            '--redis-port', '6380'
        ])
        
        assert args.config == ['test1.json', 'test2.json']
        assert args.environment == 'production'
        assert args.debug is True
        assert args.log_level == 'DEBUG'
        assert args.cluster_mode is True
        assert args.redis_host == 'test-redis'
        assert args.redis_port == 6380
    
    def test_utility_options(self):
        """Test utility CLI options"""
        parser = create_cli_parser()
        
        # Test validation only
        args = parser.parse_args(['--validate-only'])
        assert args.validate_only is True
        
        # Test export config
        args = parser.parse_args(['--export-config'])
        assert args.export_config is True
        
        # Test template generation
        args = parser.parse_args(['--generate-template', 'cluster'])
        assert args.generate_template == 'cluster'


class TestConfigurationIntegration:
    """Integration tests for the complete configuration system"""
    
    def setup_method(self):
        """Set up integration test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir(exist_ok=True)
    
    def teardown_method(self):
        """Clean up integration test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_complete_configuration_workflow(self):
        """Test complete configuration loading and usage workflow"""
        # Create configuration files
        base_config = {
            "tasks": [
                {
                    "city": "Helsinki",
                    "url": "https://example.com/helsinki",
                    "enabled": True,
                    "max_detail_workers": 3
                }
            ],
            "database": {
                "path": "production.db"
            }
        }
        
        with open(self.config_dir / "config.json", 'w') as f:
            json.dump(base_config, f)
        
        # Create environment-specific config
        prod_config = {
            "monitoring": {
                "log_level": "INFO",
                "alert_channels": ["email", "slack"]
            },
            "scheduling": {
                "enabled": True,
                "cron_expression": "0 8 * * *"
            }
        }
        
        with open(self.config_dir / "production_config.json", 'w') as f:
            json.dump(prod_config, f)
        
        # Set up configuration manager
        config_manager = ConfigurationManager(str(self.config_dir))
        
        # Set environment variables
        env_vars = {
            'SCRAPER_CLUSTER_ENABLED': 'true',
            'SCRAPER_REDIS_HOST': 'prod-redis'
        }
        
        # Create CLI arguments
        parser = create_cli_parser()
        cli_args = parser.parse_args([
            '--environment', 'production',
            '--log-level', 'WARNING'
        ])
        
        # Load complete configuration
        with patch.dict(os.environ, env_vars):
            config = config_manager.load_config(
                environment='production',
                cli_args=cli_args
            )
        
        # Verify complete configuration
        assert config.environment == "production"
        assert len(config.tasks) == 1
        assert config.tasks[0].city == "Helsinki"
        assert config.tasks[0].max_detail_workers == 3
        assert config.database.path == "production.db"
        assert config.monitoring.log_level == "WARNING"  # CLI override
        assert "email" in config.monitoring.alert_channels
        assert config.scheduling.cron_expression == "0 8 * * *"
        assert config.cluster.enabled is True  # Env var
        assert config.cluster.redis_host == "prod-redis"  # Env var
        
        # Verify load sources
        expected_sources = ["default", "file:", "env_file:production", "env_vars", "cli_args"]
        for source in expected_sources:
            assert any(source in loaded_source for loaded_source in config.loaded_from)
        
        # Test configuration export
        exported = config_manager.export_config()
        exported_data = json.loads(exported)
        assert exported_data["environment"] == "production"
        
        # Test configuration validation
        config_manager._validate_config(config)  # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])