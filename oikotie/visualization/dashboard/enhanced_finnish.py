#!/usr/bin/env python3
"""
Enhanced Finnish Real Estate Dashboard
Map-focused visualization with Finland-specific filtering and building-only display
"""

import json
import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from pathlib import Path
import duckdb
from shapely.geometry import Point, shape
from shapely import wkt
import numpy as np

class EnhancedFinnishDashboard:
    def __init__(self, db_path="data/real_estate.duckdb"):
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        
        # Load spatial extension
        self.conn.execute("INSTALL spatial;")
        self.conn.execute("LOAD spatial;")
        
    def load_listings_with_details(self):
        """Load ALL listings with parsed Finnish housing details"""
        query = """
        SELECT 
            l.*,
            al.lat as latitude,
            al.lon as longitude
        FROM listings l
        LEFT JOIN address_locations al ON l.address = al.address
        WHERE l.price_eur IS NOT NULL 
        AND al.lat IS NOT NULL 
        AND al.lon IS NOT NULL
        """
        
        df = self.conn.execute(query).fetchdf()
        
        # Parse Finnish housing details from JSON
        df = self._parse_finnish_details(df)
        
        return df
    
    def _parse_finnish_details(self, df):
        """Parse Finnish housing market details from other_details_json"""
        
        # Initialize new columns
        df['hoitovastike'] = None
        df['velkaosuus'] = None
        df['paaomavastike'] = None
        df['yhtiovastike_yhteensa'] = None
        df['asumistyyppi'] = None
        df['tontin_omistus'] = None
        df['kerros'] = None
        df['kerroksia'] = None
        df['neliohinta'] = None
        df['vesimaksu'] = None
        df['energialuokka'] = None
        df['rakennusmateriaali'] = None
        df['payment_model'] = 'Unknown'
        df['land_ownership'] = 'Unknown'
        df['maintenance_category'] = 'Unknown'
        
        # Parse JSON details
        for idx, row in df.iterrows():
            if pd.notna(row['other_details_json']):
                try:
                    details = json.loads(row['other_details_json'])
                    
                    # Extract key Finnish housing metrics
                    df.at[idx, 'hoitovastike'] = self._extract_euro_amount(details.get('hoitovastike'))
                    df.at[idx, 'velkaosuus'] = self._extract_euro_amount(details.get('velkaosuus'))
                    df.at[idx, 'paaomavastike'] = self._extract_euro_amount(details.get('paaomavastike'))
                    df.at[idx, 'yhtiovastike_yhteensa'] = self._extract_euro_amount(details.get('yhtiovastike_yhteensa'))
                    df.at[idx, 'neliohinta'] = self._extract_euro_amount(details.get('neliohinta'))
                    df.at[idx, 'vesimaksu'] = self._extract_euro_amount(details.get('vesimaksu'))
                    
                    # Extract categorical data
                    df.at[idx, 'asumistyyppi'] = details.get('asumistyyppi', 'Unknown')
                    df.at[idx, 'tontin_omistus'] = details.get('tontin_omistus', 'Unknown')
                    df.at[idx, 'kerros'] = details.get('kerros', 'Unknown')
                    df.at[idx, 'kerroksia'] = details.get('kerroksia')
                    df.at[idx, 'energialuokka'] = details.get('energialuokka', 'Unknown')
                    df.at[idx, 'rakennusmateriaali'] = details.get('rakennusmateriaali', 'Unknown')
                    
                    # Categorize payment models (Finnish housing market specific)
                    df.at[idx, 'payment_model'] = self._categorize_payment_model(details)
                    df.at[idx, 'land_ownership'] = self._categorize_land_ownership(details)
                    df.at[idx, 'maintenance_category'] = self._categorize_maintenance_fee(
                        self._extract_euro_amount(details.get('hoitovastike'))
                    )
                    
                except json.JSONDecodeError:
                    continue
        
        return df
    
    def _extract_euro_amount(self, text):
        """Extract numeric euro amount from Finnish text"""
        if not text or pd.isna(text):
            return None
        
        try:
            # Handle various Finnish euro formats
            import re
            # Match patterns like "200 €", "200€", "200 € / kk", "1,500.50 €"
            match = re.search(r'([\d\s,\.]+)', str(text).replace(' ', ''))
            if match:
                amount_str = match.group(1).replace(',', '').replace(' ', '')
                return float(amount_str)
        except:
            pass
        return None
    
    def _categorize_payment_model(self, details):
        """Categorize Finnish payment models"""
        ownership = details.get('asumistyyppi', '').lower()
        debt = details.get('velkaosuus')
        land_type = details.get('tontin_omistus', '').lower()
        
        if 'vuokra' in ownership:
            return 'Rental'
        elif debt and self._extract_euro_amount(debt) and self._extract_euro_amount(debt) > 0:
            return 'Shared Debt (Lainaosuus)'
        elif 'oma' in land_type:
            return 'Full Ownership'
        else:
            return 'Cooperative Ownership'
    
    def _categorize_land_ownership(self, details):
        """Categorize land ownership types in Finland"""
        land_ownership = details.get('tontin_omistus', '').lower()
        
        if 'oma' in land_ownership:
            return 'Owned Land'
        elif 'vuokra' in land_ownership:
            return 'Leased Land'
        else:
            return 'Unknown'
    
    def _categorize_maintenance_fee(self, fee):
        """Categorize maintenance fees into ranges"""
        if not fee or pd.isna(fee):
            return 'Unknown'
        
        if fee < 200:
            return 'Low (< €200)'
        elif fee < 400:
            return 'Medium (€200-400)'
        elif fee < 600:
            return 'High (€400-600)'
        else:
            return 'Very High (> €600)'
    
    def load_buildings_with_listings(self, listings_df):
        """Load buildings that contain listings using efficient SQL spatial query"""
        print("🔍 Finding buildings with listings using spatial query...")
        
        # Use efficient SQL spatial query instead of nested loops
        buildings_query = """
        WITH listing_points AS (
            SELECT 
                l.listing_type,
                l.price_eur,
                al.lat as latitude,
                al.lon as longitude,
                ST_Point(al.lon, al.lat) as geom
            FROM listings l
            LEFT JOIN address_locations al ON l.address = al.address
            WHERE l.price_eur IS NOT NULL 
            AND al.lat IS NOT NULL 
            AND al.lon IS NOT NULL
        ),
        buildings_with_matches AS (
            SELECT 
                b.osm_id,
                b.type as building_type,
                b.name,
                ST_AsText(b.geom) as geometry_wkt,
                COUNT(lp.geom) as listings_count
            FROM osm_buildings b
            JOIN listing_points lp ON (
                ST_Contains(b.geom, lp.geom) OR
                ST_DWithin(b.geom, lp.geom, 0.0002)  -- ~20m tolerance
            )
            GROUP BY b.osm_id, b.type, b.name, b.geom
            HAVING COUNT(lp.geom) > 0
        )
        SELECT * FROM buildings_with_matches
        ORDER BY listings_count DESC
        """
        
        buildings_df = self.conn.execute(buildings_query).fetchdf()
        print(f"✅ Found {len(buildings_df)} buildings containing listings")
        
        return buildings_df
    
    def create_enhanced_map(self, listings_df, buildings_df):
        """Create map focused on buildings with listings (no individual markers)"""
        
        # Center map on Helsinki
        center_lat = listings_df['latitude'].mean()
        center_lon = listings_df['longitude'].mean()
        
        # Create base map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=12,
            tiles=None
        )
        
        # Add reliable tile layers
        folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)
        
        # Add CartoDB tile layers (more reliable)
        folium.TileLayer(
            tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
            attr='CartoDB',
            name='Light Theme',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            attr='CartoDB',
            name='Dark Theme',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Color scheme for building highlighting
        def get_building_color(listing_count):
            if listing_count >= 10:
                return '#FF4444'  # Red for high activity
            elif listing_count >= 5:
                return '#FF8844'  # Orange for medium activity
            elif listing_count >= 2:
                return '#FFBB44'  # Yellow for some activity
            else:
                return '#44BB44'  # Green for low activity
        
        # Add buildings with listings only
        for _, building in buildings_df.iterrows():
            try:
                geom = wkt.loads(building['geometry_wkt'])
                
                # Convert to GeoJSON-like coordinates
                if hasattr(geom, 'exterior'):
                    # Polygon
                    coords = list(geom.exterior.coords)
                    folium_coords = [[lat, lon] for lon, lat in coords]
                    
                    color = get_building_color(building['listings_count'])
                    
                    folium.Polygon(
                        locations=folium_coords,
                        popup=f"""
                        <div style='width:200px'>
                        <h4>Building Information</h4>
                        <b>Type:</b> {building.get('building_type', 'Unknown')}<br>
                        <b>Listings:</b> {building['listings_count']}<br>
                        <b>OSM ID:</b> {building['osm_id']}<br>
                        </div>
                        """,
                        tooltip=f"Building with {building['listings_count']} listings",
                        color=color,
                        fillColor=color,
                        fillOpacity=0.6,
                        weight=2
                    ).add_to(m)
                    
            except Exception as e:
                continue
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add fullscreen plugin
        from folium.plugins import Fullscreen
        Fullscreen().add_to(m)
        
        # Add legend for building colors
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 50px; width: 200px; height: 120px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px">
        <p><b>Buildings with Listings</b></p>
        <p><i class="fa fa-square" style="color:#FF4444"></i> High Activity (10+ listings)</p>
        <p><i class="fa fa-square" style="color:#FF8844"></i> Medium Activity (5-9 listings)</p>
        <p><i class="fa fa-square" style="color:#FFBB44"></i> Some Activity (2-4 listings)</p>
        <p><i class="fa fa-square" style="color:#44BB44"></i> Low Activity (1 listing)</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m
    
    def create_finnish_market_charts(self, listings_df):
        """Create Finland-specific market analysis charts"""
        charts = {}
        
        # 1. Payment Model Distribution
        payment_model_counts = listings_df['payment_model'].value_counts()
        charts['payment_model'] = px.pie(
            values=payment_model_counts.values,
            names=payment_model_counts.index,
            title="Finnish Payment Models Distribution",
            color_discrete_sequence=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57']
        )
        
        # 2. Land Ownership Analysis
        land_ownership_counts = listings_df['land_ownership'].value_counts()
        charts['land_ownership'] = px.bar(
            x=land_ownership_counts.index,
            y=land_ownership_counts.values,
            title="Land Ownership Types",
            labels={'x': 'Ownership Type', 'y': 'Number of Listings'},
            color=land_ownership_counts.values,
            color_continuous_scale='Viridis'
        )
        
        # 3. Maintenance Fee Analysis
        maintenance_df = listings_df[listings_df['hoitovastike'].notna()]
        if not maintenance_df.empty:
            charts['maintenance_fees'] = px.histogram(
                maintenance_df,
                x='hoitovastike',
                nbins=30,
                title="Maintenance Fee Distribution (€/month)",
                labels={'hoitovastike': 'Monthly Maintenance Fee (€)', 'count': 'Number of Properties'}
            )
            
            # Maintenance fees by property type
            maintenance_by_type = maintenance_df.groupby('listing_type')['hoitovastike'].mean().sort_values(ascending=False)
            charts['maintenance_by_type'] = px.bar(
                x=maintenance_by_type.index,
                y=maintenance_by_type.values,
                title="Average Maintenance Fee by Property Type",
                labels={'x': 'Property Type', 'y': 'Average Monthly Fee (€)'}
            )
        
        # 4. Debt Share Analysis
        debt_df = listings_df[listings_df['velkaosuus'].notna()]
        if not debt_df.empty:
            charts['debt_analysis'] = px.scatter(
                debt_df,
                x='price_eur',
                y='velkaosuus',
                color='listing_type',
                size='size_m2',
                title="Property Price vs Debt Share",
                labels={'price_eur': 'Property Price (€)', 'velkaosuus': 'Debt Share (€)'},
                hover_data=['postal_code', 'hoitovastike']
            )
        
        # 5. Energy Efficiency Analysis
        energy_df = listings_df[listings_df['energialuokka'] != 'Unknown']
        if not energy_df.empty:
            energy_counts = energy_df['energialuokka'].value_counts()
            charts['energy_efficiency'] = px.bar(
                x=energy_counts.index,
                y=energy_counts.values,
                title="Energy Efficiency Distribution",
                labels={'x': 'Energy Class', 'y': 'Number of Properties'},
                color=energy_counts.values,
                color_continuous_scale='RdYlGn'
            )
        
        return charts
    
    def generate_enhanced_dashboard(self, output_path=None):
        """Generate complete enhanced Finnish dashboard"""
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("output/enhanced_finnish_dashboard")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"enhanced_finnish_real_estate_{timestamp}.html"
        
        print("🏠 ENHANCED FINNISH REAL ESTATE DASHBOARD")
        print("=" * 60)
        print("📊 Loading Finnish housing market data...")
        
        # Load data
        listings_df = self.load_listings_with_details()
        print(f"✅ Loaded {len(listings_df)} listings with Finnish housing details")
        
        buildings_df = self.load_buildings_with_listings(listings_df)
        print(f"✅ Found {len(buildings_df)} buildings with listings")
        
        # Create map
        print("🗺️ Creating enhanced building-focused map...")
        map_obj = self.create_enhanced_map(listings_df, buildings_df)
        
        # Create charts
        print("📈 Generating Finnish market analysis charts...")
        charts = self.create_finnish_market_charts(listings_df)
        
        # Generate market statistics
        stats = self._generate_market_statistics(listings_df)
        
        # Create HTML template
        html_content = self._create_html_template(map_obj, charts, stats, listings_df)
        
        # Save dashboard
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Enhanced Finnish dashboard created: {output_path}")
        return output_path
    
    def _generate_market_statistics(self, df):
        """Generate comprehensive market statistics"""
        total_listings = len(df)
        
        # Financial statistics
        avg_price = df['price_eur'].mean()
        avg_size = df['size_m2'].mean()
        avg_price_per_m2 = df['neliohinta'].mean() if 'neliohinta' in df.columns else None
        avg_maintenance = df['hoitovastike'].mean() if 'hoitovastike' in df.columns else None
        
        # Payment model distribution
        payment_models = df['payment_model'].value_counts().to_dict()
        land_ownership = df['land_ownership'].value_counts().to_dict()
        
        # Property type distribution
        property_types = df['listing_type'].value_counts().to_dict()
        
        return {
            'total_listings': total_listings,
            'avg_price': avg_price,
            'avg_size': avg_size,
            'avg_price_per_m2': avg_price_per_m2,
            'avg_maintenance': avg_maintenance,
            'payment_models': payment_models,
            'land_ownership': land_ownership,
            'property_types': property_types
        }
    
    def _create_html_template(self, map_obj, charts, stats, listings_df):
        """Create enhanced HTML template with map focus and collapsible panels"""
        
        map_html = map_obj._repr_html_()
        
        # Convert charts to HTML
        chart_htmls = {}
        for chart_name, chart in charts.items():
            chart_htmls[chart_name] = chart.to_html(include_plotlyjs=False, div_id=f"chart_{chart_name}")
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced Finnish Real Estate Dashboard</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <!-- Plotly -->
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f8f9fa;
        }}
        
        .dashboard-container {{
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}
        
        .map-section {{
            flex: 0 0 75%;
            height: 100%;
            position: relative;
        }}
        
        .map-container {{
            width: 100%;
            height: 100%;
        }}
        
        .data-panel {{
            flex: 0 0 25%;
            background: white;
            border-left: 2px solid #dee2e6;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}
        
        .panel-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem;
            text-align: center;
        }}
        
        .panel-tabs {{
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }}
        
        .panel-content {{
            flex: 1;
            overflow-y: auto;
            padding: 0;
        }}
        
        .tab-pane {{
            padding: 1rem;
            height: 100%;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }}
        
        .stat-value {{
            font-size: 1.5rem;
            font-weight: bold;
            color: #667eea;
        }}
        
        .stat-label {{
            color: #6c757d;
            font-size: 0.9rem;
        }}
        
        .filter-section {{
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }}
        
        .chart-container {{
            background: white;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .nav-tabs .nav-link {{
            background: transparent;
            border: none;
            color: #6c757d;
            font-weight: 500;
        }}
        
        .nav-tabs .nav-link.active {{
            background: white;
            color: #667eea;
            border-bottom: 2px solid #667eea;
        }}
        
        .toggle-panel {{
            position: absolute;
            top: 50%;
            right: -20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            z-index: 1000;
            cursor: pointer;
            transform: translateY(-50%);
        }}
        
        .collapsed {{
            flex: 0 0 0%;
        }}
        
        .map-expanded {{
            flex: 0 0 100%;
        }}
        
        @media (max-width: 768px) {{
            .dashboard-container {{
                flex-direction: column;
            }}
            .map-section {{
                flex: 0 0 60%;
            }}
            .data-panel {{
                flex: 0 0 40%;
                border-left: none;
                border-top: 2px solid #dee2e6;
            }}
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- Map Section (75% width) -->
        <div class="map-section" id="mapSection">
            <div class="map-container">
                {map_html}
            </div>
        </div>
        
        <!-- Data Panel (25% width, collapsible) -->
        <div class="data-panel" id="dataPanel">
            <button class="toggle-panel" onclick="togglePanel()" id="toggleButton">
                <i class="fas fa-chevron-right" id="toggleIcon"></i>
            </button>
            
            <div class="panel-header">
                <h4><i class="fas fa-chart-line"></i> Finnish Housing Market Analytics</h4>
                <small>Helsinki Real Estate Analysis</small>
            </div>
            
            <!-- Tab Navigation -->
            <ul class="nav nav-tabs panel-tabs" id="panelTabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="overview-tab" data-bs-toggle="tab" 
                            data-bs-target="#overview" type="button" role="tab">
                        <i class="fas fa-home"></i> Overview
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="payment-tab" data-bs-toggle="tab" 
                            data-bs-target="#payment" type="button" role="tab">
                        <i class="fas fa-euro-sign"></i> Payment
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="maintenance-tab" data-bs-toggle="tab" 
                            data-bs-target="#maintenance" type="button" role="tab">
                        <i class="fas fa-tools"></i> Maintenance
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="energy-tab" data-bs-toggle="tab" 
                            data-bs-target="#energy" type="button" role="tab">
                        <i class="fas fa-leaf"></i> Energy
                    </button>
                </li>
            </ul>
            
            <!-- Tab Content -->
            <div class="tab-content panel-content" id="panelContent">
                <!-- Overview Tab -->
                <div class="tab-pane fade show active" id="overview" role="tabpanel">
                    <div class="stat-card">
                        <div class="stat-value">{stats['total_listings']:,}</div>
                        <div class="stat-label">Total Active Listings</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">€{stats['avg_price']:,.0f}</div>
                        <div class="stat-label">Average Property Price</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{stats['avg_size']:.1f} m²</div>
                        <div class="stat-label">Average Property Size</div>
                    </div>
                    
                    {f'''<div class="stat-card">
                        <div class="stat-value">€{stats['avg_price_per_m2']:,.0f}/m²</div>
                        <div class="stat-label">Average Price per m²</div>
                    </div>''' if stats['avg_price_per_m2'] else ''}
                    
                    {f'''<div class="stat-card">
                        <div class="stat-value">€{stats['avg_maintenance']:,.0f}/month</div>
                        <div class="stat-label">Average Maintenance Fee</div>
                    </div>''' if stats['avg_maintenance'] else ''}
                    
                    <div class="filter-section">
                        <h6><i class="fas fa-filter"></i> Property Types</h6>
                        {self._create_property_type_filter(stats['property_types'])}
                    </div>
                </div>
                
                <!-- Payment Models Tab -->
                <div class="tab-pane fade" id="payment" role="tabpanel">
                    <div class="filter-section">
                        <h6><i class="fas fa-euro-sign"></i> Payment Model Filters</h6>
                        {self._create_payment_model_filter(stats['payment_models'])}
                    </div>
                    
                    <div class="filter-section">
                        <h6><i class="fas fa-map-marked-alt"></i> Land Ownership</h6>
                        {self._create_land_ownership_filter(stats['land_ownership'])}
                    </div>
                    
                    <div class="chart-container">
                        {chart_htmls.get('payment_model', '<p>Payment model chart not available</p>')}
                    </div>
                    
                    <div class="chart-container">
                        {chart_htmls.get('land_ownership', '<p>Land ownership chart not available</p>')}
                    </div>
                </div>
                
                <!-- Maintenance Tab -->
                <div class="tab-pane fade" id="maintenance" role="tabpanel">
                    <div class="filter-section">
                        <h6><i class="fas fa-tools"></i> Maintenance Fee Filters</h6>
                        {self._create_maintenance_filter()}
                    </div>
                    
                    <div class="chart-container">
                        {chart_htmls.get('maintenance_fees', '<p>Maintenance fee chart not available</p>')}
                    </div>
                    
                    <div class="chart-container">
                        {chart_htmls.get('maintenance_by_type', '<p>Maintenance by type chart not available</p>')}
                    </div>
                    
                    <div class="chart-container">
                        {chart_htmls.get('debt_analysis', '<p>Debt analysis chart not available</p>')}
                    </div>
                </div>
                
                <!-- Energy Tab -->
                <div class="tab-pane fade" id="energy" role="tabpanel">
                    <div class="chart-container">
                        {chart_htmls.get('energy_efficiency', '<p>Energy efficiency chart not available</p>')}
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        function togglePanel() {{
            const panel = document.getElementById('dataPanel');
            const mapSection = document.getElementById('mapSection');
            const toggleIcon = document.getElementById('toggleIcon');
            
            if (panel.classList.contains('collapsed')) {{
                panel.classList.remove('collapsed');
                mapSection.classList.remove('map-expanded');
                toggleIcon.className = 'fas fa-chevron-right';
            }} else {{
                panel.classList.add('collapsed');
                mapSection.classList.add('map-expanded');
                toggleIcon.className = 'fas fa-chevron-left';
            }}
        }}
    </script>
</body>
</html>
        """
        
        return html_template
    
    def _create_property_type_filter(self, property_types):
        """Create property type filter HTML"""
        html = ""
        for prop_type, count in property_types.items():
            html += f"""
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="{prop_type}" id="prop_{prop_type}" checked>
                <label class="form-check-label" for="prop_{prop_type}">
                    {prop_type} ({count})
                </label>
            </div>
            """
        return html
    
    def _create_payment_model_filter(self, payment_models):
        """Create payment model filter HTML"""
        html = ""
        for model, count in payment_models.items():
            html += f"""
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="{model}" id="pay_{model}" checked>
                <label class="form-check-label" for="pay_{model}">
                    {model} ({count})
                </label>
            </div>
            """
        return html
    
    def _create_land_ownership_filter(self, land_ownership):
        """Create land ownership filter HTML"""
        html = ""
        for ownership, count in land_ownership.items():
            html += f"""
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="{ownership}" id="land_{ownership}" checked>
                <label class="form-check-label" for="land_{ownership}">
                    {ownership} ({count})
                </label>
            </div>
            """
        return html
    
    def _create_maintenance_filter(self):
        """Create maintenance fee filter HTML"""
        categories = ["Low (< €200)", "Medium (€200-400)", "High (€400-600)", "Very High (> €600)"]
        html = ""
        for category in categories:
            html += f"""
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="{category}" id="maint_{category}" checked>
                <label class="form-check-label" for="maint_{category}">
                    {category}
                </label>
            </div>
            """
        return html

if __name__ == "__main__":
    dashboard = EnhancedFinnishDashboard()
    output_path = dashboard.generate_enhanced_dashboard()
    print(f"Dashboard created: {output_path}")
