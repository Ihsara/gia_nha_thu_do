# Finnish Real Estate Scraper

A Python-based web scraper designed to extract real estate listing data from Finnish websites like Oikotie.fi. The project is built to be modular, scalable, and resilient, allowing for easy expansion to new cities and websites. It uses `uv` for fast dependency and environment management.

## Features

-   **Modular & Config-Driven**: Easily add or disable scraping tasks for different cities by editing `config.json`—no code changes needed.
-   **Deep Data Extraction**: Scrapes both summary data from search result pages and detailed information from individual listing pages.
-   **Configurable Limits**: Set a maximum number of listings to scrape per task, ideal for quick tests, development, and benchmarking.
-   **Organized Output**: Automatically saves scraped data into a structured directory format: `output/CityName/YYYY/MM/DD/CityName_Timestamp.json`.
-   **Advanced Logging**: Utilizes `loguru` for clear, colorized console output and detailed, rotating log files.
-   **Robust Error Handling**: If scraping a specific page fails, the script saves debug information (HTML and screenshot) and continues with the rest of the tasks.
-   **Modern Tooling**: Uses `uv` for a fast and efficient development environment and dependency management.

## Project Structure

```
.
├── config.json           # Defines scraping tasks (cities, URLs, limits)
├── scraper.py            # The main scraper script
├── pyproject.toml        # Project metadata and dependencies for uv
├── uv.lock               # Pinned versions of dependencies
├── .gitignore            # Specifies files for Git to ignore
├── logs/                 # Directory for runtime log files
├── output/               # Directory for the final JSON data output
└── debug/                # Directory for HTML/screenshot debug files on error
```

## Setup and Installation

Follow these steps to set up the project environment.

**Prerequisites:**
-   Python 3.8+
-   Google Chrome browser installed. The script uses Selenium and requires a corresponding Chrome browser.
-   `uv` installed. If you don't have it, install it with pip:
    ```sh
    pip install uv
    ```

**Installation Steps:**

1.  **Clone the repository:**
    ```sh
    git clone <your-repo-url>
    cd <your-repo-name>
    ```

2.  **Create and activate a virtual environment using `uv`:**
    ```sh
    # Create the virtual environment
    uv venv

    # Activate the environment
    # On Windows (CMD/PowerShell)
    .venv\Scripts\activate

    # On macOS/Linux (Bash/Zsh)
    source .venv/bin/activate
    ```

3.  **Install the required dependencies using `uv`:**
    The project dependencies are listed in `pyproject.toml`. Install them with:
    ```sh
    uv pip install -e .
    ```
    This command reads the `pyproject.toml` file and installs packages like `selenium`, `beautifulsoup4`, and `loguru`.

## Usage

1.  **Configure Your Tasks:**
    Open the `config.json` file to define what the scraper should do. Each object in the `tasks` list represents a job.

    ```json
    {
      "tasks": [
        {
          "city": "Helsinki",
          "enabled": true,
          "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100",
          "listing_limit": 10
        },
        {
          "city": "Espoo",
          "enabled": false,
          "url": "..."
        }
      ]
    }
    ```

    **Configuration Options:**
    -   **`"city"`**: The name of the city. This is used for creating the output directory.
    -   **`"enabled"`**: Set to `true` to run the task, or `false` to skip it.
    -   **`"url"`**: The full Oikotie search URL for the desired city and filters.
    -   **`"listing_limit"` (Optional)**: Add this key to limit the number of listings scraped for a task. If this key is omitted, the scraper will fetch **all** listings from **all** pages, which can take a very long time. This is highly recommended for development and testing.

2.  **Run the Scraper:**
    Execute the main script from your terminal:
    ```sh
    python scraper.py
    ```

3.  **Find the Output:**
    The script will start scraping the enabled tasks one by one. Upon completion, the data will be saved in the `output/` directory, following the structured path. For example: `output/Helsinki/2025/06/29/Helsinki_20250629-153000.json`.

## How to Extend the Scraper

### Adding a New City

1.  Find the Oikotie search URL for the desired city (e.g., Vantaa).
2.  Open `config.json`.
3.  Add a new JSON object to the `tasks` list for the new city.
4.  Set `"enabled": true`.

    **Example for Vantaa:**
    ```json
    {
      "city": "Vantaa",
      "enabled": true,
      "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B50,6,%22Vantaa%22%5D%5D&cardType=100"
    }
    ```

### Adding a New Website (e.g., Etuovi.com)

The scraper is designed to be modular. To add a new website, you would need to:
1.  Add a new task for it in `config.json`.
2.  Add logic to `scraper.py` to handle the new site's unique HTML structure and pagination.
3.  Update the main execution loop to call the correct functions for the new site.

## Main Dependencies

-   **Selenium**: For browser automation and interacting with JavaScript-heavy pages.
-   **BeautifulSoup4**: For parsing HTML and extracting data.
-   **Loguru**: For powerful and easy-to-use logging.
-   **uv**: For creating the virtual environment and managing dependencies.

---

This project is intended for educational purposes. Please be responsible and respect the terms of service of the websites you scrape.
