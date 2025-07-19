# Configuration Management System

The Daily Scraper Automation system includes a comprehensive, flexible configuration management system that supports hierarchical loading, validation, environment-specific overrides, and runtime hot-reload capabilities.

## Features

### 1. Hierarchical Configuration Loading

The system loads configuration from multiple sources with proper precedence (highest to lowest):

1. **Command-line arguments** - Highest precedence
2. **Environment variables** - Override config files
3. **Environment-specific config files** - Override base config
4. **Base configuration files** - Default configuration
5. **Default configuration** - Embedded defaults

### 2. Configuration Validation

- Comprehensive validation of all configuration sections
- Clear error messages with specific field validation
- Type checking and range validation
- Required field validation

### 3. Environment-Specific Overrides

- Automatic environment detection (development, production, container, cluster)
- Environment-specific configuration files
- Built-in environment presets with sensible defaults

### 4. Runtime Configuration Watching

- File system watching for configuration changes
- Hot-reload capabilities without restart
- Configurable reload callbacks
- Debounced file change detection

### 5. Configuration Templates

- Pre-built templates for different deployment scenarios
- Template generation with documentation
- Configuration export functionality

## Configuration Structure

### Main Configuration Sections

```json
{
  "tasks": [
    {
      "city": "Helsinki",
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
      "enabled": true,
      "max_detail_workers": 5,
      "staleness_hours": 24,
      "listing_limit": null,
      "retry_count": 3,
      "retry_backoff_factor": 2.0
    }
  ],
  "database": {
    "path": "data/real_estate.duckdb",
    "connection_timeout": 30,
    "max_connections": 10,
    "backup_enabled": true,
    "backup_interval_hours": 24
  },
  "cluster": {
    "enabled": false,
    "redis_host": "localhost",
    "redis_port": 6379,
    "redis_db": 0,
    "redis_password": null,
    "node_id": null,
    "heartbeat_interval": 30,
    "work_lock_ttl": 300
  },
  "monitoring": {
    "metrics_enabled": true,
    "prometheus_port": 8000,
    "health_check_port": 8001,
    "log_level": "INFO",
    "log_file_retention": 30,
    "alert_channels": []
  },
  "scheduling": {
    "enabled": true,
    "cron_expression": "0 6 * * *",
    "timezone": "Europe/Helsinki",
    "max_execution_time": 7200,
    "concurrent_tasks": 1
  },
  "deployment_type": "standalone",
  "environment": "development",
  "debug": false
}
```

## Usage

### Programmatic Usage

```python
from oikotie.automation.config import ConfigurationManager

# Create configuration manager
config_manager = ConfigurationManager("config")

# Load configuration
config = config_manager.load_config(
    config_files=["config.json"],
    environment="production",
    cli_args=args
)

# Start watching for changes
def on_config_change(old_config, new_config):
    print(f"Configuration reloaded: {new_config.environment}")

config_manager.start_watching(on_config_change)
```

### CLI Usage

The system includes a comprehensive CLI tool for configuration management:

```bash
# Validate configuration
uv run python -m oikotie.automation.config_cli --environment production validate

# Generate templates
uv run python -m oikotie.automation.config_cli generate-template basic --output config/my_config.json
uv run python -m oikotie.automation.config_cli generate-template cluster --output config/cluster_config.json

# Test configuration loading
uv run python -m oikotie.automation.config_cli test-config --environments development production

# Export configuration
uv run python -m oikotie.automation.config_cli --environment production export --output prod_config.json

# Watch configuration files
uv run python -m oikotie.automation.config_cli --environment development watch --validate-on-reload
```

## Environment Variables

The system supports environment variable overrides with the `SCRAPER_` prefix:

```bash
# Basic settings
export SCRAPER_DEBUG=true
export SCRAPER_LOG_LEVEL=DEBUG
export SCRAPER_DB_PATH=/custom/path.duckdb

# Cluster settings
export SCRAPER_CLUSTER_ENABLED=true
export SCRAPER_REDIS_HOST=redis-server
export SCRAPER_REDIS_PORT=6379

# Monitoring settings
export SCRAPER_METRICS_PORT=9000
export SCRAPER_HEALTH_PORT=9001

# Scheduling settings
export SCRAPER_CRON="0 8 * * *"
export SCRAPER_TIMEZONE="Europe/Helsinki"
```

## Configuration Files

### Base Configuration Files

The system looks for configuration files in this order:

1. `config.json` - Main configuration file
2. `scraper_config.json` - Alternative main config
3. `automation_config.json` - Automation-specific config

### Environment-Specific Files

Environment-specific configurations override base settings:

1. `{environment}_config.json` (e.g., `production_config.json`)
2. `config_{environment}.json` (e.g., `config_production.json`)
3. `{environment}/config.json` (e.g., `production/config.json`)

### Example Environment Configurations

#### Development Configuration (`development_config.json`)

