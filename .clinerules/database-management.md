# Database Management Rules for Oikotie Project

## Brief overview
Database management rules for the Oikotie project establishing mandatory procedures for DuckDB schema documentation, migration management, data integrity validation, and single database approach standards.

## Single DuckDB Database Strategy

### Database Architecture Requirements
- **Single DuckDB Instance**: `data/real_estate.duckdb` is the sole database for the project
- **No SQLite Dependencies**: All SQLite references must be removed from codebase
- **Centralized Data Storage**: All real estate, spatial, and address data in one database
- **Connection Standardization**: Use unified connection utilities from `oikotie.database`

### DuckDB Advantages and Justification
- **Columnar Storage**: Optimized for analytical queries on large datasets
- **Spatial Extensions**: Native PostGIS-compatible spatial operations
- **Performance**: Superior query performance for real estate data analysis
- **File-based**: Single file database suitable for development and deployment
- **SQL Compatibility**: Standard SQL with advanced analytical functions

## Schema Documentation Standards

### Core Tables Documentation (MANDATORY)
```sql
-- PRIMARY DATA TABLES
listings (8,725 rows)
├── address TEXT (FK → address_locations.address)
├── price REAL  
├── listing_type TEXT
├── latitude REAL
├── longitude REAL
├── geometry GEOMETRY(POINT, 4326)
└── listing_date DATE

osm_buildings (79,556 rows) 
├── osm_id BIGINT PRIMARY KEY
├── geometry GEOMETRY(POLYGON, 4326) 
├── building_type TEXT
├── name TEXT
├── addr_street TEXT
├── addr_housenumber TEXT
└── addr_postcode TEXT

address_locations (6,643 rows)
├── address TEXT PRIMARY KEY
├── latitude REAL
├── longitude REAL  
├── postcode TEXT
├── district TEXT
└── geometry GEOMETRY(POINT, 4326)

-- ADMINISTRATIVE DATA TABLES  
helsinki_property_boundaries
├── boundary_id TEXT PRIMARY KEY
├── boundary_type TEXT
├── geometry GEOMETRY(POLYGON, 4326)
└── properties JSON

helsinki_admin_markers  
├── marker_id TEXT PRIMARY KEY
├── marker_type TEXT
├── geometry GEOMETRY(POINT, 4326)
└── properties JSON
```

### Relationship Documentation (MANDATORY)
```sql
-- PRIMARY RELATIONSHIPS
listings.address = address_locations.address (Many-to-One)
-- Spatial relationships (computed):
listings.geometry WITHIN osm_buildings.geometry (Spatial Join)
address_locations.geometry WITHIN helsinki_property_boundaries.geometry (Spatial Join)
```

### Index Strategy (MANDATORY)
```sql
-- Spatial Indexes (Critical for Performance)
CREATE INDEX idx_listings_geometry ON listings USING GIST(geometry);
CREATE INDEX idx_osm_buildings_geometry ON osm_buildings USING GIST(geometry);
CREATE INDEX idx_address_locations_geometry ON address_locations USING GIST(geometry);

-- Primary Key Indexes (Auto-created)
CREATE INDEX idx_osm_buildings_osm_id ON osm_buildings(osm_id);
CREATE INDEX idx_address_locations_address ON address_locations(address);

-- Query Optimization Indexes
CREATE INDEX idx_listings_address ON listings(address);
CREATE INDEX idx_listings_listing_type ON listings(listing_type);
CREATE INDEX idx_osm_buildings_building_type ON osm_buildings(building_type);
```

## Data Integrity Rules

### Primary Key Constraints (MANDATORY)
- **osm_buildings.osm_id**: Must be unique, non-null OpenStreetMap identifier
- **address_locations.address**: Must be unique, non-null address string
- **helsinki_property_boundaries.boundary_id**: Must be unique administrative boundary ID
- **helsinki_admin_markers.marker_id**: Must be unique administrative marker ID

### Foreign Key Constraints (MANDATORY)
- **listings.address**: Must reference existing address_locations.address
- **Referential Integrity**: All address references must be valid
- **Orphan Prevention**: No listings without corresponding address_locations

### Spatial Data Constraints (MANDATORY)
- **Coordinate Reference System**: All geometries must use EPSG:4326 (WGS84)
- **Geometry Validation**: All geometries must be valid using ST_IsValid()
- **Geometry Types**: Enforce specific geometry types per table
  - listings.geometry: POINT only
  - osm_buildings.geometry: POLYGON or MULTIPOLYGON only  
  - address_locations.geometry: POINT only

### Data Quality Constraints (MANDATORY)
- **Non-empty Geometries**: All geometry fields must be non-null and non-empty
- **Coordinate Bounds**: Coordinates must be within Helsinki metropolitan area bounds
  - Latitude: 60.0 to 60.5 degrees
  - Longitude: 24.5 to 25.5 degrees
