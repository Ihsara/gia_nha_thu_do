"""
CLI interface for data governance and quality assurance management.

This module provides command-line tools for managing data governance policies,
generating compliance reports, enforcing retention policies, and monitoring
data quality in the automation system.
"""

import json
import click
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from loguru import logger

from .data_governance import DataGovernanceManager, create_data_governance_config
from .governance_integration import GovernanceIntegrationConfig
from ..database.manager import EnhancedDatabaseManager


@click.group()
def governance():
    """Data governance and quality assurance management commands."""
    pass


@governance.command()
@click.option('--config-path', default='config/data_governance.json', 
              help='Path to data governance configuration file')
def init_config(config_path: str):
    """Initialize data governance configuration file."""
    try:
        config_file = create_data_governance_config()
        click.echo(f"✅ Data governance configuration created at {config_file}")
        
        # Display configuration summary
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        click.echo("\n📋 Configuration Summary:")
        click.echo(f"  • API Rate Limits: {len(config['api_rate_limits'])} domains configured")
        click.echo(f"  • Data Quality Thresholds: {len(config['data_quality_thresholds'])} metrics")
        click.echo(f"  • Retention Policy: {config['retention_policies']['default_retention_days']} days")
        click.echo(f"  • Compliance Reporting: {'Enabled' if config['compliance_reporting']['generate_daily_reports'] else 'Disabled'}")
        
    except Exception as e:
        click.echo(f"❌ Failed to initialize configuration: {e}")
        raise click.Abort()


@governance.command()
@click.option('--period-days', default=7, help='Number of days to include in report')
@click.option('--output-format', default='json', type=click.Choice(['json', 'html']),
              help='Output format for the report')
@click.option('--output-path', help='Output path for the report (optional)')
def generate_report(period_days: int, output_format: str, output_path: Optional[str]):
    """Generate comprehensive compliance report."""
    try:
        governance_manager = DataGovernanceManager()
        
        # Calculate report period
        period_end = datetime.now()
        period_start = period_end - timedelta(days=period_days)
        
        click.echo(f"🔄 Generating compliance report for period: {period_start.date()} to {period_end.date()}")
        
        # Generate report
        report = governance_manager.generate_compliance_report(period_start, period_end)
        
        # Determine output path
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"output/compliance/compliance_report_{timestamp}.{output_format}"
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save report
        if output_format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report.__dict__, f, indent=2, ensure_ascii=False, default=str)
        elif output_format == 'html':
            html_content = _generate_html_report(report)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        click.echo(f"✅ Compliance report generated: {output_path}")
        
        # Display summary
        _display_report_summary(report)
        
    except Exception as e:
        click.echo(f"❌ Failed to generate compliance report: {e}")
        raise click.Abort()


@governance.command()
@click.option('--dry-run', is_flag=True, help='Show what would be cleaned up without actually doing it')
@click.option('--table', help='Specific table to clean up (optional)')
def cleanup(dry_run: bool, table: Optional[str]):
    """Enforce retention policies and cleanup old data."""
    try:
        governance_manager = DataGovernanceManager()
        
        if dry_run:
            click.echo("🔍 DRY RUN: Showing what would be cleaned up...")
        else:
            click.echo("🧹 Enforcing retention policies...")
        
        if table:
            click.echo(f"  • Targeting specific table: {table}")
        
        # For dry run, we would need to implement a preview function
        if dry_run:
            click.echo("  • Dry run functionality not yet implemented")
            click.echo("  • Use --help to see available options")
            return
        
        # Enforce retention policies
        cleanup_results = governance_manager.enforce_retention_policies()
        
        click.echo("✅ Retention policy enforcement completed:")
        click.echo(f"  • Tables processed: {cleanup_results['tables_processed']}")
        click.echo(f"  • Records archived: {cleanup_results['records_archived']}")
        click.echo(f"  • Records deleted: {cleanup_results['records_deleted']}")
        
        if cleanup_results['errors']:
            click.echo(f"  • Errors encountered: {len(cleanup_results['errors'])}")
            for error in cleanup_results['errors']:
                click.echo(f"    - {error}")
        
    except Exception as e:
        click.echo(f"❌ Failed to enforce retention policies: {e}")
        raise click.Abort()


