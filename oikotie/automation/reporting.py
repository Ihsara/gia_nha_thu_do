"""
Status Reporting System for Daily Scraper Automation

This module provides comprehensive status reporting with multiple output formats,
historical trend analysis, error categorization, and actionable troubleshooting
information for the daily scraper automation system.
"""

import json
import smtplib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template, Environment, FileSystemLoader
from loguru import logger

from .metrics import (
    MetricsCollector, ExecutionMetrics, PerformanceMetrics, 
    DataQualityMetrics, ErrorMetrics
)
from ..database.manager import EnhancedDatabaseManager


@dataclass
class ReportConfiguration:
    """Configuration for report generation."""
    output_directory: str = "output/reports"
    include_historical_trends: bool = True
    historical_days: int = 30
    include_performance_charts: bool = True
    include_error_analysis: bool = True
    email_enabled: bool = False
    email_recipients: List[str] = None
    email_smtp_server: str = ""
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    
    def __post_init__(self):
        if self.email_recipients is None:
            self.email_recipients = []


@dataclass
class CityReport:
    """Report data for a single city."""
    city: str
    execution_metrics: ExecutionMetrics
    performance_metrics: Optional[PerformanceMetrics] = None
    data_quality_metrics: Optional[DataQualityMetrics] = None
    error_metrics: Optional[ErrorMetrics] = None
    historical_trends: Optional[Dict[str, List[Any]]] = None
    
    def get_status_summary(self) -> str:
        """Get a brief status summary."""
        if self.execution_metrics.status == "completed":
            if self.execution_metrics.error_rate < 0.05:  # Less than 5% errors
                return "✅ Healthy"
            elif self.execution_metrics.error_rate < 0.15:  # Less than 15% errors
                return "⚠️ Warning"
            else:
                return "❌ Critical"
        elif self.execution_metrics.status == "failed":
            return "❌ Failed"
        else:
            return "🔄 Running"
    
    def get_key_metrics(self) -> Dict[str, Any]:
        """Get key metrics for summary display."""
        return {
            'status': self.get_status_summary(),
            'listings_processed': self.execution_metrics.urls_processed,
            'success_rate': f"{self.execution_metrics.success_rate:.1%}",
            'execution_time': f"{self.execution_metrics.duration_seconds or 0:.1f}s",
            'data_quality': f"{self.data_quality_metrics.completeness_score:.1%}" if self.data_quality_metrics else "N/A"
        }


@dataclass
class DailyReport:
    """Comprehensive daily report."""
    report_date: datetime
    city_reports: List[CityReport]
    overall_summary: Dict[str, Any]
    system_health: Dict[str, Any]
    recommendations: List[str]
    
    def get_overall_status(self) -> str:
        """Get overall system status."""
        if not self.city_reports:
            return "❌ No Data"
        
        statuses = [report.get_status_summary() for report in self.city_reports]
        
        if all("✅" in status for status in statuses):
            return "✅ All Systems Healthy"
        elif any("❌" in status for status in statuses):
            return "❌ Issues Detected"
        else:
            return "⚠️ Some Warnings"


