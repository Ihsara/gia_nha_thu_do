"""
Command Line Interface for Status Reporting System

This module provides CLI commands for generating and managing status reports
for the daily scraper automation system.
"""

import json
import click
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from loguru import logger

from .metrics import MetricsCollector
from .reporting import StatusReporter, ReportConfiguration
from ..database.manager import EnhancedDatabaseManager


@click.group()
def status():
    """Status reporting commands for daily scraper automation."""
    pass


@status.command()
@click.option('--cities', '-c', multiple=True, help='Cities to include in report (default: all)')
@click.option('--date', '-d', help='Report date (YYYY-MM-DD, default: today)')
@click.option('--output-dir', '-o', default='output/reports', help='Output directory for reports')
@click.option('--format', '-f', multiple=True, default=['json', 'html'], 
              type=click.Choice(['json', 'html', 'email']), help='Output formats')
@click.option('--email', is_flag=True, help='Send report via email (requires configuration)')
@click.option('--historical-days', default=30, help='Days of historical data to include')
@click.option('--config-file', help='Path to report configuration file')
def generate(cities: tuple, date: str, output_dir: str, format: tuple, email: bool, 
             historical_days: int, config_file: str):
    """Generate comprehensive daily status report."""
    try:
        # Parse date
        if date:
            report_date = datetime.strptime(date, '%Y-%m-%d')
        else:
            report_date = datetime.now()
        
        # Load configuration
        config = _load_report_config(config_file, output_dir, historical_days, email)
        
        # Initialize components
        db_manager = EnhancedDatabaseManager()
        metrics_collector = MetricsCollector(db_manager)
        reporter = StatusReporter(metrics_collector, db_manager, config)
        
        # Get cities to process
        if cities:
            city_list = list(cities)
        else:
            city_list = _get_all_cities(db_manager)
        
        if not city_list:
            click.echo("No cities found to process")
            return
        
        click.echo(f"Generating report for {len(city_list)} cities: {', '.join(city_list)}")
        
        # Generate and export report
        exported_files = reporter.generate_and_export_all_formats(city_list, report_date)
        
        # Display results
        click.echo("\nReport generation completed:")
        for format_name, file_path in exported_files.items():
            if format_name == 'email':
                status = "✅ Sent" if file_path == 'sent' else "❌ Failed"
                click.echo(f"  Email: {status}")
            else:
                click.echo(f"  {format_name.upper()}: {file_path}")
        
        logger.success(f"Status report generated successfully for {report_date.strftime('%Y-%m-%d')}")
        
    except Exception as e:
        click.echo(f"Error generating report: {e}", err=True)
        logger.error(f"Report generation failed: {e}")


@status.command()
@click.option('--city', '-c', help='City to analyze (default: all cities)')
@click.option('--days', '-d', default=7, help='Number of days to analyze')
@click.option('--format', '-f', default='table', type=click.Choice(['table', 'json']), 
              help='Output format')
def metrics(city: str, days: int, format: str):
    """Display execution metrics and trends."""
    try:
        db_manager = EnhancedDatabaseManager()
        metrics_collector = MetricsCollector(db_manager)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        if city:
            cities = [city]
        else:
            cities = _get_all_cities(db_manager)
        
        if format == 'json':
            results = {}
            for city_name in cities:
                trends = metrics_collector.get_historical_trends(city_name, days)
                results[city_name] = trends
            click.echo(json.dumps(results, indent=2, default=str))
        else:
            # Display table format
            click.echo(f"\nExecution Metrics ({days} days)")
            click.echo("=" * 60)
            
            for city_name in cities:
                executions = db_manager.get_execution_history(city_name, start_date, end_date)
                if executions:
                    click.echo(f"\n{city_name}:")
                    click.echo(f"  Executions: {len(executions)}")
                    
                    # Calculate averages
                    avg_success = sum(e.get('success_rate', 0) for e in executions) / len(executions)
                    avg_time = sum(e.get('execution_time_seconds', 0) for e in executions) / len(executions)
                    total_processed = sum(e.get('listings_processed', 0) for e in executions)
                    
                    click.echo(f"  Average Success Rate: {avg_success:.1%}")
                    click.echo(f"  Average Execution Time: {avg_time:.1f}s")
                    click.echo(f"  Total Listings Processed: {total_processed}")
                else:
                    click.echo(f"\n{city_name}: No recent executions")
        
    except Exception as e:
        click.echo(f"Error retrieving metrics: {e}", err=True)
        logger.error(f"Metrics retrieval failed: {e}")


