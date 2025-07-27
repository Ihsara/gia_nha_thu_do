#!/usr/bin/env python3
"""
Multi-city health check system for Oikotie scraper.

This module provides comprehensive health checks for multi-city operations,
including city-specific metrics, database health, and system resources.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

import duckdb
import redis
from loguru import logger

from oikotie.database.connection import get_database_connection
from oikotie.utils.config import load_config


@dataclass
class HealthStatus:
    """Health status for a component."""
    name: str
    status: str  # "healthy", "warning", "critical", "unknown"
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class CityHealthStatus:
    """Health status for a specific city."""
    city: str
    scraping_status: HealthStatus
    geospatial_status: HealthStatus
    data_quality_status: HealthStatus
    last_successful_scrape: Optional[datetime] = None
    listings_count_24h: int = 0
    success_rate_1h: float = 0.0
    geospatial_match_rate: float = 0.0
    
    def overall_status(self) -> str:
        """Calculate overall status for the city."""
        statuses = [
            self.scraping_status.status,
            self.geospatial_status.status,
            self.data_quality_status.status
        ]
        
        if "critical" in statuses:
            return "critical"
        elif "warning" in statuses:
            return "warning"
        elif all(s == "healthy" for s in statuses):
            return "healthy"
        else:
            return "unknown"


class MultiCityHealthChecker:
    """Comprehensive health checker for multi-city operations."""
    
    def __init__(self, config_path: str = "config/config.json"):
        """Initialize health checker."""
        self.config = load_config(config_path)
        self.redis_client = None
        self.db_connection = None
        self.logger = logger.bind(component="health_check")
        
        # Health check thresholds
        self.thresholds = {
            "scraping_stale_hours": 2,
            "min_success_rate": 0.95,
            "min_geospatial_match_rate": 0.95,
            "min_listings_24h": 10,
            "max_error_rate_1h": 0.05,
            "max_database_latency_ms": 1000,
            "max_memory_usage_gb": 2.0,
            "max_cpu_usage_percent": 80.0
        }
        
        # Initialize connections
        self._initialize_connections()
    
    def _initialize_connections(self):
        """Initialize database and Redis connections."""
        try:
            self.db_connection = get_database_connection()
            self.logger.info("Database connection established")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
        
        try:
            redis_config = self.config.get("global_settings", {}).get("cluster_coordination", {})
            redis_url = redis_config.get("redis_url", "redis://localhost:6379")
            self.redis_client = redis.from_url(redis_url)
            self.redis_client.ping()
            self.logger.info("Redis connection established")
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {e}")
    
    async def check_overall_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        self.logger.info("Starting comprehensive health check")
        
        health_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "unknown",
            "system_health": await self._check_system_health(),
            "database_health": await self._check_database_health(),
            "cluster_health": await self._check_cluster_health(),
            "backup_health": await self._check_backup_health(),
            "disaster_recovery_health": await self._check_disaster_recovery_health(),
            "multi_city_coordination": await self._check_multi_city_coordination(),
            "cities": {},
            "alerts": []
        }
        
        # Check each enabled city
        enabled_cities = [task["city"] for task in self.config.get("tasks", []) if task.get("enabled", False)]
        
        for city in enabled_cities:
            city_health = await self._check_city_health(city)
            health_report["cities"][city] = city_health
        
        # Calculate overall status
        health_report["overall_status"] = self._calculate_overall_status(health_report)
        
        # Generate alerts
        health_report["alerts"] = self._generate_alerts(health_report)
        
        self.logger.info(f"Health check completed. Overall status: {health_report['overall_status']}")
        return health_report
    
    async def _check_system_health(self) -> Dict[str, HealthStatus]:
        """Check system-level health metrics."""
        system_health = {}
        
        # Memory usage check
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_gb = memory.used / (1024**3)
            
            if memory_gb > self.thresholds["max_memory_usage_gb"]:
                status = "warning" if memory_gb < self.thresholds["max_memory_usage_gb"] * 1.2 else "critical"
                message = f"High memory usage: {memory_gb:.2f}GB"
            else:
                status = "healthy"
                message = f"Memory usage normal: {memory_gb:.2f}GB"
            
            system_health["memory"] = HealthStatus(
                name="memory",
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
                details={"usage_gb": memory_gb, "usage_percent": memory.percent}
            )
        except ImportError:
            system_health["memory"] = HealthStatus(
                name="memory",
                status="unknown",
                message="psutil not available",
                timestamp=datetime.utcnow()
            )
        
        # CPU usage check
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            
            if cpu_percent > self.thresholds["max_cpu_usage_percent"]:
                status = "warning" if cpu_percent < 90 else "critical"
                message = f"High CPU usage: {cpu_percent:.1f}%"
            else:
                status = "healthy"
                message = f"CPU usage normal: {cpu_percent:.1f}%"
            
            system_health["cpu"] = HealthStatus(
                name="cpu",
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
                details={"usage_percent": cpu_percent}
            )
        except ImportError:
            system_health["cpu"] = HealthStatus(
                name="cpu",
                status="unknown",
                message="psutil not available",
                timestamp=datetime.utcnow()
            )
        
        return system_health
    
    async def _check_database_health(self) -> HealthStatus:
        """Check database health and performance."""
        if not self.db_connection:
            return HealthStatus(
                name="database",
                status="critical",
                message="Database connection not available",
                timestamp=datetime.utcnow()
            )
        
        try:
            # Test basic connectivity and measure latency
            start_time = time.time()
            result = self.db_connection.execute("SELECT 1").fetchone()
            latency_ms = (time.time() - start_time) * 1000
            
            if latency_ms > self.thresholds["max_database_latency_ms"]:
                status = "warning"
                message = f"High database latency: {latency_ms:.1f}ms"
            else:
                status = "healthy"
                message = f"Database responsive: {latency_ms:.1f}ms"
            
            # Check database size and table counts
            tables_info = self.db_connection.execute("""
                SELECT table_name, estimated_size 
                FROM duckdb_tables() 
                WHERE schema_name = 'main'
            """).fetchall()
            
            details = {
                "latency_ms": latency_ms,
                "tables": len(tables_info),
                "table_info": [{"name": row[0], "size": row[1]} for row in tables_info]
            }
            
            return HealthStatus(
                name="database",
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
                details=details
            )
            
        except Exception as e:
            return HealthStatus(
                name="database",
                status="critical",
                message=f"Database health check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def _check_cluster_health(self) -> HealthStatus:
        """Check cluster coordination health."""
        if not self.redis_client:
            return HealthStatus(
                name="cluster",
                status="warning",
                message="Redis not available - running in standalone mode",
                timestamp=datetime.utcnow()
            )
        
        try:
            # Test Redis connectivity
            start_time = time.time()
            self.redis_client.ping()
            latency_ms = (time.time() - start_time) * 1000
            
            # Get cluster information
            info = self.redis_client.info()
            connected_clients = info.get("connected_clients", 0)
            used_memory_mb = info.get("used_memory", 0) / (1024 * 1024)
            
            if latency_ms > 100:
                status = "warning"
                message = f"High Redis latency: {latency_ms:.1f}ms"
            else:
                status = "healthy"
                message = f"Cluster coordination healthy: {latency_ms:.1f}ms"
            
            details = {
                "latency_ms": latency_ms,
                "connected_clients": connected_clients,
                "used_memory_mb": used_memory_mb,
                "redis_version": info.get("redis_version", "unknown")
            }
            
            return HealthStatus(
                name="cluster",
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
                details=details
            )
            
        except Exception as e:
            return HealthStatus(
                name="cluster",
                status="critical",
                message=f"Cluster health check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def _check_city_health(self, city: str) -> Dict[str, Any]:
        """Check health for a specific city."""
        if not self.db_connection:
            return {
                "overall_status": "critical",
                "message": "Database not available",
                "details": {}
            }
        
        try:
            # Get recent scraping statistics
            stats_query = """
            SELECT 
                COUNT(*) as total_listings,
                COUNT(CASE WHEN scraped_at > NOW() - INTERVAL '24 hours' THEN 1 END) as listings_24h,
                COUNT(CASE WHEN scraped_at > NOW() - INTERVAL '1 hour' THEN 1 END) as listings_1h,
                MAX(scraped_at) as last_scrape,
                AVG(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1.0 ELSE 0.0 END) as geospatial_match_rate
            FROM listings 
            WHERE city = ?
            """
            
            stats = self.db_connection.execute(stats_query, [city]).fetchone()
            
            if not stats:
                return {
                    "overall_status": "unknown",
                    "message": f"No data found for {city}",
                    "details": {}
                }
            
            total_listings, listings_24h, listings_1h, last_scrape, geospatial_match_rate = stats
            
            # Check scraping status
            scraping_status = self._evaluate_scraping_status(city, last_scrape, listings_24h)
            
            # Check geospatial status
            geospatial_status = self._evaluate_geospatial_status(city, geospatial_match_rate or 0.0)
            
            # Check data quality status
            data_quality_status = self._evaluate_data_quality_status(city, total_listings, listings_24h)
            
            city_health = CityHealthStatus(
                city=city,
                scraping_status=scraping_status,
                geospatial_status=geospatial_status,
                data_quality_status=data_quality_status,
                last_successful_scrape=last_scrape,
                listings_count_24h=listings_24h or 0,
                geospatial_match_rate=geospatial_match_rate or 0.0
            )
            
            return {
                "overall_status": city_health.overall_status(),
                "scraping": city_health.scraping_status.to_dict(),
                "geospatial": city_health.geospatial_status.to_dict(),
                "data_quality": city_health.data_quality_status.to_dict(),
                "metrics": {
                    "total_listings": total_listings or 0,
                    "listings_24h": listings_24h or 0,
                    "listings_1h": listings_1h or 0,
                    "last_scrape": last_scrape.isoformat() if last_scrape else None,
                    "geospatial_match_rate": geospatial_match_rate or 0.0
                }
            }
            
        except Exception as e:
            self.logger.error(f"City health check failed for {city}: {e}")
            return {
                "overall_status": "critical",
                "message": f"Health check failed: {str(e)}",
                "details": {}
            }
    
    def _evaluate_scraping_status(self, city: str, last_scrape: Optional[datetime], listings_24h: int) -> HealthStatus:
        """Evaluate scraping health status."""
        now = datetime.utcnow()
        
        if not last_scrape:
            return HealthStatus(
                name="scraping",
                status="critical",
                message=f"No scraping data found for {city}",
                timestamp=now
            )
        
        hours_since_scrape = (now - last_scrape).total_seconds() / 3600
        
        if hours_since_scrape > self.thresholds["scraping_stale_hours"]:
            status = "warning" if hours_since_scrape < 6 else "critical"
            message = f"Last scrape {hours_since_scrape:.1f} hours ago"
        elif listings_24h < self.thresholds["min_listings_24h"]:
            status = "warning"
            message = f"Low listing count: {listings_24h} in 24h"
        else:
            status = "healthy"
            message = f"Scraping active: {listings_24h} listings in 24h"
        
        return HealthStatus(
            name="scraping",
            status=status,
            message=message,
            timestamp=now,
            details={
                "hours_since_last_scrape": hours_since_scrape,
                "listings_24h": listings_24h
            }
        )
    
    def _evaluate_geospatial_status(self, city: str, match_rate: float) -> HealthStatus:
        """Evaluate geospatial data health status."""
        now = datetime.utcnow()
        
        if match_rate < self.thresholds["min_geospatial_match_rate"]:
            status = "warning" if match_rate > 0.9 else "critical"
            message = f"Low geospatial match rate: {match_rate:.1%}"
        else:
            status = "healthy"
            message = f"Geospatial matching healthy: {match_rate:.1%}"
        
        return HealthStatus(
            name="geospatial",
            status=status,
            message=message,
            timestamp=now,
            details={"match_rate": match_rate}
        )
    
    def _evaluate_data_quality_status(self, city: str, total_listings: int, listings_24h: int) -> HealthStatus:
        """Evaluate data quality health status."""
        now = datetime.utcnow()
        
        if total_listings == 0:
            status = "critical"
            message = f"No listings data for {city}"
        elif listings_24h == 0:
            status = "warning"
            message = f"No new listings in 24h for {city}"
        else:
            status = "healthy"
            message = f"Data quality good: {total_listings} total, {listings_24h} recent"
        
        return HealthStatus(
            name="data_quality",
            status=status,
            message=message,
            timestamp=now,
            details={
                "total_listings": total_listings,
                "listings_24h": listings_24h
            }
        )
    
    def _calculate_overall_status(self, health_report: Dict[str, Any]) -> str:
        """Calculate overall system status."""
        all_statuses = []
        
        # System health
        system_health = health_report.get("system_health", {})
        all_statuses.extend([status.status for status in system_health.values()])
        
        # Database health
        db_health = health_report.get("database_health")
        if db_health:
            all_statuses.append(db_health.status)
        
        # Cluster health
        cluster_health = health_report.get("cluster_health")
        if cluster_health:
            all_statuses.append(cluster_health.status)
        
        # City health
        cities = health_report.get("cities", {})
        all_statuses.extend([city["overall_status"] for city in cities.values()])
        
        # Determine overall status
        if "critical" in all_statuses:
            return "critical"
        elif "warning" in all_statuses:
            return "warning"
        elif all(s == "healthy" for s in all_statuses):
            return "healthy"
        else:
            return "unknown"
    
    def _generate_alerts(self, health_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on health report."""
        alerts = []
        
        # System alerts
        system_health = health_report.get("system_health", {})
        for component, status in system_health.items():
            if status.status in ["warning", "critical"]:
                alerts.append({
                    "type": "system",
                    "component": component,
                    "severity": status.status,
                    "message": status.message,
                    "timestamp": status.timestamp.isoformat()
                })
        
        # Database alerts
        db_health = health_report.get("database_health")
        if db_health and db_health.status in ["warning", "critical"]:
            alerts.append({
                "type": "database",
                "component": "database",
                "severity": db_health.status,
                "message": db_health.message,
                "timestamp": db_health.timestamp.isoformat()
            })
        
        # City alerts
        cities = health_report.get("cities", {})
        for city_name, city_health in cities.items():
            if city_health["overall_status"] in ["warning", "critical"]:
                alerts.append({
                    "type": "city",
                    "component": city_name,
                    "severity": city_health["overall_status"],
                    "message": f"{city_name} health issues detected",
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": city_health
                })
        
        return alerts
    
    async def _check_backup_health(self) -> HealthStatus:
        """Check backup system health."""
        try:
            # Check if backup directory exists and is writable
            backup_dir = Path("backups")
            if not backup_dir.exists():
                return HealthStatus(
                    name="backup",
                    status="critical",
                    message="Backup directory does not exist",
                    timestamp=datetime.utcnow()
                )
            
            # Check recent backup files
            recent_backups = list(backup_dir.glob("*.metadata.json"))
            if not recent_backups:
                return HealthStatus(
                    name="backup",
                    status="warning",
                    message="No backup metadata files found",
                    timestamp=datetime.utcnow()
                )
            
            # Check if latest backup is recent (within 24 hours)
            latest_backup = max(recent_backups, key=lambda x: x.stat().st_mtime)
            backup_age_hours = (time.time() - latest_backup.stat().st_mtime) / 3600
            
            if backup_age_hours > 24:
                status = "warning" if backup_age_hours < 48 else "critical"
                message = f"Latest backup is {backup_age_hours:.1f} hours old"
            else:
                status = "healthy"
                message = f"Latest backup is {backup_age_hours:.1f} hours old"
            
            return HealthStatus(
                name="backup",
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
                details={
                    "backup_count": len(recent_backups),
                    "latest_backup_age_hours": backup_age_hours,
                    "backup_directory": str(backup_dir)
                }
            )
            
        except Exception as e:
            return HealthStatus(
                name="backup",
                status="critical",
                message=f"Backup health check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def _check_disaster_recovery_health(self) -> HealthStatus:
        """Check disaster recovery system health."""
        try:
            # Check if disaster recovery monitoring is active
            # This would typically check if the disaster recovery service is running
            
            # For now, we'll check if the disaster recovery configuration exists
            dr_config = self.config.get("disaster_recovery", {})
            
            if not dr_config.get("enabled", False):
                return HealthStatus(
                    name="disaster_recovery",
                    status="warning",
                    message="Disaster recovery is disabled",
                    timestamp=datetime.utcnow()
                )
            
            # Check if automation is enabled
            automation_enabled = dr_config.get("automation", {}).get("enabled", False)
            
            if not automation_enabled:
                status = "warning"
                message = "Disaster recovery automation is disabled"
            else:
                status = "healthy"
                message = "Disaster recovery system is active"
            
            return HealthStatus(
                name="disaster_recovery",
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
                details={
                    "enabled": dr_config.get("enabled", False),
                    "automation_enabled": automation_enabled,
                    "rto": dr_config.get("rto", "unknown"),
                    "rpo": dr_config.get("rpo", "unknown")
                }
            )
            
        except Exception as e:
            return HealthStatus(
                name="disaster_recovery",
                status="critical",
                message=f"Disaster recovery health check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def _check_multi_city_coordination(self) -> HealthStatus:
        """Check multi-city coordination health."""
        try:
            enabled_cities = [task["city"] for task in self.config.get("tasks", []) if task.get("enabled", False)]
            
            if len(enabled_cities) < 2:
                return HealthStatus(
                    name="multi_city_coordination",
                    status="warning",
                    message=f"Only {len(enabled_cities)} city enabled",
                    timestamp=datetime.utcnow(),
                    details={"enabled_cities": enabled_cities}
                )
            
            # Check if Redis is available for coordination
            if not self.redis_client:
                return HealthStatus(
                    name="multi_city_coordination",
                    status="warning",
                    message="Redis not available - running in standalone mode",
                    timestamp=datetime.utcnow(),
                    details={"enabled_cities": enabled_cities}
                )
            
            # Check coordination keys in Redis
            try:
                coordination_keys = self.redis_client.keys("coordination:*")
                active_nodes = len(coordination_keys)
                
                if active_nodes == 0:
                    status = "warning"
                    message = "No active coordination nodes found"
                else:
                    status = "healthy"
                    message = f"Multi-city coordination active with {active_nodes} nodes"
                
                return HealthStatus(
                    name="multi_city_coordination",
                    status=status,
                    message=message,
                    timestamp=datetime.utcnow(),
                    details={
                        "enabled_cities": enabled_cities,
                        "active_nodes": active_nodes,
                        "coordination_keys": len(coordination_keys)
                    }
                )
                
            except Exception as e:
                return HealthStatus(
                    name="multi_city_coordination",
                    status="critical",
                    message=f"Redis coordination check failed: {str(e)}",
                    timestamp=datetime.utcnow(),
                    details={"enabled_cities": enabled_cities}
                )
            
        except Exception as e:
            return HealthStatus(
                name="multi_city_coordination",
                status="critical",
                message=f"Multi-city coordination health check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )


async def main():
    """Main health check function."""
    health_checker = MultiCityHealthChecker()
    health_report = await health_checker.check_overall_health()
    
    # Output health report
    print(json.dumps(health_report, indent=2, default=str))
    
    # Return appropriate exit code
    overall_status = health_report.get("overall_status", "unknown")
    if overall_status == "critical":
        exit(2)
    elif overall_status == "warning":
        exit(1)
    else:
        exit(0)


if __name__ == "__main__":
    asyncio.run(main())