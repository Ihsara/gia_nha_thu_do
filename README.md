# Oikotie Scraper and Dashboard

This project scrapes real estate data from Oikotie.fi, prepares it for analysis, and provides a dashboard for visualization.

## Project Structure

-   `config/`: Contains configuration files.
    -   `config.json`: The main configuration file for the scraper.
-   `data/`: (Ignored by git) Contains the raw and processed data, including the main `real_estate.duckdb` database and open data from the National Land Survey of Finland.
-   `docs/`: Project documentation.
    -   `scripts/`: Detailed documentation for the project's scripts.
        -   `prepare/`: Documentation for data preparation scripts.
        -   `visualize/`: Documentation for visualization scripts.
-   `notebooks/`: Jupyter notebooks for data analysis and visualization.
-   `oikotie/`: The main Python package containing all source code.
    -   `scripts/`: Contains the project's standalone scripts.
        -   `prepare/`: Scripts for preparing data.
        -   `visualize/`: Scripts for visualizing data.
-   `output/`: (Ignored by git) For generated outputs like reports or images (currently unused).
-   `tests/`: Unit and integration tests.

## Workflow

The entire data pipeline is managed by a single script. For detailed information on each script, please see the documentation in the `docs/scripts` directory.

1.  **Prepare Data (Optional but Recommended)**:
    -   To prepare the main geospatial data: `python -m oikotie.scripts.prepare.prepare_geospatial_data`
    -   To prepare the topographic data: `python -m oikotie.scripts.prepare.prepare_topographic_data`
    -   To load the Helsinki-specific data: `python -m oikotie.scripts.prepare.load_helsinki_data`

2.  **Run the Full Workflow**:
    ```sh
    python -m oikotie.scripts.run_workflow
    ```

3.  **Analyze and Visualize the Data**:
    -   To inspect the database: `python -m oikotie.scripts.check_database_contents`
    -   To visualize Helsinki parcels: `python -m oikotie.scripts.visualize.visualize_parcels`
    -   To visualize Helsinki buildings: `python -m oikotie.scripts.visualize.visualize_buildings`
    -   To visualize any Helsinki layer: `python -m oikotie.scripts.visualize.visualize_helsinki_layer <table_name>`
    -   Jupyter Notebooks for more in-depth analysis are available in the `notebooks/` directory.

## Setup and Installation

1.  **Clone the repository.**
2.  **Create and activate a virtual environment:**
    ```sh
    uv venv
    source .venv/bin/activate
    ```
3.  **Install dependencies:**
    ```sh
    uv sync --all-extras
    ```
