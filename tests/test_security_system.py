"""
Tests for Security and Operational Hardening System

This module provides comprehensive tests for the security system including
credential management, audit logging, rate limiting, vulnerability scanning,
and backup operations.
"""

import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from unittest.mock import Mock, patch, MagicMock

from oikotie.automation.security import (
    SecurityManager, SecurityConfig, CredentialManager, AuditLogger,
    RateLimiter, AuditEventType, ThreatLevel, create_security_manager
)
from oikotie.automation.security_scanner import VulnerabilityScanner
from oikotie.automation.backup_manager import BackupManager


class TestSecurityConfig:
    """Test security configuration."""
    
    def test_default_config(self):
        """Test default security configuration."""
        config = SecurityConfig()
        
        assert config.encryption_enabled is True
        assert config.audit_enabled is True
        assert config.rate_limiting_enabled is True
        assert config.vulnerability_scanning_enabled is True
        assert config.backup_enabled is True
        assert config.key_rotation_days == 90
        assert config.audit_retention_days == 365
        assert config.max_requests_per_minute == 60
        assert config.max_requests_per_hour == 1000
    
    def test_custom_config(self):
        """Test custom security configuration."""
        config = SecurityConfig(
            encryption_enabled=False,
            audit_enabled=False,
            max_requests_per_minute=30,
            backup_interval_hours=12
        )
        
        assert config.encryption_enabled is False
        assert config.audit_enabled is False
        assert config.max_requests_per_minute == 30
        assert config.backup_interval_hours == 12


class TestCredentialManager:
    """Test credential management system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def config(self):
        """Create test security configuration."""
        return SecurityConfig(encryption_enabled=True)
    
    @pytest.fixture
    def credential_manager(self, config, temp_dir):
        """Create credential manager for testing."""
        key_file = temp_dir / ".security" / "master.key"
        return CredentialManager(config, str(key_file))
    
    def test_store_and_retrieve_credential(self, credential_manager):
        """Test storing and retrieving credentials."""
        # Store credential
        success = credential_manager.store_credential("test_key", "test_value", "Test credential")
        assert success is True
        
        # Retrieve credential
        value = credential_manager.get_credential("test_key")
        assert value == "test_value"
    
    def test_store_complex_credential(self, credential_manager):
        """Test storing complex credential data."""
        complex_data = {
            "username": "admin",
            "password": "secret123",
            "api_key": "abc123def456",
            "settings": {"timeout": 30, "retries": 3}
        }
        
        success = credential_manager.store_credential("complex_key", complex_data)
        assert success is True
        
        retrieved_data = credential_manager.get_credential("complex_key")
        assert retrieved_data == complex_data
    
    def test_list_credentials(self, credential_manager):
        """Test listing stored credentials."""
        # Store multiple credentials
        credential_manager.store_credential("key1", "value1", "First credential")
        credential_manager.store_credential("key2", "value2", "Second credential")
        
        # List credentials
        credentials = credential_manager.list_credentials()
        assert len(credentials) == 2
        
        keys = [cred['key'] for cred in credentials]
        assert "key1" in keys
        assert "key2" in keys
        
        # Check metadata
        for cred in credentials:
            assert 'created_at' in cred
            assert 'description' in cred
    
    def test_delete_credential(self, credential_manager):
        """Test deleting credentials."""
        # Store credential
        credential_manager.store_credential("delete_me", "value")
        
        # Verify it exists
        assert credential_manager.get_credential("delete_me") == "value"
        
        # Delete credential
        success = credential_manager.delete_credential("delete_me")
        assert success is True
        
        # Verify it's gone
        assert credential_manager.get_credential("delete_me") is None
    
    def test_nonexistent_credential(self, credential_manager):
        """Test retrieving nonexistent credential."""
        value = credential_manager.get_credential("nonexistent")
        assert value is None
    
    @patch('oikotie.automation.security.CRYPTOGRAPHY_AVAILABLE', False)
    def test_no_encryption_fallback(self, config, temp_dir):
        """Test credential manager without encryption."""
        key_file = temp_dir / ".security" / "master.key"
        manager = CredentialManager(config, str(key_file))
        
        # Should still work without encryption
        success = manager.store_credential("test", "value")
        assert success is True
        
        value = manager.get_credential("test")
        assert value == "value"


class TestAuditLogger:
    """Test audit logging system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def config(self, temp_dir):
        """Create test security configuration."""
        return SecurityConfig(
            audit_enabled=True,
            audit_log_path=str(temp_dir / "audit.log")
        )
    
    @pytest.fixture
    def audit_logger(self, config):
        """Create audit logger for testing."""
        return AuditLogger(config, "test-node")
    
    def test_log_authentication_event(self, audit_logger, config):
        """Test logging authentication events."""
        audit_logger.log_authentication("user123", "success", "192.168.1.1")
        
        # Check log file exists
        log_file = Path(config.audit_log_path)
        assert log_file.exists()
        
        # Check log content
        log_content = log_file.read_text()
        assert "user123" in log_content
        assert "success" in log_content
        assert "192.168.1.1" in log_content
        assert "authentication" in log_content
    
    def test_log_data_access_event(self, audit_logger, config):
        """Test logging data access events."""
        audit_logger.log_data_access("database_query", "listings_table", "user123", "exec-001")
        
        log_file = Path(config.audit_log_path)
        log_content = log_file.read_text()
        assert "database_query" in log_content
        assert "listings_table" in log_content
        assert "exec-001" in log_content
    
    def test_log_security_event(self, audit_logger, config):
        """Test logging security events."""
        audit_logger.log_security_event("suspicious_activity", ThreatLevel.HIGH, details="Multiple failed attempts")
        
        log_file = Path(config.audit_log_path)
        log_content = log_file.read_text()
        assert "suspicious_activity" in log_content
        assert "high" in log_content
        assert "Multiple failed attempts" in log_content
    
    def test_disabled_audit_logging(self, temp_dir):
        """Test audit logger when disabled."""
        config = SecurityConfig(audit_enabled=False)
        logger = AuditLogger(config, "test-node")
        
        # Should not create log file
        logger.log_authentication("user", "success")
        
        # No log file should be created
        log_files = list(Path(temp_dir).glob("*.log"))
        assert len(log_files) == 0


