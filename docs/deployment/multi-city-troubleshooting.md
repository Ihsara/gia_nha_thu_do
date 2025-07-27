# Multi-City Deployment Troubleshooting Guide

This guide provides solutions for common issues encountered when deploying and operating the Oikotie platform with multiple cities (Helsinki and Espoo).

## Table of Contents

1. [Configuration Issues](#configuration-issues)
2. [Database Issues](#database-issues)
3. [Geospatial Integration Issues](#geospatial-integration-issues)
4. [Visualization Issues](#visualization-issues)
5. [Performance Issues](#performance-issues)
6. [Cluster Coordination Issues](#cluster-coordination-issues)
7. [Validation Issues](#validation-issues)

## Configuration Issues

### Missing City Configuration

**Symptoms:**
- Error: "City configuration not found for 'Espoo'"
- City-specific operations fail
- Dashboard generation fails for specific city

**Solution:**
```json
// Add to config/config.json
{
  "tasks": [
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
      "priority": 2
    }
  ]
}
```

### Invalid Coordinate Bounds

**Symptoms:**
- Coordinate validation errors
- Properties being incorrectly filtered out
- Geospatial matching failures

**Solution:**
```json
// Correct coordinate bounds for Espoo
"coordinate_bounds": [24.4, 60.1, 24.9, 60.4]
```

**Validation Command:**
```bash
# Validate city coordinates
uv run python -c "
from oikotie.geospatial.base import validate_city_coordinates
print('Helsinki valid:', validate_city_coordinates('Helsinki', 60.17, 24.94))
print('Espoo valid:', validate_city_coordinates('Espoo', 60.21, 24.65))
"
```

### Priority Conflicts

**Symptoms:**
- Cities processed in unexpected order
- Resource allocation imbalance
- Some cities not being processed

**Solution:**
```json
// Set appropriate priorities (lower number = higher priority)
{
  "tasks": [
    {
      "city": "Helsinki",
      "priority": 1
    },
    {
      "city": "Espoo",
      "priority": 2
    }
  ]
}
```

## Database Issues

### Missing City Column

**Symptoms:**
- Error: "Column 'city' not found"
- City-specific queries fail
- Data not properly segregated by city

**Solution:**
```bash
# Run database migration script
uv run python -m oikotie.database.migration add_city_column

# Or manually add column
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
conn.execute('ALTER TABLE listings ADD COLUMN IF NOT EXISTS city VARCHAR')
conn.close()
"
```

### City Data Mixing

**Symptoms:**
- Properties appear in wrong city
- Incorrect geospatial matching
- Visualization shows properties in wrong locations

**Solution:**
```bash
# Fix city assignments
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
conn.execute('''
UPDATE listings 
SET city = 'Helsinki' 
WHERE city IS NULL AND 
      latitude BETWEEN 60.0 AND 60.5 AND 
      longitude BETWEEN 24.5 AND 25.5
''')
conn.execute('''
UPDATE listings 
SET city = 'Espoo' 
WHERE city IS NULL AND 
      latitude BETWEEN 60.1 AND 60.4 AND 
      longitude BETWEEN 24.4 AND 24.9
''')
conn.close()
"
```

### Missing Spatial Indexes

**Symptoms:**
- Slow geospatial queries
- High CPU usage during spatial operations
- Timeout errors during visualization

**Solution:**
```bash
# Create spatial indexes
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
conn.execute('CREATE INDEX IF NOT EXISTS idx_listings_city_location ON listings(city, latitude, longitude)')
conn.close()
"
```

## Geospatial Integration Issues

### Missing Espoo Building Data

**Symptoms:**
- Error: "Espoo building data file not found"
- Building footprints missing in Espoo visualizations
- Low match rates for Espoo properties

**Solution:**
```bash
# Extract Espoo buildings
uv run python scripts/run_espoo_geospatial_integration.py --extract-buildings

# Verify file exists
ls -la data/espoo_buildings_*.geojson
```

### Coordinate System Mismatches

**Symptoms:**
- Buildings and properties don't align
- Consistent offset in visualizations
- Low match rates despite data availability

**Solution:**
```bash
# Check and fix coordinate systems
uv run python -c "
from oikotie.geospatial.espoo import fix_coordinate_system
fix_coordinate_system('data/espoo_buildings_20250719_183000.geojson')
"
```

### API Rate Limiting

**Symptoms:**
- Frequent 429 errors
- Slow geospatial data retrieval
- Incomplete building data

**Solution:**
```json
// Adjust rate limiting in config
{
  "data_governance": {
    "max_requests_per_second": 0.5,
    "bulk_download_preference": true,
    "cache_duration_hours": 48
  }
}
```

## Visualization Issues

### City Selection Not Working

**Symptoms:**
- City selector shows but doesn't change city
- Error: "City configuration not found"
- Blank or default dashboard shown

**Solution:**
```bash
# Check city selector configuration
uv run python -c "
from oikotie.visualization.dashboard.city_selector import CitySelector
selector = CitySelector()
print('Available cities:', selector.get_available_cities())
"

# Fix city selector
uv run python -c "
from oikotie.visualization.utils.config import update_city_config
update_city_config('espoo', {
    'center': [60.21, 24.65],
    'zoom': 12,
    'bounds': [[60.1, 24.4], [60.4, 24.9]]
})
"
```

### Missing Espoo Map Styling

**Symptoms:**
- Espoo map looks identical to Helsinki
- Missing Espoo-specific boundaries
- Incorrect map centering

**Solution:**
```bash
# Update Espoo map configuration
uv run python -c "
from oikotie.visualization.utils.config import update_city_config
update_city_config('espoo', {
    'center': [60.21, 24.65],
    'zoom': 12,
    'bounds': [[60.1, 24.4], [60.4, 24.9]],
    'map_style': 'espoo_style',
    'color_scheme': 'espoo_colors'
})
"
```

### Comparative Dashboard Issues

**Symptoms:**
- Error when generating comparative dashboard
- Only one city shown in comparative mode
- Unbalanced or missing data

**Solution:**
```bash
# Check comparative dashboard configuration
uv run python -c "
from oikotie.visualization.dashboard.multi_city import MultiCityDashboard
dashboard = MultiCityDashboard()
print('Comparative support:', dashboard.supports_comparative(['helsinki', 'espoo']))
"

# Generate with explicit options
uv run python -m oikotie.visualization.cli.commands dashboard --comparative "helsinki,espoo" --options "price_comparison,building_footprints" --open
```

## Performance Issues

### Slow Multi-City Processing

**Symptoms:**
- Daily automation takes much longer with multiple cities
- High memory usage
- System becomes unresponsive

**Solution:**
```json
// Optimize worker distribution
{
  "tasks": [
    {
      "city": "Helsinki",
      "max_detail_workers": 3
    },
    {
      "city": "Espoo",
      "max_detail_workers": 2
    }
  ],
  "global_settings": {
    "max_workers": 5
  }
}
```

### Memory Issues with Multiple Cities

**Symptoms:**
- Out of memory errors
- System crashes during processing
- Slow performance with multiple cities

**Solution:**
```bash
# Process cities sequentially instead of parallel
uv run python -m oikotie.automation.cli run --sequential

# Or adjust batch sizes
uv run python -c "
from oikotie.automation.multi_city_orchestrator import create_multi_city_orchestrator
orchestrator = create_multi_city_orchestrator()
orchestrator.set_batch_size('Helsinki', 30)
orchestrator.set_batch_size('Espoo', 20)
orchestrator.run_daily_automation()
"
```

### Database Performance Degradation

**Symptoms:**
- Queries become slower over time
- High disk I/O
- Timeouts during operations

**Solution:**
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

## Cluster Coordination Issues

### Redis Connection Failures

**Symptoms:**
- Error: "Could not connect to Redis"
- Cluster coordination fails
- Fallback to standalone mode

**Solution:**
```bash
# Check Redis connection
uv run python -c "
import redis
try:
    r = redis.Redis.from_url('redis://localhost:6379')
    print('Redis connection:', r.ping())
except Exception as e:
    print(f'Redis error: {e}')
"

# Start Redis if needed
docker run -d --name redis -p 6379:6379 redis:alpine
```

### Work Distribution Imbalance

**Symptoms:**
- Some nodes process more cities than others
- Uneven load distribution
- Some cities not being processed

**Solution:**
```bash
# Check work distribution
uv run python -c "
from oikotie.automation.multi_city_orchestrator import create_multi_city_orchestrator
orchestrator = create_multi_city_orchestrator(redis_url='redis://localhost:6379')
status = orchestrator.get_cluster_status()
print('Work distribution:', status.get('work_distribution', {}))
"

# Reset work distribution
uv run python -c "
import redis
r = redis.Redis.from_url('redis://localhost:6379')
r.delete('oikotie:work_distribution')
print('Work distribution reset')
"
```

### Circuit Breaker Issues

**Symptoms:**
- City processing permanently disabled
- Error: "Circuit breaker open for city X"
- Processing skips certain cities

**Solution:**
```bash
# Check circuit breaker status
uv run python -c "
from oikotie.automation.multi_city_orchestrator import create_multi_city_orchestrator
orchestrator = create_multi_city_orchestrator()
for city in ['Helsinki', 'Espoo']:
    cb = orchestrator.circuit_breakers.get(city)
    if cb:
        print(f'{city} circuit breaker: {cb.state}')
"

# Reset circuit breakers
uv run python -c "
from oikotie.automation.multi_city_orchestrator import create_multi_city_orchestrator
orchestrator = create_multi_city_orchestrator()
for city in ['Helsinki', 'Espoo']:
    cb = orchestrator.circuit_breakers.get(city)
    if cb:
        cb.reset()
        print(f'{city} circuit breaker reset')
"
```

## Validation Issues

### Progressive Validation Failures

**Symptoms:**
- Espoo validation tests fail
- Low match rates for Espoo
- Missing geospatial data

**Solution:**
```bash
# Run bug prevention tests first
uv run python run_espoo_validation.py bug-prevention

# Check for missing data
uv run python -c "
import os
import glob
print('Espoo building data:', glob.glob('data/espoo_buildings_*.geojson'))
print('Helsinki building data:', glob.glob('data/helsinki_buildings_*.geojson'))
"

# Run validation steps in order
uv run python run_espoo_validation.py step1
uv run python run_espoo_validation.py step2
uv run python run_espoo_validation.py step3
```

### Quality Gate Failures

**Symptoms:**
- Validation reports show below-threshold match rates
- Error: "Quality gate failed: match rate below X%"
- Validation process stops at specific step

**Solution:**
```bash
# Check current match rates
uv run python -c "
import json
import glob
latest_report = sorted(glob.glob('output/validation/espoo/espoo_step*_metrics_*.json'))[-1]
with open(latest_report) as f:
    metrics = json.load(f)
    print(f'Match rate: {metrics.get("match_rate", 0):.2f}%')
    print(f'Quality grade: {metrics.get("quality_grade", "F")}')
"

# Run with debug mode for more information
uv run python run_espoo_validation.py step1 --debug
```

### Coordinate Validation Failures

**Symptoms:**
- Properties filtered out due to coordinate bounds
- Error: "X properties outside city boundaries"
- Low property counts in validation reports

**Solution:**
```bash
# Check coordinate validation
uv run python -c "
from oikotie.geospatial.base import validate_city_coordinates
import duckdb

conn = duckdb.connect('data/real_estate.duckdb')
results = conn.execute('''
    SELECT city, COUNT(*) as total,
           SUM(CASE WHEN latitude BETWEEN 60.1 AND 60.4 AND longitude BETWEEN 24.4 AND 24.9 THEN 1 ELSE 0 END) as valid_espoo,
           SUM(CASE WHEN latitude BETWEEN 60.0 AND 60.5 AND longitude BETWEEN 24.5 AND 25.5 THEN 1 ELSE 0 END) as valid_helsinki
    FROM listings
    WHERE city IN ('Espoo', 'Helsinki')
    GROUP BY city
''').fetchall()

for city, total, valid_espoo, valid_helsinki in results:
    print(f'{city}: {total} total, {valid_espoo} valid for Espoo bounds, {valid_helsinki} valid for Helsinki bounds')
conn.close()
"

# Fix coordinates if needed
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
conn.execute('''
UPDATE listings 
SET city = 'Espoo' 
WHERE city = 'Helsinki' AND 
      latitude BETWEEN 60.1 AND 60.4 AND 
      longitude BETWEEN 24.4 AND 24.9
''')
print('Updated city assignments based on coordinates')
conn.close()
"
```

This troubleshooting guide covers the most common issues encountered when deploying and operating the Oikotie platform with multiple cities. For additional assistance, consult the main documentation or contact the development team.