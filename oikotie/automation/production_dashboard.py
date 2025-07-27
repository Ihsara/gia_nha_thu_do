"""
Production monitoring dashboard for Oikotie Daily Scraper Automation.

This module provides a comprehensive web-based dashboard for monitoring
production deployments, system health, and operational metrics.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from loguru import logger

try:
    from flask import Flask, render_template_string, jsonify, request
    FLASK_AVAILABLE = True
except ImportError:
    Flask = None
    FLASK_AVAILABLE = False
    logger.warning("Flask not available - production dashboard disabled")

from .production_deployment import ProductionDeploymentManager, DeploymentStatus
from .monitoring import ComprehensiveMonitor
from .reporting import StatusReporter
from ..database.manager import EnhancedDatabaseManager


class ProductionDashboard:
    """Web-based production monitoring dashboard."""
    
    def __init__(self, 
                 deployment_manager: ProductionDeploymentManager,
                 port: int = 8090):
        """
        Initialize production dashboard.
        
        Args:
            deployment_manager: Production deployment manager
            port: Port for dashboard server
        """
        self.deployment_manager = deployment_manager
        self.port = port
        self.app: Optional[Flask] = None
        
        if FLASK_AVAILABLE:
            self._create_flask_app()
        else:
            logger.error("Flask not available - dashboard cannot be created")
    
    def _create_flask_app(self) -> None:
        """Create Flask application with dashboard routes."""
        self.app = Flask(__name__)
        
        @self.app.route('/')
        def dashboard():
            """Main dashboard page."""
            return render_template_string(self._get_dashboard_template())
        
        @self.app.route('/api/status')
        def api_status():
            """API endpoint for system status."""
            try:
                status = self.deployment_manager.get_system_status()
                return jsonify({
                    'status': status.status,
                    'deployment_name': status.deployment_name,
                    'started_at': status.started_at.isoformat(),
                    'last_check': status.last_check.isoformat(),
                    'components': status.components,
                    'metrics': status.metrics,
                    'errors': status.errors,
                    'warnings': status.warnings
                })
            except Exception as e:
                logger.error(f"Status API error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/orchestrators')
        def api_orchestrators():
            """API endpoint for orchestrator information."""
            try:
                orchestrators_info = []
                for orchestrator in self.deployment_manager.orchestrators:
                    config = orchestrator.get_configuration()
                    stats = orchestrator.get_execution_statistics(hours_back=24)
                    
                    orchestrators_info.append({
                        'city': config.city,
                        'url': config.url,
                        'max_workers': config.max_detail_workers,
                        'staleness_threshold': config.staleness_threshold_hours,
                        'smart_deduplication': config.enable_smart_deduplication,
                        'performance_monitoring': config.enable_performance_monitoring,
                        'statistics': stats
                    })
                
                return jsonify(orchestrators_info)
            except Exception as e:
                logger.error(f"Orchestrators API error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/metrics')
        def api_metrics():
            """API endpoint for system metrics."""
            try:
                # Get system metrics from comprehensive monitor
                if self.deployment_manager.comprehensive_monitor:
                    metrics = self.deployment_manager.comprehensive_monitor.get_current_metrics()
                else:
                    metrics = {}
                
                # Add deployment-specific metrics
                status = self.deployment_manager.get_system_status()
                metrics.update(status.metrics)
                
                return jsonify(metrics)
            except Exception as e:
                logger.error(f"Metrics API error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/recent_executions')
        def api_recent_executions():
            """API endpoint for recent execution history."""
            try:
                # Get recent executions from database
                db_manager = EnhancedDatabaseManager(
                    self.deployment_manager.config.database_path
                )
                
                # Query recent executions (last 24 hours)
                recent_executions = db_manager.get_recent_executions(hours_back=24)
                
                executions_data = []
                for execution in recent_executions:
                    executions_data.append({
                        'execution_id': execution.execution_id,
                        'city': execution.city,
                        'started_at': execution.started_at.isoformat(),
                        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
                        'status': execution.status,
                        'listings_processed': execution.listings_processed,
                        'listings_new': execution.listings_new,
                        'listings_failed': execution.listings_failed,
                        'execution_time_seconds': execution.execution_time_seconds,
                        'memory_usage_mb': execution.memory_usage_mb
                    })
                
                return jsonify(executions_data)
            except Exception as e:
                logger.error(f"Recent executions API error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/run_daily', methods=['POST'])
        def api_run_daily():
            """API endpoint to trigger daily automation."""
            try:
                result = self.deployment_manager.run_daily_automation()
                return jsonify(result)
            except Exception as e:
                logger.error(f"Run daily API error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/backup', methods=['POST'])
        def api_backup():
            """API endpoint to create system backup."""
            try:
                backup_path = self.deployment_manager.create_backup()
                return jsonify({'backup_path': backup_path})
            except Exception as e:
                logger.error(f"Backup API error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cleanup', methods=['POST'])
        def api_cleanup():
            """API endpoint to cleanup old data."""
            try:
                stats = self.deployment_manager.cleanup_old_data()
                return jsonify(stats)
            except Exception as e:
                logger.error(f"Cleanup API error: {e}")
                return jsonify({'error': str(e)}), 500
    
    def _get_dashboard_template(self) -> str:
        """Get HTML template for dashboard."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oikotie Production Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f5f5;
            color: #333;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            font-size: 1.8rem;
            font-weight: 600;
        }
        
        .header .subtitle {
            opacity: 0.9;
            margin-top: 0.25rem;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .card {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border: 1px solid #e1e5e9;
        }
        
        .card h2 {
            font-size: 1.2rem;
            margin-bottom: 1rem;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5rem;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }
        
        .status-healthy { background-color: #27ae60; }
        .status-degraded { background-color: #f39c12; }
        .status-failed { background-color: #e74c3c; }
        .status-not_initialized { background-color: #95a5a6; }
        
        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .metric:last-child {
            border-bottom: none;
        }
        
        .metric-label {
            font-weight: 500;
            color: #34495e;
        }
        
        .metric-value {
            font-weight: 600;
            color: #2c3e50;
        }
        
        .button {
            background: #3498db;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            transition: background-color 0.2s;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
        }
        
        .button:hover {
            background: #2980b9;
        }
        
        .button.danger {
            background: #e74c3c;
        }
        
        .button.danger:hover {
            background: #c0392b;
        }
        
        .button.success {
            background: #27ae60;
        }
        
        .button.success:hover {
            background: #229954;
        }
        
        .table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }
        
        .table th,
        .table td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .table th {
            background-color: #f8f9fa;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .loading {
            text-align: center;
            padding: 2rem;
            color: #7f8c8d;
        }
        
        .error {
            background-color: #fdf2f2;
            color: #e74c3c;
            padding: 1rem;
            border-radius: 4px;
            border-left: 4px solid #e74c3c;
            margin: 1rem 0;
        }
        
        .warning {
            background-color: #fefbf2;
            color: #f39c12;
            padding: 1rem;
            border-radius: 4px;
            border-left: 4px solid #f39c12;
            margin: 1rem 0;
        }
        
        .refresh-indicator {
            position: fixed;
            top: 1rem;
            right: 1rem;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            font-size: 0.8rem;
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Oikotie Production Dashboard</h1>
        <div class="subtitle">Real-time monitoring and control</div>
    </div>
    
    <div class="container">
        <div class="grid">
            <!-- System Status Card -->
            <div class="card">
                <h2>System Status</h2>
                <div id="system-status" class="loading">Loading...</div>
            </div>
            
            <!-- System Metrics Card -->
            <div class="card">
                <h2>System Metrics</h2>
                <div id="system-metrics" class="loading">Loading...</div>
            </div>
            
            <!-- Actions Card -->
            <div class="card">
                <h2>Actions</h2>
                <button class="button success" onclick="runDaily()">Run Daily Automation</button>
                <button class="button" onclick="createBackup()">Create Backup</button>
                <button class="button danger" onclick="cleanupData()">Cleanup Old Data</button>
            </div>
        </div>
        
        <!-- Orchestrators Section -->
        <div class="card">
            <h2>Orchestrators</h2>
            <div id="orchestrators" class="loading">Loading...</div>
        </div>
        
        <!-- Recent Executions Section -->
        <div class="card">
            <h2>Recent Executions (Last 24 Hours)</h2>
            <div id="recent-executions" class="loading">Loading...</div>
        </div>
    </div>
    
    <div id="refresh-indicator" class="refresh-indicator" style="display: none;">
        Refreshing...
    </div>
    
    <script>
        let refreshInterval;
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            loadDashboard();
            startAutoRefresh();
        });
        
        function loadDashboard() {
            showRefreshIndicator();
            
            Promise.all([
                loadSystemStatus(),
                loadSystemMetrics(),
                loadOrchestrators(),
                loadRecentExecutions()
            ]).finally(() => {
                hideRefreshIndicator();
            });
        }
        
        function loadSystemStatus() {
            return fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('system-status').innerHTML = 
                            `<div class="error">Error: ${data.error}</div>`;
                        return;
                    }
                    
                    let html = `
                        <div class="metric">
                            <span class="metric-label">Status</span>
                            <span class="metric-value">
                                <span class="status-indicator status-${data.status}"></span>
                                ${data.status.toUpperCase()}
                            </span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Deployment</span>
                            <span class="metric-value">${data.deployment_name}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Started</span>
                            <span class="metric-value">${new Date(data.started_at).toLocaleString()}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Last Check</span>
                            <span class="metric-value">${new Date(data.last_check).toLocaleString()}</span>
                        </div>
                    `;
                    
                    // Add component status
                    for (const [component, status] of Object.entries(data.components)) {
                        html += `
                            <div class="metric">
                                <span class="metric-label">${component.replace('_', ' ')}</span>
                                <span class="metric-value">
                                    <span class="status-indicator status-${status}"></span>
                                    ${status.replace('_', ' ')}
                                </span>
                            </div>
                        `;
                    }
                    
                    // Add errors and warnings
                    if (data.errors && data.errors.length > 0) {
                        html += '<div class="error">Errors:<ul>';
                        data.errors.forEach(error => {
                            html += `<li>${error}</li>`;
                        });
                        html += '</ul></div>';
                    }
                    
                    if (data.warnings && data.warnings.length > 0) {
                        html += '<div class="warning">Warnings:<ul>';
                        data.warnings.forEach(warning => {
                            html += `<li>${warning}</li>`;
                        });
                        html += '</ul></div>';
                    }
                    
                    document.getElementById('system-status').innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('system-status').innerHTML = 
                        `<div class="error">Failed to load status: ${error.message}</div>`;
                });
        }
        
        function loadSystemMetrics() {
            return fetch('/api/metrics')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('system-metrics').innerHTML = 
                            `<div class="error">Error: ${data.error}</div>`;
                        return;
                    }
                    
                    let html = '';
                    for (const [metric, value] of Object.entries(data)) {
                        let displayValue = value;
                        
                        // Format specific metrics
                        if (metric.includes('memory') && typeof value === 'number') {
                            displayValue = `${value.toFixed(1)} MB`;
                        } else if (metric.includes('cpu') && typeof value === 'number') {
                            displayValue = `${value.toFixed(1)}%`;
                        } else if (metric.includes('uptime') && typeof value === 'number') {
                            displayValue = `${(value / 3600).toFixed(1)} hours`;
                        }
                        
                        html += `
                            <div class="metric">
                                <span class="metric-label">${metric.replace('_', ' ')}</span>
                                <span class="metric-value">${displayValue}</span>
                            </div>
                        `;
                    }
                    
                    document.getElementById('system-metrics').innerHTML = html || 'No metrics available';
                })
                .catch(error => {
                    document.getElementById('system-metrics').innerHTML = 
                        `<div class="error">Failed to load metrics: ${error.message}</div>`;
                });
        }
        
        function loadOrchestrators() {
            return fetch('/api/orchestrators')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('orchestrators').innerHTML = 
                            `<div class="error">Error: ${data.error}</div>`;
                        return;
                    }
                    
                    if (!data || data.length === 0) {
                        document.getElementById('orchestrators').innerHTML = 'No orchestrators configured';
                        return;
                    }
                    
                    let html = '<table class="table"><thead><tr>';
                    html += '<th>City</th><th>Max Workers</th><th>Staleness (hrs)</th>';
                    html += '<th>Smart Dedup</th><th>Performance Mon</th></tr></thead><tbody>';
                    
                    data.forEach(orchestrator => {
                        html += `
                            <tr>
                                <td><strong>${orchestrator.city}</strong></td>
                                <td>${orchestrator.max_workers}</td>
                                <td>${orchestrator.staleness_threshold}</td>
                                <td>${orchestrator.smart_deduplication ? '✓' : '✗'}</td>
                                <td>${orchestrator.performance_monitoring ? '✓' : '✗'}</td>
                            </tr>
                        `;
                    });
                    
                    html += '</tbody></table>';
                    document.getElementById('orchestrators').innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('orchestrators').innerHTML = 
                        `<div class="error">Failed to load orchestrators: ${error.message}</div>`;
                });
        }
        
        function loadRecentExecutions() {
            return fetch('/api/recent_executions')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('recent-executions').innerHTML = 
                            `<div class="error">Error: ${data.error}</div>`;
                        return;
                    }
                    
                    if (!data || data.length === 0) {
                        document.getElementById('recent-executions').innerHTML = 'No recent executions';
                        return;
                    }
                    
                    let html = '<table class="table"><thead><tr>';
                    html += '<th>City</th><th>Started</th><th>Status</th>';
                    html += '<th>New</th><th>Failed</th><th>Duration</th></tr></thead><tbody>';
                    
                    data.forEach(execution => {
                        const duration = execution.execution_time_seconds ? 
                            `${execution.execution_time_seconds}s` : 'N/A';
                        
                        html += `
                            <tr>
                                <td>${execution.city}</td>
                                <td>${new Date(execution.started_at).toLocaleString()}</td>
                                <td>
                                    <span class="status-indicator status-${execution.status === 'completed' ? 'healthy' : 'failed'}"></span>
                                    ${execution.status}
                                </td>
                                <td>${execution.listings_new || 0}</td>
                                <td>${execution.listings_failed || 0}</td>
                                <td>${duration}</td>
                            </tr>
                        `;
                    });
                    
                    html += '</tbody></table>';
                    document.getElementById('recent-executions').innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('recent-executions').innerHTML = 
                        `<div class="error">Failed to load executions: ${error.message}</div>`;
                });
        }
        
        function runDaily() {
            if (!confirm('Start daily automation workflow?')) return;
            
            showRefreshIndicator();
            fetch('/api/run_daily', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(`Error: ${data.error}`);
                    } else {
                        alert(`Daily automation started: ${data.execution_id}`);
                        loadDashboard();
                    }
                })
                .catch(error => {
                    alert(`Failed to start daily automation: ${error.message}`);
                })
                .finally(() => {
                    hideRefreshIndicator();
                });
        }
        
        function createBackup() {
            if (!confirm('Create system backup?')) return;
            
            showRefreshIndicator();
            fetch('/api/backup', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(`Error: ${data.error}`);
                    } else {
                        alert(`Backup created: ${data.backup_path}`);
                    }
                })
                .catch(error => {
                    alert(`Failed to create backup: ${error.message}`);
                })
                .finally(() => {
                    hideRefreshIndicator();
                });
        }
        
        function cleanupData() {
            if (!confirm('Cleanup old data? This cannot be undone.')) return;
            
            showRefreshIndicator();
            fetch('/api/cleanup', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(`Error: ${data.error}`);
                    } else {
                        alert(`Cleanup completed: ${JSON.stringify(data)}`);
                    }
                })
                .catch(error => {
                    alert(`Failed to cleanup data: ${error.message}`);
                })
                .finally(() => {
                    hideRefreshIndicator();
                });
        }
        
        function startAutoRefresh() {
            refreshInterval = setInterval(loadDashboard, 30000); // Refresh every 30 seconds
        }
        
        function showRefreshIndicator() {
            document.getElementById('refresh-indicator').style.display = 'block';
        }
        
        function hideRefreshIndicator() {
            document.getElementById('refresh-indicator').style.display = 'none';
        }
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', function() {
            if (refreshInterval) {
                clearInterval(refreshInterval);
            }
        });
    </script>
