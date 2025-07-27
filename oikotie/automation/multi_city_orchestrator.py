"""
Enhanced Multi-City Scraper Orchestrator for Daily Automation

This module provides comprehensive multi-city automation with Redis cluster coordination,
smart work distribution, exponential backoff, circuit breaker patterns, and comprehensive
audit logging and data lineage tracking.
"""

import json
import time
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from loguru import logger
import redis
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..database.manager import EnhancedDatabaseManager
from ..scraper import OikotieScraper, worker_scrape_details
from .cluster import ClusterCoordinator, WorkItem, WorkItemStatus, create_cluster_coordinator
from .retry_manager import RetryManager, RetryConfiguration, FailureCategory
from .data_governance import DataGovernanceManager, DataSource
from .circuit_breaker import CircuitBreaker, CircuitBreakerState
from .audit_logger import AuditLogger, AuditEvent, AuditEventType


class ExecutionStatus(Enum):
    """Multi-city execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEGRADED = "degraded"  # Some cities failed but others succeeded


class CityExecutionResult(Enum):
    """Individual city execution result."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class CityConfig:
    """Configuration for a single city."""
    city: str
    enabled: bool
    url: str
    max_detail_workers: int = 5
    rate_limit_seconds: float = 1.0
    coordinate_bounds: Tuple[float, float, float, float] = None
    geospatial_sources: List[str] = None
    data_governance: Dict[str, Any] = None
    priority: int = 1  # Higher number = higher priority
    
    def __post_init__(self):
        if self.geospatial_sources is None:
            self.geospatial_sources = []
        if self.data_governance is None:
            self.data_governance = {}


@dataclass
class CityExecutionMetrics:
    """Metrics for a single city execution."""
    city: str
    execution_id: str
    status: CityExecutionResult
    started_at: datetime
    completed_at: Optional[datetime] = None
    urls_discovered: int = 0
    urls_processed: int = 0
    listings_new: int = 0
    listings_updated: int = 0
    listings_failed: int = 0
    execution_time_seconds: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    error_summary: Optional[str] = None
    retry_count: int = 0
    circuit_breaker_trips: int = 0
    rate_limit_hits: int = 0


@dataclass
class MultiCityExecutionResult:
    """Result of multi-city execution."""
    execution_id: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_cities: int = 0
    successful_cities: int = 0
    failed_cities: int = 0
    skipped_cities: int = 0
    total_listings_new: int = 0
    total_listings_failed: int = 0
    execution_time_seconds: Optional[float] = None
    city_results: List[CityExecutionMetrics] = None
    cluster_coordination_enabled: bool = False
    error_summary: Optional[str] = None
    
    def __post_init__(self):
        if self.city_results is None:
            self.city_results = []


