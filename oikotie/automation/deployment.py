"""
Flexible deployment manager and environment detection for the Oikotie automation system.

This module provides deployment type detection, environment-specific configuration adaptation,
Docker containerization support, health check endpoints, and graceful shutdown mechanisms.
"""

import os
import sys
import json
import signal
import socket
import threading
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
import asyncio
from loguru import logger

try:
    from .psutil_compat import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - system metrics disabled")

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - cluster coordination disabled")

try:
    from flask import Flask, jsonify, request
    FLASK_AVAILABLE = True
except ImportError:
    Flask = None
    FLASK_AVAILABLE = False
    logger.warning("Flask not available - health check endpoints disabled")


class DeploymentType(Enum):
    """Enumeration of deployment types."""
    STANDALONE = "standalone"
    CONTAINER = "container"
    CLUSTER = "cluster"


class EnvironmentType(Enum):
    """Enumeration of environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DeploymentConfig:
    """Configuration for deployment-specific settings."""
    deployment_type: DeploymentType
    environment_type: EnvironmentType
    node_id: str
    health_check_port: int = 8080
    health_check_enabled: bool = True
    cluster_coordination_enabled: bool = False
    redis_url: Optional[str] = None
    database_path: str = "data/real_estate.duckdb"
    log_level: str = "INFO"
    headless_browser: bool = True
    max_workers: int = 5
    enable_metrics: bool = True
    graceful_shutdown_timeout: int = 30


@dataclass
class HealthStatus:
    """Health status information."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    node_id: str
    deployment_type: str
    uptime_seconds: float
    memory_usage_mb: float
    cpu_usage_percent: float
    database_connected: bool
    redis_connected: bool = False
    active_workers: int = 0
    last_execution: Optional[datetime] = None
    error_count: int = 0
    details: Dict[str, Any] = None


