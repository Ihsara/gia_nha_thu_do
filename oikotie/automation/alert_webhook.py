#!/usr/bin/env python3
"""
Alert webhook service for multi-city scraper monitoring.

This service receives alerts from Prometheus Alertmanager and processes them
for various notification channels (email, Slack, webhooks, etc.).
"""

import json
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

import requests
from flask import Flask, request, jsonify
from loguru import logger

from oikotie.utils.config import load_config


@dataclass
class Alert:
    """Alert data structure."""
    alertname: str
    status: str
    severity: str
    city: Optional[str]
    instance: str
    summary: str
    description: str
    starts_at: datetime
    ends_at: Optional[datetime] = None
    
    @classmethod
    def from_alertmanager(cls, alert_data: Dict[str, Any]) -> 'Alert':
        """Create Alert from Alertmanager webhook data."""
        labels = alert_data.get('labels', {})
        annotations = alert_data.get('annotations', {})
        
        return cls(
            alertname=labels.get('alertname', 'Unknown'),
            status=alert_data.get('status', 'unknown'),
            severity=labels.get('severity', 'unknown'),
            city=labels.get('city'),
            instance=labels.get('instance', 'unknown'),
            summary=annotations.get('summary', 'No summary'),
            description=annotations.get('description', 'No description'),
            starts_at=datetime.fromisoformat(alert_data.get('startsAt', '').replace('Z', '+00:00')),
            ends_at=datetime.fromisoformat(alert_data.get('endsAt', '').replace('Z', '+00:00')) if alert_data.get('endsAt') else None
        )


