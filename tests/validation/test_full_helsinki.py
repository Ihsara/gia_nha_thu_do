#!/usr/bin/env python3
"""
Enhanced OSM Building Validation with Address Analysis
Investigating specific address matching patterns and discrepancies
Following task requirements for address comparison logging
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import folium
from folium import plugins
import duckdb
from pathlib import Path
import random
from datetime import datetime
import json
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import time
import re
from difflib import SequenceMatcher

class EnhancedOSMValidator:
    """Enhanced OSM validator with detailed address analysis and logging"""
    
    def __init__(self):
        self.db_path = "data/real_estate.duckdb"
        self.osm_buildings_path = "data/helsinki_buildings_20250711_041142.geojson"
        self.output_dir = Path(".")
        self.max_workers = min(8, mp.cpu_count())
        
        # Address analysis storage
        self.address_analysis = {
            'buffer_matches': [],
            'no_matches': [],
            'address_patterns': {},
            'specific_cases': {}
        }
        
    def normalize_address(self, address):
        """Normalize address for comparison"""
        if not address or pd.isna(address):
            return ""
        
        # Convert to lowercase and strip
        normalized = str(address).lower().strip()
        
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Common patterns
        normalized = normalized.replace('katu', 'k.')
        normalized = normalized.replace('tie ', 'tie')
        normalized = normalized.replace('väylä', 'väylä')
        
        return normalized
    
    def extract_address_components(self, address):
        """Extract street name, number, and unit from address"""
        if not address or pd.isna(address):
            return {'street': '', 'number': '', 'unit': '', 'postal': ''}
        
        address_str = str(address).strip()
        
        # Extract postal code (5 digits)
        postal_match = re.search(r'\b(\d{5})\b', address_str)
        postal = postal_match.group(1) if postal_match else ''
        
        # Remove postal code and city for street analysis
        street_part = re.sub(r'\b\d{5}\b.*$', '', address_str).strip()
        
        # Extract street name and number/unit
        # Pattern: "Street name number unit"
        match = re.match(r'^(.+?)\s+(\d+(?:-\d+)?)\s*([A-Z](?:-[A-Z])?)?', street_part)
        
        if match:
            street = match.group(1).strip()
            number = match.group(2).strip()
            unit = match.group(3).strip() if match.group(3) else ''
        else:
            street = street_part
            number = ''
            unit = ''
        
        return {
            'street': street,
            'number': number, 
            'unit': unit,
            'postal': postal,
            'full': address_str
        }
    
    def calculate_address_similarity(self, addr1, addr2):
        """Calculate similarity between two addresses"""
        if not addr1 or not addr2 or pd.isna(addr1) or pd.isna(addr2):
            return 0.0
        
        norm1 = self.normalize_address(addr1)
        norm2 = self.normalize_address(addr2)
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def load_helsinki_listings_with_analysis(self):
        """Load Helsinki listings with specific cases for analysis"""
        print("=" * 60)
        print("📋 Loading Helsinki Listings for Enhanced Analysis")
        print("=" * 60)
        
        try:
            conn = duckdb.connect(self.db_path)
            
            # Load all listings with additional analysis
            query = """
            SELECT l.url as id, l.address, al.lat as latitude, al.lon as longitude,
                   l.price_eur as price, l.rooms, l.size_m2, l.listing_type, l.city
            FROM listings l
            JOIN address_locations al ON l.address = al.address
            WHERE al.lat IS NOT NULL AND al.lon IS NOT NULL AND l.city = 'Helsinki'
            ORDER BY l.price_eur
            """
            
            df = conn.execute(query).df()
            conn.close()
            
            print(f"✅ Loaded {len(df):,} Helsinki listings")
            
            # Check for specific problematic cases mentioned in task
            specific_cases = [
                'Salpausseläntie 4-8',
                'Ounasvaarantie 1 F',
                'Salpausseläntie',
                'Ounasvaarantie'
            ]
            
            print(f"\n🔍 Searching for specific problem cases:")
            for case in specific_cases:
                matches = df[df['address'].str.contains(case, case=False, na=False)]
                print(f"   📍 '{case}': {len(matches)} matches")
                if len(matches) > 0:
                    for _, match in matches.iterrows():
                        print(f"      → {match['address']}")
                        self.address_analysis['specific_cases'][case] = {
                            'found': True,
                            'addresses': matches['address'].tolist()
                        }
            
            return df
            
        except Exception as e:
            print(f"❌ Error loading listings: {e}")
            return pd.DataFrame()
    
    def load_osm_buildings_with_names(self):
        """Load OSM buildings with name analysis"""
        print("\n" + "=" * 60)
        print("🏗️  Loading OSM Buildings with Name Analysis")
        print("=" * 60)
        
        try:
            buildings_gdf = gpd.read_file(self.osm_buildings_path)
            print(f"✅ Loaded {len(buildings_gdf):,} OSM building footprints")
            
            # Analyze building names
            buildings_with_names = buildings_gdf[buildings_gdf['name'].notna() & (buildings_gdf['name'] != '')]
            print(f"📋 Buildings with names: {len(buildings_with_names):,}")
            
            if len(buildings_with_names) > 0:
                print(f"\n🏢 Sample building names:")
                sample_names = buildings_with_names['name'].head(10).tolist()
                for name in sample_names:
                    print(f"   → {name}")
                
                # Check for our specific problem addresses
                problem_streets = ['Salpausseläntie', 'Ounasvaarantie']
                for street in problem_streets:
                    matching_buildings = buildings_with_names[
                        buildings_with_names['name'].str.contains(street, case=False, na=False)
                    ]
                    print(f"\n📍 Buildings on {street}: {len(matching_buildings)}")
                    for _, building in matching_buildings.iterrows():
                        print(f"   → {building['name']} (ID: {building['osm_id']})")
            
            return buildings_gdf
            
        except Exception as e:
            print(f"❌ Error loading OSM buildings: {e}")
            return gpd.GeoDataFrame()
    
    def enhanced_spatial_matching(self, listings_df, buildings_gdf):
        """Enhanced spatial matching with detailed address logging"""
        print("\n" + "=" * 60)
        print(f"🔍 Enhanced Spatial Matching with Address Analysis")
        print("=" * 60)
        
        results = []
        buffer_matches_detailed = []
        no_matches_detailed = []
        
        print(f"Processing {len(listings_df):,} listings...")
        
        for idx, listing in listings_df.iterrows():
            if idx % 1000 == 0:
                print(f"   Progress: {idx:,}/{len(listings_df):,} ({idx/len(listings_df)*100:.1f}%)")
            
            # Create point geometry
            point = Point(listing['longitude'], listing['latitude'])
            listing_components = self.extract_address_components(listing['address'])
            
            # Step 1: Direct containment check
            containing_buildings = buildings_gdf[buildings_gdf.contains(point)]
            
            if not containing_buildings.empty:
                # Direct match found
                building = containing_buildings.iloc[0]
                building_name = building.get('name', '')
                
                results.append({
                    'listing_id': listing['id'],
                    'address': listing['address'],
                    'latitude': listing['latitude'],
                    'longitude': listing['longitude'],
                    'price': listing['price'],
                    'match_type': 'direct',
                    'building_id': building.get('osm_id', 'N/A'),
                    'building_name': building_name,
                    'distance_m': 0.0,
                    'matched': True,
                    'address_similarity': self.calculate_address_similarity(listing['address'], building_name)
                })
            else:
                # Step 2: Buffer search with detailed logging
                buffer_distance = 0.001  # ~100m
                buffered_point = point.buffer(buffer_distance)
                intersecting_buildings = buildings_gdf[buildings_gdf.intersects(buffered_point)]
                
                if not intersecting_buildings.empty:
                    # Find all buildings within buffer and analyze
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        distances = intersecting_buildings.geometry.distance(point)
                    
                    closest_idx = distances.idxmin()
                    closest_building = intersecting_buildings.loc[closest_idx]
                    closest_distance = distances.loc[closest_idx] * 111000  # Convert to meters
                    
                    building_name = closest_building.get('name', '')
                    
                    # Detailed buffer match analysis
                    buffer_analysis = {
                        'listing_address': listing['address'],
                        'listing_components': listing_components,
                        'closest_building_name': building_name,
                        'closest_building_id': closest_building.get('osm_id', 'N/A'),
                        'distance_m': closest_distance,
                        'address_similarity': self.calculate_address_similarity(listing['address'], building_name),
                        'nearby_buildings': []
                    }
                    
                    # Log all nearby buildings for analysis
                    for building_idx, building in intersecting_buildings.iterrows():
                        building_distance = distances.loc[building_idx] * 111000
                        building_name_nearby = building.get('name', '')
                        
                        buffer_analysis['nearby_buildings'].append({
                            'building_name': building_name_nearby,
                            'building_id': building.get('osm_id', 'N/A'),
                            'distance_m': building_distance,
                            'similarity': self.calculate_address_similarity(listing['address'], building_name_nearby)
                        })
                    
                    # Sort nearby buildings by similarity
                    buffer_analysis['nearby_buildings'].sort(key=lambda x: x['similarity'], reverse=True)
                    
                    buffer_matches_detailed.append(buffer_analysis)
                    
                    results.append({
                        'listing_id': listing['id'],
                        'address': listing['address'],
                        'latitude': listing['latitude'],
                        'longitude': listing['longitude'],
                        'price': listing['price'],
                        'match_type': 'buffer',
                        'building_id': closest_building.get('osm_id', 'N/A'),
                        'building_name': building_name,
                        'distance_m': closest_distance,
                        'matched': True,
                        'address_similarity': self.calculate_address_similarity(listing['address'], building_name)
                    })
                else:
                    # No match - find nearest buildings within larger radius for analysis
                    larger_buffer = point.buffer(0.002)  # ~200m
                    nearby_buildings = buildings_gdf[buildings_gdf.intersects(larger_buffer)]
                    
                    no_match_analysis = {
                        'listing_address': listing['address'],
                        'listing_components': listing_components,
                        'latitude': listing['latitude'],
                        'longitude': listing['longitude'],
                        'nearby_buildings_200m': []
                    }
                    
                    if not nearby_buildings.empty:
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", UserWarning)
                            distances_200m = nearby_buildings.geometry.distance(point)
                        
                        for building_idx, building in nearby_buildings.iterrows():
                            building_distance = distances_200m.loc[building_idx] * 111000
                            building_name_nearby = building.get('name', '')
                            
                            no_match_analysis['nearby_buildings_200m'].append({
                                'building_name': building_name_nearby,
                                'building_id': building.get('osm_id', 'N/A'),
                                'distance_m': building_distance,
                                'similarity': self.calculate_address_similarity(listing['address'], building_name_nearby)
                            })
                        
                        # Sort by similarity
                        no_match_analysis['nearby_buildings_200m'].sort(key=lambda x: x['similarity'], reverse=True)
                    
                    no_matches_detailed.append(no_match_analysis)
                    
                    results.append({
                        'listing_id': listing['id'],
                        'address': listing['address'],
                        'latitude': listing['latitude'],
                        'longitude': listing['longitude'],
                        'price': listing['price'],
                        'match_type': 'none',
                        'building_id': None,
                        'building_name': None,
                        'distance_m': float('inf'),
                        'matched': False,
                        'address_similarity': 0.0
                    })
        
        # Store detailed analysis
        self.address_analysis['buffer_matches'] = buffer_matches_detailed
        self.address_analysis['no_matches'] = no_matches_detailed
        
        results_df = pd.DataFrame(results)
        
        # Print enhanced statistics
        total_listings = len(results_df)
        matched_listings = len(results_df[results_df['matched']])
        match_rate = (matched_listings / total_listings) * 100 if total_listings > 0 else 0
        
        direct_matches = len(results_df[results_df['match_type'] == 'direct'])
        buffer_matches = len(results_df[results_df['match_type'] == 'buffer'])
        no_matches = total_listings - matched_listings
        
        print(f"\n📊 ENHANCED MATCHING RESULTS:")
        print(f"   📋 Total listings: {total_listings:,}")
        print(f"   ✅ Overall match rate: {match_rate:.2f}%")
        print(f"   🎯 Direct matches: {direct_matches:,} ({direct_matches/total_listings*100:.1f}%)")
        print(f"   🔍 Buffer matches: {buffer_matches:,} ({buffer_matches/total_listings*100:.1f}%)")
        print(f"   ❌ No matches: {no_matches:,} ({no_matches/total_listings*100:.1f}%)")
        
        print(f"\n🔍 ADDRESS ANALYSIS COLLECTED:")
        print(f"   📍 Buffer match details: {len(buffer_matches_detailed):,}")
        print(f"   📍 No-match details: {len(no_matches_detailed):,}")
        
        return results_df
    
    def analyze_address_patterns(self):
        """Analyze collected address patterns for insights"""
        print("\n" + "=" * 60)
        print("🔍 Address Pattern Analysis")
        print("=" * 60)
        
        # Analyze buffer matches for naming patterns
        print("📍 BUFFER MATCH ANALYSIS:")
        high_similarity_buffers = []
        low_similarity_buffers = []
        
        for match in self.address_analysis['buffer_matches']:
            if match['address_similarity'] > 0.7:
                high_similarity_buffers.append(match)
            elif match['address_similarity'] < 0.3:
                low_similarity_buffers.append(match)
        
        print(f"   ✅ High similarity (>70%): {len(high_similarity_buffers)}")
        print(f"   ❌ Low similarity (<30%): {len(low_similarity_buffers)}")
        
        # Show examples of low similarity cases
        print(f"\n🔍 LOW SIMILARITY EXAMPLES (potential naming mismatches):")
        for i, match in enumerate(low_similarity_buffers[:5]):
            print(f"   {i+1}. Listing: '{match['listing_address']}'")
            print(f"      Building: '{match['closest_building_name']}' ({match['distance_m']:.1f}m)")
            print(f"      Similarity: {match['address_similarity']:.1%}")
            
            # Show best nearby building by similarity
            if match['nearby_buildings']:
                best_nearby = match['nearby_buildings'][0]
                print(f"      Best nearby: '{best_nearby['building_name']}' ({best_nearby['similarity']:.1%}, {best_nearby['distance_m']:.1f}m)")
            print()
        
        # Analyze no-matches
        print("📍 NO-MATCH ANALYSIS:")
        high_similarity_no_matches = []
        
        for no_match in self.address_analysis['no_matches']:
            if no_match['nearby_buildings_200m']:
                best_nearby = no_match['nearby_buildings_200m'][0]
                if best_nearby['similarity'] > 0.5:
                    high_similarity_no_matches.append({
                        **no_match,
                        'best_nearby': best_nearby
                    })
        
        print(f"   🎯 High similarity nearby (>50%): {len(high_similarity_no_matches)}")
        
        # Show examples of potential matches that were missed
        print(f"\n🔍 POTENTIAL MISSED MATCHES (no-match but high similarity nearby):")
        for i, no_match in enumerate(high_similarity_no_matches[:5]):
            best = no_match['best_nearby']
            print(f"   {i+1}. Listing: '{no_match['listing_address']}'")
            print(f"      Nearby: '{best['building_name']}' ({best['distance_m']:.1f}m, {best['similarity']:.1%})")
            print()
        
        # Specific case analysis
        print("📍 SPECIFIC CASE ANALYSIS:")
        for case, data in self.address_analysis['specific_cases'].items():
            if data.get('found'):
                print(f"   🎯 {case}: Found {len(data['addresses'])} listings")
                for address in data['addresses']:
                    print(f"      → {address}")
        
        return {
            'high_similarity_buffers': len(high_similarity_buffers),
            'low_similarity_buffers': len(low_similarity_buffers),
            'potential_missed_matches': len(high_similarity_no_matches),
            'examples': {
                'low_similarity_buffers': low_similarity_buffers[:5],
                'potential_missed_matches': high_similarity_no_matches[:5]
            }
        }
    
    def save_enhanced_analysis(self, results_df, pattern_analysis):
        """Save enhanced analysis results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed address analysis
        analysis_path = self.output_dir / f"address_analysis_{timestamp}.json"
        
        analysis_summary = {
            'timestamp': timestamp,
            'validation_type': 'enhanced_osm_address_analysis',
            'total_listings': len(results_df),
            'match_statistics': {
                'total_matched': len(results_df[results_df['matched']]),
                'match_rate_percent': (len(results_df[results_df['matched']]) / len(results_df)) * 100,
                'direct_matches': len(results_df[results_df['match_type'] == 'direct']),
                'buffer_matches': len(results_df[results_df['match_type'] == 'buffer']),
                'no_matches': len(results_df[results_df['match_type'] == 'none'])
            },
            'address_pattern_analysis': pattern_analysis,
            'specific_cases_found': self.address_analysis['specific_cases'],
            'detailed_buffer_matches_count': len(self.address_analysis['buffer_matches']),
            'detailed_no_matches_count': len(self.address_analysis['no_matches'])
        }
        
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_summary, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Enhanced analysis saved: {analysis_path}")
        
        # Save detailed buffer match analysis
        buffer_path = self.output_dir / f"buffer_matches_detailed_{timestamp}.json"
        with open(buffer_path, 'w', encoding='utf-8') as f:
            json.dump(self.address_analysis['buffer_matches'], f, indent=2, ensure_ascii=False)
        
        # Save detailed no-match analysis  
        no_match_path = self.output_dir / f"no_matches_detailed_{timestamp}.json"
        with open(no_match_path, 'w', encoding='utf-8') as f:
            json.dump(self.address_analysis['no_matches'], f, indent=2, ensure_ascii=False)
        
        print(f"💾 Detailed buffer matches: {buffer_path}")
        print(f"💾 Detailed no-matches: {no_match_path}")
        
        return analysis_path, buffer_path, no_match_path
    
    def run_enhanced_validation(self):
        """Run enhanced validation with address analysis"""
        print("🔍 Enhanced OSM Validation with Address Pattern Analysis")
        print("Investigating specific address matching discrepancies")
        print("=" * 60)
        
        # Load data with enhanced analysis
        listings_df = self.load_helsinki_listings_with_analysis()
        if listings_df.empty:
            print("❌ No listings loaded")
            return
        
        buildings_gdf = self.load_osm_buildings_with_names()
        if buildings_gdf.empty:
            print("❌ No buildings loaded")
            return
        
        # Perform enhanced spatial matching
        results_df = self.enhanced_spatial_matching(listings_df, buildings_gdf)
        
        # Analyze patterns
        pattern_analysis = self.analyze_address_patterns()
        
        # Save enhanced analysis
        analysis_paths = self.save_enhanced_analysis(results_df, pattern_analysis)
        
        print("\n" + "=" * 60)
        print("✅ ENHANCED VALIDATION COMPLETE")
        print("=" * 60)
        print("📊 Focus: Address matching pattern investigation")
        print("🎯 Goal: Identify naming discrepancies and improvement opportunities")
        print(f"💾 Analysis files created: {len(analysis_paths)}")
        
        return results_df, analysis_paths

def main():
    """Main function for enhanced validation"""
    validator = EnhancedOSMValidator()
    validator.run_enhanced_validation()

if __name__ == "__main__":
    main()
