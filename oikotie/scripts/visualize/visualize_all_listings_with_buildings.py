#!/usr/bin/env python3
"""
Comprehensive Listing Visualization with Related Buildings Only.

This script creates a visualization showing ALL listings with their matched building polygons.
Only buildings that have relationships with listings are displayed for performance optimization.
All outputs are saved to output/visualization/ directory.
"""

import sys
from pathlib import Path
from datetime import datetime
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely import wkt
import folium
from folium.plugins import MarkerCluster, HeatMap
from typing import Tuple, List, Dict, Any
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from oikotie.visualization.utils.data_loader import DataLoader


def load_all_listings_from_database() -> gpd.GeoDataFrame:
    """
    Load ALL real estate listings from the database with coordinates.
    
    Returns:
        GeoDataFrame with all listing points that have coordinates
    """
    print(f"📍 Loading ALL listings from database...")
    
    with DataLoader() as loader:
        conn = loader.connect()
        query = """
        SELECT 
            l.address, 
            l.price_eur as price, 
            l.listing_type, 
            l.scraped_at as listing_date,
            l.title,
            l.postal_code,
            l.size_m2,
            l.rooms,
            l.year_built,
            a.lat as latitude, 
            a.lon as longitude
        FROM listings l
        INNER JOIN address_locations a ON l.address = a.address
        WHERE a.lat IS NOT NULL AND a.lon IS NOT NULL
        AND l.deleted_ts IS NULL
        """
        
        df = conn.execute(query).fetchdf()
    
    if len(df) == 0:
        print("❌ No listings with coordinates found in database")
        return gpd.GeoDataFrame()
    
    # Create GeoDataFrame from listings
    geometry = [Point(lon, lat) for lon, lat in zip(df['longitude'], df['latitude'])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    
    print(f"✅ Loaded {len(gdf)} listings with coordinates from database")
    return gdf


def find_buildings_for_listings(listings_gdf: gpd.GeoDataFrame, buffer_distance: float = 0.001) -> Tuple[gpd.GeoDataFrame, List[Dict[str, Any]]]:
    """
    Find buildings that match with listings and return only related buildings.
    
    Args:
        listings_gdf: GeoDataFrame with listing points
        buffer_distance: Buffer distance in degrees (~100m)
        
    Returns:
        Tuple of (related_buildings_gdf, matches_list)
    """
    print(f"🏢 Finding buildings related to {len(listings_gdf)} listings...")
    
    # Load buildings from database
    with DataLoader() as loader:
        conn = loader.connect()
        
        # Load spatial extension
        try:
            conn.execute("INSTALL spatial;")
            conn.execute("LOAD spatial;")
        except:
            pass
        
        # Get buildings with WKT geometry
        query = """
        SELECT 
            feature_id, 
            ST_AsText(geometry) as geometry_wkt,
            building_use_code, 
            floor_count, 
            'gpkg_buildings' as data_source
        FROM gpkg_buildings 
        WHERE geometry IS NOT NULL
        """
        
        df = conn.execute(query).fetchdf()
    
    if len(df) == 0:
        print("❌ No buildings found in database")
        return gpd.GeoDataFrame(), []
    
    print(f"📊 Processing {len(df)} buildings from database...")
    
    # Convert WKT to shapely geometries
    def convert_wkt_geom(wkt_str):
        if wkt_str and isinstance(wkt_str, str):
            return wkt.loads(wkt_str)
        else:
            return None
    
    df['geometry'] = df['geometry_wkt'].apply(convert_wkt_geom)
    df = df[df['geometry'].notna()]
    
    buildings_gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
    print(f"✅ Created building GeoDataFrame with {len(buildings_gdf)} polygons")
    
    # Find matches and collect related building IDs
    matches = []
    related_building_ids = set()
    
    print(f"🔍 Performing spatial matching...")
    
    for idx, listing in listings_gdf.iterrows():
        point = listing.geometry
        
        # Direct contains check
        containing = buildings_gdf[buildings_gdf.contains(point)]
        if not containing.empty:
            building_idx = containing.index[0]
            building_feature_id = containing.iloc[0]['feature_id']
            related_building_ids.add(building_feature_id)
            
            matches.append({
                'listing_idx': idx,
                'building_idx': building_idx,
                'building_feature_id': building_feature_id,
                'match_type': 'direct',
                'distance': 0.0,
                'address': listing.get('address', 'Unknown'),
                'price': listing.get('price', 0),
                'listing_type': listing.get('listing_type', 'Unknown')
            })
            continue
        
        # Buffer search for nearby buildings
        buffered = point.buffer(buffer_distance)
        intersecting = buildings_gdf[buildings_gdf.intersects(buffered)]
        
        if not intersecting.empty:
            # Find closest building
            distances = intersecting.geometry.distance(point)
            closest_idx = distances.idxmin()
            closest_distance = distances.min()
            building_feature_id = intersecting.loc[closest_idx]['feature_id']
            related_building_ids.add(building_feature_id)
            
            matches.append({
                'listing_idx': idx,
                'building_idx': closest_idx,
                'building_feature_id': building_feature_id,
                'match_type': 'buffer',
                'distance': closest_distance,
                'address': listing.get('address', 'Unknown'),
                'price': listing.get('price', 0),
                'listing_type': listing.get('listing_type', 'Unknown')
            })
        else:
            # No match found
            matches.append({
                'listing_idx': idx,
                'building_idx': None,
                'building_feature_id': None,
                'match_type': 'no_match',
                'distance': None,
                'address': listing.get('address', 'Unknown'),
                'price': listing.get('price', 0),
                'listing_type': listing.get('listing_type', 'Unknown')
            })
    
    # Filter buildings to only those with relationships
    related_buildings_gdf = buildings_gdf[buildings_gdf['feature_id'].isin(related_building_ids)]
    
    print(f"✅ Found {len(related_buildings_gdf)} buildings with listing relationships")
    print(f"📊 Match Statistics:")
    
    match_stats = {
        'direct': sum(1 for m in matches if m['match_type'] == 'direct'),
        'buffer': sum(1 for m in matches if m['match_type'] == 'buffer'),
        'no_match': sum(1 for m in matches if m['match_type'] == 'no_match')
    }
    
    for match_type, count in match_stats.items():
        percentage = (count / len(matches)) * 100 if matches else 0
        print(f"   {match_type.title()}: {count} ({percentage:.1f}%)")
    
    return related_buildings_gdf, matches


def create_comprehensive_visualization(
    listings_gdf: gpd.GeoDataFrame,
    buildings_gdf: gpd.GeoDataFrame,
    matches: List[Dict[str, Any]],
    output_file: str
) -> str:
    """
    Create comprehensive interactive visualization with all listings and related buildings.
    
    Args:
        listings_gdf: GeoDataFrame with all listings
        buildings_gdf: GeoDataFrame with related buildings only
        matches: List of match results
        output_file: Output HTML file path in output/visualization/
        
    Returns:
        Path to created HTML file
    """
    print(f"🗺️  Creating comprehensive visualization...")
    
    # Ensure output directory exists
    output_dir = Path("output/visualization")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_file
    
    # Calculate center point
    if len(listings_gdf) > 0:
        center_lat = listings_gdf.geometry.y.mean()
        center_lon = listings_gdf.geometry.x.mean()
    else:
        center_lat, center_lon = 60.17, 24.94  # Helsinki center
    
    # Create map with multiple tile layers
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles='OpenStreetMap'
    )
    
    # Add additional tile layers
    folium.TileLayer('cartodbpositron', name='CartoDB Positron').add_to(m)
    folium.TileLayer('cartodbdark_matter', name='CartoDB Dark').add_to(m)
    
    # Add comprehensive title and statistics
    total_listings = len(listings_gdf)
    total_buildings = len(buildings_gdf)
    match_rate = (sum(1 for m in matches if m['match_type'] in ['direct', 'buffer']) / len(matches)) * 100 if matches else 0
    
    title_html = f'''
    <div style="position: fixed; 
                top: 10px; left: 10px; width: 400px; height: 140px; 
                background-color: white; border: 2px solid grey; z-index:9999; 
                font-size:12px; padding: 10px; border-radius: 5px; box-shadow: 3px 3px 5px rgba(0,0,0,0.3);
                ">
    <h3 style="margin: 0 0 10px 0; color: #2c3e50;">🏠 Helsinki Real Estate Overview</h3>
    <p style="margin: 5px 0;"><strong>Total Listings:</strong> {total_listings:,}</p>
    <p style="margin: 5px 0;"><strong>Related Buildings:</strong> {total_buildings:,}</p>
    <p style="margin: 5px 0;"><strong>Match Rate:</strong> {match_rate:.1f}%</p>
    <p style="margin: 5px 0;"><strong>Data Source:</strong> GeoPackage + WMS</p>
    <p style="margin: 5px 0; font-size: 10px; color: #7f8c8d;">
        Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
    </p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    # Add buildings (only related ones)
    print(f"📍 Adding {len(buildings_gdf)} related buildings to map...")
    for idx, building in buildings_gdf.iterrows():
        # Count how many listings match this building
        building_matches = [m for m in matches if m['building_feature_id'] == building['feature_id']]
        match_count = len(building_matches)
        
        # Color based on number of listings
        if match_count >= 3:
            color = '#d73027'  # Dark red for high activity
            fill_opacity = 0.7
        elif match_count == 2:
            color = '#fc8d59'  # Orange for medium activity
            fill_opacity = 0.6
        else:
            color = '#4575b4'  # Blue for single listing
            fill_opacity = 0.4
        
        # Create popup with building and listing information
        popup_content = f"""
        <div style="width: 250px;">
            <h4>🏢 Building {building['feature_id']}</h4>
            <p><strong>Use Code:</strong> {building.get('building_use_code', 'Unknown')}</p>
            <p><strong>Floors:</strong> {building.get('floor_count', 'Unknown')}</p>
            <p><strong>Matched Listings:</strong> {match_count}</p>
            <hr>
            <h5>📋 Listings in this Building:</h5>
        """
        
        for match in building_matches[:3]:  # Show up to 3 listings
            listing = listings_gdf.iloc[match['listing_idx']]
            price_str = f"€{listing.get('price', 0):,.0f}" if listing.get('price') else "Price not available"
            popup_content += f"""
            <p style="font-size: 11px; margin: 5px 0;">
                <strong>{listing.get('listing_type', 'Unknown')}</strong><br/>
                {price_str}<br/>
                <em>{match['match_type']} match</em>
            </p>
            """
        
        if match_count > 3:
            popup_content += f"<p style='font-size: 10px; color: #666;'>... and {match_count - 3} more listings</p>"
        
        popup_content += "</div>"
        
        folium.GeoJson(
            building.geometry,
            style_function=lambda x, color=color, fill_opacity=fill_opacity: {
                'fillColor': color,
                'color': color,
                'weight': 2,
                'fillOpacity': fill_opacity,
                'opacity': 0.8
            },
            popup=folium.Popup(popup_content, max_width=300),
            tooltip=f"Building {building['feature_id']} - {match_count} listing(s)"
        ).add_to(m)
    
    # Create marker clusters for listings
    print(f"📍 Adding {len(listings_gdf)} listings with marker clustering...")
    
    # Group listings by match type
    direct_cluster = MarkerCluster(name="Direct Matches").add_to(m)
    buffer_cluster = MarkerCluster(name="Buffer Matches").add_to(m)
    no_match_cluster = MarkerCluster(name="No Building Match").add_to(m)
    
    # Create match lookup
    match_dict = {match['listing_idx']: match for match in matches}
    
    for idx, listing in listings_gdf.iterrows():
        match = match_dict.get(idx, {})
        match_type = match.get('match_type', 'unknown')
        
        # Determine marker style based on match type
        if match_type == 'direct':
            color = 'green'
            icon = 'home'
            cluster = direct_cluster
        elif match_type == 'buffer':
            color = 'orange'
            icon = 'home'
            cluster = buffer_cluster
        else:
            color = 'red'
            icon = 'question-sign'
            cluster = no_match_cluster
        
        # Create comprehensive popup content
        price_str = f"€{listing.get('price', 0):,.0f}" if listing.get('price') else "Price not available"
        size_str = f"{listing.get('size_m2', 0):.0f} m²" if listing.get('size_m2') else "Size not available"
        rooms_str = f"{listing.get('rooms', 'Unknown')} rooms"
        year_str = f"Built: {listing.get('year_built', 'Unknown')}"
        
        popup_content = f"""
        <div style="width: 280px;">
            <h4>🏠 {listing.get('listing_type', 'Unknown')} Listing</h4>
            <p><strong>Address:</strong> {listing.get('address', 'Unknown')}</p>
            <p><strong>Price:</strong> {price_str}</p>
            <p><strong>Size:</strong> {size_str}</p>
            <p><strong>Rooms:</strong> {rooms_str}</p>
            <p><strong>{year_str}</strong></p>
            <p><strong>Postal Code:</strong> {listing.get('postal_code', 'Unknown')}</p>
            <hr>
            <p><strong>Building Match:</strong> 
                <span style="color: {'green' if match_type == 'direct' else 'orange' if match_type == 'buffer' else 'red'};">
                    {match_type.title()}
                </span>
            </p>
            {f"<p><strong>Distance:</strong> {match.get('distance', 0):.4f}°</p>" if match.get('distance') else ""}
            {f"<p><strong>Building ID:</strong> {match.get('building_feature_id', 'None')}</p>" if match.get('building_feature_id') else ""}
        </div>
        """
        
        folium.Marker(
            location=[listing.geometry.y, listing.geometry.x],
            popup=folium.Popup(popup_content, max_width=300),
            icon=folium.Icon(color=color, icon=icon),
            tooltip=f"{listing.get('listing_type', 'Unknown')} - {price_str}"
        ).add_to(cluster)
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 10px; width: 250px; height: 180px; 
                background-color: white; border: 2px solid grey; z-index:9999; 
                font-size:12px; padding: 10px; border-radius: 5px; box-shadow: 3px 3px 5px rgba(0,0,0,0.3);
                ">
    <h4 style="margin: 0 0 10px 0;">Legend</h4>
    
    <h5 style="margin: 10px 0 5px 0;">Listings:</h5>
    <p style="margin: 2px 0;"><i class="fa fa-home" style="color:green"></i> Direct Building Match</p>
    <p style="margin: 2px 0;"><i class="fa fa-home" style="color:orange"></i> Buffer Match (~100m)</p>
    <p style="margin: 2px 0;"><i class="fa fa-question-sign" style="color:red"></i> No Building Match</p>
    
    <h5 style="margin: 10px 0 5px 0;">Buildings:</h5>
    <p style="margin: 2px 0;"><span style="color:#d73027">■</span> High Activity (3+ listings)</p>
    <p style="margin: 2px 0;"><span style="color:#fc8d59">■</span> Medium Activity (2 listings)</p>
    <p style="margin: 2px 0;"><span style="color:#4575b4">■</span> Single Listing</p>
    
    <p style="margin: 10px 0 0 0; font-size: 10px; color: #666;">
        Only buildings with listing relationships shown
    </p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Save map
    print(f"💾 Saving visualization to {output_path}")
    m.save(str(output_path))
    
    # Also save match data as JSON
    json_path = output_path.with_suffix('.json')
    match_summary = {
        'total_listings': total_listings,
        'total_buildings': total_buildings,
        'match_rate': match_rate,
        'match_statistics': {
            'direct': sum(1 for m in matches if m['match_type'] == 'direct'),
            'buffer': sum(1 for m in matches if m['match_type'] == 'buffer'),
            'no_match': sum(1 for m in matches if m['match_type'] == 'no_match')
        },
        'generated_at': datetime.now().isoformat()
    }
    
    with open(json_path, 'w') as f:
        json.dump(match_summary, f, indent=2)
    
    print(f"📊 Match statistics saved to {json_path}")
    return str(output_path)


def main():
    """Main function for comprehensive listing visualization."""
    print("🗺️  Comprehensive Listing Visualization - Started")
    print("=" * 70)
    
    # Load all listings
    listings_gdf = load_all_listings_from_database()
    if len(listings_gdf) == 0:
        print("❌ No listings found. Exiting.")
        sys.exit(1)
    
    # Find related buildings
    buildings_gdf, matches = find_buildings_for_listings(listings_gdf)
    
    if len(buildings_gdf) == 0:
        print("⚠️  No buildings found, but continuing with listings-only visualization")
    
    # Create comprehensive visualization
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"comprehensive_helsinki_listings_{timestamp}.html"
    
    visualization_path = create_comprehensive_visualization(
        listings_gdf, buildings_gdf, matches, output_file
    )
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 COMPREHENSIVE VISUALIZATION SUMMARY")
    print("=" * 70)
    
    total_listings = len(listings_gdf)
    total_buildings = len(buildings_gdf)
    
    if matches:
        direct_matches = sum(1 for m in matches if m['match_type'] == 'direct')
        buffer_matches = sum(1 for m in matches if m['match_type'] == 'buffer')
        no_matches = sum(1 for m in matches if m['match_type'] == 'no_match')
        match_rate = ((direct_matches + buffer_matches) / len(matches)) * 100
        
        print(f"📈 Listings: {total_listings:,}")
        print(f"🏢 Related Buildings: {total_buildings:,}")
        print(f"🎯 Overall Match Rate: {match_rate:.1f}%")
        print(f"   ✅ Direct Matches: {direct_matches} ({direct_matches/len(matches)*100:.1f}%)")
        print(f"   🟡 Buffer Matches: {buffer_matches} ({buffer_matches/len(matches)*100:.1f}%)")
        print(f"   ❌ No Matches: {no_matches} ({no_matches/len(matches)*100:.1f}%)")
    
    print(f"\n🗺️  Visualization: {visualization_path}")
    print(f"📊 Data Summary: {visualization_path.replace('.html', '.json')}")
    
    print(f"\n🎯 KEY FEATURES:")
    print(f"   ✅ Comprehensive view of ALL listings in Helsinki")
    print(f"   ✅ Only buildings with listing relationships displayed")
    print(f"   ✅ Interactive clustering for performance optimization")
    print(f"   ✅ Color-coded buildings by listing activity level")
    print(f"   ✅ Detailed popups with pricing and building information")
    print(f"   ✅ Multiple map layers and legend for context")
    print(f"   ✅ Performance optimized for {total_listings:,} listings")
    
    print(f"\n✅ Comprehensive Listing Visualization - Completed Successfully")
    print(f"📂 Output saved to: output/visualization/")


if __name__ == "__main__":
    main()
