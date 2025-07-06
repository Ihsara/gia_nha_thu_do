# Documentation: `visualize_parcels.py`

This script generates an interactive map to visualize a random sample of Helsinki parcels from the database.

## Purpose

The purpose of this script is to provide a quick and easy way to visually inspect the parcel data that has been loaded into the database. The resulting interactive map allows you to pan, zoom, and hover over individual parcels to see their details.

## When to Use

You can use this script any time after you have run either the `prepare_geospatial_data.py` or `load_helsinki_data.py` script to load the parcel data into the `helsinki_07_palstansijaintitiedot` table.

## How to Run

Execute the script from the root of the project directory using the following command:

```sh
python visualize_parcels.py
```

The script will automatically open the generated HTML map in your default web browser.

### Example

```
(venv) G:\proj\oikotie> python visualize_parcels.py
2025-07-07 00:00:00 | INFO     | __main__:get_sample_polygons - Connecting to database...
2025-07-07 00:00:01 | SUCCESS  | __main__:get_sample_polygons - Successfully loaded and converted 10 sample polygons.
2025-07-07 00:00:01 | INFO     | __main__:visualize_interactive_map - Generating interactive map...
2025-07-07 00:00:02 | SUCCESS  | __main__:visualize_interactive_map - Interactive map saved to: output\helsinki_parcels_map.html
2025-07-07 00:00:02 | INFO     | __main__:visualize_interactive_map - Opening map in a new browser tab...
```
