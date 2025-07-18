import geopandas as gpd
from pathlib import Path
import duckdb
import httpx
from oikotie.wms import WMSClient

# --- Configuration ---
ADDRESS_WMS_URL = "https://paikkatiedot.ymparisto.fi/geoserver/ryhti_inspire_ad/wms"
BUILDING_WMS_URL = "https://paikkatiedot.ymparisto.fi/geoserver/ryhti_inspire_bu/wms"
OUTPUT_DIR = Path("data/processed/national")
DB_PATH = Path("data/real_estate.duckdb")

# Create output directory if it doesn't exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def fetch_and_process_addresses(bbox, crs="EPSG:4326", table_suffix=""):
    """
    Fetches address data for a given bounding box, processes it, and saves it.
    """
    print(f"--- Fetching Address Data for bbox: {bbox} ---")
    
    # Fetch data using WFS GetFeature
    params = {
        'service': 'WFS',
        'version': '2.0.0',
        'request': 'GetFeature',
        'typeName': 'AD.Address',
        'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},{crs}",
        'srsName': crs,
        'outputFormat': 'application/json',
        'maxFeatures': '500'  # Limit to 500 features for medium test
    }
    
    response = httpx.get(ADDRESS_WMS_URL, params=params)
    response.raise_for_status()
    
    data = response.json()
    
    if not data.get("features"):
        print("No address features found in the specified bounding box.")
        return 0

    gdf = gpd.GeoDataFrame.from_features(data["features"])
    gdf.set_crs(crs, inplace=True)

    # --- Standardize Column Names ---
    column_mapping = {
        'inspireId_localId': 'inspire_id_local',
        'inspireId_namespace': 'inspire_id_namespace',
        'beginLifespanVersion': 'lifespan_start_version',
        'endLifespanVersion': 'lifespan_end_version',
        'component_ThoroughfareName': 'street_name',
        'component_PostalDescriptor': 'postal_code',
        'component_AdminUnitName_1': 'admin_unit_1',
        'component_AdminUnitName_4': 'admin_unit_4',
        'locator_designator_addressNumber': 'address_number',
        'locator_designator_addressNumberExtension': 'address_number_extension',
        'locator_designator_addressNumberExtension2ndExtension': 'address_number_extension_2',
        'locator_level': 'locator_level',
        'position_specification': 'position_specification',
        'position_method': 'position_method',
        'position_default': 'is_position_default',
        'building': 'building_id_reference',
        'parcel': 'parcel_id_reference',
    }
    gdf.rename(columns=column_mapping, inplace=True)
    
    # Select only the columns we have mapped
    gdf = gdf[list(column_mapping.values()) + ['geometry']]

    # --- Save to GeoParquet and DuckDB ---
    table_name = f"national_addresses{table_suffix}"
    output_path = OUTPUT_DIR / f"{table_name}.parquet"
    gdf.to_parquet(output_path)
    print(f"Saved {len(gdf)} address records to {output_path}")

    with duckdb.connect(str(DB_PATH)) as con:
        con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet(?)", [str(output_path)])
        print(f"Loaded address data into DuckDB table '{table_name}'")
    
    return len(gdf)


