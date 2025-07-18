"""
Command Line Interface for Alert Management

This module provides CLI commands for managing the alerting system,
including configuration, testing, and monitoring of alerts.
"""

import json
import click
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path
from loguru import logger

from .alerting import AlertManager, AlertSeverity, AlertConditionType, NotificationChannel, create_alert_manager
from .alert_config import AlertConfigManager, AlertCondition, NotificationChannelConfig
from ..database.manager import EnhancedDatabaseManager


@click.group()
@click.option('--config', '-c', type=click.Path(), help='Alert configuration file path')
@click.pass_context
def alerts(ctx, config):
    """Alert management commands."""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


@alerts.command()
@click.option('--output', '-o', type=click.Path(), help='Output configuration file path')
@click.pass_context
def init_config(ctx, output):
    """Initialize alert configuration with default settings."""
    try:
        config_path = output or ctx.obj.get('config_path') or 'config/alert_config.json'
        
        # Create configuration manager
        config_manager = AlertConfigManager(config_path)
        
        # Create default configuration
        config = config_manager._create_default_configuration()
        
        # Save configuration
        if config_manager.save_configuration(config):
            click.echo(f"✅ Alert configuration initialized at {config_path}")
            click.echo(f"📝 Edit the file to configure notification channels")
        else:
            click.echo(f"❌ Failed to initialize configuration at {config_path}")
            
    except Exception as e:
        logger.error(f"Failed to initialize alert configuration: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.pass_context
def status(ctx):
    """Show alert system status and configuration summary."""
    try:
        config_manager = AlertConfigManager(ctx.obj.get('config_path'))
        summary = config_manager.get_configuration_summary()
        
        click.echo("🚨 Alert System Status")
        click.echo("=" * 50)
        click.echo(f"Alerting Enabled: {'✅' if summary['alerting_enabled'] else '❌'}")
        click.echo(f"Alert Conditions: {summary['enabled_conditions']}/{summary['total_conditions']} enabled")
        click.echo(f"Notification Channels: {summary['enabled_channels']}/{summary['total_channels']} enabled")
        click.echo(f"Escalation: {'✅' if summary['escalation_enabled'] else '❌'}")
        click.echo(f"De-duplication: {'✅' if summary['deduplication_enabled'] else '❌'}")
        click.echo(f"Rate Limit: {summary['max_alerts_per_hour']} alerts/hour")
        click.echo(f"History Retention: {summary['alert_history_days']} days")
        
        click.echo("\n📊 Conditions by Severity:")
        for severity, count in summary['conditions_by_severity'].items():
            click.echo(f"  {severity.upper()}: {count}")
        
        click.echo("\n📡 Notification Channels:")
        for channel_type, enabled in summary['channels_by_type'].items():
            status_icon = "✅" if enabled else "❌"
            click.echo(f"  {channel_type.upper()}: {status_icon}")
        
    except Exception as e:
        logger.error(f"Failed to get alert status: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.pass_context
def list_conditions(ctx):
    """List all alert conditions."""
    try:
        config_manager = AlertConfigManager(ctx.obj.get('config_path'))
        config = config_manager.load_configuration()
        
        if not config.alert_conditions:
            click.echo("No alert conditions configured.")
            return
        
        click.echo("📋 Alert Conditions")
        click.echo("=" * 80)
        
        for condition in config.alert_conditions:
            status_icon = "✅" if condition.enabled else "❌"
            severity_color = {
                AlertSeverity.INFO: "blue",
                AlertSeverity.WARNING: "yellow", 
                AlertSeverity.CRITICAL: "red",
                AlertSeverity.EMERGENCY: "bright_red"
            }.get(condition.severity, "white")
            
            click.echo(f"{status_icon} {condition.name}")
            click.echo(f"   Type: {condition.condition_type.value}")
            click.echo(f"   Severity: ", nl=False)
            click.secho(condition.severity.value.upper(), fg=severity_color)
            click.echo(f"   Threshold: {condition.comparison_operator} {condition.threshold_value}")
            click.echo(f"   Description: {condition.description}")
            click.echo(f"   Escalation: {condition.escalation_minutes}min, max {condition.max_escalations}")
            click.echo()
        
    except Exception as e:
        logger.error(f"Failed to list conditions: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.pass_context
def list_channels(ctx):
    """List all notification channels."""
    try:
        config_manager = AlertConfigManager(ctx.obj.get('config_path'))
        config = config_manager.load_configuration()
        
        if not config.notification_channels:
            click.echo("No notification channels configured.")
            return
        
        click.echo("📡 Notification Channels")
        click.echo("=" * 50)
        
        for channel in config.notification_channels:
            status_icon = "✅" if channel.enabled else "❌"
            click.echo(f"{status_icon} {channel.channel_type.value.upper()}")
            click.echo(f"   Retry Attempts: {channel.retry_attempts}")
            click.echo(f"   Timeout: {channel.timeout_seconds}s")
            
            # Show configuration status (without sensitive data)
            if channel.channel_type == NotificationChannel.EMAIL:
                smtp_server = channel.config.get('smtp_server', 'Not configured')
                from_addr = channel.config.get('from_address', 'Not configured')
                to_count = len(channel.config.get('to_addresses', []))
                click.echo(f"   SMTP Server: {smtp_server}")
                click.echo(f"   From: {from_addr}")
                click.echo(f"   Recipients: {to_count}")
                
            elif channel.channel_type == NotificationChannel.SLACK:
                webhook_configured = bool(channel.config.get('webhook_url'))
                click.echo(f"   Webhook: {'Configured' if webhook_configured else 'Not configured'}")
                
            elif channel.channel_type == NotificationChannel.WEBHOOK:
                url_configured = bool(channel.config.get('url'))
                click.echo(f"   URL: {'Configured' if url_configured else 'Not configured'}")
            
            click.echo()
        
    except Exception as e:
        logger.error(f"Failed to list channels: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.argument('channel_type', type=click.Choice(['email', 'slack', 'webhook']))
@click.pass_context
def test_channel(ctx, channel_type):
    """Test a notification channel."""
    try:
        alert_manager = create_alert_manager(ctx.obj.get('config_path'))
        channel_enum = NotificationChannel(channel_type)
        
        click.echo(f"🧪 Testing {channel_type.upper()} notification channel...")
        
        success = alert_manager.test_notification_channel(channel_enum)
        
        if success:
            click.echo(f"✅ {channel_type.upper()} test notification sent successfully!")
        else:
            click.echo(f"❌ {channel_type.upper()} test notification failed!")
            click.echo("Check the logs for detailed error information.")
        
    except Exception as e:
        logger.error(f"Failed to test notification channel: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.option('--days', '-d', default=7, help='Number of days of history to show')
@click.pass_context
def history(ctx, days):
    """Show alert history."""
    try:
        alert_manager = create_alert_manager(ctx.obj.get('config_path'))
        alerts_history = alert_manager.get_alert_history(days)
        
        if not alerts_history:
            click.echo(f"No alerts found in the last {days} days.")
            return
        
        click.echo(f"📊 Alert History (Last {days} days)")
        click.echo("=" * 80)
        
        for alert in alerts_history:
            severity_color = {
                AlertSeverity.INFO: "blue",
                AlertSeverity.WARNING: "yellow",
                AlertSeverity.CRITICAL: "red", 
                AlertSeverity.EMERGENCY: "bright_red"
            }.get(alert.severity, "white")
            
            status_icons = []
            if alert.acknowledged:
                status_icons.append("👍")
            if alert.resolved:
                status_icons.append("✅")
            if alert.escalation_level > 0:
                status_icons.append(f"🔺{alert.escalation_level}")
            
            status_str = " ".join(status_icons) if status_icons else "🔴"
            
            click.echo(f"{status_str} {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')} - ", nl=False)
            click.secho(f"{alert.severity.value.upper()}", fg=severity_color, nl=False)
            click.echo(f" - {alert.condition_name}")
            click.echo(f"   {alert.message}")
            if alert.city:
                click.echo(f"   City: {alert.city}")
            click.echo()
        
    except Exception as e:
        logger.error(f"Failed to get alert history: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.option('--days', '-d', default=30, help='Number of days to analyze')
@click.pass_context
def stats(ctx, days):
    """Show alert statistics."""
    try:
        alert_manager = create_alert_manager(ctx.obj.get('config_path'))
        stats = alert_manager.get_alert_statistics(days)
        
        if not stats or stats['total_alerts'] == 0:
            click.echo(f"No alert statistics available for the last {days} days.")
            return
        
        click.echo(f"📈 Alert Statistics (Last {days} days)")
        click.echo("=" * 50)
        click.echo(f"Total Alerts: {stats['total_alerts']}")
        click.echo(f"Resolved: {stats['resolved_alerts']} ({stats['resolution_rate']:.1%})")
        click.echo(f"Acknowledged: {stats['acknowledged_alerts']} ({stats['acknowledgment_rate']:.1%})")
        
        click.echo("\n📊 By Severity:")
        for severity, count in stats['alerts_by_severity'].items():
            if count > 0:
                click.echo(f"  {severity.upper()}: {count}")
        
        if stats.get('top_conditions'):
            click.echo("\n🔝 Top Alert Conditions:")
            for condition in stats['top_conditions'][:5]:
                click.echo(f"  {condition['condition']}: {condition['count']}")
        
    except Exception as e:
        logger.error(f"Failed to get alert statistics: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.argument('alert_id')
@click.option('--user', '-u', default='cli', help='User acknowledging the alert')
@click.pass_context
def acknowledge(ctx, alert_id, user):
    """Acknowledge an alert."""
    try:
        alert_manager = create_alert_manager(ctx.obj.get('config_path'))
        
        success = alert_manager.acknowledge_alert(alert_id, user)
        
        if success:
            click.echo(f"✅ Alert {alert_id} acknowledged by {user}")
        else:
            click.echo(f"❌ Failed to acknowledge alert {alert_id}")
        
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.argument('alert_id')
@click.pass_context
def resolve(ctx, alert_id):
    """Resolve an alert."""
    try:
        alert_manager = create_alert_manager(ctx.obj.get('config_path'))
        
        success = alert_manager.resolve_alert(alert_id)
        
        if success:
            click.echo(f"✅ Alert {alert_id} resolved")
        else:
            click.echo(f"❌ Failed to resolve alert {alert_id}")
        
    except Exception as e:
        logger.error(f"Failed to resolve alert: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.pass_context
def active(ctx):
    """Show active (unresolved) alerts."""
    try:
        alert_manager = create_alert_manager(ctx.obj.get('config_path'))
        active_alerts = alert_manager.get_active_alerts()
        
        if not active_alerts:
            click.echo("✅ No active alerts.")
            return
        
        click.echo(f"🚨 Active Alerts ({len(active_alerts)})")
        click.echo("=" * 80)
        
        for alert in sorted(active_alerts, key=lambda a: a.triggered_at, reverse=True):
            severity_color = {
                AlertSeverity.INFO: "blue",
                AlertSeverity.WARNING: "yellow",
                AlertSeverity.CRITICAL: "red",
                AlertSeverity.EMERGENCY: "bright_red"
            }.get(alert.severity, "white")
            
            age = datetime.now() - alert.triggered_at
            age_str = f"{age.days}d {age.seconds//3600}h {(age.seconds%3600)//60}m"
            
            status_icons = []
            if alert.acknowledged:
                status_icons.append("👍")
            if alert.escalation_level > 0:
                status_icons.append(f"🔺{alert.escalation_level}")
            
            status_str = " ".join(status_icons) if status_icons else "🔴"
            
            click.echo(f"{status_str} [{alert.alert_id}] ", nl=False)
            click.secho(f"{alert.severity.value.upper()}", fg=severity_color, nl=False)
            click.echo(f" - {alert.condition_name} ({age_str} ago)")
            click.echo(f"   {alert.message}")
            if alert.city:
                click.echo(f"   City: {alert.city}")
            click.echo()
        
    except Exception as e:
        logger.error(f"Failed to get active alerts: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.pass_context
def cleanup(ctx):
    """Clean up old alerts based on retention policy."""
    try:
        alert_manager = create_alert_manager(ctx.obj.get('config_path'))
        
        cleaned_count = alert_manager.cleanup_old_alerts()
        
        if cleaned_count > 0:
            click.echo(f"🧹 Cleaned up {cleaned_count} old alerts")
        else:
            click.echo("✅ No old alerts to clean up")
        
    except Exception as e:
        logger.error(f"Failed to cleanup alerts: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.pass_context
def validate_config(ctx):
    """Validate alert configuration."""
    try:
        config_manager = AlertConfigManager(ctx.obj.get('config_path'))
        config = config_manager.load_configuration()
        
        errors = config_manager.validate_configuration(config)
        
        if not errors:
            click.echo("✅ Alert configuration is valid")
        else:
            click.echo("❌ Alert configuration has errors:")
            for error in errors:
                click.echo(f"  • {error}")
        
    except Exception as e:
        logger.error(f"Failed to validate configuration: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.option('--name', required=True, help='Condition name')
@click.option('--type', 'condition_type', required=True, 
              type=click.Choice([t.value for t in AlertConditionType]),
              help='Condition type')
@click.option('--threshold', required=True, type=float, help='Threshold value')
@click.option('--operator', required=True, 
              type=click.Choice(['>', '<', '>=', '<=', '==']),
              help='Comparison operator')
@click.option('--severity', required=True,
              type=click.Choice([s.value for s in AlertSeverity]),
              help='Alert severity')
@click.option('--description', help='Condition description')
@click.option('--enabled/--disabled', default=True, help='Enable/disable condition')
@click.pass_context
def add_condition(ctx, name, condition_type, threshold, operator, severity, description, enabled):
    """Add a new alert condition."""
    try:
        config_manager = AlertConfigManager(ctx.obj.get('config_path'))
        
        condition = AlertCondition(
            name=name,
            condition_type=AlertConditionType(condition_type),
            threshold_value=threshold,
            comparison_operator=operator,
            severity=AlertSeverity(severity),
            enabled=enabled,
            description=description or f"Alert when {condition_type} {operator} {threshold}"
        )
        
        success = config_manager.add_alert_condition(condition)
        
        if success:
            click.echo(f"✅ Added alert condition: {name}")
        else:
            click.echo(f"❌ Failed to add alert condition: {name}")
        
    except Exception as e:
        logger.error(f"Failed to add alert condition: {e}")
        click.echo(f"❌ Error: {e}")


@alerts.command()
@click.argument('condition_name')
@click.pass_context
def remove_condition(ctx, condition_name):
    """Remove an alert condition."""
    try:
        config_manager = AlertConfigManager(ctx.obj.get('config_path'))
        
        success = config_manager.remove_alert_condition(condition_name)
        
        if success:
            click.echo(f"✅ Removed alert condition: {condition_name}")
        else:
            click.echo(f"❌ Failed to remove alert condition: {condition_name}")
        
    except Exception as e:
        logger.error(f"Failed to remove alert condition: {e}")
        click.echo(f"❌ Error: {e}")


if __name__ == '__main__':
    alerts()


