#!/usr/bin/env python3
"""
Simple Espoo Validation Runner

Quick script to run Espoo validation tests individually or as a complete suite.
This provides an easy entry point for testing Espoo functionality.

Usage:
    python run_espoo_validation.py                    # Run complete suite
    python run_espoo_validation.py bug-prevention     # Run bug prevention only
    python run_espoo_validation.py step1              # Run Step 1 only
    python run_espoo_validation.py step2              # Run Step 2 only
    python run_espoo_validation.py step3              # Run Step 3 only
    python run_espoo_validation.py geospatial         # Run geospatial integration tests

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4
"""

import sys
import subprocess
from pathlib import Path


def run_test(test_name, module_path):
    """Run a specific test module"""
    print(f"\n🚀 Running {test_name}")
    print("=" * 60)
    
    try:
        cmd = [sys.executable, '-m', 'pytest', module_path, '-v']
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running {test_name}: {e}")
        return False


def run_complete_suite():
    """Run the complete validation suite"""
    print("🏙️ Espoo Progressive Validation Suite")
    print("=" * 80)
    
    try:
        cmd = [sys.executable, 'tests/validation/run_espoo_validation_suite.py']
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running complete suite: {e}")
        return False


def run_geospatial_integration():
    """Run the geospatial integration tests"""
    print("🏙️ Espoo Geospatial Integration Tests")
    print("=" * 80)
    print("Testing Espoo geospatial data integration")
    print("Requirements: 2.1, 2.2, 2.3, 2.4, 2.5")
    print("=" * 80)
    
    try:
        # First run the unit tests
        print("\n🧪 Running geospatial unit tests")
        cmd = [sys.executable, '-m', 'pytest', 'tests/test_espoo_geospatial_integration.py', '-v']
        result1 = subprocess.run(cmd, cwd=Path(__file__).parent)
        
        # Then run the integration script with a small sample
        print("\n🚀 Running geospatial integration script")
        cmd = [sys.executable, 'scripts/run_espoo_geospatial_integration.py', '--sample', '10']
        result2 = subprocess.run(cmd, cwd=Path(__file__).parent)
        
        return result1.returncode == 0 and result2.returncode == 0
    except Exception as e:
        print(f"❌ Error running geospatial integration tests: {e}")
        return False


def main():
    """Main function"""
    if len(sys.argv) > 1:
        test_arg = sys.argv[1].lower()
        
        test_mapping = {
            'bug-prevention': ('Bug Prevention Tests', 'tests/validation/test_espoo_bug_prevention.py'),
            'step1': ('Step 1: 10 Samples', 'tests/validation/test_espoo_step1_10_samples.py'),
            'step2': ('Step 2: 100 Samples', 'tests/validation/test_espoo_step2_100_samples.py'),
            'step3': ('Step 3: Full Scale', 'tests/validation/test_espoo_step3_full_scale.py'),
            'geospatial': ('Geospatial Integration', None),
        }
        
        if test_arg in test_mapping:
            test_name, module_path = test_mapping[test_arg]
            if test_arg == 'geospatial':
                success = run_geospatial_integration()
            else:
                success = run_test(test_name, module_path)
        else:
            print(f"❌ Unknown test: {test_arg}")
            print("Available tests: bug-prevention, step1, step2, step3, geospatial")
            return 1
    else:
        # Run complete suite
        success = run_complete_suite()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())