def fetch_and_process_buildings(bbox, crs="EPSG:4326", table_suffix=""):
    """
    Fetches building data for a given bounding box, processes it, and saves it.
    """
    print(f"--- Fetching Building Data for bbox: {bbox} ---")
    
    # Fetch data using WFS GetFeature
    params = {
        'service': 'WFS',
        'version': '2.0.0',
        'request': 'GetFeature',
        'typeName': 'BU.Building',
        'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},{crs}",
        'srsName': crs,
        'outputFormat': 'application/json',
        'maxFeatures': '500'  # Limit to 500 features for medium test
    }
    
    response = httpx.get(BUILDING_WMS_URL, params=params)
    response.raise_for_status()
    
    data = response.json()

    if not data.get("features"):
        print("No building features found in the specified bounding box.")
        return 0

    gdf = gpd.GeoDataFrame.from_features(data["features"])
    gdf.set_crs(crs, inplace=True)

    # --- Standardize Column Names ---
    column_mapping = {
        'inspireId_localId': 'inspire_id_local',
        'inspireId_versionId': 'inspire_id_version',
        'inspireId_namespace': 'inspire_id_namespace',
        'externalReference_informationSystem': 'ext_ref_info_system',
        'externalReference_informationSystemName': 'ext_ref_info_system_name',
        'externalReference_reference': 'ext_ref_reference',
        'beginLifespanVersion': 'lifespan_start_version',
        'endLifespanVersion': 'lifespan_end_version',
        'conditionOfConstruction': 'construction_condition',
        'currentUse_percentage': 'current_use_percentage',
        'dateOfConstruction': 'construction_date',
        'dateOfDemolition': 'demolition_date',
        'currentUse_currentUse': 'current_use',
        'elevation_elevationReference': 'elevation_reference',
        'elevation_elevationValue': 'elevation_value',
        'heightAboveGround_value': 'height_above_ground',
        'numberOfFloorsAboveGround': 'floors_above_ground',
        'geometry2D_referenceGeometry': 'is_2d_reference_geometry',
        'geometry2D_horizontalGeometryReference': 'horizontal_geometry_reference',
    }
    gdf.rename(columns=column_mapping, inplace=True)
    
    # Select only the columns we have mapped
    gdf = gdf[list(column_mapping.values()) + ['geometry']]

    # --- Save to GeoParquet and DuckDB ---
    table_name = f"national_buildings{table_suffix}"
    output_path = OUTPUT_DIR / f"{table_name}.parquet"
    gdf.to_parquet(output_path)
    print(f"Saved {len(gdf)} building records to {output_path}")

    with duckdb.connect(str(DB_PATH)) as con:
        con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet(?)", [str(output_path)])
        print(f"Loaded building data into DuckDB table '{table_name}'")
    
    return len(gdf)


def get_postal_code_bbox(postal_code="00100"):
    """Get bounding box for a specific postal code from existing data"""
    with duckdb.connect(str(DB_PATH)) as con:
        # First check if we have any data for this postal code
        count = con.execute("""
            SELECT COUNT(*) 
            FROM national_addresses 
            WHERE postal_code = ?
        """, [postal_code]).fetchone()[0]
        
        if count == 0:
            print(f"No addresses found for postal code {postal_code}")
            # Return a default bbox for central Helsinki
            return (24.93, 60.16, 24.96, 60.18)
        
        # Get bounding box for the postal code
        bbox = con.execute("""
            SELECT 
                MIN(ST_X(ST_GeomFromWKB(geometry))) - 0.005 as min_lon,
                MIN(ST_Y(ST_GeomFromWKB(geometry))) - 0.005 as min_lat,
                MAX(ST_X(ST_GeomFromWKB(geometry))) + 0.005 as max_lon,
                MAX(ST_Y(ST_GeomFromWKB(geometry))) + 0.005 as max_lat
            FROM national_addresses
            WHERE postal_code = ?
        """, [postal_code]).fetchone()
        
        print(f"Found {count} addresses in postal code {postal_code}")
        print(f"Bounding box: {bbox}")
        
        return bbox


def main():
    """
    Main function to run the medium sample data preparation pipeline.
    """
    print("=== Step 2: Medium Sample Test (100-500 items) ===")
    
    # Get bounding box for postal code 00100 (Helsinki city center)
    postal_code = "00100"
    bbox = get_postal_code_bbox(postal_code)
    
    if bbox:
        print(f"\n--- Fetching data for postal code {postal_code} area ---")
        print(f"Bounding box: {bbox}")
        
        # Fetch data with _medium suffix
        addr_count = fetch_and_process_addresses(bbox, table_suffix="_medium")
        bldg_count = fetch_and_process_buildings(bbox, table_suffix="_medium")
        
        print(f"\n=== Medium Sample Test Complete ===")
        print(f"Total addresses: {addr_count}")
        print(f"Total buildings: {bldg_count}")
    else:
        # If no bbox from existing data, use a central Helsinki area
        print("\nUsing default central Helsinki bounding box")
        bbox = (24.93, 60.16, 24.96, 60.18)
        
        addr_count = fetch_and_process_addresses(bbox, table_suffix="_medium")
        bldg_count = fetch_and_process_buildings(bbox, table_suffix="_medium")
        
        print(f"\n=== Medium Sample Test Complete ===")
        print(f"Total addresses: {addr_count}")
        print(f"Total buildings: {bldg_count}")


if __name__ == "__main__":
    main()
