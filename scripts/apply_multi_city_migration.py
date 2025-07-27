#!/usr/bin/env python3
"""
Standalone Multi-City Database Migration Script

This script applies all necessary database schema changes to support
multi-city operations for the Oikotie Real Estate Analytics Platform.

Usage:
    uv run python scripts/apply_multi_city_migration.py [--dry-run] [--backup]
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from oikotie.database.multi_city_migration import MultiCityMigrationManager
from oikotie.database.coordinate_validation import CoordinateValidator
from loguru import logger


def create_backup(db_path: str) -> str:
    """Create a backup of the database before migration"""
    import shutil
    
    db_path = Path(db_path)
    if not db_path.exists():
        logger.warning(f"Database file not found: {db_path}")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("backups/database")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    backup_path = backup_dir / f"real_estate_backup_multi_city_migration_{timestamp}.duckdb"
    shutil.copy2(db_path, backup_path)
    
    logger.info(f"Database backup created: {backup_path}")
    return str(backup_path)


def validate_prerequisites() -> bool:
    """Validate prerequisites for migration"""
    logger.info("Validating migration prerequisites")
    
    # Check if database file exists
    db_path = Path("data/real_estate.duckdb")
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        logger.info("Please ensure the database exists before running migration")
        return False
    
    # Check if we can connect to database
    try:
        import duckdb
        with duckdb.connect(str(db_path), read_only=True) as con:
            # Check if listings table exists
            tables = con.execute("SHOW TABLES").fetchall()
            table_names = [table[0] for table in tables]
            
            if 'listings' not in table_names:
                logger.error("Listings table not found in database")
                return False
            
            # Check if we have some data
            count = con.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            logger.info(f"Found {count} listings in database")
            
    except Exception as e:
        logger.error(f"Failed to validate database: {e}")
        return False
    
    logger.success("Prerequisites validation passed")
    return True


def run_dry_run() -> bool:
    """Run a dry-run to show what would be changed"""
    logger.info("Running dry-run migration analysis")
    
    try:
        migrator = MultiCityMigrationManager()
        
        # Show current migration status
        status = migrator.get_migration_status()
        logger.info("Current migration status:")
        for version, info in status.items():
            status_text = "✅ Applied" if info['applied'] else "⏳ Pending"
            logger.info(f"  {version}: {info['description']} - {status_text}")
        
        # Show pending multi-city migrations
        pending = [m for m in migrator.multi_city_migrations 
                  if not status.get(m.version, {}).get('applied', False)]
        
        if pending:
            logger.info(f"\nWould apply {len(pending)} multi-city migrations:")
            for migration in pending:
                logger.info(f"  - {migration.version}: {migration.description}")
        else:
            logger.info("No pending multi-city migrations")
        
        # Show coordinate validation status
        validator = CoordinateValidator()
        summary = validator.get_validation_summary()
        
        if summary:
            logger.info("\nCurrent coordinate validation status:")
            for city, stats in summary.items():
                logger.info(f"  {city}: {stats['total_listings']} listings, "
                          f"{stats['validation_rate']:.1f}% validated")
        
        return True
        
    except Exception as e:
        logger.error(f"Dry-run failed: {e}")
        return False


def apply_migration(create_backup_flag: bool = True) -> bool:
    """Apply the multi-city migration"""
    logger.info("Starting multi-city database migration")
    
    try:
        # Create backup if requested
        backup_path = None
        if create_backup_flag:
            backup_path = create_backup("data/real_estate.duckdb")
            if backup_path:
                logger.info(f"Backup created at: {backup_path}")
        
        # Initialize migration manager
        migrator = MultiCityMigrationManager()
        
        # Apply migrations
        logger.info("Applying multi-city database schema enhancements...")
        success = migrator.apply_multi_city_migrations()
        
        if not success:
            logger.error("Migration failed")
            if backup_path:
                logger.info(f"You can restore from backup: {backup_path}")
            return False
        
        logger.success("Multi-city schema migrations applied successfully")
        
        # Update coordinate validation
        logger.info("Updating coordinate validation for existing listings...")
        validator = CoordinateValidator()
        stats = validator.update_database_validation()
        
        logger.info(f"Coordinate validation completed:")
        logger.info(f"  - Total processed: {stats['total_processed']}")
        logger.info(f"  - Valid coordinates: {stats['valid_coordinates']}")
        logger.info(f"  - Invalid coordinates: {stats['invalid_coordinates']}")
        logger.info(f"  - Validation errors: {stats['error_coordinates']}")
        
        # Show final statistics
        city_stats = migrator.get_city_statistics()
        logger.info("\nFinal city statistics:")
        for city, city_data in city_stats.items():
            logger.info(f"  {city}:")
            logger.info(f"    - Total listings: {city_data['total_listings']:,}")
            logger.info(f"    - Validated: {city_data['validated_listings']:,} ({city_data['validation_rate']:.1f}%)")
            logger.info(f"    - With coordinates: {city_data['with_coordinates']:,} ({city_data['coordinate_rate']:.1f}%)")
            logger.info(f"    - Avg quality score: {city_data['avg_quality_score']:.3f}")
        
        # Create validation report
        logger.info("Creating validation report...")
        report_content = validator.create_validation_report()
        logger.info("Validation report created")
        
        # Validate schema integrity
        logger.info("Validating schema integrity...")
        schema_validator = DatabaseSchema()
        if not schema_validator.validate_schema():
            logger.warning("Schema validation found some issues, but migration completed")
        else:
            logger.success("Schema validation passed")
        
        # Test coordinate validation functionality
        logger.info("Testing coordinate validation functionality...")
        test_results = []
        
        # Test valid coordinates
        helsinki_test = validator.validate_coordinates('Helsinki', 60.1699, 24.9384)
        test_results.append(('Helsinki valid coords', helsinki_test.is_valid))
        
        espoo_test = validator.validate_coordinates('Espoo', 60.2055, 24.6559)
        test_results.append(('Espoo valid coords', espoo_test.is_valid))
        
        # Test invalid coordinates
        invalid_test = validator.validate_coordinates('Helsinki', 70.0, 30.0)
        test_results.append(('Invalid coords rejection', not invalid_test.is_valid))
        
        # Test unsupported city
        unsupported_test = validator.validate_coordinates('Tampere', 61.4978, 23.7610)
        test_results.append(('Unsupported city rejection', not unsupported_test.is_valid))
        
        # Report test results
        all_tests_passed = all(result for _, result in test_results)
        if all_tests_passed:
            logger.success("All coordinate validation tests passed")
        else:
            logger.warning("Some coordinate validation tests failed:")
            for test_name, result in test_results:
                status = "✅" if result else "❌"
                logger.info(f"  {status} {test_name}")
        
        logger.success("Multi-city database migration completed successfully!")
        
        if backup_path:
            logger.info(f"Backup available at: {backup_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        return False


def main():
    """Main migration script entry point"""
    parser = argparse.ArgumentParser(
        description="Apply multi-city database schema migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run dry-run to see what would be changed
    uv run python scripts/apply_multi_city_migration.py --dry-run
    
    # Apply migration with backup
    uv run python scripts/apply_multi_city_migration.py --backup
    
    # Apply migration without backup
    uv run python scripts/apply_multi_city_migration.py --no-backup
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without applying migration'
    )
    
    parser.add_argument(
        '--backup',
        action='store_true',
        default=True,
        help='Create backup before migration (default: True)'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip backup creation'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Add file logging
    log_file = f"logs/multi_city_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    Path("logs").mkdir(exist_ok=True)
    logger.add(log_file, level="DEBUG")
    
    logger.info("Multi-City Database Migration Script")
    logger.info("=" * 50)
    
    # Validate prerequisites
    if not validate_prerequisites():
        logger.error("Prerequisites validation failed")
        return 1
    
    # Handle dry-run
    if args.dry_run:
        if run_dry_run():
            logger.info("Dry-run completed successfully")
            return 0
        else:
            logger.error("Dry-run failed")
            return 1
    
    # Determine backup flag
    create_backup_flag = args.backup and not args.no_backup
    
    # Apply migration
    if apply_migration(create_backup_flag):
        logger.success("Migration completed successfully")
        return 0
    else:
        logger.error("Migration failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())