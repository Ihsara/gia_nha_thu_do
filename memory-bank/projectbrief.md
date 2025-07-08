# Project Brief: Oikotie Real Estate Scraper and Dashboard

## Project Overview
The Oikotie project is a comprehensive real estate data collection and analysis system focused on Finnish property markets. It scrapes property listings from Oikotie.fi, processes and enriches the data with geospatial information, and provides visualization capabilities through dashboards and analysis tools.

## Core Objectives
1. **Data Collection**: Automated scraping of real estate listings from Oikotie.fi
2. **Data Enrichment**: Geocoding addresses, integrating with Helsinki open data
3. **Geospatial Analysis**: Processing property locations with topographic and parcel data
4. **Visualization**: Dashboard and mapping capabilities for property analysis
5. **Data Storage**: Efficient storage using DuckDB for analytics workloads

## Target Markets
- Primary: Helsinki real estate market
- Secondary: Espoo and other Finnish cities (configurable)

## Key Features
- Multi-threaded web scraping with Selenium
- Automated geocoding and address standardization
- Integration with Helsinki city open data sources
- Geospatial data processing (buildings, parcels, topography)
- Interactive visualizations using Folium
- Jupyter notebook analysis capabilities
- Database-driven architecture with DuckDB

## Success Criteria
- Successful scraping and storage of Helsinki property listings
- Accurate geocoding and geospatial data integration
- Functional dashboard for property analysis
- Scalable architecture for additional cities
- Reliable data pipeline execution

## Project Scope
**In Scope:**
- Web scraping Oikotie.fi property listings
- Geocoding and address processing
- Integration with Helsinki open datasets
- Data visualization and dashboard creation
- Automated workflow orchestration

**Out of Scope:**
- Real-time property alerts
- Property valuation algorithms
- Commercial property types (focus on residential)
- International markets outside Finland
