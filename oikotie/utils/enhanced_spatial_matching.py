#!/usr/bin/env python3
"""
Enhanced Spatial Matching with CRS Conversion and Tolerance
Fixes boundary precision issues identified in spatial logic investigation
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import numpy as np
from typing import Dict, List, Tuple, Optional
import time

class EnhancedSpatialMatcher:
    """
    Enhanced spatial matching with CRS conversion and tolerance handling
    
    Addresses precision issues where points on polygon boundaries
    return False for contains() due to floating-point precision.
    """
    
    def __init__(self, tolerance_m: float = 20.0, target_crs: str = 'EPSG:3067'):
        """
        Initialize enhanced spatial matcher
        
        Args:
            tolerance_m: Tolerance in meters for boundary precision issues
                        Default 20.0m optimized from Phase 3B.1 (achieved 85% match rate)
            target_crs: Target projected CRS for accurate distance calculations
                       Default EPSG:3067 (ETRS-TM35FIN) for Finland
        """
        self.tolerance_m = tolerance_m
        self.target_crs = target_crs
        self.stats = {
            'total_processed': 0,
            'direct_matches': 0,
            'tolerance_matches': 0,
            'no_matches': 0,
            'conversion_time': 0,
            'matching_time': 0
        }
    
    def enhanced_spatial_match(self, 
                             points_gdf: gpd.GeoDataFrame, 
                             buildings_gdf: gpd.GeoDataFrame,
                             point_id_col: str = 'address',
                             building_id_col: str = 'osm_id') -> pd.DataFrame:
        """
        Perform enhanced spatial matching with CRS conversion and tolerance
        
        Args:
            points_gdf: GeoDataFrame with points to match (listings/addresses)
            buildings_gdf: GeoDataFrame with building polygons
            point_id_col: Column name for point identifiers
            building_id_col: Column name for building identifiers
        
        Returns:
            DataFrame with matching results including match type and distances
        """
        print("🔧 Enhanced Spatial Matching - Started")
        print("=" * 60)
        print(f"Points to match: {len(points_gdf)}")
        print(f"Building polygons: {len(buildings_gdf)}")
        print(f"Tolerance: {self.tolerance_m}m")
        print(f"Target CRS: {self.target_crs}")
        print()
        
        start_time = time.time()
        
        # Reset statistics
        self.stats = {key: 0 for key in self.stats.keys()}
        self.stats['total_processed'] = len(points_gdf)
        
        # Step 1: CRS Conversion
        print("🌍 Converting coordinate systems...")
        conversion_start = time.time()
        
        # Convert points to target projected CRS
        points_proj = points_gdf.copy()
        if points_proj.crs != self.target_crs:
            points_proj = points_proj.to_crs(self.target_crs)
        
        # Convert buildings to target projected CRS  
        buildings_proj = buildings_gdf.copy()
        if buildings_proj.crs != self.target_crs:
            buildings_proj = buildings_proj.to_crs(self.target_crs)
        
        conversion_time = time.time() - conversion_start
        self.stats['conversion_time'] = conversion_time
        print(f"✅ CRS conversion completed in {conversion_time:.2f}s")
        
        # Step 2: Enhanced Spatial Matching
        print("🎯 Performing enhanced spatial matching...")
        matching_start = time.time()
        
        results = []
        
        for idx, point_row in points_proj.iterrows():
            point_geom = point_row.geometry
            point_id = point_row[point_id_col]
            
            # Find potential matches using spatial index
            potential_matches = buildings_proj[buildings_proj.geometry.intersects(
                point_geom.buffer(self.tolerance_m)
            )]
            
            if len(potential_matches) == 0:
                # No matches within tolerance
                results.append({
                    point_id_col: point_id,
                    building_id_col: None,
                    'match_type': 'no_match',
                    'distance_m': np.inf,
                    'is_direct_match': False,
                    'is_tolerance_match': False
                })
                self.stats['no_matches'] += 1
                continue
            
            # Calculate distances to all potential matches
            distances = potential_matches.geometry.distance(point_geom)
            closest_idx = distances.idxmin()
            closest_distance = distances.loc[closest_idx]
            closest_building = potential_matches.loc[closest_idx]
            
            # Determine match type
            is_direct_match = closest_building.geometry.contains(point_geom)
            is_tolerance_match = closest_distance <= self.tolerance_m
            
            if is_direct_match:
                match_type = 'direct_contains'
                self.stats['direct_matches'] += 1
            elif is_tolerance_match:
                match_type = 'tolerance_buffer'
                self.stats['tolerance_matches'] += 1
            else:
                match_type = 'no_match'
                self.stats['no_matches'] += 1
            
            results.append({
                point_id_col: point_id,
                building_id_col: closest_building[building_id_col] if is_tolerance_match else None,
                'match_type': match_type,
                'distance_m': closest_distance,
                'is_direct_match': is_direct_match,
                'is_tolerance_match': is_tolerance_match
            })
        
        matching_time = time.time() - matching_start
        self.stats['matching_time'] = matching_time
        
        total_time = time.time() - start_time
        
        # Create results DataFrame
        results_df = pd.DataFrame(results)
        
        # Print results summary
        self._print_matching_summary(results_df, total_time)
        
        return results_df
    
    def validate_boundary_cases(self, 
                               test_addresses: List[Dict],
                               buildings_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        """
        Validate specific boundary case addresses (like Siilikuja examples)
        
        Args:
            test_addresses: List of dicts with 'address', 'lat', 'lon' keys
            buildings_gdf: GeoDataFrame with building polygons
        
        Returns:
            DataFrame with detailed validation results
        """
        print("🔍 Boundary Case Validation - Started")
        print("=" * 60)
        
        # Create points GeoDataFrame from test addresses
        points_data = []
        for addr_info in test_addresses:
            point_geom = Point(addr_info['lon'], addr_info['lat'])
            points_data.append({
                'address': addr_info['address'],
                'geometry': point_geom
            })
        
        points_gdf = gpd.GeoDataFrame(points_data, crs='EPSG:4326')
        
        # Perform enhanced matching
        results_df = self.enhanced_spatial_match(points_gdf, buildings_gdf)
        
        # Add detailed analysis for boundary cases
        print("\n🔬 Detailed Boundary Case Analysis:")
        for idx, result in results_df.iterrows():
            address = result['address']
            match_type = result['match_type']
            distance = result['distance_m']
            
            print(f"\n📍 {address}")
            print(f"   Match Type: {match_type}")
            print(f"   Distance: {distance:.2f}m")
            
            if match_type == 'tolerance_buffer':
                print(f"   ✅ Fixed by tolerance buffer ({self.tolerance_m}m)")
            elif match_type == 'direct_contains':
                print(f"   ✅ Direct spatial match")
            else:
                print(f"   ❌ Still no match within {self.tolerance_m}m")
        
        return results_df
    
    def _print_matching_summary(self, results_df: pd.DataFrame, total_time: float):
        """Print comprehensive matching summary"""
        total_points = len(results_df)
        matched_points = len(results_df[results_df['match_type'] != 'no_match'])
        match_rate = (matched_points / total_points) * 100 if total_points > 0 else 0
        
        print("\n📊 Enhanced Spatial Matching Results:")
        print(f"   Total points processed: {total_points}")
        print(f"   Successfully matched: {matched_points}")
        print(f"   Match rate: {match_rate:.2f}%")
        print()
        print("📈 Match Type Breakdown:")
        print(f"   Direct contains matches: {self.stats['direct_matches']} ({(self.stats['direct_matches']/total_points)*100:.1f}%)")
        print(f"   Tolerance buffer matches: {self.stats['tolerance_matches']} ({(self.stats['tolerance_matches']/total_points)*100:.1f}%)")
        print(f"   No matches: {self.stats['no_matches']} ({(self.stats['no_matches']/total_points)*100:.1f}%)")
        print()
        print("⏱️  Performance Metrics:")
        print(f"   CRS conversion time: {self.stats['conversion_time']:.2f}s")
        print(f"   Spatial matching time: {self.stats['matching_time']:.2f}s")
        print(f"   Total processing time: {total_time:.2f}s")
        print(f"   Processing speed: {total_points/total_time:.1f} points/second")
        
        if self.stats['tolerance_matches'] > 0:
            print()
            print("💡 Tolerance Benefits:")
            print(f"   Points fixed by tolerance: {self.stats['tolerance_matches']}")
            print(f"   Additional match rate gain: {(self.stats['tolerance_matches']/total_points)*100:.2f}%")
    
    def get_statistics(self) -> Dict:
        """Get detailed matching statistics"""
        return self.stats.copy()

def test_enhanced_matching():
    """Test function for enhanced spatial matching"""
    print("🧪 Testing Enhanced Spatial Matching")
    print("=" * 60)
    
    # Test boundary cases from investigation
    boundary_test_cases = [
        {
            'address': 'Siilikuja 1 A, 00800 Helsinki',
            'lat': 60.209037,
            'lon': 25.037821
        },
        {
            'address': 'Siilikuja 1 B, 00800 Helsinki', 
            'lat': 60.209050,
            'lon': 25.037850
        }
    ]
    
    print("Note: This is a test function. To run with actual building data:")
    print("1. Load OSM building data with: data/helsinki_buildings_*.geojson")
    print("2. Call validate_boundary_cases() with actual building GeoDataFrame")
    print("3. Expected result: Both Siilikuja addresses should match with tolerance buffer")
    
    return boundary_test_cases

if __name__ == "__main__":
    test_enhanced_matching()
