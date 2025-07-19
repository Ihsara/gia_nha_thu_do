# Troubleshooting Guide and Operational Runbooks

This comprehensive guide provides troubleshooting procedures and operational runbooks for the Oikotie Daily Scraper Automation system.

## Table of Contents

1. [Quick Diagnostic Commands](#quick-diagnostic-commands)
2. [Common Issues and Solutions](#common-issues-and-solutions)
3. [Operational Runbooks](#operational-runbooks)
4. [Performance Troubleshooting](#performance-troubleshooting)
5. [Security Incident Response](#security-incident-response)
6. [Disaster Recovery Procedures](#disaster-recovery-procedures)
7. [Monitoring and Alerting](#monitoring-and-alerting)
8. [Escalation Procedures](#escalation-procedures)

## Quick Diagnostic Commands

### System Health Check

```bash
# Quick health check script
#!/bin/bash
echo "=== Oikotie Scraper Health Check ==="

# Check if service is running
if docker ps | grep -q oikotie-scraper; then
    echo "✅ Container is running"
else
    echo "❌ Container is not running"
fi

# Check health endpoint
if curl -f http://localhost:8080/health >/dev/null 2>&1; then
    echo "✅ Health endpoint responding"
else
    echo "❌ Health endpoint not responding"
fi

# Check database
if [ -f "data/real_estate.duckdb" ]; then
    echo "✅ Database file exists"
    echo "📊 Database size: $(du -h data/real_estate.duckdb | cut -f1)"
else
    echo "❌ Database file missing"
fi

# Check logs for errors
ERROR_COUNT=$(docker logs oikotie-scraper 2>&1 | grep -c "ERROR\|CRITICAL" || echo "0")
echo "⚠️  Recent errors: $ERROR_COUNT"

# Check disk space
DISK_USAGE=$(df -h . | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "⚠️  Disk usage high: ${DISK_USAGE}%"
else
    echo "✅ Disk usage OK: ${DISK_USAGE}%"
fi
```

### Kubernetes Diagnostic Commands

```bash
# Kubernetes health check
kubectl get pods -n oikotie-scraper
kubectl get services -n oikotie-scraper
kubectl get pvc -n oikotie-scraper

# Check pod status
kubectl describe pod -l app=oikotie-scraper -n oikotie-scraper

# View recent logs
kubectl logs -l app=oikotie-scraper -n oikotie-scraper --tail=100

# Check resource usage
kubectl top pods -n oikotie-scraper
kubectl top nodes
```

### Database Diagnostic Commands

```bash
# Check database integrity
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
print('Tables:', conn.execute('SHOW TABLES').fetchall())
print('Listings count:', conn.execute('SELECT COUNT(*) FROM listings').fetchone()[0])
conn.close()
"

# Check recent data
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
result = conn.execute('SELECT COUNT(*) FROM listings WHERE created_at > NOW() - INTERVAL 24 HOURS').fetchone()
print(f'Listings added in last 24h: {result[0]}')
conn.close()
"
```

## Common Issues and Solutions

### 1. Container Won't Start

#### Symptoms
- Container exits immediately
- Health check fails
- No response from application

#### Diagnostic Steps
```bash
# Check container logs
docker logs oikotie-scraper

# Check container status
docker ps -a | grep oikotie-scraper

# Inspect container configuration
docker inspect oikotie-scraper
```

#### Common Causes and Solutions

**Cause: Database file permissions**
```bash
# Solution: Fix permissions
sudo chown -R 1000:1000 data/
chmod 755 data/
chmod 644 data/real_estate.duckdb
```

**Cause: Missing configuration file**
```bash
# Solution: Create configuration
cp config/config.json.template config/config.json
# Edit configuration as needed
```

**Cause: Port already in use**
```bash
# Solution: Check port usage
netstat -tulpn | grep :8080
# Kill process or change port in configuration
```

**Cause: Insufficient memory**
```bash
# Solution: Increase memory limits
docker run --memory=2g oikotie-scraper:latest
# Or reduce MAX_WORKERS in configuration
```

### 2. Scraping Failures

#### Symptoms
- No new listings being processed
- High error rates in logs
- Timeout errors

#### Diagnostic Steps
```bash
# Check recent scraping activity
docker logs oikotie-scraper | grep "listings processed"

# Check for network errors
docker logs oikotie-scraper | grep -i "network\|timeout\|connection"

# Test network connectivity
docker exec oikotie-scraper curl -I https://asunnot.oikotie.fi
```

#### Solutions

**Network connectivity issues:**
```bash
# Check DNS resolution
docker exec oikotie-scraper nslookup asunnot.oikotie.fi

# Test with different DNS
docker run --dns=8.8.8.8 oikotie-scraper:latest

# Check proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

**Rate limiting:**
```json
{
  "scraping": {
    "rate_limit_delay": 2.0,
    "request_timeout": 45,
    "retry_limit": 5
  }
}
```

**Browser automation issues:**
```bash
# Check Chrome installation
docker exec oikotie-scraper google-chrome --version

# Test headless mode
docker exec oikotie-scraper python -c "
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
options = Options()
options.add_argument('--headless')
driver = webdriver.Chrome(options=options)
driver.get('https://google.com')
print('Browser test successful')
driver.quit()
"
```

### 3. Database Issues

#### Symptoms
- Database connection errors
- Slow query performance
- Database corruption

#### Diagnostic Steps
```bash
# Check database file
ls -la data/real_estate.duckdb*

# Test database connection
uv run python -c "
import duckdb
try:
    conn = duckdb.connect('data/real_estate.duckdb')
    print('Connection successful')
    conn.close()
except Exception as e:
    print(f'Connection failed: {e}')
"

# Check database integrity
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
conn.execute('PRAGMA integrity_check')
print('Integrity check passed')
conn.close()
"
```

#### Solutions

**Database locked:**
```bash
# Find processes using database
lsof data/real_estate.duckdb

# Kill blocking processes
kill -9 <PID>

# Restart application
docker restart oikotie-scraper
```

**Database corruption:**
```bash
# Backup current database
cp data/real_estate.duckdb data/real_estate_backup.duckdb

# Try to repair
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
conn.execute('VACUUM')
conn.close()
"

# If repair fails, restore from backup
cp backups/real_estate_latest.duckdb data/real_estate.duckdb
```

**Slow performance:**
```bash
# Analyze query performance
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
conn.execute('PRAGMA enable_profiling')
conn.execute('SELECT COUNT(*) FROM listings WHERE created_at > NOW() - INTERVAL 7 DAYS')
conn.close()
"

# Optimize database
uv run python -c "
import duckdb
conn = duckdb.connect('data/real_estate.duckdb')
conn.execute('ANALYZE')
conn.execute('VACUUM')
conn.close()
"
```

### 4. Memory Issues

#### Symptoms
- Out of memory errors
- Container restarts
- Slow performance

#### Diagnostic Steps
```bash
# Check memory usage
docker stats oikotie-scraper

# Check system memory
free -h

# Check for memory leaks
docker exec oikotie-scraper ps aux --sort=-%mem | head -10
```

#### Solutions

**Reduce memory usage:**
```json
{
  "deployment": {
    "max_workers": 2,
    "memory_limit_mb": 1024
  },
  "scraping": {
    "batch_size": 25,
    "concurrent_requests": 3
  }
}
```

**Increase memory limits:**
```yaml
# docker-compose.yml
services:
  scraper:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

**Enable memory monitoring:**
```json
{
  "monitoring": {
    "memory_monitoring": true,
    "memory_threshold": 0.8,
    "gc_enabled": true
  }
}
```

### 5. Kubernetes-Specific Issues

#### Pod Stuck in Pending State

```bash
# Check pod events
kubectl describe pod <pod-name> -n oikotie-scraper

# Check node resources
kubectl describe nodes

# Check PVC status
kubectl get pvc -n oikotie-scraper
```

**Solutions:**
```bash
# Scale down and up
kubectl scale deployment oikotie-scraper --replicas=0 -n oikotie-scraper
kubectl scale deployment oikotie-scraper --replicas=3 -n oikotie-scraper

# Check resource quotas
kubectl describe resourcequota -n oikotie-scraper
```

#### Pod CrashLoopBackOff

```bash
# Check pod logs
kubectl logs <pod-name> -n oikotie-scraper --previous

# Check liveness probe
kubectl describe pod <pod-name> -n oikotie-scraper | grep -A 10 "Liveness"
```

**Solutions:**
```yaml
# Adjust probe settings
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 120  # Increase delay
  periodSeconds: 60         # Increase period
  timeoutSeconds: 30        # Increase timeout
```

## Operational Runbooks

### Daily Operations Checklist

#### Morning Health Check (5 minutes)
```bash
#!/bin/bash
# Daily health check script

echo "=== Daily Oikotie Scraper Health Check ==="
date

# 1. Check service status
kubectl get pods -n oikotie-scraper | grep -v Running && echo "⚠️ Pods not running"

# 2. Check recent scraping activity
RECENT_LISTINGS=$(kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -c "
import duckdb
conn = duckdb.connect('/shared/real_estate.duckdb')
result = conn.execute('SELECT COUNT(*) FROM listings WHERE created_at > NOW() - INTERVAL 24 HOURS').fetchone()
print(result[0])
conn.close()
")

echo "📊 Listings processed in last 24h: $RECENT_LISTINGS"

if [ "$RECENT_LISTINGS" -lt 100 ]; then
    echo "⚠️ Low scraping activity - investigate"
fi

# 3. Check error rates
ERROR_COUNT=$(kubectl logs deployment/oikotie-scraper -n oikotie-scraper --since=24h | grep -c "ERROR\|CRITICAL")
echo "⚠️ Errors in last 24h: $ERROR_COUNT"

# 4. Check disk usage
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- df -h /shared

# 5. Check memory usage
kubectl top pods -n oikotie-scraper

echo "=== Health Check Complete ==="
```

#### Weekly Maintenance (30 minutes)
```bash
#!/bin/bash
# Weekly maintenance script

echo "=== Weekly Maintenance ==="

# 1. Database optimization
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -c "
import duckdb
conn = duckdb.connect('/shared/real_estate.duckdb')
print('Running VACUUM...')
conn.execute('VACUUM')
print('Running ANALYZE...')
conn.execute('ANALYZE')
conn.close()
print('Database optimization complete')
"

# 2. Log rotation
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  find /logs -name "*.log" -mtime +7 -delete

# 3. Backup verification
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  ls -la /backups/ | tail -5

# 4. Update check
echo "Checking for image updates..."
docker pull oikotie-scraper:latest

# 5. Performance metrics review
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  curl -s http://localhost:8080/metrics | grep scraper_

echo "=== Weekly Maintenance Complete ==="
```

### Incident Response Runbooks

#### High Error Rate Alert

**Trigger**: Error rate > 5% for 5 minutes

**Response Steps**:
1. **Immediate Assessment** (2 minutes)
   ```bash
   # Check current error rate
   kubectl logs deployment/oikotie-scraper -n oikotie-scraper --since=10m | \
     grep -c "ERROR\|CRITICAL"
   
   # Check service health
   kubectl get pods -n oikotie-scraper
   curl -f http://scraper-service:8080/health
   ```

2. **Identify Root Cause** (5 minutes)
   ```bash
   # Check recent errors
   kubectl logs deployment/oikotie-scraper -n oikotie-scraper --since=15m | \
     grep "ERROR\|CRITICAL" | tail -20
   
   # Check external dependencies
   curl -I https://asunnot.oikotie.fi
   
   # Check resource usage
   kubectl top pods -n oikotie-scraper
   ```

3. **Mitigation Actions**
   ```bash
   # If network issues
   kubectl rollout restart deployment/oikotie-scraper -n oikotie-scraper
   
   # If resource issues
   kubectl scale deployment oikotie-scraper --replicas=2 -n oikotie-scraper
   
   # If database issues
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     python -c "import duckdb; duckdb.connect('/shared/real_estate.duckdb').close()"
   ```

#### Service Down Alert

**Trigger**: Service unavailable for 1 minute

**Response Steps**:
1. **Immediate Response** (1 minute)
   ```bash
   # Check pod status
   kubectl get pods -n oikotie-scraper
   
   # Check recent events
   kubectl get events -n oikotie-scraper --sort-by='.lastTimestamp' | tail -10
   ```

2. **Recovery Actions** (3 minutes)
   ```bash
   # Restart deployment
   kubectl rollout restart deployment/oikotie-scraper -n oikotie-scraper
   
   # Check rollout status
   kubectl rollout status deployment/oikotie-scraper -n oikotie-scraper
   
   # Verify health
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     curl -f http://localhost:8080/health
   ```

3. **Post-Incident** (10 minutes)
   ```bash
   # Collect logs for analysis
   kubectl logs deployment/oikotie-scraper -n oikotie-scraper --previous > incident-logs.txt
   
   # Document incident
   echo "Incident: $(date)" >> incidents.log
   echo "Cause: TBD" >> incidents.log
   echo "Resolution: Service restart" >> incidents.log
   ```

#### Database Corruption Alert

**Trigger**: Database integrity check fails

**Response Steps**:
1. **Stop Service** (1 minute)
   ```bash
   kubectl scale deployment oikotie-scraper --replicas=0 -n oikotie-scraper
   ```

2. **Assess Damage** (5 minutes)
   ```bash
   # Check database file
   kubectl exec -it deployment/oikotie-scraper -n oikotie-scraper -- \
     ls -la /shared/real_estate.duckdb*
   
   # Try to connect
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     python -c "
   import duckdb
   try:
       conn = duckdb.connect('/shared/real_estate.duckdb')
       print('Connection OK')
       conn.close()
   except Exception as e:
       print(f'Connection failed: {e}')
   "
   ```

3. **Recovery** (15 minutes)
   ```bash
   # Restore from backup
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     cp /backups/real_estate_latest.duckdb /shared/real_estate.duckdb
   
   # Verify restoration
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     python -c "
   import duckdb
   conn = duckdb.connect('/shared/real_estate.duckdb')
   count = conn.execute('SELECT COUNT(*) FROM listings').fetchone()[0]
   print(f'Restored database has {count} listings')
   conn.close()
   "
   
   # Restart service
   kubectl scale deployment oikotie-scraper --replicas=3 -n oikotie-scraper
   ```

### Deployment Runbooks

#### Rolling Update Procedure

1. **Pre-deployment Checks**
   ```bash
   # Verify new image
   docker pull oikotie-scraper:v1.1.0
   docker run --rm oikotie-scraper:v1.1.0 python -c "import oikotie; print('OK')"
   
   # Backup current state
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     cp /shared/real_estate.duckdb /backups/pre-deployment-$(date +%Y%m%d).duckdb
   ```

2. **Deployment**
   ```bash
   # Update image
   kubectl set image deployment/oikotie-scraper \
     scraper=oikotie-scraper:v1.1.0 -n oikotie-scraper
   
   # Monitor rollout
   kubectl rollout status deployment/oikotie-scraper -n oikotie-scraper --timeout=300s
   ```

3. **Post-deployment Verification**
   ```bash
   # Check pod status
   kubectl get pods -n oikotie-scraper
   
   # Verify health
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     curl -f http://localhost:8080/health
   
   # Test functionality
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     python -m oikotie.automation.cli test --quick
   ```

4. **Rollback Procedure** (if needed)
   ```bash
   # Rollback deployment
   kubectl rollout undo deployment/oikotie-scraper -n oikotie-scraper
   
   # Verify rollback
   kubectl rollout status deployment/oikotie-scraper -n oikotie-scraper
   ```

#### Scaling Procedures

**Scale Up** (High Load)
```bash
# Increase replicas
kubectl scale deployment oikotie-scraper --replicas=5 -n oikotie-scraper

# Monitor resource usage
kubectl top pods -n oikotie-scraper

# Verify load distribution
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  curl -s http://localhost:8080/metrics | grep scraper_active_workers
```

**Scale Down** (Low Load)
```bash
# Decrease replicas gradually
kubectl scale deployment oikotie-scraper --replicas=2 -n oikotie-scraper

# Wait for graceful shutdown
sleep 60

# Verify remaining pods are healthy
kubectl get pods -n oikotie-scraper
```

## Performance Troubleshooting

### Slow Scraping Performance

#### Diagnostic Steps
```bash
# Check current performance metrics
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  curl -s http://localhost:8080/metrics | grep -E "scraper_execution_duration|scraper_listings_per_second"

# Check resource utilization
kubectl top pods -n oikotie-scraper

# Check network latency
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  ping -c 5 asunnot.oikotie.fi
```

#### Optimization Actions
```bash
# Increase worker count
kubectl patch deployment oikotie-scraper -n oikotie-scraper -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"scraper","env":[{"name":"MAX_WORKERS","value":"5"}]}]}}}}'

# Optimize database settings
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -c "
import duckdb
conn = duckdb.connect('/shared/real_estate.duckdb')
conn.execute('PRAGMA threads=4')
conn.execute('PRAGMA memory_limit=1GB')
conn.close()
"
```

### High Memory Usage

#### Investigation
```bash
# Check memory usage patterns
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  ps aux --sort=-%mem | head -10

# Check for memory leaks
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -c "
import gc
import psutil
process = psutil.Process()
print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB')
print(f'Open files: {len(process.open_files())}')
gc.collect()
"
```

#### Mitigation
```bash
# Reduce batch size
kubectl patch deployment oikotie-scraper -n oikotie-scraper -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"scraper","env":[{"name":"BATCH_SIZE","value":"25"}]}]}}}}'

# Enable garbage collection
kubectl patch deployment oikotie-scraper -n oikotie-scraper -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"scraper","env":[{"name":"PYTHONGC","value":"1"}]}]}}}}'
```

## Security Incident Response

### Suspected Breach

1. **Immediate Containment**
   ```bash
   # Isolate affected pods
   kubectl label pod <pod-name> security=quarantine -n oikotie-scraper
   
   # Block network access
   kubectl apply -f - <<EOF
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: quarantine-policy
     namespace: oikotie-scraper
   spec:
     podSelector:
       matchLabels:
         security: quarantine
     policyTypes:
     - Ingress
     - Egress
   EOF
   ```

2. **Evidence Collection**
   ```bash
   # Collect logs
   kubectl logs <pod-name> -n oikotie-scraper > security-incident-logs.txt
   
   # Collect system information
   kubectl exec <pod-name> -n oikotie-scraper -- ps aux > process-list.txt
   kubectl exec <pod-name> -n oikotie-scraper -- netstat -tulpn > network-connections.txt
   ```

3. **Analysis and Recovery**
   ```bash
   # Scan for malware
   kubectl exec <pod-name> -n oikotie-scraper -- \
     find / -name "*.sh" -newer /tmp/reference -exec ls -la {} \;
   
   # Check for unauthorized changes
   kubectl exec <pod-name> -n oikotie-scraper -- \
     find /app -type f -newer /tmp/reference
   ```

### Data Breach Response

1. **Assess Scope**
   ```bash
   # Check database access logs
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     grep -i "select\|insert\|update\|delete" /logs/database.log | tail -100
   
   # Check for data exfiltration
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     netstat -i | grep -E "RX|TX"
   ```

2. **Containment**
   ```bash
   # Revoke database access
   kubectl delete secret oikotie-scraper-secrets -n oikotie-scraper
   
   # Stop all pods
   kubectl scale deployment oikotie-scraper --replicas=0 -n oikotie-scraper
   ```

3. **Recovery**
   ```bash
   # Restore from clean backup
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     cp /backups/clean-backup.duckdb /shared/real_estate.duckdb
   
   # Update secrets
   kubectl create secret generic oikotie-scraper-secrets \
     --from-literal=database-key=<new-key> -n oikotie-scraper
   ```

## Disaster Recovery Procedures

### Complete System Failure

1. **Assessment** (5 minutes)
   ```bash
   # Check cluster status
   kubectl get nodes
   kubectl get namespaces
   
   # Check persistent volumes
   kubectl get pv
   kubectl get pvc -n oikotie-scraper
   ```

2. **Recovery** (30 minutes)
   ```bash
   # Recreate namespace
   kubectl apply -f k8s/namespace.yaml
   
   # Restore persistent volumes
   kubectl apply -f k8s/pvc-restore.yaml
   
   # Deploy application
   helm install oikotie-scraper k8s/helm/oikotie-scraper/ \
     --namespace oikotie-scraper \
     -f values-disaster-recovery.yaml
   ```

3. **Data Recovery** (60 minutes)
   ```bash
   # Restore database from backup
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     cp /backups/latest-backup.duckdb /shared/real_estate.duckdb
   
   # Verify data integrity
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     python -c "
   import duckdb
   conn = duckdb.connect('/shared/real_estate.duckdb')
   count = conn.execute('SELECT COUNT(*) FROM listings').fetchone()[0]
   print(f'Recovered {count} listings')
   conn.close()
   "
   ```

### Data Center Outage

1. **Failover to Secondary Site**
   ```bash
   # Switch DNS to secondary site
   # Update load balancer configuration
   # Activate standby cluster
   
   # Deploy to secondary cluster
   kubectl config use-context secondary-cluster
   helm install oikotie-scraper k8s/helm/oikotie-scraper/ \
     --namespace oikotie-scraper \
     -f values-secondary-site.yaml
   ```

2. **Data Synchronization**
   ```bash
   # Sync data from primary backup
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     rsync -av backup-server:/backups/ /shared/backups/
   
   # Restore latest data
   kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
     cp /shared/backups/latest.duckdb /shared/real_estate.duckdb
   ```

## Monitoring and Alerting

### Alert Response Procedures

#### Critical Alerts (Immediate Response)

**Service Down**
- Response Time: 1 minute
- Escalation: 5 minutes
- Actions: Restart service, check logs, notify team

**Database Corruption**
- Response Time: 2 minutes
- Escalation: 10 minutes
- Actions: Stop service, restore backup, verify integrity

**Security Breach**
- Response Time: Immediate
- Escalation: 1 minute
- Actions: Isolate system, collect evidence, notify security team

#### Warning Alerts (Response within 15 minutes)

**High Error Rate**
- Investigate root cause
- Check external dependencies
- Consider scaling or configuration changes

**High Memory Usage**
- Monitor trends
- Check for memory leaks
- Consider resource adjustments

**Slow Performance**
- Analyze performance metrics
- Check resource utilization
- Optimize configuration if needed

### Monitoring Dashboard Setup

```bash
# Deploy Grafana dashboard
kubectl apply -f monitoring/grafana-dashboard.yaml

# Import dashboard configuration
kubectl create configmap grafana-dashboard \
  --from-file=monitoring/dashboard.json -n monitoring

# Configure alerts
kubectl apply -f monitoring/alert-rules.yaml
```

## Escalation Procedures

### Escalation Matrix

| Severity | Response Time | Primary Contact | Secondary Contact | Manager |
|----------|---------------|-----------------|-------------------|---------|
| Critical | 1 minute | On-call Engineer | DevOps Lead | Engineering Manager |
| High | 15 minutes | DevOps Team | Platform Team | Engineering Manager |
| Medium | 1 hour | Platform Team | Development Team | Team Lead |
| Low | 4 hours | Development Team | - | - |

### Contact Information

```bash
# Emergency contacts
ONCALL_ENGINEER="+1-555-0101"
DEVOPS_LEAD="+1-555-0102"
ENGINEERING_MANAGER="+1-555-0103"

# Notification channels
SLACK_CHANNEL="#oikotie-alerts"
EMAIL_LIST="alerts@company.com"
PAGER_DUTY="https://company.pagerduty.com/incidents"
```

### Escalation Script

```bash
#!/bin/bash
# Automatic escalation script

SEVERITY=$1
INCIDENT_ID=$2
DESCRIPTION=$3

case $SEVERITY in
  "CRITICAL")
    # Immediate notification
    curl -X POST $SLACK_WEBHOOK -d "{\"text\":\"🚨 CRITICAL: $DESCRIPTION\"}"
    # Page on-call engineer
    curl -X POST $PAGERDUTY_API -d "{\"incident_key\":\"$INCIDENT_ID\"}"
    ;;
  "HIGH")
    # Notify team
    curl -X POST $SLACK_WEBHOOK -d "{\"text\":\"⚠️ HIGH: $DESCRIPTION\"}"
    ;;
  "MEDIUM")
    # Standard notification
    curl -X POST $SLACK_WEBHOOK -d "{\"text\":\"ℹ️ MEDIUM: $DESCRIPTION\"}"
    ;;
esac
```

This comprehensive troubleshooting guide provides the operational foundation for maintaining the Oikotie Daily Scraper Automation system in production environments.