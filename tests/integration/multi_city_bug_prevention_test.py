#!/usr/bin/env python3
"""
Multi-City Bug Prevention Test

This script provides comprehensive bug prevention testing before running expensive
multi-city integration operations. It validates system readiness, configuration,
and basic functionality to prevent costly failures.

Requirements: 5.1, 5.2, 5.3
"""

import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import psutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oikotie.database.manager import EnhancedDatabaseManager
from oikotie.automation.config_manager import ConfigurationManager


class MultiCityBugPreventionTest:
    """Comprehensive bug prevention testing for multi-city operations"""
    
    def __init__(self):
        self.start_time = time.time()
        self.output_dir = Path("output/validation/bug_prevention")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.test_results = {}
        self.critical_issues = []
        self.warnings = []
        
    def run_comprehensive_bug_prevention(self) -> Dict[str, Any]:
        """Run comprehensive bug prevention tests"""
        print("🛡️ Multi-City Bug Prevention Test Suite")
        print("=" * 60)
        print("Running comprehensive validation before expensive operations")
        print("=" * 60)
        
        # Test categories
        test_categories = [
            ('system_requirements', self._test_system_requirements),
            ('database_connectivity', self._test_database_connectivity),
            ('configuration_validation', self._test_configuration_validation),
            ('multi_city_schema', self._test_multi_city_schema),
            ('dependency_validation', self._test_dependency_validation),
            ('resource_availability', self._test_resource_availability),
            ('network_connectivity', self._test_network_connectivity),
            ('basic_functionality', self._test_basic_functionality)
        ]
        
        # Run all test categories
        for category_name, test_function in test_categories:
            print(f"\n🔍 Testing {category_name.replace('_', ' ').title()}...")
            
            try:
                category_start = time.time()
                result = test_function()
                category_time = time.time() - category_start
                
                self.test_results[category_name] = {
                    'success': result['success'],
                    'execution_time': category_time,
                    'details': result.get('details', {}),
                    'issues': result.get('issues', []),
                    'warnings': result.get('warnings', [])
                }
                
                # Collect critical issues and warnings
                if result.get('issues'):
                    self.critical_issues.extend(result['issues'])
                if result.get('warnings'):
                    self.warnings.extend(result['warnings'])
                
                status = "✅" if result['success'] else "❌"
                print(f"   {status} {category_name.replace('_', ' ').title()}: {'PASSED' if result['success'] else 'FAILED'} ({category_time:.2f}s)")
                
                if result.get('issues'):
                    for issue in result['issues']:
                        print(f"     ❌ CRITICAL: {issue}")
                
                if result.get('warnings'):
                    for warning in result['warnings']:
                        print(f"     ⚠️ WARNING: {warning}")
                
            except Exception as e:
                category_time = time.time() - category_start
                
                self.test_results[category_name] = {
                    'success': False,
                    'execution_time': category_time,
                    'error': str(e)
                }
                
                self.critical_issues.append(f"{category_name}: {str(e)}")
                print(f"   ❌ {category_name.replace('_', ' ').title()}: ERROR ({category_time:.2f}s)")
                print(f"     ❌ CRITICAL: {str(e)}")
        
        # Generate final report
        total_execution_time = time.time() - self.start_time
        report = self._generate_bug_prevention_report(total_execution_time)
        
        # Print summary
        self._print_bug_prevention_summary(report)
        
        return report
    
    def _test_system_requirements(self) -> Dict[str, Any]:
        """Test system requirements"""
        issues = []
        warnings = []
        details = {}
        
        try:
            # Check Python version
            python_version = sys.version_info
            details['python_version'] = f"{python_version.major}.{python_version.minor}.{python_version.micro}"
            
            if python_version < (3, 9):
                issues.append(f"Python version {details['python_version']} is too old (requires >= 3.9)")
            elif python_version < (3, 10):
                warnings.append(f"Python version {details['python_version']} is supported but 3.10+ recommended")
            
            # Check available memory
            memory_info = psutil.virtual_memory()
            available_memory_gb = memory_info.available / 1024 / 1024 / 1024
            details['available_memory_gb'] = round(available_memory_gb, 2)
            
            if available_memory_gb < 2:
                issues.append(f"Insufficient memory: {available_memory_gb:.1f}GB available (requires >= 2GB)")
            elif available_memory_gb < 4:
                warnings.append(f"Low memory: {available_memory_gb:.1f}GB available (4GB+ recommended)")
            
            # Check available disk space
            disk_usage = psutil.disk_usage('.')
            available_disk_gb = disk_usage.free / 1024 / 1024 / 1024
            details['available_disk_gb'] = round(available_disk_gb, 2)
            
            if available_disk_gb < 1:
                issues.append(f"Insufficient disk space: {available_disk_gb:.1f}GB available (requires >= 1GB)")
            elif available_disk_gb < 5:
                warnings.append(f"Low disk space: {available_disk_gb:.1f}GB available (5GB+ recommended)")
            
            # Check CPU cores
            cpu_count = psutil.cpu_count()
            details['cpu_count'] = cpu_count
            
            if cpu_count < 2:
                warnings.append(f"Low CPU count: {cpu_count} cores (2+ recommended for multi-city operations)")
            
            return {
                'success': len(issues) == 0,
                'details': details,
                'issues': issues,
                'warnings': warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"System requirements check failed: {str(e)}"]
            }
    
    def _test_database_connectivity(self) -> Dict[str, Any]:
        """Test database connectivity"""
        issues = []
        warnings = []
        details = {}
        
        try:
            # Test database connection
            db_manager = EnhancedDatabaseManager()
            connection = db_manager.get_connection()
            
            if connection is None:
                issues.append("Cannot establish database connection")
                return {
                    'success': False,
                    'issues': issues
                }
            
            details['database_connected'] = True
            
            # Test basic database operations
            try:
                # Test simple query
                result = connection.execute("SELECT 1 as test").fetchone()
                if result[0] != 1:
                    issues.append("Database query test failed")
                else:
                    details['basic_query_works'] = True
                
                # Test database info
                db_info = connection.execute("PRAGMA database_list").fetchall()
                details['database_count'] = len(db_info)
                
                # Test write capability
                connection.execute("CREATE TEMPORARY TABLE test_table (id INTEGER)")
                connection.execute("INSERT INTO test_table (id) VALUES (1)")
                test_result = connection.execute("SELECT id FROM test_table").fetchone()
                
                if test_result[0] != 1:
                    issues.append("Database write test failed")
                else:
                    details['write_capability'] = True
                
                connection.execute("DROP TABLE test_table")
                
            except Exception as e:
                issues.append(f"Database operation test failed: {str(e)}")
            
            connection.close()
            
            return {
                'success': len(issues) == 0,
                'details': details,
                'issues': issues,
                'warnings': warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"Database connectivity test failed: {str(e)}"]
            }
    
    def _test_configuration_validation(self) -> Dict[str, Any]:
        """Test configuration validation"""
        issues = []
        warnings = []
        details = {}
        
        try:
            # Test configuration loading
            config_manager = ConfigurationManager()
            
            # Test default configuration
            try:
                config_path = Path("config/config.json")
                if not config_path.exists():
                    issues.append("Configuration file config/config.json not found")
                    return {
                        'success': False,
                        'issues': issues
                    }
                
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                
                details['config_file_exists'] = True
                details['config_loaded'] = True
                
                # Validate multi-city configuration
                if 'tasks' not in config_data:
                    issues.append("Configuration missing 'tasks' section")
                else:
                    tasks = config_data['tasks']
                    details['task_count'] = len(tasks)
                    
                    # Check for Helsinki and Espoo
                    cities = [task.get('city') for task in tasks if task.get('enabled', False)]
                    details['enabled_cities'] = cities
                    
                    if 'Helsinki' not in cities:
                        warnings.append("Helsinki not enabled in configuration")
                    
                    if 'Espoo' not in cities:
                        warnings.append("Espoo not enabled in configuration")
                    
                    # Validate task configurations
                    for task in tasks:
                        city = task.get('city', 'Unknown')
                        
                        required_fields = ['city', 'url', 'max_detail_workers', 'coordinate_bounds']
                        for field in required_fields:
                            if field not in task:
                                issues.append(f"Task for {city} missing required field: {field}")
                        
                        # Validate coordinate bounds
                        if 'coordinate_bounds' in task:
                            bounds = task['coordinate_bounds']
                            if not isinstance(bounds, list) or len(bounds) != 4:
                                issues.append(f"Task for {city} has invalid coordinate_bounds format")
                            elif not all(isinstance(b, (int, float)) for b in bounds):
                                issues.append(f"Task for {city} has non-numeric coordinate_bounds")
                
                # Check global settings
                if 'global_settings' not in config_data:
                    warnings.append("Configuration missing 'global_settings' section")
                else:
                    global_settings = config_data['global_settings']
                    
                    # Check database path
                    if 'database_path' not in global_settings:
                        issues.append("Global settings missing 'database_path'")
                    else:
                        db_path = Path(global_settings['database_path'])
                        details['database_path'] = str(db_path)
                        
                        # Check if database directory exists
                        if not db_path.parent.exists():
                            issues.append(f"Database directory does not exist: {db_path.parent}")
                
            except json.JSONDecodeError as e:
                issues.append(f"Configuration file is not valid JSON: {str(e)}")
            except Exception as e:
                issues.append(f"Configuration validation failed: {str(e)}")
            
            return {
                'success': len(issues) == 0,
                'details': details,
                'issues': issues,
                'warnings': warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"Configuration validation failed: {str(e)}"]
            }
    
    def _test_multi_city_schema(self) -> Dict[str, Any]:
        """Test multi-city database schema"""
        issues = []
        warnings = []
        details = {}
        
        try:
            db_manager = EnhancedDatabaseManager()
            connection = db_manager.get_connection()
            
            # Check required tables
            tables_result = connection.execute("SHOW TABLES").fetchall()
            existing_tables = [row[0] for row in tables_result]
            details['existing_tables'] = existing_tables
            
            required_tables = ['listings', 'address_locations']
            for table in required_tables:
                if table not in existing_tables:
                    issues.append(f"Required table '{table}' does not exist")
            
            # Check listings table schema
            if 'listings' in existing_tables:
                try:
                    columns_result = connection.execute("DESCRIBE listings").fetchall()
                    column_names = [row[0] for row in columns_result]
                    details['listings_columns'] = column_names
                    
                    required_columns = ['url', 'city', 'title', 'address', 'scraped_at']
                    for column in required_columns:
                        if column not in column_names:
                            issues.append(f"Listings table missing required column: {column}")
                    
                    # Check if city column supports multi-city
                    if 'city' in column_names:
                        city_values = connection.execute("SELECT DISTINCT city FROM listings WHERE city IS NOT NULL LIMIT 10").fetchall()
                        unique_cities = [row[0] for row in city_values]
                        details['cities_in_database'] = unique_cities
                        
                        if len(unique_cities) == 0:
                            warnings.append("No city data found in listings table")
                        elif len(unique_cities) == 1 and unique_cities[0] not in ['Helsinki', 'Espoo']:
                            warnings.append(f"Only one city found in database: {unique_cities[0]}")
                
                except Exception as e:
                    issues.append(f"Failed to check listings table schema: {str(e)}")
            
            # Check address_locations table schema
            if 'address_locations' in existing_tables:
                try:
                    columns_result = connection.execute("DESCRIBE address_locations").fetchall()
                    column_names = [row[0] for row in columns_result]
                    details['address_locations_columns'] = column_names
                    
                    required_columns = ['address', 'latitude', 'longitude']
                    for column in required_columns:
                        if column not in column_names:
                            issues.append(f"Address_locations table missing required column: {column}")
                
                except Exception as e:
                    issues.append(f"Failed to check address_locations table schema: {str(e)}")
            
            connection.close()
            
            return {
                'success': len(issues) == 0,
                'details': details,
                'issues': issues,
                'warnings': warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"Multi-city schema test failed: {str(e)}"]
            }
    
    def _test_dependency_validation(self) -> Dict[str, Any]:
        """Test dependency validation"""
        issues = []
        warnings = []
        details = {}
        
        try:
            # Check critical Python packages
            critical_packages = [
                'duckdb',
                'pandas',
                'selenium',
                'loguru',
                'psutil'
            ]
            
            missing_packages = []
            package_versions = {}
            
            for package in critical_packages:
                try:
                    module = __import__(package)
                    version = getattr(module, '__version__', 'unknown')
                    package_versions[package] = version
                except ImportError:
                    missing_packages.append(package)
            
            details['package_versions'] = package_versions
            details['missing_packages'] = missing_packages
            
            if missing_packages:
                issues.append(f"Missing critical packages: {', '.join(missing_packages)}")
            
            # Check optional packages
            optional_packages = [
                'geopandas',
                'folium',
                'redis',
                'flask'
            ]
            
            missing_optional = []
            for package in optional_packages:
                try:
                    __import__(package)
                except ImportError:
                    missing_optional.append(package)
            
            if missing_optional:
                warnings.append(f"Missing optional packages: {', '.join(missing_optional)}")
            
            details['missing_optional_packages'] = missing_optional
            
            return {
                'success': len(issues) == 0,
                'details': details,
                'issues': issues,
                'warnings': warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"Dependency validation failed: {str(e)}"]
            }
    
    def _test_resource_availability(self) -> Dict[str, Any]:
        """Test resource availability"""
        issues = []
        warnings = []
        details = {}
        
        try:
            # Check current resource usage
            memory_info = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            disk_usage = psutil.disk_usage('.')
            
            details['current_memory_usage_percent'] = memory_info.percent
            details['current_cpu_usage_percent'] = cpu_percent
            details['current_disk_usage_percent'] = disk_usage.percent
            
            # Check if resources are available for multi-city operations
            if memory_info.percent > 80:
                issues.append(f"High memory usage: {memory_info.percent:.1f}% (should be < 80%)")
            elif memory_info.percent > 70:
                warnings.append(f"Moderate memory usage: {memory_info.percent:.1f}% (consider freeing memory)")
            
            if cpu_percent > 80:
                issues.append(f"High CPU usage: {cpu_percent:.1f}% (should be < 80%)")
            elif cpu_percent > 60:
                warnings.append(f"Moderate CPU usage: {cpu_percent:.1f}% (may affect performance)")
            
            if disk_usage.percent > 90:
                issues.append(f"High disk usage: {disk_usage.percent:.1f}% (should be < 90%)")
            elif disk_usage.percent > 80:
                warnings.append(f"Moderate disk usage: {disk_usage.percent:.1f}% (monitor space)")
            
            # Check for running processes that might interfere
            current_process = psutil.Process()
            details['current_process_memory_mb'] = current_process.memory_info().rss / 1024 / 1024
            
            return {
                'success': len(issues) == 0,
                'details': details,
                'issues': issues,
                'warnings': warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"Resource availability test failed: {str(e)}"]
            }
    
    def _test_network_connectivity(self) -> Dict[str, Any]:
        """Test network connectivity"""
        issues = []
        warnings = []
        details = {}
        
        try:
            # Test basic internet connectivity
            import socket
            
            test_hosts = [
                ('google.com', 80),
                ('github.com', 443),
                ('oikotie.fi', 443)
            ]
            
            connectivity_results = {}
            
            for host, port in test_hosts:
                try:
                    socket.create_connection((host, port), timeout=5)
                    connectivity_results[host] = True
                except (socket.timeout, socket.error):
                    connectivity_results[host] = False
            
            details['connectivity_results'] = connectivity_results
            
            # Check critical connectivity
            if not connectivity_results.get('oikotie.fi', False):
                issues.append("Cannot connect to oikotie.fi (required for scraping)")
            
            if not connectivity_results.get('google.com', False):
                warnings.append("Cannot connect to google.com (may indicate network issues)")
            
            # Test DNS resolution
            try:
                import socket
                socket.gethostbyname('oikotie.fi')
                details['dns_resolution'] = True
            except socket.gaierror:
                issues.append("DNS resolution failed for oikotie.fi")
                details['dns_resolution'] = False
            
            return {
                'success': len(issues) == 0,
                'details': details,
                'issues': issues,
                'warnings': warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"Network connectivity test failed: {str(e)}"]
            }
    
    def _test_basic_functionality(self) -> Dict[str, Any]:
        """Test basic functionality"""
        issues = []
        warnings = []
        details = {}
        
        try:
            # Test configuration manager
            try:
                config_manager = ConfigurationManager()
                test_config = {
                    'tasks': [
                        {
                            'city': 'TestCity',
                            'enabled': True,
                            'url': 'https://example.com',
                            'max_detail_workers': 1,
                            'coordinate_bounds': [0, 0, 1, 1]
                        }
                    ],
                    'global_settings': {
                        'database_path': 'test.db'
                    }
                }
                
                config = config_manager.load_config_from_dict(test_config)
                details['config_manager_works'] = True
                
            except Exception as e:
                issues.append(f"Configuration manager test failed: {str(e)}")
                details['config_manager_works'] = False
            
            # Test database manager basic operations
            try:
                db_manager = EnhancedDatabaseManager()
                connection = db_manager.get_connection()
                
                if connection:
                    # Test basic query
                    result = connection.execute("SELECT 1").fetchone()
                    if result and result[0] == 1:
                        details['database_manager_works'] = True
                    else:
                        issues.append("Database manager basic query failed")
                        details['database_manager_works'] = False
                    
                    connection.close()
                else:
                    issues.append("Database manager connection failed")
                    details['database_manager_works'] = False
                
            except Exception as e:
                issues.append(f"Database manager test failed: {str(e)}")
                details['database_manager_works'] = False
            
            # Test logging functionality
            try:
                from loguru import logger
                
                # Test log message
                logger.info("Bug prevention test log message")
                details['logging_works'] = True
                
            except Exception as e:
                warnings.append(f"Logging test failed: {str(e)}")
                details['logging_works'] = False
            
            return {
                'success': len(issues) == 0,
                'details': details,
                'issues': issues,
                'warnings': warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'issues': [f"Basic functionality test failed: {str(e)}"]
            }
    
    def _generate_bug_prevention_report(self, total_execution_time: float) -> Dict[str, Any]:
        """Generate bug prevention report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Calculate overall metrics
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results.values() if r['success'])
        failed_tests = total_tests - successful_tests
        
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Determine overall readiness
        system_ready = (
            len(self.critical_issues) == 0 and
            success_rate == 100.0
        )
        
        # Generate report
        report = {
            'test_info': {
                'test_name': 'Multi-City Bug Prevention Test',
                'timestamp': timestamp,
                'total_execution_time': total_execution_time,
                'tests_executed': list(self.test_results.keys())
            },
            'results': self.test_results,
            'summary': {
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'failed_tests': failed_tests,
                'success_rate_percent': success_rate,
                'critical_issues_count': len(self.critical_issues),
                'warnings_count': len(self.warnings),
                'system_ready': system_ready,
                'safe_to_proceed': system_ready
            },
            'critical_issues': self.critical_issues,
            'warnings': self.warnings,
            'recommendations': self._generate_bug_prevention_recommendations(system_ready),
            'next_steps': self._generate_bug_prevention_next_steps(system_ready)
        }
        
        # Save report to file
        report_path = self.output_dir / f"bug_prevention_report_{timestamp}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return report
    
    def _generate_bug_prevention_recommendations(self, system_ready: bool) -> List[str]:
        """Generate bug prevention recommendations"""
        recommendations = []
        
        if system_ready:
            recommendations.extend([
                "✅ System validation passed - safe to proceed with expensive operations",
                "Monitor resource usage during execution",
                "Ensure network connectivity remains stable",
                "Keep database backups current"
            ])
        else:
            recommendations.extend([
                "❌ System validation failed - DO NOT proceed with expensive operations",
                "Address all critical issues before retrying",
                "Review system requirements and configuration",
                "Consider running individual component tests"
            ])
            
            if self.critical_issues:
                recommendations.append("Priority: Fix critical issues first")
            
            if self.warnings:
                recommendations.append("Consider addressing warnings for optimal performance")
        
        return recommendations
    
    def _generate_bug_prevention_next_steps(self, system_ready: bool) -> List[str]:
        """Generate bug prevention next steps"""
        next_steps = []
        
        if system_ready:
            next_steps.extend([
                "Proceed with multi-city integration testing",
                "Run comprehensive integration test suite",
                "Monitor system performance during execution",
                "Set up automated monitoring and alerting"
            ])
        else:
            next_steps.extend([
                "Fix all critical issues identified in this report",
                "Re-run bug prevention test after fixes",
                "Verify system requirements are met",
                "Check configuration files and database setup",
                "Test individual components before full integration"
            ])
        
        return next_steps
    
    def _print_bug_prevention_summary(self, report: Dict[str, Any]):
        """Print bug prevention summary"""
        print("\n" + "=" * 60)
        print("🛡️ BUG PREVENTION TEST SUMMARY")
        print("=" * 60)
        
        summary = report['summary']
        
        print(f"Total execution time: {report['test_info']['total_execution_time']:.1f}s")
        print(f"Tests executed: {summary['total_tests']}")
        print(f"Successful tests: {summary['successful_tests']}")
        print(f"Failed tests: {summary['failed_tests']}")
        print(f"Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"Critical issues: {summary['critical_issues_count']}")
        print(f"Warnings: {summary['warnings_count']}")
        
        print("\nTest Results:")
        for test_name, result in self.test_results.items():
            status_icon = "✅" if result['success'] else "❌"
            print(f"  {status_icon} {test_name.replace('_', ' ').title()}: {'PASSED' if result['success'] else 'FAILED'} ({result['execution_time']:.2f}s)")
        
        if self.critical_issues:
            print("\n❌ CRITICAL ISSUES:")
            for issue in self.critical_issues:
                print(f"  • {issue}")
        
        if self.warnings:
            print("\n⚠️ WARNINGS:")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        print(f"\nSYSTEM READY: {'✅ YES' if summary['system_ready'] else '❌ NO'}")
        print(f"SAFE TO PROCEED: {'✅ YES' if summary['safe_to_proceed'] else '❌ NO'}")
        
        if summary['system_ready']:
            print("\n🎉 ALL BUG PREVENTION TESTS PASSED!")
            print("🚀 System validated - safe to proceed with expensive operations")
        else:
            print("\n⚠️ BUG PREVENTION TESTS FAILED")
            print("🔧 Address critical issues before proceeding")
        
        print("=" * 60)


def main():
    """Main entry point for bug prevention test"""
    try:
        # Run bug prevention tests
        tester = MultiCityBugPreventionTest()
        report = tester.run_comprehensive_bug_prevention()
        
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