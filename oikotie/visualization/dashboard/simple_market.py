#!/usr/bin/env python3
"""
Simple Market Dashboard - Direct address-based visualization
No complex spatial matching - just use existing coordinates
"""

import json
import folium
import pandas as pd
import plotly.express as px
from datetime import datetime
from pathlib import Path
import duckdb
import numpy as np

class SimpleMarketDashboard:
    def __init__(self, db_path="data/real_estate.duckdb"):
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        
    def load_listings_with_coordinates(self):
        """Load listings with their geocoded coordinates - FAST & SIMPLE"""
        query = """
        SELECT 
            l.listing_type,
            l.price_eur,
            l.size_m2,
            l.address,
            l.postal_code,
            al.lat as latitude,
            al.lon as longitude,
            l.other_details_json
        FROM listings l
        JOIN address_locations al ON l.address = al.address
        WHERE l.price_eur IS NOT NULL 
        AND al.lat IS NOT NULL 
        AND al.lon IS NOT NULL
        LIMIT 500
        """
        
        df = self.conn.execute(query).fetchdf()
        print(f"✅ Loaded {len(df)} listings with coordinates")
        
        # Add price per square meter
        df['price_per_m2'] = df['price_eur'] / df['size_m2']
        
        return df
        
    def create_simple_map(self, listings_df):
        """Create simple marker-based map"""
        
        # Center map on Helsinki
        center_lat = listings_df['latitude'].mean()
        center_lon = listings_df['longitude'].mean()
        
        # Create base map with proper sizing
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=11,
            tiles='OpenStreetMap',
            width='100%',
            height='550px'
        )
        
        # Color scheme based on price
        def get_marker_color(price):
            if price < 200000:
                return 'green'
            elif price < 400000:
                return 'blue'
            elif price < 600000:
                return 'orange'
            else:
                return 'red'
        
        # Add markers for listings
        for _, listing in listings_df.iterrows():
            color = get_marker_color(listing['price_eur'])
            
            folium.CircleMarker(
                location=[listing['latitude'], listing['longitude']],
                radius=6,
                popup=f"""
                <div style='width:250px'>
                <h5>{listing['listing_type']}</h5>
                <b>Price:</b> €{listing['price_eur']:,.0f}<br>
                <b>Size:</b> {listing['size_m2']} m²<br>
                <b>Price/m²:</b> €{listing['price_per_m2']:,.0f}<br>
                <b>Address:</b> {listing['address']}<br>
                <b>Postal:</b> {listing['postal_code']}
                </div>
                """,
                tooltip=f"€{listing['price_eur']:,.0f} - {listing['size_m2']}m²",
                color='white',
                fillColor=color,
                fillOpacity=0.8,
                weight=1
            ).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 50px; width: 180px; height: 110px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px">
        <p><b>Price Ranges</b></p>
        <p><i class="fa fa-circle" style="color:green"></i> < €200k</p>
        <p><i class="fa fa-circle" style="color:blue"></i> €200k - €400k</p>
        <p><i class="fa fa-circle" style="color:orange"></i> €400k - €600k</p>
        <p><i class="fa fa-circle" style="color:red"></i> > €600k</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m
    
    def create_market_charts(self, listings_df):
        """Create market analysis charts"""
        charts = {}
        
        # Price distribution
        charts['price_dist'] = px.histogram(
            listings_df,
            x='price_eur',
            nbins=30,
            title="Property Price Distribution",
            labels={'price_eur': 'Price (€)', 'count': 'Number of Properties'}
        )
        
        # Price by property type
        avg_by_type = listings_df.groupby('listing_type')['price_eur'].mean().sort_values(ascending=False)
        charts['price_by_type'] = px.bar(
            x=avg_by_type.index,
            y=avg_by_type.values,
            title="Average Price by Property Type",
            labels={'x': 'Property Type', 'y': 'Average Price (€)'}
        )
        
        # Price per m² analysis
        charts['price_per_m2'] = px.scatter(
            listings_df,
            x='size_m2',
            y='price_per_m2',
            color='listing_type',
            title="Price per m² vs Property Size",
            labels={'size_m2': 'Size (m²)', 'price_per_m2': 'Price per m² (€)'}
        )
        
        # Postal code analysis
        postal_stats = listings_df.groupby('postal_code').agg({
            'price_eur': 'mean',
            'price_per_m2': 'mean',
            'listing_type': 'count'
        }).rename(columns={'listing_type': 'count'}).sort_values('price_eur', ascending=False).head(10)
        
        charts['postal_analysis'] = px.bar(
            x=postal_stats.index,
            y=postal_stats['price_eur'],
            title="Average Price by Postal Code (Top 10)",
            labels={'x': 'Postal Code', 'y': 'Average Price (€)'}
        )
        
        return charts
    
    def generate_dashboard(self, output_path=None):
        """Generate complete simple dashboard"""
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("output/simple_market")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"simple_market_dashboard_{timestamp}.html"
        
        print("🏠 SIMPLE MARKET DASHBOARD")
        print("=" * 50)
        print("📊 Loading market data...")
        
        # Load data
        listings_df = self.load_listings_with_coordinates()
        
        # Create map
        print("🗺️ Creating market map...")
        map_obj = self.create_simple_map(listings_df)
        
        # Create charts
        print("📈 Generating market charts...")
        charts = self.create_market_charts(listings_df)
        
        # Generate stats
        stats = self._generate_stats(listings_df)
        
        # Create HTML
        html_content = self._create_html_template(map_obj, charts, stats)
        
        # Save dashboard
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Simple market dashboard created: {output_path}")
        return output_path
    
    def _generate_stats(self, df):
        """Generate market statistics"""
        return {
            'total_listings': len(df),
            'avg_price': df['price_eur'].mean(),
            'median_price': df['price_eur'].median(),
            'avg_size': df['size_m2'].mean(),
            'avg_price_per_m2': df['price_per_m2'].mean(),
            'property_types': df['listing_type'].value_counts().to_dict()
        }
    
    def _create_html_template(self, map_obj, charts, stats):
        """Create simple HTML template"""
        
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
    <title>Simple Market Dashboard</title>
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        
        .dashboard-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            text-align: center;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
        }}
        
        .stat-label {{
            color: #6c757d;
            margin-top: 0.5rem;
        }}
        
        .content-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }}
        
        .map-section {{
            background: white;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            min-height: 600px;
        }}
        
        .map-section iframe {{
            width: 100% !important;
            height: 550px !important;
            border: none;
            border-radius: 5px;
        }}
        
        .charts-section {{
            display: grid;
            gap: 1rem;
        }}
        
        .chart-container {{
            background: white;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        @media (max-width: 768px) {{
            .content-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="dashboard-header">
        <h1>📊 Helsinki Real Estate Market</h1>
        <p>Simple and Fast Market Visualization</p>
    </div>
    
    <!-- Statistics Cards -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{stats['total_listings']:,}</div>
            <div class="stat-label">Total Listings</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">€{stats['avg_price']:,.0f}</div>
            <div class="stat-label">Average Price</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">€{stats['median_price']:,.0f}</div>
            <div class="stat-label">Median Price</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats['avg_size']:.1f} m²</div>
            <div class="stat-label">Average Size</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">€{stats['avg_price_per_m2']:,.0f}/m²</div>
            <div class="stat-label">Average Price per m²</div>
        </div>
    </div>
    
    <!-- Main Content Grid -->
    <div class="content-grid">
        <!-- Map Section -->
        <div class="map-section">
            <h3>🗺️ Market Map</h3>
            {map_html}
        </div>
        
        <!-- Charts Section -->
        <div class="charts-section">
            <div class="chart-container">
                {chart_htmls.get('price_dist', '<p>Price distribution chart not available</p>')}
            </div>
            
            <div class="chart-container">
                {chart_htmls.get('price_by_type', '<p>Price by type chart not available</p>')}
            </div>
            
            <div class="chart-container">
                {chart_htmls.get('price_per_m2', '<p>Price per m² chart not available</p>')}
            </div>
            
            <div class="chart-container">
                {chart_htmls.get('postal_analysis', '<p>Postal analysis chart not available</p>')}
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
        """
        
        return html_template

if __name__ == "__main__":
    dashboard = SimpleMarketDashboard()
    output_path = dashboard.generate_dashboard()
    print(f"Dashboard created: {output_path}")
