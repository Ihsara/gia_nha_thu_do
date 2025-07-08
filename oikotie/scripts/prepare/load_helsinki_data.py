import geopandas as gpd
import pandas as pd
import duckdb
import os
from loguru import logger

# --- Configuration ---
DB_PATH = 'data/real_estate.duckdb'
HELSINKI_DATA_DIR = 'data/open/helsinki'
FILES_TO_LOAD = [
    '01_RajamerkinSijaintitiedot.json',
    '02_KiinteistorajanSijaintitiedot.json',
    '03_KiinteistotunnuksenSijaintitiedot.json',
    '04_MaaraalanOsanSijaintitiedot.json',
    '05_ProjisoidunPalstanKiinteistotunnuksenSijaintitiedot.json',
    '06_ProjisoidunPalstanSijaintitiedot.json',
    '07_PalstanSijaintitiedot.json'
]

# --- Loguru Configuration ---
logger.remove()
log_path = "logs/load_helsinki_data_{time:YYYY-MM-DD}.log"
logger.add(log_path, rotation="1 day", retention="7 days", level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}")
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")

def process_and_load_file(file_path, con):
    """Reads a GeoJSON file, converts geometry to WKT, and loads it into DuckDB."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        logger.warning(f"File is empty or does not exist, skipping: {file_path}")
        return

    table_name = f"helsinki_{os.path.basename(file_path).split('.')[0].lower()}"
    logger.info(f"Processing file '{os.path.basename(file_path)}' into table '{table_name}'...")

    try:
        gdf = gpd.read_file(file_path)
        
        if 'geometry' not in gdf.columns:
            logger.warning(f"No geometry column found in {file_path}, skipping.")
            return

        # Convert geometry to WKT for storing in DuckDB
        gdf['geometry_wkt'] = gdf['geometry'].apply(lambda geom: geom.wkt if geom else None)
        df_to_insert = pd.DataFrame(gdf.drop(columns='geometry'))

        # Create or replace the table and insert data
        con.execute(f"DROP TABLE IF EXISTS {table_name};")
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df_to_insert;")
        
        logger.success(f"Successfully loaded {len(df_to_insert)} records into '{table_name}'.")

    except Exception as e:
        logger.warning(f"Skipping file {file_path} due to an error: {e}")

def main():
    """Main function to run the data loading process."""
    if not os.path.isdir(HELSINKI_DATA_DIR):
        logger.error(f"Data directory not found: {HELSINKI_DATA_DIR}")
        return

    try:
        with duckdb.connect(DB_PATH) as con:
            for file_name in FILES_TO_LOAD:
                file_path = os.path.join(HELSINKI_DATA_DIR, file_name)
                process_and_load_file(file_path, con)
    except Exception as e:
        logger.critical(f"A critical failure occurred during the database operation: {e}")

if __name__ == "__main__":
    main()
