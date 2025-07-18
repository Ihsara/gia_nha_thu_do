# Polygon Processing Bugs

## Overview
This file documents bugs related to spatial geometry operations, coordinate transformations, and GIS data processing in the Oikotie project.

**Category Focus Areas:**
- Spatial geometry operations (contains, intersects, buffer)
- Coordinate reference system (CRS) transformations  
- GeoJSON parsing and conversion errors
- Shapely geometry manipulation issues
- Distance calculations and spatial joins

## Bug Statistics
- **Total Bugs**: 0
- **Active Bugs**: 0  
- **Resolved Bugs**: 0
- **Last Updated**: 2025-07-11

## Active Bugs
*No active polygon processing bugs currently documented*

## Resolved Bugs
*No resolved polygon processing bugs currently documented*

## Common Patterns and Prevention

### Known Issue Types
- CRS mismatch warnings in geographic coordinate systems
- Distance calculations in unprojected coordinates
- Polygon containment edge cases
- Buffer operations with invalid geometries

### Prevention Strategies
- Always validate CRS before spatial operations
- Use projected coordinate systems for distance calculations
- Implement robust geometry validation
- Add comprehensive spatial join testing

### Related Files
- `oikotie/visualization/dashboard/enhanced.py` - Main spatial processing
- `tests/validation/test_10_samples.py` - Spatial join validation
- Data files: `data/helsinki_buildings_*.geojson`

---
*Use the bug template from .clinerules/error-documentation-system.md when documenting new polygon processing bugs.*