class MultiCityScraperOrchestrator:
    """
    Enhanced multi-city scraper orchestrator with comprehensive automation features.
    
    Features:
    - Redis cluster coordination for distributed execution
    - Smart work distribution across cities and nodes
    - Exponential backoff and circuit breaker patterns
    - Comprehensive audit logging and data lineage tracking
    - City-specific error handling and recovery mechanisms
    """
    
    def __init__(self, 
                 config_path: str = 'config/config.json',
                 redis_url: Optional[str] = None,
                 enable_cluster_coordination: bool = True):
        """
        Initialize multi-city scraper orchestrator.
        
        Args:
            config_path: Path to configuration file
            redis_url: Redis connection URL for cluster coordination
            enable_cluster_coordination: Enable Redis cluster coordination
        """
        self.config_path = config_path
        self.enable_cluster_coordination = enable_cluster_coordination
        
        # Load configuration
        self.city_configs = self._load_city_configurations()
        self.global_settings = self._load_global_settings()
        
        # Initialize core components
        self.db_manager = EnhancedDatabaseManager()
        self.data_governance = DataGovernanceManager(self.db_manager)
        self.audit_logger = AuditLogger(self.db_manager)
        
        # Initialize cluster coordination if enabled
        self.cluster_coordinator: Optional[ClusterCoordinator] = None
        if enable_cluster_coordination and redis_url:
            try:
                self.cluster_coordinator = create_cluster_coordinator(redis_url)
                self.cluster_coordinator.start_health_monitoring()
                logger.info("Cluster coordination enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize cluster coordination: {e}")
                self.enable_cluster_coordination = False
        
        # Initialize city-specific components
        self.retry_managers = self._initialize_retry_managers()
        self.circuit_breakers = self._initialize_circuit_breakers()
        
        # Execution tracking
        self.current_execution_id: Optional[str] = None
        self.execution_lock = threading.Lock()
        
        logger.info(f"Multi-city orchestrator initialized for {len(self.city_configs)} cities")
    
    def run_daily_automation(self) -> MultiCityExecutionResult:
        """
        Execute daily automation for all enabled cities.
        
        Returns:
            MultiCityExecutionResult with comprehensive execution details
        """
        execution_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        with self.execution_lock:
            self.current_execution_id = execution_id
        
        logger.info(f"Starting multi-city daily automation (execution: {execution_id})")
        
        # Initialize result
        result = MultiCityExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.RUNNING,
            started_at=start_time,
            cluster_coordination_enabled=self.enable_cluster_coordination
        )
        
        # Log automation start
        self.audit_logger.log_event(AuditEvent(
            event_type=AuditEventType.AUTOMATION_START,
            execution_id=execution_id,
            details={
                'total_cities': len(self.city_configs),
                'enabled_cities': [c.city for c in self.city_configs if c.enabled],
                'cluster_coordination': self.enable_cluster_coordination
            }
        ))
        
        try:
            # Get enabled cities sorted by priority
            enabled_cities = [c for c in self.city_configs if c.enabled]
            enabled_cities.sort(key=lambda x: x.priority, reverse=True)
            
            result.total_cities = len(enabled_cities)
            
            if not enabled_cities:
                logger.warning("No enabled cities found in configuration")
                result.status = ExecutionStatus.COMPLETED
                result.completed_at = datetime.now()
                return result
            
            # Execute cities based on coordination mode
            if self.enable_cluster_coordination and self.cluster_coordinator:
                city_results = self._execute_cities_with_cluster_coordination(
                    enabled_cities, execution_id
                )
            else:
                city_results = self._execute_cities_sequentially(
                    enabled_cities, execution_id
                )
            
            result.city_results = city_results
            
            # Calculate summary statistics
            result.successful_cities = sum(1 for r in city_results if r.status == CityExecutionResult.SUCCESS)
            result.failed_cities = sum(1 for r in city_results if r.status == CityExecutionResult.FAILED)
            result.skipped_cities = sum(1 for r in city_results if r.status == CityExecutionResult.SKIPPED)
            result.total_listings_new = sum(r.listings_new for r in city_results)
            result.total_listings_failed = sum(r.listings_failed for r in city_results)
            
            # Determine overall status
            if result.successful_cities == result.total_cities:
                result.status = ExecutionStatus.COMPLETED
            elif result.successful_cities > 0:
                result.status = ExecutionStatus.DEGRADED
            else:
                result.status = ExecutionStatus.FAILED
            
            result.completed_at = datetime.now()
            result.execution_time_seconds = (result.completed_at - result.started_at).total_seconds()
            
            # Log automation completion
            self.audit_logger.log_event(AuditEvent(
                event_type=AuditEventType.AUTOMATION_COMPLETE,
                execution_id=execution_id,
                details={
                    'status': result.status.value,
                    'successful_cities': result.successful_cities,
                    'failed_cities': result.failed_cities,
                    'total_listings_new': result.total_listings_new,
                    'execution_time_seconds': result.execution_time_seconds
                }
            ))
            
            logger.success(f"Multi-city automation completed: "
                          f"{result.successful_cities}/{result.total_cities} cities successful, "
                          f"{result.total_listings_new} new listings, "
                          f"{result.execution_time_seconds:.1f}s")
            
        except Exception as e:
            logger.error(f"Multi-city automation failed: {e}")
            result.status = ExecutionStatus.FAILED
            result.completed_at = datetime.now()
            result.error_summary = str(e)
            result.execution_time_seconds = (result.completed_at - result.started_at).total_seconds()
            
            # Log automation failure
            self.audit_logger.log_event(AuditEvent(
                event_type=AuditEventType.AUTOMATION_ERROR,
                execution_id=execution_id,
                details={
                    'error': str(e),
                    'execution_time_seconds': result.execution_time_seconds
                }
            ))
        
        finally:
            with self.execution_lock:
                self.current_execution_id = None
        
        return result
    
    def _execute_cities_with_cluster_coordination(self, 
                                                 cities: List[CityConfig], 
                                                 execution_id: str) -> List[CityExecutionMetrics]:
        """
        Execute cities with Redis cluster coordination.
        
        Args:
            cities: List of city configurations
            execution_id: Execution ID for tracking
            
        Returns:
            List of city execution metrics
        """
        logger.info(f"Executing {len(cities)} cities with cluster coordination")
        
        # Create work items for each city
        work_items = []
        for city_config in cities:
            work_item = WorkItem(
                work_id=f"{execution_id}-{city_config.city}",
                city=city_config.city,
                url=city_config.url,
                priority=city_config.priority
            )
            work_items.append(work_item)
        
        # Distribute work across cluster
        distribution_result = self.cluster_coordinator.distribute_work(work_items)
        logger.info(f"Distributed {distribution_result.distributed_items} work items "
                   f"across {len(distribution_result.node_assignments)} nodes")
        
        # Process work items assigned to this node
        city_results = []
        processed_cities = set()
        
        # Get work for this node and process
        while len(processed_cities) < len(cities):
            node_work = self.cluster_coordinator.get_work_for_node(
                self.cluster_coordinator.node_id, 
                count=1
            )
            
            if not node_work:
                time.sleep(5)  # Wait for work or other nodes to complete
                continue
            
            for work_item in node_work:
                if work_item.city in processed_cities:
                    continue
                
                # Find city config
                city_config = next((c for c in cities if c.city == work_item.city), None)
                if not city_config:
                    self.cluster_coordinator.fail_work_item(
                        work_item, f"City configuration not found: {work_item.city}"
                    )
                    continue
                
                # Execute city with coordination
                try:
                    city_result = self._execute_single_city_with_coordination(
                        city_config, execution_id, work_item
                    )
                    city_results.append(city_result)
                    processed_cities.add(work_item.city)
                    
                    # Mark work as completed
                    self.cluster_coordinator.complete_work_item(work_item)
                    
                except Exception as e:
                    logger.error(f"Failed to execute city {work_item.city}: {e}")
                    
                    # Mark work as failed
                    self.cluster_coordinator.fail_work_item(work_item, str(e))
                    
                    # Create failed result
                    city_result = CityExecutionMetrics(
                        city=work_item.city,
                        execution_id=execution_id,
                        status=CityExecutionResult.FAILED,
                        started_at=datetime.now(),
                        completed_at=datetime.now(),
                        error_summary=str(e)
                    )
                    city_results.append(city_result)
                    processed_cities.add(work_item.city)
        
        return city_results
    
    def _execute_cities_sequentially(self, 
                                   cities: List[CityConfig], 
                                   execution_id: str) -> List[CityExecutionMetrics]:
        """
        Execute cities sequentially without cluster coordination.
        
        Args:
            cities: List of city configurations
            execution_id: Execution ID for tracking
            
        Returns:
            List of city execution metrics
        """
        logger.info(f"Executing {len(cities)} cities sequentially")
        
        city_results = []
        
        for city_config in cities:
            try:
                city_result = self._execute_single_city(city_config, execution_id)
                city_results.append(city_result)
                
                # Add delay between cities to respect rate limits
                if city_config.rate_limit_seconds > 0:
                    time.sleep(city_config.rate_limit_seconds)
                    
            except Exception as e:
                logger.error(f"Failed to execute city {city_config.city}: {e}")
                
                city_result = CityExecutionMetrics(
                    city=city_config.city,
                    execution_id=execution_id,
                    status=CityExecutionResult.FAILED,
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    error_summary=str(e)
                )
                city_results.append(city_result)
        
        return city_results
    
    def _execute_single_city_with_coordination(self, 
                                             city_config: CityConfig, 
                                             execution_id: str,
                                             work_item: WorkItem) -> CityExecutionMetrics:
        """
        Execute single city with cluster coordination.
        
        Args:
            city_config: City configuration
            execution_id: Execution ID for tracking
            work_item: Work item from cluster coordinator
            
        Returns:
            City execution metrics
        """
        # Acquire distributed lock for city
        if not self.cluster_coordinator.acquire_work_lock(work_item.work_id):
            logger.warning(f"Could not acquire lock for city {city_config.city}")
            return CityExecutionMetrics(
                city=city_config.city,
                execution_id=execution_id,
                status=CityExecutionResult.SKIPPED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                error_summary="Could not acquire distributed lock"
            )
        
        try:
            return self._execute_single_city(city_config, execution_id)
        finally:
            self.cluster_coordinator.release_work_lock(work_item.work_id)
    
    def _execute_single_city(self, 
                           city_config: CityConfig, 
                           execution_id: str) -> CityExecutionMetrics:
        """
        Execute scraping for a single city with comprehensive error handling.
        
        Args:
            city_config: City configuration
            execution_id: Execution ID for tracking
            
        Returns:
            City execution metrics
        """
        start_time = datetime.now()
        city = city_config.city
        
        logger.info(f"Starting execution for city: {city}")
        
        # Initialize metrics
        metrics = CityExecutionMetrics(
            city=city,
            execution_id=execution_id,
            status=CityExecutionResult.SUCCESS,
            started_at=start_time
        )
        
        # Check circuit breaker
        circuit_breaker = self.circuit_breakers.get(city)
        if circuit_breaker and circuit_breaker.state == CircuitBreakerState.OPEN:
            logger.warning(f"Circuit breaker is open for city {city}, skipping execution")
            metrics.status = CityExecutionResult.CIRCUIT_OPEN
            metrics.completed_at = datetime.now()
            metrics.error_summary = "Circuit breaker is open"
            return metrics
        
        # Log city execution start
        self.audit_logger.log_event(AuditEvent(
            event_type=AuditEventType.CITY_EXECUTION_START,
            execution_id=execution_id,
            city=city,
            details={'url': city_config.url}
        ))
        
        try:
            # Check data governance and rate limits
            if not self.data_governance.enforce_rate_limits(city_config.url):
                logger.warning(f"Rate limit exceeded for city {city}")
                metrics.status = CityExecutionResult.RATE_LIMITED
                metrics.rate_limit_hits = 1
                return metrics
            
            # Execute scraping with retry logic
            retry_manager = self.retry_managers.get(city)
            scraping_result = self._execute_city_scraping_with_retries(
                city_config, execution_id, retry_manager, circuit_breaker
            )
            
            # Update metrics from scraping result
            metrics.urls_discovered = scraping_result.get('urls_discovered', 0)
            metrics.urls_processed = scraping_result.get('urls_processed', 0)
            metrics.listings_new = scraping_result.get('listings_new', 0)
            metrics.listings_updated = scraping_result.get('listings_updated', 0)
            metrics.listings_failed = scraping_result.get('listings_failed', 0)
            metrics.retry_count = scraping_result.get('retry_count', 0)
            
            # Track data lineage
            self.data_governance.track_data_lineage(
                table_name='listings',
                record_id=f"{execution_id}-{city}",
                data_source=DataSource.OIKOTIE_SCRAPER,
                execution_id=execution_id,
                api_endpoint=city_config.url,
                request_parameters={'city': city},
                response_metadata={
                    'urls_discovered': metrics.urls_discovered,
                    'listings_processed': metrics.urls_processed
                }
            )
            
            # Log successful execution
            self.audit_logger.log_event(AuditEvent(
                event_type=AuditEventType.CITY_EXECUTION_SUCCESS,
                execution_id=execution_id,
                city=city,
                details={
                    'listings_new': metrics.listings_new,
                    'listings_failed': metrics.listings_failed,
                    'urls_processed': metrics.urls_processed
                }
            ))
            
        except Exception as e:
            logger.error(f"City execution failed for {city}: {e}")
            metrics.status = CityExecutionResult.FAILED
            metrics.error_summary = str(e)
            
            # Trip circuit breaker if configured
            if circuit_breaker:
                circuit_breaker.record_failure()
                if circuit_breaker.state == CircuitBreakerState.OPEN:
                    metrics.circuit_breaker_trips = 1
            
            # Log execution failure
            self.audit_logger.log_event(AuditEvent(
                event_type=AuditEventType.CITY_EXECUTION_ERROR,
                execution_id=execution_id,
                city=city,
                details={'error': str(e)}
            ))
        
        finally:
            metrics.completed_at = datetime.now()
            metrics.execution_time_seconds = (metrics.completed_at - metrics.started_at).total_seconds()
            
            # Get memory usage if available
            try:
                import psutil
                process = psutil.Process()
                metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
            except ImportError:
                pass
        
        logger.info(f"Completed execution for city {city}: "
                   f"status={metrics.status.value}, "
                   f"new={metrics.listings_new}, "
                   f"failed={metrics.listings_failed}, "
                   f"time={metrics.execution_time_seconds:.1f}s")
        
        return metrics
    
    def _execute_city_scraping_with_retries(self, 
                                          city_config: CityConfig,
                                          execution_id: str,
                                          retry_manager: Optional[RetryManager],
                                          circuit_breaker: Optional[CircuitBreaker]) -> Dict[str, Any]:
        """
        Execute city scraping with retry logic and circuit breaker protection.
        
        Args:
            city_config: City configuration
            execution_id: Execution ID for tracking
            retry_manager: Retry manager for the city
            circuit_breaker: Circuit breaker for the city
            
        Returns:
            Dictionary with scraping results
        """
        max_attempts = 3
        attempt = 1
        last_error = None
        
        while attempt <= max_attempts:
            try:
                logger.info(f"Scraping attempt {attempt}/{max_attempts} for {city_config.city}")
                
                # Execute actual scraping
                result = self._execute_scraping_operation(city_config, execution_id)
                
                # Record success in circuit breaker
                if circuit_breaker:
                    circuit_breaker.record_success()
                
                # Reset retry count on success
                if retry_manager:
                    # This would reset retry counts for successful URLs
                    pass
                
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Scraping attempt {attempt} failed for {city_config.city}: {e}")
                
                # Check if we should retry
                if retry_manager and attempt < max_attempts:
                    if retry_manager.should_retry(city_config.url, e, attempt):
                        delay = retry_manager.calculate_retry_delay(city_config.url, e, attempt)
                        logger.info(f"Retrying {city_config.city} in {delay} seconds")
                        time.sleep(delay)
                        attempt += 1
                        continue
                
                # No more retries, record failure
                if circuit_breaker:
                    circuit_breaker.record_failure()
                
                raise e
        
        # All attempts failed
        raise last_error or Exception(f"All {max_attempts} attempts failed for {city_config.city}")
    
    def _execute_scraping_operation(self, 
                                  city_config: CityConfig, 
                                  execution_id: str) -> Dict[str, Any]:
        """
        Execute the actual scraping operation for a city.
        
        Args:
            city_config: City configuration
            execution_id: Execution ID for tracking
            
        Returns:
            Dictionary with scraping results
        """
        scraper = None
        try:
            # Initialize scraper
            scraper = OikotieScraper(headless=True)
            
            # Phase 1: Discover listing URLs
            logger.info(f"Discovering listing URLs for {city_config.city}")
            listing_summaries = scraper.get_all_listing_summaries(city_config.url)
            urls_discovered = len(listing_summaries)
            
            if not listing_summaries:
                logger.warning(f"No listings discovered for {city_config.city}")
                return {
                    'urls_discovered': 0,
                    'urls_processed': 0,
                    'listings_new': 0,
                    'listings_updated': 0,
                    'listings_failed': 0,
                    'retry_count': 0
                }
            
            # Phase 2: Process details with workers
            logger.info(f"Processing {len(listing_summaries)} listings for {city_config.city}")
            
            # Split work into chunks for parallel processing
            max_workers = city_config.max_detail_workers
            chunks = [listing_summaries[i::max_workers] for i in range(max_workers)]
            
            detailed_listings = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(worker_scrape_details, chunk) for chunk in chunks]
                for future in as_completed(futures):
                    try:
                        chunk_results = future.result()
                        detailed_listings.extend(chunk_results)
                    except Exception as e:
                        logger.error(f"Worker failed for {city_config.city}: {e}")
            
            # Phase 3: Save to database
            logger.info(f"Saving {len(detailed_listings)} listings for {city_config.city}")
            
            # Use existing database manager to save listings
            from ..database.manager import DatabaseManager
            db_manager = DatabaseManager()
            db_manager.save_listings(detailed_listings, city_config.city)
            
            # Calculate results
            successful_listings = sum(1 for listing in detailed_listings 
                                    if listing.get('details') and 'error' not in listing.get('details', {}))
            failed_listings = len(detailed_listings) - successful_listings
            
            return {
                'urls_discovered': urls_discovered,
                'urls_processed': len(detailed_listings),
                'listings_new': successful_listings,  # Simplified - would need to check if actually new
                'listings_updated': 0,  # Would need to track updates
                'listings_failed': failed_listings,
                'retry_count': 0  # Would be tracked by retry manager
            }
            
        finally:
            if scraper:
                scraper.close()
    
    def _load_city_configurations(self) -> List[CityConfig]:
        """Load city configurations from config file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            city_configs = []
            for task in config_data.get('tasks', []):
                city_config = CityConfig(
                    city=task.get('city', 'unknown'),
                    enabled=task.get('enabled', False),
                    url=task.get('url', ''),
                    max_detail_workers=task.get('max_detail_workers', 5),
                    rate_limit_seconds=task.get('rate_limit_seconds', 1.0),
                    coordinate_bounds=tuple(task.get('coordinate_bounds', [])) if task.get('coordinate_bounds') else None,
                    geospatial_sources=task.get('geospatial_sources', []),
                    data_governance=task.get('data_governance', {}),
                    priority=task.get('priority', 1)
                )
                city_configs.append(city_config)
            
            logger.info(f"Loaded {len(city_configs)} city configurations")
            return city_configs
            
        except Exception as e:
            logger.error(f"Failed to load city configurations: {e}")
            return []
    
    def _load_global_settings(self) -> Dict[str, Any]:
        """Load global settings from config file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            return config_data.get('global_settings', {})
            
        except Exception as e:
            logger.error(f"Failed to load global settings: {e}")
            return {}
    
    def _initialize_retry_managers(self) -> Dict[str, RetryManager]:
        """Initialize retry managers for each city."""
        retry_managers = {}
        
        for city_config in self.city_configs:
            if city_config.enabled:
                retry_config = RetryConfiguration(
                    max_attempts=3,
                    base_delay_seconds=60,
                    max_delay_seconds=3600
                )
                retry_managers[city_config.city] = RetryManager(
                    self.db_manager, 
                    retry_config
                )
        
        logger.info(f"Initialized retry managers for {len(retry_managers)} cities")
        return retry_managers
    
    def _initialize_circuit_breakers(self) -> Dict[str, CircuitBreaker]:
        """Initialize circuit breakers for each city."""
        circuit_breakers = {}
        
        for city_config in self.city_configs:
            if city_config.enabled:
                circuit_breakers[city_config.city] = CircuitBreaker(
                    failure_threshold=5,
                    recovery_timeout=300,  # 5 minutes
                    expected_exception=Exception
                )
        
        logger.info(f"Initialized circuit breakers for {len(circuit_breakers)} cities")
        return circuit_breakers
    
    def get_execution_status(self) -> Optional[str]:
        """Get current execution ID if running."""
        with self.execution_lock:
            return self.current_execution_id
    
    def get_cluster_status(self) -> Optional[Dict[str, Any]]:
        """Get cluster status if coordination is enabled."""
        if self.cluster_coordinator:
            return self.cluster_coordinator.get_cluster_status()
        return None
    
    def shutdown(self) -> None:
        """Gracefully shutdown the orchestrator."""
        logger.info("Shutting down multi-city orchestrator")
        
        if self.cluster_coordinator:
            self.cluster_coordinator.coordinate_shutdown()
        
        logger.info("Multi-city orchestrator shutdown complete")


def create_multi_city_orchestrator(config_path: str = 'config/config.json',
                                 redis_url: Optional[str] = None,
                                 enable_cluster_coordination: bool = True) -> MultiCityScraperOrchestrator:
    """
    Factory function to create multi-city scraper orchestrator.
    
    Args:
        config_path: Path to configuration file
        redis_url: Redis connection URL for cluster coordination
        enable_cluster_coordination: Enable Redis cluster coordination
        
    Returns:
        Configured MultiCityScraperOrchestrator instance
    """
    return MultiCityScraperOrchestrator(
        config_path=config_path,
        redis_url=redis_url,
        enable_cluster_coordination=enable_cluster_coordination
    )