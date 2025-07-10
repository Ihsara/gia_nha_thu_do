#!/usr/bin/env python3
"""
Property Polygon Visualization with Enhanced Monitoring and Logging

This script includes:
1. Comprehensive file-based logging for monitoring long-running processes
2. Progress tracking with timestamps and ETA calculations
3. Tmux session management for process monitoring
4. Checkpoint saving for resumable processing
5. Real-time progress monitoring via log files
"""

import duckdb
import json
import folium
from shapely.geometry import Point, Polygon, LineString, MultiLineString
from shapely.ops import unary_union, linemerge
import shapely.wkt
from pyproj import Transformer
import logging
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import time
import os
from datetime import datetime
import subprocess

# Configure enhanced logging
def setup_logging():
    """Setup comprehensive logging to both file and console."""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create timestamped log file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'logs/property_polygon_processing_{timestamp}.log'
    
    # Configure logging with detailed format
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"=== PROPERTY POLYGON PROCESSING SESSION STARTED ===")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Process PID: {os.getpid()}")
    logger.info(f"Working directory: {os.getcwd()}")
    
    return logger, log_file

class PropertyPolygonMatcherWithMonitoring:
    def __init__(self, db_path: str = "data/real_estate.duckdb"):
        """Initialize with comprehensive monitoring capabilities."""
        self.db_path = db_path
        self.logger, self.log_file = setup_logging()
        
        # Create transformer for coordinate systems
        self.transformer = Transformer.from_crs('EPSG:3067', 'EPSG:4326', always_xy=True)
        
        # Enhanced statistics tracking
        self.stats = {
            'session_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'total_listings': 0,
            'total_boundaries': 0,
            'valid_polygons_created': 0,
            'listings_matched': 0,
            'processing_time': 0,
            'start_time': time.time(),
            'boundary_processing_time': 0,
            'spatial_join_time': 0,
            'visualization_time': 0,
            'memory_usage_mb': 0,
            'peak_memory_mb': 0
        }
        
        # Progress tracking files
        self.progress_file = f'logs/progress_{self.stats["session_id"]}.json'
        self.checkpoint_file = f'logs/checkpoint_{self.stats["session_id"]}.json'
        
        # Create monitoring info file
        self.create_monitoring_info()
        
    def create_monitoring_info(self):
        """Create monitoring information file for external tracking."""
        monitoring_info = {
            'session_id': self.stats['session_id'],
            'pid': os.getpid(),
            'log_file': self.log_file,
            'progress_file': self.progress_file,
            'checkpoint_file': self.checkpoint_file,
            'start_time': datetime.now().isoformat(),
            'monitoring_commands': {
                'tail_log': f'tail -f {self.log_file}',
                'check_progress': f'cat {self.progress_file}',
                'monitor_memory': f'ps -p {os.getpid()} -o pid,ppid,cmd,%mem,%cpu,time',
                'kill_process': f'kill {os.getpid()}'
            }
        }
        
        with open('logs/current_session.json', 'w') as f:
            json.dump(monitoring_info, f, indent=2)
        
        self.logger.info(f"Monitoring info saved to logs/current_session.json")

    def get_memory_usage(self):
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.stats['memory_usage_mb'] = memory_mb
            self.stats['peak_memory_mb'] = max(self.stats['peak_memory_mb'], memory_mb)
            return memory_mb
        except ImportError:
            return 0

    def save_progress(self, stage: str, current: int, total: int, additional_info: dict = None):
        """Save detailed progress information for external monitoring."""
        elapsed_time = time.time() - self.stats['start_time']
        processing_rate = current / elapsed_time if elapsed_time > 0 else 0
        eta_seconds = (total - current) / processing_rate if processing_rate > 0 else 0
        
        progress = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.stats['session_id'],
            'stage': stage,
            'current': current,
            'total': total,
            'percentage': (current / total * 100) if total > 0 else 0,
            'elapsed_time_seconds': elapsed_time,
            'processing_rate_per_second': processing_rate,
            'eta_seconds': eta_seconds,
            'eta_human': f"{eta_seconds/3600:.1f}h {(eta_seconds%3600)/60:.1f}m" if eta_seconds > 0 else "N/A",
            'memory_usage_mb': self.get_memory_usage(),
            'stats': self.stats.copy(),
            'additional_info': additional_info or {}
        }
        
        # Save progress to file
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
        
        # Update current session info
        with open('logs/current_session.json', 'r') as f:
            session_info = json.load(f)
        session_info['last_progress'] = progress
        with open('logs/current_session.json', 'w') as f:
            json.dump(session_info, f, indent=2)

    def save_checkpoint(self, stage: str, data: dict):
        """Save checkpoint data for resumable processing."""
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'stage': stage,
            'stats': self.stats.copy(),
            'data': data
        }
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        
        self.logger.info(f"Checkpoint saved: {stage}")

    def load_listings_data(self) -> List[Dict]:
        """Load all listings with detailed progress monitoring."""
        self.logger.info("=== STAGE 1: Loading listings data ===")
        stage_start = time.time()
        
        conn = duckdb.connect(self.db_path)
        try:
            # Check total count first
            count_result = conn.execute("""
                SELECT COUNT(*) FROM listings l
                JOIN address_locations al ON l.address = al.address
                WHERE al.lat IS NOT NULL AND al.lon IS NOT NULL
            """).fetchone()
            total_count = count_result[0]
            
            self.logger.info(f"Found {total_count} listings with coordinates to load")
            
            result = conn.execute("""
                SELECT l.url, l.title, l.price_eur, l.size_m2, l.rooms, 
                       l.address, al.lat, al.lon
                FROM listings l
                JOIN address_locations al ON l.address = al.address
                WHERE al.lat IS NOT NULL 
                AND al.lon IS NOT NULL
            """).fetchall()
            
            listings = []
            for i, row in enumerate(result):
                if i % 1000 == 0:
                    self.save_progress("loading_listings", i, len(result))
                    if i > 0:
                        self.logger.info(f"Loaded {i}/{len(result)} listings ({i/len(result)*100:.1f}%)")
                
                try:
                    listing = {
                        'id': row[0],
                        'title': row[1],
                        'price': row[2],
                        'size': row[3],
                        'rooms': row[4],
                        'location': row[5],
                        'latitude': float(row[6]),
                        'longitude': float(row[7]),
                        'url': row[0]
                    }
                    listings.append(listing)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid coordinates for listing {row[0]}: {e}")
                    continue
            
            self.stats['total_listings'] = len(listings)
            loading_time = time.time() - stage_start
            
            self.logger.info(f"✅ Loaded {len(listings)} listings in {loading_time:.2f}s")
            
            # Save checkpoint
            self.save_checkpoint("listings_loaded", {
                'listings_count': len(listings),
                'loading_time': loading_time
            })
            
            self.save_progress("loading_listings", len(listings), len(listings), {
                'loading_time_seconds': loading_time,
                'success_rate': len(listings) / len(result) * 100
            })
            
            return listings
        finally:
            conn.close()

    def load_boundary_data(self) -> List[Dict]:
        """Load boundary data with comprehensive monitoring."""
        self.logger.info("=== STAGE 2: Loading boundary data ===")
        stage_start = time.time()
        
        conn = duckdb.connect(self.db_path)
        try:
            # Check boundary types and counts
            boundary_types = conn.execute("""
                SELECT kiinteistorajalaji, COUNT(*) as count
                FROM helsinki_02_kiinteistorajansijaintitiedot 
                WHERE geometry_wkt IS NOT NULL
                GROUP BY kiinteistorajalaji
                ORDER BY count DESC
            """).fetchall()
            
            self.logger.info(f"Available boundary types: {boundary_types}")
            
            # Load property boundaries (type 696)
            total_count = next(count for btype, count in boundary_types if btype == 696)
            self.logger.info(f"Loading {total_count} property boundaries (type 696)")
            
            result = conn.execute("""
                SELECT kiinteistorajalaji, geometry_wkt, lahdeaineisto, interpolointitapa
                FROM helsinki_02_kiinteistorajansijaintitiedot
                WHERE geometry_wkt IS NOT NULL 
                AND kiinteistorajalaji = 696
            """).fetchall()
            
            boundaries = []
            for i, row in enumerate(result):
                if i % 5000 == 0:
                    self.save_progress("loading_boundaries", i, len(result))
                    if i > 0:
                        self.logger.info(f"Loaded {i}/{len(result)} boundaries ({i/len(result)*100:.1f}%) - Memory: {self.get_memory_usage():.1f}MB")
                
                try:
                    boundary = {
                        'type': row[0],
                        'geometry_wkt': row[1],
                        'id': f"boundary_{len(boundaries)}_{row[2]}_{row[3]}"
                    }
                    boundaries.append(boundary)
                except Exception as e:
                    self.logger.debug(f"Error processing boundary {i}: {e}")
                    continue
            
            self.stats['total_boundaries'] = len(boundaries)
            loading_time = time.time() - stage_start
            
            self.logger.info(f"✅ Loaded {len(boundaries)} boundaries in {loading_time:.2f}s")
            
            # Save checkpoint
            self.save_checkpoint("boundaries_loaded", {
                'boundaries_count': len(boundaries),
                'boundary_types': boundary_types,
                'loading_time': loading_time
            })
            
            self.save_progress("loading_boundaries", len(boundaries), len(boundaries), {
                'loading_time_seconds': loading_time,
                'boundary_types': boundary_types,
                'memory_usage_mb': self.get_memory_usage()
            })
            
            return boundaries
        finally:
            conn.close()

    def convert_coordinates(self, geometry) -> Optional[object]:
        """Convert geometry with error handling."""
        try:
            if hasattr(geometry, 'coords'):
                # Handle LineString
                transformed_coords = []
                for x, y in geometry.coords:
                    lon, lat = self.transformer.transform(x, y)
                    transformed_coords.append((lon, lat))
                return LineString(transformed_coords)
            elif hasattr(geometry, 'exterior'):
                # Handle Polygon
                exterior_coords = []
                for x, y in geometry.exterior.coords:
                    lon, lat = self.transformer.transform(x, y)
                    exterior_coords.append((lon, lat))
                
                holes = []
                for interior in geometry.interiors:
                    hole_coords = []
                    for x, y in interior.coords:
                        lon, lat = self.transformer.transform(x, y)
                        hole_coords.append((lon, lat))
                    holes.append(hole_coords)
                
                return Polygon(exterior_coords, holes)
            else:
                return None
        except Exception as e:
            self.logger.debug(f"Coordinate transformation failed: {e}")
            return None

    def create_polygons_from_linestrings(self, boundaries: List[Dict]) -> List[Dict]:
        """Create polygons with comprehensive progress tracking."""
        self.logger.info("=== STAGE 3: Converting boundaries to polygons ===")
        stage_start = time.time()
        
        polygons = []
        successful_conversions = 0
        failed_conversions = 0
        
        for i, boundary in enumerate(boundaries):
            if i % 1000 == 0:
                elapsed = time.time() - stage_start
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(boundaries) - i) / rate if rate > 0 else 0
                
                self.logger.info(f"Processing {i+1}/{len(boundaries)} boundaries - "
                               f"Success: {successful_conversions} - Rate: {rate:.1f}/s - "
                               f"ETA: {eta/60:.1f}min - Memory: {self.get_memory_usage():.1f}MB")
                
                self.save_progress("creating_polygons", i, len(boundaries), {
                    'successful_conversions': successful_conversions,
                    'failed_conversions': failed_conversions,
                    'success_rate': (successful_conversions / (i + 1)) * 100 if i > 0 else 0,
                    'processing_rate_per_second': rate,
                    'eta_minutes': eta/60,
                    'memory_usage_mb': self.get_memory_usage()
                })
            
            try:
                geom = shapely.wkt.loads(boundary['geometry_wkt'])
                transformed_geom = self.convert_coordinates(geom)
                
                if not transformed_geom:
                    failed_conversions += 1
                    continue
                
                polygon = None
                
                if isinstance(transformed_geom, LineString):
                    if transformed_geom.is_ring:
                        try:
                            polygon = Polygon(transformed_geom.coords)
                        except:
                            pass
                    
                    if not polygon:
                        try:
                            buffer_size = 0.00005  # ~5 meters
                            polygon = transformed_geom.buffer(buffer_size)
                        except:
                            pass
                
                elif isinstance(transformed_geom, Polygon):
                    polygon = transformed_geom
                
                if polygon and polygon.is_valid and not polygon.is_empty:
                    polygons.append({
                        'id': boundary['id'],
                        'polygon': polygon,
                        'original_type': boundary['type']
                    })
                    successful_conversions += 1
                else:
                    failed_conversions += 1
                
            except Exception as e:
                failed_conversions += 1
                self.logger.debug(f"Error processing boundary {boundary.get('id', 'unknown')}: {e}")
                continue
        
        self.stats['valid_polygons_created'] = len(polygons)
        self.stats['boundary_processing_time'] = time.time() - stage_start
        
        success_rate = (successful_conversions / len(boundaries)) * 100
        self.logger.info(f"✅ Created {len(polygons)} polygons from {len(boundaries)} boundaries "
                        f"({success_rate:.1f}% success) in {self.stats['boundary_processing_time']:.2f}s")
        
        # Save checkpoint
        self.save_checkpoint("polygons_created", {
            'polygons_count': len(polygons),
            'success_rate': success_rate,
            'processing_time': self.stats['boundary_processing_time']
        })
        
        self.save_progress("creating_polygons", len(boundaries), len(boundaries), {
            'successful_conversions': successful_conversions,
            'failed_conversions': failed_conversions,
            'success_rate': success_rate,
            'processing_time_seconds': self.stats['boundary_processing_time'],
            'memory_usage_mb': self.get_memory_usage()
        })
        
        return polygons

    def spatial_join_with_fallback(self, listings: List[Dict], polygons: List[Dict]) -> Dict[str, List[Dict]]:
        """Perform spatial join with detailed monitoring."""
        self.logger.info("=== STAGE 4: Performing spatial join ===")
        stage_start = time.time()
        
        matched_groups = defaultdict(list)
        unmatched_listings = []
        direct_matches = 0
        buffer_matches = 0
        
        self.logger.info(f"Processing {len(listings)} listings against {len(polygons)} polygons")
        
        for i, listing in enumerate(listings):
            if i % 100 == 0:
                elapsed = time.time() - stage_start
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(listings) - i) / rate if rate > 0 else 0
                matched_so_far = sum(len(group) for group in matched_groups.values())
                current_match_rate = (matched_so_far / (i + 1)) * 100 if i > 0 else 0
                
                self.logger.info(f"Processing {i+1}/{len(listings)} listings - "
                               f"Matched: {matched_so_far} ({current_match_rate:.1f}%) - "
                               f"Direct: {direct_matches}, Buffer: {buffer_matches} - "
                               f"Rate: {rate:.1f}/s - ETA: {eta/60:.1f}min")
                
                self.save_progress("spatial_join", i, len(listings), {
                    'matched_so_far': matched_so_far,
                    'match_rate_percentage': current_match_rate,
                    'direct_matches': direct_matches,
                    'buffer_matches': buffer_matches,
                    'unmatched_so_far': len(unmatched_listings),
                    'processing_rate_per_second': rate,
                    'eta_minutes': eta/60,
                    'memory_usage_mb': self.get_memory_usage()
                })
            
            try:
                point = Point(listing['longitude'], listing['latitude'])
                matched = False
                
                # Strategy 1: Direct point-in-polygon test
                for polygon_data in polygons:
                    try:
                        if polygon_data['polygon'].contains(point):
                            matched_groups[polygon_data['id']].append(listing)
                            matched = True
                            direct_matches += 1
                            break
                    except:
                        continue
                
                # Strategy 2: Buffer-based matching
                if not matched:
                    min_distance = float('inf')
                    closest_polygon = None
                    
                    for polygon_data in polygons:
                        try:
                            distance = polygon_data['polygon'].distance(point)
                            if distance < min_distance:
                                min_distance = distance
                                closest_polygon = polygon_data
                        except:
                            continue
                    
                    if closest_polygon and min_distance < 0.0005:  # ~50 meters
                        matched_groups[closest_polygon['id']].append(listing)
                        matched = True
                        buffer_matches += 1
                
                if not matched:
                    unmatched_listings.append(listing)
                    
            except Exception as e:
                self.logger.warning(f"Error processing listing {listing['id']}: {e}")
                unmatched_listings.append(listing)
        
        if unmatched_listings:
            matched_groups['UNMATCHED'] = unmatched_listings
        
        self.stats['listings_matched'] = self.stats['total_listings'] - len(unmatched_listings)
        self.stats['spatial_join_time'] = time.time() - stage_start
        
        final_match_rate = (self.stats['listings_matched'] / self.stats['total_listings']) * 100
        
        self.logger.info(f"✅ Spatial join complete!")
        self.logger.info(f"   Match rate: {final_match_rate:.2f}% ({self.stats['listings_matched']}/{self.stats['total_listings']})")
        self.logger.info(f"   Direct matches: {direct_matches}")
        self.logger.info(f"   Buffer matches: {buffer_matches}")
        self.logger.info(f"   Unmatched: {len(unmatched_listings)}")
        self.logger.info(f"   Processing time: {self.stats['spatial_join_time']:.2f}s")
        
        # Save checkpoint
        self.save_checkpoint("spatial_join_complete", {
            'match_rate': final_match_rate,
            'total_matched': self.stats['listings_matched'],
            'direct_matches': direct_matches,
            'buffer_matches': buffer_matches,
            'unmatched_count': len(unmatched_listings),
            'polygon_groups': len([k for k in matched_groups.keys() if k != 'UNMATCHED']),
            'processing_time': self.stats['spatial_join_time']
        })
        
        self.save_progress("spatial_join", len(listings), len(listings), {
            'final_match_rate': final_match_rate,
            'total_matched': self.stats['listings_matched'],
            'direct_matches': direct_matches,
            'buffer_matches': buffer_matches,
            'unmatched_count': len(unmatched_listings),
            'polygon_groups_created': len([k for k in matched_groups.keys() if k != 'UNMATCHED']),
            'processing_time_seconds': self.stats['spatial_join_time'],
            'memory_usage_mb': self.get_memory_usage()
        })
        
        return dict(matched_groups)

    def create_visualization(self, matched_groups: Dict[str, List[Dict]]) -> str:
        """Create comprehensive visualization with validation."""
        self.logger.info("=== STAGE 5: Creating visualization ===")
        stage_start = time.time()
        
        # Calculate center
        all_lats = []
        all_lons = []
        for group_listings in matched_groups.values():
            for listing in group_listings:
                all_lats.append(listing['latitude'])
                all_lons.append(listing['longitude'])
        
        center_lat = sum(all_lats) / len(all_lats) if all_lats else 60.1699
        center_lon = sum(all_lons) / len(all_lons) if all_lons else 24.9384
        
        self.logger.info(f"Map center: {center_lat:.6f}, {center_lon:.6f}")
        
        # Create map
        m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='OpenStreetMap')
        
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 
                 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'white', 'pink', 
                 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray']
        
        # Validation metrics
        polygon_groups = 0
        max_group_size = 0
        total_with_polygons = 0
        group_size_distribution = defaultdict(int)
        
        self.logger.info(f"Creating markers for {len(matched_groups)} groups")
        
        for i, (group_id, group_listings) in enumerate(matched_groups.items()):
            if not group_listings:
                continue
            
            group_size = len(group_listings)
            group_size_distribution[f"{group_size//10*10}-{group_size//10*10+9}"] += 1
            
            group_lats = [listing['latitude'] for listing in group_listings]
            group_lons = [listing['longitude'] for listing in group_listings]
            group_center_lat = sum(group_lats) / len(group_lats)
            group_center_lon = sum(group_lons) / len(group_lons)
            
            if group_id == 'UNMATCHED':
                color = 'gray'
                has_polygon = False
                radius = min(25, 5 + len(group_listings) * 0.01)  # Scale down for large unmatched groups
            else:
                color = colors[i % len(colors)]
                has_polygon = True
                polygon_groups += 1
                total_with_polygons += len(group_listings)
                radius = max(5, min(30, 5 + len(group_listings) * 2))
            
            max_group_size = max(max_group_size, len(group_listings))
            
            # Create detailed popup
            popup_html = f"""
            <div style="font-family: Arial; width: 350px;">
                <h4>Property Group: {group_id[:50]}</h4>
                <p><strong>Listings:</strong> {len(group_listings)}</p>
                <p><strong>Has Polygon:</strong> {'Yes' if has_polygon else 'No'}</p>
                <p><strong>Center:</strong> {group_center_lat:.6f}, {group_center_lon:.6f}</p>
                <hr>
                <h5>Sample Listings (showing up to 5):</h5>
                <ul style="max-height: 200px; overflow-y: auto;">
            """
            
            sample_listings = group_listings[:5]
            for listing in sample_listings:
                price_str = f"€{listing['price']:,}" if listing['price'] else "Price not available"
                size_str = f"{listing['size']}m²" if listing['size'] else "Size not available"
                rooms_str = f"{listing['rooms']} rooms" if listing['rooms'] else "Rooms not specified"
                
                popup_html += f"""
                <li style="margin-bottom: 8px;">
                    <strong>{listing['title'][:40]}...</strong><br>
                    <span style="color: green;">{price_str}</span> | {size_str} | {rooms_str}<br>
                    <small style="color: #666;">{listing['location']}</small>
                </li>
                """
            
            if len(group_listings) > 5:
                popup_html += f"<li><em>... and {len(group_listings) - 5} more listings</em></li>"
            
            popup_html += "</ul></div>"
            
            # Add marker
            folium.CircleMarker(
                location=[group_center_lat, group_center_lon],
                radius=radius,
                popup=folium.Popup(popup_html, max_width=450),
                color='black',
                weight=2,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                tooltip=f"{group_id}: {len(group_listings)} listings"
            ).add_to(m)
        
        # Add comprehensive validation summary
        total_processing_time = time.time() - self.stats['start_time']
        
        validation_html = f"""
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 350px; height: auto; 
                    background-color: white; border: 2px solid navy;
                    z-index:9999; font-size:11px; padding: 10px;
                    border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2);
                    max-height: 90vh; overflow-y: auto;">
            <h4 style="margin-top: 0;">🎯 Validation Results</h4>
            <div style="border-bottom: 1px solid #ccc; padding-bottom: 8px; margin-bottom: 8px;">
                <strong>📊 Match Statistics</strong><br>
                Total Listings: {self.stats['total_listings']}<br>
                With Polygons: {total_with_polygons} ({(total_with_polygons/self.stats['total_listings']*100):.1f}%)<br>
                Polygon Groups: {polygon_groups}<br>
                Largest Group: {max_group_size} listings<br>
                Unmatched: {len(matched_groups.get('UNMATCHED', []))}
            </div>
            <div style="border-bottom: 1px solid #ccc; padding-bottom: 8px; margin-bottom: 8px;">
                <strong>⏱️ Performance</strong><br>
                Total Time: {total_processing_time/60:.1f} minutes<br>
                Boundary Processing: {self.stats['boundary_processing_time']:.1f}s<br>
                Spatial Join: {self.stats['spatial_join_time']:.1f}s<br>
                Peak Memory: {self.stats['peak_memory_mb']:.1f} MB
            </div>
            <div style="border-bottom: 1px solid #ccc; padding-bottom: 8px; margin-bottom: 8px;">
                <strong>🗂️ Data Processing</strong><br>
                Total Boundaries: {self.stats['total_boundaries']:,}<br>
                Polygons Created: {self.stats['valid_polygons_created']:,}<br>
                Conversion Rate: {(self.stats['valid_polygons_created']/self.stats['total_boundaries']*100):.1f}%<br>
                Session ID: {self.stats['session_id']}
            </div>
            <div>
                <strong>✅ SUCCESS CRITERIA</strong><br>
                Match Rate: {'✅ PASSED' if (total_with_polygons/self.stats['total_listings']*100) >= 80 else '❌ FAILED'}<br>
                No Giant Markers: {'✅ PASSED' if max_group_size < 100 else '❌ FAILED'}<br>
                Geographic Distribution: {'✅ PASSED' if polygon_groups > 10 else '❌ FAILED'}
            </div>
        </div>
        """
        
        m.get_root().html.add_child(folium.Element(validation_html))
        
        # Save map
        output_file = f"property_polygon_visualization_monitored_{self.stats['session_id']}.html"
        m.save(output_file)
        
        self.stats['visualization_time'] = time.time() - stage_start
        
        # Log final validation results
        self.logger.info("=== FINAL VALIDATION RESULTS ===")
        self.logger.info(f"Total Listings: {self.stats['total_listings']}")
        self.logger.info(f"Listings with Polygons: {total_with_polygons} ({(total_with_polygons/self.stats['total_listings']*100):.1f}%)")
        self.logger.info(f"Polygon Groups Created: {polygon_groups}")
        self.logger.info(f"Largest Group Size: {max_group_size}")
        self.logger.info(f"Unmatched Listings: {len(matched_groups.get('UNMATCHED', []))}")
        self.logger.info(f"Visualization saved to: {output_file}")
        
        # Save final checkpoint
        self.save_checkpoint("visualization_complete", {
            'output_file': output_file,
            'total_with_polygons': total_with_polygons,
            'polygon_groups': polygon_groups,
            'max_group_size': max_group_size,
            'group_size_distribution': dict(group_size_distribution),
            'validation_results': {
                'match_rate_passed': (total_with_polygons/self.stats['total_listings']*100) >= 80,
                'no_giant_markers': max_group_size < 100,
                'geographic_distribution': polygon_groups > 10
            }
        })
        
        return output_file

    def run_full_pipeline(self) -> str:
        """Run the complete monitored pipeline."""
        try:
            self.logger.info("🚀 Starting full polygon matching pipeline...")
            
            # Stage 1: Load listings
            listings = self.load_listings_data()
            if not listings:
                raise ValueError("No listings found with valid coordinates")
            
            # Stage 2: Load boundaries
            boundaries = self.load_boundary_data()
            if not boundaries:
                raise ValueError("No boundary data found")
            
            # Stage 3: Create polygons
            polygons = self.create_polygons_from_linestrings(boundaries)
            if not polygons:
                self.logger.warning("No polygons created - using fallback strategy")
            
            # Stage 4: Spatial join
            matched_groups = self.spatial_join_with_fallback(listings, polygons)
            
            # Stage 5: Create visualization
            output_file = self.create_visualization(matched_groups)
            
            self.stats['processing_time'] = time.time() - self.stats['start_time']
            
            self.logger.info("🎉 === PIPELINE COMPLETE ===")
            self.logger.info(f"Total processing time: {self.stats['processing_time']/60:.1f} minutes")
            self.logger.info(f"Output saved to: {output_file}")
            
            return output_file
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            self.save_checkpoint("pipeline_failed", {'error': str(e)})
            raise


