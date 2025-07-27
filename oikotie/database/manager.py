"""
Enhanced database manager for the Oikotie automation system.

This module extends the existing database functionality with smart deduplication,
staleness detection, and automation-specific features while maintaining
compatibility with the existing scraper architecture.
"""

import json
import time
import uuid
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import duckdb
from loguru import logger

from .schema import DatabaseSchema
from .migrations import MigrationManager


@dataclass
class ListingRecord:
    """Represents a listing record with automation metadata."""
    url: str
    source: str
    city: str
    title: str
    address: Optional[str] = None
    postal_code: Optional[str] = None
    listing_type: Optional[str] = None
    price_eur: Optional[float] = None
    size_m2: Optional[float] = None
    rooms: Optional[int] = None
    year_built: Optional[int] = None
    overview: Optional[str] = None
    full_description: Optional[str] = None
    other_details_json: Optional[str] = None
    scraped_at: Optional[datetime] = None
    execution_id: Optional[str] = None
    last_check_ts: Optional[datetime] = None
    check_count: int = 0
    last_error: Optional[str] = None
    retry_count: int = 0
    data_quality_score: Optional[float] = None


@dataclass
class ExecutionMetadata:
    """Represents scraping execution metadata."""
    execution_id: str
    started_at: datetime
    city: str
    status: str = 'running'
    completed_at: Optional[datetime] = None
    listings_processed: int = 0
    listings_new: int = 0
    listings_updated: int = 0
    listings_skipped: int = 0
    listings_failed: int = 0
    execution_time_seconds: Optional[int] = None
    memory_usage_mb: Optional[int] = None
    error_summary: Optional[str] = None
    node_id: Optional[str] = None
    configuration_hash: Optional[str] = None


@dataclass
class UpsertResult:
    """Result of upsert operation with deduplication statistics."""
    total_processed: int
    new_records: int
    updated_records: int
    skipped_records: int
    failed_records: int
    errors: List[str]


@dataclass
class DataQualityReport:
    """Data quality assessment report."""
    total_listings: int
    geocoded_listings: int
    geocoding_success_rate: float
    listings_with_price: int
    price_completeness_rate: float
    listings_with_address: int
    address_completeness_rate: float
    average_quality_score: Optional[float]
    quality_distribution: Dict[str, int]


