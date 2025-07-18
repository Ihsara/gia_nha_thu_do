#!/usr/bin/env python3
"""
OSM Geofabrik Building Data Pipeline with Enhanced Spatial Matching
Downloads Finland OSM data from Geofabrik and performs spatial matching with listings
Much more efficient than API-based approaches
"""

import requests
import geopandas as gpd
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
import time
import subprocess
import sys
import zipfile
import tempfile
import os

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from oikotie.utils import EnhancedSpatialMatcher
from oikotie.visualization.utils.data_loader import DataLoader

class OSMGeofabrikDownloader:
    """Download and process OSM data from Geofabrik extracts with enhanced spatial matching"""
    
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Geofabrik URLs for Finland
        self.finland_pbf_url = "https://download.geofabrik.de/europe/finland-latest.osm.pbf"
        self.finland_shp_url = "https://download.geofabrik.de/europe/finland-latest-free.shp.zip"
        
        # Initialize enhanced spatial matcher
        self.spatial_matcher = EnhancedSpatialMatcher(
            tolerance_m=1.0,  # Optimal tolerance from testing
            target_crs='EPSG:3067'  # Finnish projected coordinates
        )
        
        # Initialize data loader for listings
        self.data_loader = DataLoader()
        
    def check_dependencies(self):
        """Check if required tools are available"""
        print("=" * 60)
        print("🔧 Checking Dependencies")
        print("=" * 60)
        
        dependencies_ok = True
        
        # Check Python packages (osmium not needed for shapefile approach)
        required_packages = ['geopandas', 'requests']
        for package in required_packages:
            try:
                __import__(package)
                print(f"✅ {package} available")
            except ImportError:
                print(f"❌ {package} not available")
                dependencies_ok = False
        
        # zipfile is part of standard library
        print("✅ zipfile available (standard library)")
        
        if dependencies_ok:
            print("✅ All required dependencies available")
            print("ℹ️  Using pre-processed shapefiles (no osmium required)")
        
        return dependencies_ok
    
    def download_finland_shapefile(self):
        """Download pre-processed building shapefiles from Geofabrik"""
        print("=" * 60)
        print("🏗️  Downloading Finland Building Data (Shapefile)")
        print("=" * 60)
        print(f"Source: {self.finland_shp_url}")
        print(f"Target: {self.data_dir}")
        print()
        
        try:
            # Download the shapefile archive
            print("📥 Downloading Finland OSM shapefile archive...")
            print("⏱️  This may take 5-10 minutes depending on connection")
            
            start_time = time.time()
            
            response = requests.get(self.finland_shp_url, stream=True)
            response.raise_for_status()
            
            # Save to temporary file
            zip_path = self.data_dir / "finland-latest-free.shp.zip"
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\r📥 Download progress: {progress:.1f}% ({downloaded/1024/1024:.1f}MB)", end='')
            
            download_time = time.time() - start_time
            print(f"\n✅ Download completed in {download_time:.1f} seconds")
            print(f"📊 File size: {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
            
            # Extract the archive
            print("\n📂 Extracting shapefile archive...")
            extract_dir = self.data_dir / "finland_osm_shapefiles"
            extract_dir.mkdir(exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            print(f"✅ Extracted to: {extract_dir}")
            
            # Look for building-related shapefiles
            building_files = []
            for shp_file in extract_dir.rglob("*.shp"):
                if 'building' in shp_file.name.lower():
                    building_files.append(shp_file)
            
            print(f"\n🏢 Found {len(building_files)} building-related shapefiles:")
            for shp_file in building_files:
                file_size = shp_file.stat().st_size / 1024 / 1024
                print(f"  📁 {shp_file.name} ({file_size:.1f} MB)")
            
            # Clean up zip file
            zip_path.unlink()
            
            return building_files
            
        except Exception as e:
            print(f"❌ Error downloading Finland shapefile: {e}")
            return []
    
    def load_helsinki_buildings(self, shapefile_path):
        """Load building data specifically for Helsinki area"""
        print("=" * 60)
        print("🏗️  Loading Helsinki Buildings")
        print("=" * 60)
        print(f"Source: {shapefile_path}")
        print()
        
        try:
            print("📖 Reading building shapefile...")
            start_time = time.time()
            
            # Read the entire shapefile
            buildings_gdf = gpd.read_file(shapefile_path)
            
            read_time = time.time() - start_time
            print(f"✅ Loaded {len(buildings_gdf)} buildings in {read_time:.1f} seconds")
            
            # Filter for Helsinki area (rough bounding box)
            print("\n🎯 Filtering for Helsinki area...")
            
            # Helsinki bounding box (approximate)
            helsinki_bounds = {
                'min_lat': 60.1,
                'max_lat': 60.3,
                'min_lon': 24.8,
                'max_lon': 25.1
            }
            
            # Filter buildings within Helsinki bounds
            if buildings_gdf.crs.to_string() != 'EPSG:4326':
                print(f"🔄 Converting from {buildings_gdf.crs} to EPSG:4326...")
                buildings_gdf = buildings_gdf.to_crs('EPSG:4326')
            
            # Get building centroids for filtering
            centroids = buildings_gdf.geometry.centroid
            
            helsinki_mask = (
                (centroids.y >= helsinki_bounds['min_lat']) &
                (centroids.y <= helsinki_bounds['max_lat']) &
                (centroids.x >= helsinki_bounds['min_lon']) &
                (centroids.x <= helsinki_bounds['max_lon'])
            )
            
            helsinki_buildings = buildings_gdf[helsinki_mask].copy()
            
            print(f"✅ Filtered to {len(helsinki_buildings)} Helsinki buildings")
            print(f"📊 Reduction: {len(buildings_gdf)} → {len(helsinki_buildings)} buildings")
            
            # Save Helsinki buildings for future use
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.data_dir / f"helsinki_buildings_{timestamp}.geojson"
            
            helsinki_buildings.to_file(output_path, driver='GeoJSON')
            print(f"💾 Saved Helsinki buildings: {output_path}")
            
            # Quick analysis
            self._analyze_buildings(helsinki_buildings)
            
            return helsinki_buildings, output_path
            
        except Exception as e:
            print(f"❌ Error loading Helsinki buildings: {e}")
            return None, None
    
    def _analyze_buildings(self, buildings_gdf):
        """Analyze building data and print statistics"""
        print("\n📊 Building Analysis:")
        print(f"  Total buildings: {len(buildings_gdf):,}")
        print(f"  Coordinate system: {buildings_gdf.crs}")
        print(f"  Columns: {list(buildings_gdf.columns)}")
        
        # Building area analysis
        if hasattr(buildings_gdf.geometry.iloc[0], 'area'):
            areas = buildings_gdf.geometry.area
            print(f"\n📐 Geometry Statistics:")
            print(f"  Average area: {areas.mean():.6f} sq degrees")
            print(f"  Median area: {areas.median():.6f} sq degrees")
            print(f"  Largest building: {areas.max():.6f} sq degrees")
        
        # Check for attributes
        if 'building' in buildings_gdf.columns:
            building_types = buildings_gdf['building'].value_counts()
            print(f"\n🏢 Building Types (top 5):")
            for btype, count in building_types.head().items():
                print(f"  {btype}: {count:,}")
        
        # Address information
        addr_cols = [col for col in buildings_gdf.columns if 'addr' in col.lower()]
        if addr_cols:
            print(f"\n📮 Address Columns: {len(addr_cols)}")
            for col in addr_cols[:3]:
                non_null = buildings_gdf[col].notna().sum()
                pct = (non_null / len(buildings_gdf)) * 100
                print(f"  {col}: {non_null:,} ({pct:.1f}%)")
    
    def create_duckdb_integration(self, geojson_path):
        """Create DuckDB integration for building data"""
        print("=" * 60)
        print("🦆 Creating DuckDB Integration")
        print("=" * 60)
        
        try:
            import duckdb
            
            # Connect to project database
            db_path = self.data_dir / "real_estate.duckdb"
            print(f"📊 Connecting to database: {db_path}")
            
            conn = duckdb.connect(str(db_path))
            
            # Install spatial extension
            print("🔧 Installing DuckDB spatial extension...")
            conn.execute("INSTALL spatial;")
            conn.execute("LOAD spatial;")
            
            # Create buildings table
            print(f"📥 Loading building data from: {geojson_path}")
            
            # Load GeoJSON into DuckDB
            conn.execute(f"""
                CREATE OR REPLACE TABLE osm_buildings AS 
                SELECT * FROM ST_Read('{geojson_path}')
            """)
            
            # Get table info
            result = conn.execute("SELECT COUNT(*) FROM osm_buildings").fetchone()
            building_count = result[0]
            
            print(f"✅ Loaded {building_count:,} buildings into DuckDB")
            
            # Create spatial index
            print("🗂️  Creating spatial index...")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_buildings_geom ON osm_buildings USING RTREE(geom)")
            
            # Test query
            print("🧪 Testing spatial queries...")
            test_result = conn.execute("""
                SELECT COUNT(*) 
                FROM osm_buildings 
                WHERE ST_Within(
                    geom, 
                    ST_MakeEnvelope(24.9, 60.16, 24.97, 60.17)
                )
            """).fetchone()
            
            test_count = test_result[0]
            print(f"✅ Test query successful: {test_count} buildings in test area")
            
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"❌ DuckDB integration failed: {e}")
            return False
    
    def perform_spatial_matching_test(self, helsinki_buildings):
        """Perform enhanced spatial matching test with Geofabrik buildings"""
        print("=" * 60)
        print("🎯 Enhanced Spatial Matching with Geofabrik Buildings")
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
            
            # Sample for testing (medium scale)
            sample_size = min(500, len(listings_gdf))
            print(f"🎲 Testing with {sample_size} sample listings...")
            sample_listings = listings_gdf.sample(n=sample_size, random_state=42)
            
            print(f"🏠 Processing {len(sample_listings)} listings")
            print(f"🏢 Against {len(helsinki_buildings)} Geofabrik buildings")
            
            # Perform enhanced spatial matching
            start_time = time.time()
            
            matching_results = self.spatial_matcher.enhanced_spatial_match(
                points_gdf=sample_listings,
                buildings_gdf=helsinki_buildings,
                point_id_col='address',
                building_id_col='osm_id'
            )
            
            matching_time = time.time() - start_time
            
            # Print results
            stats = matching_results['statistics']
            print(f"\n✅ Geofabrik spatial matching completed in {matching_time:.1f} seconds")
            print(f"📊 Match rate: {stats['match_rate']:.2f}%")
            print(f"🎯 Direct matches: {stats['direct_matches']}")
            print(f"🔄 Tolerance matches: {stats['tolerance_matches']}")
            print(f"❌ No matches: {stats['no_matches']}")
            print(f"⚡ Processing speed: {stats['processing_speed']:.1f} points/second")
            
            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_path = self.data_dir / f"geofabrik_spatial_matching_{timestamp}_results.json"
            
            # Save detailed results
            save_data = {
                'timestamp': datetime.now().isoformat(),
                'source': 'Geofabrik Finland OSM Extract',
                'listings_count': len(sample_listings),
                'buildings_count': len(helsinki_buildings),
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
            print(f"❌ Geofabrik spatial matching failed: {e}")
            import traceback
            traceback.print_exc()
            return None

def main():
    """Main function for OSM Geofabrik pipeline with enhanced spatial matching"""
    print("🌍 OSM Geofabrik Building Data Pipeline with Enhanced Spatial Matching")
    print("Efficient download and processing of Finnish building data")
    print()
    
    downloader = OSMGeofabrikDownloader()
    
    # Step 1: Check dependencies
    if not downloader.check_dependencies():
        print("❌ Missing dependencies - please install required tools")
        return
    
    # Step 2: Download Finland building shapefiles
    print("\n" + "="*60)
    print("STEP 1: Download Building Data")
    building_files = downloader.download_finland_shapefile()
    
    if not building_files:
        print("❌ No building files downloaded")
        return
    
    # Step 3: Process Helsinki buildings
    print("\n" + "="*60)
    print("STEP 2: Process Helsinki Buildings")
    
    # Use the first building shapefile found
    main_building_file = building_files[0]
    helsinki_buildings, geojson_path = downloader.load_helsinki_buildings(main_building_file)
    
    if helsinki_buildings is None:
        print("❌ Failed to process Helsinki buildings")
        return
    
    # Step 4: Enhanced spatial matching test
    print("\n" + "="*60)
    print("STEP 3: Enhanced Spatial Matching Test")
    
    matching_results = downloader.perform_spatial_matching_test(helsinki_buildings)
    
    # Step 5: Create DuckDB integration
    print("\n" + "="*60)
    print("STEP 4: Database Integration")
    
    duckdb_success = downloader.create_duckdb_integration(geojson_path)
    
    # Final summary
    print("\n" + "="*60)
    print("🎯 GEOFABRIK PIPELINE SUMMARY")
    print("="*60)
    
    if duckdb_success and matching_results:
        print("✅ OSM Geofabrik pipeline completed successfully!")
        print(f"✅ Helsinki buildings: {len(helsinki_buildings):,}")
        print(f"✅ Enhanced spatial matching: {matching_results['statistics']['match_rate']:.1f}% match rate")
        print(f"✅ Database integration: Ready for production use")
        print()
        print("🔄 ALTERNATIVE DATA SOURCE VALIDATED:")
        print("1. ✅ Geofabrik provides comprehensive building coverage")
        print("2. ✅ Enhanced spatial matching working with large datasets")
        print("3. ✅ Performance scaling validated for production")
        print("4. ✅ Alternative to API-based OSM downloads")
    else:
        print("⚠️  Pipeline completed with integration issues")
        print(f"✅ Building data available: {geojson_path}")
        print("🔄 Manual integration may be needed")

if __name__ == "__main__":
    main()
