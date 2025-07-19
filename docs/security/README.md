# Security and Operational Hardening

This document describes the comprehensive security and operational hardening features implemented for the Oikotie Daily Scraper Automation system.

## Overview

The security system provides multiple layers of protection and operational safeguards:

- **Secure Credential Management**: Encrypted storage and management of sensitive credentials
- **Comprehensive Audit Logging**: Detailed logging of all system operations and security events
- **Rate Limiting and Abuse Prevention**: Protection against excessive requests and abuse
- **Vulnerability Scanning**: Automated security assessments and recommendations
- **Backup and Disaster Recovery**: Automated backups with encryption and retention policies

## Components

### 1. Credential Manager

Securely stores and manages sensitive credentials using encryption.

**Features:**
- AES encryption using Fernet (cryptography library)
- Master key generation and rotation
- Secure file permissions (600)
- Credential metadata tracking
- Access logging

**Usage:**
```bash
# Store a credential
uv run python -m oikotie.automation.cli security credentials store api_key "your-secret-key" --description "API key for external service"

# Retrieve a credential
uv run python -m oikotie.automation.cli security credentials get api_key

# List all credentials
uv run python -m oikotie.automation.cli security credentials list

# Delete a credential
uv run python -m oikotie.automation.cli security credentials delete api_key

# Rotate master key
uv run python -m oikotie.automation.cli security credentials rotate-key
```

### 2. Audit Logger

Comprehensive logging of all system operations and security events.

**Event Types:**
- Authentication events
- Data access operations
- Configuration changes
- System operations
- Security events
- Error conditions

**Features:**
- Structured JSON logging
- Configurable retention periods
- Threat level classification
- Automatic log rotation
- Tamper-evident logging

**Log Format:**
```json
{
  "timestamp": "2025-01-19T10:30:00.123Z",
  "event_type": "data_access",
  "threat_level": "info",
  "operation": "database_query",
  "resource": "listings_table",
  "result": "success",
  "node_id": "scraper-node-001",
  "execution_id": "exec-20250119-103000",
  "details": {
    "query_type": "SELECT",
    "rows_affected": 150
  }
}
```

### 3. Rate Limiter

Protects against abuse and excessive requests.

**Features:**
- Per-minute and per-hour rate limits
- IP-based blocking
- Configurable thresholds
- Automatic unblocking
- Rate limit status reporting

**Configuration:**
```json
{
  "rate_limiting": {
    "enabled": true,
    "max_requests_per_minute": 60,
    "max_requests_per_hour": 1000,
    "block_duration_minutes": 30
  }
}
```

### 4. Vulnerability Scanner

Automated security assessments and vulnerability detection.

**Scan Categories:**
- File permissions
- Configuration security
- Dependency vulnerabilities
- Network security
- Database security

**Usage:**
```bash
# Run security scan
uv run python -m oikotie.automation.cli security scan run

# Show scan status
uv run python -m oikotie.automation.cli security scan status

# Save scan results to file
uv run python -m oikotie.automation.cli security scan run --output security-report.json --format json
```

**Sample Scan Results:**
```json
{
  "scan_id": "scan-abc123",
  "timestamp": "2025-01-19T10:30:00Z",
  "overall_status": "warning",
  "summary": {
    "total_checks": 5,
    "passed": 3,
    "warnings": 2,
    "failures": 0,
    "critical": 0
  },
  "checks": {
    "file_permissions": {
      "status": "warning",
      "message": "Some files have overly permissive permissions",
      "recommendations": ["Restrict permissions for config files"]
    }
  }
}
```

### 5. Backup Manager

Automated backup and disaster recovery system.

**Features:**
- Scheduled automatic backups
- Component-based backup (database, config, logs, security data)
- Backup encryption
- Retention policy enforcement
- Backup verification

**Components Backed Up:**
- Database files (`data/real_estate.duckdb`)
- Configuration files (`config/*.json`)
- Recent log files (last 7 days)
- Security data (encrypted credentials)

**Usage:**
```bash
# Create backup
uv run python -m oikotie.automation.cli security backup create --name manual-backup-20250119

# List backups
uv run python -m oikotie.automation.cli security backup list

# Clean up old backups
uv run python -m oikotie.automation.cli security backup cleanup
```

## Configuration

### Security Configuration File

Create a security configuration file at `config/security_config.json`:

```json
{
  "security": {
    "encryption": {
      "enabled": true,
      "key_rotation_days": 90
    },
    "audit_logging": {
      "enabled": true,
      "log_path": "logs/audit.log",
      "retention_days": 365
    },
    "rate_limiting": {
      "enabled": true,
      "max_requests_per_minute": 60,
      "max_requests_per_hour": 1000
    },
    "vulnerability_scanning": {
      "enabled": true,
      "scan_interval_hours": 24
    },
    "backup": {
      "enabled": true,
      "interval_hours": 6,
      "retention_days": 30,
      "encryption_enabled": true
    }
  }
}
```

### Environment Variables

Security settings can be overridden using environment variables:

```bash
export SECURITY_ENCRYPTION_ENABLED=true
export SECURITY_AUDIT_ENABLED=true
export SECURITY_RATE_LIMITING_ENABLED=true
export SECURITY_BACKUP_ENABLED=true
export SECURITY_VULNERABILITY_SCANNING_ENABLED=true
```

