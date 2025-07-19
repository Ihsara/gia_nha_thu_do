"""
Security and Operational Hardening System for Daily Scraper Automation

This module provides comprehensive security features including:
- Secure credential management and configuration encryption
- Audit logging for all system operations
- Security scanning and vulnerability assessment integration
- Rate limiting and abuse prevention mechanisms
- Backup and disaster recovery procedures

Requirements: 2.5, 6.7
"""

import os
import json
import hashlib
import secrets
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum
import base64
from collections import defaultdict, deque
from loguru import logger

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    logger.warning("cryptography package not available - encryption features disabled")
    CRYPTOGRAPHY_AVAILABLE = False
    
    # Mock classes for when cryptography is not available
    class Fernet:
        def __init__(self, key): pass
        def encrypt(self, data): return data
        def decrypt(self, data): return data


class SecurityLevel(Enum):
    """Security levels for different operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEventType(Enum):
    """Types of audit events."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    CONFIGURATION_CHANGE = "configuration_change"
    SYSTEM_OPERATION = "system_operation"
    SECURITY_EVENT = "security_event"
    ERROR = "error"


class ThreatLevel(Enum):
    """Threat levels for security events."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event record."""
    timestamp: datetime
    event_type: AuditEventType
    threat_level: ThreatLevel
    user_id: Optional[str]
    session_id: Optional[str]
    source_ip: Optional[str]
    operation: str
    resource: Optional[str]
    result: str  # success, failure, error
    details: Dict[str, Any]
    node_id: str
    execution_id: Optional[str] = None


@dataclass
class SecurityConfig:
    """Security configuration settings."""
    # Encryption settings
    encryption_enabled: bool = True
    key_rotation_days: int = 90
    
    # Audit logging
    audit_enabled: bool = True
    audit_log_path: str = "logs/audit.log"
    audit_retention_days: int = 365
    
    # Rate limiting
    rate_limiting_enabled: bool = True
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    
    # Security scanning
    vulnerability_scanning_enabled: bool = True
    scan_interval_hours: int = 24
    
    # Backup settings
    backup_enabled: bool = True
    backup_interval_hours: int = 6
    backup_retention_days: int = 30
    backup_encryption_enabled: bool = True
    
    # Access control
    require_authentication: bool = False
    session_timeout_minutes: int = 60
    max_failed_attempts: int = 5
    lockout_duration_minutes: int = 30


