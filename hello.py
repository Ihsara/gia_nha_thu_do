import json
import time
import re
from urllib.parse import urljoin
import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from loguru import logger

# --- Loguru Configuration ---
# Clear default handlers and set up new ones for file and console
logger.remove()
log_path = Path("logs") / "scraper_{time:YYYY-MM-DD}.log"
logger.add(log_path, rotation="1 day", retention="7 days", level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}")
logger.add(lambda msg: print(msg, end=""), colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")


def normalize_key(key_text):
    """Normalizes a string to be used as a JSON key."""
    return key_text.strip().lower().replace(' ', '_').replace('ä', 'a').replace('ö', 'o')

class OikotieScraper:
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self.setup_driver()

    def setup_driver(self):
        """Initializes the Chrome WebDriver."""
        logger.debug("Setting up Chrome WebDriver.")
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 15)
            logger.info("Chrome WebDriver initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize WebDriver: {e}")
            self.close_driver()
            raise

    def close_driver(self):
        """Closes the WebDriver session."""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed.")

    def save_debug_info(self, failure_context):
        """Saves page HTML and a screenshot for debugging."""
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        safe_context = re.sub(r'[\\/*?:"<>|]', "", failure_context)
        debug_path = Path("debug")
        debug_path.mkdir(exist_ok=True)
        html_filename = debug_path / f"{safe_context}_{timestamp}.html"
        screenshot_filename = debug_path / f"{safe_context}_{timestamp}.png"
        
        try:
            with open(html_filename, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            self.driver.save_screenshot(str(screenshot_filename))
            logger.debug(f"Saved debug info: {html_filename} and {screenshot_filename}")
        except Exception as e:
            logger.error(f"Could not save debug info: {e}")

    def accept_cookies(self):
        """Handles the cookie banner."""
        logger.info("Looking for cookie banner...")
        try:
            iframe = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[id^='sp_message_iframe']")))
            self.driver.switch_to.frame(iframe)
            logger.debug("Switched to cookie iframe.")
            
            accept_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Hyväksy kaikki']")))
            accept_button.click()
            
            logger.success("Cookies accepted.")
            self.driver.switch_to.default_content()
            time.sleep(2)
        except TimeoutException:
            logger.warning("Cookie banner not found or timed out. Continuing...")
            self.driver.switch_to.default_content()
        except Exception as e:
            logger.error(f"Error accepting cookies: {e}")
            self.driver.switch_to.default_content()
            self.save_debug_info("cookie_error")

    def scrape_all_listings_for_city(self, city_url):
        """Scrapes all listings from all pages for a given city URL."""
        all_listings = []
        logger.info("Initiating scrape for all pages...")
        self.driver.get(city_url)
        self.accept_cookies()

        page_num = 1
        while True:
            logger.info(f"Scraping page {page_num}...")
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[class*="cards-v2"]')))
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                current_page_listings = self._extract_listing_summaries(soup)
                if not current_page_listings:
                    logger.warning(f"No listings found on page {page_num}. Ending scrape.")
                    break
                
                all_listings.extend(current_page_listings)
                logger.success(f"Found {len(current_page_listings)} listings on page {page_num}. Total so far: {len(all_listings)}")

                if not self._go_to_next_page():
                    logger.info("No more pages found. Concluding summary extraction.")
                    break
                page_num += 1
                time.sleep(3)

            except Exception as e:
                logger.error(f"An error occurred on page {page_num}: {e}")
                self.save_debug_info(f"page_scrape_error_{page_num}")
                break
        
        return all_listings
    
    def _extract_listing_summaries(self, soup):
        """Extracts listing summaries from the search page."""
        listings = []
        listing_cards = soup.select('a.ot-card-v2')
        for card in listing_cards:
            listing = {'source': 'oikotie'}
            listing['url'] = urljoin('https://asunnot.oikotie.fi', card.get('href', ''))
            title_elem = card.select_one('.card-v2-text-container__text strong')
            if title_elem and listing['url']:
                listing['title'] = title_elem.get_text(strip=True)
                listings.append(listing)
        return listings

    def scrape_listing_details(self, listings):
        """Enriches a list of listing summaries with detailed information."""
        logger.info(f"Starting detail scraping for {len(listings)} listings.")
        for i, listing in enumerate(listings):
            logger.info(f"Processing details for: {listing['url']} ({i+1}/{len(listings)})")
            try:
                self.driver.get(listing['url'])
                self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "details-grid")))
                time.sleep(1)
                
                detail_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                details_data, overview, description = self._parse_oikotie_details_page(detail_soup)
                
                listing['details'] = details_data
                listing['overview'] = overview
                listing['full_description'] = description

            except Exception as e:
                logger.error(f"Failed to scrape details for {listing['url']}: {e}")
                self.save_debug_info(f"detail_failure_{i}")
                listing['details'] = {"error": "Failed to scrape details."}
        return listings
    
    def _parse_oikotie_details_page(self, soup):
        """Parses the detailed information and description from a listing page."""
        details = {}
        for item in soup.select('.info-table__row, .key-value-items__item, .details-grid__item dl'):
            key_elem = item.select_one('dt, .info-table__title, .key-value-items__title')
            value_elem = item.select_one('dd, .info-table__value, .key-value-items__value')
            if key_elem and value_elem:
                key = normalize_key(key_elem.get_text(strip=True))
                value = value_elem.get_text(strip=True, separator='\n').replace('\u00a0', ' ').strip()
                if key:
                    details[key] = value

        overview = self._get_text_from_element(soup, 'div.listing-overview')
        full_description = self._get_text_from_element(soup, 'div[class*="listing-description"]')
            
        return details, overview, full_description

    def _get_text_from_element(self, soup, selector):
        """Safely gets formatted text from a Beautiful Soup element."""
        element = soup.select_one(selector)
        if element:
            return '\n\n'.join([p.get_text(strip=True) for p in element.find_all('p', recursive=False)])
        return ""
        
    def _go_to_next_page(self):
        """Navigates to the next page, if available."""
        try:
            next_button_xpath = "//button[.//span[text()='Seuraava']]"
            next_button = self.driver.find_element(By.XPATH, next_button_xpath)
            if next_button.is_enabled():
                self.driver.execute_script("arguments[0].click();", next_button)
                logger.debug("Clicked 'next page' button.")
                return True
            else:
                logger.info("'Next page' button is disabled.")
                return False
        except NoSuchElementException:
            logger.info("'Next page' button not found.")
            return False

