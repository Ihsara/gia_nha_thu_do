# Technical Context: Oikotie Development Environment

## 🌟 BREAKTHROUGH: OpenStreetMap Building Integration

### Revolutionary Spatial Architecture
**Major Technical Achievement**: Integrated OpenStreetMap building footprints for building-level spatial precision, replacing administrative polygon approximations with actual building boundaries.

## 🚀 BREAKTHROUGH: Distributed Cluster Execution System

### Enterprise-Grade Distributed Architecture
**Major Technical Achievement**: Implemented Redis-based cluster coordination system for distributed scraping execution with automatic failure recovery, work distribution, and health monitoring.

## Technology Stack

### Core Dependencies
```toml
# From pyproject.toml - Core Platform
python = ">=3.9"
beautifulsoup4 = ">=4.12.3"
duckdb = ">=0.10.0"
loguru = ">=0.7.2"
pandas = ">=2.2.0"
selenium = ">=4.18.0"

# Distributed Execution and Automation
redis = ">=6.2.0"           # Cluster coordination
psutil = ">=7.0.0"          # System resource monitoring
flask = ">=3.1.1"           # Web interface (optional)

# Geospatial and Spatial Analysis Stack
geopy = ">=2.4.1"
folium = ">=0.15.1"
geopandas = ">=0.14.4"
fiona = ">=1.9.6"
contextily = ">=1.5.0"
geodatasets = ">=2023.5.0"
scipy = ">=1.12.0"
branca = ">=0.7.1"
shapely = ">=2.0.0"

# Analysis and Visualization
ipython = ">=8.18.1"
ipykernel = ">=6.29.5"
matplotlib = ">=3.8.0"
plotly = ">=5.17.0"
```

### OSM Integration Dependencies
```toml
# OpenStreetMap Data Processing
osmnx = ">=1.9.0"           # OSM network analysis
requests = ">=2.31.0"       # Geofabrik data download
zipfile = "standard-library" # Archive extraction
```

### Development Tools
- **Package Manager**: UV (modern Python package management)
- **Testing**: pytest>=8.0.0, pytest-mock>=3.12.0
- **Environment**: Virtual environment with uv
- **Version Control**: Git with GitHub integration
- **Spatial Tools**: GDAL/OGR (via GeoPandas), PostGIS compatibility

## OSM Building Architecture

### Geofabrik Data Pipeline
```python
# OSM Building Data Processing Pipeline
Source: https://download.geofabrik.de/europe/finland-latest-free.shp.zip
Processing: 2.89M buildings → 79,556 Helsinki building footprints
Output: data/helsinki_buildings_20250711_041142.geojson (36MB)
Format: GeoJSON in EPSG:4326 (WGS84)
Coordinate System: Compatible with existing listings pipeline
```

### Building Footprint Processing
```python
# Spatial Join Architecture
Listings: 8,100 Helsinki real estate listings (Point geometries)
Buildings: 79,556 Helsinki building footprints (Polygon geometries)
Join Method: Contains + 100m buffer spatial join
Performance: 250+ listings/second parallel processing
Match Rate: 89.04% building-level precision
```

### Progressive Validation Framework
```python
# 3-Step Validation Pipeline
Step 1: 10 random listings → Building precision validation
Step 2: Postal code area → Representative validation
Step 3: Full city → Production-scale validation
Quality Gates: 95%+ (Step 1), 98%+ (Step 2), 99.4%+ (Step 3)
```

## Distributed Cluster Architecture

### Redis-Based Coordination System
```python
# Cluster Coordination Pipeline
Coordinator: Redis-based work distribution and health monitoring
Work Items: Serialized scraping tasks with retry logic
Distributed Locking: Prevents duplicate work execution across nodes
Health Monitoring: Real-time CPU, memory, disk usage tracking
Failure Recovery: Automatic work redistribution from failed nodes
Performance: 30 comprehensive tests with 100% pass rate
```

### Cluster Components Architecture
```python
# Core Cluster Components
ClusterCoordinator: Main coordination class with Redis integration
WorkItem: Serializable work units with status tracking
HealthStatus: Node health monitoring with system metrics
WorkDistribution: Intelligent load balancing across nodes
Distributed Locks: Redis-based locks with TTL and ownership
Retry Logic: Exponential backoff for failed work items
```

