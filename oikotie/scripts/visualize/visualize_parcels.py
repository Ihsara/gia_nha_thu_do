import duckdb
import geopandas as gpd
import pandas as pd
import folium
from shapely import wkt
from loguru import logger
import os
import webbrowser

# --- Configuration ---
DB_PATH = 'data/real_estate.duckdb'
TABLE_NAME = 'helsinki_07_palstansijaintitiedot'
SAMPLE_SIZE = 10
OUTPUT_DIR = 'output'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'helsinki_parcels_map.html')

# --- Loguru Configuration ---
logger.remove()
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")

def get_sample_polygons():
    """Connects to the database and retrieves a random sample of polygons."""
    logger.info(f"Connecting to database at: {DB_PATH}")
    try:
        with duckdb.connect(DB_PATH, read_only=True) as con:
            tables_df = con.execute("SHOW TABLES;").fetchdf()
            if TABLE_NAME not in tables_df['name'].tolist():
                logger.error(f"Table '{TABLE_NAME}' not found in the database.")
                return None

            # Fetch a random sample of polygons and their identifiers
            query = f"SELECT geometry_wkt, kiinteistotunnuksenEsitysmuoto FROM {TABLE_NAME} USING SAMPLE {SAMPLE_SIZE} ROWS;"
            df = con.execute(query).fetchdf()

    except duckdb.Error as e:
        logger.critical(f"A database error occurred: {e}")
        return None

    if df.empty or 'geometry_wkt' not in df.columns:
        logger.warning("No polygon data found in the sample.")
        return None

    df['geometry'] = df['geometry_wkt'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry')
    gdf.crs = "EPSG:3067"
    
    logger.success(f"Successfully loaded and converted {len(gdf)} sample polygons.")
    return gdf

def visualize_interactive_map(gdf):
    """Visualizes the GeoDataFrame of polygons on an interactive Folium map."""
    if gdf is None or gdf.empty:
        logger.warning("No data to visualize.")
        return

    logger.info("Generating interactive map...")
    
    # Reproject to WGS84 (EPSG:4326) for Folium
    gdf_wgs84 = gdf.to_crs(epsg=4326)

    # Calculate the center of the map
    map_center = gdf_wgs84.geometry.union_all().centroid.coords[0][::-1]
    
    # Create a Folium map
    m = folium.Map(location=map_center, zoom_start=15, tiles="CartoDB positron")

    # Add polygons to the map with tooltips
    for _, row in gdf_wgs84.iterrows():
        sim_geo = gpd.GeoSeries(row['geometry']).to_json()
        tooltip_text = f"Property ID: {row['kiinteistotunnuksenEsitysmuoto']}"
        geo = folium.GeoJson(data=sim_geo,
                             style_function=lambda x: {'fillColor': 'lightblue', 'color': 'red', 'weight': 2},
                             tooltip=tooltip_text)
        geo.add_to(m)

    # Fit map to the bounds of the geometries
    m.fit_bounds(m.get_bounds())

    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Save the map to an HTML file
    m.save(OUTPUT_FILE)
    logger.success(f"Interactive map saved to: {OUTPUT_FILE}")

    # Open the map in a new browser tab
    try:
        webbrowser.open(f'file://{os.path.realpath(OUTPUT_FILE)}')
        logger.info("Opening map in a new browser tab...")
    except Exception as e:
        logger.error(f"Could not open browser: {e}")

def main():
    """Main function to run the visualization process."""
    sample_gdf = get_sample_polygons()
    visualize_interactive_map(sample_gdf)

if __name__ == "__main__":
    main()