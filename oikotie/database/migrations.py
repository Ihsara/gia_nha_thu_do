"""
Database migration management for the Oikotie automation system.

This module provides migration capabilities to safely evolve the database schema
while preserving existing data and maintaining backward compatibility.
"""

import os
import hashlib
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import duckdb
from loguru import logger


@dataclass
class Migration:
    """Represents a database migration."""
    version: str
    description: str
    upgrade_sql: str
    downgrade_sql: str
    validation_sql: Optional[str] = None


class MigrationManager:
    """Manages database migrations for the automation system."""
    
    def __init__(self, db_path: str = "data/real_estate.duckdb"):
        self.db_path = db_path
        self.migrations = self._define_migrations()
        self._ensure_migration_table()
    
    def _ensure_migration_table(self) -> None:
        """Ensure the migration tracking table exists."""
        try:
            with duckdb.connect(self.db_path) as con:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(50) PRIMARY KEY,
                        description VARCHAR(200) NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        checksum VARCHAR(64) NOT NULL
                    );
                """)
        except Exception as e:
            logger.error(f"Failed to create migration table: {e}")
            raise
    
    def _define_migrations(self) -> List[Migration]:
        """Define all database migrations."""
        return [
            Migration(
                version="001_add_automation_metadata",
                description="Add automation metadata columns to listings table",
                upgrade_sql="""
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS execution_id VARCHAR(50);
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_check_ts TIMESTAMP;
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS check_count INTEGER DEFAULT 0;
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_error TEXT;
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS data_quality_score REAL;
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS data_source VARCHAR(50);
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS fetch_timestamp TIMESTAMP;
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_verified TIMESTAMP;
                    ALTER TABLE listings ADD COLUMN IF NOT EXISTS source_url TEXT;
                """,
                downgrade_sql="""
                    ALTER TABLE listings DROP COLUMN IF EXISTS execution_id;
                    ALTER TABLE listings DROP COLUMN IF EXISTS last_check_ts;
                    ALTER TABLE listings DROP COLUMN IF EXISTS check_count;
                    ALTER TABLE listings DROP COLUMN IF EXISTS last_error;
                    ALTER TABLE listings DROP COLUMN IF EXISTS retry_count;
                    ALTER TABLE listings DROP COLUMN IF EXISTS data_quality_score;
                    ALTER TABLE listings DROP COLUMN IF EXISTS data_source;
                    ALTER TABLE listings DROP COLUMN IF EXISTS fetch_timestamp;
                    ALTER TABLE listings DROP COLUMN IF EXISTS last_verified;
                    ALTER TABLE listings DROP COLUMN IF EXISTS source_url;
                """,
                validation_sql="SELECT execution_id, last_check_ts, data_quality_score FROM listings LIMIT 1;"
            ),
            Migration(
                version="002_create_execution_tracking",
                description="Create scraping execution tracking table",
                upgrade_sql="""
                    CREATE TABLE IF NOT EXISTS scraping_executions (
                        execution_id VARCHAR(50) PRIMARY KEY,
                        started_at TIMESTAMP NOT NULL,
                        completed_at TIMESTAMP,
                        status VARCHAR(20) NOT NULL,
                        city VARCHAR(50) NOT NULL,
                        listings_processed INTEGER DEFAULT 0,
                        listings_new INTEGER DEFAULT 0,
                        listings_updated INTEGER DEFAULT 0,
                        listings_skipped INTEGER DEFAULT 0,
                        listings_failed INTEGER DEFAULT 0,
                        execution_time_seconds INTEGER,
                        memory_usage_mb INTEGER,
                        error_summary TEXT,
                        node_id VARCHAR(50),
                        configuration_hash VARCHAR(64),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_executions_started_at ON scraping_executions(started_at);
                    CREATE INDEX IF NOT EXISTS idx_executions_city ON scraping_executions(city);
                    CREATE INDEX IF NOT EXISTS idx_executions_status ON scraping_executions(status);
                """,
                downgrade_sql="""
                    DROP TABLE IF EXISTS scraping_executions;
                """,
                validation_sql="SELECT COUNT(*) FROM scraping_executions;"
            ),
            Migration(
                version="003_create_alert_system",
                description="Create alert configuration and monitoring tables",
                upgrade_sql="""
                    CREATE TABLE IF NOT EXISTS alert_configurations (
                        id INTEGER PRIMARY KEY,
                        alert_name VARCHAR(100) NOT NULL,
                        condition_type VARCHAR(50) NOT NULL,
                        threshold_value REAL NOT NULL,
                        comparison_operator VARCHAR(10) NOT NULL,
                        alert_channels JSON NOT NULL,
                        enabled BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_alerts_enabled ON alert_configurations(enabled);
                    CREATE INDEX IF NOT EXISTS idx_alerts_condition_type ON alert_configurations(condition_type);
                """,
                downgrade_sql="""
                    DROP TABLE IF EXISTS alert_configurations;
                """,
                validation_sql="SELECT COUNT(*) FROM alert_configurations;"
            ),
            Migration(
                version="004_create_data_governance",
                description="Create data lineage and API usage tracking tables",
                upgrade_sql="""
                    CREATE TABLE IF NOT EXISTS data_lineage (
                        id INTEGER PRIMARY KEY,
                        table_name VARCHAR(50) NOT NULL,
                        record_id VARCHAR(100) NOT NULL,
                        data_source VARCHAR(50) NOT NULL,
                        fetch_timestamp TIMESTAMP NOT NULL,
                        api_endpoint TEXT,
                        request_parameters JSON,
                        response_metadata JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE TABLE IF NOT EXISTS api_usage_log (
                        id INTEGER PRIMARY KEY,
                        api_endpoint VARCHAR(200) NOT NULL,
                        request_timestamp TIMESTAMP NOT NULL,
                        response_status INTEGER,
                        response_time_ms INTEGER,
                        records_fetched INTEGER,
                        rate_limit_remaining INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_lineage_table_record ON data_lineage(table_name, record_id);
                    CREATE INDEX IF NOT EXISTS idx_lineage_data_source ON data_lineage(data_source);
                    CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint ON api_usage_log(api_endpoint);
                    CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage_log(request_timestamp);
                """,
                downgrade_sql="""
                    DROP TABLE IF EXISTS data_lineage;
                    DROP TABLE IF EXISTS api_usage_log;
                """,
                validation_sql="SELECT COUNT(*) FROM data_lineage; SELECT COUNT(*) FROM api_usage_log;"
            ),
            Migration(
                version="005_add_listings_indexes",
                description="Add performance indexes for automation queries",
                upgrade_sql="""
                    CREATE INDEX IF NOT EXISTS idx_listings_last_check_ts ON listings(last_check_ts);
                    CREATE INDEX IF NOT EXISTS idx_listings_execution_id ON listings(execution_id);
                    CREATE INDEX IF NOT EXISTS idx_listings_data_quality_score ON listings(data_quality_score);
                    CREATE INDEX IF NOT EXISTS idx_listings_city_scraped_at ON listings(city, scraped_at);
                """,
                downgrade_sql="""
                    DROP INDEX IF EXISTS idx_listings_last_check_ts;
                    DROP INDEX IF EXISTS idx_listings_execution_id;
                    DROP INDEX IF EXISTS idx_listings_data_quality_score;
                    DROP INDEX IF EXISTS idx_listings_city_scraped_at;
                """,
                validation_sql="SELECT COUNT(*) FROM listings WHERE last_check_ts IS NOT NULL;"
            )
        ]
    
    def _calculate_checksum(self, migration: Migration) -> str:
        """Calculate checksum for migration to detect changes."""
        content = f"{migration.version}{migration.description}{migration.upgrade_sql}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions."""
        try:
            with duckdb.connect(self.db_path, read_only=True) as con:
                result = con.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Failed to get applied migrations: {e}")
            return []
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get list of pending migrations."""
        applied = set(self.get_applied_migrations())
        return [m for m in self.migrations if m.version not in applied]
    
    def apply_migration(self, migration: Migration) -> bool:
        """Apply a single migration."""
        logger.info(f"Applying migration {migration.version}: {migration.description}")
        
        try:
            with duckdb.connect(self.db_path) as con:
                # Start transaction
                con.begin()
                
                try:
                    # Execute upgrade SQL
                    for statement in migration.upgrade_sql.strip().split(';'):
                        if statement.strip():
                            con.execute(statement)
                    
                    # Validate migration if validation SQL provided
                    if migration.validation_sql:
                        for statement in migration.validation_sql.strip().split(';'):
                            if statement.strip():
                                con.execute(statement)
                    
                    # Record migration
                    checksum = self._calculate_checksum(migration)
                    con.execute("""
                        INSERT INTO schema_migrations (version, description, checksum)
                        VALUES (?, ?, ?)
                    """, [migration.version, migration.description, checksum])
                    
                    # Commit transaction
                    con.commit()
                    logger.success(f"Migration {migration.version} applied successfully")
                    return True
                    
                except Exception as e:
                    con.rollback()
                    logger.error(f"Migration {migration.version} failed: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to apply migration {migration.version}: {e}")
            return False
    
    def rollback_migration(self, migration: Migration) -> bool:
        """Rollback a single migration."""
        logger.info(f"Rolling back migration {migration.version}: {migration.description}")
        
        try:
            with duckdb.connect(self.db_path) as con:
                # Start transaction
                con.begin()
                
                try:
                    # Execute downgrade SQL
                    for statement in migration.downgrade_sql.strip().split(';'):
                        if statement.strip():
                            con.execute(statement)
                    
                    # Remove migration record
                    con.execute("DELETE FROM schema_migrations WHERE version = ?", [migration.version])
                    
                    # Commit transaction
                    con.commit()
                    logger.success(f"Migration {migration.version} rolled back successfully")
                    return True
                    
                except Exception as e:
                    con.rollback()
                    logger.error(f"Rollback of migration {migration.version} failed: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to rollback migration {migration.version}: {e}")
            return False
    
    def migrate_up(self) -> bool:
        """Apply all pending migrations."""
        pending = self.get_pending_migrations()
        
        if not pending:
            logger.info("No pending migrations")
            return True
        
        logger.info(f"Applying {len(pending)} pending migrations")
        
        for migration in pending:
            if not self.apply_migration(migration):
                logger.error(f"Migration failed at {migration.version}")
                return False
        
        logger.success("All migrations applied successfully")
        return True
    
    def migrate_down(self, target_version: Optional[str] = None) -> bool:
        """Rollback migrations to target version."""
        applied = self.get_applied_migrations()
        
        if not applied:
            logger.info("No migrations to rollback")
            return True
        
        # Find migrations to rollback
        migrations_to_rollback = []
        for version in reversed(applied):
            if target_version and version == target_version:
                break
            
            migration = next((m for m in self.migrations if m.version == version), None)
            if migration:
                migrations_to_rollback.append(migration)
        
        if not migrations_to_rollback:
            logger.info("No migrations to rollback")
            return True
        
        logger.info(f"Rolling back {len(migrations_to_rollback)} migrations")
        
        for migration in migrations_to_rollback:
            if not self.rollback_migration(migration):
                logger.error(f"Rollback failed at {migration.version}")
                return False
        
        logger.success("Migrations rolled back successfully")
        return True
    
    def get_migration_status(self) -> Dict[str, Dict]:
        """Get status of all migrations."""
        applied = set(self.get_applied_migrations())
        status = {}
        
        for migration in self.migrations:
            status[migration.version] = {
                'description': migration.description,
                'applied': migration.version in applied,
                'checksum': self._calculate_checksum(migration)
            }
        
        return status
    
    def validate_migrations(self) -> bool:
        """Validate that applied migrations match expected checksums."""
        logger.info("Validating migration integrity")
        
        try:
            with duckdb.connect(self.db_path, read_only=True) as con:
                applied_migrations = con.execute("""
                    SELECT version, checksum FROM schema_migrations
                """).fetchall()
                
                all_valid = True
                
                for version, stored_checksum in applied_migrations:
                    migration = next((m for m in self.migrations if m.version == version), None)
                    if not migration:
                        logger.error(f"Unknown migration {version} found in database")
                        all_valid = False
                        continue
                    
                    expected_checksum = self._calculate_checksum(migration)
                    if stored_checksum != expected_checksum:
                        logger.error(f"Migration {version} checksum mismatch")
                        all_valid = False
                
                if all_valid:
                    logger.success("Migration validation passed")
                else:
                    logger.error("Migration validation failed")
                
                return all_valid
                
        except Exception as e:
            logger.error(f"Migration validation failed: {e}")
            return False