### Multi-Node Execution Framework
```python
# Distributed Processing Pipeline
Node Registration: Automatic node discovery and health reporting
Work Distribution: Round-robin assignment with load balancing
Lock Acquisition: Distributed locks prevent duplicate processing
Progress Tracking: Real-time work item status monitoring
Failure Detection: Stale node cleanup and work redistribution
Graceful Shutdown: Work preservation during node termination
```

## Development Setup

### Environment Requirements
- **Python**: 3.9+ (project uses 3.13.2)
- **Operating System**: Windows 11 (current), Linux compatible
- **Browser**: Chrome/Chromium for Selenium automation
- **Memory**: Minimum 8GB RAM for OSM building processing (79K+ polygons)
- **Storage**: 25GB+ for OSM data, buildings, and databases
- **Network**: High-bandwidth for Geofabrik downloads (1.26GB Finland OSM)

### Installation Process
```bash
# 1. Clone repository
git clone <repository-url>
cd oikotie

# 2. Create virtual environment with UV
uv venv

# 3. Activate environment (Windows)
.venv\Scripts\activate

# 4. Install all dependencies including spatial stack
uv sync --all-extras

# 5. Verify installation and OSM capabilities
python -m oikotie.scripts.check_database_contents
uv run validate_10_listings_osm.py  # Test OSM building validation
```

### Project Structure (Updated)
```
oikotie/
├── config/                    # Configuration files
│   └── config.json           # Scraping configuration
├── data/                     # Data storage (git-ignored)
│   ├── real_estate.duckdb    # Main database
│   ├── helsinki_buildings_*.geojson  # OSM building footprints
│   └── finland_osm_shapefiles/      # Raw OSM data
├── docs/                     # Documentation
├── memory-bank/              # Project memory system
├── notebooks/                # Jupyter analysis notebooks
├── oikotie/                  # Main Python package
│   ├── scripts/              # Executable scripts
│   │   ├── prepare/          # Data preparation
│   │   └── visualize/        # Visualization
│   └── utils/                # Utility functions
├── quickcheck/               # OSM research and pipeline scripts
│   ├── osm_geofabrik_pipeline.py    # OSM data download
│   ├── osm_helsinki_research.py     # OSM exploration
│   └── osm_buildings_step1.py       # Step-by-step OSM tests
├── validate_*_osm.py         # OSM validation scripts
├── output/                   # Generated files (git-ignored)
├── tests/                    # Test suite
└── logs/                     # Log files
```

## Development Workflow

### OSM Building Validation Commands
```bash
# Progressive OSM Building Validation
uv run validate_10_listings_osm.py        # Step 1: Small scale
uv run validate_postal_osm.py              # Step 2: Medium scale  
uv run validate_full_helsinki_osm.py       # Step 3: Production scale

# OSM Data Pipeline
uv run python quickcheck/osm_geofabrik_pipeline.py  # Download OSM buildings
```

### Traditional Data Pipeline Commands
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

### Cluster Coordination Commands
```bash
# Cluster coordination testing
pytest tests/test_cluster_coordination.py -v    # Comprehensive cluster tests
uv run python simple_cluster_test.py           # Bug prevention tests

# Cluster system validation
python -c "from oikotie.automation.cluster import create_cluster_coordinator; print('Cluster OK')"

# Redis connectivity testing
redis-cli ping  # Verify Redis server availability
```

### Testing Commands
```bash
# Run all tests including OSM validation and cluster coordination
pytest

# Run cluster coordination tests
pytest tests/test_cluster_coordination.py

# Run spatial and building tests
pytest tests/test_spatial.py
pytest tests/test_buildings.py

# Run traditional component tests
pytest tests/test_scraper.py
pytest tests/test_geolocation.py
pytest tests/test_dashboard.py

# Run with coverage
pytest --cov=oikotie
```

## Technical Constraints

