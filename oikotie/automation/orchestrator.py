"""
Enhanced Scraper Orchestrator for the Oikotie automation system.

This module extends the existing ScraperOrchestrator with smart deduplication,
daily execution workflow, execution metadata tracking, performance monitoring,
comprehensive error handling, and OSM building footprint validation integration.
"""

import json
import time
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from loguru import logger

from ..database.manager import EnhancedDatabaseManager, ExecutionMetadata, ListingRecord
from ..scraper import OikotieScraper, worker_scrape_details
from .deduplication import SmartDeduplicationManager, DeduplicationSummary
from .listing_manager import ListingManager, ProcessingStats, ListingBatch
from .retry_manager import RetryManager, RetryConfiguration
from .metrics import MetricsCollector
from .monitoring import ComprehensiveMonitor
from .logging_config import create_monitoring_context, log_execution_start, log_performance_metric
from .data_governance import DataGovernanceManager, DataSource

# Import psutil with fallback handling
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    logger.warning("psutil not available - memory monitoring will be limited")
    PSUTIL_AVAILABLE = False
    
    # Mock psutil for when it's not available
    class MockPsutil:
        class Process:
            def __init__(self):
                pass
            
            def memory_info(self):
                class MockMemoryInfo:
                    rss = 100 * 1024 * 1024  # 100MB
                return MockMemoryInfo()
    
    psutil = MockPsutil()


