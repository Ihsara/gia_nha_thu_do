# Technology Stack

## Build System & Package Management
- **Package Manager**: `uv` (modern Python package manager)
- **Build System**: setuptools with pyproject.toml configuration
- **Python Version**: 3.9+ (currently using 3.13)
- **Virtual Environment**: `.venv` managed by uv

## Core Dependencies
- **Web Scraping**: Selenium WebDriver with Chrome/Chromium
- **Database**: DuckDB (single database strategy at `data/real_estate.duckdb`)
- **Geospatial**: GeoPandas, Fiona, OSMnx, Folium
- **Data Processing**: Pandas, NumPy, SciPy
- **Visualization**: Folium (interactive maps), Plotly
- **HTTP**: httpx, OWSLib (for WMS services)
- **Logging**: loguru

## Database Architecture
- **Primary Database**: DuckDB (`data/real_estate.duckdb`)
- **No SQLite**: All SQLite references removed, DuckDB only
- **Spatial Extensions**: PostGIS-compatible spatial operations
- **Connection**: Unified utilities from `oikotie.database`

## Common Commands

### Environment Setup
```bash
# Create and activate virtual environment
uv venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Install dependencies
uv sync --all-extras
```

### Development Commands
```bash
# Run tests
pytest
pytest --cov=oikotie  # With coverage

# Modern CLI (recommended)
uv run python -m oikotie.visualization.cli.commands dashboard --enhanced --open
uv run python -m oikotie.visualization.cli.commands info
uv run python -m oikotie.visualization.cli.commands validate --schema

# Legacy workflow
python -m oikotie.scripts.run_workflow
python -m oikotie.scripts.check_database_contents
```

### Testing Workflow
```bash
# MANDATORY: Bug prevention tests before expensive operations (>10 min)
uv run python simple_bug_test.py

# Validation tests (progressive approach)
pytest tests/validation/test_10_samples.py
pytest tests/validation/test_full_helsinki.py
```

## Code Style Standards
- **Type Hints**: Required for better documentation
- **Error Handling**: Comprehensive logging and graceful degradation
- **Modular Design**: Clear separation of concerns
- **Testing**: Comprehensive coverage, especially for expensive operations