@status.command()
@click.option('--city', '-c', help='City to analyze (default: all cities)')
@click.option('--threshold', '-t', default=0.9, help='Data quality threshold (0.0-1.0)')
def quality(city: str, threshold: float):
    """Analyze data quality metrics."""
    try:
        db_manager = EnhancedDatabaseManager()
        
        if city:
            cities = [city]
        else:
            cities = _get_all_cities(db_manager)
        
        click.echo(f"\nData Quality Analysis (threshold: {threshold:.1%})")
        click.echo("=" * 60)
        
        for city_name in cities:
            # Get latest execution for the city
            latest_execution = db_manager.get_latest_execution(city_name, datetime.now())
            if not latest_execution:
                click.echo(f"\n{city_name}: No execution data available")
                continue
            
            # Get data quality metrics
            quality_data = db_manager.get_data_quality_metrics(city_name, latest_execution['execution_id'])
            
            total = quality_data.get('total_addresses', 0)
            if total == 0:
                click.echo(f"\n{city_name}: No data available")
                continue
            
            geocoding_rate = quality_data.get('geocoded_addresses', 0) / total
            completeness_rate = quality_data.get('complete_listings', 0) / total
            
            # Status indicators
            geocoding_status = "✅" if geocoding_rate >= threshold else "⚠️" if geocoding_rate >= threshold * 0.8 else "❌"
            completeness_status = "✅" if completeness_rate >= threshold else "⚠️" if completeness_rate >= threshold * 0.8 else "❌"
            
            click.echo(f"\n{city_name}:")
            click.echo(f"  Total Listings: {total}")
            click.echo(f"  Geocoding Success: {geocoding_status} {geocoding_rate:.1%}")
            click.echo(f"  Data Completeness: {completeness_status} {completeness_rate:.1%}")
            click.echo(f"  Duplicates: {quality_data.get('duplicate_listings', 0)}")
        
    except Exception as e:
        click.echo(f"Error analyzing data quality: {e}", err=True)
        logger.error(f"Data quality analysis failed: {e}")


@status.command()
@click.option('--city', '-c', help='City to check (default: all cities)')
@click.option('--hours', '-h', default=24, help='Hours since last execution to consider stale')
def health(city: str, hours: int):
    """Check system health and recent execution status."""
    try:
        db_manager = EnhancedDatabaseManager()
        
        if city:
            cities = [city]
        else:
            cities = _get_all_cities(db_manager)
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        click.echo(f"\nSystem Health Check (last {hours} hours)")
        click.echo("=" * 60)
        
        healthy_count = 0
        warning_count = 0
        critical_count = 0
        
        for city_name in cities:
            latest_execution = db_manager.get_latest_execution(city_name, datetime.now())
            
            if not latest_execution:
                click.echo(f"{city_name}: ❌ No execution data")
                critical_count += 1
                continue
            
            started_at = latest_execution.get('started_at')
            status = latest_execution.get('status', 'unknown')
            success_rate = 0
            
            processed = latest_execution.get('listings_processed', 0)
            failed = latest_execution.get('listings_failed', 0)
            if processed > 0:
                success_rate = (processed - failed) / processed
            
            # Determine health status
            if started_at and started_at < cutoff_time:
                health_status = "⚠️ Stale"
                warning_count += 1
            elif status == 'failed':
                health_status = "❌ Failed"
                critical_count += 1
            elif success_rate < 0.8:
                health_status = "⚠️ Low Success"
                warning_count += 1
            else:
                health_status = "✅ Healthy"
                healthy_count += 1
            
            execution_time = latest_execution.get('execution_time_seconds', 0)
            click.echo(f"{city_name}: {health_status} "
                      f"({success_rate:.1%} success, {execution_time}s, {status})")
        
        # Overall summary
        total_cities = len(cities)
        click.echo(f"\nOverall Status:")
        click.echo(f"  ✅ Healthy: {healthy_count}/{total_cities}")
        click.echo(f"  ⚠️ Warning: {warning_count}/{total_cities}")
        click.echo(f"  ❌ Critical: {critical_count}/{total_cities}")
        
        if critical_count > 0:
            click.echo("\n⚠️ Critical issues detected - immediate attention required")
        elif warning_count > 0:
            click.echo("\n⚠️ Some issues detected - monitoring recommended")
        else:
            click.echo("\n✅ All systems operating normally")
        
    except Exception as e:
        click.echo(f"Error checking system health: {e}", err=True)
        logger.error(f"Health check failed: {e}")


