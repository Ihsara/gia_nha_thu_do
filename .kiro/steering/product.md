---
inclusion: always
---

# Product Context & Development Guidelines

## Platform Overview
Oikotie Real Estate Analytics Platform - Finnish property data collection, geospatial enrichment, and research analytics system.

## Core Functionality
- **Data Collection**: Automated Oikotie.fi scraping with rate limiting and error recovery
- **Geospatial Enrichment**: Integration with Helsinki open data and OSM building footprints  
- **Analytics Pipeline**: Address geocoding, spatial matching, and comprehensive data validation
- **Visualization**: Interactive dashboards and map-based exploration tools

## Development Priorities (Mandatory)
1. **Data Quality First**: Always prioritize accuracy over speed in geocoding and spatial matching
2. **Testing Before Expensive Operations**: Run bug prevention tests before any operation >10 min runtime
3. **Error Handling**: Implement comprehensive logging with loguru and graceful degradation
4. **Performance**: Optimize for batch processing and large geospatial dataset operations

## Critical Technical Constraints
- **Rate Limiting**: Respect Oikotie.fi scraping limits to avoid IP blocking
- **Spatial Accuracy**: Use EPSG:3067 for Finland coordinate transformations
- **Memory Management**: Handle large geospatial datasets with chunking strategies
- **Database**: Use DuckDB only (`data/real_estate.duckdb`) - no SQLite references

## Code Standards (Enforced)
- **Type Hints**: Required for all function signatures and complex data structures
- **Error Handling**: Use specific exception types with loguru logging, never bare except blocks
- **Documentation**: Update `docs/errors/` for new errors; update relevant docs when modifying core functionality
- **Architecture**: Clear separation between data collection (`oikotie/`), processing, and visualization (`oikotie/visualization/`) layers
- **Modern CLI**: Prefer `oikotie.visualization.cli.commands` over legacy `oikotie.scripts.*`

## Quality Targets
- **Geocoding Accuracy**: >95% successful address resolution
- **Pipeline Reliability**: 99% uptime with graceful degradation
- **Testing Investment**: 10-20% time investment in testing vs pipeline failures

## AI Assistant Guidelines
- Always run validation tests before expensive operations
- Use DuckDB connection utilities from `oikotie.database`
- Prioritize modern CLI commands over legacy scripts
- Maintain data lineage and validation for research integrity
- Update error documentation when encountering new issues