class CredentialManager:
    """Secure credential management system."""
    
    def __init__(self, config: SecurityConfig, key_file: str = ".security/master.key"):
        """Initialize credential manager."""
        self.config = config
        self.key_file = Path(key_file)
        self.credentials_file = Path(".security/credentials.enc")
        self._master_key: Optional[bytes] = None
        self._fernet: Optional[Fernet] = None
        self._credentials: Dict[str, Any] = {}
        
        # Ensure security directory exists
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        
        if self.config.encryption_enabled and CRYPTOGRAPHY_AVAILABLE:
            self._initialize_encryption()
        
        logger.info("Credential manager initialized")
    
    def _initialize_encryption(self) -> None:
        """Initialize encryption system."""
        if not CRYPTOGRAPHY_AVAILABLE:
            logger.warning("Cryptography not available - credentials will not be encrypted")
            return
        
        # Load or generate master key
        if self.key_file.exists():
            self._load_master_key()
        else:
            self._generate_master_key()
        
        # Initialize Fernet cipher
        if self._master_key:
            self._fernet = Fernet(self._master_key)
            logger.info("Encryption system initialized")
    
    def _generate_master_key(self) -> None:
        """Generate and save master encryption key."""
        if not CRYPTOGRAPHY_AVAILABLE:
            return
        
        # Generate key
        key = Fernet.generate_key()
        
        # Save key with restricted permissions
        self.key_file.write_bytes(key)
        os.chmod(self.key_file, 0o600)  # Owner read/write only
        
        self._master_key = key
        logger.info(f"Generated new master key: {self.key_file}")
    
    def _load_master_key(self) -> None:
        """Load master encryption key."""
        try:
            self._master_key = self.key_file.read_bytes()
            logger.info("Loaded master encryption key")
        except Exception as e:
            logger.error(f"Failed to load master key: {e}")
            raise
    
    def store_credential(self, key: str, value: Union[str, Dict[str, Any]], 
                        description: Optional[str] = None) -> bool:
        """Store a credential securely."""
        try:
            credential_data = {
                'value': value,
                'description': description,
                'created_at': datetime.now().isoformat(),
                'last_accessed': None
            }
            
            self._credentials[key] = credential_data
            self._save_credentials()
            
            logger.info(f"Stored credential: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store credential {key}: {e}")
            return False
    
    def get_credential(self, key: str) -> Optional[Union[str, Dict[str, Any]]]:
        """Retrieve a credential."""
        try:
            if not self._credentials:
                self._load_credentials()
            
            if key in self._credentials:
                # Update last accessed time
                self._credentials[key]['last_accessed'] = datetime.now().isoformat()
                self._save_credentials()
                
                return self._credentials[key]['value']
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve credential {key}: {e}")
            return None
    
    def delete_credential(self, key: str) -> bool:
        """Delete a credential."""
        try:
            if key in self._credentials:
                del self._credentials[key]
                self._save_credentials()
                logger.info(f"Deleted credential: {key}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete credential {key}: {e}")
            return False
    
    def list_credentials(self) -> List[Dict[str, Any]]:
        """List all stored credentials (without values)."""
        try:
            if not self._credentials:
                self._load_credentials()
            
            return [
                {
                    'key': key,
                    'description': data.get('description'),
                    'created_at': data.get('created_at'),
                    'last_accessed': data.get('last_accessed')
                }
                for key, data in self._credentials.items()
            ]
            
        except Exception as e:
            logger.error(f"Failed to list credentials: {e}")
            return []
    
    def _save_credentials(self) -> None:
        """Save credentials to encrypted file."""
        try:
            # Serialize credentials
            data = json.dumps(self._credentials, indent=2).encode('utf-8')
            
            # Encrypt if available
            if self._fernet and self.config.encryption_enabled:
                encrypted_data = self._fernet.encrypt(data)
                self.credentials_file.write_bytes(encrypted_data)
            else:
                self.credentials_file.write_bytes(data)
            
            # Set restrictive permissions
            os.chmod(self.credentials_file, 0o600)
            
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            raise
    
    def _load_credentials(self) -> None:
        """Load credentials from encrypted file."""
        try:
            if not self.credentials_file.exists():
                self._credentials = {}
                return
            
            # Read encrypted data
            encrypted_data = self.credentials_file.read_bytes()
            
            # Decrypt if available
            if self._fernet and self.config.encryption_enabled:
                try:
                    data = self._fernet.decrypt(encrypted_data)
                except Exception as e:
                    logger.error(f"Failed to decrypt credentials: {e}")
                    # Try to read as plain text (fallback)
                    data = encrypted_data
            else:
                data = encrypted_data
            
            # Deserialize
            self._credentials = json.loads(data.decode('utf-8'))
            
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            self._credentials = {}
    
    def rotate_master_key(self) -> bool:
        """Rotate the master encryption key."""
        if not CRYPTOGRAPHY_AVAILABLE or not self.config.encryption_enabled:
            logger.warning("Key rotation not available - encryption disabled")
            return False
        
        try:
            # Load current credentials
            self._load_credentials()
            
            # Generate new key
            old_key_file = self.key_file.with_suffix('.old')
            self.key_file.rename(old_key_file)
            
            self._generate_master_key()
            self._fernet = Fernet(self._master_key)
            
            # Re-encrypt credentials with new key
            self._save_credentials()
            
            # Remove old key file
            old_key_file.unlink()
            
            logger.info("Master key rotated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rotate master key: {e}")
            return False


