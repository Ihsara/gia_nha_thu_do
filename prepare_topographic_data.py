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
TOPOGRAPHY_ZIP_PATH = 'data/open/L4134C.zip'
MUNICIPALITY_ZIP_PATH = 'data/open/TietoaKuntajaosta_2025_10k.zip'
HELSINKI_MUNICIPALITY_NAME = 'Helsinki'
TOPOGRAPHY_TABLE_NAME = 'helsinki_topography'

# --- Loguru Configuration ---
logger.remove()
log_path = "logs/prepare_topographic_{time:YYYY-MM-DD}.log"
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
            logger.info(f"Searching in {root}: {files}")
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
    Reads the topography zip file, filters for Helsinki,
    and loads the data into DuckDB.
    """
    logger.info(f"Starting to process topography data from {TOPOGRAPHY_ZIP_PATH}...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Extracting {TOPOGRAPHY_ZIP_PATH} to a temporary directory...")
        with zipfile.ZipFile(TOPOGRAPHY_ZIP_PATH, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Find the GML file in the extracted contents
        gml_path = None
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.gml'):
                    gml_path = os.path.join(root, file)
                    break
            if gml_path:
                break

        if not gml_path:
            raise FileNotFoundError("Could not find a GML file in the extracted topography archive.")

        logger.info(f"Reading topography data from {gml_path}...")
        
        try:
            with duckdb.connect(DB_PATH) as con:
                # Drop the table if it exists to ensure a fresh start
                con.execute(f"DROP TABLE IF EXISTS {TOPOGRAPHY_TABLE_NAME};")
                logger.info(f"Dropped existing table '{TOPOGRAPHY_TABLE_NAME}' if it existed.")

                layers = fiona.listlayers(gml_path)
                logger.info(f"Found layers: {layers}")

                for layer in layers:
                    logger.info(f"Processing layer: {layer}")
                    try:
                        gdf = gpd.read_file(gml_path, layer=layer)
                    except Exception as e:
                        logger.warning(f"Skipping layer '{layer}' due to an error: {e}")
                        continue
                    
                    logger.info(f"Filtering {len(gdf)} features from layer '{layer}' for Helsinki...")
                    helsinki_features = gdf[gdf.within(helsinki_boundary)]
                    
                    if not helsinki_features.empty:
                        logger.info(f"Found {len(helsinki_features)} features within Helsinki in layer '{layer}'.")
                        
                        # Convert geometry to WKT for storing in DuckDB
                        helsinki_features['geometry_wkt'] = helsinki_features['geometry'].apply(lambda geom: geom.wkt)
                        df_to_insert = pd.DataFrame(helsinki_features.drop(columns=['geometry']))
                        
                        table_name = f"{TOPOGRAPHY_TABLE_NAME}_{layer.lower()}"
                        con.execute(f"DROP TABLE IF EXISTS {table_name};")
                        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df_to_insert;")
                        logger.success(f"Finished processing layer '{layer}'. A total of {len(df_to_insert)} features were loaded into the '{table_name}' table.")
                    else:
                        logger.warning(f"No features found within the Helsinki boundary for layer '{layer}'.")

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
