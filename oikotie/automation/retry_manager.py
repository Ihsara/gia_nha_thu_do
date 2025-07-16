"""
Retry management system for the Oikotie automation platform.

This module provides exponential backoff retry mechanisms, failure tracking,
and intelligent retry strategies for failed scraping operations.
"""

import math
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from ..database.manager import EnhancedDatabaseManager


class RetryStrategy(Enum):
    """Enumeration of retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


class FailureCategory(Enum):
    """Enumeration of failure categories."""
    NETWORK_ERROR = "network_error"
    PARSING_ERROR = "parsing_error"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class RetryAttempt:
    """Represents a retry attempt."""
    url: str
    attempt_number: int
    scheduled_time: datetime
    failure_category: FailureCategory
    error_message: str
    delay_seconds: int


@dataclass
class RetryConfiguration:
    """Configuration for retry behavior."""
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    max_attempts: int = 3
    base_delay_seconds: int = 60
    max_delay_seconds: int = 3600
    jitter_factor: float = 0.1
    backoff_multiplier: float = 2.0


class RetryManager:
    """Manages retry logic with exponential backoff and failure categorization."""
    
    def __init__(self, 
                 db_manager: EnhancedDatabaseManager,
                 config: Optional[RetryConfiguration] = None):
        """
        Initialize retry manager.
        
        Args:
            db_manager: Enhanced database manager instance
            config: Retry configuration (uses defaults if not provided)
        """
        self.db_manager = db_manager
        self.config = config or RetryConfiguration()
        
        logger.info(f"Retry manager initialized: "
                   f"strategy={self.config.strategy.value}, "
                   f"max_attempts={self.config.max_attempts}, "
                   f"base_delay={self.config.base_delay_seconds}s")
    
    def should_retry(self, url: str, error: Exception, attempt_number: int) -> bool:
        """
        Determine if a failed URL should be retried.
        
        Args:
            url: URL that failed
            error: Exception that occurred
            attempt_number: Current attempt number (1-based)
            
        Returns:
            True if should retry, False otherwise
        """
        # Check if we've exceeded max attempts
        if attempt_number >= self.config.max_attempts:
            logger.info(f"URL {url} exceeded max retry attempts ({self.config.max_attempts})")
            return False
        
        # Categorize the failure
        failure_category = self._categorize_failure(error)
        
        # Some failures should not be retried
        if failure_category in [FailureCategory.PARSING_ERROR]:
            logger.info(f"URL {url} has non-retryable failure: {failure_category.value}")
            return False
        
        # Rate limits should be retried with longer delays
        if failure_category == FailureCategory.RATE_LIMIT:
            logger.info(f"URL {url} hit rate limit, will retry with extended delay")
            return True
        
        # Network and server errors are generally retryable
        if failure_category in [FailureCategory.NETWORK_ERROR, FailureCategory.SERVER_ERROR, FailureCategory.TIMEOUT]:
            logger.info(f"URL {url} has retryable failure: {failure_category.value}")
            return True
        
        # Default to retry for unknown errors
        logger.info(f"URL {url} has unknown failure, will retry")
        return True
    
    def calculate_retry_delay(self, 
                             url: str, 
                             error: Exception, 
                             attempt_number: int) -> int:
        """
        Calculate delay before next retry attempt.
        
        Args:
            url: URL that failed
            error: Exception that occurred
            attempt_number: Current attempt number (1-based)
            
        Returns:
            Delay in seconds before next retry
        """
        failure_category = self._categorize_failure(error)
        
        # Base delay calculation based on strategy
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay_seconds * (self.config.backoff_multiplier ** (attempt_number - 1))
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay_seconds * attempt_number
        elif self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay_seconds
        else:  # IMMEDIATE
            delay = 0
        
        # Apply category-specific adjustments
        if failure_category == FailureCategory.RATE_LIMIT:
            delay *= 3  # Triple delay for rate limits
        elif failure_category == FailureCategory.SERVER_ERROR:
            delay *= 2  # Double delay for server errors
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay_seconds)
        
        # Add jitter to avoid thundering herd
        if self.config.jitter_factor > 0:
            jitter = delay * self.config.jitter_factor * random.random()
            delay += jitter
        
        delay_int = int(delay)
        logger.debug(f"Calculated retry delay for {url}: {delay_int}s "
                    f"(attempt {attempt_number}, category {failure_category.value})")
        
        return delay_int
    
    def schedule_retry(self, 
                      url: str, 
                      error: Exception, 
                      attempt_number: int,
                      execution_id: str) -> Optional[RetryAttempt]:
        """
        Schedule a retry attempt for a failed URL.
        
        Args:
            url: URL that failed
            error: Exception that occurred
            attempt_number: Current attempt number (1-based)
            execution_id: Execution ID for tracking
            
        Returns:
            RetryAttempt if scheduled, None if should not retry
        """
        if not self.should_retry(url, error, attempt_number):
            return None
        
        delay_seconds = self.calculate_retry_delay(url, error, attempt_number)
        scheduled_time = datetime.now() + timedelta(seconds=delay_seconds)
        failure_category = self._categorize_failure(error)
        
        retry_attempt = RetryAttempt(
            url=url,
            attempt_number=attempt_number,
            scheduled_time=scheduled_time,
            failure_category=failure_category,
            error_message=str(error),
            delay_seconds=delay_seconds
        )
        
        # Update database with retry information
        self._update_retry_metadata(url, retry_attempt, execution_id)
        
        logger.info(f"Scheduled retry for {url}: attempt {attempt_number} "
                   f"in {delay_seconds}s at {scheduled_time}")
        
        return retry_attempt
    
    def get_ready_retries(self, city: Optional[str] = None) -> List[str]:
        """
        Get URLs that are ready for retry based on their scheduled time.
        
        Args:
            city: Optional city filter
            
        Returns:
            List of URLs ready for retry
        """
        try:
            import duckdb
            current_time = datetime.now()
            
            with duckdb.connect(str(self.db_manager.db_path), read_only=True) as con:
                query = """
                    SELECT url
                    FROM listings 
                    WHERE retry_count > 0 
                      AND retry_count < ?
                      AND last_error IS NOT NULL
                      AND deleted_ts IS NULL
                      AND (last_check_ts IS NULL OR last_check_ts <= ?)
                """
                params = [self.config.max_attempts, current_time]
                
                if city:
                    query += " AND city = ?"
                    params.append(city)
                
                query += " ORDER BY last_check_ts ASC NULLS FIRST LIMIT 100"
                
                result = con.execute(query, params).fetchall()
                ready_urls = [row[0] for row in result]
                
                logger.info(f"Found {len(ready_urls)} URLs ready for retry")
                return ready_urls
                
        except Exception as e:
            logger.error(f"Failed to get ready retries: {e}")
            return []
    
    def get_retry_statistics(self, 
                           city: Optional[str] = None,
                           hours_back: int = 24) -> Dict[str, any]:
        """
        Get retry statistics for monitoring and optimization.
        
        Args:
            city: Optional city filter
            hours_back: Hours of history to analyze
            
        Returns:
            Dictionary with retry statistics
        """
        try:
            import duckdb
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            with duckdb.connect(str(self.db_manager.db_path), read_only=True) as con:
                # Base query
                base_query = """
                    FROM listings 
                    WHERE last_check_ts >= ?
                      AND deleted_ts IS NULL
                """
                params = [cutoff_time]
                
                if city:
                    base_query += " AND city = ?"
                    params.append(city)
                
                # Get total listings
                total_result = con.execute(f"SELECT COUNT(*) {base_query}", params).fetchone()
                total_listings = total_result[0] if total_result else 0
                
                # Get retry statistics
                retry_result = con.execute(f"""
                    SELECT 
                        COUNT(*) as total_retries,
                        AVG(retry_count) as avg_retry_count,
                        MAX(retry_count) as max_retry_count,
                        COUNT(CASE WHEN retry_count >= ? THEN 1 END) as max_attempts_reached
                    {base_query} AND retry_count > 0
                """, [self.config.max_attempts] + params).fetchone()
                
                if retry_result:
                    total_retries, avg_retry_count, max_retry_count, max_attempts_reached = retry_result
                else:
                    total_retries = avg_retry_count = max_retry_count = max_attempts_reached = 0
                
                # Get failure categories (simplified - would need error categorization in DB)
                error_result = con.execute(f"""
                    SELECT COUNT(*) as total_errors
                    {base_query} AND last_error IS NOT NULL
                """, params).fetchone()
                
                total_errors = error_result[0] if error_result else 0
                
                stats = {
                    'total_listings': total_listings,
                    'total_retries': total_retries or 0,
                    'total_errors': total_errors or 0,
                    'retry_rate': (total_retries / total_listings) if total_listings > 0 else 0.0,
                    'error_rate': (total_errors / total_listings) if total_listings > 0 else 0.0,
                    'average_retry_count': float(avg_retry_count or 0),
                    'max_retry_count': int(max_retry_count or 0),
                    'max_attempts_reached': int(max_attempts_reached or 0),
                    'time_window_hours': hours_back,
                    'config': {
                        'strategy': self.config.strategy.value,
                        'max_attempts': self.config.max_attempts,
                        'base_delay_seconds': self.config.base_delay_seconds
                    }
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get retry statistics: {e}")
            return {}
    
    def reset_retry_count(self, url: str) -> bool:
        """
        Reset retry count for a URL (e.g., after successful processing).
        
        Args:
            url: URL to reset
            
        Returns:
            True if reset successfully, False otherwise
        """
        try:
            import duckdb
            
            with duckdb.connect(str(self.db_manager.db_path)) as con:
                con.execute("""
                    UPDATE listings 
                    SET retry_count = 0, last_error = NULL
                    WHERE url = ?
                """, [url])
                
                logger.debug(f"Reset retry count for {url}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to reset retry count for {url}: {e}")
            return False
    
    def _categorize_failure(self, error: Exception) -> FailureCategory:
        """
        Categorize a failure based on the exception type and message.
        
        Args:
            error: Exception that occurred
            
        Returns:
            FailureCategory for the error
        """
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Network-related errors
        if any(keyword in error_str for keyword in ['connection', 'network', 'dns', 'socket']):
            return FailureCategory.NETWORK_ERROR
        
        if any(keyword in error_type for keyword in ['connection', 'network', 'socket']):
            return FailureCategory.NETWORK_ERROR
        
        # Timeout errors
        if any(keyword in error_str for keyword in ['timeout', 'timed out']):
            return FailureCategory.TIMEOUT
        
        if 'timeout' in error_type:
            return FailureCategory.TIMEOUT
        
        # Rate limiting
        if any(keyword in error_str for keyword in ['rate limit', 'too many requests', '429']):
            return FailureCategory.RATE_LIMIT
        
        # Server errors
        if any(keyword in error_str for keyword in ['500', '502', '503', '504', 'server error']):
            return FailureCategory.SERVER_ERROR
        
        # Parsing errors
        if any(keyword in error_str for keyword in ['parse', 'parsing', 'invalid html', 'malformed']):
            return FailureCategory.PARSING_ERROR
        
        if any(keyword in error_type for keyword in ['parse', 'html', 'xml']):
            return FailureCategory.PARSING_ERROR
        
        # Default to unknown
        return FailureCategory.UNKNOWN
    
    def _update_retry_metadata(self, 
                              url: str, 
                              retry_attempt: RetryAttempt,
                              execution_id: str) -> None:
        """
        Update database with retry metadata.
        
        Args:
            url: URL being retried
            retry_attempt: Retry attempt information
            execution_id: Execution ID for tracking
        """
        try:
            import duckdb
            
            with duckdb.connect(str(self.db_manager.db_path)) as con:
                con.execute("""
                    UPDATE listings 
                    SET retry_count = ?,
                        last_error = ?,
                        last_check_ts = ?,
                        execution_id = ?
                    WHERE url = ?
                """, [
                    retry_attempt.attempt_number,
                    retry_attempt.error_message,
                    datetime.now(),
                    execution_id,
                    url
                ])
                
        except Exception as e:
            logger.error(f"Failed to update retry metadata for {url}: {e}")
    
    def update_configuration(self, config: RetryConfiguration) -> None:
        """
        Update retry configuration at runtime.
        
        Args:
            config: New retry configuration
        """
        self.config = config
        logger.info(f"Updated retry configuration: "
                   f"strategy={config.strategy.value}, "
                   f"max_attempts={config.max_attempts}")
    
    def get_configuration(self) -> RetryConfiguration:
        """
        Get current retry configuration.
        
        Returns:
            Current retry configuration
        """
        return self.config