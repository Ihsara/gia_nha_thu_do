from oikotie.geolocation import (
    setup_database_tables,
    update_postal_code_locations,
    update_address_locations,
)
from loguru import logger


def main():
    """
    Main function to run the location preparation process.
    """
    logger.info("Starting location data preparation...")
    setup_database_tables()
    update_postal_code_locations()
    update_address_locations()
    logger.info("Location data preparation finished.")


if __name__ == "__main__":
    main()
