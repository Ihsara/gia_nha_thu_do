# Multi-City Deployment Best Practices

This guide provides best practices and recommendations for deploying and operating the Oikotie platform with multiple cities (Helsinki, Espoo, and others).

## Table of Contents

1. [Configuration Best Practices](#configuration-best-practices)
2. [Resource Allocation](#resource-allocation)
3. [Database Optimization](#database-optimization)
4. [Monitoring and Alerting](#monitoring-and-alerting)
5. [Deployment Strategies](#deployment-strategies)
6. [Testing and Validation](#testing-and-validation)
7. [Troubleshooting](#troubleshooting)

## Configuration Best Practices

### City Configuration Structure

Each city should be configured with the following parameters:

```json
{
  "tasks": [
    {
      "city": "Helsinki",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
      "max_detail_workers": 5,
      "rate_limit_seconds": 1.0,
      "coordinate_bounds": [24.5, 60.0, 25.5, 60.5],
      "geospatial_sources": [
        "helsinki_open_data",
        "osm_buildings",
        "national_geodata"
      ],
      "priority": 1,
      "data_governance": {
        "max_requests_per_second": 1,
        "bulk_download_preference": true,
        "cache_duration_hours": 24
      }
    },
    {
      "city": "Espoo",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B49,6,%22Espoo%22%5D%5D&cardType=100",
      "max_detail_workers": 5,
      "rate_limit_seconds": 1.0,
      "coordinate_bounds": [24.4, 60.1, 24.9, 60.4],
      "geospatial_sources": [
        "espoo_open_data",
        "osm_buildings",
        "national_geodata"
      ],
      "priority": 2,
      "data_governance": {
        "max_requests_per_second": 1,
        "bulk_download_preference": true,
        "cache_duration_hours": 24
      }
    }
  ]
}
```

### Critical Configuration Parameters

| Parameter | Description | Recommendation |
|-----------|-------------|---------------|
| `enabled` | Whether city is enabled for processing | Use to temporarily disable cities without removing configuration |
| `coordinate_bounds` | [min_lon, min_lat, max_lon, max_lat] | Critical for proper city boundary validation |
| `priority` | Execution priority (lower number = higher priority) | Use to prioritize cities based on importance |
| `max_detail_workers` | Number of parallel workers for detail scraping | Adjust based on available resources |
| `geospatial_sources` | List of geospatial data sources | Include city-specific and common sources |

### Configuration Validation

Always validate your multi-city configuration before deployment:

```bash
# Validate configuration
uv run python -m oikotie.automation.cli validate-config --config config/config.json

# Test city-specific configuration
uv run python -c "
from oikotie.visualization.utils.config import get_city_config
print(get_city_config('espoo'))
"
```

## Resource Allocation

### Worker Distribution

Allocate workers based on city size and priority:

```json
{
  "tasks": [
    {
      "city": "Helsinki",
      "max_detail_workers": 3,
      "priority": 1
    },
    {
      "city": "Espoo",
      "max_detail_workers": 2,
      "priority": 2
    }
  ],
  "global_settings": {
    "max_workers": 5
  }
}
```

### Memory Management

For multi-city deployments, increase memory allocation:

```yaml
# Docker Compose
services:
  scraper:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'

# Kubernetes
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

### Processing Strategies

Choose the appropriate processing strategy based on your resources:

1. **Sequential Processing**: Process cities one after another (lower memory usage)
   ```bash
   uv run python -m oikotie.automation.cli run --sequential
   ```

2. **Parallel Processing**: Process cities simultaneously (faster, higher memory usage)
   ```bash
   uv run python -m oikotie.automation.cli run --parallel
   ```

3. **Distributed Processing**: Distribute cities across cluster nodes (highest performance)
   ```bash
   uv run python -m oikotie.automation.cli run --cluster
   ```

## Database Optimization

### City-Specific Indexes

Create indexes optimized for multi-city queries:

```sql
-- Create city-specific indexes
CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_city_scraped ON listings(city, scraped_at);
CREATE INDEX IF NOT EXISTS idx_listings_city_location ON listings(city, latitude, longitude);
```

### Database Maintenance

Regular maintenance is critical for multi-city deployments:

```bash
# Optimize database
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
print('Running VACUUM...')
conn.execute('VACUUM')
print('Running ANALYZE...')
conn.execute('ANALYZE')
conn.close()
"
```

### Partitioning Strategy

For large deployments, consider partitioning data by city:

```python
# Example partitioning strategy
def get_database_path(city):
    """Get city-specific database path"""
    return f"data/{city.lower()}_real_estate.duckdb"

# Usage
city = "Espoo"
db_path = get_database_path(city)
```

## Monitoring and Alerting

### City-Specific Metrics

Monitor performance and health metrics per city:

```
# City-specific metrics
scraper_listings_processed_total{city="helsinki"}
scraper_listings_processed_total{city="espoo"}
scraper_execution_duration_seconds{city="helsinki"}
scraper_execution_duration_seconds{city="espoo"}
scraper_geocoding_success_rate{city="helsinki"}
scraper_geocoding_success_rate{city="espoo"}
```

### Multi-City Dashboard

Create a comprehensive monitoring dashboard:

```bash
# Generate monitoring dashboard
uv run python -m oikotie.automation.cli monitoring dashboard --multi-city
```

### Alert Configuration

Configure alerts for city-specific issues:

```yaml
# Prometheus alert rules
groups:
- name: multi-city-alerts
  rules:
  - alert: CityScraperFailure
    expr: scraper_execution_success{city="espoo"} == 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Scraper failure for {{ $labels.city }}"
      description: "The scraper for {{ $labels.city }} has failed"
  
  - alert: LowGeocodeSuccessRate
    expr: scraper_geocoding_success_rate{city="espoo"} < 0.9
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Low geocoding success rate for {{ $labels.city }}"
      description: "Geocoding success rate for {{ $labels.city }} is {{ $value }}"
```

## Deployment Strategies

### Standalone Deployment

For development and testing:

```bash
# Run with multiple cities
uv run python -m oikotie.automation.cli run --daily
```

### Container Deployment

For production single-node deployment:

```yaml
# docker-compose.yml
services:
  scraper:
    image: oikotie-scraper:latest
    environment:
      - DEPLOYMENT_TYPE=container
      - DATABASE_PATH=/data/real_estate.duckdb
      - MAX_WORKERS=5
    volumes:
      - ./data:/data
      - ./config:/app/config:ro
```

### Kubernetes Deployment

For scalable multi-node deployment:

```yaml
# k8s/scraper-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oikotie-scraper
  namespace: oikotie-scraper
spec:
  replicas: 3
  selector:
    matchLabels:
      app: oikotie-scraper
  template:
    metadata:
      labels:
        app: oikotie-scraper
    spec:
      containers:
      - name: scraper
        image: oikotie-scraper:latest
        env:
        - name: DEPLOYMENT_TYPE
          value: "cluster"
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: MAX_WORKERS
          value: "3"
        volumeMounts:
        - name: config-volume
          mountPath: /app/config
        - name: data-volume
          mountPath: /data
      volumes:
      - name: config-volume
        configMap:
          name: oikotie-scraper-config
      - name: data-volume
        persistentVolumeClaim:
          claimName: oikotie-scraper-data
```

## Testing and Validation

### Progressive Validation Strategy

Follow the 3-step validation approach for each city:

1. **Step 1**: Small sample validation (10-20 listings)
   ```bash
   uv run python run_espoo_validation.py step1
   ```

2. **Step 2**: Medium scale validation (100-500 listings)
   ```bash
   uv run python run_espoo_validation.py step2
   ```

3. **Step 3**: Full scale validation
   ```bash
   uv run python run_espoo_validation.py step3
   ```

### Bug Prevention Tests

Always run bug prevention tests before expensive operations:

```bash
# Run bug prevention tests
uv run python run_espoo_validation.py bug-prevention
```

### Quality Gates

Enforce quality gates for each validation step:

| Step | Match Rate | Quality Grade |
|------|------------|---------------|
| Step 1 (10 samples) | ≥95% | A or B |
| Step 2 (100 samples) | ≥98% | A |
| Step 3 (Full scale) | ≥99.40% | A |

## Troubleshooting

For common issues and solutions, refer to the [Multi-City Troubleshooting Guide](multi-city-troubleshooting.md).

### Common Issues

1. **Missing City Configuration**
   - Check if city is properly configured in config/config.json
   - Verify city name spelling and case sensitivity

2. **Coordinate Validation Failures**
   - Verify coordinate bounds for each city
   - Check if properties are being incorrectly filtered

3. **Database Performance Issues**
   - Create proper indexes for multi-city queries
   - Run database optimization regularly

4. **Memory Issues**
   - Reduce worker count or use sequential processing
   - Increase container memory limits

### Diagnostic Commands

```bash
# Check city configuration
uv run python -c "
from oikotie.visualization.utils.config import get_city_config
print(get_city_config('espoo'))
"

# Validate city coordinates
uv run python -c "
from oikotie.geospatial.base import validate_city_coordinates
print('Helsinki valid:', validate_city_coordinates('Helsinki', 60.17, 24.94))
print('Espoo valid:', validate_city_coordinates('Espoo', 60.21, 24.65))
"

# Check database city distribution
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
results = conn.execute('SELECT city, COUNT(*) FROM listings GROUP BY city').fetchall()
for city, count in results:
    print(f'{city}: {count} listings')
conn.close()
"
```

This guide provides best practices for deploying and operating the Oikotie platform with multiple cities. For additional assistance, refer to the main documentation or contact the development team.