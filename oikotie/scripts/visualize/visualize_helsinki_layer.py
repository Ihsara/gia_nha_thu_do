import duckdb
import geopandas as gpd
import pandas as pd
import folium
from shapely import wkt
from loguru import logger
import os
import webbrowser
import argparse

# --- Configuration ---
DB_PATH = 'data/real_estate.duckdb'
SAMPLE_SIZE = 100
OUTPUT_DIR = 'output'

# --- Loguru Configuration ---
logger.remove()
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")

def get_sample_data(table_name):
    """Connects to the database and retrieves a random sample from the specified table."""
    logger.info(f"Connecting to database at: {DB_PATH}")
    try:
        with duckdb.connect(DB_PATH, read_only=True) as con:
            tables_df = con.execute("SHOW TABLES;").fetchdf()
            if table_name not in tables_df['name'].tolist():
                logger.error(f"Table '{table_name}' not found in the database.")
                return None

            # Fetch a random sample of geometries and their properties
            query = f"SELECT * FROM {table_name} USING SAMPLE {SAMPLE_SIZE} ROWS;"
            df = con.execute(query).fetchdf()

    except duckdb.Error as e:
        logger.critical(f"A database error occurred: {e}")
        return None

    if df.empty or 'geometry_wkt' not in df.columns:
        logger.warning("No 'geometry_wkt' column found in the sample.")
        return None

    df['geometry'] = df['geometry_wkt'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:3067")
    
    logger.success(f"Successfully loaded and converted {len(gdf)} sample features from '{table_name}'.")
    return gdf

def visualize_interactive_map(gdf, table_name):
    """Visualizes the GeoDataFrame on an interactive Folium map."""
    if gdf is None or gdf.empty:
        logger.warning("No data to visualize.")
        return

    logger.info("Generating interactive map...")
    
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    map_center = gdf_wgs84.geometry.union_all().centroid.coords[0][::-1]
    
    m = folium.Map(location=map_center, zoom_start=15, tiles="CartoDB positron")

    for _, row in gdf_wgs84.iterrows():
        # Create a tooltip from all available properties
        tooltip_html = "".join([f"<b>{key}:</b> {value}<br>" for key, value in row.drop('geometry').items()])
        
        folium.GeoJson(
            row['geometry'],
            tooltip=folium.Tooltip(tooltip_html)
        ).add_to(m)

    m.fit_bounds(m.get_bounds())

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = os.path.join(OUTPUT_DIR, f"map_{table_name}.html")
    m.save(output_file)
    logger.success(f"Interactive map saved to: {output_file}")

    try:
        webbrowser.open(f'file://{os.path.realpath(output_file)}')
        logger.info("Opening map in a new browser tab...")
    except Exception as e:
        logger.error(f"Could not open browser: {e}")

def main():
    """Main function to run the visualization process."""
    parser = argparse.ArgumentParser(description="Visualize a specific layer from the Helsinki data in the database.")
    parser.add_argument("table_name", type=str, help="The name of the table to visualize (e.g., 'helsinki_07_palstansijaintitiedot').")
    args = parser.parse_args()

    sample_gdf = get_sample_data(args.table_name)
    visualize_interactive_map(sample_gdf, args.table_name)

if __name__ == "__main__":
    main()