def create_monitoring_scripts():
    """Create helper scripts for monitoring the process."""
    
    # Create tmux session script
    tmux_script = """#!/bin/bash
# Start polygon processing in tmux session
SESSION_NAME="polygon_processing"

# Check if session already exists
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo "Session $SESSION_NAME already exists. Attaching..."
    tmux attach-session -t $SESSION_NAME
    exit 0
fi

# Create new session
tmux new-session -d -s $SESSION_NAME

# Set up the session
tmux send-keys -t $SESSION_NAME "cd $(pwd)" C-m
tmux send-keys -t $SESSION_NAME "echo 'Starting property polygon processing...'" C-m
tmux send-keys -t $SESSION_NAME "uv run python create_property_polygon_visualization_with_monitoring.py" C-m

# Split window for monitoring
tmux split-window -h -t $SESSION_NAME
tmux send-keys -t $SESSION_NAME:0.1 "cd $(pwd)" C-m
tmux send-keys -t $SESSION_NAME:0.1 "echo 'Monitoring session ready. Use commands:'" C-m
tmux send-keys -t $SESSION_NAME:0.1 "echo '  tail -f logs/property_polygon_processing_*.log'" C-m
tmux send-keys -t $SESSION_NAME:0.1 "echo '  cat logs/current_session.json'" C-m
tmux send-keys -t $SESSION_NAME:0.1 "echo '  cat logs/progress_*.json'" C-m

# Attach to session
tmux attach-session -t $SESSION_NAME
"""
    
    with open('start_monitoring_session.sh', 'w') as f:
        f.write(tmux_script)
    
    # Create monitoring script
    monitor_script = """#!/usr/bin/env python3
\"\"\"
Real-time monitoring script for polygon processing.
\"\"\"

import json
import time
import os
from datetime import datetime

def monitor_progress():
    \"\"\"Monitor the current processing session.\"\"\"
    
    session_file = 'logs/current_session.json'
    
    if not os.path.exists(session_file):
        print("❌ No active session found. Start processing first.")
        return
    
    with open(session_file, 'r') as f:
        session_info = json.load(f)
    
    print(f"📊 Monitoring Session: {session_info['session_id']}")
    print(f"🕐 Started: {session_info['start_time']}")
    print(f"📝 Log file: {session_info['log_file']}")
    print(f"🔄 Progress file: {session_info['progress_file']}")
    print("="*60)
    
    try:
        while True:
            # Check if progress file exists
            if os.path.exists(session_info['progress_file']):
                with open(session_info['progress_file'], 'r') as f:
                    progress = json.load(f)
                
                print(f"\\r⏳ Stage: {progress['stage']} | "
                      f"Progress: {progress['current']}/{progress['total']} "
                      f"({progress['percentage']:.1f}%) | "
                      f"ETA: {progress['eta_human']} | "
                      f"Memory: {progress['memory_usage_mb']:.1f}MB", end='', flush=True)
            else:
                print("\\r⏳ Waiting for progress data...", end='', flush=True)
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\\n\\n📊 Monitoring stopped.")

if __name__ == "__main__":
    monitor_progress()
"""
    
    with open('monitor_progress.py', 'w') as f:
        f.write(monitor_script)
    
    print("✅ Created monitoring scripts:")
    print("   - start_monitoring_session.sh (tmux session)")
    print("   - monitor_progress.py (real-time monitoring)")


