from oikotie.scraper import main as run_scraper
from oikotie.scripts.prepare.prepare_locations import main as run_location_preparation
from oikotie.scripts.check_database_contents import main as run_status_check
from loguru import logger

def main():
    """
    Runs the full data pipeline: scraping, location preparation, and status check.
    """
    logger.info("--- Starting Daily Scraping Workflow ---")
    
    logger.info(">>> Step 1: Running the Scraper")
    try:
        run_scraper()
        logger.success(">>> Scraper finished successfully.")
    except Exception as e:
        logger.critical(f"The scraper encountered a critical error: {e}")
        return

    logger.info(">>> Step 2: Preparing Location Data")
    try:
        run_location_preparation()
        logger.success(">>> Location preparation finished successfully.")
    except Exception as e:
        logger.critical(f"Location preparation encountered a critical error: {e}")
        return

    logger.info(">>> Step 3: Checking Database Status")
    try:
        run_status_check()
        logger.success(">>> Status check finished successfully.")
    except Exception as e:
        logger.critical(f"The status check encountered a critical error: {e}")

    logger.info("--- Daily Scraping Workflow Finished ---")

if __name__ == "__main__":
    main()