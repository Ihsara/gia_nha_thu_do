"""
Security CLI for Daily Scraper Automation

This module provides command-line interface for security operations including
credential management, security scanning, backup operations, and audit log analysis.
"""

import json
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import click
from loguru import logger

from .security import SecurityManager, SecurityConfig, create_security_manager
from .config_manager import ConfigurationManager


@click.group()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--node-id', help='Node identifier')
@click.pass_context
def security_cli(ctx, config: Optional[str], node_id: Optional[str]):
    """Security management CLI for daily scraper automation."""
    ctx.ensure_object(dict)
    
    # Load security configuration
    try:
        if config:
            config_manager = ConfigurationManager([config])
            scraper_config = config_manager.load_configuration()
            security_config = SecurityConfig(
                encryption_enabled=True,
                audit_enabled=True,
                rate_limiting_enabled=True,
                vulnerability_scanning_enabled=True,
                backup_enabled=True
            )
        else:
            security_config = SecurityConfig()
        
        # Create security manager
        ctx.obj['security_manager'] = create_security_manager(security_config, node_id)
        ctx.obj['config'] = security_config
        
    except Exception as e:
        click.echo(f"Error initializing security system: {e}", err=True)
        sys.exit(1)


@security_cli.group()
def credentials():
    """Credential management commands."""
    pass


