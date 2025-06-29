import marimo

__generated_with = "0.7.1"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    import duckdb
    import pandas as pd
    import json
    import re
    import time
    from pathlib import Path
    from geopy.geocoders import Nominatim
    import folium
    from folium.plugins import HeatMap

    # --- Initial Setup ---
    # Configure pandas for better display
    pd.set_option('display.max_rows', 100)
    pd.set_option('display.max_columns', 50)
    
    # --- Database Connection ---
    db_path = 'output/real_estate.duckdb'
    db_connected = False
    table_exists = False
    con = None
    db_error = None
    
    try:
        con = duckdb.connect(database=str(db_path), read_only=True)
        db_connected = True
        try:
            con.execute("SELECT 1 FROM listings LIMIT 1;")
            table_exists = True
        except duckdb.CatalogException:
            table_exists = False
    except Exception as e:
        db_error = e
    
    # --- Geocoder Setup ---
    geolocator = Nominatim(user_agent="oikotie_dashboard_v2/1.0")
    
    # --- Helper function to extract postal code ---
    def extract_postal_code(address):
        if not isinstance(address, str):
            return None
        match = re.search(r'\b(\d{5})\b', address)
        return match.group(1) if match else None

    return (
        con, db_connected, db_path, mo, pd, table_exists, db_error, json,
        re, time, geolocator, folium, HeatMap, Path, extract_postal_code
    )


@app.cell
def __(con, db_connected, mo, pd, table_exists, extract_postal_code):
    # --- Cell 2: Load and Process Data ---
    mo.md("### Data Loading and Pre-processing")
    if db_connected and table_exists:
        # Load the entire relevant dataset into pandas
        df = con.execute("""
            SELECT 
                city, 
                address, 
                listing_type, 
                price_eur 
            FROM listings 
            WHERE city = 'Helsinki' AND address IS NOT NULL AND price_eur IS NOT NULL
        """).fetchdf()
        
        # Create the postal_code column
        df['postal_code'] = df['address'].apply(extract_postal_code)
        
        # Clean data by removing rows where postal code or listing type is missing
        df.dropna(subset=['postal_code', 'listing_type'], inplace=True)
        
        # Display a success message
        mo.md(f"Successfully loaded and processed **{len(df)}** listings from Helsinki.")
    else:
        df = pd.DataFrame() # Create empty dataframe if DB is not ready
        mo.md("Database not ready. Cannot load data.")
    return df,


@app.cell
def __(df, mo):
    # --- Cell 3: Dashboard Header with Key Stats ---
    total_listings = len(df)
    unique_postal_codes = df['postal_code'].nunique()
    
    mo.md(
        f"""
        # Helsinki Real Estate Dashboard
        ---
        """
    )
    
    # Display stats in a horizontal layout
    mo.hstack([
        mo.stat(value=f"{total_listings:,}", label="Total Listings Analyzed"),
        mo.stat(value=unique_postal_codes, label="Unique Postal Codes")
    ], justify='start')
    return total_listings, unique_postal_codes


@app.cell
def __(df, mo):
    # --- Cell 4: Postal Code Analysis Table ---
    mo.md("## Analysis by Postal Code and Housing Type")
    if not df.empty:
        # Group by postal code and listing type, then aggregate
        analysis_df = df.groupby(['postal_code', 'listing_type']).agg(
            listing_count=('price_eur', 'count'),
            average_price_eur=('price_eur', 'mean')
        ).reset_index()

        # Format for better readability
        analysis_df['average_price_eur'] = analysis_df['average_price_eur'].round(0).astype(int)
        analysis_df = analysis_df.sort_values(by=['postal_code', 'listing_count'], ascending=[True, False])
        
        mo.ui.table(analysis_df, page_size=15, label="Listings and Average Price")
    else:
        mo.md("No data available to create analysis table.")
    return analysis_df,


@app.cell
def __(
    Path, df, folium, geolocator, HeatMap, json, mo, time
):
    # --- Cell 5: Heatmap Visualization ---
    mo.md("## Listing Density Heatmap by Postal Code")

    # --- Geocoding with Caching ---
    CACHE_FILE = Path("postal_code_coords.json")
    
    def load_geocode_cache():
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_geocode_cache(cache):
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)

    def get_coords_for_postal_code(postal_code, cache):
        if postal_code in cache:
            return cache[postal_code]
        
        try:
            # Respect Nominatim's rate limit of 1 request/sec
            time.sleep(1.1) 
            # Query for the postal code in Finland for better accuracy
            location = geolocator.geocode(f"{postal_code}, Finland")
            if location:
                coords = {'lat': location.latitude, 'lon': location.longitude}
                cache[postal_code] = coords
                return coords
            return None
        except Exception as e:
            logger.error(f"Error geocoding {postal_code}: {e}")
            return None

    if not df.empty:
        # Get listing counts per postal code
        postal_code_counts = df['postal_code'].value_counts().reset_index()
        postal_code_counts.columns = ['postal_code', 'count']
        
        # Geocode all unique postal codes
        geocode_cache = load_geocode_cache()
        
        mo.md(f"Geocoding {postal_code_counts['postal_code'].nunique()} postal codes... (This may take a while for new codes)")
        
        coordinates = [get_coords_for_postal_code(pc, geocode_cache) for pc in postal_code_counts['postal_code']]
        
        save_geocode_cache(geocode_cache) # Save any new results
        
        postal_code_counts['coords'] = coordinates
        postal_code_counts.dropna(subset=['coords'], inplace=True)

        # Prepare data for the heatmap: [latitude, longitude, weight]
        heat_data = [
            [row['coords']['lat'], row['coords']['lon'], row['count']]
            for _, row in postal_code_counts.iterrows()
        ]
        
        if heat_data:
            # Create the base map centered on Helsinki
            map_helsinki = folium.Map(location=[60.1699, 24.9384], zoom_start=11)
            
            # Add the heatmap layer
            HeatMap(heat_data, radius=15, blur=10).add_to(map_helsinki)
            
            # This is the last expression, ensuring the map is rendered
            map_helsinki
        else:
            mo.md("Could not create heatmap data. No coordinates found.")
    else:
        mo.md("No data available to create heatmap.")
    return (
        CACHE_FILE,
        geocode_address,
        geocode_cache,
        heat_data,
        load_geocode_cache,
        map_helsinki,
        postal_code_counts,
        save_geocode_cache,
    )


if __name__ == "__main__":
    app.run()