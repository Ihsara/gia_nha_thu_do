import geopandas as gpd
import pandas as pd
import duckdb
import zipfile
import os
import tempfile
import shutil
from loguru import logger
import fiona

# --- Configuration ---
DB_PATH = 'data/real_estate.duckdb'
MUNICIPALITY_ZIP_PATH = 'data/open/TietoaKuntajaosta_2025_10k.zip'
PROPERTIES_GPKG_PATH = 'data/open/kiinteistorekisterikartta.gpkg'
HELSINKI_MUNICIPALITY_NAME = 'Helsinki'
PROPERTIES_TABLE_NAME = 'helsinki_properties'
CHUNK_SIZE = 100000

# --- Loguru Configuration ---
logger.remove()
log_path = "logs/prepare_geospatial_{time:YYYY-MM-DD}.log"
logger.add(log_path, rotation="1 day", retention="7 days", level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}")
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")

def get_helsinki_boundary():
    """Extracts the Helsinki municipal boundary from the zip file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Extracting {MUNICIPALITY_ZIP_PATH} to a temporary directory...")
        with zipfile.ZipFile(MUNICIPALITY_ZIP_PATH, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find the GeoPackage file in the extracted contents
        gpkg_path = None
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.gpkg'):
                    gpkg_path = os.path.join(root, file)
                    break
            if gpkg_path:
                break

        if not gpkg_path:
            raise FileNotFoundError("Could not find a GeoPackage file in the extracted archive.")

        logger.info(f"Reading municipal boundaries from {gpkg_path}...")
        municipalities = gpd.read_file(gpkg_path, layer='Kunta')
        
        # Find the Helsinki polygon
        helsinki = municipalities[municipalities['namefin'] == HELSINKI_MUNICIPALITY_NAME]
        if helsinki.empty:
            raise ValueError(f"Could not find municipality: {HELSINKI_MUNICIPALITY_NAME}")
            
        logger.success(f"Successfully extracted the boundary for {HELSINKI_MUNICIPALITY_NAME}.")
        return helsinki.geometry.union_all()

def process_and_load_data(helsinki_boundary):
    """
    Reads the properties GeoPackage, filters for Helsinki,
    and loads the data into DuckDB.
    """
    logger.info(f"Starting to process properties from {PROPERTIES_GPKG_PATH}...")
    
    try:
        with duckdb.connect(DB_PATH) as con:
            # Drop the table if it exists to ensure a fresh start
            con.execute(f"DROP TABLE IF EXISTS {PROPERTIES_TABLE_NAME};")
            logger.info(f"Dropped existing table '{PROPERTIES_TABLE_NAME}' if it existed.")

            # List layers and use the first one
            layers = fiona.listlayers(PROPERTIES_GPKG_PATH)
            if not layers:
                raise ValueError(f"No layers found in {PROPERTIES_GPKG_PATH}")
            layer_name = layers[0]
            logger.info(f"Using layer '{layer_name}' from {PROPERTIES_GPKG_PATH}")
            
            logger.info("Reading the entire GeoPackage file. This may take some time...")
            gdf = gpd.read_file(PROPERTIES_GPKG_PATH, layer=layer_name)
            
            logger.info(f"Filtering {len(gdf)} properties for Helsinki...")
            helsinki_properties = gdf[gdf.within(helsinki_boundary)]
            
            if not helsinki_properties.empty:
                logger.info(f"Found {len(helsinki_properties)} properties within Helsinki.")
                
                # Convert geometry to WKT for storing in DuckDB
                helsinki_properties['geometry_wkt'] = helsinki_properties['geometry'].apply(lambda geom: geom.wkt)
                df_to_insert = pd.DataFrame(helsinki_properties.drop(columns=['geometry']))
                
                # Create the table with the schema of the first chunk
                con.execute(f"CREATE TABLE {PROPERTIES_TABLE_NAME} AS SELECT * FROM df_to_insert;")
                logger.success(f"Finished processing. A total of {len(df_to_insert)} properties were loaded into the '{PROPERTIES_TABLE_NAME}' table.")
            else:
                logger.warning("No properties found within the Helsinki boundary.")

    except fiona.errors.DriverError as e:
        logger.critical(f"A Fiona driver error occurred: {e}. This might be due to an unsupported file format or a missing driver.")
        raise
    except Exception as e:
        logger.critical(f"An error occurred during data processing and loading: {e}")
        raise

def main():
    """Main function to run the data preparation process."""
    try:
        helsinki_boundary = get_helsinki_boundary()
        process_and_load_data(helsinki_boundary)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"A setup error occurred: {e}")
    except Exception as e:
        logger.critical(f"A critical failure occurred: {e}")

if __name__ == "__main__":
    main()
