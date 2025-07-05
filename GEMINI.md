# Gemini Project Configuration: Oikotie Scraper

This file provides instructions for the Gemini agent on how to work with this project.

## Project Overview

This project is a Python application designed to scrape housing data from Oikotie.fi. It features a resilient data pipeline with JSON fallbacks, soft deletes, and parallelized scraping. All data is stored in the `data/` directory.

## Key Commands

-   **Run the entire data pipeline:** `python run_workflow.py`
-   **Run the Jupyter dashboard:** `jupyter lab notebooks/check_data.ipynb`
-   **Run tests:** `pytest`
-   **Run linter/formatter:** `ruff check . && ruff format .`
-   **Install/sync dependencies:** `uv sync --all-extras`

## Development Workflow

1.  The main entry point for data collection is `run_workflow.py`.
2.  After the workflow completes, data can be analyzed in `notebooks/check_data.ipynb`.
3.  The database is located at `data/real_estate.duckdb`.
4.  External data lookups (like road data) are currently disabled.

## Key Components

-   `run_workflow.py`: The main entry point for the data pipeline.
-   `oikotie/scraper.py`: Handles scraping data from Oikotie.fi and saving it to the database.
-   `oikotie/geolocation.py`: Handles parallel geocoding of addresses and postal codes.
-   `prepare_locations.py`: Executes the geocoding process.
-   `check_db_status.py`: Prints a status report of the database.
-   `notebooks/check_data.ipynb`: The Jupyter Notebook for data visualization.
-   `data/`: Contains the DuckDB database and other data files.
-   `output/`: For generated reports (currently unused).