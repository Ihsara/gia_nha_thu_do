#!/usr/bin/env python3
"""
Property Polygon Visualization for Oikotie Real Estate Data

This script creates a master table linking property listings to property polygons
and generates an interactive map visualization showing:
- Property polygons from Helsinki open data
- Property listings with mouseover information
- Aggregated data when multiple listings exist for same property
"""

import duckdb
import pandas as pd
import geopandas as gpd
import folium
from folium import plugins
import json
import numpy as np
from shapely import wkt
from shapely.geometry import Point, Polygon
from shapely.ops import transform
import pyproj
from pathlib import Path
import logging
from typing import Dict, List, Tuple, Any
import matplotlib.pyplot as plt
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PropertyPolygonAnalyzer:
    """Analyzes and visualizes the relationship between property listings and polygons"""
    
    def __init__(self, db_path: str = "data/real_estate.duckdb"):
        """Initialize with database connection"""
        self.db_path = db_path
        self.conn = None
        
        # Coordinate system transformations
        self.finnish_crs = "EPSG:3067"  # Finnish National Grid KKJ
        self.wgs84_crs = "EPSG:4326"   # WGS84 for web maps
        
    def connect_db(self):
        """Connect to DuckDB database"""
        try:
            self.conn = duckdb.connect(self.db_path)
            logger.info(f"Connected to database: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def get_table_info(self) -> Dict[str, Dict]:
        """Get information about all tables in the database"""
        tables_info = {}
        
        # Get list of tables
        tables_query = "SHOW TABLES"
        tables = self.conn.execute(tables_query).fetchall()
        
        for table in tables:
            table_name = table[0]
            
            # Get column information
            desc_query = f"DESCRIBE {table_name}"
            columns = self.conn.execute(desc_query).fetchall()
            
            # Get row count
            count_query = f"SELECT COUNT(*) FROM {table_name}"
            row_count = self.conn.execute(count_query).fetchone()[0]
            
            tables_info[table_name] = {
                'columns': [col[0] for col in columns],
                'column_types': {col[0]: col[1] for col in columns},
                'row_count': row_count
            }
            
        return tables_info
    
    def analyze_table_relationships(self) -> Dict[str, Any]:
        """Analyze relationships between tables for linking listings to polygons"""
        logger.info("Analyzing table relationships...")
        
        table_info = self.get_table_info()
        
        # Key tables for our analysis
        key_tables = {
            'listings': 'Property listings with addresses',
            'helsinki_02_kiinteistorajansijaintitiedot': 'Property boundary polygons',
            'helsinki_properties': 'Property markers/points',
            'address_locations': 'Geocoded addresses',
            'postal_code_locations': 'Postal code centroids'
        }
        
        analysis = {
            'table_summary': {},
            'linking_strategy': {},
            'data_availability': {}
        }
        
        for table_name, description in key_tables.items():
            if table_name in table_info:
                info = table_info[table_name]
                analysis['table_summary'][table_name] = {
                    'description': description,
                    'row_count': info['row_count'],
                    'columns': info['columns'],
                    'has_geometry': any('geometry' in col.lower() for col in info['columns']),
                    'has_address': any('address' in col.lower() for col in info['columns']),
                    'has_coordinates': any(col.lower() in ['lat', 'lon', 'latitude', 'longitude', 'x', 'y'] for col in info['columns'])
                }
        
        # Define linking strategy
        analysis['linking_strategy'] = {
            'primary_approach': 'spatial_join',
            'steps': [
                '1. Extract property polygons from helsinki_02_kiinteistorajansijaintitiedot',
                '2. Geocode listing addresses to get coordinates',
                '3. Perform spatial join to find which polygon contains each listing point',
                '4. Aggregate multiple listings per property',
                '5. Create interactive visualization'
            ],
            'fallback_methods': [
                'Address matching with helsingin property addresses',
                'Postal code-based approximation',
                'Nearest neighbor matching'
            ]
        }
        
        return analysis
    
    def create_relationship_diagram(self, analysis: Dict[str, Any]):
        """Create a visual diagram of table relationships"""
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # Define table positions and connections
        tables = {
            'listings': {'pos': (2, 4), 'color': '#FF6B6B', 'size': 1500},
            'address_locations': {'pos': (1, 2), 'color': '#4ECDC4', 'size': 1200},
            'helsinki_02_kiinteistorajansijaintitiedot': {'pos': (4, 2), 'color': '#45B7D1', 'size': 1800},
            'helsinki_properties': {'pos': (6, 3), 'color': '#96CEB4', 'size': 1000},
            'postal_code_locations': {'pos': (0, 0), 'color': '#FFEAA7', 'size': 800}
        }
        
        # Draw tables as nodes
        for table_name, props in tables.items():
            if table_name in analysis['table_summary']:
                x, y = props['pos']
                info = analysis['table_summary'][table_name]
                
                # Draw circle for table
                circle = plt.Circle((x, y), 0.3, color=props['color'], alpha=0.7)
                ax.add_patch(circle)
                
                # Add table name
                ax.text(x, y, table_name.replace('_', '\n'), ha='center', va='center', 
                       fontsize=8, fontweight='bold', wrap=True)
                
                # Add row count
                ax.text(x, y-0.5, f"{info['row_count']:,} rows", ha='center', va='center', fontsize=6)
        
        # Draw relationships
        relationships = [
            ('listings', 'address_locations', 'address matching'),
            ('address_locations', 'helsinki_02_kiinteistorajansijaintitiedot', 'spatial join'),
            ('listings', 'postal_code_locations', 'postal code'),
            ('helsinki_properties', 'helsinki_02_kiinteistorajansijaintitiedot', 'boundary markers')
        ]
        
        for table1, table2, relationship in relationships:
            if table1 in tables and table2 in tables:
                x1, y1 = tables[table1]['pos']
                x2, y2 = tables[table2]['pos']
                
                ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                           arrowprops=dict(arrowstyle='->', lw=1.5, color='gray'))
                
                # Add relationship label
                mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
                ax.text(mid_x, mid_y + 0.1, relationship, ha='center', va='center', 
                       fontsize=6, style='italic', bbox=dict(boxstyle="round,pad=0.1", 
                       facecolor='white', alpha=0.8))
        
        ax.set_xlim(-1, 7)
        ax.set_ylim(-1, 5)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title('Property Data Table Relationships\nLinking Strategy for Listings → Property Polygons', 
                    fontsize=14, fontweight='bold', pad=20)
        
        plt.tight_layout()
        plt.savefig('output/table_relationships.png', dpi=300, bbox_inches='tight')
        plt.close()  # Close the plot instead of showing it
        
        logger.info("Table relationship diagram saved to output/table_relationships.png")
    
    def extract_listings_with_coords(self) -> pd.DataFrame:
        """Extract listings with their geocoded coordinates"""
        query = """
        SELECT 
            l.*,
            al.lat as latitude,
            al.lon as longitude
        FROM listings l
        LEFT JOIN address_locations al ON l.address = al.address
        WHERE al.lat IS NOT NULL AND al.lon IS NOT NULL
        """
        
        try:
            df = self.conn.execute(query).fetchdf()
            logger.info(f"Extracted {len(df)} listings with coordinate data")
            return df
        except Exception as e:
            logger.error(f"Error extracting listings: {e}")
            return pd.DataFrame()
    
    def extract_property_polygons(self) -> gpd.GeoDataFrame:
        """Extract property boundary polygons and convert LineStrings to Polygons"""
        query = """
        SELECT 
            kiinteistorajalaji,
            lahdeaineisto,
            interpolointitapa,
            geometry_wkt
        FROM helsinki_02_kiinteistorajansijaintitiedot
        WHERE geometry_wkt IS NOT NULL
        AND kiinteistorajalaji = 696
        LIMIT 10000
        """
        
        try:
            df = self.conn.execute(query).fetchdf()
            logger.info(f"Extracted {len(df)} property boundary records")
            
            # Convert WKT to geometry
            df['geometry'] = df['geometry_wkt'].apply(wkt.loads)
            
            # Create GeoDataFrame
            gdf = gpd.GeoDataFrame(df, geometry='geometry')
            
            # Set coordinate system to WGS84
            gdf.crs = self.wgs84_crs
            
            # DEBUG: Check geometry types
            geom_types = gdf['geometry'].geom_type.value_counts()
            logger.info(f"Geometry types found: {geom_types.to_dict()}")
            
            # Convert LineStrings to Polygons where possible
            converted_polygons = []
            failed_conversions = 0
            
            logger.info("Converting LineString boundaries to Polygons...")
            for idx, row in gdf.iterrows():
                geom = row['geometry']
                
                if geom.geom_type == 'LineString':
                    # Check if LineString is closed
                    if geom.is_closed:
                        try:
                            # Convert closed LineString to Polygon
                            polygon = Polygon(geom.coords)
                            if polygon.is_valid and polygon.area > 1e-10:  # Very small area threshold
                                new_row = row.copy()
                                new_row['geometry'] = polygon
                                converted_polygons.append(new_row)
                            else:
                                failed_conversions += 1
                        except Exception as e:
                            failed_conversions += 1
                    else:
                        # Try to close the LineString by adding the first point to the end
                        try:
                            coords = list(geom.coords)
                            if len(coords) > 2:  # Need at least 3 points for a polygon
                                coords.append(coords[0])  # Close the polygon
                                polygon = Polygon(coords)
                                if polygon.is_valid and polygon.area > 1e-10:
                                    new_row = row.copy()
                                    new_row['geometry'] = polygon
                                    converted_polygons.append(new_row)
                                else:
                                    failed_conversions += 1
                            else:
                                failed_conversions += 1
                        except Exception as e:
                            failed_conversions += 1
                elif geom.geom_type == 'Polygon':
                    # Keep existing polygons
                    converted_polygons.append(row)
                else:
                    failed_conversions += 1
            
            logger.info(f"Successfully converted {len(converted_polygons)} boundaries to polygons")
            logger.info(f"Failed conversions: {failed_conversions}")
            
            if converted_polygons:
                # Create new GeoDataFrame with converted polygons
                polygons_gdf = gpd.GeoDataFrame(converted_polygons, crs=self.wgs84_crs)
                
                # DEBUG: Check final geometry types
                final_geom_types = polygons_gdf['geometry'].geom_type.value_counts()
                logger.info(f"Final geometry types: {final_geom_types.to_dict()}")
                
                return polygons_gdf
            else:
                logger.error("No valid polygons could be created from boundary data")
                return gpd.GeoDataFrame()
            
        except Exception as e:
            logger.error(f"Error extracting property polygons: {e}")
            return gpd.GeoDataFrame()
    
    def create_master_table(self) -> pd.DataFrame:
        """Create master table linking listings to property polygons"""
        logger.info("Creating master table...")
        
        # Get listings with coordinates
        listings_df = self.extract_listings_with_coords()
        
        # Get property polygons
        polygons_gdf = self.extract_property_polygons()
        
        if listings_df.empty or polygons_gdf.empty:
            logger.error("Cannot create master table - missing data")
            return pd.DataFrame()
        
        # Create points from listing coordinates
        listings_with_coords = listings_df.dropna(subset=['latitude', 'longitude'])
        if listings_with_coords.empty:
            logger.error("No listings with valid coordinates")
            return pd.DataFrame()
        
        geometry = [Point(lon, lat) for lon, lat in 
                   zip(listings_with_coords['longitude'], listings_with_coords['latitude'])]
        listings_gdf = gpd.GeoDataFrame(listings_with_coords, geometry=geometry, crs=self.wgs84_crs)
        
        # DEBUG: Check listing coordinate ranges
        listing_bounds = listings_gdf.bounds
        logger.info(f"Listing coordinates range:")
        logger.info(f"  Longitude (min/max): {listing_bounds['minx'].min():.6f} / {listing_bounds['maxx'].max():.6f}")
        logger.info(f"  Latitude (min/max): {listing_bounds['miny'].min():.6f} / {listing_bounds['maxy'].max():.6f}")
        
        # DEBUG: Check polygon coordinate ranges
        polygon_bounds = polygons_gdf.bounds
        logger.info(f"Polygon coordinates range:")
        logger.info(f"  Longitude (min/max): {polygon_bounds['minx'].min():.6f} / {polygon_bounds['maxx'].max():.6f}")
        logger.info(f"  Latitude (min/max): {polygon_bounds['miny'].min():.6f} / {polygon_bounds['maxy'].max():.6f}")
        
        # DEBUG: Test specific point within Helsinki center for spatial relationships
        test_point = Point(24.9384, 60.1699)  # Helsinki center coordinates
        test_contains = polygons_gdf.contains(test_point).any()
        logger.info(f"Test Helsinki center point within any polygon: {test_contains}")
        
        # DEBUG: Check if any listing points are contained within any polygons using different predicates
        logger.info("Testing spatial relationship predicates...")
        
        # Test intersects predicate
        test_intersects = gpd.sjoin(listings_gdf.head(10), polygons_gdf, how='inner', predicate='intersects')
        logger.info(f"Sample intersects join found {len(test_intersects)} matches")
        
        # Test within predicate
        test_within = gpd.sjoin(listings_gdf.head(10), polygons_gdf, how='inner', predicate='within')
        logger.info(f"Sample within join found {len(test_within)} matches")
        
        # Perform spatial join
        logger.info("Performing spatial join...")
        joined = gpd.sjoin(listings_gdf, polygons_gdf, how='left', predicate='within')
        
        # DEBUG: Check join results
        matches = joined['index_right'].notna().sum()
        total = len(joined)
        logger.info(f"Spatial join results: {matches}/{total} listings matched to polygons")
        
        # If no matches with 'within', try 'intersects' as fallback
        if matches == 0:
            logger.warning("No matches with 'within' predicate, trying 'intersects'...")
            joined = gpd.sjoin(listings_gdf, polygons_gdf, how='left', predicate='intersects')
            matches = joined['index_right'].notna().sum()
            logger.info(f"Intersects join results: {matches}/{total} listings matched to polygons")
        
        # Create property identifier (using row index as natural key for now)
        joined['property_id'] = joined.index_right.fillna(-1).astype(int)
        joined['property_id'] = joined['property_id'].apply(lambda x: f"PROP_{x:06d}" if x >= 0 else "UNMATCHED")
        
        # Aggregate data by property
        master_data = []
        
        for property_id in joined['property_id'].unique():
            property_listings = joined[joined['property_id'] == property_id]
            
            if len(property_listings) == 0:
                continue
            
            # Get representative address and coordinates
            first_listing = property_listings.iloc[0]
            
            # Aggregate listing information
            listing_count = len(property_listings)
            prices = property_listings['price_eur'].dropna()
            sizes = property_listings['size_m2'].dropna()
            rooms = property_listings['rooms'].dropna()
            
            # Get layout distribution
            layout_counts = property_listings['rooms'].value_counts().to_dict()
            layout_info = []
            for room_count, count in layout_counts.items():
                if pd.notna(room_count):
                    if room_count == 1:
                        layout_info.append(f"{count}x Studio")
                    else:
                        layout_info.append(f"{count}x {int(room_count)}BR")
            
            master_record = {
                'property_id': property_id,
                'address': first_listing['address'],
                'postal_code': first_listing['postal_code'],
                'city': first_listing['city'],
                'latitude': first_listing['latitude'],
                'longitude': first_listing['longitude'],
                'polygon_geometry': first_listing.get('geometry_wkt_right', None),
                'listing_count': listing_count,
                'min_price_eur': prices.min() if len(prices) > 0 else None,
                'max_price_eur': prices.max() if len(prices) > 0 else None,
                'avg_price_eur': prices.mean() if len(prices) > 0 else None,
                'min_size_m2': sizes.min() if len(sizes) > 0 else None,
                'max_size_m2': sizes.max() if len(sizes) > 0 else None,
                'avg_size_m2': sizes.mean() if len(sizes) > 0 else None,
                'layout_distribution': ', '.join(layout_info) if layout_info else 'Unknown',
                'property_types': ', '.join(property_listings['listing_type'].unique()),
                'confidence_score': first_listing.get('confidence_score', None),
                'geocoding_source': first_listing.get('geocoding_source', None),
                'has_polygon': property_id != "UNMATCHED"
            }
            
            master_data.append(master_record)
        
        master_df = pd.DataFrame(master_data)
        logger.info(f"Created master table with {len(master_df)} properties")
        logger.info(f"Properties with polygons: {master_df['has_polygon'].sum()}")
        logger.info(f"Properties with multiple listings: {(master_df['listing_count'] > 1).sum()}")
        
        return master_df
    
    def create_interactive_visualization(self, master_df: pd.DataFrame):
        """Create interactive map visualization"""
        logger.info("Creating interactive visualization...")
        
        # Create base map centered on Helsinki
        helsinki_center = [60.1699, 24.9384]
        m = folium.Map(
            location=helsinki_center,
            zoom_start=11,
            tiles='OpenStreetMap'
        )
        
        # Add different tile layers
        folium.TileLayer('cartodbpositron').add_to(m)
        folium.TileLayer('cartodbdark_matter').add_to(m)
        
        # Color mapping for listing counts
        def get_color(listing_count):
            if listing_count == 1:
                return '#1f77b4'  # Blue for single listings
            elif listing_count == 2:
                return '#ff7f0e'  # Orange for 2 listings
            elif listing_count <= 5:
                return '#d62728'  # Red for 3-5 listings
            else:
                return '#9467bd'  # Purple for 6+ listings
        
        # Add property markers
        for idx, row in master_df.iterrows():
            if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                
                # Create popup content
                popup_html = f"""
                <div style="font-family: Arial; max-width: 300px;">
                    <h4 style="margin-bottom: 10px; color: #333;">Property {row['property_id']}</h4>
                    <p><strong>Address:</strong> {row['address']}</p>
                    <p><strong>Listings:</strong> {row['listing_count']}</p>
                    
                    {f"<p><strong>Price Range:</strong> €{row['min_price_eur']:,.0f} - €{row['max_price_eur']:,.0f}</p>" if pd.notna(row['min_price_eur']) else ""}
                    {f"<p><strong>Average Price:</strong> €{row['avg_price_eur']:,.0f}</p>" if pd.notna(row['avg_price_eur']) else ""}
                    
                    {f"<p><strong>Size Range:</strong> {row['min_size_m2']:.0f} - {row['max_size_m2']:.0f} m²</p>" if pd.notna(row['min_size_m2']) else ""}
                    
                    <p><strong>Layout:</strong> {row['layout_distribution']}</p>
                    <p><strong>Property Types:</strong> {row['property_types']}</p>
                    
                    <p><strong>Has Polygon:</strong> {"Yes" if row['has_polygon'] else "No"}</p>
                </div>
                """
                
                # Determine marker size based on listing count
                radius = 5 + (row['listing_count'] * 2)
                
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=radius,
                    popup=folium.Popup(popup_html, max_width=350),
                    color='white',
                    weight=2,
                    fillColor=get_color(row['listing_count']),
                    fillOpacity=0.7,
                    tooltip=f"Property {row['property_id']} - {row['listing_count']} listing(s)"
                ).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 200px; height: 150px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <h4>Legend</h4>
        <p><span style="color:#1f77b4;">●</span> 1 listing</p>
        <p><span style="color:#ff7f0e;">●</span> 2 listings</p>
        <p><span style="color:#d62728;">●</span> 3-5 listings</p>
        <p><span style="color:#9467bd;">●</span> 6+ listings</p>
        <p><small>Marker size = number of listings</small></p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Save map
        output_path = Path("output/property_polygon_visualization.html")
        output_path.parent.mkdir(exist_ok=True)
        m.save(str(output_path))
        
        logger.info(f"Interactive visualization saved to {output_path}")
        
        return m
    
    def generate_summary_report(self, master_df: pd.DataFrame):
        """Generate summary statistics and report"""
        logger.info("Generating summary report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_properties': len(master_df),
            'properties_with_polygons': master_df['has_polygon'].sum(),
            'properties_with_multiple_listings': (master_df['listing_count'] > 1).sum(),
            'total_listings': master_df['listing_count'].sum(),
            'avg_listings_per_property': master_df['listing_count'].mean(),
            'max_listings_per_property': master_df['listing_count'].max(),
            'price_statistics': {
                'min_avg_price': master_df['avg_price_eur'].min(),
                'max_avg_price': master_df['avg_price_eur'].max(),
                'overall_avg_price': master_df['avg_price_eur'].mean()
            },
            'size_statistics': {
                'min_avg_size': master_df['avg_size_m2'].min(),
                'max_avg_size': master_df['avg_size_m2'].max(),
                'overall_avg_size': master_df['avg_size_m2'].mean()
            }
        }
        
        # Save master table
        master_output_path = Path("output/master_property_table.csv")
        master_output_path.parent.mkdir(exist_ok=True)
        master_df.to_csv(master_output_path, index=False)
        
        # Save report
        report_path = Path("output/property_analysis_report.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Master table saved to {master_output_path}")
        logger.info(f"Analysis report saved to {report_path}")
        
        return report
    
    def run_complete_analysis(self):
        """Run the complete analysis and visualization"""
        logger.info("Starting complete property polygon analysis...")
        
        try:
            # Connect to database
            self.connect_db()
            
            # Analyze table relationships
            analysis = self.analyze_table_relationships()
            
            # Create relationship diagram
            self.create_relationship_diagram(analysis)
            
            # Create master table
            master_df = self.create_master_table()
            
            if not master_df.empty:
                # Create visualization
                self.create_interactive_visualization(master_df)
                
                # Generate report
                report = self.generate_summary_report(master_df)
                
                logger.info("Analysis completed successfully!")
                logger.info(f"Total properties analyzed: {len(master_df)}")
                logger.info(f"Properties with polygons: {master_df['has_polygon'].sum()}")
                logger.info(f"Properties with multiple listings: {(master_df['listing_count'] > 1).sum()}")
                
                return master_df, report
            else:
                logger.error("Failed to create master table")
                return None, None
                
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise
        finally:
            if self.conn:
                self.conn.close()

def main():
    """Main function to run the analysis"""
    try:
        analyzer = PropertyPolygonAnalyzer()
        master_df, report = analyzer.run_complete_analysis()
        
        if master_df is not None:
            print("\n" + "="*50)
            print("PROPERTY POLYGON ANALYSIS COMPLETED")
            print("="*50)
            print(f"Total Properties: {len(master_df)}")
            print(f"Properties with Polygons: {master_df['has_polygon'].sum()}")
            print(f"Properties with Multiple Listings: {(master_df['listing_count'] > 1).sum()}")
            print(f"Total Listings: {master_df['listing_count'].sum()}")
            print("\nOutput Files Generated:")
            print("- output/table_relationships.png")
            print("- output/property_polygon_visualization.html")
            print("- output/master_property_table.csv")
            print("- output/property_analysis_report.json")
            print("\nOpen the HTML file in your browser to see the interactive map!")
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
