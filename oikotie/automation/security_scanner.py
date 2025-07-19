"""
Vulnerability Scanner and Security Assessment System

This module provides security scanning and vulnerability assessment capabilities
for the daily scraper automation system.
"""

import json
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from loguru import logger


class VulnerabilityScanner:
    """Security scanning and vulnerability assessment system."""
    
    def __init__(self, config):
        """
        Initialize vulnerability scanner.
        
        Args:
            config: Security configuration
        """
        self.config = config
        self.scan_results: List[Dict[str, Any]] = []
        self.last_scan_time: Optional[datetime] = None
        
        logger.info("Vulnerability scanner initialized")
    
    def run_security_scan(self) -> Dict[str, Any]:
        """
        Run comprehensive security scan.
        
        Returns:
            Security scan results
        """
        if not self.config.vulnerability_scanning_enabled:
            return {"status": "disabled", "message": "Vulnerability scanning is disabled"}
        
        logger.info("Starting security scan")
        scan_start = datetime.now()
        
        results = {
            'scan_id': secrets.token_hex(8),
            'timestamp': scan_start.isoformat(),
            'scanner_version': '1.0.0',
            'checks': {},
            'summary': {
                'total_checks': 0,
                'passed': 0,
                'warnings': 0,
                'failures': 0,
                'critical': 0
            }
        }
        
        # File permissions check
        results['checks']['file_permissions'] = self._check_file_permissions()
        
        # Configuration security check
        results['checks']['configuration_security'] = self._check_configuration_security()
        
        # Dependency vulnerability check
        results['checks']['dependency_vulnerabilities'] = self._check_dependency_vulnerabilities()
        
        # Network security check
        results['checks']['network_security'] = self._check_network_security()
        
        # Database security check
        results['checks']['database_security'] = self._check_database_security()
        
        # Calculate summary
        for check_name, check_result in results['checks'].items():
            results['summary']['total_checks'] += 1
            
            if check_result['status'] == 'pass':
                results['summary']['passed'] += 1
            elif check_result['status'] == 'warning':
                results['summary']['warnings'] += 1
            elif check_result['status'] == 'fail':
                results['summary']['failures'] += 1
            elif check_result['status'] == 'critical':
                results['summary']['critical'] += 1
        
        # Overall status
        if results['summary']['critical'] > 0:
            results['overall_status'] = 'critical'
        elif results['summary']['failures'] > 0:
            results['overall_status'] = 'fail'
        elif results['summary']['warnings'] > 0:
            results['overall_status'] = 'warning'
        else:
            results['overall_status'] = 'pass'
        
        scan_duration = (datetime.now() - scan_start).total_seconds()
        results['scan_duration_seconds'] = scan_duration
        
        self.scan_results.append(results)
        self.last_scan_time = scan_start
        
        logger.info(f"Security scan completed in {scan_duration:.2f}s - Status: {results['overall_status']}")
        return results
    
    def _check_file_permissions(self) -> Dict[str, Any]:
        """Check file and directory permissions."""
        check_result = {
            'status': 'pass',
            'message': 'File permissions are secure',
            'details': [],
            'recommendations': []
        }
        
        # Check sensitive files
        sensitive_files = [
            '.security/master.key',
            '.security/credentials.enc',
            'config/scraper_config.json',
            'logs/audit.log'
        ]
        
        for file_path in sensitive_files:
            path = Path(file_path)
            if path.exists():
                try:
                    stat = path.stat()
                    mode = oct(stat.st_mode)[-3:]  # Get last 3 digits of octal mode
                    
                    # Check if file is readable by others
                    if int(mode[2]) > 0:  # Others have permissions
                        check_result['status'] = 'warning'
                        check_result['details'].append(f"{file_path}: permissions {mode} - readable by others")
                        check_result['recommendations'].append(f"Restrict permissions for {file_path}")
                    
                except Exception as e:
                    check_result['details'].append(f"{file_path}: error checking permissions - {e}")
        
        return check_result
    
    def _check_configuration_security(self) -> Dict[str, Any]:
        """Check configuration security settings."""
        check_result = {
            'status': 'pass',
            'message': 'Configuration security is adequate',
            'details': [],
            'recommendations': []
        }
        
        # Check for hardcoded secrets in config files
        config_files = [
            'config/scraper_config.json',
            'config/scraper_config.local.json'
        ]
        
        secret_patterns = [
            'password', 'secret', 'key', 'token', 'api_key'
        ]
        
        for config_file in config_files:
            path = Path(config_file)
            if path.exists():
                try:
                    content = path.read_text().lower()
                    for pattern in secret_patterns:
                        if pattern in content and not content.count(pattern) == content.count(f'"{pattern}": ""'):
                            check_result['status'] = 'warning'
                            check_result['details'].append(f"{config_file}: may contain hardcoded secrets")
                            check_result['recommendations'].append(f"Use credential manager for secrets in {config_file}")
                            break
                except Exception as e:
                    check_result['details'].append(f"{config_file}: error reading file - {e}")
        
        return check_result
    
    def _check_dependency_vulnerabilities(self) -> Dict[str, Any]:
        """Check for known vulnerabilities in dependencies."""
        check_result = {
            'status': 'pass',
            'message': 'No obvious dependency vulnerabilities found',
            'details': [],
            'recommendations': []
        }
        
        # This is a basic check - in production, you'd integrate with tools like
        # safety, bandit, or vulnerability databases
        
        try:
            # Check if requirements.txt or pyproject.toml exists
            if Path('pyproject.toml').exists():
                check_result['details'].append('Found pyproject.toml - recommend running safety check')
                check_result['recommendations'].append('Run: uv run safety check')
            
            if Path('requirements.txt').exists():
                check_result['details'].append('Found requirements.txt - recommend running safety check')
                check_result['recommendations'].append('Run: safety check -r requirements.txt')
            
        except Exception as e:
            check_result['details'].append(f"Error checking dependencies: {e}")
        
        return check_result
    
    def _check_network_security(self) -> Dict[str, Any]:
        """Check network security configuration."""
        check_result = {
            'status': 'pass',
            'message': 'Network security configuration is adequate',
            'details': [],
            'recommendations': []
        }
        
        # Check for open ports
        try:
            import socket
            
            # Check common ports
            ports_to_check = [8080, 8000, 5432, 6379, 3306]  # Health, metrics, postgres, redis, mysql
            
            for port in ports_to_check:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                if result == 0:  # Port is open
                    check_result['details'].append(f"Port {port} is open on localhost")
                    if port in [5432, 6379, 3306]:  # Database ports
                        check_result['status'] = 'warning'
                        check_result['recommendations'].append(f"Ensure port {port} is properly secured")
            
        except Exception as e:
            check_result['details'].append(f"Error checking network ports: {e}")
        
        return check_result
    
    def _check_database_security(self) -> Dict[str, Any]:
        """Check database security configuration."""
        check_result = {
            'status': 'pass',
            'message': 'Database security is adequate',
            'details': [],
            'recommendations': []
        }
        
        # Check database file permissions
        db_files = [
            'data/real_estate.duckdb',
            'data/real_estate.duckdb.wal'
        ]
        
        for db_file in db_files:
            path = Path(db_file)
            if path.exists():
                try:
                    stat = path.stat()
                    mode = oct(stat.st_mode)[-3:]
                    
                    if int(mode[1]) > 0 or int(mode[2]) > 0:  # Group or others have permissions
                        check_result['status'] = 'warning'
                        check_result['details'].append(f"{db_file}: permissions {mode} - accessible by others")
                        check_result['recommendations'].append(f"Restrict database file permissions: chmod 600 {db_file}")
                
                except Exception as e:
                    check_result['details'].append(f"{db_file}: error checking permissions - {e}")
        
        return check_result
    
    def get_latest_scan_results(self) -> Optional[Dict[str, Any]]:
        """Get the latest security scan results."""
        return self.scan_results[-1] if self.scan_results else None
    
    def should_run_scan(self) -> bool:
        """Check if a security scan should be run based on schedule."""
        if not self.config.vulnerability_scanning_enabled:
            return False
        
        if not self.last_scan_time:
            return True
        
        next_scan_time = self.last_scan_time + timedelta(hours=self.config.scan_interval_hours)
        return datetime.now() >= next_scan_time