"""
Database module for Oikotie project.
Provides database management, schema definitions, and migration utilities.

Available modules:
- schema: Database schema definitions and validation
- models: Data class models for database entities  
- migration: Database migration and backup utilities
"""

# Import key classes and functions for easy access
from .schema import (
    DatabaseSchema,
    TableSchema,
    ColumnDefinition,
    get_database_schema,
    get_table_names,
    get_table_info,
    get_spatial_tables,
    get_foreign_key_relationships,
    validate_database_schema
)

from .models import (
    Listing,
    OSMBuilding,
    AddressLocation,
    PropertyBoundary,
    AdminMarker,
    SpatialJoinResult,
    ValidationResult,
    get_model_class,
    validate_model_data,
    batch_validate_model_data,
    convert_to_model_instances,
    convert_from_model_instances
)

from .migration import (
    DatabaseMigrator,
    MigrationInfo,
    create_sample_migration,
    validate_migration_environment,
    run_migration_tests
)

__all__ = [
    # Schema exports
    'DatabaseSchema',
    'TableSchema', 
    'ColumnDefinition',
    'get_database_schema',
    'get_table_names',
    'get_table_info',
    'get_spatial_tables',
    'get_foreign_key_relationships',
    'validate_database_schema',
    
    # Model exports
    'Listing',
    'OSMBuilding',
    'AddressLocation',
    'PropertyBoundary',
    'AdminMarker',
    'SpatialJoinResult',
    'ValidationResult',
    'get_model_class',
    'validate_model_data',
    'batch_validate_model_data',
    'convert_to_model_instances',
    'convert_from_model_instances',
    
    # Migration exports
    'DatabaseMigrator',
    'MigrationInfo',
    'create_sample_migration',
    'validate_migration_environment',
    'run_migration_tests'
]
