#!/usr/bin/env python3
"""
Enhanced Geocoding Service with Unified Data Manager Integration
Provides high-accuracy address geocoding using multiple data sources with intelligent fallback
"""

import duckdb
import geopandas as gpd
import pandas as pd
from typing import Tuple, Optional, Dict, List, NamedTuple, Union, Any
from geopy.geocoders import Nominatim
from shapely.geometry import Point
from pathlib import Path
import re
import logging
from datetime import datetime
import hashlib

# Import the unified manager
from oikotie.data_sources import UnifiedDataManager, create_helsinki_manager


class GeocodeResult(NamedTuple):
    """Structured geocoding result with quality metrics."""
    latitude: float
    longitude: float
    confidence: float  # 0.0 to 1.0
    source: str       # Which data source provided the result
    method: str       # Geocoding method used
    original_address: str
    normalized_address: str
    quality_score: float  # Overall quality assessment


class AddressNormalizer:
    """Normalizes Finnish addresses for better matching."""
    
    def __init__(self):
        # Finnish address patterns
        self.street_type_mappings = {
            'katu': ['k', 'ktu', 'katu'],
            'tie': ['t', 'tie'],
            'kuja': ['kj', 'kuja'],
            'polku': ['p', 'polku', 'plk'],
            'väylä': ['väylä', 'vl'],
            'kari': ['kari'],
            'rinne': ['rinne', 'r'],
            'bulevardi': ['bulevardi', 'blvd', 'bul']
        }
        
        # Common abbreviations
        self.abbreviations = {
            'helsingin': 'helsinki',
            'hki': 'helsinki',
            'hel': 'helsinki'
        }
        
        # Postal code pattern for Helsinki area
        self.helsinki_postal_pattern = re.compile(r'^00\d{3}$')
    
    def normalize_address(self, address: str) -> str:
        """
        Normalize a Finnish address for better matching.
        
        Args:
            address: Raw address string
            
        Returns:
            Normalized address string
        """
        if not address:
            return ""
        
        # Convert to lowercase
        normalized = address.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Handle common abbreviations
        for abbrev, full in self.abbreviations.items():
            normalized = normalized.replace(abbrev, full)
        
        # Normalize street types
        for standard, variants in self.street_type_mappings.items():
            for variant in variants:
                # Match whole words to avoid partial replacements
                pattern = r'\b' + re.escape(variant) + r'\b'
                normalized = re.sub(pattern, standard, normalized)
        
        # Clean up street numbers (ensure space between name and number)
        normalized = re.sub(r'([a-zäöå])(\d)', r'\1 \2', normalized)
        
        # Remove punctuation except dashes and spaces
        normalized = re.sub(r'[^\w\s\-äöå]', '', normalized)
        
        return normalized.strip()
    
    def extract_components(self, address: str) -> Dict[str, str]:
        """
        Extract address components (street, number, city, postal code).
        
        Args:
            address: Address string to parse
            
        Returns:
            Dictionary with address components
        """
        components = {
            'street_name': '',
            'street_number': '',
            'city': '',
            'postal_code': '',
            'full_normalized': self.normalize_address(address)
        }
        
        normalized = components['full_normalized']
        
        # Extract postal code
        postal_match = re.search(r'\b\d{5}\b', normalized)
        if postal_match:
            components['postal_code'] = postal_match.group()
            normalized = normalized.replace(components['postal_code'], '').strip()
        
        # Extract city (Helsinki variations)
        city_match = re.search(r'\b(helsinki|hki|hel)\b', normalized)
        if city_match:
            components['city'] = 'helsinki'
            normalized = normalized.replace(city_match.group(), '').strip()
        
        # Extract street number (typically at the end)
        number_match = re.search(r'\b(\d+[a-z]?)\s*$', normalized)
        if number_match:
            components['street_number'] = number_match.group(1)
            normalized = normalized.replace(number_match.group(), '').strip()
        
        # Remaining text is street name
        components['street_name'] = normalized.strip()
        
        return components


