# Documentation: `prepare_geospatial_data.py`

This script is designed to process the large, nationwide geospatial data file from the National Land Survey of Finland, filter it for a specific municipality (Helsinki), and load the relevant data into the project's DuckDB database.

## Purpose

The primary goal of this script is to create a smaller, more manageable subset of the property data that is focused on the area of interest (Helsinki). This significantly improves the performance of any subsequent analysis or visualization that uses this data.

## When to Use

You should run this script **once** as part of the initial project setup, or whenever the source `kiinteistorekisterikartta.gpkg` file is updated. Running this script is highly recommended before using the `notebooks/explore_open_data.ipynb` notebook for the first time to ensure a fast and smooth experience.

## Setup

Before running this script, ensure the following files are present in the `data/open/` directory:

-   `kiinteistorekisterikartta.gpkg`
-   `TietoaKuntajaosta_2025_10k.zip`

## How to Run

Execute the script from the root of the project directory using the following command:

```sh
python prepare_geospatial_data.py
```

### Example

```
(venv) G:\proj\oikotie> python prepare_geospatial_data.py
2025-07-07 00:00:00 | INFO     | __main__:get_helsinki_boundary - Extracting municipal boundaries...
2025-07-07 00:00:01 | SUCCESS  | __main__:get_helsinki_boundary - Successfully extracted the boundary for Helsinki.
2025-07-07 00:00:01 | INFO     | __main__:process_and_load_data - Starting to process properties...
...
2025-07-07 00:02:02 | SUCCESS  | __main__:process_and_load_data - Successfully loaded 151725 properties into 'helsinki_properties'.
```