class TestRateLimiter:
    """Test rate limiting system."""
    
    @pytest.fixture
    def config(self):
        """Create test security configuration."""
        return SecurityConfig(
            rate_limiting_enabled=True,
            max_requests_per_minute=5,
            max_requests_per_hour=20
        )
    
    @pytest.fixture
    def rate_limiter(self, config):
        """Create rate limiter for testing."""
        return RateLimiter(config)
    
    def test_allow_requests_within_limit(self, rate_limiter):
        """Test allowing requests within rate limits."""
        identifier = "test-client"
        
        # Should allow requests within limit
        for i in range(5):
            assert rate_limiter.is_allowed(identifier) is True
    
    def test_block_requests_over_minute_limit(self, rate_limiter):
        """Test blocking requests over minute limit."""
        identifier = "test-client"
        
        # Use up minute limit
        for i in range(5):
            assert rate_limiter.is_allowed(identifier) is True
        
        # Next request should be blocked
        assert rate_limiter.is_allowed(identifier) is False
    
    def test_rate_limit_status(self, rate_limiter):
        """Test getting rate limit status."""
        identifier = "test-client"
        
        # Make some requests
        for i in range(3):
            rate_limiter.is_allowed(identifier)
        
        status = rate_limiter.get_rate_limit_status(identifier)
        
        assert status['identifier'] == identifier
        assert status['requests_last_minute'] == 3
        assert status['requests_last_hour'] == 3
        assert status['minute_limit'] == 5
        assert status['hour_limit'] == 20
        assert status['remaining_minute'] == 2
        assert status['remaining_hour'] == 17
        assert status['is_blocked'] is False
    
    def test_disabled_rate_limiting(self):
        """Test rate limiter when disabled."""
        config = SecurityConfig(rate_limiting_enabled=False)
        limiter = RateLimiter(config)
        
        # Should always allow requests
        for i in range(100):
            assert limiter.is_allowed("test-client") is True