- **Price Validation**: Listing prices must be positive numbers
- **Date Validation**: Listing dates must be valid dates not in the future

## Migration Procedures

### Database Schema Migration Workflow
1. **Schema Backup**: Always backup current schema before changes
2. **Migration Scripts**: Create versioned migration scripts in `oikotie/database/migrations/`
3. **Validation Testing**: Test migration on sample data before full database
4. **Rollback Plan**: Maintain rollback procedures for all schema changes

### Migration Script Standards
```python
# Migration file naming: YYYYMMDD_HHMMSS_description.py
# Example: 20250711_120000_add_building_type_index.py

def upgrade():
    """Apply migration changes"""
    pass

def downgrade():
    """Rollback migration changes"""  
    pass

def validate():
    """Verify migration success"""
    pass
```

### Data Import Procedures
- **Staging Validation**: Import new data to staging tables first
- **Quality Checks**: Run comprehensive data quality validation
- **Incremental Updates**: Support both full refresh and incremental updates
- **Conflict Resolution**: Define procedures for handling duplicate data

## Connection Management

### Connection Pooling Standards
- **Single Connection Pattern**: Use DataLoader class for consistent connections
- **Connection Reuse**: Minimize connection overhead through pooling
- **Error Handling**: Robust connection error handling and retry logic
- **Resource Cleanup**: Ensure proper connection cleanup and resource management

### Database Configuration
```python
# Standard database configuration
DATABASE_CONFIG = {
    'path': 'data/real_estate.duckdb',
    'read_only': False,
    'enable_spatial': True,
    'memory_limit': '2GB',
    'threads': 4
}
```

### Connection Security
- **Local File Access**: Database file must be accessible to application
- **Backup Procedures**: Regular automated backups to prevent data loss
- **Version Control**: Never commit database files to version control
- **Access Control**: Limit database file permissions for security

## Performance Optimization

### Query Optimization Standards
- **Spatial Index Usage**: Always use spatial indexes for geometry operations
- **Query Planning**: Use EXPLAIN ANALYZE for complex query optimization
- **Batch Operations**: Prefer batch operations over individual row operations
- **Memory Management**: Monitor memory usage for large analytical queries

### Cache Strategy
- **Query Result Caching**: Cache expensive spatial join results
- **Geometry Preprocessing**: Cache preprocessed geometry calculations
- **Index Warming**: Warm spatial indexes after database startup
- **Cache Invalidation**: Clear caches when underlying data changes

## Monitoring and Maintenance

### Database Health Monitoring
- **Table Statistics**: Regular UPDATE STATISTICS for query optimization
- **Index Usage Analysis**: Monitor index effectiveness and usage patterns
- **Query Performance**: Track slow queries and optimization opportunities
- **Storage Monitoring**: Monitor database file size and growth patterns

### Maintenance Procedures
- **Regular VACUUM**: Optimize database storage and performance
- **Index Maintenance**: Rebuild spatial indexes when performance degrades
- **Schema Validation**: Regular validation of data integrity constraints
- **Backup Verification**: Verify backup integrity and restoration procedures

## Development Workflow Integration

### Code Integration Requirements
- **Schema Changes**: All schema changes must update documentation
- **Migration Scripts**: Required for all database structure changes
- **Test Data**: Maintain test data that reflects production schema
- **Documentation Sync**: Keep schema documentation current with codebase

### Testing Standards
- **Unit Tests**: Test all database operations and edge cases
- **Integration Tests**: Test complete workflows with real database
- **Performance Tests**: Benchmark critical queries and operations
- **Migration Testing**: Test all migration scripts with sample data

## Error Handling and Recovery

### Common Error Patterns
- **Connection Failures**: Handle database file locks and access issues
- **Spatial Query Errors**: Handle invalid geometries and projection errors
- **Import Errors**: Handle malformed data and constraint violations
- **Performance Issues**: Handle memory limits and query timeouts

### Recovery Procedures
- **Database Corruption**: Steps for database file recovery and validation
- **Index Corruption**: Procedures for rebuilding corrupted spatial indexes
- **Data Inconsistency**: Scripts for detecting and fixing data integrity issues
- **Backup Restoration**: Tested procedures for restoring from backups

## Integration with Memory Bank Workflow

### Documentation Update Triggers
- **Schema Changes**: Update Memory Bank when database schema changes
- **Performance Issues**: Document database performance patterns and solutions
- **Migration History**: Track database evolution in Memory Bank
- **Data Quality Issues**: Document recurring data quality problems and fixes

### Database Context in Memory Bank
- **Current Schema State**: Always document current schema in techContext.md
- **Active Migrations**: Track pending and completed migrations in progress.md
- **Performance Patterns**: Document query optimization patterns in systemPatterns.md
- **Data Quality Status**: Include database health status in activeContext.md

This database management system ensures reliable, performant, and maintainable database operations throughout the Oikotie project lifecycle.
