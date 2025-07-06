# Documentation: `prepare_topographic_data.py`

This script processes a topographic map sheet from the National Land Survey of Finland, filters the data for a specific municipality (Helsinki), and loads the building footprint data into the project's DuckDB database.

## Purpose

The main goal of this script is to extract building data from a GML file and store it in a structured format in the database. This makes the building data readily available for analysis and visualization.

## When to Use

You should run this script if you need to work with the building footprint data from the `L4134C.zip` file. This is an optional step and is not required for the main real estate analysis.

## Setup

Before running this script, ensure the following files are present in the `data/open/` directory:

-   `L4134C.zip`
-   `TietoaKuntajaosta_2025_10k.zip`

## How to Run

Execute the script from the root of the project directory using the following command:

```sh
python prepare_topographic_data.py
```

### Example

```
(venv) G:\proj\oikotie> python prepare_topographic_data.py
2025-07-07 00:00:26 | INFO     | __main__:process_and_load_data - Starting to process topography data...
...
2025-07-07 00:02:02 | SUCCESS  | __main__:process_and_load_data - Successfully loaded 14565 buildings into 'helsinki_buildings'.
```
