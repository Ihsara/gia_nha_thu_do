import geopandas as gpd
from pathlib import Path
import duckdb
from oikotie.wms import WMSClient

# --- Configuration ---
ADDRESS_WMS_URL = "https://paikkatiedot.ymparisto.fi/geoserver/ryhti_inspire_ad/wms"
BUILDING_WMS_URL = "https://paikkatiedot.ymparisto.fi/geoserver/ryhti_inspire_bu/wms"
OUTPUT_DIR = Path("data/processed/national")
DB_PATH = Path("data/real_estate.duckdb")

# Create output directory if it doesn't exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def fetch_and_process_addresses(bbox, crs="EPSG:4326"):
    """
    Fetches address data for a given bounding box, processes it, and saves it.
    """
    print("--- Fetching Address Data ---")
    client = WMSClient(ADDRESS_WMS_URL)
    
    # Fetch data using WFS GetFeature
    params = {
        'service': 'WFS',
        'version': '2.0.0',
        'request': 'GetFeature',
        'typeName': 'AD.Address',
        'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},{crs}",
        'srsName': crs,
        'outputFormat': 'application/json'
    }
    
    # OWSLib doesn't have great WFS 2.0.0 support, so we'll use httpx directly
    import httpx
    response = httpx.get(ADDRESS_WMS_URL, params=params)
    response.raise_for_status()
    
    data = response.json()
    
    if not data.get("features"):
        print("No address features found in the specified bounding box.")
        return

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
    output_path = OUTPUT_DIR / "national_addresses.parquet"
    gdf.to_parquet(output_path)
    print(f"Saved address data to {output_path}")

    with duckdb.connect(str(DB_PATH)) as con:
        con.execute("CREATE OR REPLACE TABLE national_addresses AS SELECT * FROM read_parquet(?)", [str(output_path)])
        print("Loaded address data into DuckDB table 'national_addresses'")


def fetch_and_process_buildings(bbox, crs="EPSG:4326"):
    """
    Fetches building data for a given bounding box, processes it, and saves it.
    """
    print("--- Fetching Building Data ---")
    
    # Fetch data using WFS GetFeature
    params = {
        'service': 'WFS',
        'version': '2.0.0',
        'request': 'GetFeature',
        'typeName': 'BU.Building',
        'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},{crs}",
        'srsName': crs,
        'outputFormat': 'application/json'
    }
    
    import httpx
    response = httpx.get(BUILDING_WMS_URL, params=params)
    response.raise_for_status()
    
    data = response.json()

    if not data.get("features"):
        print("No building features found in the specified bounding box.")
        return

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
    output_path = OUTPUT_DIR / "national_buildings.parquet"
    gdf.to_parquet(output_path)
    print(f"Saved building data to {output_path}")

    with duckdb.connect(str(DB_PATH)) as con:
        con.execute("CREATE OR REPLACE TABLE national_buildings AS SELECT * FROM read_parquet(?)", [str(output_path)])
        print("Loaded building data into DuckDB table 'national_buildings'")


def main():
    """
    Main function to run the data preparation pipeline.
    """
    # Bounding box for a small sample of 10 listings
    sample_bbox = (24.8859824, 60.149434, 25.088612100000002, 60.2598991)
    print(f"--- Running Small Sample Test with BBox: {sample_bbox} ---")
    fetch_and_process_addresses(sample_bbox)
    fetch_and_process_buildings(sample_bbox)

if __name__ == "__main__":
    main()