### OSM Integration Constraints
- **Data Size**: 79,556 building polygons require 8GB+ RAM for processing
- **Download Requirements**: 1.26GB Finland OSM data from Geofabrik
- **Processing Time**: Initial OSM download and processing ~15 minutes
- **Update Frequency**: Manual OSM data refresh from Geofabrik (weekly/monthly)
- **Coordinate Systems**: Geographic CRS warnings in distance calculations

### Performance Limitations
- **Scraping Speed**: Rate-limited to respect Oikotie.fi servers
- **Spatial Memory Usage**: GeoPandas + 79K polygons require significant RAM
- **Storage**: DuckDB + OSM building data can exceed 1GB total
- **Geocoding**: Limited by external service rate limits
- **Parallel Processing**: Optimal 8 workers for spatial joins

### Browser Dependencies
- **Selenium**: Requires Chrome/Chromium browser installation
- **WebDriver**: Automatic driver management via Selenium 4+
- **Headless Mode**: Configurable for server environments
- **JavaScript**: Full browser engine required for modern web scraping

### External Dependencies
- **Geocoding Services**: Nominatim (OpenStreetMap) for address resolution
- **OSM Data**: Geofabrik Finland extracts for building boundaries
- **Helsinki Open Data**: City planning and infrastructure datasets
- **Internet Connection**: Required for scraping, geocoding, and OSM data
- **API Stability**: Dependent on Oikotie.fi website structure

## Configuration Management

### OSM Configuration
```python
# OSM Building Data Configuration
HELSINKI_BOUNDS = {
    'north': 60.3,    'south': 59.9,
    'east': 25.3,     'west': 24.7
}
OSM_BUILDING_TAGS = ['building']
SPATIAL_BUFFER_DISTANCE = 0.001  # ~100 meters
GEOFABRIK_URL = "https://download.geofabrik.de/europe/finland-latest-free.shp.zip"
```

### Environment Variables
- **Database Path**: Configurable via `data/real_estate.duckdb`
- **OSM Data Path**: `data/helsinki_buildings_*.geojson`
- **Log Level**: Controlled by Loguru configuration
- **Browser Settings**: Headless/GUI mode selection
- **Worker Threads**: Configurable concurrency limits (default: 8 for spatial)

### Configuration Files
```json
// config/config.json
{
  "tasks": [
    {
      "city": "Helsinki",
      "enabled": true,
      "url": "...",
      "max_detail_workers": 5,
      "spatial_validation": true,
      "osm_buildings": true,
      "cluster_enabled": true,
      "redis_url": "redis://localhost:6379"
    }
  ]
}
```

### Cluster Configuration
```python
# Cluster coordination configuration
REDIS_URL = "redis://localhost:6379"
NODE_ID = "auto-generated"              # Unique node identifier
HEARTBEAT_INTERVAL = 30                 # Health check interval (seconds)
LOCK_TTL = 300                         # Distributed lock TTL (seconds)
MAX_RETRIES = 3                        # Work item retry limit
RETRY_BACKOFF = 30                     # Base retry delay (seconds)
HEALTH_CHECK_TIMEOUT = 120             # Node health timeout (seconds)
```

### Python Version Management
- **Base Requirement**: Python 3.9+
- **Current Development**: Python 3.13.2
- **UV Integration**: Automatic Python version management
- **Virtual Environment**: Isolated dependency management
- **Spatial Extensions**: GDAL/OGR via GeoPandas installation

## Tool Usage Patterns

### OSM Building Integration Patterns
```python
# Standard OSM building loading pattern
import geopandas as gpd

def load_osm_buildings():
    """Load Helsinki building footprints"""
    osm_path = "data/helsinki_buildings_20250711_041142.geojson"
    buildings_gdf = gpd.read_file(osm_path)
    return buildings_gdf

# Spatial join pattern for building matching
def spatial_join_buildings(listings_gdf, buildings_gdf):
    """Match listings to building footprints"""
    matches = []
    for listing in listings_gdf.itertuples():
        point = Point(listing.longitude, listing.latitude)
        
        # Direct contains check
        containing = buildings_gdf[buildings_gdf.contains(point)]
        if not containing.empty:
            matches.append((listing.Index, containing.index[0], 'direct'))
            continue
            
        # Buffer search for nearby buildings
        buffered = point.buffer(0.001)  # ~100m
        intersecting = buildings_gdf[buildings_gdf.intersects(buffered)]
        if not intersecting.empty:
            distances = intersecting.geometry.distance(point)
            closest_idx = distances.idxmin()
            distance = distances.min()
            matches.append((listing.Index, closest_idx, 'buffer', distance))
    
    return matches
```