class AlertProcessor:
    """Process and route alerts to appropriate channels."""
    
    def __init__(self, config_path: str = "config/config.json"):
        """Initialize alert processor."""
        self.config = load_config(config_path)
        self.logger = logger.bind(component="alert_processor")
        
        # Alert routing configuration
        self.routing_config = self.config.get("alerting", {})
        self.notification_channels = self.routing_config.get("channels", {})
        
        # Initialize notification handlers
        self.handlers = {
            "email": self._send_email_alert,
            "slack": self._send_slack_alert,
            "webhook": self._send_webhook_alert,
            "teams": self._send_teams_alert
        }
    
    def process_alerts(self, alerts_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process incoming alerts from Alertmanager."""
        self.logger.info(f"Processing {len(alerts_data)} alerts")
        
        processed_alerts = []
        results = {"success": 0, "failed": 0, "errors": []}
        
        for alert_data in alerts_data:
            try:
                alert = Alert.from_alertmanager(alert_data)
                processed_alerts.append(alert)
                
                # Route alert to appropriate channels
                self._route_alert(alert)
                results["success"] += 1
                
            except Exception as e:
                self.logger.error(f"Failed to process alert: {e}")
                results["failed"] += 1
                results["errors"].append(str(e))
        
        # Store alerts for historical tracking
        self._store_alerts(processed_alerts)
        
        return results
    
    def _route_alert(self, alert: Alert):
        """Route alert to appropriate notification channels."""
        # Determine routing based on alert properties
        channels = self._get_channels_for_alert(alert)
        
        for channel in channels:
            try:
                handler = self.handlers.get(channel["type"])
                if handler:
                    handler(alert, channel["config"])
                else:
                    self.logger.warning(f"Unknown notification channel: {channel['type']}")
            except Exception as e:
                self.logger.error(f"Failed to send alert via {channel['type']}: {e}")
    
    def _get_channels_for_alert(self, alert: Alert) -> List[Dict[str, Any]]:
        """Determine which channels should receive this alert."""
        channels = []
        
        # Default channels for all alerts
        default_channels = self.notification_channels.get("default", [])
        channels.extend(default_channels)
        
        # Severity-based routing
        severity_channels = self.notification_channels.get("severity", {}).get(alert.severity, [])
        channels.extend(severity_channels)
        
        # City-specific routing
        if alert.city:
            city_channels = self.notification_channels.get("city", {}).get(alert.city, [])
            channels.extend(city_channels)
        
        # Alert-specific routing
        alert_channels = self.notification_channels.get("alert", {}).get(alert.alertname, [])
        channels.extend(alert_channels)
        
        # Remove duplicates
        unique_channels = []
        seen = set()
        for channel in channels:
            channel_key = f"{channel['type']}:{channel.get('config', {}).get('target', '')}"
            if channel_key not in seen:
                unique_channels.append(channel)
                seen.add(channel_key)
        
        return unique_channels
    
    def _send_email_alert(self, alert: Alert, config: Dict[str, Any]):
        """Send alert via email."""
        smtp_config = config.get("smtp", {})
        
        if not smtp_config.get("enabled", False):
            return
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = smtp_config.get("from", "alerts@oikotie-scraper.local")
        msg['To'] = ", ".join(config.get("recipients", []))
        msg['Subject'] = f"[{alert.severity.upper()}] {alert.alertname}"
        
        # Email body
        body = self._format_alert_email(alert)
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        try:
            server = smtplib.SMTP(smtp_config.get("host", "localhost"), smtp_config.get("port", 587))
            if smtp_config.get("tls", True):
                server.starttls()
            if smtp_config.get("username") and smtp_config.get("password"):
                server.login(smtp_config["username"], smtp_config["password"])
            
            server.send_message(msg)
            server.quit()
            
            self.logger.info(f"Email alert sent for {alert.alertname}")
            
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
    
    def _send_slack_alert(self, alert: Alert, config: Dict[str, Any]):
        """Send alert to Slack."""
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            self.logger.warning("Slack webhook URL not configured")
            return
        
        # Format Slack message
        color = self._get_alert_color(alert.severity)
        
        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"{alert.alertname}",
                    "text": alert.summary,
                    "fields": [
                        {"title": "Severity", "value": alert.severity, "short": True},
                        {"title": "Status", "value": alert.status, "short": True},
                        {"title": "City", "value": alert.city or "N/A", "short": True},
                        {"title": "Instance", "value": alert.instance, "short": True},
                        {"title": "Description", "value": alert.description, "short": False}
                    ],
                    "footer": "Oikotie Scraper Monitoring",
                    "ts": int(alert.starts_at.timestamp())
                }
            ]
        }
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            self.logger.info(f"Slack alert sent for {alert.alertname}")
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}")
    
    def _send_webhook_alert(self, alert: Alert, config: Dict[str, Any]):
        """Send alert to custom webhook."""
        webhook_url = config.get("url")
        if not webhook_url:
            self.logger.warning("Webhook URL not configured")
            return
        
        payload = {
            "alertname": alert.alertname,
            "status": alert.status,
            "severity": alert.severity,
            "city": alert.city,
            "instance": alert.instance,
            "summary": alert.summary,
            "description": alert.description,
            "starts_at": alert.starts_at.isoformat(),
            "ends_at": alert.ends_at.isoformat() if alert.ends_at else None
        }
        
        headers = config.get("headers", {})
        headers.setdefault("Content-Type", "application/json")
        
        try:
            response = requests.post(
                webhook_url, 
                json=payload, 
                headers=headers,
                timeout=config.get("timeout", 10)
            )
            response.raise_for_status()
            self.logger.info(f"Webhook alert sent for {alert.alertname}")
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")
    
    def _send_teams_alert(self, alert: Alert, config: Dict[str, Any]):
        """Send alert to Microsoft Teams."""
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            self.logger.warning("Teams webhook URL not configured")
            return
        
        color = self._get_alert_color(alert.severity)
        
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color.replace("#", ""),
            "summary": f"{alert.alertname} - {alert.severity}",
            "sections": [
                {
                    "activityTitle": alert.alertname,
                    "activitySubtitle": alert.summary,
                    "facts": [
                        {"name": "Severity", "value": alert.severity},
                        {"name": "Status", "value": alert.status},
                        {"name": "City", "value": alert.city or "N/A"},
                        {"name": "Instance", "value": alert.instance},
                        {"name": "Time", "value": alert.starts_at.strftime("%Y-%m-%d %H:%M:%S UTC")}
                    ],
                    "text": alert.description
                }
            ]
        }
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            self.logger.info(f"Teams alert sent for {alert.alertname}")
        except Exception as e:
            self.logger.error(f"Failed to send Teams alert: {e}")
    
    def _format_alert_email(self, alert: Alert) -> str:
        """Format alert as HTML email."""
        color = self._get_alert_color(alert.severity)
        
        html = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <div style="background-color: {color}; color: white; padding: 20px; border-radius: 5px 5px 0 0;">
                    <h2 style="margin: 0;">{alert.alertname}</h2>
                    <p style="margin: 5px 0 0 0; font-size: 14px;">Severity: {alert.severity.upper()}</p>
                </div>
                
                <div style="border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 5px 5px;">
                    <h3 style="color: #333; margin-top: 0;">Summary</h3>
                    <p>{alert.summary}</p>
                    
                    <h3 style="color: #333;">Description</h3>
                    <p>{alert.description}</p>
                    
                    <h3 style="color: #333;">Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Status:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.status}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">City:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.city or 'N/A'}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Instance:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.instance}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Started:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.starts_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
                        </tr>
                    </table>
                    
                    <p style="margin-top: 20px; font-size: 12px; color: #666;">
                        This alert was generated by the Oikotie Scraper Monitoring System.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _get_alert_color(self, severity: str) -> str:
        """Get color code for alert severity."""
        colors = {
            "critical": "#d32f2f",
            "warning": "#f57c00",
            "info": "#1976d2",
            "unknown": "#757575"
        }
        return colors.get(severity.lower(), colors["unknown"])
    
    def _store_alerts(self, alerts: List[Alert]):
        """Store alerts for historical tracking."""
        # This could be implemented to store alerts in database
        # for historical analysis and reporting
        pass


# Flask application for webhook endpoints
app = Flask(__name__)
alert_processor = AlertProcessor()


@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Main webhook endpoint for Alertmanager."""
    try:
        data = request.get_json()
        alerts = data.get('alerts', [])
        
        if not alerts:
            return jsonify({"status": "success", "message": "No alerts received"}), 200
        
        results = alert_processor.process_alerts(alerts)
        
        return jsonify({
            "status": "success",
            "processed": results["success"],
            "failed": results["failed"],
            "errors": results["errors"]
        }), 200
        
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/webhook/critical', methods=['POST'])
def critical_webhook_handler():
    """Webhook endpoint for critical alerts only."""
    try:
        data = request.get_json()
        alerts = data.get('alerts', [])
        
        # Filter for critical alerts only
        critical_alerts = [
            alert for alert in alerts 
            if alert.get('labels', {}).get('severity') == 'critical'
        ]
        
        if not critical_alerts:
            return jsonify({"status": "success", "message": "No critical alerts"}), 200
        
        results = alert_processor.process_alerts(critical_alerts)
        
        return jsonify({
            "status": "success",
            "processed": results["success"],
            "failed": results["failed"],
            "errors": results["errors"]
        }), 200
        
    except Exception as e:
        logger.error(f"Critical webhook handler error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/webhook/city', methods=['POST'])
def city_webhook_handler():
    """Webhook endpoint for city-specific alerts."""
    try:
        data = request.get_json()
        alerts = data.get('alerts', [])
        
        # Process city-specific alerts
        results = alert_processor.process_alerts(alerts)
        
        return jsonify({
            "status": "success",
            "processed": results["success"],
            "failed": results["failed"],
            "errors": results["errors"]
        }), 200
        
    except Exception as e:
        logger.error(f"City webhook handler error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for the webhook service."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "alert-webhook"
    }), 200


if __name__ == '__main__':
    # Run the Flask application
    app.run(host='0.0.0.0', port=5001, debug=False)