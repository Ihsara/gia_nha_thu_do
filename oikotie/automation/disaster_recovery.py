#!/usr/bin/env python3
"""
Disaster recovery orchestrator for multi-city scraper system.

This module provides automated disaster recovery capabilities including
failover detection, automated recovery procedures, and system restoration.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from loguru import logger

from oikotie.automation.health_check import MultiCityHealthChecker
from oikotie.automation.backup_manager import BackupManager
from oikotie.utils.config import load_config


class DisasterType(Enum):
    """Types of disasters that can be detected."""
    DATABASE_FAILURE = "database_failure"
    SYSTEM_OVERLOAD = "system_overload"
    CITY_SCRAPING_FAILURE = "city_scraping_failure"
    CLUSTER_COORDINATION_FAILURE = "cluster_coordination_failure"
    DATA_CORRUPTION = "data_corruption"
    NETWORK_PARTITION = "network_partition"
    STORAGE_FAILURE = "storage_failure"


class RecoveryAction(Enum):
    """Types of recovery actions."""
    RESTART_SERVICE = "restart_service"
    RESTORE_FROM_BACKUP = "restore_from_backup"
    FAILOVER_TO_BACKUP_CITY = "failover_to_backup_city"
    SCALE_RESOURCES = "scale_resources"
    REPAIR_DATABASE = "repair_database"
    CLEAR_CACHE = "clear_cache"
    MANUAL_INTERVENTION = "manual_intervention"


@dataclass
class DisasterEvent:
    """Disaster event information."""
    event_id: str
    disaster_type: DisasterType
    severity: str  # "low", "medium", "high", "critical"
    affected_components: List[str]
    affected_cities: List[str]
    detected_at: datetime
    description: str
    metrics: Dict[str, Any]
    recovery_actions: List[RecoveryAction]
    estimated_recovery_time_minutes: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['disaster_type'] = self.disaster_type.value
        result['recovery_actions'] = [action.value for action in self.recovery_actions]
        result['detected_at'] = self.detected_at.isoformat()
        return result


@dataclass
class RecoveryPlan:
    """Recovery plan for a disaster event."""
    event_id: str
    steps: List[Dict[str, Any]]
    estimated_duration_minutes: int
    success_criteria: List[str]
    rollback_plan: List[Dict[str, Any]]
    dependencies: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class DisasterRecoveryOrchestrator:
    """Orchestrates disaster recovery procedures."""
    
    def __init__(self, config_path: str = "config/config.json"):
        """Initialize disaster recovery orchestrator."""
        self.config = load_config(config_path)
        self.dr_config = self.config.get("disaster_recovery", {})
        
        self.logger = logger.bind(component="disaster_recovery")
        
        # Initialize components
        self.health_checker = MultiCityHealthChecker(config_path)
        self.backup_manager = BackupManager(config_path)
        
        # Recovery settings
        self.auto_recovery_enabled = self.dr_config.get("automation", {}).get("enabled", True)
        self.failover_threshold = self.dr_config.get("automation", {}).get("failover_threshold", 3)
        self.health_check_interval = self.dr_config.get("automation", {}).get("health_check_interval", "5m")
        
        # State tracking
        self.active_disasters: Dict[str, DisasterEvent] = {}
        self.recovery_history: List[Dict[str, Any]] = []
        self.consecutive_failures: Dict[str, int] = {}
        
        # Recovery procedures
        self.recovery_procedures = {
            DisasterType.DATABASE_FAILURE: self._recover_database_failure,
            DisasterType.SYSTEM_OVERLOAD: self._recover_system_overload,
            DisasterType.CITY_SCRAPING_FAILURE: self._recover_city_scraping_failure,
            DisasterType.CLUSTER_COORDINATION_FAILURE: self._recover_cluster_failure,
            DisasterType.DATA_CORRUPTION: self._recover_data_corruption,
            DisasterType.NETWORK_PARTITION: self._recover_network_partition,
            DisasterType.STORAGE_FAILURE: self._recover_storage_failure
        }
    
    async def start_monitoring(self):
        """Start continuous disaster monitoring."""
        self.logger.info("Starting disaster recovery monitoring")
        
        while True:
            try:
                await self._check_for_disasters()
                await self._process_active_disasters()
                await self._cleanup_resolved_disasters()
                
                # Parse interval (e.g., "5m" -> 300 seconds)
                interval_seconds = self._parse_interval(self.health_check_interval)
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                self.logger.error(f"Error in disaster monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _check_for_disasters(self):
        """Check system health and detect disasters."""
        try:
            health_report = await self.health_checker.check_overall_health()
            
            # Analyze health report for disaster conditions
            disasters = await self._analyze_health_for_disasters(health_report)
            
            for disaster in disasters:
                await self._handle_new_disaster(disaster)
                
        except Exception as e:
            self.logger.error(f"Failed to check for disasters: {e}")
    
    async def _analyze_health_for_disasters(self, health_report: Dict[str, Any]) -> List[DisasterEvent]:
        """Analyze health report to detect disaster conditions."""
        disasters = []
        current_time = datetime.utcnow()
        
        # Check overall system status
        overall_status = health_report.get("overall_status", "unknown")
        
        if overall_status == "critical":
            # Determine specific disaster types
            
            # Database failure
            db_health = health_report.get("database_health")
            if db_health and db_health.status == "critical":
                disasters.append(DisasterEvent(
                    event_id=f"db_failure_{int(current_time.timestamp())}",
                    disaster_type=DisasterType.DATABASE_FAILURE,
                    severity="critical",
                    affected_components=["database"],
                    affected_cities=list(health_report.get("cities", {}).keys()),
                    detected_at=current_time,
                    description=db_health.message,
                    metrics=db_health.details or {},
                    recovery_actions=[RecoveryAction.RESTART_SERVICE, RecoveryAction.RESTORE_FROM_BACKUP],
                    estimated_recovery_time_minutes=30
                ))
            
            # System overload
            system_health = health_report.get("system_health", {})
            cpu_status = system_health.get("cpu")
            memory_status = system_health.get("memory")
            
            if (cpu_status and cpu_status.status == "critical") or (memory_status and memory_status.status == "critical"):
                disasters.append(DisasterEvent(
                    event_id=f"system_overload_{int(current_time.timestamp())}",
                    disaster_type=DisasterType.SYSTEM_OVERLOAD,
                    severity="high",
                    affected_components=["system"],
                    affected_cities=list(health_report.get("cities", {}).keys()),
                    detected_at=current_time,
                    description="System resource exhaustion detected",
                    metrics={
                        "cpu": cpu_status.details if cpu_status else {},
                        "memory": memory_status.details if memory_status else {}
                    },
                    recovery_actions=[RecoveryAction.SCALE_RESOURCES, RecoveryAction.CLEAR_CACHE],
                    estimated_recovery_time_minutes=15
                ))
            
            # City-specific failures
            cities = health_report.get("cities", {})
            for city_name, city_health in cities.items():
                if city_health.get("overall_status") == "critical":
                    # Track consecutive failures
                    self.consecutive_failures[city_name] = self.consecutive_failures.get(city_name, 0) + 1
                    
                    if self.consecutive_failures[city_name] >= self.failover_threshold:
                        disasters.append(DisasterEvent(
                            event_id=f"city_failure_{city_name}_{int(current_time.timestamp())}",
                            disaster_type=DisasterType.CITY_SCRAPING_FAILURE,
                            severity="high",
                            affected_components=["scraper"],
                            affected_cities=[city_name],
                            detected_at=current_time,
                            description=f"Persistent scraping failures for {city_name}",
                            metrics=city_health.get("metrics", {}),
                            recovery_actions=[RecoveryAction.RESTART_SERVICE, RecoveryAction.FAILOVER_TO_BACKUP_CITY],
                            estimated_recovery_time_minutes=20
                        ))
                else:
                    # Reset failure counter on success
                    self.consecutive_failures[city_name] = 0
            
            # Cluster coordination failure
            cluster_health = health_report.get("cluster_health")
            if cluster_health and cluster_health.status == "critical":
                disasters.append(DisasterEvent(
                    event_id=f"cluster_failure_{int(current_time.timestamp())}",
                    disaster_type=DisasterType.CLUSTER_COORDINATION_FAILURE,
                    severity="medium",
                    affected_components=["cluster", "redis"],
                    affected_cities=list(health_report.get("cities", {}).keys()),
                    detected_at=current_time,
                    description=cluster_health.message,
                    metrics=cluster_health.details or {},
                    recovery_actions=[RecoveryAction.RESTART_SERVICE],
                    estimated_recovery_time_minutes=10
                ))
        
        return disasters
    
    async def _handle_new_disaster(self, disaster: DisasterEvent):
        """Handle a newly detected disaster."""
        # Check if this disaster is already being handled
        existing_disaster = None
        for active_disaster in self.active_disasters.values():
            if (active_disaster.disaster_type == disaster.disaster_type and 
                active_disaster.affected_cities == disaster.affected_cities):
                existing_disaster = active_disaster
                break
        
        if existing_disaster:
            # Update existing disaster
            existing_disaster.metrics.update(disaster.metrics)
            self.logger.info(f"Updated existing disaster: {existing_disaster.event_id}")
        else:
            # New disaster
            self.active_disasters[disaster.event_id] = disaster
            self.logger.critical(f"New disaster detected: {disaster.event_id} - {disaster.description}")
            
            # Send alert
            await self._send_disaster_alert(disaster)
            
            # Start recovery if auto-recovery is enabled
            if self.auto_recovery_enabled:
                await self._initiate_recovery(disaster)
    
    async def _process_active_disasters(self):
        """Process all active disasters."""
        for disaster in list(self.active_disasters.values()):
            try:
                # Check if disaster is still active
                if await self._is_disaster_resolved(disaster):
                    await self._mark_disaster_resolved(disaster)
                else:
                    # Continue recovery efforts
                    await self._continue_recovery(disaster)
                    
            except Exception as e:
                self.logger.error(f"Error processing disaster {disaster.event_id}: {e}")
    
    async def _initiate_recovery(self, disaster: DisasterEvent):
        """Initiate recovery procedures for a disaster."""
        self.logger.info(f"Initiating recovery for disaster: {disaster.event_id}")
        
        try:
            # Create recovery plan
            recovery_plan = await self._create_recovery_plan(disaster)
            
            # Execute recovery procedure
            recovery_procedure = self.recovery_procedures.get(disaster.disaster_type)
            if recovery_procedure:
                success = await recovery_procedure(disaster, recovery_plan)
                
                if success:
                    self.logger.info(f"Recovery successful for disaster: {disaster.event_id}")
                else:
                    self.logger.error(f"Recovery failed for disaster: {disaster.event_id}")
                    await self._escalate_disaster(disaster)
            else:
                self.logger.warning(f"No recovery procedure for disaster type: {disaster.disaster_type}")
                await self._escalate_disaster(disaster)
                
        except Exception as e:
            self.logger.error(f"Recovery initiation failed for disaster {disaster.event_id}: {e}")
            await self._escalate_disaster(disaster)
    
    async def _create_recovery_plan(self, disaster: DisasterEvent) -> RecoveryPlan:
        """Create a recovery plan for a disaster."""
        steps = []
        estimated_duration = disaster.estimated_recovery_time_minutes
        
        for action in disaster.recovery_actions:
            if action == RecoveryAction.RESTART_SERVICE:
                steps.append({
                    "action": "restart_service",
                    "description": "Restart affected services",
                    "timeout_minutes": 5,
                    "components": disaster.affected_components
                })
            elif action == RecoveryAction.RESTORE_FROM_BACKUP:
                steps.append({
                    "action": "restore_backup",
                    "description": "Restore from latest backup",
                    "timeout_minutes": 30,
                    "cities": disaster.affected_cities
                })
            elif action == RecoveryAction.SCALE_RESOURCES:
                steps.append({
                    "action": "scale_resources",
                    "description": "Scale system resources",
                    "timeout_minutes": 10,
                    "target_cpu_limit": "1000m",
                    "target_memory_limit": "2Gi"
                })
            elif action == RecoveryAction.CLEAR_CACHE:
                steps.append({
                    "action": "clear_cache",
                    "description": "Clear system caches",
                    "timeout_minutes": 2,
                    "cache_types": ["redis", "application"]
                })
        
        return RecoveryPlan(
            event_id=disaster.event_id,
            steps=steps,
            estimated_duration_minutes=estimated_duration,
            success_criteria=[
                "System health status returns to 'healthy'",
                "All affected cities resume normal operation",
                "No critical alerts for 10 minutes"
            ],
            rollback_plan=[
                {
                    "action": "restore_previous_state",
                    "description": "Restore system to pre-recovery state"
                }
            ],
            dependencies=[]
        )
    
    async def _recover_database_failure(self, disaster: DisasterEvent, recovery_plan: RecoveryPlan) -> bool:
        """Recover from database failure."""
        self.logger.info(f"Recovering from database failure: {disaster.event_id}")
        
        try:
            # Step 1: Try to restart database connection
            self.health_checker._initialize_connections()
            
            # Wait and check if connection is restored
            await asyncio.sleep(10)
            
            # Step 2: If still failing, restore from backup
            if not self.health_checker.db_connection:
                self.logger.info("Database connection still failing, restoring from backup")
                
                # Get latest backup
                restore_points = await self.backup_manager.get_restore_points()
                if restore_points:
                    latest_backup = restore_points[0]
                    success = await self.backup_manager.restore_from_backup(
                        latest_backup.backup_id,
                        cities=disaster.affected_cities
                    )
                    
                    if not success:
                        return False
                else:
                    self.logger.error("No backup available for restore")
                    return False
            
            # Step 3: Verify recovery
            await asyncio.sleep(30)  # Allow time for system to stabilize
            health_report = await self.health_checker.check_overall_health()
            
            db_health = health_report.get("database_health")
            return db_health and db_health.status in ["healthy", "warning"]
            
        except Exception as e:
            self.logger.error(f"Database recovery failed: {e}")
            return False
    
    async def _recover_system_overload(self, disaster: DisasterEvent, recovery_plan: RecoveryPlan) -> bool:
        """Recover from system overload."""
        self.logger.info(f"Recovering from system overload: {disaster.event_id}")
        
        try:
            # Step 1: Clear caches to free memory
            # This would typically involve clearing Redis cache, application caches, etc.
            # For now, we'll simulate this
            await asyncio.sleep(5)
            
            # Step 2: Reduce system load by temporarily disabling non-critical operations
            # This could involve reducing scraping frequency, pausing background tasks, etc.
            
            # Step 3: If in Kubernetes, trigger horizontal pod autoscaler
            # This would be handled by the Kubernetes HPA based on metrics
            
            # Step 4: Verify recovery
            await asyncio.sleep(60)  # Allow time for system to stabilize
            health_report = await self.health_checker.check_overall_health()
            
            system_health = health_report.get("system_health", {})
            cpu_healthy = system_health.get("cpu", {}).get("status") in ["healthy", "warning"]
            memory_healthy = system_health.get("memory", {}).get("status") in ["healthy", "warning"]
            
            return cpu_healthy and memory_healthy
            
        except Exception as e:
            self.logger.error(f"System overload recovery failed: {e}")
            return False
    
    async def _recover_city_scraping_failure(self, disaster: DisasterEvent, recovery_plan: RecoveryPlan) -> bool:
        """Recover from city scraping failure."""
        self.logger.info(f"Recovering from city scraping failure: {disaster.event_id}")
        
        try:
            # Step 1: Restart scraping service for affected cities
            # This would typically involve restarting the scraper process or pod
            
            # Step 2: Check for configuration issues
            # Verify city configuration, URL accessibility, etc.
            
            # Step 3: Implement temporary failover if available
            # This could involve using cached data or alternative data sources
            
            # Step 4: Verify recovery
            await asyncio.sleep(300)  # Allow time for scraping to resume
            health_report = await self.health_checker.check_overall_health()
            
            cities = health_report.get("cities", {})
            for city in disaster.affected_cities:
                city_health = cities.get(city, {})
                if city_health.get("overall_status") == "critical":
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"City scraping recovery failed: {e}")
            return False
    
    async def _recover_cluster_failure(self, disaster: DisasterEvent, recovery_plan: RecoveryPlan) -> bool:
        """Recover from cluster coordination failure."""
        self.logger.info(f"Recovering from cluster failure: {disaster.event_id}")
        
        try:
            # Step 1: Restart Redis connection
            self.health_checker._initialize_connections()
            
            # Step 2: Clear any corrupted cluster state
            if self.health_checker.redis_client:
                try:
                    # Clear cluster coordination keys
                    keys = self.health_checker.redis_client.keys("cluster:*")
                    if keys:
                        self.health_checker.redis_client.delete(*keys)
                except Exception as e:
                    self.logger.warning(f"Failed to clear Redis keys: {e}")
            
            # Step 3: Verify recovery
            await asyncio.sleep(30)
            health_report = await self.health_checker.check_overall_health()
            
            cluster_health = health_report.get("cluster_health")
            return cluster_health and cluster_health.status in ["healthy", "warning"]
            
        except Exception as e:
            self.logger.error(f"Cluster recovery failed: {e}")
            return False
    
    async def _recover_data_corruption(self, disaster: DisasterEvent, recovery_plan: RecoveryPlan) -> bool:
        """Recover from data corruption."""
        self.logger.info(f"Recovering from data corruption: {disaster.event_id}")
        
        try:
            # Step 1: Identify corrupted data
            # This would involve running data integrity checks
            
            # Step 2: Restore from backup
            restore_points = await self.backup_manager.get_restore_points()
            if restore_points:
                # Find the most recent valid backup
                for restore_point in restore_points:
                    if restore_point.data_integrity_score > 0.95:
                        success = await self.backup_manager.restore_from_backup(
                            restore_point.backup_id,
                            cities=disaster.affected_cities
                        )
                        if success:
                            return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Data corruption recovery failed: {e}")
            return False
    
    async def _recover_network_partition(self, disaster: DisasterEvent, recovery_plan: RecoveryPlan) -> bool:
        """Recover from network partition."""
        self.logger.info(f"Recovering from network partition: {disaster.event_id}")
        
        try:
            # Step 1: Wait for network to recover (network partitions often resolve themselves)
            await asyncio.sleep(60)
            
            # Step 2: Re-establish connections
            self.health_checker._initialize_connections()
            
            # Step 3: Verify recovery
            health_report = await self.health_checker.check_overall_health()
            return health_report.get("overall_status") in ["healthy", "warning"]
            
        except Exception as e:
            self.logger.error(f"Network partition recovery failed: {e}")
            return False
    
    async def _recover_storage_failure(self, disaster: DisasterEvent, recovery_plan: RecoveryPlan) -> bool:
        """Recover from storage failure."""
        self.logger.info(f"Recovering from storage failure: {disaster.event_id}")
        
        try:
            # Step 1: Check storage availability
            # This would involve checking disk space, mount points, etc.
            
            # Step 2: If storage is unavailable, try to remount or use alternative storage
            
            # Step 3: Restore data from backup if necessary
            restore_points = await self.backup_manager.get_restore_points()
            if restore_points:
                latest_backup = restore_points[0]
                success = await self.backup_manager.restore_from_backup(
                    latest_backup.backup_id,
                    cities=disaster.affected_cities
                )
                return success
            
            return False
            
        except Exception as e:
            self.logger.error(f"Storage failure recovery failed: {e}")
            return False
    
    async def _continue_recovery(self, disaster: DisasterEvent):
        """Continue recovery efforts for an ongoing disaster."""
        # Check if recovery is taking too long
        time_since_detection = datetime.utcnow() - disaster.detected_at
        
        if time_since_detection > timedelta(hours=1):
            self.logger.warning(f"Disaster recovery taking too long: {disaster.event_id}")
            await self._escalate_disaster(disaster)
    
    async def _is_disaster_resolved(self, disaster: DisasterEvent) -> bool:
        """Check if a disaster has been resolved."""
        try:
            health_report = await self.health_checker.check_overall_health()
            
            # Check overall system health
            if health_report.get("overall_status") == "critical":
                return False
            
            # Check specific components affected by this disaster
            if disaster.disaster_type == DisasterType.DATABASE_FAILURE:
                db_health = health_report.get("database_health")
                return db_health and db_health.status in ["healthy", "warning"]
            
            elif disaster.disaster_type == DisasterType.CITY_SCRAPING_FAILURE:
                cities = health_report.get("cities", {})
                for city in disaster.affected_cities:
                    city_health = cities.get(city, {})
                    if city_health.get("overall_status") == "critical":
                        return False
                return True
            
            elif disaster.disaster_type == DisasterType.CLUSTER_COORDINATION_FAILURE:
                cluster_health = health_report.get("cluster_health")
                return cluster_health and cluster_health.status in ["healthy", "warning"]
            
            # For other disaster types, check overall system health
            return health_report.get("overall_status") in ["healthy", "warning"]
            
        except Exception as e:
            self.logger.error(f"Failed to check disaster resolution: {e}")
            return False
    
    async def _mark_disaster_resolved(self, disaster: DisasterEvent):
        """Mark a disaster as resolved."""
        self.logger.info(f"Disaster resolved: {disaster.event_id}")
        
        # Remove from active disasters
        if disaster.event_id in self.active_disasters:
            del self.active_disasters[disaster.event_id]
        
        # Add to recovery history
        recovery_record = {
            "disaster": disaster.to_dict(),
            "resolved_at": datetime.utcnow().isoformat(),
            "resolution_time_minutes": (datetime.utcnow() - disaster.detected_at).total_seconds() / 60
        }
        self.recovery_history.append(recovery_record)
        
        # Reset consecutive failure counters for affected cities
        for city in disaster.affected_cities:
            self.consecutive_failures[city] = 0
        
        # Send resolution alert
        await self._send_disaster_resolution_alert(disaster)
    
    async def _escalate_disaster(self, disaster: DisasterEvent):
        """Escalate a disaster that couldn't be automatically resolved."""
        self.logger.critical(f"Escalating disaster: {disaster.event_id}")
        
        # Send escalation alert
        await self._send_disaster_escalation_alert(disaster)
        
        # Mark for manual intervention
        disaster.recovery_actions.append(RecoveryAction.MANUAL_INTERVENTION)
    
    async def _cleanup_resolved_disasters(self):
        """Clean up old resolved disasters from history."""
        cutoff_time = datetime.utcnow() - timedelta(days=30)
        
        self.recovery_history = [
            record for record in self.recovery_history
            if datetime.fromisoformat(record["resolved_at"]) > cutoff_time
        ]
    
    async def _send_disaster_alert(self, disaster: DisasterEvent):
        """Send alert for a new disaster."""
        # This would integrate with the alert webhook system
        alert_data = {
            "alertname": f"DisasterDetected_{disaster.disaster_type.value}",
            "status": "firing",
            "severity": disaster.severity,
            "summary": f"Disaster detected: {disaster.description}",
            "description": f"Disaster {disaster.event_id} detected affecting {', '.join(disaster.affected_cities)}",
            "labels": {
                "disaster_type": disaster.disaster_type.value,
                "severity": disaster.severity,
                "cities": ",".join(disaster.affected_cities)
            }
        }
        
        # Send to alert system (would be implemented based on your alerting setup)
        self.logger.critical(f"DISASTER ALERT: {alert_data}")
    
    async def _send_disaster_resolution_alert(self, disaster: DisasterEvent):
        """Send alert for disaster resolution."""
        resolution_time = (datetime.utcnow() - disaster.detected_at).total_seconds() / 60
        
        alert_data = {
            "alertname": f"DisasterResolved_{disaster.disaster_type.value}",
            "status": "resolved",
            "severity": "info",
            "summary": f"Disaster resolved: {disaster.description}",
            "description": f"Disaster {disaster.event_id} resolved after {resolution_time:.1f} minutes",
            "labels": {
                "disaster_type": disaster.disaster_type.value,
                "cities": ",".join(disaster.affected_cities)
            }
        }
        
        self.logger.info(f"DISASTER RESOLVED: {alert_data}")
    
    async def _send_disaster_escalation_alert(self, disaster: DisasterEvent):
        """Send alert for disaster escalation."""
        alert_data = {
            "alertname": f"DisasterEscalated_{disaster.disaster_type.value}",
            "status": "firing",
            "severity": "critical",
            "summary": f"Disaster escalated: {disaster.description}",
            "description": f"Disaster {disaster.event_id} requires manual intervention",
            "labels": {
                "disaster_type": disaster.disaster_type.value,
                "severity": "critical",
                "cities": ",".join(disaster.affected_cities),
                "escalated": "true"
            }
        }
        
        self.logger.critical(f"DISASTER ESCALATED: {alert_data}")
    
    def _parse_interval(self, interval_str: str) -> int:
        """Parse interval string (e.g., '5m', '1h') to seconds."""
        if interval_str.endswith('s'):
            return int(interval_str[:-1])
        elif interval_str.endswith('m'):
            return int(interval_str[:-1]) * 60
        elif interval_str.endswith('h'):
            return int(interval_str[:-1]) * 3600
        else:
            return int(interval_str)  # Assume seconds
    
    def get_disaster_status(self) -> Dict[str, Any]:
        """Get current disaster status."""
        return {
            "active_disasters": len(self.active_disasters),
            "disasters": [disaster.to_dict() for disaster in self.active_disasters.values()],
            "recovery_history_count": len(self.recovery_history),
            "consecutive_failures": self.consecutive_failures,
            "auto_recovery_enabled": self.auto_recovery_enabled
        }


async def main():
    """Main disaster recovery function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Disaster recovery orchestrator")
    parser.add_argument("action", choices=["monitor", "status", "test"], help="Action to perform")
    parser.add_argument("--disaster-type", help="Disaster type for testing")
    
    args = parser.parse_args()
    
    dr_orchestrator = DisasterRecoveryOrchestrator()
    
    if args.action == "monitor":
        await dr_orchestrator.start_monitoring()
    elif args.action == "status":
        status = dr_orchestrator.get_disaster_status()
        print(json.dumps(status, indent=2))
    elif args.action == "test":
        # Test disaster detection and recovery
        print("Testing disaster recovery system...")
        # This would implement test scenarios


if __name__ == "__main__":
    asyncio.run(main())