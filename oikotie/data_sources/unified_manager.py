"""
Unified Data Access Layer for Geodata Sources.

This module provides a smart data manager that automatically selects the best
data source based on query type, combines data from multiple sources when
beneficial, and handles caching and fallback strategies.
"""

from typing import Optional, Dict, Any, List, Tuple, Union
import geopandas as gpd
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging
from enum import Enum
import hashlib
import pickle

from .base import GeoDataSource
from .wms_source import WMSDataSource
from .geopackage_source import GeoPackageDataSource


class QueryType(Enum):
    """Types of spatial data queries."""
    BUILDING_POLYGONS = "building_polygons"
    BUILDING_ATTRIBUTES = "building_attributes"
    ADDRESSES = "addresses"
    TOPOGRAPHIC_LAYERS = "topographic_layers"
    ROADS = "roads"
    ADMINISTRATIVE = "administrative"
    COMBINED = "combined"


class DataSourcePriority(Enum):
    """Priority levels for data source selection."""
    PRIMARY = 1
    FALLBACK = 2
    ENRICHMENT = 3


class UnifiedDataManager:
    """
    Unified data access layer that intelligently combines multiple geodata sources.
    
    This class provides intelligent source selection, data combination, caching,
    and fallback strategies for optimal geodata access.
    """
    
    def __init__(
        self,
        geopackage_path: Optional[str] = None,
        cache_dir: Optional[str] = None,
        cache_ttl_hours: int = 24,
        enable_logging: bool = True
    ):
        """
        Initialize the unified data manager.
        
        Args:
            geopackage_path: Path to Helsinki GeoPackage file
            cache_dir: Directory for caching query results
            cache_ttl_hours: Cache time-to-live in hours
            enable_logging: Enable detailed logging
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        
        # Initialize logging
        if enable_logging:
            logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize data sources
        self.sources = {}
        self._initialize_sources(geopackage_path)
        
        # Source selection rules
        self._source_rules = self._define_source_rules()
        
        # Metadata
        self._metadata = {
            "manager_created": datetime.now().isoformat(),
            "cache_dir": str(self.cache_dir),
            "cache_ttl_hours": cache_ttl_hours,
            "sources_available": list(self.sources.keys())
        }
    
    def _initialize_sources(self, geopackage_path: Optional[str]):
        """Initialize available data sources."""
        # Always initialize WMS source (national coverage)
        try:
            self.sources["wms"] = WMSDataSource(name="Finnish National WMS")
            self.logger.info("WMS source initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize WMS source: {e}")
        
        # Initialize GeoPackage source if path provided
        if geopackage_path:
            try:
                if Path(geopackage_path).exists():
                    self.sources["geopackage"] = GeoPackageDataSource(
                        gpkg_path=geopackage_path,
                        name="Helsinki GeoPackage"
                    )
                    self.logger.info("GeoPackage source initialized successfully")
                else:
                    self.logger.warning(f"GeoPackage file not found: {geopackage_path}")
            except Exception as e:
                self.logger.error(f"Failed to initialize GeoPackage source: {e}")
    
    def _define_source_rules(self) -> Dict[QueryType, List[Tuple[str, DataSourcePriority]]]:
        """
        Define source selection rules for different query types.
        
        Returns:
            Dictionary mapping query types to ordered source preferences
        """
        return {
            QueryType.BUILDING_POLYGONS: [
                ("geopackage", DataSourcePriority.PRIMARY),  # Has actual polygons
                ("wms", DataSourcePriority.FALLBACK)         # Only points, but better than nothing
            ],
            QueryType.BUILDING_ATTRIBUTES: [
                ("wms", DataSourcePriority.PRIMARY),         # More comprehensive attributes
                ("geopackage", DataSourcePriority.ENRICHMENT) # Local detail enrichment
            ],
            QueryType.ADDRESSES: [
                ("wms", DataSourcePriority.PRIMARY),         # National coverage
                ("geopackage", DataSourcePriority.FALLBACK)  # Local Helsinki addresses
            ],
            QueryType.TOPOGRAPHIC_LAYERS: [
                ("geopackage", DataSourcePriority.PRIMARY)   # Rich topographic data
            ],
            QueryType.ROADS: [
                ("geopackage", DataSourcePriority.PRIMARY)   # Detailed road network
            ],
            QueryType.ADMINISTRATIVE: [
                ("wms", DataSourcePriority.PRIMARY),         # Administrative boundaries
                ("geopackage", DataSourcePriority.ENRICHMENT)
            ],
            QueryType.COMBINED: [
                ("geopackage", DataSourcePriority.PRIMARY),  # Start with local detail
                ("wms", DataSourcePriority.ENRICHMENT)       # Enrich with national data
            ]
        }
    
    def _get_cache_key(self, query_type: QueryType, bbox: Optional[Tuple], limit: Optional[int], **kwargs) -> str:
        """Generate cache key for query parameters with enhanced specificity."""
        cache_data = {
            "query_type": query_type.value,
            "bbox": tuple(round(x, 6) for x in bbox) if bbox else None,  # Round bbox for consistency
            "limit": limit,
            **kwargs
        }
        
        # Include all kwargs to ensure unique keys for different parameters
        cache_str = str(sorted(cache_data.items()))
        cache_key = hashlib.md5(cache_str.encode()).hexdigest()
        
        # Log cache key generation for debugging
        self.logger.debug(f"Generated cache key {cache_key[:8]}... for: {cache_data}")
        
        return cache_key
    
    def _get_from_cache(self, cache_key: str) -> Optional[gpd.GeoDataFrame]:
        """Retrieve data from cache if available and not expired."""
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        if not cache_file.exists():
            return None
        
        # Check if cache is expired
        file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if file_age > self.cache_ttl:
            cache_file.unlink()  # Remove expired cache
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load cache {cache_key}: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, data: gpd.GeoDataFrame):
        """Save data to cache."""
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            self.logger.warning(f"Failed to save cache {cache_key}: {e}")
    
    def _select_source(self, query_type: QueryType) -> List[Tuple[str, DataSourcePriority]]:
        """
        Select appropriate data sources for query type.
        
        Args:
            query_type: Type of query to execute
            
        Returns:
            List of (source_name, priority) tuples in order of preference
        """
        rules = self._source_rules.get(query_type, [])
        
        # Filter to only available sources
        available_sources = []
        for source_name, priority in rules:
            if source_name in self.sources:
                available_sources.append((source_name, priority))
            else:
                self.logger.debug(f"Source '{source_name}' not available for {query_type}")
        
        return available_sources
    
    def fetch_buildings(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: Optional[int] = None,
        use_cache: bool = True,
        combine_sources: bool = False
    ) -> gpd.GeoDataFrame:
        """
        Fetch building data using optimal source selection.
        
        Args:
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
            limit: Maximum number of records to fetch
            use_cache: Whether to use cached results
            combine_sources: Whether to combine data from multiple sources
            
        Returns:
            GeoDataFrame with building geometries and attributes
        """
        query_type = QueryType.BUILDING_POLYGONS
        cache_key = self._get_cache_key(query_type, bbox, limit, combine_sources=combine_sources)
        
        # Try cache first
        if use_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                self.logger.info(f"Returning cached building data (key: {cache_key[:8]})")
                return cached_data
        
        # Get source selection
        source_priorities = self._select_source(query_type)
        
        if not source_priorities:
            self.logger.error("No available sources for building data")
            return gpd.GeoDataFrame(columns=['geometry'])
        
        result_gdf = None
        
        if combine_sources and len(source_priorities) > 1:
            # Combine data from multiple sources
            result_gdf = self._fetch_buildings_combined(bbox, limit, source_priorities)
        else:
            # Use primary source with fallback
            result_gdf = self._fetch_buildings_with_fallback(bbox, limit, source_priorities)
        
        # Cache the result
        if use_cache and result_gdf is not None and len(result_gdf) > 0:
            self._save_to_cache(cache_key, result_gdf)
        
        return result_gdf if result_gdf is not None else gpd.GeoDataFrame(columns=['geometry'])
    
    def _fetch_buildings_combined(
        self,
        bbox: Optional[Tuple],
        limit: Optional[int],
        source_priorities: List[Tuple[str, DataSourcePriority]]
    ) -> gpd.GeoDataFrame:
        """Fetch buildings from multiple sources and combine intelligently."""
        combined_data = []
        total_fetched = 0
        
        for source_name, priority in source_priorities:
            if limit and total_fetched >= limit:
                break
            
            remaining_limit = limit - total_fetched if limit else None
            
            try:
                source = self.sources[source_name]
                data = source.fetch_buildings(bbox=bbox, limit=remaining_limit)
                
                if len(data) > 0:
                    # Add source metadata
                    data['data_source'] = source_name
                    data['source_priority'] = priority.value
                    combined_data.append(data)
                    total_fetched += len(data)
                    
                    self.logger.info(f"Fetched {len(data)} buildings from {source_name}")
                
            except Exception as e:
                self.logger.error(f"Error fetching buildings from {source_name}: {e}")
        
        if not combined_data:
            return gpd.GeoDataFrame(columns=['geometry'])
        
        # Combine all data
        result = gpd.concat(combined_data, ignore_index=True)
        
        # If we have overlapping data, prioritize by source priority
        if len(combined_data) > 1:
            result = self._deduplicate_buildings(result)
        
        return result
    
    def _fetch_buildings_with_fallback(
        self,
        bbox: Optional[Tuple],
        limit: Optional[int],
        source_priorities: List[Tuple[str, DataSourcePriority]]
    ) -> gpd.GeoDataFrame:
        """Fetch buildings with fallback strategy."""
        for source_name, priority in source_priorities:
            try:
                source = self.sources[source_name]
                data = source.fetch_buildings(bbox=bbox, limit=limit)
                
                if len(data) > 0:
                    data['data_source'] = source_name
                    self.logger.info(f"Successfully fetched {len(data)} buildings from {source_name}")
                    return data
                else:
                    self.logger.warning(f"No buildings found in {source_name}")
                    
            except Exception as e:
                self.logger.error(f"Error fetching buildings from {source_name}: {e}")
        
        return gpd.GeoDataFrame(columns=['geometry'])
    
    def _deduplicate_buildings(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Remove duplicate buildings, preferring higher priority sources."""
        # Sort by source priority (lower numbers = higher priority)
        gdf_sorted = gdf.sort_values('source_priority')
        
        # For buildings, we could deduplicate by spatial proximity
        # For now, just return the sorted data
        return gdf_sorted
    
    def fetch_addresses(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: Optional[int] = None,
        use_cache: bool = True,
        **kwargs
    ) -> gpd.GeoDataFrame:
        """
        Fetch address data using optimal source selection.
        
        Args:
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
            limit: Maximum number of records to fetch
            use_cache: Whether to use cached results
            
        Returns:
            GeoDataFrame with address points and attributes
        """
        query_type = QueryType.ADDRESSES
        cache_key = self._get_cache_key(query_type, bbox, limit, **kwargs)
        
        # Try cache first
        if use_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                self.logger.info(f"Returning cached address data (key: {cache_key[:8]})")
                return cached_data
        
        # Get source selection
        source_priorities = self._select_source(query_type)
        
        if not source_priorities:
            self.logger.error("No available sources for address data")
            return gpd.GeoDataFrame(columns=['geometry'])
        
        # Use primary source with fallback
        for source_name, priority in source_priorities:
            try:
                source = self.sources[source_name]
                data = source.fetch_addresses(bbox=bbox, limit=limit)
                
                if len(data) > 0:
                    data['data_source'] = source_name
                    self.logger.info(f"Successfully fetched {len(data)} addresses from {source_name}")
                    
                    # Cache the result
                    if use_cache:
                        self._save_to_cache(cache_key, data)
                    
                    return data
                else:
                    self.logger.warning(f"No addresses found in {source_name}")
                    
            except Exception as e:
                self.logger.error(f"Error fetching addresses from {source_name}: {e}")
        
        return gpd.GeoDataFrame(columns=['geometry'])
    
    def fetch_topographic_layer(
        self,
        layer_name: str,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: Optional[int] = None,
        use_cache: bool = True
    ) -> gpd.GeoDataFrame:
        """
        Fetch topographic layer data (only available from GeoPackage).
        
        Args:
            layer_name: Name of the topographic layer
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
            limit: Maximum number of records to fetch
            use_cache: Whether to use cached results
            
        Returns:
            GeoDataFrame with layer geometries and attributes
        """
        if "geopackage" not in self.sources:
            self.logger.error("GeoPackage source not available for topographic layers")
            return gpd.GeoDataFrame(columns=['geometry'])
        
        query_type = QueryType.TOPOGRAPHIC_LAYERS
        cache_key = self._get_cache_key(query_type, bbox, limit, layer_name=layer_name)
        
        # Try cache first
        if use_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                self.logger.info(f"Returning cached {layer_name} data (key: {cache_key[:8]})")
                return cached_data
        
        try:
            source = self.sources["geopackage"]
            data = source.fetch_layer(layer_name, bbox=bbox, limit=limit)
            
            if len(data) > 0:
                data['data_source'] = 'geopackage'
                self.logger.info(f"Successfully fetched {len(data)} records from {layer_name}")
                
                # Cache the result
                if use_cache:
                    self._save_to_cache(cache_key, data)
                
                return data
            else:
                self.logger.warning(f"No data found in layer {layer_name}")
                
        except Exception as e:
            self.logger.error(f"Error fetching layer {layer_name}: {e}")
        
        return gpd.GeoDataFrame(columns=['geometry'])
    
    def get_source_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status and metadata for all data sources.
        
        Returns:
            Dictionary with status information for each source
        """
        status = {}
        
        for source_name, source in self.sources.items():
            try:
                is_available = source.test_connection()
                metadata = source.get_metadata()
                
                status[source_name] = {
                    "available": is_available,
                    "metadata": metadata,
                    "last_tested": datetime.now().isoformat()
                }
                
            except Exception as e:
                status[source_name] = {
                    "available": False,
                    "error": str(e),
                    "last_tested": datetime.now().isoformat()
                }
        
        return status
    
    def get_available_layers(self) -> Dict[str, List[str]]:
        """
        Get available layers from all sources.
        
        Returns:
            Dictionary mapping source names to available layer lists
        """
        layers = {}
        
        for source_name, source in self.sources.items():
            try:
                if hasattr(source, 'list_all_layers'):
                    layers[source_name] = source.list_all_layers()
                else:
                    # Get from metadata
                    metadata = source.get_metadata()
                    layers[source_name] = metadata.get('available_layers', [])
                    
            except Exception as e:
                self.logger.error(f"Error getting layers from {source_name}: {e}")
                layers[source_name] = []
        
        return layers
    
    def clear_cache(self, older_than_hours: Optional[int] = None):
        """
        Clear cached data.
        
        Args:
            older_than_hours: Only clear cache older than this many hours.
                             If None, clear all cache.
        """
        cache_files = list(self.cache_dir.glob("*.pkl"))
        cleared_count = 0
        
        for cache_file in cache_files:
            should_clear = True
            
            if older_than_hours is not None:
                file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
                should_clear = file_age > timedelta(hours=older_than_hours)
            
            if should_clear:
                try:
                    cache_file.unlink()
                    cleared_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to clear cache file {cache_file}: {e}")
        
        self.logger.info(f"Cleared {cleared_count} cache files")
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the unified data manager.
        
        Returns:
            Dictionary containing manager metadata
        """
        metadata = self._metadata.copy()
        metadata['sources_status'] = self.get_source_status()
        metadata['available_layers'] = self.get_available_layers()
        metadata['cache_files_count'] = len(list(self.cache_dir.glob("*.pkl")))
        
        return metadata


# Convenience function for creating manager with default Helsinki setup
def create_helsinki_manager(
    geopackage_path: str = "data/helsinki_topographic_data.gpkg",
    cache_dir: str = "data/cache"
) -> UnifiedDataManager:
    """
    Create a unified data manager configured for Helsinki.
    
    Args:
        geopackage_path: Path to Helsinki GeoPackage file
        cache_dir: Directory for caching
        
    Returns:
        Configured UnifiedDataManager instance
    """
    return UnifiedDataManager(
        geopackage_path=geopackage_path,
        cache_dir=cache_dir,
        cache_ttl_hours=24,
        enable_logging=True
    )