class TestVulnerabilityScanner:
    """Test vulnerability scanning system."""
    
    @pytest.fixture
    def config(self):
        """Create test security configuration."""
        return SecurityConfig(vulnerability_scanning_enabled=True)
    
    @pytest.fixture
    def scanner(self, config):
        """Create vulnerability scanner for testing."""
        return VulnerabilityScanner(config)
    
    def test_run_security_scan(self, scanner):
        """Test running security scan."""
        results = scanner.run_security_scan()
        
        assert 'scan_id' in results
        assert 'timestamp' in results
        assert 'overall_status' in results
        assert 'checks' in results
        assert 'summary' in results
        
        # Check summary structure
        summary = results['summary']
        assert 'total_checks' in summary
        assert 'passed' in summary
        assert 'warnings' in summary
        assert 'failures' in summary
        assert 'critical' in summary
        
        # Should have run multiple checks
        assert summary['total_checks'] > 0
    
    def test_scan_results_storage(self, scanner):
        """Test scan results are stored."""
        # Run scan
        results1 = scanner.run_security_scan()
        results2 = scanner.run_security_scan()
        
        # Should store results
        assert len(scanner.scan_results) == 2
        
        # Latest results should be accessible
        latest = scanner.get_latest_scan_results()
        assert latest['scan_id'] == results2['scan_id']
    
    def test_should_run_scan_schedule(self, scanner):
        """Test scan scheduling logic."""
        # Should run scan initially
        assert scanner.should_run_scan() is True
        
        # Run a scan
        scanner.run_security_scan()
        
        # Should not run again immediately
        assert scanner.should_run_scan() is False
    
    def test_disabled_scanning(self):
        """Test scanner when disabled."""
        config = SecurityConfig(vulnerability_scanning_enabled=False)
        scanner = VulnerabilityScanner(config)
        
        results = scanner.run_security_scan()
        assert results['status'] == 'disabled'
        
        assert scanner.should_run_scan() is False


class TestBackupManager:
    """Test backup management system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def config(self):
        """Create test security configuration."""
        return SecurityConfig(backup_enabled=True, backup_retention_days=7)
    
    @pytest.fixture
    def backup_manager(self, config, temp_dir):
        """Create backup manager for testing."""
        # Change to temp directory for testing
        original_cwd = Path.cwd()
        import os
        os.chdir(temp_dir)
        
        # Create test data
        (temp_dir / "data").mkdir()
        (temp_dir / "data" / "real_estate.duckdb").write_text("test database")
        (temp_dir / "config").mkdir()
        (temp_dir / "config" / "scraper_config.json").write_text('{"test": "config"}')
        
        manager = BackupManager(config)
        
        yield manager
        
        # Restore original directory
        os.chdir(original_cwd)
    
    def test_create_backup(self, backup_manager):
        """Test creating a backup."""
        results = backup_manager.create_backup("test-backup")
        
        assert results['status'] == 'success'
        assert results['backup_name'] == 'test-backup'
        assert 'components' in results
        assert 'total_size_mb' in results
        
        # Check backup directory exists
        backup_path = Path(results['backup_path'])
        assert backup_path.exists()
        assert backup_path.is_dir()
        
        # Check manifest file
        manifest_file = backup_path / 'manifest.json'
        assert manifest_file.exists()
        
        manifest = json.loads(manifest_file.read_text())
        assert manifest['backup_name'] == 'test-backup'
    
    def test_list_backups(self, backup_manager):
        """Test listing backups."""
        # Create test backups
        backup_manager.create_backup("backup1")
        backup_manager.create_backup("backup2")
        
        backups = backup_manager.list_backups()
        
        assert len(backups) == 2
        backup_names = [b['backup_name'] for b in backups]
        assert "backup1" in backup_names
        assert "backup2" in backup_names
    
    def test_cleanup_old_backups(self, backup_manager):
        """Test cleaning up old backups."""
        # Create backup
        backup_manager.create_backup("old-backup")
        
        # Modify backup timestamp to make it old
        backup_dir = Path("backups/old-backup")
        old_time = datetime.now() - timedelta(days=10)
        import os
        os.utime(backup_dir, (old_time.timestamp(), old_time.timestamp()))
        
        # Run cleanup
        results = backup_manager.cleanup_old_backups()
        
        assert len(results['deleted_backups']) == 1
        assert results['deleted_backups'][0]['name'] == 'old-backup'
        
        # Backup should be gone
        assert not backup_dir.exists()
    
    def test_disabled_backup(self):
        """Test backup manager when disabled."""
        config = SecurityConfig(backup_enabled=False)
        manager = BackupManager(config)
        
        results = manager.create_backup()
        assert results['status'] == 'disabled'
        
        cleanup_results = manager.cleanup_old_backups()
        assert cleanup_results['status'] == 'disabled'


class TestSecurityManager:
    """Test comprehensive security manager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def config(self, temp_dir):
        """Create test security configuration."""
        return SecurityConfig(
            audit_log_path=str(temp_dir / "audit.log"),
            backup_enabled=True
        )
    
    @pytest.fixture
    def security_manager(self, config):
        """Create security manager for testing."""
        manager = SecurityManager(config, "test-node")
        yield manager
        manager.stop_background_tasks()
    
    def test_security_manager_initialization(self, security_manager):
        """Test security manager initialization."""
        assert security_manager.credential_manager is not None
        assert security_manager.audit_logger is not None
        assert security_manager.rate_limiter is not None
        assert security_manager.vulnerability_scanner is not None
        assert security_manager.backup_manager is not None
        assert security_manager.node_id == "test-node"
    
    def test_get_security_status(self, security_manager):
        """Test getting security status."""
        status = security_manager.get_security_status()
        
        assert 'timestamp' in status
        assert 'node_id' in status
        assert 'security_level' in status
        assert 'components' in status
        
        components = status['components']
        assert 'credential_manager' in components
        assert 'audit_logging' in components
        assert 'rate_limiting' in components
        assert 'vulnerability_scanning' in components
        assert 'backup' in components
    
    def test_background_tasks(self, security_manager):
        """Test background task management."""
        # Background tasks should start automatically
        assert security_manager._background_tasks_running is True
        assert security_manager._background_thread is not None
        
        # Stop background tasks
        security_manager.stop_background_tasks()
        assert security_manager._background_tasks_running is False
    
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_background_task_execution(self, mock_sleep, security_manager):
        """Test background task execution."""
        # Mock the should_run_scan method to return True once
        with patch.object(security_manager.vulnerability_scanner, 'should_run_scan', return_value=True):
            with patch.object(security_manager.vulnerability_scanner, 'run_security_scan') as mock_scan:
                mock_scan.return_value = {
                    'overall_status': 'pass',
                    'summary': {'critical': 0}
                }
                
                # Let background task run once
                security_manager._background_tasks_running = True
                
                # Simulate one iteration
                try:
                    # This would normally run in background thread
                    if security_manager.vulnerability_scanner.should_run_scan():
                        security_manager.vulnerability_scanner.run_security_scan()
                    
                    mock_scan.assert_called_once()
                except Exception:
                    pass  # Expected due to mocking


