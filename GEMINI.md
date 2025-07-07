# Gemini Project Configuration: Oikotie Scraper

This file provides instructions for the Gemini agent on how to work with this project.

## Project Overview

This project is a Python application designed to scrape housing data from Oikotie.fi. It features a resilient data pipeline with JSON fallbacks, soft deletes, and parallelized scraping. All data is stored in the `data/` directory.

## Key Commands

-   **Run the entire data pipeline:** `python -m oikotie.scripts.run_workflow`
-   **Prepare geospatial data:** `python -m oikotie.scripts.prepare.prepare_geospatial_data`
-   **Prepare topographic data:** `python -m oikotie.scripts.prepare.prepare_topographic_data`
-   **Load Helsinki data:** `python -m oikotie.scripts.prepare.load_helsinki_data`
-   **Visualize Helsinki parcels:** `python -m oikotie.scripts.visualize.visualize_parcels`
-   **Visualize Helsinki buildings:** `python -m oikotie.scripts.visualize.visualize_buildings`
-   **Visualize Helsinki layer:** `python -m oikotie.scripts.visualize.visualize_helsinki_layer <table_name>`
-   **Run the Jupyter dashboard:** `jupyter lab notebooks/check_data.ipynb`
-   **Visualize Helsinki properties:** `jupyter lab notebooks/explore_open_data.ipynb`
-   **Inspect GML data:** `jupyter lab notebooks/inspect_gml_data.ipynb`
-   **Run tests:** `python -m oikotie.utils.run_tests`
-   **Run linter/formatter:** `ruff check . && ruff format .`
-   **Install/sync dependencies:** `uv sync --all-extras`

## Development Workflow

1.  The main entry point for data collection is `oikotie/scripts/run_workflow.py`.
2.  Data preparation scripts are located in `oikotie/scripts/prepare/`.
3.  Visualization scripts are located in `oikotie/scripts/visualize/`.
4.  Utility scripts are located in `oikotie/utils/`.
5.  Jupyter notebooks for data analysis and exploration are in the `notebooks/` directory.
6.  The database is located at `data/real_estate.duckdb`.
7.  Configuration is managed in `config/config.json`.

## Key Components

-   `oikotie/scripts/run_workflow.py`: The main entry point for the data pipeline.
-   `oikotie/scripts/prepare/`: Contains scripts for preparing data.
-   `oikotie/scripts/visualize/`: Contains scripts for visualizing data.
-   `oikotie/utils/`: Contains utility scripts.
-   `oikotie/scraper.py`: Handles scraping data from Oikotie.fi.
-   `oikotie/geolocation.py`: Handles geocoding of addresses and postal codes.
-   `docs/`: Project documentation.
    -   `scripts/`: Detailed documentation for the project's scripts.
-   `notebooks/`: Contains Jupyter Notebooks for data analysis and exploration.
-   `config/`: Contains configuration files.
-   `data/`: (Ignored by git) Contains the DuckDB database and other data files.
-   `output/`: (Ignored by git) For generated outputs like reports or images.
    -   `examples/`: Example JSON files.