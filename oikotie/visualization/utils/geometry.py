#!/usr/bin/env python3
"""
Geometry utilities for the Oikotie visualization package.

This module provides spatial processing utilities, CRS transformation helpers,
and geometry validation functions.
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely import wkt
from shapely.ops import transform
import pyproj
from typing import List, Tuple, Optional, Union, Any
import warnings
import logging
from functools import lru_cache


class GeometryProcessor:
    """Main geometry processing class for spatial operations."""
    
    def __init__(self, source_crs: str = 'EPSG:4326', target_crs: str = 'EPSG:3879'):
        """
        Initialize geometry processor.
        
        Args:
            source_crs: Source coordinate reference system (default: WGS84)
            target_crs: Target CRS for distance calculations (default: Helsinki local)
        """
        self.source_crs = source_crs
        self.target_crs = target_crs
        self.transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)
        self.logger = logging.getLogger(__name__)
    
    def validate_geometry(self, geom: Union[str, Any]) -> bool:
        """Validate if geometry is valid."""
        try:
            if isinstance(geom, str):
                geom = wkt.loads(geom)
            return geom.is_valid if hasattr(geom, 'is_valid') else False
        except Exception:
            return False
    
    def parse_geometry(self, geom_str: str) -> Optional[Any]:
        """Parse WKT geometry string safely."""
        try:
            geom = wkt.loads(geom_str)
            if self.validate_geometry(geom):
                return geom
            return None
        except Exception as e:
            self.logger.warning(f"Failed to parse geometry: {e}")
            return None
    
    def transform_to_projected(self, geom: Any) -> Any:
        """Transform geometry to projected coordinate system for accurate distance calculations."""
        try:
            return transform(self.transformer.transform, geom)
        except Exception as e:
            self.logger.warning(f"Failed to transform geometry: {e}")
            return geom
    
    def calculate_distance(self, point1: Point, point2: Point, use_projected: bool = True) -> float:
        """Calculate distance between two points."""
        try:
            if use_projected:
                # Transform to projected CRS for accurate distance
                point1_proj = self.transform_to_projected(point1)
                point2_proj = self.transform_to_projected(point2)
                return point1_proj.distance(point2_proj)
            else:
                # Use geographic distance (less accurate)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    return point1.distance(point2) * 111000  # Approximate conversion to meters
        except Exception as e:
            self.logger.error(f"Distance calculation failed: {e}")
            return float('inf')
    
    def create_buffer(self, geom: Any, buffer_distance: float, use_projected: bool = True) -> Any:
        """Create buffer around geometry."""
        try:
            if use_projected:
                geom_proj = self.transform_to_projected(geom)
                buffered = geom_proj.buffer(buffer_distance)
                # Transform back to original CRS
                return transform(lambda x, y: self.transformer.transform(x, y, direction='INVERSE'), buffered)
            else:
                return geom.buffer(buffer_distance)
        except Exception as e:
            self.logger.error(f"Buffer creation failed: {e}")
            return geom
    
    def spatial_join_contains(self, points_gdf: gpd.GeoDataFrame, polygons_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Perform spatial join to find which polygon contains each point."""
        try:
            # Ensure both GeoDataFrames have the same CRS
            if points_gdf.crs != polygons_gdf.crs:
                polygons_gdf = polygons_gdf.to_crs(points_gdf.crs)
            
            # Perform spatial join
            joined = gpd.sjoin(points_gdf, polygons_gdf, how='left', predicate='within')
            return joined
        except Exception as e:
            self.logger.error(f"Spatial join failed: {e}")
            return points_gdf
    
    def find_nearest_polygon(self, point: Point, polygons: List[Any], max_distance: float = 1000) -> Tuple[Optional[int], float]:
        """Find the nearest polygon to a point within max_distance."""
        min_distance = float('inf')
        nearest_idx = None
        
        for idx, polygon in enumerate(polygons):
            if not self.validate_geometry(polygon):
                continue
                
            try:
                # Calculate distance to polygon boundary
                distance = self.calculate_distance(point, polygon.exterior)
                
                if distance < min_distance and distance <= max_distance:
                    min_distance = distance
                    nearest_idx = idx
            except Exception as e:
                self.logger.warning(f"Distance calculation failed for polygon {idx}: {e}")
                continue
        
        return nearest_idx, min_distance if nearest_idx is not None else float('inf')


