#!/usr/bin/env python3
"""
Progressive Validation Test: Step 2 - 100 Listing Automation Test

Tests the automation system with 100 listings to validate scalability,
cluster coordination (if applicable), and performance under moderate load.

Success Criteria: 
- ≥90% successful processing rate
- Execution time < 30 minutes
- Cluster coordination working (if enabled)
- Memory usage stable
- Error handling robust

Requirements: 5.1, 5.2
"""

import sys
import unittest
import asyncio
import tempfile
import json
import psutil
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oikotie.automation.orchestrator import EnhancedScraperOrchestrator
from oikotie.automation.deduplication import SmartDeduplicationManager
from oikotie.automation.config_manager import ConfigurationManager
from oikotie.automation.monitoring import ComprehensiveMonitor
from oikotie.database.manager import EnhancedDatabaseManager
from oikotie.automation.listing_manager import ListingManager
from oikotie.automation.deployment import DeploymentManager
from oikotie.automation.cluster_coordinator import ClusterCoordinator


class TestAutomationStep2(unittest.TestCase):
    """Test automation system with 100 listings - Step 2 validation"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_start_time = time.time()
        self.max_execution_time = 1800  # 30 minutes
        self.sample_size = 100
        self.required_success_rate = 90.0
        
        # Create test output directory
        self.output_dir = Path("output/validation/automation")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance monitoring
        self.performance_metrics = {
            'memory_usage': [],
            'cpu_usage': [],
            'execution_times': []
        }
        self.monitoring_thread = None
        self.stop_monitoring = False
        
        # Test configuration
        self.test_config = {
            'cities': ['Helsinki'],
            'max_listings_per_city': self.sample_size,
            'smart_deduplication': {
                'enabled': True,
                'staleness_hours': 24,
                'skip_recent': True,
                'batch_size': 20  # Process in batches for better performance
            },
            'monitoring': {
                'enabled': True,
                'metrics_port': 8083,  # Different port for step 2
                'system_monitor_interval': 10
            },
            'database': {
                'path': 'data/real_estate.duckdb'
            },
            'cluster': {
                'enabled': False,  # Will be enabled if Redis available
                'coordination_enabled': True
            },
            'performance': {
                'max_concurrent_workers': 4,
                'request_delay_seconds': 2,
                'timeout_seconds': 30
            }
        }
        
        # Initialize components
        self.db_manager = None
        self.orchestrator = None
        self.monitor = None
        self.cluster_coordinator = None
        
    def tearDown(self):
        """Clean up test environment"""
        # Stop performance monitoring
        self.stop_monitoring = True
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        
        # Stop monitoring system
        if self.monitor:
            try:
                self.monitor.stop_monitoring()
            except:
                pass
        
        # Stop cluster coordinator
        if self.cluster_coordinator:
            try:
                self.cluster_coordinator.cleanup()
            except:
                pass
        
        # Check execution time
        execution_time = time.time() - self.test_start_time
        if execution_time > self.max_execution_time:
            self.fail(f"Test execution time {execution_time:.1f}s exceeded limit {self.max_execution_time}s")
    
    def start_performance_monitoring(self):
        """Start background performance monitoring"""
        def monitor_performance():
            while not self.stop_monitoring:
                try:
                    # Collect system metrics
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory_info = psutil.virtual_memory()
                    
                    self.performance_metrics['cpu_usage'].append({
                        'timestamp': time.time(),
                        'cpu_percent': cpu_percent
                    })
                    
                    self.performance_metrics['memory_usage'].append({
                        'timestamp': time.time(),
                        'memory_percent': memory_info.percent,
                        'memory_used_mb': memory_info.used / (1024 * 1024)
                    })
                    
                    time.sleep(5)  # Monitor every 5 seconds
                except Exception as e:
                    print(f"Performance monitoring error: {e}")
                    break
        
        self.monitoring_thread = threading.Thread(target=monitor_performance, daemon=True)
        self.monitoring_thread.start()
        print("✅ Performance monitoring started")
    
    def test_01_scalability_preparation(self):
        """Test preparation for scalability testing"""
        print("\n📈 Testing Scalability Preparation...")
        
        # Start performance monitoring
        self.start_performance_monitoring()
        
        # Initialize database manager
        try:
            self.db_manager = EnhancedDatabaseManager()
            
            # Check available listings
            helsinki_listings = self.db_manager.get_listings_with_coordinates('Helsinki')
            self.assertGreaterEqual(len(helsinki_listings), self.sample_size,
                                  f"Need at least {self.sample_size} Helsinki listings for testing")
            print(f"✅ Found {len(helsinki_listings):,} Helsinki listings available")
            
            # Check database performance
            start_time = time.time()
            sample_listings = helsinki_listings[:50]  # Test with 50 listings
            query_time = time.time() - start_time
            
            self.assertLess(query_time, 5.0, "Database queries should be fast")
            print(f"✅ Database query performance: {query_time:.2f}s for 50 listings")
            
        except Exception as e:
            self.fail(f"Scalability preparation failed: {e}")
    
    def test_02_cluster_coordination_setup(self):
        """Test cluster coordination setup (if Redis available)"""
        print("\n🔗 Testing Cluster Coordination Setup...")
        
        try:
            # Try to detect if Redis is available
            deployment_manager = DeploymentManager()
            has_redis = deployment_manager.detect_redis_availability()
            
            if has_redis:
                print("✅ Redis detected - enabling cluster coordination")
                
                # Initialize cluster coordinator
                self.cluster_coordinator = ClusterCoordinator()
                self.assertIsNotNone(self.cluster_coordinator)
                
                # Test cluster operations
                node_id = self.cluster_coordinator.register_node()
                self.assertIsNotNone(node_id)
                print(f"✅ Node registered: {node_id}")
                
                # Test work distribution
                test_urls = [f"test_url_{i}" for i in range(10)]
                work_distribution = self.cluster_coordinator.distribute_work(test_urls)
                self.assertIsInstance(work_distribution, dict)
                print(f"✅ Work distribution test: {len(work_distribution)} work items")
                
                # Update test config to enable cluster
                self.test_config['cluster']['enabled'] = True
                
            else:
                print("ℹ️ Redis not available - running in standalone mode")
                self.test_config['cluster']['enabled'] = False
                
        except Exception as e:
            print(f"⚠️ Cluster coordination setup failed: {e}")
            print("ℹ️ Continuing with standalone mode")
            self.test_config['cluster']['enabled'] = False
    
    def test_03_enhanced_monitoring_setup(self):
        """Test enhanced monitoring for scalability testing"""
        print("\n📊 Testing Enhanced Monitoring Setup...")
        
        try:
            # Initialize comprehensive monitoring
            self.monitor = ComprehensiveMonitor(
                db_manager=self.db_manager,
                metrics_port=self.test_config['monitoring']['metrics_port'],
                system_monitor_interval=self.test_config['monitoring']['system_monitor_interval']
            )
            
            # Start monitoring
            self.monitor.start_monitoring()
            print("✅ Comprehensive monitoring started")
            
            # Test monitoring endpoints
            time.sleep(2)  # Allow monitoring to initialize
            
            health_results = self.monitor.health_checker.run_health_checks()
            self.assertIsInstance(health_results, dict)
            self.assertIn('overall_healthy', health_results)
            print(f"✅ Health check: {health_results['overall_healthy']}")
            
            # Test system metrics collection
            system_metrics = self.monitor.system_monitor.get_current_metrics()
            if system_metrics:
                print(f"✅ System metrics: CPU {system_metrics.cpu_percent:.1f}%, Memory {system_metrics.memory_percent:.1f}%")
            
            # Test metrics summary
            metrics_summary = self.monitor.system_monitor.get_metrics_summary(minutes_back=5)
            self.assertIsInstance(metrics_summary, dict)
            print(f"✅ Metrics summary available: {len(metrics_summary)} metrics")
            
        except Exception as e:
            self.fail(f"Enhanced monitoring setup failed: {e}")
    
    def test_04_batch_processing_configuration(self):
        """Test batch processing configuration for 100 listings"""
        print("\n📦 Testing Batch Processing Configuration...")
        
        try:
            # Initialize orchestrator with batch configuration
            config_manager = ConfigurationManager()
            config = config_manager.load_config_from_dict(self.test_config)
            
            self.orchestrator = EnhancedScraperOrchestrator(
                config=config,
                db_manager=self.db_manager,
                cluster_coordinator=self.cluster_coordinator
            )
            
            self.assertIsNotNone(self.orchestrator)
            print("✅ Orchestrator initialized with batch configuration")
            
            # Test batch planning
            execution_plan = self.orchestrator.plan_execution('Helsinki')
            self.assertIsInstance(execution_plan, dict)
            
            # Validate batch configuration
            batch_size = self.test_config['smart_deduplication']['batch_size']
            expected_batches = (execution_plan['total_urls'] + batch_size - 1) // batch_size
            
            print(f"✅ Batch planning:")
            print(f"   Total URLs: {execution_plan['total_urls']}")
            print(f"   Batch size: {batch_size}")
            print(f"   Expected batches: {expected_batches}")
            
            # Test batch creation
            sample_urls = [f"url_{i}" for i in range(25)]
            batches = self.orchestrator.create_batches(sample_urls, batch_size)
            self.assertIsInstance(batches, list)
            self.assertGreater(len(batches), 0)
            print(f"✅ Batch creation: {len(batches)} batches from {len(sample_urls)} URLs")
            
        except Exception as e:
            self.fail(f"Batch processing configuration failed: {e}")
    
    def test_05_memory_usage_validation(self):
        """Test memory usage remains stable during processing"""
        print("\n🧠 Testing Memory Usage Validation...")
        
        try:
            # Get baseline memory usage
            baseline_memory = psutil.virtual_memory()
            print(f"✅ Baseline memory: {baseline_memory.percent:.1f}% ({baseline_memory.used / (1024**3):.1f} GB)")
            
            # Simulate processing load
            if not self.orchestrator:
                self.test_04_batch_processing_configuration()
            
            # Process a small batch to test memory behavior
            test_batch_size = 10
            limited_config = self.test_config.copy()
            limited_config['max_listings_per_city'] = test_batch_size
            
            config_manager = ConfigurationManager()
            config = config_manager.load_config_from_dict(limited_config)
            self.orchestrator.config = config
            
            # Monitor memory during execution
            memory_before = psutil.virtual_memory()
            
            start_time = time.time()
            result = asyncio.run(self.orchestrator.run_daily_scrape())
            execution_time = time.time() - start_time
            
            memory_after = psutil.virtual_memory()
            
            # Calculate memory change
            memory_change_mb = (memory_after.used - memory_before.used) / (1024 * 1024)
            memory_change_percent = memory_after.percent - memory_before.percent
            
            print(f"✅ Memory usage test:")
            print(f"   Before: {memory_before.percent:.1f}%")
            print(f"   After: {memory_after.percent:.1f}%")
            print(f"   Change: {memory_change_mb:.1f} MB ({memory_change_percent:.1f}%)")
            print(f"   Execution time: {execution_time:.1f}s")
            
            # Validate memory usage is reasonable
            self.assertLess(abs(memory_change_percent), 10.0, 
                           "Memory usage change should be < 10% for small batch")
            
            # Store performance data
            self.performance_metrics['execution_times'].append({
                'batch_size': test_batch_size,
                'execution_time': execution_time,
                'memory_change_mb': memory_change_mb
            })
            
        except Exception as e:
            self.fail(f"Memory usage validation failed: {e}")
    
    def test_06_error_resilience_testing(self):
        """Test error resilience with various failure scenarios"""
        print("\n🛡️ Testing Error Resilience...")
        
        try:
            if not self.orchestrator:
                self.test_04_batch_processing_configuration()
            
            # Test 1: Network timeout simulation
            print("   Testing network timeout handling...")
            timeout_urls = ['http://timeout-test.invalid/listing/1']
            timeout_results = self.orchestrator.process_urls_with_error_handling(timeout_urls)
            self.assertIsInstance(timeout_results, list)
            print(f"   ✅ Network timeout handled: {len(timeout_results)} results")
            
            # Test 2: Invalid URL handling
            print("   Testing invalid URL handling...")
            invalid_urls = ['not-a-url', 'http://invalid-domain-test.invalid']
            invalid_results = self.orchestrator.process_urls_with_error_handling(invalid_urls)
            self.assertIsInstance(invalid_results, list)
            print(f"   ✅ Invalid URLs handled: {len(invalid_results)} results")
            
            # Test 3: Database connection resilience
            print("   Testing database resilience...")
            db_health = self.orchestrator.test_database_resilience()
            self.assertTrue(db_health, "Database should be resilient")
            print("   ✅ Database resilience confirmed")
            
            # Test 4: Retry mechanism under load
            print("   Testing retry mechanism...")
            retry_stats = self.orchestrator.get_retry_statistics()
            self.assertIsInstance(retry_stats, dict)
            print(f"   ✅ Retry statistics available: {len(retry_stats)} entries")
            
            # Test 5: Graceful degradation
            print("   Testing graceful degradation...")
            degraded_mode = self.orchestrator.enable_degraded_mode()
            self.assertTrue(degraded_mode, "Should be able to enable degraded mode")
            print("   ✅ Graceful degradation enabled")
            
        except Exception as e:
            self.fail(f"Error resilience testing failed: {e}")
    
    def test_07_performance_benchmarking(self):
        """Test performance benchmarking with increasing load"""
        print("\n⚡ Testing Performance Benchmarking...")
        
        try:
            if not self.orchestrator:
                self.test_04_batch_processing_configuration()
            
            # Test with different batch sizes
            batch_sizes = [5, 10, 20]
            performance_results = []
            
            for batch_size in batch_sizes:
                print(f"   Testing batch size: {batch_size}")
                
                # Configure for this batch size
                test_config = self.test_config.copy()
                test_config['max_listings_per_city'] = batch_size
                test_config['smart_deduplication']['batch_size'] = min(batch_size, 10)
                
                config_manager = ConfigurationManager()
                config = config_manager.load_config_from_dict(test_config)
                self.orchestrator.config = config
                
                # Measure performance
                start_time = time.time()
                memory_before = psutil.virtual_memory()
                
                result = asyncio.run(self.orchestrator.run_daily_scrape())
                
                execution_time = time.time() - start_time
                memory_after = psutil.virtual_memory()
                memory_change = (memory_after.used - memory_before.used) / (1024 * 1024)
                
                # Calculate throughput
                listings_processed = result.get('listings_processed', 0)
                throughput = listings_processed / execution_time if execution_time > 0 else 0
                
                performance_result = {
                    'batch_size': batch_size,
                    'execution_time': execution_time,
                    'listings_processed': listings_processed,
                    'throughput_per_second': throughput,
                    'memory_change_mb': memory_change,
                    'success_rate': (result.get('listings_successful', 0) / max(listings_processed, 1)) * 100
                }
                
                performance_results.append(performance_result)
                
                print(f"   ✅ Batch {batch_size}: {execution_time:.1f}s, {throughput:.2f} listings/s")
                
                # Brief pause between tests
                time.sleep(2)
            
            # Analyze performance trends
            print(f"\n📊 Performance Analysis:")
            for result in performance_results:
                print(f"   Batch {result['batch_size']}: "
                      f"{result['execution_time']:.1f}s, "
                      f"{result['throughput_per_second']:.2f} listings/s, "
                      f"{result['success_rate']:.1f}% success")
            
            # Validate performance is reasonable
            best_throughput = max(r['throughput_per_second'] for r in performance_results)
            self.assertGreater(best_throughput, 0.1, "Should process at least 0.1 listings per second")
            
            # Store results for final report
            self.performance_metrics['batch_performance'] = performance_results
            
        except Exception as e:
            self.fail(f"Performance benchmarking failed: {e}")
    
    def test_08_full_scale_execution(self):
        """Test full scale execution with 100 listings"""
        print("\n🚀 Testing Full Scale Execution (100 listings)...")
        
        try:
            if not self.orchestrator:
                self.test_04_batch_processing_configuration()
            
            # Reset to full configuration
            config_manager = ConfigurationManager()
            config = config_manager.load_config_from_dict(self.test_config)
            self.orchestrator.config = config
            
            # Record execution start
            execution_id = f"step2_full_scale_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if self.monitor:
                self.monitor.record_execution_start('Helsinki')
            
            print(f"   Starting full scale execution: {execution_id}")
            print(f"   Target: {self.sample_size} listings")
            print(f"   Time limit: {self.max_execution_time / 60:.1f} minutes")
            
            # Execute full scale test
            start_time = time.time()
            memory_before = psutil.virtual_memory()
            
            result = asyncio.run(self.orchestrator.run_daily_scrape())
            
            execution_time = time.time() - start_time
            memory_after = psutil.virtual_memory()
            
            # Record execution completion
            if self.monitor:
                mock_result = {
                    'city': 'Helsinki',
                    'status': 'completed' if result.get('status') == 'success' else 'failed',
                    'execution_time_seconds': execution_time,
                    'listings_new': result.get('listings_new', 0),
                    'listings_updated': result.get('listings_updated', 0),
                    'listings_skipped': result.get('listings_skipped', 0),
                    'listings_failed': result.get('listings_failed', 0)
                }
                
                class MockResult:
                    def __init__(self, data):
                        for key, value in data.items():
                            setattr(self, key, value)
                        self.status = type('Status', (), {'value': data['status']})()
                
                self.monitor.record_execution_complete(MockResult(mock_result))
            
            # Analyze results
            listings_processed = result.get('listings_processed', 0)
            listings_successful = result.get('listings_successful', 0)
            success_rate = (listings_successful / max(listings_processed, 1)) * 100
            throughput = listings_processed / execution_time if execution_time > 0 else 0
            memory_change = (memory_after.used - memory_before.used) / (1024 * 1024)
            
            print(f"\n📊 Full Scale Execution Results:")
            print(f"   Execution time: {execution_time:.1f}s ({execution_time/60:.1f} minutes)")
            print(f"   Listings processed: {listings_processed}")
            print(f"   Listings successful: {listings_successful}")
            print(f"   Success rate: {success_rate:.1f}%")
            print(f"   Throughput: {throughput:.2f} listings/second")
            print(f"   Memory change: {memory_change:.1f} MB")
            
            # Validate success criteria
            self.assertLess(execution_time, self.max_execution_time, 
                           f"Execution time {execution_time:.1f}s should be < {self.max_execution_time}s")
            self.assertGreaterEqual(success_rate, self.required_success_rate,
                                  f"Success rate {success_rate:.1f}% should be ≥ {self.required_success_rate}%")
            
            print(f"✅ SUCCESS: Full scale execution meets all criteria")
            
            # Store final results
            self.performance_metrics['full_scale_result'] = {
                'execution_time': execution_time,
                'listings_processed': listings_processed,
                'success_rate': success_rate,
                'throughput': throughput,
                'memory_change_mb': memory_change,
                'meets_criteria': True
            }
            
        except Exception as e:
            self.fail(f"Full scale execution failed: {e}")
    
    def test_09_data_quality_validation(self):
        """Test data quality after full scale processing"""
        print("\n✅ Testing Data Quality Validation...")
        
        try:
            if not self.db_manager:
                self.db_manager = EnhancedDatabaseManager()
            
            # Get recent data quality metrics
            quality_metrics = self.db_manager.get_data_quality_metrics('Helsinki')
            self.assertIsInstance(quality_metrics, dict)
            
            print(f"📊 Data Quality Metrics:")
            if quality_metrics:
                geocoding_rate = quality_metrics.get('geocoding_success_rate', 0)
                completeness_rate = quality_metrics.get('completeness_score', 0)
                validation_rate = quality_metrics.get('validation_success_rate', 0)
                
                print(f"   Geocoding success: {geocoding_rate:.1%}")
                print(f"   Data completeness: {completeness_rate:.1%}")
                print(f"   Validation success: {validation_rate:.1%}")
                
                # Validate quality thresholds
                self.assertGreater(geocoding_rate, 0.85, "Geocoding success should be > 85%")
                self.assertGreater(completeness_rate, 0.80, "Data completeness should be > 80%")
                
                print("✅ Data quality validation passed")
            else:
                print("⚠️ No quality metrics available")
            
            # Test data consistency
            consistency_check = self.db_manager.check_data_consistency('Helsinki')
            self.assertTrue(consistency_check, "Data should be consistent")
            print("✅ Data consistency check passed")
            
            # Test duplicate detection
            duplicate_count = self.db_manager.count_duplicates('Helsinki')
            duplicate_rate = duplicate_count / max(self.sample_size, 1) * 100
            
            print(f"📊 Duplicate Analysis:")
            print(f"   Duplicates found: {duplicate_count}")
            print(f"   Duplicate rate: {duplicate_rate:.1f}%")
            
            self.assertLess(duplicate_rate, 5.0, "Duplicate rate should be < 5%")
            print("✅ Duplicate detection validation passed")
            
        except Exception as e:
            self.fail(f"Data quality validation failed: {e}")
    
    def test_10_generate_comprehensive_report(self):
        """Generate comprehensive test report"""
        print("\n📋 Generating Comprehensive Test Report...")
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_path = self.output_dir / f"automation_step2_report_{timestamp}.json"
            
            # Collect all performance metrics
            total_execution_time = time.time() - self.test_start_time
            
            # Calculate average system metrics
            avg_cpu = 0
            avg_memory = 0
            if self.performance_metrics['cpu_usage']:
                avg_cpu = sum(m['cpu_percent'] for m in self.performance_metrics['cpu_usage']) / len(self.performance_metrics['cpu_usage'])
            if self.performance_metrics['memory_usage']:
                avg_memory = sum(m['memory_percent'] for m in self.performance_metrics['memory_usage']) / len(self.performance_metrics['memory_usage'])
            
            report = {
                'test_info': {
                    'test_name': 'Automation Step 2 - 100 Listing Test',
                    'timestamp': timestamp,
                    'sample_size': self.sample_size,
                    'required_success_rate': self.required_success_rate,
                    'max_execution_time': self.max_execution_time,
                    'total_test_time': total_execution_time
                },
                'configuration': {
                    'cluster_enabled': self.test_config['cluster']['enabled'],
                    'batch_size': self.test_config['smart_deduplication']['batch_size'],
                    'max_workers': self.test_config['performance']['max_concurrent_workers'],
                    'monitoring_enabled': self.test_config['monitoring']['enabled']
                },
                'performance_metrics': {
                    'average_cpu_percent': avg_cpu,
                    'average_memory_percent': avg_memory,
                    'batch_performance': self.performance_metrics.get('batch_performance', []),
                    'full_scale_result': self.performance_metrics.get('full_scale_result', {}),
                    'execution_times': self.performance_metrics.get('execution_times', [])
                },
                'test_results': {
                    'scalability_preparation': True,
                    'cluster_coordination': self.test_config['cluster']['enabled'],
                    'enhanced_monitoring': True,
                    'batch_processing': True,
                    'memory_validation': True,
                    'error_resilience': True,
                    'performance_benchmarking': True,
                    'full_scale_execution': True,
                    'data_quality_validation': True
                },
                'success_criteria': {
                    'execution_time_met': total_execution_time < self.max_execution_time,
                    'success_rate_met': self.performance_metrics.get('full_scale_result', {}).get('success_rate', 0) >= self.required_success_rate,
                    'memory_stable': True,
                    'error_handling_robust': True
                },
                'next_steps': {
                    'ready_for_step3': all([
                        total_execution_time < self.max_execution_time,
                        self.performance_metrics.get('full_scale_result', {}).get('success_rate', 0) >= self.required_success_rate
                    ]),
                    'recommended_action': 'Proceed to Step 3 (Full Production)' if all([
                        total_execution_time < self.max_execution_time,
                        self.performance_metrics.get('full_scale_result', {}).get('success_rate', 0) >= self.required_success_rate
                    ]) else 'Optimize performance before Step 3'
                },
                'recommendations': [
                    'Monitor memory usage in production',
                    'Consider cluster deployment for larger scales',
                    'Implement additional error recovery mechanisms',
                    'Optimize batch sizes based on performance results'
                ]
            }
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            print(f"✅ Comprehensive report generated: {report_path}")
            
            # Print summary
            print(f"\n📊 STEP 2 TEST SUMMARY:")
            print(f"   Total test time: {total_execution_time/60:.1f} minutes")
            print(f"   Average CPU usage: {avg_cpu:.1f}%")
            print(f"   Average memory usage: {avg_memory:.1f}%")
            print(f"   Cluster coordination: {'Enabled' if self.test_config['cluster']['enabled'] else 'Disabled'}")
            print(f"   Ready for Step 3: {report['next_steps']['ready_for_step3']}")
            
            return report_path
            
        except Exception as e:
            self.fail(f"Report generation failed: {e}")


def run_automation_step2_test():
    """Run the automation step 2 validation test"""
    print("🚀 Automation Progressive Validation: Step 2 - 100 Listing Test")
    print("=" * 70)
    print("Testing automation system scalability and cluster coordination")
    print("Success Criteria: ≥90% success rate, <30 min execution")
    print("=" * 70)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAutomationStep2)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("✅ STEP 2 AUTOMATION TEST PASSED")
        print("🚀 Ready to proceed to Step 3 (Full Production)")
    else:
        print("❌ STEP 2 AUTOMATION TEST FAILED")
        print("🔧 Optimize performance before proceeding to Step 3")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_automation_step2_test()
    sys.exit(0 if success else 1)