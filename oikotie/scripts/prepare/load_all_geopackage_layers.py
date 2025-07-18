#!/usr/bin/env python3
"""
Load all layers from Helsinki GeoPackage into DuckDB.

This script loads all 128 layers from the Helsinki topographic GeoPackage
into DuckDB with standardized English table names and column mappings.
"""

import sys
from pathlib import Path
import duckdb
import geopandas as gpd
import fiona
from datetime import datetime
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from oikotie.data_sources import GeoPackageDataSource


# Finnish to English layer name mappings
LAYER_NAME_MAPPINGS = {
    # Buildings & Infrastructure
    "rakennus": "gpkg_buildings",
    "rakennusreunaviiva": "gpkg_building_edges", 
    "rakennusosa": "gpkg_building_parts",
    "osoitepiste": "gpkg_address_points",
    
    # Transportation
    "tieviiva": "gpkg_roads",
    "rautatie": "gpkg_railways",
    "autoliikennealue": "gpkg_traffic_areas",
    "katu": "gpkg_streets",
    "kevyenliikenteenvaylä": "gpkg_light_traffic_lanes",
    "ajopolku": "gpkg_driveways",
    "talvitie": "gpkg_winter_roads",
    
    # Water Features
    "jarvi": "gpkg_lakes",
    "virtavesialue": "gpkg_rivers",
    "meri": "gpkg_sea_areas",
    "allas": "gpkg_pools",
    "vesikuoppa": "gpkg_water_pits",
    "lampi": "gpkg_ponds",
    "vakavesi": "gpkg_water_bodies",
    
    # Land Use
    "maatalousmaa": "gpkg_agricultural_land",
    "urheilujavirkistysalue": "gpkg_recreation_areas",
    "hautausmaa": "gpkg_cemeteries",
    "puisto": "gpkg_parks",
    "niitty": "gpkg_meadows",
    "pelto": "gpkg_fields",
    "metsämaa": "gpkg_forest_land",
    "avokallio": "gpkg_exposed_bedrock",
    "kallioalue": "gpkg_rock_areas",
    "hietikko": "gpkg_sand_areas",
    "louhos": "gpkg_quarries",
    "soistuma": "gpkg_wetlands",
    "suo": "gpkg_swamps",
    
    # Topography
    "korkeuskayra": "gpkg_contour_lines",
    "harjuviiva": "gpkg_ridge_lines",
    "korkeusluku": "gpkg_elevation_points",
    "syvyyskayra": "gpkg_depth_contours",
    
    # Administrative
    "kunnanraja": "gpkg_municipality_borders",
    "aluemerkinta": "gpkg_area_markings",
    "rajamerkki": "gpkg_boundary_markers",
    
    # Other Features
    "rakennelma": "gpkg_structures",
    "masto": "gpkg_masts",
    "piippu": "gpkg_chimneys",
    "savupiippu": "gpkg_smoke_stacks",
    "aita": "gpkg_fences",
    "reunaviiva": "gpkg_edge_lines",
    "pato": "gpkg_dams",
    "ilmarata": "gpkg_aerial_lines",
    "portaat": "gpkg_stairs",
    "luiska": "gpkg_ramps",
}


# Common Finnish to English column mappings
COLUMN_MAPPINGS = {
    "mtk_id": "feature_id",
    "gid": "gid",
    "kohderyhma": "feature_group",
    "kohdeluokka": "feature_class",
    "gml_id": "gml_id",
    "namespace": "namespace",
    "versionid": "version_id",
    "beginlifespanversion": "lifespan_start",
    "endlifespanversion": "lifespan_end",
    "sijaintitarkkuus": "location_accuracy",
    "korkeustarkkuus": "height_accuracy",
    "aineistolahde": "data_source",
    "alkupvm": "start_date",
    "geometria_muokkauspvm": "geometry_modified_date",
    "asemakaavatunnus": "zoning_plan_id",
    "rakennustunnus": "building_id",
    "kayttotarkoitus": "building_use_code",
    "kerrosluku": "floor_count",
    "olotila": "state",
    "pinta_ala": "area",
    "korkeus": "height",
    "tienpinta": "road_surface",
    "nimi": "name",
    "nimi_suomi": "name_finnish",
    "nimi_ruotsi": "name_swedish",
    "numero": "number",
    "postinumero": "postal_code",
    "osoiteteksti": "address_text",
    "katunimi": "street_name",
    "tyyppi": "type",
    "leveys": "width",
    "materiaali": "material",
    "valmistumisvuosi": "completion_year",
    "geometry": "geometry"
}


