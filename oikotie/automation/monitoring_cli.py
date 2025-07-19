"""
CLI Interface for Monitoring and Observability System

This module provides command-line interface for managing and interacting with
the comprehensive monitoring and observability system.
"""

import json
import sys
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
import click
from loguru import logger

from .monitoring import ComprehensiveMonitor, PrometheusMetricsExporter, SystemMonitor, HealthChecker
from .dashboard import DashboardDataCollector, DashboardGenerator, create_monitoring_dashboard
from .logging_config import LoggingConfiguration, setup_monitoring_logging
from ..database.manager import EnhancedDatabaseManager


@click.group()
@click.option('--log-level', default='INFO', help='Logging level')
@click.option('--structured-logs/--no-structured-logs', default=True, help='Enable structured logging')
@click.pass_context
def monitoring_cli(ctx, log_level: str, structured_logs: bool):
    """Monitoring and Observability CLI for Daily Scraper Automation."""
    # Setup logging
    logging_config = setup_monitoring_logging(
        log_level=log_level,
        structured=structured_logs
    )
    
    # Store in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['logging_config'] = logging_config
    ctx.obj['log_level'] = log_level
    ctx.obj['structured_logs'] = structured_logs


@monitoring_cli.group()
def server():
    """Monitoring server management commands."""
    pass


@server.command()
@click.option('--port', default=8080, help='Port for monitoring server')
@click.option('--system-interval', default=30, help='System monitoring interval in seconds')
@click.pass_context
def start(ctx, port: int, system_interval: int):
    """Start the comprehensive monitoring server."""
    try:
        logger.info(f"Starting monitoring server on port {port}")
        
        # Initialize comprehensive monitor
        monitor = ComprehensiveMonitor(
            metrics_port=port,
            system_monitor_interval=system_interval
        )
        
        # Start monitoring
        monitor.start_monitoring()
        
        logger.success(f"Monitoring server started successfully")
        logger.info(f"Metrics endpoint: http://localhost:{port}/metrics")
        logger.info(f"Health endpoint: http://localhost:{port}/health")
        
        # Keep running until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down monitoring server...")
            monitor.stop_monitoring()
            logger.success("Monitoring server stopped")
            
    except Exception as e:
        logger.error(f"Failed to start monitoring server: {e}")
        sys.exit(1)


@server.command()
@click.option('--port', default=8080, help='Port to check')
def status(port: int):
    """Check monitoring server status."""
    try:
        import requests
        
        # Check health endpoint
        health_url = f"http://localhost:{port}/health"
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                logger.success(f"Monitoring server is healthy on port {port}")
                logger.info(f"Overall health: {health_data.get('overall_healthy', 'Unknown')}")
                
                # Show health check details
                checks = health_data.get('checks', {})
                for check_name, check_result in checks.items():
                    status_icon = "✅" if check_result.get('healthy', False) else "❌"
                    logger.info(f"  {status_icon} {check_name}: {check_result.get('healthy', 'Unknown')}")
            else:
                logger.warning(f"Monitoring server returned status {response.status_code}")
        except requests.exceptions.RequestException:
            logger.error(f"Monitoring server not responding on port {port}")
            
        # Check metrics endpoint
        metrics_url = f"http://localhost:{port}/metrics"
        try:
            response = requests.get(metrics_url, timeout=5)
            if response.status_code == 200:
                logger.success("Metrics endpoint is accessible")
            else:
                logger.warning(f"Metrics endpoint returned status {response.status_code}")
        except requests.exceptions.RequestException:
            logger.error("Metrics endpoint not accessible")
            
    except ImportError:
        logger.error("requests library not available - cannot check server status")
        logger.info("Install with: uv add requests")


@monitoring_cli.group()
def metrics():
    """Metrics collection and export commands."""
    pass


