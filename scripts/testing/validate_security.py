"""Validate security system implementation."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_imports():
    """Test that all security modules can be imported."""
    try:
        from oikotie.automation.security import (
            SecurityConfig, SecurityManager, CredentialManager, 
            AuditLogger, RateLimiter, create_security_manager
        )
        from oikotie.automation.security_scanner import VulnerabilityScanner
        from oikotie.automation.backup_manager import BackupManager
        from oikotie.automation.security_cli import security_cli
        print("✅ All security modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_config():
    """Test security configuration."""
    try:
        from oikotie.automation.security import SecurityConfig
        
        # Test default config
        config = SecurityConfig()
        assert config.encryption_enabled is True
        assert config.audit_enabled is True
        assert config.rate_limiting_enabled is True
        
        # Test custom config
        custom_config = SecurityConfig(
            encryption_enabled=False,
            max_requests_per_minute=30
        )
        assert custom_config.encryption_enabled is False
        assert custom_config.max_requests_per_minute == 30
        
        print("✅ Security configuration tests passed")
        return True
    except Exception as e:
        print(f"❌ Configuration test error: {e}")
        return False

def test_basic_functionality():
    """Test basic security functionality without file operations."""
    try:
        from oikotie.automation.security import SecurityConfig, RateLimiter
        
        # Test rate limiter
        config = SecurityConfig(rate_limiting_enabled=True, max_requests_per_minute=5)
        limiter = RateLimiter(config)
        
        # Should allow initial requests
        assert limiter.is_allowed("test-client") is True
        assert limiter.is_allowed("test-client") is True
        
        # Get status
        status = limiter.get_rate_limit_status("test-client")
        assert status['requests_last_minute'] == 2
        assert status['minute_limit'] == 5
        
        print("✅ Basic functionality tests passed")
        return True
    except Exception as e:
        print(f"❌ Basic functionality test error: {e}")
        return False

def main():
    """Run all validation tests."""
    print("🔒 Validating Security System Implementation")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Configuration Tests", test_config),
        ("Basic Functionality Tests", test_basic_functionality),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All security validation tests passed!")
        return True
    else:
        print("⚠️  Some security validation tests failed")
        return False

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)