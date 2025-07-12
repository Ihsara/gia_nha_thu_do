# Helsinki GeoPackage Data Documentation

## Overview

The Helsinki topographic GeoPackage (`maastotietokanta_kaikki_Helsinki.gpkg`) contains 128 layers of comprehensive geodata for Helsinki. This documentation provides a complete reference for all layers, their purposes, and usage examples.

## Data Source Details

- **File**: `data/open/maastotietokanta_kaikki_Helsinki.gpkg`
- **Size**: 176.33 MB
- **Layers**: 128 (94 with data, 34 empty)
- **Native CRS**: EPSG:3067 (Finnish National Coordinate System)
- **Target CRS**: EPSG:4326 (WGS84) - automatically transformed on load
- **Coverage**: Complete Helsinki metropolitan area

## Key Layers for Real Estate Analysis

### Building Data (Primary)
| Table Name | Finnish Name | Records | Geometry | Description |
|------------|--------------|---------|----------|-------------|
| `gpkg_buildings` | rakennus | 59,426 | Polygon | Building footprints with attributes |
| `gpkg_building_edges` | rakennusreunaviiva | 63,288 | LineString | Building edge lines |
| `gpkg_address_points` | osoitepiste | 475 | Point | Address point locations |

### Transportation Infrastructure
| Table Name | Finnish Name | Records | Geometry | Description |
|------------|--------------|---------|----------|-------------|
| `gpkg_roads` | tieviiva | 39,822 | LineString | Road network |
| `gpkg_railways` | rautatie | 2,940 | LineString | Railway lines |
| `gpkg_traffic_areas` | autoliikennealue | 370 | Polygon | Traffic areas (parking, etc.) |

### Land Use
| Table Name | Finnish Name | Records | Geometry | Description |
|------------|--------------|---------|----------|-------------|
| `gpkg_parks` | puisto | 327 | Polygon | Park areas |
| `gpkg_recreation_areas` | urheilujavirkistysalue | 410 | Polygon | Sports and recreation areas |
| `gpkg_cemeteries` | hautausmaa | 11 | Polygon | Cemetery areas |
| `gpkg_agricultural_land` | maatalousmaa | 229 | Polygon | Agricultural areas |

### Water Features
| Table Name | Finnish Name | Records | Geometry | Description |
|------------|--------------|---------|----------|-------------|
| `gpkg_lakes` | jarvi | 44 | Polygon | Lakes |
| `gpkg_rivers` | virtavesialue | 31 | Polygon | River areas |
| `gpkg_sea_areas` | meri | 24 | Polygon | Sea areas |
| `gpkg_pools` | allas | 98 | Polygon | Pools and ponds |

### Topography
| Table Name | Finnish Name | Records | Geometry | Description |
|------------|--------------|---------|----------|-------------|
| `gpkg_contour_lines` | korkeuskayra | 9,577 | LineString | Elevation contour lines |
| `gpkg_rock_areas` | kallioalue | 3,970 | Polygon | Rock and bedrock areas |

## Column Mappings

### Building Tables (gpkg_buildings)
| Finnish Column | English Column | Type | Description |
|----------------|----------------|------|-------------|
| mtk_id | feature_id | Integer | Unique feature identifier |
| kayttotarkoitus | building_use_code | Integer | Building use classification code |
| kerrosluku | floor_count | Integer | Number of floors |
| rakennustunnus | building_id | String | Building registry ID |
| sijaintitarkkuus | location_accuracy | Float | Location accuracy in meters |
| alkupvm | start_date | Date | Feature creation date |
| geometry | geometry | Polygon | Building footprint geometry |

### Common Columns (All Tables)
| Finnish Column | English Column | Type | Description |
|----------------|----------------|------|-------------|
| mtk_id | feature_id | Integer | Unique feature identifier |
| kohderyhma | feature_group | Integer | Feature group classification |
| kohdeluokka | feature_class | Integer | Feature class within group |
| sijaintitarkkuus | location_accuracy | Float | Location accuracy in meters |
| aineistolahde | data_source | String | Data source identifier |
| alkupvm | start_date | Date | Feature creation date |
| geometry | geometry | Various | Spatial geometry |

## Building Use Codes (kayttotarkoitus)

Common building use codes in the data:
- **011**: Detached houses
- **012**: Row houses
- **013**: Apartment buildings  
- **021**: Office buildings
- **031**: Retail buildings
- **041**: Industrial buildings
- **111**: Public buildings
- **121**: Educational buildings
- **131**: Healthcare facilities
- **999**: Other/Unknown

## Usage Examples

### Find All Residential Buildings
```sql
SELECT 
    feature_id,
    building_use_code,
    floor_count,
    ST_Area(geometry) as area_sqm
FROM gpkg_buildings
WHERE building_use_code BETWEEN 11 AND 19
LIMIT 100;
```

