#!/usr/bin/env python3
"""
CLI for Enhanced Finnish Real Estate Dashboard
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from oikotie.visualization.dashboard.enhanced_finnish import EnhancedFinnishDashboard

def main():
    """Generate Enhanced Finnish Real Estate Dashboard"""
    
    print("🏠 ENHANCED FINNISH REAL ESTATE DASHBOARD")
    print("Map-focused visualization with building highlighting")
    print("=" * 60)
    
    try:
        # Create dashboard
        dashboard = EnhancedFinnishDashboard()
        
        # Generate enhanced dashboard
        output_path = dashboard.generate_enhanced_dashboard()
        
        print("=" * 60)
        print("✅ ENHANCED FINNISH DASHBOARD COMPLETE")
        print("=" * 60)
        print("🎯 Features Implemented:")
        print("   📊 Map-focused layout (75% width)")
        print("   🏢 Buildings-only visualization (no listing markers)")
        print("   🇫🇮 Finnish housing market filtering:")
        print("      • Payment models (Rental, Shared Debt, Full Ownership)")
        print("      • Land ownership (Owned, Leased, Unknown)")
        print("      • Maintenance fee categories")
        print("      • Energy efficiency classes")
        print("   📱 Collapsible data panel with tabs")
        print("   🎨 Professional color-coded building highlighting")
        print("   📈 Finnish-specific market analytics")
        print()
        print(f"🌐 Dashboard created: {output_path}")
        print("🚀 Ready for Finnish real estate market analysis!")
        
        return output_path
        
    except Exception as e:
        print(f"❌ Error creating dashboard: {e}")
        return None

if __name__ == "__main__":
    main()