def load_config(config_path='config.json'):
    """Loads scraping tasks from the configuration file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get('tasks', [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.critical(f"Error loading config file: {e}")
        return []

def save_results(city, listings):
    """Saves the scraped listings to a structured JSON file."""
    if not listings:
        logger.warning(f"No listings to save for {city}.")
        return

    today = time.strftime('%Y/%m/%d')
    output_dir = Path("output") / city / today
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = output_dir / f"{city}_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json_data = {
                'city': city,
                'total_listings': len(listings),
                'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'listings': listings
            }
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        logger.success(f"Successfully saved {len(listings)} listings for {city} to {filename}")
    except Exception as e:
        logger.error(f"Failed to save results to {filename}: {e}")

def main():
    """Main function to run the scraper based on the config file."""
    tasks = load_config()
    if not tasks:
        logger.error("No tasks found in config.json. Exiting.")
        return

    for task in tasks:
        city = task.get("city")
        url = task.get("url")
        enabled = task.get("enabled", False)

        if not enabled:
            logger.info(f"Skipping disabled task for city: {city}")
            continue

        if not city or not url:
            logger.warning(f"Skipping task due to missing 'city' or 'url': {task}")
            continue
            
        logger.info(f"--- Starting task for city: {city} ---")
        scraper = OikotieScraper(headless=True)
        try:
            listing_summaries = scraper.scrape_all_listings_for_city(url)
            if listing_summaries:
                detailed_listings = scraper.scrape_listing_details(listing_summaries)
                save_results(city, detailed_listings)
            else:
                logger.warning(f"No listings found for {city}. No details will be scraped.")
        except Exception as e:
            logger.critical(f"A critical error occurred during the task for {city}: {e}")
        finally:
            scraper.close_driver()
            logger.info(f"--- Task for city: {city} finished ---")

if __name__ == "__main__":
    main()