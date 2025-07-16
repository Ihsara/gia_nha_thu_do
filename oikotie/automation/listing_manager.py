"""
Listing management system for the Oikotie automation platform.

This module provides comprehensive listing management with prioritization,
batch processing, and intelligent workflow coordination.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import uuid
from loguru import logger

from ..database.manager import EnhancedDatabaseManager, ListingRecord, ExecutionMetadata
from .deduplication import SmartDeduplicationManager, DeduplicationSummary


class ListingPriority(Enum):
    """Enumeration of listing processing priorities."""
    HIGH = "high"      # New listings, critical updates
    MEDIUM = "medium"  # Stale listings, routine updates
    LOW = "low"        # Retry attempts, maintenance


@dataclass
class ListingBatch:
    """Represents a batch of listings for processing."""
    batch_id: str
    urls: List[str]
    priority: ListingPriority
    city: str
    created_at: datetime
    estimated_duration: Optional[int] = None  # seconds
    metadata: Optional[Dict] = None


@dataclass
class ProcessingStats:
    """Statistics for listing processing operations."""
    total_urls: int
    processed_urls: int
    successful_urls: int
    failed_urls: int
    skipped_urls: int
    processing_time_seconds: float
    average_time_per_url: float
    error_rate: float


class ListingManager:
    """Manages listing processing workflow with intelligent prioritization."""
    
    def __init__(self, 
                 db_manager: EnhancedDatabaseManager,
                 deduplication_manager: SmartDeduplicationManager,
                 batch_size: int = 100,
                 max_concurrent_batches: int = 3):
        """
        Initialize listing manager.
        
        Args:
            db_manager: Enhanced database manager instance
            deduplication_manager: Smart deduplication manager instance
            batch_size: Default batch size for processing
            max_concurrent_batches: Maximum concurrent batches
        """
        self.db_manager = db_manager
        self.deduplication_manager = deduplication_manager
        self.batch_size = batch_size
        self.max_concurrent_batches = max_concurrent_batches
        
        self.active_batches: Dict[str, ListingBatch] = {}
        self.processing_stats: Dict[str, ProcessingStats] = {}
        
        logger.info(f"Listing manager initialized: "
                   f"batch_size={batch_size}, "
                   f"max_concurrent={max_concurrent_batches}")
    
    def create_processing_plan(self, 
                              urls: List[str], 
                              city: str,
                              execution_id: str) -> List[ListingBatch]:
        """
        Create an intelligent processing plan for a list of URLs.
        
        Args:
            urls: List of URLs to process
            city: City name for the listings
            execution_id: Execution ID for tracking
            
        Returns:
            List of ListingBatch objects in priority order
        """
        logger.info(f"Creating processing plan for {len(urls)} URLs in {city}")
        
        # Analyze URLs for deduplication
        dedup_summary = self.deduplication_manager.analyze_urls(urls)
        
        # Get prioritized URLs
        prioritized_urls = self.deduplication_manager.get_prioritized_urls(urls)
        
        # Create batches based on priority
        batches = self._create_priority_batches(prioritized_urls, dedup_summary, city, execution_id)
        
        logger.info(f"Created {len(batches)} processing batches: "
                   f"high={sum(1 for b in batches if b.priority == ListingPriority.HIGH)}, "
                   f"medium={sum(1 for b in batches if b.priority == ListingPriority.MEDIUM)}, "
                   f"low={sum(1 for b in batches if b.priority == ListingPriority.LOW)}")
        
        return batches
    
    def execute_processing_plan(self, 
                               batches: List[ListingBatch],
                               execution_id: str) -> ProcessingStats:
        """
        Execute a processing plan with intelligent batch management.
        
        Args:
            batches: List of batches to process
            execution_id: Execution ID for tracking
            
        Returns:
            Overall processing statistics
        """
        logger.info(f"Executing processing plan with {len(batches)} batches")
        
        start_time = datetime.now()
        total_stats = ProcessingStats(
            total_urls=sum(len(batch.urls) for batch in batches),
            processed_urls=0,
            successful_urls=0,
            failed_urls=0,
            skipped_urls=0,
            processing_time_seconds=0.0,
            average_time_per_url=0.0,
            error_rate=0.0
        )
        
        # Process batches in priority order
        for batch in batches:
            logger.info(f"Processing batch {batch.batch_id} "
                       f"({batch.priority.value} priority, {len(batch.urls)} URLs)")
            
            batch_stats = self._process_batch(batch, execution_id)
            
            # Aggregate statistics
            total_stats.processed_urls += batch_stats.processed_urls
            total_stats.successful_urls += batch_stats.successful_urls
            total_stats.failed_urls += batch_stats.failed_urls
            total_stats.skipped_urls += batch_stats.skipped_urls
            
            # Store batch statistics
            self.processing_stats[batch.batch_id] = batch_stats
        
        # Calculate final statistics
        end_time = datetime.now()
        total_stats.processing_time_seconds = (end_time - start_time).total_seconds()
        
        if total_stats.processed_urls > 0:
            total_stats.average_time_per_url = (
                total_stats.processing_time_seconds / total_stats.processed_urls
            )
            total_stats.error_rate = (
                total_stats.failed_urls / total_stats.processed_urls
            )
        
        logger.info(f"Processing plan completed: "
                   f"{total_stats.successful_urls}/{total_stats.total_urls} successful, "
                   f"error_rate={total_stats.error_rate:.2%}, "
                   f"avg_time={total_stats.average_time_per_url:.2f}s/url")
        
        return total_stats
    
    def get_stale_listings_for_city(self, 
                                   city: str,
                                   staleness_threshold_hours: int = 24,
                                   limit: Optional[int] = None) -> List[str]:
        """
        Get stale listings for a specific city that need re-processing.
        
        Args:
            city: City name to filter by
            staleness_threshold_hours: Hours after which listings are considered stale
            limit: Maximum number of URLs to return
            
        Returns:
            List of URLs that need re-processing
        """
        staleness_threshold = timedelta(hours=staleness_threshold_hours)
        stale_listings = self.db_manager.get_stale_listings(staleness_threshold)
        
        # Filter by city
        city_listings = [
            listing.url for listing in stale_listings 
            if listing.city.lower() == city.lower()
        ]
        
        if limit:
            city_listings = city_listings[:limit]
        
        logger.info(f"Found {len(city_listings)} stale listings for {city}")
        return city_listings
    
    def estimate_processing_time(self, urls: List[str]) -> int:
        """
        Estimate processing time for a list of URLs based on historical data.
        
        Args:
            urls: List of URLs to estimate for
            
        Returns:
            Estimated processing time in seconds
        """
        # Get historical average processing time
        historical_avg = self._get_historical_average_time()
        
        # Apply deduplication analysis to get actual URLs to process
        urls_to_process = self.deduplication_manager.get_urls_to_process(urls)
        
        # Estimate based on URLs that will actually be processed
        estimated_seconds = len(urls_to_process) * historical_avg
        
        logger.debug(f"Estimated processing time: {estimated_seconds:.0f}s "
                    f"for {len(urls_to_process)}/{len(urls)} URLs")
        
        return int(estimated_seconds)
    
    def get_processing_statistics(self, 
                                 execution_id: Optional[str] = None,
                                 city: Optional[str] = None,
                                 hours_back: int = 24) -> Dict[str, any]:
        """
        Get processing statistics for monitoring and optimization.
        
        Args:
            execution_id: Specific execution ID to analyze
            city: City to filter by
            hours_back: Hours of history to analyze
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            # Get execution history
            executions = self.db_manager.get_execution_history(city=city, limit=100)
            
            # Filter by time window
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            recent_executions = [
                exec for exec in executions 
                if exec.started_at >= cutoff_time and exec.status == 'completed'
            ]
            
            if not recent_executions:
                return {
                    'total_executions': 0,
                    'total_listings_processed': 0,
                    'average_processing_time': 0.0,
                    'success_rate': 0.0,
                    'error_rate': 0.0
                }
            
            # Calculate statistics
            total_listings = sum(exec.listings_processed for exec in recent_executions)
            total_successful = sum(exec.listings_new + exec.listings_updated for exec in recent_executions)
            total_failed = sum(exec.listings_failed for exec in recent_executions)
            total_time = sum(exec.execution_time_seconds or 0 for exec in recent_executions)
            
            stats = {
                'total_executions': len(recent_executions),
                'total_listings_processed': total_listings,
                'average_processing_time': total_time / len(recent_executions) if recent_executions else 0.0,
                'success_rate': total_successful / total_listings if total_listings > 0 else 0.0,
                'error_rate': total_failed / total_listings if total_listings > 0 else 0.0,
                'average_listings_per_execution': total_listings / len(recent_executions) if recent_executions else 0.0,
                'time_window_hours': hours_back
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get processing statistics: {e}")
            return {}
    
    def _create_priority_batches(self, 
                                urls: List[str], 
                                dedup_summary: DeduplicationSummary,
                                city: str,
                                execution_id: str) -> List[ListingBatch]:
        """
        Create priority-based batches from URLs and deduplication analysis.
        
        Args:
            urls: Prioritized list of URLs
            dedup_summary: Deduplication analysis results
            city: City name
            execution_id: Execution ID for tracking
            
        Returns:
            List of ListingBatch objects
        """
        batches = []
        
        # Create decision lookup for priority assignment
        decision_lookup = {decision.url: decision for decision in dedup_summary.decisions}
        
        # Group URLs by priority
        high_priority_urls = []
        medium_priority_urls = []
        low_priority_urls = []
        
        for url in urls:
            decision = decision_lookup.get(url)
            if not decision:
                continue
            
            if decision.decision.value in ['process_new']:
                high_priority_urls.append(url)
            elif decision.decision.value in ['process_stale']:
                medium_priority_urls.append(url)
            elif decision.decision.value in ['process_retry']:
                low_priority_urls.append(url)
        
        # Create batches for each priority level
        for priority, priority_urls in [
            (ListingPriority.HIGH, high_priority_urls),
            (ListingPriority.MEDIUM, medium_priority_urls),
            (ListingPriority.LOW, low_priority_urls)
        ]:
            if not priority_urls:
                continue
            
            # Split into batches of appropriate size
            for i in range(0, len(priority_urls), self.batch_size):
                batch_urls = priority_urls[i:i + self.batch_size]
                
                batch = ListingBatch(
                    batch_id=f"{execution_id}_{priority.value}_{i // self.batch_size + 1}",
                    urls=batch_urls,
                    priority=priority,
                    city=city,
                    created_at=datetime.now(),
                    estimated_duration=self.estimate_processing_time(batch_urls),
                    metadata={
                        'execution_id': execution_id,
                        'batch_index': i // self.batch_size + 1,
                        'total_batches_for_priority': (len(priority_urls) + self.batch_size - 1) // self.batch_size
                    }
                )
                
                batches.append(batch)
        
        return batches
    
    def _process_batch(self, batch: ListingBatch, execution_id: str) -> ProcessingStats:
        """
        Process a single batch of listings.
        
        Args:
            batch: Batch to process
            execution_id: Execution ID for tracking
            
        Returns:
            Processing statistics for the batch
        """
        start_time = datetime.now()
        
        # Mark batch as active
        self.active_batches[batch.batch_id] = batch
        
        try:
            # This is a placeholder for actual scraping logic
            # In the real implementation, this would call the scraper
            logger.info(f"Processing batch {batch.batch_id} with {len(batch.urls)} URLs")
            
            # Simulate processing statistics
            # In real implementation, this would come from actual scraping results
            stats = ProcessingStats(
                total_urls=len(batch.urls),
                processed_urls=len(batch.urls),
                successful_urls=int(len(batch.urls) * 0.9),  # 90% success rate simulation
                failed_urls=int(len(batch.urls) * 0.1),     # 10% failure rate simulation
                skipped_urls=0,
                processing_time_seconds=0.0,
                average_time_per_url=0.0,
                error_rate=0.1
            )
            
            end_time = datetime.now()
            stats.processing_time_seconds = (end_time - start_time).total_seconds()
            
            if stats.processed_urls > 0:
                stats.average_time_per_url = stats.processing_time_seconds / stats.processed_urls
            
            logger.info(f"Batch {batch.batch_id} completed: "
                       f"{stats.successful_urls}/{stats.total_urls} successful")
            
            return stats
            
        except Exception as e:
            logger.error(f"Batch {batch.batch_id} failed: {e}")
            
            # Return error statistics
            end_time = datetime.now()
            return ProcessingStats(
                total_urls=len(batch.urls),
                processed_urls=0,
                successful_urls=0,
                failed_urls=len(batch.urls),
                skipped_urls=0,
                processing_time_seconds=(end_time - start_time).total_seconds(),
                average_time_per_url=0.0,
                error_rate=1.0
            )
        
        finally:
            # Remove from active batches
            self.active_batches.pop(batch.batch_id, None)
    
    def _get_historical_average_time(self) -> float:
        """
        Get historical average processing time per URL.
        
        Returns:
            Average processing time in seconds per URL
        """
        try:
            # Get recent execution history
            executions = self.db_manager.get_execution_history(limit=20)
            
            if not executions:
                return 5.0  # Default estimate: 5 seconds per URL
            
            # Calculate average time per URL from successful executions
            total_time = 0.0
            total_listings = 0
            
            for execution in executions:
                if (execution.status == 'completed' and 
                    execution.execution_time_seconds and 
                    execution.listings_processed > 0):
                    
                    total_time += execution.execution_time_seconds
                    total_listings += execution.listings_processed
            
            if total_listings > 0:
                avg_time = total_time / total_listings
                logger.debug(f"Historical average processing time: {avg_time:.2f}s per URL")
                return avg_time
            else:
                return 5.0  # Default estimate
                
        except Exception as e:
            logger.error(f"Failed to get historical average time: {e}")
            return 5.0  # Default estimate
    
    def get_active_batches(self) -> Dict[str, ListingBatch]:
        """
        Get currently active processing batches.
        
        Returns:
            Dictionary of active batches
        """
        return self.active_batches.copy()
    
    def cancel_batch(self, batch_id: str) -> bool:
        """
        Cancel an active batch.
        
        Args:
            batch_id: ID of batch to cancel
            
        Returns:
            True if batch was cancelled, False if not found
        """
        if batch_id in self.active_batches:
            logger.info(f"Cancelling batch {batch_id}")
            del self.active_batches[batch_id]
            return True
        return False