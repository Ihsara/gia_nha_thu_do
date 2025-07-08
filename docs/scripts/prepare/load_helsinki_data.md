# Documentation: `load_helsinki_data.py`

This script is responsible for loading a set of Helsinki-specific GeoJSON files into the project's DuckDB database.

## Purpose

The purpose of this script is to provide a straightforward way to import pre-filtered, Helsinki-specific geospatial data into the database. This is an alternative to processing the large, nationwide files and is useful when you have already obtained data for just Helsinki.

## When to Use

You should run this script if you have downloaded the Helsinki-specific GeoJSON files and want to load them into the database. This is an optional step and is not required if you have already run the `prepare_geospatial_data.py` script.

## Setup

Before running this script, ensure the following GeoJSON files are present in the `data/open/helsinki/` directory:

-   `01_RajamerkinSijaintitiedot.json`
-   `02_KiinteistorajanSijaintitiedot.json`
-   `03_KiinteistotunnuksenSijaintitiedot.json`
-   `04_MaaraalanOsanSijaintitiedot.json`
-   `05_ProjisoidunPalstanKiinteistotunnuksenSijaintitiedot.json`
-   `06_ProjisoidunPalstanSijaintitiedot.json`
-   `07_PalstanSijaintitiedot.json`

## How to Run

Execute the script from the root of the project directory using the following command:

```sh
python -m oikotie.scripts.prepare.load_helsinki_data
```

### Example

```
(venv) G:\proj\oikotie> python -m oikotie.scripts.prepare.load_helsinki_data
2025-07-07 00:00:00 | INFO     | __main__:main - Starting to load Helsinki data...
...
2025-07-07 00:00:05 | SUCCESS  | __main__:process_and_load_file - Successfully loaded 12345 records into 'helsinki_07_palstansijaintitiedot'.
```