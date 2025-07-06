# Documentation: `check_database_contents.py`

This script provides a way to inspect the contents of the DuckDB database, giving a quick overview of the tables and their data.

## Purpose

The main goal of this script is to allow for a quick and easy inspection of the database without needing to open a database client. It lists all tables, shows their schemas, and prints a sample of the data from each one. It also specifically checks for and identifies tables containing geospatial polygon data.

## When to Use

You can use this script at any time to get a snapshot of the current state of the database. It is particularly useful after running any of the data loading scripts (`prepare_geospatial_data.py`, `prepare_topographic_data.py`, `load_helsinki_data.py`) to verify that the data has been loaded correctly.

## How to Run

Execute the script from the root of the project directory using the following command:

```sh
python check_database_contents.py
```

### Example

```
(venv) G:\proj\oikotie> python check_database_contents.py
2025-07-07 00:00:00 | INFO     | __main__:inspect_database - Connecting to database...
2025-07-07 00:00:00 | INFO     | __main__:inspect_database - Found 9 tables: ...
...
2025-07-07 00:00:01 | SUCCESS  | __main__:inspect_database - Table 'helsinki_07_palstansijaintitiedot' contains polygon data...
```