def main():
    """Main execution function with enhanced monitoring."""
    try:
        # Create monitoring scripts
        create_monitoring_scripts()
        
        # Run the pipeline
        matcher = PropertyPolygonMatcherWithMonitoring()
        output_file = matcher.run_full_pipeline()
        
        print("\n" + "="*80)
        print("🎉 MONITORED PROPERTY POLYGON ANALYSIS COMPLETED")
        print("="*80)
        print(f"📊 Session ID: {matcher.stats['session_id']}")
        print(f"📋 Total Listings: {matcher.stats['total_listings']}")
        print(f"🗺️  Total Boundaries Processed: {matcher.stats['total_boundaries']}")
        print(f"🔷 Valid Polygons Created: {matcher.stats['valid_polygons_created']}")
        print(f"✅ Listings Matched: {matcher.stats['listings_matched']}")
        print(f"📈 Match Rate: {(matcher.stats['listings_matched']/matcher.stats['total_listings']*100):.2f}%")
        print(f"⏱️  Total Processing Time: {matcher.stats['processing_time']/60:.1f} minutes")
        print(f"💾 Peak Memory Usage: {matcher.stats['peak_memory_mb']:.1f} MB")
        print(f"📄 Visualization: {output_file}")
        print(f"📝 Log File: {matcher.log_file}")
        print("\n🔍 Open the HTML file in your browser to validate results!")
        print("📊 Check logs/current_session.json for session details")
        
        return 0
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
