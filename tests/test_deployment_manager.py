"""
Test suite for the deployment manager and environment detection.

This module tests the flexible deployment manager's ability to detect environments,
configure for different deployment types, and provide health check endpoints.
"""

import os
import sys
import json
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from oikotie.automation.deployment import (
    DeploymentManager,
    DeploymentType,
    EnvironmentType,
    DeploymentConfig,
    HealthStatus,
    create_deployment_manager
)


class TestDeploymentManager:
    """Test cases for DeploymentManager."""
    
    def setup_method(self):
        """Setup test environment."""
        self.manager = DeploymentManager()
        
        # Clear environment variables that might affect tests
        self.original_env = {}
        env_vars_to_clear = [
            'CONTAINER', 'DOCKER_CONTAINER', 'KUBERNETES_SERVICE_HOST',
            'REDIS_URL', 'REDIS_HOST', 'ENVIRONMENT', 'NODE_ID',
            'HEALTH_CHECK_PORT', 'DATABASE_PATH', 'LOG_LEVEL'
        ]
        
        for var in env_vars_to_clear:
            if var in os.environ:
                self.original_env[var] = os.environ[var]
                del os.environ[var]
    
    def teardown_method(self):
        """Cleanup test environment."""
        # Restore original environment variables
        for var, value in self.original_env.items():
            os.environ[var] = value
    
    def test_detect_standalone_environment(self):
        """Test detection of standalone deployment environment."""
        with patch.object(self.manager, '_is_container_environment', return_value=False):
            deployment_type = self.manager.detect_environment()
            assert deployment_type == DeploymentType.STANDALONE
    
    def test_detect_container_environment(self):
        """Test detection of container deployment environment."""
        with patch.object(self.manager, '_is_container_environment', return_value=True), \
             patch.object(self.manager, '_has_cluster_services', return_value=False):
            deployment_type = self.manager.detect_environment()
            assert deployment_type == DeploymentType.CONTAINER
    
    def test_detect_cluster_environment(self):
        """Test detection of cluster deployment environment."""
        with patch.object(self.manager, '_is_container_environment', return_value=True), \
             patch.object(self.manager, '_has_cluster_services', return_value=True):
            deployment_type = self.manager.detect_environment()
            assert deployment_type == DeploymentType.CLUSTER
    
    def test_container_detection_docker_env(self):
        """Test container detection with Docker environment file."""
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = True
            assert self.manager._is_container_environment() is True
    
    def test_container_detection_env_vars(self):
        """Test container detection with environment variables."""
        os.environ['CONTAINER'] = 'true'
        assert self.manager._is_container_environment() is True
        
        del os.environ['CONTAINER']
        os.environ['DOCKER_CONTAINER'] = 'true'
        assert self.manager._is_container_environment() is True
        
        del os.environ['DOCKER_CONTAINER']
        os.environ['KUBERNETES_SERVICE_HOST'] = 'kubernetes.default.svc'
        assert self.manager._is_container_environment() is True
    
    def test_cluster_services_detection_redis(self):
        """Test cluster services detection with Redis."""
        os.environ['REDIS_URL'] = 'redis://localhost:6379'
        with patch.object(self.manager, '_can_connect_redis', return_value=True):
            assert self.manager._has_cluster_services() is True
    
    def test_cluster_services_detection_kubernetes(self):
        """Test cluster services detection with Kubernetes."""
        os.environ['KUBERNETES_SERVICE_HOST'] = 'kubernetes.default.svc'
        assert self.manager._has_cluster_services() is True
    
    def test_environment_type_detection(self):
        """Test environment type detection from various sources."""
        # Test production
        os.environ['ENVIRONMENT'] = 'production'
        assert self.manager._detect_environment_type() == EnvironmentType.PRODUCTION
        
        # Test staging
        os.environ['ENVIRONMENT'] = 'staging'
        assert self.manager._detect_environment_type() == EnvironmentType.STAGING
        
        # Test testing
        os.environ['ENVIRONMENT'] = 'testing'
        assert self.manager._detect_environment_type() == EnvironmentType.TESTING
        
        # Test development
        os.environ['ENVIRONMENT'] = 'development'
        assert self.manager._detect_environment_type() == EnvironmentType.DEVELOPMENT
        
        # Test debug fallback
        del os.environ['ENVIRONMENT']
        os.environ['DEBUG'] = 'true'
        assert self.manager._detect_environment_type() == EnvironmentType.DEVELOPMENT
    
    def test_node_id_generation(self):
        """Test node ID generation from various sources."""
        # Test from environment variable
        os.environ['NODE_ID'] = 'test-node-123'
        node_id = self.manager._generate_node_id()
        assert node_id == 'test-node-123'
        
        # Test hostname fallback
        del os.environ['NODE_ID']
        with patch('socket.gethostname', return_value='test-hostname'):
            node_id = self.manager._generate_node_id()
            assert node_id == 'test-hostname'
        
        # Test MAC address fallback
        with patch('socket.gethostname', side_effect=Exception()), \
             patch('uuid.getnode', return_value=123456789012):
            node_id = self.manager._generate_node_id()
            assert node_id.startswith('node-') and len(node_id) > 5
    
    def test_configure_for_environment_standalone(self):
        """Test configuration for standalone environment."""
        with patch.object(self.manager, 'detect_environment', return_value=DeploymentType.STANDALONE):
            config = self.manager.configure_for_environment()
            
            assert config.deployment_type == DeploymentType.STANDALONE
            assert config.health_check_enabled is False
            assert config.cluster_coordination_enabled is False
    
    def test_configure_for_environment_container(self):
        """Test configuration for container environment."""
        with patch.object(self.manager, 'detect_environment', return_value=DeploymentType.CONTAINER):
            config = self.manager.configure_for_environment()
            
            assert config.deployment_type == DeploymentType.CONTAINER
            assert config.health_check_enabled is True
            assert config.database_path == "/data/real_estate.duckdb"
    
    def test_configure_for_environment_cluster(self):
        """Test configuration for cluster environment."""
        with patch.object(self.manager, 'detect_environment', return_value=DeploymentType.CLUSTER):
            config = self.manager.configure_for_environment()
            
            assert config.deployment_type == DeploymentType.CLUSTER
            assert config.health_check_enabled is True
            assert config.cluster_coordination_enabled is True
            assert config.database_path == "/shared/real_estate.duckdb"
    
    def test_environment_overrides(self):
        """Test environment-specific configuration overrides."""
        config = DeploymentConfig(
            deployment_type=DeploymentType.STANDALONE,
            environment_type=EnvironmentType.DEVELOPMENT,
            node_id="test-node"
        )
        
        self.manager._apply_environment_overrides(config)
        
        assert config.log_level == "DEBUG"
        assert config.headless_browser is False
        assert config.graceful_shutdown_timeout == 10
    
    def test_env_var_overrides(self):
        """Test environment variable configuration overrides."""
        os.environ['HEALTH_CHECK_PORT'] = '9090'
        os.environ['DATABASE_PATH'] = '/custom/path/db.duckdb'
        os.environ['LOG_LEVEL'] = 'ERROR'
        os.environ['MAX_WORKERS'] = '10'
        os.environ['HEADLESS_BROWSER'] = 'false'
        
        config = DeploymentConfig(
            deployment_type=DeploymentType.STANDALONE,
            environment_type=EnvironmentType.PRODUCTION,
            node_id="test-node"
        )
        
        self.manager._apply_env_var_overrides(config)
        
        assert config.health_check_port == 9090
        assert config.database_path == '/custom/path/db.duckdb'
        assert config.log_level == 'ERROR'
        assert config.max_workers == 10
        assert config.headless_browser is False
    
    def test_config_file_loading(self):
        """Test configuration loading from file."""
        config_data = {
            "deployment": {
                "health_check_port": 8888,
                "max_workers": 8,
                "log_level": "WARNING"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            manager = DeploymentManager(config_path)
            config = DeploymentConfig(
                deployment_type=DeploymentType.STANDALONE,
                environment_type=EnvironmentType.PRODUCTION,
                node_id="test-node"
            )
            
            manager._load_config_file_overrides(config)
            
            assert config.health_check_port == 8888
            assert config.max_workers == 8
            assert config.log_level == "WARNING"
        
        finally:
            os.unlink(config_path)
    
    @patch('oikotie.automation.deployment.FLASK_AVAILABLE', True)
    def test_health_check_setup(self):
        """Test health check endpoint setup."""
        config = DeploymentConfig(
            deployment_type=DeploymentType.CONTAINER,
            environment_type=EnvironmentType.PRODUCTION,
            node_id="test-node",
            health_check_enabled=True
        )
        
        self.manager.deployment_config = config
        
        with patch('oikotie.automation.deployment.Flask') as mock_flask:
            mock_app = Mock()
            mock_flask.return_value = mock_app
            
            app = self.manager.setup_health_checks()
            
            assert app is not None
            assert self.manager.health_app == mock_app
    
    def test_health_status_generation(self):
        """Test health status generation."""
        config = DeploymentConfig(
            deployment_type=DeploymentType.STANDALONE,
            environment_type=EnvironmentType.PRODUCTION,
            node_id="test-node"
        )
        
        self.manager.deployment_config = config
        
        with patch.object(self.manager, '_check_database_connection', return_value=True), \
             patch('oikotie.automation.deployment.PSUTIL_AVAILABLE', True):
            
            # Mock psutil functions directly in the module
            with patch('oikotie.automation.deployment.psutil') as mock_psutil:
                mock_memory = Mock()
                mock_memory.used = 512 * 1024 * 1024  # 512MB
                mock_psutil.virtual_memory.return_value = mock_memory
                mock_psutil.cpu_percent.return_value = 25.0
                
                status = self.manager._get_health_status()
                
                assert status.status == "healthy"
                assert status.node_id == "test-node"
                assert status.database_connected is True
                assert status.memory_usage_mb == 512.0
                assert status.cpu_usage_percent == 25.0
    
    def test_health_status_unhealthy_database(self):
        """Test health status when database is disconnected."""
        config = DeploymentConfig(
            deployment_type=DeploymentType.STANDALONE,
            environment_type=EnvironmentType.PRODUCTION,
            node_id="test-node"
        )
        
        self.manager.deployment_config = config
        
        with patch.object(self.manager, '_check_database_connection', return_value=False):
            status = self.manager._get_health_status()
            
            assert status.status == "unhealthy"
            assert status.database_connected is False
    
    def test_database_connection_check(self):
        """Test database connectivity check."""
        config = DeploymentConfig(
            deployment_type=DeploymentType.STANDALONE,
            environment_type=EnvironmentType.PRODUCTION,
            node_id="test-node",
            database_path="test.db"
        )
        
        self.manager.deployment_config = config
        
        with patch('duckdb.connect') as mock_connect:
            mock_con = Mock()
            mock_connect.return_value.__enter__.return_value = mock_con
            mock_con.execute.return_value.fetchone.return_value = (1,)
            
            result = self.manager._check_database_connection()
            assert result is True
            
            mock_connect.assert_called_once_with("test.db", read_only=True)
    
    def test_graceful_shutdown_setup(self):
        """Test graceful shutdown handler setup."""
        with patch('signal.signal') as mock_signal:
            self.manager.setup_graceful_shutdown()
            
            # Verify signal handlers were registered
            assert mock_signal.call_count >= 2  # SIGTERM and SIGINT at minimum
    
    def test_shutdown_handler_registration(self):
        """Test shutdown handler registration and execution."""
        handler_called = False
        
        def test_handler():
            nonlocal handler_called
            handler_called = True
        
        self.manager.register_shutdown_handler(test_handler)
        assert len(self.manager.shutdown_handlers) == 1
        
        # Test handler execution during shutdown
        self.manager.initiate_shutdown()
        assert handler_called is True
    
    def test_prometheus_metrics_generation(self):
        """Test Prometheus metrics generation."""
        config = DeploymentConfig(
            deployment_type=DeploymentType.CLUSTER,
            environment_type=EnvironmentType.PRODUCTION,
            node_id="test-node",
            cluster_coordination_enabled=True
        )
        
        self.manager.deployment_config = config
        
        with patch.object(self.manager, '_get_health_status') as mock_health:
            mock_health.return_value = HealthStatus(
                status="healthy",
                timestamp=self.manager.start_time,
                node_id="test-node",
                deployment_type="cluster",
                uptime_seconds=3600.0,
                memory_usage_mb=512.0,
                cpu_usage_percent=25.0,
                database_connected=True,
                redis_connected=True
            )
            
            metrics = self.manager._get_prometheus_metrics()
            
            assert "scraper_uptime_seconds 3600.0" in metrics
            assert "scraper_memory_usage_mb 512.0" in metrics
            assert "scraper_cpu_usage_percent 25.0" in metrics
            assert "scraper_database_connected 1" in metrics
            assert "scraper_redis_connected 1" in metrics
    
    def test_create_deployment_manager_function(self):
        """Test the create_deployment_manager factory function."""
        with patch('oikotie.automation.deployment.DeploymentManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager
            
            mock_config = Mock()
            mock_config.health_check_enabled = True
            mock_manager.configure_for_environment.return_value = mock_config
            
            result = create_deployment_manager()
            
            assert result == mock_manager
            mock_manager.configure_for_environment.assert_called_once()
            mock_manager.setup_health_checks.assert_called_once()
            mock_manager.start_health_server.assert_called_once()
            mock_manager.setup_graceful_shutdown.assert_called_once()


class TestDeploymentIntegration:
    """Integration tests for deployment manager."""
    
    def test_full_standalone_deployment(self):
        """Test complete standalone deployment configuration."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=False):
            manager = create_deployment_manager()
            config = manager.get_configuration()
            
            assert config is not None
            assert config.deployment_type == DeploymentType.STANDALONE
            assert config.environment_type == EnvironmentType.DEVELOPMENT
            assert config.health_check_enabled is False
            assert config.cluster_coordination_enabled is False
    
    def test_full_container_deployment(self):
        """Test complete container deployment configuration."""
        env_vars = {
            'CONTAINER': 'true',
            'ENVIRONMENT': 'production',
            'HEALTH_CHECK_PORT': '8080',
            'DATABASE_PATH': '/data/real_estate.duckdb'
        }
        
        with patch.dict(os.environ, env_vars, clear=False), \
             patch('pathlib.Path.exists', return_value=False):
            
            manager = create_deployment_manager()
            config = manager.get_configuration()
            
            assert config is not None
            assert config.deployment_type == DeploymentType.CONTAINER
            assert config.environment_type == EnvironmentType.PRODUCTION
            assert config.health_check_enabled is True
            assert config.health_check_port == 8080
            assert config.database_path == '/data/real_estate.duckdb'
    
    def test_full_cluster_deployment(self):
        """Test complete cluster deployment configuration."""
        env_vars = {
            'CONTAINER': 'true',
            'REDIS_URL': 'redis://redis:6379',
            'ENVIRONMENT': 'production',
            'NODE_ID': 'cluster-node-1'
        }
        
        with patch.dict(os.environ, env_vars, clear=False), \
             patch('pathlib.Path.exists', return_value=False), \
             patch('oikotie.automation.deployment.REDIS_AVAILABLE', True):
            
            with patch('redis.from_url') as mock_redis:
                mock_client = Mock()
                mock_redis.return_value = mock_client
                mock_client.ping.return_value = True
                
                manager = create_deployment_manager()
                config = manager.get_configuration()
                
                assert config is not None
                assert config.deployment_type == DeploymentType.CLUSTER
                assert config.environment_type == EnvironmentType.PRODUCTION
                assert config.health_check_enabled is True
                assert config.cluster_coordination_enabled is True
                assert config.redis_url == 'redis://redis:6379'
                assert config.node_id == 'cluster-node-1'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])