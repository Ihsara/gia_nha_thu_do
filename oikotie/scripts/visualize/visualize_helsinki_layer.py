import duckdb
import geopandas as gpd
import pandas as pd
import folium
from shapely import wkt
from loguru import logger
import os
import webbrowser
import argparse
import random

# --- Configuration ---
DB_PATH = 'data/real_estate.duckdb'
SAMPLE_SIZE = 100
OUTPUT_DIR = 'output'
TABLE_DESCRIPTIONS = {
    "helsinki_01_rajamerkinsijaintitiedot": "Boundary marker locations",
    "helsinki_02_kiinteistorajansijaintitiedot": "Property boundary locations",
    "helsinki_03_kiinteistotunnuksensijaintitiedot": "Property ID locations",
    "helsinki_04_maaraalanosansijaintitiedot": "Sub-area locations",
    "helsinki_07_palstansijaintitiedot": "Parcel locations",
    "helsinki_buildings": "Building footprints",
    "helsinki_properties": "Filtered Helsinki properties"
}

# --- Loguru Configuration ---
logger.remove()
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")

def list_available_tables(con):
    """Lists all available Helsinki data tables with their descriptions."""
    logger.info("Available Helsinki data tables:")
    tables_df = con.execute("SHOW TABLES;").fetchdf()
    for table_name in tables_df['name'].tolist():
        if table_name.startswith('helsinki_'):
            description = TABLE_DESCRIPTIONS.get(table_name, "No description available.")
            print(f"- {table_name}: {description}")

def get_sample_data(table_name, con):
    """Retrieves a random sample from the specified table."""
    query = f"SELECT * FROM {table_name} USING SAMPLE {SAMPLE_SIZE} ROWS;"
    df = con.execute(query).fetchdf()
    if df.empty or 'geometry_wkt' not in df.columns:
        return None
    df['geometry'] = df['geometry_wkt'].apply(wkt.loads)
    return gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:3067")

def visualize_interactive_map(gdf_dict):
    """Visualizes one or more GeoDataFrames on an interactive Folium map."""
    if not gdf_dict:
        logger.warning("No data to visualize.")
        return

    logger.info("Generating interactive map...")
    
    # Combine all GeoDataFrames to calculate the center and bounds
    all_gdfs = pd.concat(gdf_dict.values(), ignore_index=True)
    all_gdfs_wgs84 = all_gdfs.to_crs(epsg=4326)
    map_center = all_gdfs_wgs84.geometry.union_all().centroid.coords[0][::-1]
    
    m = folium.Map(location=map_center, zoom_start=13, tiles="CartoDB positron")
    
    # Define a color palette
    colors = ['#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00','#ffff33', '#a65628']
    color_map = {name: color for name, color in zip(gdf_dict.keys(), colors)}

    for name, gdf in gdf_dict.items():
        gdf_wgs84 = gdf.to_crs(epsg=4326)
        feature_group = folium.FeatureGroup(name=name)
        
        for _, row in gdf_wgs84.iterrows():
            tooltip_html = "".join([f"<b>{key}:</b> {value}<br>" for key, value in row.drop('geometry').items()])
            
            folium.GeoJson(
                row['geometry'],
                style_function=lambda x, color=color_map[name]: {'fillColor': color, 'color': color, 'weight': 2},
                tooltip=folium.Tooltip(tooltip_html)
            ).add_to(feature_group)
        
        feature_group.add_to(m)

    folium.LayerControl().add_to(m)
    m.fit_bounds(m.get_bounds())

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = os.path.join(OUTPUT_DIR, "map_all_helsinki_layers.html")
    m.save(output_file)
    logger.success(f"Interactive map saved to: {output_file}")

    try:
        webbrowser.open(f'file://{os.path.realpath(output_file)}')
        logger.info("Opening map in a new browser tab...")
    except Exception as e:
        logger.error(f"Could not open browser: {e}")

def main():
    """Main function to run the visualization process."""
    parser = argparse.ArgumentParser(description="Visualize Helsinki data layers from the database.")
    parser.add_argument("table_name", nargs='?', default=None, help="The name of the table to visualize, or 'all' to visualize all layers.")
    args = parser.parse_args()

    with duckdb.connect(DB_PATH, read_only=True) as con:
        if not args.table_name:
            list_available_tables(con)
            return

        gdf_dict = {}
        if args.table_name.lower() == 'all':
            logger.info("Loading samples from all available Helsinki tables...")
            tables_df = con.execute("SHOW TABLES;").fetchdf()
            for table in tables_df['name'].tolist():
                if table.startswith('helsinki_'):
                    gdf = get_sample_data(table, con)
                    if gdf is not None:
                        gdf_dict[table] = gdf
        else:
            gdf = get_sample_data(args.table_name, con)
            if gdf is not None:
                gdf_dict[args.table_name] = gdf
        
        visualize_interactive_map(gdf_dict)

if __name__ == "__main__":
    main()
