import json
import time
import re
from urllib.parse import urljoin
from pathlib import Path
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from loguru import logger
import duckdb
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
from .utils import extract_postal_code

# --- Loguru Configuration ---
logger.remove()
log_path = Path("logs") / "scraper_{time:YYYY-MM-DD}.log"
logger.add(log_path, rotation="1 day", retention="7 days", level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}")
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
]

def normalize_key(key_text):
    return key_text.strip().lower().replace(' ', '_').replace('ä', 'a').replace('ö', 'o')

class DatabaseManager:
    # This class is robust and does not need changes.
    def __init__(self, db_path="data/real_estate.duckdb"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Database will be stored at: {self.db_path}")
        self.create_table()

    def create_table(self):
        try:
            with duckdb.connect(str(self.db_path)) as con:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS listings (
                        url VARCHAR PRIMARY KEY, 
                        source VARCHAR, 
                        city VARCHAR, 
                        title VARCHAR,
                        address VARCHAR, 
                        postal_code VARCHAR, 
                        listing_type VARCHAR, 
                        price_eur FLOAT, 
                        size_m2 FLOAT,
                        rooms INTEGER, 
                        year_built INTEGER, 
                        overview VARCHAR, 
                        full_description VARCHAR,
                        other_details_json VARCHAR, 
                        scraped_at TIMESTAMP,
                        insert_ts TIMESTAMP,
                        updated_ts TIMESTAMP,
                        deleted_ts TIMESTAMP
                    );
                """)
            logger.success("Database table 'listings' is ready.")
        except Exception as e:
            logger.critical(f"Failed to create database table: {e}")
            raise

    def _clean_and_convert(self, value_str, target_type):
        if not value_str: return None
        try:
            # Remove thousands separators, then find the first number
            cleaned_str = value_str.replace('\u00a0', '').replace(' ', '')
            # Find the first sequence of digits, possibly with a decimal comma/dot
            match = re.search(r'[\d,.]+', cleaned_str)
            if not match:
                return None
            
            # Convert comma to dot for float conversion
            num_str = match.group(0).replace(',', '.')
            
            return float(num_str) if target_type == 'float' else int(float(num_str))
        except (ValueError, TypeError):
            return None

    def save_listings(self, listings, city_name):
        if not listings:
            logger.warning("No listings provided to save.")
            return

        try:
            with duckdb.connect(str(self.db_path)) as con:
                # Start a transaction
                con.begin()

                # Get existing URLs for the current city that are not deleted
                existing_urls_in_db = set(
                    row[0] for row in con.execute(
                        "SELECT url FROM listings WHERE city = ? AND deleted_ts IS NULL", [city_name]
                    ).fetchall()
                )
                
                scraped_urls = set()
                upsert_count = 0

                for listing in listings:
                    url = listing.get('url')
                    if not url:
                        continue
                    
                    scraped_urls.add(url)
                    details = listing.get('details', {})
                    if not details or 'error' in details:
                        continue

                    address = details.get('sijainti')
                    postal_code = extract_postal_code(address) if address else None
                    
                    core_data = {
                        'price_eur': self._clean_and_convert(details.get('velaton_hinta') or details.get('myyntihinta'), 'float'),
                        'size_m2': self._clean_and_convert(details.get('asuinpinta-ala'), 'float'),
                        'rooms': self._clean_and_convert(details.get('huoneita'), 'int'),
                        'year_built': self._clean_and_convert(details.get('rakennusvuosi'), 'int'),
                    }
                    core_keys = ['sijainti', 'rakennuksen_tyyppi', 'velaton_hinta', 'myyntihinta', 'asuinpinta-ala', 'huoneita', 'rakennusvuosi']
                    other_details = {k: v for k, v in details.items() if k not in core_keys}
                    
                    params = (
                        listing.get('source'), city_name, listing.get('title'),
                        address, postal_code, details.get('rakennuksen_tyyppi'),
                        core_data['price_eur'], core_data['size_m2'], core_data['rooms'], core_data['year_built'],
                        listing.get('overview'), listing.get('full_description'),
                        json.dumps(other_details, ensure_ascii=False), 
                        time.strftime('%Y-%m-%d %H:%M:%S'), # scraped_at
                        url
                    )

                    if url in existing_urls_in_db:
                        # UPDATE existing record
                        update_query = """
                            UPDATE listings 
                            SET source=?, city=?, title=?, address=?, postal_code=?, listing_type=?, 
                                price_eur=?, size_m2=?, rooms=?, year_built=?, overview=?, 
                                full_description=?, other_details_json=?, scraped_at=?,
                                updated_ts=NOW(), deleted_ts=NULL
                            WHERE url=?"""
                        con.execute(update_query, params)
                    else:
                        # INSERT new record
                        insert_query = """
                            INSERT INTO listings (
                                source, city, title, address, postal_code, listing_type, 
                                price_eur, size_m2, rooms, year_built, overview, 
                                full_description, other_details_json, scraped_at, url, insert_ts
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())"""
                        con.execute(insert_query, params)
                    
                    upsert_count += 1

                # Soft delete listings that are no longer on the site
                urls_to_delete = existing_urls_in_db - scraped_urls
                if urls_to_delete:
                    logger.info(f"Marking {len(urls_to_delete)} listings as deleted for city: {city_name}.")
                    # Use a list of tuples for executemany
                    delete_params = [(url,) for url in urls_to_delete]
                    con.executemany("UPDATE listings SET deleted_ts = NOW() WHERE url = ?", delete_params)

                # Commit the transaction
                con.commit()
                logger.success(f"Successfully saved/updated {upsert_count} and soft-deleted {len(urls_to_delete)} listings for {city_name}.")

        except duckdb.Error as e:
            logger.critical(f"A database error occurred: {e}. Rolling back transaction.")
            if 'con' in locals() and con:
                con.rollback()
            self._save_to_fallback_json(listings, city_name)
        except Exception as e:
            logger.critical(f"An unexpected error occurred during database operations: {e}")
            if 'con' in locals() and con:
                con.rollback()
            self._save_to_fallback_json(listings, city_name)

    def _save_to_fallback_json(self, listings, city_name):
        """Saves listings to a JSON file if the database operation fails."""
        fallback_dir = Path("output/failed_saves")
        fallback_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        fallback_path = fallback_dir / f"failed_db_save_{city_name}_{timestamp}.json"
        
        logger.info(f"Saving {len(listings)} listings to fallback file: {fallback_path}")
        try:
            with open(fallback_path, 'w', encoding='utf-8') as f:
                json.dump(listings, f, ensure_ascii=False, indent=4)
            logger.success(f"Successfully saved listings to {fallback_path}.")
        except Exception as e:
            logger.error(f"Could not write to fallback JSON file: {e}")

    def load_from_json(self, file_path):
        """Loads listings from a JSON file and saves them to the database."""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                listings = json.load(f)
            
            # Assuming the city can be inferred or is generic
            # A more robust implementation might store city in the JSON file
            city_name = "loaded_from_json" 
            logger.info(f"Loaded {len(listings)} listings from {file_path}. Now saving to database.")
            self.save_listings(listings, city_name)
            
            # Rename the file to avoid reprocessing
            processed_path = path.with_name(f"{path.stem}_processed.json")
            path.rename(processed_path)
            logger.success(f"Successfully processed and renamed {path.name} to {processed_path.name}")

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to load or process JSON file {file_path}: {e}")


class OikotieScraper:
    """Represents a single scraping session with one browser instance."""
    def __init__(self, headless=True):
        self.headless = headless
        self.driver, self.wait = self._init_driver()

    def _init_driver(self):
        logger.debug("Initializing new Chrome WebDriver instance...")
        chrome_options = Options()
        if self.headless: chrome_options.add_argument('--headless')
        chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            wait = WebDriverWait(driver, 20) # Increased wait time for stability
            return driver, wait
        except Exception as e:
            logger.critical(f"Failed to initialize WebDriver: {e}")
            raise

    def close(self):
        if self.driver: self.driver.quit()

    def _accept_cookies(self):
        try:
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[id^='sp_message_iframe']")))
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Hyväksy kaikki']"))).click()
            self.driver.switch_to.default_content()
        except TimeoutException:
            logger.warning("Cookie banner not found or handled.")
            self.driver.switch_to.default_content()

    def get_all_listing_summaries(self, url, limit=None):
        logger.info(f"Initiating sequential summary scrape (limit: {limit or 'all'})...")
        self.driver.get(url)
        self._accept_cookies()
        
        all_summaries = []
        page_num = 1
        
        while not (limit and len(all_summaries) >= limit):
            logger.info(f"Scraping summary page {page_num}...")
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[class*="cards-v2"]')))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            summaries = self._parse_listing_summaries(soup)
            
            if not summaries:
                logger.warning(f"No new listings found on page {page_num}. Ending scrape.")
                break
            
            all_summaries.extend(summaries)
            
            try:
                next_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Seuraava']]"))
                )
                # Use JavaScript to click as a fallback
                self.driver.execute_script("arguments[0].click();", next_button)
                page_num += 1
                time.sleep(random.uniform(1.5, 3.0)) # Wait for next page to load
            except TimeoutException:
                logger.info("No 'Next' button found. This is the last page.")
                break
        
        return all_summaries[:limit] if limit else all_summaries

    def get_single_listing_details(self, listing_summary):
        try:
            time.sleep(random.uniform(2.0, 5.0)) # Longer, more human-like delay
            self.driver.get(listing_summary['url'])
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "details-grid")))
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            details, overview, description = self._parse_oikotie_details_page(soup)
            listing_summary.update({'details': details, 'overview': overview, 'full_description': description})
        except Exception as e:
            logger.error(f"Failed to process {listing_summary.get('url')}: {e}")
            listing_summary['details'] = {"error": str(e)}
        return listing_summary

    def _parse_listing_summaries(self, soup):
        listings = []
        for card in soup.select('a.ot-card-v2'):
            url = urljoin('https://asunnot.oikotie.fi', card.get('href', ''))
            title_elem = card.select_one('.card-v2-text-container__text strong')
            if title_elem and url:
                listings.append({'source': 'oikotie', 'url': url, 'title': title_elem.get_text(strip=True)})
        return listings

    def _parse_oikotie_details_page(self, soup):
        details, overview, full_description = {}, "", ""
        for item in soup.select('.info-table__row, .key-value-items__item, .details-grid__item dl'):
            key_elem = item.select_one('dt, .info-table__title, .key-value-items__title')
            value_elem = item.select_one('dd, .info-table__value, .key-value-items__value')
            if key_elem and value_elem:
                key = normalize_key(key_elem.get_text(strip=True))
                value = value_elem.get_text(strip=True, separator='\n').replace('\u00a0', ' ').strip()
                if key: details[key] = value
        overview = self._get_text_from_element(soup, 'div.listing-overview')
        full_description = self._get_text_from_element(soup, 'div[class*="listing-description"]')
        return details, overview, full_description
        
    def _get_text_from_element(self, soup, selector):
        element = soup.select_one(selector)
        return '\n\n'.join([p.get_text(strip=True) for p in element.find_all('p', recursive=False)]) if element else ""

    def _go_to_next_page(self):
        try:
            next_button = self.driver.find_element(By.XPATH, "//button[.//span[text()='Seuraava']]")
            if next_button.is_enabled():
                self.driver.execute_script("arguments[0].click();", next_button)
                return True
        except NoSuchElementException: return False
        return False

def worker_scrape_details(listing_summaries_chunk):
    """Worker target. Creates one browser session to process a chunk of URLs."""
    scraper = OikotieScraper(headless=True)
    results = []
    try:
        for summary in listing_summaries_chunk:
            logger.info(f"Worker processing: {summary['url']}")
            results.append(scraper.get_single_listing_details(summary))
    finally:
        scraper.close()
    return results

def load_config(config_path='config/config.json'):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f).get('tasks', [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.critical(f"Error loading config file '{config_path}': {e}")
        return []

def worker_scrape_summaries(page_urls_chunk):
    """Worker target for scraping a chunk of summary pages."""
    scraper = OikotieScraper(headless=True)
    results = []
    try:
        for page_url in page_urls_chunk:
            logger.info(f"Summary worker processing: {page_url}")
            results.extend(scraper._scrape_summary_page(page_url))
    finally:
        scraper.close()
    return results

class ScraperOrchestrator:
    """Manages the entire scraping workflow for all tasks."""
    def __init__(self, config_path='config/config.json'):
        self.tasks = load_config(config_path)
        self.db_manager = DatabaseManager()

    def run(self):
        if not self.tasks:
            logger.error("No tasks found in config.json. Exiting.")
            return

        for task in self.tasks:
            if not task.get("enabled", False):
                logger.info(f"Skipping disabled task: {task.get('city')}")
                continue

            city, url, limit, max_workers = (
                task.get("city"), task.get("url"), 
                task.get("listing_limit"), task.get("max_detail_workers", 5)
            )
            logger.info(f"--- Starting task for city: {city} ---")
            
            try:
                # Phase 1: Scrape summaries sequentially for stability
                summary_scraper = OikotieScraper(headless=True)
                listing_summaries = summary_scraper.get_all_listing_summaries(url, limit=limit)
                summary_scraper.close()

                if not listing_summaries:
                    logger.warning(f"No listings found for {city}. Task finished.")
                    continue

                # Phase 2: Scrape details in parallel
                logger.info(f"Distributing {len(listing_summaries)} URLs to {max_workers} detail workers...")
                detail_chunks = [listing_summaries[i::max_workers] for i in range(max_workers)]
                
                detailed_listings = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(worker_scrape_details, chunk) for chunk in detail_chunks]
                    for future in as_completed(futures):
                        detailed_listings.extend(future.result())
                        logger.info(f"Detail scraping progress: {len(detailed_listings)}/{len(listing_summaries)}")
                
                # Phase 3: Save results to database
                self.db_manager.save_listings(detailed_listings, city)

            except Exception as e:
                logger.critical(f"A critical error occurred during the task for {city}: {e}")
            finally:
                logger.info(f"--- Task for city: {city} finished ---")


def main():
    orchestrator = ScraperOrchestrator()
    orchestrator.run()

if __name__ == "__main__":
    main()