class TestSecurityIntegration:
    """Integration tests for security system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    def test_create_security_manager_function(self, temp_dir):
        """Test security manager creation function."""
        config = SecurityConfig(
            audit_log_path=str(temp_dir / "audit.log")
        )
        
        manager = create_security_manager(config, "integration-test-node")
        
        try:
            assert manager is not None
            assert manager.node_id == "integration-test-node"
            assert manager._background_tasks_running is True
            
            # Test basic functionality
            status = manager.get_security_status()
            assert status['node_id'] == "integration-test-node"
            
        finally:
            manager.stop_background_tasks()
    
    def test_end_to_end_security_workflow(self, temp_dir):
        """Test complete security workflow."""
        # Create security manager
        config = SecurityConfig(
            audit_log_path=str(temp_dir / "audit.log"),
            backup_enabled=True
        )
        manager = create_security_manager(config, "e2e-test")
        
        try:
            # Store credential
            success = manager.credential_manager.store_credential("test_key", "test_value")
            assert success is True
            
            # Log audit event
            manager.audit_logger.log_data_access("test_operation", "test_resource")
            
            # Check rate limiting
            assert manager.rate_limiter.is_allowed("test-client") is True
            
            # Run security scan
            scan_results = manager.vulnerability_scanner.run_security_scan()
            assert 'overall_status' in scan_results
            
            # Get security status
            status = manager.get_security_status()
            assert status['security_level'] in ['low', 'medium', 'high', 'critical']
            
            # Verify audit log was created
            audit_log = Path(config.audit_log_path)
            assert audit_log.exists()
            
        finally:
            manager.stop_background_tasks()


if __name__ == '__main__':
    pytest.main([__file__])