class CoordinateConverter:
    """Utility class for coordinate conversions."""
    
    @staticmethod
    def address_to_point(lat: float, lon: float) -> Point:
        """Convert latitude/longitude to Point geometry."""
        try:
            return Point(lon, lat)  # Note: Point(x, y) = Point(lon, lat)
        except Exception:
            return None
    
    @staticmethod
    def points_to_geodataframe(points: List[Tuple[float, float]], crs: str = 'EPSG:4326') -> gpd.GeoDataFrame:
        """Convert list of coordinate tuples to GeoDataFrame."""
        geometries = [Point(lon, lat) for lat, lon in points]
        return gpd.GeoDataFrame(geometry=geometries, crs=crs)
    
    @staticmethod
    def extract_coordinates(geom: Any) -> Optional[Tuple[float, float]]:
        """Extract coordinates from geometry (for Point geometries)."""
        try:
            if hasattr(geom, 'x') and hasattr(geom, 'y'):
                return (geom.y, geom.x)  # Return as (lat, lon)
            return None
        except Exception:
            return None


def create_sample_points(center_lat: float, center_lon: float, count: int = 10, radius: float = 0.01) -> gpd.GeoDataFrame:
    """Create sample points around a center location for testing."""
    import random
    
    points = []
    for _ in range(count):
        # Random offset within radius
        lat_offset = random.uniform(-radius, radius)
        lon_offset = random.uniform(-radius, radius)
        
        point = Point(center_lon + lon_offset, center_lat + lat_offset)
        points.append(point)
    
    return gpd.GeoDataFrame(geometry=points, crs='EPSG:4326')


def validate_spatial_data(gdf: gpd.GeoDataFrame) -> dict:
    """Validate spatial data quality."""
    validation_results = {
        'total_features': len(gdf),
        'valid_geometries': 0,
        'invalid_geometries': 0,
        'empty_geometries': 0,
        'geometry_types': {},
        'crs': str(gdf.crs) if gdf.crs else None,
        'bounds': None
    }
    
    try:
        processor = GeometryProcessor()
        
        for idx, geom in enumerate(gdf.geometry):
            if geom is None or geom.is_empty:
                validation_results['empty_geometries'] += 1
            elif processor.validate_geometry(geom):
                validation_results['valid_geometries'] += 1
                
                # Count geometry types
                geom_type = geom.geom_type
                validation_results['geometry_types'][geom_type] = validation_results['geometry_types'].get(geom_type, 0) + 1
            else:
                validation_results['invalid_geometries'] += 1
        
        # Calculate bounds if valid geometries exist
        if validation_results['valid_geometries'] > 0:
            bounds = gdf.total_bounds
            validation_results['bounds'] = {
                'minx': bounds[0], 'miny': bounds[1],
                'maxx': bounds[2], 'maxy': bounds[3]
            }
    
    except Exception as e:
        validation_results['error'] = str(e)
    
    return validation_results


@lru_cache(maxsize=50)
def get_transformer(source_crs: str, target_crs: str) -> pyproj.Transformer:
    """Get cached transformer for coordinate conversion."""
    return pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)


if __name__ == "__main__":
    print("🔧 Geometry Utils Demo")
    print("=" * 30)
    
    # Test geometry processor
    processor = GeometryProcessor()
    
    # Test point creation and validation
    helsinki_center = Point(24.9354, 60.1695)
    print(f"✅ Helsinki center point: {helsinki_center}")
    print(f"✅ Point is valid: {processor.validate_geometry(helsinki_center)}")
    
    # Test sample points creation
    sample_points = create_sample_points(60.1695, 24.9354, count=5)
    print(f"📍 Created {len(sample_points)} sample points")
    
    # Test validation
    validation = validate_spatial_data(sample_points)
    print(f"🔍 Validation results:")
    print(f"  - Valid geometries: {validation['valid_geometries']}")
    print(f"  - Geometry types: {validation['geometry_types']}")
    print(f"  - CRS: {validation['crs']}")
