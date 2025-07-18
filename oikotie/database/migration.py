"""
Database Migration Utilities for Oikotie Real Estate Project

This module provides utilities for database schema migrations,
data validation, and backup/restore operations for DuckDB.
"""

import duckdb
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import json
import shutil
from dataclasses import dataclass

from .schema import get_database_schema, validate_database_schema
from .models import ValidationResult


@dataclass
class MigrationInfo:
    """Information about a database migration"""
    version: str
    timestamp: datetime
    description: str
    upgrade_sql: List[str]
    downgrade_sql: List[str]
    validation_checks: List[Callable] = None
    
    def __post_init__(self):
        if self.validation_checks is None:
            self.validation_checks = []


class DatabaseMigrator:
    """Database migration manager for DuckDB operations"""
    
    def __init__(self, db_path: str = "data/real_estate.duckdb"):
        self.db_path = Path(db_path)
        self.migrations_dir = Path("oikotie/database/migrations")
        self.backup_dir = Path("backups/database")
        
        # Ensure directories exist
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, suffix: str = None) -> Path:
        """Create a backup of the current database"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"real_estate_backup_{timestamp}"
        if suffix:
            backup_name += f"_{suffix}"
        backup_name += ".duckdb"
        
        backup_path = self.backup_dir / backup_name
        shutil.copy2(self.db_path, backup_path)
        
        print(f"✅ Database backup created: {backup_path}")
        return backup_path
    
    def restore_backup(self, backup_path: Path) -> None:
        """Restore database from backup"""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        # Create backup of current state before restore
        if self.db_path.exists():
            self.create_backup("before_restore")
        
        shutil.copy2(backup_path, self.db_path)
        print(f"✅ Database restored from: {backup_path}")
    
    def validate_database_integrity(self) -> ValidationResult:
        """Validate database schema and data integrity"""
        if not self.db_path.exists():
            return ValidationResult(
                total_records=0, 
                valid_records=0, 
                invalid_records=0,
                validation_errors=["Database file does not exist"]
            )
        
        result = ValidationResult(total_records=0, valid_records=0, invalid_records=0)
        
        try:
            conn = duckdb.connect(str(self.db_path), read_only=True)
            
            # Get current schema
            actual_schema = self._get_current_schema(conn)
            
            # Validate against expected schema
            schema_issues = validate_database_schema(actual_schema)
            
            if schema_issues:
                for table, issues in schema_issues.items():
                    for issue in issues:
                        result.add_error(f"Schema issue in {table}: {issue}")
            
            # Validate data integrity
            self._validate_data_integrity(conn, result)
            
            conn.close()
            
        except Exception as e:
            result.add_error(f"Database validation failed: {str(e)}")
        
        return result
    
    def _get_current_schema(self, conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
        """Get current database schema information"""
        schema = {}
        
        # Get table list
        tables_result = conn.execute("SHOW TABLES").fetchall()
        table_names = [row[0] for row in tables_result]
        
        for table_name in table_names:
            # Get column information
            columns_result = conn.execute(f"DESCRIBE {table_name}").fetchall()
            columns = {row[0]: {'type': row[1], 'nullable': row[2]} for row in columns_result}
            
            # Get row count
            count_result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            row_count = count_result[0] if count_result else 0
            
            schema[table_name] = {
                'columns': columns,
                'row_count': row_count,
                'exists': True
            }
        
        return schema
    
    def _validate_data_integrity(self, conn: duckdb.DuckDBPyConnection, result: ValidationResult) -> None:
        """Validate data integrity constraints"""
        
        # Check listings table constraints
        try:
            # Check coordinate bounds
            invalid_coords = conn.execute("""
                SELECT COUNT(*) FROM listings 
                WHERE latitude NOT BETWEEN 60.0 AND 60.5 
                   OR longitude NOT BETWEEN 24.5 AND 25.5
            """).fetchone()[0]
            
            if invalid_coords > 0:
                result.add_error(f"Found {invalid_coords} listings with coordinates outside Helsinki bounds")
            
            # Check positive prices
            invalid_prices = conn.execute("""
                SELECT COUNT(*) FROM listings 
                WHERE price IS NOT NULL AND price <= 0
            """).fetchone()[0]
            
            if invalid_prices > 0:
                result.add_error(f"Found {invalid_prices} listings with invalid prices")
            
            # Check foreign key integrity
            orphaned_listings = conn.execute("""
                SELECT COUNT(*) FROM listings l
                LEFT JOIN address_locations a ON l.address = a.address
                WHERE a.address IS NULL
            """).fetchone()[0]
            
            if orphaned_listings > 0:
                result.add_error(f"Found {orphaned_listings} listings without corresponding address_locations")
            
        except Exception as e:
            result.add_error(f"Data integrity validation failed: {str(e)}")
    
    def apply_migration(self, migration: MigrationInfo) -> bool:
        """Apply a database migration"""
        print(f"🔄 Applying migration: {migration.description}")
        
        # Create backup before migration
        backup_path = self.create_backup(f"before_migration_{migration.version}")
        
        try:
            conn = duckdb.connect(str(self.db_path))
            
            # Execute upgrade SQL statements
            for sql in migration.upgrade_sql:
                print(f"   Executing: {sql[:50]}...")
                conn.execute(sql)
            
            # Run validation checks
            for validation_check in migration.validation_checks:
                if not validation_check(conn):
                    raise Exception(f"Migration validation failed: {validation_check.__name__}")
            
            conn.close()
            
            # Final integrity check
            validation_result = self.validate_database_integrity()
            if not validation_result.is_valid:
                raise Exception(f"Post-migration validation failed: {validation_result.validation_errors}")
            
            print(f"✅ Migration {migration.version} applied successfully")
            return True
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            print(f"🔄 Restoring from backup: {backup_path}")
            self.restore_backup(backup_path)
            return False
    
    def rollback_migration(self, migration: MigrationInfo) -> bool:
        """Rollback a database migration"""
        print(f"🔄 Rolling back migration: {migration.description}")
        
        # Create backup before rollback
        backup_path = self.create_backup(f"before_rollback_{migration.version}")
        
        try:
            conn = duckdb.connect(str(self.db_path))
            
            # Execute downgrade SQL statements
            for sql in migration.downgrade_sql:
                print(f"   Executing: {sql[:50]}...")
                conn.execute(sql)
            
            conn.close()
            
            # Final integrity check
            validation_result = self.validate_database_integrity()
            if not validation_result.is_valid:
                raise Exception(f"Post-rollback validation failed: {validation_result.validation_errors}")
            
            print(f"✅ Migration {migration.version} rolled back successfully")
            return True
            
        except Exception as e:
            print(f"❌ Rollback failed: {str(e)}")
            print(f"🔄 Restoring from backup: {backup_path}")
            self.restore_backup(backup_path)
            return False
    
    def optimize_database(self) -> None:
        """Optimize database performance"""
        print("🔄 Optimizing database...")
        
        backup_path = self.create_backup("before_optimization")
        
        try:
            conn = duckdb.connect(str(self.db_path))
            
            # Update table statistics
            print("   Updating table statistics...")
            conn.execute("ANALYZE")
            
            # Vacuum database
            print("   Vacuuming database...")
            conn.execute("VACUUM")
            
            # Rebuild spatial indexes if needed
            schema = get_database_schema()
            spatial_tables = schema.get_spatial_tables()
            
            for table_name in spatial_tables:
                print(f"   Checking spatial indexes for {table_name}...")
                # Note: DuckDB spatial extension handles spatial indexes automatically
                
            conn.close()
            print("✅ Database optimization completed")
            
        except Exception as e:
            print(f"❌ Optimization failed: {str(e)}")
            print(f"🔄 Restoring from backup: {backup_path}")
            self.restore_backup(backup_path)
    
    def export_schema_sql(self, output_path: str = None) -> str:
        """Export current database schema as SQL"""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"schema_export_{timestamp}.sql"
        
        schema = get_database_schema()
        sql_lines = []
        
        # Add header
        sql_lines.append("-- Oikotie Real Estate Database Schema")
        sql_lines.append(f"-- Generated: {datetime.now().isoformat()}")
        sql_lines.append("-- Single DuckDB database with spatial extensions")
        sql_lines.append("")
        
        # Add CREATE TABLE statements
        for table_name in schema.get_all_tables():
            sql_lines.append(f"-- Table: {table_name}")
            create_sql = schema.generate_create_table_sql(table_name)
            sql_lines.append(create_sql)
            sql_lines.append("")
            
            # Add indexes
            index_sqls = schema.generate_index_sql(table_name)
            for index_sql in index_sqls:
                sql_lines.append(index_sql)
            sql_lines.append("")
        
        schema_sql = "\n".join(sql_lines)
        
        # Write to file
        with open(output_path, 'w') as f:
            f.write(schema_sql)
        
        print(f"✅ Schema exported to: {output_path}")
        return schema_sql


def create_sample_migration() -> MigrationInfo:
    """Create a sample migration for testing"""
    return MigrationInfo(
        version="20250711_120000",
        timestamp=datetime.now(),
        description="Add building_type index for performance optimization",
        upgrade_sql=[
            "CREATE INDEX IF NOT EXISTS idx_osm_buildings_building_type ON osm_buildings(building_type);"
        ],
        downgrade_sql=[
            "DROP INDEX IF EXISTS idx_osm_buildings_building_type;"
        ],
        validation_checks=[
            lambda conn: len(conn.execute("SHOW INDEXES FROM osm_buildings").fetchall()) > 0
        ]
    )


def validate_migration_environment() -> ValidationResult:
    """Validate that migration environment is properly set up"""
    result = ValidationResult(total_records=1, valid_records=0, invalid_records=0)
    
    # Check if database file exists
    db_path = Path("data/real_estate.duckdb")
    if not db_path.exists():
        result.add_error("Database file not found: data/real_estate.duckdb")
        return result
    
    # Check if DuckDB spatial extension is available
    try:
        conn = duckdb.connect(":memory:")
        conn.execute("INSTALL spatial")
        conn.execute("LOAD spatial")
        conn.close()
        result.valid_records = 1
    except Exception as e:
        result.add_error(f"DuckDB spatial extension not available: {str(e)}")
    
    return result


def run_migration_tests() -> ValidationResult:
    """Run comprehensive migration system tests"""
    result = ValidationResult(total_records=0, valid_records=0, invalid_records=0)
    
    print("🧪 Running migration system tests...")
    
    # Test 1: Environment validation
    env_result = validate_migration_environment()
    result.total_records += 1
    if env_result.is_valid:
        result.valid_records += 1
        print("✅ Migration environment validation passed")
    else:
        result.invalid_records += 1
        result.validation_errors.extend(env_result.validation_errors)
    
    # Test 2: Database integrity check
    migrator = DatabaseMigrator()
    integrity_result = migrator.validate_database_integrity()
    result.total_records += 1
    if integrity_result.is_valid:
        result.valid_records += 1
        print("✅ Database integrity validation passed")
    else:
        result.invalid_records += 1
        result.validation_errors.extend(integrity_result.validation_errors)
    
    # Test 3: Backup and restore functionality
    try:
        backup_path = migrator.create_backup("test")
        if backup_path.exists():
            backup_path.unlink()  # Clean up test backup
            result.valid_records += 1
            print("✅ Backup functionality test passed")
        else:
            result.add_error("Backup creation failed")
    except Exception as e:
        result.add_error(f"Backup test failed: {str(e)}")
    result.total_records += 1
    
    print(f"🏁 Migration tests completed: {result.valid_records}/{result.total_records} passed")
    return result