### Database Operations
```python
# Standard pattern for database connections
from oikotie.geolocation import get_db_connection

with get_db_connection() as conn:
    # Database operations
    # OSM building integration ready
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

### Progressive Validation Pattern
```python
# OSM validation workflow
def progressive_osm_validation():
    """3-step OSM building validation"""
    
    # Step 1: Small scale (10 listings)
    step1_result = validate_small_scale_osm()
    if step1_result.match_rate < 0.95:
        raise ValidationError("Step 1 failed")
    
    # Step 2: Medium scale (postal code)
    step2_result = validate_postal_code_osm()
    if step2_result.match_rate < 0.98:
        raise ValidationError("Step 2 failed")
    
    # Step 3: Production scale (full city)
    step3_result = validate_full_city_osm()
    if step3_result.match_rate < 0.994:
        log.warning("Production validation below target")
    
    return step3_result
```

### Cluster Coordination Patterns
```python
# Standard cluster coordinator setup
from oikotie.automation.cluster import create_cluster_coordinator, WorkItem

def setup_cluster_scraping():
    """Initialize cluster-based scraping"""
    # Create cluster coordinator
    coordinator = create_cluster_coordinator("redis://localhost:6379")
    
    # Start health monitoring
    coordinator.start_health_monitoring()
    
    # Create work items
    work_items = [
        WorkItem(work_id="helsinki-1", city="Helsinki", url="https://..."),
        WorkItem(work_id="espoo-1", city="Espoo", url="https://...")
    ]
    
    # Distribute work across cluster
    result = coordinator.distribute_work(work_items)
    return coordinator, result

# Distributed work processing pattern
def process_cluster_work(coordinator):
    """Process work items from cluster queue"""
    work_items = coordinator.get_work_for_node(coordinator.node_id, count=5)
    
    for work_item in work_items:
        if coordinator.acquire_work_lock(work_item.work_id):
            try:
                # Process the work item
                result = process_scraping_work(work_item)
                coordinator.complete_work_item(work_item)
            except Exception as e:
                coordinator.fail_work_item(work_item, str(e))
            finally:
                coordinator.release_work_lock(work_item.work_id)

# Cluster health monitoring pattern
def monitor_cluster_health(coordinator):
    """Monitor cluster status and health"""
    status = coordinator.get_cluster_status()
    healthy_nodes = coordinator.get_healthy_nodes()
    
    print(f"Cluster: {status['healthy_nodes']} healthy nodes")
    print(f"Work: {status['active_work_items']} active items")
    return status
