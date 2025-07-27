#!/usr/bin/env python3
"""
City Selection Interface for Multi-City Dashboards
Provides navigation interface for switching between different city dashboards
Part of the Oikotie visualization package
"""

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import json

from ..utils.config import get_available_cities, get_city_config, OutputConfig


class CitySelector:
    """City selection interface generator for multi-city dashboard navigation"""
    
    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir) if output_dir else Path("output/visualization/dashboard")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_city_selector_interface(self, available_dashboards: Dict[str, str]) -> str:
        """Create city selection interface HTML"""
        print("🎛️ Creating city selection interface...")
        
        # Generate city cards HTML
        city_cards = ""
        for city, dashboard_path in available_dashboards.items():
            try:
                city_config = get_city_config(city)
                
                # Check if dashboard file exists
                dashboard_exists = dashboard_path and Path(dashboard_path).exists()
                status_class = "available" if dashboard_exists else "unavailable"
                status_text = "Available" if dashboard_exists else "Not Generated"
                
                # Special styling for Espoo (highlight as new feature)
                special_class = ""
                feature_badge = ""
                
                if city.lower() == "espoo":
                    special_class = "espoo-card"
                    feature_badge = '<span class="new-feature-badge">NEW</span>'
                
                # Get dashboard generation time if available
                generation_time = ""
                if dashboard_exists:
                    try:
                        timestamp = Path(dashboard_path).name.split('_')[-1].split('.')[0]
                        if len(timestamp) == 12:  # Format: YYYYMMDD_HHMMSS
                            date = timestamp[:8]
                            time = timestamp[9:]
                            formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
                            formatted_time = f"{time[:2]}:{time[2:4]}:{time[4:6]}"
                            generation_time = f"<p><strong>Generated:</strong> {formatted_date} {formatted_time}</p>"
                    except Exception:
                        pass
                
                city_cards += f"""
                <div class="city-card {status_class} {special_class}">
                    <div class="city-header">
                        <h3>{city_config.name} {feature_badge}</h3>
                        <span class="status-badge {status_class}">{status_text}</span>
                    </div>
                    <div class="city-info">
                        <p><strong>Center:</strong> {city_config.center_lat:.4f}, {city_config.center_lon:.4f}</p>
                        <p><strong>Zoom Level:</strong> {city_config.zoom_level}</p>
                        <p><strong>Bounds:</strong> {city_config.bbox[0]:.2f}, {city_config.bbox[1]:.2f}, {city_config.bbox[2]:.2f}, {city_config.bbox[3]:.2f}</p>
                        {generation_time}
                    </div>
                    <div class="city-actions">
                        {'<button class="btn-primary" onclick="openDashboard(\'' + str(dashboard_path) + '\')"><i class="fas fa-map-marked-alt"></i> Open Dashboard</button>' if dashboard_exists else '<button class="btn-disabled" disabled><i class="fas fa-map-marked-alt"></i> Dashboard Not Available</button>'}
                        <button class="btn-secondary" onclick="generateDashboard('{city}')"><i class="fas fa-sync-alt"></i> Generate New</button>
                        {'<button class="btn-enhanced" onclick="generateEnhancedDashboard(\'' + city + '\')"><i class="fas fa-building"></i> Enhanced View</button>' if city.lower() in ['helsinki', 'espoo'] else ''}
                    </div>
                    {'<div class="city-feature-tag">Multi-City Support</div>' if city.lower() == "espoo" else ''}
                </div>
                """
            except Exception as e:
                print(f"⚠️ Error processing {city}: {e}")
        
        # Create HTML template
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Oikotie Multi-City Dashboard Selector</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                }}
                
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                
                .header {{
                    text-align: center;
                    color: white;
                    margin-bottom: 40px;
                }}
                
                .header h1 {{
                    font-size: 2.5em;
                    margin-bottom: 10px;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                }}
                
                .header p {{
                    font-size: 1.2em;
                    opacity: 0.9;
                }}
                
                .city-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                    margin-bottom: 40px;
                }}
                
                .city-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                }}
                
                .city-card:hover {{
                    transform: translateY(-5px);
                    box-shadow: 0 12px 35px rgba(0,0,0,0.2);
                }}
                
                .city-card.unavailable {{
                    opacity: 0.7;
                    background: #f8f9fa;
                }}
                
                .espoo-card {{
                    border-left: 4px solid #0047AB;
                    background: linear-gradient(135deg, white 0%, #f0f8ff 100%);
                    box-shadow: 0 8px 30px rgba(0, 71, 171, 0.15);
                    position: relative;
                }}
                
                .city-feature-tag {{
                    position: absolute;
                    top: 10px;
                    right: -5px;
                    background: #0047AB;
                    color: white;
                    padding: 3px 10px;
                    font-size: 0.7em;
                    font-weight: bold;
                    border-radius: 3px 0 0 3px;
                    box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
                }}
                
                .city-feature-tag:after {{
                    content: '';
                    position: absolute;
                    right: 0;
                    bottom: -5px;
                    border-left: 5px solid #00255A;
                    border-bottom: 5px solid transparent;
                }}
                
                .city-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #e9ecef;
                }}
                
                .city-header h3 {{
                    margin: 0;
                    color: #333;
                    font-size: 1.4em;
                }}
                
                .status-badge {{
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.8em;
                    font-weight: 600;
                    text-transform: uppercase;
                }}
                
                .status-badge.available {{
                    background-color: #d4edda;
                    color: #155724;
                }}
                
                .status-badge.unavailable {{
                    background-color: #f8d7da;
                    color: #721c24;
                }}
                
                .city-info {{
                    margin-bottom: 20px;
                    color: #666;
                }}
                
                .city-info p {{
                    margin: 5px 0;
                    font-size: 0.9em;
                }}
                
                .city-actions {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                }}
                
                .btn-primary {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: 600;
                    flex: 1;
                    transition: opacity 0.3s ease;
                }}
                
                .btn-primary:hover {{
                    opacity: 0.9;
                }}
                
                .btn-secondary {{
                    background: #6c757d;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: 600;
                    flex: 1;
                    transition: background-color 0.3s ease;
                }}
                
                .btn-secondary:hover {{
                    background: #5a6268;
                }}
                
                .btn-disabled {{
                    background: #e9ecef;
                    color: #6c757d;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    cursor: not-allowed;
                    font-weight: 600;
                    flex: 1;
                }}
                
                .btn-enhanced {{
                    background: linear-gradient(135deg, #0047AB 0%, #4169E1 100%);
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: 600;
                    margin-top: 10px;
                    width: 100%;
                    transition: opacity 0.3s ease;
                }}
                
                .btn-enhanced:hover {{
                    opacity: 0.9;
                }}
                
                .comparative-section {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                    margin-bottom: 20px;
                }}
                
                .comparative-section h2 {{
                    margin-top: 0;
                    color: #333;
                    border-bottom: 2px solid #e9ecef;
                    padding-bottom: 10px;
                }}
                
                .comparative-options {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 20px;
                    margin-bottom: 20px;
                }}
                
                .option-group {{
                    flex: 1;
                    min-width: 250px;
                    background-color: rgba(255, 255, 255, 0.7);
                    border-radius: 8px;
                    padding: 15px;
                }}
                
                .option-group h4 {{
                    margin-top: 0;
                    margin-bottom: 10px;
                    color: #333;
                    border-bottom: 1px solid #ddd;
                    padding-bottom: 5px;
                }}
                
                .comparative-controls {{
                    display: flex;
                    gap: 10px;
                    align-items: center;
                    flex-wrap: wrap;
                }}
                
                .city-checkbox {{
                    display: flex;
                    align-items: center;
                    gap: 5px;
                    margin-right: 15px;
                    padding: 5px 10px;
                    border-radius: 5px;
                    transition: background-color 0.3s ease;
                }}
                
                .city-checkbox:hover {{
                    background-color: rgba(255, 255, 255, 0.8);
                }}
                
                .city-checkbox.highlighted {{
                    background-color: rgba(0, 71, 171, 0.1);
                    border: 1px solid rgba(0, 71, 171, 0.3);
                }}
                
                .city-checkbox input[type="checkbox"],
                .option-checkbox input[type="checkbox"] {{
                    transform: scale(1.2);
                }}
                
                .comparison-options {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                }}
                
                .option-checkbox {{
                    display: flex;
                    align-items: center;
                    gap: 5px;
                    margin-right: 15px;
                    padding: 5px 10px;
                    border-radius: 5px;
                    transition: background-color 0.3s ease;
                }}
                
                .option-checkbox:hover {{
                    background-color: rgba(255, 255, 255, 0.8);
                }}
                
                .action-buttons {{
                    display: flex;
                    gap: 10px;
                    margin-bottom: 20px;
                }}
                
                .comparison-preview {{
                    background-color: rgba(255, 255, 255, 0.7);
                    border-radius: 8px;
                    padding: 15px;
                }}
                
                .comparison-preview h4 {{
                    margin-top: 0;
                    margin-bottom: 10px;
                    color: #333;
                }}
                
                .comparison-preview ul {{
                    margin: 0;
                    padding-left: 20px;
                }}
                
                .comparison-preview li {{
                    margin-bottom: 5px;
                }}
                
                .footer {{
                    text-align: center;
                    color: white;
                    opacity: 0.8;
                    margin-top: 40px;
                }}
                
                .instructions {{
                    background: rgba(255,255,255,0.1);
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 30px;
                    color: white;
                }}
                
                .instructions h3 {{
                    margin-top: 0;
                    color: white;
                }}
                
                .new-feature-badge {{
                    background-color: #0047AB;
                    color: white;
                    padding: 3px 8px;
                    border-radius: 10px;
                    font-size: 0.7em;
                    margin-left: 8px;
                    vertical-align: middle;
                }}
                
                .command-modal {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.5);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    z-index: 9999;
                }}
                
                .modal-content {{
                    background-color: white;
                    border-radius: 8px;
                    width: 80%;
                    max-width: 600px;
                    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
                }}
                
                .modal-header {{
                    padding: 15px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border-radius: 8px 8px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                
                .modal-header h3 {{
                    margin: 0;
                }}
                
                .close-button {{
                    font-size: 24px;
                    cursor: pointer;
                }}
                
                .modal-body {{
                    padding: 20px;
                }}
                
                .command-box {{
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 15px;
                    margin: 10px 0;
                    position: relative;
                }}
                
                .command-box code {{
                    display: block;
                    white-space: pre-wrap;
                    word-break: break-all;
                    font-family: monospace;
                }}
                
                .copy-button {{
                    position: absolute;
                    top: 5px;
                    right: 5px;
                    background-color: #667eea;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                    cursor: pointer;
                }}
                
                .modal-footer {{
                    padding: 15px;
                    text-align: right;
                    border-top: 1px solid #ddd;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1><i class="fas fa-map-marked-alt"></i> Oikotie Multi-City Dashboard</h1>
                    <p>Select a city to explore property listings and building footprints</p>
                </div>
                
                <div class="instructions">
                    <h3><i class="fas fa-info-circle"></i> How to Use</h3>
                    <ul>
                        <li><strong>Open Dashboard:</strong> Click to view existing city dashboard</li>
                        <li><strong>Generate New:</strong> Create a fresh dashboard with latest data</li>
                        <li><strong>Enhanced View:</strong> <span class="new-feature-badge">NEW</span> Open city-specific enhanced dashboard with building footprints</li>
                        <li><strong>Comparative View:</strong> Select multiple cities below for side-by-side comparison</li>
                    </ul>
                </div>
                
                <div class="city-grid">
                    {city_cards}
                </div>
                
                <div class="comparative-section">
                    <h2><i class="fas fa-chart-bar"></i> Comparative Dashboard <span class="new-feature-badge">ENHANCED</span></h2>
                    <p>Select multiple cities to generate a comparative dashboard with side-by-side analysis:</p>
                    
                    <div class="comparative-options">
                        <div class="option-group">
                            <h4>Select Cities to Compare</h4>
                            <div class="comparative-controls">
                                <div class="city-checkbox">
                                    <input type="checkbox" id="helsinki" value="helsinki" checked>
                                    <label for="helsinki">Helsinki</label>
                                </div>
                                <div class="city-checkbox highlighted">
                                    <input type="checkbox" id="espoo" value="espoo" checked>
                                    <label for="espoo">Espoo <span class="new-feature-badge">NEW</span></label>
                                </div>
                                <div class="city-checkbox">
                                    <input type="checkbox" id="tampere" value="tampere">
                                    <label for="tampere">Tampere</label>
                                </div>
                                <div class="city-checkbox">
                                    <input type="checkbox" id="turku" value="turku">
                                    <label for="turku">Turku</label>
                                </div>
                            </div>
                        </div>
                        
                        <div class="option-group">
                            <h4>Comparison Options</h4>
                            <div class="comparison-options">
                                <div class="option-checkbox">
                                    <input type="checkbox" id="price_comparison" value="price_comparison" checked>
                                    <label for="price_comparison">Price Comparison</label>
                                </div>
                                <div class="option-checkbox">
                                    <input type="checkbox" id="size_comparison" value="size_comparison" checked>
                                    <label for="size_comparison">Size Comparison</label>
                                </div>
                                <div class="option-checkbox">
                                    <input type="checkbox" id="price_per_sqm" value="price_per_sqm" checked>
                                    <label for="price_per_sqm">Price per m²</label>
                                </div>
                                <div class="option-checkbox">
                                    <input type="checkbox" id="building_footprints" value="building_footprints" checked>
                                    <label for="building_footprints">Building Footprints</label>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="action-buttons">
                        <button class="btn-primary" onclick="generateComparativeDashboard()">
                            <i class="fas fa-chart-line"></i> Generate Comparative Dashboard
                        </button>
                        
                        <button class="btn-secondary" onclick="generateQuickComparison()">
                            <i class="fas fa-bolt"></i> Quick Helsinki-Espoo Comparison
                        </button>
                    </div>
                    
                    <div class="comparison-preview">
                        <h4><i class="fas fa-info-circle"></i> Comparative Dashboard Features</h4>
                        <ul>
                            <li><strong>Side-by-side maps</strong> for visual comparison</li>
                            <li><strong>Price distribution charts</strong> across selected cities</li>
                            <li><strong>Statistical comparison</strong> of key metrics</li>
                            <li><strong>Building footprint visualization</strong> for spatial analysis</li>
                            <li><strong>Downloadable data</strong> for further analysis</li>
                        </ul>
                    </div>
                </div>
                
                <div class="footer">
                    <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Oikotie Real Estate Analytics Platform</p>
                </div>
            </div>
            
            <script>
                function openDashboard(dashboardPath) {{
                    if (dashboardPath && dashboardPath !== 'None') {{
                        window.open(dashboardPath, '_blank');
                    }} else {{
                        alert('Dashboard not available. Please generate a new dashboard first.');
                    }}
                }}
                
                function generateDashboard(city) {{
                    const command = 'uv run python -m oikotie.visualization.cli.commands dashboard --city ' + city + ' --multi-city --open';
                    
                    // Create a styled modal for the command
                    showCommandModal('Generate ' + city + ' Dashboard', command);
                }}
                
                function generateEnhancedDashboard(city) {{
                    let command = '';
                    
                    if (city.toLowerCase() === 'espoo') {{
                        command = 'uv run python -m oikotie.visualization.cli.commands dashboard --city espoo --enhanced --open';
                    }} else {{
                        command = 'uv run python -m oikotie.visualization.cli.commands dashboard --city ' + city + ' --enhanced --open';
                    }}
                    
                    // Create a styled modal for the command
                    showCommandModal('Generate Enhanced ' + city + ' Dashboard', command);
                }}
                
                function generateComparativeDashboard() {{
                    const cityCheckboxes = document.querySelectorAll('.city-checkbox input[type="checkbox"]:checked');
                    const selectedCities = Array.from(cityCheckboxes).map(cb => cb.value);
                    
                    if (selectedCities.length < 2) {{
                        alert('Please select at least 2 cities for comparison.');
                        return;
                    }}
                    
                    // Get selected options
                    const optionCheckboxes = document.querySelectorAll('.option-checkbox input[type="checkbox"]:checked');
                    const selectedOptions = Array.from(optionCheckboxes).map(cb => cb.value);
                    
                    const citiesStr = selectedCities.join(',');
                    const optionsStr = selectedOptions.length > 0 ? ' --options "' + selectedOptions.join(',') + '"' : '';
                    
                    const command = 'uv run python -m oikotie.visualization.cli.commands dashboard --comparative "' + citiesStr + '"' + optionsStr + ' --open';
                    
                    // Create a styled modal for the command
                    showCommandModal('Generate Comparative Dashboard', command);
                }}
                
                function generateQuickComparison() {{
                    const command = 'uv run python -m oikotie.visualization.cli.commands dashboard --comparative "helsinki,espoo" --options "price_comparison,building_footprints" --open';
                    
                    // Create a styled modal for the command
                    showCommandModal('Quick Helsinki-Espoo Comparison', command);
                }}
                
                function showCommandModal(title, command) {{
                    // Create modal container
                    const modal = document.createElement('div');
                    modal.className = 'command-modal';
                    
                    // Create modal content with proper escaping
                    const escapedCommand = command.replace(/'/g, "\\'");
                    
                    // Create HTML content without template literals
                    modal.innerHTML = 
                        '<div class="modal-content">' +
                            '<div class="modal-header">' +
                                '<h3>' + title + '</h3>' +
                                '<span class="close-button" onclick="closeModal()">&times;</span>' +
                            '</div>' +
                            '<div class="modal-body">' +
                                '<p>Run the following command in your terminal:</p>' +
                                '<div class="command-box">' +
                                    '<code>' + command + '</code>' +
                                    '<button class="copy-button" onclick="copyCommand(\'' + escapedCommand + '\')">' +
                                        '<i class="fas fa-copy"></i> Copy' +
                                    '</button>' +
                                '</div>' +
                            '</div>' +
                            '<div class="modal-footer">' +
                                '<button class="btn-secondary" onclick="closeModal()">Close</button>' +
                            '</div>' +
                        '</div>';
                    
                    // Add modal to body
                    document.body.appendChild(modal);
                    
                    // Add close modal function to window
                    window.closeModal = function() {{
                        document.body.removeChild(modal);
                    }};
                    
                    // Add copy command function to window
                    window.copyCommand = function(cmd) {{
                        navigator.clipboard.writeText(cmd).then(() => {{
                            const copyButton = document.querySelector('.copy-button');
                            copyButton.innerHTML = '<i class="fas fa-check"></i> Copied!';
                            setTimeout(() => {{
                                copyButton.innerHTML = '<i class="fas fa-copy"></i> Copy';
                            }}, 2000);
                        }});
                    }};
                }}
            </script>
        </body>
        </html>
        """
        
        # Save selector interface
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        selector_path = self.output_dir / f"city_selector_{timestamp}.html"
        
        with open(selector_path, 'w', encoding='utf-8') as f:
            f.write(html_template)
        
        print(f"✅ City selector interface created: {selector_path}")
        return str(selector_path)
    
    def scan_existing_dashboards(self) -> Dict[str, str]:
        """Scan output directory for existing dashboards"""
        print("🔍 Scanning for existing dashboards...")
        
        available_dashboards = {}
        available_cities = get_available_cities()
        
        for city in available_cities:
            # Look for city-specific dashboards
            city_pattern = f"{city.lower()}_enhanced_dashboard_*.html"
            city_dashboards = list(self.output_dir.glob(city_pattern))
            
            if city_dashboards:
                # Get the most recent dashboard
                latest_dashboard = max(city_dashboards, key=lambda p: p.stat().st_mtime)
                available_dashboards[city] = str(latest_dashboard)
                print(f"  ✅ Found {city} dashboard: {latest_dashboard.name}")
            else:
                available_dashboards[city] = None
                print(f"  ❌ No {city} dashboard found")
        
        return available_dashboards
    
    def create_dashboard_index(self) -> str:
        """Create main dashboard index with city selector"""
        print("📋 Creating dashboard index...")
        
        # Scan for existing dashboards
        available_dashboards = self.scan_existing_dashboards()
        
        # Create city selector interface
        selector_path = self.create_city_selector_interface(available_dashboards)
        
        return selector_path


def main():
    """Demo usage of CitySelector"""
    print("🎛️ City Selector Interface Demo")
    print("=" * 50)
    
    selector = CitySelector()
    
    # Create dashboard index
    index_path = selector.create_dashboard_index()
    print(f"✅ Dashboard index created: {index_path}")
    
    # Open in browser
    import webbrowser
    webbrowser.open(f"file://{Path(index_path).absolute()}")


if __name__ == "__main__":
    main()