class DeploymentManager:
    """Manages deployment detection and environment-specific configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize deployment manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path
        self.deployment_config: Optional[DeploymentConfig] = None
        self.health_app: Optional[Flask] = None
        self.health_thread: Optional[threading.Thread] = None
        self.shutdown_handlers: List[Callable] = []
        self.start_time = datetime.now()
        self._shutdown_requested = False
        
        logger.info("Deployment manager initialized")
    
    def detect_environment(self) -> DeploymentType:
        """
        Detect deployment environment based on system characteristics.
        
        Returns:
            Detected deployment type
        """
        # Check for container environment
        if self._is_container_environment():
            # Check for cluster coordination services
            if self._has_cluster_services():
                logger.info("Detected cluster deployment environment")
                return DeploymentType.CLUSTER
            else:
                logger.info("Detected container deployment environment")
                return DeploymentType.CONTAINER
        else:
            logger.info("Detected standalone deployment environment")
            return DeploymentType.STANDALONE
    
    def _is_container_environment(self) -> bool:
        """Check if running in a container environment."""
        # Check for Docker container indicators
        container_indicators = [
            # Docker-specific files
            Path("/.dockerenv").exists(),
            # Container environment variables
            os.getenv("CONTAINER") is not None,
            os.getenv("DOCKER_CONTAINER") is not None,
            # Kubernetes environment variables
            os.getenv("KUBERNETES_SERVICE_HOST") is not None,
            # Check cgroup for container
            self._check_cgroup_container()
        ]
        
        return any(container_indicators)
    
    def _check_cgroup_container(self) -> bool:
        """Check cgroup for container indicators."""
        try:
            with open("/proc/1/cgroup", "r") as f:
                content = f.read()
                return "docker" in content or "containerd" in content or "kubepods" in content
        except (FileNotFoundError, PermissionError):
            return False
    
    def _has_cluster_services(self) -> bool:
        """Check for cluster coordination services."""
        # Check for Redis (cluster coordination)
        redis_indicators = [
            os.getenv("REDIS_URL") is not None,
            os.getenv("REDIS_HOST") is not None,
            self._can_connect_redis()
        ]
        
        # Check for Kubernetes
        k8s_indicators = [
            os.getenv("KUBERNETES_SERVICE_HOST") is not None,
            Path("/var/run/secrets/kubernetes.io").exists()
        ]
        
        return any(redis_indicators) or any(k8s_indicators)
    
    def _can_connect_redis(self) -> bool:
        """Test Redis connectivity."""
        if not REDIS_AVAILABLE:
            return False
        
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            client = redis.from_url(redis_url, socket_timeout=2)
            client.ping()
            return True
        except Exception:
            return False
    
    def configure_for_environment(self, deployment_type: Optional[DeploymentType] = None) -> DeploymentConfig:
        """
        Create environment-specific configuration.
        
        Args:
            deployment_type: Override deployment type detection
            
        Returns:
            Deployment configuration
        """
        if deployment_type is None:
            deployment_type = self.detect_environment()
        
        # Detect environment type
        env_type = self._detect_environment_type()
        
        # Generate node ID
        node_id = self._generate_node_id()
        
        # Base configuration
        config = DeploymentConfig(
            deployment_type=deployment_type,
            environment_type=env_type,
            node_id=node_id
        )
        
        # Apply environment-specific overrides
        self._apply_environment_overrides(config)
        
        # Apply deployment-specific overrides
        self._apply_deployment_overrides(config)
        
        # Load configuration file overrides
        if self.config_path:
            self._load_config_file_overrides(config)
        
        # Apply environment variable overrides
        self._apply_env_var_overrides(config)
        
        self.deployment_config = config
        logger.info(f"Configuration created for {deployment_type.value} deployment in {env_type.value} environment")
        
        return config
    
    def _detect_environment_type(self) -> EnvironmentType:
        """Detect environment type from various indicators."""
        env_name = os.getenv("ENVIRONMENT", "").lower()
        
        if env_name in ["prod", "production"]:
            return EnvironmentType.PRODUCTION
        elif env_name in ["staging", "stage"]:
            return EnvironmentType.STAGING
        elif env_name in ["test", "testing"]:
            return EnvironmentType.TESTING
        elif env_name in ["dev", "development"]:
            return EnvironmentType.DEVELOPMENT
        
        # Fallback detection
        if os.getenv("DEBUG") == "true":
            return EnvironmentType.DEVELOPMENT
        elif "test" in sys.argv[0].lower():
            return EnvironmentType.TESTING
        else:
            return EnvironmentType.PRODUCTION  # Default to production for safety
    
    def _generate_node_id(self) -> str:
        """Generate unique node identifier."""
        # Try to get from environment
        node_id = os.getenv("NODE_ID")
        if node_id:
            return node_id
        
        # Try to get hostname
        try:
            import socket
            hostname = socket.gethostname()
            if hostname and hostname != "localhost":
                return hostname
        except Exception:
            pass
        
        # Generate based on system info
        try:
            import uuid
            mac = uuid.getnode()
            return f"node-{mac:012x}"
        except Exception:
            return f"node-{os.getpid()}"
    
    def _apply_environment_overrides(self, config: DeploymentConfig) -> None:
        """Apply environment-specific configuration overrides."""
        if config.environment_type == EnvironmentType.DEVELOPMENT:
            config.log_level = "DEBUG"
            config.headless_browser = False
            config.enable_metrics = True
            config.graceful_shutdown_timeout = 10
        
        elif config.environment_type == EnvironmentType.TESTING:
            config.log_level = "INFO"
            config.headless_browser = True
            config.enable_metrics = False
            config.max_workers = 2
            config.graceful_shutdown_timeout = 5
        
        elif config.environment_type == EnvironmentType.STAGING:
            config.log_level = "INFO"
            config.headless_browser = True
            config.enable_metrics = True
            config.max_workers = 3
        
        elif config.environment_type == EnvironmentType.PRODUCTION:
            config.log_level = "WARNING"
            config.headless_browser = True
            config.enable_metrics = True
            config.health_check_enabled = True
    
    def _apply_deployment_overrides(self, config: DeploymentConfig) -> None:
        """Apply deployment-specific configuration overrides."""
        if config.deployment_type == DeploymentType.STANDALONE:
            config.health_check_enabled = False
            config.cluster_coordination_enabled = False
        
        elif config.deployment_type == DeploymentType.CONTAINER:
            config.health_check_enabled = True
            config.health_check_port = int(os.getenv("HEALTH_CHECK_PORT", "8080"))
            config.database_path = "/data/real_estate.duckdb"
        
        elif config.deployment_type == DeploymentType.CLUSTER:
            config.health_check_enabled = True
            config.cluster_coordination_enabled = True
            config.redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
            config.database_path = "/shared/real_estate.duckdb"
    
    def _load_config_file_overrides(self, config: DeploymentConfig) -> None:
        """Load configuration overrides from file."""
        try:
            config_path = Path(self.config_path)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                
                deployment_config = file_config.get('deployment', {})
                
                # Apply overrides
                for key, value in deployment_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                
                logger.info(f"Loaded configuration overrides from {config_path}")
        
        except Exception as e:
            logger.warning(f"Failed to load configuration file: {e}")
    
    def _apply_env_var_overrides(self, config: DeploymentConfig) -> None:
        """Apply environment variable overrides."""
        env_mappings = {
            "HEALTH_CHECK_PORT": ("health_check_port", int),
            "DATABASE_PATH": ("database_path", str),
            "LOG_LEVEL": ("log_level", str),
            "MAX_WORKERS": ("max_workers", int),
            "HEADLESS_BROWSER": ("headless_browser", lambda x: x.lower() == "true"),
            "ENABLE_METRICS": ("enable_metrics", lambda x: x.lower() == "true"),
            "GRACEFUL_SHUTDOWN_TIMEOUT": ("graceful_shutdown_timeout", int),
            "REDIS_URL": ("redis_url", str)
        }
        
        for env_var, (attr_name, converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    converted_value = converter(value)
                    setattr(config, attr_name, converted_value)
                    logger.debug(f"Applied environment override: {attr_name} = {converted_value}")
                except Exception as e:
                    logger.warning(f"Failed to convert environment variable {env_var}: {e}")
    
    def setup_health_checks(self) -> Optional[Flask]:
        """
        Setup health check endpoints for monitoring.
        
        Returns:
            Flask app instance if health checks are enabled
        """
        if not self.deployment_config or not self.deployment_config.health_check_enabled:
            logger.info("Health checks disabled")
            return None
        
        if not FLASK_AVAILABLE:
            logger.warning("Flask not available - health checks disabled")
            return None
        
        app = Flask(__name__)
        
        @app.route('/health', methods=['GET'])
        def health_check():
            """Basic health check endpoint."""
            try:
                status = self._get_health_status()
                return jsonify(asdict(status)), 200 if status.status == "healthy" else 503
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return jsonify({"status": "unhealthy", "error": str(e)}), 503
        
        @app.route('/health/ready', methods=['GET'])
        def readiness_check():
            """Readiness check for Kubernetes."""
            try:
                # Check if system is ready to accept traffic
                if self._is_system_ready():
                    return jsonify({"status": "ready"}), 200
                else:
                    return jsonify({"status": "not_ready"}), 503
            except Exception as e:
                logger.error(f"Readiness check failed: {e}")
                return jsonify({"status": "not_ready", "error": str(e)}), 503
        
        @app.route('/health/live', methods=['GET'])
        def liveness_check():
            """Liveness check for Kubernetes."""
            try:
                # Check if system is alive (not deadlocked)
                if not self._shutdown_requested:
                    return jsonify({"status": "alive"}), 200
                else:
                    return jsonify({"status": "shutting_down"}), 503
            except Exception as e:
                logger.error(f"Liveness check failed: {e}")
                return jsonify({"status": "dead", "error": str(e)}), 503
        
        @app.route('/metrics', methods=['GET'])
        def metrics_endpoint():
            """Prometheus-compatible metrics endpoint."""
            try:
                if not self.deployment_config.enable_metrics:
                    return jsonify({"error": "Metrics disabled"}), 404
                
                metrics = self._get_prometheus_metrics()
                return metrics, 200, {'Content-Type': 'text/plain'}
            except Exception as e:
                logger.error(f"Metrics endpoint failed: {e}")
                return jsonify({"error": str(e)}), 500
        
        self.health_app = app
        logger.info(f"Health check endpoints configured on port {self.deployment_config.health_check_port}")
        
        return app
    
    def start_health_server(self) -> None:
        """Start health check server in background thread."""
        if not self.health_app or not self.deployment_config:
            return
        
        def run_server():
            try:
                self.health_app.run(
                    host='0.0.0.0',
                    port=self.deployment_config.health_check_port,
                    debug=False,
                    use_reloader=False
                )
            except Exception as e:
                logger.error(f"Health server failed: {e}")
        
        self.health_thread = threading.Thread(target=run_server, daemon=True)
        self.health_thread.start()
        logger.info(f"Health server started on port {self.deployment_config.health_check_port}")
    
    def _get_health_status(self) -> HealthStatus:
        """Get current system health status."""
        try:
            # Get system metrics if psutil is available
            if PSUTIL_AVAILABLE:
                try:
                    memory_usage = psutil.virtual_memory().used / 1024 / 1024  # MB
                    cpu_usage = psutil.cpu_percent(interval=1)
                except AttributeError:
                    # Handle case where psutil is imported but doesn't have expected attributes
                    memory_usage = 0.0
                    cpu_usage = 0.0
            else:
                memory_usage = 0.0
                cpu_usage = 0.0
            
            uptime = (datetime.now() - self.start_time).total_seconds()
            
            # Check database connectivity
            database_connected = self._check_database_connection()
            
            # Check Redis connectivity (if cluster mode)
            redis_connected = False
            if self.deployment_config and self.deployment_config.cluster_coordination_enabled:
                redis_connected = self._can_connect_redis()
            
            # Determine overall status
            status = "healthy"
            if not database_connected:
                status = "unhealthy"
            elif PSUTIL_AVAILABLE and (cpu_usage > 90 or memory_usage > 1024):  # 1GB
                status = "degraded"
            
            return HealthStatus(
                status=status,
                timestamp=datetime.now(),
                node_id=self.deployment_config.node_id if self.deployment_config else "unknown",
                deployment_type=self.deployment_config.deployment_type.value if self.deployment_config else "unknown",
                uptime_seconds=uptime,
                memory_usage_mb=memory_usage,
                cpu_usage_percent=cpu_usage,
                database_connected=database_connected,
                redis_connected=redis_connected,
                details={
                    "python_version": sys.version,
                    "platform": sys.platform,
                    "pid": os.getpid(),
                    "psutil_available": PSUTIL_AVAILABLE
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return HealthStatus(
                status="unhealthy",
                timestamp=datetime.now(),
                node_id="unknown",
                deployment_type="unknown",
                uptime_seconds=0,
                memory_usage_mb=0,
                cpu_usage_percent=0,
                database_connected=False,
                details={"error": str(e)}
            )
    
    def _check_database_connection(self) -> bool:
        """Check database connectivity."""
        try:
            import duckdb
            db_path = self.deployment_config.database_path if self.deployment_config else "data/real_estate.duckdb"
            
            with duckdb.connect(db_path, read_only=True) as con:
                con.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False
    
    def _is_system_ready(self) -> bool:
        """Check if system is ready to accept traffic."""
        # Check database connection
        if not self._check_database_connection():
            return False
        
        # Check cluster coordination (if enabled)
        if (self.deployment_config and 
            self.deployment_config.cluster_coordination_enabled and 
            not self._can_connect_redis()):
            return False
        
        return True
    
    def _get_prometheus_metrics(self) -> str:
        """Generate Prometheus-compatible metrics."""
        status = self._get_health_status()
        
        metrics = []
        metrics.append(f"# HELP scraper_uptime_seconds System uptime in seconds")
        metrics.append(f"# TYPE scraper_uptime_seconds gauge")
        metrics.append(f"scraper_uptime_seconds {status.uptime_seconds}")
        
        metrics.append(f"# HELP scraper_memory_usage_mb Memory usage in megabytes")
        metrics.append(f"# TYPE scraper_memory_usage_mb gauge")
        metrics.append(f"scraper_memory_usage_mb {status.memory_usage_mb}")
        
        metrics.append(f"# HELP scraper_cpu_usage_percent CPU usage percentage")
        metrics.append(f"# TYPE scraper_cpu_usage_percent gauge")
        metrics.append(f"scraper_cpu_usage_percent {status.cpu_usage_percent}")
        
        metrics.append(f"# HELP scraper_database_connected Database connection status")
        metrics.append(f"# TYPE scraper_database_connected gauge")
        metrics.append(f"scraper_database_connected {1 if status.database_connected else 0}")
        
        if self.deployment_config and self.deployment_config.cluster_coordination_enabled:
            metrics.append(f"# HELP scraper_redis_connected Redis connection status")
            metrics.append(f"# TYPE scraper_redis_connected gauge")
            metrics.append(f"scraper_redis_connected {1 if status.redis_connected else 0}")
        
        return "\n".join(metrics)
    
    def setup_graceful_shutdown(self) -> None:
        """Setup graceful shutdown handlers."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self.initiate_shutdown()
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
        
        logger.info("Graceful shutdown handlers registered")
    
    def register_shutdown_handler(self, handler: Callable) -> None:
        """
        Register a shutdown handler function.
        
        Args:
            handler: Function to call during shutdown
        """
        self.shutdown_handlers.append(handler)
        logger.debug(f"Registered shutdown handler: {handler.__name__}")
    
    def initiate_shutdown(self) -> None:
        """Initiate graceful shutdown sequence."""
        if self._shutdown_requested:
            logger.warning("Shutdown already in progress")
            return
        
        self._shutdown_requested = True
        logger.info("Starting graceful shutdown sequence")
        
        timeout = self.deployment_config.graceful_shutdown_timeout if self.deployment_config else 30
        
        try:
            # Call all registered shutdown handlers
            for handler in self.shutdown_handlers:
                try:
                    logger.info(f"Calling shutdown handler: {handler.__name__}")
                    handler()
                except Exception as e:
                    logger.error(f"Shutdown handler {handler.__name__} failed: {e}")
            
            logger.success("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
        
        finally:
            # Force exit after timeout
            import threading
            def force_exit():
                import time
                time.sleep(timeout)
                logger.warning("Graceful shutdown timeout exceeded, forcing exit")
                os._exit(1)
            
            threading.Thread(target=force_exit, daemon=True).start()
    
    def get_configuration(self) -> Optional[DeploymentConfig]:
        """Get current deployment configuration."""
        return self.deployment_config
    
    def is_cluster_mode(self) -> bool:
        """Check if running in cluster mode."""
        return (self.deployment_config and 
                self.deployment_config.deployment_type == DeploymentType.CLUSTER)
    
    def is_container_mode(self) -> bool:
        """Check if running in container mode."""
        return (self.deployment_config and 
                self.deployment_config.deployment_type == DeploymentType.CONTAINER)
    
    def get_node_id(self) -> str:
        """Get current node identifier."""
        return self.deployment_config.node_id if self.deployment_config else "unknown"


def create_deployment_manager(config_path: Optional[str] = None) -> DeploymentManager:
    """
    Create and configure deployment manager.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Configured DeploymentManager instance
    """
    manager = DeploymentManager(config_path)
    
    # Configure for current environment
    config = manager.configure_for_environment()
    
    # Setup health checks if enabled
    if config.health_check_enabled:
        manager.setup_health_checks()
        manager.start_health_server()
    
    # Setup graceful shutdown
    manager.setup_graceful_shutdown()
    
    logger.info(f"Deployment manager created for {config.deployment_type.value} deployment")
    return manager