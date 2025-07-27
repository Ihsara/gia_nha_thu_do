#!/usr/bin/env python3
"""
Multi-City Enhanced Dashboard Generator
Supports Espoo-specific dashboard generation with building footprints and comparative visualizations
Part of the Oikotie visualization package
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
import branca.colormap as cm
from jinja2 import Template
from typing import Dict, List, Optional, Tuple, Any

from ..utils.config import get_city_config, CityConfig, OutputConfig


class MultiCityDashboard:
    """Enhanced multi-city dashboard generator with Espoo support and comparative visualizations"""
    
    def __init__(self, db_path="data/real_estate.duckdb", output_dir=None):
        self.db_path = db_path
        self.output_dir = Path(output_dir) if output_dir else Path("output/visualization/dashboard")
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Dashboard configuration
        self.default_config = {
            'gradient_colors': ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D'],
            'building_opacity': 0.7,
            'listing_opacity': 0.9
        }
        
    def load_city_data(self, city: str, sample_size: Optional[int] = None) -> pd.DataFrame:
        """Load listings data for a specific city"""
        print(f"📊 Loading data for {city}")
        
        try:
            conn = duckdb.connect(self.db_path)
            
            # Debug: Check if city exists in database
            city_check = conn.execute("SELECT COUNT(*) FROM listings WHERE city = ?", [city]).fetchone()[0]
            print(f"   Debug: Found {city_check} total listings for {city}")
            
            # Base query for city listings with coordinates
            query = """
            SELECT 
                url as id, 
                address, 
                latitude, 
                longitude,
                price_eur as price, 
                rooms, 
                size_m2, 
                listing_type, 
                city,
                scraped_at,
                data_quality_score,
                coordinate_source,
                geospatial_quality_score
            FROM listings 
            WHERE city = ? 
                AND latitude IS NOT NULL 
                AND longitude IS NOT NULL
                AND price_eur IS NOT NULL
                AND size_m2 IS NOT NULL
                AND rooms IS NOT NULL
            ORDER BY price_eur
            """
            
            if sample_size:
                query += f" LIMIT {sample_size}"
            
            listings_df = conn.execute(query, [city]).df()
            conn.close()
            
            print(f"✅ Loaded {len(listings_df):,} {city} listings")
            return listings_df
            
        except Exception as e:
            print(f"❌ Error loading {city} data: {e}")
            return pd.DataFrame()
    
    def load_building_footprints(self, city: str, bbox: Optional[Tuple[float, float, float, float]] = None) -> gpd.GeoDataFrame:
        """Load building footprints for a specific city"""
        print(f"🏗️ Loading building footprints for {city}")
        
        # City-specific building footprint files
        building_files = {
            'helsinki': 'data/helsinki_buildings_20250711_041142.geojson',
            'espoo': 'data/espoo_buildings_20250719_183000.geojson'  # Espoo-specific building footprints
        }
        
        building_file = building_files.get(city.lower())
        if not building_file or not Path(building_file).exists():
            print(f"⚠️ No building footprints available for {city}")
            return gpd.GeoDataFrame()
        
        try:
            buildings_gdf = gpd.read_file(building_file)
            
            # Filter by bounding box if provided
            if bbox:
                min_lon, min_lat, max_lon, max_lat = bbox
                buildings_gdf = buildings_gdf.cx[min_lon:max_lon, min_lat:max_lat]
            
            print(f"✅ Loaded {len(buildings_gdf):,} building footprints for {city}")
            return buildings_gdf
            
        except Exception as e:
            print(f"❌ Error loading building footprints for {city}: {e}")
            return gpd.GeoDataFrame()
    
    def perform_spatial_matching(self, listings_df: pd.DataFrame, buildings_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        """Perform spatial matching between listings and building footprints"""
        if buildings_gdf.empty:
            # Return listings with no match information if no buildings available
            results = listings_df.copy()
            results['match_type'] = 'no_buildings'
            results['building_id'] = None
            results['building_name'] = None
            results['building_type'] = None
            results['distance_m'] = float('inf')
            results['matched'] = False
            return results
        
        print(f"🔍 Performing spatial matching for {len(listings_df):,} listings...")
        
        results = []
        
        for idx, listing in listings_df.iterrows():
            if idx % 100 == 0 and idx > 0:
                print(f"   Progress: {idx:,}/{len(listings_df):,}")
            
            point = Point(listing['longitude'], listing['latitude'])
            
            # Direct containment check
            containing_buildings = buildings_gdf[buildings_gdf.contains(point)]
            
            if not containing_buildings.empty:
                building = containing_buildings.iloc[0]
                result = listing.to_dict()
                result.update({
                    'match_type': 'direct',
                    'building_id': building.get('osm_id', 'N/A'),
                    'building_name': building.get('name', ''),
                    'building_type': building.get('fclass', ''),
                    'distance_m': 0.0,
                    'matched': True
                })
                results.append(result)
            else:
                # Buffer search
                buffer_distance = 0.001  # ~100m
                buffered_point = point.buffer(buffer_distance)
                intersecting_buildings = buildings_gdf[buildings_gdf.intersects(buffered_point)]
                
                if not intersecting_buildings.empty:
                    # Find closest building
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        distances = intersecting_buildings.geometry.distance(point)
                    
                    closest_idx = distances.idxmin()
                    closest_building = intersecting_buildings.loc[closest_idx]
                    closest_distance = distances.loc[closest_idx] * 111000
                    
                    result = listing.to_dict()
                    result.update({
                        'match_type': 'buffer',
                        'building_id': closest_building.get('osm_id', 'N/A'),
                        'building_name': closest_building.get('name', ''),
                        'building_type': closest_building.get('fclass', ''),
                        'distance_m': closest_distance,
                        'matched': True
                    })
                    results.append(result)
                else:
                    result = listing.to_dict()
                    result.update({
                        'match_type': 'none',
                        'building_id': None,
                        'building_name': None,
                        'building_type': None,
                        'distance_m': float('inf'),
                        'matched': False
                    })
                    results.append(result)
        
        results_df = pd.DataFrame(results)
        matched_count = len(results_df[results_df['matched']])
        print(f"✅ Spatial matching complete: {matched_count:,}/{len(results_df):,} matched")
        
        return results_df
    
    def create_city_dashboard(self, city: str, enhanced_mode: bool = True, sample_size: int = 2000) -> str:
        """Generate city-specific interactive dashboard"""
        print(f"\n🎨 Creating Enhanced Dashboard for {city}")
        print("=" * 60)
        
        # Normalize city name (capitalize first letter)
        city_normalized = city.capitalize()
        
        # Get city configuration
        try:
            city_config = get_city_config(city.lower())  # Config uses lowercase
        except ValueError as e:
            print(f"❌ {e}")
            return ""
        
        # Load city data
        listings_df = self.load_city_data(city_normalized, sample_size)
        if listings_df.empty:
            print(f"❌ No data available for {city}")
            return ""
        
        # Load building footprints
        buildings_gdf = self.load_building_footprints(city_normalized, city_config.bbox)
        
        # Perform spatial matching
        results_df = self.perform_spatial_matching(listings_df, buildings_gdf)
        
        # Create map
        map_html = self._create_city_map(city_normalized, city_config, results_df, buildings_gdf)
        
        # Generate dashboard HTML
        dashboard_html = self._create_city_dashboard_html(city_normalized, city_config, results_df, map_html)
        
        # Save dashboard
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dashboard_path = self.output_dir / f"{city_normalized.lower()}_enhanced_dashboard_{timestamp}.html"
        
        with open(dashboard_path, 'w', encoding='utf-8') as f:
            f.write(dashboard_html)
        
        print(f"✅ {city_normalized} dashboard created: {dashboard_path}")
        return str(dashboard_path)
    
    def create_comparative_dashboard(self, cities: List[str], sample_size: int = 1000, options: List[str] = None) -> str:
        """Generate multi-city comparative dashboard"""
        print(f"\n🎨 Creating Comparative Dashboard for {', '.join(cities)}")
        print("=" * 60)
        
        # Default options if none provided
        if options is None:
            options = ['price_comparison', 'size_comparison', 'price_per_sqm', 'building_footprints']
        
        print(f"🔧 Using options: {', '.join(options)}")
        
        city_data = {}
        all_results = []
        
        # Load data for all cities
        for city in cities:
            try:
                city_normalized = city.capitalize()
                city_config = get_city_config(city.lower())
                listings_df = self.load_city_data(city_normalized, sample_size)
                
                if not listings_df.empty:
                    # Only load building footprints if needed
                    buildings_gdf = gpd.GeoDataFrame()
                    if 'building_footprints' in options:
                        buildings_gdf = self.load_building_footprints(city_normalized, city_config.bbox)
                    
                    results_df = self.perform_spatial_matching(listings_df, buildings_gdf)
                    
                    city_data[city_normalized] = {
                        'config': city_config,
                        'results': results_df,
                        'buildings': buildings_gdf,
                        'options': options
                    }
                    all_results.append(results_df)
                    
            except Exception as e:
                print(f"⚠️ Skipping {city_normalized}: {e}")
        
        if not city_data:
            print("❌ No valid city data available for comparison")
            return ""
        
        # Create comparative map
        map_html = self._create_comparative_map(city_data, options)
        
        # Generate comparative dashboard HTML
        dashboard_html = self._create_comparative_dashboard_html(city_data, map_html, options)
        
        # Save dashboard
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cities_str = "_".join([c.lower() for c in cities])
        dashboard_path = self.output_dir / f"comparative_{cities_str}_dashboard_{timestamp}.html"
        
        with open(dashboard_path, 'w', encoding='utf-8') as f:
            f.write(dashboard_html)
        
        print(f"✅ Comparative dashboard created: {dashboard_path}")
        return str(dashboard_path)
    
    def _create_city_map(self, city: str, city_config: CityConfig, results_df: pd.DataFrame, buildings_gdf: gpd.GeoDataFrame) -> str:
        """Create interactive map for a single city"""
        # Create base map
        m = folium.Map(
            location=[city_config.center_lat, city_config.center_lon],
            zoom_start=city_config.zoom_level,
            tiles='OpenStreetMap',
            prefer_canvas=True
        )
        
        # Add city boundary if available
        if city_config.bbox:
            min_lon, min_lat, max_lon, max_lat = city_config.bbox
            boundary = [
                [min_lat, min_lon],
                [max_lat, min_lon],
                [max_lat, max_lon],
                [min_lat, max_lon],
                [min_lat, min_lon]
            ]
            
            folium.PolyLine(
                boundary,
                color='red',
                weight=2,
                opacity=0.8,
                popup=f"{city} boundary"
            ).add_to(m)
        
        # Add building footprints with price-based coloring
        if not buildings_gdf.empty:
            self._add_building_footprints(m, results_df, buildings_gdf)
        
        # Add listings by match type
        self._add_listings_to_map(m, results_df)
        
        return m._repr_html_()
    
    def _create_comparative_map(self, city_data: Dict[str, Dict], options: List[str] = None) -> str:
        """Create comparative map showing multiple cities"""
        # Default options if none provided
        if options is None:
            options = ['price_comparison', 'size_comparison', 'price_per_sqm', 'building_footprints']
            
        # Calculate center point from all cities
        all_lats = [data['config'].center_lat for data in city_data.values()]
        all_lons = [data['config'].center_lon for data in city_data.values()]
        
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
        
        # Create base map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=10,
            tiles='CartoDB positron',  # Use a cleaner base map
            prefer_canvas=True
        )
        
        # City colors for differentiation
        city_colors = {
            'Helsinki': '#0000FF',  # Blue
            'Espoo': '#0047AB',     # Espoo blue
            'Tampere': '#008000',   # Green
            'Turku': '#800080',     # Purple
            'Vantaa': '#FFA500'     # Orange
        }
        
        # Add city boundaries and data
        for city, data in city_data.items():
            # Get color for this city (fallback to blue if not in predefined colors)
            color = city_colors.get(city, '#0000FF')
            
            # Create feature group for this city
            city_group = folium.FeatureGroup(name=f"{city} Data", show=True)
            
            # Add city boundary
            if data['config'].bbox:
                min_lon, min_lat, max_lon, max_lat = data['config'].bbox
                boundary = [
                    [min_lat, min_lon],
                    [max_lat, min_lon],
                    [max_lat, max_lon],
                    [min_lat, max_lon],
                    [min_lat, min_lon]
                ]
                
                folium.PolyLine(
                    boundary,
                    color=color,
                    weight=3,
                    opacity=0.8,
                    popup=f"{city} boundary"
                ).add_to(city_group)
            
            # Add city center marker with appropriate color
            # Map hex colors to folium color names
            color_map = {
                '#0000FF': 'blue',
                '#0047AB': 'blue',
                '#008000': 'green',
                '#800080': 'purple',
                '#FFA500': 'orange'
            }
            
            folium_color = color_map.get(color, 'blue')
            
            folium.Marker(
                location=[data['config'].center_lat, data['config'].center_lon],
                popup=f"{city} Center",
                icon=folium.Icon(color=folium_color, icon='star')
            ).add_to(city_group)
            
            # Add sample listings
            sample_listings = data['results'].sample(min(100, len(data['results'])), random_state=42)
            for _, listing in sample_listings.iterrows():
                # Create detailed popup content
                popup_content = f"""
                <div style="font-family: Arial, sans-serif; min-width: 200px;">
                    <h4 style="margin: 0 0 10px 0; color: {color};">{city} Property</h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 3px 0;"><b>Address:</b></td><td>{listing.get('address', 'N/A')}</td></tr>
                        <tr><td style="padding: 3px 0;"><b>Price:</b></td><td>€{listing['price']:,}</td></tr>
                        <tr><td style="padding: 3px 0;"><b>Size:</b></td><td>{listing['size_m2']} m²</td></tr>
                        <tr><td style="padding: 3px 0;"><b>€/m²:</b></td><td>€{listing['price']/listing['size_m2']:,.0f}</td></tr>
                        <tr><td style="padding: 3px 0;"><b>Rooms:</b></td><td>{listing['rooms']}</td></tr>
                    </table>
                </div>
                """
                
                folium.CircleMarker(
                    location=[listing['latitude'], listing['longitude']],
                    radius=5,
                    popup=folium.Popup(popup_content, max_width=300),
                    tooltip=f"{city}: €{listing['price']:,}",
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.6
                ).add_to(city_group)
            
            # Add building footprints if option is enabled
            if 'building_footprints' in options and not data['buildings'].empty:
                # Create building footprints group
                buildings_group = folium.FeatureGroup(name=f"{city} Buildings", show=False)
                
                # Limit buildings for performance
                max_buildings = 1000
                buildings_gdf = data['buildings']
                if len(buildings_gdf) > max_buildings:
                    buildings_gdf = buildings_gdf.sample(max_buildings, random_state=42)
                    print(f"   Limited to {max_buildings} buildings for {city}")
                
                # Add buildings
                for _, building in buildings_gdf.iterrows():
                    # Find listings in this building
                    building_listings = data['results'][data['results']['building_id'] == building.get('osm_id', '')]
                    
                    if not building_listings.empty:
                        # Color based on average price
                        avg_price = building_listings['price'].mean()
                        opacity = 0.7
                        popup_text = f"{city} Building<br>Listings: {len(building_listings)}<br>Avg Price: €{avg_price:,.0f}"
                    else:
                        opacity = 0.3
                        popup_text = f"{city} Building<br>No listings"
                    
                    # Add building polygon with city-specific color
                    folium.GeoJson(
                        building.geometry,
                        style_function=lambda x, color=color, opacity=opacity: {
                            'fillColor': color,
                            'color': '#333333',
                            'weight': 1,
                            'fillOpacity': opacity,
                            'opacity': 0.7
                        },
                        popup=popup_text,
                        tooltip=f"{city} Building"
                    ).add_to(buildings_group)
                
                buildings_group.add_to(m)
            
            # Add city group to map
            city_group.add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add fullscreen control
        plugins.Fullscreen(
            position='topleft',
            title='Expand map',
            title_cancel='Exit fullscreen',
            force_separate_button=True
        ).add_to(m)
        
        # Add measure control
        plugins.MeasureControl(
            position='bottomleft',
            primary_length_unit='meters',
            secondary_length_unit='kilometers',
            primary_area_unit='sqmeters',
            secondary_area_unit='hectares'
        ).add_to(m)
        
        return m._repr_html_()
    
    def _add_building_footprints(self, map_obj: folium.Map, results_df: pd.DataFrame, buildings_gdf: gpd.GeoDataFrame):
        """Add building footprints with price-based coloring"""
        print("🏗️ Adding building footprints with gradient highlighting...")
        
        # Limit buildings for performance
        max_buildings = 3000
        if len(buildings_gdf) > max_buildings:
            buildings_gdf = buildings_gdf.sample(max_buildings, random_state=42)
            print(f"   Limited to {max_buildings} buildings for performance")
        
        for idx, building in buildings_gdf.iterrows():
            # Find listings in this building
            building_listings = results_df[results_df['building_id'] == building.get('osm_id', '')]
            
            if not building_listings.empty:
                # Color based on average price
                avg_price = building_listings['price'].mean()
                if avg_price < 200000:
                    color = '#2E86AB'  # Blue for lower prices
                elif avg_price < 400000:
                    color = '#A23B72'  # Purple for medium prices
                elif avg_price < 600000:
                    color = '#F18F01'  # Orange for higher prices
                else:
                    color = '#C73E1D'  # Red for highest prices
                    
                opacity = self.default_config['building_opacity']
                popup_text = f"Building ID: {building.get('osm_id', 'N/A')}<br>"
                popup_text += f"Listings: {len(building_listings)}<br>"
                popup_text += f"Avg Price: €{avg_price:,.0f}"
            else:
                # Default color for buildings without listings
                color = '#E0E0E0'
                opacity = 0.3
                popup_text = f"Building ID: {building.get('osm_id', 'N/A')}<br>No listings"
            
            # Add building polygon
            folium.GeoJson(
                building.geometry,
                style_function=lambda x, color=color, opacity=opacity: {
                    'fillColor': color,
                    'color': '#333333',
                    'weight': 1,
                    'fillOpacity': opacity,
                    'opacity': 0.7
                },
                popup=folium.Popup(popup_text, max_width=200),
                tooltip=f"Building {building.get('osm_id', 'N/A')}"
            ).add_to(map_obj)
    
    def _add_listings_to_map(self, map_obj: folium.Map, results_df: pd.DataFrame):
        """Add listings to map with match type indicators"""
        print("📍 Adding listings with match type indicators...")
        
        # Group listings by match type
        match_types = {
            'direct': {'color': 'green', 'icon': 'home', 'label': 'Direct Match'},
            'buffer': {'color': 'orange', 'icon': 'search', 'label': 'Buffer Match'},
            'none': {'color': 'red', 'icon': 'exclamation', 'label': 'No Match'},
            'no_buildings': {'color': 'gray', 'icon': 'question', 'label': 'No Buildings Available'}
        }
        
        for match_type, config in match_types.items():
            type_listings = results_df[results_df['match_type'] == match_type]
            
            for _, listing in type_listings.iterrows():
                popup_content = self._create_listing_popup(listing, match_type)
                
                tooltip_text = f"€{listing['price']:,}"
                if match_type == 'buffer':
                    tooltip_text += f" - {config['label']} ({listing['distance_m']:.0f}m)"
                else:
                    tooltip_text += f" - {config['label']}"
                
                folium.Marker(
                    location=[listing['latitude'], listing['longitude']],
                    popup=folium.Popup(popup_content, max_width=350),
                    icon=folium.Icon(
                        color=config['color'],
                        icon=config['icon'],
                        prefix='fa'
                    ),
                    tooltip=tooltip_text
                ).add_to(map_obj)
    
    def _create_listing_popup(self, listing: pd.Series, match_type: str) -> str:
        """Create detailed popup content for listings"""
        # Match type specific content
        match_configs = {
            'direct': {
                'info': "✅ <b>DIRECT BUILDING MATCH</b><br>Listing is inside building footprint",
                'color': "#28a745"
            },
            'buffer': {
                'info': f"🎯 <b>BUFFER MATCH</b> ({listing.get('distance_m', 0):.1f}m)<br>Closest building within 100m radius",
                'color': "#fd7e14"
            },
            'none': {
                'info': "❌ <b>NO BUILDING FOUND</b><br>No buildings within 100m radius",
                'color': "#dc3545"
            },
            'no_buildings': {
                'info': "❓ <b>NO BUILDING DATA</b><br>Building footprints not available for this area",
                'color': "#6c757d"
            }
        }
        
        match_config = match_configs.get(match_type, match_configs['none'])
        
        popup_content = f"""
        <div style="font-family: Arial, sans-serif; min-width: 300px;">
            <div style="background-color: {match_config['color']}; color: white; padding: 8px; margin: -9px -9px 10px -9px; border-radius: 3px;">
                {match_config['info']}
            </div>
            
            <h4 style="margin: 0 0 10px 0; color: #333;">{listing['address']}</h4>
            
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 3px 0;"><b>💰 Price:</b></td><td>€{listing['price']:,}</td></tr>
                <tr><td style="padding: 3px 0;"><b>🏠 Rooms:</b></td><td>{listing['rooms']}</td></tr>
                <tr><td style="padding: 3px 0;"><b>📐 Size:</b></td><td>{listing['size_m2']} m²</td></tr>
                <tr><td style="padding: 3px 0;"><b>🏷️ Type:</b></td><td>{listing['listing_type']}</td></tr>
                <tr><td style="padding: 3px 0;"><b>€/m²:</b></td><td>€{listing['price']/listing['size_m2']:,.0f}</td></tr>
                <tr><td style="padding: 3px 0;"><b>🏙️ City:</b></td><td>{listing['city']}</td></tr>
            </table>
            
            <hr style="margin: 10px 0;">
            
            <h5 style="margin: 5px 0; color: #666;">Building Information</h5>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 2px 0;"><b>Building ID:</b></td><td>{listing.get('building_id', 'N/A')}</td></tr>
                <tr><td style="padding: 2px 0;"><b>Building Name:</b></td><td>{listing.get('building_name', 'N/A') or 'Unnamed'}</td></tr>
                <tr><td style="padding: 2px 0;"><b>Building Type:</b></td><td>{listing.get('building_type', 'N/A')}</td></tr>
                <tr><td style="padding: 2px 0;"><b>Distance:</b></td><td>{listing.get('distance_m', 0):.1f}m</td></tr>
            </table>
            
            <hr style="margin: 10px 0;">
            
            <h5 style="margin: 5px 0; color: #666;">Data Quality</h5>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 2px 0;"><b>Data Quality:</b></td><td>{listing.get('data_quality_score', 'N/A')}</td></tr>
                <tr><td style="padding: 2px 0;"><b>Coordinate Source:</b></td><td>{listing.get('coordinate_source', 'N/A')}</td></tr>
                <tr><td style="padding: 2px 0;"><b>Geospatial Quality:</b></td><td>{listing.get('geospatial_quality_score', 'N/A')}</td></tr>
            </table>
        </div>
        """
        
        return popup_content
    
    def _create_city_dashboard_html(self, city: str, city_config: CityConfig, results_df: pd.DataFrame, map_html: str) -> str:
        """Create HTML dashboard for a single city"""
        # Calculate statistics
        total_listings = len(results_df)
        matched_listings = len(results_df[results_df['matched']])
        match_rate = (matched_listings / total_listings) * 100 if total_listings > 0 else 0
        
        direct_matches = len(results_df[results_df['match_type'] == 'direct'])
        buffer_matches = len(results_df[results_df['match_type'] == 'buffer'])
        no_matches = len(results_df[results_df['match_type'] == 'none'])
        no_buildings = len(results_df[results_df['match_type'] == 'no_buildings'])
        
        # Price statistics
        price_stats = results_df['price'].describe()
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{city} Enhanced Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f5f5f5;
                }}
                
                .dashboard-container {{
                    display: flex;
                    height: 100vh;
                    overflow: hidden;
                }}
                
                .statistics-panel {{
                    width: 30%;
                    background-color: white;
                    border-right: 3px solid #ddd;
                    overflow-y: auto;
                    padding: 20px;
                    box-shadow: 2px 0 10px rgba(0,0,0,0.1);
                }}
                
                .map-panel {{
                    width: 70%;
                    position: relative;
                }}
                
                .panel-header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 15px;
                    margin: -20px -20px 20px -20px;
                    border-radius: 0;
                }}
                
                .panel-header h2 {{
                    margin: 0;
                    font-size: 18px;
                }}
                
                .metrics-section {{
                    background-color: #fff;
                    border: 1px solid #e9ecef;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 20px;
                }}
                
                .metric-item {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 8px 0;
                    border-bottom: 1px solid #f8f9fa;
                }}
                
                .metric-item:last-child {{
                    border-bottom: none;
                }}
                
                .metric-label {{
                    font-weight: 500;
                    color: #495057;
                }}
                
                .metric-value {{
                    font-weight: 600;
                    color: #212529;
                }}
                
                .section-title {{
                    font-weight: 600;
                    color: #495057;
                    margin-bottom: 10px;
                    padding-bottom: 5px;
                    border-bottom: 2px solid #e9ecef;
                }}
                
                .map-container {{
                    height: 100vh;
                    width: 100%;
                }}
                
                .status-indicator {{
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    margin-right: 8px;
                }}
                
                .status-direct {{ background-color: #28a745; }}
                .status-buffer {{ background-color: #ffc107; }}
                .status-none {{ background-color: #dc3545; }}
                .status-no-buildings {{ background-color: #6c757d; }}
            </style>
        </head>
        <body>
            <div class="dashboard-container">
                <!-- Statistics Panel -->
                <div class="statistics-panel">
                    <div class="panel-header">
                        <h2><i class="fas fa-chart-line"></i> {city} Enhanced Dashboard</h2>
                    </div>
                    
                    <!-- City Information -->
                    <div class="metrics-section">
                        <div class="section-title">City Information</div>
                        <div class="metric-item">
                            <span class="metric-label">City:</span>
                            <span class="metric-value">{city}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Center:</span>
                            <span class="metric-value">{city_config.center_lat:.4f}, {city_config.center_lon:.4f}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Zoom Level:</span>
                            <span class="metric-value">{city_config.zoom_level}</span>
                        </div>
                    </div>
                    
                    <!-- Listing Statistics -->
                    <div class="metrics-section">
                        <div class="section-title">Listing Statistics</div>
                        <div class="metric-item">
                            <span class="metric-label">Total Listings:</span>
                            <span class="metric-value">{total_listings:,}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Matched Listings:</span>
                            <span class="metric-value">{matched_listings:,}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Match Rate:</span>
                            <span class="metric-value">{match_rate:.2f}%</span>
                        </div>
                    </div>
                    
                    <!-- Match Type Breakdown -->
                    <div class="metrics-section">
                        <div class="section-title">Match Type Breakdown</div>
                        <div class="metric-item">
                            <span class="metric-label"><span class="status-indicator status-direct"></span>Direct Matches:</span>
                            <span class="metric-value">{direct_matches:,}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label"><span class="status-indicator status-buffer"></span>Buffer Matches:</span>
                            <span class="metric-value">{buffer_matches:,}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label"><span class="status-indicator status-none"></span>No Matches:</span>
                            <span class="metric-value">{no_matches:,}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label"><span class="status-indicator status-no-buildings"></span>No Buildings:</span>
                            <span class="metric-value">{no_buildings:,}</span>
                        </div>
                    </div>
                    
                    <!-- Price Statistics -->
                    <div class="metrics-section">
                        <div class="section-title">Price Statistics</div>
                        <div class="metric-item">
                            <span class="metric-label">Average Price:</span>
                            <span class="metric-value">€{price_stats['mean']:,.0f}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Median Price:</span>
                            <span class="metric-value">€{price_stats['50%']:,.0f}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Min Price:</span>
                            <span class="metric-value">€{price_stats['min']:,.0f}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Max Price:</span>
                            <span class="metric-value">€{price_stats['max']:,.0f}</span>
                        </div>
                    </div>
                    
                    <!-- Generation Info -->
                    <div class="metrics-section">
                        <div class="section-title">Generation Info</div>
                        <div class="metric-item">
                            <span class="metric-label">Generated:</span>
                            <span class="metric-value">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Dashboard Type:</span>
                            <span class="metric-value">Enhanced Multi-City</span>
                        </div>
                    </div>
                </div>
                
                <!-- Map Panel -->
                <div class="map-panel">
                    <div class="map-container">
                        {map_html}
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template
    
    def _create_comparative_dashboard_html(self, city_data: Dict[str, Dict], map_html: str, options: List[str] = None) -> str:
        """Create HTML dashboard for city comparison"""
        # Calculate comparative statistics
        comparison_stats = {}
        for city, data in city_data.items():
            results_df = data['results']
            comparison_stats[city] = {
                'total_listings': len(results_df),
                'matched_listings': len(results_df[results_df['matched']]),
                'match_rate': (len(results_df[results_df['matched']]) / len(results_df)) * 100 if len(results_df) > 0 else 0,
                'avg_price': results_df['price'].mean(),
                'median_price': results_df['price'].median(),
                'avg_size': results_df['size_m2'].mean()
            }
        
        # Generate comparison table HTML
        comparison_table = ""
        for city, stats in comparison_stats.items():
            comparison_table += f"""
            <tr>
                <td style="font-weight: 600;">{city}</td>
                <td>{stats['total_listings']:,}</td>
                <td>{stats['matched_listings']:,}</td>
                <td>{stats['match_rate']:.1f}%</td>
                <td>€{stats['avg_price']:,.0f}</td>
                <td>€{stats['median_price']:,.0f}</td>
                <td>{stats['avg_size']:.0f}m²</td>
            </tr>
            """
        
        cities_list = ', '.join(city_data.keys())
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Multi-City Comparative Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f5f5f5;
                }}
                
                .dashboard-container {{
                    display: flex;
                    height: 100vh;
                    overflow: hidden;
                }}
                
                .statistics-panel {{
                    width: 35%;
                    background-color: white;
                    border-right: 3px solid #ddd;
                    overflow-y: auto;
                    padding: 20px;
                    box-shadow: 2px 0 10px rgba(0,0,0,0.1);
                }}
                
                .map-panel {{
                    width: 65%;
                    position: relative;
                }}
                
                .panel-header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 15px;
                    margin: -20px -20px 20px -20px;
                    border-radius: 0;
                }}
                
                .panel-header h2 {{
                    margin: 0;
                    font-size: 18px;
                }}
                
                .comparison-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }}
                
                .comparison-table th,
                .comparison-table td {{
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                    font-size: 12px;
                }}
                
                .comparison-table th {{
                    background-color: #f8f9fa;
                    font-weight: 600;
                }}
                
                .section-title {{
                    font-weight: 600;
                    color: #495057;
                    margin-bottom: 10px;
                    padding-bottom: 5px;
                    border-bottom: 2px solid #e9ecef;
                }}
                
                .map-container {{
                    height: 100vh;
                    width: 100%;
                }}
                
                .metrics-section {{
                    background-color: #fff;
                    border: 1px solid #e9ecef;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="dashboard-container">
                <!-- Statistics Panel -->
                <div class="statistics-panel">
                    <div class="panel-header">
                        <h2><i class="fas fa-chart-bar"></i> Multi-City Comparative Dashboard</h2>
                    </div>
                    
                    <!-- Cities Overview -->
                    <div class="metrics-section">
                        <div class="section-title">Cities Compared</div>
                        <p><strong>Cities:</strong> {cities_list}</p>
                        <p><strong>Total Cities:</strong> {len(city_data)}</p>
                        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                    
                    <!-- Comparison Table -->
                    <div class="metrics-section">
                        <div class="section-title">Comparative Statistics</div>
                        <table class="comparison-table">
                            <thead>
                                <tr>
                                    <th>City</th>
                                    <th>Listings</th>
                                    <th>Matched</th>
                                    <th>Match Rate</th>
                                    <th>Avg Price</th>
                                    <th>Median Price</th>
                                    <th>Avg Size</th>
                                </tr>
                            </thead>
                            <tbody>
                                {comparison_table}
                            </tbody>
                        </table>
                    </div>
                    
                    <!-- Legend -->
                    <div class="metrics-section">
                        <div class="section-title">Map Legend</div>
                        <p><strong>Boundaries:</strong> Colored lines show city boundaries</p>
                        <p><strong>Centers:</strong> Star markers show city centers</p>
                        <p><strong>Listings:</strong> Small circles show sample property listings</p>
                        <p><strong>Colors:</strong> Each city has a unique color for identification</p>
                    </div>
                </div>
                
                <!-- Map Panel -->
                <div class="map-panel">
                    <div class="map-container">
                        {map_html}
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template


def main():
    """Demo usage of MultiCityDashboard"""
    print("🎨 Multi-City Dashboard Generator Demo")
    print("=" * 50)
    
    dashboard = MultiCityDashboard()
    
    # Create Espoo dashboard
    print("\n1. Creating Espoo Dashboard...")
    espoo_dashboard = dashboard.create_city_dashboard('espoo', sample_size=50)
    if espoo_dashboard:
        print(f"✅ Espoo dashboard: {espoo_dashboard}")
    
    # Create Helsinki dashboard for comparison
    print("\n2. Creating Helsinki Dashboard...")
    helsinki_dashboard = dashboard.create_city_dashboard('helsinki', sample_size=50)
    if helsinki_dashboard:
        print(f"✅ Helsinki dashboard: {helsinki_dashboard}")
    
    # Create comparative dashboard
    print("\n3. Creating Comparative Dashboard...")
    comparative_dashboard = dashboard.create_comparative_dashboard(['helsinki', 'espoo'], sample_size=50)
    if comparative_dashboard:
        print(f"✅ Comparative dashboard: {comparative_dashboard}")


if __name__ == "__main__":
    main()