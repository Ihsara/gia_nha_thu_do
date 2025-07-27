# Multi-City Production Deployment Readiness Checklist

This checklist ensures that the multi-city Oikotie scraper system is ready for production deployment with comprehensive monitoring, backup, and disaster recovery capabilities.

## Pre-Deployment Checklist

### Infrastructure Requirements

- [ ] **Container Runtime**
  - [ ] Docker Engine 20.10+ installed and running
  - [ ] Docker Compose 2.0+ available (for standalone deployment)
  - [ ] Container registry access configured

- [ ] **Kubernetes Cluster** (for K8s deployment)
  - [ ] Kubernetes cluster 1.21+ available and accessible
  - [ ] kubectl configured with cluster access
  - [ ] Sufficient cluster resources (minimum 4 CPU cores, 8GB RAM)
  - [ ] Persistent storage class available
  - [ ] Ingress controller configured (optional)

- [ ] **Helm** (for Helm deployment)
  - [ ] Helm 3.7+ installed
  - [ ] Helm repository access configured

### Configuration Validation

- [ ] **Multi-City Configuration**
  - [ ] `config/config.json` contains both Helsinki and Espoo configurations
  - [ ] City-specific URLs and parameters validated
  - [ ] Coordinate bounds properly configured for both cities
  - [ ] Rate limiting settings appropriate for production

- [ ] **Database Configuration**
  - [ ] DuckDB path configured for shared storage
  - [ ] Database schema migrations ready
  - [ ] Spatial indexes configured for both cities

- [ ] **Security Configuration**
  - [ ] Backup encryption keys generated and stored securely
  - [ ] S3 credentials configured (if using remote backup)
  - [ ] Alert webhook URLs configured
  - [ ] Network policies defined (for Kubernetes)

### Monitoring and Alerting

- [ ] **Prometheus Configuration**
  - [ ] Prometheus server configured with appropriate retention
  - [ ] Alert rules defined for multi-city operations
  - [ ] Service discovery configured for scraper pods

- [ ] **Grafana Dashboards**
  - [ ] Multi-city overview dashboard imported
  - [ ] City comparison dashboard imported
  - [ ] System health dashboard imported
  - [ ] Geospatial quality dashboard imported

- [ ] **Alertmanager Configuration**
  - [ ] Alert routing rules configured
  - [ ] Notification channels configured (email, Slack, etc.)
  - [ ] City-specific alert routing tested

### Backup and Disaster Recovery

- [ ] **Backup System**
  - [ ] Backup storage configured and accessible
  - [ ] Encryption keys generated and secured
  - [ ] Backup schedules configured for both cities
  - [ ] S3 or remote storage configured (if applicable)

- [ ] **Disaster Recovery**
  - [ ] Disaster recovery procedures documented
  - [ ] Recovery time objectives (RTO) defined
  - [ ] Recovery point objectives (RPO) defined
  - [ ] Automated recovery procedures tested

## Deployment Validation

### System Health Checks

- [ ] **Container Health**
  - [ ] All containers start successfully
  - [ ] Health check endpoints respond correctly
  - [ ] Resource limits appropriate for workload

- [ ] **Database Connectivity**
  - [ ] Database connection established
  - [ ] Schema validation passes
  - [ ] Spatial indexes created successfully

- [ ] **Multi-City Coordination**
  - [ ] Redis cluster coordination working
  - [ ] Work distribution functioning correctly
  - [ ] City-specific metrics being collected

### Functional Testing

- [ ] **Scraping Operations**
  - [ ] Helsinki scraping operational
  - [ ] Espoo scraping operational
  - [ ] Data quality validation passing
  - [ ] Geospatial enrichment working

- [ ] **Monitoring Systems**
  - [ ] Prometheus collecting metrics
  - [ ] Grafana dashboards displaying data
  - [ ] Alerts firing correctly for test conditions

- [ ] **Backup Operations**
  - [ ] Daily backups executing successfully
  - [ ] City-specific backups working
  - [ ] Backup validation passing
  - [ ] Restore procedures tested

## Post-Deployment Verification

### Performance Validation

- [ ] **Resource Usage**
  - [ ] CPU usage within acceptable limits (<80%)
  - [ ] Memory usage within acceptable limits (<80%)
  - [ ] Disk I/O performance adequate
  - [ ] Network bandwidth sufficient

- [ ] **Scraping Performance**
  - [ ] Success rate >95% for both cities
  - [ ] Processing time within SLA
  - [ ] Geospatial match rate >95%
  - [ ] Error rate <5%

### Data Quality Validation

- [ ] **Data Integrity**
  - [ ] Listings data complete and accurate
  - [ ] Coordinate validation passing
  - [ ] Duplicate detection working
  - [ ] Data lineage tracking functional

