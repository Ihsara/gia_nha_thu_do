"""
GeoPackage data source implementation for local geodata files.

This module provides access to geodata stored in GeoPackage format,
specifically the Helsinki topographic data.
"""

from typing import Optional, Dict, Any, List, Tuple
import geopandas as gpd
import pandas as pd
from pathlib import Path
from shapely.geometry import Point, Polygon
import fiona
from datetime import datetime

from .base import GeoDataSource


class GeoPackageDataSource(GeoDataSource):
    """GeoPackage data source implementation for local geodata files."""
    
    # Layer name mappings (Finnish to English)
    LAYER_MAPPINGS = {
        # Buildings and structures
        "rakennus": "buildings",
        "rakennusreunaviiva": "building_edges",
        "osoitepiste": "address_points",
        
        # Transportation
        "tieviiva": "roads",
        "rautatie": "railways",
        "autoliikennealue": "traffic_areas",
        "kevyenliikentreitti": "light_traffic_routes",
        
        # Land use
        "maatalousmaa": "agricultural_land",
        "urheilujavirkistysalue": "recreation_areas",
        "hautausmaa": "cemeteries",
        "puisto": "parks",
        "niitty": "meadows",
        "metsä": "forests",
        
        # Water features
        "jarvi": "lakes",
        "virtavesialue": "rivers",
        "meri": "sea_areas",
        "lampi": "ponds",
        
        # Topography
        "korkeuskayra": "contour_lines",
        "kallioalue": "rock_areas",
        "harjualue": "ridge_areas",
        "suo": "wetlands"
    }
    
    # Standard column mappings (Finnish to English)
    BUILDING_COLUMN_MAPPING = {
        "mtk_id": "feature_id",
        "kohdeluokka": "feature_class",
        "kohderyhma": "feature_group",
        "kayttotarkoitus": "building_use_code",
        "kerrosluku": "floor_count",
        "kerrosala": "floor_area",
        "tilavuus": "volume",
        "alkupvm": "start_date",
        "loppupvm": "end_date",
        "sijaintitarkkuus": "location_accuracy",
        "korkeustarkkuus": "height_accuracy",
        "korkeus": "height",
        "aineistolahde": "data_source",
        "historia": "history",
        "paivitetty": "updated",
        "geometry": "geometry"
    }
    
    ADDRESS_COLUMN_MAPPING = {
        "mtk_id": "feature_id",
        "osoitenumero": "house_number",
        "katunimi": "street_name",
        "postinumero": "postal_code",
        "kunta": "municipality",
        "kiinteistotunnus": "property_id",
        "rakennustunnus": "building_id",
        "sijaintitarkkuus": "location_accuracy",
        "korkeus": "height",
        "alkupvm": "start_date",
        "loppupvm": "end_date",
        "aineistolahde": "data_source",
        "paivitetty": "updated",
        "geometry": "geometry"
    }
    
    def __init__(self, gpkg_path: str, name: str = "Helsinki GeoPackage", crs: str = "EPSG:4326"):
        """
        Initialize GeoPackage data source.
        
        Args:
            gpkg_path: Path to the GeoPackage file
            name: Human-readable name for the data source
            crs: Target coordinate reference system (default: EPSG:4326)
        """
        super().__init__(name, crs)
        
        self.gpkg_path = Path(gpkg_path)
        if not self.gpkg_path.exists():
            raise FileNotFoundError(f"GeoPackage file not found: {gpkg_path}")
        
        # Get available layers
        self._layers = None
        self._layer_info = {}
        self._scan_layers()
        
        # Update metadata
        self._metadata.update({
            "gpkg_path": str(self.gpkg_path),
            "native_crs": "EPSG:3067",  # Finnish coordinate system
            "layer_count": len(self._layers) if self._layers else 0
        })
    
    def _scan_layers(self):
        """Scan the GeoPackage for available layers and their properties."""
        try:
            self._layers = fiona.listlayers(str(self.gpkg_path))
            
            # Get basic info for each layer
            for layer in self._layers:
                try:
                    with fiona.open(str(self.gpkg_path), layer=layer) as src:
                        self._layer_info[layer] = {
                            "record_count": len(src),
                            "crs": src.crs,
                            "bounds": src.bounds if hasattr(src, 'bounds') else None,
                            "schema": dict(src.schema) if hasattr(src, 'schema') else None
                        }
                except Exception as e:
                    self._layer_info[layer] = {"error": str(e)}
                    
        except Exception as e:
            print(f"Error scanning GeoPackage layers: {e}")
            self._layers = []
    
    def fetch_buildings(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: Optional[int] = None
    ) -> gpd.GeoDataFrame:
        """
        Fetch building data from GeoPackage.
        
        Args:
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat) in target CRS
            limit: Maximum number of records to fetch
            
        Returns:
            GeoDataFrame with building geometries and attributes
        """
        # Load the buildings layer
        if "rakennus" not in self._layers:
            print("Warning: 'rakennus' layer not found in GeoPackage")
            return gpd.GeoDataFrame(columns=['geometry'] + list(self.BUILDING_COLUMN_MAPPING.values()))
        
        # Read the layer
        gdf = gpd.read_file(str(self.gpkg_path), layer="rakennus")
        
        # Apply bbox filter if provided (convert bbox to native CRS first)
        if bbox is not None and len(gdf) > 0:
            # Convert bbox from target CRS to native CRS
            bbox_gdf = gpd.GeoDataFrame(
                [{'geometry': gpd.GeoSeries.from_xy([bbox[0], bbox[2]], [bbox[1], bbox[3]]).unary_union.envelope}],
                crs=self.target_crs
            )
            bbox_native = bbox_gdf.to_crs(gdf.crs).geometry[0].bounds
            
            # Filter by bbox
            gdf = gdf.cx[bbox_native[0]:bbox_native[2], bbox_native[1]:bbox_native[3]]
        
        # Apply limit if provided
        if limit is not None and len(gdf) > limit:
            gdf = gdf.head(limit)
        
        # Standardize column names
        gdf = self.standardize_columns(gdf, self.BUILDING_COLUMN_MAPPING)
        
        # Transform to target CRS
        gdf = self.transform_to_target_crs(gdf)
        
        return gdf
    
    def fetch_addresses(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: Optional[int] = None
    ) -> gpd.GeoDataFrame:
        """
        Fetch address point data from GeoPackage.
        
        Args:
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat) in target CRS
            limit: Maximum number of records to fetch
            
        Returns:
            GeoDataFrame with address points and attributes
        """
        # Load the address points layer
        if "osoitepiste" not in self._layers:
            print("Warning: 'osoitepiste' layer not found in GeoPackage")
            return gpd.GeoDataFrame(columns=['geometry'] + list(self.ADDRESS_COLUMN_MAPPING.values()))
        
        # Read the layer
        gdf = gpd.read_file(str(self.gpkg_path), layer="osoitepiste")
        
        # Apply bbox filter if provided
        if bbox is not None and len(gdf) > 0:
            # Convert bbox from target CRS to native CRS
            bbox_gdf = gpd.GeoDataFrame(
                [{'geometry': gpd.GeoSeries.from_xy([bbox[0], bbox[2]], [bbox[1], bbox[3]]).unary_union.envelope}],
                crs=self.target_crs
            )
            bbox_native = bbox_gdf.to_crs(gdf.crs).geometry[0].bounds
            
            # Filter by bbox
            gdf = gdf.cx[bbox_native[0]:bbox_native[2], bbox_native[1]:bbox_native[3]]
        
        # Apply limit if provided
        if limit is not None and len(gdf) > limit:
            gdf = gdf.head(limit)
        
        # Standardize column names
        gdf = self.standardize_columns(gdf, self.ADDRESS_COLUMN_MAPPING)
        
        # Transform to target CRS
        gdf = self.transform_to_target_crs(gdf)
        
        return gdf
    
    def fetch_layer(
        self,
        layer_name: str,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: Optional[int] = None,
        column_mapping: Optional[Dict[str, str]] = None
    ) -> gpd.GeoDataFrame:
        """
        Fetch data from any layer in the GeoPackage.
        
        Args:
            layer_name: Name of the layer to fetch
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat) in target CRS
            limit: Maximum number of records to fetch
            column_mapping: Optional column name mapping dictionary
            
        Returns:
            GeoDataFrame with geometries and attributes
        """
        if layer_name not in self._layers:
            raise ValueError(f"Layer '{layer_name}' not found. Available layers: {', '.join(self._layers[:10])}...")
        
        # Read the layer
        gdf = gpd.read_file(str(self.gpkg_path), layer=layer_name)
        
        # Apply bbox filter if provided
        if bbox is not None and len(gdf) > 0:
            # Convert bbox from target CRS to native CRS
            bbox_gdf = gpd.GeoDataFrame(
                [{'geometry': gpd.GeoSeries.from_xy([bbox[0], bbox[2]], [bbox[1], bbox[3]]).unary_union.envelope}],
                crs=self.target_crs
            )
            bbox_native = bbox_gdf.to_crs(gdf.crs).geometry[0].bounds
            
            # Filter by bbox
            gdf = gdf.cx[bbox_native[0]:bbox_native[2], bbox_native[1]:bbox_native[3]]
        
        # Apply limit if provided
        if limit is not None and len(gdf) > limit:
            gdf = gdf.head(limit)
        
        # Apply column mapping if provided
        if column_mapping:
            gdf = self.standardize_columns(gdf, column_mapping)
        
        # Transform to target CRS
        gdf = self.transform_to_target_crs(gdf)
        
        return gdf
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the GeoPackage data source.
        
        Returns:
            Dictionary containing source metadata
        """
        metadata = self._metadata.copy()
        
        # Add layer information
        metadata['available_layers'] = self._layers
        metadata['layer_count'] = len(self._layers)
        
        # Add detailed layer info
        layer_summary = {}
        for layer, info in self._layer_info.items():
            if 'error' not in info:
                layer_summary[layer] = {
                    'record_count': info.get('record_count', 0),
                    'geometry_type': info.get('schema', {}).get('geometry', 'Unknown') if info.get('schema') else 'Unknown'
                }
        
        metadata['layer_summary'] = layer_summary
        
        # Add key layer record counts
        metadata['record_counts'] = {
            'buildings': self._layer_info.get('rakennus', {}).get('record_count', 'Unknown'),
            'addresses': self._layer_info.get('osoitepiste', {}).get('record_count', 'Unknown'),
            'roads': self._layer_info.get('tieviiva', {}).get('record_count', 'Unknown'),
            'contours': self._layer_info.get('korkeuskayra', {}).get('record_count', 'Unknown')
        }
        
        # File information
        metadata['file_size_mb'] = round(self.gpkg_path.stat().st_size / (1024 * 1024), 2)
        metadata['last_modified'] = datetime.fromtimestamp(self.gpkg_path.stat().st_mtime).isoformat()
        
        return metadata
    
    def test_connection(self) -> bool:
        """
        Test if the GeoPackage file is accessible and valid.
        
        Returns:
            True if file accessible and has layers, False otherwise
        """
        try:
            # Check file exists
            if not self.gpkg_path.exists():
                return False
            
            # Check we can list layers
            layers = fiona.listlayers(str(self.gpkg_path))
            
            # Check we have at least one layer
            return len(layers) > 0
            
        except Exception as e:
            print(f"GeoPackage connection test failed: {e}")
            return False
    
    def list_all_layers(self) -> List[str]:
        """
        Get a list of all available layers in the GeoPackage.
        
        Returns:
            List of layer names
        """
        return self._layers.copy() if self._layers else []
    
    def get_layer_info(self, layer_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific layer.
        
        Args:
            layer_name: Name of the layer
            
        Returns:
            Dictionary with layer information
        """
        if layer_name not in self._layer_info:
            return {"error": f"Layer '{layer_name}' not found"}
        
        return self._layer_info[layer_name].copy()
