
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
    Open the `config.json` file. To scrape a city, set its `"enabled"` property to `true`. You can enable multiple cities.

    ```json
    {
      "tasks": [
        {
          "city": "Helsinki",
          "enabled": true,
          "url": "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100"
        },
        {
          "city": "Espoo",
          "enabled": false,
          "url": "..."
        }
      ]
    }
    ```

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
2.  Update the `detect_site_type` method in `scraper.py` to recognize the new site's URL.
3.  Create new parsing methods specific to the new site's HTML structure (e.g., `_extract_etuovi_summaries`, `_parse_etuovi_details_page`).
4.  Update the main `run` method to call the appropriate functions based on the detected site type.

## Main Dependencies

-   **Selenium**: For browser automation and interacting with JavaScript-heavy pages.
-   **BeautifulSoup4**: For parsing HTML and extracting data.
-   **Loguru**: For powerful and easy-to-use logging.
-   **uv**: For creating the virtual environment and managing dependencies.

---

This project is intended for educational purposes. Please be responsible and respect the terms of service of the websites you scrape.