import duckdb
import pytest
from pathlib import Path

DB_PATH = Path("data/real_estate.duckdb")

@pytest.fixture(scope="module")
def db_con():
    """
    Pytest fixture to connect to the DuckDB database.
    """
    con = duckdb.connect(str(DB_PATH), read_only=True)
    yield con
    con.close()

def test_national_addresses_table_exists(db_con):
    """
    Tests if the 'national_addresses' table was created.
    """
    tables = db_con.execute("SHOW TABLES").fetchall()
    assert any('national_addresses' in t for t in tables)

def test_national_buildings_table_exists(db_con):
    """
    Tests if the 'national_buildings' table was created.
    """
    tables = db_con.execute("SHOW TABLES").fetchall()
    assert any('national_buildings' in t for t in tables)

def test_national_addresses_schema(db_con):
    """
    Tests the schema of the 'national_addresses' table.
    """
    schema = db_con.execute("DESCRIBE national_addresses").fetchall()
    columns = [col[0] for col in schema]
    
    expected_columns = [
        'inspire_id_local', 'inspire_id_namespace', 'lifespan_start_version',
        'lifespan_end_version', 'street_name', 'postal_code', 'admin_unit_1',
        'admin_unit_4', 'address_number', 'address_number_extension',
        'address_number_extension_2', 'locator_level', 'position_specification',
        'position_method', 'is_position_default', 'building_id_reference',
        'parcel_id_reference', 'geometry'
    ]
    
    assert all(col in columns for col in expected_columns)

def test_national_buildings_schema(db_con):
    """
    Tests the schema of the 'national_buildings' table.
    """
    schema = db_con.execute("DESCRIBE national_buildings").fetchall()
    columns = [col[0] for col in schema]
    
    expected_columns = [
        'inspire_id_local', 'inspire_id_version', 'inspire_id_namespace',
        'ext_ref_info_system', 'ext_ref_info_system_name', 'ext_ref_reference',
        'lifespan_start_version', 'lifespan_end_version', 'construction_condition',
        'current_use_percentage', 'construction_date', 'demolition_date',
        'current_use', 'elevation_reference', 'elevation_value',
        'height_above_ground', 'floors_above_ground', 'is_2d_reference_geometry',
        'horizontal_geometry_reference', 'geometry'
    ]
    
    assert all(col in columns for col in expected_columns)
