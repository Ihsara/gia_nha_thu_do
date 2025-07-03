import marimo

__generated_with = "0.14.9"
app = marimo.App(width="full")


@app.cell
def _():
    # --- Cell 1: Imports and Setup ---
    import marimo as mo
    import duckdb
    import pandas as pd
    import json
    import numpy as np
    import re
    import time
    from pathlib import Path
    from geopy.geocoders import Nominatim
    import folium
    from scipy.spatial import Voronoi
    import branca.colormap as cm

    pd.set_option('display.max_rows', 100)
    geolocator = Nominatim(user_agent="oikotie_dashboard_voronoi/1.4")
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
            db_error = "Table 'listings' not found."
    except Exception as e:
        db_error = e

    return (
        Path, cm, con, db_connected, db_error, db_path, folium, geolocator,
        json, mo, np, pd, re, table_exists, time, Voronoi
    )


@app.cell
def _(db_connected, db_error, db_path, mo, table_exists):
    # --- Cell 2: Connection Status ---
    if not db_connected:
        return mo.md(f"## ❌ Database Connection Failed\nCould not connect to `{db_path}`.\n**Error:** `{db_error}`")
    elif not table_exists:
        return mo.md(f"## ⚠️ Table Not Found\nSuccessfully connected to `{db_path}`, but the `listings` table is missing. Please run the scraper first.")
    else:
        return mo.md(f"## ✅ Database Connected Successfully\nConnected to `{db_path}`.")


@app.cell
def _(con, db_connected, pd, re, table_exists):
    # --- Cell 3: Load and Process Data ---
    if db_connected and table_exists:
        df = con.execute("""
            SELECT 
                city, address, listing_type, price_eur, size_m2,
                (price_eur / NULLIF(size_m2, 0)) as price_eur_per_m2
            FROM listings 
            WHERE 
                city = 'Helsinki' AND address IS NOT NULL AND 
                price_eur IS NOT NULL AND size_m2 > 0
        """).fetchdf()

        from oikotie.utils import extract_postal_code

        df['postal_code'] = df['address'].apply(extract_postal_code)
        df.dropna(subset=['postal_code', 'listing_type', 'price_eur_per_m2'], inplace=True)
    else:
        df = pd.DataFrame()
    return df, extract_postal_code


@app.cell
def _(mo):
    # --- Cell 4: Dashboard Title ---
    return mo.md(r"""# Helsinki Real Estate Dashboard""")


@app.cell
def _(df, mo):
    # --- Cell 5: KPI Cards ---
    if not df.empty:
        total_listings = len(df)
        avg_price = df['price_eur'].mean()
        avg_price_per_m2 = df['price_eur_per_m2'].mean()
        median_price = df['price_eur'].median()

        return mo.ui.grid(
            [
                mo.stat(label="Total Listings", value=f"{total_listings:,}"),
                mo.stat(label="Avg. Price", value=f"€{avg_price:,.0f}"),
                mo.stat(label="Avg. Price / m²", value=f"€{avg_price_per_m2:,.0f}"),
                mo.stat(label="Median Price", value=f"€{median_price:,.0f}"),
            ]
        )
    else:
        return mo.md("### No data to display KPIs. Run the scraper.")


@app.cell
def _(mo):
    # --- Cell 6: Analysis by Postal Code and Housing Type ---
    return mo.md(r"""## Analysis by Postal Code and Housing Type
    This table shows the number of listings, average price, and average price per square meter
    for each postal code and housing type combination.
    """)


@app.cell
def _(df, mo):
    # --- Cell 7: Data Table ---
    if not df.empty:
        analysis_df = df.groupby(['postal_code', 'listing_type']).agg(
            num_listings=('price_eur', 'size'),
            avg_price_eur=('price_eur', 'mean'),
            avg_price_per_m2=('price_eur_per_m2', 'mean')
        ).reset_index()

        analysis_df.sort_values(by=['postal_code', 'num_listings'], ascending=[True, False], inplace=True)

        return mo.ui.table(
            analysis_df,
            pagination=True,
            page_size=10,
            label="Aggregated Listing Data"
        )
    return


