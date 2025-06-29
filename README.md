# Finnish Real Estate Scraper

A Python-based web scraper designed to extract real estate listing data from Finnish websites like Oikotie.fi. The project is built to be modular, scalable, and resilient, using DuckDB for efficient data storage and `uv` for dependency management.

## Features

-   **Parallel Processing**: Drastically speeds up scraping by processing multiple listing detail pages concurrently using a configurable pool of worker threads.
-   **Modular & Config-Driven**: Easily add or disable scraping tasks for different cities by editing `config.json`.
-   **Structured Database Storage**: Saves data into a DuckDB database (`output/real_estate.duckdb`) with a hybrid schema:
    -   **Core Columns**: Key fields like price, size, and year are stored in dedicated, typed columns for fast querying.
    -   **JSON "Catch-All"**: All other miscellaneous details are stored in a single JSON column, providing flexibility and ensuring no data is lost.
-   **Upsert Logic**: Uses `INSERT OR REPLACE` to ensure that listings are updated upon re-scraping, preventing duplicate data.
-   **Configurable Limits**: Set a maximum number of listings to scrape per task, ideal for quick tests and development.
-   **Advanced Logging**: Utilizes `loguru` for clear, colorized console output and detailed, rotating log files.

## Project Structure

```
.
├── config.json           # Defines scraping tasks (cities, URLs, limits)
├── scraper.py            # The main scraper script
├── pyproject.toml        # Project metadata and dependencies for uv
├── .gitignore            # Specifies files for Git to ignore
├── logs/                 # Directory for runtime log files
└── output/               # Directory for the final database file
    └── real_estate.duckdb
```

## Setup and Installation

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

2.  **Create and activate a virtual environment:**
    ```sh
    uv venv
    source .venv/bin/activate  # On macOS/Linux
    # .venv\Scripts\activate  # On Windows
    ```

3.  **Install dependencies:**
    ```sh
    uv pip install -e .
    ```

## Usage

1.  **Configure Your Tasks:**
    Open `config.json` to define scraping jobs.

    ```json
    {
      "tasks": [
        {
          "city": "Helsinki",
          "enabled": true,
          "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
          "listing_limit": 20,
          "max_detail_workers": 5
        }
      ]
    }
    ```
    -   **`"enabled"`**: `true` to run the task, `false` to skip.
    -   **`"listing_limit"` (Optional)**: Limits the number of listings to scrape. If omitted, it scrapes all listings.
    -   **`"max_detail_workers"` (Optional)**: Sets the number of parallel browser instances for scraping details. Defaults to 5. Adjust based on your system's RAM and CPU.

2.  **Run the Scraper:**
    ```sh
    python scraper.py
    ```

3.  **Query the Data:**
    All data is saved to `output/real_estate.duckdb`.

### Example Queries

Using the DuckDB CLI (`pip install duckdb-cli`):

```sh
# Connect to the database
duckdb output/real_estate.duckdb

# See the table schema
DESCRIBE listings;

# Find the 5 cheapest 3-room apartments in Helsinki built after 2010
SELECT url, title, price_eur, size_m2, year_built
FROM listings
WHERE city = 'Helsinki' AND rooms = 3 AND year_built > 2010
ORDER BY price_eur ASC
LIMIT 5;

# Query a field from the JSON details column
SELECT 
    title, 
    json_extract_string(other_details_json, '$.kunto') AS condition
FROM listings
WHERE condition = 'Hyvä';
```

## Main Dependencies

-   **DuckDB**: An in-process SQL OLAP database for data storage.
-   **Selenium**: For browser automation.
-   **BeautifulSoup4**: For parsing HTML.
-   **Loguru**: For powerful logging.
-   **uv**: For dependency management.
---
This project is intended for educational purposes. Please be responsible and respect the terms of service of the websites you scrape.