class StatusReporter:
    """Comprehensive status reporting system."""
    
    def __init__(self, 
                 metrics_collector: MetricsCollector,
                 db_manager: Optional[EnhancedDatabaseManager] = None,
                 config: Optional[ReportConfiguration] = None):
        """
        Initialize status reporter.
        
        Args:
            metrics_collector: Metrics collector instance
            db_manager: Enhanced database manager
            config: Report configuration
        """
        self.metrics_collector = metrics_collector
        self.db_manager = db_manager or EnhancedDatabaseManager()
        self.config = config or ReportConfiguration()
        
        # Ensure output directory exists
        Path(self.config.output_directory).mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment for templates
        self.template_env = Environment(
            loader=FileSystemLoader(Path(__file__).parent / "templates"),
            autoescape=True
        )
        
        logger.info("Status reporter initialized")
    
    def generate_daily_report(self, cities: List[str], report_date: Optional[datetime] = None) -> DailyReport:
        """
        Generate comprehensive daily status report.
        
        Args:
            cities: List of cities to include in report
            report_date: Date for the report (defaults to today)
            
        Returns:
            DailyReport with comprehensive status information
        """
        if report_date is None:
            report_date = datetime.now()
        
        logger.info(f"Generating daily report for {len(cities)} cities")
        
        # Collect city reports
        city_reports = []
        for city in cities:
            try:
                city_report = self._generate_city_report(city, report_date)
                if city_report:
                    city_reports.append(city_report)
            except Exception as e:
                logger.error(f"Failed to generate report for {city}: {e}")
        
        # Generate overall summary
        overall_summary = self._generate_overall_summary(city_reports)
        
        # Assess system health
        system_health = self._assess_system_health(city_reports)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(city_reports, system_health)
        
        report = DailyReport(
            report_date=report_date,
            city_reports=city_reports,
            overall_summary=overall_summary,
            system_health=system_health,
            recommendations=recommendations
        )
        
        logger.success(f"Generated daily report with {len(city_reports)} city reports")
        return report
    
    def _generate_city_report(self, city: str, report_date: datetime) -> Optional[CityReport]:
        """
        Generate report for a single city.
        
        Args:
            city: City name
            report_date: Report date
            
        Returns:
            CityReport or None if no data available
        """
        try:
            # Get latest execution for the city
            latest_execution = self.db_manager.get_latest_execution(city, report_date)
            if not latest_execution:
                logger.warning(f"No execution data found for {city}")
                return None
            
            # Create execution metrics from database data
            execution_metrics = ExecutionMetrics(
                execution_id=latest_execution.get('execution_id', ''),
                city=city,
                started_at=latest_execution.get('started_at', report_date),
                completed_at=latest_execution.get('completed_at'),
                status=latest_execution.get('status', 'unknown'),
                total_urls_discovered=latest_execution.get('total_urls_discovered', 0),
                urls_processed=latest_execution.get('listings_processed', 0),
                listings_new=latest_execution.get('listings_new', 0),
                listings_updated=latest_execution.get('listings_updated', 0),
                listings_skipped=latest_execution.get('listings_skipped', 0),
                listings_failed=latest_execution.get('listings_failed', 0)
            )
            execution_metrics.calculate_derived_metrics()
            
            # Collect additional metrics
            data_quality_metrics = self.metrics_collector.collect_data_quality_metrics(
                execution_metrics.execution_id, city
            )
            
            # Get historical trends if enabled
            historical_trends = None
            if self.config.include_historical_trends:
                historical_trends = self.metrics_collector.get_historical_trends(
                    city, self.config.historical_days
                )
            
            # Get error metrics from logs
            error_logs = self.db_manager.get_execution_errors(execution_metrics.execution_id)
            error_metrics = self.metrics_collector.collect_error_metrics(
                execution_metrics.execution_id, error_logs
            )
            
            return CityReport(
                city=city,
                execution_metrics=execution_metrics,
                data_quality_metrics=data_quality_metrics,
                error_metrics=error_metrics,
                historical_trends=historical_trends
            )
            
        except Exception as e:
            logger.error(f"Failed to generate city report for {city}: {e}")
            return None
    
    def _generate_overall_summary(self, city_reports: List[CityReport]) -> Dict[str, Any]:
        """
        Generate overall summary statistics.
        
        Args:
            city_reports: List of city reports
            
        Returns:
            Dictionary with overall summary statistics
        """
        if not city_reports:
            return {}
        
        total_listings = sum(report.execution_metrics.urls_processed for report in city_reports)
        total_new = sum(report.execution_metrics.listings_new for report in city_reports)
        total_failed = sum(report.execution_metrics.listings_failed for report in city_reports)
        
        avg_success_rate = sum(report.execution_metrics.success_rate for report in city_reports) / len(city_reports)
        avg_execution_time = sum(report.execution_metrics.duration_seconds or 0 for report in city_reports) / len(city_reports)
        
        # Data quality summary
        quality_reports = [r for r in city_reports if r.data_quality_metrics]
        avg_data_quality = 0.0
        if quality_reports:
            avg_data_quality = sum(r.data_quality_metrics.completeness_score for r in quality_reports) / len(quality_reports)
        
        return {
            'total_cities': len(city_reports),
            'total_listings_processed': total_listings,
            'total_new_listings': total_new,
            'total_failed_listings': total_failed,
            'average_success_rate': avg_success_rate,
            'average_execution_time_seconds': avg_execution_time,
            'average_data_quality_score': avg_data_quality,
            'healthy_cities': len([r for r in city_reports if "✅" in r.get_status_summary()]),
            'warning_cities': len([r for r in city_reports if "⚠️" in r.get_status_summary()]),
            'critical_cities': len([r for r in city_reports if "❌" in r.get_status_summary()])
        }
    
    def _assess_system_health(self, city_reports: List[CityReport]) -> Dict[str, Any]:
        """
        Assess overall system health.
        
        Args:
            city_reports: List of city reports
            
        Returns:
            Dictionary with system health assessment
        """
        health_score = 100.0
        issues = []
        
        if not city_reports:
            return {'score': 0, 'status': 'No Data', 'issues': ['No execution data available']}
        
        # Check success rates
        low_success_cities = [r for r in city_reports if r.execution_metrics.success_rate < 0.8]
        if low_success_cities:
            health_score -= len(low_success_cities) * 10
            issues.append(f"{len(low_success_cities)} cities with low success rates")
        
        # Check data quality
        quality_reports = [r for r in city_reports if r.data_quality_metrics]
        low_quality_cities = [r for r in quality_reports if r.data_quality_metrics.completeness_score < 0.9]
        if low_quality_cities:
            health_score -= len(low_quality_cities) * 5
            issues.append(f"{len(low_quality_cities)} cities with data quality issues")
        
        # Check error rates
        high_error_cities = [r for r in city_reports if r.execution_metrics.error_rate > 0.1]
        if high_error_cities:
            health_score -= len(high_error_cities) * 15
            issues.append(f"{len(high_error_cities)} cities with high error rates")
        
        # Determine status
        if health_score >= 90:
            status = "Excellent"
        elif health_score >= 75:
            status = "Good"
        elif health_score >= 60:
            status = "Fair"
        else:
            status = "Poor"
        
        return {
            'score': max(0, health_score),
            'status': status,
            'issues': issues
        }
    
    def _generate_recommendations(self, city_reports: List[CityReport], system_health: Dict[str, Any]) -> List[str]:
        """
        Generate actionable recommendations based on report data.
        
        Args:
            city_reports: List of city reports
            system_health: System health assessment
            
        Returns:
            List of actionable recommendations
        """
        recommendations = []
        
        # Performance recommendations
        slow_cities = [r for r in city_reports if (r.execution_metrics.duration_seconds or 0) > 3600]  # > 1 hour
        if slow_cities:
            recommendations.append(
                f"Consider optimizing scraping for {len(slow_cities)} slow cities: "
                f"{', '.join(r.city for r in slow_cities[:3])}"
            )
        
        # Error rate recommendations
        error_cities = [r for r in city_reports if r.execution_metrics.error_rate > 0.1]
        if error_cities:
            recommendations.append(
                f"Investigate high error rates in {len(error_cities)} cities. "
                f"Check network connectivity and website changes."
            )
        
        # Data quality recommendations
        quality_reports = [r for r in city_reports if r.data_quality_metrics]
        geocoding_issues = [r for r in quality_reports if r.data_quality_metrics.geocoding_success_rate < 0.9]
        if geocoding_issues:
            recommendations.append(
                f"Address geocoding issues in {len(geocoding_issues)} cities. "
                f"Consider updating address parsing logic."
            )
        
        # System health recommendations
        if system_health.get('score', 0) < 75:
            recommendations.append(
                "Overall system health is below optimal. Review error logs and consider "
                "increasing monitoring frequency."
            )
        
        # Resource recommendations
        high_memory_cities = []  # Would need performance metrics to determine
        if high_memory_cities:
            recommendations.append(
                "Monitor memory usage - some executions may benefit from resource optimization."
            )
        
        if not recommendations:
            recommendations.append("System is operating within normal parameters. Continue monitoring.")
        
        return recommendations
    
    def export_report_json(self, report: DailyReport, filename: Optional[str] = None) -> str:
        """
        Export report as JSON file.
        
        Args:
            report: Daily report to export
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to exported file
        """
        if filename is None:
            filename = f"daily_report_{report.report_date.strftime('%Y%m%d')}.json"
        
        filepath = Path(self.config.output_directory) / filename
        
        # Convert report to serializable format
        report_data = {
            'report_date': report.report_date.isoformat(),
            'overall_status': report.get_overall_status(),
            'overall_summary': report.overall_summary,
            'system_health': report.system_health,
            'recommendations': report.recommendations,
            'city_reports': []
        }
        
        for city_report in report.city_reports:
            city_data = {
                'city': city_report.city,
                'status_summary': city_report.get_status_summary(),
                'key_metrics': city_report.get_key_metrics(),
                'execution_metrics': asdict(city_report.execution_metrics),
                'data_quality_metrics': asdict(city_report.data_quality_metrics) if city_report.data_quality_metrics else None,
                'error_metrics': asdict(city_report.error_metrics) if city_report.error_metrics else None,
                'historical_trends': city_report.historical_trends
            }
            report_data['city_reports'].append(city_data)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, default=str)
            
            logger.info(f"Exported JSON report to {filepath}")
            return str(filepath)
        except (PermissionError, OSError, IOError) as e:
            logger.error(f"Failed to export JSON report to {filepath}: {e}")
            # Try alternative location
            alt_filepath = Path.cwd() / f"report_backup_{report.report_date.strftime('%Y%m%d_%H%M%S')}.json"
            try:
                with open(alt_filepath, 'w', encoding='utf-8') as f:
                    json.dump(report_data, f, indent=2, default=str)
                logger.warning(f"Exported JSON report to backup location: {alt_filepath}")
                return str(alt_filepath)
            except Exception as backup_error:
                logger.error(f"Failed to export to backup location: {backup_error}")
                return f"export_failed_{filepath.name}"
    
    def export_report_html(self, report: DailyReport, filename: Optional[str] = None) -> str:
        """
        Export report as HTML file.
        
        Args:
            report: Daily report to export
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to exported file
        """
        if filename is None:
            filename = f"daily_report_{report.report_date.strftime('%Y%m%d')}.html"
        
        filepath = Path(self.config.output_directory) / filename
        
        # Create HTML template
        html_template = self._get_html_template()
        
        # Render template
        html_content = html_template.render(
            report=report,
            report_date=report.report_date.strftime('%Y-%m-%d'),
            generation_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Exported HTML report to {filepath}")
            return str(filepath)
        except (PermissionError, OSError, IOError) as e:
            logger.error(f"Failed to export HTML report to {filepath}: {e}")
            # Try alternative location
            alt_filepath = Path.cwd() / f"report_backup_{report.report_date.strftime('%Y%m%d_%H%M%S')}.html"
            try:
                with open(alt_filepath, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.warning(f"Exported HTML report to backup location: {alt_filepath}")
                return str(alt_filepath)
            except Exception as backup_error:
                logger.error(f"Failed to export to backup location: {backup_error}")
                return f"export_failed_{filepath.name}"
    
    def _get_html_template(self) -> Template:
        """Get HTML template for report generation."""
        template_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Scraper Report - {{ report_date }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .status-badge { padding: 4px 8px; border-radius: 4px; font-weight: bold; }
        .status-healthy { background-color: #d4edda; color: #155724; }
        .status-warning { background-color: #fff3cd; color: #856404; }
        .status-critical { background-color: #f8d7da; color: #721c24; }
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .summary-card { background: #f8f9fa; padding: 15px; border-radius: 6px; text-align: center; }
        .summary-card h3 { margin: 0 0 10px 0; color: #495057; }
        .summary-card .value { font-size: 24px; font-weight: bold; color: #007bff; }
        .city-reports { margin-top: 30px; }
        .city-card { background: white; border: 1px solid #dee2e6; border-radius: 6px; margin-bottom: 20px; overflow: hidden; }
        .city-header { background: #f8f9fa; padding: 15px; border-bottom: 1px solid #dee2e6; }
        .city-content { padding: 15px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; }
        .metric { text-align: center; }
        .metric-label { font-size: 12px; color: #6c757d; text-transform: uppercase; }
        .metric-value { font-size: 18px; font-weight: bold; color: #495057; }
        .recommendations { background: #e7f3ff; padding: 20px; border-radius: 6px; margin-top: 30px; }
        .recommendations h3 { margin-top: 0; color: #0056b3; }
        .recommendations ul { margin: 10px 0; }
        .footer { text-align: center; margin-top: 30px; color: #6c757d; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Daily Scraper Automation Report</h1>
            <h2>{{ report_date }}</h2>
            <div class="status-badge status-{{ 'healthy' if 'Healthy' in report.get_overall_status() else 'warning' if 'Warning' in report.get_overall_status() else 'critical' }}">
                {{ report.get_overall_status() }}
            </div>
        </div>
        
        <div class="summary-grid">
            <div class="summary-card">
                <h3>Cities Processed</h3>
                <div class="value">{{ report.overall_summary.get('total_cities', 0) }}</div>
            </div>
            <div class="summary-card">
                <h3>Total Listings</h3>
                <div class="value">{{ report.overall_summary.get('total_listings_processed', 0) }}</div>
            </div>
            <div class="summary-card">
                <h3>Success Rate</h3>
                <div class="value">{{ "%.1f%%" | format(report.overall_summary.get('average_success_rate', 0) * 100) }}</div>
            </div>
            <div class="summary-card">
                <h3>System Health</h3>
                <div class="value">{{ "%.0f" | format(report.system_health.get('score', 0)) }}/100</div>
            </div>
        </div>
        
        <div class="city-reports">
            <h3>City Reports</h3>
            {% for city_report in report.city_reports %}
            <div class="city-card">
                <div class="city-header">
                    <h4 style="margin: 0; display: inline-block;">{{ city_report.city }}</h4>
                    <span class="status-badge status-{{ 'healthy' if '✅' in city_report.get_status_summary() else 'warning' if '⚠️' in city_report.get_status_summary() else 'critical' }}" style="float: right;">
                        {{ city_report.get_status_summary() }}
                    </span>
                </div>
                <div class="city-content">
                    <div class="metrics-grid">
                        <div class="metric">
                            <div class="metric-label">Processed</div>
                            <div class="metric-value">{{ city_report.execution_metrics.urls_processed }}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Success Rate</div>
                            <div class="metric-value">{{ "%.1f%%" | format(city_report.execution_metrics.success_rate * 100) }}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Duration</div>
                            <div class="metric-value">{{ "%.1f" | format(city_report.execution_metrics.duration_seconds or 0) }}s</div>
                        </div>
                        {% if city_report.data_quality_metrics %}
                        <div class="metric">
                            <div class="metric-label">Data Quality</div>
                            <div class="metric-value">{{ "%.1f%%" | format(city_report.data_quality_metrics.completeness_score * 100) }}</div>
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        
        {% if report.recommendations %}
        <div class="recommendations">
            <h3>Recommendations</h3>
            <ul>
                {% for recommendation in report.recommendations %}
                <li>{{ recommendation }}</li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}
        
        <div class="footer">
            Generated on {{ generation_time }} by Daily Scraper Automation System
        </div>
    </div>
</body>
</html>
        """
        return Template(template_content)
    
    def send_email_report(self, report: DailyReport, subject: Optional[str] = None) -> bool:
        """
        Send report via email.
        
        Args:
            report: Daily report to send
            subject: Email subject (auto-generated if None)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.config.email_enabled or not self.config.email_recipients:
            logger.warning("Email reporting not configured")
            return False
        
        try:
            if subject is None:
                subject = f"Daily Scraper Report - {report.report_date.strftime('%Y-%m-%d')} - {report.get_overall_status()}"
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.config.email_username
            msg['To'] = ', '.join(self.config.email_recipients)
            
            # Create text version
            text_content = self._create_text_summary(report)
            text_part = MIMEText(text_content, 'plain')
            msg.attach(text_part)
            
            # Create HTML version
            html_template = self._get_html_template()
            html_content = html_template.render(
                report=report,
                report_date=report.report_date.strftime('%Y-%m-%d'),
                generation_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.config.email_smtp_server, self.config.email_smtp_port) as server:
                server.starttls()
                server.login(self.config.email_username, self.config.email_password)
                server.send_message(msg)
            
            logger.success(f"Email report sent to {len(self.config.email_recipients)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email report: {e}")
            return False
    
    def _create_text_summary(self, report: DailyReport) -> str:
        """Create text summary for email."""
        lines = [
            f"Daily Scraper Automation Report - {report.report_date.strftime('%Y-%m-%d')}",
            "=" * 60,
            "",
            f"Overall Status: {report.get_overall_status()}",
            f"System Health: {report.system_health.get('score', 0):.0f}/100",
            "",
            "Summary:",
            f"  Cities Processed: {report.overall_summary.get('total_cities', 0)}",
            f"  Total Listings: {report.overall_summary.get('total_listings_processed', 0)}",
            f"  Average Success Rate: {report.overall_summary.get('average_success_rate', 0):.1%}",
            "",
            "City Status:"
        ]
        
        for city_report in report.city_reports:
            lines.append(f"  {city_report.city}: {city_report.get_status_summary()} "
                        f"({city_report.execution_metrics.urls_processed} processed, "
                        f"{city_report.execution_metrics.success_rate:.1%} success)")
        
        if report.recommendations:
            lines.extend(["", "Recommendations:"])
            for rec in report.recommendations:
                lines.append(f"  • {rec}")
        
        return "\n".join(lines)
    
    def generate_and_export_all_formats(self, cities: List[str], report_date: Optional[datetime] = None) -> Dict[str, str]:
        """
        Generate report and export in all configured formats.
        
        Args:
            cities: List of cities to include
            report_date: Report date (defaults to today)
            
        Returns:
            Dictionary mapping format names to file paths
        """
        report = self.generate_daily_report(cities, report_date)
        
        exported_files = {}
        
        # Export JSON
        json_path = self.export_report_json(report)
        exported_files['json'] = json_path
        
        # Export HTML
        html_path = self.export_report_html(report)
        exported_files['html'] = html_path
        
        # Send email if configured
        if self.config.email_enabled:
            email_sent = self.send_email_report(report)
            exported_files['email'] = 'sent' if email_sent else 'failed'
        
        logger.success(f"Generated and exported report in {len(exported_files)} formats")
        return exported_files