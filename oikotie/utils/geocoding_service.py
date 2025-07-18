#!/usr/bin/env python3
"""
Enhanced Geocoding Service
Provides multiple geocoding options including Google Maps API and other reliable services
"""

import requests
import time
import json
from typing import Tuple, Optional, Dict, List
from geopy.geocoders import Nominatim
import duckdb

class EnhancedGeocodingService:
    def __init__(self, google_api_key: Optional[str] = None):
        self.google_api_key = google_api_key
        self.nominatim = Nominatim(user_agent="oikotie_enhanced_geocoding")
        self.db_path = "data/real_estate.duckdb"
        
    def geocode_with_google(self, address: str, city: str = "Helsinki", country: str = "Finland") -> Optional[Tuple[float, float]]:
        """Geocode using Google Maps Geocoding API"""
        if not self.google_api_key:
            print("⚠️  Google API key not provided")
            return None
            
        # Format address for Google
        full_address = f"{address}, {city}, {country}"
        
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'address': full_address,
            'key': self.google_api_key,
            'components': f'country:{country}|locality:{city}'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                location = data['results'][0]['geometry']['location']
                return (location['lat'], location['lng'])
            else:
                print(f"❌ Google geocoding failed: {data.get('status', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"❌ Google geocoding error: {e}")
            return None
    
    def geocode_with_nominatim(self, address: str, city: str = "Helsinki", country: str = "Finland") -> Optional[Tuple[float, float]]:
        """Geocode using OpenStreetMap Nominatim (free)"""
        try:
            full_address = f"{address}, {city}, {country}"
            
            location = self.nominatim.geocode(full_address, timeout=10)
            if location:
                return (location.latitude, location.longitude)
            else:
                return None
                
        except Exception as e:
            print(f"❌ Nominatim geocoding error: {e}")
            return None
    
    def geocode_with_here(self, address: str, api_key: str, city: str = "Helsinki", country: str = "Finland") -> Optional[Tuple[float, float]]:
        """Geocode using HERE Maps API (alternative to Google)"""
        try:
            url = "https://geocode.search.hereapi.com/v1/geocode"
            params = {
                'q': f"{address}, {city}, {country}",
                'apiKey': api_key,
                'limit': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('items'):
                position = data['items'][0]['position']
                return (position['lat'], position['lng'])
            else:
                return None
                
        except Exception as e:
            print(f"❌ HERE geocoding error: {e}")
            return None
    
    def geocode_with_fallback(self, address: str, google_key: Optional[str] = None, here_key: Optional[str] = None) -> Optional[Tuple[float, float]]:
        """Try multiple geocoding services with fallback"""
        
        # Try Google first (most accurate)
        if google_key:
            result = self.geocode_with_google(address)
            if result:
                print(f"✅ Google geocoding successful for {address}")
                return result
        
        # Try HERE as backup
        if here_key:
            result = self.geocode_with_here(address, here_key)
            if result:
                print(f"✅ HERE geocoding successful for {address}")
                return result
        
        # Fall back to Nominatim (free)
        result = self.geocode_with_nominatim(address)
        if result:
            print(f"✅ Nominatim geocoding successful for {address}")
            return result
        
        print(f"❌ All geocoding services failed for {address}")
        return None
    
    def validate_coordinates(self, address: str, lat: float, lon: float, tolerance: float = 0.001) -> Dict:
        """Validate coordinates against multiple services"""
        print(f"\n🔍 Validating coordinates for: {address}")
        print(f"   Current: ({lat:.6f}, {lon:.6f})")
        
        results = {
            'address': address,
            'current_coords': (lat, lon),
            'validations': {},
            'is_accurate': True,
            'max_difference': 0.0,
            'recommendation': 'keep_current'
        }
        
        # Test with Nominatim
        nom_coords = self.geocode_with_nominatim(address)
        if nom_coords:
            nom_lat, nom_lon = nom_coords
            lat_diff = abs(lat - nom_lat)
            lon_diff = abs(lon - nom_lon)
            max_diff = max(lat_diff, lon_diff)
            
            results['validations']['nominatim'] = {
                'coords': nom_coords,
                'difference': (lat_diff, lon_diff),
                'max_difference': max_diff,
                'within_tolerance': max_diff <= tolerance
            }
            
            if max_diff > results['max_difference']:
                results['max_difference'] = max_diff
            
            print(f"   Nominatim: ({nom_lat:.6f}, {nom_lon:.6f}) - Diff: {max_diff:.6f}")
        
        # Determine if coordinates are accurate
        if results['max_difference'] > tolerance:
            results['is_accurate'] = False
            results['recommendation'] = 'update_coordinates'
            print(f"   ⚠️  INACCURATE: Difference {results['max_difference']:.6f} > tolerance {tolerance}")
        else:
            print(f"   ✅ ACCURATE: Within tolerance")
        
        return results
    
    def bulk_validate_database_coordinates(self, sample_size: int = 50, tolerance: float = 0.001):
        """Validate a sample of coordinates from the database"""
        print(f"\n🔍 BULK COORDINATE VALIDATION")
        print(f"Sample size: {sample_size}, Tolerance: {tolerance}")
        print("=" * 50)
        
        conn = duckdb.connect(self.db_path)
        
        # Get random sample
        sample_addresses = conn.execute(f"""
            SELECT address, lat, lon
            FROM address_locations 
            WHERE lat IS NOT NULL 
            ORDER BY RANDOM() 
            LIMIT {sample_size}
        """).fetchall()
        
        results = {
            'total_tested': len(sample_addresses),
            'accurate_count': 0,
            'inaccurate_count': 0,
            'failed_validation': 0,
            'inaccurate_addresses': [],
            'accuracy_rate': 0.0
        }
        
        for i, (address, lat, lon) in enumerate(sample_addresses, 1):
            try:
                print(f"\n{i}/{len(sample_addresses)}: {address}")
                validation = self.validate_coordinates(address, lat, lon, tolerance)
                
                if validation['is_accurate']:
                    results['accurate_count'] += 1
                else:
                    results['inaccurate_count'] += 1
                    results['inaccurate_addresses'].append({
                        'address': address,
                        'current_coords': (lat, lon),
                        'max_difference': validation['max_difference'],
                        'validations': validation['validations']
                    })
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ Validation failed for {address}: {e}")
                results['failed_validation'] += 1
        
        results['accuracy_rate'] = (results['accurate_count'] / results['total_tested']) * 100
        
        print(f"\n📊 VALIDATION SUMMARY")
        print("=" * 30)
        print(f"Total tested: {results['total_tested']}")
        print(f"Accurate: {results['accurate_count']} ({results['accuracy_rate']:.1f}%)")
        print(f"Inaccurate: {results['inaccurate_count']}")
        print(f"Failed validation: {results['failed_validation']}")
        
        if results['inaccurate_addresses']:
            print(f"\n⚠️  INACCURATE ADDRESSES:")
            for addr_info in results['inaccurate_addresses'][:5]:  # Show top 5
                print(f"   {addr_info['address']} - Diff: {addr_info['max_difference']:.6f}")
        
        return results
    
    def update_database_coordinates(self, google_key: Optional[str] = None, here_key: Optional[str] = None, 
                                  sample_size: int = 10, dry_run: bool = True):
        """Update inaccurate coordinates in database"""
        print(f"\n🔧 COORDINATE UPDATE PROCESS")
        print(f"Sample size: {sample_size}, Dry run: {dry_run}")
        print("=" * 40)
        
        # First validate to find inaccurate coordinates
        validation_results = self.bulk_validate_database_coordinates(sample_size)
        
        if not validation_results['inaccurate_addresses']:
            print("✅ No inaccurate coordinates found - no updates needed")
            return
        
        conn = duckdb.connect(self.db_path)
        updated_count = 0
        
        for addr_info in validation_results['inaccurate_addresses']:
            address = addr_info['address']
            current_coords = addr_info['current_coords']
            
            print(f"\n🔄 Updating: {address}")
            print(f"   Current: {current_coords}")
            
            # Get new coordinates
            new_coords = self.geocode_with_fallback(address, google_key, here_key)
            
            if new_coords:
                new_lat, new_lon = new_coords
                print(f"   New: ({new_lat:.6f}, {new_lon:.6f})")
                
                if not dry_run:
                    # Update database
                    conn.execute("""
                        UPDATE address_locations 
                        SET lat = ?, lon = ? 
                        WHERE address = ?
                    """, [new_lat, new_lon, address])
                    print(f"   ✅ Updated in database")
                else:
                    print(f"   🔍 DRY RUN - would update")
                
                updated_count += 1
            else:
                print(f"   ❌ Could not get new coordinates")
            
            time.sleep(1)  # Rate limiting
        
        if not dry_run:
            print(f"\n✅ Updated {updated_count} coordinates in database")
        else:
            print(f"\n🔍 DRY RUN: Would update {updated_count} coordinates")

if __name__ == "__main__":
    # Example usage
    service = EnhancedGeocodingService()
    
    # Validate sample coordinates
    results = service.bulk_validate_database_coordinates(sample_size=10)
    
    # Optionally update coordinates (dry run by default)
    # service.update_database_coordinates(sample_size=5, dry_run=True)
