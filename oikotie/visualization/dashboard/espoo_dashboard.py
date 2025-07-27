#!/usr/bin/env python3
"""
Espoo-specific Dashboard Generator
Provides enhanced visualization capabilities for Espoo properties
Part of the Oikotie visualization package
"""

import geopandas as gpd
import pandas as pd
import folium
from folium import plugins
import duckdb
from pathlib import Path
import random
from datetime import datetime
import json
import numpy as np
import branca.colormap as cm
from typing import Dict, List, Optional, Tuple, Any

from ..utils.config import get_city_config, CityConfig, OutputConfig
from .multi_city import MultiCityDashboard


class EspooDashboard(MultiCityDashboard):
    """Enhanced dashboard generator specifically for Espoo properties"""
    
    def __init__(self, db_path="data/real_estate.duckdb", output_dir=None):
        super().__init__(db_path, output_dir)
        
        # Espoo-specific configuration
        self.espoo_config = get_city_config('espoo')
        
        # Espoo-specific styling
        self.espoo_style = {
            'gradient_colors': ['#0047AB', '#4169E1', '#6495ED', '#87CEEB'],  # Blue shades for Espoo
            'building_opacity': 0.7,
            'listing_opacity': 0.9,
            'boundary_color': '#0047AB',  # Espoo blue
            'boundary_weight': 3,
            'boundary_opacity': 0.8,
            'water_color': '#B0E0E6',  # Light blue for water bodies
            'parks_color': '#90EE90',  # Light green for parks
            'district_colors': {
                'Tapiola': '#1E3F66',
                'Leppävaara': '#2E5984',
                'Espoonlahti': '#3E73A2',
                'Matinkylä': '#4E8DC0',
                'Espoon keskus': '#5EA7DE',
                'Kauklahti': '#6EC1FC',
                'Other': '#80DAFF'
            },
            'price_ranges': [
                {'min': 0, 'max': 200000, 'color': '#0047AB', 'label': '< €200k'},
                {'min': 200000, 'max': 400000, 'color': '#4169E1', 'label': '€200k - €400k'},
                {'min': 400000, 'max': 600000, 'color': '#6495ED', 'label': '€400k - €600k'},
                {'min': 600000, 'max': 800000, 'color': '#87CEEB', 'label': '€600k - €800k'},
                {'min': 800000, 'max': 1000000, 'color': '#B0E0E6', 'label': '€800k - €1M'},
                {'min': 1000000, 'max': float('inf'), 'color': '#E6F7FF', 'label': '> €1M'}
            ]
        }
    
    def create_espoo_dashboard(self, enhanced_mode: bool = True, sample_size: int = 2000) -> str:
        """Generate Espoo-specific interactive dashboard with enhanced features"""
        print(f"\n🎨 Creating Enhanced Espoo Dashboard")
        print("=" * 60)
        
        # Load Espoo data
        listings_df = self.load_city_data('Espoo', sample_size)
        if listings_df.empty:
            print(f"❌ No data available for Espoo")
            return ""
        
        # Load Espoo building footprints
        buildings_gdf = self.load_building_footprints('Espoo', self.espoo_config.bbox)
        
        # Perform spatial matching
        results_df = self.perform_spatial_matching(listings_df, buildings_gdf)
        
        # Create Espoo-specific map with enhanced styling
        map_html = self._create_espoo_map(results_df, buildings_gdf)
        
        # Generate dashboard HTML with Espoo-specific styling
        dashboard_html = self._create_espoo_dashboard_html(results_df, map_html)
        
        # Save dashboard
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dashboard_path = self.output_dir / f"espoo_enhanced_dashboard_{timestamp}.html"
        
        with open(dashboard_path, 'w', encoding='utf-8') as f:
            f.write(dashboard_html)
        
        print(f"✅ Espoo dashboard created: {dashboard_path}")
        return str(dashboard_path)
    
    def _create_espoo_map(self, results_df: pd.DataFrame, buildings_gdf: gpd.GeoDataFrame) -> str:
        """Create interactive map specifically styled for Espoo"""
        # Create base map with Espoo center
        m = folium.Map(
            location=[self.espoo_config.center_lat, self.espoo_config.center_lon],
            zoom_start=self.espoo_config.zoom_level,
            tiles='CartoDB positron',  # Use a cleaner base map
            prefer_canvas=True
        )
        
        # Add Espoo boundary with specific styling
        if self.espoo_config.bbox:
            min_lon, min_lat, max_lon, max_lat = self.espoo_config.bbox
            boundary = [
                [min_lat, min_lon],
                [max_lat, min_lon],
                [max_lat, max_lon],
                [min_lat, max_lon],
                [min_lat, min_lon]
            ]
            
            folium.PolyLine(
                boundary,
                color=self.espoo_style['boundary_color'],
                weight=self.espoo_style['boundary_weight'],
                opacity=self.espoo_style['boundary_opacity'],
                popup="Espoo city boundary"
            ).add_to(m)
        
        # Add Espoo districts
        self._add_espoo_districts(m)
        
        # Add building footprints with Espoo-specific coloring
        if not buildings_gdf.empty:
            self._add_espoo_building_footprints(m, results_df, buildings_gdf)
        
        # Add listings by match type with Espoo-specific styling
        self._add_espoo_listings_to_map(m, results_df)
        
        # Add price heatmap layer
        self._add_price_heatmap(m, results_df)
        
        # Add map controls
        folium.LayerControl().add_to(m)
        
        # Add fullscreen control
        plugins.Fullscreen(
            position='topleft',
            title='Expand map',
            title_cancel='Exit fullscreen',
            force_separate_button=True
        ).add_to(m)
        
        # Create a feature group for search
        search_group = folium.FeatureGroup(name="Search")
        
        # Add some searchable markers
        for _, listing in results_df.iterrows():
            folium.Marker(
                location=[listing['latitude'], listing['longitude']],
                popup=listing.get('address', 'N/A'),
                icon=folium.Icon(color='blue', icon='info-sign', prefix='fa'),
                tooltip=listing.get('address', 'N/A')
            ).add_to(search_group)
        
        search_group.add_to(m)
        
        # Add search control
        plugins.Search(
            layer=search_group,
            geom_type='Point',
            placeholder='Search for an address',
            collapsed=True,
            search_label='tooltip',
            search_zoom=16
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
        
    def _add_espoo_districts(self, map_obj: folium.Map):
        """Add Espoo district boundaries to the map"""
        print("🏙️ Adding Espoo districts...")
        
        # Define major Espoo districts with approximate centers
        districts = [
            {"name": "Tapiola", "center": [60.1752, 24.8054], "radius": 1500},
            {"name": "Leppävaara", "center": [60.2188, 24.8137], "radius": 1500},
            {"name": "Espoonlahti", "center": [60.1491, 24.6651], "radius": 1500},
            {"name": "Matinkylä", "center": [60.1591, 24.7384], "radius": 1500},
            {"name": "Espoon keskus", "center": [60.2052, 24.6522], "radius": 1500},
            {"name": "Kauklahti", "center": [60.1905, 24.5957], "radius": 1200}
        ]
        
        # Create feature group for districts
        district_group = folium.FeatureGroup(name="Espoo Districts", show=False)
        
        for district in districts:
            # Create circle to represent district area
            folium.Circle(
                location=district["center"],
                radius=district["radius"],
                color=self.espoo_style['district_colors'].get(district["name"], self.espoo_style['district_colors']["Other"]),
                fill=True,
                fill_opacity=0.2,
                weight=2,
                popup=folium.Popup(f"<b>{district['name']}</b><br>Major district in Espoo", max_width=200),
                tooltip=district["name"]
            ).add_to(district_group)
            
            # Add district label
            folium.Marker(
                location=district["center"],
                icon=folium.DivIcon(
                    icon_size=(150, 36),
                    icon_anchor=(75, 18),
                    html=f'<div style="font-size: 12pt; font-weight: bold; text-align: center; text-shadow: 1px 1px 1px white;">{district["name"]}</div>'
                )
            ).add_to(district_group)
        
        district_group.add_to(map_obj)
        
    def _add_price_heatmap(self, map_obj: folium.Map, results_df: pd.DataFrame):
        """Add price heatmap layer to the map"""
        print("🔥 Adding price heatmap layer...")
        
        if len(results_df) < 5:
            print("   Not enough data for heatmap, skipping")
            return
            
        # Create heatmap data
        heatmap_data = []
        for _, row in results_df.iterrows():
            # Weight by price (normalized)
            weight = min(1.0, row['price'] / 1000000)  # Cap at 1.0 for prices >= 1M
            heatmap_data.append([row['latitude'], row['longitude'], weight])
        
        # Create heatmap layer
        heatmap = plugins.HeatMap(
            heatmap_data,
            radius=15,
            blur=10,
            gradient={0.2: 'blue', 0.4: 'cyan', 0.6: 'lime', 0.8: 'yellow', 1.0: 'red'},
            name="Price Heatmap",
            show=False
        )
        
        heatmap.add_to(map_obj)
    
    def _add_espoo_building_footprints(self, map_obj: folium.Map, results_df: pd.DataFrame, buildings_gdf: gpd.GeoDataFrame):
        """Add building footprints with Espoo-specific styling"""
        print("🏗️ Adding Espoo building footprints with gradient highlighting...")
        
        # Limit buildings for performance
        max_buildings = 3000
        if len(buildings_gdf) > max_buildings:
            buildings_gdf = buildings_gdf.sample(max_buildings, random_state=42)
            print(f"   Limited to {max_buildings} buildings for performance")
        
        # Create feature groups for buildings by price range
        building_groups = {}
        for price_range in self.espoo_style['price_ranges']:
            group_name = f"Buildings: {price_range['label']}"
            building_groups[price_range['label']] = folium.FeatureGroup(
                name=group_name, 
                show=(price_range['min'] == 0)  # Only show the lowest price range by default
            )
        
        # Add buildings with no listings
        no_listings_group = folium.FeatureGroup(name="Buildings: No Listings", show=False)
        
        # Process buildings
        for idx, building in buildings_gdf.iterrows():
            # Find listings in this building
            building_listings = results_df[results_df['building_id'] == building.get('osm_id', '')]
            
            if not building_listings.empty:
                # Color based on average price using Espoo-specific price ranges
                avg_price = building_listings['price'].mean()
                
                # Find the appropriate price range
                for price_range in self.espoo_style['price_ranges']:
                    if price_range['min'] <= avg_price < price_range['max']:
                        color = price_range['color']
                        group = building_groups[price_range['label']]
                        break
                else:
                    # Fallback
                    color = self.espoo_style['gradient_colors'][0]
                    group = building_groups[self.espoo_style['price_ranges'][0]['label']]
                
                opacity = self.espoo_style['building_opacity']
                
                # Create detailed popup content
                popup_text = f"""
                <div style="font-family: Arial, sans-serif; min-width: 200px;">
                    <h4 style="margin: 0 0 10px 0; color: #0047AB;">Building Information</h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 3px 0;"><b>Building ID:</b></td><td>{building.get('osm_id', 'N/A')}</td></tr>
                        <tr><td style="padding: 3px 0;"><b>Listings:</b></td><td>{len(building_listings)}</td></tr>
                        <tr><td style="padding: 3px 0;"><b>Avg Price:</b></td><td>€{avg_price:,.0f}</td></tr>
                        <tr><td style="padding: 3px 0;"><b>Price Range:</b></td><td>{next((r['label'] for r in self.espoo_style['price_ranges'] if r['min'] <= avg_price < r['max']), 'Unknown')}</td></tr>
                        <tr><td style="padding: 3px 0;"><b>Building Type:</b></td><td>{building.get('fclass', 'N/A')}</td></tr>
                    </table>
                </div>
                """
            else:
                # Default color for buildings without listings
                color = '#E0E0E0'
                opacity = 0.2
                group = no_listings_group
                popup_text = f"""
                <div style="font-family: Arial, sans-serif; min-width: 200px;">
                    <h4 style="margin: 0 0 10px 0; color: #666;">Building Information</h4>
                    <p>No listings available for this building</p>
                    <p><b>Building ID:</b> {building.get('osm_id', 'N/A')}</p>
                    <p><b>Building Type:</b> {building.get('fclass', 'N/A')}</p>
                </div>
                """
            
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
                popup=folium.Popup(popup_text, max_width=250),
                tooltip=f"Building {building.get('osm_id', 'N/A')}"
            ).add_to(group)
        
        # Add all building groups to map
        for group in building_groups.values():
            group.add_to(map_obj)
        
        no_listings_group.add_to(map_obj)
        
        # Add legend for building colors
        self._add_building_color_legend(map_obj)
    
    def _add_espoo_listings_to_map(self, map_obj: folium.Map, results_df: pd.DataFrame):
        """Add listings to map with Espoo-specific styling"""
        print("📍 Adding Espoo listings with match type indicators...")
        
        # Group listings by match type
        match_types = {
            'direct': {'color': 'green', 'icon': 'home', 'label': 'Direct Match', 'group': 'Direct Matches'},
            'buffer': {'color': 'orange', 'icon': 'search', 'label': 'Buffer Match', 'group': 'Buffer Matches'},
            'none': {'color': 'red', 'icon': 'exclamation', 'label': 'No Match', 'group': 'Unmatched'},
            'no_buildings': {'color': 'gray', 'icon': 'question', 'label': 'No Buildings Available', 'group': 'No Building Data'}
        }
        
        # Create feature groups for each match type
        feature_groups = {}
        for match_type, config in match_types.items():
            feature_groups[match_type] = folium.FeatureGroup(name=config['group'], show=(match_type == 'direct'))
        
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
                ).add_to(feature_groups[match_type])
        
        # Add all feature groups to map
        for group in feature_groups.values():
            group.add_to(map_obj)
            
    def _add_building_color_legend(self, map_obj: folium.Map):
        """Add color legend for building price ranges"""
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; 
                    border: 2px solid grey; z-index: 9999; 
                    background-color: white;
                    padding: 10px;
                    border-radius: 5px;
                    font-family: Arial, sans-serif;">
            <div style="font-size: 14px; font-weight: bold; margin-bottom: 5px;">
                Building Price Ranges
            </div>
        '''
        
        for price_range in self.espoo_style['price_ranges']:
            legend_html += f'''
            <div style="display: flex; align-items: center; margin-bottom: 3px;">
                <div style="background-color: {price_range['color']}; 
                            width: 15px; height: 15px; 
                            margin-right: 5px; 
                            border: 1px solid #333;"></div>
                <div style="font-size: 12px;">{price_range['label']}</div>
            </div>
            '''
        
        legend_html += '''
            <div style="display: flex; align-items: center; margin-bottom: 3px;">
                <div style="background-color: #E0E0E0; 
                            width: 15px; height: 15px; 
                            margin-right: 5px; 
                            border: 1px solid #333;"></div>
                <div style="font-size: 12px;">No Listings</div>
            </div>
        </div>
        '''
        
        map_obj.get_root().html.add_child(folium.Element(legend_html))
    
    def _create_espoo_dashboard_html(self, results_df: pd.DataFrame, map_html: str) -> str:
        """Create HTML dashboard with Espoo-specific styling"""
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
            <title>Espoo Enhanced Dashboard</title>
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
                    background: linear-gradient(135deg, #0047AB 0%, #4169E1 100%);
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
                
                .espoo-footer {{
                    background-color: #0047AB;
                    color: white;
                    text-align: center;
                    padding: 10px;
                    font-size: 12px;
                    position: absolute;
                    bottom: 0;
                    width: 100%;
                }}
                
                .price-chart {{
                    height: 200px;
                    margin-bottom: 20px;
                }}
            </style>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body>
            <div class="dashboard-container">
                <!-- Statistics Panel -->
                <div class="statistics-panel">
                    <div class="panel-header">
                        <h2><i class="fas fa-chart-line"></i> Espoo Enhanced Dashboard</h2>
                    </div>
                    
                    <!-- City Information -->
                    <div class="metrics-section">
                        <div class="section-title">City Information</div>
                        <div class="metric-item">
                            <span class="metric-label">City:</span>
                            <span class="metric-value">Espoo</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Center:</span>
                            <span class="metric-value">{self.espoo_config.center_lat:.4f}, {self.espoo_config.center_lon:.4f}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Bounds:</span>
                            <span class="metric-value">{self.espoo_config.bbox[0]:.2f}, {self.espoo_config.bbox[1]:.2f}, {self.espoo_config.bbox[2]:.2f}, {self.espoo_config.bbox[3]:.2f}</span>
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
                            <span class="metric-value">{matched_listings:,} ({match_rate:.1f}%)</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label"><span class="status-indicator status-direct"></span>Direct Matches:</span>
                            <span class="metric-value">{direct_matches:,} ({direct_matches/total_listings*100 if total_listings else 0:.1f}%)</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label"><span class="status-indicator status-buffer"></span>Buffer Matches:</span>
                            <span class="metric-value">{buffer_matches:,} ({buffer_matches/total_listings*100 if total_listings else 0:.1f}%)</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label"><span class="status-indicator status-none"></span>No Matches:</span>
                            <span class="metric-value">{no_matches:,} ({no_matches/total_listings*100 if total_listings else 0:.1f}%)</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label"><span class="status-indicator status-no-buildings"></span>No Building Data:</span>
                            <span class="metric-value">{no_buildings:,} ({no_buildings/total_listings*100 if total_listings else 0:.1f}%)</span>
                        </div>
                    </div>
                    
                    <!-- Price Statistics -->
                    <div class="metrics-section">
                        <div class="section-title">Price Statistics (€)</div>
                        <div class="price-chart">
                            <canvas id="priceChart"></canvas>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Minimum:</span>
                            <span class="metric-value">€{price_stats['min']:,.0f}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Maximum:</span>
                            <span class="metric-value">€{price_stats['max']:,.0f}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Average:</span>
                            <span class="metric-value">€{price_stats['mean']:,.0f}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Median:</span>
                            <span class="metric-value">€{price_stats['50%']:,.0f}</span>
                        </div>
                    </div>
                    
                    <!-- Size Statistics -->
                    <div class="metrics-section">
                        <div class="section-title">Size Statistics (m²)</div>
                        <div class="metric-item">
                            <span class="metric-label">Minimum:</span>
                            <span class="metric-value">{results_df['size_m2'].min():.1f} m²</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Maximum:</span>
                            <span class="metric-value">{results_df['size_m2'].max():.1f} m²</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Average:</span>
                            <span class="metric-value">{results_df['size_m2'].mean():.1f} m²</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Median:</span>
                            <span class="metric-value">{results_df['size_m2'].median():.1f} m²</span>
                        </div>
                    </div>
                    
                    <!-- Price per Square Meter -->
                    <div class="metrics-section">
                        <div class="section-title">Price per m² (€/m²)</div>
                        <div class="metric-item">
                            <span class="metric-label">Minimum:</span>
                            <span class="metric-value">€{(results_df['price'] / results_df['size_m2']).min():,.0f}/m²</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Maximum:</span>
                            <span class="metric-value">€{(results_df['price'] / results_df['size_m2']).max():,.0f}/m²</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Average:</span>
                            <span class="metric-value">€{(results_df['price'] / results_df['size_m2']).mean():,.0f}/m²</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Median:</span>
                            <span class="metric-value">€{(results_df['price'] / results_df['size_m2']).median():,.0f}/m²</span>
                        </div>
                    </div>
                    
                    <!-- Dashboard Info -->
                    <div class="metrics-section">
                        <div class="section-title">Dashboard Information</div>
                        <div class="metric-item">
                            <span class="metric-label">Generated:</span>
                            <span class="metric-value">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                        </div>
                        <div class="metric-item">
                            <span class="metric-label">Sample Size:</span>
                            <span class="metric-value">{total_listings:,} listings</span>
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
            
            <script>
                // Price distribution chart
                const ctx = document.getElementById('priceChart').getContext('2d');
                new Chart(ctx, {{
                    type: 'bar',
                    data: {{
                        labels: ['<200k', '200-400k', '400-600k', '600-800k', '800k-1M', '>1M'],
                        datasets: [{{
                            label: 'Price Distribution',
                            data: [
                                {len(results_df[results_df['price'] < 200000])},
                                {len(results_df[(results_df['price'] >= 200000) & (results_df['price'] < 400000)])},
                                {len(results_df[(results_df['price'] >= 400000) & (results_df['price'] < 600000)])},
                                {len(results_df[(results_df['price'] >= 600000) & (results_df['price'] < 800000)])},
                                {len(results_df[(results_df['price'] >= 800000) & (results_df['price'] < 1000000)])},
                                {len(results_df[results_df['price'] >= 1000000])}
                            ],
                            backgroundColor: [
                                '#0047AB',
                                '#1E90FF',
                                '#4169E1',
                                '#6495ED',
                                '#87CEEB',
                                '#B0E0E6'
                            ],
                            borderColor: '#0047AB',
                            borderWidth: 1
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                title: {{
                                    display: true,
                                    text: 'Number of Listings'
                                }}
                            }},
                            x: {{
                                title: {{
                                    display: true,
                                    text: 'Price Range (€)'
                                }}
                            }}
                        }},
                        plugins: {{
                            legend: {{
                                display: false
                            }},
                            title: {{
                                display: true,
                                text: 'Espoo Property Price Distribution'
                            }}
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        return html_template


def main():
    """Demo usage of EspooDashboard"""
    print("🎨 Espoo Dashboard Generator Demo")
    print("=" * 50)
    
    dashboard = EspooDashboard()
    
    # Create Espoo dashboard
    espoo_dashboard = dashboard.create_espoo_dashboard(sample_size=20)
    
    if espoo_dashboard:
        print(f"✅ Espoo dashboard created: {espoo_dashboard}")
        
        # Open in browser
        import webbrowser
        webbrowser.open(f"file://{Path(espoo_dashboard).absolute()}")
    else:
        print("❌ Failed to create Espoo dashboard")


if __name__ == "__main__":
    main()