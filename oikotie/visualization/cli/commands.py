#!/usr/bin/env python3
"""
CLI Commands for Oikotie Visualization
Provides command-line interface for generating dashboards and visualizations
"""

import argparse
import webbrowser
from pathlib import Path
import sys

from ..dashboard.multi_city import MultiCityDashboard
from ..dashboard.espoo_dashboard import EspooDashboard
from ..dashboard.city_selector import CitySelector


def dashboard_command(args):
    """Generate dashboard based on command-line arguments"""
    print("🎨 Oikotie Dashboard Generator")
    print("=" * 50)
    
    # Handle city selector
    if args.selector:
        selector = CitySelector()
        selector_path = selector.create_dashboard_index()
        
        if args.open:
            print(f"🌐 Opening city selector in browser...")
            webbrowser.open(f"file://{Path(selector_path).absolute()}")
        
        return selector_path
    
    # Handle comparative dashboard
    if args.comparative:
        cities = [city.strip() for city in args.comparative.split(',')]
        
        if len(cities) < 2:
            print("❌ Comparative dashboard requires at least 2 cities")
            return None
        
        # Parse options if provided
        options = []
        if args.options:
            options = [option.strip() for option in args.options.split(',')]
            print(f"🔧 Using options: {', '.join(options)}")
        
        print(f"🎨 Generating comparative dashboard for: {', '.join(cities)}")
        dashboard = MultiCityDashboard()
        dashboard_path = dashboard.create_comparative_dashboard(
            cities, 
            sample_size=args.sample_size,
            options=options
        )
        
        if args.open and dashboard_path:
            print(f"🌐 Opening comparative dashboard in browser...")
            webbrowser.open(f"file://{Path(dashboard_path).absolute()}")
        
        return dashboard_path
    
    # Handle city-specific dashboard
    if args.city:
        city = args.city.strip()
        
        # Handle enhanced Espoo dashboard
        if city.lower() == 'espoo' and args.enhanced:
            print(f"🎨 Generating enhanced Espoo dashboard")
            dashboard = EspooDashboard()
            dashboard_path = dashboard.create_espoo_dashboard(sample_size=args.sample_size)
        # Handle regular city dashboard
        else:
            print(f"🎨 Generating dashboard for {city}")
            dashboard = MultiCityDashboard()
            dashboard_path = dashboard.create_city_dashboard(
                city, 
                enhanced_mode=args.enhanced, 
                sample_size=args.sample_size
            )
        
        if args.open and dashboard_path:
            print(f"🌐 Opening dashboard in browser...")
            webbrowser.open(f"file://{Path(dashboard_path).absolute()}")
        
        return dashboard_path
    
    # Default to city selector if no specific options provided
    print("ℹ️ No specific dashboard options provided, showing city selector")
    selector = CitySelector()
    selector_path = selector.create_dashboard_index()
    
    if args.open:
        print(f"🌐 Opening city selector in browser...")
        webbrowser.open(f"file://{Path(selector_path).absolute()}")
    
    return selector_path


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Oikotie Visualization CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser("dashboard", help="Generate interactive dashboards")
    dashboard_parser.add_argument("--city", help="City to generate dashboard for")
    dashboard_parser.add_argument("--enhanced", action="store_true", help="Generate enhanced dashboard with building footprints")
    dashboard_parser.add_argument("--comparative", help="Generate comparative dashboard for comma-separated list of cities")
    dashboard_parser.add_argument("--options", help="Dashboard options as comma-separated list (e.g., 'price_comparison,building_footprints')")
    dashboard_parser.add_argument("--selector", action="store_true", help="Show city selector interface")
    dashboard_parser.add_argument("--sample-size", type=int, default=2000, help="Number of listings to include (default: 2000)")
    dashboard_parser.add_argument("--open", action="store_true", help="Open dashboard in browser after generation")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute command
    if args.command == "dashboard":
        dashboard_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()