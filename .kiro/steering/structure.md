# Project Structure

## Core Package Organization
```
oikotie/                    # Main Python package
├── database/               # Database schema and models
│   ├── schema.py          # Table definitions and relationships
│   ├── models.py          # Data model classes
│   └── migration.py       # Migration utilities
├── visualization/          # Modern visualization package (preferred)
│   ├── cli/               # Command-line interface
│   ├── dashboard/         # Dashboard generation
│   ├── maps/              # Map utilities
│   └── utils/             # Visualization utilities
├── scripts/               # Legacy executable scripts
└── utils/                 # Core utility functions
```

## Data and Configuration
```
config/                     # Configuration files
├── config.json            # Scraping configuration (cities, URLs)
└── system_config_local.json

data/                       # Data storage (git-ignored)
├── real_estate.duckdb     # Primary DuckDB database
├── cache/                 # Cached data
└── processed/             # Processed datasets

output/                     # Generated files (git-ignored)
└── visualization/         # Dashboard outputs
```

## Development and Documentation
```
.clinerules/               # Development workflow standards
├── database-management.md # Database rules and schema docs
├── testing-workflow.md    # Mandatory testing procedures
└── git-workflow.md        # Git conventions

docs/                      # Project documentation
├── errors/                # Error documentation system
└── scripts/               # Script documentation

memory-bank/               # Project knowledge management
├── projectbrief.md        # Project overview
├── productContext.md      # Product context
└── progress.md            # Development progress

tests/                     # Test suite
├── integration/           # Integration tests
├── unit/                  # Unit tests
└── validation/            # Validation tests (progressive)
```

## Key Architecture Patterns

### Modern vs Legacy Code
- **Preferred**: Use `oikotie.visualization.cli.commands` for new functionality
- **Legacy**: `oikotie.scripts.*` maintained for compatibility
- **Migration**: Gradually move legacy scripts to modern CLI

### Database Strategy
- **Single Source**: All data in `data/real_estate.duckdb`
- **No SQLite**: DuckDB only, remove any SQLite references
- **Connection**: Use `oikotie.database` utilities

### Testing Strategy
- **Progressive Validation**: 10-sample → full dataset testing
- **Bug Prevention**: Mandatory tests before expensive operations (>10 min)
- **Cost Optimization**: 10-20% time investment in testing vs pipeline failures

### File Naming Conventions
- **Scripts**: Descriptive names with timestamps for analysis scripts
- **Branches**: `feature/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/`
- **Commits**: Conventional commits format: `type(scope): description`

### Data Flow
1. **Collection**: Web scraping → Raw data
2. **Processing**: Geocoding → Address standardization → Spatial enrichment
3. **Storage**: DuckDB with spatial extensions
4. **Visualization**: Interactive dashboards and maps
5. **Analysis**: Jupyter notebooks and custom scripts