```json
{
  "debug": true,
  "monitoring": {
    "log_level": "DEBUG"
  },
  "tasks": [
    {
      "city": "Helsinki",
      "listing_limit": 20,
      "max_detail_workers": 2,
      "staleness_hours": 1
    }
  ],
  "scheduling": {
    "enabled": false
  }
}
```

#### Production Configuration (`production_config.json`)

```json
{
  "debug": false,
  "monitoring": {
    "log_level": "INFO",
    "alert_channels": ["email", "slack"],
    "metrics_enabled": true
  },
  "tasks": [
    {
      "city": "Helsinki",
      "max_detail_workers": 8,
      "staleness_hours": 24
    },
    {
      "city": "Espoo",
      "enabled": true,
      "max_detail_workers": 6
    }
  ],
  "scheduling": {
    "enabled": true,
    "cron_expression": "0 6 * * *"
  }
}
```

## Validation Rules

### Task Configuration

- `city`: Required, non-empty string
- `url`: Required, non-empty string
- `enabled`: Optional boolean (default: true)
- `max_detail_workers`: Positive integer (1-20 recommended)
- `staleness_hours`: Positive number
- `listing_limit`: Positive integer or null
- `retry_count`: Non-negative integer
- `retry_backoff_factor`: Number >= 1

### Database Configuration

- `path`: Required, non-empty string
- `connection_timeout`: Positive integer
- `max_connections`: Positive integer
- `backup_enabled`: Boolean
- `backup_interval_hours`: Positive integer

### Cluster Configuration

- `enabled`: Boolean
- `redis_host`: Required when cluster enabled
- `redis_port`: Valid port number (1-65535)
- `redis_db`: Non-negative integer
- `heartbeat_interval`: Positive integer
- `work_lock_ttl`: Positive integer

### Monitoring Configuration

- `log_level`: One of DEBUG, INFO, WARNING, ERROR, CRITICAL
- `prometheus_port`: Valid port number (1024-65535)
- `health_check_port`: Valid port number (1024-65535)
- `log_file_retention`: Positive integer
- `alert_channels`: List of valid channels (email, slack, webhook, sms)

### Scheduling Configuration

- `cron_expression`: Valid cron expression (5 or 6 fields)
- `timezone`: Valid timezone string
- `max_execution_time`: Positive integer
- `concurrent_tasks`: Positive integer

## Templates

### Basic Template

Suitable for standalone deployments:

```bash
uv run python -m oikotie.automation.config_cli generate-template basic
```

### Cluster Template

Suitable for distributed deployments:

```bash
uv run python -m oikotie.automation.config_cli generate-template cluster
```

## Error Handling

The configuration system provides detailed error messages for validation failures:

```
Configuration validation failed:
  - Task 0: city is required and cannot be empty
  - Task 0: url is required and cannot be empty
  - Task 0: max_detail_workers must be >= 1
  - Database path is required
  - Redis host is required when cluster is enabled
```

## Hot Reload

The system supports hot-reload of configuration files:

```python
# Start watching
config_manager.start_watching(callback_function)

# Configuration will be automatically reloaded when files change
# Callback function will be called with old and new configurations

# Stop watching
config_manager.stop_watching()
```

## Integration with Automation System

The configuration system is fully integrated with the daily scraper automation:

```python
from oikotie.automation.config import ConfigurationManager
from oikotie.automation.orchestrator import EnhancedScraperOrchestrator

# Load configuration
config_manager = ConfigurationManager()
config = config_manager.load_config(environment="production")

# Create orchestrator with configuration
orchestrator = EnhancedScraperOrchestrator(config)

# Run scraping with loaded configuration
result = await orchestrator.run_daily_scrape()
```

## Best Practices

### 1. Environment Separation

- Use separate configuration files for each environment
- Never commit sensitive data to version control
- Use environment variables for secrets

### 2. Configuration Validation

- Always validate configuration before deployment
- Use the CLI validation tool in CI/CD pipelines
- Test configuration loading in different environments

### 3. Hot Reload

- Use hot reload in development for faster iteration
- Be cautious with hot reload in production
- Always validate reloaded configuration

### 4. Template Usage

- Start with templates for new deployments
- Customize templates for specific needs
- Keep templates updated with new features

### 5. Monitoring

- Monitor configuration changes in production
- Log configuration reload events
- Alert on configuration validation failures

## Troubleshooting

### Common Issues

1. **Configuration not found**
   - Check file paths and permissions
   - Verify configuration directory exists
   - Use absolute paths if needed

2. **Validation failures**
   - Check required fields are present
   - Verify data types and ranges
   - Use CLI validation tool for details

3. **Environment variables not working**
   - Check variable names have `SCRAPER_` prefix
   - Verify environment variable values
   - Check for typos in variable names

4. **Hot reload not working**
   - Check file system permissions
   - Verify file watcher is started
   - Check for file system limitations

### Debug Mode

Enable debug mode for detailed logging:

```bash
export SCRAPER_DEBUG=true
export SCRAPER_LOG_LEVEL=DEBUG
```

Or use CLI:

```bash
uv run python -m oikotie.automation.config_cli --log-level DEBUG validate
```