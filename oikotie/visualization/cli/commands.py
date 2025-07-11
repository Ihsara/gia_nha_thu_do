#!/usr/bin/env python3
"""
Command-line interface for the Oikotie visualization package.

This module provides CLI commands for dashboard generation, mapping, analysis,
and other visualization tasks with configurable output paths.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, List
import logging

from ..utils.config import get_city_config, OutputConfig, get_default_config
from ..dashboard.enhanced import EnhancedDashboard
from ..dashboard.builder import DashboardBuilder
from ..utils.building_analyzer import BuildingAnalyzer
from ..utils.data_loader import load_sample_data, validate_database_schema


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def dashboard_command(args):
    """Generate dashboard visualizations."""
    print(f"🎛️ Generating dashboard for {args.city}")
    
    try:
        # Setup configuration
        city_config = get_city_config(args.city)
        output_config = OutputConfig(args.output) if args.output else OutputConfig()
        
        # Create dashboard
        if args.enhanced:
            dashboard = EnhancedDashboard(output_dir=str(output_config.dashboard_dir))
            result_file = dashboard.run_dashboard_creation()
        else:
            builder = DashboardBuilder(output_dir=str(output_config.dashboard_dir))
            result_file = builder.create_enhanced_dashboard_solution()
        
        print(f"✅ Dashboard generated: {result_file}")
        
        if args.open:
            import webbrowser
            webbrowser.open(f"file://{Path(result_file).absolute()}")
            
    except Exception as e:
        print(f"❌ Dashboard generation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def analyze_command(args):
    """Analyze building properties and generate reports."""
    print(f"🔍 Analyzing buildings for {args.city}")
    
    try:
        # Setup configuration
        city_config = get_city_config(args.city)
        output_config = OutputConfig(args.output) if args.output else OutputConfig()
        
        # Create analyzer
        analyzer = BuildingAnalyzer(output_dir=str(output_config.data_dir))
        
        if args.building_id:
            # Analyze specific building
            result = analyzer.investigate_building_by_id(args.building_id)
            print(f"✅ Building {args.building_id} analysis completed")
        else:
            # General analysis
            result = analyzer.analyze_address_patterns()
            print(f"✅ Address pattern analysis completed")
        
        print(f"📊 Results saved to: {output_config.data_dir}")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def validate_command(args):
    """Validate data and run tests."""
    print(f"🧪 Running validation tests")
    
    try:
        output_config = OutputConfig(args.output) if args.output else OutputConfig()
        
        if args.schema:
            # Validate database schema
            schema_info = validate_database_schema()
            print(f"🗄️ Database Schema Validation:")
            for table, info in schema_info.items():
                if info['exists']:
                    print(f"  ✅ {table}: {info['row_count']} rows")
                else:
                    print(f"  ❌ {table}: {info.get('error', 'Missing')}")
        
        if args.sample:
            # Load and validate sample data
            sample_data = load_sample_data(limit=args.sample, city=args.city)
            print(f"📊 Sample Data Validation:")
            print(f"  ✅ Listings: {sample_data['summary']['listings_count']}")
            print(f"  ✅ Buildings: {sample_data['summary']['buildings_count']}")
        
        print(f"✅ Validation completed successfully")
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def info_command(args):
    """Display system and configuration information."""
    print(f"ℹ️ Oikotie Visualization Package Information")
    print("=" * 50)
    
    try:
        # Display available cities
        from ..utils.config import CITY_CONFIGS
        print(f"📍 Available Cities:")
        for city_name, city_config in CITY_CONFIGS.items():
            print(f"  - {city_config.name}: {city_config.center_lat}, {city_config.center_lon}")
        
        # Display database status
        schema_info = validate_database_schema()
        print(f"\n🗄️ Database Status:")
        for table, info in schema_info.items():
            if info['exists']:
                print(f"  ✅ {table}: {info['row_count']} rows")
            else:
                print(f"  ❌ {table}: Not available")
        
        # Display output configuration
        output_config = OutputConfig(args.output) if args.output else OutputConfig()
        print(f"\n📁 Output Configuration:")
        print(f"  - Base directory: {output_config.base_output_dir}")
        print(f"  - Dashboard: {output_config.dashboard_dir}")
        print(f"  - Maps: {output_config.maps_dir}")
        print(f"  - Validation: {output_config.validation_dir}")
        
    except Exception as e:
        print(f"❌ Info command failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()


def create_parser():
    """Create argument parser for CLI commands."""
    parser = argparse.ArgumentParser(
        description='Oikotie Visualization Package CLI',
        prog='oikotie.visualization'
    )
    
    # Global arguments
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-o', '--output', type=str, help='Output directory (default: output/)')
    parser.add_argument('--city', type=str, default='helsinki', 
                       choices=['helsinki', 'tampere', 'turku'], 
                       help='Target city (default: helsinki)')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Generate dashboard visualizations')
    dashboard_parser.add_argument('--enhanced', action='store_true', 
                                 help='Use enhanced dashboard (default: builder)')
    dashboard_parser.add_argument('--open', action='store_true', 
                                 help='Open generated dashboard in browser')
    dashboard_parser.set_defaults(func=dashboard_command)
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze building properties')
    analyze_parser.add_argument('--building-id', type=str, 
                                help='Specific building ID to analyze')
    analyze_parser.set_defaults(func=analyze_command)
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate data and run tests')
    validate_parser.add_argument('--schema', action='store_true', 
                                help='Validate database schema')
    validate_parser.add_argument('--sample', type=int, default=10,
                                help='Load and validate sample data (default: 10)')
    validate_parser.set_defaults(func=validate_command)
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Display system information')
    info_parser.set_defaults(func=info_command)
    
    return parser


def main(argv: Optional[List[str]] = None):
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Execute command
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