@governance.command()
@click.option('--table', default='listings', help='Table to analyze')
@click.option('--limit', default=100, help='Number of recent records to analyze')
def quality_check(table: str, limit: int):
    """Analyze data quality for recent records."""
    try:
        governance_manager = DataGovernanceManager()
        db_manager = EnhancedDatabaseManager()
        
        click.echo(f"🔍 Analyzing data quality for {table} (last {limit} records)...")
        
        # Get recent records
        with db_manager.get_connection() as con:
            if table == 'listings':
                records = con.execute(f"""
                    SELECT url, title, address, price_eur, size_m2, rooms, year_built,
                           data_quality_score, scraped_at
                    FROM {table} 
                    WHERE deleted_ts IS NULL 
                    ORDER BY scraped_at DESC 
                    LIMIT ?
                """, [limit]).fetchall()
            else:
                click.echo(f"❌ Quality analysis not implemented for table: {table}")
                return
        
        if not records:
            click.echo(f"❌ No records found in {table}")
            return
        
        # Analyze quality
        quality_scores = []
        quality_issues = []
        
        for record in records:
            listing_data = {
                'url': record[0],
                'title': record[1],
                'address': record[2],
                'price_eur': record[3],
                'size_m2': record[4],
                'rooms': record[5],
                'year_built': record[6],
                'scraped_at': record[8]
            }
            
            quality_score = governance_manager.calculate_data_quality_score(listing_data)
            quality_scores.append(quality_score.overall_score)
            
            if quality_score.issues:
                quality_issues.extend(quality_score.issues)
        
        # Display results
        avg_quality = sum(quality_scores) / len(quality_scores)
        
        click.echo(f"✅ Quality analysis completed:")
        click.echo(f"  • Records analyzed: {len(records)}")
        click.echo(f"  • Average quality score: {avg_quality:.2f}")
        click.echo(f"  • Quality distribution:")
        
        excellent = sum(1 for score in quality_scores if score >= 0.9)
        good = sum(1 for score in quality_scores if 0.7 <= score < 0.9)
        fair = sum(1 for score in quality_scores if 0.5 <= score < 0.7)
        poor = sum(1 for score in quality_scores if score < 0.5)
        
        click.echo(f"    - Excellent (≥0.9): {excellent} ({excellent/len(quality_scores)*100:.1f}%)")
        click.echo(f"    - Good (0.7-0.89): {good} ({good/len(quality_scores)*100:.1f}%)")
        click.echo(f"    - Fair (0.5-0.69): {fair} ({fair/len(quality_scores)*100:.1f}%)")
        click.echo(f"    - Poor (<0.5): {poor} ({poor/len(quality_scores)*100:.1f}%)")
        
        # Show common issues
        if quality_issues:
            issue_counts = {}
            for issue in quality_issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
            
            click.echo(f"  • Common quality issues:")
            for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                click.echo(f"    - {issue}: {count} occurrences")
        
    except Exception as e:
        click.echo(f"❌ Failed to analyze data quality: {e}")
        raise click.Abort()


