"""
Abstract base class for geodata sources.

This module defines the interface that all geodata sources must implement,
ensuring consistent access patterns across different data providers.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
import geopandas as gpd
from datetime import datetime


class GeoDataSource(ABC):
    """Abstract base class for geodata sources."""
    
    def __init__(self, name: str, crs: str = "EPSG:4326"):
        """
        Initialize the data source.
        
        Args:
            name: Human-readable name for the data source
            crs: Target coordinate reference system (default: EPSG:4326)
        """
        self.name = name
        self.target_crs = crs
        self._metadata = {
            "name": name,
            "type": self.__class__.__name__,
            "created": datetime.now().isoformat(),
            "target_crs": crs
        }
    
    @abstractmethod
    def fetch_buildings(
        self, 
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: Optional[int] = None
    ) -> gpd.GeoDataFrame:
        """
        Fetch building data from the source.
        
        Args:
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
            limit: Maximum number of records to fetch
            
        Returns:
            GeoDataFrame with building geometries and attributes
        """
        pass
    
    @abstractmethod
    def fetch_addresses(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: Optional[int] = None
    ) -> gpd.GeoDataFrame:
        """
        Fetch address point data from the source.
        
        Args:
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
            limit: Maximum number of records to fetch
            
        Returns:
            GeoDataFrame with address points and attributes
        """
        pass
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the data source.
        
        Returns:
            Dictionary containing source metadata including:
            - name: Source name
            - type: Source type (WMS, GeoPackage, etc.)
            - available_layers: List of available data layers
            - crs: Native coordinate reference system
            - extent: Geographic extent of data
            - record_counts: Number of records per layer
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the data source is accessible.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    def transform_to_target_crs(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Transform GeoDataFrame to target CRS if needed.
        
        Args:
            gdf: Input GeoDataFrame
            
        Returns:
            GeoDataFrame in target CRS
        """
        if gdf.crs and gdf.crs != self.target_crs:
            return gdf.to_crs(self.target_crs)
        return gdf
    
    def standardize_columns(self, gdf: gpd.GeoDataFrame, column_mapping: Dict[str, str]) -> gpd.GeoDataFrame:
        """
        Rename columns according to standardized mapping.
        
        Args:
            gdf: Input GeoDataFrame
            column_mapping: Dictionary mapping source columns to standard names
            
        Returns:
            GeoDataFrame with standardized column names
        """
        # Only rename columns that exist in the dataframe
        existing_columns = {k: v for k, v in column_mapping.items() if k in gdf.columns}
        return gdf.rename(columns=existing_columns)
    
    def __repr__(self) -> str:
        """String representation of the data source."""
        return f"{self.__class__.__name__}(name='{self.name}', crs='{self.target_crs}')"
