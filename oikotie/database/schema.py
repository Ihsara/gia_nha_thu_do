"""
Database Schema Definitions for Oikotie Real Estate Project

This module provides comprehensive schema definitions, table relationships,
and validation utilities for the DuckDB database structure.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum


class TableNames(Enum):
    """Enumeration of all table names in the database"""
    LISTINGS = "listings"
    OSM_BUILDINGS = "osm_buildings"
    ADDRESS_LOCATIONS = "address_locations"
    HELSINKI_PROPERTY_BOUNDARIES = "helsinki_property_boundaries"
    HELSINKI_ADMIN_MARKERS = "helsinki_admin_markers"


@dataclass
class ColumnDefinition:
    """Definition of a database column"""
    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False
    foreign_key: Optional[str] = None
    description: str = ""


@dataclass
class TableSchema:
    """Complete schema definition for a database table"""
    name: str
    columns: List[ColumnDefinition]
    indexes: List[str]
    constraints: List[str]
    description: str = ""
    row_count: Optional[int] = None


class DatabaseSchema:
    """Complete database schema definition and validation"""
    
    def __init__(self):
        self.tables = self._define_tables()
    
    def _define_tables(self) -> Dict[str, TableSchema]:
        """Define all table schemas in the database"""
        
        # Listings table schema
        listings_schema = TableSchema(
            name=TableNames.LISTINGS.value,
            description="Real estate listings with spatial coordinates",
            row_count=8725,
            columns=[
                ColumnDefinition("address", "TEXT", nullable=False, 
                               foreign_key="address_locations.address",
                               description="Property address (FK to address_locations)"),
                ColumnDefinition("price", "REAL", nullable=True,
                               description="Listing price in euros"),
                ColumnDefinition("listing_type", "TEXT", nullable=True,
                               description="Type of listing (sale, rent, etc.)"),
                ColumnDefinition("latitude", "REAL", nullable=False,
                               description="Latitude coordinate (WGS84)"),
                ColumnDefinition("longitude", "REAL", nullable=False,
                               description="Longitude coordinate (WGS84)"),
                ColumnDefinition("geometry", "GEOMETRY(POINT, 4326)", nullable=False,
                               description="Spatial point geometry in EPSG:4326"),
                ColumnDefinition("listing_date", "DATE", nullable=True,
                               description="Date when listing was published")
            ],
            indexes=[
                "idx_listings_geometry",
                "idx_listings_address", 
                "idx_listings_listing_type"
            ],
            constraints=[
                "FOREIGN KEY (address) REFERENCES address_locations(address)",
                "CHECK (price > 0)",
                "CHECK (latitude BETWEEN 60.0 AND 60.5)",
                "CHECK (longitude BETWEEN 24.5 AND 25.5)",
                "CHECK (ST_IsValid(geometry))"
            ]
        )
        
        # OSM Buildings table schema
        osm_buildings_schema = TableSchema(
            name=TableNames.OSM_BUILDINGS.value,
            description="OpenStreetMap building footprints for Helsinki",
            row_count=79556,
            columns=[
                ColumnDefinition("osm_id", "BIGINT", nullable=False, primary_key=True,
                               description="Unique OpenStreetMap identifier"),
                ColumnDefinition("geometry", "GEOMETRY(POLYGON, 4326)", nullable=False,
                               description="Building footprint polygon in EPSG:4326"),
                ColumnDefinition("building_type", "TEXT", nullable=True,
                               description="Type of building (residential, commercial, etc.)"),
                ColumnDefinition("name", "TEXT", nullable=True,
                               description="Building name if available"),
                ColumnDefinition("addr_street", "TEXT", nullable=True,
                               description="Street name from OSM address"),
                ColumnDefinition("addr_housenumber", "TEXT", nullable=True,
                               description="House number from OSM address"),
                ColumnDefinition("addr_postcode", "TEXT", nullable=True,
                               description="Postal code from OSM address")
            ],
            indexes=[
                "idx_osm_buildings_osm_id",
                "idx_osm_buildings_geometry",
                "idx_osm_buildings_building_type"
            ],
            constraints=[
                "PRIMARY KEY (osm_id)",
                "CHECK (ST_IsValid(geometry))",
                "CHECK (ST_GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON'))"
            ]
        )
        
        # Address Locations table schema
        address_locations_schema = TableSchema(
            name=TableNames.ADDRESS_LOCATIONS.value,
            description="Geocoded address locations for Helsinki",
            row_count=6643,
            columns=[
                ColumnDefinition("address", "TEXT", nullable=False, primary_key=True,
                               description="Unique address string"),
                ColumnDefinition("latitude", "REAL", nullable=False,
                               description="Latitude coordinate (WGS84)"),
                ColumnDefinition("longitude", "REAL", nullable=False,
                               description="Longitude coordinate (WGS84)"),
                ColumnDefinition("postcode", "TEXT", nullable=True,
                               description="Postal code for the address"),
                ColumnDefinition("district", "TEXT", nullable=True,
                               description="District or neighborhood name"),
                ColumnDefinition("geometry", "GEOMETRY(POINT, 4326)", nullable=False,
                               description="Spatial point geometry in EPSG:4326")
            ],
            indexes=[
                "idx_address_locations_address",
                "idx_address_locations_geometry"
            ],
            constraints=[
                "PRIMARY KEY (address)",
                "CHECK (latitude BETWEEN 60.0 AND 60.5)",
                "CHECK (longitude BETWEEN 24.5 AND 25.5)",
                "CHECK (ST_IsValid(geometry))",
                "CHECK (ST_GeometryType(geometry) = 'POINT')"
            ]
        )
        
        # Helsinki Property Boundaries table schema
        helsinki_property_boundaries_schema = TableSchema(
            name=TableNames.HELSINKI_PROPERTY_BOUNDARIES.value,
            description="Administrative property boundaries for Helsinki",
            columns=[
                ColumnDefinition("boundary_id", "TEXT", nullable=False, primary_key=True,
                               description="Unique boundary identifier"),
                ColumnDefinition("boundary_type", "TEXT", nullable=True,
                               description="Type of administrative boundary"),
                ColumnDefinition("geometry", "GEOMETRY(POLYGON, 4326)", nullable=False,
                               description="Boundary polygon geometry in EPSG:4326"),
                ColumnDefinition("properties", "JSON", nullable=True,
                               description="Additional boundary properties as JSON")
            ],
            indexes=[
                "idx_helsinki_property_boundaries_geometry"
            ],
            constraints=[
                "PRIMARY KEY (boundary_id)",
                "CHECK (ST_IsValid(geometry))"
            ]
        )
        
        # Helsinki Admin Markers table schema
        helsinki_admin_markers_schema = TableSchema(
            name=TableNames.HELSINKI_ADMIN_MARKERS.value,
            description="Administrative markers for Helsinki",
            columns=[
                ColumnDefinition("marker_id", "TEXT", nullable=False, primary_key=True,
                               description="Unique marker identifier"),
                ColumnDefinition("marker_type", "TEXT", nullable=True,
                               description="Type of administrative marker"),
                ColumnDefinition("geometry", "GEOMETRY(POINT, 4326)", nullable=False,
                               description="Marker point geometry in EPSG:4326"),
                ColumnDefinition("properties", "JSON", nullable=True,
                               description="Additional marker properties as JSON")
            ],
            indexes=[
                "idx_helsinki_admin_markers_geometry"
            ],
            constraints=[
                "PRIMARY KEY (marker_id)",
                "CHECK (ST_IsValid(geometry))",
                "CHECK (ST_GeometryType(geometry) = 'POINT')"
            ]
        )
        
        return {
            TableNames.LISTINGS.value: listings_schema,
            TableNames.OSM_BUILDINGS.value: osm_buildings_schema,
            TableNames.ADDRESS_LOCATIONS.value: address_locations_schema,
            TableNames.HELSINKI_PROPERTY_BOUNDARIES.value: helsinki_property_boundaries_schema,
            TableNames.HELSINKI_ADMIN_MARKERS.value: helsinki_admin_markers_schema
        }
    
    def get_table_schema(self, table_name: str) -> Optional[TableSchema]:
        """Get schema definition for a specific table"""
        return self.tables.get(table_name)
    
    def get_all_tables(self) -> List[str]:
        """Get list of all table names"""
        return list(self.tables.keys())
    
    def get_relationships(self) -> Dict[str, List[str]]:
        """Get foreign key relationships between tables"""
        relationships = {}
        
        for table_name, schema in self.tables.items():
            table_fks = []
            for column in schema.columns:
                if column.foreign_key:
                    table_fks.append(f"{column.name} -> {column.foreign_key}")
            if table_fks:
                relationships[table_name] = table_fks
        
        return relationships
    
    def get_spatial_tables(self) -> List[str]:
        """Get list of tables with spatial columns"""
        spatial_tables = []
        
        for table_name, schema in self.tables.items():
            for column in schema.columns:
                if column.data_type.startswith("GEOMETRY"):
                    spatial_tables.append(table_name)
                    break
        
        return spatial_tables
    
    def validate_schema_compliance(self, actual_schema: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate actual database schema against expected schema"""
        issues = {}
        
        for table_name, expected_schema in self.tables.items():
            table_issues = []
            
            # Check if table exists
            if table_name not in actual_schema:
                table_issues.append(f"Table {table_name} does not exist")
                issues[table_name] = table_issues
                continue
            
            # Check columns
            actual_columns = actual_schema[table_name].get('columns', {})
            expected_columns = {col.name: col for col in expected_schema.columns}
            
            for col_name, expected_col in expected_columns.items():
                if col_name not in actual_columns:
                    table_issues.append(f"Column {col_name} missing")
                # Additional column validation could be added here
            
            if table_issues:
                issues[table_name] = table_issues
        
        return issues
    
    def generate_create_table_sql(self, table_name: str) -> str:
        """Generate CREATE TABLE SQL statement for a table"""
        schema = self.get_table_schema(table_name)
        if not schema:
            raise ValueError(f"Unknown table: {table_name}")
        
        lines = [f"CREATE TABLE {table_name} ("]
        
        # Add column definitions
        column_lines = []
        for column in schema.columns:
            col_def = f"    {column.name} {column.data_type}"
            if not column.nullable:
                col_def += " NOT NULL"
            if column.primary_key:
                col_def += " PRIMARY KEY"
            column_lines.append(col_def)
        
        lines.append(",\n".join(column_lines))
        lines.append(");")
        
        return "\n".join(lines)
    
    def generate_index_sql(self, table_name: str) -> List[str]:
        """Generate CREATE INDEX SQL statements for a table"""
        schema = self.get_table_schema(table_name)
        if not schema:
            raise ValueError(f"Unknown table: {table_name}")
        
        index_statements = []
        for index_name in schema.indexes:
            if "geometry" in index_name:
                # Spatial index
                column_name = index_name.split("_")[-1]  # Extract column name
                sql = f"CREATE INDEX {index_name} ON {table_name} USING GIST({column_name});"
            else:
                # Regular index - determine column from index name
                column_name = index_name.replace(f"idx_{table_name}_", "")
                sql = f"CREATE INDEX {index_name} ON {table_name}({column_name});"
            
            index_statements.append(sql)
        
        return index_statements


# Global schema instance
DATABASE_SCHEMA = DatabaseSchema()


def get_database_schema() -> DatabaseSchema:
    """Get the global database schema instance"""
    return DATABASE_SCHEMA


def get_table_names() -> List[str]:
    """Get list of all table names"""
    return DATABASE_SCHEMA.get_all_tables()


def get_table_info(table_name: str) -> Optional[TableSchema]:
    """Get schema information for a specific table"""
    return DATABASE_SCHEMA.get_table_schema(table_name)


def get_spatial_tables() -> List[str]:
    """Get list of tables with spatial geometry columns"""
    return DATABASE_SCHEMA.get_spatial_tables()


def get_foreign_key_relationships() -> Dict[str, List[str]]:
    """Get foreign key relationships between tables"""
    return DATABASE_SCHEMA.get_relationships()


def validate_database_schema(actual_schema: Dict[str, Any]) -> Dict[str, List[str]]:
    """Validate actual database schema against expected schema"""
    return DATABASE_SCHEMA.validate_schema_compliance(actual_schema)