class AuditLogger:
    """Comprehensive audit logging system."""
    
    def __init__(self, config: SecurityConfig, node_id: str):
        """Initialize audit logger."""
        self.config = config
        self.node_id = node_id
        self.audit_log_path = Path(config.audit_log_path)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Audit logger initialized: {self.audit_log_path}")
    
    def log_event(self, 
                  event_type: AuditEventType,
                  operation: str,
                  result: str = "success",
                  threat_level: ThreatLevel = ThreatLevel.INFO,
                  user_id: Optional[str] = None,
                  session_id: Optional[str] = None,
                  source_ip: Optional[str] = None,
                  resource: Optional[str] = None,
                  execution_id: Optional[str] = None,
                  **details) -> None:
        """Log an audit event."""
        if not self.config.audit_enabled:
            return
        
        try:
            event = AuditEvent(
                timestamp=datetime.now(),
                event_type=event_type,
                threat_level=threat_level,
                user_id=user_id,
                session_id=session_id,
                source_ip=source_ip,
                operation=operation,
                resource=resource,
                result=result,
                details=details,
                node_id=self.node_id,
                execution_id=execution_id
            )
            
            # Log as structured JSON
            event_data = asdict(event)
            event_data['timestamp'] = event.timestamp.isoformat()
            event_data['event_type'] = event.event_type.value
            event_data['threat_level'] = event.threat_level.value
            
            # Write to audit log file
            with open(self.audit_log_path, 'a') as f:
                f.write(json.dumps(event_data) + '\n')
            
            # Log high-threat events to main logger as well
            if threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                logger.warning(f"Security event: {operation} - {result} (Threat: {threat_level.value})")
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
    
    def log_authentication(self, user_id: str, result: str, source_ip: Optional[str] = None, **details) -> None:
        """Log authentication event."""
        threat_level = ThreatLevel.HIGH if result == "failure" else ThreatLevel.INFO
        self.log_event(
            AuditEventType.AUTHENTICATION,
            "user_authentication",
            result=result,
            threat_level=threat_level,
            user_id=user_id,
            source_ip=source_ip,
            **details
        )
    
    def log_data_access(self, operation: str, resource: str, user_id: Optional[str] = None, 
                       execution_id: Optional[str] = None, **details) -> None:
        """Log data access event."""
        self.log_event(
            AuditEventType.DATA_ACCESS,
            operation,
            resource=resource,
            user_id=user_id,
            execution_id=execution_id,
            **details
        )
    
    def log_configuration_change(self, operation: str, resource: str, user_id: Optional[str] = None, **details) -> None:
        """Log configuration change event."""
        self.log_event(
            AuditEventType.CONFIGURATION_CHANGE,
            operation,
            resource=resource,
            threat_level=ThreatLevel.MEDIUM,
            user_id=user_id,
            **details
        )
    
    def log_system_operation(self, operation: str, execution_id: Optional[str] = None, **details) -> None:
        """Log system operation event."""
        self.log_event(
            AuditEventType.SYSTEM_OPERATION,
            operation,
            execution_id=execution_id,
            **details
        )
    
    def log_security_event(self, operation: str, threat_level: ThreatLevel = ThreatLevel.MEDIUM, **details) -> None:
        """Log security-related event."""
        self.log_event(
            AuditEventType.SECURITY_EVENT,
            operation,
            threat_level=threat_level,
            **details
        )
    
    def log_error(self, operation: str, error: str, execution_id: Optional[str] = None, **details) -> None:
        """Log error event."""
        self.log_event(
            AuditEventType.ERROR,
            operation,
            result="error",
            threat_level=ThreatLevel.LOW,
            execution_id=execution_id,
            error=error,
            **details
        )


