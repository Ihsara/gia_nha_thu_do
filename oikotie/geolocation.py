import duckdb
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time
import random

from geopy.geocoders import Nominatim
from loguru import logger

DB_PATH = Path("data/real_estate.duckdb")


def get_db_connection():
    """Establishes and returns a connection to the DuckDB database."""
    return duckdb.connect(database=str(DB_PATH), read_only=False)


def setup_database_tables():
    """Ensures the necessary tables for storing geocoded data exist."""
    with get_db_connection() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS postal_code_locations (
                postal_code VARCHAR PRIMARY KEY,
                lat DOUBLE,
                lon DOUBLE
            );
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS address_locations (
                address VARCHAR PRIMARY KEY,
                lat DOUBLE,
                lon DOUBLE
            );
        """)
    logger.info("Database tables for geolocation are set up.")


def geocode_location(geolocator, query, location_type, max_retries=3):
    """Geocodes a single location query with retry logic."""
    for attempt in range(max_retries):
        try:
            time.sleep(random.uniform(1.1, 2.5))  # Be respectful with a random delay
            location = geolocator.geocode(query, timeout=10)
            if location:
                return query, location.latitude, location.longitude
            else:
                logger.warning(f"Could not find coordinates for {location_type}: {query}")
                return query, None, None
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {location_type} '{query}': {e}")
            if attempt + 1 == max_retries:
                logger.error(f"Final attempt failed for {location_type} '{query}'.")
                return query, None, None
            time.sleep(2 ** attempt)  # Exponential backoff
    return query, None, None


def parallel_geocode(queries, location_type):
    """
    Performs geocoding for a list of queries in parallel.
    """
    results = []
    geolocator = Nominatim(user_agent=f"oikotie_geocoder_{location_type}/1.1") # Updated user agent

    with ThreadPoolExecutor(max_workers=2) as executor: # Reduced workers
        futures = {executor.submit(geocode_location, geolocator, query, location_type): query for query in queries}
        for future in as_completed(futures):
            query = futures[future]
            try:
                _, lat, lon = future.result()
                if lat and lon:
                    results.append((query, lat, lon))
            except Exception as e:
                logger.error(f"A geocoding task for {query} failed: {e}")
    return results


def update_postal_code_locations():
    """
    Finds missing postal codes, geocodes them, and updates the database.
    """
    with get_db_connection() as con:
        missing_codes = con.execute("""
            SELECT DISTINCT postal_code
            FROM listings
            WHERE postal_code IS NOT NULL
            AND postal_code NOT IN (SELECT postal_code FROM postal_code_locations)
        """).df()['postal_code'].tolist()

        if not missing_codes:
            logger.info("No new postal codes to geocode.")
            return

        logger.info(f"Found {len(missing_codes)} new postal codes to geocode.")
        geocoded_data = parallel_geocode(missing_codes, "postal code")

        if geocoded_data:
            con.executemany(
                "INSERT INTO postal_code_locations (postal_code, lat, lon) VALUES (?, ?, ?)",
                geocoded_data
            )
            logger.success(f"Successfully added {len(geocoded_data)} new postal code locations to the database.")


def update_address_locations():
    """
    Finds missing addresses, geocodes them, and updates the database.
    """
    with get_db_connection() as con:
        missing_addresses = con.execute("""
            SELECT DISTINCT address
            FROM listings
            WHERE address IS NOT NULL
            AND address NOT IN (SELECT address FROM address_locations)
        """).df()['address'].tolist()

        if not missing_addresses:
            logger.info("No new addresses to geocode.")
            return

        logger.info(f"Found {len(missing_addresses)} new addresses to geocode.")
        geocoded_data = parallel_geocode(missing_addresses, "address")

        if geocoded_data:
            con.executemany(
                "INSERT INTO address_locations (address, lat, lon) VALUES (?, ?, ?)",
                geocoded_data
            )
            logger.success(f"Successfully added {len(geocoded_data)} new address locations to the database.")

