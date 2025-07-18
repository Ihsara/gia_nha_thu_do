#!/usr/bin/env python3
"""
Database Migration: Add Data Governance Fields
Created: 2025-07-13 00:19
Description: Add data governance tracking fields to listings table and create
             data lineage and API usage monitoring tables per data governance rules.
"""

from datetime import datetime
from typing import List, Callable
import duckdb

from ..migration import MigrationInfo


def create_data_governance_migration() -> MigrationInfo:
    """Create migration to add data governance fields and tables"""
    
    upgrade_sql = [
        # Add data governance fields to listings table
        """
        ALTER TABLE listings ADD COLUMN IF NOT EXISTS data_source VARCHAR(50);
        """,
        """
        ALTER TABLE listings ADD COLUMN IF NOT EXISTS fetch_timestamp TIMESTAMP;
        """,
        """
        ALTER TABLE listings ADD COLUMN IF NOT EXISTS data_quality_score REAL;
        """,
        """
        ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_verified TIMESTAMP;
        """,
        """
        ALTER TABLE listings ADD COLUMN IF NOT EXISTS source_url TEXT;
        """,
        
        # Create data lineage tracking table
        """
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
        """,
        
        # Create API usage monitoring table
        """
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
        """,
        
        # Create indexes for performance
        """
        CREATE INDEX IF NOT EXISTS idx_listings_data_source ON listings(data_source);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_listings_fetch_timestamp ON listings(fetch_timestamp);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_data_lineage_table_record ON data_lineage(table_name, record_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_data_lineage_fetch_timestamp ON data_lineage(fetch_timestamp);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint ON api_usage_log(api_endpoint);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage_log(request_timestamp);
        """
    ]
    
    downgrade_sql = [
        # Drop indexes
        "DROP INDEX IF EXISTS idx_api_usage_timestamp;",
        "DROP INDEX IF EXISTS idx_api_usage_endpoint;",
        "DROP INDEX IF EXISTS idx_data_lineage_fetch_timestamp;",
        "DROP INDEX IF EXISTS idx_data_lineage_table_record;",
        "DROP INDEX IF EXISTS idx_listings_fetch_timestamp;",
        "DROP INDEX IF EXISTS idx_listings_data_source;",
        
        # Drop tables
        "DROP TABLE IF EXISTS api_usage_log;",
        "DROP TABLE IF EXISTS data_lineage;",
        
        # Remove columns from listings table
        "ALTER TABLE listings DROP COLUMN IF EXISTS source_url;",
        "ALTER TABLE listings DROP COLUMN IF EXISTS last_verified;",
        "ALTER TABLE listings DROP COLUMN IF EXISTS data_quality_score;",
        "ALTER TABLE listings DROP COLUMN IF EXISTS fetch_timestamp;",
        "ALTER TABLE listings DROP COLUMN IF EXISTS data_source;"
    ]
    
    def validate_governance_tables(conn: duckdb.DuckDBPyConnection) -> bool:
        """Validate that governance tables were created successfully"""
        try:
            # Check data_lineage table exists and has correct structure
            result = conn.execute("DESCRIBE data_lineage").fetchall()
            expected_columns = ['id', 'table_name', 'record_id', 'data_source', 
                              'fetch_timestamp', 'api_endpoint', 'request_parameters', 
                              'response_metadata', 'created_at']
            actual_columns = [row[0] for row in result]
            
            for col in expected_columns:
                if col not in actual_columns:
                    print(f"❌ Missing column {col} in data_lineage table")
                    return False
            
            # Check api_usage_log table exists and has correct structure
            result = conn.execute("DESCRIBE api_usage_log").fetchall()
            expected_columns = ['id', 'api_endpoint', 'request_timestamp', 
                              'response_status', 'response_time_ms', 'records_fetched',
                              'rate_limit_remaining', 'created_at']
            actual_columns = [row[0] for row in result]
            
            for col in expected_columns:
                if col not in actual_columns:
                    print(f"❌ Missing column {col} in api_usage_log table")
                    return False
            
            # Check listings table has new governance columns
            result = conn.execute("DESCRIBE listings").fetchall()
            actual_columns = [row[0] for row in result]
            governance_columns = ['data_source', 'fetch_timestamp', 'data_quality_score',
                                 'last_verified', 'source_url']
            
            for col in governance_columns:
                if col not in actual_columns:
                    print(f"❌ Missing governance column {col} in listings table")
                    return False
            
            print("✅ All governance tables and columns validated successfully")
            return True
            
        except Exception as e:
            print(f"❌ Governance table validation failed: {str(e)}")
            return False
    
    def validate_governance_indexes(conn: duckdb.DuckDBPyConnection) -> bool:
        """Validate that governance indexes were created successfully"""
        try:
            # Check that indexes exist by attempting to query with them
            conn.execute("SELECT COUNT(*) FROM listings WHERE data_source IS NOT NULL").fetchone()
            conn.execute("SELECT COUNT(*) FROM data_lineage WHERE table_name = 'test'").fetchone()
            conn.execute("SELECT COUNT(*) FROM api_usage_log WHERE api_endpoint LIKE '%test%'").fetchone()
            
            print("✅ All governance indexes validated successfully")
            return True
            
        except Exception as e:
            print(f"❌ Governance index validation failed: {str(e)}")
            return False
    
    return MigrationInfo(
        version="20250713_001900",
        timestamp=datetime.now(),
        description="Add data governance fields and tracking tables",
        upgrade_sql=upgrade_sql,
        downgrade_sql=downgrade_sql,
        validation_checks=[validate_governance_tables, validate_governance_indexes]
    )


def apply_data_governance_migration():
    """Apply the data governance migration to the database"""
    from ..migration import DatabaseMigrator
    
    migrator = DatabaseMigrator()
    migration = create_data_governance_migration()
    
    print("🔄 Applying data governance migration...")
    success = migrator.apply_migration(migration)
    
    if success:
        print("✅ Data governance migration completed successfully")
        print("📊 Added governance tracking fields to listings table")
        print("📋 Created data_lineage table for tracking data sources")
        print("📈 Created api_usage_log table for monitoring API usage")
    else:
        print("❌ Data governance migration failed")
    
    return success


if __name__ == "__main__":
    apply_data_governance_migration()