</body>
</html>
        """
    
    def start_dashboard(self) -> None:
        """Start the production dashboard server."""
        if not self.app:
            logger.error("Dashboard app not initialized")
            return
        
        logger.info(f"Starting production dashboard on port {self.port}")
        
        try:
            self.app.run(
                host='0.0.0.0',
                port=self.port,
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            logger.error(f"Failed to start dashboard: {e}")
            raise


def create_production_dashboard(
    deployment_manager: ProductionDeploymentManager,
    port: int = 8090
) -> Optional[ProductionDashboard]:
    """
    Create production dashboard for deployment manager.
    
    Args:
        deployment_manager: Production deployment manager
        port: Port for dashboard server
        
    Returns:
        ProductionDashboard instance if Flask is available, None otherwise
    """
    if not FLASK_AVAILABLE:
        logger.warning("Flask not available - production dashboard cannot be created")
        return None
    
    return ProductionDashboard(deployment_manager, port)


def main():
    """Main entry point for production dashboard."""
    import argparse
    from .production_deployment import create_production_deployment, DeploymentType
    
    parser = argparse.ArgumentParser(description="Oikotie Production Dashboard")
    parser.add_argument("--port", type=int, default=8090, help="Dashboard port")
    parser.add_argument("--deployment-name", default="oikotie-production", help="Deployment name")
    parser.add_argument("--config", help="Configuration file path")
    
    args = parser.parse_args()
    
    try:
        # Create deployment manager
        config_overrides = {}
        if args.config:
            config_overrides['config_path'] = args.config
        
        deployment_manager = create_production_deployment(
            args.deployment_name,
            DeploymentType.STANDALONE,
            "production",
            config_overrides
        )
        
        # Initialize deployment
        if not deployment_manager.initialize_deployment():
            logger.error("Failed to initialize deployment")
            return
        
        # Create and start dashboard
        dashboard = create_production_dashboard(deployment_manager, args.port)
        if dashboard:
            dashboard.start_dashboard()
        else:
            logger.error("Failed to create dashboard")
    
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Dashboard failed: {e}")


if __name__ == "__main__":
    main()