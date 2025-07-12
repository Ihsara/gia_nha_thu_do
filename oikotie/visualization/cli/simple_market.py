#!/usr/bin/env python3
"""
CLI for Simple Market Dashboard
"""

from oikotie.visualization.dashboard.simple_market import SimpleMarketDashboard

def main():
    print("🏠 SIMPLE MARKET DASHBOARD")
    print("Fast visualization using existing coordinates")
    print("=" * 60)
    
    try:
        dashboard = SimpleMarketDashboard()
        output_path = dashboard.generate_dashboard()
        
        print("=" * 60)
        print("✅ SIMPLE MARKET DASHBOARD COMPLETE")
        print("=" * 60)
        print(f"🎯 Features:")
        print(f"   📍 Direct coordinate visualization (no spatial matching)")
        print(f"   🗺️ Interactive map with price-based markers")
        print(f"   📊 Market analysis charts")
        print(f"   📈 Property type and postal code analysis")
        print()
        print(f"🌐 Dashboard created: {output_path}")
        print("🚀 Ready for market analysis!")
        
    except Exception as e:
        print(f"❌ Error creating dashboard: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