def load_geopackage_layers(gpkg_path: str, db_path: str):
    """Load all layers from GeoPackage into DuckDB."""
    
    print("🔧 Loading Helsinki GeoPackage Layers to DuckDB")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Source: {gpkg_path}")
    print(f"Target: {db_path}")
    print()
    
    # Check if GeoPackage exists
    if not Path(gpkg_path).exists():
        print(f"❌ GeoPackage file not found: {gpkg_path}")
        return
    
    # List all layers
    print("📋 Discovering layers...")
    layers = fiona.listlayers(gpkg_path)
    print(f"Found {len(layers)} layers")
    print()
    
    # Connect to DuckDB
    con = duckdb.connect(db_path)
    
    # Enable spatial extension
    con.execute("INSTALL spatial")
    con.execute("LOAD spatial")
    
    # Track loaded layers
    loaded_layers = []
    failed_layers = []
    
    # Process each layer
    for i, layer_name in enumerate(layers, 1):
        # Get English table name
        table_name = LAYER_NAME_MAPPINGS.get(layer_name, f"gpkg_{layer_name.lower()}")
        
        print(f"[{i}/{len(layers)}] Loading {layer_name} → {table_name}")
        
        try:
            # Read layer
            gdf = gpd.read_file(gpkg_path, layer=layer_name)
            
            # Skip empty layers
            if len(gdf) == 0:
                print(f"  ⚠️  Skipping empty layer")
                continue
            
            # Transform to EPSG:4326 if needed
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                print(f"  📐 Transforming from {gdf.crs} to EPSG:4326")
                gdf = gdf.to_crs("EPSG:4326")
            
            # Rename columns to English
            rename_dict = {}
            for col in gdf.columns:
                if col in COLUMN_MAPPINGS:
                    rename_dict[col] = COLUMN_MAPPINGS[col]
            
            if rename_dict:
                gdf = gdf.rename(columns=rename_dict)
                print(f"  🔤 Renamed {len(rename_dict)} columns")
            
            # Save to temporary parquet file
            temp_file = f"temp_{table_name}.parquet"
            gdf.to_parquet(temp_file)
            
            # Load into DuckDB
            con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet('{temp_file}')")
            
            # Get record count
            count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            print(f"  ✅ Loaded {count:,} records")
            
            # Clean up temp file
            Path(temp_file).unlink()
            
            loaded_layers.append({
                "finnish_name": layer_name,
                "english_name": table_name,
                "record_count": count,
                "geometry_type": gdf.geometry.iloc[0].geom_type if len(gdf) > 0 else "Unknown"
            })
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            failed_layers.append({
                "layer_name": layer_name,
                "error": str(e)
            })
    
    print()
    print("📊 Summary:")
    print(f"  - Total layers: {len(layers)}")
    print(f"  - Successfully loaded: {len(loaded_layers)}")
    print(f"  - Failed: {len(failed_layers)}")
    
    # Save loading report
    report = {
        "timestamp": datetime.now().isoformat(),
        "source_file": gpkg_path,
        "target_database": db_path,
        "total_layers": len(layers),
        "loaded_layers": loaded_layers,
        "failed_layers": failed_layers,
        "layer_mappings": LAYER_NAME_MAPPINGS,
        "column_mappings": COLUMN_MAPPINGS
    }
    
    report_file = "output/geopackage_loading_report.json"
    Path("output").mkdir(exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Loading report saved to: {report_file}")
    
    # Show sample queries
    print("\n💡 Sample queries to test the loaded data:")
    print("-- Count buildings in Helsinki:")
    print("SELECT COUNT(*) FROM gpkg_buildings;")
    print("\n-- Find roads near a location:")
    print("SELECT * FROM gpkg_roads")
    print("WHERE ST_DWithin(geometry, ST_Point(24.94, 60.17), 0.01)")
    print("LIMIT 10;")
    print("\n-- List all available tables:")
    print("SHOW TABLES;")
    
    con.close()
    print("\n✅ GeoPackage Loading Complete")


def main():
    """Main function."""
    gpkg_path = "data/open/maastotietokanta_kaikki_Helsinki.gpkg"
    db_path = "data/real_estate.duckdb"
    
    load_geopackage_layers(gpkg_path, db_path)


if __name__ == "__main__":
    main()
