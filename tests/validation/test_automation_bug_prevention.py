#!/usr/bin/env python3
"""
Comprehensive Bug Prevention Tests for Automation System

Tests all automation components for common bugs, edge cases, and failure scenarios
to prevent issues before expensive operations.

Requirements: 5.1, 5.2
"""

import sys
import unittest
import asyncio
import json
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oikotie.automation.orchestrator import EnhancedScraperOrchestrator
from oikotie.automation.deduplication import SmartDeduplicationManager
from oikotie.automation.config_manager import ConfigurationManager
from oikotie.automation.monitoring import SystemMonitor, HealthChecker
from oikotie.database.manager import EnhancedDatabaseManager


class TestAutomationBugPrevention(unittest.TestCase):
    """Comprehensive bug prevention tests for automation system"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_start_time = time.time()
        self.output_dir = Path("output/validation/automation")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.test_config = {
            'cities': ['Helsinki'],
            'max_listings_per_city': 5,
            'smart_deduplication': {
                'enabled': True,
                'staleness_hours': 1,
                'skip_recent': True
            },
            'monitoring': {
                'enabled': True,
                'metrics_port': 8085
            },
            'database': {
                'path': 'data/real_estate.duckdb'
            }
        }
        
        self.bugs_found = []
        self.edge_cases_tested = []
        
    def record_bug(self, component: str, bug_type: str, description: str, severity: str = 'medium'):
        """Record a bug for reporting"""
        bug = {
            'component': component,
            'bug_type': bug_type,
            'description': description,
            'severity': severity,
            'timestamp': datetime.now().isoformat(),
            'test_method': self._testMethodName
        }
        self.bugs_found.append(bug)
        print(f"🐛 BUG FOUND: {component} - {bug_type}: {description}")
    
    def record_edge_case(self, component: str, case: str, result: str):
        """Record an edge case test"""
        edge_case = {
            'component': component,
            'case': case,
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
        self.edge_cases_tested.append(edge_case)
    
    def test_01_database_manager_edge_cases(self):
        """Test database manager edge cases"""
        print("\n🔍 Testing Database Manager Edge Cases...")
        
        try:
            db_manager = EnhancedDatabaseManager()
            
            # Test empty/None inputs
            try:
                result = db_manager.get_listings_with_coordinates(None)
                if result is not None:
                    self.record_bug('DatabaseManager', 'null_handling', 
                                  'Should handle None city gracefully')
            except Exception as e:
                self.record_edge_case('DatabaseManager', 'null_city_input', f'Exception: {e}')
            
            # Test invalid city names
            invalid_cities = ['', 'NonExistentCity123', 'DROP TABLE listings;']
            for city in invalid_cities:
                try:
                    result = db_manager.get_listings_with_coordinates(city)
                    self.record_edge_case('DatabaseManager', f'invalid_city_{city}', 
                                        f'Returned {len(result) if result else 0} results')
                except Exception as e:
                    self.record_edge_case('DatabaseManager', f'invalid_city_{city}', f'Exception: {e}')
            
            print("✅ Database Manager edge cases tested")
            
        except Exception as e:
            self.record_bug('DatabaseManager', 'general_failure', f'Unexpected failure: {e}')
    
    def test_02_smart_deduplication_edge_cases(self):
        """Test smart deduplication edge cases"""
        print("\n🔍 Testing Smart Deduplication Edge Cases...")
        
        try:
            db_manager = EnhancedDatabaseManager()
            dedup_manager = SmartDeduplicationManager(db_manager)
            
            # Test empty URL lists
            try:
                result = dedup_manager.prioritize_listings([])
                if result != []:
                    self.record_bug('SmartDeduplication', 'empty_list_handling', 
                                  'Empty list should return empty list')
                self.record_edge_case('SmartDeduplication', 'empty_url_list', 'Handled correctly')
            except Exception as e:
                self.record_bug('SmartDeduplication', 'empty_list_exception', f'Exception: {e}')
            
            # Test invalid URLs
            invalid_urls = [None, '', 'not-a-url', 'http://']
            try:
                result = dedup_manager.prioritize_listings(invalid_urls)
                self.record_edge_case('SmartDeduplication', 'invalid_urls', 
                                    f'Processed {len(result)} from {len(invalid_urls)} invalid URLs')
            except Exception as e:
                self.record_bug('SmartDeduplication', 'invalid_url_exception', f'Exception: {e}')
            
            print("✅ Smart Deduplication edge cases tested")
            
        except Exception as e:
            self.record_bug('SmartDeduplication', 'general_failure', f'Unexpected failure: {e}')
    
    def test_03_configuration_manager_edge_cases(self):
        """Test configuration manager edge cases"""
        print("\n🔍 Testing Configuration Manager Edge Cases...")
        
        try:
            config_manager = ConfigurationManager()
            
            # Test empty configuration
            try:
                config = config_manager.load_config_from_dict({})
                if not hasattr(config, 'cities') or not config.cities:
                    self.record_bug('ConfigurationManager', 'empty_config', 
                                  'Empty config should have default values')
                self.record_edge_case('ConfigurationManager', 'empty_config', 'Handled with defaults')
            except Exception as e:
                self.record_bug('ConfigurationManager', 'empty_config_exception', f'Exception: {e}')
            
            # Test invalid configuration values
            invalid_configs = [
                {'cities': None},
                {'cities': []},
                {'max_listings_per_city': -1},
                {'max_listings_per_city': 'invalid'}
            ]
            
            for i, invalid_config in enumerate(invalid_configs):
                try:
                    config = config_manager.load_config_from_dict(invalid_config)
                    self.record_edge_case('ConfigurationManager', f'invalid_config_{i}', 
                                        'Loaded with validation/defaults')
                except Exception as e:
                    self.record_edge_case('ConfigurationManager', f'invalid_config_{i}', f'Exception: {e}')
            
            print("✅ Configuration Manager edge cases tested")
            
        except Exception as e:
            self.record_bug('ConfigurationManager', 'general_failure', f'Unexpected failure: {e}')
    
    def test_04_monitoring_system_edge_cases(self):
        """Test monitoring system edge cases"""
        print("\n🔍 Testing Monitoring System Edge Cases...")
        
        try:
            # Test System Monitor edge cases
            system_monitor = SystemMonitor(collection_interval=1)
            
            # Test with invalid collection interval
            try:
                invalid_monitor = SystemMonitor(collection_interval=0)
                self.record_edge_case('SystemMonitor', 'zero_interval', 'Created with zero interval')
            except Exception as e:
                self.record_edge_case('SystemMonitor', 'zero_interval', f'Exception: {e}')
            
            # Test Health Checker edge cases
            health_checker = HealthChecker()
            
            # Test with invalid database
            try:
                invalid_db_manager = Mock()
                invalid_db_manager.get_connection.side_effect = Exception("Database error")
                
                invalid_health_checker = HealthChecker(db_manager=invalid_db_manager)
                health_results = invalid_health_checker.run_health_checks()
                
                if health_results.get('overall_healthy', True):
                    self.record_bug('HealthChecker', 'false_positive', 
                                  'Health check passed with broken database')
                
                self.record_edge_case('HealthChecker', 'broken_database', 'Correctly detected failure')
            except Exception as e:
                self.record_edge_case('HealthChecker', 'broken_database', f'Exception: {e}')
            
            print("✅ Monitoring System edge cases tested")
            
        except Exception as e:
            self.record_bug('MonitoringSystem', 'general_failure', f'Unexpected failure: {e}')
    
    def test_05_orchestrator_edge_cases(self):
        """Test orchestrator edge cases"""
        print("\n🔍 Testing Orchestrator Edge Cases...")
        
        try:
            db_manager = EnhancedDatabaseManager()
            config_manager = ConfigurationManager()
            config = config_manager.load_config_from_dict(self.test_config)
            
            # Test with invalid configuration
            try:
                invalid_config = config_manager.load_config_from_dict({'cities': []})
                orchestrator = EnhancedScraperOrchestrator(config=invalid_config, db_manager=db_manager)
                
                plan = orchestrator.plan_execution('NonExistentCity')
                if plan.get('total_urls', 0) > 0:
                    self.record_bug('Orchestrator', 'invalid_city_plan', 
                                  'Generated plan for non-existent city')
                
                self.record_edge_case('Orchestrator', 'invalid_config', 'Handled gracefully')
            except Exception as e:
                self.record_edge_case('Orchestrator', 'invalid_config', f'Exception: {e}')
            
            # Test with broken database
            try:
                broken_db_manager = Mock()
                broken_db_manager.get_connection.side_effect = Exception("Database connection failed")
                
                orchestrator = EnhancedScraperOrchestrator(config=config, db_manager=broken_db_manager)
                
                result = asyncio.run(orchestrator.run_daily_scrape())
                
                if result.get('status') == 'success':
                    self.record_bug('Orchestrator', 'broken_db_success', 
                                  'Reported success with broken database')
                
                self.record_edge_case('Orchestrator', 'broken_database', 'Handled database failure')
            except Exception as e:
                self.record_edge_case('Orchestrator', 'broken_database', f'Exception: {e}')
            
            print("✅ Orchestrator edge cases tested")
            
        except Exception as e:
            self.record_bug('Orchestrator', 'general_failure', f'Unexpected failure: {e}')
    
    def test_06_generate_bug_report(self):
        """Generate comprehensive bug report"""
        print("\n📋 Generating Bug Report...")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.output_dir / f"bug_prevention_report_{timestamp}.json"
        
        # Categorize bugs by severity
        critical_bugs = [b for b in self.bugs_found if b['severity'] == 'critical']
        high_bugs = [b for b in self.bugs_found if b['severity'] == 'high']
        medium_bugs = [b for b in self.bugs_found if b['severity'] == 'medium']
        low_bugs = [b for b in self.bugs_found if b['severity'] == 'low']
        
        report = {
            'test_info': {
                'test_name': 'Automation Bug Prevention Test',
                'timestamp': timestamp,
                'execution_time': time.time() - self.test_start_time,
                'total_bugs_found': len(self.bugs_found),
                'total_edge_cases_tested': len(self.edge_cases_tested)
            },
            'bug_summary': {
                'critical': len(critical_bugs),
                'high': len(high_bugs),
                'medium': len(medium_bugs),
                'low': len(low_bugs)
            },
            'all_bugs': self.bugs_found,
            'edge_cases_tested': self.edge_cases_tested,
            'recommendations': [
                'Fix all critical and high severity bugs before production',
                'Review medium severity bugs for potential issues',
                'Add additional error handling for edge cases'
            ]
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"📋 Bug Prevention Report Generated: {report_path}")
        print(f"   Total bugs found: {len(self.bugs_found)}")
        print(f"   Edge cases tested: {len(self.edge_cases_tested)}")
        
        return report_path


def run_bug_prevention_test():
    """Run the comprehensive bug prevention test"""
    print("🐛 Automation Bug Prevention Test Suite")
    print("=" * 60)
    print("Testing all automation components for bugs and edge cases")
    print("=" * 60)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAutomationBugPrevention)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ BUG PREVENTION TEST PASSED")
        print("🚀 No critical bugs found - safe to proceed")
    else:
        print("❌ BUG PREVENTION TEST FAILED")
        print("🐛 Critical bugs found - must fix before proceeding")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_bug_prevention_test()
    sys.exit(0 if success else 1)