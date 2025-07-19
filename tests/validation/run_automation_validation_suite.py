#!/usr/bin/env python3
"""
Master Test Runner for Automation Progressive Validation Suite

Orchestrates the complete progressive validation test suite for the automation system:
1. Bug Prevention Tests (mandatory before expensive operations)
2. Step 1: 10 Listing Automation Test
3. Step 2: 100 Listing Scalability Test  
4. Step 3: Full Production Test
5. Deployment Mode Validation

Requirements: 5.1, 5.2
"""

import sys
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class AutomationValidationSuite:
    """Master orchestrator for automation validation tests"""
    
    def __init__(self):
        self.start_time = time.time()
        self.output_dir = Path("output/validation/automation")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test results tracking
        self.test_results = {}
        self.overall_success = True
        
        # Test configuration
        self.tests = [
            {
                'name': 'Bug Prevention',
                'script': 'test_automation_bug_prevention.py',
                'description': 'Comprehensive bug prevention tests for all components',
                'mandatory': True,
                'max_time_minutes': 10
            },
            {
                'name': 'Step 1 - 10 Listings',
                'script': 'test_automation_step1_10_listings.py', 
                'description': 'Basic automation test with 10 listings',
                'mandatory': True,
                'max_time_minutes': 5,
                'depends_on': ['Bug Prevention']
            },
            {
                'name': 'Step 2 - 100 Listings',
                'script': 'test_automation_step2_100_listings.py',
                'description': 'Scalability test with 100 listings and cluster coordination',
                'mandatory': True,
                'max_time_minutes': 30,
                'depends_on': ['Step 1 - 10 Listings']
            },
            {
                'name': 'Step 3 - Full Production',
                'script': 'test_automation_step3_full_production.py',
                'description': 'Complete production test with monitoring and alerting',
                'mandatory': True,
                'max_time_minutes': 60,
                'depends_on': ['Step 2 - 100 Listings']
            },
            {
                'name': 'Deployment Modes',
                'script': 'test_automation_deployment_modes.py',
                'description': 'Validation of all deployment modes (standalone, container, cluster)',
                'mandatory': False,
                'max_time_minutes': 15,
                'depends_on': ['Step 1 - 10 Listings']
            }
        ]
    
    def print_header(self):
        """Print test suite header"""
        print("🚀 AUTOMATION PROGRESSIVE VALIDATION SUITE")
        print("=" * 80)
        print("Comprehensive validation of the daily scraper automation system")
        print("Following progressive validation strategy: Bug Prevention → Step 1 → Step 2 → Step 3")
        print("=" * 80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Tests to run: {len(self.tests)}")
        print()
    
    def check_dependencies(self, test: Dict[str, Any]) -> bool:
        """Check if test dependencies are satisfied"""
        if 'depends_on' not in test:
            return True
        
        for dependency in test['depends_on']:
            if dependency not in self.test_results:
                print(f"⚠️ Dependency not run: {dependency}")
                return False
            
            if not self.test_results[dependency]['success']:
                print(f"❌ Dependency failed: {dependency}")
                return False
        
        return True
    
    def run_test(self, test: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Run a single test and return results"""
        test_name = test['name']
        script_path = Path(__file__).parent / test['script']
        
        print(f"\n{'='*60}")
        print(f"🧪 Running: {test_name}")
        print(f"📝 Description: {test['description']}")
        print(f"⏱️ Max time: {test['max_time_minutes']} minutes")
        print(f"📁 Script: {test['script']}")
        print(f"{'='*60}")
        
        # Check if script exists
        if not script_path.exists():
            print(f"❌ Test script not found: {script_path}")
            return False, {
                'success': False,
                'error': f'Script not found: {script_path}',
                'execution_time': 0
            }
        
        # Run the test
        start_time = time.time()
        
        try:
            # Execute test script
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=test['max_time_minutes'] * 60  # Convert to seconds
            )
            
            execution_time = time.time() - start_time
            
            # Analyze results
            success = result.returncode == 0
            
            test_result = {
                'success': success,
                'execution_time': execution_time,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
            # Print results
            if success:
                print(f"✅ {test_name} PASSED")
                print(f"⏱️ Execution time: {execution_time:.1f}s")
            else:
                print(f"❌ {test_name} FAILED")
                print(f"⏱️ Execution time: {execution_time:.1f}s")
                print(f"🔍 Return code: {result.returncode}")
                if result.stderr:
                    print(f"🚨 Error output:")
                    print(result.stderr[:500])  # First 500 chars of error
            
            return success, test_result
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            print(f"⏰ {test_name} TIMED OUT after {test['max_time_minutes']} minutes")
            
            return False, {
                'success': False,
                'error': f'Test timed out after {test["max_time_minutes"]} minutes',
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"💥 {test_name} CRASHED: {e}")
            
            return False, {
                'success': False,
                'error': str(e),
                'execution_time': execution_time
            }
    
    def run_all_tests(self) -> bool:
        """Run all tests in the validation suite"""
        self.print_header()
        
        for test in self.tests:
            test_name = test['name']
            
            # Check dependencies
            if not self.check_dependencies(test):
                print(f"⏭️ Skipping {test_name} due to failed dependencies")
                self.test_results[test_name] = {
                    'success': False,
                    'error': 'Dependencies not satisfied',
                    'execution_time': 0,
                    'skipped': True
                }
                
                if test['mandatory']:
                    self.overall_success = False
                    print(f"❌ Mandatory test {test_name} skipped - overall failure")
                
                continue
            
            # Run the test
            success, result = self.run_test(test)
            self.test_results[test_name] = result
            
            # Check if mandatory test failed
            if not success and test['mandatory']:
                self.overall_success = False
                print(f"❌ Mandatory test {test_name} failed - stopping execution")
                break
            elif not success:
                print(f"⚠️ Optional test {test_name} failed - continuing")
        
        return self.overall_success
    
    def generate_final_report(self) -> str:
        """Generate comprehensive final report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.output_dir / f"automation_validation_suite_report_{timestamp}.json"
        
        total_execution_time = time.time() - self.start_time
        
        # Calculate statistics
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results.values() 
                             if result.get('success', False))
        failed_tests = total_tests - successful_tests
        skipped_tests = sum(1 for result in self.test_results.values() 
                          if result.get('skipped', False))
        
        # Categorize tests
        mandatory_tests = [test for test in self.tests if test['mandatory']]
        optional_tests = [test for test in self.tests if not test['mandatory']]
        
        mandatory_success = all(
            self.test_results.get(test['name'], {}).get('success', False)
            for test in mandatory_tests
        )
        
        # Create comprehensive report
        report = {
            'suite_info': {
                'name': 'Automation Progressive Validation Suite',
                'timestamp': timestamp,
                'total_execution_time': total_execution_time,
                'overall_success': self.overall_success
            },
            'test_statistics': {
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'failed_tests': failed_tests,
                'skipped_tests': skipped_tests,
                'success_rate_percent': (successful_tests / total_tests * 100) if total_tests > 0 else 0
            },
            'mandatory_tests': {
                'total': len(mandatory_tests),
                'successful': sum(1 for test in mandatory_tests 
                                if self.test_results.get(test['name'], {}).get('success', False)),
                'all_passed': mandatory_success
            },
            'optional_tests': {
                'total': len(optional_tests),
                'successful': sum(1 for test in optional_tests 
                                if self.test_results.get(test['name'], {}).get('success', False))
            },
            'test_results': self.test_results,
            'progressive_validation_status': {
                'bug_prevention_passed': self.test_results.get('Bug Prevention', {}).get('success', False),
                'step1_passed': self.test_results.get('Step 1 - 10 Listings', {}).get('success', False),
                'step2_passed': self.test_results.get('Step 2 - 100 Listings', {}).get('success', False),
                'step3_passed': self.test_results.get('Step 3 - Full Production', {}).get('success', False),
                'deployment_validated': self.test_results.get('Deployment Modes', {}).get('success', False),
                'ready_for_production': mandatory_success
            },
            'recommendations': self._generate_recommendations(),
            'next_steps': self._generate_next_steps()
        }
        
        # Save report
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return str(report_path)
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        if not self.test_results.get('Bug Prevention', {}).get('success', False):
            recommendations.append('Fix all bugs identified in bug prevention tests before proceeding')
        
        if not self.test_results.get('Step 1 - 10 Listings', {}).get('success', False):
            recommendations.append('Resolve basic automation issues before scaling up')
        
        if not self.test_results.get('Step 2 - 100 Listings', {}).get('success', False):
            recommendations.append('Address scalability issues before production deployment')
        
        if not self.test_results.get('Step 3 - Full Production', {}).get('success', False):
            recommendations.append('Fix production readiness issues before deployment')
        
        if self.overall_success:
            recommendations.extend([
                'Automation system is ready for production deployment',
                'Set up monitoring and alerting in production environment',
                'Plan regular maintenance and updates',
                'Establish backup and recovery procedures'
            ])
        
        return recommendations
    
    def _generate_next_steps(self) -> List[str]:
        """Generate next steps based on test results"""
        next_steps = []
        
        if self.overall_success:
            next_steps.extend([
                'Deploy automation system to production environment',
                'Configure production monitoring and alerting',
                'Set up scheduled execution (daily scraping)',
                'Monitor system performance and data quality',
                'Plan capacity scaling as needed'
            ])
        else:
            next_steps.extend([
                'Review failed test results and error logs',
                'Fix identified issues and bugs',
                'Re-run failed tests to verify fixes',
                'Continue progressive validation once issues resolved',
                'Consider reducing scope if persistent issues'
            ])
        
        return next_steps
    
    def print_final_summary(self, report_path: str):
        """Print final test suite summary"""
        total_time = time.time() - self.start_time
        
        print(f"\n{'='*80}")
        print("🏁 AUTOMATION VALIDATION SUITE COMPLETE")
        print(f"{'='*80}")
        print(f"⏱️ Total execution time: {total_time/60:.1f} minutes")
        print(f"📊 Tests run: {len(self.test_results)}")
        
        # Print test results summary
        for test_name, result in self.test_results.items():
            status = "✅ PASSED" if result.get('success', False) else "❌ FAILED"
            if result.get('skipped', False):
                status = "⏭️ SKIPPED"
            
            time_str = f"{result.get('execution_time', 0):.1f}s"
            print(f"   {status} {test_name} ({time_str})")
        
        print(f"\n🎯 Overall Result: {'✅ SUCCESS' if self.overall_success else '❌ FAILURE'}")
        
        if self.overall_success:
            print("🚀 AUTOMATION SYSTEM IS READY FOR PRODUCTION!")
            print("   All mandatory tests passed")
            print("   Progressive validation complete")
            print("   System validated for deployment")
        else:
            print("🔧 AUTOMATION SYSTEM NEEDS FIXES")
            print("   One or more mandatory tests failed")
            print("   Review test results and fix issues")
            print("   Re-run validation suite after fixes")
        
        print(f"\n📋 Detailed report: {report_path}")
        print(f"{'='*80}")


def main():
    """Main function to run the automation validation suite"""
    suite = AutomationValidationSuite()
    
    try:
        # Run all tests
        overall_success = suite.run_all_tests()
        
        # Generate final report
        report_path = suite.generate_final_report()
        
        # Print summary
        suite.print_final_summary(report_path)
        
        # Exit with appropriate code
        sys.exit(0 if overall_success else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️ Validation suite interrupted by user")
        print("🔄 You can resume by running individual test scripts")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n💥 Validation suite crashed: {e}")
        print("🔍 Check logs and fix issues before retrying")
        sys.exit(1)


if __name__ == "__main__":
    main()