import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import duckdb
import json
from bs4 import BeautifulSoup

# Add the project root to the path so that we can import the scraper
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from oikotie.scraper import DatabaseManager, OikotieScraper, normalize_key


@pytest.fixture
def db_manager(tmp_path):
    """Fixture for a DatabaseManager instance using a temporary database."""
    db_path = tmp_path / "test_db.duckdb"
    manager = DatabaseManager(db_path=str(db_path))
    return manager


class TestDatabaseManager:
    def test_create_table(self, db_manager):
        """Test that the listings table is created correctly."""
        with duckdb.connect(str(db_manager.db_path)) as con:
            res = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='listings'").fetchone()
            assert res is not None, "Table 'listings' should be created."

    def test_save_listings_success(self, db_manager):
        """Test saving a list of valid listings."""
        listings = [
            {
                'url': 'http://example.com/1', 'source': 'oikotie', 'title': 'Test Listing 1',
                'overview': 'Overview 1', 'full_description': 'Desc 1',
                'details': {
                    'sijainti': 'Test address 1, 00100 Helsinki',
                    'rakennuksen_tyyppi': 'Kerrostalo',
                    'velaton_hinta': '100 000 €',
                    'asuinpinta-ala': '50 m²',
                    'huoneita': '2',
                    'rakennusvuosi': '2000'
                }
            }
        ]
        db_manager.save_listings(listings, "Helsinki")
        with duckdb.connect(str(db_manager.db_path)) as con:
            res = con.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            assert res == 1

            data = con.execute("SELECT * FROM listings").fetchdf()
            assert data['price_eur'][0] == 100000.0
            assert data['size_m2'][0] == 50.0
            assert data['rooms'][0] == 2
            assert data['year_built'][0] == 2000

    def test_save_listings_empty(self, db_manager):
        """Test that saving an empty list does nothing."""
        db_manager.save_listings([], "Helsinki")
        with duckdb.connect(str(db_manager.db_path)) as con:
            res = con.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            assert res == 0

    def test_clean_and_convert(self, db_manager):
        """Test the internal data cleaning utility."""
        assert db_manager._clean_and_convert("123,45 €", 'float') == 123.45
        assert db_manager._clean_and_convert("100 m²", 'int') == 100
        assert db_manager._clean_and_convert(None, 'float') is None
        assert db_manager._clean_and_convert("Invalid", 'int') is None
        assert db_manager._clean_and_convert("2 500 000 €", 'float') == 2500000.0
        assert db_manager._clean_and_convert("100 000 €", 'float') == 100000.0


def test_normalize_key():
    assert normalize_key("  Velaton hinta  ") == "velaton_hinta"
    assert normalize_key("Asuinpinta-ala") == "asuinpinta-ala"
    assert normalize_key("Rakennusvuosi") == "rakennusvuosi"


def test_parse_listing_summaries():
    """Test parsing the main listings page for summary cards."""
    html_content = """
    <html><body>
        <a href="/myytavat-asunnot/helsinki/123" class="ot-card-v2">
            <div class="card-v2-text-container__text"><strong>Beautiful Apartment</strong></div>
        </a>
        <a href="/myytavat-asunnot/helsinki/456" class="ot-card-v2">
            <div class="card-v2-text-container__text"><strong>Cozy Studio</strong></div>
        </a>
    </body></html>
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    scraper = OikotieScraper(headless=True) # We need an instance to call the method
    summaries = scraper._parse_listing_summaries(soup)
    assert len(summaries) == 2
    assert summaries[0]['url'] == 'https://asunnot.oikotie.fi/myytavat-asunnot/helsinki/123'
    assert summaries[0]['title'] == 'Beautiful Apartment'


def test_parse_oikotie_details_page():
    """Test parsing the details from a single listing page."""
    html_content = """
    <html><body>
            <div class="details-grid__item">
                <dl><dt>My Key</dt><dd>My Value</dd></dl>
            </div>
        </body></html>
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    with patch('oikotie.scraper.OikotieScraper._init_driver', return_value=(MagicMock(), MagicMock())):
        scraper = OikotieScraper(headless=True)
        details, _, _ = scraper._parse_oikotie_details_page(soup)
        assert 'my_key' in details
        assert details['my_key'] == 'My Value'