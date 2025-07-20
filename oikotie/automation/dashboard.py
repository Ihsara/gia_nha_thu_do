"""
Custom Dashboard Integration for Operational Visibility

This module provides dashboard generation and integration capabilities for
monitoring the daily scraper automation system with real-time operational visibility.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from loguru import logger

from .monitoring import ComprehensiveMonitor, SystemMetrics
from .metrics import MetricsCollector, ExecutionMetrics, DataQualityMetrics
from .logging_config import LogAggregator
from ..database.manager import EnhancedDatabaseManager


@dataclass
class DashboardMetrics:
    """Metrics specifically formatted for dashboard display."""
    timestamp: datetime
    system_health_score: float
    active_executions: int
    total_executions_today: int
    success_rate_24h: float
    error_rate_24h: float
    avg_execution_time: float
    data_quality_score: float
    cities_processed: int
    total_listings_today: int
    system_cpu_percent: float
    system_memory_percent: float
    disk_free_gb: float
    recent_errors: List[Dict[str, Any]]
    top_performing_cities: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]]


@dataclass
class DashboardAlert:
    """Dashboard alert information."""
    id: str
    severity: str  # 'info', 'warning', 'error', 'critical'
    title: str
    message: str
    timestamp: datetime
    city: Optional[str] = None
    acknowledged: bool = False
    auto_resolve: bool = True


class DashboardDataCollector:
    """Collects and aggregates data for dashboard display."""
    
    def __init__(self, 
                 db_manager: Optional[EnhancedDatabaseManager] = None,
                 metrics_collector: Optional[MetricsCollector] = None,
                 log_aggregator: Optional[LogAggregator] = None):
        """
        Initialize dashboard data collector.
        
        Args:
            db_manager: Database manager for historical data
            metrics_collector: Metrics collector for current data
            log_aggregator: Log aggregator for error analysis
        """
        self.db_manager = db_manager or EnhancedDatabaseManager()
        self.metrics_collector = metrics_collector or MetricsCollector(self.db_manager)
        self.log_aggregator = log_aggregator
        
        # Cache for dashboard data
        self._dashboard_cache: Optional[DashboardMetrics] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 30  # Cache for 30 seconds
        
        # Alert management
        self._active_alerts: Dict[str, DashboardAlert] = {}
        self._alert_history: List[DashboardAlert] = []
        
        logger.info("Dashboard data collector initialized")
    
    def collect_dashboard_metrics(self, force_refresh: bool = False) -> DashboardMetrics:
        """
        Collect comprehensive metrics for dashboard display.
        
        Args:
            force_refresh: Force refresh of cached data
            
        Returns:
            DashboardMetrics with current system state
        """
        # Check cache first
        if (not force_refresh and 
            self._dashboard_cache and 
            self._cache_timestamp and 
            (datetime.now() - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds):
            return self._dashboard_cache
        
        try:
            # Collect system health metrics
            system_health_score = self._calculate_system_health_score()
            
            # Collect execution metrics
            execution_stats = self._get_execution_statistics()
            
            # Collect data quality metrics
            data_quality_score = self._get_data_quality_score()
            
            # Collect system performance metrics
            system_metrics = self._get_system_performance_metrics()
            
            # Collect recent errors
            recent_errors = self._get_recent_errors()
            
            # Collect top performing cities
            top_cities = self._get_top_performing_cities()
            
            # Collect active alerts
            alerts = list(self._active_alerts.values())
            
            # Create dashboard metrics
            dashboard_metrics = DashboardMetrics(
                timestamp=datetime.now(),
                system_health_score=system_health_score,
                active_executions=execution_stats.get('active_executions', 0),
                total_executions_today=execution_stats.get('total_executions_today', 0),
                success_rate_24h=execution_stats.get('success_rate_24h', 0.0),
                error_rate_24h=execution_stats.get('error_rate_24h', 0.0),
                avg_execution_time=execution_stats.get('avg_execution_time', 0.0),
                data_quality_score=data_quality_score,
                cities_processed=execution_stats.get('cities_processed', 0),
                total_listings_today=execution_stats.get('total_listings_today', 0),
                system_cpu_percent=system_metrics.get('cpu_percent', 0.0),
                system_memory_percent=system_metrics.get('memory_percent', 0.0),
                disk_free_gb=system_metrics.get('disk_free_gb', 0.0),
                recent_errors=recent_errors,
                top_performing_cities=top_cities,
                alerts=[asdict(alert) for alert in alerts]
            )
            
            # Update cache
            self._dashboard_cache = dashboard_metrics
            self._cache_timestamp = datetime.now()
            
            return dashboard_metrics
            
        except Exception as e:
            logger.error(f"Failed to collect dashboard metrics: {e}")
            # Return minimal metrics on error
            return DashboardMetrics(
                timestamp=datetime.now(),
                system_health_score=0.0,
                active_executions=0,
                total_executions_today=0,
                success_rate_24h=0.0,
                error_rate_24h=1.0,
                avg_execution_time=0.0,
                data_quality_score=0.0,
                cities_processed=0,
                total_listings_today=0,
                system_cpu_percent=0.0,
                system_memory_percent=0.0,
                disk_free_gb=0.0,
                recent_errors=[{'message': f'Dashboard collection error: {e}', 'timestamp': datetime.now().isoformat()}],
                top_performing_cities=[],
                alerts=[]
            )
    
    def _calculate_system_health_score(self) -> float:
        """Calculate overall system health score (0-100)."""
        try:
            score = 100.0
            
            # Check execution success rates
            execution_stats = self._get_execution_statistics()
            success_rate = execution_stats.get('success_rate_24h', 1.0)
            if success_rate < 0.9:
                score -= (0.9 - success_rate) * 50  # Penalize low success rates heavily
            
            # Check error rates
            error_rate = execution_stats.get('error_rate_24h', 0.0)
            if error_rate > 0.05:
                score -= error_rate * 30  # Penalize high error rates
            
            # Check data quality
            data_quality = self._get_data_quality_score()
            if data_quality < 0.9:
                score -= (0.9 - data_quality) * 20
            
            # Check system resources
            system_metrics = self._get_system_performance_metrics()
            cpu_percent = system_metrics.get('cpu_percent', 0)
            memory_percent = system_metrics.get('memory_percent', 0)
            
            if cpu_percent > 80:
                score -= (cpu_percent - 80) * 0.5
            if memory_percent > 85:
                score -= (memory_percent - 85) * 0.5
            
            # Check disk space
            disk_free_gb = system_metrics.get('disk_free_gb', 100)
            if disk_free_gb < 5:  # Less than 5GB free
                score -= (5 - disk_free_gb) * 5
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"Failed to calculate system health score: {e}")
            return 0.0
    
    def _get_execution_statistics(self) -> Dict[str, Any]:
        """Get execution statistics for the dashboard."""
        try:
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            
            # Get executions from the last 24 hours
            executions_24h = self.db_manager.get_executions_by_date_range(
                start_date=datetime.combine(yesterday, datetime.min.time()),
                end_date=datetime.now()
            )
            
            if not executions_24h:
                return {
                    'active_executions': 0,
                    'total_executions_today': 0,
                    'success_rate_24h': 1.0,
                    'error_rate_24h': 0.0,
                    'avg_execution_time': 0.0,
                    'cities_processed': 0,
                    'total_listings_today': 0
                }
            
            # Calculate statistics
            total_executions = len(executions_24h)
            successful_executions = len([e for e in executions_24h if e.get('status') == 'completed'])
            failed_executions = len([e for e in executions_24h if e.get('status') == 'failed'])
            
            success_rate = successful_executions / total_executions if total_executions > 0 else 1.0
            error_rate = failed_executions / total_executions if total_executions > 0 else 0.0
            
            # Calculate average execution time
            execution_times = [e.get('execution_time_seconds', 0) for e in executions_24h if e.get('execution_time_seconds')]
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
            
            # Count unique cities and total listings
            cities_processed = len(set(e.get('city', '') for e in executions_24h))
            total_listings = sum(e.get('listings_processed', 0) for e in executions_24h)
            
            # Count active executions
            active_executions = len([e for e in executions_24h if e.get('status') == 'running'])
            
            return {
                'active_executions': active_executions,
                'total_executions_today': total_executions,
                'success_rate_24h': success_rate,
                'error_rate_24h': error_rate,
                'avg_execution_time': avg_execution_time,
                'cities_processed': cities_processed,
                'total_listings_today': total_listings
            }
            
        except Exception as e:
            logger.error(f"Failed to get execution statistics: {e}")
            return {}
    
    def _get_data_quality_score(self) -> float:
        """Get overall data quality score."""
        try:
            # Get recent data quality metrics from database
            quality_metrics = self.db_manager.get_recent_data_quality_metrics(hours_back=24)
            
            if not quality_metrics:
                return 1.0  # Assume good quality if no data
            
            # Calculate weighted average of quality scores
            total_weight = 0
            weighted_sum = 0
            
            for metric in quality_metrics:
                geocoding_rate = metric.get('geocoding_success_rate', 1.0)
                completeness_rate = metric.get('completeness_score', 1.0)
                validation_rate = 1.0 - metric.get('validation_error_rate', 0.0)
                
                # Weight by number of listings processed
                weight = metric.get('total_listings', 1)
                
                # Combined quality score
                quality_score = (geocoding_rate * 0.4 + completeness_rate * 0.4 + validation_rate * 0.2)
                
                weighted_sum += quality_score * weight
                total_weight += weight
            
            return weighted_sum / total_weight if total_weight > 0 else 1.0
            
        except Exception as e:
            logger.error(f"Failed to get data quality score: {e}")
            return 0.0
    
    def _get_system_performance_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics."""
        try:
            from .psutil_compat import psutil
            
            # Get current system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk_usage = psutil.disk_usage('.')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / (1024**2),
                'memory_available_mb': memory.available / (1024**2),
                'disk_free_gb': disk_usage.free / (1024**3),
                'disk_usage_percent': (disk_usage.used / disk_usage.total) * 100
            }
            
        except Exception as e:
            logger.error(f"Failed to get system performance metrics: {e}")
            return {}
    
    def _get_recent_errors(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent error logs for dashboard display."""
        try:
            if self.log_aggregator:
                error_logs = self.log_aggregator.get_error_logs(count)
                return [
                    {
                        'timestamp': log.get('timestamp', ''),
                        'level': log.get('level', 'ERROR'),
                        'message': log.get('message', '')[:200],  # Truncate long messages
                        'module': log.get('module', ''),
                        'city': log.get('extra', {}).get('city', '')
                    }
                    for log in error_logs
                ]
            else:
                # Fallback to database error logs
                return self.db_manager.get_recent_error_logs(count)
                
        except Exception as e:
            logger.error(f"Failed to get recent errors: {e}")
            return []
    
    def _get_top_performing_cities(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get top performing cities for dashboard display."""
        try:
            # Get city performance data from the last 24 hours
            city_stats = self.db_manager.get_city_performance_stats(hours_back=24)
            
            # Sort by success rate and execution efficiency
            sorted_cities = sorted(
                city_stats,
                key=lambda x: (x.get('success_rate', 0), -x.get('avg_execution_time', float('inf'))),
                reverse=True
            )
            
            return [
                {
                    'city': city.get('city', ''),
                    'success_rate': city.get('success_rate', 0.0),
                    'listings_processed': city.get('listings_processed', 0),
                    'avg_execution_time': city.get('avg_execution_time', 0.0),
                    'data_quality_score': city.get('data_quality_score', 0.0)
                }
                for city in sorted_cities[:count]
            ]
            
        except Exception as e:
            logger.error(f"Failed to get top performing cities: {e}")
            return []
    
    def add_alert(self, alert: DashboardAlert) -> None:
        """Add an alert to the dashboard."""
        self._active_alerts[alert.id] = alert
        self._alert_history.append(alert)
        
        # Keep alert history manageable
        if len(self._alert_history) > 1000:
            self._alert_history = self._alert_history[-500:]
        
        logger.info(f"Added dashboard alert: {alert.title}")
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        if alert_id in self._active_alerts:
            self._active_alerts[alert_id].acknowledged = True
            logger.info(f"Acknowledged alert: {alert_id}")
            return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        if alert_id in self._active_alerts:
            del self._active_alerts[alert_id]
            logger.info(f"Resolved alert: {alert_id}")
            return True
        return False
    
    def auto_resolve_alerts(self) -> None:
        """Auto-resolve alerts that are configured for auto-resolution."""
        current_time = datetime.now()
        alerts_to_resolve = []
        
        for alert_id, alert in self._active_alerts.items():
            if (alert.auto_resolve and 
                (current_time - alert.timestamp).total_seconds() > 3600):  # Auto-resolve after 1 hour
                alerts_to_resolve.append(alert_id)
        
        for alert_id in alerts_to_resolve:
            self.resolve_alert(alert_id)


class DashboardGenerator:
    """Generates HTML dashboard for operational visibility."""
    
    def __init__(self, data_collector: DashboardDataCollector):
        """
        Initialize dashboard generator.
        
        Args:
            data_collector: Dashboard data collector
        """
        self.data_collector = data_collector
        logger.info("Dashboard generator initialized")
    
    def generate_html_dashboard(self, output_path: Optional[str] = None) -> str:
        """
        Generate HTML dashboard.
        
        Args:
            output_path: Output file path (auto-generated if None)
            
        Returns:
            Path to generated dashboard file
        """
        if output_path is None:
            output_path = f"output/dashboard/monitoring_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Collect dashboard data
        metrics = self.data_collector.collect_dashboard_metrics()
        
        # Generate HTML content
        html_content = self._generate_html_content(metrics)
        
        # Write to file
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.success(f"Generated dashboard at {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to generate dashboard: {e}")
            raise
    
    def _generate_html_content(self, metrics: DashboardMetrics) -> str:
        """Generate HTML content for the dashboard."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scraper Automation Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; }}
        .dashboard {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #2c3e50; margin-bottom: 10px; }}
        .header .timestamp {{ color: #7f8c8d; font-size: 14px; }}
        
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric-card h3 {{ color: #34495e; margin-bottom: 10px; font-size: 14px; text-transform: uppercase; }}
        .metric-value {{ font-size: 32px; font-weight: bold; margin-bottom: 5px; }}
        .metric-unit {{ color: #7f8c8d; font-size: 14px; }}
        
        .health-score {{ color: {self._get_health_color(metrics.system_health_score)}; }}
        .success-rate {{ color: {self._get_success_color(metrics.success_rate_24h)}; }}
        .error-rate {{ color: {self._get_error_color(metrics.error_rate_24h)}; }}
        
        .section {{ background: white; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .section-header {{ background: #34495e; color: white; padding: 15px 20px; border-radius: 8px 8px 0 0; }}
        .section-content {{ padding: 20px; }}
        
        .error-list {{ max-height: 300px; overflow-y: auto; }}
        .error-item {{ padding: 10px; border-bottom: 1px solid #ecf0f1; }}
        .error-item:last-child {{ border-bottom: none; }}
        .error-timestamp {{ color: #7f8c8d; font-size: 12px; }}
        .error-message {{ margin-top: 5px; }}
        
        .city-list {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .city-item {{ padding: 15px; background: #f8f9fa; border-radius: 6px; }}
        .city-name {{ font-weight: bold; color: #2c3e50; }}
        .city-stats {{ margin-top: 8px; font-size: 12px; color: #7f8c8d; }}
        
        .alert-list {{ }}
        .alert-item {{ padding: 15px; margin-bottom: 10px; border-radius: 6px; border-left: 4px solid; }}
        .alert-critical {{ background: #fdf2f2; border-color: #e53e3e; }}
        .alert-warning {{ background: #fffbf0; border-color: #dd6b20; }}
        .alert-info {{ background: #f0f9ff; border-color: #3182ce; }}
        .alert-title {{ font-weight: bold; margin-bottom: 5px; }}
        .alert-message {{ font-size: 14px; }}
        .alert-timestamp {{ font-size: 12px; color: #7f8c8d; margin-top: 5px; }}
        
        .refresh-info {{ text-align: center; margin-top: 30px; color: #7f8c8d; font-size: 12px; }}
        
        @media (max-width: 768px) {{
            .metrics-grid {{ grid-template-columns: 1fr; }}
            .city-list {{ grid-template-columns: 1fr; }}
        }}
    </style>
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(function() {{
            window.location.reload();
        }}, 30000);
    </script>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>🚀 Scraper Automation Dashboard</h1>
            <div class="timestamp">Last updated: {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <h3>System Health</h3>
                <div class="metric-value health-score">{metrics.system_health_score:.0f}</div>
                <div class="metric-unit">/ 100</div>
            </div>
            
            <div class="metric-card">
                <h3>Active Executions</h3>
                <div class="metric-value">{metrics.active_executions}</div>
                <div class="metric-unit">running</div>
            </div>
            
            <div class="metric-card">
                <h3>Success Rate (24h)</h3>
                <div class="metric-value success-rate">{metrics.success_rate_24h:.1%}</div>
                <div class="metric-unit">success</div>
            </div>
            
            <div class="metric-card">
                <h3>Error Rate (24h)</h3>
                <div class="metric-value error-rate">{metrics.error_rate_24h:.1%}</div>
                <div class="metric-unit">errors</div>
            </div>
            
            <div class="metric-card">
                <h3>Data Quality</h3>
                <div class="metric-value">{metrics.data_quality_score:.1%}</div>
                <div class="metric-unit">quality</div>
            </div>
            
            <div class="metric-card">
                <h3>Listings Today</h3>
                <div class="metric-value">{metrics.total_listings_today:,}</div>
                <div class="metric-unit">processed</div>
            </div>
            
            <div class="metric-card">
                <h3>CPU Usage</h3>
                <div class="metric-value">{metrics.system_cpu_percent:.1f}%</div>
                <div class="metric-unit">cpu</div>
            </div>
            
            <div class="metric-card">
                <h3>Memory Usage</h3>
                <div class="metric-value">{metrics.system_memory_percent:.1f}%</div>
                <div class="metric-unit">memory</div>
            </div>
        </div>
        
        {self._generate_alerts_section(metrics.alerts)}
        
        {self._generate_errors_section(metrics.recent_errors)}
        
        {self._generate_cities_section(metrics.top_performing_cities)}
        
        <div class="refresh-info">
            Dashboard auto-refreshes every 30 seconds | 
            Executions today: {metrics.total_executions_today} | 
            Cities processed: {metrics.cities_processed} |
            Disk free: {metrics.disk_free_gb:.1f} GB
        </div>
    </div>
</body>
</html>
        """
    
    def _get_health_color(self, score: float) -> str:
        """Get color for health score."""
        if score >= 90:
            return "#27ae60"  # Green
        elif score >= 70:
            return "#f39c12"  # Orange
        else:
            return "#e74c3c"  # Red
    
    def _get_success_color(self, rate: float) -> str:
        """Get color for success rate."""
        if rate >= 0.95:
            return "#27ae60"  # Green
        elif rate >= 0.8:
            return "#f39c12"  # Orange
        else:
            return "#e74c3c"  # Red
    
    def _get_error_color(self, rate: float) -> str:
        """Get color for error rate."""
        if rate <= 0.05:
            return "#27ae60"  # Green
        elif rate <= 0.15:
            return "#f39c12"  # Orange
        else:
            return "#e74c3c"  # Red
    
    def _generate_alerts_section(self, alerts: List[Dict[str, Any]]) -> str:
        """Generate alerts section HTML."""
        if not alerts:
            return ""
        
        alerts_html = ""
        for alert in alerts:
            severity_class = f"alert-{alert.get('severity', 'info')}"
            alerts_html += f"""
            <div class="alert-item {severity_class}">
                <div class="alert-title">{alert.get('title', 'Alert')}</div>
                <div class="alert-message">{alert.get('message', '')}</div>
                <div class="alert-timestamp">{alert.get('timestamp', '')}</div>
            </div>
            """
        
        return f"""
        <div class="section">
            <div class="section-header">
                <h2>🚨 Active Alerts ({len(alerts)})</h2>
            </div>
            <div class="section-content">
                <div class="alert-list">
                    {alerts_html}
                </div>
            </div>
        </div>
        """
    
    def _generate_errors_section(self, errors: List[Dict[str, Any]]) -> str:
        """Generate recent errors section HTML."""
        if not errors:
            return """
            <div class="section">
                <div class="section-header">
                    <h2>✅ Recent Errors (0)</h2>
                </div>
                <div class="section-content">
                    <p>No recent errors detected.</p>
                </div>
            </div>
            """
        
        errors_html = ""
        for error in errors:
            errors_html += f"""
            <div class="error-item">
                <div class="error-timestamp">{error.get('timestamp', '')}</div>
                <div class="error-message"><strong>{error.get('level', 'ERROR')}:</strong> {error.get('message', '')}</div>
            </div>
            """
        
        return f"""
        <div class="section">
            <div class="section-header">
                <h2>⚠️ Recent Errors ({len(errors)})</h2>
            </div>
            <div class="section-content">
                <div class="error-list">
                    {errors_html}
                </div>
            </div>
        </div>
        """
    
    def _generate_cities_section(self, cities: List[Dict[str, Any]]) -> str:
        """Generate top performing cities section HTML."""
        if not cities:
            return ""
        
        cities_html = ""
        for city in cities:
            cities_html += f"""
            <div class="city-item">
                <div class="city-name">{city.get('city', 'Unknown')}</div>
                <div class="city-stats">
                    Success: {city.get('success_rate', 0):.1%}<br>
                    Listings: {city.get('listings_processed', 0):,}<br>
                    Time: {city.get('avg_execution_time', 0):.1f}s<br>
                    Quality: {city.get('data_quality_score', 0):.1%}
                </div>
            </div>
            """
        
        return f"""
        <div class="section">
            <div class="section-header">
                <h2>🏆 Top Performing Cities</h2>
            </div>
            <div class="section-content">
                <div class="city-list">
                    {cities_html}
                </div>
            </div>
        </div>
        """


def create_monitoring_dashboard(db_manager: Optional[EnhancedDatabaseManager] = None,
                              log_aggregator: Optional[LogAggregator] = None) -> Tuple[DashboardDataCollector, DashboardGenerator]:
    """
    Create monitoring dashboard components.
    
    Args:
        db_manager: Database manager
        log_aggregator: Log aggregator
        
    Returns:
        Tuple of (data_collector, dashboard_generator)
    """
    data_collector = DashboardDataCollector(
        db_manager=db_manager,
        log_aggregator=log_aggregator
    )
    
    dashboard_generator = DashboardGenerator(data_collector)
    
    logger.success("Monitoring dashboard components created")
    return data_collector, dashboard_generator