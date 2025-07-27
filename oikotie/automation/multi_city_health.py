"""
Multi-city health check implementation for Oikotie Scraper.

This module extends the base health check system to provide city-specific health metrics
and monitoring capabilities for multi-city deployments.
"""

import time
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

from loguru import logger

from .monitoring import HealthChecker, MetricsCollector
from ..database.manager import EnhancedDatabaseManager
from .config import ScraperConfig


class MultiCityHealthChecker(HealthChecker):
    """Extended health checker with city-specific health metrics."""
    
    def __init__(self, db_manager: Optional[EnhancedDatabaseManager] = None, config: Optional[ScraperConfig] = None):
        """
        Initialize multi-city health checker.
        
        Args:
            db_manager: Database manager for health checks
            config: Scraper configuration
        """
        super().__init__(db_manager)
        self.config = config
        self.city_health_checks = {}
        self.city_health_status = {}
        
        # Register city-specific health checks
        self._register_city_health_checks()
        
        logger.info("Multi-city health checker initialized")
    
    def _register_city_health_checks(self) -> None:
        """Register health checks for each enabled city."""
        if not self.config:
            logger.warning("No configuration provided, skipping city-specific health checks")
            return
            
        for city_config in self.config.get_enabled_cities():
            city_name = city_config.get('city')
            if not city_name:
                continue
                
            logger.info(f"Registering health checks for city: {city_name}")
            
            # Register city-specific checks
            self.register_check(
                f'database_{city_name.lower()}', 
                lambda c=city_name: self._check_city_database_health(c)
            )
            self.register_check(
                f'data_freshness_{city_name.lower()}', 
                lambda c=city_name: self._check_city_data_freshness(c)
            )
            self.register_check(
                f'geospatial_{city_name.lower()}', 
                lambda c=city_name: self._check_city_geospatial_health(c)
            )
    
    def _check_city_database_health(self, city: str) -> bool:
        """
        Check database health for a specific city.
        
        Args:
            city: City name
            
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            # Test database connection and city-specific query
            with self.db_manager.get_connection() as conn:
                query = f"SELECT COUNT(*) FROM listings WHERE city = ?"
                result = conn.execute(query, (city,)).fetchone()
                
                # Store the result in city health status
                if result and result[0] is not None:
                    self.city_health_status[f"{city}_record_count"] = result[0]
                    return True
                return False
        except Exception as e:
            logger.error(f"City database health check failed for {city}: {e}")
            return False
    
    def _check_city_data_freshness(self, city: str) -> bool:
        """
        Check data freshness for a specific city.
        
        Args:
            city: City name
            
        Returns:
            bool: True if data is fresh, False otherwise
        """
        try:
            # Get the staleness threshold from city config
            staleness_hours = 24  # Default
            if self.config:
                for city_config in self.config.get_enabled_cities():
                    if city_config.get('city') == city:
                        staleness_hours = city_config.get('staleness_threshold_hours', 24)
                        break
            
            # Check for recent data
            with self.db_manager.get_connection() as conn:
                query = """
                    SELECT MAX(scraped_at) FROM listings 
                    WHERE city = ? AND scraped_at IS NOT NULL
                """
                result = conn.execute(query, (city,)).fetchone()
                
                if not result or not result[0]:
                    logger.warning(f"No scraped_at data found for {city}")
                    return False
                
                # Parse the timestamp
                try:
                    last_scraped = datetime.fromisoformat(result[0].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    try:
                        last_scraped = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                    except (ValueError, AttributeError):
                        logger.error(f"Could not parse timestamp: {result[0]}")
                        return False
                
                # Calculate age in hours
                age_hours = (datetime.now() - last_scraped).total_seconds() / 3600
                
                # Store the result in city health status
                self.city_health_status[f"{city}_data_age_hours"] = age_hours
                self.city_health_status[f"{city}_last_scraped"] = last_scraped.isoformat()
                
                # Check if data is fresh enough
                return age_hours <= staleness_hours
                
        except Exception as e:
            logger.error(f"City data freshness check failed for {city}: {e}")
            return False
    
    def _check_city_geospatial_health(self, city: str) -> bool:
        """
        Check geospatial data health for a specific city.
        
        Args:
            city: City name
            
        Returns:
            bool: True if geospatial data is healthy, False otherwise
        """
        try:
            # Check geospatial match rate
            with self.db_manager.get_connection() as conn:
                query = """
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 ELSE 0 END) as geocoded
                    FROM listings 
                    WHERE city = ?
                """
                result = conn.execute(query, (city,)).fetchone()
                
                if not result or not result[0] or result[0] == 0:
                    logger.warning(f"No listings found for {city}")
                    return False
                
                total = result[0]
                geocoded = result[1] or 0
                
                # Calculate match rate
                match_rate = geocoded / total if total > 0 else 0
                
                # Store the result in city health status
                self.city_health_status[f"{city}_total_listings"] = total
                self.city_health_status[f"{city}_geocoded_listings"] = geocoded
                self.city_health_status[f"{city}_geocoding_rate"] = match_rate
                
                # Check if match rate is acceptable (95% or higher)
                return match_rate >= 0.95
                
        except Exception as e:
            logger.error(f"City geospatial health check failed for {city}: {e}")
            return False
    
    def get_city_health(self, city: str) -> Dict[str, Any]:
        """
        Get health status for a specific city.
        
        Args:
            city: City name
            
        Returns:
            Dict: Health status for the city
        """
        # Run city-specific health checks
        database_health = self._check_city_database_health(city)
        data_freshness = self._check_city_data_freshness(city)
        geospatial_health = self._check_city_geospatial_health(city)
        
        # Compile health status
        status = "healthy" if all([database_health, data_freshness, geospatial_health]) else "unhealthy"
        
        # Get city-specific metrics
        metrics = {k: v for k, v in self.city_health_status.items() if k.startswith(f"{city}_")}
        
        return {
            "city": city,
            "status": status,
            "checks": {
                "database": database_health,
                "data_freshness": data_freshness,
                "geospatial": geospatial_health
            },
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_all_cities_health(self) -> Dict[str, Any]:
        """
        Get health status for all cities.
        
        Returns:
            Dict: Health status for all cities
        """
        if not self.config:
            return {"error": "No configuration available"}
            
        cities_health = {}
        overall_status = "healthy"
        
        for city_config in self.config.get_enabled_cities():
            city_name = city_config.get('city')
            if not city_name:
                continue
                
            city_health = self.get_city_health(city_name)
            cities_health[city_name] = city_health
            
            # If any city is unhealthy, the overall status is unhealthy
            if city_health["status"] != "healthy":
                overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "cities": cities_health,
            "timestamp": datetime.now().isoformat()
        }


class MultiCityMetricsCollector(MetricsCollector):
    """Extended metrics collector with city-specific metrics."""
    
    def __init__(self, db_manager: Optional[EnhancedDatabaseManager] = None, config: Optional[ScraperConfig] = None):
        """
        Initialize multi-city metrics collector.
        
        Args:
            db_manager: Database manager for metrics collection
            config: Scraper configuration
        """
        super().__init__(db_manager)
        self.config = config
        self.city_metrics = {}
        
        logger.info("Multi-city metrics collector initialized")
    
    def collect_city_metrics(self, city: str) -> Dict[str, Any]:
        """
        Collect metrics for a specific city.
        
        Args:
            city: City name
            
        Returns:
            Dict: Metrics for the city
        """
        metrics = {}
        
        try:
            with self.db_manager.get_connection() as conn:
                # Listing counts
                query = "SELECT COUNT(*) FROM listings WHERE city = ?"
                result = conn.execute(query, (city,)).fetchone()
                metrics["total_listings"] = result[0] if result else 0
                
                # Geocoding rate
                query = """
                    SELECT 
                        SUM(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 ELSE 0 END) as geocoded
                    FROM listings 
                    WHERE city = ?
                """
                result = conn.execute(query, (city,)).fetchone()
                geocoded = result[0] if result and result[0] else 0
                metrics["geocoded_listings"] = geocoded
                metrics["geocoding_rate"] = geocoded / metrics["total_listings"] if metrics["total_listings"] > 0 else 0
                
                # Data freshness
                query = "SELECT MAX(scraped_at) FROM listings WHERE city = ?"
                result = conn.execute(query, (city,)).fetchone()
                last_scraped = result[0] if result and result[0] else None
                metrics["last_scraped"] = last_scraped
                
                if last_scraped:
                    try:
                        last_scraped_dt = datetime.fromisoformat(last_scraped.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        try:
                            last_scraped_dt = datetime.strptime(last_scraped, '%Y-%m-%d %H:%M:%S')
                        except (ValueError, AttributeError):
                            last_scraped_dt = None
                    
                    if last_scraped_dt:
                        metrics["data_age_hours"] = (datetime.now() - last_scraped_dt).total_seconds() / 3600
                
                # Error counts
                query = """
                    SELECT COUNT(*) FROM listings 
                    WHERE city = ? AND last_error IS NOT NULL AND last_error != ''
                """
                result = conn.execute(query, (city,)).fetchone()
                metrics["error_count"] = result[0] if result else 0
                
                # Retry counts
                query = """
                    SELECT AVG(retry_count) FROM listings 
                    WHERE city = ? AND retry_count > 0
                """
                result = conn.execute(query, (city,)).fetchone()
                metrics["avg_retry_count"] = result[0] if result and result[0] else 0
                
        except Exception as e:
            logger.error(f"Failed to collect metrics for city {city}: {e}")
            metrics["error"] = str(e)
        
        # Store metrics
        self.city_metrics[city] = metrics
        
        return metrics
    
    def collect_all_city_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Collect metrics for all cities.
        
        Returns:
            Dict: Metrics for all cities
        """
        if not self.config:
            return {"error": "No configuration available"}
            
        all_metrics = {}
        
        for city_config in self.config.get_enabled_cities():
            city_name = city_config.get('city')
            if not city_name:
                continue
                
            city_metrics = self.collect_city_metrics(city_name)
            all_metrics[city_name] = city_metrics
        
        return all_metrics
    
    def get_prometheus_city_metrics(self) -> List[str]:
        """
        Get Prometheus metrics for all cities.
        
        Returns:
            List[str]: Prometheus metrics
        """
        metrics = []
        
        # Collect latest metrics
        self.collect_all_city_metrics()
        
        # Convert to Prometheus format
        for city, city_metrics in self.city_metrics.items():
            city_label = f'city="{city}"'
            
            # Total listings
            metrics.append(f'scraper_city_listings_total{{{city_label}}} {city_metrics.get("total_listings", 0)}')
            
            # Geocoded listings
            metrics.append(f'scraper_city_geocoded_listings{{{city_label}}} {city_metrics.get("geocoded_listings", 0)}')
            
            # Geocoding rate
            metrics.append(f'scraper_city_geospatial_match_rate{{{city_label}}} {city_metrics.get("geocoding_rate", 0)}')
            
            # Data age in hours
            if "data_age_hours" in city_metrics:
                metrics.append(f'scraper_city_data_age_hours{{{city_label}}} {city_metrics.get("data_age_hours", 0)}')
            
            # Error count
            metrics.append(f'scraper_city_errors_total{{{city_label}}} {city_metrics.get("error_count", 0)}')
            
            # Average retry count
            metrics.append(f'scraper_city_avg_retry_count{{{city_label}}} {city_metrics.get("avg_retry_count", 0)}')
        
        return metrics