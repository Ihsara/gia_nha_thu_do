"""
Multi-city geospatial integration manager for Oikotie Real Estate Analytics Platform.

This module provides a unified interface for geospatial data integration across
different cities, handling city-specific implementations transparently.
"""

from typing import Dict, List, Optional, Any, Union
import pandas as pd
import geopandas as gpd
from loguru import logger

from oikotie.geospatial.base import GeospatialIntegrator
from oikotie.geospatial.espoo import EspooGeospatialIntegrator


class MultiCityGeospatialManager:
    """
    Unified geospatial data management for all cities.
    
    Provides a single interface for geospatial operations across different cities,
    delegating to city-specific implementations as needed.
    """
    
    def __init__(self):
        """Initialize with city-specific integrators"""
        self.integrators = {}
        self._initialize_integrators()
    
    def _initialize_integrators(self):
        """Initialize city-specific integrators"""
        # Add Espoo integrator
        self.integrators['Espoo'] = EspooGeospatialIntegrator()
        
        # Add other city integrators as they become available
        # self.integrators['Helsinki'] = HelsinkiGeospatialIntegrator()
        
        logger.info(f"Initialized geospatial integrators for {len(self.integrators)} cities")
    
    def get_integrator(self, city: str) -> Optional[GeospatialIntegrator]:
        """Get the appropriate integrator for a specific city"""
        if city in self.integrators:
            return self.integrators[city]
        
        logger.warning(f"No geospatial integrator available for {city}")
        return None
    
    def process_city_listings(self, city: str, listings_df: pd.DataFrame) -> pd.DataFrame:
        """
        Process listings with city-appropriate geospatial enrichment.
        
        Args:
            city: City name
            listings_df: DataFrame with listings data
            
        Returns:
            DataFrame with added geospatial information
        """
        integrator = self.get_integrator(city)
        
        if integrator is None:
            logger.warning(f"Cannot process listings for {city}: no integrator available")
            return listings_df
        
        logger.info(f"Processing {len(listings_df)} {city} listings with geospatial enrichment")
        
        # Step 1: Geocode addresses if needed
        if 'latitude' not in listings_df.columns or 'longitude' not in listings_df.columns:
            if 'address' in listings_df.columns:
                addresses = listings_df['address'].dropna().unique().tolist()
                
                if addresses:
                    logger.info(f"Geocoding {len(addresses)} addresses")
                    geocoded = integrator.geocode_addresses(addresses)
                    
                    # Create mapping from address to coordinates
                    coord_map = {addr: (lat, lon) for addr, lat, lon, _ in geocoded if lat is not None and lon is not None}
                    
                    # Add coordinates to listings
                    for idx, row in listings_df.iterrows():
                        if row['address'] in coord_map:
                            lat, lon = coord_map[row['address']]
                            listings_df.loc[idx, 'latitude'] = lat
                            listings_df.loc[idx, 'longitude'] = lon
        
        # Step 2: Match to buildings
        listings_with_buildings = integrator.match_listings_to_buildings(listings_df)
        
        # Step 3: Validate spatial data
        result_df = integrator.validate_spatial_data(listings_with_buildings)
        
        # Calculate success metrics
        geocoded_count = result_df['latitude'].notna().sum()
        building_match_count = result_df['building_match'].sum() if 'building_match' in result_df.columns else 0
        
        geocoded_rate = (geocoded_count / len(result_df)) * 100 if len(result_df) > 0 else 0
        building_match_rate = (building_match_count / len(result_df)) * 100 if len(result_df) > 0 else 0
        
        logger.success(f"Geospatial enrichment complete for {city}:")
        logger.success(f"  Geocoded: {geocoded_count}/{len(result_df)} ({geocoded_rate:.1f}%)")
        logger.success(f"  Building matches: {building_match_count}/{len(result_df)} ({building_match_rate:.1f}%)")
        
        return result_df
    
    def get_available_cities(self) -> List[str]:
        """Get list of cities with available geospatial integrators"""
        return list(self.integrators.keys())
    
    def validate_city_coordinates(self, city: str, lat: float, lon: float) -> bool:
        """Validate if coordinates are within city bounds"""
        integrator = self.get_integrator(city)
        
        if integrator is None:
            logger.warning(f"Cannot validate coordinates for {city}: no integrator available")
            return False
        
        return integrator.validate_coordinates(lat, lon)