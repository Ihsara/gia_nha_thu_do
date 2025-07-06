# Documentation: `visualize_buildings.py`

This script generates an interactive map to visualize a random sample of Helsinki buildings from the database.

## Purpose

The purpose of this script is to provide a quick and easy way to visually inspect the building data that has been loaded into the database. The resulting interactive map allows you to pan, zoom, and hover over individual buildings to see their details.

## When to Use

You can use this script any time after you have run the `prepare_topographic_data.py` script to load the building data into the `helsinki_buildings` table.

## How to Run

Execute the script from the root of the project directory using the following command:

```sh
python visualize_buildings.py
```

The script will automatically open the generated HTML map in your default web browser.

### Example

```
(venv) G:\proj\oikotie> python visualize_buildings.py
2025-07-07 00:00:00 | INFO     | __main__:get_sample_polygons - Connecting to database...
2025-07-07 00:00:01 | SUCCESS  | __main__:get_sample_polygons - Successfully loaded and converted 100 sample building polygons.
2025-07-07 00:00:01 | INFO     | __main__:visualize_interactive_map - Generating interactive map...
2025-07-07 00:00:02 | SUCCESS  | __main__:visualize_interactive_map - Interactive map saved to: output\helsinki_buildings_map.html
2025-07-07 00:00:02 | INFO     | __main__:visualize_interactive_map - Opening map in a new browser tab...
```
