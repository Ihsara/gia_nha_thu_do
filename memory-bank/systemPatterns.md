# System Patterns: Oikotie Architecture

## System Architecture

### High-Level Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Scraper   │    │  Data Pipeline  │    │  Visualization  │
│   (Selenium)    │───▶│   (Processing)  │───▶│   (Dashboard)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Raw Listings  │    │   DuckDB Store  │    │   Folium Maps   │
│   (JSON/HTML)   │    │   (Analytics)   │    │   (Interactive) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Components

#### 1. Data Collection Layer
- **OikotieScraper**: Main scraping orchestrator
- **DatabaseManager**: Data persistence and retrieval
- **Worker Pattern**: Multi-threaded scraping for performance

#### 2. Data Processing Layer
- **Geolocation Module**: Address geocoding and standardization
- **Road Data Integration**: Helsinki open data processing
- **Data Enrichment**: Combining multiple data sources

#### 3. Storage Layer
- **DuckDB**: Analytics-optimized database
- **JSON Fallback**: Backup storage for raw data
- **File System**: Organized output and logging

#### 4. Analysis Layer
- **Jupyter Notebooks**: Interactive data exploration
- **Visualization Scripts**: Automated map generation
- **Statistics Pipeline**: Data quality and metrics

## Key Technical Decisions

### Database Choice: DuckDB
**Decision**: Use DuckDB instead of PostgreSQL/SQLite
**Rationale**: 
- Analytics-optimized for OLAP workloads
- Excellent performance for geospatial queries
- Embedded deployment (no server required)
- Native Python integration
- Columnar storage for large datasets

### Web Scraping: Selenium
**Decision**: Selenium over requests/BeautifulSoup
**Rationale**:
- Handles JavaScript-heavy modern web pages
- Better resilience to anti-bot measures
- Cookie consent automation
- Dynamic content loading support

### Concurrency Pattern: Worker Pool
**Decision**: Multi-threaded workers for detail scraping
**Rationale**:
- I/O bound operations benefit from threading
- Configurable worker count for rate limiting
- Fault isolation between workers
- Progress tracking and error handling

### Data Pipeline: Script-Based
**Decision**: Python scripts over frameworks like Airflow
**Rationale**:
- Simpler deployment and maintenance
- Academic/research environment friendly
- Lower infrastructure requirements
- Easier debugging and modification

## Design Patterns

### 1. Strategy Pattern
- **Context**: Different scraping strategies per city
- **Implementation**: Configurable URL patterns and parsing rules
- **Location**: `config/config.json` and scraper orchestration

### 2. Builder Pattern
- **Context**: Complex database schema creation
- **Implementation**: `DatabaseManager.create_table()`
- **Benefit**: Flexible schema evolution

### 3. Worker Pool Pattern
- **Context**: Parallel detail page scraping
- **Implementation**: `worker_scrape_details()` functions
- **Benefit**: Controlled concurrency and resource management

### 4. Repository Pattern
- **Context**: Data access abstraction
- **Implementation**: `DatabaseManager` class
- **Benefit**: Clean separation of business logic and data access

### 5. Pipeline Pattern
- **Context**: Data processing workflow
- **Implementation**: Prepare → Scrape → Enrich → Visualize
- **Benefit**: Clear data flow and error handling

### 6. Monitoring Pattern
- **Context**: Long-running spatial processing tasks
- **Implementation**: Real-time progress tracking with checkpoints
- **Location**: `create_property_polygon_visualization_with_monitoring.py`
- **Benefit**: Process monitoring, ETA calculations, resumable operations

### 7. Git Workflow Pattern
- **Context**: Professional Python development practices
- **Implementation**: Feature branches, conventional commits, atomic changes
- **Location**: `.clinerules/git-workflow.md`
- **Benefit**: Version control, collaboration, code quality assurance

## Component Relationships

### Core Dependencies
```
ScraperOrchestrator
├── OikotieScraper (1:1)
├── DatabaseManager (1:1)
└── Worker Pool (1:N)

DatabaseManager
├── DuckDB Connection (1:1)
├── Schema Management (1:1)
└── Data Validation (1:1)

Geolocation Module
├── GeoPy Integration (1:1)
├── Address Parsing (1:N)
└── Database Updates (1:1)
```

### Data Flow
1. **Configuration** → ScraperOrchestrator
2. **URL Generation** → OikotieScraper
3. **Summary Scraping** → Listing URLs
4. **Detail Scraping** → Worker Pool
5. **Data Storage** → DatabaseManager
6. **Geocoding** → Geolocation Module
7. **Enrichment** → Helsinki Data Integration
8. **Visualization** → Analysis Scripts

## Critical Implementation Paths

### 1. Scraping Reliability
- **Error Handling**: Try-catch blocks with fallback strategies
- **Rate Limiting**: Configurable delays and worker limits
- **Session Management**: Cookie handling and connection pooling
- **Data Validation**: Schema enforcement and type checking

### 2. Performance Optimization
- **Parallel Processing**: Multi-threaded detail scraping
- **Database Optimization**: Columnar storage and indexing
- **Memory Management**: Streaming data processing
- **Caching**: Geocoding results and static data

### 3. Data Quality Assurance
- **Geocoding Validation**: Address matching confidence scores
- **Data Consistency**: Cross-reference validation
- **Error Tracking**: Comprehensive logging and monitoring
- **Backup Systems**: JSON fallback for database failures

### 4. Extensibility Points
- **City Configuration**: JSON-based scraping parameters
- **Schema Evolution**: Flexible database table creation
- **Output Formats**: Multiple export options
- **Analysis Integration**: Jupyter notebook compatibility

## Technology Stack Rationale

### Core Technologies
- **Python 3.9+**: Mature ecosystem for data processing
- **Selenium 4.18+**: Modern web automation
- **DuckDB 0.10+**: Analytics database
- **GeoPandas 0.14+**: Geospatial data processing
- **Folium 0.15+**: Interactive mapping

### Supporting Libraries
- **BeautifulSoup**: HTML parsing and data extraction
- **Loguru**: Structured logging
- **Pandas**: Data manipulation and analysis
- **GeoPy**: Geocoding services integration
- **UV**: Modern Python dependency management
