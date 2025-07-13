#!/usr/bin/env python3
"""
Enhanced Geocoding Service Testing and Validation
Tests the unified geocoding service and validates performance against targets
"""

import sys
from pathlib import Path
import pandas as pd
import duckdb
from typing import Dict, List, Any
import time
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from oikotie.utils.enhanced_geocoding_service import create_enhanced_geocoding_service


def test_service_initialization():
    """Test that the enhanced geocoding service initializes correctly."""
    print("🔧 Testing Enhanced Geocoding Service Initialization")
    print("=" * 60)
    
    try:
        service = create_enhanced_geocoding_service()
        print("✅ Service initialized successfully")
        
        # Get performance report
        report = service.get_performance_report()
        print(f"✅ Performance report generated")
        
        # Check data source status
        if "data_sources" in report:
            print(f"📊 Data Sources Status:")
            for source_name, status in report["data_sources"].items():
                available = status.get("available", False)
                status_icon = "✅" if available else "❌"
                print(f"   {status_icon} {source_name}: {'Available' if available else 'Unavailable'}")
        
        # Check available layers
        if "available_layers" in report:
            print(f"📊 Available Data Layers:")
            for source_name, layers in report["available_layers"].items():
                print(f"   {source_name}: {len(layers)} layers")
                
        return service
        
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return None


def test_single_address_geocoding(service):
    """Test geocoding of individual addresses."""
    print("\n🎯 Testing Single Address Geocoding")
    print("=" * 50)
    
    test_addresses = [
        "Mannerheimintie 1, Helsinki",
        "Helsingin keskustori 1",
        "Kauppatori 1, Helsinki",
        "Senaatintori 1",
        "Aleksanterinkatu 1, Helsinki",
        "Rautatientori 1",
        "Esplanadi 1, Helsinki",
        "Bulevardi 1, Helsinki"
    ]
    
    results = []
    
    for address in test_addresses:
        print(f"\n🔍 Testing: {address}")
        
        start_time = time.time()
        result = service.geocode_address(address)
        processing_time = (time.time() - start_time) * 1000  # milliseconds
        
        if result:
            print(f"   ✅ Success ({processing_time:.1f}ms)")
            print(f"      Coordinates: ({result.latitude:.6f}, {result.longitude:.6f})")
            print(f"      Quality Score: {result.quality_score:.3f}")
            print(f"      Confidence: {result.confidence:.3f}")
            print(f"      Source: {result.source}")
            print(f"      Method: {result.method}")
            
            results.append({
                "address": address,
                "success": True,
                "latitude": result.latitude,
                "longitude": result.longitude,
                "quality_score": result.quality_score,
                "confidence": result.confidence,
                "source": result.source,
                "method": result.method,
                "processing_time_ms": processing_time
            })
        else:
            print(f"   ❌ Failed ({processing_time:.1f}ms)")
            results.append({
                "address": address,
                "success": False,
                "processing_time_ms": processing_time
            })
    
    # Summary statistics
    successful = [r for r in results if r["success"]]
    if successful:
        avg_quality = sum(r["quality_score"] for r in successful) / len(successful)
        avg_confidence = sum(r["confidence"] for r in successful) / len(successful)
        avg_time = sum(r["processing_time_ms"] for r in results) / len(results)
        
        print(f"\n📊 Single Address Test Summary:")
        print(f"   Success Rate: {len(successful)}/{len(test_addresses)} ({len(successful)/len(test_addresses)*100:.1f}%)")
        print(f"   Average Quality Score: {avg_quality:.3f}")
        print(f"   Average Confidence: {avg_confidence:.3f}")
        print(f"   Average Processing Time: {avg_time:.1f}ms")
        
        # Source distribution
        sources = {}
        for r in successful:
            source = r["source"]
            sources[source] = sources.get(source, 0) + 1
        
        print(f"   Source Distribution:")
        for source, count in sources.items():
            print(f"      {source}: {count} addresses")
    
    return results