## Security Best Practices

### 1. File Permissions

Ensure proper file permissions for sensitive files:

```bash
# Security files
chmod 600 .security/master.key
chmod 600 .security/credentials.enc

# Configuration files
chmod 600 config/scraper_config.json
chmod 600 config/security_config.json

# Database files
chmod 600 data/real_estate.duckdb

# Log files
chmod 640 logs/audit.log
```

### 2. Network Security

- Bind services to localhost only in production
- Use TLS for external communications
- Implement firewall rules to restrict access
- Monitor network connections

### 3. Access Control

- Use strong passwords for any authentication
- Implement session timeouts
- Monitor failed authentication attempts
- Use principle of least privilege

### 4. Data Protection

- Encrypt sensitive data at rest
- Use secure communication channels
- Implement data retention policies
- Regular security audits

## Monitoring and Alerting

### Security Status

Check overall security status:

```bash
uv run python -m oikotie.automation.cli security status
```

### Security Metrics

The security system exposes metrics for monitoring:

- `security_events_total`: Total security events by type and threat level
- `credential_operations_total`: Credential management operations
- `rate_limit_blocks_total`: Rate limiting blocks by identifier
- `vulnerability_scan_results`: Latest scan results
- `backup_operations_total`: Backup operations by status

### Alerting

Configure alerts for security events:

- Critical vulnerability scan results
- Failed authentication attempts
- Rate limiting violations
- Backup failures
- Audit log tampering

## Incident Response

### Security Event Response

1. **Detection**: Monitor audit logs and security metrics
2. **Assessment**: Analyze threat level and impact
3. **Containment**: Block malicious IPs, disable compromised credentials
4. **Investigation**: Review audit logs, scan for vulnerabilities
5. **Recovery**: Restore from backups if necessary
6. **Documentation**: Update security procedures

### Backup Recovery

To restore from backup:

1. Stop the automation system
2. Identify the backup to restore from
3. Extract backup files to appropriate locations
4. Verify data integrity
5. Restart the system
6. Validate functionality

## Compliance

### Audit Requirements

The security system supports compliance with:

- Data protection regulations (GDPR, etc.)
- Security frameworks (OWASP, NIST)
- Industry standards (ISO 27001)

### Audit Trail

All security-relevant operations are logged with:

- Timestamp
- User/system identifier
- Operation performed
- Resource accessed
- Result (success/failure)
- Additional context

## Troubleshooting

### Common Issues

1. **Encryption Key Issues**
   ```bash
   # Regenerate master key (will lose existing credentials)
   rm .security/master.key
   uv run python -m oikotie.automation.cli security credentials rotate-key
   ```

2. **Audit Log Permissions**
   ```bash
   # Fix audit log permissions
   chmod 640 logs/audit.log
   chown scraper:scraper logs/audit.log
   ```

3. **Rate Limiting False Positives**
   ```bash
   # Check rate limit status
   uv run python -m oikotie.automation.cli security status
   
   # Adjust rate limits in configuration
   ```

4. **Backup Failures**
   ```bash
   # Check disk space
   df -h
   
   # Check backup directory permissions
   ls -la backups/
   
   # Manual backup creation
   uv run python -m oikotie.automation.cli security backup create
   ```

### Debug Mode

Enable debug logging for security components:

```bash
export LOG_LEVEL=DEBUG
uv run python -m oikotie.automation.cli --log-level DEBUG security status
```

## Integration

### With Existing Systems

The security system integrates with:

- **Monitoring**: Prometheus metrics and health checks
- **Alerting**: Integration with existing alert systems
- **Logging**: Structured logs compatible with log aggregation systems
- **Deployment**: Docker and Kubernetes security contexts

### API Integration

Security components can be used programmatically:

```python
from oikotie.automation.security import create_security_manager, SecurityConfig

# Create security manager
config = SecurityConfig(
    encryption_enabled=True,
    audit_enabled=True,
    rate_limiting_enabled=True
)
security_manager = create_security_manager(config, "my-node")

# Store credential
security_manager.credential_manager.store_credential("api_key", "secret")

# Log audit event
security_manager.audit_logger.log_data_access("query", "database")

# Check rate limit
allowed = security_manager.rate_limiter.is_allowed("client-ip")

# Run security scan
scan_results = security_manager.vulnerability_scanner.run_security_scan()

# Create backup
backup_results = security_manager.backup_manager.create_backup()
```

## Updates and Maintenance

### Regular Tasks

1. **Weekly**
   - Review security scan results
   - Check backup integrity
   - Monitor audit logs for anomalies

2. **Monthly**
   - Rotate encryption keys
   - Update vulnerability databases
   - Review and update security policies

3. **Quarterly**
   - Comprehensive security audit
   - Penetration testing
   - Update security documentation

### Version Updates

When updating the security system:

1. Review changelog for security implications
2. Test in staging environment
3. Backup current configuration
4. Update dependencies
5. Run security scan after update
6. Monitor for issues

## Support

For security-related issues:

1. Check this documentation
2. Review audit logs
3. Run security diagnostics
4. Contact security team if needed

**Emergency Contact**: For critical security incidents, follow your organization's incident response procedures.