@status.command()
@click.option('--days', '-d', default=90, help='Retention period in days')
@click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually deleting')
def cleanup(days: int, dry_run: bool):
    """Clean up old execution data and logs."""
    try:
        db_manager = EnhancedDatabaseManager()
        
        if dry_run:
            click.echo(f"DRY RUN: Would clean up data older than {days} days")
            # In a real implementation, this would show what would be deleted
            click.echo("This would remove old execution records, API logs, and lineage data")
        else:
            click.echo(f"Cleaning up data older than {days} days...")
            cleanup_stats = db_manager.cleanup_old_data(days)
            
            click.echo("Cleanup completed:")
            for key, value in cleanup_stats.items():
                if key != 'error':
                    click.echo(f"  {key}: {value}")
            
            if 'error' in cleanup_stats:
                click.echo(f"Error during cleanup: {cleanup_stats['error']}", err=True)
        
    except Exception as e:
        click.echo(f"Error during cleanup: {e}", err=True)
        logger.error(f"Cleanup failed: {e}")


def _load_report_config(config_file: Optional[str], output_dir: str, 
                       historical_days: int, email_enabled: bool) -> ReportConfiguration:
    """Load report configuration from file or create default."""
    if config_file and Path(config_file).exists():
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            return ReportConfiguration(
                output_directory=config_data.get('output_directory', output_dir),
                include_historical_trends=config_data.get('include_historical_trends', True),
                historical_days=config_data.get('historical_days', historical_days),
                include_performance_charts=config_data.get('include_performance_charts', True),
                include_error_analysis=config_data.get('include_error_analysis', True),
                email_enabled=config_data.get('email_enabled', email_enabled),
                email_recipients=config_data.get('email_recipients', []),
                email_smtp_server=config_data.get('email_smtp_server', ''),
                email_smtp_port=config_data.get('email_smtp_port', 587),
                email_username=config_data.get('email_username', ''),
                email_password=config_data.get('email_password', '')
            )
        except Exception as e:
            logger.warning(f"Failed to load config file {config_file}: {e}")
    
    return ReportConfiguration(
        output_directory=output_dir,
        historical_days=historical_days,
        email_enabled=email_enabled
    )


def _get_all_cities(db_manager: EnhancedDatabaseManager) -> List[str]:
    """Get list of all cities with execution data."""
    try:
        import duckdb
        with duckdb.connect(str(db_manager.db_path), read_only=True) as con:
            result = con.execute("""
                SELECT DISTINCT city FROM scraping_executions 
                WHERE city IS NOT NULL 
                ORDER BY city
            """).fetchall()
            
            return [row[0] for row in result]
    except Exception as e:
        logger.error(f"Failed to get cities list: {e}")
        return []


if __name__ == '__main__':
    status()