# Documentation: `visualize_helsinki_layer.py`

This script provides a flexible way to generate an interactive map for any of the Helsinki-specific data layers that have been loaded into the database.

## Purpose

The main goal of this script is to allow for easy, on-the-fly visualization of different geospatial datasets without needing to create a separate script for each one. You can specify which layer you want to see, and the script will generate an appropriate interactive map.

## When to Use

You can use this script any time after you have run the `load_helsinki_data.py` script to load the Helsinki-specific GeoJSON files into the database. It is a powerful tool for quickly exploring any of the `helsinki_*` tables.

## How to Run

Execute the script from the root of the project directory, providing the name of the table you want to visualize as a command-line argument.

```sh
python visualize_helsinki_layer.py <table_name>
```

### Example

To visualize the property boundary data, you would run:

```sh
python visualize_helsinki_layer.py helsinki_02_kiinteistorajansijaintitiedot
```

This will generate an interactive HTML map named `output/map_helsinki_02_kiinteistorajansijaintitiedot.html` and open it in your browser.

```
(venv) G:\proj\oikotie> python visualize_helsinki_layer.py helsinki_02_kiinteistorajansijaintitiedot
2025-07-07 00:18:17 | INFO     | __main__:get_sample_data - Connecting to database...
2025-07-07 00:18:17 | SUCCESS  | __main__:get_sample_data - Successfully loaded and converted 100 sample features from 'helsinki_02_kiinteistorajansijaintitiedot'.
2025-07-07 00:18:17 | INFO     | __main__:visualize_interactive_map - Generating interactive map...
2025-07-07 00:18:18 | SUCCESS  | __main__:visualize_interactive_map - Interactive map saved to: output\map_helsinki_02_kiinteistorajansijaintitiedot.html
2025-07-07 00:18:18 | INFO     | __main__:visualize_interactive_map - Opening map in a new browser tab...
```
