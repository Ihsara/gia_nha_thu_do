"""
Database schema definitions for the Oikotie automation system.

This module defines the enhanced database schema with automation metadata,
execution tracking, and data quality management capabilities.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import duckdb
from loguru import logger


@dataclass
class TableSchema:
    """Represents a database table schema."""
    name: str
    columns: Dict[str, str]
    constraints: List[str]
    indexes: List[str]


class DatabaseSchema:
    """Manages database schema definitions and operations."""
    
    def __init__(self, db_path: str = "data/real_estate.duckdb"):
        self.db_path = db_path
        self.schemas = self._define_schemas()
    
    def _define_schemas(self) -> Dict[str, TableSchema]:
        """Define all table schemas for the automation system."""
        return {
            'listings': self._define_listings_schema(),
            'scraping_executions': self._define_executions_schema(),
            'alert_configurations': self._define_alerts_schema(),
            'data_lineage': self._define_lineage_schema(),
            'api_usage_log': self._define_api_usage_schema(),
            'address_locations': self._define_address_locations_schema(),
        }
    
    def _define_listings_schema(self) -> TableSchema:
        """Define enhanced listings table schema with automation metadata."""
        return TableSchema(
            name='listings',
            columns={
                # Original columns
                'url': 'VARCHAR PRIMARY KEY',
                'source': 'VARCHAR',
                'city': 'VARCHAR',
                'title': 'VARCHAR',
                'address': 'VARCHAR',
                'postal_code': 'VARCHAR',
                'listing_type': 'VARCHAR',
                'price_eur': 'FLOAT',
                'size_m2': 'FLOAT',
                'rooms': 'INTEGER',
                'year_built': 'INTEGER',
                'overview': 'VARCHAR',
                'full_description': 'VARCHAR',
                'other_details_json': 'VARCHAR',
                'scraped_at': 'TIMESTAMP',
                'insert_ts': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_ts': 'TIMESTAMP',
                'deleted_ts': 'TIMESTAMP',
                
                # Enhanced automation columns
                'execution_id': 'VARCHAR(50)',
                'last_check_ts': 'TIMESTAMP',
                'check_count': 'INTEGER DEFAULT 0',
                'last_error': 'TEXT',
                'retry_count': 'INTEGER DEFAULT 0',
                'data_quality_score': 'REAL',
                'data_source': 'VARCHAR(50)',
                'fetch_timestamp': 'TIMESTAMP',
                'last_verified': 'TIMESTAMP',
                'source_url': 'TEXT',
            },
            constraints=[
                # Foreign key constraint removed for now - address_locations table may not exist
                # 'CONSTRAINT fk_listings_address FOREIGN KEY (address) REFERENCES address_locations(address)',
            ],
            indexes=[
                'CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city)',
                'CREATE INDEX IF NOT EXISTS idx_listings_scraped_at ON listings(scraped_at)',
                'CREATE INDEX IF NOT EXISTS idx_listings_last_check_ts ON listings(last_check_ts)',
                'CREATE INDEX IF NOT EXISTS idx_listings_execution_id ON listings(execution_id)',
                'CREATE INDEX IF NOT EXISTS idx_listings_data_quality_score ON listings(data_quality_score)',
            ]
        )
    
    def _define_executions_schema(self) -> TableSchema:
        """Define scraping executions tracking table."""
        return TableSchema(
            name='scraping_executions',
            columns={
                'execution_id': 'VARCHAR(50) PRIMARY KEY',
                'started_at': 'TIMESTAMP NOT NULL',
                'completed_at': 'TIMESTAMP',
                'status': 'VARCHAR(20) NOT NULL', # 'running', 'completed', 'failed'
                'city': 'VARCHAR(50) NOT NULL',
                'listings_processed': 'INTEGER DEFAULT 0',
                'listings_new': 'INTEGER DEFAULT 0',
                'listings_updated': 'INTEGER DEFAULT 0',
                'listings_skipped': 'INTEGER DEFAULT 0',
                'listings_failed': 'INTEGER DEFAULT 0',
                'execution_time_seconds': 'INTEGER',
                'memory_usage_mb': 'INTEGER',
                'error_summary': 'TEXT',
                'node_id': 'VARCHAR(50)', # for cluster deployments
                'configuration_hash': 'VARCHAR(64)',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            },
            constraints=[],
            indexes=[
                'CREATE INDEX IF NOT EXISTS idx_executions_started_at ON scraping_executions(started_at)',
                'CREATE INDEX IF NOT EXISTS idx_executions_city ON scraping_executions(city)',
                'CREATE INDEX IF NOT EXISTS idx_executions_status ON scraping_executions(status)',
                'CREATE INDEX IF NOT EXISTS idx_executions_node_id ON scraping_executions(node_id)',
            ]
        )
    
    def _define_alerts_schema(self) -> TableSchema:
        """Define alert configurations table."""
        return TableSchema(
            name='alert_configurations',
            columns={
                'id': 'INTEGER PRIMARY KEY',
                'alert_name': 'VARCHAR(100) NOT NULL',
                'condition_type': 'VARCHAR(50) NOT NULL', # 'error_rate', 'execution_time', 'data_quality'
                'threshold_value': 'REAL NOT NULL',
                'comparison_operator': 'VARCHAR(10) NOT NULL', # '>', '<', '>=', '<=', '=='
                'alert_channels': 'JSON NOT NULL', # ['email', 'slack', 'webhook']
                'enabled': 'BOOLEAN DEFAULT TRUE',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            },
            constraints=[],
            indexes=[
                'CREATE INDEX IF NOT EXISTS idx_alerts_enabled ON alert_configurations(enabled)',
                'CREATE INDEX IF NOT EXISTS idx_alerts_condition_type ON alert_configurations(condition_type)',
            ]
        )
    
    def _define_lineage_schema(self) -> TableSchema:
        """Define data lineage tracking table."""
        return TableSchema(
            name='data_lineage',
            columns={
                'id': 'INTEGER PRIMARY KEY',
                'table_name': 'VARCHAR(50) NOT NULL',
                'record_id': 'VARCHAR(100) NOT NULL',
                'data_source': 'VARCHAR(50) NOT NULL',
                'fetch_timestamp': 'TIMESTAMP NOT NULL',
                'api_endpoint': 'TEXT',
                'request_parameters': 'JSON',
                'response_metadata': 'JSON',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            },
            constraints=[],
            indexes=[
                'CREATE INDEX IF NOT EXISTS idx_lineage_table_record ON data_lineage(table_name, record_id)',
                'CREATE INDEX IF NOT EXISTS idx_lineage_data_source ON data_lineage(data_source)',
                'CREATE INDEX IF NOT EXISTS idx_lineage_fetch_timestamp ON data_lineage(fetch_timestamp)',
            ]
        )
    
    def _define_api_usage_schema(self) -> TableSchema:
        """Define API usage monitoring table."""
        return TableSchema(
            name='api_usage_log',
            columns={
                'id': 'INTEGER PRIMARY KEY',
                'api_endpoint': 'VARCHAR(200) NOT NULL',
                'request_timestamp': 'TIMESTAMP NOT NULL',
                'response_status': 'INTEGER',
                'response_time_ms': 'INTEGER',
                'records_fetched': 'INTEGER',
                'rate_limit_remaining': 'INTEGER',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            },
            constraints=[],
            indexes=[
                'CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint ON api_usage_log(api_endpoint)',
                'CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage_log(request_timestamp)',
            ]
        )
    
    def _define_address_locations_schema(self) -> TableSchema:
        """Define address locations table (existing, for reference)."""
        return TableSchema(
            name='address_locations',
            columns={
                'address': 'TEXT PRIMARY KEY',
                'latitude': 'REAL',
                'longitude': 'REAL',
                'postcode': 'TEXT',
                'district': 'TEXT',
                'geometry': 'GEOMETRY',
            },
            constraints=[],
            indexes=[
                # Only create index if postcode column exists
                # 'CREATE INDEX IF NOT EXISTS idx_address_locations_postcode ON address_locations(postcode)',
            ]
        )
    
    def create_all_tables(self) -> None:
        """Create all tables with their schemas."""
        logger.info("Creating enhanced database schema for automation system")
        
        try:
            with duckdb.connect(self.db_path) as con:
                # Enable spatial extension
                con.execute("INSTALL spatial;")
                con.execute("LOAD spatial;")
                
                for table_name, schema in self.schemas.items():
                    self._create_table(con, schema)
                    self._create_indexes(con, schema)
                
                logger.success("Enhanced database schema created successfully")
                
        except Exception as e:
            logger.error(f"Failed to create database schema: {e}")
            raise
    
    def _create_table(self, con: duckdb.DuckDBPyConnection, schema: TableSchema) -> None:
        """Create a single table."""
        columns_sql = ', '.join([f"{name} {definition}" for name, definition in schema.columns.items()])
        constraints_sql = ', ' + ', '.join(schema.constraints) if schema.constraints else ''
        
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {schema.name} (
            {columns_sql}{constraints_sql}
        );
        """
        
        logger.debug(f"Creating table {schema.name}")
        con.execute(create_sql)
    
    def _create_indexes(self, con: duckdb.DuckDBPyConnection, schema: TableSchema) -> None:
        """Create indexes for a table."""
        for index_sql in schema.indexes:
            logger.debug(f"Creating index: {index_sql}")
            con.execute(index_sql)
    
    def get_table_info(self) -> Dict[str, Dict]:
        """Get information about all tables."""
        table_info = {}
        
        try:
            with duckdb.connect(self.db_path, read_only=True) as con:
                for table_name in self.schemas.keys():
                    try:
                        # Check if table exists
                        result = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                        row_count = result[0] if result else 0
                        
                        # Get schema info
                        schema_result = con.execute(f"DESCRIBE {table_name}").fetchall()
                        columns = [{'name': row[0], 'type': row[1]} for row in schema_result]
                        
                        table_info[table_name] = {
                            'exists': True,
                            'row_count': row_count,
                            'columns': columns
                        }
                    except Exception as e:
                        table_info[table_name] = {
                            'exists': False,
                            'error': str(e)
                        }
                        
        except Exception as e:
            logger.error(f"Failed to get table info: {e}")
            
        return table_info
    
    def validate_schema(self) -> bool:
        """Validate that all required tables and columns exist."""
        logger.info("Validating database schema")
        
        try:
            table_info = self.get_table_info()
            all_valid = True
            
            # Core tables that must exist
            core_tables = ['listings', 'scraping_executions']
            
            for table_name, schema in self.schemas.items():
                if not table_info.get(table_name, {}).get('exists', False):
                    if table_name in core_tables:
                        logger.error(f"Core table {table_name} does not exist")
                        all_valid = False
                    else:
                        logger.warning(f"Optional table {table_name} does not exist")
                    continue
                
                existing_columns = {col['name'] for col in table_info[table_name]['columns']}
                required_columns = set(schema.columns.keys())
                
                missing_columns = required_columns - existing_columns
                if missing_columns:
                    if table_name in core_tables:
                        # For core tables, only check essential columns
                        essential_columns = self._get_essential_columns(table_name)
                        missing_essential = missing_columns & essential_columns
                        if missing_essential:
                            logger.error(f"Core table {table_name} missing essential columns: {missing_essential}")
                            all_valid = False
                        else:
                            logger.info(f"Core table {table_name} missing optional columns: {missing_columns}")
                    else:
                        logger.warning(f"Optional table {table_name} missing columns: {missing_columns}")
            
            if all_valid:
                logger.success("Database schema validation passed")
            else:
                logger.error("Database schema validation failed")
                
            return all_valid
            
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return False
    
    def _get_essential_columns(self, table_name: str) -> set:
        """Get essential columns that must exist for core tables."""
        essential_columns = {
            'listings': {
                'url', 'source', 'city', 'title', 'scraped_at', 'insert_ts'
            },
            'scraping_executions': {
                'execution_id', 'started_at', 'status', 'city'
            }
        }
        return essential_columns.get(table_name, set())