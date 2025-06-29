import marimo

__generated_with = "0.7.1"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import duckdb
    import pandas as pd
    import json
    import numpy as np
    import re
    import time
    from geopy.geocoders import Nominatim
    import folium  # <-- Import the new library
    
    # Configure pandas for better display
    pd.set_option('display.max_rows', 50)
    pd.set_option('display.max_columns', 50)
    
    # --- Geocoder Setup ---
    geolocator = Nominatim(user_agent="oikotie_marimo_dashboard/1.1")
    
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

    return con, db_connected, db_path, mo, pd, table_exists, db_error, np, json, re, time, geolocator, folium


@app.cell
def __(db_connected, db_error, db_path, mo, table_exists):
    if not db_connected:
        mo.md(f"""
            ## ❌ Database Connection Failed
            Could not connect to the database at `{db_path}`.
            
            **Error:** `{db_error}`
        """)
    elif not table_exists:
        mo.md(f"""
            ## ⚠️ Table Not Found
            Successfully connected, but the `listings` table does not exist. Please run the scraper.
        """)
    else:
        mo.md(f"## ✅ Database Connected Successfully\nConnected to `{db_path}`.")
    return


@app.cell
def __(con, db_connected, mo, pd, table_exists):
    mo.md("## 1. First 10 Scraped Listings")
    if db_connected and table_exists:
        df_first_10 = con.execute("""
            SELECT city, title, price_eur, size_m2, year_built, url
            FROM listings LIMIT 10
        """).fetchdf()
        mo.ui.table(df_first_10, page_size=10)
    else:
        mo.md("Database not ready.")
    return


@app.cell
def __(con, db_connected, mo, pd, table_exists):
    mo.md("## 2. Top 10 Most Expensive Listings (Helsinki)")
    if db_connected and table_exists:
        df_expensive = con.execute("""
            SELECT title, price_eur, size_m2, rooms, year_built, overview
            FROM listings WHERE city = 'Helsinki'
            ORDER BY price_eur DESC NULLS LAST LIMIT 10;
        """).fetchdf()
        mo.ui.table(df_expensive, page_size=10)
    else:
        mo.md("Database not ready.")
    return


@app.cell
def __(con, db_connected, folium, geolocator, mo, pd, table_exists, time):
    mo.md("## 3. Map of Random Listings with Real Coordinates")
    
    geocode_cache = {}
    def geocode_address(address):
        if address in geocode_cache:
            return geocode_cache[address]
        try:
            time.sleep(1.1)
            location = geolocator.geocode(address)
            geocode_cache[address] = location
            return location
        except Exception as e:
            mo.md(f"**Error geocoding `{address}`:** {e}")
            return None

    if db_connected and table_exists:
        df_map = con.execute("""
            SELECT title, address, price_eur FROM listings
            WHERE address IS NOT NULL AND city = 'Helsinki'
            USING SAMPLE 10;
        """).fetchdf()

        if not df_map.empty:
            mo.md("Geocoding addresses... (This will take ~1 second per address)")
            
            df_map['location_data'] = df_map['address'].apply(geocode_address)
            df_map.dropna(subset=['location_data'], inplace=True)
            
            df_map['latitude'] = df_map['location_data'].apply(lambda loc: loc.latitude)
            df_map['longitude'] = df_map['location_data'].apply(lambda loc: loc.longitude)
            
            mo.md(f"Successfully geocoded and mapped **{len(df_map)}** addresses.")
            
            if not df_map.empty:
                # Create a Folium map centered on the mean location of the points
                map_center = [df_map['latitude'].mean(), df_map['longitude'].mean()]
                my_map = folium.Map(location=map_center, zoom_start=12)

                # Add a marker for each listing
                for _, row in df_map.iterrows():
                    popup_html = f"<b>{row['title']}</b><br>Price: {row['price_eur']:,.0f} €"
                    folium.Marker(
                        location=[row['latitude'], row['longitude']],
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=row['title'],
                        icon=folium.Icon(color='red', icon='home')
                    ).add_to(my_map)

                # This is the last expression, ensuring the map is rendered by Marimo
                my_map
            else:
                mo.md("Could not geocode any of the selected addresses.")
        else:
            mo.md("No listings with addresses found to display on the map.")
    else:
        mo.md("Database not ready.")
    return geocode_address, geocode_cache, my_map


if __name__ == "__main__":
    app.run()