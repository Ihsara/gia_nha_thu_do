import duckdb
import pandas as pd
from loguru import logger

# --- Configuration ---
DB_PATH = 'data/real_estate.duckdb'

# --- Loguru Configuration ---
logger.remove()
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")

def inspect_database():
    """Connects to the database, lists tables, and inspects their contents."""
    logger.info(f"Connecting to database at: {DB_PATH}")
    try:
        with duckdb.connect(DB_PATH, read_only=True) as con:
            tables_df = con.execute("SHOW TABLES;").fetchdf()
            table_names = tables_df['name'].tolist()

            if not table_names:
                logger.warning("No tables found in the database.")
                return

            logger.info(f"Found {len(table_names)} tables: {', '.join(table_names)}")

            for table in table_names:
                logger.info(f"--- Inspecting Table: {table} ---")

                # Get table schema
                schema_df = con.execute(f"DESCRIBE {table};").fetchdf()
                logger.info(f"Schema for '{table}':")
                print(schema_df.to_string())

                # Get sample data
                sample_df = con.execute(f"SELECT * FROM {table} LIMIT 5;").fetchdf()
                logger.info(f"Sample data from '{table}':")
                
                # Check for polygon data
                if 'geometry_wkt' in sample_df.columns:
                    logger.success(f"Table '{table}' contains polygon data in the 'geometry_wkt' column.")
                    print("This column stores geospatial shapes (polygons) in Well-Known Text format.")
                    # Truncate long WKT strings for cleaner display
                    sample_df['geometry_wkt'] = sample_df['geometry_wkt'].str.slice(0, 100) + '...'
                
                print(sample_df.to_string())
                print("\n")

    except duckdb.Error as e:
        logger.critical(f"A database error occurred: {e}")
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    inspect_database()
