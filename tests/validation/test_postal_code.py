#!/usr/bin/env python3
"""
Part 2: Single Postal Code Validation
Purpose: Medium-scale validation with representative dataset

Requirements:
- Pass Part 1 validation first
- Select one Helsinki postal code (e.g., 00100, 00120, 00140)
- Process all listings from that postal code (~100-300 listings)
- Generate postal code-specific visualization
- Validate enhanced polygon rendering and interactivity
- Must achieve >98% match rate before proceeding

Success Criteria: >98% match rate with postal code dataset
"""

import os
import sys
import time
import subprocess
from pathlib import Path

import duckdb
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from concurrent.futures import ProcessPoolExecutor
from collections import Counter


def run_mandatory_bug_test():
    """Run mandatory bug prevention test before expensive operations."""
    print("=" * 60)
    print("MANDATORY: Running Bug Prevention Test")
    print("=" * 60)
    
    try:
        result = subprocess.run([
            sys.executable, 'simple_bug_test.py'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print("❌ CRITICAL: Bug prevention test FAILED!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            print("\n🚫 STOPPING: Cannot proceed with expensive operations!")
            sys.exit(1)
        else:
            print("✅ Bug prevention test PASSED!")
            print("✅ Safe to proceed with validation")
            return True
            
    except subprocess.TimeoutExpired:
        print("❌ CRITICAL: Bug prevention test timed out!")
        sys.exit(1)
    except Exception as e:
        print(f"❌ CRITICAL: Error running bug prevention test: {e}")
        sys.exit(1)


def check_part1_prerequisite():
    """Check if Part 1 validation has been completed successfully."""
    print("\n🔗 Checking Part 1 Prerequisite...")
    
    part1_output = Path("validation_10_listings.html")
    if not part1_output.exists():
        print("❌ Part 1 validation output not found!")
        print("🚫 Must run Part 1 first: uv run python validate_10_listings.py")
        sys.exit(1)
    else:
        print("✅ Part 1 validation output found")
        print("✅ Proceeding with Part 2 validation")


def load_database_connection():
    """Load database connection and verify data availability."""
    print("\n📊 Loading Database Connection...")
    
    try:
        conn = duckdb.connect('data/real_estate.duckdb')
        
        # Check listings table
        listings_count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        print(f"✅ Found {listings_count:,} total listings in database")
        
        # Get Helsinki listings for Python-based postal code extraction
        helsinki_query = """
        SELECT l.address
        FROM listings l
        JOIN address_locations al ON l.address = al.address
        WHERE al.lat IS NOT NULL 
        AND al.lon IS NOT NULL
        AND l.city = 'Helsinki'
        """
        
        addresses_df = conn.execute(helsinki_query).df()
        print(f"✅ Found {len(addresses_df):,} Helsinki listings with coordinates")
        
        # Extract postal codes using Python regex
        import re
        postal_counts = {}
        
        for address in addresses_df['address']:
            # Finnish postal codes are 5 digits starting with 0
            patterns = [
                r'\b(0\d{4})\b',
                r'\n(0\d{4})\n', 
                r'(0\d{4})\n',
                r'(\d{5})'  # Fallback pattern
            ]
            
            postal_code = None
            for pattern in patterns:
                match = re.search(pattern, str(address), re.MULTILINE)
                if match:
                    postal_code = match.group(1)
                    if postal_code.startswith('0'):  # Valid Finnish postal code
                        break
            
            if postal_code and postal_code.startswith('0'):
                postal_counts[postal_code] = postal_counts.get(postal_code, 0) + 1
        
        # Convert to DataFrame
        if postal_counts:
            postal_counts_list = [{'postal_code': code, 'count': count} 
                                 for code, count in postal_counts.items()]
            postal_counts_df = pd.DataFrame(postal_counts_list).sort_values('count', ascending=False)
            
            print(f"✅ Found {len(postal_counts_df)} unique postal codes:")
            for _, row in postal_counts_df.head(10).iterrows():
                print(f"   📮 {row['postal_code']}: {row['count']} listings")
        else:
            # Create a minimal fallback using '00100'
            print("⚠️ No postal codes found, using fallback")
            postal_counts_df = pd.DataFrame([{'postal_code': '00100', 'count': 50}])
        
        return conn, postal_counts_df
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)


def load_polygon_cache(conn):
    """Load cached polygon data from database (critical for performance)."""
    print("\n🗺️  Loading Polygon Cache from Database...")
    
    try:
        # Load polygons from database polygon_cache table
        query = """
        SELECT polygon_wkt as wkt_geometry
        FROM polygon_cache
        WHERE polygon_wkt IS NOT NULL
        """
        
        polygons_df = conn.execute(query).df()
        print(f"✅ Loaded {len(polygons_df):,} cached polygons from database")
        
        # Convert WKT to GeoDataFrame
        from shapely import wkt
        polygons_df['geometry'] = polygons_df['wkt_geometry'].apply(wkt.loads)
        polygons_gdf = gpd.GeoDataFrame(polygons_df, geometry='geometry', crs='EPSG:4326')
        
        print("✅ Polygons already in EPSG:4326 (breakthrough coordinate system)")
        print(f"✅ {len(polygons_gdf):,} polygons ready for spatial join")
            
        return polygons_gdf
        
    except Exception as e:
        print(f"❌ Failed to load polygon cache from database: {e}")
        sys.exit(1)


def select_postal_code_listings(conn, postal_counts):
    """Select a representative postal code and its listings."""
    print(f"\n📮 Selecting Postal Code for Validation...")
    
    try:
        # Select a postal code with reasonable number of listings (100-300)
        suitable_postal_codes = postal_counts[
            (postal_counts['count'] >= 50) & (postal_counts['count'] <= 400)
        ].head(3)
        
        if suitable_postal_codes.empty:
            # Fallback to any postal code with listings
            selected_postal = postal_counts.iloc[0]['postal_code']
            selected_count = postal_counts.iloc[0]['count']
        else:
            selected_postal = suitable_postal_codes.iloc[0]['postal_code']
            selected_count = suitable_postal_codes.iloc[0]['count']
        
        print(f"📮 Selected Postal Code: {selected_postal}")
        print(f"📊 Expected Listings: {selected_count}")
        
        # Get all Helsinki listings and filter by postal code using Python
        query = """
        SELECT 
            l.url as id, l.address, al.lat as latitude, al.lon as longitude, 
            l.price_eur as price, l.rooms, l.size_m2, l.listing_type, l.city
        FROM listings l
        JOIN address_locations al ON l.address = al.address
        WHERE al.lat IS NOT NULL 
        AND al.lon IS NOT NULL
        AND l.city = 'Helsinki'
        ORDER BY l.address
        """
        
        all_listings_df = conn.execute(query).df()
        print(f"✅ Retrieved {len(all_listings_df)} total Helsinki listings")
        
        # Filter listings by postal code using Python regex
        import re
        selected_listings = []
        
        for _, row in all_listings_df.iterrows():
            address = str(row['address'])
            
            # Extract postal code using same patterns as before
            patterns = [
                r'\b(0\d{4})\b',
                r'\n(0\d{4})\n', 
                r'(0\d{4})\n',
                r'(\d{5})'
            ]
            
            extracted_postal = None
            for pattern in patterns:
                match = re.search(pattern, address, re.MULTILINE)
                if match:
                    postal_code = match.group(1)
                    if postal_code.startswith('0'):  # Valid Finnish postal code
                        extracted_postal = postal_code
                        break
            
            # If postal code matches our selected one, include the listing
            if extracted_postal == selected_postal:
                listing_dict = row.to_dict()
                listing_dict['postal_code'] = extracted_postal
                selected_listings.append(listing_dict)
        
        print(f"✅ Filtered to {len(selected_listings)} listings for postal code {selected_postal}")
        
        if len(selected_listings) == 0:
            raise ValueError(f"No valid listings found for postal code {selected_postal}")
            
        return selected_listings, selected_postal
        
    except Exception as e:
        print(f"❌ Failed to select postal code listings: {e}")
        sys.exit(1)


def process_chunk_spatial_join(chunk_data):
    """Process a chunk of listings using breakthrough spatial join logic."""
    listings_chunk, polygons_gdf_serialized = chunk_data
    
    # Reconstruct polygons_gdf from serialized data
    polygons_gdf = gpd.GeoDataFrame.from_features(polygons_gdf_serialized, crs='EPSG:4326')
    
    matches = []
    match_count = 0
    
    for listing in listings_chunk:
        try:
            # BREAKTHROUGH: Create point directly from coordinates (already EPSG:4326)
            point = Point(listing['longitude'], listing['latitude'])
            
            # Find polygon containing point (breakthrough spatial join logic)
            containing_polygons = polygons_gdf[polygons_gdf.contains(point)]
            
            if not containing_polygons.empty:
                # Direct match found
                polygon_data = containing_polygons.iloc[0]
                match_count += 1
                match_type = "direct"
                polygon_geometry = polygon_data.geometry
            else:
                # Apply buffer search (100m buffer)
                buffered_point = point.buffer(0.001)  # ~100m buffer
                intersecting_polygons = polygons_gdf[polygons_gdf.intersects(buffered_point)]
                
                if not intersecting_polygons.empty:
                    polygon_data = intersecting_polygons.iloc[0]
                    match_count += 1
                    match_type = "buffered"
                    polygon_geometry = polygon_data.geometry
                else:
                    polygon_data = None
                    match_type = "no_match"
                    polygon_geometry = None
            
            matches.append({
                'listing_id': listing['id'],
                'address': listing['address'],
                'coordinates': (listing['latitude'], listing['longitude']),
                'polygon_matched': polygon_data is not None,
                'match_type': match_type,
                'polygon_geometry': polygon_geometry,
                'listing_data': listing
            })
            
        except Exception as e:
            matches.append({
                'listing_id': listing['id'],
                'address': listing['address'],
                'coordinates': (listing['latitude'], listing['longitude']),
                'polygon_matched': False,
                'match_type': 'error',
                'polygon_geometry': None,
                'listing_data': listing
            })
    
    return matches, match_count


def perform_parallel_spatial_join(listings, polygons_gdf, max_workers=4):
    """
    Perform parallel spatial join validation for medium-scale dataset.
    Uses breakthrough parallel processing logic.
    """
    print(f"\n🔍 Performing Parallel Spatial Join Validation...")
    print(f"📍 Processing {len(listings)} listings against {len(polygons_gdf):,} polygons")
    print(f"⚡ Using {max_workers} workers for parallel processing")
    
    # Serialize polygons for multiprocessing
    polygons_serialized = polygons_gdf.__geo_interface__['features']
    
    # Split listings into chunks
    chunk_size = max(1, len(listings) // max_workers)
    chunks = [listings[i:i + chunk_size] for i in range(0, len(listings), chunk_size)]
    
    print(f"📦 Split into {len(chunks)} chunks of ~{chunk_size} listings each")
    
    all_matches = []
    total_match_count = 0
    
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all chunks
        futures = []
        for i, chunk in enumerate(chunks):
            chunk_data = (chunk, polygons_serialized)
            future = executor.submit(process_chunk_spatial_join, chunk_data)
            futures.append((i, future))
        
        # Collect results
        for i, future in futures:
            try:
                matches, match_count = future.result(timeout=300)  # 5 minute timeout per chunk
                all_matches.extend(matches)
                total_match_count += match_count
                
                chunk_match_rate = (match_count / len(matches)) * 100 if matches else 0
                print(f"  ✅ Chunk {i+1}/{len(chunks)}: {match_count}/{len(matches)} matches ({chunk_match_rate:.1f}%)")
                
            except Exception as e:
                print(f"❌ Chunk {i+1} failed: {e}")
                # Add error entries for this chunk
                chunk_size = len(chunks[i])
                for listing in chunks[i]:
                    all_matches.append({
                        'listing_id': listing['id'],
                        'address': listing['address'],
                        'coordinates': (listing['latitude'], listing['longitude']),
                        'polygon_matched': False,
                        'match_type': 'chunk_error',
                        'polygon_geometry': None,
                        'listing_data': listing
                    })
    
    processing_time = time.time() - start_time
    total_match_rate = (total_match_count / len(all_matches)) * 100 if all_matches else 0
    
    print(f"\n📊 Parallel Spatial Join Results:")
    print(f"   ✅ Total Matches: {total_match_count}/{len(all_matches)}")
    print(f"   📈 Overall Match Rate: {total_match_rate:.1f}%")
    print(f"   ⏱️  Processing Time: {processing_time:.1f} seconds")
    print(f"   🚀 Speed: {len(all_matches)/processing_time:.1f} listings/second")
    
    return all_matches, total_match_rate


def calculate_density_colors(matches):
    """Calculate density-based colors for enhanced visualization."""
    print(f"\n🎨 Calculating Density Colors...")
    
    # Count listings per polygon
    polygon_counts = Counter()
    polygon_geometries = {}
    
    for match in matches:
        if match['polygon_matched'] and match['polygon_geometry'] is not None:
            # Use geometry as key (convert to WKT for hashing)
            geom_key = match['polygon_geometry'].wkt
            polygon_counts[geom_key] += 1
            polygon_geometries[geom_key] = match['polygon_geometry']
    
    if not polygon_counts:
        print("⚠️  No matched polygons found for density calculation")
        return {}
    
    # Calculate color mapping based on density
    max_count = max(polygon_counts.values())
    min_count = min(polygon_counts.values())
    
    print(f"   📊 Polygon Density Range: {min_count} - {max_count} listings per polygon")
    
    density_colors = {}
    for geom_wkt, count in polygon_counts.items():
        if max_count == min_count:
            # All polygons have same density
            color_intensity = 0.5
        else:
            color_intensity = (count - min_count) / (max_count - min_count)
        
        # Enhanced color mapping: Green (low) → Yellow (medium) → Red (high)
        if color_intensity <= 0.33:
            color = f'rgba(0, 255, 0, {0.3 + color_intensity * 0.4})'  # Green
        elif color_intensity <= 0.66:
            color = f'rgba(255, 255, 0, {0.3 + color_intensity * 0.4})'  # Yellow
        else:
            color = f'rgba(255, 0, 0, {0.3 + color_intensity * 0.4})'  # Red
        
        density_colors[geom_wkt] = {
            'color': color,
            'count': count,
            'intensity': color_intensity
        }
    
    print(f"   ✅ Generated density colors for {len(density_colors)} polygons")
    return density_colors


def create_enhanced_visualization(matches, postal_code, density_colors, output_filename=None):
    """Create enhanced interactive visualization with density colors."""
    if output_filename is None:
        output_filename = f"validation_postal_{postal_code}.html"
    
    print(f"\n🗺️  Creating Enhanced Visualization...")
    
    try:
        # Calculate center point from matched listings
        valid_coords = [match['coordinates'] for match in matches if match['polygon_matched']]
        if valid_coords:
            center_lat = sum(coord[0] for coord in valid_coords) / len(valid_coords)
            center_lon = sum(coord[1] for coord in valid_coords) / len(valid_coords)
        else:
            # Default to Helsinki center
            center_lat, center_lon = 60.1699, 24.9384
        
        # Create map with enhanced styling
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=13,
            tiles='OpenStreetMap'
        )
        
        # Add enhanced polygons with density colors
        matched_count = 0
        unmatched_count = 0
        
        # Track processed polygons to avoid duplicates
        processed_polygons = set()
        
        for match in matches:
            lat, lon = match['coordinates']
            listing = match['listing_data']
            
            if match['polygon_matched'] and match['polygon_geometry'] is not None:
                geom_wkt = match['polygon_geometry'].wkt
                
                # Add polygon only once per unique geometry
                if geom_wkt not in processed_polygons:
                    processed_polygons.add(geom_wkt)
                    
                    polygon_coords = []
                    if match['polygon_geometry'].geom_type == 'Polygon':
                        coords = list(match['polygon_geometry'].exterior.coords)
                        polygon_coords = [[lat, lon] for lon, lat in coords]
                    elif match['polygon_geometry'].geom_type == 'MultiPolygon':
                        for poly in match['polygon_geometry'].geoms:
                            coords = list(poly.exterior.coords)
                            polygon_coords.extend([[lat, lon] for lon, lat in coords])
                    
                    if polygon_coords and geom_wkt in density_colors:
                        density_info = density_colors[geom_wkt]
                        color_value = density_info['color']
                        listing_count = density_info['count']
                        
                        # Enhanced polygon styling
                        folium.Polygon(
                            locations=polygon_coords,
                            color='darkblue',
                            weight=2,
                            fillColor=color_value,
                            fillOpacity=0.6,
                            popup=f"""
                            <b>Enhanced Polygon</b><br>
                            <b>Listings:</b> {listing_count}<br>
                            <b>Density:</b> {density_info['intensity']:.2f}<br>
                            <b>Postal Code:</b> {postal_code}
                            """
                        ).add_to(m)
                
                # Add listing marker
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color='darkgreen',
                    fillColor='lightgreen',
                    fillOpacity=0.8,
                    popup=f"""
                    <b>✅ MATCHED LISTING</b><br>
                    <b>Address:</b> {listing['address']}<br>
                    <b>Price:</b> €{listing['price']:,}<br>
                    <b>Rooms:</b> {listing.get('rooms', 'N/A')}<br>
                    <b>Size:</b> {listing.get('size_m2', 'N/A')} m²<br>
                    <b>Match Type:</b> {match['match_type']}<br>
                    <b>Postal Code:</b> {postal_code}
                    """
                ).add_to(m)
                
                matched_count += 1
            else:
                # Add unmatched listing marker
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color='darkred',
                    fillColor='red',
                    fillOpacity=0.8,
                    popup=f"""
                    <b>❌ UNMATCHED LISTING</b><br>
                    <b>Address:</b> {listing['address']}<br>
                    <b>Price:</b> €{listing['price']:,}<br>
                    <b>Rooms:</b> {listing.get('rooms', 'N/A')}<br>
                    <b>Size:</b> {listing.get('size_m2', 'N/A')} m²<br>
                    <b>Postal Code:</b> {postal_code}
                    """
                ).add_to(m)
                
                unmatched_count += 1
        
        # Enhanced legend with postal code info
        match_rate = (matched_count/(matched_count+unmatched_count)*100) if (matched_count+unmatched_count) > 0 else 0
        
        legend_html = f"""
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 250px; height: 120px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <b>Part 2: Postal Code {postal_code}</b><br>
        <i class="fa fa-polygon" style="color:blue"></i> Enhanced Polygons: {len(processed_polygons)}<br>
        <i class="fa fa-circle" style="color:green"></i> Matched: {matched_count}<br>
        <i class="fa fa-circle" style="color:red"></i> Unmatched: {unmatched_count}<br>
        <b>Match Rate: {match_rate:.1f}%</b><br>
        <small>Colors: Green(low) → Yellow(med) → Red(high density)</small>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Add postal code title
        title_html = f"""
        <div style="position: fixed; 
                    top: 10px; left: 50%; transform: translateX(-50%); 
                    background-color: rgba(255,255,255,0.8); border:1px solid grey; 
                    z-index:9999; font-size:16px; padding: 10px; text-align: center;">
        <b>Part 2: Enhanced Polygon Validation - Postal Code {postal_code}</b>
        </div>
        """
        m.get_root().html.add_child(folium.Element(title_html))
        
        # Save map
        output_path = Path(output_filename)
        m.save(str(output_path))
        
        print(f"✅ Enhanced visualization saved: {output_path.absolute()}")
        print(f"   📮 Postal Code: {postal_code}")
        print(f"   🗺️  Enhanced Polygons: {len(processed_polygons)}")
        print(f"   📊 Matched Listings: {matched_count}")
        print(f"   📊 Unmatched Listings: {unmatched_count}")
        print(f"   📈 Match Rate: {match_rate:.1f}%")
        
        return output_path, match_rate
        
    except Exception as e:
        print(f"❌ Failed to create enhanced visualization: {e}")
        return None, 0


def validate_success_criteria(match_rate, required_rate=98.0):
    """Validate success criteria for Part 2."""
    print(f"\n🎯 Validating Success Criteria...")
    print(f"   📊 Required Match Rate: ≥{required_rate}%")
    print(f"   📈 Achieved Match Rate: {match_rate:.1f}%")
    
    if match_rate >= required_rate:
        print(f"   ✅ SUCCESS: Part 2 validation PASSED!")
        print(f"   ✅ Enhanced polygon visualization validated")
        print(f"   ✅ Ready to proceed to Part 3 (Full Helsinki)")
        return True
    else:
        print(f"   ❌ FAILURE: Part 2 validation FAILED!")
        print(f"   ❌ Need {required_rate - match_rate:.1f}% improvement")
        print(f"   🔧 Review parallel processing and polygon enhancement")
        return False


def main():
    """Main validation workflow for Part 2: Single Postal Code."""
    start_time = time.time()
    
    print("🔍 PART 2: Single Postal Code Validation")
    print("=" * 60)
    print("Purpose: Medium-scale validation with representative dataset")
    print("Success Criteria: >98% match rate with postal code dataset")
    print("=" * 60)
    
    # Step 1: Mandatory bug prevention test
    run_mandatory_bug_test()
    
    # Step 2: Check Part 1 prerequisite
    check_part1_prerequisite()
    
    # Step 3: Load database and polygon data
    conn, postal_counts = load_database_connection()
    polygons_gdf = load_polygon_cache(conn)
    
    # Step 4: Select postal code and listings
    listings, postal_code = select_postal_code_listings(conn, postal_counts)
    
    # Step 5: Perform parallel spatial join validation
    matches, match_rate = perform_parallel_spatial_join(listings, polygons_gdf)
    
    # Step 6: Calculate density colors for enhanced visualization
    density_colors = calculate_density_colors(matches)
    
    # Step 7: Create enhanced visualization
    viz_path, final_match_rate = create_enhanced_visualization(matches, postal_code, density_colors)
    
    # Step 8: Validate success criteria
    success = validate_success_criteria(final_match_rate)
    
    # Summary
    total_time = time.time() - start_time
    print(f"\n📊 PART 2 VALIDATION SUMMARY")
    print("=" * 60)
    print(f"📮 Postal Code: {postal_code}")
    print(f"📊 Listings Processed: {len(listings)}")
    print(f"⏱️  Processing Time: {total_time:.1f} seconds")
    print(f"📈 Match Rate: {final_match_rate:.1f}%")
    print(f"🗺️  Enhanced Visualization: {viz_path}")
    print(f"🎯 Success: {'✅ PASSED' if success else '❌ FAILED'}")
    
    if success:
        print(f"\n🚀 Next Steps:")
        print(f"   1. Review enhanced visualization: {viz_path}")
        print(f"   2. Verify polygon density colors and interactivity")
        print(f"   3. Run Part 3: uv run python validate_full_helsinki.py")
        return 0
    else:
        print(f"\n🔧 Required Actions:")
        print(f"   1. Review parallel processing implementation")
        print(f"   2. Check enhanced polygon rendering")
        print(f"   3. Investigate density color calculation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
