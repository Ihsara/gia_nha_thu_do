# Technical Context: Oikotie Development Environment

## Technology Stack

### Core Dependencies
```toml
# From pyproject.toml
python = ">=3.9"
beautifulsoup4 = ">=4.12.3"
duckdb = ">=0.10.0"
loguru = ">=0.7.2"
pandas = ">=2.2.0"
selenium = ">=4.18.0"
geopy = ">=2.4.1"
folium = ">=0.15.1"
scipy = ">=1.12.0"
branca = ">=0.7.1"
geopandas = ">=0.14.4"
fiona = ">=1.9.6"
contextily = ">=1.5.0"
geodatasets = ">=2023.5.0"
ipython = ">=8.18.1"
ipykernel = ">=6.29.5"
```

### Development Tools
- **Package Manager**: UV (modern Python package management)
- **Testing**: pytest>=8.0.0, pytest-mock>=3.12.0
- **Environment**: Virtual environment with uv
- **Version Control**: Git with GitHub integration

## Development Setup

### Environment Requirements
- **Python**: 3.9+ (project uses 3.13.2)
- **Operating System**: Windows 11 (current), Linux compatible
- **Browser**: Chrome/Chromium for Selenium automation
- **Memory**: Minimum 4GB RAM for geospatial processing
- **Storage**: 10GB+ for data files and databases

### Installation Process
```bash
# 1. Clone repository
git clone <repository-url>
cd oikotie

# 2. Create virtual environment
uv venv

# 3. Activate environment (Windows)
.venv\Scripts\activate

# 4. Install dependencies
uv sync --all-extras

# 5. Verify installation
python -m oikotie.scripts.check_database_contents
```

### Project Structure
```
oikotie/
├── config/           # Configuration files
│   └── config.json   # Scraping configuration
├── data/            # Data storage (git-ignored)
├── docs/            # Documentation
├── memory-bank/     # Project memory system
├── notebooks/       # Jupyter analysis notebooks
├── oikotie/         # Main Python package
│   ├── scripts/     # Executable scripts
│   │   ├── prepare/ # Data preparation
│   │   └── visualize/ # Visualization
│   └── utils/       # Utility functions
├── output/          # Generated files (git-ignored)
├── tests/           # Test suite
└── logs/            # Log files
```

## Development Workflow

### Data Pipeline Commands
```bash
# Full workflow execution
python -m oikotie.scripts.run_workflow

# Individual preparation steps
python -m oikotie.scripts.prepare.prepare_geospatial_data
python -m oikotie.scripts.prepare.prepare_topographic_data
python -m oikotie.scripts.prepare.load_helsinki_data

# Analysis and visualization
python -m oikotie.scripts.check_database_contents
python -m oikotie.scripts.visualize.visualize_parcels
python -m oikotie.scripts.visualize.visualize_buildings
```

### Testing Commands
```bash
# Run all tests
pytest

# Run specific test files
pytest tests/test_scraper.py
pytest tests/test_geolocation.py
pytest tests/test_dashboard.py

# Run with coverage
pytest --cov=oikotie
```

## Technical Constraints

### Performance Limitations
- **Scraping Speed**: Rate-limited to respect Oikotie.fi servers
- **Memory Usage**: GeoPandas operations require significant RAM
- **Storage**: DuckDB files can grow large with comprehensive data
- **Geocoding**: Limited by external service rate limits

### Browser Dependencies
- **Selenium**: Requires Chrome/Chromium browser installation
- **WebDriver**: Automatic driver management via Selenium 4+
- **Headless Mode**: Configurable for server environments
- **JavaScript**: Full browser engine required for modern web scraping

### External Dependencies
- **Geocoding Services**: Nominatim (OpenStreetMap) for address resolution
- **Helsinki Open Data**: City planning and infrastructure datasets
- **Internet Connection**: Required for scraping and geocoding
- **API Stability**: Dependent on Oikotie.fi website structure

## Configuration Management

### Environment Variables
- **Database Path**: Configurable via `data/real_estate.duckdb`
- **Log Level**: Controlled by Loguru configuration
- **Browser Settings**: Headless/GUI mode selection
- **Worker Threads**: Configurable concurrency limits

### Configuration Files
```json
// config/config.json
{
  "tasks": [
    {
      "city": "Helsinki",
      "enabled": true,
      "url": "...",
      "max_detail_workers": 5
    }
  ]
}
```

### Python Version Management
- **Base Requirement**: Python 3.9+
- **Current Development**: Python 3.13.2
- **UV Integration**: Automatic Python version management
- **Virtual Environment**: Isolated dependency management

## Tool Usage Patterns

### Database Operations
```python
# Standard pattern for database connections
from oikotie.geolocation import get_db_connection

with get_db_connection() as conn:
    # Database operations
    pass
```

### Selenium Automation
```python
# Standard scraper initialization
scraper = OikotieScraper(headless=True)
try:
    # Scraping operations
    listings = scraper.get_all_listing_summaries(url)
finally:
    scraper.close()
```

### Geospatial Processing
```python
# GeoPandas integration pattern
import geopandas as gpd
gdf = gpd.read_file("data/geospatial.geojson")
```

## Development Environment Integration

### IDE Configuration
- **VSCode**: Recommended with Python extension
- **Jupyter**: Integrated notebook support
- **Debugging**: Python debugger configuration
- **Linting**: Configurable code quality tools

### Version Control Workflow
- **Git Repository**: GitHub integration
- **Branching**: Feature branch workflow recommended
- **Ignored Files**: Data and output directories excluded
- **Commit Patterns**: Conventional commit messages preferred

## Deployment Considerations

### Local Development
- **Minimal Setup**: Single machine development
- **Resource Requirements**: Moderate CPU/memory usage
- **Internet Dependency**: Required for data collection
- **Browser Requirements**: GUI or headless browser support

### Production Considerations
- **Headless Operation**: No GUI dependencies
- **Scheduled Execution**: Cron job compatibility
- **Error Handling**: Robust error recovery
- **Resource Monitoring**: Memory and storage management

## Known Technical Issues

### Common Problems
- **Browser Driver Issues**: Selenium WebDriver compatibility
- **Memory Consumption**: Large GeoPandas datasets
- **Geocoding Rate Limits**: External service limitations
- **Website Changes**: Oikotie.fi structure modifications

### Troubleshooting
- **Log Files**: Comprehensive error logging in `logs/`
- **Fallback Systems**: JSON backup for database failures
- **Retry Logic**: Automatic retry for transient failures
- **Validation**: Data quality checks throughout pipeline