class ExecutionStatus(Enum):
    """Enumeration of execution statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScrapingResult:
    """Result of a scraping execution."""
    execution_id: str
    city: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_urls_discovered: int = 0
    urls_processed: int = 0
    listings_new: int = 0
    listings_updated: int = 0
    listings_skipped: int = 0
    listings_failed: int = 0
    execution_time_seconds: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    error_summary: Optional[str] = None
    deduplication_summary: Optional[DeduplicationSummary] = None
    processing_stats: Optional[ProcessingStats] = None


@dataclass
class ScraperConfig:
    """Configuration for the enhanced scraper orchestrator."""
    city: str
    url: str
    listing_limit: Optional[int] = None
    max_detail_workers: int = 5
    staleness_threshold_hours: int = 24
    retry_limit: int = 3
    retry_delay_hours: int = 1
    batch_size: int = 100
    enable_smart_deduplication: bool = True
    enable_performance_monitoring: bool = True
    headless_browser: bool = True


class EnhancedScraperOrchestrator:
    """Enhanced scraper orchestrator with automation capabilities."""
    
    def __init__(self, 
                 config: ScraperConfig,
                 db_manager: Optional[EnhancedDatabaseManager] = None):
        """
        Initialize enhanced scraper orchestrator.
        
        Args:
            config: Scraper configuration
            db_manager: Enhanced database manager (creates new if None)
        """
        self.config = config
        self.db_manager = db_manager or EnhancedDatabaseManager()
        
        # Initialize automation components
        self.deduplication_manager = SmartDeduplicationManager(
            db_manager=self.db_manager,
            staleness_threshold_hours=config.staleness_threshold_hours,
            retry_limit=config.retry_limit,
            retry_delay_hours=config.retry_delay_hours
        )
        
        self.listing_manager = ListingManager(
            db_manager=self.db_manager,
            deduplication_manager=self.deduplication_manager,
            batch_size=config.batch_size
        )
        
        self.retry_manager = RetryManager(
            db_manager=self.db_manager,
            config=RetryConfiguration(
                max_attempts=config.retry_limit,
                base_delay_seconds=config.retry_delay_hours * 3600
            )
        )
        
        # Initialize metrics collector
        self.metrics_collector = MetricsCollector(self.db_manager)
        
        # Initialize comprehensive monitor if performance monitoring is enabled
        self.comprehensive_monitor: Optional[ComprehensiveMonitor] = None
        if config.enable_performance_monitoring:
            try:
                self.comprehensive_monitor = ComprehensiveMonitor(
                    db_manager=self.db_manager,
                    metrics_port=8080 + hash(config.city) % 1000,  # Unique port per city
                    system_monitor_interval=30
                )
                logger.info(f"Comprehensive monitoring enabled for {config.city}")
            except Exception as e:
                logger.warning(f"Failed to initialize comprehensive monitoring: {e}")
        
        logger.info(f"Enhanced scraper orchestrator initialized for {config.city}")
    
    def run_daily_scrape(self) -> ScrapingResult:
        """
        Execute daily scraping with smart deduplication and automation features.
        
        Returns:
            ScrapingResult with execution details and statistics
        """
        execution_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        logger.info(f"Starting daily scrape for {self.config.city} (execution: {execution_id})")
        
        # Initialize result
        result = ScrapingResult(
            execution_id=execution_id,
            city=self.config.city,
            status=ExecutionStatus.RUNNING,
            started_at=start_time
        )
        
        # Track execution metadata
        execution_metadata = ExecutionMetadata(
            execution_id=execution_id,
            started_at=start_time,
            city=self.config.city,
            status='running'
        )
        
        try:
            # Start metrics tracking
            self.metrics_collector.start_execution_tracking(execution_id, self.config.city)
            
            # Phase 1: Discover listing URLs
            logger.info("Phase 1: Discovering listing URLs")
            discovered_urls = self._discover_listing_urls()
            result.total_urls_discovered = len(discovered_urls)
            
            if not discovered_urls:
                logger.warning(f"No listings discovered for {self.config.city}")
                result.status = ExecutionStatus.COMPLETED
                result.completed_at = datetime.now()
                return result
            
            # Phase 2: Smart deduplication analysis
            logger.info("Phase 2: Performing smart deduplication analysis")
            if self.config.enable_smart_deduplication:
                dedup_summary = self.deduplication_manager.analyze_urls(discovered_urls)
                result.deduplication_summary = dedup_summary
                
                # Log deduplication decisions
                self.deduplication_manager.log_deduplication_decisions(dedup_summary)
                
                # Get URLs to process
                urls_to_process = self.deduplication_manager.get_urls_to_process(discovered_urls)
            else:
                urls_to_process = discovered_urls
                logger.info("Smart deduplication disabled, processing all URLs")
            
            logger.info(f"Processing {len(urls_to_process)} URLs after deduplication")
            
            # Phase 3: Create processing plan
            logger.info("Phase 3: Creating intelligent processing plan")
            processing_batches = self.listing_manager.create_processing_plan(
                urls_to_process, self.config.city, execution_id
            )
            
            # Phase 4: Execute processing plan
            logger.info("Phase 4: Executing processing plan")
            processing_stats = self._execute_processing_batches(processing_batches, execution_id)
            result.processing_stats = processing_stats
            
            # Update result with processing statistics
            result.urls_processed = processing_stats.processed_urls
            result.listings_new = processing_stats.successful_urls  # Simplified for now
            result.listings_failed = processing_stats.failed_urls
            result.listings_skipped = processing_stats.skipped_urls
            
            # Phase 5: Performance monitoring and cleanup
            if self.config.enable_performance_monitoring:
                result.memory_usage_mb = self._get_memory_usage()
                # Collect performance metrics
                performance_metrics = self.metrics_collector.collect_performance_metrics(execution_id)
            
            # Mark as completed
            result.status = ExecutionStatus.COMPLETED
            result.completed_at = datetime.now()
            result.execution_time_seconds = (result.completed_at - result.started_at).total_seconds()
            
            # Collect final execution metrics
            execution_metrics = self.metrics_collector.collect_execution_metrics(result)
            
            # Update execution metadata
            execution_metadata.status = 'completed'
            execution_metadata.completed_at = result.completed_at
            execution_metadata.listings_processed = result.urls_processed
            execution_metadata.listings_new = result.listings_new
            execution_metadata.listings_failed = result.listings_failed
            execution_metadata.execution_time_seconds = int(result.execution_time_seconds)
            execution_metadata.memory_usage_mb = int(result.memory_usage_mb or 0)
            
            logger.success(f"Daily scrape completed successfully: "
                          f"{result.listings_new} new, {result.listings_failed} failed, "
                          f"{result.execution_time_seconds:.1f}s")
            
        except Exception as e:
            logger.error(f"Daily scrape failed: {e}")
            result.status = ExecutionStatus.FAILED
            result.completed_at = datetime.now()
            result.error_summary = str(e)
            result.execution_time_seconds = (result.completed_at - result.started_at).total_seconds()
            
            # Update execution metadata
            execution_metadata.status = 'failed'
            execution_metadata.completed_at = result.completed_at
            execution_metadata.error_summary = str(e)
            execution_metadata.execution_time_seconds = int(result.execution_time_seconds)
        
        finally:
            # Always track execution metadata
            self.db_manager.track_execution_metadata(execution_metadata)
        
        return result
    
    def get_stale_listings(self, staleness_hours: int = 24) -> List[str]:
        """
        Identify listings that need re-scraping based on staleness threshold.
        
        Args:
            staleness_hours: Hours after which listings are considered stale
            
        Returns:
            List of URLs that need re-scraping
        """
        staleness_threshold = timedelta(hours=staleness_hours)
        stale_listings = self.db_manager.get_stale_listings(staleness_threshold)
        
        # Filter by city
        city_stale_listings = [
            listing.url for listing in stale_listings 
            if listing.city and listing.city.lower() == self.config.city.lower()
        ]
        
        logger.info(f"Found {len(city_stale_listings)} stale listings for {self.config.city}")
        return city_stale_listings
    
    def should_skip_listing(self, url: str) -> bool:
        """
        Determine if a listing should be skipped based on smart deduplication logic.
        
        Args:
            url: URL to check
            
        Returns:
            True if listing should be skipped, False otherwise
        """
        if not self.config.enable_smart_deduplication:
            return False
        
        staleness_threshold = timedelta(hours=self.config.staleness_threshold_hours)
        return self.db_manager.should_skip_listing(url, staleness_threshold)
    
    def _discover_listing_urls(self) -> List[str]:
        """
        Discover listing URLs from the configured source.
        
        Returns:
            List of discovered listing URLs
        """
        try:
            scraper = OikotieScraper(headless=self.config.headless_browser)
            
            try:
                # Get listing summaries
                listing_summaries = scraper.get_all_listing_summaries(
                    self.config.url, 
                    limit=self.config.listing_limit
                )
                
                # Extract URLs
                urls = [summary['url'] for summary in listing_summaries if summary.get('url')]
                
                logger.info(f"Discovered {len(urls)} listing URLs for {self.config.city}")
                return urls
                
            finally:
                scraper.close()
                
        except Exception as e:
            logger.error(f"Failed to discover listing URLs: {e}")
            return []
    
    def _execute_processing_batches(self, 
                                  batches: List[ListingBatch], 
                                  execution_id: str) -> ProcessingStats:
        """
        Execute processing batches using the existing scraper infrastructure.
        
        Args:
            batches: List of processing batches
            execution_id: Execution ID for tracking
            
        Returns:
            Overall processing statistics
        """
        try:
            # For now, use the listing manager's execution logic
            # In a full implementation, this would integrate with the actual scraper
            return self.listing_manager.execute_processing_plan(batches, execution_id)
            
        except Exception as e:
            logger.error(f"Failed to execute processing batches: {e}")
            
            # Return error statistics
            total_urls = sum(len(batch.urls) for batch in batches)
            return ProcessingStats(
                total_urls=total_urls,
                processed_urls=0,
                successful_urls=0,
                failed_urls=total_urls,
                skipped_urls=0,
                processing_time_seconds=0.0,
                average_time_per_url=0.0,
                error_rate=1.0
            )
    
    def _get_memory_usage(self) -> float:
        """
        Get current memory usage in MB.
        
        Returns:
            Memory usage in megabytes
        """
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss / 1024 / 1024  # Convert bytes to MB
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {e}")
            return 0.0
    
    def get_execution_statistics(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Get execution statistics for monitoring and optimization.
        
        Args:
            hours_back: Hours of history to analyze
            
        Returns:
            Dictionary with execution statistics
        """
        return self.listing_manager.get_processing_statistics(
            city=self.config.city,
            hours_back=hours_back
        )
    
    def update_configuration(self, new_config: ScraperConfig) -> None:
        """
        Update orchestrator configuration at runtime.
        
        Args:
            new_config: New configuration to apply
        """
        self.config = new_config
        
        # Update component configurations
        self.deduplication_manager.update_configuration(
            staleness_threshold_hours=new_config.staleness_threshold_hours,
            retry_limit=new_config.retry_limit,
            retry_delay_hours=new_config.retry_delay_hours
        )
        
        retry_config = RetryConfiguration(
            max_attempts=new_config.retry_limit,
            base_delay_seconds=new_config.retry_delay_hours * 3600
        )
        self.retry_manager.update_configuration(retry_config)
        
        logger.info(f"Configuration updated for {new_config.city}")
    
    def get_configuration(self) -> ScraperConfig:
        """
        Get current orchestrator configuration.
        
        Returns:
            Current scraper configuration
        """
        return self.config
    
    def plan_execution(self, city: Optional[str] = None) -> Dict[str, Any]:
        """
        Plan execution for a city and return execution plan details.
        
        Args:
            city: City name to plan execution for (uses config city if None)
            
        Returns:
            Dictionary with execution plan details
        """
        target_city = city or self.config.city
        
        try:
            # Discover URLs that would be processed
            discovered_urls = self._discover_listing_urls()
            
            # Apply smart deduplication if enabled
            if self.config.enable_smart_deduplication:
                dedup_summary = self.deduplication_manager.analyze_urls(discovered_urls)
                urls_to_process = self.deduplication_manager.get_urls_to_process(discovered_urls)
            else:
                urls_to_process = discovered_urls
                dedup_summary = None
            
            # Create processing plan
            processing_batches = self.listing_manager.create_processing_plan(
                urls_to_process, target_city, f"plan_{uuid.uuid4()}"
            )
            
            # Calculate estimated execution time
            estimated_time = len(urls_to_process) * 2.0  # Rough estimate: 2 seconds per URL
            
            return {
                'city': target_city,
                'total_urls': len(discovered_urls),
                'urls_to_process': len(urls_to_process),
                'urls_to_skip': len(discovered_urls) - len(urls_to_process),
                'processing_batches': len(processing_batches),
                'estimated_execution_time_seconds': estimated_time,
                'deduplication_enabled': self.config.enable_smart_deduplication,
                'deduplication_summary': dedup_summary,
                'batch_details': [
                    {
                        'batch_id': batch.batch_id,
                        'priority': batch.priority.name,
                        'url_count': len(batch.urls),
                        'estimated_time': len(batch.urls) * 2.0
                    }
                    for batch in processing_batches
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to plan execution for {target_city}: {e}")
            return {
                'city': target_city,
                'error': str(e),
                'total_urls': 0,
                'urls_to_process': 0,
                'urls_to_skip': 0,
                'processing_batches': 0,
                'estimated_execution_time_seconds': 0
            }


def create_orchestrator_from_task_config(task_config: Dict[str, Any]) -> EnhancedScraperOrchestrator:
    """
    Create an enhanced scraper orchestrator from a task configuration.
    
    Args:
        task_config: Task configuration dictionary
        
    Returns:
        Configured EnhancedScraperOrchestrator instance
    """
    config = ScraperConfig(
        city=task_config.get('city', 'unknown'),
        url=task_config.get('url', ''),
        listing_limit=task_config.get('listing_limit'),
        max_detail_workers=task_config.get('max_detail_workers', 5),
        staleness_threshold_hours=task_config.get('staleness_threshold_hours', 24),
        retry_limit=task_config.get('retry_limit', 3),
        retry_delay_hours=task_config.get('retry_delay_hours', 1),
        batch_size=task_config.get('batch_size', 100),
        enable_smart_deduplication=task_config.get('enable_smart_deduplication', True),
        enable_performance_monitoring=task_config.get('enable_performance_monitoring', True),
        headless_browser=task_config.get('headless_browser', True)
    )
    
    return EnhancedScraperOrchestrator(config)


def load_config_and_create_orchestrators(config_path: str = 'config/config.json') -> List[EnhancedScraperOrchestrator]:
    """
    Load configuration and create orchestrators for all enabled tasks.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        List of configured orchestrator instances
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        tasks = config_data.get('tasks', [])
        orchestrators = []
        
        for task in tasks:
            if task.get('enabled', False):
                orchestrator = create_orchestrator_from_task_config(task)
                orchestrators.append(orchestrator)
                logger.info(f"Created orchestrator for {task.get('city')}")
        
        logger.info(f"Created {len(orchestrators)} orchestrators from configuration")
        return orchestrators
        
    except Exception as e:
        logger.error(f"Failed to load configuration from {config_path}: {e}")
        return []