@metrics.command()
@click.option('--format', 'output_format', default='json', type=click.Choice(['json', 'prometheus']), help='Output format')
@click.option('--output', help='Output file path')
def export(output_format: str, output: Optional[str]):
    """Export current metrics."""
    try:
        if output_format == 'prometheus':
            # Export Prometheus metrics
            exporter = PrometheusMetricsExporter()
            metrics_text = exporter.get_metrics_text()
            
            if output:
                with open(output, 'w') as f:
                    f.write(metrics_text)
                logger.success(f"Prometheus metrics exported to {output}")
            else:
                click.echo(metrics_text)
        else:
            # Export JSON metrics
            db_manager = EnhancedDatabaseManager()
            
            # Get recent execution metrics
            executions = db_manager.get_recent_executions(hours_back=24)
            
            metrics_data = {
                'timestamp': datetime.now().isoformat(),
                'executions_24h': len(executions),
                'executions': [
                    {
                        'execution_id': e.get('execution_id'),
                        'city': e.get('city'),
                        'status': e.get('status'),
                        'started_at': e.get('started_at'),
                        'listings_processed': e.get('listings_processed', 0)
                    }
                    for e in executions
                ]
            }
            
            if output:
                with open(output, 'w') as f:
                    json.dump(metrics_data, f, indent=2, default=str)
                logger.success(f"JSON metrics exported to {output}")
            else:
                click.echo(json.dumps(metrics_data, indent=2, default=str))
                
    except Exception as e:
        logger.error(f"Failed to export metrics: {e}")
        sys.exit(1)


@metrics.command()
@click.option('--city', help='Filter by city')
@click.option('--hours', default=24, help='Hours of history to show')
def show(city: Optional[str], hours: int):
    """Show current metrics."""
    try:
        db_manager = EnhancedDatabaseManager()
        
        # Get execution statistics
        start_time = datetime.now() - timedelta(hours=hours)
        executions = db_manager.get_executions_by_date_range(start_time, datetime.now())
        
        if city:
            executions = [e for e in executions if e.get('city') == city]
        
        if not executions:
            logger.warning(f"No executions found in the last {hours} hours" + (f" for {city}" if city else ""))
            return
        
        # Calculate statistics
        total_executions = len(executions)
        successful = len([e for e in executions if e.get('status') == 'completed'])
        failed = len([e for e in executions if e.get('status') == 'failed'])
        running = len([e for e in executions if e.get('status') == 'running'])
        
        success_rate = successful / total_executions if total_executions > 0 else 0
        
        total_listings = sum(e.get('listings_processed', 0) for e in executions)
        
        # Display statistics
        logger.info(f"📊 Metrics Summary ({hours}h)" + (f" - {city}" if city else ""))
        logger.info(f"  Total Executions: {total_executions}")
        logger.info(f"  ✅ Successful: {successful}")
        logger.info(f"  ❌ Failed: {failed}")
        logger.info(f"  🔄 Running: {running}")
        logger.info(f"  📈 Success Rate: {success_rate:.1%}")
        logger.info(f"  📋 Total Listings: {total_listings:,}")
        
        # Show recent executions
        recent_executions = sorted(executions, key=lambda x: x.get('started_at', ''), reverse=True)[:5]
        logger.info(f"\n🕒 Recent Executions:")
        for execution in recent_executions:
            status_icon = {"completed": "✅", "failed": "❌", "running": "🔄"}.get(execution.get('status'), "❓")
            logger.info(f"  {status_icon} {execution.get('city', 'Unknown')} - {execution.get('started_at', 'Unknown time')} - {execution.get('listings_processed', 0)} listings")
        
    except Exception as e:
        logger.error(f"Failed to show metrics: {e}")
        sys.exit(1)


@monitoring_cli.group()
def health():
    """Health check commands."""
    pass


@health.command()
def check():
    """Run health checks."""
    try:
        health_checker = HealthChecker()
        results = health_checker.run_health_checks()
        
        overall_healthy = results.get('overall_healthy', False)
        status_icon = "✅" if overall_healthy else "❌"
        
        logger.info(f"{status_icon} Overall Health: {'Healthy' if overall_healthy else 'Unhealthy'}")
        
        # Show individual check results
        checks = results.get('checks', {})
        for check_name, check_result in checks.items():
            healthy = check_result.get('healthy', False)
            duration = check_result.get('duration_ms', 0)
            check_icon = "✅" if healthy else "❌"
            
            logger.info(f"  {check_icon} {check_name}: {'Healthy' if healthy else 'Unhealthy'} ({duration:.1f}ms)")
            
            if not healthy and 'error' in check_result:
                logger.error(f"    Error: {check_result['error']}")
        
        if not overall_healthy:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to run health checks: {e}")
        sys.exit(1)