def test_geocoding_quality_validation(service, sample_size: int = 50):
    """Test geocoding quality validation against existing database records."""
    print(f"\n🔍 Testing Geocoding Quality Validation (Sample: {sample_size})")
    print("=" * 60)
    
    try:
        validation_results = service.validate_geocoding_quality(
            sample_size=sample_size,
            quality_threshold=0.8
        )
        
        if "error" in validation_results:
            print(f"❌ Validation failed: {validation_results['error']}")
            return None
        
        print(f"📊 Quality Validation Results:")
        print(f"   Total Tested: {validation_results.get('total_tested', 0)}")
        print(f"   Success Rate: {validation_results.get('success_rate', 0):.1f}%")
        print(f"   High Quality Rate: {validation_results.get('high_quality_rate', 0):.1f}%")
        print(f"   Average Quality Score: {validation_results.get('average_quality', 0):.3f}")
        
        print(f"\n   Quality Distribution:")
        print(f"      High Quality (≥0.8): {validation_results.get('high_quality', 0)}")
        print(f"      Medium Quality (0.6-0.8): {validation_results.get('medium_quality', 0)}")
        print(f"      Low Quality (<0.6): {validation_results.get('low_quality', 0)}")
        print(f"      Failed: {validation_results.get('failed', 0)}")
        
        # Source distribution
        source_dist = validation_results.get('source_distribution', {})
        if source_dist:
            print(f"\n   Source Distribution:")
            for source, count in source_dist.items():
                print(f"      {source}: {count} addresses")
        
        # Method distribution
        method_dist = validation_results.get('method_distribution', {})
        if method_dist:
            print(f"\n   Method Distribution:")
            for method, count in method_dist.items():
                print(f"      {method}: {count} addresses")
        
        # Target validation
        success_rate = validation_results.get('success_rate', 0)
        high_quality_rate = validation_results.get('high_quality_rate', 0)
        
        print(f"\n🎯 Target Achievement Assessment:")
        print(f"   Address Resolution Target: ≥95%")
        print(f"   Current Achievement: {success_rate:.1f}% {'✅' if success_rate >= 95 else '❌'}")
        print(f"   High Quality Target: ≥80%")
        print(f"   Current Achievement: {high_quality_rate:.1f}% {'✅' if high_quality_rate >= 80 else '❌'}")
        
        # Distance error analysis (rough estimation)
        details = validation_results.get('details', [])
        if details:
            distance_errors = [d['distance_error_m'] for d in details if d.get('distance_error_m') != float('inf')]
            if distance_errors:
                median_error = sorted(distance_errors)[len(distance_errors)//2]
                print(f"   Distance Error Target: <50m median")
                print(f"   Current Achievement: {median_error:.1f}m {'✅' if median_error < 50 else '❌'}")
        
        return validation_results
        
    except Exception as e:
        print(f"❌ Quality validation failed: {e}")
        return None


def test_batch_geocoding_performance(service, batch_size: int = 20):
    """Test batch geocoding performance."""
    print(f"\n⚡ Testing Batch Geocoding Performance (Batch Size: {batch_size})")
    print("=" * 60)
    
    # Get sample addresses from database
    try:
        with duckdb.connect("data/real_estate.duckdb") as conn:
            sample_addresses = conn.execute(f"""
                SELECT DISTINCT address
                FROM listings
                WHERE address IS NOT NULL
                ORDER BY RANDOM()
                LIMIT {batch_size}
            """).fetchall()
            
            if not sample_addresses:
                print("❌ No addresses found in listings table for batch testing")
                return None
            
            addresses = [row[0] for row in sample_addresses]
            
        print(f"📦 Testing batch geocoding of {len(addresses)} addresses...")
        
        # Progress callback
        def progress_callback(current, total, address):
            if current % 5 == 0:  # Log every 5 addresses
                print(f"   Progress: {current+1}/{total} - {address[:50]}")
        
        start_time = time.time()
        results = service.batch_geocode_addresses(addresses, progress_callback)
        total_time = time.time() - start_time
        
        # Analyze results
        successful = sum(1 for r in results.values() if r is not None)
        success_rate = (successful / len(addresses)) * 100
        avg_time_per_address = (total_time / len(addresses)) * 1000  # milliseconds
        
        print(f"\n📊 Batch Geocoding Results:")
        print(f"   Total Addresses: {len(addresses)}")
        print(f"   Successful: {successful}")
        print(f"   Success Rate: {success_rate:.1f}%")
        print(f"   Total Time: {total_time:.2f}s")
        print(f"   Average Time per Address: {avg_time_per_address:.1f}ms")
        print(f"   Throughput: {len(addresses)/total_time:.1f} addresses/second")
        
        # Source distribution for successful results
        sources = {}
        quality_scores = []
        
        for address, result in results.items():
            if result:
                source = result.source
                sources[source] = sources.get(source, 0) + 1
                quality_scores.append(result.quality_score)
        
        if sources:
            print(f"\n   Source Distribution:")
            for source, count in sources.items():
                percentage = (count / successful) * 100
                print(f"      {source}: {count} ({percentage:.1f}%)")
        
        if quality_scores:
            avg_quality = sum(quality_scores) / len(quality_scores)
            print(f"\n   Quality Metrics:")
            print(f"      Average Quality Score: {avg_quality:.3f}")
            print(f"      High Quality (≥0.8): {sum(1 for q in quality_scores if q >= 0.8)}")
            print(f"      Medium Quality (0.6-0.8): {sum(1 for q in quality_scores if 0.6 <= q < 0.8)}")
            print(f"      Low Quality (<0.6): {sum(1 for q in quality_scores if q < 0.6)}")
        
        return {
            "total_addresses": len(addresses),
            "successful": successful,
            "success_rate": success_rate,
            "total_time": total_time,
            "avg_time_per_address": avg_time_per_address,
            "throughput": len(addresses)/total_time,
            "source_distribution": sources,
            "average_quality": avg_quality if quality_scores else 0
        }
        
    except Exception as e:
        print(f"❌ Batch geocoding test failed: {e}")
        return None


def test_cache_performance(service):
    """Test caching performance."""
    print(f"\n💾 Testing Cache Performance")
    print("=" * 40)
    
    test_address = "Mannerheimintie 1, Helsinki"
    
    # First call (no cache)
    print(f"🔍 First call (cold cache): {test_address}")
    start_time = time.time()
    result1 = service.geocode_address(test_address, use_cache=True)
    first_call_time = (time.time() - start_time) * 1000
    
    if result1:
        print(f"   ✅ Success ({first_call_time:.1f}ms)")
        print(f"      Source: {result1.source}")
    
    # Second call (with cache)
    print(f"\n🔍 Second call (warm cache): {test_address}")
    start_time = time.time()
    result2 = service.geocode_address(test_address, use_cache=True)
    second_call_time = (time.time() - start_time) * 1000
    
    if result2:
        print(f"   ✅ Success ({second_call_time:.1f}ms)")
        print(f"      Source: {result2.source}")
    
    # Calculate cache performance
    if result1 and result2:
        speedup = first_call_time / second_call_time if second_call_time > 0 else float('inf')
        print(f"\n📊 Cache Performance:")
        print(f"   First Call: {first_call_time:.1f}ms")
        print(f"   Second Call: {second_call_time:.1f}ms")
        print(f"   Speedup: {speedup:.1f}x faster")
        print(f"   Cache Hit: {'✅' if speedup > 2 else '❌'}")
        
        return {
            "first_call_ms": first_call_time,
            "second_call_ms": second_call_time,
            "speedup": speedup,
            "cache_effective": speedup > 2
        }
    
    return None


def generate_comprehensive_report(service, all_results: Dict[str, Any]):
    """Generate comprehensive test report."""
    print(f"\n📋 COMPREHENSIVE ENHANCED GEOCODING TEST REPORT")
    print("=" * 70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Service status
    print("🔧 SERVICE STATUS")
    print("-" * 20)
    if all_results.get("initialization_success", False):
        print("✅ Service initialization: SUCCESS")
    else:
        print("❌ Service initialization: FAILED")
    
    # Individual address performance
    single_results = all_results.get("single_address_results", [])
    if single_results:
        successful = [r for r in single_results if r.get("success", False)]
        print(f"✅ Single address geocoding: {len(successful)}/{len(single_results)} addresses")
        
        if successful:
            avg_quality = sum(r["quality_score"] for r in successful) / len(successful)
            avg_time = sum(r["processing_time_ms"] for r in single_results) / len(single_results)
            print(f"   Average quality score: {avg_quality:.3f}")
            print(f"   Average processing time: {avg_time:.1f}ms")
    
    # Quality validation results
    validation_results = all_results.get("validation_results")
    if validation_results:
        print(f"\n🔍 QUALITY VALIDATION")
        print("-" * 20)
        success_rate = validation_results.get("success_rate", 0)
        high_quality_rate = validation_results.get("high_quality_rate", 0)
        
        print(f"Success rate: {success_rate:.1f}% (Target: ≥95%) {'✅' if success_rate >= 95 else '❌'}")
        print(f"High quality rate: {high_quality_rate:.1f}% (Target: ≥80%) {'✅' if high_quality_rate >= 80 else '❌'}")
    
    # Batch performance
    batch_results = all_results.get("batch_results")
    if batch_results:
        print(f"\n⚡ BATCH PERFORMANCE")
        print("-" * 20)
        print(f"Batch success rate: {batch_results.get('success_rate', 0):.1f}%")
        print(f"Throughput: {batch_results.get('throughput', 0):.1f} addresses/second")
        print(f"Average time per address: {batch_results.get('avg_time_per_address', 0):.1f}ms")
    
    # Cache performance
    cache_results = all_results.get("cache_results")
    if cache_results:
        print(f"\n💾 CACHE PERFORMANCE")
        print("-" * 20)
        speedup = cache_results.get("speedup", 1)
        print(f"Cache speedup: {speedup:.1f}x faster")
        print(f"Cache effectiveness: {'✅ Effective' if cache_results.get('cache_effective', False) else '❌ Ineffective'}")
    
    # Overall assessment
    print(f"\n🎯 OVERALL ASSESSMENT")
    print("-" * 20)
    
    targets_met = 0
    total_targets = 0
    
    if validation_results:
        total_targets += 2
        if validation_results.get("success_rate", 0) >= 95:
            targets_met += 1
        if validation_results.get("high_quality_rate", 0) >= 80:
            targets_met += 1
    
    if batch_results:
        total_targets += 1
        if batch_results.get("success_rate", 0) >= 90:
            targets_met += 1
    
    if cache_results:
        total_targets += 1
        if cache_results.get("cache_effective", False):
            targets_met += 1
    
    overall_score = (targets_met / total_targets * 100) if total_targets > 0 else 0
    
    print(f"Targets achieved: {targets_met}/{total_targets} ({overall_score:.1f}%)")
    
    if overall_score >= 80:
        print("🏆 EXCELLENT: Enhanced geocoding service exceeds performance targets")
    elif overall_score >= 60:
        print("✅ GOOD: Enhanced geocoding service meets most performance targets")
    elif overall_score >= 40:
        print("⚠️ FAIR: Enhanced geocoding service needs optimization")
    else:
        print("❌ POOR: Enhanced geocoding service requires significant improvements")
    
    return {
        "targets_met": targets_met,
        "total_targets": total_targets,
        "overall_score": overall_score,
        "timestamp": datetime.now().isoformat()
    }


def main():
    """Main testing function."""
    print("🚀 ENHANCED GEOCODING SERVICE TESTING SUITE")
    print("=" * 70)
    print("Testing the unified geocoding service with multiple data sources")
    print()
    
    all_results = {}
    
    # Test 1: Service initialization
    service = test_service_initialization()
    all_results["initialization_success"] = service is not None
    
    if not service:
        print("❌ Cannot proceed with tests - service initialization failed")
        return
    
    # Test 2: Single address geocoding
    single_results = test_single_address_geocoding(service)
    all_results["single_address_results"] = single_results
    
    # Test 3: Quality validation
    validation_results = test_geocoding_quality_validation(service, sample_size=30)
    all_results["validation_results"] = validation_results
    
    # Test 4: Batch geocoding performance
    batch_results = test_batch_geocoding_performance(service, batch_size=15)
    all_results["batch_results"] = batch_results
    
    # Test 5: Cache performance
    cache_results = test_cache_performance(service)
    all_results["cache_results"] = cache_results
    
    # Generate comprehensive report
    generate_comprehensive_report(service, all_results)
    
    print(f"\n🎯 Enhanced geocoding service testing complete!")
    print(f"   Check the comprehensive report above for detailed results")


if __name__ == "__main__":
    main()
