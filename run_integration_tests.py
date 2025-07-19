#!/usr/bin/env python3
"""
Integration Test Runner Script

Simple script to run the comprehensive integration test suite for the daily scraper automation system.
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Run integration tests"""
    print("🧪 Running Integration Test Suite for Daily Scraper Automation")
    print("=" * 70)
    
    # Change to tests/integration directory
    test_dir = Path("tests/integration")
    
    if not test_dir.exists():
        print("❌ Integration test directory not found!")
        return False
    
    try:
        # Run the comprehensive integration test suite
        result = subprocess.run([
            sys.executable, 
            str(test_dir / "run_integration_test_suite.py"),
            "--mode", "quick"  # Run quick validation by default
        ], cwd=".", capture_output=False)
        
        success = result.returncode == 0
        
        if success:
            print("\n✅ Integration tests completed successfully!")
        else:
            print("\n❌ Integration tests failed!")
        
        return success
        
    except Exception as e:
        print(f"❌ Error running integration tests: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)