class RateLimiter:
    """Rate limiting and abuse prevention system."""
    
    def __init__(self, config: SecurityConfig):
        """Initialize rate limiter."""
        self.config = config
        self.request_counts: Dict[str, deque] = defaultdict(lambda: deque())
        self.blocked_ips: Dict[str, datetime] = {}
        self.lock = threading.Lock()
        
        logger.info("Rate limiter initialized")
    
    def is_allowed(self, identifier: str, operation: str = "default") -> bool:
        """Check if request is allowed based on rate limits."""
        if not self.config.rate_limiting_enabled:
            return True
        
        with self.lock:
            # Check if identifier is blocked
            if identifier in self.blocked_ips:
                if datetime.now() < self.blocked_ips[identifier]:
                    return False
                else:
                    # Unblock expired blocks
                    del self.blocked_ips[identifier]
            
            current_time = datetime.now()
            
            # Clean old requests (older than 1 hour)
            cutoff_time = current_time - timedelta(hours=1)
            request_times = self.request_counts[identifier]
            
            while request_times and request_times[0] < cutoff_time:
                request_times.popleft()
            
            # Check minute limit
            minute_cutoff = current_time - timedelta(minutes=1)
            minute_requests = sum(1 for t in request_times if t >= minute_cutoff)
            
            if minute_requests >= self.config.max_requests_per_minute:
                self._block_identifier(identifier, "rate_limit_minute")
                return False
            
            # Check hour limit
            if len(request_times) >= self.config.max_requests_per_hour:
                self._block_identifier(identifier, "rate_limit_hour")
                return False
            
            # Record this request
            request_times.append(current_time)
            return True
    
    def _block_identifier(self, identifier: str, reason: str) -> None:
        """Block an identifier for abuse prevention."""
        block_until = datetime.now() + timedelta(minutes=30)  # 30-minute block
        self.blocked_ips[identifier] = block_until
        
        logger.warning(f"Blocked identifier {identifier} for {reason} until {block_until}")
    
    def get_rate_limit_status(self, identifier: str) -> Dict[str, Any]:
        """Get rate limit status for an identifier."""
        with self.lock:
            current_time = datetime.now()
            request_times = self.request_counts.get(identifier, deque())
            
            # Count recent requests
            minute_cutoff = current_time - timedelta(minutes=1)
            hour_cutoff = current_time - timedelta(hours=1)
            
            minute_requests = sum(1 for t in request_times if t >= minute_cutoff)
            hour_requests = len(request_times)
            
            # Check if blocked
            is_blocked = identifier in self.blocked_ips
            block_expires = self.blocked_ips.get(identifier)
            
            return {
                'identifier': identifier,
                'requests_last_minute': minute_requests,
                'requests_last_hour': hour_requests,
                'minute_limit': self.config.max_requests_per_minute,
                'hour_limit': self.config.max_requests_per_hour,
                'is_blocked': is_blocked,
                'block_expires': block_expires.isoformat() if block_expires else None,
                'remaining_minute': max(0, self.config.max_requests_per_minute - minute_requests),
                'remaining_hour': max(0, self.config.max_requests_per_hour - hour_requests)
            }


# Import scanner and backup manager locally to avoid circular imports
from .security_scanner import VulnerabilityScanner
from .backup_manager import BackupManager


