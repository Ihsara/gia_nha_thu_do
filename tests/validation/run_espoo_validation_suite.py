#!/usr/bin/env python3
"""
Espoo Progressive Validation Suite Runner

Orchestrates the complete Espoo validation workflow:
1. Bug Prevention Tests (mandatory before expensive operations)
2. Geospatial Integration Tests
3. Step 1: 10 Sample Validation
4. Step 2: 100 Sample Validation  
5. Step 3: Full Scale Production Validation

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4
"""

import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime
import json

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class EspooValidationSuiteRunner:
    """Orchestrates the complete Espoo validation workflow"""
    
    def __init__(self):
        self.output_dir = Path("output/validation/espoo/")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.test_modules = [
            {
                'name': 'Bug Prevention',
                'module': 'tests.validation.test_espoo_bug_prevention',
                'required': True,
                'description': 'Comprehensive bug prevention before expensive operations'
            },
            {
                'name': 'Geospatial Integration',
                'module': 'tests.test_espoo_geospatial_integration',
                'required': True,
                'description': 'Geospatial data integration for Espoo'
            },
            {
                'name': 'Step 1: 10 Samples',
                'module': 'tests.validation.test_espoo_step1_10_samples',
                'required': True,
                'description': 'Proof of concept validation with 10 sample listings'
            },
            {
                'name': 'Step 2: 100 Samples',
                'module': 'tests.validation.test_espoo_step2_100_samples',
                'required': True,
                'description': 'Medium scale validation with geospatial integration'
            },
            {
                'name': 'Step 3: Full Scale',
                'module': 'tests.validation.test_espoo_step3_full_scale',
                'required': True,
                'description': 'Production scale validation with performance benchmarks'
            }
        ]
        
        self.results = {}
        
    def run_test_module(self, test_info):
        """Run a single test module"""
        print(f"\n{'='*80}")
        print(f"🚀 Running {test_info['name']}")
        print(f"📝 {test_info['description']}")
        print(f"📦 Module: {test_info['module']}")
        print(f"{'='*80}")
        
        start_time = time.time()
        
        try:
            # Run the test module using pytest
            cmd = [
                sys.executable, '-m', 'pytest', 
                f"{test_info['module'].replace('.', '/')}.py",
                '-v', '--tb=short'
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd=Path(__file__).parent.parent.parent
            )
            
            execution_time = time.time() - start_time
            
            success = result.returncode == 0
            
            test_result = {
                'name': test_info['name'],
                'module': test_info['module'],
                'success': success,
                'execution_time_seconds': execution_time,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'timestamp': datetime.now().isoformat()
            }
            
            if success:
                print(f"✅ {test_info['name']} PASSED in {execution_time:.1f}s")
            else:
                print(f"❌ {test_info['name']} FAILED in {execution_time:.1f}s")
                print(f"Return code: {result.returncode}")
                if result.stderr:
                    print(f"Error output:\n{result.stderr}")
            
            return test_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"❌ {test_info['name']} FAILED with exception: {e}")
            
            return {
                'name': test_info['name'],
                'module': test_info['module'],
                'success': False,
                'execution_time_seconds': execution_time,
                'return_code': -1,
                'stdout': '',
                'stderr': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def run_complete_suite(self):
        """Run the complete Espoo validation suite"""
        print("🏙️ Espoo Progressive Validation Suite")
        print("=" * 90)
        print("Complete validation workflow for Espoo expansion")
        print("Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4")
        print("=" * 90)
        
        suite_start_time = time.time()
        all_passed = True
        
        for test_info in self.test_modules:
            result = self.run_test_module(test_info)
            self.results[test_info['name']] = result
            
            if not result['success']:
                all_passed = False
                if test_info['required']:
                    print(f"\n❌ CRITICAL FAILURE: {test_info['name']} is required but failed")
                    print("🛑 Stopping validation suite due to critical failure")
                    break
        
        suite_execution_time = time.time() - suite_start_time
        
        # Generate comprehensive report
        self.generate_suite_report(all_passed, suite_execution_time)
        
        return all_passed
    
    def generate_suite_report(self, all_passed, suite_execution_time):
        """Generate comprehensive validation suite report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Calculate summary statistics
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r['success'])
        failed_tests = total_tests - passed_tests
        
        total_test_time = sum(r['execution_time_seconds'] for r in self.results.values())
        
        # Create comprehensive report
        suite_report = {
            'timestamp': datetime.now().isoformat(),
            'suite_name': 'espoo_progressive_validation_suite',
            'overall_success': all_passed,
            'suite_execution_time_seconds': suite_execution_time,
            'summary_statistics': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate_percent': (passed_tests / total_tests) * 100 if total_tests > 0 else 0,
                'total_test_execution_time_seconds': total_test_time
            },
            'test_results': self.results,
            'recommendations': self._generate_recommendations(all_passed)
        }
        
        # Save JSON report
        json_report_path = self.output_dir / f"espoo_validation_suite_report_{timestamp}.json"
        with open(json_report_path, 'w', encoding='utf-8') as f:
            json.dump(suite_report, f, indent=2, ensure_ascii=False)
        
        # Generate HTML report
        html_report_path = self.output_dir / f"espoo_validation_suite_report_{timestamp}.html"
        html_content = self._generate_html_report(suite_report)
        with open(html_report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Print summary
        self._print_suite_summary(suite_report, json_report_path, html_report_path)
    
    def _generate_recommendations(self, all_passed):
        """Generate recommendations based on test results"""
        if all_passed:
            return [
                "🎉 All validation tests passed successfully!",
                "✅ Espoo expansion is ready for production deployment",
                "🚀 Proceed with production configuration and deployment",
                "📊 Monitor performance metrics in production environment",
                "🔄 Schedule regular validation runs to maintain quality"
            ]
        else:
            failed_tests = [name for name, result in self.results.items() if not result['success']]
            return [
                f"❌ {len(failed_tests)} test(s) failed: {', '.join(failed_tests)}",
                "🔧 Address failing tests before proceeding to production",
                "📊 Review test output and error messages for specific issues",
                "🔄 Re-run validation suite after fixes are implemented",
                "💡 Consider running individual test modules for debugging"
            ]
    
    def _generate_html_report(self, suite_report):
        """Generate HTML validation suite report"""
        success_class = "success" if suite_report['overall_success'] else "error"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Espoo Progressive Validation Suite Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .success {{ color: green; font-weight: bold; }}
                .error {{ color: red; font-weight: bold; }}
                .warning {{ color: orange; font-weight: bold; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .metric-box {{ 
                    border: 1px solid #ddd; 
                    padding: 15px; 
                    margin: 10px 0; 
                    border-radius: 5px; 
                    background-color: #f9f9f9; 
                }}
                .suite-header {{ background-color: #e3f2fd; }}
                .test-passed {{ background-color: #e8f5e8; }}
                .test-failed {{ background-color: #ffebee; }}
                pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }}
            </style>
        </head>
        <body>
            <h1>🏙️ Espoo Progressive Validation Suite Report</h1>
            
            <div class="metric-box suite-header">
                <h2>📊 Suite Summary</h2>
                <p><strong>Overall Result:</strong> 
                   <span class="{success_class}">
                   {'✅ ALL TESTS PASSED' if suite_report['overall_success'] else '❌ SOME TESTS FAILED'}
                   </span>
                </p>
                <p><strong>Execution Time:</strong> {suite_report['suite_execution_time_seconds']:.1f} seconds</p>
                <p><strong>Timestamp:</strong> {suite_report['timestamp']}</p>
                <p><strong>Success Rate:</strong> {suite_report['summary_statistics']['success_rate_percent']:.1f}%</p>
            </div>
            
            <div class="metric-box">
                <h2>📈 Statistics</h2>
                <p><strong>Total Tests:</strong> {suite_report['summary_statistics']['total_tests']}</p>
                <p><strong>Passed Tests:</strong> {suite_report['summary_statistics']['passed_tests']}</p>
                <p><strong>Failed Tests:</strong> {suite_report['summary_statistics']['failed_tests']}</p>
                <p><strong>Total Test Time:</strong> {suite_report['summary_statistics']['total_test_execution_time_seconds']:.1f} seconds</p>
            </div>
            
            <div class="metric-box">
                <h2>🧪 Test Results</h2>
                <table>
                    <tr>
                        <th>Test Name</th>
                        <th>Status</th>
                        <th>Execution Time</th>
                        <th>Module</th>
                    </tr>
        """
        
        for test_name, result in suite_report['test_results'].items():
            status_class = "test-passed" if result['success'] else "test-failed"
            status_text = "✅ PASSED" if result['success'] else "❌ FAILED"
            
            html_content += f"""
                    <tr class="{status_class}">
                        <td><strong>{test_name}</strong></td>
                        <td>{status_text}</td>
                        <td>{result['execution_time_seconds']:.1f}s</td>
                        <td><code>{result['module']}</code></td>
                    </tr>
            """
        
        html_content += """
                </table>
            </div>
            
            <div class="metric-box">
                <h2>💡 Recommendations</h2>
                <ul>
        """
        
        for recommendation in suite_report['recommendations']:
            html_content += f"<li>{recommendation}</li>"
        
        html_content += f"""
                </ul>
            </div>
            
            <div class="metric-box">
                <h2>🚀 Next Steps</h2>
        """
        
        if suite_report['overall_success']:
            html_content += """
                <p>🎉 <strong>Congratulations!</strong> All Espoo validation tests passed.</p>
                <ol>
                    <li>✅ Review this comprehensive report</li>
                    <li>🚀 Proceed with production deployment configuration</li>
                    <li>📊 Set up production monitoring and alerting</li>
                    <li>🔄 Schedule regular validation runs</li>
                    <li>📝 Update documentation with Espoo support details</li>
                </ol>
            """
        else:
            html_content += """
                <p>⚠️ <strong>Action Required:</strong> Some tests failed and need attention.</p>
                <ol>
                    <li>❌ Review failed test details below</li>
                    <li>🔧 Address specific issues identified in test output</li>
                    <li>🔄 Re-run individual tests after fixes</li>
                    <li>✅ Re-run complete suite when all issues resolved</li>
                    <li>📝 Document any configuration changes made</li>
                </ol>
            """
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def _print_suite_summary(self, suite_report, json_path, html_path):
        """Print comprehensive suite summary"""
        print(f"\n{'='*90}")
        print(f"📊 ESPOO VALIDATION SUITE SUMMARY")
        print(f"{'='*90}")
        
        print(f"🏙️ Suite: Espoo Progressive Validation")
        print(f"⏱️ Total Execution Time: {suite_report['suite_execution_time_seconds']:.1f} seconds")
        print(f"📅 Timestamp: {suite_report['timestamp']}")
        
        print(f"\n📈 Results:")
        print(f"   📊 Total Tests: {suite_report['summary_statistics']['total_tests']}")
        print(f"   ✅ Passed: {suite_report['summary_statistics']['passed_tests']}")
        print(f"   ❌ Failed: {suite_report['summary_statistics']['failed_tests']}")
        print(f"   📈 Success Rate: {suite_report['summary_statistics']['success_rate_percent']:.1f}%")
        
        print(f"\n🧪 Individual Test Results:")
        for test_name, result in suite_report['test_results'].items():
            status = "✅ PASSED" if result['success'] else "❌ FAILED"
            print(f"   {status} {test_name} ({result['execution_time_seconds']:.1f}s)")
        
        print(f"\n📄 Reports Generated:")
        print(f"   📋 JSON Report: {json_path}")
        print(f"   🌐 HTML Report: {html_path}")
        
        print(f"\n💡 Recommendations:")
        for recommendation in suite_report['recommendations']:
            print(f"   {recommendation}")
        
        if suite_report['overall_success']:
            print(f"\n🎉 SUCCESS: Espoo expansion validation complete!")
            print(f"🚀 Ready for production deployment")
        else:
            print(f"\n❌ FAILURE: Some tests failed")
            print(f"🔧 Address issues before proceeding to production")


def main():
    """Main function to run the Espoo validation suite"""
    runner = EspooValidationSuiteRunner()
    success = runner.run_complete_suite()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())