@health.command()
@click.option('--interval', default=30, help='Check interval in seconds')
@click.option('--count', default=0, help='Number of checks to run (0 for infinite)')
def monitor(interval: int, count: int):
    """Monitor health continuously."""
    try:
        health_checker = HealthChecker()
        checks_run = 0
        
        logger.info(f"Starting health monitoring (interval: {interval}s)")
        
        while count == 0 or checks_run < count:
            results = health_checker.run_health_checks()
            overall_healthy = results.get('overall_healthy', False)
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            status_icon = "✅" if overall_healthy else "❌"
            
            logger.info(f"[{timestamp}] {status_icon} Health: {'OK' if overall_healthy else 'ISSUES'}")
            
            if not overall_healthy:
                # Show failed checks
                checks = results.get('checks', {})
                failed_checks = [name for name, result in checks.items() if not result.get('healthy', True)]
                logger.warning(f"  Failed checks: {', '.join(failed_checks)}")
            
            checks_run += 1
            
            if count == 0 or checks_run < count:
                time.sleep(interval)
        
        logger.info("Health monitoring completed")
        
    except KeyboardInterrupt:
        logger.info("Health monitoring stopped by user")
    except Exception as e:
        logger.error(f"Health monitoring failed: {e}")
        sys.exit(1)


@monitoring_cli.group()
def dashboard():
    """Dashboard generation and management commands."""
    pass


@dashboard.command()
@click.option('--output', help='Output file path')
@click.option('--open-browser/--no-open-browser', default=False, help='Open dashboard in browser')
def generate(output: Optional[str], open_browser: bool):
    """Generate monitoring dashboard."""
    try:
        # Create dashboard components
        data_collector, dashboard_generator = create_monitoring_dashboard()
        
        # Generate dashboard
        dashboard_path = dashboard_generator.generate_html_dashboard(output)
        
        logger.success(f"Dashboard generated: {dashboard_path}")
        
        if open_browser:
            try:
                import webbrowser
                webbrowser.open(f"file://{Path(dashboard_path).absolute()}")
                logger.info("Dashboard opened in browser")
            except Exception as e:
                logger.warning(f"Failed to open browser: {e}")
        
    except Exception as e:
        logger.error(f"Failed to generate dashboard: {e}")
        sys.exit(1)


@dashboard.command()
@click.option('--port', default=8081, help='Port for dashboard server')
@click.option('--refresh-interval', default=30, help='Dashboard refresh interval in seconds')
def serve(port: int, refresh_interval: int):
    """Serve live dashboard."""
    try:
        import http.server
        import socketserver
        from urllib.parse import urlparse
        import threading
        
        # Create dashboard components
        data_collector, dashboard_generator = create_monitoring_dashboard()
        
        # Dashboard directory
        dashboard_dir = Path("output/dashboard")
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        
        class DashboardHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(dashboard_dir), **kwargs)
            
            def do_GET(self):
                if self.path == '/' or self.path == '/index.html':
                    # Generate fresh dashboard
                    try:
                        dashboard_path = dashboard_generator.generate_html_dashboard(
                            str(dashboard_dir / "index.html")
                        )
                        logger.debug("Dashboard refreshed")
                    except Exception as e:
                        logger.error(f"Failed to refresh dashboard: {e}")
                
                super().do_GET()
        
        # Start server
        with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
            logger.success(f"Dashboard server started on http://localhost:{port}")
            logger.info(f"Dashboard will refresh every {refresh_interval} seconds")
            
            # Auto-refresh dashboard in background
            def refresh_dashboard():
                while True:
                    try:
                        time.sleep(refresh_interval)
                        dashboard_generator.generate_html_dashboard(
                            str(dashboard_dir / "index.html")
                        )
                    except Exception as e:
                        logger.error(f"Background dashboard refresh failed: {e}")
            
            refresh_thread = threading.Thread(target=refresh_dashboard, daemon=True)
            refresh_thread.start()
            
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                logger.info("Dashboard server stopped")
        
    except Exception as e:
        logger.error(f"Failed to serve dashboard: {e}")
        sys.exit(1)


