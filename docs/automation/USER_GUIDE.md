# Oikotie Daily Scraper Automation - User Guide

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Configuration](#configuration)
4. [Deployment Options](#deployment-options)
5. [Daily Operations](#daily-operations)
6. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
7. [Advanced Features](#advanced-features)
8. [Best Practices](#best-practices)
9. [FAQ](#faq)

## Overview

The Oikotie Daily Scraper Automation system transforms manual property data collection into an intelligent, production-ready automation platform. The system provides:

- **Smart Daily Execution**: Automated scraping with intelligent deduplication
- **Flexible Deployment**: Standalone, container, or cluster deployment options
- **Comprehensive Monitoring**: Real-time health monitoring and status reporting
- **Production Ready**: Security, backup, and operational procedures

### Key Benefits

- **Efficiency**: Reduces manual work by 95% through automation
- **Intelligence**: Smart deduplication prevents unnecessary re-processing
- **Reliability**: Built-in error handling and recovery mechanisms
- **Scalability**: Supports single-node to distributed cluster deployments
- **Observability**: Comprehensive monitoring and alerting capabilities

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Chrome/Chromium browser (for web scraping)
- 4GB+ RAM (8GB+ recommended for production)
- 10GB+ available disk space

### Quick Installation

1. **Clone and setup environment**:
   ```bash
   git clone https://github.com/Ihsara/gia_nha_thu_do.git
   cd oikotie
   uv venv && .venv\Scripts\activate  # Windows
   uv sync --all-extras
   ```

2. **Verify installation**:
   ```bash
   uv run python -m oikotie.automation.cli --help
   ```

3. **Run first automation**:
   ```bash
   uv run python -m oikotie.automation.cli run --daily
   ```

### First Run Checklist

- [ ] Database directory exists (`data/`)
- [ ] Configuration file present (`config/config.json`)
- [ ] Chrome/Chromium browser available
- [ ] Network connectivity to Oikotie.fi
- [ ] Sufficient disk space for data storage

## Configuration

### Basic Configuration

Edit `config/config.json` to configure scraping tasks:

```json
{
  "tasks": [
    {
      "city": "Helsinki",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
      "max_detail_workers": 5,
      "staleness_threshold_hours": 24,
      "retry_limit": 3,
      "batch_size": 100,
      "enable_smart_deduplication": true
    },
    {
      "city": "Espoo",
      "enabled": false,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B49,6,%22Espoo%22%5D%5D&cardType=100",
      "max_detail_workers": 3
    }
  ]
}
```

### Configuration Parameters

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `city` | City name for identification | Required | String |
| `enabled` | Enable/disable task | `true` | Boolean |
| `url` | Oikotie search URL | Required | Valid URL |
| `max_detail_workers` | Concurrent workers | `5` | 1-10 |
| `staleness_threshold_hours` | Hours before re-scraping | `24` | 1-168 |
| `retry_limit` | Max retry attempts | `3` | 1-10 |
| `batch_size` | Processing batch size | `100` | 10-1000 |
| `enable_smart_deduplication` | Smart deduplication | `true` | Boolean |

### Environment Variables

Override configuration using environment variables:

```bash
# Database configuration
export DATABASE_PATH="/custom/path/database.duckdb"

# Performance tuning
export MAX_WORKERS=8
export HEADLESS_BROWSER=true

# Monitoring
export HEALTH_CHECK_PORT=8080
export ENABLE_METRICS=true

# Cluster configuration (optional)
export REDIS_URL="redis://localhost:6379"
```

## Deployment Options

### Option 1: Standalone Deployment

**Best for**: Development, testing, single-machine production

```bash
# Basic standalone execution
uv run python -m oikotie.automation.cli run --daily

# With custom configuration
uv run python -m oikotie.automation.cli run --daily --config custom_config.json

# Interactive mode for testing
uv run python -m oikotie.automation.cli run
```

**Features**:
- Simple setup and operation
- Local database storage
- No external dependencies
- Suitable for small-scale operations

### Option 2: Container Deployment

**Best for**: Production deployments, cloud environments

1. **Build container**:
   ```bash
   docker build -t oikotie-scraper .
   ```

2. **Run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

3. **Check status**:
   ```bash
   docker-compose logs -f scraper
   curl http://localhost:8080/health
   ```

**Features**:
- Isolated environment
- Easy scaling and deployment
- Health check endpoints
- Volume-mounted data persistence

### Option 3: Cluster Deployment

**Best for**: High-availability, distributed processing

1. **Setup Redis coordination**:
   ```bash
   docker run -d --name redis -p 6379:6379 redis:alpine
   ```

2. **Deploy cluster nodes**:
   ```bash
   # Node 1
   export NODE_ID=node-1
   export REDIS_URL=redis://localhost:6379
   uv run python -m oikotie.automation.cli run --cluster

   # Node 2
   export NODE_ID=node-2
   uv run python -m oikotie.automation.cli run --cluster
   ```

3. **Monitor cluster**:
   ```bash
   uv run python -m oikotie.automation.cli system_status
   ```

**Features**:
- Distributed work coordination
- Automatic failover
- Load balancing
- Horizontal scaling

## Daily Operations

### Running Daily Automation

**Command Line**:
```bash
# Run daily automation for all enabled cities
uv run python -m oikotie.automation.cli run --daily

# Run for specific city
uv run python -m oikotie.automation.cli run --daily --city Helsinki

# Run in cluster mode
uv run python -m oikotie.automation.cli run --daily --cluster
```

**Python API**:
```python
from oikotie.automation.production_deployment import create_production_deployment
from oikotie.automation.deployment import DeploymentType

# Create deployment manager
manager = create_production_deployment(
    "daily-scraper",
    DeploymentType.STANDALONE
)

# Initialize and run
if manager.initialize_deployment():
    result = manager.run_daily_automation()
    print(f"Processed {result['total_new']} new listings")
```

### Scheduling Automation

**Using Cron (Linux/macOS)**:
```bash
# Add to crontab (crontab -e)
0 6 * * * cd /path/to/oikotie && uv run python -m oikotie.automation.cli run --daily
```

**Using Task Scheduler (Windows)**:
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: Daily at 6:00 AM
4. Set action: Start program
5. Program: `uv`
6. Arguments: `run python -m oikotie.automation.cli run --daily`
7. Start in: `C:\path\to\oikotie`

**Using systemd (Linux)**:
```ini
# /etc/systemd/system/oikotie-daily.service
[Unit]
Description=Oikotie Daily Scraper
After=network.target

[Service]
Type=oneshot
User=oikotie
WorkingDirectory=/opt/oikotie
ExecStart=/opt/oikotie/.venv/bin/uv run python -m oikotie.automation.cli run --daily
Environment=PATH=/opt/oikotie/.venv/bin:/usr/bin:/bin

# /etc/systemd/system/oikotie-daily.timer
[Unit]
Description=Run Oikotie Daily Scraper
Requires=oikotie-daily.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

Enable with:
```bash
sudo systemctl enable oikotie-daily.timer
sudo systemctl start oikotie-daily.timer
```

## Monitoring and Troubleshooting

### Health Monitoring

**Health Check Endpoints**:
```bash
# Basic health check
curl http://localhost:8080/health

# Readiness check (Kubernetes)
curl http://localhost:8080/health/ready

# Liveness check (Kubernetes)
curl http://localhost:8080/health/live

# Prometheus metrics
curl http://localhost:8080/metrics
```

**System Status**:
```bash
# Get deployment status
uv run python -m oikotie.automation.cli system_status

# Check specific components
uv run python -c "
from oikotie.automation.production_deployment import create_production_deployment
manager = create_production_deployment('test')
status = manager.get_system_status()
print(f'Status: {status.status}')
print(f'Components: {status.components}')
"
```

### Production Dashboard

Start the web-based monitoring dashboard:

```bash
# Start dashboard on port 8090
uv run python -m oikotie.automation.production_dashboard --port 8090

# Access dashboard
open http://localhost:8090
```

**Dashboard Features**:
- Real-time system status
- Component health monitoring
- Recent execution history
- One-click operations (backup, cleanup)
- System metrics visualization

### Log Analysis

**Log Locations**:
- Application logs: `logs/scraper_YYYY-MM-DD.log`
- Execution logs: `logs/execution_*.log`
- Error logs: `logs/error_*.log`

**Common Log Patterns**:
```bash
# Check for errors
grep -i error logs/scraper_$(date +%Y-%m-%d).log

# Monitor real-time logs
tail -f logs/scraper_$(date +%Y-%m-%d).log

# Check execution statistics
grep "Daily scrape completed" logs/scraper_*.log
```

### Common Issues and Solutions

#### Issue: "No listings discovered"
**Symptoms**: Zero listings found for a city
**Solutions**:
1. Check URL validity in configuration
2. Verify network connectivity
3. Check if website structure changed
4. Review browser automation logs

#### Issue: "Database connection failed"
**Symptoms**: Cannot connect to DuckDB database
**Solutions**:
1. Check database file permissions
2. Verify disk space availability
3. Ensure database directory exists
4. Check for file locks

#### Issue: "High memory usage"
**Symptoms**: System running out of memory
**Solutions**:
1. Reduce `max_detail_workers` in configuration
2. Decrease `batch_size` parameter
3. Enable headless browser mode
4. Monitor system resources

#### Issue: "Cluster coordination failed"
**Symptoms**: Nodes cannot coordinate work
**Solutions**:
1. Verify Redis connectivity
2. Check network configuration
3. Ensure consistent node configuration
4. Review cluster logs

## Advanced Features

### Smart Deduplication

The system automatically identifies and skips recently processed listings:

```python
# Configure deduplication behavior
{
  "staleness_threshold_hours": 24,  # Re-process after 24 hours
  "enable_smart_deduplication": true,
  "retry_limit": 3  # Retry failed URLs up to 3 times
}
```

**Benefits**:
- Reduces processing time by 60-80%
- Minimizes server load on Oikotie.fi
- Focuses resources on new/updated listings
- Intelligent retry logic for failed URLs

### Performance Monitoring

Enable comprehensive performance tracking:

```python
{
  "enable_performance_monitoring": true,
  "enable_metrics": true
}
```

**Metrics Collected**:
- Execution time per city
- Memory usage patterns
- CPU utilization
- Network request statistics
- Database operation performance
- Error rates and patterns

### Security Features

**Credential Management**:
```bash
# Set secure credentials
export OIKOTIE_API_KEY="your-api-key"
export DATABASE_PASSWORD="secure-password"
```

**Audit Logging**:
All system operations are logged with:
- User identification
- Timestamp
- Action performed
- Result status
- Resource access

**Rate Limiting**:
Built-in rate limiting prevents:
- Excessive requests to Oikotie.fi
- Database overload
- Resource exhaustion

### Backup and Recovery

**Automated Backups**:
```bash
# Create manual backup
uv run python -c "
from oikotie.automation.production_deployment import create_production_deployment
manager = create_production_deployment('backup-test')
backup_path = manager.create_backup()
print(f'Backup created: {backup_path}')
"
```

**Backup Contents**:
- Complete DuckDB database
- Configuration files
- Recent log files (last 7 days)
- System state information

**Recovery Procedure**:
1. Stop automation system
2. Extract backup archive
3. Restore database file
4. Restore configuration
5. Restart system
6. Verify functionality

## Best Practices

### Configuration Management

1. **Version Control**: Store configuration in version control
2. **Environment Separation**: Use different configs for dev/staging/prod
3. **Validation**: Always validate configuration before deployment
4. **Documentation**: Document all configuration changes

### Operational Procedures

1. **Regular Monitoring**: Check system status daily
2. **Log Review**: Review logs weekly for patterns
3. **Performance Tuning**: Monitor and adjust worker counts
4. **Backup Schedule**: Create backups before major changes

### Security Guidelines

1. **Access Control**: Limit access to production systems
2. **Credential Rotation**: Rotate credentials regularly
3. **Network Security**: Use firewalls and VPNs
4. **Audit Trails**: Maintain comprehensive audit logs

### Performance Optimization

1. **Resource Monitoring**: Monitor CPU, memory, and disk usage
2. **Worker Tuning**: Adjust worker counts based on system capacity
3. **Database Optimization**: Regular database maintenance
4. **Network Optimization**: Monitor network usage patterns

## FAQ

### General Questions

**Q: How often should I run the daily automation?**
A: Once per day is recommended. The smart deduplication system makes multiple runs efficient, but daily execution provides the best balance of freshness and resource usage.

**Q: Can I run multiple cities simultaneously?**
A: Yes, the system processes all enabled cities in the configuration file. Each city is processed sequentially to manage resource usage.

**Q: What happens if the system crashes during execution?**
A: The system includes comprehensive error handling and recovery. Failed executions are logged, and the next run will retry failed URLs with exponential backoff.

### Technical Questions

**Q: How much disk space do I need?**
A: Plan for approximately 1GB per 10,000 listings, plus additional space for logs and backups. A typical Helsinki dataset requires 2-3GB.

**Q: Can I customize the scraping logic?**
A: Yes, the system is designed for extensibility. You can modify the orchestrator classes or create custom processors while maintaining the automation framework.

**Q: How do I scale to handle more cities?**
A: Use cluster deployment with multiple nodes. Each node can process different cities, or work can be distributed automatically across the cluster.

### Troubleshooting Questions

**Q: The system reports "No new listings" but I know there are new properties.**
A: Check the staleness threshold configuration. If set too low, the system may skip recently processed listings. Also verify the search URL is correct.

**Q: Memory usage keeps increasing during execution.**
A: This is normal for large datasets. Reduce `max_detail_workers` and `batch_size` if memory becomes an issue. Enable headless browser mode to reduce memory usage.

**Q: How do I recover from a corrupted database?**
A: Restore from the most recent backup. If no backup is available, delete the database file and run a fresh scraping operation. The system will rebuild the database from scratch.

---

## Support and Resources

- **Documentation**: [docs/automation/](../automation/)
- **API Reference**: [docs/api/](../api/)
- **Troubleshooting**: [docs/troubleshooting/](../troubleshooting/)
- **GitHub Issues**: [Project Issues](https://github.com/Ihsara/gia_nha_thu_do/issues)

For additional support, please refer to the project documentation or create an issue on GitHub.