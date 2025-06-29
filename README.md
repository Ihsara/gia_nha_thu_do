# Finnish Real Estate Scraper

A Python-based web scraper designed to extract real estate listing data from Finnish websites like Oikotie.fi. The project is built to be modular, scalable, and resilient, using DuckDB for efficient data storage and `uv` for dependency management.

## Key Features

-   **Stable Parallel Architecture**: The scraper uses a robust two-phase process to maximize speed and stability:
    1.  **Sequential Summary Scan**: A single, stable browser instance first discovers all listing URLs to prevent crashes during pagination.
    2.  **Parallel Detail Scraping**: The collected URLs are then distributed to a pool of parallel workers, each with its own browser instance, to scrape detailed information concurrently.
-   **Config-Driven**: Easily add or disable scraping tasks for different cities and control concurrency by editing `config.json`.
-   **Structured Database Storage**: Saves all data into a DuckDB database (`output/real_estate.duckdb`) with a hybrid schema for fast querying and data integrity.
-   **Anti-Bot Detection Measures**: Incorporates techniques like User-Agent rotation and randomized delays to mimic human behavior and reduce the risk of being blocked.
-   **Advanced Logging & Debugging**: Utilizes `loguru` for clear console output and detailed log files. Automatically saves debug info on errors.
-   **Interactive Analysis Notebook**: Includes a `test.py` Marimo notebook for interactive data exploration, featuring tables and a real map visualization with geocoded addresses via `folium`.

## Project Structure

```
.
├── config.json           # Defines scraping tasks (cities, URLs, limits)
├── scraper.py            # The main scraper script (run this file)
├── test.py               # The Marimo notebook for data analysis
├── pyproject.toml        # Project metadata and dependencies for uv
├── .gitignore            # Specifies files for Git to ignore
├── logs/                 # Directory for runtime log files
├── output/               # Directory for the final database file
│   └── real_estate.duckdb
└── debug/                # Directory for HTML/screenshot debug files on error
```

## Setup and Installation

Follow these steps to set up the project environment.

**Prerequisites:**
-   Python 3.8+
-   Google Chrome browser installed.
-   `uv` installed. If you don't have it: `pip install uv`.

**Installation Steps:**

1.  **Clone the repository:**
    ```sh
    git clone <your-repo-url>
    cd <your-repo-name>
    ```

2.  **Create and activate a virtual environment using `uv`:**
    ```sh
    uv venv
    source .venv/bin/activate  # On macOS/Linux
    # .venv\Scripts\activate  # On Windows
    ```

3.  **Install all dependencies using `uv`:**
    This reads `pyproject.toml` and installs all necessary packages.
    ```sh
    uv pip install -e .
    ```

## Complete Workflow: From Scraping to Analysis

This project has two main scripts: `scraper.py` for fetching data and `test.py` for analyzing it. Due to database file locking, they should be run one at a time.

### Step 1: Configure and Run the Scraper

1.  **Close the Analysis Notebook**:
    > ⚠️ **IMPORTANT**: Before running the scraper, ensure that the Marimo notebook (`test.py`) or any other program connected to `output/real_estate.duckdb` is **not running**. If it is, the scraper will fail with a file lock error. Stop it with `Ctrl + C` in its terminal.

2.  **Configure `config.json`**:
    Open the file to define your scraping tasks.
    ```json
    {
      "tasks": [
        {
          "city": "Helsinki",
          "enabled": true,
          "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
          "listing_limit": 50,
          "max_detail_workers": 5
        }
      ]
    }
    ```
    -   `"enabled"`: `true` to run the task, `false` to skip.
    -   `"listing_limit"` (Optional): Limits the number of listings to scrape. **Recommended for testing.** If omitted, the scraper will attempt to fetch all listings from all pages.
    -   `"max_detail_workers"` (Optional): Sets the number of parallel browser instances for scraping details. A good starting value is 4-8, depending on your system's RAM and CPU.

3.  **Run the scraper script**:
    ```sh
    python scraper.py
    ```
    The script will log its progress to the console. Wait for it to complete.

### Step 2: Analyze the Data with Marimo

1.  **Start the Marimo server**:
    Once the scraper is finished, you can start the interactive notebook to view the results.
    ```sh
    marimo run test.py
    ```

2.  **Open the Notebook**:
    Marimo will provide a URL in your terminal (e.g., `http://localhost:2718`). Open this in your browser.

3.  **Explore the Data**:
    - The notebook will connect to the `real_estate.duckdb` file.
    - You will see cells displaying the first 10 rows, the top 10 most expensive listings, and a map.
    - The map cell will geocode addresses in real-time, which will take about **1 second per listing** due to rate limiting. Please be patient while it runs.

## Troubleshooting

> **Error:** `duckdb.duckdb.IOException: IO Error: Cannot open file... because it is being used by another process.`

This is the most common error. It means another program (almost certainly the Marimo notebook) has the database file open.

**Solution**: Stop the Marimo server (`Ctrl + C`) and then re-run the `scraper.py` script.