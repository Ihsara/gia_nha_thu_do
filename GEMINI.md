# Gemini Project Configuration: Oikotie Scraper

This file provides instructions for the Gemini agent on how to work with this project.

## Project Overview

This project is a Python application designed to scrape housing data from Oikotie.fi. It features a resilient data pipeline with JSON fallbacks, soft deletes, and parallelized scraping. All data is stored in the `data/` directory.

## Key Commands

-   **Run the entire data pipeline:** `python run_workflow.py`
-   **Prepare geospatial data:** `python prepare_geospatial_data.py`
-   **Prepare topographic data:** `python prepare_topographic_data.py`
-   **Load Helsinki data:** `python load_helsinki_data.py`
-   **Visualize Helsinki parcels:** `python visualize_parcels.py`
-   **Visualize Helsinki buildings:** `python visualize_buildings.py`
-   **Visualize Helsinki layer:** `python visualize_helsinki_layer.py <table_name>`
-   **Run the Jupyter dashboard:** `jupyter lab notebooks/check_data.ipynb`
-   **Visualize Helsinki properties:** `jupyter lab notebooks/explore_open_data.ipynb`
-   **Inspect GML data:** `jupyter lab notebooks/inspect_gml_data.ipynb`
-   **Run tests:** `pytest`
-   **Run linter/formatter:** `ruff check . && ruff format .`
-   **Install/sync dependencies:** `uv sync --all-extras`

## Development Workflow

1.  The main entry point for data collection is `run_workflow.py`.
2.  To load and filter the large geospatial data into the database, run `python prepare_geospatial_data.py`. This is recommended for better performance in the visualization notebook.
3.  To process the topographic data, run `python prepare_topographic_data.py`.
4.  To load the Helsinki-specific GeoJSON files into the database, run `python load_helsinki_data.py`.
5.  To generate an interactive map of a sample of Helsinki parcels, run `python visualize_parcels.py`.
6.  To generate an interactive map of a sample of Helsinki buildings, run `python visualize_buildings.py`.
7.  To generate an interactive map of any Helsinki layer, run `python visualize_helsinki_layer.py <table_name>`.
8.  After the workflow completes, data can be analyzed in `notebooks/check_data.ipynb`.
9.  Helsinki properties can be visualized in `notebooks/explore_open_data.ipynb`. This notebook will first attempt to load pre-processed data from the database.
10. The GML data can be inspected in `notebooks/inspect_gml_data.ipynb`.
11. The database is located at `data/real_estate.duckdb`.
12. External data lookups (like road data) are currently disabled.
13. Configuration is managed in `config/config.json`.

## Key Components

-   `run_workflow.py`: The main entry point for the data pipeline.
-   `prepare_geospatial_data.py`: A script to process and load large geospatial data into the database, filtered for Helsinki.
-   `prepare_topographic_data.py`: A script to process the topographic data from the `L4134C.zip` file.
-   `load_helsinki_data.py`: A script to load Helsinki-specific GeoJSON files into the database.
-   `visualize_parcels.py`: A script to generate an interactive map of a sample of Helsinki parcels.
-   `visualize_buildings.py`: A script to generate an interactive map of a sample of Helsinki buildings.
-   `visualize_helsinki_layer.py`: A flexible script to visualize any Helsinki data layer from the database.
-   `oikotie/scraper.py`: Handles scraping data from Oikotie.fi and saving it to the database.
-   `oikotie/geolocation.py`: Handles parallel geocoding of addresses and postal codes.
-   `prepare_locations.py`: Executes the geocoding process.
-   `check_db_status.py`: Prints a status report of the database.
-   `docs/`: Project documentation.
    -   `scripts/`: Detailed documentation for the project's scripts.
-   `notebooks/`: Contains Jupyter Notebooks for data analysis and exploration.
    -   `check_data.ipynb`: For data visualization and quality checks.
    -   `explore_open_data.ipynb`: For visualizing Helsinki properties with a map background. It prioritizes loading data from the database for performance.
    -   `inspect_gml_data.ipynb`: For inspecting the GML data from the `L4134C.zip` file.
-   `config/`: Contains configuration files.
    -   `config.json`: The main configuration file for the scraper.
-   `data/`: (Ignored by git) Contains the DuckDB database and other data files.
-   `output/`: (Ignored by git) For generated reports (currently unused).
