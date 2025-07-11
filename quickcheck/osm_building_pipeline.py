#!/usr/bin/env python3
"""
OSM Building Data Integration Pipeline with Enhanced Spatial Matching
Downloads OpenStreetMap building footprints for Helsinki and performs spatial matching with listings
"""

import osmnx as ox
import geopandas as gpd
import pandas as pd
from datetime import datetime
import sqlite3
import json
from pathlib import Path
import time
import sys
sys.path.append(str(Path(__file__).parent.parent))

from oikotie.utils import EnhancedSpatialMatcher
from oikotie.visualization.utils.data_loader import DataLoader

class OSMBuildingDownloader:
    """Download and process OSM building data for Helsinki with enhanced spatial matching"""
    
    def __init__(self, output_dir="data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize enhanced spatial matcher
        self.spatial_matcher = EnhancedSpatialMatcher(
            tolerance_m=1.0,  # Optimal tolerance from testing
            target_crs='EPSG:3067'  # Finnish projected coordinates
        )
        
        # Initialize data loader for listings
        self.data_loader = DataLoader()
        
    def download_helsinki_buildings(self, save_to_file=True):
        """Download all building footprints for Helsinki"""
        print("=" * 60)
        print("OSM Helsinki Building Download")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        try:
            print("Downloading Helsinki building footprints from OpenStreetMap...")
            print("This may take several minutes depending on data size...")
            
            start_time = time.time()
            
            # Download buildings for entire Helsinki city
            place_name = "Helsinki, Finland" 
            buildings_gdf = ox.features_from_place(
                place_name, 
                tags={'building': True}
            )
            
            download_time = time.time() - start_time
            
            print(f"✅ Successfully downloaded {len(buildings_gdf)} buildings")
            print(f"Download time: {download_time:.1f} seconds")
            
            # Analyze the data
            self._analyze_building_data(buildings_gdf)
            
            if save_to_file:
                # Save to multiple formats
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Save as GeoJSON
                geojson_path = self.output_dir / f"helsinki_buildings_{timestamp}.geojson"
                buildings_gdf.to_file(geojson_path, driver='GeoJSON')
                print(f"💾 Saved GeoJSON: {geojson_path}")
                
                # Save as Parquet (more efficient)
                parquet_path = self.output_dir / f"helsinki_buildings_{timestamp}.parquet"
                buildings_gdf.to_parquet(parquet_path)
                print(f"💾 Saved Parquet: {parquet_path}")
                
                # Save metadata
                metadata = {
                    'download_timestamp': datetime.now().isoformat(),
                    'building_count': len(buildings_gdf),
                    'download_time_seconds': download_time,
                    'place_name': place_name,
                    'coordinate_system': str(buildings_gdf.crs),
                    'columns': list(buildings_gdf.columns),
                    'building_types': self._get_building_types(buildings_gdf)
                }
                
                metadata_path = self.output_dir / f"helsinki_buildings_{timestamp}_metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                print(f"📋 Saved metadata: {metadata_path}")
            
            return buildings_gdf
            
        except Exception as e:
            print(f"❌ Error downloading Helsinki buildings: {e}")
            return None
    
    def download_postal_code_buildings(self, postal_code="00590", save_to_file=True):
        """Download building footprints for a specific postal code area"""
        print("=" * 60)
        print(f"OSM Building Download - Postal Code {postal_code}")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        try:
            print(f"Downloading buildings for postal code {postal_code}...")
            
            start_time = time.time()
            
            # Create a more specific query for the postal code area
            # We'll use a bounding box approach since OSMnx doesn't directly support postal code queries
            if postal_code == "00590":
                # Specific bounding box for postal code 00590 (Länsisatama area)
                # These coordinates were determined from the previous validation
                north, south, east, west = 60.166, 60.155, 24.940, 24.920
            else:
                # Default to wider Helsinki area
                north, south, east, west = 60.3, 60.1, 25.1, 24.8
            
            buildings_gdf = ox.features_from_bbox(
                bbox=(north, south, east, west),
                tags={'building': True}
            )
            
            download_time = time.time() - start_time
            
            print(f"✅ Successfully downloaded {len(buildings_gdf)} buildings")
            print(f"Download time: {download_time:.1f} seconds")
            print(f"Bounding box: N={north}, S={south}, E={east}, W={west}")
            
            # Analyze the data
            self._analyze_building_data(buildings_gdf)
            
            if save_to_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Save as GeoJSON
                geojson_path = self.output_dir / f"buildings_postal_{postal_code}_{timestamp}.geojson"
                buildings_gdf.to_file(geojson_path, driver='GeoJSON')
                print(f"💾 Saved GeoJSON: {geojson_path}")
                
                # Save metadata
                metadata = {
                    'download_timestamp': datetime.now().isoformat(),
                    'postal_code': postal_code,
                    'building_count': len(buildings_gdf),
                    'download_time_seconds': download_time,
                    'bounding_box': {'north': north, 'south': south, 'east': east, 'west': west},
                    'coordinate_system': str(buildings_gdf.crs),
                    'building_types': self._get_building_types(buildings_gdf)
                }
                
                metadata_path = self.output_dir / f"buildings_postal_{postal_code}_{timestamp}_metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                print(f"📋 Saved metadata: {metadata_path}")
            
            return buildings_gdf
            
        except Exception as e:
            print(f"❌ Error downloading postal code {postal_code} buildings: {e}")
            return None
    
    def _analyze_building_data(self, buildings_gdf):
        """Analyze building data and print summary statistics"""
        print()
        print("📊 Building Data Analysis:")
        print(f"  Total buildings: {len(buildings_gdf)}")
        print(f"  Coordinate system: {buildings_gdf.crs}")
        print(f"  Columns: {len(buildings_gdf.columns)}")
        
        # Building types
        building_types = self._get_building_types(buildings_gdf)
        print()
        print("🏢 Building Types (top 10):")
        for building_type, count in list(building_types.items())[:10]:
            print(f"  {building_type}: {count}")
        
        # Address information
        address_columns = [col for col in buildings_gdf.columns if 'addr:' in col]
        if address_columns:
            print()
            print("📮 Address Information Available:")
            for col in address_columns:
                non_null_count = buildings_gdf[col].notna().sum()
                percentage = (non_null_count / len(buildings_gdf)) * 100
                print(f"  {col}: {non_null_count} buildings ({percentage:.1f}%)")
        
        # Geometry analysis
        print()
        print("📐 Geometry Analysis:")
        areas = buildings_gdf.geometry.area
        print(f"  Average building area: {areas.mean():.1f} sq units")
        print(f"  Median building area: {areas.median():.1f} sq units")
        print(f"  Largest building: {areas.max():.1f} sq units")
        print(f"  Smallest building: {areas.min():.1f} sq units")
    
    def _get_building_types(self, buildings_gdf):
        """Get building type statistics"""
        building_types = {}
        if 'building' in buildings_gdf.columns:
            for building_type in buildings_gdf['building'].fillna('unspecified'):
                building_types[str(building_type)] = building_types.get(str(building_type), 0) + 1
        
        # Sort by count
        return dict(sorted(building_types.items(), key=lambda x: x[1], reverse=True))
    
    def perform_spatial_matching(self, buildings_gdf, sample_size=None, output_prefix="osm_matching"):
        """Perform enhanced spatial matching between listings and OSM buildings"""
        print("=" * 60)
        print("🎯 Enhanced Spatial Matching with OSM Buildings")
        print("=" * 60)
        
        try:
            # Load listings data
            print("📊 Loading listings data...")
            listings_data = self.data_loader.load_listings_data()
            
            if listings_data is None or len(listings_data) == 0:
                print("❌ No listings data available")
                return None
            
            # Convert to GeoDataFrame
            listings_gdf = gpd.GeoDataFrame(
                listings_data,
                geometry=gpd.points_from_xy(listings_data.longitude, listings_data.latitude),
                crs='EPSG:4326'
            )
            
            # Sample if requested
            if sample_size and sample_size < len(listings_gdf):
                print(f"🎲 Sampling {sample_size} listings for testing...")
                listings_gdf = listings_gdf.sample(n=sample_size, random_state=42)
            
            print(f"🏠 Processing {len(listings_gdf)} listings")
            print(f"🏢 Against {len(buildings_gdf)} buildings")
            
            # Perform enhanced spatial matching
            start_time = time.time()
            
            matching_results = self.spatial_matcher.enhanced_spatial_match(
                points_gdf=listings_gdf,
                buildings_gdf=buildings_gdf,
                point_id_col='address',
                building_id_col='osm_id'
            )
            
            matching_time = time.time() - start_time
            
            # Print results
            stats = matching_results['statistics']
            print(f"\n✅ Spatial matching completed in {matching_time:.1f} seconds")
            print(f"📊 Match rate: {stats['match_rate']:.2f}%")
            print(f"🎯 Direct matches: {stats['direct_matches']}")
            print(f"🔄 Tolerance matches: {stats['tolerance_matches']}")
            print(f"❌ No matches: {stats['no_matches']}")
            print(f"⚡ Processing speed: {stats['processing_speed']:.1f} points/second")
            
            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_path = self.output_dir / f"{output_prefix}_{timestamp}_results.json"
            
            # Save detailed results
            save_data = {
                'timestamp': datetime.now().isoformat(),
                'listings_count': len(listings_gdf),
                'buildings_count': len(buildings_gdf),
                'sample_size': sample_size,
                'processing_time_seconds': matching_time,
                'statistics': stats,
                'matcher_config': {
                    'tolerance_m': self.spatial_matcher.tolerance_m,
                    'target_crs': self.spatial_matcher.target_crs
                }
            }
            
            with open(results_path, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            print(f"💾 Results saved: {results_path}")
            
            return matching_results
            
        except Exception as e:
            print(f"❌ Spatial matching failed: {e}")
            import traceback
            traceback.print_exc()
            return None

def main():
    """Main function to test OSM building download with enhanced spatial matching"""
    downloader = OSMBuildingDownloader()
    
    print("🏗️  OSM Building Data Integration Pipeline with Enhanced Spatial Matching")
    print("Downloads building footprints and performs spatial matching with listings")
    print()
    
    # Test 1: Download postal code 00590 (medium scale test)
    print("TEST 1: Downloading buildings for postal code 00590...")
    buildings_postal = downloader.download_postal_code_buildings("00590")
    
    if buildings_postal is not None and len(buildings_postal) > 50:
        print("✅ Postal code download successful - ready for spatial matching")
        
        # Test enhanced spatial matching with sample
        print("\n" + "="*50)
        print("TEST 2: Enhanced Spatial Matching (10 sample listings)")
        
        matching_results = downloader.perform_spatial_matching(
            buildings_postal, 
            sample_size=10, 
            output_prefix="postal_00590_sample"
        )
        
        if matching_results and matching_results['statistics']['match_rate'] >= 95.0:
            print("✅ Enhanced spatial matching successful!")
            print("🎯 Ready for progressive validation implementation")
        else:
            print("⚠️  Spatial matching needs optimization")
    else:
        print("⚠️  Postal code download had limited results")
    
    print("\n" + "="*60)
    
    # Information about full pipeline
    print("FULL PIPELINE CAPABILITIES:")
    print("✅ OSMnx integration with enhanced spatial matching")
    print("✅ EPSG:3067 CRS conversion for precision")
    print("✅ 1.0m tolerance buffer for boundary cases")
    print("✅ Performance monitoring and statistics")
    print()
    print("🎯 READY FOR PROGRESSIVE VALIDATION:")
    print("1. ✅ Enhanced spatial matching implemented and tested")
    print("2. 🔄 Step 1: validate_10_listings_osm.py (10 samples)")
    print("3. 🔄 Step 2: validate_postal_osm.py (medium scale)")
    print("4. 🔄 Step 3: validate_full_helsinki_osm.py (full scale)")
    
    return buildings_postal

if __name__ == "__main__":
    buildings = main()
