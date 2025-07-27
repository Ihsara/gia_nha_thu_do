# Oikotie Real Estate Analytics Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> A comprehensive Finnish real estate data collection, processing, and analytics platform focused on market research and geospatial analysis.

The Oikotie Analytics Platform automates the collection of property listings from Oikotie.fi, enriches the data with municipal geospatial information, and provides powerful visualization and analysis tools for researchers, analysts, and developers interested in the Finnish real estate market.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Multi-City Support](#multi-city-support)
- [Testing](#testing)
- [Documentation](#documentation)
- [Development](#development)
- [Research & Citation](#research--citation)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Features

### 🏠 **Automated Data Collection**
- Multi-threaded web scraping of Oikotie.fi property listings
- **Distributed cluster execution** with Redis-based coordination
- **Smart deduplication** and intelligent work distribution
- **Health monitoring** and automatic failure recovery
- Intelligent rate limiting and error handling
- Cookie consent automation and website interaction
- Configurable city-specific scraping parameters

### 🛡️ **Enterprise Data Governance**
- Production-ready batch processing for thousands of listings
- Complete audit trails and API usage monitoring
- Rate limiting compliance with open data portals
- Quality scoring and data lineage tracking
- Automated governance workflows with progress monitoring
- Database-first strategy with comprehensive error handling

### 🗺️ **Geospatial Data Integration**
- Automated address geocoding and standardization
- Dual-source geodata: Finnish National WMS & Helsinki GeoPackage
- 128 topographic layers including 59,426 building polygons
- Abstract data source interface for seamless switching
- Building footprint and parcel boundary processing
- Topographic and infrastructure data enrichment

### 📊 **Analytics & Storage**
- High-performance DuckDB database optimized for analytics
- Structured property schema with comprehensive metadata
- JSON fallback systems for data reliability
- Historical data tracking and trend analysis

### 🎯 **Interactive Visualization**
- Folium-based interactive property mapping
- Customizable visualization layers and filters
- Export capabilities for presentations and reports
- Jupyter notebook integration for custom analysis

### 🔬 **Research-Ready Output**
- Clean, structured datasets suitable for academic research
- Comprehensive data validation and quality checks
- Export formats compatible with statistical software
- Citation guidelines for academic use

## Installation

### System Requirements

- **Python**: 3.9 or higher
- **Operating System**: Windows, macOS, or Linux
- **Browser**: Chrome or Chromium (for web scraping)
- **Memory**: Minimum 4GB RAM (8GB+ recommended for large datasets)
- **Storage**: 10GB+ available space for data and databases

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/Ihsara/gia_nha_thu_do.git
   cd oikotie
   ```

2. **Create and activate a virtual environment**
   ```bash
   # Using uv (recommended)
   uv venv
   
   # Activate on Windows
   .venv\Scripts\activate
   
   # Activate on macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   uv sync --all-extras
   ```

4. **Verify installation**
   ```bash
   uv run python -m oikotie.visualization.cli.commands info
   ```

### Alternative Installation Methods

**Using pip:**
```bash
pip install -e .
pip install -e ".[test]"  # Include testing dependencies
```

**Using conda:**
```bash
conda create -n oikotie python=3.9
conda activate oikotie
pip install -e .
```

## Quick Start

### Basic Data Collection

1. **Configure scraping parameters**
   ```bash
   # Edit config/config.json to specify cities and parameters
   ```

2. **Run the complete data collection workflow**
   ```bash
   python -m oikotie.scripts.run_workflow
   ```

3. **Explore the collected data**
   ```bash
   python -m oikotie.scripts.check_database_contents
   ```

4. **Generate visualizations**
   ```bash
   python -m oikotie.scripts.visualize.visualize_parcels
   ```

### Command-Line Interface

The platform provides a comprehensive CLI for common tasks with multi-city support:

```bash
# Generate enhanced interactive dashboard for Helsinki (default)
uv run python -m oikotie.visualization.cli.commands dashboard --enhanced --open

# Generate enhanced dashboard for Espoo
uv run python -m oikotie.visualization.cli.commands dashboard --city espoo --enhanced --open

# Generate comparative dashboard for Helsinki and Espoo
uv run python -m oikotie.visualization.cli.commands dashboard --comparative "helsinki,espoo" --open

# Show city selector interface
uv run python -m oikotie.visualization.cli.commands dashboard --selector --open

# Run multi-city daily automation
uv run python -m oikotie.automation.cli run --daily

# Validate Espoo data quality
uv run python -m oikotie.visualization.cli.commands validate --city espoo --schema --sample

# Run progressive validation for Espoo
uv run python run_espoo_validation.py
```

**Available CLI Options:**
- `--enhanced`: Enable enhanced dashboard features with building footprints
- `--open`: Automatically open generated dashboard in browser
- `--output`: Specify custom output directory
- `--city`: Select city (helsinki, espoo, tampere, turku)
- `--comparative`: Generate comparative dashboard for multiple cities (comma-separated)
- `--selector`: Show city selection interface
- `--sample-size`: Number of listings to include (default: 2000)
- `--priority`: Set city processing priority (1=highest)
- `--validate-coordinates`: Validate coordinates against city boundaries

### Python API Usage

```python
from oikotie.visualization.dashboard.enhanced import EnhancedDashboard
from oikotie.visualization.utils.data_loader import DataLoader
from oikotie.visualization.utils.config import get_city_config

# Initialize data loader
loader = DataLoader()

# Generate enhanced dashboard
dashboard = EnhancedDashboard(
    data_loader=loader,
    city_config=get_city_config("helsinki")
)

# Create interactive visualization
output_path = dashboard.run_dashboard_creation(
    enhanced_mode=True,
    max_listings=2000
)
print(f"Dashboard created: {output_path}")
```

## Usage

### Data Collection and Visualization Workflow

The platform provides both legacy scripts and modern CLI tools:

#### 1. **Modern CLI Workflow (Recommended)**
```bash
# System information and validation
uv run python -m oikotie.visualization.cli.commands info
uv run python -m oikotie.visualization.cli.commands validate --schema

# Generate enhanced interactive dashboards  
uv run python -m oikotie.visualization.cli.commands dashboard --enhanced --open

# Analyze specific buildings
uv run python -m oikotie.visualization.cli.commands analyze --building-id OSM_12345

# Progressive validation testing (10-sample → full scale)
uv run python -m tests.validation.test_10_samples
uv run python -m tests.validation.test_full_helsinki
```

#### 2. **Legacy Script Workflow**
```bash
# Prepare geospatial data (optional)
python -m oikotie.scripts.prepare.prepare_geospatial_data
python -m oikotie.scripts.prepare.load_helsinki_data

# Execute complete data collection
python -m oikotie.scripts.run_workflow

# Database analysis
python -m oikotie.scripts.check_database_contents

# Interactive analysis
jupyter notebook notebooks/
```

#### 3. **Enhanced Dashboard Features**
```bash
# Multiple visualization modes
uv run python -m oikotie.visualization.cli.commands dashboard --enhanced
# ✅ Split-screen layout (30% controls + 70% map)
# ✅ Gradient building highlighting with price-based colors
# ✅ Multi-mode view system (Direct/Buffer/No-match)
# ✅ Interactive controls (toggles, filters, sliders)
# ✅ Building footprint visualization with OSM data

# Espoo-specific enhanced dashboard
uv run python -m oikotie.visualization.cli.commands dashboard --city espoo --enhanced --open
# ✅ Espoo-specific styling and color scheme
# ✅ Espoo building footprints visualization
# ✅ Espoo boundary rendering and map styling

# Multi-city comparative dashboard
uv run python -m oikotie.visualization.cli.commands dashboard --comparative "helsinki,espoo" --open
# ✅ Side-by-side city comparison
# ✅ Cross-city statistical analysis
# ✅ Multi-city map visualization
```

### Configuration

Edit `config/config.json` to customize scraping parameters for multiple cities:

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
  ],
  "global_settings": {
    "database_path": "data/real_estate.duckdb",
    "output_directory": "output",
    "log_level": "INFO",
    "cluster_coordination": {
      "redis_url": "redis://localhost:6379",
      "heartbeat_interval": 30,
      "work_distribution_strategy": "round_robin"
    }
  }
}
```

### Daily Automation System

The platform includes a comprehensive daily automation system for production use:

```bash
# Run daily automation for all enabled cities
uv run python -m oikotie.automation.cli run --daily

# Deploy production system
uv run python -m oikotie.automation.cli production deploy --type standalone

# Start production monitoring dashboard
uv run python -m oikotie.automation.cli production dashboard --port 8090

# Validate production readiness
uv run python -m oikotie.automation.cli production validate
```

**Automation Features:**
- **Smart Daily Execution**: Intelligent deduplication prevents re-processing recent listings
- **Flexible Deployment**: Standalone, container, or cluster deployment options
- **Production Dashboard**: Real-time monitoring and operational control
- **Comprehensive Monitoring**: Health checks, metrics, and alerting
- **Security & Backup**: Built-in security features and automated backup procedures

### Distributed Cluster Execution

For large-scale operations, the platform supports distributed execution across multiple nodes:

```bash
# Setup Redis coordination
docker run -d --name redis -p 6379:6379 redis:alpine

# Start cluster nodes
export REDIS_URL=redis://localhost:6379
uv run python -m oikotie.automation.cli run --cluster
```

**Cluster Features:**
- **Redis-based coordination** for work distribution
- **Distributed locking** to prevent duplicate work
- **Health monitoring** with automatic failure detection
- **Work redistribution** when nodes fail
- **Exponential backoff** retry logic
- **Graceful shutdown** with work preservation

### Jupyter Notebook Analysis

The platform includes comprehensive Jupyter notebooks for data exploration:

- `notebooks/explore_open_data.ipynb` - Helsinki open data integration
- `notebooks/visualize_helsinki_properties.ipynb` - Property visualization
- `notebooks/check_data.ipynb` - Data quality analysis
- `notebooks/inspect_gml_data.ipynb` - GML file inspection

### Command-Line Interface

#### Modern CLI Commands (Recommended)

| Command | Purpose | Example |
|---------|---------|---------|
| `dashboard` | Generate interactive dashboards | `uv run python -m oikotie.visualization.cli.commands dashboard --enhanced --open` |
| `analyze` | Building-specific analysis | `uv run python -m oikotie.visualization.cli.commands analyze --building-id OSM_12345` |
| `validate` | Data quality validation | `uv run python -m oikotie.visualization.cli.commands validate --schema --sample` |
| `info` | System information display | `uv run python -m oikotie.visualization.cli.commands info` |

#### Database Operations

| Command | Purpose |
|---------|---------|
| `python -c "from oikotie.database.schema import DatabaseSchema; print(DatabaseSchema().get_table_info())"` | Check database schema |
| `python -c "from oikotie.database.models import Listing; print('Models available')"` | Validate data models |

#### Test Validation (Quality Assurance)

| Test | Purpose |
|------|---------|
| `pytest tests/validation/test_10_samples.py` | Quick 10-sample validation |
| `pytest tests/validation/test_postal_code.py` | Postal code specific testing |
| `pytest tests/validation/test_full_helsinki.py` | Full Helsinki dataset validation |
| `pytest tests/validation/test_package_imports.py` | Package structure validation |

## Multi-City Support

The platform provides comprehensive support for multiple Finnish cities, currently supporting **Helsinki** and **Espoo** with the same feature set and data quality standards.

### Supported Cities

| City | Status | Features | Data Sources |
|------|--------|----------|--------------|
| **Helsinki** | ✅ Production Ready | Full feature set | Helsinki Open Data, OSM, National Geodata |
| **Espoo** | ✅ Production Ready | Full feature set | Espoo Open Data, OSM, National Geodata |

### Multi-City Configuration

Configure multiple cities in `config/config.json`:

```json
{
  "tasks": [
    {
      "city": "Helsinki",
      "enabled": true,
      "coordinate_bounds": [24.5, 60.0, 25.5, 60.5],
      "geospatial_sources": ["helsinki_open_data", "osm_buildings"]
    },
    {
      "city": "Espoo", 
      "enabled": true,
      "coordinate_bounds": [24.4, 60.1, 24.9, 60.4],
      "geospatial_sources": ["espoo_open_data", "osm_buildings"]
    }
  ]
}
```

### Multi-City Operations

```bash
# Run automation for all enabled cities
uv run python -m oikotie.automation.cli run --daily

# Generate multi-city comparative dashboard
uv run python -m oikotie.visualization.cli.commands dashboard --comparative "helsinki,espoo" --open

# City-specific operations
uv run python -m oikotie.visualization.cli.commands dashboard --city helsinki --enhanced
uv run python -m oikotie.visualization.cli.commands dashboard --city espoo --enhanced

# Multi-city validation
uv run python -m tests.validation.test_multi_city_workflow
```

### Multi-City Features

- **Concurrent Processing**: Process multiple cities simultaneously with intelligent work distribution
- **City-Specific Configuration**: Customizable parameters per city (rate limits, coordinate bounds, data sources)
- **Unified Database**: Single DuckDB database with proper city separation and indexing
- **Cross-City Analytics**: Comparative analysis and visualization across cities
- **Independent Error Handling**: City-specific error handling and recovery mechanisms
- **Scalable Architecture**: Add new cities with minimal configuration changes

## Testing

The platform includes a comprehensive testing framework with multiple levels of validation to ensure reliability and prevent costly failures.

### Bug Prevention Testing

**MANDATORY**: Run bug prevention tests before any expensive operation (>10 minutes):

```bash
# Quick bug prevention test (< 1 minute)
python run_bug_prevention_test.py
# or
uv run python run_bug_prevention_test.py

# Comprehensive bug prevention with detailed report
uv run python tests/integration/multi_city_bug_prevention_test.py
```

**Bug Prevention Validates:**
- System requirements (Python version, memory, disk space)
- Database connectivity and schema
- Multi-city configuration validation
- Dependency availability
- Network connectivity
- Basic functionality tests

### Progressive Validation Strategy

Follow the **3-step progressive validation** approach:

#### Step 1: Small Sample Validation (10-20 listings, <5 minutes)
```bash
# Quick proof of concept
pytest tests/validation/test_10_samples.py
uv run python quickcheck/validate_10_listings_osm.py

# Multi-city small sample
uv run python tests/integration/test_multi_city_integration_suite.py::TestMultiCityIntegrationSuite::test_01_multi_city_end_to_end_workflow
```

#### Step 2: Medium Scale Validation (100-500 listings, 10-15 minutes)
```bash
# Medium scale testing
pytest tests/validation/test_100_comprehensive_osm.py
uv run python quickcheck/validate_100_comprehensive_osm.py
```

#### Step 3: Full Scale Production Validation (≥99.40% match rate)
```bash
# Full Helsinki validation
pytest tests/validation/test_full_helsinki.py
uv run python quickcheck/validate_full_helsinki_osm.py

# Full multi-city validation
uv run python tests/integration/comprehensive_integration_test_runner.py --mode production
```

### Comprehensive Integration Testing

The platform includes a comprehensive integration testing suite for production readiness validation:

```bash
# Run all integration tests
uv run python tests/integration/comprehensive_integration_test_runner.py

# Run specific test suites
uv run python tests/integration/comprehensive_integration_test_runner.py --suites multi_city_integration end_to_end_workflows

# Run critical tests only (quick validation)
uv run python tests/integration/comprehensive_integration_test_runner.py --mode critical

# Run performance-focused tests
uv run python tests/integration/comprehensive_integration_test_runner.py --mode performance

# Run with parallel execution
uv run python tests/integration/comprehensive_integration_test_runner.py --parallel
```

### Integration Test Categories

| Test Category | Purpose | Duration | Critical |
|---------------|---------|----------|----------|
| **Multi-City Integration** | End-to-end multi-city workflow validation | 15 min | ✅ Yes |
| **End-to-End Workflows** | Complete user journey validation | 10 min | ✅ Yes |
| **Performance & Load** | Performance testing under various loads | 20 min | No |
| **Chaos Engineering** | System resilience under failure scenarios | 10 min | No |
| **Deployment & Rollback** | Deployment validation and rollback testing | 8 min | No |

### Quality Gates

**Technical Correctness:**
- ≥95% scraping success rate for both cities
- ≥95% geocoding accuracy for both cities  
- 100% database constraint compliance
- 100% API rate limit compliance

**Logical Correctness:**
- Manual verification of address geocoding accuracy
- Visual verification of building footprint matching
- Cross-city data quality consistency validation
- Real-world sense validation of results

**Performance Acceptability:**
- Comparable performance to single-city operations
- Memory usage < 2GB peak during testing
- Average CPU usage < 80% during operations
- Database query performance < 1s for standard operations

### Testing Best Practices

1. **Always run bug prevention tests first** - Prevents expensive failures
2. **Follow progressive validation** - 10 → 100 → full scale approach
3. **Validate both cities** - Ensure Helsinki and Espoo work correctly
4. **Monitor resource usage** - Track memory, CPU, and disk usage
5. **Test deployment scenarios** - Validate all deployment modes
6. **Document test results** - Keep comprehensive test reports

### Continuous Integration

```bash
# Pre-commit testing
python run_bug_prevention_test.py && pytest tests/unit/

# Integration testing pipeline
python run_bug_prevention_test.py
pytest tests/validation/test_10_samples.py
uv run python tests/integration/comprehensive_integration_test_runner.py --mode critical

# Production readiness validation
uv run python tests/integration/comprehensive_integration_test_runner.py --mode production
```

## Documentation

Comprehensive documentation is available in the `docs/` directory:

### Core Documentation
- **[Dashboard Documentation](docs/DASHBOARD.md)** - Interactive dashboard usage
- **[Script Documentation](docs/scripts/)** - Detailed script references
- **[Workflow Documentation](docs/scripts/run_workflow.md)** - Complete workflow guide

### Deployment Documentation
- **[Deployment Guide](docs/deployment/)** - Complete deployment documentation
- **[Configuration Examples](docs/deployment/configuration-examples.md)** - Ready-to-use configurations
- **[Multi-City Best Practices](docs/deployment/multi-city-best-practices.md)** - Best practices for multi-city deployments
- **[CLI Commands](docs/deployment/cli-commands.md)** - Comprehensive CLI command documentation
- **[Multi-City Troubleshooting](docs/deployment/multi-city-troubleshooting.md)** - Troubleshooting multi-city issues
- **[Troubleshooting Guide](docs/deployment/troubleshooting-guide.md)** - Common issues and solutions
- **[Operational Runbooks](docs/deployment/operational-runbooks.md)** - Step-by-step procedures

### Deployment Options
The system supports multiple deployment architectures:

| Deployment Type | Use Case | Documentation |
|----------------|----------|---------------|
| **Standalone** | Development, testing | [Standalone Guide](docs/deployment/README.md#standalone-deployment) |
| **Docker Container** | Single-node production | [Container Guide](docs/deployment/README.md#container-deployment) |
| **Kubernetes** | Cloud-native, scalable | [Kubernetes Guide](docs/deployment/README.md#kubernetes-deployment) |
| **Helm Chart** | Flexible K8s deployment | [Helm Guide](docs/deployment/README.md#helm-deployment) |

#### Quick Deployment
```bash
# Docker Compose (Production-ready)
docker-compose up -d

# Kubernetes with Helm
helm install oikotie-scraper k8s/helm/oikotie-scraper/

# Standalone (Development)
uv run python -m oikotie.automation.cli run --daily
```

### API Reference

Key modules and their functionality:

#### Core Modules
- `oikotie.scraper` - Web scraping functionality
- `oikotie.geolocation` - Address processing and geocoding
- `oikotie.utils` - Utility functions and helpers
- `oikotie.road_data` - Road network data processing

#### Automation Package
- `oikotie.automation.cluster` - **Redis-based cluster coordination**
- `oikotie.automation.cluster.ClusterCoordinator` - **Distributed work management**
- `oikotie.automation.cluster.WorkItem` - **Work unit representation**
- `oikotie.automation.cluster.HealthStatus` - **Node health monitoring**

#### Visualization Package
- `oikotie.visualization.dashboard.enhanced` - Enhanced interactive dashboards
- `oikotie.visualization.dashboard.builder` - Dashboard construction utilities
- `oikotie.visualization.utils.data_loader` - Database connection and data loading
- `oikotie.visualization.utils.config` - Configuration management
- `oikotie.visualization.utils.geometry` - Spatial processing utilities
- `oikotie.visualization.cli.commands` - Command-line interface

#### Database Package
- `oikotie.database.schema` - Database schema definitions
- `oikotie.database.models` - Data model classes
- `oikotie.database.migration` - Database migration utilities

## Development

### Development Setup

1. **Clone and setup environment** (see Installation)

2. **Install development dependencies**
   ```bash
   uv sync --all-extras
   ```

3. **Run tests**
   ```bash
   pytest
   pytest --cov=oikotie  # With coverage
   ```

### Project Structure

```
oikotie/
├── .clinerules/           # Development workflow standards
│   ├── database-management.md
│   ├── error-documentation-system.md
│   └── progressive-validation-strategy.md
├── config/                # Configuration files
├── data/                  # Data storage (git-ignored)
│   └── real_estate.duckdb # Main DuckDB database
├── docs/                  # Project documentation
│   ├── automation/        # Automation system documentation
│   ├── deployment/        # Deployment guides and examples
│   ├── errors/            # Error documentation system
│   ├── scripts/           # Script documentation
│   └── security/          # Security implementation docs
├── memory-bank/           # Project knowledge management
├── notebooks/             # Jupyter analysis notebooks
├── oikotie/              # Main Python package
│   ├── automation/       # **Distributed execution system**
│   │   ├── cluster.py    # **Redis-based cluster coordination**
│   │   └── __init__.py   # **Automation package exports**
│   ├── database/         # Database schema and models
│   │   ├── schema.py     # Table definitions and relationships
│   │   ├── models.py     # Data model classes
│   │   └── migration.py  # Migration utilities
│   ├── scripts/          # Legacy executable scripts
│   ├── visualization/    # Modern visualization package
│   │   ├── cli/          # Command-line interface
│   │   ├── dashboard/    # Dashboard generation
│   │   ├── maps/         # Map utilities
│   │   └── utils/        # Visualization utilities
│   └── utils/            # Core utility functions
├── output/               # Generated files (git-ignored)
│   └── visualization/    # Dashboard outputs
├── scripts/              # Organized utility scripts
│   ├── automation/       # Automation scripts
│   ├── demos/            # Demonstration scripts
│   ├── deployment/       # Deployment scripts
│   └── testing/          # Testing utilities
├── tests/                # Test suite
│   ├── integration/      # Integration tests
│   ├── unit/             # Unit tests
│   └── validation/       # Validation tests
└── logs/                 # Log files
```

### Architecture Overview

The platform uses a modular architecture:

- **Data Collection Layer**: Selenium-based web scraping
- **Processing Layer**: GeoPandas and DuckDB for data processing
- **Storage Layer**: DuckDB for analytics, JSON for fallback
- **Visualization Layer**: Folium for interactive mapping
- **Analysis Layer**: Jupyter notebooks and pandas

### Testing

#### Bug Prevention Testing (MANDATORY)
For expensive computational pipelines (>10 minutes), comprehensive bug testing is **required** before execution:

```bash
# Run critical bug validation tests (10 seconds)
uv run python simple_bug_test.py

# Only proceed with expensive operations after 100% test pass rate
```

#### Standard Testing
```bash
# Run all tests
pytest

# Run specific test modules
pytest tests/test_scraper.py
pytest tests/test_geolocation.py
pytest tests/test_dashboard.py

# Generate coverage report
pytest --cov=oikotie --cov-report=html
```

#### Testing Workflow Rules
- **ANY script taking >10 minutes MUST have bug tests created first**
- **NO expensive pipeline execution without passing bug validation**
- **ALL known bugs from previous failures MUST be cataloged and tested**
- See `.clinerules/testing-workflow.md` for complete testing procedures

### Code Style

The project follows Python best practices:
- Type hints for better code documentation
- Comprehensive error handling and logging
- Modular design with clear separation of concerns
- Comprehensive test coverage

## Research & Citation

### Academic Usage

This platform is designed to support academic research in:
- Real estate market analysis
- Urban planning and development
- Geospatial data science
- Housing market economics

### Citation

If you use this platform in your research, please cite:

```bibtex
@software{oikotie_analytics,
  title={Oikotie Real Estate Analytics Platform},
  author={Trần Long Châu},
  year={2025},
  url={https://github.com/Ihsara/gia_nha_thu_do},
  license={MIT}
}
```

### Data Usage Guidelines

- **Respect Rate Limits**: The scraper includes built-in rate limiting
- **Academic Use**: Suitable for non-commercial research purposes
- **Data Attribution**: Credit Oikotie.fi as the original data source
- **Compliance**: Ensure compliance with Oikotie.fi terms of service

## Contributing

We welcome contributions! Please see our contributing guidelines:

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes** with comprehensive tests
4. **Update documentation** as needed
5. **Commit your changes** (`git commit -m 'Add amazing feature'`)
6. **Push to the branch** (`git push origin feature/amazing-feature`)
7. **Open a Pull Request**

### Development Guidelines

- Write comprehensive tests for new features
- Update documentation for any user-facing changes
- Follow existing code style and patterns
- Include type hints for better code documentation
- Ensure all tests pass before submitting

### Issue Reporting

Please use GitHub Issues to report:
- Bugs and errors
- Feature requests
- Documentation improvements
- Performance issues

Include:
- Python version and operating system
- Complete error messages and stack traces
- Steps to reproduce the issue
- Expected vs. actual behavior

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Third-Party Acknowledgments

- **Selenium** - Web automation framework
- **DuckDB** - High-performance analytical database
- **GeoPandas** - Geospatial data processing
- **Folium** - Interactive mapping visualization
- **Helsinki Open Data** - Municipal geospatial datasets

## Support

### Documentation
- [Project Documentation](docs/)
- [Script References](docs/scripts/)
- [Jupyter Notebooks](notebooks/)

### Community
- **Issues**: [GitHub Issues](https://github.com/Ihsara/gia_nha_thu_do/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Ihsara/gia_nha_thu_do/discussions)

### Professional Support
For commercial applications or professional support, please contact the maintainer.

---

**Made with ❤️ for the Finnish real estate research community**
