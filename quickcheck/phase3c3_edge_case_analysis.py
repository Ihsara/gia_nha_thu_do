#!/usr/bin/env python3
"""
Phase 3C.3: Edge Case Analysis and Advanced Optimization
Purpose: Investigate and resolve remaining unmatched listings from Phase 3C.2
Created: 2025-07-12 00:36
Usage: uv run python quickcheck/phase3c3_edge_case_analysis.py
"""

import sys
import json
import time
from pathlib import Path
from collections import defaultdict

import duckdb
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

from oikotie.visualization.utils.data_loader import DataLoader
from oikotie.utils.enhanced_spatial_matching import EnhancedSpatialMatcher

class AdvancedEdgeCaseAnalyzer:
    """Advanced analyzer for investigating and resolving edge cases"""
    
    def __init__(self, target_crs="EPSG:3067"):
        self.target_crs = target_crs
        self.problem_postal_codes = ['00970', '00990', '00960', '00980', '00890']
        
    def load_phase3c2_results(self):
        """Load Phase 3C.2 results for analysis"""
        print("📊 Loading Phase 3C.2 results for edge case analysis...")
        
        # Find most recent Phase 3C.2 results
        data_dir = Path("data")
        pattern = "phase3c2_custom_tolerance_*.json"
        result_files = list(data_dir.glob(pattern))
        
        if not result_files:
            raise FileNotFoundError("No Phase 3C.2 results found. Run Phase 3C.2 first.")
        
        latest_file = max(result_files, key=lambda x: x.stat().st_mtime)
        print(f"✅ Found Phase 3C.2 results: {latest_file}")
        
        with open(latest_file, 'r') as f:
            phase3c2_results = json.load(f)
        
        # Load match results CSV
        csv_pattern = latest_file.stem.replace('custom_tolerance', 'match_results') + '.csv'
        csv_file = data_dir / f"{csv_pattern}"
        
        if csv_file.exists():
            match_results_df = pd.read_csv(csv_file)
            print(f"✅ Loaded {len(match_results_df)} match results")
        else:
            match_results_df = None
            print("⚠️ Match results CSV not found")
        
        return phase3c2_results, match_results_df
    
    def analyze_problem_areas(self, listings_gdf, buildings_gdf):
        """Analyze specific problem areas that failed in Phase 3C.2"""
        print("\n🔍 Analyzing Problem Areas from Phase 3C.2...")
        print("=" * 60)
        
        problem_analysis = {}
        
        # Focus on critical postal codes that failed
        for postal_code in self.problem_postal_codes:
            print(f"\n📮 Analyzing postal code {postal_code}...")
            
            # Extract listings in this postal code
            postal_listings = []
            for idx, row in listings_gdf.iterrows():
                address = row.get('address', '')
                if address and postal_code in address:
                    postal_listings.append(idx)
            
            if not postal_listings:
                print(f"   No listings found for postal code {postal_code}")
                continue
            
            postal_gdf = listings_gdf.iloc[postal_listings].copy()
            print(f"   Found {len(postal_gdf)} listings in postal code {postal_code}")
            
            # Analyze spatial characteristics
            if len(postal_gdf) > 0:
                # Convert to target CRS for analysis
                postal_projected = postal_gdf.to_crs(self.target_crs)
                
                # Calculate spatial statistics
                bounds = postal_projected.total_bounds
                area_km2 = ((bounds[2] - bounds[0]) * (bounds[3] - bounds[1])) / 1_000_000
                density = len(postal_projected) / area_km2 if area_km2 > 0 else 0
                
                # Find nearest buildings for each listing
                distances_to_buildings = []
                for listing_geom in postal_projected.geometry:
                    buildings_projected = buildings_gdf.to_crs(self.target_crs)
                    min_distance = float('inf')
                    
                    # Sample buildings to avoid performance issues
                    building_sample = buildings_projected.sample(min(1000, len(buildings_projected)))
                    
                    for building_geom in building_sample.geometry:
                        try:
                            distance = listing_geom.distance(building_geom)
                            min_distance = min(min_distance, distance)
                        except:
                            continue
                    
                    if min_distance != float('inf'):
                        distances_to_buildings.append(min_distance)
                
                avg_distance_to_building = np.mean(distances_to_buildings) if distances_to_buildings else None
                
                problem_analysis[postal_code] = {
                    'listing_count': len(postal_gdf),
                    'area_km2': area_km2,
                    'density_listings_per_km2': density,
                    'avg_distance_to_building_m': avg_distance_to_building,
                    'min_distance_to_building_m': min(distances_to_buildings) if distances_to_buildings else None,
                    'max_distance_to_building_m': max(distances_to_buildings) if distances_to_buildings else None,
                    'building_coverage': len(buildings_projected)
                }
                
                print(f"   📏 Area: {area_km2:.2f} km²")
                print(f"   🏠 Density: {density:.1f} listings/km²")
                print(f"   📐 Avg distance to building: {avg_distance_to_building:.1f}m" if avg_distance_to_building else "   📐 No distance data")
                print(f"   🏗️ Buildings in area: {len(buildings_projected)}")
        
        return problem_analysis
    
    def suggest_specialized_strategies(self, problem_analysis):
        """Suggest specialized strategies for problem areas"""
        print("\n💡 Specialized Strategy Recommendations...")
        print("=" * 60)
        
        strategies = {}
        
        for postal_code, analysis in problem_analysis.items():
            strategy = {}
            
            avg_distance = analysis.get('avg_distance_to_building_m')
            density = analysis.get('density_listings_per_km2', 0)
            building_count = analysis.get('building_coverage', 0)
            
            print(f"\n📮 {postal_code} Strategy:")
            
            if avg_distance and avg_distance > 100:
                strategy['issue'] = 'Very large distances to buildings'
                strategy['recommendation'] = 'Use alternative spatial data or administrative boundaries'
                strategy['action'] = 'investigate_alternative_data'
                print(f"   🚨 Issue: Very large distances ({avg_distance:.1f}m)")
                print(f"   💡 Recommendation: Use alternative spatial data")
                
            elif building_count < 10:
                strategy['issue'] = 'Insufficient building coverage'
                strategy['recommendation'] = 'Expand building data source or use administrative polygons'
                strategy['action'] = 'expand_building_data'
                print(f"   🚨 Issue: Low building coverage ({building_count} buildings)")
                print(f"   💡 Recommendation: Expand building data source")
                
            elif density < 10:
                strategy['issue'] = 'Very low listing density'
                strategy['recommendation'] = 'Use larger tolerance or different matching approach'
                strategy['action'] = 'increase_tolerance'
                strategy['suggested_tolerance'] = 100.0
                print(f"   🚨 Issue: Low density ({density:.1f} listings/km²)")
                print(f"   💡 Recommendation: Try 100m+ tolerance")
                
            else:
                strategy['issue'] = 'Complex spatial mismatch'
                strategy['recommendation'] = 'Apply machine learning tolerance optimization'
                strategy['action'] = 'ml_optimization'
                print(f"   🔍 Issue: Complex spatial mismatch")
                print(f"   💡 Recommendation: ML-based optimization")
            
            strategies[postal_code] = strategy
        
        return strategies
    
    def test_extreme_tolerance(self, listings_gdf, buildings_gdf, problem_postal_codes, test_tolerance=100.0):
        """Test extreme tolerance values for problem areas"""
        print(f"\n🧪 Testing Extreme Tolerance ({test_tolerance}m) for Problem Areas...")
        print("=" * 60)
        
        # Extract problem area listings
        problem_listings = []
        for idx, row in listings_gdf.iterrows():
            address = row.get('address', '')
            for postal_code in problem_postal_codes:
                if postal_code in address:
                    problem_listings.append(idx)
                    break
        
        if not problem_listings:
            print("No problem listings found")
            return None
        
        problem_gdf = listings_gdf.iloc[problem_listings].copy()
        print(f"Testing {len(problem_gdf)} problem listings with {test_tolerance}m tolerance...")
        
        # Test with extreme tolerance
        matcher = EnhancedSpatialMatcher(
            tolerance_m=test_tolerance,
            target_crs=self.target_crs
        )
        
        try:
            extreme_results = matcher.enhanced_spatial_match(
                points_gdf=problem_gdf,
                buildings_gdf=buildings_gdf,
                point_id_col='address',
                building_id_col='osm_id'
            )
            
            matched_count = len(extreme_results[extreme_results['match_type'] != 'no_match'])
            match_rate = (matched_count / len(problem_gdf)) * 100
            
            print(f"📊 Extreme Tolerance Results:")
            print(f"   Tolerance: {test_tolerance}m")
            print(f"   Matched: {matched_count}/{len(problem_gdf)} ({match_rate:.1f}%)")
            
            if match_rate > 50:
                print(f"   ✅ SUCCESS: Extreme tolerance effective for problem areas")
            else:
                print(f"   ❌ LIMITATION: Even extreme tolerance insufficient")
                print(f"   💡 Recommendation: Investigate data quality issues")
            
            return extreme_results
            
        except Exception as e:
            print(f"❌ Error testing extreme tolerance: {e}")
            return None
    
    def ml_tolerance_optimization(self, listings_gdf, buildings_gdf):
        """Use machine learning to predict optimal tolerance per listing"""
        print("\n🤖 Machine Learning Tolerance Optimization...")
        print("=" * 60)
        
        # Extract features for ML model
        features = []
        targets = []
        
        print("📊 Extracting features for ML model...")
        
        # Sample subset for ML training due to performance
        sample_size = min(1000, len(listings_gdf))
        sample_indices = np.random.choice(len(listings_gdf), sample_size, replace=False)
        sample_gdf = listings_gdf.iloc[sample_indices].copy()
        
        buildings_projected = buildings_gdf.to_crs(self.target_crs)
        
        for idx, row in sample_gdf.iterrows():
            try:
                # Convert to projected CRS
                point_geom = gpd.GeoSeries([row.geometry], crs=sample_gdf.crs).to_crs(self.target_crs).iloc[0]
                
                # Extract spatial features
                # 1. Distance to nearest building
                min_distance = float('inf')
                building_count_500m = 0
                building_count_1km = 0
                
                # Sample buildings for performance
                building_sample = buildings_projected.sample(min(500, len(buildings_projected)))
                
                for building_geom in building_sample.geometry:
                    try:
                        distance = point_geom.distance(building_geom)
                        min_distance = min(min_distance, distance)
                        
                        if distance <= 500:
                            building_count_500m += 1
                        if distance <= 1000:
                            building_count_1km += 1
                    except:
                        continue
                
                if min_distance == float('inf'):
                    continue
                
                # Extract postal code features
                address = row.get('address', '')
                postal_code = 'Unknown'
                for part in address.replace('\n', ', ').split(', '):
                    part = part.strip()
                    if len(part) == 5 and part.startswith('00') and part.isdigit():
                        postal_code = part
                        break
                
                # Encode postal code as district
                postal_int = int(postal_code) if postal_code != 'Unknown' else 0
                district_code = postal_int // 100 if postal_int > 0 else 0
                
                # Create feature vector
                feature_vector = [
                    min_distance,  # Distance to nearest building
                    building_count_500m,  # Building density 500m
                    building_count_1km,   # Building density 1km
                    district_code,        # District encoded
                    point_geom.x,        # X coordinate
                    point_geom.y,        # Y coordinate
                ]
                
                # Target: optimal tolerance based on distance
                if min_distance <= 20:
                    optimal_tolerance = 20.0
                elif min_distance <= 35:
                    optimal_tolerance = 35.0
                elif min_distance <= 50:
                    optimal_tolerance = 50.0
                elif min_distance <= 75:
                    optimal_tolerance = 75.0
                else:
                    optimal_tolerance = 100.0
                
                features.append(feature_vector)
                targets.append(optimal_tolerance)
                
            except Exception as e:
                continue
        
        if len(features) < 10:
            print("❌ Insufficient data for ML training")
            return None
        
        # Train ML model
        print(f"🎯 Training ML model with {len(features)} samples...")
        
        X = np.array(features)
        y = np.array(targets)
        
        # Standardize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Train Random Forest
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_scaled, y)
        
        # Feature importance
        feature_names = [
            'distance_to_building', 'buildings_500m', 'buildings_1km',
            'district_code', 'x_coord', 'y_coord'
        ]
        
        importance = model.feature_importances_
        print("\n📈 Feature Importance:")
        for name, imp in zip(feature_names, importance):
            print(f"   {name}: {imp:.3f}")
        
        return model, scaler, feature_names

