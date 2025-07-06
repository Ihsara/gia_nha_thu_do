# Documentation: `prepare_locations.py`

This script is responsible for geocoding the addresses and postal codes of the real estate listings in the database.

## Purpose

The purpose of this script is to enrich the real estate data with geographic coordinates (latitude and longitude). This allows the data to be used in geospatial analysis and visualizations, such as plotting listings on a map.

## When to Use

This script is typically run as part of the main data collection workflow (`run_workflow.py`). However, you can also run it independently if you need to geocode any new or missing locations in the database without running the full scraper.

## How to Run

Execute the script from the root of the project directory using the following command:

```sh
python prepare_locations.py
```

### Example

```
(venv) G:\proj\oikotie> python prepare_locations.py
2025-07-07 00:00:00 | INFO     | oikotie.geolocation:update_postal_code_locations - Found 10 new postal codes to geocode.
...
2025-07-07 00:00:10 | SUCCESS  | oikotie.geolocation:update_address_locations - Successfully updated 50 address locations.
```
