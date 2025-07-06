# Oikotie Scraper and Dashboard

This project scrapes real estate data from Oikotie.fi, prepares it for analysis, and provides a dashboard for visualization.

## Project Structure

-   `config/`: Contains configuration files.
-   `data/`: (Ignored by git) Contains the raw and processed data.
-   `docs/`: Project documentation.
    -   `scripts/`: Detailed documentation for the project's scripts.
-   `notebooks/`: Jupyter notebooks for data analysis and visualization.
-   `oikotie/`: The main Python package containing all source code.
    -   `scripts/`: Contains the project's standalone scripts.
        -   `prepare/`: Scripts for preparing data.
        -   `visualize/`: Scripts for visualizing data.
    -   `utils/`: Utility scripts.
-   `output/`: (Ignored by git) For generated outputs like reports or images.
    -   `examples/`: Example JSON files.
-   `tests/`: Unit and integration tests.

## Workflow

For detailed information on each script, please see the documentation in the `docs/scripts` directory.

1.  **Prepare Data (Optional but Recommended)**:
    -   `python -m oikotie.scripts.prepare.prepare_geospatial_data`
    -   `python -m oikotie.scripts.prepare.prepare_topographic_data`
    -   `python -m oikotie.scripts.prepare.load_helsinki_data`

2.  **Run the Full Workflow**:
    ```sh
    python -m oikotie.scripts.run_workflow
    ```

3.  **Analyze and Visualize the Data**:
    -   `python -m oikotie.scripts.check_database_contents`
    -   `python -m oikotie.scripts.visualize.visualize_parcels`
    -   `python -m oikotie.scripts.visualize.visualize_buildings`
    -   `python -m oikotie.scripts.visualize.visualize_helsinki_layer <table_name>`
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