### Spatial Join with Addresses
```sql
SELECT 
    b.feature_id,
    b.building_use_code,
    b.floor_count,
    a.address_text,
    a.postal_code
FROM gpkg_buildings b
LEFT JOIN gpkg_address_points a
    ON ST_Contains(b.geometry, a.geometry)
WHERE b.building_use_code = 13  -- Apartment buildings
LIMIT 10;
```

### Find Buildings Near Roads
```sql
SELECT 
    b.feature_id,
    b.building_use_code,
    COUNT(r.feature_id) as nearby_roads
FROM gpkg_buildings b
JOIN gpkg_roads r
    ON ST_DWithin(b.geometry, r.geometry, 0.0001)  -- ~10 meters
GROUP BY b.feature_id, b.building_use_code
HAVING COUNT(r.feature_id) > 2
LIMIT 20;
```

### Analyze Building Density by Area
```sql
WITH building_stats AS (
    SELECT 
        ST_Envelope(geometry) as bbox,
        COUNT(*) as building_count,
        SUM(CASE WHEN floor_count > 3 THEN 1 ELSE 0 END) as tall_buildings
    FROM gpkg_buildings
    GROUP BY ST_SnapToGrid(geometry, 0.01)  -- ~1km grid
)
SELECT 
    building_count,
    tall_buildings,
    tall_buildings::float / building_count as tall_ratio
FROM building_stats
WHERE building_count > 10
ORDER BY building_count DESC;
```

## Data Quality Notes

### Strengths
- **Complete coverage**: All buildings in Helsinki included
- **Accurate geometries**: High-quality polygon data
- **Rich attributes**: Building use codes, floor counts, IDs
- **Topographic context**: Roads, water, land use layers
- **Professional quality**: Official national topographic data

### Limitations
- **Limited addresses**: Only 475 address points (use WMS for addresses)
- **Finnish language**: Original column names in Finnish
- **Update frequency**: Static snapshot, not real-time
- **Building details**: Limited attribute data (no materials, year built, etc.)

## Integration with WMS Data

### Recommended Hybrid Approach
1. **Primary**: Use GeoPackage for building geometries (polygons)
2. **Enrichment**: Use WMS for detailed addresses and attributes
3. **Fallback**: Use WMS when specific building data not in GeoPackage

### Example Hybrid Query
```python
# Get building polygon from GeoPackage
building = gpd.read_postgis(
    "SELECT * FROM gpkg_buildings WHERE feature_id = 12345",
    con=engine,
    geom_col='geometry'
)

# Get address from WMS
wms_source = WMSDataSource()
addresses = wms_source.fetch_addresses(
    bbox=building.total_bounds,
    limit=10
)

# Combine data
building['address'] = addresses.iloc[0]['address_text']
```

## Performance Considerations

### Query Optimization
- **Spatial indexes**: Automatically created on geometry columns
- **Bounding box filters**: Always use ST_MakeEnvelope for area queries
- **Join order**: Filter large tables before spatial joins
- **Grid snapping**: Use ST_SnapToGrid for density analysis

### Recommended Indexes
```sql
-- Already created during load
CREATE INDEX idx_gpkg_buildings_geometry ON gpkg_buildings USING GIST(geometry);
CREATE INDEX idx_gpkg_buildings_use_code ON gpkg_buildings(building_use_code);
CREATE INDEX idx_gpkg_roads_geometry ON gpkg_roads USING GIST(geometry);
```

## Complete Layer Reference

See [GeoPackage Loading Report](../../output/geopackage_loading_report.json) for complete list of all 128 layers with record counts and geometry types.

### Categories
- **Buildings & Infrastructure**: 5 layers
- **Transportation**: 11 layers  
- **Water Features**: 18 layers
- **Land Use**: 20 layers
- **Topography**: 15 layers
- **Administrative**: 8 layers
- **Utilities**: 12 layers
- **Natural Features**: 25 layers
- **Symbols & Markers**: 14 layers

## Maintenance Notes

### Loading Process
- Script: `oikotie/scripts/prepare/load_all_geopackage_layers.py`
- Duration: ~20 seconds for all layers
- Automatic CRS transformation: EPSG:3067 → EPSG:4326
- Column renaming: Finnish → English

### Updates
- Check for new GeoPackage releases quarterly
- Reload all layers to capture updates
- Verify column mappings still valid
- Update documentation if schema changes

## Related Documentation

- [Finnish National WMS Data](finnish_national_data.md)
- [Data Source Integration Guide](../integration/data_sources.md)
- [Spatial Analysis Examples](../examples/spatial_analysis.md)
