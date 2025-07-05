import duckdb
from pathlib import Path
from loguru import logger
import pandas as pd

DB_PATH = Path("data/real_estate.duckdb")

def main():
    """
    Connects to the database and prints out a status report.
    """
    if not DB_PATH.exists():
        logger.error(f"Database file not found at: {DB_PATH}")
        return

    logger.info(f"--- Database Status Report for {DB_PATH} ---")

    try:
        with duckdb.connect(database=str(DB_PATH), read_only=True) as con:
            # 1. Total Listings
            total_listings = con.execute("SELECT COUNT(*) FROM listings WHERE deleted_ts IS NULL").fetchone()[0]
            logger.info(f"Total Active Listings: {total_listings}")

            # 2. Listings per City
            city_counts = con.execute("""
                SELECT city, COUNT(*) as count 
                FROM listings 
                WHERE deleted_ts IS NULL 
                GROUP BY city
            """).df()
            logger.info("Listings per City:")
            print(city_counts.to_string(index=False))

            # 3. Geocoded Data Counts
            geocoded_postal_codes = con.execute("SELECT COUNT(*) FROM postal_code_locations").fetchone()[0]
            geocoded_addresses = con.execute("SELECT COUNT(*) FROM address_locations").fetchone()[0]
            logger.info(f"Geocoded Postal Codes: {geocoded_postal_codes}")
            logger.info(f"Geocoded Addresses: {geocoded_addresses}")

            # 4. Random Sample of 10 Listings
            logger.info("--- Random Sample of 10 Listings ---")
            random_sample = con.execute("""
                SELECT title, address, price_eur, size_m2 
                FROM listings 
                WHERE deleted_ts IS NULL 
                USING SAMPLE 10 ROWS
            """).df()
            pd.set_option('display.max_colwidth', 60)
            print(random_sample.to_string())
            
            logger.info("--- End of Report ---")

    except duckdb.Error as e:
        logger.critical(f"An error occurred while querying the database: {e}")

if __name__ == "__main__":
    main()
