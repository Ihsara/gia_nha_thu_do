#!/usr/bin/env python3
"""
Building Property Analyzer
Migrated from building_property_investigator.py to package structure
Analyzes specific OSM building properties for address matching enhancement.
"""

import geopandas as gpd
import pandas as pd
import json
from pathlib import Path
from shapely.geometry import Point
import folium
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


class BuildingAnalyzer:
    """Analyzes OSM building properties for address matching and investigation"""
    
    def __init__(self, 
                 buildings_file: str = "data/helsinki_buildings_20250711_041142.geojson",
                 output_dir: str = "output/visualization/maps/"):
        """Initialize building analyzer
        
        Args:
            buildings_file: Path to OSM buildings GeoJSON file
            output_dir: Directory for output visualizations
        """
        self.buildings_file = buildings_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.buildings_gdf = None
        
    def load_osm_buildings(self) -> gpd.GeoDataFrame:
        """Load Helsinki OSM building footprints"""
        if not Path(self.buildings_file).exists():
            raise FileNotFoundError(f"OSM building data not found: {self.buildings_file}")
        
        self.buildings_gdf = gpd.read_file(self.buildings_file)
        print(f"Loaded {len(self.buildings_gdf)} Helsinki building footprints")
        return self.buildings_gdf
    
    def load_validation_results(self, 
                               buffer_matches_file: str = "buffer_matches_detailed_20250711_053227.json",
                               no_matches_file: str = "no_matches_detailed_20250711_053227.json",
                               address_analysis_file: str = "address_analysis_20250711_053227.json") -> Dict[str, List]:
        """Load detailed validation results for context
        
        Args:
            buffer_matches_file: Path to buffer matches JSON
            no_matches_file: Path to no matches JSON
            address_analysis_file: Path to address analysis JSON
            
        Returns:
            Dictionary containing all loaded matches
        """
        results = {"matches": []}
        
        # Load buffer matches (if available)
        if Path(buffer_matches_file).exists():
            with open(buffer_matches_file, 'r', encoding='utf-8') as f:
                buffer_matches = json.load(f)
                results["matches"].extend(buffer_matches)
                print(f"Loaded {len(buffer_matches)} buffer matches")
        
        # Load no matches (if available)
        if Path(no_matches_file).exists():
            with open(no_matches_file, 'r', encoding='utf-8') as f:
                no_matches = json.load(f)
                results["matches"].extend(no_matches)
                print(f"Loaded {len(no_matches)} no matches")
        
        # Load address analysis (if available)
        if Path(address_analysis_file).exists():
            with open(address_analysis_file, 'r', encoding='utf-8') as f:
                address_analysis = json.load(f)
                if isinstance(address_analysis, list):
                    results["matches"].extend(address_analysis)
                    print(f"Loaded {len(address_analysis)} from address analysis")
        
        print(f"Total loaded validation results: {len(results['matches'])} matches")
        return results
    
    def investigate_building_by_id(self, building_id: int) -> Optional[pd.Series]:
        """Investigate specific building by OSM ID
        
        Args:
            building_id: OSM building ID to investigate
            
        Returns:
            Building information as pandas Series or None if not found
        """
        if self.buildings_gdf is None:
            self.load_osm_buildings()
            
        building = self.buildings_gdf[self.buildings_gdf['osm_id'] == building_id]
        
        if building.empty:
            print(f"❌ Building ID {building_id} not found in OSM data")
            return None
        
        building_info = building.iloc[0]
        
        print(f"\n🏢 BUILDING ID {building_id} INVESTIGATION:")
        print("=" * 50)
        print(f"OSM ID: {building_info['osm_id']}")
        print(f"Feature Class: {building_info.get('fclass', 'N/A')}")
        print(f"Building Type: {building_info.get('type', 'N/A')}")
        print(f"Name: {building_info.get('name', 'N/A')}")
        print(f"Code: {building_info.get('code', 'N/A')}")
        
        # Check for address fields (OSM addr:* pattern)
        addr_fields = [col for col in building.columns if col.startswith('addr:')]
        if addr_fields:
            print("\n📍 ADDRESS FIELDS FOUND:")
            for field in addr_fields:
                value = building_info.get(field, 'N/A')
                print(f"  {field}: {value}")
        else:
            print("\n❌ NO ADDRESS FIELDS FOUND (addr:* pattern)")
        
        # Get geometry info
        geom = building_info.geometry
        centroid = geom.centroid
        area = geom.area
        
        print(f"\n📐 GEOMETRY INFORMATION:")
        print(f"  Centroid: ({centroid.x:.6f}, {centroid.y:.6f})")
        print(f"  Area: {area:.8f} square degrees")
        print(f"  Geometry Type: {geom.geom_type}")
        
        # Check all available fields
        print(f"\n📋 ALL AVAILABLE FIELDS:")
        for col in building.columns:
            if col != 'geometry':
                value = building_info.get(col, 'N/A')
                print(f"  {col}: {value}")
        
        return building_info
    
    def find_buildings_near_address(self, 
                                  address_coords: Tuple[float, float], 
                                  radius_degrees: float = 0.002) -> Optional[gpd.GeoDataFrame]:
        """Find buildings near specific coordinates
        
        Args:
            address_coords: (longitude, latitude) coordinates
            radius_degrees: Search radius in degrees
            
        Returns:
            GeoDataFrame of nearby buildings sorted by distance
        """
        if self.buildings_gdf is None:
            self.load_osm_buildings()
            
        point = Point(address_coords)
        buffer = point.buffer(radius_degrees)
        
        nearby_buildings = self.buildings_gdf[self.buildings_gdf.intersects(buffer)]
        
        if nearby_buildings.empty:
            print(f"❌ No buildings found within {radius_degrees} degrees of coordinates")
            return None
        
        # Calculate distances and sort
        distances = nearby_buildings.geometry.distance(point)
        nearby_buildings = nearby_buildings.copy()
        nearby_buildings['distance'] = distances
        nearby_buildings = nearby_buildings.sort_values('distance')
        
        print(f"\n🎯 FOUND {len(nearby_buildings)} BUILDINGS NEARBY:")
        print("=" * 50)
        
        for idx, (_, building) in enumerate(nearby_buildings.head(5).iterrows()):
            print(f"\n{idx+1}. Building OSM ID: {building['osm_id']}")
            print(f"   Distance: {building['distance']:.6f} degrees (~{building['distance']*111000:.1f}m)")
            print(f"   Type: {building.get('type', 'N/A')}")
            print(f"   Name: {building.get('name', 'N/A')}")
            print(f"   Feature Class: {building.get('fclass', 'N/A')}")
            
            # Check for address fields
            addr_fields = [col for col in building.index if col.startswith('addr:')]
            if addr_fields:
                print(f"   Address fields:")
                for field in addr_fields:
                    print(f"     {field}: {building.get(field, 'N/A')}")
        
        return nearby_buildings
    
    def investigate_listings_by_address(self, 
                                      target_addresses: List[str], 
                                      validation_results: Dict[str, List]) -> Dict[str, List]:
        """Find listings by address pattern
        
        Args:
            target_addresses: List of address patterns to search for
            validation_results: Validation results containing matches
            
        Returns:
            Dictionary mapping addresses to found listings
        """
        matches = validation_results['matches']
        found_results = {}
        
        for target_address in target_addresses:
            print(f"\n🔍 SEARCHING FOR: {target_address}")
            print("=" * 50)
            
            found_listings = []
            for match in matches:
                listing_address = match.get('listing_address', '')
                if target_address.lower() in listing_address.lower():
                    found_listings.append(match)
            
            found_results[target_address] = found_listings
            
            if found_listings:
                print(f"✅ Found {len(found_listings)} matching listings:")
                for listing in found_listings:
                    print(f"\n  📍 Listing: {listing['listing_address']}")
                    print(f"     Coordinates: ({listing['longitude']}, {listing['latitude']})")
                    print(f"     Match Type: {listing['match_type']}")
                    if listing['match_type'] != 'no_match':
                        print(f"     Building OSM ID: {listing['building_osm_id']}")
                        if 'distance' in listing:
                            print(f"     Distance: {listing['distance']:.6f} degrees")
            else:
                print(f"❌ No listings found matching '{target_address}'")
        
        return found_results
    
    def analyze_osm_address_patterns(self) -> Dict[str, Any]:
        """Analyze address patterns in OSM data
        
        Returns:
            Analysis results as dictionary
        """
        if self.buildings_gdf is None:
            self.load_osm_buildings()
            
        print("\n" + "="*60)
        print("OSM ADDRESS PATTERN ANALYSIS")
        print("="*60)
        
        # Check how many buildings have various address fields
        addr_columns = [col for col in self.buildings_gdf.columns if col.startswith('addr:')]
        name_buildings = self.buildings_gdf[self.buildings_gdf['name'].notna()].shape[0]
        
        analysis = {
            'total_buildings': len(self.buildings_gdf),
            'buildings_with_name': name_buildings,
            'addr_columns': addr_columns,
            'addr_field_counts': {}
        }
        
        print(f"\nOSM Address Field Analysis:")
        print(f"  Total buildings: {analysis['total_buildings']}")
        print(f"  Buildings with name: {analysis['buildings_with_name']}")
        
        if addr_columns:
            print(f"  Address fields found: {addr_columns}")
            for col in addr_columns:
                count = self.buildings_gdf[self.buildings_gdf[col].notna()].shape[0]
                analysis['addr_field_counts'][col] = count
                print(f"  Buildings with {col}: {count}")
        else:
            print("  ❌ No addr:* fields found in OSM data")
        
        return analysis
    
    def create_investigation_visualization(self, 
                                        specific_buildings: List[pd.Series], 
                                        output_filename: Optional[str] = None) -> str:
        """Create visualization of investigated buildings
        
        Args:
            specific_buildings: List of building Series objects to visualize
            output_filename: Optional custom filename
            
        Returns:
            Path to created visualization file
        """
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"building_investigation_{timestamp}.html"
        
        output_path = self.output_dir / output_filename
        
        # Calculate center for map
        if specific_buildings:
            center_lat = sum(b.geometry.centroid.y for b in specific_buildings) / len(specific_buildings)
            center_lon = sum(b.geometry.centroid.x for b in specific_buildings) / len(specific_buildings)
        else:
            center_lat, center_lon = 60.1699, 24.9384  # Helsinki center
        
        # Create map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=15,
            tiles='OpenStreetMap'
        )
        
        # Add investigated buildings
        for idx, building in enumerate(specific_buildings):
            centroid = building.geometry.centroid
            
            # Create popup with building information
            popup_html = f"""
            <div style="width: 300px;">
                <h4>🏢 Building {idx+1}</h4>
                <p><strong>OSM ID:</strong> {building['osm_id']}</p>
                <p><strong>Type:</strong> {building.get('type', 'N/A')}</p>
                <p><strong>Name:</strong> {building.get('name', 'N/A')}</p>
                <p><strong>Feature Class:</strong> {building.get('fclass', 'N/A')}</p>
                <p><strong>Coordinates:</strong> ({centroid.x:.6f}, {centroid.y:.6f})</p>
            </div>
            """
            
            folium.Marker(
                location=[centroid.y, centroid.x],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color='red', icon='building')
            ).add_to(m)
            
            # Add building footprint
            if building.geometry.geom_type == 'Polygon':
                coords = [[point[1], point[0]] for point in building.geometry.exterior.coords]
                folium.Polygon(
                    locations=coords,
                    color='red',
                    weight=2,
                    fillColor='red',
                    fillOpacity=0.3,
                    popup=f"Building {building['osm_id']}"
                ).add_to(m)
        
        # Save map
        m.save(output_path)
        print(f"\n💾 Investigation visualization saved: {output_path}")
        return str(output_path)
    
    def run_comprehensive_investigation(self, 
                                      target_building_ids: List[int] = [19728651],
                                      target_addresses: List[str] = ["Vanhanlinnankuja 1 C", "Rantakartanontie 8", "Rantakartanontie 2 K"],
                                      validation_files: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Run comprehensive building investigation
        
        Args:
            target_building_ids: List of building OSM IDs to investigate
            target_addresses: List of addresses to search for in listings
            validation_files: Custom validation file paths
            
        Returns:
            Complete investigation results
        """
        print("🔍 OSM BUILDING PROPERTY INVESTIGATOR")
        print("=" * 60)
        print("Investigating specific buildings mentioned in user feedback")
        
        results = {
            'buildings_investigated': [],
            'listings_found': {},
            'nearby_buildings': [],
            'address_analysis': {},
            'visualization_path': None
        }
        
        try:
            # Load data
            self.load_osm_buildings()
            
            if validation_files:
                validation_results = self.load_validation_results(**validation_files)
            else:
                validation_results = self.load_validation_results()
            
            # Investigate specific buildings
            investigated_buildings = []
            
            for building_id in target_building_ids:
                print(f"\n" + "="*60)
                print(f"INVESTIGATING BUILDING ID {building_id}")
                building_info = self.investigate_building_by_id(building_id)
                if building_info is not None:
                    investigated_buildings.append(building_info)
                    results['buildings_investigated'].append(building_info.to_dict())
            
            # Search for target addresses in listings
            print("\n" + "="*60)
            print("INVESTIGATING TARGET ADDRESSES IN LISTINGS")
            listings_found = self.investigate_listings_by_address(target_addresses, validation_results)
            results['listings_found'] = listings_found
            
            # Find buildings near specific coordinates (if applicable)
            print("\n" + "="*60)
            print("INVESTIGATING AREA BUILDINGS")
            
            # Example: Rantakartanontie area
            rantakartano_coords = (24.9600, 60.2100)  # Approximate coordinates
            nearby_buildings = self.find_buildings_near_address(rantakartano_coords)
            if nearby_buildings is not None and not nearby_buildings.empty:
                nearby_list = nearby_buildings.head(3).to_dict('records')
                investigated_buildings.extend([pd.Series(b) for b in nearby_list])
                results['nearby_buildings'] = nearby_list
            
            # Analyze OSM address patterns
            address_analysis = self.analyze_osm_address_patterns()
            results['address_analysis'] = address_analysis
            
            # Create investigation visualization
            if investigated_buildings:
                viz_path = self.create_investigation_visualization(investigated_buildings)
                results['visualization_path'] = viz_path
            
            # Generate summary
            self._print_investigation_summary(results, address_analysis)
            
        except Exception as e:
            print(f"❌ Error during investigation: {e}")
            raise
        
        return results
    
    def _print_investigation_summary(self, results: Dict[str, Any], address_analysis: Dict[str, Any]):
        """Print investigation summary"""
        print("\n" + "="*60)
        print("📊 INVESTIGATION SUMMARY")
        print("="*60)
        
        print(f"✅ Loaded {address_analysis['total_buildings']} Helsinki building footprints")
        print(f"✅ Analyzed {len(results['buildings_investigated'])} specific buildings")
        
        if results['visualization_path']:
            print(f"✅ Created investigation visualization: {results['visualization_path']}")
        
        print(f"\n🔍 KEY FINDINGS:")
        print(f"  • Buildings investigated: {len(results['buildings_investigated'])}")
        print(f"  • OSM buildings with names: {address_analysis['buildings_with_name']}")
        print(f"  • OSM address fields available: {len(address_analysis['addr_columns'])}")
        
        total_listings = sum(len(listings) for listings in results['listings_found'].values())
        print(f"  • Listings found for target addresses: {total_listings}")
        
        if not address_analysis['addr_columns']:
            print(f"\n⚠️  CRITICAL ISSUE: No addr:* fields found in OSM building data")
            print(f"     This explains address matching challenges")
            print(f"     Alternative: Use building 'name' field and proximity matching")
        
        print(f"\n📋 NEXT STEPS:")
        print(f"  1. Examine building names vs listing addresses")
        print(f"  2. Implement fuzzy string matching for building names")
        print(f"  3. Enhance buffer-based matching with address similarity")
        print(f"  4. Create address normalization pipeline")


def investigate_building_properties():
    """Legacy function wrapper for backward compatibility"""
    analyzer = BuildingAnalyzer()
    return analyzer.run_comprehensive_investigation()


if __name__ == "__main__":
    investigate_building_properties()
