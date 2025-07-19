#!/usr/bin/env python3
"""
Configuration Management CLI Tool

This script provides command-line utilities for managing scraper configurations,
including validation, template generation, and configuration testing.

Usage:
    python -m oikotie.automation.config_cli --help
    python -m oikotie.automation.config_cli validate
    python -m oikotie.automation.config_cli generate-template basic
    python -m oikotie.automation.config_cli test-config --environment production
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

from loguru import logger
from .config import ConfigurationManager, ConfigValidationError, create_cli_parser


def setup_logging(log_level: str = "INFO"):
    """Set up logging configuration"""
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )


def validate_config_command(args):
    """Validate configuration files"""
    logger.info("Validating configuration...")
    
    try:
        config_manager = ConfigurationManager(args.config_dir)
        config = config_manager.load_config(
            config_files=args.config_files,
            environment=args.environment
        )
        
        logger.success("✅ Configuration validation passed!")
        logger.info(f"Environment: {config.environment}")
        logger.info(f"Tasks configured: {len(config.tasks)}")
        logger.info(f"Cluster mode: {config.cluster.enabled}")
        logger.info(f"Scheduling enabled: {config.scheduling.enabled}")
        logger.info(f"Configuration sources: {', '.join(config.loaded_from)}")
        
        if args.verbose:
            logger.info("Configuration details:")
            for i, task in enumerate(config.tasks):
                logger.info(f"  Task {i+1}: {task.city} ({'enabled' if task.enabled else 'disabled'})")
            logger.info(f"  Database: {config.database.path}")
            logger.info(f"  Log level: {config.monitoring.log_level}")
        
        return True
        
    except ConfigValidationError as e:
        logger.error(f"❌ Configuration validation failed:")
        for line in str(e).split('\n'):
            if line.strip():
                logger.error(f"  {line.strip()}")
        return False
    except Exception as e:
        logger.error(f"❌ Error validating configuration: {e}")
        return False


def generate_template_command(args):
    """Generate configuration templates"""
    logger.info(f"Generating {args.template_type} configuration template...")
    
    try:
        config_manager = ConfigurationManager()
        template = config_manager.generate_template(args.template_type)
        
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(template)
            logger.success(f"✅ Template saved to: {output_path}")
        else:
            print(template)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error generating template: {e}")
        return False


def test_config_command(args):
    """Test configuration loading and merging"""
    logger.info("Testing configuration loading...")
    
    try:
        config_manager = ConfigurationManager(args.config_dir)
        
        # Test with different environments
        environments = args.environments or ['development', 'production']
        
        for env in environments:
            logger.info(f"\n--- Testing environment: {env} ---")
            
            try:
                config = config_manager.load_config(
                    config_files=args.config_files,
                    environment=env
                )
                
                logger.success(f"✅ {env} configuration loaded successfully")
                logger.info(f"  Tasks: {len(config.tasks)}")
                logger.info(f"  Database: {config.database.path}")
                logger.info(f"  Log level: {config.monitoring.log_level}")
                logger.info(f"  Cluster: {config.cluster.enabled}")
                logger.info(f"  Sources: {', '.join(config.loaded_from)}")
                
            except Exception as e:
                logger.error(f"❌ {env} configuration failed: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing configurations: {e}")
        return False


def export_config_command(args):
    """Export current configuration"""
    logger.info("Exporting configuration...")
    
    try:
        config_manager = ConfigurationManager(args.config_dir)
        config = config_manager.load_config(
            config_files=args.config_files,
            environment=args.environment
        )
        
        exported = config_manager.export_config(
            format=args.format,
            include_defaults=args.include_defaults
        )
        
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(exported)
            logger.success(f"✅ Configuration exported to: {output_path}")
        else:
            print(exported)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error exporting configuration: {e}")
        return False


def watch_config_command(args):
    """Watch configuration files for changes"""
    logger.info("Starting configuration file watcher...")
    
    try:
        config_manager = ConfigurationManager(args.config_dir)
        
        # Load initial configuration
        config = config_manager.load_config(
            config_files=args.config_files,
            environment=args.environment
        )
        logger.info(f"Initial configuration loaded from: {', '.join(config.loaded_from)}")
        
        # Define reload callback
        def on_config_reload(old_config, new_config):
            logger.info("🔄 Configuration reloaded!")
            logger.info(f"Environment: {new_config.environment}")
            logger.info(f"Tasks: {len(new_config.tasks)}")
            
            if args.validate_on_reload:
                try:
                    config_manager._validate_config(new_config)
                    logger.success("✅ Reloaded configuration is valid")
                except ConfigValidationError as e:
                    logger.error(f"❌ Reloaded configuration is invalid: {e}")
        
        # Start watching
        config_manager.start_watching(on_config_reload)
        
        logger.info(f"👀 Watching configuration directory: {args.config_dir}")
        logger.info("Press Ctrl+C to stop watching...")
        
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping configuration watcher...")
            config_manager.stop_watching()
            logger.info("Configuration watcher stopped.")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error watching configuration: {e}")
        return False


def create_config_cli_parser():
    """Create CLI parser for configuration management"""
    parser = argparse.ArgumentParser(
        description="Configuration Management CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s validate --environment production
  %(prog)s generate-template basic --output config/my_config.json
  %(prog)s test-config --environments development production
  %(prog)s export --environment production --output prod_config.json
  %(prog)s watch --environment development --validate-on-reload
        """
    )
    
    # Global options
    parser.add_argument('--config-dir', default='config',
                       help='Configuration directory (default: config)')
    parser.add_argument('--config-files', nargs='+',
                       help='Specific configuration files to load')
    parser.add_argument('--environment', '-e',
                       help='Environment name')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Log level')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration')
    validate_parser.set_defaults(func=validate_config_command)
    
    # Generate template command
    template_parser = subparsers.add_parser('generate-template', help='Generate configuration template')
    template_parser.add_argument('template_type', choices=['basic', 'cluster'],
                                help='Template type to generate')
    template_parser.add_argument('--output', '-o',
                                help='Output file path')
    template_parser.set_defaults(func=generate_template_command)
    
    # Test config command
    test_parser = subparsers.add_parser('test-config', help='Test configuration loading')
    test_parser.add_argument('--environments', nargs='+',
                            help='Environments to test (default: development, production)')
    test_parser.set_defaults(func=test_config_command)
    
    # Export config command
    export_parser = subparsers.add_parser('export', help='Export configuration')
    export_parser.add_argument('--format', choices=['json'], default='json',
                              help='Export format')
    export_parser.add_argument('--output', '-o',
                              help='Output file path')
    export_parser.add_argument('--include-defaults', action='store_true',
                              help='Include default values in export')
    export_parser.set_defaults(func=export_config_command)
    
    # Watch config command
    watch_parser = subparsers.add_parser('watch', help='Watch configuration files for changes')
    watch_parser.add_argument('--validate-on-reload', action='store_true',
                             help='Validate configuration on reload')
    watch_parser.set_defaults(func=watch_config_command)
    
    return parser


def main():
    """Main CLI entry point"""
    parser = create_config_cli_parser()
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    
    # Check if command was provided
    if not hasattr(args, 'func'):
        parser.print_help()
        return 1
    
    # Execute command
    try:
        success = args.func(args)
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())