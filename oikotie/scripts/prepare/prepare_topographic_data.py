import geopandas as gpd
import pandas as pd
import duckdb
import zipfile
import os
import tempfile
from shapely.ops import transform
from shapely.geometry import shape
from loguru import logger
import fiona

# --- Configuration ---
DB_PATH = 'data/real_estate.duckdb'
TOPOGRAPHY_ZIP_PATH = 'data/open/L4134C.zip'
MUNICIPALITY_ZIP_PATH = 'data/open/TietoaKuntajaosta_2025_10k.zip'
HELSINKI_MUNICIPALITY_NAME = 'Helsinki'
BUILDINGS_TABLE_NAME = 'helsinki_buildings'

# --- Loguru Configuration ---
logger.remove()
log_path = "logs/prepare_topographic_{time:YYYY-MM-DD}.log"
logger.add(log_path, rotation="1 day", retention="7 days", level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}")
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")

def get_helsinki_boundary():
    """Extracts the Helsinki municipal boundary from the zip file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(MUNICIPALITY_ZIP_PATH, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
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

        municipalities = gpd.read_file(gpkg_path, layer='Kunta')
        helsinki = municipalities[municipalities['namefin'] == HELSINKI_MUNICIPALITY_NAME]
        if helsinki.empty:
            raise ValueError(f"Could not find municipality: {HELSINKI_MUNICIPALITY_NAME}")
            
        return helsinki.geometry.union_all()

def process_and_load_data(helsinki_boundary):
    """Reads the topography GML, filters for Helsinki, and loads the data into DuckDB."""
    logger.info(f"Starting to process topography data from {TOPOGRAPHY_ZIP_PATH}...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(TOPOGRAPHY_ZIP_PATH, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        gml_path = None
        for root, _, files in os.walk(temp_dir):
            for file_in_dir in files:
                if file_in_dir.endswith('.gml'):
                    gml_path = os.path.join(root, file_in_dir)
                    break
            if gml_path:
                break

        if not gml_path:
            raise FileNotFoundError("Could not find a GML file in the extracted topography archive.")

        logger.info(f"Reading topography data from {gml_path}...")
        
        try:
            features = []
            with fiona.open(gml_path, 'r') as source:
                for feature in source:
                    geom = shape(feature['geometry'])
                    geom_2d = transform(lambda x, y, z=None: (x, y), geom)
                    features.append({
                        'properties': feature['properties'],
                        'geometry': geom_2d
                    })
            
            gdf = gpd.GeoDataFrame.from_features(features)
            gdf.crs = "EPSG:3067"

            logger.info(f"Filtering {len(gdf)} features for Helsinki...")
            helsinki_buildings = gdf[gdf.within(helsinki_boundary)]
            
            if not helsinki_buildings.empty:
                logger.info(f"Found {len(helsinki_buildings)} buildings within Helsinki.")
                
                helsinki_buildings['geometry_wkt'] = helsinki_buildings['geometry'].apply(lambda geom: geom.wkt if geom else None)
                df_to_insert = pd.DataFrame(helsinki_buildings.drop(columns='geometry'))
                
                with duckdb.connect(DB_PATH) as con:
                    con.execute(f"DROP TABLE IF EXISTS {BUILDINGS_TABLE_NAME};")
                    con.execute(f"CREATE TABLE {BUILDINGS_TABLE_NAME} AS SELECT * FROM df_to_insert;")
                
                logger.success(f"Successfully loaded {len(df_to_insert)} buildings into '{BUILDINGS_TABLE_NAME}'.")
            else:
                logger.warning("No buildings found within the Helsinki boundary.")

        except Exception as e:
            logger.critical(f"An error occurred during data processing: {e}")
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
