# Oikotie Scraper and Dashboard

This project scrapes real estate data from Oikotie.fi, prepares it for analysis, and provides a dashboard for visualization.

## Project Structure

-   `data/`: Contains the raw and processed data, including the main `real_estate.duckdb` database.
-   `docs/`: Project documentation.
-   `notebooks/`: Jupyter notebooks for data analysis and visualization.
-   `oikotie/`: The main Python package containing all source code.
-   `output/`: For generated outputs like reports or images (currently unused).
-   `tests/`: Unit and integration tests.

## Workflow

The entire data pipeline is managed by a single script.

1.  **Run the full workflow**:
    ```sh
    python run_workflow.py
    ```
    This script executes the following steps in order:
    a.  **Scrape Data**: Fetches the latest listings from Oikotie.fi.
    b.  **Prepare Locations**: Geocodes any new addresses or postal codes.
    c.  **Check Status**: Prints a report on the final state of the database.

2.  **Analyze the Data**:
    Once the workflow is complete, you can use the Jupyter Notebook to explore the data.
    ```sh
    jupyter lab notebooks/dashboard.ipynb
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
