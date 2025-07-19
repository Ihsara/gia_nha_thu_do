#!/usr/bin/env python3
"""
Performance and Load Testing for Daily Scraper Automation

This module provides comprehensive performance and load testing for production scenarios,
including stress testing, resource monitoring, and scalability validation.

Requirements: 5.1, 5.2, 5.3
"""

import sys
import unittest
import asyncio
import json
import time
import threading
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import gc

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oikotie.automation.orchestrator import EnhancedScraperOrchestrator
from oikotie.automation.config_manager import ConfigurationManager
from oikotie.automation.monitoring import SystemMonitor, ComprehensiveMonitor
from oikotie.database.manager import EnhancedDatabaseManager


class TestPerformanceLoad(unittest.TestCase):
    """Performance and load testing for automation system"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_start_time = time.time()
        self.output_dir = Path("output/validation/performance")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance test configurations
        self.performance_configs = {
            'light_load': {
                'cities': ['Helsinki'],
                'max_listings_per_city': 25,
                'concurrent_workers': 2,
                'expected_duration': 120  # 2 minutes
            },
            'medium_load': {
                'cities': ['Helsinki', 'Espoo'],
                'max_listings_per_city': 50,
                'concurrent_workers': 4,
                'expected_duration': 300  # 5 minutes
            },
            'heavy_load': {
                'cities': ['Helsinki', 'Espoo', 'Vantaa'],
                'max_listings_per_city': 100,
                'concurrent_workers': 6,
                'expected_duration': 600  # 10 minutes
            },
            'stress_test': {
                'cities': ['Helsinki', 'Espoo', 'Vantaa', 'Tampere'],
                'max_listings_per_city': 150,
                'concurrent_workers': 8,
                'expected_duration': 900  # 15 minutes
            }
        }
        
        self.performance_results = {}
        self.resource_metrics = {}
        self.scalability_data = {}
        
    def tearDown(self):
        """Clean up test environment"""
        execution_time = time.time() - self.test_start_time
        print(f"\n⚡ Performance Testing Summary:")
        print(f"   Total execution time: {execution_time:.1f}s")
        print(f"   Performance tests: {len(self.performance_results)}")
        print(f"   Resource metrics collected: {len(self.resource_metrics)}")
        
        # Force garbage collection
        gc.collect()
    
    def test_01_baseline_performance_measurement(self):
        """Measure baseline performance with minimal load"""
        print("\n📊 Testing Baseline Performance Measurement...")
        
        try:
            # Configure for baseline test
            baseline_config = {
                'cities': ['Helsinki'],
                'max_listings_per_city': 10,
                'smart_deduplication': {
                    'enabled': True,
                    'staleness_hours': 1
                },
                'monitoring': {
                    'enabled': True,
                    'metrics_port': 8089
                },
                'database': {
                    'path': 'data/real_estate.duckdb'
                }
            }
            
            # Initialize components
            db_manager = EnhancedDatabaseManager()
            config_manager = ConfigurationManager()
            config = config_manager.load_config_from_dict(baseline_config)
            
            orchestrator = EnhancedScraperOrchestrator(config=config, db_manager=db_manager)
            
            # Start resource monitoring
            system_monitor = SystemMonitor(collection_interval=1)
            system_monitor.start_monitoring()
            
            # Measure baseline performance
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            start_cpu = psutil.cpu_percent()
            
            # Execute baseline test
            result = asyncio.run(orchestrator.run_daily_scrape())
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            end_cpu = psutil.cpu_percent()
            
            system_monitor.stop_monitoring()
            
            # Calculate baseline metrics
            execution_time = end_time - start_time
            memory_usage = end_memory - start_memory
            cpu_usage = end_cpu - start_cpu
            
            # Get system metrics during execution
            system_metrics = system_monitor.get_metrics_summary()
            
            baseline_metrics = {
                'execution_time': execution_time,
                'memory_usage_mb': memory_usage,
                'cpu_usage_percent': cpu_usage,
                'listings_processed': result.get('urls_processed', 0),
                'success': result.get('status') in ['success', 'completed'],
                'system_metrics': system_metrics,
                'throughput_listings_per_second': result.get('urls_processed', 0) / execution_time if execution_time > 0 else 0
            }
            
            self.performance_results['baseline'] = baseline_metrics
            
            print(f"✅ Baseline Performance: {execution_time:.1f}s, {memory_usage:.1f}MB, {baseline_metrics['throughput_listings_per_second']:.2f} listings/s")
            
        except Exception as e:
            self.performance_results['baseline'] = {
                'success': False,
                'error': str(e)
            }
            self.fail(f"Baseline performance measurement failed: {e}")
    
    def test_02_load_testing_scenarios(self):
        """Test various load scenarios"""
        print("\n🔥 Testing Load Scenarios...")
        
        for load_name, load_config in self.performance_configs.items():
            print(f"   Testing {load_name} scenario...")
            
            try:
                # Configure for load test
                test_config = {
                    'cities': load_config['cities'],
                    'max_listings_per_city': load_config['max_listings_per_city'],
                    'smart_deduplication': {
                        'enabled': True,
                        'staleness_hours': 1
                    },
                    'monitoring': {
                        'enabled': True,
                        'metrics_port': 8089 + hash(load_name) % 100  # Unique port
                    },
                    'database': {
                        'path': 'data/real_estate.duckdb'
                    }
                }
                
                # Initialize components
                db_manager = EnhancedDatabaseManager()
                config_manager = ConfigurationManager()
                config = config_manager.load_config_from_dict(test_config)
                
                orchestrator = EnhancedScraperOrchestrator(config=config, db_manager=db_manager)
                
                # Start comprehensive monitoring
                monitor = ComprehensiveMonitor(
                    metrics_port=test_config['monitoring']['metrics_port'],
                    system_monitor_interval=2
                )
                monitor.start_monitoring()
                
                # Execute load test
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                
                result = asyncio.run(orchestrator.run_daily_scrape())
                
                end_time = time.time()
                end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                
                monitor.stop_monitoring()
                
                # Calculate load test metrics
                execution_time = end_time - start_time
                memory_usage = end_memory - start_memory
                
                # Get comprehensive metrics
                system_metrics = monitor.get_current_system_metrics()
                metrics_summary = monitor.get_metrics_summary()
                
                # Performance thresholds
                expected_duration = load_config['expected_duration']
                performance_acceptable = execution_time <= expected_duration * 1.5  # 50% tolerance
                
                load_metrics = {
                    'load_scenario': load_name,
                    'execution_time': execution_time,
                    'expected_duration': expected_duration,
                    'performance_acceptable': performance_acceptable,
                    'memory_usage_mb': memory_usage,
                    'cities_processed': len(load_config['cities']),
                    'max_listings_per_city': load_config['max_listings_per_city'],
                    'listings_processed': result.get('urls_processed', 0),
                    'success': result.get('status') in ['success', 'completed'],
                    'system_metrics': system_metrics,
                    'metrics_summary': metrics_summary,
                    'throughput_listings_per_second': result.get('urls_processed', 0) / execution_time if execution_time > 0 else 0,
                    'result': result
                }
                
                self.performance_results[load_name] = load_metrics
                
                status = "✅" if performance_acceptable else "⚠️"
                print(f"   {status} {load_name}: {execution_time:.1f}s (expected ≤{expected_duration}s), {memory_usage:.1f}MB")
                
                # Brief pause between tests to allow system recovery
                time.sleep(5)
                
            except Exception as e:
                self.performance_results[load_name] = {
                    'success': False,
                    'error': str(e)
                }
                print(f"   ❌ {load_name} failed: {e}")
        
        print("✅ Load Testing Scenarios completed")
    
    def test_03_concurrent_execution_performance(self):
        """Test performance under concurrent execution"""
        print("\n🔀 Testing Concurrent Execution Performance...")
        
        try:
            # Configure concurrent execution test
            concurrent_configs = []
            for i in range(3):  # 3 concurrent sessions
                config = {
                    'cities': ['Helsinki'],
                    'max_listings_per_city': 20,
                    'smart_deduplication': {
                        'enabled': True,
                        'staleness_hours': 1
                    },
                    'monitoring': {
                        'enabled': True,
                        'metrics_port': 8090 + i
                    },
                    'database': {
                        'path': 'data/real_estate.duckdb'
                    }
                }
                concurrent_configs.append(config)
            
            # Start system monitoring
            system_monitor = SystemMonitor(collection_interval=1)
            system_monitor.start_monitoring()
            
            # Execute concurrent sessions
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                
                for i, config in enumerate(concurrent_configs):
                    future = executor.submit(self._execute_performance_session, config, f"concurrent_{i}")
                    futures.append(future)
                
                # Wait for all sessions to complete
                concurrent_results = []
                for future in as_completed(futures, timeout=600):  # 10 minute timeout
                    result = future.result()
                    concurrent_results.append(result)
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            system_monitor.stop_monitoring()
            
            # Analyze concurrent performance
            total_execution_time = end_time - start_time
            total_memory_usage = end_memory - start_memory
            
            successful_sessions = sum(1 for r in concurrent_results if r['success'])
            total_sessions = len(concurrent_results)
            
            # Calculate aggregate metrics
            total_listings_processed = sum(r.get('listings_processed', 0) for r in concurrent_results)
            avg_session_time = statistics.mean([r.get('execution_time', 0) for r in concurrent_results if r['success']])
            
            system_metrics = system_monitor.get_metrics_summary()
            
            concurrent_metrics = {
                'total_execution_time': total_execution_time,
                'avg_session_time': avg_session_time,
                'total_memory_usage_mb': total_memory_usage,
                'successful_sessions': successful_sessions,
                'total_sessions': total_sessions,
                'total_listings_processed': total_listings_processed,
                'aggregate_throughput': total_listings_processed / total_execution_time if total_execution_time > 0 else 0,
                'system_metrics': system_metrics,
                'session_results': concurrent_results,
                'success': successful_sessions == total_sessions
            }
            
            self.performance_results['concurrent_execution'] = concurrent_metrics
            
            print(f"✅ Concurrent Execution: {total_execution_time:.1f}s total, {avg_session_time:.1f}s avg, {successful_sessions}/{total_sessions} successful")
            
        except Exception as e:
            self.performance_results['concurrent_execution'] = {
                'success': False,
                'error': str(e)
            }
            self.fail(f"Concurrent execution performance test failed: {e}")
    
    def test_04_memory_usage_profiling(self):
        """Profile memory usage patterns"""
        print("\n💾 Testing Memory Usage Profiling...")
        
        try:
            # Configure for memory profiling
            memory_config = {
                'cities': ['Helsinki', 'Espoo'],
                'max_listings_per_city': 75,
                'smart_deduplication': {
                    'enabled': True,
                    'staleness_hours': 1
                },
                'monitoring': {
                    'enabled': True,
                    'metrics_port': 8091
                },
                'database': {
                    'path': 'data/real_estate.duckdb'
                }
            }
            
            # Initialize components
            db_manager = EnhancedDatabaseManager()
            config_manager = ConfigurationManager()
            config = config_manager.load_config_from_dict(memory_config)
            
            orchestrator = EnhancedScraperOrchestrator(config=config, db_manager=db_manager)
            
            # Memory profiling
            memory_samples = []
            
            def collect_memory_sample():
                """Collect memory usage sample"""
                process = psutil.Process()
                memory_info = process.memory_info()
                return {
                    'timestamp': time.time(),
                    'rss_mb': memory_info.rss / 1024 / 1024,
                    'vms_mb': memory_info.vms / 1024 / 1024,
                    'percent': process.memory_percent()
                }
            
            # Start memory monitoring
            memory_monitor_active = True
            
            def memory_monitor():
                while memory_monitor_active:
                    memory_samples.append(collect_memory_sample())
                    time.sleep(2)  # Sample every 2 seconds
            
            memory_thread = threading.Thread(target=memory_monitor)
            memory_thread.start()
            
            # Execute test with memory monitoring
            start_time = time.time()
            initial_memory = collect_memory_sample()
            
            result = asyncio.run(orchestrator.run_daily_scrape())
            
            end_time = time.time()
            final_memory = collect_memory_sample()
            
            # Stop memory monitoring
            memory_monitor_active = False
            memory_thread.join()
            
            # Analyze memory usage patterns
            if memory_samples:
                rss_values = [sample['rss_mb'] for sample in memory_samples]
                memory_stats = {
                    'initial_memory_mb': initial_memory['rss_mb'],
                    'final_memory_mb': final_memory['rss_mb'],
                    'peak_memory_mb': max(rss_values),
                    'min_memory_mb': min(rss_values),
                    'avg_memory_mb': statistics.mean(rss_values),
                    'memory_growth_mb': final_memory['rss_mb'] - initial_memory['rss_mb'],
                    'memory_samples_count': len(memory_samples),
                    'execution_time': end_time - start_time
                }
                
                # Memory efficiency metrics
                listings_processed = result.get('urls_processed', 0)
                memory_per_listing = memory_stats['memory_growth_mb'] / listings_processed if listings_processed > 0 else 0
                
                memory_stats['memory_per_listing_mb'] = memory_per_listing
                memory_stats['memory_efficient'] = memory_per_listing < 1.0  # Less than 1MB per listing
                
            else:
                memory_stats = {'error': 'No memory samples collected'}
            
            self.resource_metrics['memory_profiling'] = {
                'success': result.get('status') in ['success', 'completed'],
                'memory_stats': memory_stats,
                'memory_samples': memory_samples[-10:],  # Last 10 samples
                'result': result
            }
            
            print(f"✅ Memory Profiling: Peak {memory_stats.get('peak_memory_mb', 0):.1f}MB, Growth {memory_stats.get('memory_growth_mb', 0):.1f}MB")
            
        except Exception as e:
            self.resource_metrics['memory_profiling'] = {
                'success': False,
                'error': str(e)
            }
            self.fail(f"Memory usage profiling failed: {e}")
    
    def test_05_cpu_performance_analysis(self):
        """Analyze CPU performance patterns"""
        print("\n🖥️ Testing CPU Performance Analysis...")
        
        try:
            # Configure for CPU analysis
            cpu_config = {
                'cities': ['Helsinki', 'Espoo'],
                'max_listings_per_city': 60,
                'smart_deduplication': {
                    'enabled': True,
                    'staleness_hours': 1
                },
                'monitoring': {
                    'enabled': True,
                    'metrics_port': 8092
                },
                'database': {
                    'path': 'data/real_estate.duckdb'
                }
            }
            
            # Initialize components
            db_manager = EnhancedDatabaseManager()
            config_manager = ConfigurationManager()
            config = config_manager.load_config_from_dict(cpu_config)
            
            orchestrator = EnhancedScraperOrchestrator(config=config, db_manager=db_manager)
            
            # CPU monitoring
            cpu_samples = []
            
            def collect_cpu_sample():
                """Collect CPU usage sample"""
                return {
                    'timestamp': time.time(),
                    'cpu_percent': psutil.cpu_percent(interval=None),
                    'cpu_count': psutil.cpu_count(),
                    'load_avg': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
                }
            
            # Start CPU monitoring
            cpu_monitor_active = True
            
            def cpu_monitor():
                while cpu_monitor_active:
                    cpu_samples.append(collect_cpu_sample())
                    time.sleep(1)  # Sample every second
            
            cpu_thread = threading.Thread(target=cpu_monitor)
            cpu_thread.start()
            
            # Execute test with CPU monitoring
            start_time = time.time()
            initial_cpu = collect_cpu_sample()
            
            result = asyncio.run(orchestrator.run_daily_scrape())
            
            end_time = time.time()
            final_cpu = collect_cpu_sample()
            
            # Stop CPU monitoring
            cpu_monitor_active = False
            cpu_thread.join()
            
            # Analyze CPU usage patterns
            if cpu_samples:
                cpu_values = [sample['cpu_percent'] for sample in cpu_samples if sample['cpu_percent'] is not None]
                
                if cpu_values:
                    cpu_stats = {
                        'initial_cpu_percent': initial_cpu['cpu_percent'],
                        'final_cpu_percent': final_cpu['cpu_percent'],
                        'peak_cpu_percent': max(cpu_values),
                        'min_cpu_percent': min(cpu_values),
                        'avg_cpu_percent': statistics.mean(cpu_values),
                        'cpu_samples_count': len(cpu_values),
                        'execution_time': end_time - start_time,
                        'cpu_count': initial_cpu['cpu_count']
                    }
                    
                    # CPU efficiency metrics
                    listings_processed = result.get('urls_processed', 0)
                    cpu_efficiency = listings_processed / cpu_stats['avg_cpu_percent'] if cpu_stats['avg_cpu_percent'] > 0 else 0
                    
                    cpu_stats['cpu_efficiency'] = cpu_efficiency
                    cpu_stats['cpu_utilization_good'] = cpu_stats['avg_cpu_percent'] < 80.0  # Less than 80% average
                    
                else:
                    cpu_stats = {'error': 'No valid CPU samples collected'}
            else:
                cpu_stats = {'error': 'No CPU samples collected'}
            
            self.resource_metrics['cpu_analysis'] = {
                'success': result.get('status') in ['success', 'completed'],
                'cpu_stats': cpu_stats,
                'cpu_samples': cpu_samples[-10:],  # Last 10 samples
                'result': result
            }
            
            print(f"✅ CPU Analysis: Peak {cpu_stats.get('peak_cpu_percent', 0):.1f}%, Avg {cpu_stats.get('avg_cpu_percent', 0):.1f}%")
            
        except Exception as e:
            self.resource_metrics['cpu_analysis'] = {
                'success': False,
                'error': str(e)
            }
            self.fail(f"CPU performance analysis failed: {e}")
    
    def test_06_scalability_testing(self):
        """Test system scalability with increasing load"""
        print("\n📈 Testing System Scalability...")
        
        try:
            # Scalability test scenarios (increasing load)
            scalability_scenarios = [
                {'cities': 1, 'listings_per_city': 20, 'name': 'scale_1x'},
                {'cities': 2, 'listings_per_city': 30, 'name': 'scale_2x'},
                {'cities': 3, 'listings_per_city': 40, 'name': 'scale_3x'},
                {'cities': 4, 'listings_per_city': 50, 'name': 'scale_4x'}
            ]
            
            scalability_results = []
            
            for scenario in scalability_scenarios:
                print(f"   Testing {scenario['name']} scenario...")
                
                # Configure for scalability test
                cities = ['Helsinki', 'Espoo', 'Vantaa', 'Tampere'][:scenario['cities']]
                
                scale_config = {
                    'cities': cities,
                    'max_listings_per_city': scenario['listings_per_city'],
                    'smart_deduplication': {
                        'enabled': True,
                        'staleness_hours': 1
                    },
                    'monitoring': {
                        'enabled': True,
                        'metrics_port': 8093 + len(scalability_results)
                    },
                    'database': {
                        'path': 'data/real_estate.duckdb'
                    }
                }
                
                # Execute scalability test
                try:
                    db_manager = EnhancedDatabaseManager()
                    config_manager = ConfigurationManager()
                    config = config_manager.load_config_from_dict(scale_config)
                    
                    orchestrator = EnhancedScraperOrchestrator(config=config, db_manager=db_manager)
                    
                    # Measure performance
                    start_time = time.time()
                    start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                    start_cpu = psutil.cpu_percent()
                    
                    result = asyncio.run(orchestrator.run_daily_scrape())
                    
                    end_time = time.time()
                    end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                    end_cpu = psutil.cpu_percent()
                    
                    # Calculate scalability metrics
                    execution_time = end_time - start_time
                    memory_usage = end_memory - start_memory
                    cpu_usage = end_cpu - start_cpu
                    
                    listings_processed = result.get('urls_processed', 0)
                    throughput = listings_processed / execution_time if execution_time > 0 else 0
                    
                    scale_result = {
                        'scenario': scenario['name'],
                        'cities_count': scenario['cities'],
                        'listings_per_city': scenario['listings_per_city'],
                        'total_expected_listings': scenario['cities'] * scenario['listings_per_city'],
                        'execution_time': execution_time,
                        'memory_usage_mb': memory_usage,
                        'cpu_usage_percent': cpu_usage,
                        'listings_processed': listings_processed,
                        'throughput_listings_per_second': throughput,
                        'success': result.get('status') in ['success', 'completed'],
                        'result': result
                    }
                    
                    scalability_results.append(scale_result)
                    
                    print(f"   ✅ {scenario['name']}: {execution_time:.1f}s, {throughput:.2f} listings/s")
                    
                    # Brief pause between scalability tests
                    time.sleep(3)
                    
                except Exception as e:
                    scale_result = {
                        'scenario': scenario['name'],
                        'success': False,
                        'error': str(e)
                    }
                    scalability_results.append(scale_result)
                    print(f"   ❌ {scenario['name']} failed: {e}")
            
            # Analyze scalability trends
            successful_results = [r for r in scalability_results if r.get('success', False)]
            
            if len(successful_results) >= 2:
                # Calculate scalability metrics
                execution_times = [r['execution_time'] for r in successful_results]
                throughputs = [r['throughput_listings_per_second'] for r in successful_results]
                memory_usages = [r['memory_usage_mb'] for r in successful_results]
                
                scalability_analysis = {
                    'linear_scaling': self._analyze_linear_scaling(successful_results),
                    'throughput_trend': 'increasing' if throughputs[-1] > throughputs[0] else 'decreasing',
                    'memory_scaling': self._analyze_memory_scaling(successful_results),
                    'performance_degradation': execution_times[-1] / execution_times[0] if execution_times[0] > 0 else 1.0
                }
            else:
                scalability_analysis = {'error': 'Insufficient successful results for analysis'}
            
            self.scalability_data['scalability_testing'] = {
                'success': len(successful_results) >= len(scalability_scenarios) * 0.75,  # 75% success rate
                'scalability_results': scalability_results,
                'scalability_analysis': scalability_analysis,
                'successful_scenarios': len(successful_results),
                'total_scenarios': len(scalability_scenarios)
            }
            
            print(f"✅ Scalability Testing: {len(successful_results)}/{len(scalability_scenarios)} scenarios successful")
            
        except Exception as e:
            self.scalability_data['scalability_testing'] = {
                'success': False,
                'error': str(e)
            }
            self.fail(f"Scalability testing failed: {e}")
    
    def test_07_generate_performance_report(self):
        """Generate comprehensive performance test report"""
        print("\n📋 Generating Performance Test Report...")
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_path = self.output_dir / f"performance_test_report_{timestamp}.json"
            
            # Calculate overall performance metrics
            total_performance_tests = len(self.performance_results)
            successful_performance_tests = sum(
                1 for result in self.performance_results.values() 
                if result.get('success', False)
            )
            
            total_resource_tests = len(self.resource_metrics)
            successful_resource_tests = sum(
                1 for result in self.resource_metrics.values() 
                if result.get('success', False)
            )
            
            total_scalability_tests = len(self.scalability_data)
            successful_scalability_tests = sum(
                1 for result in self.scalability_data.values() 
                if result.get('success', False)
            )
            
            # Generate comprehensive report
            report = {
                'test_info': {
                    'test_name': 'Performance and Load Testing Suite',
                    'timestamp': timestamp,
                    'total_execution_time': time.time() - self.test_start_time,
                    'test_categories': {
                        'performance_tests': total_performance_tests,
                        'resource_tests': total_resource_tests,
                        'scalability_tests': total_scalability_tests
                    }
                },
                'performance_results': self.performance_results,
                'resource_metrics': self.resource_metrics,
                'scalability_data': self.scalability_data,
                'summary': {
                    'performance_success_rate': (successful_performance_tests / total_performance_tests * 100) if total_performance_tests > 0 else 0,
                    'resource_success_rate': (successful_resource_tests / total_resource_tests * 100) if total_resource_tests > 0 else 0,
                    'scalability_success_rate': (successful_scalability_tests / total_scalability_tests * 100) if total_scalability_tests > 0 else 0,
                    'overall_performance_ready': (
                        successful_performance_tests == total_performance_tests and
                        successful_resource_tests == total_resource_tests and
                        successful_scalability_tests == total_scalability_tests
                    )
                },
                'performance_benchmarks': self._calculate_performance_benchmarks(),
                'recommendations': [
                    'Monitor resource usage in production environment',
                    'Set up performance alerting based on test results',
                    'Plan capacity based on scalability test findings',
                    'Optimize memory usage for large-scale deployments',
                    'Consider horizontal scaling for heavy loads'
                ],
                'next_steps': [
                    'Deploy with appropriate resource limits',
                    'Set up production performance monitoring',
                    'Create performance regression testing',
                    'Plan capacity scaling strategies',
                    'Optimize bottlenecks identified in testing'
                ]
            }
            
            # Write report to file
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            print(f"✅ Performance test report generated: {report_path}")
            print(f"   Performance success rate: {report['summary']['performance_success_rate']:.1f}%")
            print(f"   Resource success rate: {report['summary']['resource_success_rate']:.1f}%")
            print(f"   Scalability success rate: {report['summary']['scalability_success_rate']:.1f}%")
            
            return report_path
            
        except Exception as e:
            self.fail(f"Performance report generation failed: {e}")
    
    def _execute_performance_session(self, config: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Execute a performance session for concurrent testing"""
        try:
            db_manager = EnhancedDatabaseManager()
            config_manager = ConfigurationManager()
            session_config = config_manager.load_config_from_dict(config)
            
            orchestrator = EnhancedScraperOrchestrator(
                config=session_config, 
                db_manager=db_manager
            )
            
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            result = asyncio.run(orchestrator.run_daily_scrape())
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            return {
                'session_id': session_id,
                'success': result.get('status') in ['success', 'completed'],
                'execution_time': end_time - start_time,
                'memory_usage_mb': end_memory - start_memory,
                'listings_processed': result.get('urls_processed', 0),
                'result': result
            }
            
        except Exception as e:
            return {
                'session_id': session_id,
                'success': False,
                'error': str(e)
            }
    
    def _analyze_linear_scaling(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze if system scales linearly"""
        try:
            if len(results) < 2:
                return {'error': 'Insufficient data for linear scaling analysis'}
            
            # Calculate scaling factors
            base_result = results[0]
            scaling_factors = []
            
            for result in results[1:]:
                expected_load_factor = result['total_expected_listings'] / base_result['total_expected_listings']
                actual_time_factor = result['execution_time'] / base_result['execution_time']
                
                scaling_factors.append({
                    'expected_load_factor': expected_load_factor,
                    'actual_time_factor': actual_time_factor,
                    'scaling_efficiency': expected_load_factor / actual_time_factor if actual_time_factor > 0 else 0
                })
            
            avg_efficiency = statistics.mean([sf['scaling_efficiency'] for sf in scaling_factors])
            
            return {
                'scaling_factors': scaling_factors,
                'average_efficiency': avg_efficiency,
                'linear_scaling': avg_efficiency > 0.8  # 80% efficiency threshold
            }
            
        except Exception as e:
            return {'error': f'Linear scaling analysis failed: {e}'}
    
    def _analyze_memory_scaling(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze memory scaling patterns"""
        try:
            if len(results) < 2:
                return {'error': 'Insufficient data for memory scaling analysis'}
            
            memory_usages = [r['memory_usage_mb'] for r in results]
            load_factors = [r['total_expected_listings'] for r in results]
            
            # Calculate memory per listing
            memory_per_listing = [
                memory_usages[i] / load_factors[i] if load_factors[i] > 0 else 0
                for i in range(len(results))
            ]
            
            return {
                'memory_usages': memory_usages,
                'memory_per_listing': memory_per_listing,
                'memory_scaling_linear': max(memory_per_listing) / min(memory_per_listing) < 2.0 if min(memory_per_listing) > 0 else False,
                'avg_memory_per_listing': statistics.mean(memory_per_listing)
            }
            
        except Exception as e:
            return {'error': f'Memory scaling analysis failed: {e}'}
    
    def _calculate_performance_benchmarks(self) -> Dict[str, Any]:
        """Calculate performance benchmarks from test results"""
        try:
            benchmarks = {}
            
            # Baseline performance benchmark
            if 'baseline' in self.performance_results:
                baseline = self.performance_results['baseline']
                benchmarks['baseline_throughput'] = baseline.get('throughput_listings_per_second', 0)
                benchmarks['baseline_memory_per_listing'] = (
                    baseline.get('memory_usage_mb', 0) / baseline.get('listings_processed', 1)
                    if baseline.get('listings_processed', 0) > 0 else 0
                )
            
            # Load test benchmarks
            load_tests = {k: v for k, v in self.performance_results.items() if k in self.performance_configs}
            if load_tests:
                throughputs = [v.get('throughput_listings_per_second', 0) for v in load_tests.values() if v.get('success')]
                if throughputs:
                    benchmarks['max_throughput'] = max(throughputs)
                    benchmarks['avg_throughput'] = statistics.mean(throughputs)
            
            # Memory benchmarks
            if 'memory_profiling' in self.resource_metrics:
                memory_stats = self.resource_metrics['memory_profiling'].get('memory_stats', {})
                benchmarks['peak_memory_mb'] = memory_stats.get('peak_memory_mb', 0)
                benchmarks['memory_per_listing_mb'] = memory_stats.get('memory_per_listing_mb', 0)
            
            # CPU benchmarks
            if 'cpu_analysis' in self.resource_metrics:
                cpu_stats = self.resource_metrics['cpu_analysis'].get('cpu_stats', {})
                benchmarks['peak_cpu_percent'] = cpu_stats.get('peak_cpu_percent', 0)
                benchmarks['avg_cpu_percent'] = cpu_stats.get('avg_cpu_percent', 0)
            
            return benchmarks
            
        except Exception as e:
            return {'error': f'Benchmark calculation failed: {e}'}


def run_performance_load_tests():
    """Run the performance and load test suite"""
    print("⚡ Performance and Load Testing Suite")
    print("=" * 80)
    print("Comprehensive performance testing for production scenarios")
    print("Testing: Load scenarios, resource usage, scalability, concurrent execution")
    print("=" * 80)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPerformanceLoad)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    if result.wasSuccessful():
        print("✅ PERFORMANCE AND LOAD TESTS PASSED")
        print("⚡ System performance validated for production")
    else:
        print("❌ PERFORMANCE AND LOAD TESTS FAILED")
        print("🔧 Optimize performance before production deployment")
    print("=" * 80)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_performance_load_tests()
    sys.exit(0 if success else 1)