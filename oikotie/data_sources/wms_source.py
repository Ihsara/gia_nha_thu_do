"""
WMS data source implementation for Finnish national geodata.

This module provides access to geodata through Web Map Services (WMS),
specifically the Finnish national geodata services.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, box
from owslib.wms import WebMapService
import requests
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime

from .base import GeoDataSource


class WMSDataSource(GeoDataSource):
    """WMS data source implementation for Finnish national geodata."""
    
    # Standard column mappings from Finnish to English
    BUILDING_COLUMN_MAPPING = {
        "rakennustunnus": "building_id",
        "kiinteistotunnus": "property_id",
        "alkupvm": "start_date",
        "loppupvm": "end_date",
        "kerrosala": "floor_area",
        "kerrosluku": "floor_count",
        "kayttotarkoitus": "building_use_code",
        "kayttotarkoitusselite": "building_use",
        "rakennusluokka": "building_class",
        "julkisivumateriaali": "facade_material",
        "kantavienrakenteidenaine": "structural_material",
        "pinta_ala": "area",
        "aineistolahde": "data_source",
        "historia": "history",
        "paivitetty_tietopalveluun": "updated_to_service",
        "bbox": "bbox"
    }
    
    ADDRESS_COLUMN_MAPPING = {
        "nimi": "name",
        "osoitenumero": "house_number",
        "katunimi": "street_name",
        "kunta": "municipality",
        "postinumero": "postal_code",
        "osoiteteksti": "address_text",
        "sijainti_virhesade": "location_error_radius",
        "osoitenumero_alaosa": "house_number_lower",
        "kiinteistotunnus": "property_id",
        "rakennustunnus": "building_id",
        "paikannimi": "place_name",
        "poimintapvm": "extraction_date",
        "alkupvm": "start_date",
        "loppupvm": "end_date",
        "aineistolahde": "data_source",
        "historia": "history",
        "paivitetty_tietopalveluun": "updated_to_service",
        "bbox": "bbox"
    }
    
    def __init__(self, name: str = "Finnish National WMS", crs: str = "EPSG:4326"):
        """
        Initialize WMS data source.
        
        Args:
            name: Human-readable name for the data source
            crs: Target coordinate reference system (default: EPSG:4326)
        """
        super().__init__(name, crs)
        
        # WFS endpoints (using same endpoints as prepare_national_geodata.py)
        self.address_wfs_url = "https://paikkatiedot.ymparisto.fi/geoserver/ryhti_inspire_ad/wms"
        self.building_wfs_url = "https://paikkatiedot.ymparisto.fi/geoserver/ryhti_inspire_bu/wms"
        
        # Update metadata
        self._metadata.update({
            "address_wfs_url": self.address_wfs_url,
            "building_wfs_url": self.building_wfs_url,
            "native_crs": "EPSG:4326"  # WFS returns data in EPSG:4326
        })
    
    def fetch_buildings(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: Optional[int] = None
    ) -> gpd.GeoDataFrame:
        """
        Fetch building data from WFS.
        
        Args:
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
            limit: Maximum number of records to fetch
            
        Returns:
            GeoDataFrame with building geometries and attributes
        """
        if bbox is None:
            # Default to Helsinki area
            bbox = (24.88, 60.15, 25.09, 60.26)
        
        # Prepare WFS GetFeature request parameters
        params = {
            'service': 'WFS',
            'version': '2.0.0',
            'request': 'GetFeature',
            'typeName': 'BU.Building',
            'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:4326",
            'srsName': 'EPSG:4326',
            'outputFormat': 'application/json'
        }
        
        if limit:
            params['count'] = str(limit)
        
        try:
            # Make the request
            response = httpx.get(self.building_wfs_url, params=params, timeout=30.0)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("features"):
                print("No building features found in the specified bounding box.")
                return gpd.GeoDataFrame(columns=['geometry'])
            
            # Create GeoDataFrame from features
            gdf = gpd.GeoDataFrame.from_features(data["features"])
            gdf.set_crs("EPSG:4326", inplace=True)
            
            # Update column mapping for INSPIRE data
            inspire_building_mapping = {
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
            
            # Standardize column names
            gdf = self.standardize_columns(gdf, inspire_building_mapping)
            
            # Transform to target CRS if needed
            gdf = self.transform_to_target_crs(gdf)
            
            return gdf
            
        except httpx.HTTPError as e:
            print(f"HTTP Error fetching building data: {e}")
            return gpd.GeoDataFrame(columns=['geometry'])
        except Exception as e:
            print(f"Error fetching building data: {e}")
            return gpd.GeoDataFrame(columns=['geometry'])
    
    def fetch_addresses(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: Optional[int] = None
    ) -> gpd.GeoDataFrame:
        """
        Fetch address point data from WFS.
        
        Args:
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
            limit: Maximum number of records to fetch
            
        Returns:
            GeoDataFrame with address points and attributes
        """
        if bbox is None:
            # Default to Helsinki area
            bbox = (24.88, 60.15, 25.09, 60.26)
        
        # Prepare WFS GetFeature request parameters
        params = {
            'service': 'WFS',
            'version': '2.0.0',
            'request': 'GetFeature',
            'typeName': 'AD.Address',
            'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:4326",
            'srsName': 'EPSG:4326',
            'outputFormat': 'application/json'
        }
        
        if limit:
            params['count'] = str(limit)
        
        try:
            # Make the request
            response = httpx.get(self.address_wfs_url, params=params, timeout=30.0)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("features"):
                print("No address features found in the specified bounding box.")
                return gpd.GeoDataFrame(columns=['geometry'])
            
            # Create GeoDataFrame from features
            gdf = gpd.GeoDataFrame.from_features(data["features"])
            gdf.set_crs("EPSG:4326", inplace=True)
            
            # Update column mapping for INSPIRE data
            inspire_address_mapping = {
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
            
            # Standardize column names
            gdf = self.standardize_columns(gdf, inspire_address_mapping)
            
            # Transform to target CRS if needed
            gdf = self.transform_to_target_crs(gdf)
            
            return gdf
            
        except httpx.HTTPError as e:
            print(f"HTTP Error fetching address data: {e}")
            return gpd.GeoDataFrame(columns=['geometry'])
        except Exception as e:
            print(f"Error fetching address data: {e}")
            return gpd.GeoDataFrame(columns=['geometry'])
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the WFS data source.
        
        Returns:
            Dictionary containing source metadata
        """
        metadata = self._metadata.copy()
        
        # Try to get capabilities information
        try:
            # Test with small request to building service
            response = httpx.get(
                self.building_wfs_url,
                params={
                    'service': 'WFS',
                    'version': '2.0.0',
                    'request': 'GetCapabilities'
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                metadata['building_service_status'] = 'Available'
            else:
                metadata['building_service_status'] = f'Error: {response.status_code}'
                
        except Exception as e:
            metadata['building_service_status'] = f'Connection Error: {str(e)}'
        
        # Test address service
        try:
            response = httpx.get(
                self.address_wfs_url,
                params={
                    'service': 'WFS',
                    'version': '2.0.0',
                    'request': 'GetCapabilities'
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                metadata['address_service_status'] = 'Available'
            else:
                metadata['address_service_status'] = f'Error: {response.status_code}'
                
        except Exception as e:
            metadata['address_service_status'] = f'Connection Error: {str(e)}'
        
        # Record counts are not available from WFS without querying
        metadata['record_counts'] = {
            'buildings': 'Unknown (streaming service)',
            'addresses': 'Unknown (streaming service)'
        }
        
        metadata['available_layers'] = ['BU.Building', 'AD.Address']
        
        return metadata
    
    def test_connection(self) -> bool:
        """
        Test if the WMS service is accessible.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try a small request
            test_bbox = (24.9, 60.17, 24.95, 60.18)  # Small area in Helsinki
            buildings = self.fetch_buildings(bbox=test_bbox, limit=1)
            return len(buildings) >= 0  # Even 0 results means connection worked
        except Exception as e:
            print(f"WMS connection test failed: {e}")
            return False