@monitoring_cli.group()
def logs():
    """Log management commands."""
    pass


@logs.command()
@click.option('--level', help='Filter by log level')
@click.option('--count', default=50, help='Number of logs to show')
@click.option('--search', help='Search query')
def show(level: Optional[str], count: int, search: Optional[str]):
    """Show recent logs."""
    try:
        # Try to get logs from aggregator if available
        logging_config = LoggingConfiguration()
        log_aggregator = logging_config.get_log_aggregator()
        
        if log_aggregator:
            if search:
                logs = log_aggregator.search_logs(search, count)
            else:
                logs = log_aggregator.get_recent_logs(count, level)
            
            if not logs:
                logger.info("No logs found matching criteria")
                return
            
            logger.info(f"📋 Recent Logs ({len(logs)} entries)")
            for log_entry in logs:
                timestamp = log_entry.get('timestamp', 'Unknown')
                log_level = log_entry.get('level', 'INFO')
                message = log_entry.get('message', '')
                
                level_icon = {
                    'DEBUG': '🔍',
                    'INFO': 'ℹ️',
                    'WARNING': '⚠️',
                    'ERROR': '❌',
                    'CRITICAL': '🚨'
                }.get(log_level, '📝')
                
                logger.info(f"  {level_icon} [{timestamp}] {log_level}: {message}")
        else:
            logger.warning("Log aggregator not available - showing file-based logs")
            
            # Fallback to reading log files
            log_file = Path("logs/scraper_automation.log")
            if log_file.exists():
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-count:]
                    for line in lines:
                        click.echo(line.strip())
            else:
                logger.warning("No log files found")
        
    except Exception as e:
        logger.error(f"Failed to show logs: {e}")
        sys.exit(1)


@logs.command()
@click.option('--output', required=True, help='Output file path')
@click.option('--count', help='Number of logs to export')
def export(output: str, count: Optional[int]):
    """Export logs to file."""
    try:
        logging_config = LoggingConfiguration()
        log_aggregator = logging_config.get_log_aggregator()
        
        if log_aggregator:
            success = log_aggregator.export_logs(output, count)
            if success:
                logger.success(f"Logs exported to {output}")
            else:
                logger.error("Failed to export logs")
                sys.exit(1)
        else:
            logger.error("Log aggregator not available")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Failed to export logs: {e}")
        sys.exit(1)


@logs.command()
def stats():
    """Show log statistics."""
    try:
        logging_config = LoggingConfiguration()
        log_aggregator = logging_config.get_log_aggregator()
        
        if log_aggregator:
            stats = log_aggregator.get_log_statistics()
            
            logger.info("📊 Log Statistics")
            logger.info(f"  Total Logs: {stats.get('total_logs', 0):,}")
            logger.info(f"  Error Rate: {stats.get('error_rate', 0):.2%}")
            logger.info(f"  Buffer Usage: {stats.get('current_buffer_size', 0)}/{stats.get('max_buffer_size', 0)}")
            
            # Show logs by level
            logs_by_level = stats.get('logs_by_level', {})
            logger.info("  Logs by Level:")
            for level, count in logs_by_level.items():
                level_icon = {
                    'DEBUG': '🔍',
                    'INFO': 'ℹ️',
                    'WARNING': '⚠️',
                    'ERROR': '❌',
                    'CRITICAL': '🚨'
                }.get(level, '📝')
                logger.info(f"    {level_icon} {level}: {count:,}")
        else:
            logger.warning("Log aggregator not available")
        
    except Exception as e:
        logger.error(f"Failed to get log statistics: {e}")
        sys.exit(1)


if __name__ == '__main__':
    monitoring_cli()