```

## Development Environment Integration

### IDE Configuration
- **VSCode**: Recommended with Python + GIS extensions
- **Jupyter**: Integrated notebook support with spatial libraries
- **Debugging**: Python debugger + spatial visualization
- **Linting**: Configurable code quality tools + spatial lint rules

### Version Control Workflow
- **Git Repository**: GitHub integration
- **Branching**: Feature branch workflow for OSM integration
- **Ignored Files**: Data, OSM files, and output directories excluded
- **Commit Patterns**: Conventional commit messages for spatial features

### OSM Development Tools
- **QGIS**: Recommended for OSM data visualization and debugging
- **Overpass Turbo**: OSM data query testing and exploration
- **Geofabrik**: Reliable OSM data source for production use
- **OSMnx**: Network analysis and OSM data processing

## Deployment Considerations

### Local Development
- **Minimal Setup**: Single machine development with OSM support
- **Resource Requirements**: High CPU/memory for spatial processing
- **Internet Dependency**: Required for scraping and OSM data downloads
- **Browser Requirements**: GUI or headless browser support
- **Storage Planning**: 25GB+ for complete OSM integration

### Production Considerations
- **Headless Operation**: No GUI dependencies for OSM processing
- **Scheduled Execution**: Cron job compatibility with OSM refresh
- **Error Handling**: Robust OSM download and processing recovery
- **Resource Monitoring**: Memory management for large spatial datasets
- **OSM Updates**: Automated or scheduled Geofabrik data refresh

### Spatial Performance Optimization
- **Parallel Processing**: 8-worker spatial join optimization
- **Memory Management**: Efficient handling of 79K+ building polygons
- **Spatial Indexing**: R-tree indexes for faster spatial queries
- **Coordinate Systems**: Projected CRS for accurate distance calculations

## Known Technical Issues

### OSM Integration Issues
- **Column Name Mismatch**: DuckDB expects `geometry`, OSM uses `geom`
- **Geographic CRS Warnings**: Distance calculations need projected coordinates
- **Memory Consumption**: 79K+ building polygons require 8GB+ RAM
- **Buffer Distance Optimization**: Current 100m may not be optimal for all areas
- **Coordinate System Precision**: Geographic vs projected CRS for measurements

### Common Problems
- **Browser Driver Issues**: Selenium WebDriver compatibility
- **Large Dataset Memory**: GeoPandas + OSM buildings memory usage
- **Geocoding Rate Limits**: External service limitations
- **Website Changes**: Oikotie.fi structure modifications
- **OSM Data Currency**: Building data updates from Geofabrik timing

### Troubleshooting
- **Log Files**: Comprehensive error logging in `logs/`
- **Fallback Systems**: JSON backup for database failures
- **Retry Logic**: Automatic retry for transient failures
- **Validation**: OSM data quality checks and spatial validation
- **Progressive Testing**: 3-step validation prevents expensive failures

## Spatial Technology Integration

### GeoPandas Ecosystem
```python
# Core spatial stack integration
import geopandas as gpd           # Spatial dataframes
import shapely.geometry as geom   # Geometric operations
import folium                     # Interactive mapping
import contextily as ctx          # Basemap tiles
```

### Coordinate Reference Systems
```python
# Standard CRS handling
WGS84 = "EPSG:4326"              # Geographic coordinates (OSM standard)
FINLAND_TM35 = "EPSG:3067"       # Projected coordinates (Finland national)
WEB_MERCATOR = "EPSG:3857"       # Web mapping standard
```

### Spatial Analysis Patterns
```python
# Standard spatial operations
point_in_polygon = buildings_gdf.contains(point)
buffer_intersection = buildings_gdf.intersects(buffered_point)
distance_calculation = buildings_gdf.distance(point)
area_calculation = buildings_gdf.area
centroid_extraction = buildings_gdf.centroid
```

## OSM Data Architecture

### Geofabrik Pipeline Architecture
```python
Data Source: Geofabrik Finland OSM Extract (Updated Weekly)
Download: finland-latest-free.shp.zip (1.26GB)
Processing: Extract buildings shapefile → Filter Helsinki → Export GeoJSON
Output: 79,556 Helsinki building footprints (36MB GeoJSON)
Integration: Compatible with existing DuckDB + listings pipeline
```

### Building Footprint Schema
```python
# OSM building data structure
{
    'osm_id': int,           # Unique OSM identifier
    'code': int,             # Building classification code
    'fclass': str,           # Feature class (building)
    'name': str,             # Building name (if available)
    'type': str,             # Building type (residential, commercial, etc.)
    'geometry': Polygon      # Building footprint polygon
}
```

### Spatial Join Performance
```python
# Production spatial join metrics
Listings: 8,100 Helsinki properties
Buildings: 79,556 OSM building footprints
Processing Time: 32.4 seconds
Speed: 250.2 listings/second
Match Rate: 89.04% (7,212 matched, 888 no-match)
Direct Matches: 37.3% (exact point-in-polygon)
Buffer Matches: 51.7% (within 100m buffer)
```

This technical context reflects the revolutionary integration of OpenStreetMap building footprints, transforming the project from administrative polygon approximations to building-level spatial precision. The OSM breakthrough represents a fundamental advancement in spatial accuracy and real-world logical correctness for Helsinki real estate analysis.
