import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
import duckdb

# Add the project root to the path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from oikotie.geolocation import (
    get_db_connection,
    setup_database_tables,
    geocode_location,
    parallel_geocode,
    update_postal_code_locations,
    update_address_locations,
)


@pytest.fixture
def db_connection(tmp_path):
    """Fixture for a DuckDB connection to a temporary database."""
    db_path = tmp_path / "test_geo.duckdb"
    with patch('oikotie.geolocation.DB_PATH', db_path):
        con = duckdb.connect(database=str(db_path), read_only=False)
        # Setup initial listings table for testing
        con.execute("""
            CREATE TABLE listings (
                postal_code VARCHAR,
                address VARCHAR
            );
        """)
        con.execute("INSERT INTO listings VALUES ('00100', 'Test Address 1'), ('00200', 'Test Address 2'), (NULL, NULL);")
        yield con
        con.close()


def test_setup_database_tables(db_connection):
    """Test that the geolocation tables are created correctly."""
    setup_database_tables()
    tables = db_connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {table[0] for table in tables}
    assert 'postal_code_locations' in table_names
    assert 'address_locations' in table_names


@patch('oikotie.geolocation.Nominatim')
def test_geocode_location_success(mock_nominatim):
    """Test a successful geocoding lookup."""
    mock_geolocator = MagicMock()
    mock_location = MagicMock()
    mock_location.latitude = 60.1
    mock_location.longitude = 24.9
    mock_geolocator.geocode.return_value = mock_location
    mock_nominatim.return_value = mock_geolocator

    query = "00100, Helsinki, Finland"
    result_query, lat, lon = geocode_location(mock_geolocator, query, "postal code")

    assert result_query == query
    assert lat == 60.1
    assert lon == 24.9
    mock_geolocator.geocode.assert_called_once_with(query, timeout=10)


@patch('oikotie.geolocation.Nominatim')
def test_geocode_location_failure(mock_nominatim):
    """Test a failed geocoding lookup."""
    mock_geolocator = MagicMock()
    mock_geolocator.geocode.return_value = None
    mock_nominatim.return_value = mock_geolocator

    query = "Invalid Place"
    result_query, lat, lon = geocode_location(mock_geolocator, query, "address")

    assert result_query == query
    assert lat is None
    assert lon is None


@patch('oikotie.geolocation.geocode_location')
def test_parallel_geocode(mock_geocode_location):
    """Test that geocoding runs in parallel."""
    mock_geocode_location.side_effect = [
        ("00100", 60.1, 24.9),
        ("00200", 60.2, 25.0),
    ]
    queries = ["00100", "00200"]
    results = parallel_geocode(queries, "postal code")

    assert len(results) == 2
    assert ("00100", 60.1, 24.9) in results
    assert ("00200", 60.2, 25.0) in results


def test_update_postal_code_locations(db_connection):
    """Test finding and updating missing postal codes."""
    setup_database_tables()
    with patch('oikotie.geolocation.parallel_geocode') as mock_parallel_geocode:
        mock_parallel_geocode.return_value = [("00100", 60.1, 24.9), ("00200", 60.2, 25.0)]
        
        update_postal_code_locations()

        # Verify that the geocoded data was inserted
        res = db_connection.execute("SELECT COUNT(*) FROM postal_code_locations").fetchone()[0]
        assert res == 2

        # Run again and ensure it doesn't re-geocode
        mock_parallel_geocode.reset_mock()
        update_postal_code_locations()
        mock_parallel_geocode.assert_not_called()


def test_update_address_locations(db_connection):
    """Test finding and updating missing addresses."""
    setup_database_tables()
    with patch('oikotie.geolocation.parallel_geocode') as mock_parallel_geocode:
        mock_parallel_geocode.return_value = [("Test Address 1", 60.1, 24.9), ("Test Address 2", 60.2, 25.0)]

        update_address_locations()

        res = db_connection.execute("SELECT COUNT(*) FROM address_locations").fetchone()[0]
        assert res == 2

        # Run again and ensure it doesn't re-geocode
        mock_parallel_geocode.reset_mock()
        update_address_locations()
        mock_parallel_geocode.assert_not_called()
