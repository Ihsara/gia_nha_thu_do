# Configuration Examples and Best Practices

This document provides comprehensive configuration examples and best practices for the Oikotie Daily Scraper Automation system across different deployment scenarios.

## Table of Contents

1. [Configuration Overview](#configuration-overview)
2. [Environment-Specific Configurations](#environment-specific-configurations)
3. [Deployment-Specific Examples](#deployment-specific-examples)
4. [Best Practices](#best-practices)
5. [Security Configuration](#security-configuration)
6. [Performance Tuning](#performance-tuning)
7. [Monitoring Configuration](#monitoring-configuration)
8. [Troubleshooting Configuration Issues](#troubleshooting-configuration-issues)

## Configuration Overview

The Oikotie scraper uses a hierarchical configuration system that loads settings from multiple sources:

```
Priority (High to Low):
1. Command-line arguments
2. Environment variables  
3. Configuration files
4. Default values
```

### Configuration File Structure

```json
{
  "deployment": {
    "type": "standalone|container|cluster",
    "health_check_port": 8080,
    "database_path": "/path/to/database.duckdb",
    "log_level": "DEBUG|INFO|WARNING|ERROR",
    "max_workers": 3,
    "headless_browser": true,
    "enable_metrics": true,
    "graceful_shutdown_timeout": 30
  },
  "scraping": {
    "staleness_threshold_hours": 24,
    "retry_limit": 3,
    "batch_size": 50,
    "rate_limit_delay": 1.0,
    "user_agent_rotation": true,
    "request_timeout": 30
  },
  "tasks": [
    {
      "city": "Helsinki",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/...",
      "max_detail_workers": 3,
      "priority": 1
    }
  ],
  "database": {
    "connection_pool_size": 5,
    "query_timeout": 30,
    "backup_enabled": true,
    "backup_interval_hours": 24
  },
  "monitoring": {
    "metrics_enabled": true,
    "health_check_enabled": true,
    "prometheus_port": 9090,
    "log_structured": true
  },
  "alerting": {
    "email": { "enabled": false },
    "slack": { "enabled": false },
    "webhook": { "enabled": false }
  }
}
```

## Environment-Specific Configurations

### Development Environment

**File**: `config/development_config.json`

```json
{
  "deployment": {
    "type": "standalone",
    "health_check_port": 8080,
    "database_path": "./data/real_estate_dev.duckdb",
    "log_level": "DEBUG",
    "max_workers": 2,
    "headless_browser": false,
    "enable_metrics": false,
    "graceful_shutdown_timeout": 10
  },
  "scraping": {
    "staleness_threshold_hours": 1,
    "retry_limit": 2,
    "batch_size": 10,
    "rate_limit_delay": 2.0,
    "user_agent_rotation": false,
    "request_timeout": 15
  },
  "tasks": [
    {
      "city": "Helsinki",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
      "max_detail_workers": 1,
      "priority": 1,
      "test_mode": true,
      "max_listings": 20
    }
  ],
  "database": {
    "connection_pool_size": 2,
    "query_timeout": 15,
    "backup_enabled": false
  },
  "monitoring": {
    "metrics_enabled": false,
    "health_check_enabled": true,
    "log_structured": false
  },
  "alerting": {
    "email": { "enabled": false },
    "slack": { "enabled": false }
  }
}
```

### Staging Environment

**File**: `config/staging_config.json`

```json
{
  "deployment": {
    "type": "container",
    "health_check_port": 8080,
    "database_path": "/data/real_estate_staging.duckdb",
    "log_level": "INFO",
    "max_workers": 3,
    "headless_browser": true,
    "enable_metrics": true,
    "graceful_shutdown_timeout": 20
  },
  "scraping": {
    "staleness_threshold_hours": 12,
    "retry_limit": 3,
    "batch_size": 30,
    "rate_limit_delay": 1.5,
    "user_agent_rotation": true,
    "request_timeout": 25
  },
  "tasks": [
    {
      "city": "Helsinki",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
      "max_detail_workers": 2,
      "priority": 1
    },
    {
      "city": "Espoo",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,49,%22Espoo%22%5D%5D&cardType=100",
      "max_detail_workers": 2,
      "priority": 2
    }
  ],
  "database": {
    "connection_pool_size": 3,
    "query_timeout": 25,
    "backup_enabled": true,
    "backup_interval_hours": 12
  },
  "monitoring": {
    "metrics_enabled": true,
    "health_check_enabled": true,
    "prometheus_port": 9090,
    "log_structured": true
  },
  "alerting": {
    "email": {
      "enabled": true,
      "smtp_server": "smtp.staging.example.com",
      "smtp_port": 587,
      "username": "${SMTP_USERNAME}",
      "password": "${SMTP_PASSWORD}",
      "recipients": ["staging-alerts@example.com"]
    },
    "slack": {
      "enabled": true,
      "webhook_url": "${SLACK_WEBHOOK_URL}",
      "channel": "#staging-alerts"
    }
  }
}
```

### Production Environment

**File**: `config/production_config.json`

```json
{
  "deployment": {
    "type": "cluster",
    "health_check_port": 8080,
    "database_path": "/shared/real_estate.duckdb",
    "log_level": "INFO",
    "max_workers": 5,
    "headless_browser": true,
    "enable_metrics": true,
    "graceful_shutdown_timeout": 30
  },
  "scraping": {
    "staleness_threshold_hours": 24,
    "retry_limit": 5,
    "batch_size": 50,
    "rate_limit_delay": 1.0,
    "user_agent_rotation": true,
    "request_timeout": 30,
    "circuit_breaker_enabled": true,
    "circuit_breaker_threshold": 10
  },
  "tasks": [
    {
      "city": "Helsinki",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
      "max_detail_workers": 3,
      "priority": 1
    },
    {
      "city": "Espoo",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,49,%22Espoo%22%5D%5D&cardType=100",
      "max_detail_workers": 3,
      "priority": 2
    },
    {
      "city": "Vantaa",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,92,%22Vantaa%22%5D%5D&cardType=100",
      "max_detail_workers": 2,
      "priority": 3
    },
    {
      "city": "Tampere",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,837,%22Tampere%22%5D%5D&cardType=100",
      "max_detail_workers": 2,
      "priority": 4
    }
  ],
  "database": {
    "connection_pool_size": 10,
    "query_timeout": 30,
    "backup_enabled": true,
    "backup_interval_hours": 6,
    "backup_retention_days": 30,
    "vacuum_enabled": true,
    "vacuum_interval_hours": 168
  },
  "monitoring": {
    "metrics_enabled": true,
    "health_check_enabled": true,
    "prometheus_port": 9090,
    "log_structured": true,
    "performance_monitoring": true,
    "resource_monitoring": true
  },
  "alerting": {
    "email": {
      "enabled": true,
      "smtp_server": "smtp.production.example.com",
      "smtp_port": 587,
      "username": "${SMTP_USERNAME}",
      "password": "${SMTP_PASSWORD}",
      "recipients": [
        "ops-team@example.com",
        "data-team@example.com"
      ],
      "alert_levels": ["ERROR", "CRITICAL"]
    },
    "slack": {
      "enabled": true,
      "webhook_url": "${SLACK_WEBHOOK_URL}",
      "channel": "#production-alerts",
      "alert_levels": ["WARNING", "ERROR", "CRITICAL"]
    },
    "webhook": {
      "enabled": true,
      "url": "${WEBHOOK_URL}",
      "headers": {
        "Authorization": "Bearer ${WEBHOOK_TOKEN}"
      },
      "alert_levels": ["CRITICAL"]
    }
  },
  "security": {
    "encryption_enabled": true,
    "audit_logging": true,
    "rate_limiting": {
      "enabled": true,
      "requests_per_minute": 60
    }
  }
}
```

## Deployment-Specific Examples

### Docker Compose Configuration

**File**: `docker-compose.production.yml`

```yaml
version: '3.8'

services:
  scraper:
    build:
      context: .
      target: production
    container_name: oikotie-scraper-prod
    restart: unless-stopped
    environment:
      # Core configuration
      - ENVIRONMENT=production
      - DEPLOYMENT_TYPE=container
      - CONFIG_FILE=/app/config/production_config.json
      
      # Database
      - DATABASE_PATH=/data/real_estate.duckdb
      
      # Performance
      - MAX_WORKERS=5
      - HEADLESS_BROWSER=true
      - LOG_LEVEL=INFO
      
      # Security
      - SMTP_USERNAME=${SMTP_USERNAME}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
      
      # Monitoring
      - PROMETHEUS_ENABLED=true
      - HEALTH_CHECK_ENABLED=true
      
    volumes:
      # Data persistence
      - scraper_data:/data
      - scraper_logs:/logs
      - scraper_output:/output
      - scraper_backups:/backups
      
      # Configuration
      - ./config/production_config.json:/app/config/production_config.json:ro
      - ./config/cities.json:/app/config/cities.json:ro
      
    ports:
      - "8080:8080"   # Health checks
      - "9090:9090"   # Metrics
      
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
      
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
        
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'

  # Redis for caching (optional)
  redis:
    image: redis:7-alpine
    container_name: scraper-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Monitoring stack
  prometheus:
    image: prom/prometheus:latest
    container_name: scraper-prometheus
    restart: unless-stopped
    ports:
      - "9091:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'

volumes:
  scraper_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /opt/oikotie-scraper/data
  scraper_logs:
    driver: local
  scraper_output:
    driver: local
  scraper_backups:
    driver: local
  redis_data:
    driver: local
  prometheus_data:
    driver: local

networks:
  default:
    name: oikotie-scraper-network
    driver: bridge
```

### Kubernetes ConfigMap

**File**: `k8s/configmap-production.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: oikotie-scraper-config
  namespace: oikotie-scraper
  labels:
    app: oikotie-scraper
    environment: production
data:
  config.json: |
    {
      "deployment": {
        "type": "cluster",
        "health_check_port": 8080,
        "database_path": "/shared/real_estate.duckdb",
        "log_level": "INFO",
        "max_workers": 3,
        "headless_browser": true,
        "enable_metrics": true,
        "graceful_shutdown_timeout": 30
      },
      "scraping": {
        "staleness_threshold_hours": 24,
        "retry_limit": 5,
        "batch_size": 50,
        "rate_limit_delay": 1.0,
        "user_agent_rotation": true,
        "request_timeout": 30
      },
      "tasks": [
        {
          "city": "Helsinki",
          "enabled": true,
          "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
          "max_detail_workers": 3,
          "priority": 1
        }
      ],
      "database": {
        "connection_pool_size": 5,
        "query_timeout": 30,
        "backup_enabled": true,
        "backup_interval_hours": 6
      },
      "monitoring": {
        "metrics_enabled": true,
        "health_check_enabled": true,
        "prometheus_port": 9090,
        "log_structured": true
      }
    }
  
  cities.json: |
    [
      {
        "name": "Helsinki",
        "code": "helsinki",
        "location_id": 64,
        "sub_location_id": 6,
        "enabled": true,
        "priority": 1,
        "max_workers": 3
      },
      {
        "name": "Espoo",
        "code": "espoo", 
        "location_id": 64,
        "sub_location_id": 49,
        "enabled": true,
        "priority": 2,
        "max_workers": 2
      }
    ]
    
  logging.yaml: |
    version: 1
    disable_existing_loggers: false
    formatters:
      standard:
        format: '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
      json:
        format: '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
    handlers:
      console:
        class: logging.StreamHandler
        level: INFO
        formatter: json
        stream: ext://sys.stdout
      file:
        class: logging.handlers.RotatingFileHandler
        level: INFO
        formatter: json
        filename: /logs/scraper.log
        maxBytes: 10485760
        backupCount: 5
    loggers:
      oikotie:
        level: INFO
        handlers: [console, file]
        propagate: false
    root:
      level: INFO
      handlers: [console]
```

## Best Practices

### 1. Configuration Management

#### Environment Variable Naming
```bash
# Use consistent prefixes
OIKOTIE_DATABASE_PATH=/data/real_estate.duckdb
OIKOTIE_LOG_LEVEL=INFO
OIKOTIE_MAX_WORKERS=5

# Avoid hardcoding secrets
OIKOTIE_SMTP_PASSWORD=${SMTP_PASSWORD}
OIKOTIE_SLACK_WEBHOOK=${SLACK_WEBHOOK_URL}
```

#### Configuration Validation
```json
{
  "validation": {
    "required_fields": [
      "deployment.database_path",
      "deployment.max_workers",
      "tasks"
    ],
    "field_types": {
      "deployment.max_workers": "integer",
      "deployment.headless_browser": "boolean",
      "scraping.staleness_threshold_hours": "number"
    },
    "constraints": {
      "deployment.max_workers": {"min": 1, "max": 20},
      "scraping.batch_size": {"min": 1, "max": 1000}
    }
  }
}
```

### 2. Resource Management

#### Memory Configuration
```json
{
  "deployment": {
    "max_workers": 3,
    "memory_limit_mb": 1024,
    "gc_threshold": 0.8
  },
  "scraping": {
    "batch_size": 50,
    "concurrent_requests": 5
  }
}
```

#### Database Optimization
```json
{
  "database": {
    "connection_pool_size": 5,
    "query_timeout": 30,
    "pragma_settings": {
      "journal_mode": "WAL",
      "synchronous": "NORMAL",
      "cache_size": -64000,
      "temp_store": "MEMORY"
    }
  }
}
```

### 3. Error Handling Configuration

```json
{
  "error_handling": {
    "retry_strategy": {
      "max_retries": 3,
      "backoff_factor": 2,
      "max_backoff": 300
    },
    "circuit_breaker": {
      "enabled": true,
      "failure_threshold": 10,
      "recovery_timeout": 60
    },
    "fallback": {
      "json_storage_enabled": true,
      "json_storage_path": "/fallback/data"
    }
  }
}
```

### 4. Logging Best Practices

```json
{
  "logging": {
    "level": "INFO",
    "structured": true,
    "format": "json",
    "fields": {
      "timestamp": true,
      "level": true,
      "logger": true,
      "message": true,
      "execution_id": true,
      "city": true,
      "correlation_id": true
    },
    "rotation": {
      "max_size": "100MB",
      "max_files": 10,
      "compress": true
    }
  }
}
```

## Security Configuration

### 1. Secrets Management

#### Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: oikotie-scraper-secrets
  namespace: oikotie-scraper
type: Opaque
data:
  smtp-username: <base64-encoded-username>
  smtp-password: <base64-encoded-password>
  slack-webhook-url: <base64-encoded-webhook-url>
  database-encryption-key: <base64-encoded-key>
```

#### Environment Variables for Secrets
```bash
# Use external secret management
export SMTP_USERNAME=$(vault kv get -field=username secret/smtp)
export SMTP_PASSWORD=$(vault kv get -field=password secret/smtp)
export SLACK_WEBHOOK_URL=$(vault kv get -field=webhook secret/slack)
```

### 2. Network Security

```json
{
  "security": {
    "network": {
      "allowed_domains": [
        "asunnot.oikotie.fi",
        "api.openstreetmap.org"
      ],
      "proxy": {
        "enabled": false,
        "http_proxy": "",
        "https_proxy": ""
      },
      "ssl_verification": true,
      "timeout": 30
    },
    "rate_limiting": {
      "enabled": true,
      "requests_per_minute": 60,
      "burst_limit": 10
    }
  }
}
```

### 3. Data Protection

```json
{
  "data_protection": {
    "encryption": {
      "enabled": true,
      "algorithm": "AES-256-GCM",
      "key_rotation_days": 90
    },
    "anonymization": {
      "enabled": true,
      "fields": ["personal_data", "contact_info"]
    },
    "retention": {
      "data_retention_days": 365,
      "log_retention_days": 90,
      "backup_retention_days": 30
    }
  }
}
```

## Performance Tuning

### 1. Scraping Performance

```json
{
  "performance": {
    "scraping": {
      "concurrent_cities": 2,
      "concurrent_listings_per_city": 5,
      "page_load_timeout": 30,
      "element_wait_timeout": 10,
      "browser_pool_size": 3,
      "browser_reuse_count": 100
    },
    "database": {
      "batch_insert_size": 100,
      "connection_pool_size": 10,
      "query_cache_size": 1000,
      "vacuum_threshold": 0.3
    }
  }
}
```

### 2. Resource Limits

```yaml
# Kubernetes resource configuration
resources:
  requests:
    memory: "512Mi"
    cpu: "200m"
    ephemeral-storage: "1Gi"
  limits:
    memory: "2Gi"
    cpu: "1000m"
    ephemeral-storage: "5Gi"
```

### 3. Caching Configuration

```json
{
  "caching": {
    "enabled": true,
    "redis": {
      "host": "redis",
      "port": 6379,
      "db": 0,
      "ttl": 3600
    },
    "cache_strategies": {
      "listing_urls": {"ttl": 1800},
      "geocoding_results": {"ttl": 86400},
      "building_footprints": {"ttl": 604800}
    }
  }
}
```

## Monitoring Configuration

### 1. Metrics Configuration

```json
{
  "monitoring": {
    "metrics": {
      "enabled": true,
      "port": 9090,
      "path": "/metrics",
      "collection_interval": 30,
      "custom_metrics": [
        "scraper_listings_processed_total",
        "scraper_execution_duration_seconds",
        "scraper_error_rate",
        "scraper_data_quality_score"
      ]
    },
    "health_checks": {
      "enabled": true,
      "port": 8080,
      "endpoints": {
        "liveness": "/health/live",
        "readiness": "/health/ready",
        "startup": "/health/startup"
      }
    }
  }
}
```

### 2. Alerting Rules

```json
{
  "alerting": {
    "rules": [
      {
        "name": "high_error_rate",
        "condition": "error_rate > 0.05",
        "duration": "5m",
        "severity": "warning",
        "channels": ["email", "slack"]
      },
      {
        "name": "scraper_down",
        "condition": "up == 0",
        "duration": "1m",
        "severity": "critical",
        "channels": ["email", "slack", "webhook"]
      },
      {
        "name": "low_data_quality",
        "condition": "data_quality_score < 0.9",
        "duration": "10m",
        "severity": "warning",
        "channels": ["email"]
      }
    ]
  }
}
```

## Troubleshooting Configuration Issues

### 1. Configuration Validation

```bash
# Validate configuration file
uv run python -m oikotie.automation.cli validate-config --config config/production_config.json

# Check environment variables
uv run python -m oikotie.automation.cli show-config --environment production

# Test database connection
uv run python -m oikotie.automation.cli test-database --config config/production_config.json
```

### 2. Common Configuration Problems

#### Problem: High Memory Usage
```json
{
  "solution": {
    "deployment": {
      "max_workers": 2,  // Reduce from 5
      "memory_limit_mb": 512
    },
    "scraping": {
      "batch_size": 25,  // Reduce from 50
      "concurrent_requests": 3  // Reduce from 5
    }
  }
}
```

#### Problem: Slow Scraping Performance
```json
{
  "solution": {
    "scraping": {
      "rate_limit_delay": 0.5,  // Reduce from 1.0
      "request_timeout": 20,    // Reduce from 30
      "page_load_timeout": 20   // Reduce from 30
    },
    "performance": {
      "browser_pool_size": 5,   // Increase from 3
      "concurrent_listings_per_city": 8  // Increase from 5
    }
  }
}
```

#### Problem: Database Lock Issues
```json
{
  "solution": {
    "database": {
      "connection_pool_size": 3,  // Reduce from 10
      "query_timeout": 60,        // Increase from 30
      "pragma_settings": {
        "journal_mode": "WAL",
        "busy_timeout": 30000
      }
    }
  }
}
```

### 3. Configuration Testing

```bash
# Test configuration in dry-run mode
uv run python -m oikotie.automation.cli run --dry-run --config config/test_config.json

# Validate against schema
uv run python -m oikotie.automation.cli validate-schema --config config/production_config.json

# Performance test with configuration
uv run python -m oikotie.automation.cli benchmark --config config/performance_test.json
```

This comprehensive configuration guide provides the foundation for deploying and operating the Oikotie Daily Scraper Automation system across different environments and deployment scenarios.