@app.cell
def _(mo):
    # --- Cell 8: Map Title ---
    return mo.md(r"""## Postal Code Boundaries and Price Analysis (Voronoi)
    This map visualizes the average price per square meter (€/m²) for each postal code area in Helsinki.
    The boundaries are estimated using a Voronoi diagram based on the geographical center of each postal code.
    Darker colors indicate a higher average price per square meter.
    """)


@app.cell
def _(Path, cm, df, folium, geolocator, json, mo, np, time, Voronoi):
    # --- Cell 9: Voronoi Map ---
    CACHE_FILE = Path('postal_code_coords.json')
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r') as f:
            postal_code_coords = json.load(f)
    else:
        postal_code_coords = {}

    if not df.empty:
        unique_postal_codes = df['postal_code'].unique()
        new_codes_found = False
        # Create a status area for geocoding updates
        status = mo.output.replace(mo.md("Checking for new postal codes..."))
        for code in unique_postal_codes:
            if code not in postal_code_coords:
                if not new_codes_found: # First new code
                    status.append(mo.md("Geocoding new postal codes (this may take a moment)..."))
                new_codes_found = True
                status.append(f"Querying: {code}...")
                try:
                    location = geolocator.geocode(f"{code}, Helsinki, Finland")
                    if location:
                        postal_code_coords[code] = {"lat": location.latitude, "lon": location.longitude}
                    else:
                        status.append(f"⚠️ Could not find coordinates for {code}.")
                    time.sleep(1.1) # Respect Nominatim's usage policy
                except Exception as e:
                    status.append(f"❌ Error geocoding {code}: {e}")

        if new_codes_found:
            with open(CACHE_FILE, 'w') as f:
                json.dump(postal_code_coords, f, indent=2)
            status.append("✅ Cache updated.")
        else:
            status.replace(mo.md("All postal codes are cached."))

        map_df = df.groupby('postal_code').agg(
            avg_price_per_m2=('price_eur_per_m2', 'mean'),
            num_listings=('price_eur', 'size')
        ).reset_index()

        map_df['lat'] = map_df['postal_code'].apply(lambda c: postal_code_coords.get(c, {}).get('lat'))
        map_df['lon'] = map_df['postal_code'].apply(lambda c: postal_code_coords.get(c, {}).get('lon'))
        map_df.dropna(subset=['lat', 'lon'], inplace=True)

        points = map_df[['lat', 'lon']].values
        
        if len(points) > 3:
            points_center = points.mean(axis=0)
            bounding_box = np.array([
                [points_center[0] - 1, points_center[1] - 1], [points_center[0] - 1, points_center[1] + 1],
                [points_center[0] + 1, points_center[1] + 1], [points_center[0] + 1, points_center[1] - 1]
            ])
            all_points = np.vstack([points, bounding_box])
            vor = Voronoi(all_points)

            m = folium.Map(location=[60.1699, 24.9384], zoom_start=11)

            min_price = map_df['avg_price_per_m2'].min()
            max_price = map_df['avg_price_per_m2'].max()
            colormap = cm.LinearColormap(
                colors=['#ffffcc', '#a1dab4', '#41b6c4', '#2c7fb8', '#253494'],
                index=np.linspace(min_price, max_price, 5), vmin=min_price, vmax=max_price
            )
            colormap.caption = 'Average Price per m² (€)'

            for i, region_index in enumerate(vor.point_region[:len(points)]):
                region = vor.regions[region_index]
                if -1 not in region:
                    polygon = [vor.vertices[j] for j in region]
                    row = map_df.iloc[i]
                    price = row['avg_price_per_m2']
                    
                    folium.Polygon(
                        locations=polygon, color='black', weight=1, fill_color=colormap(price),
                        fill_opacity=0.7,
                        tooltip=f"<b>Postal Code: {row['postal_code']}</b><br>"
                                f"Avg. Price/m²: €{price:,.0f}<br>"
                                f"Listings: {row['num_listings']}"
                    ).add_to(m)
            
            m.add_child(colormap)
            return m, status
        else:
            return mo.md("### Not enough data points to generate a Voronoi map (need at least 4)."), status
    else:
        return mo.md("### No data available to generate map.")


if __name__ == "__main__":
    app.run()