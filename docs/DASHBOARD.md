# Dashboard Documentation

## Overview

The Oikotie Analytics Platform provides comprehensive dashboard capabilities for visualizing real estate data collected through both single-node and distributed cluster execution.

## Dashboard Types

### Interactive Folium Dashboards

The primary dashboard system uses Folium for interactive mapping with the following features:

- **Key Metrics**: Displays total listings, average price, and price per square meter
- **Data Table**: Aggregated listings by postal code and housing type  
- **Listing Density Heatmap**: Concentration visualization across postal codes
- **Price Range Road Map**: Individual listings colored by price range
- **Building Footprint Integration**: OSM building polygon overlays
- **Multi-mode Views**: Direct matches, buffer zones, and unmatched listings

### Enhanced Dashboard Features

```bash
# Generate enhanced interactive dashboard
uv run python -m oikotie.visualization.cli.commands dashboard --enhanced --open
```

**Enhanced Features:**
- Split-screen layout (30% controls + 70% map)
- Gradient building highlighting with price-based colors
- Interactive controls (toggles, filters, sliders)
- Building footprint visualization with OSM data
- Real-time filtering and data exploration

## Cluster Integration

### Distributed Data Collection Monitoring

When using the cluster coordination system, dashboards can display:

- **Cluster Status**: Real-time node health and work distribution
- **Processing Progress**: Work item completion rates across nodes
- **Data Quality Metrics**: Validation results from distributed processing
- **Performance Analytics**: Processing times and throughput statistics

### Cluster Dashboard Usage

```python
from oikotie.automation.cluster import create_cluster_coordinator
from oikotie.visualization.dashboard.enhanced import EnhancedDashboard

# Create cluster coordinator
coordinator = create_cluster_coordinator("redis://localhost:6379")

# Get cluster status for dashboard
cluster_status = coordinator.get_cluster_status()

# Generate dashboard with cluster information
dashboard = EnhancedDashboard(
    data_loader=loader,
    cluster_status=cluster_status
)
```

## Usage Instructions

### Command Line Interface

```bash
# Basic dashboard generation
uv run python -m oikotie.visualization.cli.commands dashboard

# Enhanced dashboard with all features
uv run python -m oikotie.visualization.cli.commands dashboard --enhanced --open

# City-specific dashboard
uv run python -m oikotie.visualization.cli.commands dashboard --city helsinki

# Custom output location
uv run python -m oikotie.visualization.cli.commands dashboard --output custom_output/
```

### Python API

```python
from oikotie.visualization.dashboard.enhanced import EnhancedDashboard
from oikotie.visualization.utils.data_loader import DataLoader
from oikotie.visualization.utils.config import get_city_config

# Initialize components
loader = DataLoader()
city_config = get_city_config("helsinki")

# Create enhanced dashboard
dashboard = EnhancedDashboard(
    data_loader=loader,
    city_config=city_config
)

# Generate with custom parameters
output_path = dashboard.run_dashboard_creation(
    enhanced_mode=True,
    max_listings=2000,
    include_building_footprints=True
)
```

## Dashboard Components

### Data Visualization Layers

1. **Property Listings**: Individual property markers with price information
2. **Building Footprints**: OSM building polygon overlays
3. **Density Heatmaps**: Concentration visualization using postal codes
4. **Price Gradients**: Color-coded price ranges and trends
5. **Cluster Metrics**: Node health and processing statistics (when applicable)

### Interactive Controls

- **Layer Toggles**: Show/hide different data layers
- **Price Filters**: Filter by price range and property type
- **Geographic Filters**: Focus on specific areas or postal codes
- **Time Filters**: Filter by listing date and data freshness
- **Cluster Controls**: Monitor and control distributed processing

### Export Capabilities

- **HTML Export**: Standalone interactive dashboards
- **Image Export**: Static maps and visualizations
- **Data Export**: Filtered datasets in CSV/JSON format
- **Report Generation**: Automated analysis reports

## Configuration

### Dashboard Settings

Edit dashboard configuration in `config/dashboard_config.json`:

```json
{
  "default_city": "helsinki",
  "max_listings": 2000,
  "enable_building_footprints": true,
  "cluster_monitoring": true,
  "export_formats": ["html", "png", "csv"],
  "refresh_interval": 300
}
```

### Cluster Integration Settings

```json
{
  "cluster": {
    "redis_url": "redis://localhost:6379",
    "enable_monitoring": true,
    "health_check_interval": 30,
    "status_refresh_rate": 10
  }
}
```

## Performance Considerations

### Large Dataset Handling

- **Pagination**: Automatic pagination for large datasets
- **Lazy Loading**: Progressive data loading for better performance
- **Caching**: Intelligent caching of processed visualizations
- **Sampling**: Smart sampling for preview dashboards

### Cluster Performance

- **Distributed Processing**: Leverage cluster for data preparation
- **Parallel Visualization**: Generate multiple dashboards simultaneously
- **Load Balancing**: Distribute visualization workload across nodes
- **Resource Monitoring**: Track memory and CPU usage during generation

## Troubleshooting

### Common Issues

1. **Dashboard Not Loading**: Check data availability and file permissions
2. **Missing Building Footprints**: Verify OSM data integration
3. **Slow Performance**: Reduce dataset size or enable sampling
4. **Cluster Connection Issues**: Verify Redis connectivity

### Debug Commands

```bash
# Validate data availability
uv run python -m oikotie.visualization.cli.commands validate --schema

# Check system information
uv run python -m oikotie.visualization.cli.commands info

# Test cluster connectivity (if using distributed mode)
python -c "from oikotie.automation.cluster import create_cluster_coordinator; print('Cluster OK')"
```

For detailed instructions on running dashboards, please refer to the main `README.md` file.
