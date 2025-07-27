#!/usr/bin/env python3
"""
Comprehensive Integration Test Runner

This module orchestrates all integration tests for the multi-city automation system,
providing a unified entry point for running end-to-end, performance, chaos engineering,
deployment, and multi-city specific integration tests.

Requirements: 5.1, 5.2, 5.3, 5.5
"""

import sys
import unittest
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import concurrent.futures
import psutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import test modules
from test_multi_city_integration_suite import run_multi_city_integration_tests
from test_end_to_end_workflows import TestEndToEndWorkflows
from test_performance_load import TestPerformanceLoad
from test_chaos_engineering import TestChaosEngineering
from test_deployment_rollback import TestDeploymentRollback


class ComprehensiveIntegrationTestRunner:
    """Comprehensive integration test runner for multi-city automation system"""
    
    def __init__(self):
        self.start_time = time.time()
        self.output_dir = Path("output/validation/comprehensive_integration")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Define test suites with priorities and dependencies
        self.test_suites = {
            'multi_city_integration': {
                'name': 'Multi-City Integration Tests',
                'runner': self._run_multi_city_integration,
                'description': 'Comprehensive multi-city workflow and integration testing',
                'priority': 1,
                'estimated_time': 900,  # 15 minutes
                'critical': True,
                'dependencies': []
            },
            'end_to_end_workflows': {
                'name': 'End-to-End Workflow Tests',
                'runner': self._run_end_to_end_workflows,
                'description': 'Complete user journey and workflow validation',
                'priority': 2,
                'estimated_time': 600,  # 10 minutes
                'critical': True,
                'dependencies': []
            },
            'performance_load': {
                'name': 'Performance and Load Tests',
                'runner': self._run_performance_load,
                'description': 'Performance testing for production scenarios',
                'priority': 3,
                'estimated_time': 1200,  # 20 minutes
                'critical': False,
                'dependencies': ['multi_city_integration']
            },
            'chaos_engineering': {
                'name': 'Chaos Engineering Tests',
                'runner': self._run_chaos_engineering,
                'description': 'System resilience under failure scenarios',
                'priority': 4,
                'estimated_time': 600,  # 10 minutes
                'critical': False,
                'dependencies': ['multi_city_integration']
            },
            'deployment_rollback': {
                'name': 'Deployment and Rollback Tests',
                'runner': self._run_deployment_rollback,
                'description': 'Automated deployment and rollback validation',
                'priority': 5,
                'estimated_time': 480,  # 8 minutes
                'critical': False,
                'dependencies': []
            }
        }
        
        self.results = {}
        self.execution_times = {}
        self.system_metrics = {}
        
    def run_comprehensive_test_suite(self, 
                                   selected_suites: Optional[List[str]] = None,
                                   skip_non_critical: bool = False,
                                   parallel_execution: bool = False) -> Dict[str, Any]:
        """Run comprehensive integration test suite"""
        print("🧪 Comprehensive Multi-City Integration Test Suite")
        print("=" * 90)
        print("Running complete integration testing for multi-city automation system")
        
        # Determine which suites to run
        suites_to_run = self._determine_suites_to_run(selected_suites, skip_non_critical)
        
        # Validate dependencies
        suites_to_run = self._resolve_dependencies(suites_to_run)
        
        # Calculate estimated total time
        total_estimated_time = sum(
            self.test_suites[suite]['estimated_time'] 
            for suite in suites_to_run
        )
        
        print(f"Test suites to run: {len(suites_to_run)}")
        print(f"Estimated total time: {total_estimated_time // 60}m {total_estimated_time % 60}s")
        print(f"Parallel execution: {'Enabled' if parallel_execution else 'Disabled'}")
        print("=" * 90)
        
        # Start system monitoring
        self._start_system_monitoring()
        
        # Execute test suites
        if parallel_execution:
            self._run_suites_parallel(suites_to_run)
        else:
            self._run_suites_sequential(suites_to_run)
        
        # Stop system monitoring
        self._stop_system_monitoring()
        
        # Generate comprehensive report
        total_execution_time = time.time() - self.start_time
        report = self._generate_comprehensive_report(total_execution_time)
        
        # Print final summary
        self._print_final_summary(report)
        
        return report
    
    def run_critical_tests_only(self) -> Dict[str, Any]:
        """Run only critical integration tests for quick validation"""
        print("⚡ Critical Integration Tests")
        print("=" * 60)
        print("Running essential integration tests for quick validation")
        print("=" * 60)
        
        return self.run_comprehensive_test_suite(skip_non_critical=True)
    
    def run_production_readiness_check(self) -> Dict[str, Any]:
        """Run complete production readiness check"""
        print("🚀 Production Readiness Check")
        print("=" * 80)
        print("Running comprehensive testing to validate production readiness")
        print("This includes all integration, performance, chaos, and deployment tests")
        print("=" * 80)
        
        return self.run_comprehensive_test_suite()
    
    def run_performance_focused_suite(self) -> Dict[str, Any]:
        """Run performance-focused test suite"""
        print("⚡ Performance-Focused Test Suite")
        print("=" * 70)
        print("Running performance and load testing with supporting integration tests")
        print("=" * 70)
        
        performance_suites = ['multi_city_integration', 'performance_load', 'chaos_engineering']
        return self.run_comprehensive_test_suite(selected_suites=performance_suites)
    
    def run_deployment_focused_suite(self) -> Dict[str, Any]:
        """Run deployment-focused test suite"""
        print("🚀 Deployment-Focused Test Suite")
        print("=" * 70)
        print("Running deployment and rollback testing with supporting integration tests")
        print("=" * 70)
        
        deployment_suites = ['multi_city_integration', 'deployment_rollback']
        return self.run_comprehensive_test_suite(selected_suites=deployment_suites)
    
    def _determine_suites_to_run(self, 
                                selected_suites: Optional[List[str]], 
                                skip_non_critical: bool) -> List[str]:
        """Determine which test suites to run"""
        if selected_suites:
            # Validate selected suites
            invalid_suites = [s for s in selected_suites if s not in self.test_suites]
            if invalid_suites:
                raise ValueError(f"Invalid test suites: {invalid_suites}")
            return selected_suites
        
        if skip_non_critical:
            return [name for name, info in self.test_suites.items() if info['critical']]
        
        return list(self.test_suites.keys())
    
    def _resolve_dependencies(self, suites_to_run: List[str]) -> List[str]:
        """Resolve dependencies and return ordered list of suites"""
        resolved_suites = []
        remaining_suites = suites_to_run.copy()
        
        while remaining_suites:
            # Find suites with no unresolved dependencies
            ready_suites = []
            for suite in remaining_suites:
                dependencies = self.test_suites[suite]['dependencies']
                if all(dep in resolved_suites or dep not in suites_to_run for dep in dependencies):
                    ready_suites.append(suite)
            
            if not ready_suites:
                # Circular dependency or missing dependency
                raise ValueError(f"Cannot resolve dependencies for suites: {remaining_suites}")
            
            # Sort ready suites by priority
            ready_suites.sort(key=lambda x: self.test_suites[x]['priority'])
            
            # Add to resolved list
            resolved_suites.extend(ready_suites)
            
            # Remove from remaining
            for suite in ready_suites:
                remaining_suites.remove(suite)
        
        return resolved_suites
    
    def _run_suites_sequential(self, suites_to_run: List[str]):
        """Run test suites sequentially"""
        for i, suite_name in enumerate(suites_to_run, 1):
            suite_info = self.test_suites[suite_name]
            
            print(f"\n[{i}/{len(suites_to_run)}] Running {suite_info['name']}...")
            print(f"Description: {suite_info['description']}")
            print(f"Estimated time: {suite_info['estimated_time'] // 60}m {suite_info['estimated_time'] % 60}s")
            print(f"Critical: {'Yes' if suite_info['critical'] else 'No'}")
            print("-" * 80)
            
            # Run the test suite
            suite_start_time = time.time()
            
            try:
                success = suite_info['runner']()
                suite_execution_time = time.time() - suite_start_time
                
                self.results[suite_name] = {
                    'success': success,
                    'execution_time': suite_execution_time,
                    'status': 'PASSED' if success else 'FAILED',
                    'critical': suite_info['critical']
                }
                
                status_icon = "✅" if success else "❌"
                print(f"\n{status_icon} {suite_info['name']}: {'PASSED' if success else 'FAILED'}")
                print(f"Execution time: {suite_execution_time:.1f}s")
                
            except Exception as e:
                suite_execution_time = time.time() - suite_start_time
                
                self.results[suite_name] = {
                    'success': False,
                    'execution_time': suite_execution_time,
                    'status': 'ERROR',
                    'error': str(e),
                    'critical': suite_info['critical']
                }
                
                print(f"\n❌ {suite_info['name']}: ERROR")
                print(f"Error: {e}")
                print(f"Execution time: {suite_execution_time:.1f}s")
                
                # Stop execution if critical test fails
                if suite_info['critical']:
                    print(f"\n⚠️ Critical test failed. Stopping execution.")
                    break
            
            print("-" * 80)
    
    def _run_suites_parallel(self, suites_to_run: List[str]):
        """Run test suites in parallel where possible"""
        print("\n🔀 Running test suites in parallel...")
        
        # Group suites by dependency level
        dependency_levels = self._group_by_dependency_level(suites_to_run)
        
        for level, suites in dependency_levels.items():
            if len(suites) == 1:
                # Single suite, run normally
                suite_name = suites[0]
                suite_info = self.test_suites[suite_name]
                
                print(f"\nRunning {suite_info['name']} (Level {level})...")
                
                suite_start_time = time.time()
                try:
                    success = suite_info['runner']()
                    suite_execution_time = time.time() - suite_start_time
                    
                    self.results[suite_name] = {
                        'success': success,
                        'execution_time': suite_execution_time,
                        'status': 'PASSED' if success else 'FAILED',
                        'critical': suite_info['critical']
                    }
                    
                except Exception as e:
                    suite_execution_time = time.time() - suite_start_time
                    
                    self.results[suite_name] = {
                        'success': False,
                        'execution_time': suite_execution_time,
                        'status': 'ERROR',
                        'error': str(e),
                        'critical': suite_info['critical']
                    }
            
            else:
                # Multiple suites, run in parallel
                print(f"\nRunning {len(suites)} suites in parallel (Level {level})...")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(suites)) as executor:
                    # Submit all suites
                    future_to_suite = {}
                    suite_start_times = {}
                    
                    for suite_name in suites:
                        suite_info = self.test_suites[suite_name]
                        suite_start_times[suite_name] = time.time()
                        future = executor.submit(suite_info['runner'])
                        future_to_suite[future] = suite_name
                    
                    # Collect results
                    for future in concurrent.futures.as_completed(future_to_suite):
                        suite_name = future_to_suite[future]
                        suite_info = self.test_suites[suite_name]
                        suite_execution_time = time.time() - suite_start_times[suite_name]
                        
                        try:
                            success = future.result()
                            
                            self.results[suite_name] = {
                                'success': success,
                                'execution_time': suite_execution_time,
                                'status': 'PASSED' if success else 'FAILED',
                                'critical': suite_info['critical']
                            }
                            
                        except Exception as e:
                            self.results[suite_name] = {
                                'success': False,
                                'execution_time': suite_execution_time,
                                'status': 'ERROR',
                                'error': str(e),
                                'critical': suite_info['critical']
                            }
            
            # Check if any critical tests failed
            critical_failures = [
                name for name, result in self.results.items() 
                if not result['success'] and result.get('critical', False)
            ]
            
            if critical_failures:
                print(f"\n⚠️ Critical test(s) failed: {', '.join(critical_failures)}. Stopping execution.")
                break
    
    def _group_by_dependency_level(self, suites_to_run: List[str]) -> Dict[int, List[str]]:
        """Group suites by dependency level for parallel execution"""
        levels = {}
        suite_levels = {}
        
        def get_level(suite_name):
            if suite_name in suite_levels:
                return suite_levels[suite_name]
            
            dependencies = self.test_suites[suite_name]['dependencies']
            if not dependencies:
                level = 0
            else:
                level = max(get_level(dep) for dep in dependencies if dep in suites_to_run) + 1
            
            suite_levels[suite_name] = level
            return level
        
        # Calculate levels for all suites
        for suite in suites_to_run:
            level = get_level(suite)
            if level not in levels:
                levels[level] = []
            levels[level].append(suite)
        
        return levels
    
    def _start_system_monitoring(self):
        """Start system resource monitoring"""
        self.system_metrics['start_time'] = time.time()
        self.system_metrics['start_memory'] = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        self.system_metrics['start_cpu'] = psutil.cpu_percent()
        
        # Start continuous monitoring
        self.system_metrics['samples'] = []
        self._monitoring_active = True
        
        import threading
        def monitor():
            while self._monitoring_active:
                sample = {
                    'timestamp': time.time(),
                    'memory_mb': psutil.Process().memory_info().rss / 1024 / 1024,
                    'cpu_percent': psutil.cpu_percent(),
                    'disk_usage': psutil.disk_usage('.').percent
                }
                self.system_metrics['samples'].append(sample)
                time.sleep(5)  # Sample every 5 seconds
        
        self._monitor_thread = threading.Thread(target=monitor)
        self._monitor_thread.start()
    
    def _stop_system_monitoring(self):
        """Stop system resource monitoring"""
        self._monitoring_active = False
        if hasattr(self, '_monitor_thread'):
            self._monitor_thread.join()
        
        self.system_metrics['end_time'] = time.time()
        self.system_metrics['end_memory'] = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        self.system_metrics['end_cpu'] = psutil.cpu_percent()
        
        # Calculate summary metrics
        if self.system_metrics['samples']:
            memory_values = [s['memory_mb'] for s in self.system_metrics['samples']]
            cpu_values = [s['cpu_percent'] for s in self.system_metrics['samples']]
            
            self.system_metrics['peak_memory_mb'] = max(memory_values)
            self.system_metrics['avg_memory_mb'] = sum(memory_values) / len(memory_values)
            self.system_metrics['peak_cpu_percent'] = max(cpu_values)
            self.system_metrics['avg_cpu_percent'] = sum(cpu_values) / len(cpu_values)
    
    def _run_multi_city_integration(self) -> bool:
        """Run multi-city integration tests"""
        try:
            return run_multi_city_integration_tests()
        except Exception as e:
            print(f"Multi-city integration tests failed: {e}")
            return False
    
    def _run_end_to_end_workflows(self) -> bool:
        """Run end-to-end workflow tests"""
        try:
            suite = unittest.TestLoader().loadTestsFromTestCase(TestEndToEndWorkflows)
            runner = unittest.TextTestRunner(verbosity=1, stream=open('/dev/null', 'w'))
            result = runner.run(suite)
            return result.wasSuccessful()
        except Exception as e:
            print(f"End-to-end workflow tests failed: {e}")
            return False
    
    def _run_performance_load(self) -> bool:
        """Run performance and load tests"""
        try:
            suite = unittest.TestLoader().loadTestsFromTestCase(TestPerformanceLoad)
            runner = unittest.TextTestRunner(verbosity=1, stream=open('/dev/null', 'w'))
            result = runner.run(suite)
            return result.wasSuccessful()
        except Exception as e:
            print(f"Performance and load tests failed: {e}")
            return False
    
    def _run_chaos_engineering(self) -> bool:
        """Run chaos engineering tests"""
        try:
            suite = unittest.TestLoader().loadTestsFromTestCase(TestChaosEngineering)
            runner = unittest.TextTestRunner(verbosity=1, stream=open('/dev/null', 'w'))
            result = runner.run(suite)
            return result.wasSuccessful()
        except Exception as e:
            print(f"Chaos engineering tests failed: {e}")
            return False
    
    def _run_deployment_rollback(self) -> bool:
        """Run deployment and rollback tests"""
        try:
            suite = unittest.TestLoader().loadTestsFromTestCase(TestDeploymentRollback)
            runner = unittest.TextTestRunner(verbosity=1, stream=open('/dev/null', 'w'))
            result = runner.run(suite)
            return result.wasSuccessful()
        except Exception as e:
            print(f"Deployment and rollback tests failed: {e}")
            return False
    
    def _generate_comprehensive_report(self, total_execution_time: float) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Calculate overall metrics
        total_suites = len(self.results)
        successful_suites = sum(1 for r in self.results.values() if r['success'])
        failed_suites = total_suites - successful_suites
        
        critical_suites = sum(1 for r in self.results.values() if r.get('critical', False))
        successful_critical = sum(1 for r in self.results.values() if r['success'] and r.get('critical', False))
        
        success_rate = (successful_suites / total_suites * 100) if total_suites > 0 else 0
        critical_success_rate = (successful_critical / critical_suites * 100) if critical_suites > 0 else 0
        
        # Categorize results
        passed_suites = [name for name, result in self.results.items() if result['success']]
        failed_suites_list = [name for name, result in self.results.items() if not result['success']]
        critical_failed = [name for name, result in self.results.items() if not result['success'] and result.get('critical', False)]
        
        # Generate report
        report = {
            'test_info': {
                'test_name': 'Comprehensive Multi-City Integration Test Suite',
                'timestamp': timestamp,
                'total_execution_time': total_execution_time,
                'suites_executed': list(self.results.keys()),
                'system_info': {
                    'python_version': sys.version,
                    'platform': sys.platform,
                    'cpu_count': psutil.cpu_count(),
                    'total_memory_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024
                }
            },
            'results': self.results,
            'system_metrics': self.system_metrics,
            'summary': {
                'total_suites': total_suites,
                'successful_suites': successful_suites,
                'failed_suites': failed_suites,
                'success_rate_percent': success_rate,
                'critical_suites': critical_suites,
                'successful_critical': successful_critical,
                'critical_success_rate_percent': critical_success_rate,
                'all_tests_passed': success_rate == 100.0,
                'all_critical_passed': critical_success_rate == 100.0,
                'production_ready': self._assess_production_readiness()
            },
            'suite_breakdown': {
                'passed_suites': passed_suites,
                'failed_suites': failed_suites_list,
                'critical_failed': critical_failed,
                'execution_times': {
                    name: result['execution_time'] 
                    for name, result in self.results.items()
                }
            },
            'production_readiness_assessment': self._generate_production_readiness_assessment(),
            'multi_city_capabilities': self._assess_multi_city_capabilities(),
            'performance_analysis': self._analyze_performance_metrics(),
            'recommendations': self._generate_recommendations(),
            'next_steps': self._generate_next_steps()
        }
        
        # Save report to file
        report_path = self.output_dir / f"comprehensive_integration_report_{timestamp}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📋 Comprehensive report saved: {report_path}")
        
        return report
    
    def _assess_production_readiness(self) -> bool:
        """Assess overall production readiness"""
        # All critical tests must pass
        critical_passed = all(
            result['success'] for result in self.results.values() 
            if result.get('critical', False)
        )
        
        # Overall success rate should be high
        total_suites = len(self.results)
        successful_suites = sum(1 for r in self.results.values() if r['success'])
        success_rate = (successful_suites / total_suites) if total_suites > 0 else 0
        
        return critical_passed and success_rate >= 0.8
    
    def _generate_production_readiness_assessment(self) -> Dict[str, Any]:
        """Generate detailed production readiness assessment"""
        assessment = {}
        
        for suite_name, result in self.results.items():
            suite_info = self.test_suites[suite_name]
            assessment[f"{suite_name}_ready"] = result['success']
        
        # Calculate readiness score
        total_criteria = len(assessment)
        met_criteria = sum(1 for met in assessment.values() if met)
        readiness_score = (met_criteria / total_criteria * 100) if total_criteria > 0 else 0
        
        assessment['readiness_score'] = readiness_score
        assessment['production_ready'] = readiness_score >= 80.0
        
        return assessment
    
    def _assess_multi_city_capabilities(self) -> Dict[str, Any]:
        """Assess multi-city specific capabilities"""
        multi_city_result = self.results.get('multi_city_integration', {})
        
        return {
            'multi_city_workflow_validated': multi_city_result.get('success', False),
            'helsinki_espoo_support': multi_city_result.get('success', False),
            'concurrent_city_processing': self.results.get('performance_load', {}).get('success', False),
            'multi_city_resilience': self.results.get('chaos_engineering', {}).get('success', False),
            'multi_city_deployment': self.results.get('deployment_rollback', {}).get('success', False),
            'overall_multi_city_ready': (
                multi_city_result.get('success', False) and
                sum(1 for r in self.results.values() if r['success']) >= len(self.results) * 0.8
            )
        }
    
    def _analyze_performance_metrics(self) -> Dict[str, Any]:
        """Analyze performance metrics from system monitoring"""
        if not self.system_metrics.get('samples'):
            return {'error': 'No performance data collected'}
        
        return {
            'total_execution_time': self.system_metrics.get('end_time', 0) - self.system_metrics.get('start_time', 0),
            'peak_memory_usage_mb': self.system_metrics.get('peak_memory_mb', 0),
            'average_memory_usage_mb': self.system_metrics.get('avg_memory_mb', 0),
            'peak_cpu_usage_percent': self.system_metrics.get('peak_cpu_percent', 0),
            'average_cpu_usage_percent': self.system_metrics.get('avg_cpu_percent', 0),
            'memory_efficient': self.system_metrics.get('peak_memory_mb', 0) < 2048,  # Less than 2GB
            'cpu_efficient': self.system_metrics.get('avg_cpu_percent', 0) < 80,  # Less than 80% average
            'performance_acceptable': (
                self.system_metrics.get('peak_memory_mb', 0) < 2048 and
                self.system_metrics.get('avg_cpu_percent', 0) < 80
            )
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check critical test failures
        critical_failures = [
            name for name, result in self.results.items() 
            if not result['success'] and result.get('critical', False)
        ]
        
        if critical_failures:
            recommendations.append(f"URGENT: Fix critical test failures: {', '.join(critical_failures)}")
        
        # Check multi-city specific issues
        if not self.results.get('multi_city_integration', {}).get('success', False):
            recommendations.append("Fix multi-city integration issues before production deployment")
        
        # Check performance issues
        if not self.results.get('performance_load', {}).get('success', True):
            recommendations.append("Optimize performance issues identified in load testing")
        
        # Check resilience issues
        if not self.results.get('chaos_engineering', {}).get('success', True):
            recommendations.append("Improve system resilience based on chaos engineering findings")
        
        # Check deployment issues
        if not self.results.get('deployment_rollback', {}).get('success', True):
            recommendations.append("Fix deployment and rollback procedures")
        
        # General recommendations
        if self._assess_production_readiness():
            recommendations.extend([
                "System appears ready for multi-city production deployment",
                "Set up comprehensive monitoring for both Helsinki and Espoo",
                "Create multi-city operational procedures and runbooks",
                "Plan gradual rollout strategy for both cities"
            ])
        else:
            recommendations.extend([
                "System not ready for production - address failed tests first",
                "Focus on critical multi-city integration issues",
                "Re-run comprehensive test suite after fixes"
            ])
        
        return recommendations
    
    def _generate_next_steps(self) -> List[str]:
        """Generate next steps based on test results"""
        next_steps = []
        
        if self._assess_production_readiness():
            next_steps.extend([
                "Deploy multi-city system to staging environment",
                "Configure production monitoring and alerting for both cities",
                "Set up automated multi-city deployment pipeline",
                "Create incident response procedures for multi-city operations",
                "Train operations team on multi-city system management",
                "Plan production rollout strategy for Helsinki and Espoo"
            ])
        else:
            next_steps.extend([
                "Address all failed test scenarios, prioritizing critical tests",
                "Re-run comprehensive integration test suite after fixes",
                "Focus on multi-city workflow and integration issues first",
                "Consider system architecture improvements",
                "Validate individual city functionality before multi-city testing"
            ])
        
        return next_steps
    
    def _print_final_summary(self, report: Dict[str, Any]):
        """Print final test summary"""
        print("\n" + "=" * 90)
        print("🧪 COMPREHENSIVE INTEGRATION TEST SUITE SUMMARY")
        print("=" * 90)
        
        summary = report['summary']
        
        print(f"Total execution time: {report['test_info']['total_execution_time']:.1f}s")
        print(f"Test suites executed: {summary['total_suites']}")
        print(f"Successful suites: {summary['successful_suites']}")
        print(f"Failed suites: {summary['failed_suites']}")
        print(f"Overall success rate: {summary['success_rate_percent']:.1f}%")
        print(f"Critical success rate: {summary['critical_success_rate_percent']:.1f}%")
        
        print("\nSuite Results:")
        for suite_name, result in self.results.items():
            status_icon = "✅" if result['success'] else "❌"
            critical_marker = " (CRITICAL)" if result.get('critical', False) else ""
            print(f"  {status_icon} {self.test_suites[suite_name]['name']}: {result['status']} ({result['execution_time']:.1f}s){critical_marker}")
        
        # Performance summary
        perf_analysis = report.get('performance_analysis', {})
        if 'error' not in perf_analysis:
            print(f"\nPerformance Summary:")
            print(f"  Peak memory usage: {perf_analysis.get('peak_memory_usage_mb', 0):.1f}MB")
            print(f"  Average CPU usage: {perf_analysis.get('average_cpu_usage_percent', 0):.1f}%")
            print(f"  Performance acceptable: {'Yes' if perf_analysis.get('performance_acceptable', False) else 'No'}")
        
        # Multi-city capabilities
        multi_city_caps = report.get('multi_city_capabilities', {})
        print(f"\nMulti-City Readiness: {'✅ READY' if multi_city_caps.get('overall_multi_city_ready', False) else '❌ NOT READY'}")
        
        print(f"\nProduction Readiness: {'✅ READY' if summary['production_ready'] else '❌ NOT READY'}")
        
        if summary['all_tests_passed']:
            print("\n🎉 ALL INTEGRATION TESTS PASSED!")
            print("🚀 Multi-city system validated for production deployment")
        elif summary['all_critical_passed']:
            print("\n✅ ALL CRITICAL TESTS PASSED!")
            print("🔧 Address non-critical issues for optimal production deployment")
        else:
            print("\n⚠️ CRITICAL INTEGRATION TESTS FAILED")
            print("🔧 Address critical issues before production deployment")
        
        print("=" * 90)


def main():
    """Main entry point for comprehensive integration test suite"""
    parser = argparse.ArgumentParser(description='Run comprehensive integration test suite for multi-city automation')
    
    parser.add_argument(
        '--mode',
        choices=['all', 'critical', 'production', 'performance', 'deployment'],
        default='all',
        help='Test mode to run (default: all)'
    )
    
    parser.add_argument(
        '--suites',
        nargs='+',
        choices=['multi_city_integration', 'end_to_end_workflows', 'performance_load', 'chaos_engineering', 'deployment_rollback'],
        help='Specific test suites to run'
    )
    
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Enable parallel execution of compatible test suites'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory for test reports'
    )
    
    args = parser.parse_args()
    
    # Initialize test runner
    runner = ComprehensiveIntegrationTestRunner()
    
    if args.output_dir:
        runner.output_dir = Path(args.output_dir)
        runner.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run tests based on mode
    try:
        if args.suites:
            # Run specific suites
            report = runner.run_comprehensive_test_suite(
                selected_suites=args.suites,
                parallel_execution=args.parallel
            )
        elif args.mode == 'critical':
            report = runner.run_critical_tests_only()
        elif args.mode == 'production':
            report = runner.run_production_readiness_check()
        elif args.mode == 'performance':
            report = runner.run_performance_focused_suite()
        elif args.mode == 'deployment':
            report = runner.run_deployment_focused_suite()
        else:
            report = runner.run_comprehensive_test_suite(parallel_execution=args.parallel)
        
        # Exit with appropriate code
        success = report['summary']['production_ready']
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()