class SecurityManager:
    """Comprehensive security management system."""
    
    def __init__(self, config: SecurityConfig, node_id: str):
        """Initialize security manager."""
        self.config = config
        self.node_id = node_id
        
        # Initialize components
        self.credential_manager = CredentialManager(config)
        self.audit_logger = AuditLogger(config, node_id)
        self.rate_limiter = RateLimiter(config)
        self.vulnerability_scanner = VulnerabilityScanner(config)
        self.backup_manager = BackupManager(config, self.credential_manager)
        
        # Background tasks
        self._background_tasks_running = False
        self._background_thread: Optional[threading.Thread] = None
        
        logger.info("Security manager initialized")
    
    def start_background_tasks(self) -> None:
        """Start background security tasks."""
        if self._background_tasks_running:
            logger.warning("Background security tasks already running")
            return
        
        self._background_tasks_running = True
        self._background_thread = threading.Thread(target=self._background_task_loop, daemon=True)
        self._background_thread.start()
        
        logger.info("Background security tasks started")
    
    def stop_background_tasks(self) -> None:
        """Stop background security tasks."""
        self._background_tasks_running = False
        if self._background_thread and self._background_thread.is_alive():
            self._background_thread.join(timeout=5)
        
        logger.info("Background security tasks stopped")
    
    def _background_task_loop(self) -> None:
        """Background task execution loop."""
        while self._background_tasks_running:
            try:
                # Run security scan if needed
                if self.vulnerability_scanner.should_run_scan():
                    scan_results = self.vulnerability_scanner.run_security_scan()
                    self.audit_logger.log_security_event(
                        "vulnerability_scan_completed",
                        threat_level=ThreatLevel.INFO,
                        scan_status=scan_results['overall_status'],
                        critical_issues=scan_results['summary']['critical']
                    )
                
                # Create backup if needed
                if self._should_create_backup():
                    backup_results = self.backup_manager.create_backup()
                    self.audit_logger.log_system_operation(
                        "backup_created",
                        backup_status=backup_results['status'],
                        backup_size_mb=backup_results.get('total_size_mb', 0)
                    )
                
                # Cleanup old backups
                if self._should_cleanup_backups():
                    cleanup_results = self.backup_manager.cleanup_old_backups()
                    self.audit_logger.log_system_operation(
                        "backup_cleanup",
                        deleted_count=len(cleanup_results.get('deleted_backups', [])),
                        errors=len(cleanup_results.get('errors', []))
                    )
                
                # Sleep for 1 hour between checks
                time.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in background security tasks: {e}")
                self.audit_logger.log_error("background_security_task", str(e))
                time.sleep(300)  # Sleep 5 minutes on error
    
    def _should_create_backup(self) -> bool:
        """Check if a backup should be created."""
        if not self.config.backup_enabled:
            return False
        
        # Check if enough time has passed since last backup
        backups = self.backup_manager.list_backups()
        if not backups:
            return True
        
        latest_backup = backups[0]
        if 'created_at' in latest_backup:
            try:
                last_backup_time = datetime.fromisoformat(latest_backup['created_at'].replace('Z', '+00:00'))
                next_backup_time = last_backup_time + timedelta(hours=self.config.backup_interval_hours)
                return datetime.now() >= next_backup_time
            except Exception:
                return True
        
        return True
    
    def _should_cleanup_backups(self) -> bool:
        """Check if backup cleanup should be performed."""
        # Run cleanup once per day
        return True  # Simplified - in production, you'd track last cleanup time
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get comprehensive security status."""
        status = {
            'timestamp': datetime.now().isoformat(),
            'node_id': self.node_id,
            'security_level': 'medium',  # Default
            'components': {}
        }
        
        # Credential manager status
        status['components']['credential_manager'] = {
            'encryption_enabled': self.config.encryption_enabled and CRYPTOGRAPHY_AVAILABLE,
            'credentials_count': len(self.credential_manager.list_credentials())
        }
        
        # Audit logging status
        status['components']['audit_logging'] = {
            'enabled': self.config.audit_enabled,
            'log_file': str(self.audit_logger.audit_log_path)
        }
        
        # Rate limiting status
        status['components']['rate_limiting'] = {
            'enabled': self.config.rate_limiting_enabled,
            'blocked_identifiers': len(self.rate_limiter.blocked_ips)
        }
        
        # Vulnerability scanning status
        latest_scan = self.vulnerability_scanner.get_latest_scan_results()
        status['components']['vulnerability_scanning'] = {
            'enabled': self.config.vulnerability_scanning_enabled,
            'last_scan': latest_scan['timestamp'] if latest_scan else None,
            'last_scan_status': latest_scan['overall_status'] if latest_scan else None
        }
        
        # Backup status
        backups = self.backup_manager.list_backups()
        status['components']['backup'] = {
            'enabled': self.config.backup_enabled,
            'backup_count': len(backups),
            'latest_backup': backups[0]['created_at'] if backups else None
        }
        
        # Determine overall security level
        if latest_scan and latest_scan['overall_status'] == 'critical':
            status['security_level'] = 'critical'
        elif not self.config.encryption_enabled or not self.config.audit_enabled:
            status['security_level'] = 'low'
        elif self.config.vulnerability_scanning_enabled and self.config.backup_enabled:
            status['security_level'] = 'high'
        
        return status


def create_security_manager(config: Optional[SecurityConfig] = None, node_id: Optional[str] = None) -> SecurityManager:
    """Create and configure security manager."""
    if config is None:
        config = SecurityConfig()
    
    if node_id is None:
        node_id = f"node-{secrets.token_hex(4)}"
    
    manager = SecurityManager(config, node_id)
    manager.start_background_tasks()
    
    logger.info(f"Security manager created for node {node_id}")
    return manager