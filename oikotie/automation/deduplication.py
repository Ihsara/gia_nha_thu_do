"""
Smart deduplication manager for the Oikotie automation system.

This module provides intelligent deduplication logic with configurable staleness
thresholds, URL prioritization, and comprehensive logging for deduplication decisions.
"""

import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from ..database.manager import EnhancedDatabaseManager, ListingRecord


class DeduplicationDecision(Enum):
    """Enumeration of deduplication decisions."""
    SKIP_RECENT = "skip_recent"
    SKIP_FAILED_RETRY_LIMIT = "skip_failed_retry_limit"
    PROCESS_NEW = "process_new"
    PROCESS_STALE = "process_stale"
    PROCESS_RETRY = "process_retry"


@dataclass
class DeduplicationResult:
    """Result of deduplication analysis."""
    url: str
    decision: DeduplicationDecision
    reason: str
    last_check: Optional[datetime] = None
    retry_count: int = 0
    staleness_hours: Optional[float] = None


@dataclass
class DeduplicationSummary:
    """Summary of deduplication analysis for a batch of URLs."""
    total_urls: int
    skip_recent: int
    skip_failed: int
    process_new: int
    process_stale: int
    process_retry: int
    decisions: List[DeduplicationResult]


class SmartDeduplicationManager:
    """Manages smart deduplication logic with configurable thresholds."""
    
    def __init__(self, 
                 db_manager: EnhancedDatabaseManager,
                 staleness_threshold_hours: int = 24,
                 retry_limit: int = 3,
                 retry_delay_hours: int = 1):
        """
        Initialize smart deduplication manager.
        
        Args:
            db_manager: Enhanced database manager instance
            staleness_threshold_hours: Hours after which a listing is considered stale
            retry_limit: Maximum number of retry attempts for failed listings
            retry_delay_hours: Hours to wait before retrying failed listings
        """
        self.db_manager = db_manager
        self.staleness_threshold = timedelta(hours=staleness_threshold_hours)
        self.retry_limit = retry_limit
        self.retry_delay = timedelta(hours=retry_delay_hours)
        
        logger.info(f"Smart deduplication manager initialized: "
                   f"staleness={staleness_threshold_hours}h, "
                   f"retry_limit={retry_limit}, "
                   f"retry_delay={retry_delay_hours}h")
    
    def analyze_urls(self, urls: List[str]) -> DeduplicationSummary:
        """
        Analyze a list of URLs and determine deduplication decisions.
        
        Args:
            urls: List of URLs to analyze
            
        Returns:
            DeduplicationSummary with decisions for each URL
        """
        logger.info(f"Analyzing {len(urls)} URLs for deduplication")
        
        decisions = []
        summary_counts = {
            'skip_recent': 0,
            'skip_failed': 0,
            'process_new': 0,
            'process_stale': 0,
            'process_retry': 0
        }
        
        # Get existing URL data in batch for efficiency
        url_data = self._get_url_batch_data(urls)
        current_time = datetime.now()
        
        for url in urls:
            decision = self._analyze_single_url(url, url_data.get(url), current_time)
            decisions.append(decision)
            
            # Update summary counts
            if decision.decision == DeduplicationDecision.SKIP_RECENT:
                summary_counts['skip_recent'] += 1
            elif decision.decision == DeduplicationDecision.SKIP_FAILED_RETRY_LIMIT:
                summary_counts['skip_failed'] += 1
            elif decision.decision == DeduplicationDecision.PROCESS_NEW:
                summary_counts['process_new'] += 1
            elif decision.decision == DeduplicationDecision.PROCESS_STALE:
                summary_counts['process_stale'] += 1
            elif decision.decision == DeduplicationDecision.PROCESS_RETRY:
                summary_counts['process_retry'] += 1
        
        summary = DeduplicationSummary(
            total_urls=len(urls),
            skip_recent=summary_counts['skip_recent'],
            skip_failed=summary_counts['skip_failed'],
            process_new=summary_counts['process_new'],
            process_stale=summary_counts['process_stale'],
            process_retry=summary_counts['process_retry'],
            decisions=decisions
        )
        
        logger.info(f"Deduplication analysis complete: "
                   f"skip_recent={summary.skip_recent}, "
                   f"skip_failed={summary.skip_failed}, "
                   f"process_new={summary.process_new}, "
                   f"process_stale={summary.process_stale}, "
                   f"process_retry={summary.process_retry}")
        
        return summary
    
    def get_urls_to_process(self, urls: List[str]) -> List[str]:
        """
        Get filtered list of URLs that should be processed.
        
        Args:
            urls: List of candidate URLs
            
        Returns:
            List of URLs that should be processed
        """
        summary = self.analyze_urls(urls)
        
        urls_to_process = [
            decision.url for decision in summary.decisions
            if decision.decision in [
                DeduplicationDecision.PROCESS_NEW,
                DeduplicationDecision.PROCESS_STALE,
                DeduplicationDecision.PROCESS_RETRY
            ]
        ]
        
        logger.info(f"Filtered {len(urls)} URLs to {len(urls_to_process)} for processing")
        return urls_to_process
    
    def get_prioritized_urls(self, urls: List[str]) -> List[str]:
        """
        Get URLs prioritized by processing importance.
        
        Priority order:
        1. New listings (never processed)
        2. Failed listings ready for retry
        3. Stale listings (oldest first)
        
        Args:
            urls: List of URLs to prioritize
            
        Returns:
            List of URLs in priority order
        """
        summary = self.analyze_urls(urls)
        
        # Separate URLs by category
        new_urls = []
        retry_urls = []
        stale_urls = []
        
        for decision in summary.decisions:
            if decision.decision == DeduplicationDecision.PROCESS_NEW:
                new_urls.append(decision.url)
            elif decision.decision == DeduplicationDecision.PROCESS_RETRY:
                retry_urls.append((decision.url, decision.last_check))
            elif decision.decision == DeduplicationDecision.PROCESS_STALE:
                stale_urls.append((decision.url, decision.last_check))
        
        # Sort retry and stale URLs by last check time (oldest first)
        retry_urls.sort(key=lambda x: x[1] or datetime.min)
        stale_urls.sort(key=lambda x: x[1] or datetime.min)
        
        # Combine in priority order
        prioritized = (
            new_urls +
            [url for url, _ in retry_urls] +
            [url for url, _ in stale_urls]
        )
        
        logger.info(f"Prioritized URLs: {len(new_urls)} new, "
                   f"{len(retry_urls)} retry, {len(stale_urls)} stale")
        
        return prioritized
    
    def log_deduplication_decisions(self, summary: DeduplicationSummary) -> None:
        """
        Log detailed deduplication decisions for debugging and monitoring.
        
        Args:
            summary: Deduplication summary to log
        """
        logger.info("=== Deduplication Decision Log ===")
        logger.info(f"Total URLs analyzed: {summary.total_urls}")
        logger.info(f"Skip recent: {summary.skip_recent}")
        logger.info(f"Skip failed (retry limit): {summary.skip_failed}")
        logger.info(f"Process new: {summary.process_new}")
        logger.info(f"Process stale: {summary.process_stale}")
        logger.info(f"Process retry: {summary.process_retry}")
        
        # Log sample decisions for each category
        decision_samples = {}
        for decision in summary.decisions:
            category = decision.decision.value
            if category not in decision_samples:
                decision_samples[category] = []
            if len(decision_samples[category]) < 3:  # Log up to 3 samples per category
                decision_samples[category].append(decision)
        
        for category, samples in decision_samples.items():
            logger.info(f"\n{category.upper()} samples:")
            for sample in samples:
                staleness_info = f" (stale: {sample.staleness_hours:.1f}h)" if sample.staleness_hours else ""
                retry_info = f" (retries: {sample.retry_count})" if sample.retry_count > 0 else ""
                logger.info(f"  - {sample.url}: {sample.reason}{staleness_info}{retry_info}")
        
        logger.info("=== End Deduplication Log ===")
    
    def _get_url_batch_data(self, urls: List[str]) -> Dict[str, Dict]:
        """
        Get existing data for a batch of URLs efficiently.
        
        Args:
            urls: List of URLs to query
            
        Returns:
            Dictionary mapping URLs to their database records
        """
        if not urls:
            return {}
        
        try:
            import duckdb
            url_data = {}
            
            with duckdb.connect(str(self.db_manager.db_path), read_only=True) as con:
                # Use parameterized query with IN clause for efficiency
                placeholders = ','.join(['?' for _ in urls])
                query = f"""
                    SELECT url, last_check_ts, retry_count, deleted_ts, last_error
                    FROM listings 
                    WHERE url IN ({placeholders})
                """
                
                result = con.execute(query, urls).fetchall()
                
                for row in result:
                    url_data[row[0]] = {
                        'last_check_ts': row[1],
                        'retry_count': row[2] or 0,
                        'deleted_ts': row[3],
                        'last_error': row[4]
                    }
            
            logger.debug(f"Retrieved data for {len(url_data)} existing URLs")
            return url_data
            
        except Exception as e:
            logger.error(f"Failed to get URL batch data: {e}")
            return {}
    
    def _analyze_single_url(self, 
                           url: str, 
                           existing_data: Optional[Dict], 
                           current_time: datetime) -> DeduplicationResult:
        """
        Analyze a single URL and determine deduplication decision.
        
        Args:
            url: URL to analyze
            existing_data: Existing database data for the URL
            current_time: Current timestamp for calculations
            
        Returns:
            DeduplicationResult with decision and reasoning
        """
        # New URL - never processed
        if not existing_data:
            return DeduplicationResult(
                url=url,
                decision=DeduplicationDecision.PROCESS_NEW,
                reason="New URL, never processed"
            )
        
        last_check = existing_data.get('last_check_ts')
        retry_count = existing_data.get('retry_count', 0)
        deleted_ts = existing_data.get('deleted_ts')
        last_error = existing_data.get('last_error')
        
        # Process if previously deleted (might be re-listed)
        if deleted_ts:
            return DeduplicationResult(
                url=url,
                decision=DeduplicationDecision.PROCESS_NEW,
                reason="Previously deleted, might be re-listed",
                last_check=last_check,
                retry_count=retry_count
            )
        
        # Never checked - process
        if not last_check:
            return DeduplicationResult(
                url=url,
                decision=DeduplicationDecision.PROCESS_NEW,
                reason="Never checked before",
                retry_count=retry_count
            )
        
        # Calculate staleness
        time_since_check = current_time - last_check
        staleness_hours = time_since_check.total_seconds() / 3600
        
        # Check if failed and at retry limit
        if retry_count >= self.retry_limit:
            return DeduplicationResult(
                url=url,
                decision=DeduplicationDecision.SKIP_FAILED_RETRY_LIMIT,
                reason=f"Retry limit reached ({retry_count}/{self.retry_limit})",
                last_check=last_check,
                retry_count=retry_count,
                staleness_hours=staleness_hours
            )
        
        # Check if failed but ready for retry
        if retry_count > 0 and last_error:
            if time_since_check >= self.retry_delay:
                return DeduplicationResult(
                    url=url,
                    decision=DeduplicationDecision.PROCESS_RETRY,
                    reason=f"Ready for retry after {staleness_hours:.1f}h delay",
                    last_check=last_check,
                    retry_count=retry_count,
                    staleness_hours=staleness_hours
                )
            else:
                retry_remaining = self.retry_delay - time_since_check
                retry_hours = retry_remaining.total_seconds() / 3600
                return DeduplicationResult(
                    url=url,
                    decision=DeduplicationDecision.SKIP_RECENT,
                    reason=f"Failed, retry in {retry_hours:.1f}h",
                    last_check=last_check,
                    retry_count=retry_count,
                    staleness_hours=staleness_hours
                )
        
        # Check if stale
        if time_since_check >= self.staleness_threshold:
            return DeduplicationResult(
                url=url,
                decision=DeduplicationDecision.PROCESS_STALE,
                reason=f"Stale after {staleness_hours:.1f}h",
                last_check=last_check,
                retry_count=retry_count,
                staleness_hours=staleness_hours
            )
        
        # Recent and successful - skip
        return DeduplicationResult(
            url=url,
            decision=DeduplicationDecision.SKIP_RECENT,
            reason=f"Recently checked {staleness_hours:.1f}h ago",
            last_check=last_check,
            retry_count=retry_count,
            staleness_hours=staleness_hours
        )
    
    def update_configuration(self, 
                           staleness_threshold_hours: Optional[int] = None,
                           retry_limit: Optional[int] = None,
                           retry_delay_hours: Optional[int] = None) -> None:
        """
        Update deduplication configuration at runtime.
        
        Args:
            staleness_threshold_hours: New staleness threshold in hours
            retry_limit: New retry limit
            retry_delay_hours: New retry delay in hours
        """
        if staleness_threshold_hours is not None:
            self.staleness_threshold = timedelta(hours=staleness_threshold_hours)
            logger.info(f"Updated staleness threshold to {staleness_threshold_hours}h")
        
        if retry_limit is not None:
            self.retry_limit = retry_limit
            logger.info(f"Updated retry limit to {retry_limit}")
        
        if retry_delay_hours is not None:
            self.retry_delay = timedelta(hours=retry_delay_hours)
            logger.info(f"Updated retry delay to {retry_delay_hours}h")
    
    def get_configuration(self) -> Dict[str, any]:
        """
        Get current deduplication configuration.
        
        Returns:
            Dictionary with current configuration values
        """
        return {
            'staleness_threshold_hours': self.staleness_threshold.total_seconds() / 3600,
            'retry_limit': self.retry_limit,
            'retry_delay_hours': self.retry_delay.total_seconds() / 3600
        }
    
    def generate_url_hash(self, url: str) -> str:
        """
        Generate a consistent hash for a URL for tracking purposes.
        
        Args:
            url: URL to hash
            
        Returns:
            SHA-256 hash of the URL
        """
        return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]