- [ ] **Geospatial Quality**
  - [ ] Address geocoding accuracy >95%
  - [ ] Building footprint matching working
  - [ ] Coordinate bounds validation active
  - [ ] Spatial data quality scores acceptable

### Monitoring and Alerting Validation

- [ ] **Alert Testing**
  - [ ] Critical alerts tested and working
  - [ ] City-specific alerts routing correctly
  - [ ] Notification channels receiving alerts
  - [ ] Alert resolution notifications working

- [ ] **Dashboard Validation**
  - [ ] All dashboards loading correctly
  - [ ] Metrics displaying accurate data
  - [ ] City comparison views functional
  - [ ] Historical data retention working

## Production Readiness Sign-off

### Technical Sign-off

- [ ] **Development Team**
  - [ ] Code review completed
  - [ ] Unit tests passing
  - [ ] Integration tests passing
  - [ ] Performance tests passing

- [ ] **Operations Team**
  - [ ] Infrastructure validated
  - [ ] Monitoring configured
  - [ ] Backup procedures tested
  - [ ] Disaster recovery validated

### Business Sign-off

- [ ] **Data Quality Team**
  - [ ] Data accuracy validated
  - [ ] Quality metrics acceptable
  - [ ] Compliance requirements met

- [ ] **Product Team**
  - [ ] Feature requirements met
  - [ ] User acceptance criteria satisfied
  - [ ] Performance requirements met

## Deployment Commands

### Docker Compose Deployment
```bash
# Validate configuration
docker-compose config

# Deploy services
docker-compose up -d --build

# Verify deployment
docker-compose ps
docker-compose logs
```

### Kubernetes Deployment
```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/scraper-cluster.yaml
kubectl apply -f k8s/monitoring.yaml
kubectl apply -f k8s/backup-cronjob.yaml

# Verify deployment
kubectl get pods -n oikotie-scraper
kubectl get services -n oikotie-scraper
kubectl logs -n oikotie-scraper -l app=oikotie-scraper
```

### Helm Deployment
```bash
# Deploy with Helm
helm upgrade --install oikotie-scraper k8s/helm/oikotie-scraper \
  --namespace oikotie-scraper \
  --create-namespace \
  --values k8s/helm/oikotie-scraper/values.yaml

# Verify deployment
helm status oikotie-scraper -n oikotie-scraper
kubectl get pods -n oikotie-scraper
```

### Automated Deployment
```bash
# Use deployment script
python scripts/deployment/deploy-multi-city-production.py \
  --deployment-type kubernetes \
  --cities Helsinki Espoo \
  --verbose

# Dry run first
python scripts/deployment/deploy-multi-city-production.py \
  --deployment-type kubernetes \
  --cities Helsinki Espoo \
  --dry-run
```

## Rollback Procedures

### Emergency Rollback
```bash
# Docker Compose
docker-compose down
docker-compose up -d --build

# Kubernetes
kubectl rollout undo deployment/oikotie-scraper -n oikotie-scraper

# Helm
helm rollback oikotie-scraper -n oikotie-scraper
```

### Data Recovery
```bash
# Restore from backup
python -m oikotie.automation.backup_manager restore \
  --backup-id <backup_id> \
  --cities Helsinki,Espoo

# Disaster recovery
python -m oikotie.automation.disaster_recovery recover \
  --disaster-type <type> \
  --cities Helsinki,Espoo
```

## Support and Troubleshooting

### Health Check Endpoints
- **System Health**: `http://localhost:8080/health`
- **Metrics**: `http://localhost:9090/metrics`
- **Grafana**: `http://localhost:3000`
- **Prometheus**: `http://localhost:9090`

### Log Locations
- **Container Logs**: `docker logs <container_name>`
- **Kubernetes Logs**: `kubectl logs -n oikotie-scraper <pod_name>`
- **Application Logs**: `/logs/` directory in containers

### Common Issues
1. **Database Connection Issues**: Check database path and permissions
2. **Redis Connection Issues**: Verify Redis service availability
3. **Scraping Failures**: Check rate limiting and website accessibility
4. **Backup Failures**: Verify storage permissions and encryption keys
5. **Alert Issues**: Check webhook URLs and notification configurations

## Maintenance Schedule

### Daily
- [ ] Monitor system health dashboards
- [ ] Review backup completion status
- [ ] Check alert notifications

### Weekly
- [ ] Review performance metrics
- [ ] Validate data quality reports
- [ ] Test disaster recovery procedures

### Monthly
- [ ] Update security configurations
- [ ] Review and rotate encryption keys
- [ ] Perform full system health assessment
- [ ] Update documentation and procedures

---

**Deployment Date**: _______________
**Deployed By**: _______________
**Reviewed By**: _______________
**Production Ready**: [ ] Yes [ ] No

**Notes**:
_________________________________
_________________________________
_________________________________