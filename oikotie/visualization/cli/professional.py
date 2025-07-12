#!/usr/bin/env python3
"""
CLI command for Professional Real Estate Dashboard
Enhanced visualization platform for real estate professionals
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
import webbrowser

from ..dashboard.professional import ProfessionalRealEstateDashboard


def create_professional_dashboard(output_dir: Optional[str] = None, 
                                sample_size: int = 1500,
                                open_browser: bool = False) -> str:
    """Create professional real estate dashboard"""
    
    print("🏢 Creating Professional Real Estate Dashboard...")
    print("=" * 60)
    
    try:
        # Initialize professional dashboard
        dashboard = ProfessionalRealEstateDashboard(output_dir=output_dir)
        
        # Create dashboard with specified sample size
        result_path = dashboard.run_professional_dashboard_creation(sample_size=sample_size)
        
        if result_path and open_browser:
            print(f"\n🌐 Opening dashboard in browser...")
            webbrowser.open(f"file://{Path(result_path).absolute()}")
        
        return result_path
        
    except Exception as e:
        print(f"❌ Professional dashboard creation failed: {e}")
        return None


def main():
    """Main CLI entry point for professional dashboard"""
    parser = argparse.ArgumentParser(
        description='Create Professional Real Estate Dashboard',
        prog='professional-dashboard'
    )
    
    parser.add_argument('-o', '--output', type=str, 
                       help='Output directory (default: output/professional_dashboard)')
    parser.add_argument('-s', '--sample-size', type=int, default=1500,
                       help='Sample size for map performance (default: 1500)')
    parser.add_argument('--open', action='store_true',
                       help='Open dashboard in browser after creation')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Create professional dashboard
    result_path = create_professional_dashboard(
        output_dir=args.output,
        sample_size=args.sample_size,
        open_browser=args.open
    )
    
    if result_path:
        print(f"\n✅ SUCCESS: Professional dashboard created")
        print(f"📁 Location: {result_path}")
        print("🎯 Features: Building-level precision, market analytics, interactive charts")
        return 0
    else:
        print("❌ Dashboard creation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
