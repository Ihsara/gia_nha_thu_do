# Operational Runbooks

This document provides step-by-step operational procedures for deploying, maintaining, and operating the Oikotie Daily Scraper Automation system.

## Table of Contents

1. [Deployment Runbooks](#deployment-runbooks)
2. [Maintenance Runbooks](#maintenance-runbooks)
3. [Backup and Recovery Runbooks](#backup-and-recovery-runbooks)
4. [Monitoring Runbooks](#monitoring-runbooks)
5. [Security Runbooks](#security-runbooks)
6. [Emergency Procedures](#emergency-procedures)

## Deployment Runbooks

### Initial Deployment Runbook

#### Prerequisites Checklist
- [ ] Kubernetes cluster available (1.19+)
- [ ] Helm 3.x installed
- [ ] kubectl configured and tested
- [ ] Docker registry access
- [ ] Persistent storage configured
- [ ] Monitoring stack available (optional)

#### Step 1: Environment Preparation (15 minutes)

```bash
#!/bin/bash
# Environment preparation script

set -euo pipefail

echo "🚀 Starting Oikotie Scraper Deployment"

# 1. Verify prerequisites
echo "✅ Checking prerequisites..."

# Check kubectl
if ! kubectl version --client >/dev/null 2>&1; then
    echo "❌ kubectl not found or not configured"
    exit 1
fi

# Check Helm
if ! helm version >/dev/null 2>&1; then
    echo "❌ Helm not found"
    exit 1
fi

# Check cluster connectivity
if ! kubectl get nodes >/dev/null 2>&1; then
    echo "❌ Cannot connect to Kubernetes cluster"
    exit 1
fi

echo "✅ Prerequisites verified"

# 2. Create namespace
echo "📁 Creating namespace..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: oikotie-scraper
  labels:
    app: oikotie-scraper
    environment: production
EOF

# 3. Verify storage class
echo "💾 Checking storage class..."
if ! kubectl get storageclass >/dev/null 2>&1; then
    echo "⚠️ No storage classes found - using default"
fi

# 4. Create secrets (if not using external secret management)
echo "🔐 Creating secrets..."
read -s -p "Enter SMTP password: " SMTP_PASSWORD
echo
read -s -p "Enter Slack webhook URL: " SLACK_WEBHOOK
echo

kubectl create secret generic oikotie-scraper-secrets \
  --namespace=oikotie-scraper \
  --from-literal=smtp-password="$SMTP_PASSWORD" \
  --from-literal=slack-webhook-url="$SLACK_WEBHOOK" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "✅ Environment preparation complete"
```

#### Step 2: Application Deployment (10 minutes)

```bash
#!/bin/bash
# Application deployment script

set -euo pipefail

echo "🚀 Deploying Oikotie Scraper Application"

# 1. Add Helm repository (if using external chart)
# helm repo add oikotie-scraper https://charts.example.com/oikotie-scraper
# helm repo update

# 2. Create custom values file
cat > values-production.yaml <<EOF
deployment:
  replicaCount: 3
  
image:
  repository: oikotie-scraper
  tag: "latest"
  pullPolicy: IfNotPresent

app:
  environment: production
  logLevel: INFO
  maxWorkers: 3
  cities:
    - name: "Helsinki"
      enabled: true
      url: "https://asunnot.oikotie.fi/myytavat-asunnot?locations=%5B%5B64,6,%22Helsinki%22%5D%5D&cardType=100"
      maxDetailWorkers: 3

resources:
  requests:
    memory: "512Mi"
    cpu: "200m"
  limits:
    memory: "1Gi"
    cpu: "500m"

persistence:
  enabled: true
  size: 20Gi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5

monitoring:
  enabled: true
  serviceMonitor:
    enabled: true

redis:
  enabled: true
EOF

# 3. Deploy application
echo "📦 Installing Helm chart..."
helm install oikotie-scraper k8s/helm/oikotie-scraper/ \
  --namespace oikotie-scraper \
  --values values-production.yaml \
  --wait \
  --timeout 10m

# 4. Verify deployment
echo "🔍 Verifying deployment..."
kubectl get pods -n oikotie-scraper
kubectl get services -n oikotie-scraper
kubectl get pvc -n oikotie-scraper

# 5. Wait for pods to be ready
echo "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=oikotie-scraper \
  --namespace=oikotie-scraper --timeout=300s

echo "✅ Application deployment complete"
```

#### Step 3: Post-Deployment Verification (5 minutes)

```bash
#!/bin/bash
# Post-deployment verification script

set -euo pipefail

echo "🔍 Starting post-deployment verification"

# 1. Check pod status
echo "📊 Checking pod status..."
kubectl get pods -n oikotie-scraper -o wide

# 2. Check service endpoints
echo "🌐 Checking service endpoints..."
kubectl get endpoints -n oikotie-scraper

# 3. Test health endpoints
echo "🏥 Testing health endpoints..."
kubectl port-forward service/oikotie-scraper 8080:8080 -n oikotie-scraper &
PORT_FORWARD_PID=$!
sleep 5

if curl -f http://localhost:8080/health >/dev/null 2>&1; then
    echo "✅ Health endpoint responding"
else
    echo "❌ Health endpoint not responding"
fi

kill $PORT_FORWARD_PID 2>/dev/null || true

# 4. Check logs for errors
echo "📋 Checking recent logs..."
kubectl logs -l app.kubernetes.io/name=oikotie-scraper -n oikotie-scraper --tail=50 | \
  grep -i error || echo "No errors found in recent logs"

# 5. Test database connectivity
echo "🗄️ Testing database connectivity..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -c "
import duckdb
try:
    conn = duckdb.connect('/shared/real_estate.duckdb')
    conn.execute('CREATE TABLE IF NOT EXISTS test_table (id INTEGER)')
    conn.execute('DROP TABLE test_table')
    conn.close()
    print('✅ Database connectivity test passed')
except Exception as e:
    print(f'❌ Database connectivity test failed: {e}')
"

# 6. Test scraping functionality (dry run)
echo "🕷️ Testing scraping functionality..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli test --dry-run --max-listings 5

echo "✅ Post-deployment verification complete"
```

### Update Deployment Runbook

#### Rolling Update Procedure (20 minutes)

```bash
#!/bin/bash
# Rolling update procedure

set -euo pipefail

NEW_VERSION=${1:-latest}
echo "🔄 Starting rolling update to version: $NEW_VERSION"

# 1. Pre-update backup
echo "💾 Creating pre-update backup..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  cp /shared/real_estate.duckdb /shared/backups/pre-update-$(date +%Y%m%d-%H%M%S).duckdb

# 2. Update image
echo "🖼️ Updating container image..."
kubectl set image deployment/oikotie-scraper \
  scraper=oikotie-scraper:$NEW_VERSION \
  -n oikotie-scraper

# 3. Monitor rollout
echo "👀 Monitoring rollout progress..."
kubectl rollout status deployment/oikotie-scraper -n oikotie-scraper --timeout=600s

# 4. Verify update
echo "✅ Verifying update..."
kubectl get pods -n oikotie-scraper -o jsonpath='{.items[*].spec.containers[*].image}'

# 5. Health check
echo "🏥 Performing health check..."
sleep 30
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  curl -f http://localhost:8080/health

# 6. Functional test
echo "🧪 Running functional test..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli test --quick

echo "✅ Rolling update complete"
```

#### Rollback Procedure (10 minutes)

```bash
#!/bin/bash
# Rollback procedure

set -euo pipefail

echo "⏪ Starting rollback procedure"

# 1. Check rollout history
echo "📜 Checking rollout history..."
kubectl rollout history deployment/oikotie-scraper -n oikotie-scraper

# 2. Rollback to previous version
echo "🔄 Rolling back to previous version..."
kubectl rollout undo deployment/oikotie-scraper -n oikotie-scraper

# 3. Monitor rollback
echo "👀 Monitoring rollback progress..."
kubectl rollout status deployment/oikotie-scraper -n oikotie-scraper --timeout=300s

# 4. Verify rollback
echo "✅ Verifying rollback..."
kubectl get pods -n oikotie-scraper
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  curl -f http://localhost:8080/health

# 5. Restore data if needed
read -p "Restore pre-update backup? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "💾 Restoring pre-update backup..."
    BACKUP_FILE=$(kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
      ls -t /shared/backups/pre-update-*.duckdb | head -1)
    kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
      cp "$BACKUP_FILE" /shared/real_estate.duckdb
fi

echo "✅ Rollback complete"
```

## Maintenance Runbooks

### Daily Maintenance Runbook (10 minutes)

```bash
#!/bin/bash
# Daily maintenance script

set -euo pipefail

echo "🌅 Starting daily maintenance - $(date)"

# 1. Health check
echo "🏥 Performing health check..."
kubectl get pods -n oikotie-scraper | grep -v Running && echo "⚠️ Some pods not running"

# 2. Check recent activity
echo "📊 Checking recent scraping activity..."
RECENT_LISTINGS=$(kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -c "
import duckdb
conn = duckdb.connect('/shared/real_estate.duckdb')
result = conn.execute('SELECT COUNT(*) FROM listings WHERE created_at > NOW() - INTERVAL 24 HOURS').fetchone()
print(result[0])
conn.close()
")

echo "📈 Listings processed in last 24h: $RECENT_LISTINGS"

if [ "$RECENT_LISTINGS" -lt 50 ]; then
    echo "⚠️ Low activity detected - investigating..."
    kubectl logs deployment/oikotie-scraper -n oikotie-scraper --tail=100 | grep -i error
fi

# 3. Resource usage check
echo "💻 Checking resource usage..."
kubectl top pods -n oikotie-scraper

# 4. Disk usage check
echo "💾 Checking disk usage..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- df -h /shared

# 5. Log rotation
echo "📋 Rotating logs..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  find /logs -name "*.log" -mtime +7 -delete

# 6. Generate daily report
echo "📄 Generating daily report..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli report --daily --output /shared/reports/daily-$(date +%Y%m%d).json

echo "✅ Daily maintenance complete"
```

### Weekly Maintenance Runbook (45 minutes)

```bash
#!/bin/bash
# Weekly maintenance script

set -euo pipefail

echo "📅 Starting weekly maintenance - $(date)"

# 1. Database optimization
echo "🗄️ Optimizing database..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -c "
import duckdb
conn = duckdb.connect('/shared/real_estate.duckdb')
print('Running VACUUM...')
conn.execute('VACUUM')
print('Running ANALYZE...')
conn.execute('ANALYZE')
print('Checking integrity...')
conn.execute('PRAGMA integrity_check')
conn.close()
print('Database optimization complete')
"

# 2. Update system packages
echo "📦 Updating system packages..."
kubectl set env deployment/oikotie-scraper -n oikotie-scraper \
  FORCE_UPDATE="$(date +%s)"
kubectl rollout restart deployment/oikotie-scraper -n oikotie-scraper
kubectl rollout status deployment/oikotie-scraper -n oikotie-scraper

# 3. Security scan
echo "🔒 Running security scan..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli security-scan

# 4. Performance analysis
echo "📈 Analyzing performance metrics..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli analyze-performance --days 7

# 5. Backup verification
echo "💾 Verifying backups..."
BACKUP_COUNT=$(kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  ls /shared/backups/*.duckdb | wc -l)
echo "📊 Available backups: $BACKUP_COUNT"

if [ "$BACKUP_COUNT" -lt 7 ]; then
    echo "⚠️ Insufficient backups - creating manual backup..."
    kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
      cp /shared/real_estate.duckdb /shared/backups/manual-$(date +%Y%m%d).duckdb
fi

# 6. Configuration review
echo "⚙️ Reviewing configuration..."
kubectl get configmap oikotie-scraper-config -n oikotie-scraper -o yaml > config-backup-$(date +%Y%m%d).yaml

# 7. Generate weekly report
echo "📄 Generating weekly report..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli report --weekly --output /shared/reports/weekly-$(date +%Y%m%d).json

echo "✅ Weekly maintenance complete"
```

### Monthly Maintenance Runbook (2 hours)

```bash
#!/bin/bash
# Monthly maintenance script

set -euo pipefail

echo "📆 Starting monthly maintenance - $(date)"

# 1. Full system backup
echo "💾 Creating full system backup..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  tar -czf /shared/backups/full-backup-$(date +%Y%m).tar.gz \
  /shared/real_estate.duckdb /shared/reports /shared/logs

# 2. Database maintenance
echo "🗄️ Performing comprehensive database maintenance..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -c "
import duckdb
import os
conn = duckdb.connect('/shared/real_estate.duckdb')

# Get database stats
stats = conn.execute('SELECT COUNT(*) as total_listings FROM listings').fetchone()
print(f'Total listings: {stats[0]}')

# Clean old data (older than 2 years)
deleted = conn.execute('DELETE FROM listings WHERE created_at < NOW() - INTERVAL 2 YEARS').fetchone()
print(f'Deleted old listings: {deleted}')

# Optimize database
conn.execute('VACUUM')
conn.execute('ANALYZE')

# Check database size
size = os.path.getsize('/shared/real_estate.duckdb') / (1024*1024*1024)
print(f'Database size: {size:.2f} GB')

conn.close()
"

# 3. Security audit
echo "🔒 Performing security audit..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli security-audit --comprehensive

# 4. Performance benchmarking
echo "📈 Running performance benchmarks..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli benchmark --full

# 5. Dependency updates
echo "📦 Checking for dependency updates..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  pip list --outdated

# 6. Log analysis
echo "📋 Analyzing logs for patterns..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli analyze-logs --days 30

# 7. Capacity planning
echo "📊 Performing capacity planning analysis..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli capacity-planning

# 8. Generate monthly report
echo "📄 Generating monthly report..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli report --monthly --output /shared/reports/monthly-$(date +%Y%m).json

echo "✅ Monthly maintenance complete"
```

## Backup and Recovery Runbooks

### Backup Creation Runbook (15 minutes)

```bash
#!/bin/bash
# Backup creation script

set -euo pipefail

BACKUP_TYPE=${1:-daily}
echo "💾 Creating $BACKUP_TYPE backup - $(date)"

# 1. Create backup directory
BACKUP_DIR="/shared/backups/$(date +%Y%m%d)"
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- mkdir -p "$BACKUP_DIR"

# 2. Database backup
echo "🗄️ Backing up database..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  cp /shared/real_estate.duckdb "$BACKUP_DIR/real_estate.duckdb"

# 3. Configuration backup
echo "⚙️ Backing up configuration..."
kubectl get configmap oikotie-scraper-config -n oikotie-scraper -o yaml > "$BACKUP_DIR/config.yaml"
kubectl get secret oikotie-scraper-secrets -n oikotie-scraper -o yaml > "$BACKUP_DIR/secrets.yaml"

# 4. Application state backup
echo "📊 Backing up application state..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli export-state --output "$BACKUP_DIR/state.json"

# 5. Compress backup
echo "🗜️ Compressing backup..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  tar -czf "/shared/backups/$BACKUP_TYPE-$(date +%Y%m%d-%H%M%S).tar.gz" -C "$BACKUP_DIR" .

# 6. Verify backup
echo "✅ Verifying backup..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  tar -tzf "/shared/backups/$BACKUP_TYPE-$(date +%Y%m%d-%H%M%S).tar.gz" | head -10

# 7. Cleanup old backups
echo "🧹 Cleaning up old backups..."
if [ "$BACKUP_TYPE" = "daily" ]; then
    kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
      find /shared/backups -name "daily-*.tar.gz" -mtime +30 -delete
elif [ "$BACKUP_TYPE" = "weekly" ]; then
    kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
      find /shared/backups -name "weekly-*.tar.gz" -mtime +90 -delete
fi

echo "✅ Backup creation complete"
```

### Recovery Runbook (30 minutes)

```bash
#!/bin/bash
# Recovery procedure script

set -euo pipefail

BACKUP_FILE=${1:-latest}
echo "🔄 Starting recovery from backup: $BACKUP_FILE"

# 1. Stop application
echo "⏹️ Stopping application..."
kubectl scale deployment oikotie-scraper --replicas=0 -n oikotie-scraper
kubectl wait --for=delete pod -l app.kubernetes.io/name=oikotie-scraper -n oikotie-scraper --timeout=300s

# 2. Identify backup file
if [ "$BACKUP_FILE" = "latest" ]; then
    BACKUP_FILE=$(kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
      ls -t /shared/backups/*.tar.gz | head -1)
fi

echo "📦 Using backup file: $BACKUP_FILE"

# 3. Extract backup
echo "📂 Extracting backup..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  tar -xzf "$BACKUP_FILE" -C /tmp/recovery/

# 4. Restore database
echo "🗄️ Restoring database..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  cp /tmp/recovery/real_estate.duckdb /shared/real_estate.duckdb

# 5. Restore configuration
echo "⚙️ Restoring configuration..."
kubectl apply -f /tmp/recovery/config.yaml
kubectl apply -f /tmp/recovery/secrets.yaml

# 6. Verify database integrity
echo "🔍 Verifying database integrity..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -c "
import duckdb
conn = duckdb.connect('/shared/real_estate.duckdb')
conn.execute('PRAGMA integrity_check')
count = conn.execute('SELECT COUNT(*) FROM listings').fetchone()[0]
print(f'Restored database contains {count} listings')
conn.close()
"

# 7. Restart application
echo "🚀 Restarting application..."
kubectl scale deployment oikotie-scraper --replicas=3 -n oikotie-scraper
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=oikotie-scraper -n oikotie-scraper --timeout=300s

# 8. Verify recovery
echo "✅ Verifying recovery..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  curl -f http://localhost:8080/health

# 9. Test functionality
echo "🧪 Testing functionality..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli test --quick

echo "✅ Recovery complete"
```

## Monitoring Runbooks

### Monitoring Setup Runbook (30 minutes)

```bash
#!/bin/bash
# Monitoring setup script

set -euo pipefail

echo "📊 Setting up monitoring infrastructure"

# 1. Deploy Prometheus
echo "📈 Deploying Prometheus..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: oikotie-scraper
data:
  prometheus.yml: |
    global:
      scrape_interval: 30s
    scrape_configs:
    - job_name: 'oikotie-scraper'
      static_configs:
      - targets: ['oikotie-scraper:8080']
      metrics_path: '/metrics'
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: oikotie-scraper
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        command:
        - /bin/prometheus
        - --config.file=/etc/prometheus/prometheus.yml
        - --storage.tsdb.path=/prometheus
        - --web.console.libraries=/etc/prometheus/console_libraries
        - --web.console.templates=/etc/prometheus/consoles
      volumes:
      - name: config
        configMap:
          name: prometheus-config
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: oikotie-scraper
spec:
  selector:
    app: prometheus
  ports:
  - port: 9090
    targetPort: 9090
EOF

# 2. Deploy Grafana
echo "📊 Deploying Grafana..."
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: oikotie-scraper
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
      - name: grafana
        image: grafana/grafana:latest
        ports:
        - containerPort: 3000
        env:
        - name: GF_SECURITY_ADMIN_PASSWORD
          value: "admin123"
---
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: oikotie-scraper
spec:
  selector:
    app: grafana
  ports:
  - port: 3000
    targetPort: 3000
EOF

# 3. Configure alerts
echo "🚨 Configuring alerts..."
kubectl apply -f monitoring/alert-rules.yaml

# 4. Import dashboards
echo "📊 Importing dashboards..."
kubectl create configmap grafana-dashboards \
  --from-file=monitoring/dashboards/ -n oikotie-scraper

echo "✅ Monitoring setup complete"
```

### Alert Response Runbook

```bash
#!/bin/bash
# Alert response script

set -euo pipefail

ALERT_TYPE=$1
SEVERITY=$2

echo "🚨 Responding to alert: $ALERT_TYPE (Severity: $SEVERITY)"

case $ALERT_TYPE in
  "service_down")
    echo "🔄 Service down - attempting restart..."
    kubectl rollout restart deployment/oikotie-scraper -n oikotie-scraper
    kubectl rollout status deployment/oikotie-scraper -n oikotie-scraper
    ;;
  "high_error_rate")
    echo "⚠️ High error rate - investigating..."
    kubectl logs deployment/oikotie-scraper -n oikotie-scraper --tail=100 | grep ERROR
    ;;
  "database_issues")
    echo "🗄️ Database issues - running diagnostics..."
    kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
      python -c "import duckdb; duckdb.connect('/shared/real_estate.duckdb').execute('PRAGMA integrity_check')"
    ;;
  "high_memory_usage")
    echo "💾 High memory usage - checking resources..."
    kubectl top pods -n oikotie-scraper
    kubectl describe pods -l app.kubernetes.io/name=oikotie-scraper -n oikotie-scraper
    ;;
esac

echo "✅ Alert response complete"
```

## Security Runbooks

### Security Audit Runbook (60 minutes)

```bash
#!/bin/bash
# Security audit script

set -euo pipefail

echo "🔒 Starting security audit - $(date)"

# 1. Check pod security context
echo "👤 Checking pod security context..."
kubectl get pods -n oikotie-scraper -o jsonpath='{.items[*].spec.securityContext}' | jq .

# 2. Check network policies
echo "🌐 Checking network policies..."
kubectl get networkpolicies -n oikotie-scraper

# 3. Check RBAC
echo "🔐 Checking RBAC configuration..."
kubectl get rolebindings -n oikotie-scraper
kubectl get clusterrolebindings | grep oikotie-scraper

# 4. Check secrets
echo "🔑 Checking secrets..."
kubectl get secrets -n oikotie-scraper
kubectl describe secret oikotie-scraper-secrets -n oikotie-scraper

# 5. Vulnerability scan
echo "🔍 Running vulnerability scan..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli security-scan --comprehensive

# 6. Check for exposed services
echo "🌍 Checking for exposed services..."
kubectl get services -n oikotie-scraper -o wide

# 7. Generate security report
echo "📄 Generating security report..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  python -m oikotie.automation.cli security-report --output /shared/reports/security-$(date +%Y%m%d).json

echo "✅ Security audit complete"
```

### Incident Response Runbook

```bash
#!/bin/bash
# Security incident response script

set -euo pipefail

INCIDENT_TYPE=$1
echo "🚨 Security incident response: $INCIDENT_TYPE"

# 1. Immediate containment
echo "🔒 Implementing immediate containment..."
kubectl label pods -l app.kubernetes.io/name=oikotie-scraper security=quarantine -n oikotie-scraper

# 2. Evidence collection
echo "🔍 Collecting evidence..."
kubectl logs deployment/oikotie-scraper -n oikotie-scraper > incident-logs-$(date +%Y%m%d-%H%M%S).txt
kubectl describe pods -l app.kubernetes.io/name=oikotie-scraper -n oikotie-scraper > incident-pods-$(date +%Y%m%d-%H%M%S).txt

# 3. Network isolation
echo "🌐 Implementing network isolation..."
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
  egress: []
  ingress: []
EOF

# 4. Notify security team
echo "📞 Notifying security team..."
curl -X POST $SECURITY_WEBHOOK -d "{\"incident\":\"$INCIDENT_TYPE\",\"timestamp\":\"$(date)\"}"

echo "✅ Incident response initiated"
```

## Emergency Procedures

### Emergency Shutdown Runbook (5 minutes)

```bash
#!/bin/bash
# Emergency shutdown script

set -euo pipefail

echo "🚨 EMERGENCY SHUTDOWN INITIATED"

# 1. Scale down application
echo "⏹️ Scaling down application..."
kubectl scale deployment oikotie-scraper --replicas=0 -n oikotie-scraper

# 2. Stop all related services
echo "🛑 Stopping related services..."
kubectl scale deployment redis --replicas=0 -n oikotie-scraper || true
kubectl scale deployment prometheus --replicas=0 -n oikotie-scraper || true

# 3. Create emergency backup
echo "💾 Creating emergency backup..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  cp /shared/real_estate.duckdb /shared/backups/emergency-$(date +%Y%m%d-%H%M%S).duckdb || true

# 4. Notify team
echo "📞 Notifying emergency contacts..."
curl -X POST $EMERGENCY_WEBHOOK -d "{\"status\":\"EMERGENCY_SHUTDOWN\",\"timestamp\":\"$(date)\"}" || true

echo "✅ Emergency shutdown complete"
```

### Emergency Recovery Runbook (15 minutes)

```bash
#!/bin/bash
# Emergency recovery script

set -euo pipefail

echo "🚀 EMERGENCY RECOVERY INITIATED"

# 1. Verify cluster status
echo "🔍 Verifying cluster status..."
kubectl get nodes
kubectl get namespaces

# 2. Restore from emergency backup
echo "💾 Restoring from emergency backup..."
EMERGENCY_BACKUP=$(kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  ls -t /shared/backups/emergency-*.duckdb | head -1)
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  cp "$EMERGENCY_BACKUP" /shared/real_estate.duckdb

# 3. Restart services
echo "🚀 Restarting services..."
kubectl scale deployment oikotie-scraper --replicas=1 -n oikotie-scraper
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=oikotie-scraper -n oikotie-scraper --timeout=300s

# 4. Verify recovery
echo "✅ Verifying recovery..."
kubectl exec deployment/oikotie-scraper -n oikotie-scraper -- \
  curl -f http://localhost:8080/health

# 5. Gradual scale up
echo "📈 Gradually scaling up..."
kubectl scale deployment oikotie-scraper --replicas=3 -n oikotie-scraper

# 6. Notify team
echo "📞 Notifying team of recovery..."
curl -X POST $RECOVERY_WEBHOOK -d "{\"status\":\"RECOVERY_COMPLETE\",\"timestamp\":\"$(date)\"}"

echo "✅ Emergency recovery complete"
```

These operational runbooks provide comprehensive procedures for deploying, maintaining, and operating the Oikotie Daily Scraper Automation system in production environments.