@governance.command()
@click.option('--endpoint', help='Specific API endpoint to check (optional)')
@click.option('--hours', default=24, help='Number of hours to analyze')
def api_usage(endpoint: Optional[str], hours: int):
    """Analyze API usage patterns and rate limiting compliance."""
    try:
        db_manager = EnhancedDatabaseManager()
        
        click.echo(f"📊 Analyzing API usage for the last {hours} hours...")
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        with db_manager.get_connection() as con:
            if endpoint:
                # Analyze specific endpoint
                usage_stats = con.execute("""
                    SELECT COUNT(*) as total_calls,
                           AVG(response_time_ms) as avg_response_time,
                           SUM(records_fetched) as total_records,
                           SUM(CASE WHEN response_status >= 400 THEN 1 ELSE 0 END) as error_calls
                    FROM api_usage_log 
                    WHERE api_endpoint = ? AND request_timestamp BETWEEN ? AND ?
                """, [endpoint, start_time, end_time]).fetchone()
                
                if usage_stats and usage_stats[0] > 0:
                    total_calls, avg_response_time, total_records, error_calls = usage_stats
                    error_rate = error_calls / total_calls if total_calls > 0 else 0
                    
                    click.echo(f"✅ API usage analysis for {endpoint}:")
                    click.echo(f"  • Total calls: {total_calls}")
                    click.echo(f"  • Average response time: {avg_response_time:.1f}ms")
                    click.echo(f"  • Total records fetched: {total_records}")
                    click.echo(f"  • Error rate: {error_rate:.1%}")
                else:
                    click.echo(f"❌ No usage data found for {endpoint}")
                
            else:
                # Analyze all endpoints
                endpoint_stats = con.execute("""
                    SELECT api_endpoint,
                           COUNT(*) as total_calls,
                           AVG(response_time_ms) as avg_response_time,
                           SUM(records_fetched) as total_records,
                           SUM(CASE WHEN response_status >= 400 THEN 1 ELSE 0 END) as error_calls
                    FROM api_usage_log 
                    WHERE request_timestamp BETWEEN ? AND ?
                    GROUP BY api_endpoint
                    ORDER BY total_calls DESC
                """, [start_time, end_time]).fetchall()
                
                if endpoint_stats:
                    click.echo("✅ API usage analysis (all endpoints):")
                    click.echo(f"{'Endpoint':<40} {'Calls':<8} {'Avg RT':<8} {'Records':<10} {'Error %':<8}")
                    click.echo("-" * 80)
                    
                    for stats in endpoint_stats:
                        endpoint_name, total_calls, avg_response_time, total_records, error_calls = stats
                        error_rate = error_calls / total_calls if total_calls > 0 else 0
                        
                        # Truncate long endpoint names
                        display_endpoint = endpoint_name[:37] + "..." if len(endpoint_name) > 40 else endpoint_name
                        
                        click.echo(f"{display_endpoint:<40} {total_calls:<8} {avg_response_time:<8.1f} {total_records:<10} {error_rate:<8.1%}")
                else:
                    click.echo("❌ No API usage data found for the specified period")
        
    except Exception as e:
        click.echo(f"❌ Failed to analyze API usage: {e}")
        raise click.Abort()


@governance.command()
def status():
    """Show data governance system status."""
    try:
        governance_manager = DataGovernanceManager()
        db_manager = EnhancedDatabaseManager()
        
        click.echo("📊 Data Governance System Status")
        click.echo("=" * 40)
        
        # Check database tables
        with db_manager.get_connection() as con:
            # Check data_lineage table
            lineage_count = con.execute("SELECT COUNT(*) FROM data_lineage").fetchone()[0]
            click.echo(f"📋 Data Lineage Records: {lineage_count:,}")
            
            # Check api_usage_log table
            api_usage_count = con.execute("SELECT COUNT(*) FROM api_usage_log").fetchone()[0]
            click.echo(f"🌐 API Usage Records: {api_usage_count:,}")
            
            # Check listings with quality scores
            quality_count = con.execute("""
                SELECT COUNT(*) FROM listings 
                WHERE data_quality_score IS NOT NULL AND deleted_ts IS NULL
            """).fetchone()[0]
            click.echo(f"⭐ Listings with Quality Scores: {quality_count:,}")
            
            # Recent activity
            recent_executions = con.execute("""
                SELECT COUNT(*) FROM scraping_executions 
                WHERE started_at > datetime('now', '-7 days')
            """).fetchone()[0]
            click.echo(f"🔄 Recent Executions (7 days): {recent_executions}")
        
        # Check configuration
        config_path = Path("config/data_governance.json")
        if config_path.exists():
            click.echo(f"⚙️  Configuration: {config_path} (exists)")
        else:
            click.echo(f"⚠️  Configuration: {config_path} (missing)")
        
        # Check retention policies
        click.echo(f"🗂️  Retention Policies: {len(governance_manager.retention_policies)} configured")
        
        click.echo("\n✅ Data governance system is operational")
        
    except Exception as e:
        click.echo(f"❌ Failed to get governance system status: {e}")
        raise click.Abort()