@credentials.command()
@click.argument('key')
@click.argument('value')
@click.option('--description', '-d', help='Credential description')
@click.pass_context
def store(ctx, key: str, value: str, description: Optional[str]):
    """Store a credential securely."""
    security_manager = ctx.obj['security_manager']
    
    try:
        success = security_manager.credential_manager.store_credential(key, value, description)
        if success:
            click.echo(f"✅ Credential '{key}' stored successfully")
            security_manager.audit_logger.log_configuration_change(
                "credential_stored",
                resource=key,
                description=description
            )
        else:
            click.echo(f"❌ Failed to store credential '{key}'", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error storing credential: {e}", err=True)
        sys.exit(1)


@credentials.command()
@click.argument('key')
@click.pass_context
def get(ctx, key: str):
    """Retrieve a credential."""
    security_manager = ctx.obj['security_manager']
    
    try:
        value = security_manager.credential_manager.get_credential(key)
        if value is not None:
            click.echo(f"Credential '{key}': {value}")
            security_manager.audit_logger.log_data_access(
                "credential_retrieved",
                resource=key
            )
        else:
            click.echo(f"❌ Credential '{key}' not found", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error retrieving credential: {e}", err=True)
        sys.exit(1)


@credentials.command()
@click.pass_context
def list(ctx):
    """List all stored credentials."""
    security_manager = ctx.obj['security_manager']
    
    try:
        credentials = security_manager.credential_manager.list_credentials()
        
        if not credentials:
            click.echo("No credentials stored")
            return
        
        click.echo("Stored credentials:")
        click.echo("-" * 80)
        
        for cred in credentials:
            click.echo(f"Key: {cred['key']}")
            if cred['description']:
                click.echo(f"  Description: {cred['description']}")
            click.echo(f"  Created: {cred['created_at']}")
            if cred['last_accessed']:
                click.echo(f"  Last accessed: {cred['last_accessed']}")
            click.echo()
        
        security_manager.audit_logger.log_data_access(
            "credentials_listed",
            resource="credential_store",
            count=len(credentials)
        )
        
    except Exception as e:
        click.echo(f"Error listing credentials: {e}", err=True)
        sys.exit(1)


@credentials.command()
@click.argument('key')
@click.confirmation_option(prompt='Are you sure you want to delete this credential?')
@click.pass_context
def delete(ctx, key: str):
    """Delete a credential."""
    security_manager = ctx.obj['security_manager']
    
    try:
        success = security_manager.credential_manager.delete_credential(key)
        if success:
            click.echo(f"✅ Credential '{key}' deleted successfully")
            security_manager.audit_logger.log_configuration_change(
                "credential_deleted",
                resource=key
            )
        else:
            click.echo(f"❌ Credential '{key}' not found", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error deleting credential: {e}", err=True)
        sys.exit(1)


@credentials.command()
@click.confirmation_option(prompt='Are you sure you want to rotate the master key?')
@click.pass_context
def rotate_key(ctx):
    """Rotate the master encryption key."""
    security_manager = ctx.obj['security_manager']
    
    try:
        success = security_manager.credential_manager.rotate_master_key()
        if success:
            click.echo("✅ Master key rotated successfully")
            security_manager.audit_logger.log_security_event(
                "master_key_rotated",
                threat_level="medium"
            )
        else:
            click.echo("❌ Failed to rotate master key", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error rotating master key: {e}", err=True)
        sys.exit(1)


@security_cli.group()
def scan():
    """Security scanning commands."""
    pass


@scan.command()
@click.option('--output', '-o', help='Output file for scan results')
@click.option('--format', '-f', type=click.Choice(['json', 'text']), default='text', help='Output format')
@click.pass_context
def run(ctx, output: Optional[str], format: str):
    """Run security vulnerability scan."""
    security_manager = ctx.obj['security_manager']
    
    try:
        click.echo("🔍 Running security scan...")
        results = security_manager.vulnerability_scanner.run_security_scan()
        
        if format == 'json':
            output_text = json.dumps(results, indent=2)
        else:
            output_text = _format_scan_results(results)
        
        if output:
            Path(output).write_text(output_text)
            click.echo(f"📄 Scan results saved to {output}")
        else:
            click.echo(output_text)
        
        # Show summary
        summary = results['summary']
        status = results['overall_status']
        
        if status == 'critical':
            click.echo(f"🚨 CRITICAL: {summary['critical']} critical issues found!", err=True)
        elif status == 'fail':
            click.echo(f"❌ FAILED: {summary['failures']} failures found", err=True)
        elif status == 'warning':
            click.echo(f"⚠️  WARNING: {summary['warnings']} warnings found")
        else:
            click.echo("✅ PASSED: No security issues found")
        
    except Exception as e:
        click.echo(f"Error running security scan: {e}", err=True)
        sys.exit(1)


@scan.command()
@click.pass_context
def status(ctx):
    """Show security scan status."""
    security_manager = ctx.obj['security_manager']
    
    try:
        latest_scan = security_manager.vulnerability_scanner.get_latest_scan_results()
        
        if not latest_scan:
            click.echo("No security scans have been run")
            return
        
        click.echo("Latest Security Scan Results:")
        click.echo("-" * 40)
        click.echo(f"Scan ID: {latest_scan['scan_id']}")
        click.echo(f"Timestamp: {latest_scan['timestamp']}")
        click.echo(f"Status: {latest_scan['overall_status']}")
        click.echo(f"Duration: {latest_scan['scan_duration_seconds']:.2f}s")
        
        summary = latest_scan['summary']
        click.echo(f"\nSummary:")
        click.echo(f"  Total checks: {summary['total_checks']}")
        click.echo(f"  Passed: {summary['passed']}")
        click.echo(f"  Warnings: {summary['warnings']}")
        click.echo(f"  Failures: {summary['failures']}")
        click.echo(f"  Critical: {summary['critical']}")
        
    except Exception as e:
        click.echo(f"Error getting scan status: {e}", err=True)
        sys.exit(1)


@security_cli.group()
def backup():
    """Backup management commands."""
    pass


@backup.command()
@click.option('--name', '-n', help='Backup name (auto-generated if not provided)')
@click.pass_context
def create(ctx, name: Optional[str]):
    """Create a system backup."""
    security_manager = ctx.obj['security_manager']
    
    try:
        click.echo("💾 Creating backup...")
        results = security_manager.backup_manager.create_backup(name)
        
        if results['status'] == 'success':
            click.echo(f"✅ Backup created successfully: {results['backup_name']}")
            click.echo(f"📁 Path: {results['backup_path']}")
            click.echo(f"📊 Size: {results['total_size_mb']:.1f} MB")
            click.echo(f"⏱️  Duration: {results['duration_seconds']:.1f}s")
            
            # Show component details
            click.echo("\nComponents backed up:")
            for component, details in results['components'].items():
                if details['status'] == 'success':
                    click.echo(f"  ✅ {component}: {details['size_mb']:.1f} MB")
                else:
                    click.echo(f"  ❌ {component}: {details.get('error', 'Failed')}")
        else:
            click.echo(f"❌ Backup failed: {results.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"Error creating backup: {e}", err=True)
        sys.exit(1)


@backup.command()
@click.pass_context
def list(ctx):
    """List available backups."""
    security_manager = ctx.obj['security_manager']
    
    try:
        backups = security_manager.backup_manager.list_backups()
        
        if not backups:
            click.echo("No backups found")
            return
        
        click.echo("Available backups:")
        click.echo("-" * 80)
        
        for backup in backups:
            click.echo(f"Name: {backup['backup_name']}")
            click.echo(f"  Created: {backup['created_at']}")
            if 'total_size_mb' in backup:
                click.echo(f"  Size: {backup['total_size_mb']:.1f} MB")
            if 'has_manifest' in backup and not backup['has_manifest']:
                click.echo("  ⚠️  No manifest file")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error listing backups: {e}", err=True)
        sys.exit(1)


@backup.command()
@click.confirmation_option(prompt='Are you sure you want to clean up old backups?')
@click.pass_context
def cleanup(ctx):
    """Clean up old backups."""
    security_manager = ctx.obj['security_manager']
    
    try:
        click.echo("🧹 Cleaning up old backups...")
        results = security_manager.backup_manager.cleanup_old_backups()
        
        deleted_count = len(results['deleted_backups'])
        kept_count = len(results['kept_backups'])
        error_count = len(results['errors'])
        
        click.echo(f"✅ Cleanup completed:")
        click.echo(f"  Deleted: {deleted_count} backups")
        click.echo(f"  Kept: {kept_count} backups")
        
        if error_count > 0:
            click.echo(f"  ❌ Errors: {error_count}")
            for error in results['errors']:
                click.echo(f"    {error}")
        
        if deleted_count > 0:
            click.echo("\nDeleted backups:")
            for backup in results['deleted_backups']:
                click.echo(f"  - {backup['name']} ({backup['date']})")
        
    except Exception as e:
        click.echo(f"Error cleaning up backups: {e}", err=True)
        sys.exit(1)


@security_cli.command()
@click.pass_context
def status(ctx):
    """Show comprehensive security status."""
    security_manager = ctx.obj['security_manager']
    
    try:
        status = security_manager.get_security_status()
        
        click.echo("Security Status Report")
        click.echo("=" * 50)
        click.echo(f"Node ID: {status['node_id']}")
        click.echo(f"Timestamp: {status['timestamp']}")
        click.echo(f"Security Level: {status['security_level'].upper()}")
        click.echo()
        
        # Component status
        click.echo("Component Status:")
        click.echo("-" * 30)
        
        for component, details in status['components'].items():
            component_name = component.replace('_', ' ').title()
            click.echo(f"{component_name}:")
            
            for key, value in details.items():
                if isinstance(value, bool):
                    status_icon = "✅" if value else "❌"
                    click.echo(f"  {key}: {status_icon} {value}")
                else:
                    click.echo(f"  {key}: {value}")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error getting security status: {e}", err=True)
        sys.exit(1)


def _format_scan_results(results: Dict[str, Any]) -> str:
    """Format scan results for text output."""
    output = []
    
    output.append("Security Scan Results")
    output.append("=" * 50)
    output.append(f"Scan ID: {results['scan_id']}")
    output.append(f"Timestamp: {results['timestamp']}")
    output.append(f"Status: {results['overall_status'].upper()}")
    output.append(f"Duration: {results['scan_duration_seconds']:.2f}s")
    output.append("")
    
    # Summary
    summary = results['summary']
    output.append("Summary:")
    output.append("-" * 20)
    output.append(f"Total checks: {summary['total_checks']}")
    output.append(f"Passed: {summary['passed']}")
    output.append(f"Warnings: {summary['warnings']}")
    output.append(f"Failures: {summary['failures']}")
    output.append(f"Critical: {summary['critical']}")
    output.append("")
    
    # Detailed results
    output.append("Detailed Results:")
    output.append("-" * 30)
    
    for check_name, check_result in results['checks'].items():
        status_icon = {
            'pass': '✅',
            'warning': '⚠️',
            'fail': '❌',
            'critical': '🚨'
        }.get(check_result['status'], '❓')
        
        output.append(f"{status_icon} {check_name.replace('_', ' ').title()}")
        output.append(f"   Status: {check_result['status'].upper()}")
        output.append(f"   Message: {check_result['message']}")
        
        if check_result.get('details'):
            output.append("   Details:")
            for detail in check_result['details']:
                output.append(f"     - {detail}")
        
        if check_result.get('recommendations'):
            output.append("   Recommendations:")
            for rec in check_result['recommendations']:
                output.append(f"     - {rec}")
        
        output.append("")
    
    return "\n".join(output)


if __name__ == '__main__':
    security_cli()