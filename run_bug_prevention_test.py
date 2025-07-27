#!/usr/bin/env python3
"""
Quick Bug Prevention Test Runner

This script runs the multi-city bug prevention test to validate system readiness
before executing expensive integration operations.

Usage:
    python run_bug_prevention_test.py
    uv run python run_bug_prevention_test.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from tests.integration.multi_city_bug_prevention_test import MultiCityBugPreventionTest


def main():
    """Run bug prevention test"""
    print("🛡️ Running Multi-City Bug Prevention Test...")
    print("This test validates system readiness before expensive operations.")
    print()
    
    try:
        # Run bug prevention tests
        tester = MultiCityBugPreventionTest()
        report = tester.run_comprehensive_bug_prevention()
        
        # Print final recommendation
        if report['summary']['safe_to_proceed']:
            print("\n✅ RECOMMENDATION: Safe to proceed with expensive operations")
            print("   System validation passed all critical checks")
        else:
            print("\n❌ RECOMMENDATION: DO NOT proceed with expensive operations")
            print("   Critical issues must be resolved first")
            print(f"   Found {report['summary']['critical_issues_count']} critical issues")
        
        # Exit with appropriate code
        success = report['summary']['safe_to_proceed']
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Bug prevention test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Bug prevention test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()