class UnifiedGeocodingService:
    """
    Enhanced geocoding service using unified data manager with intelligent source selection.
    """
    
    def __init__(
        self,
        geopackage_path: str = "data/helsinki_topographic_data.gpkg",
        db_path: str = "data/real_estate.duckdb",
        cache_dir: str = "data/cache/geocoding",
        enable_logging: bool = True
    ):
        """
        Initialize the unified geocoding service.
        
        Args:
            geopackage_path: Path to Helsinki GeoPackage
            db_path: Path to DuckDB database
            cache_dir: Directory for geocoding cache
            enable_logging: Enable detailed logging
        """
        self.db_path = db_path
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize logging
        if enable_logging:
            logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize unified data manager
        self.manager = create_helsinki_manager(
            geopackage_path=geopackage_path,
            cache_dir=str(self.cache_dir / "unified_manager")
        )
        
        # Initialize address normalizer
        self.normalizer = AddressNormalizer()
        
        # Initialize fallback geocoder
        self.nominatim = Nominatim(user_agent="oikotie_unified_geocoding")
        
        # Helsinki bounding box for filtering
        self.helsinki_bbox = (24.7, 60.1, 25.3, 60.3)  # (min_lon, min_lat, max_lon, max_lat)
        
        self.logger.info("Unified geocoding service initialized successfully")
    
    def geocode_address(
        self,
        address: str,
        use_cache: bool = True,
        quality_threshold: float = 0.7
    ) -> Optional[GeocodeResult]:
        """
        Geocode an address using unified data sources with intelligent fallback.
        
        Args:
            address: Address string to geocode
            use_cache: Whether to use cached results
            quality_threshold: Minimum quality score to accept result
            
        Returns:
            GeocodeResult with coordinates and quality metrics, or None if failed
        """
        if not address or not address.strip():
            return None
        
        original_address = address.strip()
        normalized_address = self.normalizer.normalize_address(original_address)
        
        # Check cache first
        if use_cache:
            cached_result = self._get_cached_result(normalized_address)
            if cached_result:
                self.logger.debug(f"Cache hit for: {original_address}")
                return cached_result
        
        # Strategy 1: WMS National Addresses (Primary)
        result = self._geocode_with_wms_addresses(original_address, normalized_address)
        if result and result.quality_score >= quality_threshold:
            if use_cache:
                self._cache_result(normalized_address, result)
            return result
        
        # Strategy 2: GeoPackage Local Addresses (Fallback)
        result = self._geocode_with_geopackage_addresses(original_address, normalized_address)
        if result and result.quality_score >= quality_threshold:
            if use_cache:
                self._cache_result(normalized_address, result)
            return result
        
        # Strategy 3: Database Exact Match (Existing data)
        result = self._geocode_from_database(original_address, normalized_address)
        if result and result.quality_score >= quality_threshold:
            if use_cache:
                self._cache_result(normalized_address, result)
            return result
        
        # Strategy 4: Nominatim Fallback (External API)
        result = self._geocode_with_nominatim(original_address, normalized_address)
        if result and result.quality_score >= quality_threshold:
            if use_cache:
                self._cache_result(normalized_address, result)
            return result
        
        self.logger.warning(f"Failed to geocode address: {original_address}")
        return None
    
    def _geocode_with_wms_addresses(self, original: str, normalized: str) -> Optional[GeocodeResult]:
        """Geocode using WMS national address data with targeted approach."""
        try:
            # Extract components for targeted query
            components = self.normalizer.extract_components(normalized)
            
            # Create address-specific cache key for targeted caching
            address_cache_params = {
                "address_query": normalized,
                "street_name": components.get('street_name', ''),
                "postal_code": components.get('postal_code', '')
            }
            
            # Fetch addresses from WMS within Helsinki bbox with address-specific caching
            addresses_gdf = self.manager.fetch_addresses(
                bbox=self.helsinki_bbox,
                limit=5000,  # Reduced limit for better performance
                use_cache=True,
                **address_cache_params  # Pass address-specific parameters for unique cache key
            )
            
            if addresses_gdf.empty:
                self.logger.debug("No WMS addresses available")
                return None
            
            # Find best match
            best_match = self._find_best_address_match(normalized, addresses_gdf, 'wms_national')
            return best_match
            
        except Exception as e:
            self.logger.error(f"WMS geocoding error for {original}: {e}")
            return None
    
    def _geocode_with_geopackage_addresses(self, original: str, normalized: str) -> Optional[GeocodeResult]:
        """Geocode using GeoPackage local address data."""
        try:
            # Fetch addresses from GeoPackage
            addresses_gdf = self.manager.fetch_topographic_layer(
                "osoitepiste",  # Address points layer
                bbox=self.helsinki_bbox,
                use_cache=True
            )
            
            if addresses_gdf.empty:
                self.logger.debug("No GeoPackage addresses available")
                return None
            
            # Find best match
            best_match = self._find_best_address_match(normalized, addresses_gdf, 'geopackage_local')
            return best_match
            
        except Exception as e:
            self.logger.error(f"GeoPackage geocoding error for {original}: {e}")
            return None
    
    def _geocode_from_database(self, original: str, normalized: str) -> Optional[GeocodeResult]:
        """Geocode using existing database records with enhanced multi-line address handling."""
        try:
            with duckdb.connect(self.db_path) as conn:
                # Try exact match first with normalized address
                result = conn.execute("""
                    SELECT address, lat, lon
                    FROM address_locations
                    WHERE LOWER(TRIM(REPLACE(REPLACE(address, '\n', ' '), ',', ' '))) = ?
                    AND lat IS NOT NULL
                    AND lon IS NOT NULL
                    LIMIT 1
                """, [normalized]).fetchone()
                
                if result:
                    address, lat, lon = result
                    return GeocodeResult(
                        latitude=lat,
                        longitude=lon,
                        confidence=0.95,  # High confidence for exact match
                        source='database_exact',
                        method='exact_match',
                        original_address=original,
                        normalized_address=normalized,
                        quality_score=0.95
                    )
                
                # Try component-based matching for better results
                results = conn.execute("""
                    SELECT address, lat, lon
                    FROM address_locations
                    WHERE lat IS NOT NULL
                    AND lon IS NOT NULL
                    AND TRIM(address) != ''
                    LIMIT 100
                """).fetchall()
                
                if results:
                    # Score each result using enhanced similarity
                    best_score = 0
                    best_result = None
                    
                    for address, lat, lon in results:
                        # Preprocess database address to handle multi-line format
                        db_address_processed = self._preprocess_address_for_matching(address)
                        score = self._calculate_text_similarity(normalized, db_address_processed)
                        
                        if score > best_score and score > 0.6:  # Lower threshold for database matches
                            best_score = score
                            best_result = (address, lat, lon)
                    
                    if best_result and best_score > 0.6:
                        return GeocodeResult(
                            latitude=best_result[1],
                            longitude=best_result[2],
                            confidence=best_score * 0.85,  # Slightly reduced for database fuzzy match
                            source='database_fuzzy',
                            method='enhanced_fuzzy_match',
                            original_address=original,
                            normalized_address=normalized,
                            quality_score=best_score * 0.85
                        )
            
        except Exception as e:
            self.logger.error(f"Database geocoding error for {original}: {e}")
        
        return None
    
    def _geocode_with_nominatim(self, original: str, normalized: str) -> Optional[GeocodeResult]:
        """Geocode using Nominatim as final fallback."""
        try:
            # Try with city context
            query_with_city = f"{original}, Helsinki, Finland"
            location = self.nominatim.geocode(query_with_city, timeout=10)
            
            if location:
                # Verify the result is in Helsinki area
                if self._is_in_helsinki_area(location.latitude, location.longitude):
                    return GeocodeResult(
                        latitude=location.latitude,
                        longitude=location.longitude,
                        confidence=0.6,  # Lower confidence for external API
                        source='nominatim',
                        method='external_api',
                        original_address=original,
                        normalized_address=normalized,
                        quality_score=0.6
                    )
            
        except Exception as e:
            self.logger.error(f"Nominatim geocoding error for {original}: {e}")
        
        return None
    
    def _find_best_address_match(
        self,
        normalized_query: str,
        addresses_gdf: gpd.GeoDataFrame,
        source_name: str
    ) -> Optional[GeocodeResult]:
        """Find the best matching address in a GeoDataFrame."""
        if addresses_gdf.empty:
            return None
        
        best_score = 0
        best_match = None
        
        # Extract coordinates from geometry if needed
        if 'latitude' not in addresses_gdf.columns and 'geometry' in addresses_gdf.columns:
            addresses_gdf['latitude'] = addresses_gdf.geometry.y
            addresses_gdf['longitude'] = addresses_gdf.geometry.x
        
        # Determine address field based on source type
        address_field = None
        
        if source_name == 'wms_national':
            # Build full address from WMS components - enhanced field detection
            self.logger.debug(f"WMS columns available: {list(addresses_gdf.columns)}")
            
            if 'street_name' in addresses_gdf.columns:
                # Build clean, normalized address from components
                addresses_gdf['full_address'] = (
                    addresses_gdf['street_name'].fillna('').astype(str) + ' ' +
                    addresses_gdf['address_number'].fillna('').astype(str) + ' ' +
                    addresses_gdf['postal_code'].fillna('').astype(str) + ' ' +
                    addresses_gdf['admin_unit_4'].fillna('').astype(str)
                ).str.strip()
                address_field = 'full_address'
                self.logger.debug(f"Built WMS addresses, sample: {addresses_gdf['full_address'].iloc[0] if not addresses_gdf.empty else 'No data'}")
            else:
                self.logger.warning(f"WMS data missing street_name field. Available: {list(addresses_gdf.columns)}")
                # Try alternative field names that might exist
                alternative_fields = ['name', 'address', 'full_address', 'text', 'label']
                for field in alternative_fields:
                    if field in addresses_gdf.columns:
                        address_field = field
                        self.logger.info(f"Using alternative address field: {field}")
                        break
                
                if not address_field:
                    return None
        else:
            # Look for address field variations in other sources
            for field in ['address', 'full_address', 'street_address', 'name', 'osoite']:
                if field in addresses_gdf.columns:
                    address_field = field
                    break
        
        if not address_field:
            self.logger.warning(f"No address field found in {source_name} data. Available columns: {list(addresses_gdf.columns)}")
            return None
        
        # Score each address
        for idx, row in addresses_gdf.iterrows():
            if pd.isna(row[address_field]) or pd.isna(row['latitude']) or pd.isna(row['longitude']):
                continue
            
            candidate_address = str(row[address_field]).lower().strip()
            normalized_candidate = self.normalizer.normalize_address(candidate_address)
            
            # Calculate similarity score
            score = self._calculate_text_similarity(normalized_query, normalized_candidate)
            
            if score > best_score and score > 0.6:  # Minimum threshold
                best_score = score
                best_match = row
        
        if best_match is not None:
            return GeocodeResult(
                latitude=float(best_match['latitude']),
                longitude=float(best_match['longitude']),
                confidence=best_score,
                source=source_name,
                method='address_matching',
                original_address=normalized_query,  # Using normalized as original wasn't passed
                normalized_address=normalized_query,
                quality_score=best_score
            )
        
        return None
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Enhanced similarity calculation with better component-wise matching and postal code weighting.
        Optimized for Finnish address formats with multi-line support.
        """
        if not text1 or not text2:
            return 0.0
        
        # Preprocess both texts - handle multi-line addresses
        clean_text1 = self._preprocess_address_for_matching(text1)
        clean_text2 = self._preprocess_address_for_matching(text2)
        
        # Extract components for component-wise matching
        components1 = self.normalizer.extract_components(clean_text1)
        components2 = self.normalizer.extract_components(clean_text2)
        
        # Debug logging for component analysis
        self.logger.debug(f"Text1 components: {components1}")
        self.logger.debug(f"Text2 components: {components2}")
        
        # 1. Postal code matching (critical for Helsinki addresses)
        postal_score = self._calculate_postal_code_similarity(components1, components2)
        
        # 2. Street name similarity (most important for address matching)
        street_score = self._calculate_enhanced_street_similarity(
            components1['street_name'], 
            components2['street_name']
        )
        
        # 3. Street number similarity (important for exact address matching)
        number_score = self._calculate_number_similarity(
            components1['street_number'], 
            components2['street_number']
        )
        
        # 4. Overall text similarity using multiple algorithms
        levenshtein_score = self._calculate_levenshtein_similarity(clean_text1, clean_text2)
        jaccard_score = self._calculate_jaccard_similarity(clean_text1, clean_text2)
        
        # 5. Bonus for exact component matches
        exact_match_bonus = 0.0
        if components1['street_name'] and components2['street_name']:
            if components1['street_name'] == components2['street_name']:
                exact_match_bonus += 0.2
        if components1['postal_code'] and components2['postal_code']:
            if components1['postal_code'] == components2['postal_code']:
                exact_match_bonus += 0.15
        
        # Enhanced weighted combination with postal code priority
        if postal_score >= 0.9:  # Exact postal code match - high confidence
            final_score = (
                postal_score * 0.35 +      # Postal code: 35% weight
                street_score * 0.40 +      # Street name: 40% weight  
                number_score * 0.15 +      # Street number: 15% weight
                levenshtein_score * 0.05 + # Levenshtein: 5% weight
                jaccard_score * 0.05 +     # Jaccard: 5% weight
                exact_match_bonus          # Bonus for exact matches
            )
        elif postal_score >= 0.7:  # Good postal code match - medium confidence  
            final_score = (
                postal_score * 0.25 +      # Postal code: 25% weight
                street_score * 0.45 +      # Street name: 45% weight
                number_score * 0.20 +      # Street number: 20% weight
                levenshtein_score * 0.05 + # Levenshtein: 5% weight
                jaccard_score * 0.05 +     # Jaccard: 5% weight
                exact_match_bonus * 0.8    # Reduced bonus
            )
        else:  # Poor/no postal code match - lower overall confidence
            final_score = (
                postal_score * 0.15 +      # Postal code: 15% weight
                street_score * 0.50 +      # Street name: 50% weight
                number_score * 0.25 +      # Street number: 25% weight
                levenshtein_score * 0.05 + # Levenshtein: 5% weight
                jaccard_score * 0.05 +     # Jaccard: 5% weight
                exact_match_bonus * 0.6    # Further reduced bonus
            )
        
        # Apply penalty for very different lengths (indicates mismatch)
        length_ratio = min(len(clean_text1), len(clean_text2)) / max(len(clean_text1), len(clean_text2))
        if length_ratio < 0.5:  # Very different lengths
            final_score *= 0.8
        
        result = min(1.0, max(0.0, final_score))
        
        # Enhanced logging for debugging
        self.logger.debug(f"Similarity calculation: '{clean_text1}' vs '{clean_text2}'")
        self.logger.debug(f"  Postal: {postal_score:.3f}, Street: {street_score:.3f}, Number: {number_score:.3f}")
        self.logger.debug(f"  Levenshtein: {levenshtein_score:.3f}, Jaccard: {jaccard_score:.3f}")
        self.logger.debug(f"  Final score: {result:.3f}")
        
        return result
    
    def _preprocess_address_for_matching(self, address: str) -> str:
        """Preprocess address to handle multi-line formats and normalize for matching."""
        if not address:
            return ""
        
        # Handle multi-line addresses (convert newlines and commas to spaces)
        processed = re.sub(r'\n|,', ' ', address.strip())
        
        # Remove extra whitespace
        processed = re.sub(r'\s+', ' ', processed)
        
        # Convert to lowercase
        processed = processed.lower()
        
        # Remove punctuation except spaces and alphanumeric
        processed = re.sub(r'[^\w\s\-äöå]', '', processed)
        
        return processed.strip()
    
    def _calculate_levenshtein_similarity(self, text1: str, text2: str) -> float:
        """Calculate Levenshtein distance-based similarity."""
        if not text1 or not text2:
            return 0.0
        
        # Simple Levenshtein distance implementation
        if text1 == text2:
            return 1.0
        
        len1, len2 = len(text1), len(text2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Create distance matrix
        distances = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        # Initialize first row and column
        for i in range(len1 + 1):
            distances[i][0] = i
        for j in range(len2 + 1):
            distances[0][j] = j
        
        # Calculate distances
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if text1[i-1] == text2[j-1] else 1
                distances[i][j] = min(
                    distances[i-1][j] + 1,      # deletion
                    distances[i][j-1] + 1,      # insertion
                    distances[i-1][j-1] + cost  # substitution
                )
        
        # Convert distance to similarity (0-1 scale)
        max_len = max(len1, len2)
        distance = distances[len1][len2]
        similarity = 1.0 - (distance / max_len)
        
        return max(0.0, similarity)
    
    def _calculate_jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity for token overlap."""
        if not text1 or not text2:
            return 0.0
        
        tokens1 = set(text1.split())
        tokens2 = set(text2.split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_postal_code_similarity(self, components1: dict, components2: dict) -> float:
        """Calculate postal code similarity with high weighting for exact matches."""
        postal1 = components1.get('postal_code', '').strip()
        postal2 = components2.get('postal_code', '').strip()
        
        if not postal1 or not postal2:
            return 0.3  # No postal code available
        
        if postal1 == postal2:
            return 1.0  # Exact match
        
        # Partial postal code match (first 3 digits for Helsinki area)
        if len(postal1) >= 3 and len(postal2) >= 3:
            if postal1[:3] == postal2[:3]:
                return 0.7  # Same postal area
        
        return 0.1  # Different postal codes
    
    def _calculate_enhanced_street_similarity(self, street1: str, street2: str) -> float:
        """Calculate enhanced street name similarity with Finnish-specific optimizations."""
        if not street1 or not street2:
            return 0.1
        
        # Normalize both street names
        norm1 = self.normalizer.normalize_address(street1)
        norm2 = self.normalizer.normalize_address(street2)
        
        if norm1 == norm2:
            return 1.0  # Exact match
        
        # Check for common Finnish street name variations
        # Handle abbreviated street types (e.g., "katu" vs "k")
        if self._are_street_variants(norm1, norm2):
            return 0.95
        
        # Levenshtein similarity for close matches
        levenshtein_sim = self._calculate_levenshtein_similarity(norm1, norm2)
        
        # Bonus for partial matches (e.g., "mannerheimintie" in both)
        if len(norm1) >= 4 and len(norm2) >= 4:
            if norm1[:4] == norm2[:4]:  # Same first 4 characters
                levenshtein_sim = min(1.0, levenshtein_sim + 0.1)
        
        return levenshtein_sim
    
    def _are_street_variants(self, street1: str, street2: str) -> bool:
        """Check if two street names are variants of each other (e.g., abbreviations)."""
        # Remove street type suffixes for comparison
        base1 = self._extract_street_base_name(street1)
        base2 = self._extract_street_base_name(street2)
        
        return base1 == base2 and len(base1) > 3
    
    def _extract_street_base_name(self, street_name: str) -> str:
        """Extract the base name of a street, removing common suffixes."""
        if not street_name:
            return ""
        
        # Common Finnish street type suffixes
        suffixes = ['katu', 'tie', 'kuja', 'polku', 'väylä', 'kari', 'rinne', 'bulevardi', 'k', 't', 'kj', 'p']
        
        name = street_name.strip().lower()
        for suffix in suffixes:
            if name.endswith(' ' + suffix) or name.endswith(suffix):
                name = name.replace(suffix, '').strip()
                break
        
        return name
    
    def _calculate_number_similarity(self, number1: str, number2: str) -> float:
        """Calculate street number similarity."""
        if not number1 or not number2:
            return 0.5  # No number available
        
        # Extract numeric part
        num1 = re.search(r'\d+', number1)
        num2 = re.search(r'\d+', number2)
        
        if num1 and num2:
            if num1.group() == num2.group():
                return 1.0  # Exact number match
            
            # Check if numbers are close (within 2)
            try:
                n1, n2 = int(num1.group()), int(num2.group())
                if abs(n1 - n2) <= 2:
                    return 0.8  # Close numbers
            except ValueError:
                pass
        
        return 0.2  # Different or invalid numbers
    
    def _is_in_helsinki_area(self, lat: float, lon: float) -> bool:
        """Check if coordinates are within Helsinki area."""
        min_lon, min_lat, max_lon, max_lat = self.helsinki_bbox
        return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
    
    def _get_cached_result(self, normalized_address: str) -> Optional[GeocodeResult]:
        """Get geocoding result from cache with enhanced key generation."""
        # Create more specific cache key that preserves address uniqueness
        cache_key = self._generate_specific_cache_key(normalized_address)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            if cache_file.exists():
                import json
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.logger.debug(f"Cache hit for key: {cache_key[:8]}... (address: {normalized_address})")
                    return GeocodeResult(**data)
        except Exception as e:
            self.logger.debug(f"Cache read error: {e}")
        
        return None
    
    def _cache_result(self, normalized_address: str, result: GeocodeResult):
        """Cache geocoding result with enhanced key generation."""
        # Create more specific cache key that preserves address uniqueness
        cache_key = self._generate_specific_cache_key(normalized_address)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            import json
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result._asdict(), f, ensure_ascii=False, indent=2)
                self.logger.debug(f"Cached result for key: {cache_key[:8]}... (address: {normalized_address})")
        except Exception as e:
            self.logger.debug(f"Cache write error: {e}")
    
    def _generate_specific_cache_key(self, address: str) -> str:
        """
        Generate cache key that preserves address uniqueness.
        
        Args:
            address: Address string to generate key for
            
        Returns:
            Unique cache key that distinguishes between different addresses
        """
        # Extract components to ensure uniqueness
        components = self.normalizer.extract_components(address)
        
        # Create composite key that includes all distinguishing components
        key_components = [
            components.get('street_name', '').strip(),
            components.get('street_number', '').strip(),  # CRITICAL: Include street number
            components.get('postal_code', '').strip(),    # CRITICAL: Include postal code
            components.get('city', '').strip()
        ]
        
        # Join non-empty components with separator
        unique_key = '|'.join(component for component in key_components if component)
        
        # Add fallback to original address if components are insufficient
        if not unique_key.strip():
            unique_key = address.strip()
        
        # Generate hash of the unique key
        cache_key = hashlib.md5(unique_key.encode('utf-8')).hexdigest()
        
        self.logger.debug(f"Generated cache key: {cache_key[:8]}... for components: {key_components}")
        
        return cache_key
    
    def batch_geocode_addresses(
        self,
        addresses: List[str],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Optional[GeocodeResult]]:
        """
        Geocode multiple addresses efficiently.
        
        Args:
            addresses: List of address strings to geocode
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dictionary mapping addresses to GeocodeResult objects
        """
        results = {}
        total = len(addresses)
        
        self.logger.info(f"Starting batch geocoding of {total} addresses")
        
        for i, address in enumerate(addresses):
            if progress_callback:
                progress_callback(i, total, address)
            
            result = self.geocode_address(address)
            results[address] = result
            
            if i % 50 == 0:  # Log progress every 50 addresses
                success_count = sum(1 for r in results.values() if r is not None)
                success_rate = (success_count / (i + 1)) * 100
                self.logger.info(f"Progress: {i+1}/{total} ({success_rate:.1f}% success rate)")
        
        success_count = sum(1 for r in results.values() if r is not None)
        final_success_rate = (success_count / total) * 100
        
        self.logger.info(f"Batch geocoding complete: {success_count}/{total} "
                        f"addresses geocoded ({final_success_rate:.1f}% success rate)")
        
        return results
    
    def validate_geocoding_quality(
        self,
        sample_size: int = 100,
        quality_threshold: float = 0.8
    ) -> Dict[str, Any]:
        """
        Validate geocoding quality using existing database records.
        
        Args:
            sample_size: Number of addresses to validate
            quality_threshold: Minimum quality score threshold
            
        Returns:
            Dictionary with validation results and statistics
        """
        self.logger.info(f"Starting geocoding quality validation (sample size: {sample_size})")
        
        # Get sample addresses from database
        with duckdb.connect(self.db_path) as conn:
            sample_addresses = conn.execute(f"""
                SELECT address, lat, lon
                FROM address_locations
                WHERE lat IS NOT NULL
                ORDER BY RANDOM()
                LIMIT {sample_size}
            """).fetchall()
        
        if not sample_addresses:
            return {"error": "No addresses found in database for validation"}
        
        validation_results = {
            "total_tested": len(sample_addresses),
            "high_quality": 0,
            "medium_quality": 0,
            "low_quality": 0,
            "failed": 0,
            "quality_scores": [],
            "source_distribution": {},
            "method_distribution": {},
            "average_quality": 0.0,
            "details": []
        }
        
        for address, original_lat, original_lon in sample_addresses:
            try:
                result = self.geocode_address(address)
                
                if result:
                    # Calculate distance difference (rough quality check)
                    lat_diff = abs(result.latitude - original_lat)
                    lon_diff = abs(result.longitude - original_lon)
                    distance_error = (lat_diff + lon_diff) * 111000  # Rough meters
                    
                    # Adjust quality score based on distance error
                    distance_penalty = min(0.5, distance_error / 1000)  # Max 0.5 penalty for 1km+ error
                    adjusted_quality = max(0.0, result.quality_score - distance_penalty)
                    
                    validation_results["quality_scores"].append(adjusted_quality)
                    
                    # Categorize quality
                    if adjusted_quality >= quality_threshold:
                        validation_results["high_quality"] += 1
                    elif adjusted_quality >= 0.6:
                        validation_results["medium_quality"] += 1
                    else:
                        validation_results["low_quality"] += 1
                    
                    # Track source and method distribution
                    source = result.source
                    method = result.method
                    validation_results["source_distribution"][source] = \
                        validation_results["source_distribution"].get(source, 0) + 1
                    validation_results["method_distribution"][method] = \
                        validation_results["method_distribution"].get(method, 0) + 1
                    
                    validation_results["details"].append({
                        "address": address,
                        "original_coords": (original_lat, original_lon),
                        "new_coords": (result.latitude, result.longitude),
                        "quality_score": adjusted_quality,
                        "distance_error_m": distance_error,
                        "source": source,
                        "method": method
                    })
                    
                else:
                    validation_results["failed"] += 1
                    validation_results["details"].append({
                        "address": address,
                        "original_coords": (original_lat, original_lon),
                        "new_coords": None,
                        "quality_score": 0.0,
                        "distance_error_m": float('inf'),
                        "source": "failed",
                        "method": "failed"
                    })
                
            except Exception as e:
                self.logger.error(f"Validation error for {address}: {e}")
                validation_results["failed"] += 1
        
        # Calculate summary statistics
        if validation_results["quality_scores"]:
            validation_results["average_quality"] = \
                sum(validation_results["quality_scores"]) / len(validation_results["quality_scores"])
        
        success_rate = ((validation_results["high_quality"] + 
                        validation_results["medium_quality"] + 
                        validation_results["low_quality"]) / 
                       validation_results["total_tested"]) * 100
        
        validation_results["success_rate"] = success_rate
        validation_results["high_quality_rate"] = \
            (validation_results["high_quality"] / validation_results["total_tested"]) * 100
        
        self.logger.info(f"Validation complete: {success_rate:.1f}% success rate, "
                        f"{validation_results['high_quality_rate']:.1f}% high quality")
        
        return validation_results
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance report for the geocoding service."""
        try:
            source_status = self.manager.get_source_status()
            available_layers = self.manager.get_available_layers()
            
            return {
                "service_status": "operational",
                "data_sources": source_status,
                "available_layers": available_layers,
                "cache_directory": str(self.cache_dir),
                "helsinki_bbox": self.helsinki_bbox,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating performance report: {e}")
            return {
                "service_status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Convenience function for creating the service
def create_enhanced_geocoding_service(
    geopackage_path: str = "data/helsinki_topographic_data.gpkg",
    db_path: str = "data/real_estate.duckdb"
) -> UnifiedGeocodingService:
    """
    Create enhanced geocoding service with default configuration.
    
    Args:
        geopackage_path: Path to Helsinki GeoPackage
        db_path: Path to DuckDB database
        
    Returns:
        Configured UnifiedGeocodingService instance
    """
    return UnifiedGeocodingService(
        geopackage_path=geopackage_path,
        db_path=db_path,
        enable_logging=True
    )


if __name__ == "__main__":
    # Example usage and testing
    service = create_enhanced_geocoding_service()
    
    # Test single address
    test_address = "Mannerheimintie 1, Helsinki"
    result = service.geocode_address(test_address)
    
    if result:
        print(f"✅ Successfully geocoded: {test_address}")
        print(f"   Coordinates: ({result.latitude:.6f}, {result.longitude:.6f})")
        print(f"   Quality Score: {result.quality_score:.3f}")
        print(f"   Source: {result.source}")
        print(f"   Method: {result.method}")
    else:
        print(f"❌ Failed to geocode: {test_address}")
    
    # Run quality validation
    print("\n🔍 Running quality validation...")
    validation_results = service.validate_geocoding_quality(sample_size=20)
    
    print(f"📊 Validation Results:")
    print(f"   Success Rate: {validation_results.get('success_rate', 0):.1f}%")
    print(f"   High Quality: {validation_results.get('high_quality_rate', 0):.1f}%")
    print(f"   Average Quality: {validation_results.get('average_quality', 0):.3f}")
