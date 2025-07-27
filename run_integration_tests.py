#!/usr/bin/env python3
"""
Integration Test Runner

This script provides a simple interface to run the comprehensive integration test suite
for the multi-city automation system.

Usage:
    python run_integration_tests.py [--mode MODE] [--parallel]
    uv run python run_integration_tests.py [--mode MODE] [--parallel]
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from tests.integration.comprehensive_integration_test_runner import ComprehensiveIntegrationTestRunner


def main():
    """Run integration tests with command line options"""
    parser = argparse.ArgumentParser(description='Run comprehensive integration tests for multi-city automation')
    
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
        '--bug-prevention',
        action='store_true',
        help='Run bug prevention test first'
    )
    
    args = parser.parse_args()
    
    print("🧪 Multi-City Integration Test Runner")
    print("=" * 60)
    
    try:
        # Run bug prevention test first if requested
        if args.bug_prevention:
            print("🛡️ Running bug prevention test first...")
            from tests.integration.multi_city_bug_prevention_test import MultiCityBugPreventionTest
            
            tester = MultiCityBugPreventionTest()
            bug_report = tester.run_comprehensive_bug_prevention()
            
            if not bug_report['summary']['safe_to_proceed']:
                print("\n❌ Bug prevention test failed - stopping execution")
                print("Fix critical issues before running integration tests")
                sys.exit(1)
            
            print("\n✅ Bug prevention test passed - proceeding with integration tests")
            print("=" * 60)
        
        # Initialize test runner
        runner = ComprehensiveIntegrationTestRunner()
        
        # Run tests based on arguments
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
        
        # Print final recommendation
        if report['summary']['production_ready']:
            print("\n✅ RECOMMENDATION: System ready for production deployment")
            print("   All critical tests passed successfully")
        else:
            print("\n❌ RECOMMENDATION: System NOT ready for production")
            print("   Address failed tests before deployment")
            if report['summary']['all_critical_passed']:
                print("   Critical tests passed - non-critical issues can be addressed later")
        
        # Exit with appropriate code
        success = report['summary']['production_ready']
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Integration test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Integration test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()