import duckdb
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import contextily as cx
from shapely import wkt
from loguru import logger
import os

# --- Configuration ---
DB_PATH = 'data/real_estate.duckdb'
TABLE_NAME = 'helsinki_07_palstansijaintitiedot'
SAMPLE_SIZE = 10
OUTPUT_DIR = 'output'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'helsinki_parcels_visualization.png')

# --- Loguru Configuration ---
logger.remove()
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")

def get_sample_polygons():
    """Connects to the database and retrieves a random sample of polygons."""
    logger.info(f"Connecting to database at: {DB_PATH}")
    try:
        with duckdb.connect(DB_PATH, read_only=True) as con:
            # Check if the table exists
            tables_df = con.execute("SHOW TABLES;").fetchdf()
            if TABLE_NAME not in tables_df['name'].tolist():
                logger.error(f"Table '{TABLE_NAME}' not found in the database.")
                return None

            # Fetch a random sample of polygons
            query = f"SELECT geometry_wkt FROM {TABLE_NAME} USING SAMPLE {SAMPLE_SIZE} ROWS;"
            df = con.execute(query).fetchdf()

    except duckdb.Error as e:
        logger.critical(f"A database error occurred: {e}")
        return None

    if df.empty or 'geometry_wkt' not in df.columns:
        logger.warning("No polygon data found in the sample.")
        return None

    # Convert WKT strings to geometry objects
    df['geometry'] = df['geometry_wkt'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry')
    gdf.crs = "EPSG:3067"  # Set the original CRS for the data
    
    logger.success(f"Successfully loaded and converted {len(gdf)} sample polygons.")
    return gdf

def visualize_polygons(gdf):
    """Visualizes the GeoDataFrame of polygons on a map."""
    if gdf is None or gdf.empty:
        logger.warning("No data to visualize.")
        return

    logger.info("Generating plot...")
    fig, ax = plt.subplots(1, 1, figsize=(12, 12))

    # Project to Web Mercator for plotting with contextily
    gdf_web_mercator = gdf.to_crs(epsg=3857)
    
    # Plot the polygons
    gdf_web_mercator.plot(ax=ax, alpha=0.7, edgecolor='red', facecolor='lightblue', linewidth=2)

    # Add a basemap
    cx.add_basemap(ax, source=cx.providers.CartoDB.Positron)

    ax.set_title(f'Random Sample of {SAMPLE_SIZE} Parcels in Helsinki')
    ax.set_axis_off()

    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Save the plot
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches='tight')
    logger.success(f"Plot saved to: {OUTPUT_FILE}")
    plt.show()

def main():
    """Main function to run the visualization process."""
    sample_gdf = get_sample_polygons()
    visualize_polygons(sample_gdf)

if __name__ == "__main__":
    main()