def _display_report_summary(report):
    """Display a summary of the compliance report."""
    click.echo("\n📊 Report Summary:")
    click.echo(f"  • Report ID: {report.report_id}")
    click.echo(f"  • Period: {report.period_start.date()} to {report.period_end.date()}")
    
    # API usage summary
    api_summary = report.api_usage_summary
    if 'total_api_calls' in api_summary:
        click.echo(f"  • Total API calls: {api_summary['total_api_calls']:,}")
    
    # Data quality summary
    quality_summary = report.data_quality_summary
    if 'average_quality_score' in quality_summary:
        click.echo(f"  • Average quality score: {quality_summary['average_quality_score']:.2f}")
    
    # Violations
    if report.governance_violations:
        click.echo(f"  • Governance violations: {len(report.governance_violations)}")
        for violation in report.governance_violations:
            severity = violation.get('severity', 'unknown')
            description = violation.get('description', 'Unknown violation')
            click.echo(f"    - {severity.upper()}: {description}")
    else:
        click.echo("  • No governance violations detected ✅")
    
    # Recommendations
    if report.recommendations:
        click.echo(f"  • Recommendations: {len(report.recommendations)}")
        for i, recommendation in enumerate(report.recommendations[:3], 1):
            click.echo(f"    {i}. {recommendation}")
        if len(report.recommendations) > 3:
            click.echo(f"    ... and {len(report.recommendations) - 3} more")


def _generate_html_report(report) -> str:
    """Generate HTML version of compliance report."""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Data Governance Compliance Report</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
            .section { margin: 20px 0; }
            .metric { background-color: #f9f9f9; padding: 10px; margin: 5px 0; border-left: 4px solid #007acc; }
            .violation { background-color: #ffe6e6; padding: 10px; margin: 5px 0; border-left: 4px solid #ff4444; }
            .recommendation { background-color: #e6f3ff; padding: 10px; margin: 5px 0; border-left: 4px solid #0066cc; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Data Governance Compliance Report</h1>
            <p><strong>Report ID:</strong> {report_id}</p>
            <p><strong>Generated:</strong> {generated_at}</p>
            <p><strong>Period:</strong> {period_start} to {period_end}</p>
        </div>
        
        <div class="section">
            <h2>API Usage Summary</h2>
            <div class="metric">
                <strong>Total API Calls:</strong> {total_api_calls}
            </div>
            <!-- Add more API metrics here -->
        </div>
        
        <div class="section">
            <h2>Data Quality Summary</h2>
            <div class="metric">
                <strong>Average Quality Score:</strong> {avg_quality_score:.2f}
            </div>
            <!-- Add more quality metrics here -->
        </div>
        
        <div class="section">
            <h2>Governance Violations</h2>
            {violations_html}
        </div>
        
        <div class="section">
            <h2>Recommendations</h2>
            {recommendations_html}
        </div>
    </body>
    </html>
    """
    
    # Generate violations HTML
    violations_html = ""
    if report.governance_violations:
        for violation in report.governance_violations:
            violations_html += f'<div class="violation"><strong>{violation.get("severity", "").upper()}:</strong> {violation.get("description", "")}</div>'
    else:
        violations_html = '<div class="metric">No governance violations detected ✅</div>'
    
    # Generate recommendations HTML
    recommendations_html = ""
    for recommendation in report.recommendations:
        recommendations_html += f'<div class="recommendation">{recommendation}</div>'
    
    return html_template.format(
        report_id=report.report_id,
        generated_at=report.generated_at.strftime('%Y-%m-%d %H:%M:%S'),
        period_start=report.period_start.strftime('%Y-%m-%d'),
        period_end=report.period_end.strftime('%Y-%m-%d'),
        total_api_calls=report.api_usage_summary.get('total_api_calls', 0),
        avg_quality_score=report.data_quality_summary.get('average_quality_score', 0),
        violations_html=violations_html,
        recommendations_html=recommendations_html
    )


if __name__ == '__main__':
    governance()