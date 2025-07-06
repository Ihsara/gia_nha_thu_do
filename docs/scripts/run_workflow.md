# Documentation: `run_workflow.py`

This script is the main entry point for the entire data collection and processing pipeline.

## Purpose

The purpose of this script is to automate the process of scraping new real estate listings, geocoding their locations, and saving the data to the database. It orchestrates the different components of the project to ensure a smooth and resilient data pipeline.

## When to Use

You should run this script whenever you want to update the real estate database with the latest listings from Oikotie.fi. It is the primary script for data collection.

## How to Run

Execute the script from the root of the project directory using the following command:

```sh
python run_workflow.py
```

### Example

```
(venv) G:\proj\oikotie> python run_workflow.py
2025-07-07 00:00:00 | INFO     | __main__:main - --- Starting Oikotie Scraper Workflow ---
...
2025-07-07 00:15:00 | SUCCESS  | oikotie.scraper:ScraperOrchestrator:run - --- Task for city: Helsinki finished ---
```
