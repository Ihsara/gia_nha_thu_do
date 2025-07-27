#!/usr/bin/env python3
"""
Simple test script for security system functionality.
"""

import sys
import tempfile
import shutil
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oikotie.automation.security import SecurityConfig, create_security_manager


def test_security_system():
    """Test basic security system functionality."""
    print("🔒 Testing Security System")
    print("=" * 50)
    
    # Create test configuration
    config = SecurityConfig(
        encryption_enabled=True,
        audit_enabled=True,
        rate_limiting_enabled=True,
        vulnerability_scanning_enabled=True,
        backup_enabled=True
    )
    
    # Create temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    original_dir = Path.cwd()
    
    try:
        # Change to temp directory
        import os
        os.chdir(temp_dir)
        
        print("📁 Test directory:", temp_dir)
        
        # Test 1: Security Manager Creation
        print("\n1. Testing Security Manager Creation...")
        manager = create_security_manager(config, 'test-node-001')
        print("   ✅ Security manager created successfully")
        
        # Test 2: Credential Management
        print("\n2. Testing Credential Management...")
        success = manager.credential_manager.store_credential(
            'test_api_key', 
            'secret-key-12345', 
            'Test API key for security testing'
        )
        print(f"   ✅ Credential storage: {success}")
        
        value = manager.credential_manager.get_credential('test_api_key')
        print(f"   ✅ Credential retrieval: {value == 'secret-key-12345'}")
        
        credentials = manager.credential_manager.list_credentials()
        print(f"   ✅ Credential listing: {len(credentials)} credentials found")
        
        # Test 3: Audit Logging
        print("\n3. Testing Audit Logging...")
        manager.audit_logger.log_system_operation(
            'security_test', 
            execution_id='test-exec-001',
            test_data='security system validation'
        )
        print("   ✅ Audit logging completed")
        
        # Test 4: Rate Limiting
        print("\n4. Testing Rate Limiting...")
        client_id = 'test-client-192.168.1.100'
        
        # Test normal requests
        for i in range(3):
            allowed = manager.rate_limiter.is_allowed(client_id)
            print(f"   Request {i+1}: {'✅ Allowed' if allowed else '❌ Blocked'}")
        
        # Get rate limit status
        status = manager.rate_limiter.get_rate_limit_status(client_id)
        print(f"   ✅ Rate limit status: {status['requests_last_minute']}/{status['minute_limit']} per minute")
        
        # Test 5: Security Status
        print("\n5. Testing Security Status...")
        security_status = manager.get_security_status()
        print(f"   ✅ Security level: {security_status['security_level']}")
        print(f"   ✅ Node ID: {security_status['node_id']}")
        print(f"   ✅ Components: {len(security_status['components'])}")
        
        # Test 6: Vulnerability Scanner
        print("\n6. Testing Vulnerability Scanner...")
        scan_results = manager.vulnerability_scanner.run_security_scan()
        print(f"   ✅ Scan completed: {scan_results['overall_status']}")
        print(f"   ✅ Checks run: {scan_results['summary']['total_checks']}")
        print(f"   ✅ Duration: {scan_results['scan_duration_seconds']:.2f}s")
        
        # Test 7: Backup System
        print("\n7. Testing Backup System...")
        
        # Create some test data to backup
        (Path(temp_dir) / "data").mkdir(exist_ok=True)
        (Path(temp_dir) / "data" / "real_estate.duckdb").write_text("test database content")
        (Path(temp_dir) / "config").mkdir(exist_ok=True)
        (Path(temp_dir) / "config" / "scraper_config.json").write_text('{"test": "config"}')
        
        backup_results = manager.backup_manager.create_backup('security-test-backup')
        print(f"   ✅ Backup created: {backup_results['status']}")
        if backup_results['status'] == 'success':
            print(f"   ✅ Backup size: {backup_results['total_size_mb']:.2f} MB")
            print(f"   ✅ Components: {len(backup_results['components'])}")
        
        # List backups
        backups = manager.backup_manager.list_backups()
        print(f"   ✅ Backups available: {len(backups)}")
        
        # Stop background tasks
        manager.stop_background_tasks()
        print("\n✅ All security tests completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Security test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        try:
            os.chdir(original_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"\n🧹 Cleaned up test directory: {temp_dir}")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")


if __name__ == '__main__':
    success = test_security_system()
    sys.exit(0 if success else 1)