class EnhancedDatabaseManager:
    """Enhanced database manager with automation capabilities."""
    
    _instances = {}
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str = "data/real_estate.duckdb"):
        """Implement singleton pattern per database path to prevent connection conflicts."""
        with cls._lock:
            if db_path not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[db_path] = instance
            return cls._instances[db_path]
    
    def __init__(self, db_path: str = "data/real_estate.duckdb"):
        # Only initialize once per instance
        if hasattr(self, '_initialized'):
            return
            
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.schema = DatabaseSchema(str(self.db_path))
        self.migration_manager = MigrationManager(str(self.db_path))
        self._connection_lock = threading.Lock()
        
        logger.info(f"Enhanced database manager initialized: {self.db_path}")
        self._initialize_database()
        self._initialized = True
    
    def _initialize_database(self) -> None:
        """Initialize database with schema and migrations."""
        try:
            # Apply any pending migrations
            self.migration_manager.migrate_up()
            
            # Create any missing tables
            self.schema.create_all_tables()
            
            # Validate schema
            if not self.schema.validate_schema():
                raise Exception("Database schema validation failed")
                
            logger.success("Enhanced database initialized successfully")
            
        except Exception as e:
            logger.critical(f"Failed to initialize database: {e}")
            raise
    
    def get_connection(self):
        """Get a database connection for direct queries."""
        with self._connection_lock:
            return duckdb.connect(str(self.db_path))
    
    def get_stale_listings(self, staleness_threshold: timedelta = timedelta(hours=24)) -> List[ListingRecord]:
        """Get listings that need re-scraping based on staleness threshold."""
        cutoff_time = datetime.now() - staleness_threshold
        
        try:
            with duckdb.connect(str(self.db_path), read_only=True) as con:
                query = """
                    SELECT url, source, city, title, address, postal_code, listing_type,
                           price_eur, size_m2, rooms, year_built, overview, full_description,
                           other_details_json, scraped_at, execution_id, last_check_ts,
                           check_count, last_error, retry_count, data_quality_score
                    FROM listings 
                    WHERE (last_check_ts IS NULL OR last_check_ts < ?)
                      AND (deleted_ts IS NULL)
                      AND (retry_count < 3 OR last_check_ts < ?)
                    ORDER BY last_check_ts ASC NULLS FIRST, retry_count ASC
                """
                
                # Use cutoff time for both conditions
                retry_cutoff = datetime.now() - timedelta(hours=1)  # Retry failed items after 1 hour
                
                result = con.execute(query, [cutoff_time, retry_cutoff]).fetchall()
                
                listings = []
                for row in result:
                    listings.append(ListingRecord(
                        url=row[0], source=row[1], city=row[2], title=row[3],
                        address=row[4], postal_code=row[5], listing_type=row[6],
                        price_eur=row[7], size_m2=row[8], rooms=row[9], year_built=row[10],
                        overview=row[11], full_description=row[12], other_details_json=row[13],
                        scraped_at=row[14], execution_id=row[15], last_check_ts=row[16],
                        check_count=row[17], last_error=row[18], retry_count=row[19],
                        data_quality_score=row[20]
                    ))
                
                logger.info(f"Found {len(listings)} stale listings requiring re-scraping")
                return listings
                
        except Exception as e:
            logger.error(f"Failed to get stale listings: {e}")
            return []
    
    def should_skip_listing(self, url: str, staleness_threshold: timedelta = timedelta(hours=24)) -> bool:
        """Determine if a listing should be skipped based on recency."""
        cutoff_time = datetime.now() - staleness_threshold
        
        try:
            with duckdb.connect(str(self.db_path), read_only=True) as con:
                result = con.execute("""
                    SELECT last_check_ts, retry_count, deleted_ts
                    FROM listings 
                    WHERE url = ?
                """, [url]).fetchone()
                
                if not result:
                    return False  # New listing, don't skip
                
                last_check_ts, retry_count, deleted_ts = result
                
                # Don't skip if deleted
                if deleted_ts:
                    return False
                
                # Don't skip if never checked
                if not last_check_ts:
                    return False
                
                # Don't skip if stale
                if last_check_ts < cutoff_time:
                    return False
                
                # Don't skip if failed and retry limit not reached
                if retry_count > 0 and retry_count < 3:
                    retry_cutoff = datetime.now() - timedelta(hours=1)
                    if last_check_ts < retry_cutoff:
                        return False
                
                # Skip if recently checked and successful
                return True
                
        except Exception as e:
            logger.error(f"Failed to check if listing should be skipped: {e}")
            return False
    
    def upsert_with_deduplication(self, listings: List[Dict], city_name: str, execution_id: str) -> UpsertResult:
        """Insert or update listings with smart deduplication."""
        if not listings:
            logger.warning("No listings provided for upsert")
            return UpsertResult(0, 0, 0, 0, 0, [])
        
        result = UpsertResult(
            total_processed=len(listings),
            new_records=0,
            updated_records=0,
            skipped_records=0,
            failed_records=0,
            errors=[]
        )
        
        try:
            with duckdb.connect(str(self.db_path)) as con:
                con.begin()
                
                # Get existing URLs for the city
                existing_urls = set(
                    row[0] for row in con.execute(
                        "SELECT url FROM listings WHERE city = ? AND deleted_ts IS NULL", 
                        [city_name]
                    ).fetchall()
                )
                
                for listing in listings:
                    try:
                        url = listing.get('url')
                        if not url:
                            result.failed_records += 1
                            result.errors.append("Missing URL in listing")
                            continue
                        
                        # Extract and clean data
                        details = listing.get('details', {})
                        if 'error' in details:
                            result.failed_records += 1
                            result.errors.append(f"Listing error: {details.get('error')}")
                            continue
                        
                        # Calculate data quality score
                        quality_score = self._calculate_quality_score(listing, details)
                        
                        # Prepare data
                        address = details.get('sijainti')
                        postal_code = self._extract_postal_code(address) if address else None
                        
                        core_data = {
                            'price_eur': self._clean_and_convert(details.get('velaton_hinta') or details.get('myyntihinta'), 'float'),
                            'size_m2': self._clean_and_convert(details.get('asuinpinta-ala'), 'float'),
                            'rooms': self._clean_and_convert(details.get('huoneita'), 'int'),
                            'year_built': self._clean_and_convert(details.get('rakennusvuosi'), 'int'),
                        }
                        
                        # Prepare other details
                        core_keys = ['sijainti', 'rakennuksen_tyyppi', 'velaton_hinta', 'myyntihinta', 'asuinpinta-ala', 'huoneita', 'rakennusvuosi']
                        other_details = {k: v for k, v in details.items() if k not in core_keys}
                        
                        current_time = datetime.now()
                        
                        if url in existing_urls:
                            # Update existing record
                            update_params = [
                                listing.get('source'), city_name, listing.get('title'),
                                address, postal_code, details.get('rakennuksen_tyyppi'),
                                core_data['price_eur'], core_data['size_m2'], core_data['rooms'], core_data['year_built'],
                                listing.get('overview'), listing.get('full_description'),
                                json.dumps(other_details, ensure_ascii=False),
                                current_time,  # scraped_at
                                execution_id,
                                current_time,  # last_check_ts
                                quality_score,
                                url
                            ]
                            
                            con.execute("""
                                UPDATE listings 
                                SET source=?, city=?, title=?, address=?, postal_code=?, listing_type=?, 
                                    price_eur=?, size_m2=?, rooms=?, year_built=?, overview=?, 
                                    full_description=?, other_details_json=?, scraped_at=?,
                                    execution_id=?, last_check_ts=?, check_count=check_count+1,
                                    data_quality_score=?, updated_ts=CURRENT_TIMESTAMP, deleted_ts=NULL,
                                    last_error=NULL, retry_count=0
                                WHERE url=?
                            """, update_params)
                            
                            result.updated_records += 1
                            
                        else:
                            # Insert new record
                            insert_params = [
                                listing.get('source'), city_name, listing.get('title'),
                                address, postal_code, details.get('rakennuksen_tyyppi'),
                                core_data['price_eur'], core_data['size_m2'], core_data['rooms'], core_data['year_built'],
                                listing.get('overview'), listing.get('full_description'),
                                json.dumps(other_details, ensure_ascii=False),
                                current_time,  # scraped_at
                                url, execution_id, current_time,  # last_check_ts
                                1,  # check_count
                                quality_score
                            ]
                            
                            con.execute("""
                                INSERT INTO listings (
                                    source, city, title, address, postal_code, listing_type, 
                                    price_eur, size_m2, rooms, year_built, overview, 
                                    full_description, other_details_json, scraped_at, url,
                                    execution_id, last_check_ts, check_count, data_quality_score,
                                    insert_ts
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """, insert_params)
                            
                            result.new_records += 1
                    
                    except Exception as e:
                        result.failed_records += 1
                        result.errors.append(f"Failed to process listing {listing.get('url', 'unknown')}: {str(e)}")
                        logger.error(f"Failed to process listing: {e}")
                
                con.commit()
                logger.success(f"Upsert completed: {result.new_records} new, {result.updated_records} updated, {result.failed_records} failed")
                
        except Exception as e:
            logger.error(f"Upsert operation failed: {e}")
            result.errors.append(f"Database operation failed: {str(e)}")
            
        return result
    
    def track_execution_metadata(self, metadata: ExecutionMetadata) -> None:
        """Track scraping execution metadata."""
        try:
            with duckdb.connect(str(self.db_path)) as con:
                con.execute("""
                    INSERT OR REPLACE INTO scraping_executions (
                        execution_id, started_at, completed_at, status, city,
                        listings_processed, listings_new, listings_updated, 
                        listings_skipped, listings_failed, execution_time_seconds,
                        memory_usage_mb, error_summary, node_id, configuration_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    metadata.execution_id, metadata.started_at, metadata.completed_at,
                    metadata.status, metadata.city, metadata.listings_processed,
                    metadata.listings_new, metadata.listings_updated, metadata.listings_skipped,
                    metadata.listings_failed, metadata.execution_time_seconds,
                    metadata.memory_usage_mb, metadata.error_summary, metadata.node_id,
                    metadata.configuration_hash
                ])
                
        except Exception as e:
            logger.error(f"Failed to track execution metadata: {e}")
    
    def get_data_quality_metrics(self) -> DataQualityReport:
        """Generate comprehensive data quality assessment."""
        try:
            with duckdb.connect(str(self.db_path), read_only=True) as con:
                # Get basic counts
                total_result = con.execute("SELECT COUNT(*) FROM listings WHERE deleted_ts IS NULL").fetchone()
                total_listings = total_result[0] if total_result else 0
                
                if total_listings == 0:
                    return DataQualityReport(0, 0, 0.0, 0, 0.0, 0, 0.0, None, {})
                
                # Get geocoded listings count
                geocoded_result = con.execute("""
                    SELECT COUNT(*) FROM listings 
                    WHERE deleted_ts IS NULL AND address IS NOT NULL AND address != ''
                """).fetchone()
                geocoded_listings = geocoded_result[0] if geocoded_result else 0
                
                # Get listings with price
                price_result = con.execute("""
                    SELECT COUNT(*) FROM listings 
                    WHERE deleted_ts IS NULL AND price_eur IS NOT NULL AND price_eur > 0
                """).fetchone()
                listings_with_price = price_result[0] if price_result else 0
                
                # Get listings with address
                address_result = con.execute("""
                    SELECT COUNT(*) FROM listings 
                    WHERE deleted_ts IS NULL AND address IS NOT NULL AND address != ''
                """).fetchone()
                listings_with_address = address_result[0] if address_result else 0
                
                # Get average quality score
                quality_result = con.execute("""
                    SELECT AVG(data_quality_score) FROM listings 
                    WHERE deleted_ts IS NULL AND data_quality_score IS NOT NULL
                """).fetchone()
                average_quality_score = quality_result[0] if quality_result and quality_result[0] else None
                
                # Get quality distribution
                distribution_result = con.execute("""
                    SELECT 
                        CASE 
                            WHEN data_quality_score >= 0.8 THEN 'High'
                            WHEN data_quality_score >= 0.6 THEN 'Medium'
                            WHEN data_quality_score >= 0.4 THEN 'Low'
                            ELSE 'Very Low'
                        END as quality_level,
                        COUNT(*) as count
                    FROM listings 
                    WHERE deleted_ts IS NULL AND data_quality_score IS NOT NULL
                    GROUP BY quality_level
                """).fetchall()
                
                quality_distribution = {row[0]: row[1] for row in distribution_result}
                
                return DataQualityReport(
                    total_listings=total_listings,
                    geocoded_listings=geocoded_listings,
                    geocoding_success_rate=geocoded_listings / total_listings if total_listings > 0 else 0.0,
                    listings_with_price=listings_with_price,
                    price_completeness_rate=listings_with_price / total_listings if total_listings > 0 else 0.0,
                    listings_with_address=listings_with_address,
                    address_completeness_rate=listings_with_address / total_listings if total_listings > 0 else 0.0,
                    average_quality_score=average_quality_score,
                    quality_distribution=quality_distribution
                )
                
        except Exception as e:
            logger.error(f"Failed to generate data quality metrics: {e}")
            return DataQualityReport(0, 0, 0.0, 0, 0.0, 0, 0.0, None, {})
    
    def cleanup_old_data(self, retention_days: int = 90) -> Dict[str, int]:
        """Clean up old data based on retention policy."""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cleanup_stats = {}
        
        try:
            with duckdb.connect(str(self.db_path)) as con:
                # Clean up old execution records
                result = con.execute("""
                    DELETE FROM scraping_executions 
                    WHERE started_at < ? AND status IN ('completed', 'failed')
                """, [cutoff_date])
                cleanup_stats['executions_deleted'] = result.rowcount if hasattr(result, 'rowcount') else 0
                
                # Clean up old API usage logs
                result = con.execute("""
                    DELETE FROM api_usage_log 
                    WHERE request_timestamp < ?
                """, [cutoff_date])
                cleanup_stats['api_logs_deleted'] = result.rowcount if hasattr(result, 'rowcount') else 0
                
                # Clean up old data lineage records
                result = con.execute("""
                    DELETE FROM data_lineage 
                    WHERE fetch_timestamp < ?
                """, [cutoff_date])
                cleanup_stats['lineage_deleted'] = result.rowcount if hasattr(result, 'rowcount') else 0
                
                logger.info(f"Data cleanup completed: {cleanup_stats}")
                
        except Exception as e:
            logger.error(f"Data cleanup failed: {e}")
            cleanup_stats['error'] = str(e)
        
        return cleanup_stats
    
    def _calculate_quality_score(self, listing: Dict, details: Dict) -> float:
        """Calculate data quality score for a listing."""
        score = 0.0
        max_score = 0.0
        
        # Check required fields
        if listing.get('title'):
            score += 0.2
        max_score += 0.2
        
        if details.get('sijainti'):
            score += 0.2
        max_score += 0.2
        
        if details.get('velaton_hinta') or details.get('myyntihinta'):
            score += 0.2
        max_score += 0.2
        
        if details.get('asuinpinta-ala'):
            score += 0.15
        max_score += 0.15
        
        if details.get('huoneita'):
            score += 0.1
        max_score += 0.1
        
        if details.get('rakennusvuosi'):
            score += 0.1
        max_score += 0.1
        
        if listing.get('overview'):
            score += 0.05
        max_score += 0.05
        
        return score / max_score if max_score > 0 else 0.0
    
    def _clean_and_convert(self, value_str: str, target_type: str) -> Optional[Any]:
        """Clean and convert string values to appropriate types."""
        if not value_str:
            return None
        
        try:
            # Remove thousands separators and find first number
            cleaned_str = value_str.replace('\u00a0', '').replace(' ', '')
            import re
            match = re.search(r'[\d,.]+', cleaned_str)
            if not match:
                return None
            
            # Convert comma to dot for float conversion
            num_str = match.group(0).replace(',', '.')
            
            if target_type == 'float':
                return float(num_str)
            elif target_type == 'int':
                return int(float(num_str))
            else:
                return num_str
                
        except (ValueError, TypeError):
            return None
    
    def _extract_postal_code(self, address: str) -> Optional[str]:
        """Extract postal code from address string."""
        if not address:
            return None
        
        import re
        # Finnish postal codes are 5 digits
        match = re.search(r'\b\d{5}\b', address)
        return match.group(0) if match else None
    
    def get_execution_history(self, city: Optional[str] = None, limit: int = 50) -> List[ExecutionMetadata]:
        """Get execution history with optional city filter."""
        try:
            with duckdb.connect(str(self.db_path), read_only=True) as con:
                query = """
                    SELECT execution_id, started_at, completed_at, status, city,
                           listings_processed, listings_new, listings_updated,
                           listings_skipped, listings_failed, execution_time_seconds,
                           memory_usage_mb, error_summary, node_id, configuration_hash
                    FROM scraping_executions
                """
                params = []
                
                if city:
                    query += " WHERE city = ?"
                    params.append(city)
                
                query += " ORDER BY started_at DESC LIMIT ?"
                params.append(limit)
                
                result = con.execute(query, params).fetchall()
                
                executions = []
                for row in result:
                    executions.append(ExecutionMetadata(
                        execution_id=row[0],
                        started_at=row[1],
                        completed_at=row[2],
                        status=row[3],
                        city=row[4],
                        listings_processed=row[5] or 0,
                        listings_new=row[6] or 0,
                        listings_updated=row[7] or 0,
                        listings_skipped=row[8] or 0,
                        listings_failed=row[9] or 0,
                        execution_time_seconds=row[10],
                        memory_usage_mb=row[11],
                        error_summary=row[12],
                        node_id=row[13],
                        configuration_hash=row[14]
                    ))
                
                return executions
                
        except Exception as e:
            logger.error(f"Failed to get execution history: {e}")
            return []
    
    def get_latest_execution(self, city: str, report_date: datetime) -> Optional[Dict[str, Any]]:
        """Get the latest execution for a city on or before the report date."""
        try:
            with duckdb.connect(str(self.db_path), read_only=True) as con:
                result = con.execute("""
                    SELECT execution_id, started_at, completed_at, status, city,
                           listings_processed, listings_new, listings_updated,
                           listings_skipped, listings_failed, execution_time_seconds,
                           memory_usage_mb, error_summary
                    FROM scraping_executions
                    WHERE city = ? AND DATE(started_at) <= DATE(?)
                    ORDER BY started_at DESC
                    LIMIT 1
                """, [city, report_date]).fetchone()
                
                if result:
                    return {
                        'execution_id': result[0],
                        'started_at': result[1],
                        'completed_at': result[2],
                        'status': result[3],
                        'city': result[4],
                        'listings_processed': result[5] or 0,
                        'listings_new': result[6] or 0,
                        'listings_updated': result[7] or 0,
                        'listings_skipped': result[8] or 0,
                        'listings_failed': result[9] or 0,
                        'execution_time_seconds': result[10],
                        'memory_usage_mb': result[11],
                        'error_summary': result[12]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to get latest execution for {city}: {e}")
            return None
    
    def get_data_quality_metrics(self, city: str, execution_id: str) -> Dict[str, Any]:
        """Get data quality metrics for a specific city and execution."""
        try:
            with duckdb.connect(str(self.db_path), read_only=True) as con:
                # Get total addresses for the city
                total_result = con.execute("""
                    SELECT COUNT(*) FROM listings 
                    WHERE city = ? AND deleted_ts IS NULL
                """, [city]).fetchone()
                total_addresses = total_result[0] if total_result else 0
                
                # Get geocoded addresses
                geocoded_result = con.execute("""
                    SELECT COUNT(*) FROM listings 
                    WHERE city = ? AND deleted_ts IS NULL 
                    AND address IS NOT NULL AND address != ''
                """, [city]).fetchone()
                geocoded_addresses = geocoded_result[0] if geocoded_result else 0
                
                # Get complete listings (with all major fields)
                complete_result = con.execute("""
                    SELECT COUNT(*) FROM listings 
                    WHERE city = ? AND deleted_ts IS NULL 
                    AND address IS NOT NULL AND price_eur IS NOT NULL 
                    AND size_m2 IS NOT NULL AND rooms IS NOT NULL
                """, [city]).fetchone()
                complete_listings = complete_result[0] if complete_result else 0
                
                # Get validation errors (simplified - would need error tracking)
                validation_errors = []
                
                # Get duplicate count (simplified)
                duplicate_result = con.execute("""
                    SELECT COUNT(*) - COUNT(DISTINCT url) FROM listings 
                    WHERE city = ? AND deleted_ts IS NULL
                """, [city]).fetchone()
                duplicate_listings = max(0, duplicate_result[0] if duplicate_result else 0)
                
                # Get spatial matches (would need spatial data integration)
                spatial_matches = geocoded_addresses  # Simplified assumption
                
                return {
                    'total_addresses': total_addresses,
                    'geocoded_addresses': geocoded_addresses,
                    'complete_listings': complete_listings,
                    'incomplete_listings': total_addresses - complete_listings,
                    'valid_listings': complete_listings,  # Simplified
                    'invalid_listings': 0,  # Would need validation tracking
                    'duplicate_listings': duplicate_listings,
                    'spatial_matches': spatial_matches,
                    'validation_errors': validation_errors
                }
                
        except Exception as e:
            logger.error(f"Failed to get data quality metrics for {city}: {e}")
            return {
                'total_addresses': 0,
                'geocoded_addresses': 0,
                'complete_listings': 0,
                'incomplete_listings': 0,
                'valid_listings': 0,
                'invalid_listings': 0,
                'duplicate_listings': 0,
                'spatial_matches': 0,
                'validation_errors': []
            }
    
    def get_execution_errors(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get error logs for a specific execution."""
        # This is a simplified implementation
        # In a full system, this would query a separate error log table
        try:
            with duckdb.connect(str(self.db_path), read_only=True) as con:
                result = con.execute("""
                    SELECT error_summary FROM scraping_executions 
                    WHERE execution_id = ? AND error_summary IS NOT NULL
                """, [execution_id]).fetchone()
                
                if result and result[0]:
                    # Parse error summary into structured format
                    return [{
                        'message': result[0],
                        'level': 'ERROR',
                        'timestamp': datetime.now().isoformat()
                    }]
                
                return []
                
        except Exception as e:
            logger.error(f"Failed to get execution errors: {e}")
            return []
    
    def get_execution_history_by_date_range(self, city: str, start_date: datetime = None, end_date: datetime = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history for a city within a date range."""
        try:
            with duckdb.connect(str(self.db_path), read_only=True) as con:
                # Build query based on provided parameters
                query = """
                    SELECT execution_id, started_at, completed_at, status,
                           listings_processed, listings_new, listings_failed,
                           execution_time_seconds, memory_usage_mb
                    FROM scraping_executions
                    WHERE city = ?
                """
                params = [city]
                
                if start_date:
                    query += " AND started_at >= ?"
                    params.append(start_date)
                
                if end_date:
                    query += " AND started_at <= ?"
                    params.append(end_date)
                
                query += " ORDER BY started_at DESC"
                
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                
                result = con.execute(query, params).fetchall()
                
                executions = []
                for row in result:
                    processed = row[4] or 0
                    failed = row[6] or 0
                    success_rate = (processed - failed) / processed if processed > 0 else 0
                    error_rate = failed / processed if processed > 0 else 0
                    
                    executions.append({
                        'execution_id': row[0],
                        'started_at': row[1],
                        'completed_at': row[2],
                        'status': row[3],
                        'listings_processed': processed,
                        'listings_new': row[5] or 0,
                        'listings_failed': failed,
                        'execution_time_seconds': row[7] or 0,
                        'memory_usage_mb': row[8] or 0,
                        'success_rate': success_rate,
                        'error_rate': error_rate,
                        'data_quality_score': 0.9  # Simplified - would calculate from data
                    })
                
                return executions
                
        except Exception as e:
            logger.error(f"Failed to get execution history for {city}: {e}")
            return []