def main():
    """Main execution function for Phase 3C.3"""
    print("🔍 Phase 3C.3: Edge Case Analysis and Advanced Optimization")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        # Initialize analyzer
        analyzer = AdvancedEdgeCaseAnalyzer()
        
        # Load Phase 3C.2 results
        phase3c2_results, match_results_df = analyzer.load_phase3c2_results()
        
        print(f"📊 Phase 3C.2 Performance Summary:")
        stats = phase3c2_results['performance_stats']
        print(f"   Match Rate: {stats['match_rate']:.2f}%")
        print(f"   Improvement: +{stats['improvement_over_baseline']:.2f} percentage points")
        print(f"   Unmatched: {stats['total_processed'] - stats['total_matched']} listings")
        
        # Load listings and buildings data
        print("\n📋 Loading listings and buildings data...")
        data_loader = DataLoader()
        
        with data_loader as loader:
            conn = loader.connect()
            query = """
            SELECT DISTINCT 
                l.address,
                l.price_eur as price,
                l.listing_type,
                l.postal_code,
                al.lat,
                al.lon
            FROM listings l
            INNER JOIN address_locations al ON l.address = al.address
            WHERE al.lat IS NOT NULL 
                AND al.lon IS NOT NULL
                AND l.address LIKE '%Helsinki%'
            ORDER BY l.address
            """
            
            listings_df = pd.read_sql_query(query, conn)
        
        # Load buildings
        buildings_path = Path("data/helsinki_buildings_20250711_041142.geojson")
        buildings_gdf = gpd.read_file(buildings_path)
        
        # Convert to GeoDataFrame
        geometry = [Point(row.lon, row.lat) for row in listings_df.itertuples()]
        listings_gdf = gpd.GeoDataFrame(listings_df, geometry=geometry, crs="EPSG:4326")
        
        print(f"✅ Loaded {len(listings_gdf)} listings and {len(buildings_gdf)} buildings")
        
        # Analyze problem areas
        problem_analysis = analyzer.analyze_problem_areas(listings_gdf, buildings_gdf)
        
        # Suggest specialized strategies
        strategies = analyzer.suggest_specialized_strategies(problem_analysis)
        
        # Test extreme tolerance for problem areas
        extreme_results = analyzer.test_extreme_tolerance(
            listings_gdf, buildings_gdf, 
            analyzer.problem_postal_codes,
            test_tolerance=100.0
        )
        
        # ML tolerance optimization
        ml_model_results = analyzer.ml_tolerance_optimization(listings_gdf, buildings_gdf)
        
        # Compile results
        results = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'phase': 'Phase 3C.3 - Edge Case Analysis and Advanced Optimization',
            'phase3c2_baseline': phase3c2_results['performance_stats'],
            'problem_analysis': problem_analysis,
            'specialized_strategies': strategies,
            'extreme_tolerance_test': {
                'tolerance_tested': 100.0,
                'results_available': extreme_results is not None
            },
            'ml_optimization': {
                'model_trained': ml_model_results is not None,
                'features_used': ml_model_results[2] if ml_model_results else None
            }
        }
        
        # Save results
        results_file = f"data/phase3c3_edge_case_analysis_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Phase 3C.3 results saved: {results_file}")
        
        # Summary and recommendations
        print(f"\n🚀 Phase 3C.3 Summary:")
        print(f"   ✅ Identified {len(problem_analysis)} problem postal codes")
        print(f"   🎯 Developed {len(strategies)} specialized strategies")
        print(f"   🧪 Tested extreme tolerance approach")
        if ml_model_results:
            print(f"   🤖 Trained ML model for dynamic tolerance prediction")
        
        print(f"\n🏗️ Phase 3C.4 Recommendations:")
        print(f"   1. Implement specialized strategies for identified problem areas")
        print(f"   2. Deploy ML-based dynamic tolerance for remaining edge cases")
        print(f"   3. Investigate alternative data sources for persistent failures")
        print(f"   4. Progressive validation with Phase 3C.3 improvements")
        
        processing_time = time.time() - start_time
        print(f"\n✅ Phase 3C.3 Edge Case Analysis completed in {processing_time:.1f} seconds")
        
        return results
        
    except Exception as e:
        print(f"❌ Error in Phase 3C.3 analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
