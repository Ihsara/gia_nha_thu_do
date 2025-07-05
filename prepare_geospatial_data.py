import geopandas as gpd
import pandas as pd
import duckdb
import zipfile
import os
import tempfile
import shutil
from loguru import logger

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
        
        # Find the shapefile in the extracted contents
        shapefile_path = None
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.shp'):
                    shapefile_path = os.path.join(root, file)
                    break
            if shapefile_path:
                break

        if not shapefile_path:
            raise FileNotFoundError("Could not find a shapefile in the extracted archive.")

        logger.info(f"Reading municipal boundaries from {shapefile_path}...")
        municipalities = gpd.read_file(shapefile_path)
        
        # Find the Helsinki polygon
        helsinki = municipalities[municipalities['NimiSuomi'] == HELSINKI_MUNICIPALITY_NAME]
        if helsinki.empty:
            raise ValueError(f"Could not find municipality: {HELSINKI_MUNICIPALITY_NAME}")
            
        logger.success(f"Successfully extracted the boundary for {HELSINKI_MUNICIPALITY_NAME}.")
        return helsinki.geometry.unary_union

def process_and_load_data(helsinki_boundary):
    """
    Reads the properties GeoPackage in chunks, filters for Helsinki,
    and loads the data into DuckDB.
    """
    logger.info(f"Starting to process properties from {PROPERTIES_GPKG_PATH}...")
    
    try:
        with duckdb.connect(DB_PATH) as con:
            # Drop the table if it exists to ensure a fresh start
            con.execute(f"DROP TABLE IF EXISTS {PROPERTIES_TABLE_NAME};")
            logger.info(f"Dropped existing table '{PROPERTIES_TABLE_NAME}' if it existed.")

            is_first_chunk = True
            total_rows_written = 0

            # Assuming the layer name is 'kiinteistorekisterikartta'
            # This might need adjustment if the layer name is different
            layer_name = 'kiinteistorekisterikartta' 
            
            for chunk in gpd.read_file(PROPERTIES_GPKG_PATH, layer=layer_name, chunksize=CHUNK_SIZE):
                logger.info(f"Processing a chunk of {len(chunk)} properties...")
                
                # Filter properties within the Helsinki boundary
                helsinki_properties = chunk[chunk.within(helsinki_boundary)]
                
                if not helsinki_properties.empty:
                    logger.info(f"Found {len(helsinki_properties)} properties within Helsinki in this chunk.")
                    
                    # Convert GeoDataFrame to DataFrame for DuckDB insertion
                    df_to_insert = pd.DataFrame(helsinki_properties.drop(columns='geometry'))
                    
                    if is_first_chunk:
                        # Create the table with the schema of the first chunk
                        con.execute(f"CREATE TABLE {PROPERTIES_TABLE_NAME} AS SELECT * FROM df_to_insert;")
                        is_first_chunk = False
                    else:
                        # Append to the existing table
                        con.execute(f"INSERT INTO {PROPERTIES_TABLE_NAME} SELECT * FROM df_to_insert;")
                    
                    total_rows_written += len(df_to_insert)
                    logger.info(f"Wrote {len(df_to_insert)} rows to the database. Total written: {total_rows_written}")

            logger.success(f"Finished processing. A total of {total_rows_written} properties were loaded into the '{PROPERTIES_TABLE_NAME}' table.")

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
