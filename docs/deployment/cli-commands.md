# CLI Commands for Multi-City Operations

This document provides comprehensive documentation for command-line interface (CLI) operations with multi-city support in the Oikotie platform.

## Table of Contents

1. [Dashboard Commands](#dashboard-commands)
2. [Automation Commands](#automation-commands)
3. [Validation Commands](#validation-commands)
4. [Configuration Commands](#configuration-commands)
5. [Geospatial Commands](#geospatial-commands)
6. [Database Commands](#database-commands)

## Dashboard Commands

### Generate City-Specific Dashboards

```bash
# Generate dashboard for Helsinki (default)
uv run python -m oikotie.visualization.cli.commands dashboard

# Generate enhanced dashboard for Helsinki with building footprints
uv run python -m oikotie.visualization.cli.commands dashboard --enhanced --open

# Generate dashboard for Espoo
uv run python -m oikotie.visualization.cli.commands dashboard --city espoo --open

# Generate enhanced dashboard for Espoo
uv run python -m oikotie.visualization.cli.commands dashboard --city espoo --enhanced --open
```

### Generate Comparative Dashboards

```bash
# Generate comparative dashboard for Helsinki and Espoo
uv run python -m oikotie.visualization.cli.commands dashboard --comparative "helsinki,espoo" --open

# Generate comparative dashboard with specific options
uv run python -m oikotie.visualization.cli.commands dashboard --comparative "helsinki,espoo" --options "price_comparison,building_footprints" --open
```

### City Selection Interface

```bash
# Show city selector interface
uv run python -m oikotie.visualization.cli.commands dashboard --selector --open
```

### Dashboard Command Options

| Option | Description | Example |
|--------|-------------|---------|
| `--city` | City to generate dashboard for | `--city espoo` |
| `--enhanced` | Generate enhanced dashboard with building footprints | `--enhanced` |
| `--comparative` | Generate comparative dashboard for comma-separated list of cities | `--comparative "helsinki,espoo"` |
| `--options` | Dashboard options as comma-separated list | `--options "price_comparison,building_footprints"` |
| `--selector` | Show city selector interface | `--selector` |
| `--sample-size` | Number of listings to include | `--sample-size 1000` |
| `--open` | Open dashboard in browser after generation | `--open` |
| `--output` | Specify custom output directory | `--output "./custom_output"` |

## Automation Commands

### Run Daily Automation

```bash
# Run daily automation for all enabled cities
uv run python -m oikotie.automation.cli run --daily

# Run daily automation for specific city
uv run python -m oikotie.automation.cli run --daily --city espoo

# Run daily automation with sequential city processing
uv run python -m oikotie.automation.cli run --daily --sequential

# Run daily automation with parallel city processing
uv run python -m oikotie.automation.cli run --daily --parallel
```

### Cluster Coordination

```bash
# Run with cluster coordination
uv run python -m oikotie.automation.cli run --cluster

# Check cluster status
uv run python -m oikotie.automation.cli cluster status

# Reset work distribution
uv run python -m oikotie.automation.cli cluster reset-work
```

### Production Deployment

```bash
# Deploy production system
uv run python -m oikotie.automation.cli production deploy --type standalone

# Deploy production system with multiple cities
uv run python -m oikotie.automation.cli production deploy --type cluster

# Start production monitoring dashboard
uv run python -m oikotie.automation.cli production dashboard --port 8090

# Validate production readiness
uv run python -m oikotie.automation.cli production validate
```

### Automation Command Options

| Option | Description | Example |
|--------|-------------|---------|
| `--city` | Specific city to process | `--city espoo` |
| `--sequential` | Process cities sequentially | `--sequential` |
| `--parallel` | Process cities in parallel | `--parallel` |
| `--cluster` | Enable cluster coordination | `--cluster` |
| `--redis-url` | Redis connection URL | `--redis-url "redis://localhost:6379"` |
| `--max-workers` | Maximum worker threads | `--max-workers 5` |
| `--log-level` | Logging level | `--log-level INFO` |
| `--dry-run` | Simulate execution without making changes | `--dry-run` |

## Validation Commands

### Schema Validation

```bash
# Validate database schema
uv run python -m oikotie.visualization.cli.commands validate --schema

# Validate schema for specific city
uv run python -m oikotie.visualization.cli.commands validate --city espoo --schema
```

### Data Quality Validation

```bash
# Validate data quality with sample
uv run python -m oikotie.visualization.cli.commands validate --sample

# Validate data quality for specific city
uv run python -m oikotie.visualization.cli.commands validate --city espoo --sample

# Validate coordinates against city boundaries
uv run python -m oikotie.visualization.cli.commands validate --validate-coordinates
```

### Progressive Validation

```bash
# Run progressive validation for Espoo
uv run python run_espoo_validation.py

# Run specific validation step
uv run python run_espoo_validation.py step1
uv run python run_espoo_validation.py step2
uv run python run_espoo_validation.py step3

# Run bug prevention tests
uv run python run_espoo_validation.py bug-prevention
```

### Validation Command Options

| Option | Description | Example |
|--------|-------------|---------|
| `--city` | City to validate | `--city espoo` |
| `--schema` | Validate database schema | `--schema` |
| `--sample` | Validate with sample data | `--sample` |
| `--sample-size` | Number of samples to validate | `--sample-size 100` |
| `--validate-coordinates` | Validate coordinates against city boundaries | `--validate-coordinates` |
| `--report` | Generate validation report | `--report` |
| `--output` | Specify report output directory | `--output "./validation_reports"` |

## Configuration Commands

### Configuration Validation

```bash
# Validate configuration
uv run python -m oikotie.automation.cli validate-config

# Validate configuration file
uv run python -m oikotie.automation.cli validate-config --config config/config.json
```

### Show Configuration

```bash
# Show current configuration
uv run python -m oikotie.automation.cli show-config

# Show configuration for specific environment
uv run python -m oikotie.automation.cli show-config --environment production

# Show city-specific configuration
uv run python -m oikotie.automation.cli show-config --city espoo
```

### Update Configuration

```bash
# Update city configuration
uv run python -m oikotie.automation.cli update-config --city espoo --enabled true

# Update city priority
uv run python -m oikotie.automation.cli update-config --city espoo --priority 1
```

### Configuration Command Options

| Option | Description | Example |
|--------|-------------|---------|
| `--config` | Configuration file path | `--config "config/production_config.json"` |
| `--environment` | Environment name | `--environment production` |
| `--city` | City name | `--city espoo` |
| `--enabled` | Enable/disable city | `--enabled true` |
| `--priority` | Set city priority | `--priority 1` |
| `--max-workers` | Set maximum workers | `--max-workers 3` |

## Geospatial Commands

### City-Specific Geospatial Operations

```bash
# Extract building footprints for Espoo
uv run python -m oikotie.geospatial.cli extract-buildings --city espoo

# Geocode addresses for specific city
uv run python -m oikotie.geospatial.cli geocode --city espoo --batch-size 100

# Match buildings for specific city
uv run python -m oikotie.geospatial.cli match-buildings --city espoo
```

### Geospatial Data Integration

```bash
# Run Espoo geospatial integration
uv run python scripts/run_espoo_geospatial_integration.py

# Validate Espoo geospatial data
uv run python scripts/validate_espoo_geospatial.py
```

### Geospatial Command Options

| Option | Description | Example |
|--------|-------------|---------|
| `--city` | City name | `--city espoo` |
| `--batch-size` | Batch size for processing | `--batch-size 100` |
| `--output` | Output file path | `--output "data/espoo_buildings.geojson"` |
| `--force` | Force reprocessing of existing data | `--force` |
| `--validate` | Validate results after processing | `--validate` |

## Database Commands

### City-Specific Database Operations

```bash
# Count listings by city
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
results = conn.execute('SELECT city, COUNT(*) FROM listings GROUP BY city').fetchall()
for city, count in results:
    print(f'{city}: {count} listings')
conn.close()
"

# Export city data
uv run python -m oikotie.database.cli export --city espoo --format csv --output "data/exports/espoo_listings.csv"

# Create city-specific indexes
uv run python -m oikotie.database.cli create-indexes --city espoo
```

### Database Maintenance

```bash
# Optimize database
uv run python -m oikotie.database.cli optimize

# Backup database
uv run python -m oikotie.database.cli backup --output "backups/real_estate_$(date +%Y%m%d).duckdb"

# Validate database integrity
uv run python -m oikotie.database.cli validate
```

### Database Command Options

| Option | Description | Example |
|--------|-------------|---------|
| `--city` | City name | `--city espoo` |
| `--format` | Export format (csv, json, parquet) | `--format csv` |
| `--output` | Output file path | `--output "data/exports/espoo_listings.csv"` |
| `--where` | SQL WHERE clause | `--where "price_eur > 100000"` |
| `--limit` | Maximum number of records | `--limit 1000` |

This comprehensive CLI command documentation provides all the necessary information for working with multi-city operations in the Oikotie platform.