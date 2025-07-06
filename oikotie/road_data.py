import duckdb
from pathlib import Path
from loguru import logger
import requests
import geopandas as gpd
from shapely.geometry import mapping

DB_PATH = Path("output/real_estate.duckdb")

# WFS endpoint for Digiroad data
WFS_URL = "https://www.paikkatietohakemisto.fi/wfs/digiroad"

def get_db_connection():
    """Establishes and returns a connection to the DuckDB database."""
    return duckdb.connect(database=str(DB_PATH), read_only=False)

def setup_road_table():
    """Ensures the 'roads' table exists in the database."""
    with get_db_connection() as con:
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute("""
            CREATE TABLE IF NOT EXISTS roads (
                id VARCHAR PRIMARY KEY,
                geom GEOMETRY
            );
        """)
    logger.info("Database table 'roads' is set up.")

def download_and_store_road_data():
    """
    Downloads road network data for Uusimaa using WFS and stores it in DuckDB.
    """
    with get_db_connection() as con:
        count = con.execute("SELECT COUNT(*) FROM roads").fetchone()[0]
        if count > 0:
            logger.info("Road data already exists. Skipping download.")
            return

    logger.info("Downloading road data via WFS...")
    
    # Parameters for the WFS GetFeature request
    params = {
        'service': 'WFS',
        'version': '2.0.0',
        'request': 'GetFeature',
        'typeName': 'dr_tieosoiteviiva', # Layer name for road addresses
        'outputFormat': 'application/json',
        'srsName': 'EPSG:3067',
        # BBOX for Uusimaa region to limit the request
        'bbox': '24.0,60.0,26.0,60.5,EPSG:4326' 
    }

    try:
        response = requests.get(WFS_URL, params=params)
        response.raise_for_status()
        geojson_data = response.json()

        if not geojson_data or 'features' not in geojson_data or not geojson_data['features']:
            logger.warning("No road features returned from WFS request.")
            return

        logger.info(f"Downloaded {len(geojson_data['features'])} road features.")

        # Use GeoPandas to simplify processing
        gdf = gpd.GeoDataFrame.from_features(geojson_data['features'])
        
        # Prepare data for insertion
        # The 'id' can be derived from properties, e.g., 'link_id' or another unique identifier
        # Here we will use the 'id' field from the properties if it exists, otherwise generate one
        if 'id' not in gdf.columns:
            gdf['id'] = range(len(gdf))

        # Convert geometries to WKB (Well-Known Binary) for storage
        gdf['geom_wkb'] = gdf['geometry'].apply(lambda g: g.wkb)
        
        records_to_insert = gdf[['id', 'geom_wkb']].values.tolist()

        with get_db_connection() as con:
            con.execute("INSTALL spatial; LOAD spatial;")
            con.executemany("INSERT INTO roads (id, geom) VALUES (?, ?)", records_to_insert)
            logger.success(f"Successfully loaded {len(records_to_insert)} roads into the database.")

    except requests.RequestException as e:
        logger.critical(f"Failed to download road data from WFS: {e}")
    except Exception as e:
        logger.critical(f"An unexpected error occurred during road data processing: {e}")

if __name__ == '__main__':
    setup_road_table()
    download_and_store_road_data()
