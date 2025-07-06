# Oikotie Scraper and Dashboard

This project scrapes real estate data from Oikotie.fi, prepares it for analysis, and provides a dashboard for visualization.

## Project Structure

-   `config/`: Contains configuration files.
    -   `config.json`: The main configuration file for the scraper.
-   `data/`: (Ignored by git) Contains the raw and processed data, including the main `real_estate.duckdb` database and open data from the National Land Survey of Finland.
-   `docs/`: Project documentation.
    -   `scripts/`: Detailed documentation for the project's scripts.
-   `notebooks/`: Jupyter notebooks for data analysis and visualization.
    -   `check_data.ipynb`: For data visualization and quality checks of the scraped data.
    -   `explore_open_data.ipynb`: For visualizing Helsinki properties with a map background. It prioritizes loading data from the database for performance.
    -   `inspect_gml_data.ipynb`: For inspecting the GML data from the `L4134C.zip` file.
-   `oikotie/`: The main Python package containing all source code.
-   `output/`: (Ignored by git) For generated outputs like reports or images (currently unused).
-   `tests/`: Unit and integration tests.
-   `prepare_geospatial_data.py`: A script to process and load large geospatial data into the database, filtered for Helsinki.
-   `prepare_topographic_data.py`: A script to process the topographic data from the `L4134C.zip` file.
-   `load_helsinki_data.py`: A script to load Helsinki-specific GeoJSON files into the database.
-   `visualize_parcels.py`: A script to generate an interactive map of a sample of Helsinki parcels.
-   `visualize_buildings.py`: A script to generate an interactive map of a sample of Helsinki buildings.
-   `visualize_helsinki_layer.py`: A flexible script to visualize any Helsinki data layer from the database.

## Workflow

The entire data pipeline is managed by a single script. For detailed information on each script, please see the documentation in the `docs/scripts` directory.

1.  **Prepare Geospatial Data (Recommended for performance)**:
    Before running the visualization notebook, it is recommended to load the large geospatial data into the database. This only needs to be done once.
    ```sh
    python prepare_geospatial_data.py
    ```

2.  **Prepare Topographic Data (Optional)**:
    To process the topographic data, run the following script:
    ```sh
    python prepare_topographic_data.py
    ```

3.  **Load Helsinki Data (Optional)**:
    To load the Helsinki-specific GeoJSON files into the database, run the following script:
    ```sh
    python load_helsinki_data.py
    ```

4.  **Run the full workflow**:
    ```sh
    python run_workflow.py
    ```
    This script executes the following steps in order:
    a.  **Scrape Data**: Fetches the latest listings from Oikotie.fi.
    b.  **Prepare Locations**: Geocodes any new addresses or postal codes.
    c.  **Check Status**: Prints a report on the final state of the database.

5.  **Analyze the Data**:
    Once the workflow is complete, you can use the Jupyter Notebooks and scripts to explore the data.
    -   To check the scraped data:
        ```sh
        jupyter lab notebooks/check_data.ipynb
        ```
    -   To visualize Helsinki properties:
        ```sh
        jupyter lab notebooks/explore_open_data.ipynb
        ```
    -   To inspect the GML data:
        ```sh
        jupyter lab notebooks/inspect_gml_data.ipynb
        ```
    -   To generate an interactive map of a sample of Helsinki parcels:
        ```sh
        python visualize_parcels.py
        ```
    -   To generate an interactive map of a sample of Helsinki buildings:
        ```sh
        python visualize_buildings.py
        ```
    -   To generate an interactive map of any Helsinki layer:
        ```sh
        python visualize_helsinki_layer.py <table_name>
        ```

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