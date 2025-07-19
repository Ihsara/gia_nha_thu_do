#!/usr/bin/env python3
"""
Comprehensive Integration Test Suite Runner

This module orchestrates all integration tests for the daily scraper automation system,
providing a unified entry point for running all integration, end-to-end, performance,
chaos engineering, and deployment tests.

Requirements: 5.1, 5.2, 5.3
"""

import sys
import unittest
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import subprocess

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import all integration test modules
from test_automation_integration import run_integration_test_suite
from test_end_to_end_workflows import run_e2e_workflow_tests
from test_performance_load import run_performance_load_tests
from test_chaos_engineering import run_chaos_engineering_tests
from test_deployment_rollback import run_deployment_rollback_tests


class IntegrationTestSuiteRunner:
    """Comprehensive integration test suite runner"""
    
    def __init__(self):
        self.start_time = time.time()
        self.output_dir = Path("output/validation/integration_suite")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.test_suites = {
            'integration': {
                'name': 'Automation Integration Tests',
                'runner': run_integration_test_suite,
                'description': 'Core integration testing for all deployment scenarios',
                'priority': 1,
                'estimated_time': 300  # 5 minutes
            },
            'e2e_workflows': {
                'name': 'End-to-End Workflow Tests',
                'runner': run_e2e_workflow_tests,
                'description': 'Complete user journey and workflow validation',
                'priority': 2,
                'estimated_time': 600  # 10 minutes
            },
            'performance': {
                'name': 'Performance and Load Tests',
                'runner': run_performance_load_tests,
                'description': 'Performance testing for production scenarios',
                'priority': 3,
                'estimated_time': 900  # 15 minutes
            },
            'chaos': {
                'name': 'Chaos Engineering Tests',
                'runner': run_chaos_engineering_tests,
                'description': 'System resilience under failure scenarios',
                'priority': 4,
                'estimated_time': 450  # 7.5 minutes
            },
            'deployment': {
                'name': 'Deployment and Rollback Tests',
                'runner': run_deployment_rollback_tests,
                'description': 'Automated deployment and rollback validation',
                'priority': 5,
                'estimated_time': 360  # 6 minutes
            }
        }
        
        self.results = {}
        self.execution_times = {}
        
    def run_all_tests(self, selected_suites: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run all integration test suites"""
        print("🧪 Comprehensive Integration Test Suite")
        print("=" * 80)
        print("Running complete integration testing for daily scraper automation system")
        
        # Determine which suites to run
        suites_to_run = selected_suites if selected_suites else list(self.test_suites.keys())
        
        # Sort by priority
        suites_to_run.sort(key=lambda x: self.test_suites[x]['priority'])
        
        # Calculate estimated total time
        total_estimated_time = sum(
            self.test_suites[suite]['estimated_time'] 
            for suite in suites_to_run
        )
        
        print(f"Test suites to run: {len(suites_to_run)}")
        print(f"Estimated total time: {total_estimated_time // 60}m {total_estimated_time % 60}s")
        print("=" * 80)
        
        # Run each test suite
        for i, suite_name in enumerate(suites_to_run, 1):
            suite_info = self.test_suites[suite_name]
            
            print(f"\n[{i}/{len(suites_to_run)}] Running {suite_info['name']}...")
            print(f"Description: {suite_info['description']}")
            print(f"Estimated time: {suite_info['estimated_time'] // 60}m {suite_info['estimated_time'] % 60}s")
            print("-" * 60)
            
            # Run the test suite
            suite_start_time = time.time()
            
            try:
                success = suite_info['runner']()
                suite_execution_time = time.time() - suite_start_time
                
                self.results[suite_name] = {
                    'success': success,
                    'execution_time': suite_execution_time,
                    'status': 'PASSED' if success else 'FAILED'
                }
                
                print(f"\n{suite_info['name']}: {'✅ PASSED' if success else '❌ FAILED'}")
                print(f"Execution time: {suite_execution_time:.1f}s")
                
            except Exception as e:
                suite_execution_time = time.time() - suite_start_time
                
                self.results[suite_name] = {
                    'success': False,
                    'execution_time': suite_execution_time,
                    'status': 'ERROR',
                    'error': str(e)
                }
                
                print(f"\n{suite_info['name']}: ❌ ERROR")
                print(f"Error: {e}")
                print(f"Execution time: {suite_execution_time:.1f}s")
            
            print("-" * 60)
        
        # Generate comprehensive report
        total_execution_time = time.time() - self.start_time
        report = self._generate_comprehensive_report(total_execution_time)
        
        # Print final summary
        self._print_final_summary(report)
        
        return report
    
    def run_quick_validation(self) -> Dict[str, Any]:
        """Run quick validation tests (subset of full suite)"""
        print("⚡ Quick Integration Validation")
        print("=" * 60)
        print("Running essential integration tests for quick validation")
        print("=" * 60)
        
        # Quick validation includes core integration and basic e2e tests
        quick_suites = ['integration', 'e2e_workflows']
        
        return self.run_all_tests(selected_suites=quick_suites)
    
    def run_production_readiness_check(self) -> Dict[str, Any]:
        """Run production readiness check (all tests)"""
        print("🚀 Production Readiness Check")
        print("=" * 80)
        print("Running comprehensive testing to validate production readiness")
        print("This includes all integration, performance, chaos, and deployment tests")
        print("=" * 80)
        
        return self.run_all_tests()
    
    def run_performance_focused_tests(self) -> Dict[str, Any]:
        """Run performance-focused test suite"""
        print("⚡ Performance-Focused Test Suite")
        print("=" * 70)
        print("Running performance and load testing with basic integration")
        print("=" * 70)
        
        performance_suites = ['integration', 'performance', 'chaos']
        
        return self.run_all_tests(selected_suites=performance_suites)
    
    def run_deployment_focused_tests(self) -> Dict[str, Any]:
        """Run deployment-focused test suite"""
        print("🚀 Deployment-Focused Test Suite")
        print("=" * 70)
        print("Running deployment and rollback testing with basic integration")
        print("=" * 70)
        
        deployment_suites = ['integration', 'deployment']
        
        return self.run_all_tests(selected_suites=deployment_suites)
    
    def _generate_comprehensive_report(self, total_execution_time: float) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Calculate overall metrics
        total_suites = len(self.results)
        successful_suites = sum(1 for r in self.results.values() if r['success'])
        failed_suites = total_suites - successful_suites
        
        success_rate = (successful_suites / total_suites * 100) if total_suites > 0 else 0
        
        # Categorize results
        passed_suites = [name for name, result in self.results.items() if result['success']]
        failed_suites_list = [name for name, result in self.results.items() if not result['success']]
        
        # Generate report
        report = {
            'test_info': {
                'test_name': 'Comprehensive Integration Test Suite',
                'timestamp': timestamp,
                'total_execution_time': total_execution_time,
                'suites_executed': list(self.results.keys())
            },
            'results': self.results,
            'summary': {
                'total_suites': total_suites,
                'successful_suites': successful_suites,
                'failed_suites': failed_suites,
                'success_rate_percent': success_rate,
                'all_tests_passed': success_rate == 100.0,
                'production_ready': self._assess_production_readiness()
            },
            'suite_breakdown': {
                'passed_suites': passed_suites,
                'failed_suites': failed_suites_list,
                'execution_times': {
                    name: result['execution_time'] 
                    for name, result in self.results.items()
                }
            },
            'production_readiness_assessment': self._generate_production_readiness_assessment(),
            'recommendations': self._generate_recommendations(),
            'next_steps': self._generate_next_steps()
        }
        
        # Save report to file
        report_path = self.output_dir / f"integration_test_suite_report_{timestamp}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📋 Comprehensive report saved: {report_path}")
        
        return report
    
    def _assess_production_readiness(self) -> bool:
        """Assess overall production readiness"""
        # Critical suites that must pass for production readiness
        critical_suites = ['integration', 'e2e_workflows']
        
        # Check if all critical suites passed
        critical_passed = all(
            self.results.get(suite, {}).get('success', False) 
            for suite in critical_suites
        )
        
        # Check overall success rate
        total_suites = len(self.results)
        successful_suites = sum(1 for r in self.results.values() if r['success'])
        success_rate = (successful_suites / total_suites) if total_suites > 0 else 0
        
        # Production ready if critical tests pass and overall success rate > 80%
        return critical_passed and success_rate >= 0.8
    
    def _generate_production_readiness_assessment(self) -> Dict[str, Any]:
        """Generate detailed production readiness assessment"""
        assessment = {
            'core_functionality': self.results.get('integration', {}).get('success', False),
            'end_to_end_workflows': self.results.get('e2e_workflows', {}).get('success', False),
            'performance_acceptable': self.results.get('performance', {}).get('success', True),  # Optional
            'resilience_validated': self.results.get('chaos', {}).get('success', True),  # Optional
            'deployment_ready': self.results.get('deployment', {}).get('success', True)  # Optional
        }
        
        # Calculate readiness score
        total_criteria = len(assessment)
        met_criteria = sum(1 for met in assessment.values() if met)
        readiness_score = (met_criteria / total_criteria * 100) if total_criteria > 0 else 0
        
        assessment['readiness_score'] = readiness_score
        assessment['production_ready'] = readiness_score >= 80.0  # 80% threshold
        
        return assessment
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check each test suite and provide specific recommendations
        if not self.results.get('integration', {}).get('success', False):
            recommendations.append("Fix core integration issues before proceeding to production")
        
        if not self.results.get('e2e_workflows', {}).get('success', False):
            recommendations.append("Resolve end-to-end workflow issues for complete user journeys")
        
        if not self.results.get('performance', {}).get('success', True):
            recommendations.append("Optimize performance issues identified in load testing")
        
        if not self.results.get('chaos', {}).get('success', True):
            recommendations.append("Improve system resilience based on chaos engineering findings")
        
        if not self.results.get('deployment', {}).get('success', True):
            recommendations.append("Fix deployment and rollback procedures before production")
        
        # General recommendations
        if self._assess_production_readiness():
            recommendations.extend([
                "System appears ready for production deployment",
                "Set up comprehensive monitoring and alerting",
                "Create operational runbooks and procedures",
                "Plan capacity and scaling strategies"
            ])
        else:
            recommendations.extend([
                "System not ready for production - address failed tests",
                "Focus on critical integration and workflow issues first",
                "Re-run tests after fixes to validate improvements"
            ])
        
        return recommendations
    
    def _generate_next_steps(self) -> List[str]:
        """Generate next steps based on test results"""
        next_steps = []
        
        if self._assess_production_readiness():
            next_steps.extend([
                "Deploy to staging environment for final validation",
                "Configure production monitoring and alerting systems",
                "Set up automated deployment pipeline",
                "Create incident response procedures",
                "Train operations team on system management",
                "Plan production rollout strategy"
            ])
        else:
            next_steps.extend([
                "Address all failed test scenarios",
                "Re-run integration test suite after fixes",
                "Focus on core functionality and workflows first",
                "Consider additional testing for identified issues",
                "Review system architecture for improvements"
            ])
        
        return next_steps
    
    def _print_final_summary(self, report: Dict[str, Any]):
        """Print final test summary"""
        print("\n" + "=" * 80)
        print("🧪 INTEGRATION TEST SUITE SUMMARY")
        print("=" * 80)
        
        summary = report['summary']
        
        print(f"Total execution time: {report['test_info']['total_execution_time']:.1f}s")
        print(f"Test suites executed: {summary['total_suites']}")
        print(f"Successful suites: {summary['successful_suites']}")
        print(f"Failed suites: {summary['failed_suites']}")
        print(f"Success rate: {summary['success_rate_percent']:.1f}%")
        
        print("\nSuite Results:")
        for suite_name, result in self.results.items():
            status_icon = "✅" if result['success'] else "❌"
            print(f"  {status_icon} {self.test_suites[suite_name]['name']}: {result['status']} ({result['execution_time']:.1f}s)")
        
        print(f"\nProduction Readiness: {'✅ READY' if summary['production_ready'] else '❌ NOT READY'}")
        
        if summary['all_tests_passed']:
            print("\n🎉 ALL INTEGRATION TESTS PASSED!")
            print("🚀 System validated for production deployment")
        else:
            print("\n⚠️ SOME INTEGRATION TESTS FAILED")
            print("🔧 Address failed tests before production deployment")
        
        print("=" * 80)


def main():
    """Main entry point for integration test suite"""
    parser = argparse.ArgumentParser(description='Run integration test suite for daily scraper automation')
    
    parser.add_argument(
        '--mode',
        choices=['all', 'quick', 'production', 'performance', 'deployment'],
        default='all',
        help='Test mode to run (default: all)'
    )
    
    parser.add_argument(
        '--suites',
        nargs='+',
        choices=['integration', 'e2e_workflows', 'performance', 'chaos', 'deployment'],
        help='Specific test suites to run'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory for test reports'
    )
    
    args = parser.parse_args()
    
    # Initialize test runner
    runner = IntegrationTestSuiteRunner()
    
    if args.output_dir:
        runner.output_dir = Path(args.output_dir)
        runner.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run tests based on mode
    try:
        if args.suites:
            # Run specific suites
            report = runner.run_all_tests(selected_suites=args.suites)
        elif args.mode == 'quick':
            report = runner.run_quick_validation()
        elif args.mode == 'production':
            report = runner.run_production_readiness_check()
        elif args.mode == 'performance':
            report = runner.run_performance_focused_tests()
        elif args.mode == 'deployment':
            report = runner.run_deployment_focused_tests()
        else:
            report = runner.run_all_tests()
        
        # Exit with appropriate code
        success = report['summary']['all_tests_passed']
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()